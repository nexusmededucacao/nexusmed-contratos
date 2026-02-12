import streamlit as st
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# --- IMPORTAÇÕES DO PROJETO ---
from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.database.repo_contratos import ContratoRepository
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.storage import StorageService
from src.utils.email_sender import enviar_email_contrato

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

# --- FUNÇÃO DE CALLBACK PARA RECÁLCULO (A MÁGICA ACONTECE AQUI) ---
def recalcular_parcelas_entrada():
    """
    Esta função é chamada toda vez que o usuário altera uma parcela.
    Ela recalcula as parcelas seguintes para garantir que a soma bata com o total.
    """
    total = st.session_state.get('v_entrada_total_safe', 0.0)
    qtd = st.session_state.get('q_entrada_safe', 1)
    
    # 1. Recupera os valores atuais
    soma_acumulada = 0.0
    
    for i in range(qtd):
        key = f"input_ent_{i}"
        # Se a chave não existir ainda (primeira renderização), ignora
        if key in st.session_state:
            val_atual = st.session_state[key]
            
            # Se for a parcela que acabou de ser editada ou anterior, mantemos.
            # Se for uma parcela futura, recalculamos o saldo.
            soma_acumulada += val_atual
            
            # Calculamos quanto falta para chegar no total
            saldo_restante = total - soma_acumulada
            
            # Se ainda tem parcelas para frente, distribui o saldo
            parcelas_restantes = qtd - (i + 1)
            
            if parcelas_restantes > 0:
                # Divide o que sobrou igualmente entre as próximas
                valor_prox = round(saldo_restante / parcelas_restantes, 2)
                
                # Aplica nos inputs seguintes
                for j in range(i + 1, qtd):
                    key_prox = f"input_ent_{j}"
                    # Ajuste fino para a última parcela pegar os centavos
                    if j == qtd - 1:
                        # A última pega tudo que sobrou
                        val_prox_final = round(total - (soma_acumulada + (valor_prox * (parcelas_restantes - 1))), 2)
                        st.session_state[key_prox] = max(0.0, val_prox_final)
                    else:
                        st.session_state[key_prox] = max(0.0, valor_prox)
                
                # Como já distribuímos o resto, paramos o loop principal
                break

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}

    # --- PASSO 1: SELEÇÃO DE ALUNO ---
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

    # --- PASSO 2: CURSO E TURMA ---
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

    # --- PASSO 3: FINANCEIRO (SISTEMA DE CASCATA RECUPERADA) ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
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

        # 1. CONFIGURAÇÃO DA ENTRADA
        st.markdown("#### 1. Pagamento de Entrada / À Vista")
        ce1, ce2 = st.columns(2)
        
        # Armazena o total em session_state para o callback acessar
        v_entrada_total = ce1.number_input("Valor Total da Entrada", 0.0, valor_final, 0.0, step=100.0, key="v_entrada_total_safe")
        q_entrada = ce2.selectbox("Qtd. Parcelas Entrada", [1, 2, 3], key="q_entrada_safe")
        
        # --- LÓGICA DE INICIALIZAÇÃO INTELIGENTE ---
        # Se mudou o valor total ou a quantidade, reiniciamos os valores das parcelas
        if "last_v_entrada" not in st.session_state or st.session_state.last_v_entrada != v_entrada_total or st.session_state.last_q_entrada != q_entrada:
            st.session_state.last_v_entrada = v_entrada_total
            st.session_state.last_q_entrada = q_entrada
            
            # Distribui igualmente
            v_base = round(v_entrada_total / q_entrada, 2) if q_entrada > 0 else 0
            for k in range(q_entrada):
                key_p = f"input_ent_{k}"
                if k == q_entrada - 1:
                    # Ajuste final
                    v_final_p = round(v_entrada_total - (v_base * (q_entrada - 1)), 2)
                    st.session_state[key_p] = max(0.0, v_final_p)
                else:
                    st.session_state[key_p] = v_base

        lista_entrada = []
        opcoes_pagamento = ["PIX", "Cartão de Crédito", "Boleto", "Transferência"]
        data_ultima_entrada = date.today()

        if v_entrada_total > 0:
            for i in range(q_entrada):
                with st.container(border=True):
                    c_e1, c_e2, c_e3 = st.columns(3)
                    
                    key_val = f"input_ent_{i}"
                    
                    # --- O SEGREDO PARA NÃO TRAVAR ---
                    # max_value é SEMPRE o valor_final (bem alto).
                    # A validação acontece na matemática, não no componente.
                    # O 'value' vem do session_state, que é atualizado pelo callback.
                    
                    v_p = c_e1.number_input(
                        f"Valor P{i+1}", 
                        min_value=0.0, 
                        max_value=valor_final, # EVITA O ERRO ValueAboveMaxError
                        key=key_val,
                        on_change=recalcular_parcelas_entrada # CHAMA O RECÁLCULO QUANDO EDITA
                    )
                    
                    d_p = c_e2.date_input(f"Vencimento P{i+1}", value=date.today() + relativedelta(days=i*30), key=f"dent_{i}")
                    f_p = c_e3.selectbox(f"Forma P{i+1}", opcoes_pagamento, key=f"fent_{i}")
                    
                    lista_entrada.append({
                        "numero": i+1, 
                        "data": d_p.strftime("%d/%m/%Y"), 
                        "valor": format_currency(v_p), 
                        "forma": f_p, 
                        "valor_num": v_p
                    })
                    data_ultima_entrada = d_p

            # Validação Visual
            soma_entrada = sum(p['valor_num'] for p in lista_entrada)
            diff = round(soma_entrada - v_entrada_total, 2)
            if diff != 0:
                st.warning(f"⚠️ A soma das parcelas (R$ {format_currency(soma_entrada)}) difere do total (R$ {format_currency(v_entrada_total)}). Diferença: {diff}")

        # 2. SALDO REMANESCENTE
        saldo_restante = round(valor_final - v_entrada_total, 2)
        lista_saldo = []
        
        if saldo_restante > 0:
            st.divider()
            st.markdown(f"#### 2. Saldo Remanescente: {format_currency(saldo_restante)}")
            
            with st.expander("📊 Clique aqui para configurar o parcelamento do Saldo", expanded=False):
                cs1, cs2, cs3 = st.columns(3)
                q_saldo = cs1.number_input("Qtd Parcelas Saldo", 1, 36, 12)
                d_saldo_ini = cs2.date_input("1º Vencimento Saldo", value=data_ultima_entrada + relativedelta(months=1))
                f_saldo = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão de Crédito", "PIX"])
                
                v_base_saldo = round(saldo_restante / q_saldo, 2)
                soma_acumulada_saldo = 0
                
                for i in range(q_saldo):
                    if i == q_saldo - 1:
                        v_parc = round(saldo_restante - soma_acumulada_saldo, 2)
                    else:
                        v_parc = v_base_saldo
                    
                    soma_acumulada_saldo += v_parc
                    venc_p = d_saldo_ini + relativedelta(months=i)
                    
                    lista_saldo.append({
                        "Parcela": f"{i+1}/{q_saldo}",
                        "Vencimento": venc_p.strftime("%d/%m/%Y"),
                        "Valor": format_currency(v_parc),
                        "Forma": f_saldo,
                        "valor_num": v_parc
                    })

                st.table(lista_saldo)

        # 3. VALIDAÇÃO FINAL
        soma_total_dist = sum(p['valor_num'] for p in lista_entrada) + sum(p['valor_num'] for p in lista_saldo)
        
        # Verifica se a entrada bate (com tolerância de 0.05)
        entrada_ok = True
        if v_entrada_total > 0:
             entrada_ok = abs(sum(p['valor_num'] for p in lista_entrada) - v_entrada_total) <= 0.05

        # Verifica total geral
        total_ok = abs(round(soma_total_dist, 2) - valor_final) <= 0.05
        
        pode_gerar = entrada_ok and total_ok

        st.divider()
        if not entrada_ok:
            st.error(f"❌ Erro na Entrada: A soma das parcelas não bate com o valor da entrada.")
        elif not total_ok:
            st.error(f"❌ Erro Global: A soma total ({format_currency(soma_total_dist)}) difere do contrato ({format_currency(valor_final)}).")
        
        c_b1, c_b2 = st.columns([1, 4])
        if c_b1.button("Voltar"): st.session_state.step = 2; st.rerun()
        
        if c_b2.button("🚀 Gerar Contrato", type="primary", disabled=not pode_gerar, use_container_width=True):
            with st.spinner("Gerando Documentos..."):
                token = str(uuid.uuid4())
                agora = datetime.now()
                
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
                    'valor_material': format_currency(valor_material_calc),
                    'dia': agora.day,
                    'mês': obter_mes_extenso(agora),
                    'ano': agora.year
                }

                tab_ent = [{"n": p["numero"], "vencimento": p["data"], "valor": p["valor"], "forma": p["forma"]} for p in lista_entrada]
                tab_sal = [{"n": p["Parcela"], "vencimento": p["Vencimento"], "valor": p["Valor"], "forma": p["Forma"]} for p in lista_saldo]
                
                processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                docx_buffer = processor.generate_docx(ctx_doc, tab_ent, tab_sal)
                pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                
                path_s, _ = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                
                ContratoRepository.criar_contrato({
                    "aluno_id": aluno['id'], 
                    "turma_id": st.session_state.form_data['turma']['id'],
                    "valor_final": valor_final, 
                    "token_acesso": token, 
                    "status": "Pendente",
                    "caminho_arquivo": path_s, 
                    "valor_desconto": valor_desconto, 
                    "valor_material": valor_material_calc,
                    "entrada_valor": v_entrada_total,
                    "saldo_valor": saldo_restante,
                    "saldo_qtd_parcelas": q_saldo
                })
                
                st.session_state.ultimo_token = token
                st.session_state.step = 4
                st.rerun()

    # --- PASSO 4: SUCESSO ---
    elif st.session_state.step == 4:
        st.balloons()
        st.success("✅ Contrato Gerado!")
        st.code(f"https://nexusmed.portal/Assinatura?token={st.session_state.ultimo_token}")
        
        if st.button("Novo Contrato"): 
            st.session_state.step = 1
            st.session_state.form_data = {}
            st.rerun()

if __name__ == "__main__":
    main()
