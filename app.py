import streamlit as st
from src.ui import tela_admin_geracao, tela_aluno_aceite

# Configuração deve ser a primeira linha do app.py
# Mas como a tela de aluno tem config própria, vamos gerenciar aqui ou remover do ui.py
# Vamos deixar uma config genérica aqui
st.set_page_config(page_title="Portal NexusMed", layout="wide")

def main():
    # Verifica parâmetros da URL
    # Sintaxe nova do Streamlit (versões recentes)
    query_params = st.query_params
    
    token = query_params.get("token", None)

    if token:
        # Modo Aluno (Tela Limpa)
        tela_aluno_aceite(token)
    else:
        # Modo Admin (Dashboard)
        # Aqui você poderia adicionar um login simples (st.text_input senha) para proteger essa tela
        tela_admin_geracao()

if __name__ == "__main__":
    main()
