import streamlit as st
import hashlib
from datetime import datetime
import io
import re
import requests # Necessário para baixar o PDF original do bucket
from src.database.repo_contratos import ContratoRepository
from src.document_engine.pdf_converter import PDFManager
from src.utils.formatters import format_currency, format_cpf
from src.utils.storage import StorageService
from src.database.connection import supabase

# Configuração White Label
st.set_page_config(page_title="Assinatura de Contrato | NexusMed", layout="centered")

st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stHeader"], footer {display: none;}
    .main {background-color: #f8fafc;}
    iframe {border: 1px solid #e2e8f0; border-radius: 8px;}
    </style>
    """, unsafe_allow_html=True)

def limpar_cpf(cpf_str):
    return re.sub(r'\D', '', str(cpf_str))

def main():
    token = st.query_params.get("token")

    if not token:
        st.error("Link de assinatura inválido ou expirado.")
        return

    contrato = ContratoRepository.buscar_por_token(token)
    
    if not contrato:
        st.error("Contrato não encontrado.")
        return

    if contrato['status'] == 'Assinado':
        st.success(f"✅ Este contrato já foi assinado em {format_date_br(contrato.get('data_aceite'))}.")
        # Se já assinado, mostra o arquivo final
        if contrato.get('caminho_arquivo'):
             st.markdown(f'<iframe src="{contrato["caminho_arquivo"]}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)
        return

    aluno = contrato['alunos']
    curso = contrato['turmas']['cursos']
    url_original = contrato.get('caminho_arquivo')

    st.title("🖋️ Assinatura Digital")
    st.write(f"Olá, **{aluno['nome_completo']}**.")
    st.info("Por favor, revise o documento oficial abaixo. Este é o arquivo registrado em nosso sistema.")

    # --- LÓGICA CORRIGIDA: VISUALIZAR A FONTE DA VERDADE ---
    if not url_original:
        st.error("Erro crítico: O arquivo do contrato não foi encontrado no servidor.")
        st.stop()

    # 1. Exibe o PDF original via iFrame (O aluno vê o que está no bucket)
    st.markdown(f'''
        <iframe src="{url_original}" width="100%" height="800px">
        </iframe>
    ''', unsafe_allow_html=True)

    # Botão de download de segurança
    st.markdown(f"<div style='text-align: right; margin-bottom: 20px;'><a href='{url_original}' target='_blank'>📥 Baixar documento original para ler externamente</a></div>", unsafe_allow_html=True)

    st.divider()

    st.subheader("Confirmação de Identidade")
    col1, col2 = st.columns(2)
    with col1:
        nome_input = st.text_input("Seu Nome Completo")
    with col2:
        cpf_input = st.text_input("Seu CPF (apenas números)")
    
    termos = st.checkbox("Li e concordo com todas as cláusulas e condições deste contrato.")

    if st.button("ASSINAR DIGITALMENTE", type="primary", use_container_width=True):
        input_cpf_limpo = limpar_cpf(cpf_input)
        aluno_cpf_limpo = limpar_cpf(aluno['cpf'])

        if not nome_input:
            st.error("Por favor, informe seu nome.")
        elif input_cpf_limpo != aluno_cpf_limpo:
            st.error("O CPF informado não corresponde ao cadastro do contrato.")
        elif not termos:
            st.error("Você deve aceitar os termos do contrato.")
        else:
            with st.spinner("Registrando assinatura na Blockchain (Simulação)..."):
                try:
                    # --- LÓGICA CORRIGIDA: ASSINAR O ARQUIVO DO BUCKET ---
                    
                    # 1. Baixa os bytes do PDF Original (Fonte da Verdade)
                    response = requests.get(url_original)
                    if response.status_code != 200:
                        raise Exception("Falha ao recuperar o arquivo original para assinatura.")
                    
                    pdf_bytes_original = response.content
                    pdf_buffer = io.BytesIO(pdf_bytes_original)

                    # 2. Prepara dados de auditoria
                    from streamlit.web.server.websocket_headers import _get_websocket_headers
                    try:
                        ip_usuario = _get_websocket_headers().get("X-Forwarded-For", "127.0.0.1").split(",")[0]
                    except:
                        ip_usuario = "127.0.0.1"

                    timestamp_agora = datetime.now()
                    hash_auth = hashlib.sha256(f"{token}{input_cpf_limpo}{timestamp_agora.isoformat()}".encode()).hexdigest()[:16].upper()

                    # 3. Aplica o carimbo no PDF ORIGINAL
                    stamp_text = PDFManager.create_signature_stamp(
                        timestamp_agora, nome_input.upper(), format_cpf(input_cpf_limpo), ip_usuario, hash_auth
                    )
                    
                    # Aqui usamos o buffer baixado, não gerado
                    pdf_final = PDFManager.apply_stamp_to_pdf(pdf_buffer, stamp_text)

                    # 4. Upload do PDF Assinado
                    aluno_nome_limpo = StorageService.sanitizar_nome(aluno['nome_completo'])
                    curso_nome_limpo = StorageService.sanitizar_nome(curso['nome'])
                    
                    nome_arquivo_assinado = f"Contrato_{aluno_nome_limpo}_{curso_nome_limpo}_ASSINADO.pdf"
                    novo_path = f"minutas/{nome_arquivo_assinado}"

                    # Upload Supabase
                    supabase.storage.from_("contratos").upload(
                        path=novo_path,
                        file=pdf_final.getvalue(),
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )
                    
                    # 5. Obtém a nova URL Pública do arquivo assinado
                    nova_url_publica = supabase.storage.from_("contratos").get_public_url(novo_path)

                    # 6. Atualiza Banco de Dados
                    payload = {
                        "status": "Assinado",
                        "data_aceite": timestamp_agora.isoformat(),
                        "ip_aceite": ip_usuario,
                        "hash_aceite": hash_auth,
                        "recibo_aceite_texto": f"Assinado por {nome_input} (IP: {ip_usuario})",
                        "caminho_arquivo": nova_url_publica # Atualiza para o link do arquivo assinado
                    }
                    ContratoRepository.registrar_assinatura(contrato['id'], payload)

                    st.balloons()
                    st.success(f"Contrato assinado com sucesso! Arquivo arquivado: {nome_arquivo_assinado}")
                    
                    st.download_button(
                        label="📥 Baixar minha via assinada (PDF)",
                        data=pdf_final,
                        file_name=nome_arquivo_assinado,
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Erro ao processar assinatura: {e}")

if __name__ == "__main__":
    main()
