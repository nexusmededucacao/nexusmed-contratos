from src.database.connection import supabase

class CursoRepository:
    """
    Repositório para operações nas tabelas 'cursos' e 'turmas'.
    """

    @staticmethod
    def listar_todos_com_turmas():
        """Lista cursos e aninha as turmas relacionadas."""
        response = supabase.table("cursos")\
            .select("*, turmas(*)")\
            .order("nome")\
            .execute()
        return response.data

    @staticmethod
    def listar_cursos_ativos():
        """Lista apenas cursos ativos para o formulário de nova turma."""
        response = supabase.table("cursos")\
            .select("*")\
            .eq("ativo", True)\
            .order("nome")\
            .execute()
        return response.data

    @staticmethod
    def criar_curso(dados: dict):
        return supabase.table("cursos").insert(dados).execute()

    @staticmethod
    def atualizar_curso(curso_id: int, dados: dict):
        """Atualiza dados do curso (nome, valor, status)."""
        return supabase.table("cursos").update(dados).eq("id", curso_id).execute()

    # --- Operações de Turmas ---

    @staticmethod
    def criar_turma(dados: dict):
        return supabase.table("turmas").insert(dados).execute()

    @staticmethod
    def atualizar_turma(turma_id: int, dados: dict):
        """
        Atualiza dados da turma.
        Usado para mudar data de fim, formato ou inativar (soft delete).
        """
        return supabase.table("turmas").update(dados).eq("id", turma_id).execute()

    @staticmethod
    def inativar_turma(turma_id: int, status: bool):
        """Helper específico para mudar apenas o status."""
        return supabase.table("turmas").update({"ativo": status}).eq("id", turma_id).execute()
