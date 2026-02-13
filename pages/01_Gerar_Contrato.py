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

# URL de Produção para os links de assinatura
BASE_URL = "https://nexusmed-contratos.streamlit.app" 

def obter_mes_extenso(dt):
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    return meses[dt.month]

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    if "url_pdf_oficial" not in st.session_state: st.session_state.url_pdf_oficial = None

    # --- PASSO 1: SELECIONAR ALUNO ---
    if st.session_state.step == 1:
        st.subheader("Etapa 1: Selecionar Aluno")
        busca = st.text_input("Buscar Aluno por Nome ou CPF")
        if busca:
            alunos = AlunoRepository.buscar_por_cpf(busca) if any(c.isdigit() for c in busca) else AlunoRepository.filtrar_por_nome(busca)
            if alunos:
                for a in (alunos if isinstance(alunos, list) else [alunos]):
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{a.get('nome_completo')}**")
                        if c2.button("Selecionar", key=f"sel_{a['id']}"):
                            st.session_state.form_data['aluno'] = a
                            st.session_state.step = 2
                            st.rerun()

    # --- PASSO 2: CURSO E TURMA ---
    elif st.session_state.step == 2:
        st.subheader("Etapa 2: Curso e Turma")
        aluno = st.session_state.form_data.get('aluno', {})
        cursos = CursoRepository.listar_todos_com_turmas()
        map_cursos = {c['nome']: c for c in cursos}
        sel_curso = st.selectbox("Selecione o Curso", [""] + list(map_cursos.keys()))
        if sel_curso:
            curso_dados = map_cursos[sel_curso]
            turmas = curso_dados.get('turmas', [])
            if turmas:
                map_turmas = {f"{t['codigo_turma']} ({t.get('formato','-')})": t for t in turmas}
                sel_turma = st.selectbox("Selecione a Turma", list(map_turmas.keys()))
                if st.button("Avançar"):
                    st.session_state.form_data['curso'] = curso_dados
                    st.session_state.form_data['turma'] = map_turmas[sel_turma]
                    st.session_state.step = 3
                    st.rerun()

    # --- PASSO 3: FINANCEIRO E GERAÇÃO ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        dados_turma = st.session_state.form_data['turma']
        
        valor_bruto = float(curso.get('valor_bruto', 0))
        percent_desc = st.number_input("Desconto Comercial (%)", 0.0, 100.0, 0.0, step=0.5)
        valor_final = round(valor_bruto - round(valor_bruto * (percent_desc / 100), 2), 2)
        st.success(f"### Valor Final: {format_currency(valor_final)}")

        v_entrada_total = st.number_input("Total Entrada", 0.0, valor_final, 0.0, key="v_entrada_total_safe")
        q_entrada = st.selectbox("Parcelas Entrada", [1, 2, 3], key="q_entrada_safe")
        saldo_restante = round(valor_final - v_entrada_total, 2)
        q_saldo = st.number_input("Parcelas Saldo", 1, 36, 12)

        if st.button("🚀 Gerar e Sincronizar com Servidor", type="primary", use_container_width=True):
            with st.spinner("Processando e enviando para o Supabase..."):
                try:
                    token = str(uuid.uuid4())
                    agora = datetime.now()
                    
                    # 1. GERAÇÃO DO CONTEXTO (Garantindo dados preenchidos)
                    ctx_doc = {
                        'nome': str(aluno.get('nome_completo', '')).upper(),
                        'cpf': format_cpf(str(aluno.get('cpf', ''))),
                        'data_nascimento': format_date_br(aluno.get('data_nascimento')),
                        'estado_civil': str(aluno.get('estado_civil', 'Solteiro(a)')),
                        'curso': str(curso.get('nome', '')),
                        'turma': str(dados_turma.get('codigo_turma', '')),
                        'valor_final': format_currency(valor_final).replace("R$", "").strip(),
                        'dia': agora.day, 'mês': obter_mes_extenso(agora), 'ano': agora.year
                    }

                    processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                    docx_buffer = processor.generate_docx(ctx_doc, [], []) 
                    pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                    
                    # 2. UPLOAD E CONGELAMENTO
                    url_pdf_servidor, erro_upload = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                    if erro_upload: raise Exception(f"Erro no Upload: {erro_upload}")

                    # 3. SALVAMENTO NO BANCO COM MAPEAMENTO COMPLETO
                    dados_db = {
                        "aluno_id": aluno['id'],
                        "turma_id": int(dados_turma['id']), # Cast para bigint
                        "valor_curso": float(valor_bruto),
                        "valor_desconto": float(valor_desconto),
                        "percentual_desconto": float(percent_desc),
                        "valor_final": float(valor_final),
                        "valor_material": float(valor_material_calc),
                        "bolsista": True if percent_desc > 0 else False,
                        "atendimento_paciente": True if dados_turma.get('atendimento') == 'Sim' else False,
                        "entrada_valor": float(v_entrada_total),
                        "entrada_qtd_parcelas": int(q_entrada),
                        "saldo_valor": float(saldo_restante),
                        "saldo_qtd_parcelas": int(q_saldo),
                        "token_acesso": token,
                        "status": "Pendente",
                        "caminho_arquivo": url_pdf_servidor, # URL do Bucket
                        "formato_curso": dados_turma.get('formato', 'Digital'),
                        "entrada_forma_pagamento": lista_entrada[0]['forma'] if lista_entrada else "N/A",
                        "saldo_forma_pagamento": f_saldo if 'f_saldo' in locals() else "N/A"
                    }
                    
                    res = ContratoRepository.criar_contrato(dados_db)
                    if res and isinstance(res, dict) and 'error' in res: raise Exception(res['error'])

                    st.session_state.url_pdf_oficial = url_pdf_servidor
                    st.session_state.ultimo_token = token
                    st.session_state.step = 4
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Falha crítica: {e}")

    # --- PASSO 4: AUDITORIA E ENVIO ---
    elif st.session_state.step == 4:
        st.success("✅ Arquivo Oficial Gerado e Sincronizado!")
        url_oficial = st.session_state.get('url_pdf_oficial')
        token = st.session_state.ultimo_token
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
        # Link que será enviado por e-mail e exibido na tela
        link_assinatura = f"{BASE_URL}/Assinatura?token={token}"

        with st.container(border=True):
            st.markdown("### 📢 Ações de Auditoria")
            st.info("Baixe o arquivo abaixo para conferir se está idêntico ao que o aluno acessará.")
            
            c1, c2 = st.columns(2)
            
            if url_oficial:
                c1.link_button("📥 Baixar PDF do Servidor", url_oficial, use_container_width=True)
            
            if c2.button("📧 Enviar Convite por E-mail", type="primary", use_container_width=True):
                with st.spinner("Enviando..."):
                    try:
                        # Ajuste na chamada para bater com a função do email_sender.py
                        sucesso = enviar_email_contrato(
                            aluno['email'], 
                            aluno['nome_completo'], 
                            link_assinatura, 
                            curso['nome']
                        )
                        if sucesso:
                            st.toast("E-mail disparado!", icon="✅")
                            st.success(f"Convite enviado para: {aluno['email']}")
                    except Exception as e: 
                        st.error(f"Erro no e-mail: {e}")

            st.divider()
            st.code(link_assinatura, language="text")

        if st.button("⬅️ Novo Contrato"):
            st.session_state.step = 1
            st.session_state.url_pdf_oficial = None
            st.rerun()

if __name__ == "__main__":
    main()
