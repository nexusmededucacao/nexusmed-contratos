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

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    if "pdf_cache" not in st.session_state: st.session_state.pdf_cache = None
    if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""

    # --- PASSO 1 E 2 MANTIDOS (ESTRUTURA ORIGINAL) ---
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

    # --- PASSO 3: FINANCEIRO COM TRAVAS E PRECISÃO ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
        valor_bruto = float(curso.get('valor_bruto', 0))
        percent_desc = st.number_input("Desconto (%)", 0.0, 100.0, 0.0, step=0.5)
        
        valor_desconto = round(valor_bruto * (percent_desc / 100), 2)
        valor_final = round(valor_bruto - valor_desconto, 2)
        valor_material = round(valor_bruto * 0.30, 2)

        st.success(f"Valor Final do Contrato: {format_currency(valor_final)}")

        # 1. ENTRADA
        st.markdown("#### 1. Entrada")
        ce1, ce2 = st.columns(2)
        v_entrada_total = ce1.number_input("Valor Total da Entrada", 0.0, valor_final, 0.0)
        q_entrada = ce2.selectbox("Parcelas Entrada", [1, 2, 3])
        
        lista_entrada = []
        opcoes_pagamento = ["PIX", "Cartão de Crédito", "Boleto", "Transferência"]
        
        data_ultima_entrada = date.today()
        if v_entrada_total > 0:
            v_unit_ent = round(v_entrada_total / q_entrada, 2)
            for i in range(q_entrada):
                with st.container(border=True):
                    c_e1, c_e2, c_e3 = st.columns(3)
                    v_p = c_e1.number_input(f"Valor P{i+1}", value=v_unit_ent, key=f"vent_{i}")
                    d_p = c_e2.date_input(f"Vencimento P{i+1}", value=date.today() + relativedelta(days=i*2), key=f"dent_{i}")
                    f_p = c_e3.selectbox(f"Forma P{i+1}", opcoes_pagamento, key=f"fent_{i}")
                    lista_entrada.append({"numero": i+1, "data": d_p, "valor": v_p, "forma": f_p})
                    data_ultima_entrada = d_p

        # 2. SALDO COM AJUSTE DE CENTAVOS
        saldo_restante = round(valor_final - v_entrada_total, 2)
        lista_saldo = []
        
        st.markdown(f"#### 2. Saldo Remanescente: {format_currency(saldo_restante)}")
        if saldo_restante > 0:
            cs1, cs2, cs3 = st.columns(3)
            q_saldo = cs1.number_input("Qtd Parcelas Saldo", 1, 36, 1)
            # Regra: Não pode ser anterior à última entrada
            d_saldo_ini = cs2.date_input("1º Vencimento Saldo", value=data_ultima_entrada + relativedelta(months=1))
            
            if d_saldo_ini <= data_ultima_entrada:
                st.error("⚠️ O 1º vencimento do saldo deve ser após a última parcela da entrada.")
            
            f_saldo = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão de Crédito", "PIX"])
            
            valor_base_saldo = round(saldo_restante / q_saldo, 2)
            soma_acumulada = 0
            for i in range(q_saldo):
                # Se for a última parcela, ajusta para bater o valor exato
                if i == q_saldo - 1:
                    valor_parc = round(saldo_restante - soma_acumulada, 2)
                else:
                    valor_parc = valor_base_saldo
                
                soma_acumulada += valor_parc
                lista_saldo.append({
                    "numero": f"{i+1}/{q_saldo}",
                    "data": (d_saldo_ini + relativedelta(months=i)).strftime("%d/%m/%Y"),
                    "valor": format_currency(valor_parc),
                    "forma": f_saldo
                })

        # 3. VALIDAÇÃO DE TRAVA FINANCEIRA
        total_pactuado = sum(p['valor'] for p in lista_entrada) + (saldo_restante if saldo_restante > 0 else 0)
        conferido = abs(total_pactuado - valor_final) < 0.01

        st.divider()
        if not conferido:
            st.error(f"❌ Erro matemático: A soma das parcelas ({format_currency(total_pactuado)}) não fecha com o total ({format_currency(valor_final)}).")
        
        c_b1, c_b2 = st.columns([1, 4])
        if c_b1.button("Voltar"): st.session_state.step = 2; st.rerun()
        
        if c_b2.button("🚀 Gerar Contrato", type="primary", disabled=not conferido, use_container_width=True):
            with st.spinner("Processando Documento..."):
                token = str(uuid.uuid4())
                
                # Preparar Contexto Completo para o Word
                
                ctx_doc = {
                    # Dados Pessoais (Tags exatas do seu Word)
                    'nome': aluno['nome_completo'].upper(),
                    'nacionalidade': aluno.get('nacionalidade', 'Brasileira'),
                    'estado_civil': aluno.get('estado_civil', ''),
                    'área_formação': aluno.get('area_formacao', ''),
                    'cpf': format_cpf(aluno['cpf']),
                    'crm': aluno.get('crm', ''),
                    'email': aluno.get('email', ''),
                    'telefone': aluno.get('telefone', ''),
    
                    # Endereço
                    'logradouro': aluno.get('logradouro', ''),
                    'numero': aluno.get('numero', ''),
                    'complemento': aluno.get('complemento', ''),
                    'bairro': aluno.get('bairro', ''),
                    'cidade': aluno.get('cidade', ''),
                    'uf': aluno.get('uf', ''),
                    'cep': aluno.get('cep', ''),

                    # Dados do Curso
                    'curso': curso['nome'],
                    'pos_graduacao': curso['nome'], # Caso use uma tag diferente
                    'turma': st.session_state.form_data['turma']['codigo_turma'],
                    'formato_curso': st.session_state.form_data['turma'].get('formato', 'Digital'),
    
                    # Valores
                    'valor_total': format_currency(valor_final),
                    'valor_material': format_currency(valor_material),
    
                    # Data por Extenso (Para o rodapé da página 07 do Word)
                    'dia': datetime.now().day,
                    'mês': get_full_date_ptbr().split(' de ')[1], # Pega apenas o nome do mês
                    'ano': datetime.now().year,
                    'data_atual': format_date_br(date.today())
                }

                # Execução do Motor de Documentos
                processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                # ENVIO DE AMBAS AS LISTAS PARA AS DUAS TABELAS
                docx_buffer = processor.generate_docx(ctx_doc, lista_entrada, lista_saldo)
                pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                
                # Salvamento e Upload
                path_s, name_s = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                
                novo_contrato = {
                    "aluno_id": aluno['id'], "turma_id": st.session_state.form_data['turma']['id'],
                    "valor_final": valor_final, "token_acesso": token, "status": "Pendente",
                    "caminho_arquivo": path_s, "valor_desconto": valor_desconto, "valor_material": valor_material
                }
                ContratoRepository.criar_contrato(novo_contrato)
                
                st.session_state.ultimo_token = token
                st.session_state.step = 4
                st.rerun()

    elif st.session_state.step == 4:
        st.success("Contrato Gerado!")
        st.code(f"Link: https://nexusmed.portal/Assinatura?token={st.session_state.ultimo_token}")
        if st.button("Novo Contrato"): st.session_state.step = 1; st.rerun()

if __name__ == "__main__":
    main()
