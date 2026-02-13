import streamlit as st
import hashlib
from datetime import datetime
import io
import re
import requests
from src.database.repo_contratos import ContratoRepository
from src.document_engine.pdf_converter import PDFManager
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.utils.storage import StorageService
from src.database.connection import supabase

# Configuração da página (Modo Leitura/Aluno)
st.set_page_config(page_title="Assinatura Digital | NexusMed", layout="centered")

# CSS para esconder menus e deixar a interface limpa
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
    # 1. Captura o Token
    token = st.query_params.get("token")

    if not token:
        st.error("Link de assinatura inválido ou expirado.")
        return

    # 2. Busca o Contrato
    contrato = ContratoRepository.buscar_por_token(token)
    
    if not contrato:
        st.error("Contrato não encontrado.")
        return

    # --- TELA 1: CONTRATO JÁ ASSINADO (Onde você provavelmente está) ---
    if contrato['status'] == 'Assinado':
        st.success(f"✅ Contrato assinado em {format_date_br(contrato.get('data_aceite'))}.")
        
        url_final = contrato.get('caminho_arquivo')
        
        # Botão de Download Grande e Visível
        if url_final:
            st.link_button("📥 BAIXAR CONTRATO ASSINADO (PDF)", url_final, type="primary", use_container_width=True)
            
            st.divider()
            st.caption("Visualização do documento arquivado:")
            # Visualizador
            st.markdown(f'<iframe src="{url_final}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)
        else:
            st.warning("O documento foi assinado, mas o arquivo ainda está sendo processado. Tente atualizar a página em instantes.")
            
        return

    # --- TELA 2: PENDENTE DE ASSINATURA ---
    aluno = contrato['alunos']
    curso = contrato['turmas']['cursos']
    url_original = contrato.get('caminho_arquivo')

    st.title("🖋️ Assinatura Digital")
    st.write(f"Olá, **{aluno['nome_completo']}**.")
    st.info("Por favor, revise o documento oficial abaixo antes de assinar.")

    if not url_original:
        st.error("Erro técnico: O arquivo original não foi localizado. Contate o suporte.")
        st.stop()

    # Visualizador do PDF Original (Bucket)
    st.markdown(f'''
        <iframe src="{url_original}" width="100%" height="600px">
        </iframe>
    ''', unsafe_allow_html=True)

    # Link de backup caso o iframe falhe
    st.markdown(f"<div style='text-align: right; margin-bottom: 20px;'><a href='{url_original}' target='_blank'>🔍 Abrir PDF em nova guia</a></div>", unsafe_allow_html=True)

    st.divider()

    # Formulário de Assinatura
    st.subheader("Confirmação de Identidade")
    col1, col2 = st.columns(2)
    with col1:
        nome_input = st.text_input("Nome Completo")
    with col2:
        cpf_input = st.text_input("CPF (somente números)")
    
    termos = st.checkbox("Declaro que li o contrato acima e concordo com todos os seus termos.")

    if st.button("✍️ ASSINAR DIGITALMENTE", type="primary", use_container_width=True):
        input_cpf_limpo = limpar_cpf(cpf_input)
        aluno_cpf_limpo = limpar_cpf(aluno['cpf'])

        if not nome_input:
            st.error("Preencha seu nome completo.")
        elif input_cpf_limpo != aluno_cpf_limpo:
            st.error(f"O CPF informado não corresponde ao aluno {aluno['nome_completo']}.")
        elif not termos:
            st.error("Você precisa marcar a caixa de aceite dos termos.")
        else:
            with st.spinner("Registrando assinatura e gerando documento final..."):
                try:
                    # 1. Baixa o PDF Original (Bytes)
                    response = requests.get(url_original)
                    if response.status_code != 200:
                        raise Exception("Falha ao acessar o documento original.")
                    
                    pdf_bytes_original = response.content
                    pdf_buffer = io.BytesIO(pdf_bytes_original)

                    # 2. Dados de Auditoria
                    from streamlit.web.server.websocket_headers import _get_websocket_headers
                    try:
                        ip_usuario = _get_websocket_headers().get("X-Forwarded-For", "127.0.0.1").split(",")[0]
                    except:
                        ip_usuario = "127.0.0.1"

                    timestamp_agora = datetime.now()
                    hash_auth = hashlib.sha256(f"{token}{input_cpf_limpo}{timestamp_agora.isoformat()}".encode()).hexdigest()[:16].upper()

                    # 3. Aplica o Carimbo
                    stamp_text = PDFManager.create_signature_stamp(
                        timestamp_agora, nome_input.upper(), format_cpf(input_cpf_limpo), ip_usuario, hash_auth
                    )
                    pdf_final = PDFManager.apply_stamp_to_pdf(pdf_buffer, stamp_text)

                    # 4. Upload do PDF Assinado
                    aluno_nome_limpo = StorageService.sanitizar_nome(aluno['nome_completo'])
                    curso_nome_limpo = StorageService.sanitizar_nome(curso['nome'])
                    nome_arquivo_assinado = f"Contrato_{aluno_nome_limpo}_{curso_nome_limpo}_ASSINADO.pdf"
                    novo_path = f"minutas/{nome_arquivo_assinado}"

                    # Upload direto via Supabase Client
                    supabase.storage.from_("contratos").upload(
                        path=novo_path,
                        file=pdf_final.getvalue(),
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )
                    
                    # Gera URL Pública do novo arquivo
                    nova_url_publica = supabase.storage.from_("contratos").get_public_url(novo_path)

                    # 5. Atualiza Banco de Dados
                    payload = {
                        "status": "Assinado",
                        "data_aceite": timestamp_agora.isoformat(),
                        "ip_aceite": ip_usuario,
                        "hash_aceite": hash_auth,
                        "recibo_aceite_texto": f"Assinado por {nome_input} (IP: {ip_usuario})",
                        "caminho_arquivo": nova_url_publica # Atualiza o link para o assinado
                    }
                    ContratoRepository.registrar_assinatura(contrato['id'], payload)

                    st.balloons()
                    st.success("Assinatura realizada com sucesso!")
                    
                    # Atualiza a página para cair no bloco "Já Assinado" com o botão de download
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao assinar: {e}")

if __name__ == "__main__":
    main()
