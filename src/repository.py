import streamlit as st
from src.db import supabase

# --- CURSOS ---
def get_cursos():
    try:
        response = supabase.table("cursos").select("*").order("nome").execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Erro ao buscar cursos: {e}")
        return []

def create_curso(dados):
    try:
        return supabase.table("cursos").insert(dados).execute()
    except Exception as e:
        st.error(f"Erro ao criar curso: {e}")
        return None

# --- TURMAS ---
def get_turmas_by_curso(curso_id):
    try:
        response = supabase.table("turmas").select("*").eq("curso_id", curso_id).execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Erro ao buscar turmas: {e}")
        return []

def create_turma(dados):
    try:
        return supabase.table("turmas").insert(dados).execute()
    except Exception as e:
        st.error(f"Erro ao criar turma: {e}")
        return None

# --- ALUNOS (Onde o bicho pega) ---
def get_aluno_by_cpf(cpf):
    try:
        if not cpf: return None
        cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
        
        response = supabase.table("alunos").select("*").eq("cpf", cpf_limpo).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            return None
    except Exception as e:
        st.error(f"Erro ao buscar CPF: {e}")
        return None

def upsert_aluno(dados):
    """
    Esta função agora vai jogar o erro na tela se falhar.
    """
    try:
        # Garante CPF limpo e string
        if 'cpf' in dados:
            dados['cpf'] = ''.join(filter(str.isdigit, str(dados['cpf'])))
        
        # Garante que campos de data vazios não vão como string vazia ""
        # O Postgres odeia data vazia "". Tem que ser None.
        if 'data_nascimento' in dados and not dados['data_nascimento']:
             dados['data_nascimento'] = None

        # Tenta salvar
        response = supabase.table("alunos").upsert(dados, on_conflict="cpf").select().execute()
        
        # Se voltou vazio, mostra o objeto de resposta para entendermos o porquê
        if not response.data:
            st.error(f"⚠️ O Supabase recusou salvar e não deu erro explícito. Resposta técnica: {response}")
            return None
            
        return response.data[0]

    except Exception as e:
        # AQUI É O PULO DO GATO: Mostra o erro exato na interface
        st.error(f"❌ ERRO TÉCNICO NO BANCO: {e}")
        return None

# --- CONTRATOS ---
def create_contrato(dados):
    try:
        response = supabase.table("contratos").insert(dados).select().execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao criar contrato: {e}")
        return None

def get_contrato_by_token(token):
    try:
        response = supabase.table("contratos")\
            .select("*, alunos:aluno_id(*), turmas:turma_id(*, cursos(*))")\
            .eq("token_acesso", token)\
            .execute()
            
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao buscar contrato: {e}")
        return None

def registrar_aceite(contrato_id, dados_update):
    try:
        return supabase.table("contratos").update(dados_update).eq("id", contrato_id).execute()
    except Exception as e:
        st.error(f"Erro no aceite: {e}")
        return None
