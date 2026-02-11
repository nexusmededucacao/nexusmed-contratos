import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_supabase_client() -> Client:
    """
    Estabelece e armazena em cache a conexão com o Supabase.
    Certifique-se de que as chaves 'supabase_url' e 'supabase_key' 
    estão configuradas no arquivo .streamlit/secrets.toml.
    """
    try:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"Erro: Chave {e} não encontrada no secrets.toml.")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        st.stop()

# Instância global para ser importada nos repositórios
supabase = get_supabase_client()
