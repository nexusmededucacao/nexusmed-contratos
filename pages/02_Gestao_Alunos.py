from src.database.connection import supabase
import streamlit as st

class AlunoRepository:
    """
    Repositório oficial para a tabela 'alunos'.
    Validado com esquema: id, nome_completo, cpf, email, telefone, etc.
    """

    @staticmethod
    def listar_todos():
        try:
            # Ordena direto no banco para performance
            response = supabase.table("alunos").select("*").order("nome_completo").execute()
            return response.data
        except Exception as e:
            # Retorna lista vazia em caso de erro de conexão, mas não trava o app
            print(f"Erro ao listar: {e}")
            return []

    @staticmethod
    def filtrar_por_nome(termo: str):
        try:
            # Busca insensível a maiúsculas/minúsculas (ilike)
            response = supabase.table("alunos")\
                .select("*")\
                .ilike("nome_completo", f"%{termo}%")\
                .order("nome_completo")\
                .execute()
            return response.data
        except Exception as e:
            st.error(f"Erro na busca: {e}")
            return []

    @staticmethod
    def buscar_por_cpf(cpf: str):
        try:
            # Limpa pontuação antes de buscar
            cpf_limpo = "".join(filter(str.isdigit, cpf))
            response = supabase.table("alunos").select("*").eq("cpf", cpf_limpo).execute()
            return response.data
        except Exception as e:
            st.error(f"Erro ao buscar CPF: {e}")
            return []

    @staticmethod
    def buscar_por_id(aluno_id: int):
        try:
            response = supabase.table("alunos").select("*").eq("id", aluno_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            return None

    @staticmethod
    def criar_aluno(dados: dict):
        try:
            # Garante CPF limpo
            if 'cpf' in dados:
                dados['cpf'] = "".join(filter(str.isdigit, dados['cpf']))
                
            response = supabase.table("alunos").insert(dados).execute()
            return response.data
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def atualizar_aluno(aluno_id: int, dados: dict):
        try:
            return supabase.table("alunos").update(dados).eq("id", aluno_id).execute()
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")
            return None
