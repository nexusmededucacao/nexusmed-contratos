from src.database.connection import supabase
import streamlit as st

class UsuarioRepository:
    """
    Repositório para operações CRUD na tabela 'usuarios'.
    Esquema validado: id (uuid), nome, email, senha_hash, perfil, ativo (bool).
    """
    
    @staticmethod
    def listar_todos():
        """Retorna todos os utilizadores registados ordenados por nome."""
        try:
            response = supabase.table("usuarios").select("*").order("nome").execute()
            return response.data
        except Exception as e:
            st.error(f"Erro ao listar utilizadores: {e}")
            return []

    @staticmethod
    def buscar_por_email(email: str):
        """Procura um utilizador ativo pelo e-mail para o processo de login."""
        try:
            # Busca apenas utilizadores ativos para login
            response = supabase.table("usuarios")\
                .select("*")\
                .eq("email", email)\
                .eq("ativo", True)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            return None

    @staticmethod
    def criar_usuario(dados: dict):
        """
        Insere um novo utilizador no sistema.
        Retorna o registo criado ou None em caso de erro.
        """
        try:
            response = supabase.table("usuarios").insert(dados).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao criar utilizador: {e}")
            return None

    @staticmethod
    def atualizar_status(user_id: str, novo_status: bool):
        """Ativa ou desativa um utilizador (soft delete) usando UUID."""
        try:
            response = supabase.table("usuarios")\
                .update({"ativo": novo_status})\
                .eq("id", user_id)\
                .execute()
            return True if response.data else False
        except Exception as e:
            return False

    @staticmethod
    def eliminar_usuario(user_id: str):
        """Remove permanentemente um utilizador do banco de dados pelo UUID."""
        try:
            response = supabase.table("usuarios").delete().eq("id", user_id).execute()
            return True if response.data else False
        except Exception as e:
            st.error(f"Erro ao eliminar utilizador: {e}")
            return False
