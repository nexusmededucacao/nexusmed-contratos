import streamlit as st
import uuid
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# --- CONFIG DA PÁGINA (Deve ser a primeira linha) ---
st.set_page_config(page_title="Gerar Contrato", layout="wide")

# --- DEBUG DE IMPORTAÇÃO (MODO DE SEGURANÇA) ---
try:
    from src.repository import get_cursos, get_turmas_by_curso, get_aluno_by_cpf, create_contrato
    from src.services import gerar_contrato_pdf, enviar_email
except Exception as e:
    st.error("🚨 ERRO CRÍTICO NOS IMPORTS!")
    st.error(f"Detalhes do erro: {e}")
    st.warning("Verifique se os arquivos em 'src/' estão corretos e sem erros de sintaxe.")
    st.stop() # Para a execução aqui se der erro

# --- SEGURANÇA DE LOGIN ---
if 'usuario' not in st.session_state or not st.session_state['usuario']:
    st.switch_page("app.py")

st.header("📝 Emissão de Contrato")

# --- SELEÇÃO ---
c1, c2 = st.columns(2)
cpf = c1.text_input("CPF do Aluno")
aluno = get_aluno_by_cpf(cpf) if cpf else None
if aluno: st.success(f"Aluno: {aluno['nome_completo']}")

cursos = get_cursos()
nome_curso = c2.selectbox("Curso", [c['nome'] for c in cursos] if cursos else [])
curso_sel = next((c for c in cursos if c['nome'] == nome_curso), None)

turma_sel = None
if curso_sel:
    turmas = get_turmas_by_curso(curso_sel['id'])
    cod_turma = st.selectbox("Turma", [t['codigo_turma'] for t in turmas] if turmas else [])
    if cod_turma:
        turma_sel = next(t for t in turmas if t['codigo_turma'] == cod_turma)

if not (aluno and curso_sel and turma_sel):
    st.info("Preencha os dados acima para continuar.")
    st.stop()

# --- FINANCEIRO ---
st.divider()
v_base = float(curso_sel['valor_bruto'])
c1, c2, c3 = st.columns(3)
c1.metric("Valor Base", f"R$ {v_base:,.2f}")
perc = c2.number_input("% Desconto", 0.0, 100.0, 0.0)
v_desc = v_base * (perc/100)
v_final = v_base - v_desc
c3.metric("Valor Final", f"R$ {v_final:,.2f}")

# --- PARCELAS ---
st.subheader("Pagamento")
ce1, ce2 = st.columns(2)
ent_val = ce1.number_input("Valor Entrada", 0.0, v_final, 0.0)
ent_qtd = ce2.number_input("Qtd Parc. Entrada", 1, 12, 1)

detalhes_ent = []
if ent_qtd > 0:
    v_p = ent_val / ent_qtd
    for i in range(ent_qtd):
        c_a, c_b = st.columns(2)
        dt = c_a.date_input(f"Vencimento {i+1}", date.today())
        frm = c_b.selectbox(f"Forma {i+1}", ["PIX", "Boleto", "Cartão"], key=f"f{i}")
        detalhes_ent.append({"numero": i+1, "valor": v_p, "data": dt, "forma": frm})

saldo = v_final - ent_val
st.info(f"Saldo a Parcelar: R$ {saldo:,.2f}")
cs1, cs2, cs3 = st.columns(3)
s_qtd = cs1.number_input("Qtd Saldo", 1, 60, 12)
s_ini = cs2.date_input("1º Venc Saldo", date.today() + relativedelta(months=1))
s_forma = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão"])

st.divider()
cc1, cc2 = st.columns(2)
bolsista = cc1.checkbox("Bolsista")
paciente = cc2.checkbox("Atendimento a Paciente")

if st.button("💾 Gerar Contrato", type="primary", use_container_width=True):
    with st.spinner("Gerando..."):
        token = str(uuid.uuid4())
        dados = {
            "aluno_id": aluno['id'], "turma_id": turma_sel['id'],
            "valor_curso": v_base, "percentual_desconto": perc,
            "valor_desconto": v_desc, "valor_final": v_final,
            "entrada_valor": ent_val, "entrada_qtd_parcelas": ent_qtd,
            "entrada_forma_pagamento": detalhes_ent[0]['forma'] if detalhes_ent else "PIX",
            "saldo_valor": saldo, "saldo_qtd_parcelas": s_qtd,
            "saldo_forma_pagamento": s_forma,
            "bolsista": bolsista, "atendimento_paciente": paciente,
            "formato_curso": turma_sel['formato'], "token_acesso": token, "status": "pendente"
        }
        infos = {"detalhes_entrada": detalhes_ent, "inicio_saldo": str(s_ini)}
        
        # Chama seu Service
        paths = gerar_contrato_pdf(aluno, turma_sel, curso_sel, dados, infos)
        
        if paths:
            local, cloud = paths
            dados['caminho_arquivo'] = cloud
            create_contrato(dados)
            
            # Estado para mostrar sucesso
            st.session_state['novo_contrato'] = {
                "link": f"https://nexusmed-contratos.streamlit.app/?token={token}",
                "path": local,
                "email": aluno['email'],
                "nome": aluno['nome_completo']
            }
            st.rerun()
        else:
            st.error("Erro na geração do PDF.")

# --- TELA DE SUCESSO ---
if 'novo_contrato' in st.session_state:
    res = st.session_state['novo_contrato']
    st.success("Contrato Criado!")
    st.text_input("Link para o Aluno", res['link'])
    
    c1, c2 = st.columns(2)
    with c1:
        with open(res['path'], "rb") as f:
            st.download_button("📥 Baixar PDF", f, "Contrato.pdf", mime="application/pdf")
    with c2:
        if st.button("📧 Enviar por E-mail"):
            enviar_email(res['email'], res['nome'], res['link'])
            st.toast("E-mail enviado!")
    
    if st.button("Novo Contrato"):
        del st.session_state['novo_contrato']
        st.rerun()
