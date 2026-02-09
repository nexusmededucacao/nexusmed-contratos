import streamlit as st
from src.db import supabase
from datetime import datetime, timezone

# --- CURSOS E TURMAS ---

def get_cursos():
    """Busca todos os cursos cadastrados para preencher o selectbox."""
    try:
        response = supabase.table("cursos").select("*").execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar cursos: {e}")
        return []

def get_turmas_by_curso(curso_id: int):
    """Busca turmas vinculadas a um curso específico."""
    try:
        response = supabase.table("turmas").select("*").eq("curso_id", curso_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar turmas: {e}")
        return []

def get_turma_by_id(turma_id: int):
    """Busca detalhes de uma turma específica para preencher o contrato."""
    try:
        response = supabase.table("turmas").select("*").eq("id", turma_id).single().execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar turma {turma_id}: {e}")
        return None

# --- ALUNOS ---

def get_aluno_by_cpf(cpf: str):
    """Verifica se o aluno já existe pelo CPF."""
    # Remove formatação para garantir match exato
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    try:
        response = supabase.table("alunos").select("*").eq("cpf", cpf_limpo).maybe_single().execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar aluno: {e}")
        return None

def upsert_aluno(dados_aluno: dict):
    """
    Cria ou Atualiza um aluno.
    Usa a lógica de UPSERT do Supabase baseada na constraint UNIQUE do CPF.
    Se o CPF já existe, atualiza os dados (endereço novo, telefone novo, etc).
    Se não existe, cria um novo.
    """
    try:
        # Garante que o CPF está limpo antes de salvar
        if 'cpf' in dados_aluno:
            dados_aluno['cpf'] = ''.join(filter(str.isdigit, dados_aluno['cpf']))
            
        response = supabase.table("alunos").upsert(dados_aluno, on_conflict="cpf").select().execute()
        if response.data:
            return response.data[0] # Retorna o objeto aluno atualizado/criado com o ID
        return None
    except Exception as e:
        st.error(f"Erro ao salvar aluno: {e}")
        raise e

# --- CONTRATOS ---

def create_contrato(dados_contrato: dict):
    """Salva o registro do contrato no banco."""
    try:
        response = supabase.table("contratos").insert(dados_contrato).select().execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao criar contrato: {e}")
        raise e

def get_contrato_by_token(token: str):
    """
    Busca contrato pelo token de acesso (Link enviado por email).
    Traz também os dados do Aluno (Join) para validação do CPF na tela de aceite.
    """
    try:
        response = supabase.table("contratos")\
            .select("*, alunos:aluno_id(*), turmas:turma_id(*)")\
            .eq("token_acesso", token)\
            .maybe_single()\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar contrato pelo token: {e}")
        return None

def registrar_aceite(contrato_id: str, dados_aceite: dict):
    """
    Atualiza o contrato com os dados do aceite digital.
    dados_aceite deve conter: status, data_aceite, ip_aceite, hash_aceite, recibo_aceite_texto
    """
    try:
        response = supabase.table("contratos")\
            .update(dados_aceite)\
            .eq("id", contrato_id)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao registrar aceite: {e}")
        raise e
