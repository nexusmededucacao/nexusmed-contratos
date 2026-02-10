import streamlit as st
from src.db import supabase

# --- CURSOS ---
def get_cursos():
    try:
        response = supabase.table("cursos").select("*").order("nome").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Erro ao buscar cursos: {e}")
        return []

def create_curso(dados):
    try:
        return supabase.table("cursos").insert(dados).execute()
    except Exception as e:
        print(f"Erro ao criar curso: {e}")
        return None

def update_curso(id, dados):
    try:
        return supabase.table("cursos").update(dados).eq("id", id).execute()
    except Exception as e:
        print(f"Erro ao atualizar curso: {e}")
        return None

# --- TURMAS ---
def get_turmas_by_curso(curso_id):
    try:
        response = supabase.table("turmas").select("*").eq("curso_id", curso_id).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Erro ao buscar turmas: {e}")
        return []

def create_turma(dados):
    try:
        return supabase.table("turmas").insert(dados).execute()
    except Exception as e:
        print(f"Erro ao criar turma: {e}")
        return None

def update_turma(id, dados):
    try:
        return supabase.table("turmas").update(dados).eq("id", id).execute()
    except Exception as e:
        print(f"Erro ao atualizar turma: {e}")
        return None

# --- ALUNOS (Busca Segura) ---
def get_aluno_by_cpf(cpf):
    try:
        if not cpf: return None
        # Limpa o CPF
        cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
        
        # AQUI ESTAVA O ERRO: Removemos o maybe_single()
        # Buscamos uma lista normal. Se tiver algo, retornamos o índice [0]
        response = supabase.table("alunos").select("*").eq("cpf", cpf_limpo).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            return None
    except Exception as e:
        print(f"Erro ao buscar aluno por CPF: {e}")
        return None

def upsert_aluno(dados):
    try:
        # Garante CPF limpo
        if 'cpf' in dados:
            dados['cpf'] = ''.join(filter(str.isdigit, str(dados['cpf'])))
        
        # on_conflict="cpf" faz o UPDATE se já existir, ou INSERT se não
        response = supabase.table("alunos").upsert(dados, on_conflict="cpf").select().execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao salvar aluno: {e}")
        return None

# --- CONTRATOS ---
def create_contrato(dados):
    try:
        response = supabase.table("contratos").insert(dados).select().execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao criar contrato: {e}")
        return None

def get_contrato_by_token(token):
    try:
        # Traz contrato + dados do aluno (join) + dados da turma (join)
        # Nota: Removemos o maybe_single() aqui também por segurança
        response = supabase.table("contratos")\
            .select("*, alunos:aluno_id(*), turmas:turma_id(*, cursos(*))")\
            .eq("token_acesso", token)\
            .execute()
            
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar contrato pelo token: {e}")
        return None

def registrar_aceite(contrato_id, dados_update):
    try:
        return supabase.table("contratos").update(dados_update).eq("id", contrato_id).execute()
    except Exception as e:
        print(f"Erro ao registrar aceite: {e}")
        return None

# --- USUÁRIOS ---
def get_all_usuarios():
    try:
        response = supabase.table("usuarios").select("*").order("nome").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Erro ao buscar usuários: {e}")
        return []

def create_usuario(dados):
    try:
        return supabase.table("usuarios").insert(dados).execute()
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        return None
