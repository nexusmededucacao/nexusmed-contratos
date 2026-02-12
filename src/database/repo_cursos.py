from src.database.connection import supabase
import streamlit as st

class CursoRepository:
    """
    Repositório para operações nas tabelas 'cursos' e 'turmas'.
    Esquema validado: IDs tipo bigint, campos ativo (boolean).
    """

    @staticmethod
    def listar_todos_com_turmas():
        """Lista cursos e aninha as turmas relacionadas (JOIN)."""
        try:
            response = supabase.table("cursos")\
                .select("*, turmas(*)")\
                .order("nome")\
                .execute()
            return response.data
        except Exception as e:
            print(f"Erro ao listar cursos e turmas: {e}")
            return []

    @staticmethod
    def listar_cursos_ativos():
        """Lista apenas cursos ativos para preenchimento de seletores."""
        try:
            response = supabase.table("cursos")\
                .select("*")\
                .eq("ativo", True)\
                .order("nome")\
                .execute()
            return response.data
        except Exception as e:
            return []

    @staticmethod
    def criar_curso(dados: dict):
        try:
            response = supabase.table("cursos").insert(dados).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao criar curso: {e}")
            return None

    @staticmethod
    def atualizar_curso(curso_id: int, dados: dict):
        """Atualiza dados do curso (nome, valor_bruto, ativo)."""
        try:
            # Garante que o ID não seja alterado
            dados.pop('id', None)
            response = supabase.table("cursos").update(dados).eq("id", curso_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao atualizar curso: {e}")
            return None

    # --- Operações de Turmas ---

    @staticmethod
    def criar_turma(dados: dict):
        """Cria nova turma vinculada a um curso_id."""
        try:
            response = supabase.table("turmas").insert(dados).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao criar turma: {e}")
            return None

    @staticmethod
    def atualizar_turma(turma_id: int, dados: dict):
        """Atualiza dados da turma (data_inicio, data_fim, formato, ativo)."""
        try:
            dados.pop('id', None)
            response = supabase.table("turmas").update(dados).eq("id", turma_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao atualizar turma: {e}")
            return None

    @staticmethod
    def inativar_turma(turma_id: int, status: bool):
        """Helper para ativar/inativar (soft delete) uma turma específica."""
        try:
            response = supabase.table("turmas").update({"ativo": status}).eq("id", turma_id).execute()
            return True if response.data else False
        except Exception as e:
            return False
