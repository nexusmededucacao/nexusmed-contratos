from src.database.connection import supabase
import streamlit as st

class AlunoRepository:
    """
    Repositório oficial para a tabela 'alunos'.
    Validado com esquema: id (uuid), nome_completo, cpf, email, etc.
    """

    @staticmethod
    def listar_todos():
        try:
            response = supabase.table("alunos").select("*").order("nome_completo").execute()
            return response.data
        except Exception as e:
            print(f"Erro ao listar: {e}")
            return []

    @staticmethod
    def filtrar_por_nome(termo: str):
        try:
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
            cpf_limpo = "".join(filter(str.isdigit, cpf))
            response = supabase.table("alunos").select("*").eq("cpf", cpf_limpo).execute()
            # Retorna o objeto único se encontrado
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao buscar CPF: {e}")
            return None

    @staticmethod
    def buscar_por_id(aluno_id: str): # Alterado para str (UUID)
        try:
            response = supabase.table("alunos").select("*").eq("id", aluno_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            return None

    @staticmethod
    def criar_aluno(dados: dict):
        try:
            if 'cpf' in dados:
                dados['cpf'] = "".join(filter(str.isdigit, dados['cpf']))
                
            response = supabase.table("alunos").insert(dados).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao criar aluno: {e}")
            return None

    @staticmethod
    def atualizar_aluno(aluno_id: str, dados: dict): # Alterado para str (UUID)
        try:
            # Remove o ID dos dados se presente para evitar erro de alteração de chave primária
            dados.pop('id', None)
            if 'cpf' in dados:
                dados['cpf'] = "".join(filter(str.isdigit, dados['cpf']))
                
            response = supabase.table("alunos").update(dados).eq("id", aluno_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")
            return None
