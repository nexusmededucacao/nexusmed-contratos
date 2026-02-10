import streamlit as st
from supabase import create_client, Client

# @st.cache_resource faz com que o Python reuse a conexão aberta
# em vez de abrir uma nova a cada clique.
@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar no Supabase: {e}")
        return None

# Função simples para pegar a conexão já pronta
def get_supabase() -> Client:
    return init_connection()

# Cria a variável supabase para ser importada pelos outros arquivos
supabase = init_connection()
