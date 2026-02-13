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

# --- CALLBACK PARA RECÁLCULO AUTOMÁTICO DA ENTRADA ---
def recalcular_parcelas_entrada():
    """
    Recalcula as parcelas seguintes da entrada quando o usuário edita uma anterior.
    """
    # Usamos session_state para pegar os valores mais recentes
    total = st.session_state.get('v_entrada_total_safe', 0.0)
    qtd = st.session_state.get('q_entrada_safe', 1)
    
    soma_acumulada = 0.0
    
    for i in range(qtd):
        key = f"input_ent_{i}"
        
        # Se a chave existe (o widget já foi criado/editado)
        if key in st.session_state:
            val_atual = st.session_state[key]
            soma_acumulada += val_atual
            
            # Quanto falta para completar a entrada?
            saldo_restante = total - soma_acumulada
            parcelas_restantes = qtd - (i + 1)
            
            # Se ainda tem parcelas para frente, distribui o saldo
            if parcelas_restantes > 0:
                # Divide o que sobrou igualmente
                valor_prox = round(saldo_restante / parcelas_restantes, 2)
                
                # Aplica nos inputs seguintes
                for j in range(i + 1, qtd):
                    key_prox = f"input_ent_{j}"
                    
                    # A última parcela pega a diferença exata (ajuste de centavos)
                    if j == qtd - 1:
                        # (Total - (tudo que já foi somado + parcelas intermediárias))
                        val_prox_final = round(total - (soma_acumulada + (valor_prox * (parcelas_restantes - 1))), 2)
                        st.session_state[key_prox] = max(0.0, val_prox_final)
                    else:
                        st.session_state[key_prox] = max(0.0, valor_prox)
                
                # Interrompe o loop pois já recalculamos o futuro com base na edição atual
                break

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    if "pdf_buffer_cache" not in st.session_state: st.session_state.pdf_buffer_cache = None

    # --- PASSO 1: SELEÇÃO DE ALUNO ---
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
        st.info(f"👤 Aluno: {aluno.get('nome_completo')}")
        
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

    # --- PASSO 3: FINANCEIRO ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
        valor_bruto = float(curso.get('valor_bruto', 0))
        valor_material_calc = round(valor_bruto * 0.30, 2)
        
        st.markdown(f"""
        <div style="background-color: #f0f9ff; padding: 15px; border-radius: 8px; border-left: 5px solid #0ea5e9; margin-bottom: 20px;">
            <h4 style="margin:0; color: #0369a1;">📚 Detalhamento do Produto</h4>
            <p style="margin:5px 0 0 0; font-size: 14px;">Valor Bruto do Curso: <b>{format_currency(valor_bruto)}</b></p>
            <p style="margin:2px 0 0 0; font-size: 14px; color: #0c4a6e;">
                Valor destinado ao Material Didático: <b>{format_currency(valor_material_calc)}</b> (30% conforme Cláusula 13ª).
            </p>
        </div>
        """, unsafe_allow_html=True)

        percent_desc = st.number_input("Desconto Comercial (%)", 0.0, 100.0, 0.0, step=0.5)
        valor_desconto = round(valor_bruto * (percent_desc / 100), 2)
        valor_final = round(valor_bruto - valor_desconto, 2)

        st.success(f"### Valor Final do Contrato: {format_currency(valor_final)}")
        st.divider()

        # 1. ENTRADA (CORREÇÃO DO TRAVAMENTO)
        st.markdown("#### 1. Pagamento de Entrada / À Vista")
        ce1, ce2 = st.columns(2)
        
        v_entrada_total = ce1.number_input("Valor Total da Entrada", 0.0, valor_final, 0.0, step=100.0, key="v_entrada_total_safe")
        q_entrada = ce2.selectbox("Qtd. Parcelas Entrada", [1, 2, 3], key="q_entrada_safe")
        
        # Inicializa valores da entrada (reset inteligente)
        if "last_v_entrada" not in st.session_state or st.session_state.last_v_entrada != v_entrada_total or st.session_state.last_q_entrada != q_entrada:
            st.session_state.last_v_entrada = v_entrada_total
            st.session_state.last_q_entrada = q_entrada
            
            v_base = round(v_entrada_total / q_entrada, 2) if q_entrada > 0 else 0
            for k in range(q_entrada):
                key_p = f"input_ent_{k}"
                # Ajuste de centavos na última parcela
                if k == q_entrada - 1:
                    v_final_p = round(v_entrada_total - (v_base * (q_entrada - 1)), 2)
                    st.session_state[key_p] = max(0.0, v_final_p)
                else:
                    st.session_state[key_p] = v_base

        lista_entrada = []
        opcoes_pagamento = ["PIX", "Cartão de Crédito", "Boleto", "Transferência"]
        
        if v_entrada_total > 0:
            for i in range(q_entrada):
                with st.container(border=True):
                    c_e1, c_e2, c_e3 = st.columns(3)
                    key_val = f"input_ent_{i}"
                    
                    # --- CORREÇÃO DO CRASH ---
                    # Antes de criar o widget, garantimos que o valor no session_state não ultrapasse o contrato.
                    # Mas no widget, usamos max_value = valor_final (bem alto) para não travar a UI durante a digitação.
                    if key_val in st.session_state:
                         if st.session_state[key_val] > valor_final:
                             st.session_state[key_val] = valor_final

                    v_p = c_e1.number_input(
                        f"Valor P{i+1}", 
                        min_value=0.0, 
                        max_value=float(valor_final), # EVITA O CRASH: O limite é o contrato todo
                        step=0.01,
                        key=key_val,
                        on_change=recalcular_parcelas_entrada
                    )
                    
                    d_p = c_e2.date_input(f"Vencimento P{i+1}", value=date.today() + relativedelta(days=i*30), key=f"dent_{i}")
                    f_p = c_e3.selectbox(f"Forma P{i+1}", opcoes_pagamento, key=f"fent_{i}")
                    
                    lista_entrada.append({"numero": i+1, "data": d_p.strftime("%d/%m/%Y"), "valor": format_currency(v_p), "forma": f_p, "valor_num": v_p})

            # Validação visual de soma
            soma_entrada = sum(p['valor_num'] for p in lista_entrada)
            if round(soma_entrada, 2) != round(v_entrada_total, 2):
                st.warning(f"⚠️ Atenção: A soma das parcelas ({format_currency(soma_entrada)}) difere do total da entrada.")

        # 2. SALDO
        saldo_restante = round(valor_final - v_entrada_total, 2)
        lista_saldo = []
        
        if saldo_restante > 0:
            st.divider()
            st.markdown(f"#### 2. Saldo Remanescente: {format_currency(saldo_restante)}")
            cs1, cs2, cs3 = st.columns(3)
            q_saldo = cs1.number_input("Qtd Parcelas Saldo", 1, 36, 12)
            d_saldo_ini = cs2.date_input("1º Vencimento Saldo", value=date.today() + relativedelta(months=1))
            f_saldo = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão de Crédito", "PIX"])
            
            v_base_saldo = round(saldo_restante / q_saldo, 2)
            soma_acumulada_saldo = 0
            for i in range(q_saldo):
                v_parc = round(saldo_restante - soma_acumulada_saldo, 2) if i == q_saldo - 1 else v_base_saldo
                soma_acumulada_saldo += v_parc
                venc_p = d_saldo_ini + relativedelta(months=i)
                lista_saldo.append({
                    "Parcela": f"{i+1}/{q_saldo}", "Vencimento": venc_p.strftime("%d/%m/%Y"),
                    "Valor": format_currency(v_parc), "Forma": f_saldo, "valor_num": v_parc
                })
            
            with st.expander("📊 Ver Tabela Detalhada de Vencimentos"):
                st.dataframe(lista_saldo, column_order=["Parcela", "Vencimento", "Valor", "Forma"], hide_index=True, use_container_width=True)

        # 3. VALIDAÇÃO E GERAÇÃO
        soma_total = sum(p['valor_num'] for p in lista_entrada) + sum(p['valor_num'] for p in lista_saldo)
        entrada_ok = True if v_entrada_total == 0 else abs(sum(p['valor_num'] for p in lista_entrada) - v_entrada_total) <= 0.05
        total_ok = abs(round(soma_total, 2) - valor_final) <= 0.05
        
        st.divider()
        if not entrada_ok: st.error("❌ Erro na Entrada: Soma das parcelas não bate com o total definido.")
        elif not total_ok: st.error(f"❌ Erro Global: Soma total ({format_currency(soma_total)}) difere do contrato.")
        
        c_b1, c_b2 = st.columns([1, 4])
        if c_b1.button("Voltar"): st.session_state.step = 2; st.rerun()
        
        if c_b2.button("🚀 Gerar Contrato", type="primary", disabled=not (entrada_ok and total_ok), use_container_width=True):
            with st.spinner("Gerando Documentos..."):
                token = str(uuid.uuid4())
                agora = datetime.now()
                
                # --- FUNÇÕES AUXILIARES DE DADOS ---
                def get_safe(source, key, default=""):
                    val = source.get(key)
                    return str(val) if val is not None else default

                def format_money_word(valor):
                    return format_currency(valor).replace("R$", "").strip()

                # Tratamento Data Nascimento
                d_nasc = aluno.get('data_nascimento', '')
                try:
                    if isinstance(d_nasc, str) and d_nasc: 
                        d_nasc_fmt = datetime.strptime(d_nasc, "%Y-%m-%d").strftime("%d/%m/%Y")
                    elif isinstance(d_nasc, (date, datetime)): 
                        d_nasc_fmt = d_nasc.strftime("%d/%m/%Y")
                    else: d_nasc_fmt = ""
                except: d_nasc_fmt = str(d_nasc)

                # --- DEFINIÇÃO OBRIGATÓRIA DA TURMA ---
                dados_turma = st.session_state.form_data['turma']

                # Contexto Word (Mapeamento EXATO para suas tags)
                ctx_doc = {
                    # 1. DADOS DO ALUNO
                    'nome': get_safe(aluno, 'nome_completo').upper(),
                    'cpf': format_cpf(get_safe(aluno, 'cpf')),
                    'rg': get_safe(aluno, 'rg'),
                    'orgao_emissor': get_safe(aluno, 'orgao_emissor'),
                    'nacionalidade': get_safe(aluno, 'nacionalidade', 'Brasileira'),
                    'estado_civil': get_safe(aluno, 'estado_civil', 'Solteiro(a)'),
                    'data_nascimento': d_nasc_fmt,
                    'email': get_safe(aluno, 'email'),
                    'telefone': get_safe(aluno, 'telefone'),
                    'celular': get_safe(aluno, 'telefone'),
                    'crm': get_safe(aluno, 'crm'),
                    'area_formacao': get_safe(aluno, 'area_formacao', get_safe(aluno, 'especialidade', '')),
                    
                    'logradouro': get_safe(aluno, 'logradouro'),
                    'numero': get_safe(aluno, 'numero'),
                    'complemento': get_safe(aluno, 'complemento'),
                    'bairro': get_safe(aluno, 'bairro'),
                    'cidade': get_safe(aluno, 'cidade'),
                    'uf': get_safe(aluno, 'uf'),
                    'cep': get_safe(aluno, 'cep'),

                    # 2. DADOS DO PRODUTO (Corrigido para seu modelo)
                    'curso': get_safe(curso, 'nome'),
                    'pos_graduacao': get_safe(curso, 'nome'),
                    
                    # Correção: codigo_turma (conforme sua tabela)
                    'codigo_turma': get_safe(dados_turma, 'codigo_turma'), 
                    
                    # Correção: formato (conforme sua tabela) para a tag formato_curso
                    'formato_curso': get_safe(dados_turma, 'formato', 'EAD'),
                    
                    # Correção: atendimento (com padrão 'Sim' ou 'Não')
                    'atendimento': get_safe(dados_turma, 'atendimento', 'Sim'), 

                    # 3. FINANCEIRO
                    'valor_curso': format_money_word(valor_bruto),
                    'valor_desconto': format_money_word(valor_desconto),
                    'pencentual_desconto': f"{percent_desc}", 
                    'valor_final': format_money_word(valor_final),
                    'valor_material': format_money_word(valor_material_calc),
                    'bolsista': "SIM" if percent_desc > 0 else "NÃO",
                    
                    # 4. DATAS
                    'dia': agora.day, 'mês': obter_mes_extenso(agora), 'ano': agora.year,
                    'data_atual': format_date_br(agora)
                }

                tab_ent = [{"n": p["numero"], "vencimento": p["data"], "valor": p["valor"], "forma": p["forma"]} for p in lista_entrada]
                tab_sal = [{"n": p["Parcela"], "vencimento": p["Vencimento"], "valor": p["Valor"], "forma": p["Forma"]} for p in lista_saldo]
                
                processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                docx_buffer = processor.generate_docx(ctx_doc, tab_ent, tab_sal)
                pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                
                st.session_state.pdf_buffer_cache = pdf_buffer

                path_s, _ = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                
                ContratoRepository.criar_contrato({
                    "aluno_id": aluno['id'], 
                    "turma_id": st.session_state.form_data['turma']['id'],
                    "valor_final": valor_final, "token_acesso": token, "status": "Pendente",
                    "caminho_arquivo": path_s, "valor_desconto": valor_desconto, "valor_material": valor_material_calc,
                    "entrada_valor": v_entrada_total, "saldo_valor": saldo_restante, "saldo_qtd_parcelas": q_saldo
                })
                
                st.session_state.ultimo_token = token
                st.session_state.step = 4
                st.rerun()

    # --- PASSO 4: PAINEL DE AÇÃO ---
    elif st.session_state.step == 4:
        st.success("✅ Contrato Gerado com Sucesso!")
        
        token = st.session_state.ultimo_token
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
        link_assinatura = f"http://localhost:8501/Assinatura?token={token}"

        with st.container(border=True):
            st.markdown("### 📢 Ações Disponíveis")
            st.write("Escolha como deseja prosseguir com este contrato:")
            
            c1, c2 = st.columns(2)
            
            if st.session_state.pdf_buffer_cache:
                c1.download_button(
                    label="📥 Baixar PDF do Contrato",
                    data=st.session_state.pdf_buffer_cache,
                    file_name=f"Contrato_{aluno['nome_completo']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            if c2.button("📧 Enviar por E-mail", type="primary", use_container_width=True):
                with st.spinner("Enviando e-mail..."):
                    try:
                        enviar_email_contrato(
                            destinatario_email=aluno['email'],
                            destinatario_nome=aluno['nome_completo'],
                            link_assinatura=link_assinatura,
                            nome_curso=curso['nome']
                        )
                        st.toast("E-mail enviado com sucesso!", icon="✅")
                        st.success(f"Convite enviado para: {aluno['email']}")
                    except Exception as e:
                        st.error(f"Falha no envio: {e}")

            st.divider()
            st.markdown("**🔗 Link para WhatsApp:**")
            st.code(link_assinatura, language="text")

        if st.button("⬅️ Iniciar Novo Contrato"):
            st.session_state.step = 1
            st.session_state.form_data = {}
            st.rerun()

if __name__ == "__main__":
    main()
