import streamlit as st
from src.db import supabase

# --- CURSOS ---
def get_cursos():
    return supabase.table("cursos").select("*").order("nome").execute().data

def create_curso(dados):
    return supabase.table("cursos").insert(dados).execute()

def update_curso(id, dados):
    return supabase.table("cursos").update(dados).eq("id", id).execute()

# --- TURMAS ---
def get_turmas_by_curso(curso_id):
    return supabase.table("turmas").select("*").eq("curso_id", curso_id).execute().data

def create_turma(dados):
    return supabase.table("turmas").insert(dados).execute()

def update_turma(id, dados):
    return supabase.table("turmas").update(dados).eq("id", id).execute()

# --- ALUNOS (Busca e Upsert) ---
def get_aluno_by_cpf(cpf):
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    return supabase.table("alunos").select("*").eq("cpf", cpf_limpo).maybe_single().execute().data

def upsert_aluno(dados):
    # Garante CPF limpo
    if 'cpf' in dados:
        dados['cpf'] = ''.join(filter(str.isdigit, dados['cpf']))
    
    # on_conflict="cpf" faz o UPDATE se já existir, ou INSERT se não
    response = supabase.table("alunos").upsert(dados, on_conflict="cpf").select().execute()
    return response.data[0] if response.data else None

# --- CONTRATOS ---
def create_contrato(dados):
    response = supabase.table("contratos").insert(dados).select().execute()
    return response.data[0] if response.data else None

def get_contrato_by_token(token):
    # Traz contrato + dados do aluno (join) + dados da turma (join)
    return supabase.table("contratos")\
        .select("*, alunos:aluno_id(*), turmas:turma_id(*, cursos(*))")\
        .eq("token_acesso", token)\
        .maybe_single().execute().data

def registrar_aceite(contrato_id, dados_update):
    return supabase.table("contratos").update(dados_update).eq("id", contrato_id).execute()

# --- USUÁRIOS ---
def get_all_usuarios():
    return supabase.table("usuarios").select("*").order("nome").execute().data

def create_usuario(dados):
    return supabase.table("usuarios").insert(dados).execute()
