import streamlit as st
from src.auth import login_usuario

# Configuração da Página Inicial
st.set_page_config(page_title="NexusMed Portal", layout="centered")

# 1. ROTEAMENTO DE ASSINATURA (ALUNO)
# Se houver um token na URL, o aluno não deve ver login, nem menu.
if "token" in st.query_params:
    token = st.query_params["token"]
    # Redireciona para a página de assinatura (Nome exato do seu arquivo)
    st.switch_page("pages/Assinatura.py")

# 2. TELA DE LOGIN (ADMIN)
if 'usuario' not in st.session_state:
    st.session_state['usuario'] = None

if st.session_state['usuario']:
    # Se já estiver logado, vai direto para a primeira página do menu
    # Nome exato do seu arquivo (sem emoji)
    st.switch_page("pages/01_Gerar_Contrato.py")

st.markdown("<h1 style='text-align: center;'>🔒 NexusMed Portal</h1>", unsafe_allow_html=True)
st.markdown("---")

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    with st.form("login_form"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", use_container_width=True):
            user = login_usuario(email, senha)
            if user:
                st.session_state['usuario'] = user
                st.rerun()
            else:
                st.error("E-mail ou senha inválidos.")
