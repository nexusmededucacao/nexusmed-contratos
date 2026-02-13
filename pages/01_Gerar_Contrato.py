import streamlit as st
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# --- IMPORTAÇÕES DO PROJETO ---
from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.database.repo_contratos import ContratoRepository
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.storage import StorageService
from src.utils.email_sender import enviar_email_contrato

# ==============================================================================
# ⚠️ CONFIGURAÇÃO DE URL (FIXA PARA PRODUÇÃO)
# ==============================================================================
BASE_URL = "https://nexusmed-contratos.streamlit.app" 
# ==============================================================================

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def obter_mes_extenso(dt):
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    return meses[dt.month]

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    if "url_pdf_atual" not in st.session_state: st.session_state.url_pdf_atual = None

    # --- ETAPA 1 E 2 (SELEÇÃO DE ALUNO E CURSO) ---
    # (Mantidas conforme seu código atual para brevidade)
    # ... [CÓDIGO DAS ETAPAS 1 E 2] ...

    # --- ETAPA 3: FINANCEIRO E GERAÇÃO ---
    if st.session_state.step == 3:
        # ... [CÓDIGO DE CÁLCULO FINANCEIRO] ...
        
        # (Supondo que chegamos no botão de Gerar)
        if st.button("🚀 Gerar e Salvar Oficialmente", type="primary", use_container_width=True):
            with st.spinner("Sincronizando com o servidor..."):
                try:
                    token = str(uuid.uuid4())
                    
                    # 1. GERA O DOCUMENTO (Igual ao que fizemos antes)
                    # ... [Lógica de processamento do Word/PDF] ...
                    
                    # 2. "O PULO DO GATO": UPLOAD PRIMEIRO
                    # Enviamos para o bucket e pegamos o link fixo
                    url_publica_arquivo, erro_upload = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                    
                    if erro_upload:
                        raise Exception(f"Erro ao subir arquivo para o servidor: {erro_upload}")

                    # 3. SALVA NO BANCO O LINK DO QUE ACABOU DE SUBIR
                    dados_contrato_db = {
                        "aluno_id": aluno['id'],
                        "turma_id": int(st.session_state.form_data['turma']['id']),
                        "caminho_arquivo": url_publica_arquivo, # Link do servidor
                        "token_acesso": token,
                        "status": "Pendente",
                        # ... outros campos mapeados ...
                    }
                    
                    res = ContratoRepository.criar_contrato(dados_contrato_db)
                    
                    if res and isinstance(res, dict) and 'error' in res:
                        raise Exception(f"Erro ao registrar no banco: {res['error']}")

                    # 4. FINALIZAÇÃO: Agora a sessão só conhece o arquivo do SERVIDOR
                    st.session_state.url_pdf_atual = url_publica_arquivo
                    st.session_state.ultimo_token = token
                    st.session_state.step = 4
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Erro na sincronização: {str(e)}")

    # --- ETAPA 4: PAINEL DE DOWNLOAD E ENVIO ---
    elif st.session_state.step == 4:
        st.success("✅ Documento Oficial Armazenado!")
        
        url_servidor = st.session_state.get('url_pdf_atual')
        token = st.session_state.ultimo_token
        aluno = st.session_state.form_data['aluno']
        link_assinatura = f"{BASE_URL}/Assinatura?token={token}"

        with st.container(border=True):
            st.write("O arquivo abaixo é o link direto do servidor (o mesmo que o aluno verá):")
            
            c1, c2 = st.columns(2)
            
            # Botão de Download que aponta para o SERVIDOR
            if url_servidor:
                c1.link_button("📥 Baixar Arquivo do Servidor", url_servidor, use_container_width=True)
            
            # Botão de E-mail
            if c2.button("📧 Enviar Convite", type="primary", use_container_width=True):
                # ... lógica de envio ...
