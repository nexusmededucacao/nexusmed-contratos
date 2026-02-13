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

# URL Base para o carimbo
BASE_URL = "https://nexusmed-contratos.streamlit.app"

# CSS Clean (Simplificado pois não tem mais iframe)
st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stHeader"], footer {display: none;}
    .main {background-color: #f8fafc;}
    .stButton button {font-weight: bold;}
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
        st.success(f"✅ Contrato assinado com sucesso em {format_date_br(contrato.get('data_aceite'))}.")
        
        url_final = contrato.get('caminho_arquivo')
        
        if url_final:
            st.markdown("### Documento Finalizado")
            st.info("Seu documento já foi processado e armazenado com segurança.")
            
            # BOTÃO DE DOWNLOAD (PÓS-ASSINATURA)
            st.link_button(
                "📥 FAÇA O DOWNLOAD DO SEU CONTRATO ASSINADO", 
                url_final, 
                type="primary", 
                use_container_width=True
            )
        else:
            st.warning("O documento está sendo processado. Atualize a página em instantes.")
        return

    # --- TELA 2: PENDENTE DE ASSINATURA ---
    aluno = contrato['alunos']
    url_original = contrato.get('caminho_arquivo')

    st.title("🖋️ Assinatura Digital")
    st.write(f"Olá, **{aluno['nome_completo']}**.")
    st.markdown("Para prosseguir, é obrigatório baixar e ler o documento original.")

    if url_original:
        # ÁREA DE DOWNLOAD (PRÉ-ASSINATURA)
        with st.container(border=True):
            st.warning("⚠️ FAÇA O DOWNLOAD E LEIA O CONTRATO ANTES DE ASSINAR! ⚠️.")
            st.link_button(
                "📄 DOWNLOAD 📄", 
                url_original, 
                type="primary", 
                use_container_width=True
            )
    else:
        st.error("Erro: Arquivo original não encontrado. Contate o suporte.")
        st.stop()

    st.divider()

    # --- FORMULÁRIO DE ASSINATURA ---
    st.subheader("Confirmação e Aceite")
    
    c1, c2 = st.columns(2)
    nome_input = c1.text_input("Nome Completo")
    cpf_input = c2.text_input("CPF (Apenas números)")
    
    termos = st.checkbox("Declaro que BAIXEI, LI e CONCORDO com todos os termos do contrato acima.")

    if st.button("✍️ ASSINAR DIGITALMENTE", type="primary", use_container_width=True):
        input_cpf_limpo = limpar_cpf(cpf_input)
        aluno_cpf_limpo = limpar_cpf(aluno['cpf'])

        if not nome_input:
            st.error("Preencha seu nome completo.")
        elif input_cpf_limpo != aluno_cpf_limpo:
            st.error("O CPF informado não corresponde ao cadastro deste contrato.")
        elif not termos:
            st.error("Você precisa confirmar a leitura e o aceite dos termos.")
        else:
            with st.spinner("Registrando assinatura e gerando via final..."):
                try:
                    # 1. Download do Original
                    response = requests.get(url_original)
                    if response.status_code != 200:
                        raise Exception("Falha ao baixar contrato original para processamento.")
                    pdf_buffer = io.BytesIO(response.content)

                    # 2. Dados de Auditoria
                    try:
                        from streamlit.web.server.websocket_headers import _get_websocket_headers
                        ip_usuario = _get_websocket_headers().get("X-Forwarded-For", "0.0.0.0").split(",")[0]
                    except:
                        ip_usuario = "0.0.0.0"

                    # Ajuste de Fuso Horário (GMT-3)
                    timestamp_gmt3 = datetime.now() - timedelta(hours=3)
                    
                    # Link e Hash
                    link_completo = f"{BASE_URL}/Assinatura?token={token}"
                    hash_auth = hashlib.sha256(f"{token}{input_cpf_limpo}{timestamp_gmt3.isoformat()}".encode()).hexdigest().upper()

                    # 3. Gera Carimbo
                    stamp_text = PDFManager.create_signature_stamp(
                        data_assinatura=timestamp_gmt3,
                        nome_aluno=nome_input.upper(),
                        cpf=format_cpf(input_cpf_limpo),
                        email=aluno.get('email', 'N/A'),
                        ip=ip_usuario,
                        link=link_completo,
                        hash_auth=hash_auth
                    )
                    
                    # Aplica Carimbo
                    pdf_final = PDFManager.apply_stamp_to_pdf(pdf_buffer, stamp_text)

                    # 4. Upload do Assinado
                    nome_arq = f"Contrato_{StorageService.sanitizar_nome(aluno['nome_completo'])}_ASSINADO.pdf"
                    path = f"minutas/{nome_arq}"

                    supabase.storage.from_("contratos").upload(
                        path=path, 
                        file=pdf_final.getvalue(), 
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )
                    
                    nova_url = supabase.storage.from_("contratos").get_public_url(path)

                    # 5. Atualiza Banco
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
                    st.error(f"Erro ao processar assinatura: {e}")

if __name__ == "__main__":
    main()
