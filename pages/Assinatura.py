import streamlit as st
import hashlib
from datetime import datetime
from src.database.repo_contratos import ContratoRepository
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.formatters import format_currency, format_cpf, get_full_date_ptbr

# Configuração White Label: Esconde menus e barra lateral
st.set_page_config(page_title="Assinatura de Contrato | NexusMed", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stHeader"] {display: none;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

def main():
    # 1. Validação do Token via URL (?token=...)
    query_params = st.query_params
    token = query_params.get("token")

    if not token:
        st.error("Link de assinatura inválido. Por favor, solicite um novo link à administração.")
        return

    # 2. Busca dados do contrato
    contrato = ContratoRepository.buscar_por_token(token)
    
    if not contrato:
        st.error("Contrato não encontrado.")
        return

    if contrato['status'] == 'Assinado':
        st.success("✅ Este contrato já foi assinado e finalizado.")
        st.info(f"Data do aceite: {datetime.fromisoformat(contrato['data_aceite']).strftime('%d/%m/%Y %H:%M')}")
        return

    st.title("🖋️ Assinatura Digital de Contrato")
    st.write(f"Olá, **{contrato['alunos']['nome_completo']}**.")
    st.write("Revise os detalhes do seu curso abaixo:")

    # 3. Resumo para conferência
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.write(f"**Curso:** {contrato['turmas']['cursos']['nome']}")
        col1.write(f"**Turma:** {contrato['turmas']['codigo_turma']}")
        col2.write(f"**Investimento:** {format_currency(contrato['valor_final'])}")
        col2.write(f"**Formato:** {contrato['formato_curso']}")

    st.warning("⚠️ É obrigatório ler o contrato antes de prosseguir.")

    # 4. Geração em Tempo Real para Download/Visualização
    # (Usando o processador para gerar o DOCX e converter para PDF em memória)
    try:
        processor = ContractProcessor("assets/modelo_contrato_V2.docx")
        
        # Contexto simplificado para o template
        context = {
            "nome_completo": contrato['alunos']['nome_completo'],
            "cpf": format_cpf(contrato['alunos']['cpf']),
            "email": contrato['alunos']['email'],
            "curso_nome": contrato['turmas']['cursos']['nome'],
            "valor_total": format_currency(contrato['valor_final']),
            "data_hoje": get_full_date_ptbr()
        }
        
        # Mock de parcelas para a tabela
        payment_rows = [
            {"parcela": "Entrada", "vencimento": "Imediato", "valor": format_currency(contrato['entrada_valor'])},
            {"parcela": f"{contrato['saldo_qtd_parcelas']}x Saldo", "vencimento": "Mensal", "valor": format_currency(contrato['saldo_valor'] / contrato['saldo_qtd_parcelas'])}
        ]

        docx_buffer = processor.generate_docx(context, payment_rows)
        pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)

        st.download_button(
            label="📄 Baixar Contrato para Leitura (PDF)",
            data=pdf_buffer,
            file_name=f"Contrato_NexusMed_{contrato['alunos']['nome_completo']}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Erro ao gerar visualização: {e}")

    # 5. Validação de Identidade
    st.write("---")
    st.subheader("Confirmação de Identidade")
    
    check_nome = st.text_input("Confirme seu Nome Completo")
    check_cpf = st.text_input("Confirme seu CPF (apenas números)")
    
    termos = st.checkbox("Li e concordo com todos os termos e cláusulas do contrato.")

    if st.button("ASSINAR CONTRATO AGORA", type="primary", use_container_width=True):
        # Validação rigorosa
        if check_nome.strip().lower() != contrato['alunos']['nome_completo'].lower():
            st.error("O nome digitado não confere com o contrato.")
        elif check_cpf.strip() != contrato['alunos']['cpf']:
            st.error("O CPF digitado não confere com o contrato.")
        elif not termos:
            st.error("Você precisa aceitar os termos para prosseguir.")
        else:
            # Lógica de Carimbo e Finalização
            with st.spinner("Processando assinatura digital..."):
                ip_usuario = "127.0.0.1" # Em prod: usar headers para pegar IP real
                timestamp = datetime.now().isoformat()
                
                # Gera Hash de Autenticidade único para este aceite
                hash_base = f"{token}-{timestamp}-{check_cpf}"
                hash_auth = hashlib.sha256(hash_base.encode()).hexdigest()[:16].upper()

                # Aplica o carimbo no PDF
                stamp = PDFManager.create_signature_stamp(
                    datetime.now(), check_nome, check_cpf, ip_usuario, hash_auth
                )
                pdf_final = PDFManager.apply_stamp_to_pdf(pdf_buffer, stamp)

                # Salva no Banco
                payload = {
                    "ip_aceite": ip_usuario,
                    "hash_aceite": hash_auth,
                    "recibo_aceite_texto": f"Assinado via Portal NexusMed por {check_nome}",
                }
                ContratoRepository.registrar_assinatura(contrato['id'], payload)

                st.success("🎉 Contrato assinado com sucesso!")
                
                # Disponibiliza o contrato já carimbado
                st.download_button(
                    label="📥 Baixar meu Contrato Assinado",
                    data=pdf_final,
                    file_name=f"CONTRATO_ASSINADO_NEXUSMED.pdf",
                    mime="application/pdf"
                )

if __name__ == "__main__":
    main()
