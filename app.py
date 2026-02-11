import streamlit as st
from src.auth import AuthManager

# 1. Configuração da Página (Deve ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="NexusMed Portal",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    # 2. Inicialização de estados globais
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 3. Lógica de Autenticação
    if not st.session_state.authenticated:
        # Se não estiver logado, exibe apenas a tela de login
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("https://nexusmed.com.br/logo.png", width=200) # Exemplo de Logo
            st.title("Portal Administrativo")
            AuthManager.login_form()
            
        # Esconde as outras páginas via CSS se não estiver logado (Opcional)
        st.markdown("""
            <style>
                [data-testid="stSidebarNav"] {display: none;}
            </style>
        """, unsafe_allow_html=True)
    
    else:
        # 4. Painel Principal (Utilizador Autenticado)
        st.sidebar.write(f"👤 Olá, **{st.session_state.get('user_nome')}**")
        st.sidebar.info(f"Nível: {st.session_state.get('user_perfil').capitalize()}")
        
        if st.sidebar.button("Terminar Sessão"):
            AuthManager.logout()

        st.title("🚀 Painel de Contratos NexusMed")
        st.write("---")
        
        # Dashboard Rápido (Exemplo de métricas)
        col1, col2, col3 = st.columns(3)
        col1.metric("Contratos Pendentes", "12", "2")
        col2.metric("Assinados este mês", "45", "15%")
        col3.metric("Novos Alunos", "8", "+12%")

        st.info("Utilize o menu lateral para navegar entre a gestão de alunos, cursos e geração de contratos.")

if __name__ == "__main__":
    main()
