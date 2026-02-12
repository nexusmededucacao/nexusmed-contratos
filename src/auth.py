import streamlit as st
import bcrypt
from src.database.repo_usuarios import UsuarioRepository

class AuthManager:
    """Gerencia a sessão e segurança do usuário."""

    @staticmethod
    def initialize_session():
        """Inicializa as variáveis de estado de sessão necessárias."""
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
        if "user_nome" not in st.session_state:
            st.session_state.user_nome = None
        if "user_perfil" not in st.session_state:
            st.session_state.user_perfil = None

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Compara senha em texto plano com o hash do banco."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False

    @staticmethod
    def login_form():
        """Exibe o formulário de login na sidebar."""
        AuthManager.initialize_session()
        
        st.sidebar.title("🔐 Acesso Restrito")
        email = st.sidebar.text_input("E-mail")
        password = st.sidebar.text_input("Senha", type="password")
        
        if st.sidebar.button("Entrar"):
            # O repositório já filtra por usuários ativos
            user = UsuarioRepository.buscar_por_email(email)
            
            if user:
                if AuthManager.verify_password(password, user['senha_hash']):
                    st.session_state.authenticated = True
                    st.session_state.user_nome = user['nome']
                    st.session_state.user_perfil = user['perfil']
                    st.sidebar.success(f"Bem-vindo, {user['nome']}!")
                    st.rerun()
                else:
                    st.sidebar.error("Senha incorreta.")
            else:
                st.sidebar.error("Usuário não encontrado ou inativo.")

    @staticmethod
    def is_authenticated() -> bool:
        """Verifica se o usuário está logado."""
        return st.session_state.get("authenticated", False)

    @staticmethod
    def check_access():
        """Bloqueia o acesso a páginas caso não esteja autenticado."""
        if not AuthManager.is_authenticated():
            st.warning("Por favor, faça login para acessar esta página.")
            st.stop() # Interrompe a renderização da página

    @staticmethod
    def logout():
        """Limpa a sessão e desloga o usuário."""
        st.session_state.clear()
        st.rerun()
