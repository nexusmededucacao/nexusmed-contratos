import streamlit as st
import os

st.title("Modo de Diagnóstico")

# Vamos ver onde estamos
diretorio_atual = os.getcwd()
print(f"📍 Diretório Atual: {diretorio_atual}")

# Vamos ver o que tem na pasta src
caminho_src = os.path.join(diretorio_atual, "src")

if os.path.exists(caminho_src):
    arquivos = os.listdir(caminho_src)
    print(f"📂 Arquivos dentro de SRC: {arquivos}")
    st.success(f"Arquivos encontrados: {arquivos}")
else:
    print("❌ A pasta SRC não foi encontrada!")
    st.error("A pasta SRC não existe.")
