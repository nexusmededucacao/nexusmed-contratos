import streamlit as st
import sys
import os

# --- CORREÇÃO DE CAMINHO (A MARRETA) ---
# Adiciona a pasta raiz do projeto ao Python Path para garantir que ele ache o 'src'
root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_path)

# --- IMPORTS AGORA VÃO FUNCIONAR ---
from src.auth import criar_admin_inicial
from src.ui import (
    render_login, render_sidebar, 
    tela_gestao_cursos, tela_gestao_alunos, tela_novo_contrato,
    tela_aceite_aluno
)

# Configuração da Página deve ser a primeira instrução Streamlit
st.set_page_config(page_title="NexusMed Acadêmico", layout="wide")

def main():
    # 1. Roteamento: Verifica se é link de assinatura (Aluno)
    # st.query_params é a nova sintaxe do Streamlit. Antes era st.experimental_get_query_params()
    query_params = st.query_params
    token = query_params.get("token", None)

    if token:
        # Modo ALUNO (Tela limpa, sem sidebar)
        tela_aceite_aluno(token)
        return

    # 2. Modo SISTEMA INTERNO (Admin/Consultor)
    
    # Garante que existe pelo menos o usuário Admin no banco (primeiro deploy)
    criar_admin_inicial()

    # Verifica Sessão
    if 'usuario' not in st.session_state or st.session_state['usuario'] is None:
        render_login()
        return

    # Se logado, renderiza menu lateral e conteúdo
    escolha = render_sidebar()
    
    if escolha == "Gerar Contrato":
        tela_novo_contrato()
    elif escolha == "Gestão de Alunos":
        tela_gestao_alunos()
    elif escolha == "Gestão de Cursos":
        tela_gestao_cursos()
    elif escolha == "Gestão de Usuários":
        st.title("Gestão de Usuários")
        st.info("Funcionalidade futura: Cadastre novos consultores aqui.")

if __name__ == "__main__":
    main()
