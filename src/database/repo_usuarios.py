from src.database.connection import supabase

class UsuarioRepository:
    """
    Repositório para operações CRUD na tabela 'usuarios'.
    Tabela: id (uuid), nome, email, senha_hash, perfil, ativo (bool)
    """
    
    @staticmethod
    def listar_todos():
        """Retorna todos os utilizadores registados."""
        response = supabase.table("usuarios").select("*").order("nome").execute()
        return response.data

    @staticmethod
    def buscar_por_email(email: str):
        """Procura um utilizador específico pelo e-mail para o processo de login."""
        response = supabase.table("usuarios").select("*").eq("email", email).execute()
        return response.data[0] if response.data else None

    @staticmethod
    def criar_usuario(dados: dict):
        """
        Insere um novo utilizador no sistema.
        dados deve conter: nome, email, senha_hash, perfil, ativo
        """
        return supabase.table("usuarios").insert(dados).execute()

    @staticmethod
    def atualizar_status(user_id: str, novo_status: bool):
        """Ativa ou desativa um utilizador (soft delete)."""
        return supabase.table("usuarios").update({"ativo": novo_status}).eq("id", user_id).execute()

    @staticmethod
    def eliminar_usuario(user_id: str):
        """Remove permanentemente um utilizador do banco de dados."""
        return supabase.table("usuarios").delete().eq("id", user_id).execute()
