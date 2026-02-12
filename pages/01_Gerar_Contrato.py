import streamlit as st
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.database.repo_contratos import ContratoRepository
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.storage import StorageService
from src.utils.email_sender import enviar_email_contrato

# --- FUNÇÃO AUXILIAR PARA DATA POR EXTENSO ---
def obter_mes_extenso(dt):
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    return meses[dt.month]

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}

    # --- PASSO 1 E 2 (MANTIDOS CONFORME SEU CÓDIGO) ---
    if st.session_state.step == 1:
        st.subheader("Etapa 1: Selecionar Aluno")
        busca = st.text_input("Buscar Aluno por Nome ou CPF")
        if busca:
            alunos = AlunoRepository.buscar_por_cpf(busca) if any(c.isdigit() for c in busca) else AlunoRepository.filtrar_por_nome(busca)
            if alunos:
                for a in (alunos if isinstance(alunos, list) else [alunos]):
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{a.get('nome_completo')}**")
                        if c2.button("Selecionar", key=f"sel_{a['id']}"):
                            st.session_state.form_data['aluno'] = a
                            st.session_state.step = 2
                            st.rerun()

    elif st.session_state.step == 2:
        st.subheader("Etapa 2: Curso e Turma")
        aluno = st.session_state.form_data.get('aluno', {})
        st.info(f"👤 Aluno: {aluno.get('nome_completo')}")
        
        cursos = CursoRepository.listar_todos_com_turmas()
        map_cursos = {c['nome']: c for c in cursos}
        sel_curso = st.selectbox("Selecione o Curso", [""] + list(map_cursos.keys()))
        
        if sel_curso:
            curso_dados = map_cursos[sel_curso]
            turmas = curso_dados.get('turmas', [])
            if turmas:
                map_turmas = {f"{t['codigo_turma']} ({t.get('formato','-')})": t for t in turmas}
                sel_turma = st.selectbox("Selecione a Turma", list(map_turmas.keys()))
                if st.button("Avançar"):
                    st.session_state.form_data['curso'] = curso_dados
                    st.session_state.form_data['turma'] = map_turmas[sel_turma]
                    st.session_state.step = 3
                    st.rerun()

    # --- PASSO 3: FINANCEIRO (ATUALIZADO COM REATIVIDADE E TABELAS) ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
        # 1. CÁLCULO DE VALORES E DESTAQUE DO MATERIAL (Melhoria Visual)
        valor_bruto = float(curso.get('valor_bruto', 0))
        valor_material_calc = round(valor_bruto * 0.30, 2)
        
        st.markdown(f"""
        <div style="background-color: #f0f9ff; padding: 15px; border-radius: 8px; border-left: 5px solid #0ea5e9; margin-bottom: 20px;">
            <h4 style="margin:0; color: #0369a1;">📚 Detalhamento do Produto</h4>
            <p style="margin:5px 0 0 0; font-size: 14px;">Valor Bruto do Curso: <b>{format_currency(valor_bruto)}</b></p>
            <p style="margin:2px 0 0 0; font-size: 14px; color: #0c4a6e;">
                Valor destinado ao Material Didático: <b>{format_currency(valor_material_calc)}</b> (30% conforme Cláusula 13ª).
            </p>
        </div>
        """, unsafe_allow_html=True)

        percent_desc = st.number_input("Desconto Comercial (%)", 0.0, 100.0, 0.0, step=0.5)
        valor_desconto = round(valor_bruto * (percent_desc / 100), 2)
        valor_final = round(valor_bruto - valor_desconto, 2)

        st.success(f"### Valor Final do Contrato: {format_currency(valor_final)}")
        st.divider()

        # 2. ENTRADA
        st.markdown("#### 1. Pagamento de Entrada / À Vista")
        ce1, ce2 = st.columns(2)
        v_entrada_total = ce1.number_input("Valor Total da Entrada", 0.0, valor_final, 0.0)
        q_entrada = ce2.selectbox("Qtd. Parcelas Entrada", [1, 2, 3])
        
        lista_entrada = []
        opcoes_pagamento = ["PIX", "Cartão de Crédito", "Boleto", "Transferência"]
        data_ultima_entrada = date.today()

        if v_entrada_total > 0:
            v_unit_ent = round(v_entrada_total / q_entrada, 2)
            for i in range(q_entrada):
                # Ajuste para a última parcela da entrada (evitar erro de centavos)
                if i == q_entrada - 1:
                    v_p_sugerido = round(v_entrada_total - (v_unit_ent * (q_entrada - 1)), 2)
                else:
                    v_p_sugerido = v_unit_ent

                with st.container(border=True):
                    c_e1, c_e2, c_e3 = st.columns(3)
                    v_p = c_e1.number_input(f"Valor P{i+1}", value=v_p_sugerido, key=f"vent_{i}")
                    d_p = c_e2.date_input(f"Vencimento P{i+1}", value=date.today() + relativedelta(days=i*2), key=f"dent_{i}")
                    f_p = c_e3.selectbox(f"Forma P{i+1}", opcoes_pagamento, key=f"fent_{i}")
                    
                    lista_entrada.append({
                        "numero": i+1, 
                        "data": d_p.strftime("%d/%m/%Y"), 
                        "valor": format_currency(v_p), 
                        "forma": f_p,
                        "valor_num": v_p # Usado para cálculo interno
                    })
                    data_ultima_entrada = d_p

        # 3. SALDO REMANESCENTE (CÁLCULO E EXIBIÇÃO DA LISTA)
        saldo_restante = round(valor_final - v_entrada_total, 2)
        lista_saldo = []
        
        if saldo_restante > 0:
            st.divider()
            st.markdown(f"#### 2. Saldo Remanescente: {format_currency(saldo_restante)}")
            
            cs1, cs2, cs3 = st.columns(3)
            q_saldo = cs1.number_input("Qtd Parcelas Saldo", 1, 36, 12)
            d_saldo_ini = cs2.date_input("1º Vencimento Saldo", value=data_ultima_entrada + relativedelta(months=1))
            f_saldo = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão de Crédito", "PIX"])
            
            # Cálculo com ajuste de centavos
            valor_base_saldo = round(saldo_restante / q_saldo, 2)
            soma_acumulada_saldo = 0
            
            for i in range(q_saldo):
                if i == q_saldo - 1:
                    v_parc = round(saldo_restante - soma_acumulada_saldo, 2)
                else:
                    v_parc = valor_base_saldo
                
                soma_acumulada_saldo += v_parc
                venc_p = d_saldo_ini + relativedelta(months=i)
                
                lista_saldo.append({
                    "Parcela": f"{i+1}/{q_saldo}",
                    "Vencimento": venc_p.strftime("%d/%m/%Y"),
                    "Valor": format_currency(v_parc),
                    "Forma": f_saldo,
                    "valor_num": v_parc
                })

            # EXIBIÇÃO DA TABELA DE SALDO (O que foi solicitado)
            st.dataframe(lista_saldo, column_order=("Parcela", "Vencimento", "Valor", "Forma"), 
                         use_container_width=True, hide_index=True)

        # 4. VALIDAÇÃO DE TRAVA FINANCEIRA
        soma_entrada = sum(p['valor_num'] for p in lista_entrada)
        soma_saldo = sum(p['valor_num'] for p in lista_saldo)
        total_pactuado = round(soma_entrada + soma_saldo, 2)
        
        conferido = abs(total_pactuado - valor_final) < 0.01

        st.divider()
        if not conferido:
            st.error(f"❌ Erro matemático: A soma das parcelas ({format_currency(total_pactuado)}) não fecha com o total ({format_currency(valor_final)}).")
        else:
            st.success("✅ Conciliação financeira aprovada.")
        
        c_b1, c_b2 = st.columns([1, 4])
        if c_b1.button("Voltar"): st.session_state.step = 2; st.rerun()
        
        if c_b2.button("🚀 Gerar Contrato", type="primary", disabled=not conferido, use_container_width=True):
            with st.spinner("Processando Documento..."):
                token = str(uuid.uuid4())
                agora = datetime.now()
                
                # Contexto para as tags do Word (Baseado no seu modelo_contrato_V2.docx)
                ctx_doc = {
                    'nome': aluno['nome_completo'].upper(),
                    'cpf': format_cpf(aluno['cpf']),
                    'email': aluno.get('email', ''),
                    'crm': aluno.get('crm', ''),
                    'logradouro': aluno.get('logradouro', ''),
                    'numero': aluno.get('numero', ''),
                    'bairro': aluno.get('bairro', ''),
                    'cidade': aluno.get('cidade', ''),
                    'uf': aluno.get('uf', ''),
                    'pos_graduacao': curso['nome'],
                    'turma': st.session_state.form_data['turma']['codigo_turma'],
                    'valor_curso': format_currency(valor_bruto),
                    'valor_desconto': format_currency(valor_desconto),
                    'pencentual_desconto': f"{percent_desc}%",
                    'valor_final': format_currency(valor_final),
                    'valor_material': format_currency(valor_material_calc), # Para Cláusula 13ª
                    'dia': agora.day,
                    'mês': obter_mes_extenso(agora),
                    'ano': agora.year
                }

                # Execução do motor de PDF
                processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                # Importante: lista_entrada e lista_saldo devem conter dicionários com chaves compatíveis com as tabelas do Word
                docx_buffer = processor.generate_docx(ctx_doc, lista_entrada, lista_saldo)
                pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                
                path_s, _ = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                
                novo_contrato = {
                    "aluno_id": aluno['id'], 
                    "turma_id": st.session_state.form_data['turma']['id'],
                    "valor_final": valor_final, 
                    "token_acesso": token, 
                    "status": "Pendente",
                    "caminho_arquivo": path_s, 
                    "valor_desconto": valor_desconto, 
                    "valor_material": valor_material_calc
                }
                ContratoRepository.criar_contrato(novo_contrato)
                
                st.session_state.ultimo_token = token
                st.session_state.step = 4
                st.rerun()

    # --- PASSO 4: SUCESSO ---
    elif st.session_state.step == 4:
        st.balloons()
        st.success("✅ Contrato Gerado com Sucesso!")
        url_assinatura = f"https://nexusmed.portal/Assinatura?token={st.session_state.ultimo_token}"
        st.code(url_assinatura, language="markdown")
        
        st.info("O arquivo foi salvo no Storage e o registro criado no banco de dados.")
        
        if st.button("Gerar Outro Contrato"):
            st.session_state.step = 1
            st.session_state.form_data = {}
            st.rerun()

if __name__ == "__main__":
    main()
