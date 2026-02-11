import streamlit as st
from src.auth import login_usuario
from streamlit.source_util import get_pages

st.set_page_config(page_title="Debug NexusMed", layout="centered")

st.title("🕵️ Debugger de Páginas")

# Imprime o que o Streamlit está enxergando na pasta pages
st.write("### Páginas Encontradas:")
pages = get_pages("app.py")
st.write(pages)

st.divider()

# Tenta fazer o login para testar
if 'usuario' not in st.session_state:
    st.session_state['usuario'] = None

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    with st.form("login_form"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            user = login_usuario(email, senha)
            if user:
                st.session_state['usuario'] = user
                st.success("Logado! Tente clicar no link abaixo.")
            else:
                st.error("Erro login")

if st.session_state['usuario']:
    # Link manual para testar se o arquivo abre
    st.page_link("pages/01_Gerar_Contrato.py", label="IR PARA CONTRATOS", icon="📝")
