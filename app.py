import streamlit as st
from src.auth import criar_admin_inicial
from src.ui import *

st.set_page_config(layout="wide")

# Rota Pública (Aceite)
if "token" in st.query_params:
    tela_aceite_aluno(st.query_params["token"])
    st.stop()

# Rota Privada (Sistema)
criar_admin_inicial() # Garante que existe admin

if 'usuario' not in st.session_state or not st.session_state['usuario']:
    render_login()
else:
    opcao = render_sidebar()
    if opcao == "Gerar Contrato": tela_novo_contrato()
    elif opcao == "Gestão de Alunos": tela_gestao_alunos()
    elif opcao == "Gestão de Cursos": tela_gestao_cursos()
    # Adicionar Gestão Usuários aqui
