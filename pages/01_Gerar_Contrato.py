import streamlit as st

# Configuração da página
st.set_page_config(page_title="Gerar Contrato", layout="wide")

st.title("✅ A página carregou!")
st.success("O sistema de navegação está funcionando perfeitamente.")

st.write("Se você está vendo esta mensagem, significa que o erro anterior era causado por um dos arquivos dentro da pasta 'src' (provavelmente 'services.py' ou 'repository.py').")

# Botão para testar o caminho de volta
if st.button("Voltar ao Menu Principal"):
    st.switch_page("app.py")
