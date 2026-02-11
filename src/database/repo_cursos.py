from src.database.connection import supabase

class CursoRepository:
    """
    Repositório para operações nas tabelas 'cursos' e 'turmas'.
    """

    @staticmethod
    def listar_todos_com_turmas():
        response = supabase.table("cursos")\
            .select("*, turmas(*)")\
            .order("nome")\
            .execute()
        return response.data

    @staticmethod
    def listar_cursos_ativos():
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
        """Atualiza campos de um curso (ex: inativar, mudar preço)."""
        return supabase.table("cursos").update(dados).eq("id", curso_id).execute()

    # --- Operações de Turmas ---

    @staticmethod
    def listar_turmas_por_curso(curso_id: int, apenas_ativas=False):
        """
        Busca todas as turmas. 
        Se apenas_ativas=True, filtra as inativas.
        """
        query = supabase.table("turmas").select("*").eq("curso_id", curso_id).order("codigo_turma", desc=True)
        
        if apenas_ativas:
            query = query.eq("ativo", True)
            
        return query.execute().data

    @staticmethod
    def inativar_turma(turma_id: int, status: bool):
        """
        Atualiza o status da turma (True = Ativa, False = Inativa).
        Substitui o antigo 'deletar_turma'.
        """
        return supabase.table("turmas").update({"ativo": status}).eq("id", turma_id).execute()
