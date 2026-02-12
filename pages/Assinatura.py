import streamlit as st
import hashlib
from datetime import datetime
import io
import re
from src.database.repo_contratos import ContratoRepository
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.utils.storage import StorageService # Importação necessária para o Storage

# Configuração White Label
st.set_page_config(page_title="Assinatura de Contrato | NexusMed", layout="centered")

st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stHeader"], footer {display: none;}
    .main {background-color: #f8fafc;}
    </style>
    """, unsafe_allow_html=True)

def limpar_cpf(cpf_str):
    """Remove pontos, traços e espaços, mantendo apenas números."""
    return re.sub(r'\D', '', str(cpf_str))

def obter_mes_extenso(dt):
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    return meses[dt.month]

def main():
    token = st.query_params.get("token")

    if not token:
        st.error("Link de assinatura inválido ou expirado.")
        return

    # 1. Busca profunda dos dados do contrato para reconstituição fiel
    contrato = ContratoRepository.buscar_por_token(token)
    
    if not contrato:
        st.error("Contrato não encontrado.")
        return

    if contrato['status'] == 'Assinado':
        st.success("✅ Este contrato já foi assinado e finalizado.")
        # Opcional: Permitir que o aluno baixe o arquivo que já está no storage
        return

    aluno = contrato['alunos']
    curso = contrato['turmas']['cursos']

    st.title("🖋️ Assinatura Digital")
    st.write(f"Olá, **{aluno['nome_completo']}**.")
    st.write("Por favor, revise o documento abaixo antes de confirmar sua assinatura.")

    # 2. Reconstituição fiel das tabelas
    try:
        lista_entrada = [{
            "n": "1",
            "vencimento": "À Vista",
            "valor": format_currency(contrato['entrada_valor']),
            "forma": contrato.get('entrada_forma_pagamento', 'PIX')
        }] if contrato['entrada_valor'] > 0 else []

        lista_saldo = []
        if contrato['saldo_valor'] > 0:
            v_parc = contrato['saldo_valor'] / contrato['saldo_qtd_parcelas']
            for i in range(contrato['saldo_qtd_parcelas']):
                lista_saldo.append({
                    "numero": f"{i+1}/{contrato['saldo_qtd_parcelas']}",
                    "data": "Mensal",
                    "valor": format_currency(v_parc),
                    "forma": contrato.get('saldo_forma_pagamento', 'Boleto')
                })

        agora = datetime.now()
        ctx = {
            'nome': aluno['nome_completo'].upper(),
            'cpf': format_cpf(aluno['cpf']),
            'email': aluno.get('email', ''),
            'crm': aluno.get('crm', ''),
            'logradouro': aluno.get('logradouro', ''),
            'numero': aluno.get('numero', ''),
            'cidade': aluno.get('cidade', ''),
            'uf': aluno.get('uf', ''),
            'pos_graduacao': curso['nome'],
            'turma': contrato['turmas']['codigo_turma'],
            'valor_total': format_currency(contrato['valor_final']),
            'dia': agora.day,
            'mês': obter_mes_extenso(agora),
            'ano': agora.year
        }

        processor = ContractProcessor("assets/modelo_contrato_V2.docx")
        docx_buffer = processor.generate_docx(ctx, lista_entrada, lista_saldo)
        pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)

        st.download_button(
            label="📄 Visualizar Contrato Completo (PDF)",
            data=pdf_buffer,
            file_name=f"Contrato_NexusMed_{aluno['nome_completo']}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Erro ao processar visualização do contrato: {e}")
        return

    st.divider()

    # 3. Validação e Assinatura
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
            with st.spinner("Registrando assinatura e finalizando documento..."):
                # Captura de IP
                try:
                    from streamlit.web.server.websocket_headers import _get_websocket_headers
                    ip_usuario = _get_websocket_headers().get("X-Forwarded-For", "127.0.0.1").split(",")[0]
                except:
                    ip_usuario = "127.0.0.1"

                # Geração de Hash de Autenticidade
                timestamp_agora = datetime.now()
                hash_auth = hashlib.sha256(f"{token}{input_cpf_limpo}{timestamp_agora.isoformat()}".encode()).hexdigest()[:16].upper()

                # Aplicação do carimbo em todas as páginas
                stamp_text = PDFManager.create_signature_stamp(
                    timestamp_agora, nome_input.upper(), format_cpf(input_cpf_limpo), ip_usuario, hash_auth
                )
                pdf_final = PDFManager.apply_stamp_to_pdf(pdf_buffer, stamp_text)

                # --- NOVA LÓGICA: SUBSTITUIÇÃO NO STORAGE ---
                # Reutilizamos o StorageService.upload_minuta que possui upsert=True por padrão
                path_storage, _ = StorageService.upload_minuta(
                    pdf_final, 
                    aluno['nome_completo'], 
                    curso['nome']
                )

                if path_storage:
                    # Persistência no Banco com dados da assinatura
                    payload = {
                        "status": "Assinado",
                        "data_aceite": timestamp_agora.isoformat(),
                        "ip_aceite": ip_usuario,
                        "hash_aceite": hash_auth,
                        "recibo_aceite_texto": f"Assinado por {nome_input} (IP: {ip_usuario})",
                        "caminho_arquivo": path_storage # Garante que o banco aponta para o path correto
                    }
                    ContratoRepository.registrar_assinatura(contrato['id'], payload)

                    st.balloons()
                    st.success("Assinatura realizada e contrato arquivado com sucesso!")
                    
                    st.download_button(
                        label="📥 Baixar minha via assinada (PDF)",
                        data=pdf_final,
                        file_name=f"CONTRATO_ASSINADO_{aluno['nome_completo']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.error("Erro ao salvar o arquivo assinado no servidor. Tente novamente.")

if __name__ == "__main__":
    main()
