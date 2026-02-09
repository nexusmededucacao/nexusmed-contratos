import streamlit as st
from supabase import create_client, Client

# Cache para não reconectar a cada recarregamento da página
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# Função auxiliar para verificar conexão
def check_connection():
    try:
        # Tenta buscar 1 curso só para ver se a API responde
        response = supabase.table("cursos").select("count", count="exact").execute()
        return True
    except Exception as e:
        st.error(f"Erro ao conectar com Supabase: {e}")
        return False
