import streamlit as st
import bcrypt
from src.database.repo_usuarios import UsuarioRepository

class AuthManager:
    """Gerencia a sessão e segurança do usuário."""

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Compara senha em texto plano com o hash do banco."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    @staticmethod
    def login_form():
        """Exibe o formulário de login na sidebar ou main."""
        st.sidebar.title("🔐 Acesso Restrito")
        email = st.sidebar.text_input("E-mail")
        password = st.sidebar.text_input("Senha", type="password")
        
        if st.sidebar.button("Entrar"):
            user = UsuarioRepository.buscar_por_email(email)
            
            if user and user.get('ativo'):
                if AuthManager.verify_password(password, user['senha_hash']):
                    st.session_state.authenticated = True
                    st.session_state.user_nome = user['nome']
                    st.session_state.user_perfil = user['perfil']
                    st.success(f"Bem-vindo, {user['nome']}!")
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado ou inativo.")

    @staticmethod
    def is_authenticated():
        return st.session_state.get("authenticated", False)

    @staticmethod
    def logout():
        from src.utils.formatters import limpar_sessao # Se você moveu para utils
        st.session_state.authenticated = False
        st.rerun()
