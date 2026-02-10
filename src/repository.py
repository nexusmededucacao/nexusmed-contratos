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
        # Removemos o .select() para evitar erro de versão
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

# --- ALUNOS (Correção Principal Aqui) ---
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
    Salva o aluno e busca os dados atualizados em duas etapas separadas
    para evitar o erro 'SyncQueryRequestBuilder has no attribute select'
    """
    try:
        # 1. Limpeza de dados
        if 'cpf' in dados:
            dados['cpf'] = ''.join(filter(str.isdigit, str(dados['cpf'])))
        
        if 'data_nascimento' in dados and not dados['data_nascimento']:
             dados['data_nascimento'] = None

        # 2. A CORREÇÃO: Executa o salvamento SEM .select()
        # Isso evita o erro técnico da biblioteca
        supabase.table("alunos").upsert(dados, on_conflict="cpf").execute()
        
        # 3. Busca Manual: Já que salvamos, agora buscamos o registro salvo
        # para garantir que temos o ID correto.
        return get_aluno_by_cpf(dados['cpf'])

    except Exception as e:
        st.error(f"❌ ERRO TÉCNICO AO SALVAR: {e}")
        return None

# --- CONTRATOS ---
def create_contrato(dados):
    try:
        # A mesma correção aqui: Inserimos sem .select()
        supabase.table("contratos").insert(dados).execute()
        
        # Buscamos usando o token que acabamos de gerar (que é único)
        token = dados.get('token_acesso')
        if token:
             return get_contrato_by_token(token)
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
