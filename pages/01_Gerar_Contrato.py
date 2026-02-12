import streamlit as st
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# --- IMPORTAÇÕES DO PROJETO ---
from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.database.repo_contratos import ContratoRepository
from src.utils.formatters import format_currency, format_cpf
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.storage import StorageService
from src.utils.email_sender import enviar_email_contrato

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("📄 Gerador de Contratos")
    
    # Inicializa variáveis de sessão
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    
    # Cache para o PDF gerado
    if "pdf_cache" not in st.session_state: st.session_state.pdf_cache = None
    if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""

    # --- PASSO 1: SELEÇÃO DE ALUNO ---
    if st.session_state.step == 1:
        st.subheader("Etapa 1: Selecionar Aluno")
        busca = st.text_input("Buscar Aluno por Nome ou CPF", placeholder="Digite...")
        
        if busca:
            if any(char.isdigit() for char in busca):
                alunos = AlunoRepository.buscar_por_cpf(busca)
                if not alunos: alunos = AlunoRepository.filtrar_por_nome(busca)
            else:
                alunos = AlunoRepository.filtrar_por_nome(busca)

            if alunos:
                st.success(f"{len(alunos)} aluno(s) encontrado(s).")
                for a in alunos:
                    if not isinstance(a, dict): continue
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{a.get('nome_completo')}**")
                        c1.caption(f"CPF: {format_cpf(a.get('cpf'))} | Email: {a.get('email')}")
                        if c2.button("Selecionar", key=f"sel_{a['id']}"):
                            st.session_state.form_data['aluno'] = a
                            st.session_state.step = 2
                            st.rerun()
            else:
                st.warning("Nenhum aluno encontrado.")
                
        st.info("Dica: Se não encontrar, vá em 'Gestão de Alunos' para cadastrar.")

    # --- PASSO 2: CURSO E TURMA ---
    elif st.session_state.step == 2:
        st.subheader("Etapa 2: Curso e Turma")
        aluno = st.session_state.form_data.get('aluno', {})
        st.write(f"👤 Aluno: **{aluno.get('nome_completo')}**")
        
        cursos = CursoRepository.listar_todos_com_turmas()
        if not cursos:
            st.error("Nenhum curso cadastrado.")
            st.stop()
            
        map_cursos = {c['nome']: c for c in cursos}
        sel_curso = st.selectbox("Selecione o Curso", [""] + list(map_cursos.keys()))
        
        if sel_curso:
            curso_dados = map_cursos[sel_curso]
            turmas = curso_dados.get('turmas', [])
            
            if turmas:
                map_turmas = {f"{t['codigo_turma']} ({t.get('formato','-')})": t for t in turmas}
                sel_turma = st.selectbox("Selecione a Turma", list(map_turmas.keys()))
                
                if st.button("Confirmar e Avançar"):
                    st.session_state.form_data['curso'] = curso_dados
                    st.session_state.form_data['turma'] = map_turmas[sel_turma]
                    st.session_state.step = 3
                    st.rerun()
            else:
                st.warning("Curso sem turmas abertas.")
        
        if st.button("Voltar"):
            st.session_state.step = 1
            st.rerun()

    # --- PASSO 3: FINANCEIRO ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        
        # 1. VALORES DO CURSO
        curso = st.session_state.form_data['curso']
        valor_bruto = float(curso.get('valor_bruto', 0))
        valor_material_calc = valor_bruto * 0.30
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Valor Curso (Bruto)", format_currency(valor_bruto))
        c2.metric("Material Incluso (30%)", format_currency(valor_material_calc))
        
        percent_desc = c3.number_input("Desconto (%)", 0.0, 100.0, 0.0, step=1.0)
        
        # Cálculos Finais
        valor_desconto = valor_bruto * (percent_desc / 100)
        valor_final = valor_bruto - valor_desconto
        
        st.markdown(f"""
        <div style="background-color: #dcfce7; padding: 15px; border-radius: 8px; border: 1px solid #22c55e; margin-bottom: 20px;">
            <h3 style="margin:0; color: #14532d;">Valor Final: {format_currency(valor_final)}</h3>
            <small style="color: #166534;">Este é o valor total a ser pago pelo aluno (Serviço + Material).</small>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # 2. ENTRADA
        st.markdown("#### 1. Entrada")
        ce1, ce2 = st.columns([2, 1])
        v_entrada_total = ce1.number_input("Valor Total da Entrada", min_value=0.0, max_value=valor_final, value=0.0, step=50.0)
        q_entrada = ce2.selectbox("Parcelas Entrada", [1, 2, 3])
        
        lista_entrada = []
        opcoes_pagamento = ["PIX", "Cartão de Crédito", "Boleto", "Dinheiro", "Cartão de Débito"]

        if v_entrada_total > 0:
            st.caption("Detalhamento da Entrada:")
            
            with st.container(border=True):
                st.markdown("**1ª Parcela**")
                c_ep1, c_ep2, c_ep3 = st.columns(3)
                v_sugestao = v_entrada_total / q_entrada
                
                v_p1 = c_ep1.number_input("Valor", value=v_sugestao, step=10.0, key="v_e1")
                d_p1 = c_ep2.date_input("Vencimento", value=date.today(), key="d_e1")
                f_p1 = c_ep3.selectbox("Forma", opcoes_pagamento, key="f_e1")
                
                lista_entrada.append({"n": 1, "vencimento": d_p1, "valor": v_p1, "forma": f_p1})
                
            resto = v_entrada_total - v_p1
            if q_entrada > 1:
                qtd_restante = q_entrada - 1
                val_restante_base = resto / qtd_restante if resto > 0 else 0
                
                for i in range(qtd_restante):
                    n_parc = i + 2
                    with st.container(border=True):
                        st.markdown(f"**{n_parc}ª Parcela**")
                        col_a, col_b, col_c = st.columns(3)
                        key_base = f"p{n_parc}_{v_p1}_{v_entrada_total}"
                        
                        val_real = col_a.number_input("Valor", value=val_restante_base, step=10.0, key=f"v_{key_base}")
                        d_sugestao = d_p1 + relativedelta(months=i+1)
                        d_real = col_b.date_input("Vencimento", value=d_sugestao, key=f"d_{key_base}")
                        idx_forma = opcoes_pagamento.index(f_p1) if f_p1 in opcoes_pagamento else 0
                        f_real = col_c.selectbox("Forma", opcoes_pagamento, index=idx_forma, key=f"f_{key_base}")
                        
                        lista_entrada.append({"n": n_parc, "vencimento": d_real, "valor": val_real, "forma": f_real})
            
            soma_ent = sum(p['valor'] for p in lista_entrada)
            if abs(soma_ent - v_entrada_total) > 0.10:
                st.warning(f"⚠️ A soma das parcelas (R$ {soma_ent:.2f}) difere do Total da Entrada.")

        # 3. SALDO RESTANTE
        saldo = valor_final - v_entrada_total
        lista_saldo = []
        
        st.markdown("---")
        st.markdown(f"#### 2. Saldo a Parcelar: {format_currency(saldo)}")
        
        if saldo > 0.01:
            cs1, cs2, cs3 = st.columns(3)
            q_saldo = cs1.number_input("Qtd Parcelas (Máx 36)", min_value=1, max_value=36, value=1)
            d_saldo_ini = cs2.date_input("1º Vencimento Saldo", value=date.today() + relativedelta(months=1))
            f_saldo = cs3.selectbox("Forma de Pagamento Saldo", ["Boleto", "Cartão de Crédito", "PIX"], key="forma_saldo")
            
            valor_parc_saldo = saldo / q_saldo
            for i in range(q_saldo):
                lista_saldo.append({
                    "n": i+1,
                    "vencimento": d_saldo_ini + relativedelta(months=i),
                    "valor": valor_parc_saldo,
                    "forma": f_saldo
                })
        else:
            st.success("O contrato foi quitado na entrada!")

        # 4. AÇÃO FINAL
        st.divider()
        cb1, cb2 = st.columns([1, 4])
        
        if cb1.button("Voltar"):
            st.session_state.step = 2
            st.rerun()
            
        if cb2.button("🚀 Gerar Contrato e Link de Assinatura", type="primary", use_container_width=True):
            try:
                with st.spinner("Gravando dados no sistema..."):
                    # 1. DADOS PARA O BANCO (Estrutura ajustada para a tabela existente)
                    token_unico = str(uuid.uuid4())
                    
                    # Define a forma de pagamento da entrada (Pega a primeira ou padrão)
                    forma_entrada_principal = lista_entrada[0]['forma'] if lista_entrada else "Não Informado"

                    novo_contrato = {
                        "aluno_id": st.session_state.form_data['aluno']['id'],
                        "turma_id": st.session_state.form_data['turma']['id'],
                        "valor_curso": valor_bruto,
                        "percentual_desconto": percent_desc,
                        "valor_desconto": valor_desconto,  # Adicionado conforme tabela
                        "valor_final": valor_final,
                        "valor_material": valor_material_calc,
                        
                        # Entrada (Sem detalhes JSON, apenas totais e forma)
                        "entrada_valor": v_entrada_total,
                        "entrada_qtd_parcelas": len(lista_entrada),
                        "entrada_forma_pagamento": forma_entrada_principal,
                        
                        # Saldo (Sem detalhes JSON, apenas totais e forma)
                        "saldo_valor": saldo,
                        "saldo_qtd_parcelas": len(lista_saldo),
                        "saldo_forma_pagamento": f_saldo if saldo > 0 else "À Vista",
                        
                        "token_acesso": token_unico,
                        "status": "Pendente",
                        "created_at": datetime.now().isoformat()
                    }
                    
                    # 2. SALVA NO BANCO
                    res = ContratoRepository.criar_contrato(novo_contrato)
                    contrato_id = res.data[0]['id']
                    
                    # 3. GERA PDF (MINUTA)
                    aluno_nome = st.session_state.form_data['aluno']['nome_completo']
                    curso_nome = st.session_state.form_data['curso']['nome']
                    
                    ctx_doc = {
                        'nome': aluno_nome,
                        'cpf': format_cpf(st.session_state.form_data['aluno']['cpf']),
                        'curso': curso_nome,
                        'turma': st.session_state.form_data['turma']['codigo_turma'],
                        'valor_total': format_currency(valor_final),
                        'data_atual': date.today().strftime("%d/%m/%Y")
                    }
                    
                    # O Processor ainda recebe lista_saldo para preencher a tabela no Word, se existir
                    processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                    docx_buffer = processor.generate_docx(ctx_doc, lista_saldo) 
                    pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                    
                    # 4. UPLOAD PARA STORAGE
                    path_storage, nome_final_pdf = StorageService.upload_minuta(pdf_buffer, aluno_nome, curso_nome)
                    
                    if path_storage:
                        ContratoRepository.atualizar_caminho_arquivo(contrato_id, path_storage)
                    
                    # 5. SUCESSO
                    st.session_state.ultimo_token = token_unico
                    st.session_state.pdf_cache = pdf_buffer
                    st.session_state.pdf_name = nome_final_pdf
                    st.session_state.step = 4
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao salvar contrato: {e}")

    # --- PASSO 4: SUCESSO E ENVIO ---
    elif st.session_state.step == 4:
        st.balloons()
        st.success("✅ Contrato Gerado e Salvo com Sucesso!")
        
        token = st.session_state.get('ultimo_token', '')
        link_ass = f"https://nexusmed-portal.streamlit.app/Assinatura?token={token}"
        pdf_bytes = st.session_state.get('pdf_cache')
        nome_pdf = st.session_state.get('pdf_name', 'contrato.pdf')

        col_link, col_acoes = st.columns([1.5, 1])
        
        with col_link:
            st.markdown("### 🔗 Link de Assinatura")
            st.info("Copie e envie para o aluno:")
            st.code(link_ass, language="text")
            
        with col_acoes:
            st.markdown("### 📂 Ações")
            
            if pdf_bytes:
                st.download_button(
                    label="📥 Baixar PDF para Revisão",
                    data=pdf_bytes,
                    file_name=nome_pdf,
                    mime="application/pdf",
                    use_container_width=True
                )
            
            if st.button("📧 Enviar Link por E-mail", use_container_width=True):
                email_aluno = st.session_state.form_data['aluno'].get('email')
                nome_aluno = st.session_state.form_data['aluno'].get('nome_completo')
                nome_curso = st.session_state.form_data['curso'].get('nome')

                if email_aluno:
                    with st.spinner(f"Enviando para {email_aluno}..."):
                        resultado = enviar_email_contrato(email_aluno, nome_aluno, nome_curso, token)
                    
                    if resultado['success']:
                        st.toast(f"E-mail enviado!", icon="✅")
                        st.success(f"Enviado para: **{email_aluno}**")
                    else:
                        st.error(f"Falha no envio: {resultado['message']}")
                else:
                    st.warning("Aluno sem e-mail cadastrado.")
                
        st.divider()
        if st.button("🔄 Iniciar Novo Contrato"):
            st.session_state.step = 1
            st.session_state.form_data = {}
            st.session_state.pdf_cache = None
            st.rerun()

if __name__ == "__main__":
    main()
