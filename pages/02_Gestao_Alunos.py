from src.database.connection import supabase
import streamlit as st

class AlunoRepository:
    """
    Repositório robusto para a tabela 'alunos'.
    """

    @staticmethod
    def listar_todos():
        try:
            # Tenta ordenar por nome_completo, se falhar, tenta apenas listar sem ordem
            response = supabase.table("alunos").select("*").execute()
            
            # Ordenação manual no Python para evitar erro de coluna no SQL
            dados = response.data
            if dados and 'nome_completo' in dados[0]:
                dados.sort(key=lambda x: x.get('nome_completo', ''))
            return dados
        except Exception as e:
            print(f"Erro ao listar alunos: {e}")
            return []

    @staticmethod
    def filtrar_por_nome(termo: str):
        try:
            # Tenta filtrar. Se a coluna 'nome_completo' não existir, vai cair no except.
            # DICA: Verifique se no seu banco a coluna é 'nome' ou 'nome_completo'
            response = supabase.table("alunos")\
                .select("*")\
                .ilike("nome_completo", f"%{termo}%")\
                .execute()
            return response.data
        except Exception as e:
            # Fallback: Se der erro na busca (ex: coluna errada), retorna lista vazia e avisa
            st.error(f"Erro na busca: Verifique se a coluna 'nome_completo' existe no Supabase. Detalhe: {e}")
            return []

    @staticmethod
    def buscar_por_cpf(cpf: str):
        try:
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
            print(f"Erro ao buscar ID: {e}")
            return None

    @staticmethod
    def criar_aluno(dados: dict):
        try:
            if 'cpf' in dados:
                dados['cpf'] = "".join(filter(str.isdigit, dados['cpf']))
                
            response = supabase.table("alunos").insert(dados).execute()
            return response.data
        except Exception as e:
            # Retorna o erro amigável para a interface
            return {"error": str(e)}

    @staticmethod
    def atualizar_aluno(aluno_id: int, dados: dict):
        try:
            return supabase.table("alunos").update(dados).eq("id", aluno_id).execute()
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")
            return None
