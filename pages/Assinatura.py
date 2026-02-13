import streamlit as st
import hashlib
from datetime import datetime, timedelta
import io
import re
import requests
from src.database.repo_contratos import ContratoRepository
from src.document_engine.pdf_converter import PDFManager
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.utils.storage import StorageService
from src.database.connection import supabase

# Configuração da página
st.set_page_config(page_title="Assinatura Digital | NexusMed", layout="centered")

# URL Base para o carimbo (Ajuste conforme seu ambiente)
# Em produção no Streamlit Cloud, geralmente não conseguimos pegar a URL exata via código facilmente
# Então é bom definir ou tentar inferir.
BASE_URL = "https://nexusmed-contratos.streamlit.app"

# CSS Clean
st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stHeader"], footer {display: none;}
    .main {background-color: #f8fafc;}
    iframe {border: 1px solid #e2e8f0; border-radius: 8px; background-color: white;}
    </style>
    """, unsafe_allow_html=True)

def limpar_cpf(cpf_str):
    return re.sub(r'\D', '', str(cpf_str))

def main():
    token = st.query_params.get("token")

    if not token:
        st.error("Link inválido.")
        return

    contrato = ContratoRepository.buscar_por_token(token)
    
    if not contrato:
        st.error("Contrato não encontrado.")
        return

    # --- TELA 1: JÁ ASSINADO ---
    if contrato['status'] == 'Assinado':
        st.success(f"✅ Contrato assinado em {format_date_br(contrato.get('data_aceite'))}.")
        url_final = contrato.get('caminho_arquivo')
        if url_final:
            st.link_button("📥 BAIXAR CONTRATO ASSINADO (PDF)", url_final, type="primary", use_container_width=True)
            st.divider()
            st.markdown(f'<iframe src="{url_final}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)
        return

    # --- TELA 2: ASSINATURA ---
    aluno = contrato['alunos']
    curso = contrato['turmas']['cursos']
    url_original = contrato.get('caminho_arquivo')

    st.title("🖋️ Assinatura Digital")
    st.write(f"Olá, **{aluno['nome_completo']}**.")
    st.info("Revise o documento oficial abaixo:")

    if url_original:
        st.markdown(f'<iframe src="{url_original}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: right;'><a href='{url_original}' target='_blank'>🔍 Abrir em nova guia</a></div>", unsafe_allow_html=True)
    else:
        st.error("Arquivo original não encontrado.")
        st.stop()

    st.divider()
    st.subheader("Confirmação")
    
    c1, c2 = st.columns(2)
    nome_input = c1.text_input("Nome Completo")
    cpf_input = c2.text_input("CPF")
    
    termos = st.checkbox("Li e concordo com os termos.")

    if st.button("✍️ ASSINAR DIGITALMENTE", type="primary", use_container_width=True):
        input_cpf_limpo = limpar_cpf(cpf_input)
        aluno_cpf_limpo = limpar_cpf(aluno['cpf'])

        if not nome_input or input_cpf_limpo != aluno_cpf_limpo or not termos:
            st.error("Dados incorretos ou termos não aceitos.")
        else:
            with st.spinner("Registrando assinatura..."):
                try:
                    # 1. Download do Original
                    response = requests.get(url_original)
                    if response.status_code != 200:
                        raise Exception("Falha ao baixar contrato original.")
                    pdf_buffer = io.BytesIO(response.content)

                    # 2. Dados do Carimbo
                    try:
                        from streamlit.web.server.websocket_headers import _get_websocket_headers
                        ip_usuario = _get_websocket_headers().get("X-Forwarded-For", "0.0.0.0").split(",")[0]
                    except:
                        ip_usuario = "0.0.0.0"

                    # Ajuste de Fuso Horário (GMT-3)
                    timestamp_gmt3 = datetime.now() - timedelta(hours=3)
                    
                    # Link Completo para o Carimbo
                    link_completo = f"{BASE_URL}/Assinatura?token={token}"
                    
                    # Hash de Autenticação
                    hash_auth = hashlib.sha256(f"{token}{input_cpf_limpo}{timestamp_gmt3.isoformat()}".encode()).hexdigest().upper()

                    # 3. Gera Carimbo com NOVOS ARGUMENTOS (link e hash_auth)
                    stamp_text = PDFManager.create_signature_stamp(
                        data_assinatura=timestamp_gmt3,
                        nome_aluno=nome_input.upper(),
                        cpf=format_cpf(input_cpf_limpo),
                        email=aluno.get('email', 'N/A'),
                        ip=ip_usuario,
                        link=link_completo,    # Argumento Novo
                        hash_auth=hash_auth    # Argumento Novo
                    )
                    
                    pdf_final = PDFManager.apply_stamp_to_pdf(pdf_buffer, stamp_text)

                    # 4. Upload e Salvar
                    nome_arq = f"Contrato_{StorageService.sanitizar_nome(aluno['nome_completo'])}_ASSINADO.pdf"
                    path = f"minutas/{nome_arq}"

                    supabase.storage.from_("contratos").upload(
                        path=path, 
                        file=pdf_final.getvalue(), 
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )
                    
                    nova_url = supabase.storage.from_("contratos").get_public_url(path)

                    payload = {
                        "status": "Assinado",
                        "data_aceite": timestamp_gmt3.isoformat(),
                        "ip_aceite": ip_usuario,
                        "hash_aceite": hash_auth,
                        "recibo_aceite_texto": f"Assinado digitalmente. Hash: {hash_auth}", 
                        "caminho_arquivo": nova_url
                    }
                    ContratoRepository.registrar_assinatura(contrato['id'], payload)

                    st.balloons()
                    st.success("Assinado com sucesso!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro: {e}")

if __name__ == "__main__":
    main()
