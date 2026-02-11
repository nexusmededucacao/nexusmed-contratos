from src.database.connection import supabase

class CursoRepository:
    """
    Repositório para operações nas tabelas 'cursos' e 'turmas'.
    Cursos: id, nome, duracao_meses, carga_horaria, valor_bruto, ativo
    Turmas: id, curso_id, codigo_turma, data_inicio, data_fim, formato
    """

    @staticmethod
    def listar_todos_com_turmas():
        """Retorna todos os cursos e suas respectivas turmas."""
        response = supabase.table("cursos")\
            .select("*, turmas(*)")\
            .order("nome")\
            .execute()
        return response.data

    @staticmethod
    def listar_cursos_ativos():
        """Retorna apenas cursos marcados como ativos."""
        response = supabase.table("cursos")\
            .select("*")\
            .eq("ativo", True)\
            .order("nome")\
            .execute()
        return response.data

    @staticmethod
    def criar_curso(dados: dict):
        """Insere um novo curso no banco."""
        return supabase.table("cursos").insert(dados).execute()

    @staticmethod
    def atualizar_curso(curso_id: int, dados: dict):
        """Atualiza dados de um curso existente."""
        return supabase.table("cursos").update(dados).eq("id", curso_id).execute()

    # --- Operações de Turmas ---

    @staticmethod
    def listar_turmas_por_curso(curso_id: int):
        """Busca todas as turmas de um curso específico."""
        response = supabase.table("turmas")\
            .select("*")\
            .eq("curso_id", curso_id)\
            .order("codigo_turma")\
            .execute()
        return response.data

    @staticmethod
    def criar_turma(dados: dict):
        """
        Insere uma nova turma vinculada a um curso.
        dados deve conter: curso_id, codigo_turma, data_inicio, data_fim, formato
        """
        return supabase.table("turmas").insert(dados).execute()
