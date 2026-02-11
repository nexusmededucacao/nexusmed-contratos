import streamlit as st
import os

st.set_page_config(page_title="Debug Mode")

st.title("🕵️ Diagnóstico de Arquivos")

# 1. Verifica o que o Python vê na pasta 'pages'
try:
    arquivos = os.listdir("pages")
    st.write("### Arquivos encontrados na pasta 'pages':")
    st.code(arquivos)
    
    # Verifica se o arquivo alvo está na lista
    target = "01_Gerar_Contrato.py"
    if target in arquivos:
        st.success(f"✅ O arquivo '{target}' EXISTE fisicamente!")
    else:
        st.error(f"❌ O arquivo '{target}' NÃO foi encontrado. Verifique o nome exato.")
except Exception as e:
    st.error(f"Erro ao ler pasta: {e}")

st.divider()

# 2. Tenta trocar de página manualmente via botão
if st.button("Tentar ir para Gerar Contrato"):
    st.switch_page("pages/01_Gerar_Contrato.py")
