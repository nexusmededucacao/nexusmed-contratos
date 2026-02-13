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

# --- CALLBACK PARA RECÁLCULO DA ENTRADA ---
def recalcular_parcelas_entrada():
    total = st.session_state.get('v_entrada_total_safe', 0.0)
    qtd = st.session_state.get('q_entrada_safe', 1)
    soma_acumulada = 0.0
    for i in range(qtd):
        key = f"input_ent_{i}"
        if key in st.session_state:
            val_atual = st.session_state[key]
            soma_acumulada += val_atual
            saldo_restante = total - soma_acumulada
            parcelas_restantes = qtd - (i + 1)
            if parcelas_restantes > 0:
                valor_prox = round(saldo_restante / parcelas_restantes, 2)
                for j in range(i + 1, qtd):
                    key_prox = f"input_ent_{j}"
                    st.session_state[key_prox] = max(0.0, round(total - (soma_acumulada + (valor_prox * (parcelas_restantes - 1))), 2) if j == qtd - 1 else valor_prox)
                break

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    if "url_pdf_oficial" not in st.session_state: st.session_state.url_pdf_oficial = None

    # --- PASSO 1 E 2: SELEÇÃO (Mesma lógica anterior) ---
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

    # --- PASSO 3: FINANCEIRO E "O PULO DO GATO" ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        dados_turma = st.session_state.form_data['turma']
        
        valor_bruto = float(curso.get('valor_bruto', 0))
        valor_material_calc = round(valor_bruto * 0.30, 2)
        
        percent_desc = st.number_input("Desconto Comercial (%)", 0.0, 100.0, 0.0, step=0.5)
        valor_final = round(valor_bruto - round(valor_bruto * (percent_desc / 100), 2), 2)
        st.success(f"### Valor Final: {format_currency(valor_final)}")

        # Lógica simplificada de parcelas para o teste
        v_entrada_total = st.number_input("Total Entrada", 0.0, valor_final, 0.0, key="v_entrada_total_safe")
        q_entrada = st.selectbox("Parcelas Entrada", [1, 2, 3], key="q_entrada_safe")
        saldo_restante = round(valor_final - v_entrada_total, 2)
        q_saldo = st.number_input("Parcelas Saldo", 1, 36, 12)

        if st.button("🚀 Gerar e Sincronizar com Servidor", type="primary", use_container_width=True):
            with st.spinner("Processando e enviando para o Supabase..."):
                try:
                    token = str(uuid.uuid4())
                    agora = datetime.now()
                    
                    # 1. GERAÇÃO DO CONTEXTO E DOCUMENTO
                    def get_safe(source, key, default=""): return str(source.get(key)) if source.get(key) is not None else default
                    
                    ctx_doc = {
                        'nome': get_safe(aluno, 'nome_completo').upper(),
                        'cpf': format_cpf(get_safe(aluno, 'cpf')),
                        'data_nascimento': format_date_br(aluno.get('data_nascimento')),
                        'estado_civil': get_safe(aluno, 'estado_civil', 'Solteiro(a)'),
                        'curso': get_safe(curso, 'nome'),
                        'turma': get_safe(dados_turma, 'codigo_turma'),
                        'valor_final': format_currency(valor_final).replace("R$", "").strip(),
                        'dia': agora.day, 'mês': obter_mes_extenso(agora), 'ano': agora.year
                    }

                    processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                    docx_buffer = processor.generate_docx(ctx_doc, [], []) # Tabelas vazias para o teste rápido
                    pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                    
                    # 2. UPLOAD PARA O BUCKET (Congelamento do arquivo)
                    url_pdf_servidor, erro_upload = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                    
                    if erro_upload: raise Exception(f"Erro no Upload: {erro_upload}")

                    # 3. SALVAMENTO NO BANCO COM O LINK DA NUVEM
                    dados_db = {
                        "aluno_id": aluno['id'], "turma_id": int(dados_turma['id']),
                        "valor_final": valor_final, "token_acesso": token, "status": "Pendente",
                        "caminho_arquivo": url_pdf_servidor, # Fonte Única da Verdade
                        "entrada_valor": v_entrada_total, "saldo_valor": saldo_restante
                    }
                    
                    res = ContratoRepository.criar_contrato(dados_db)
                    if res and isinstance(res, dict) and 'error' in res: raise Exception(res['error'])

                    # Transição para o sucesso
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
        link_assinatura = f"{BASE_URL}/Assinatura?token={st.session_state.ultimo_token}"

        with st.container(border=True):
            st.markdown("### 📢 Ações de Auditoria")
            st.info("Baixe o arquivo abaixo para conferir se está idêntico ao que o aluno acessará.")
            
            c1, c2 = st.columns(2)
            
            # Botão de Download direto da Nuvem (Integridade Garantida)
            if url_oficial:
                c1.link_button("📥 Baixar PDF do Servidor", url_oficial, use_container_width=True)
            
            if c2.button("📧 Enviar Convite por E-mail", type="primary", use_container_width=True):
                with st.spinner("Enviando..."):
                    try:
                        enviar_email_contrato(st.session_state.form_data['aluno']['email'], st.session_state.form_data['aluno']['nome_completo'], link_assinatura, st.session_state.form_data['curso']['nome'])
                        st.toast("E-mail disparado!", icon="✅")
                    except Exception as e: st.error(f"Erro no e-mail: {e}")

            st.divider()
            st.code(link_assinatura, language="text")

        if st.button("⬅️ Novo Contrato"):
            st.session_state.step = 1
            st.session_state.url_pdf_oficial = None
            st.rerun()

if __name__ == "__main__":
    main()
