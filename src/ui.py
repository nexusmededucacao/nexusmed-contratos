import streamlit as st
import pandas as pd
import hashlib
import time
import pytz
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta 
from src.auth import login_usuario
from src.repository import (
    get_cursos, create_curso, 
    get_turmas_by_curso, create_turma, 
    get_aluno_by_cpf, upsert_aluno, 
    create_contrato, get_contrato_by_token, registrar_aceite
)
from src.services import gerar_contrato_pdf, enviar_email, aplicar_carimbo_digital

# --- LÓGICA DE CÁLCULO (CASCATA & RESET) ---

def resetar_parcelas():
    """Reseta todas as parcelas para valores iguais quando muda o Total ou Qtd."""
    total = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    
    if qtd > 0:
        val_igual = total / qtd
        for i in range(qtd):
            st.session_state[f'ent_val_{i}'] = val_igual

def calcular_cascata():
    """Mantém a 1ª parcela fixa e distribui o restante nas outras."""
    total = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    p1 = st.session_state.get('ent_val_0', 0.0)
    
    if qtd > 1:
        restante = total - p1
        val_resto = restante / (qtd - 1)
        for i in range(1, qtd):
            st.session_state[f'ent_val_{i}'] = val_resto

# --- COMPONENTES AUXILIARES ---

def render_login():
    st.markdown("<h1 style='text-align: center;'>🔒 NexusMed Portal</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                user = login_usuario(email, senha)
                if user:
                    st.session_state['usuario'] = user
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

def render_sidebar():
    if 'usuario' not in st.session_state or not st.session_state['usuario']:
        return None
    user = st.session_state['usuario']
    st.sidebar.title(f"Olá, {user['nome'].split()[0]}")
    st.sidebar.caption(f"Perfil: {user['perfil'].upper()}")
    opcoes = ["Gerar Contrato", "Gestão de Alunos"]
    if user['perfil'] == 'admin':
        opcoes.extend(["Gestão de Cursos", "Gestão de Usuários"])
    opcoes.append("Sair")
    escolha = st.sidebar.radio("Navegação", opcoes)
    if escolha == "Sair":
        st.session_state['usuario'] = None
        st.rerun()
    return escolha

# --- TELAS DO SISTEMA ---

def tela_gestao_cursos():
    st.header("📚 Gestão de Oferta Acadêmica")
    tab1, tab2 = st.tabs(["Cursos (Produtos)", "Turmas (Calendário)"])
    with tab1:
        with st.form("form_curso"):
            st.subheader("Novo Curso")
            nome = st.text_input("Nome da Pós-Graduação")
            duracao = st.number_input("Duração (Meses)", 1, 60, 12)
            carga = st.number_input("Carga Horária", 0, 5000, 360)
            valor = st.number_input("Valor Bruto (R$)", 0.0, format="%.2f")
            if st.form_submit_button("Salvar Curso"):
                create_curso({"nome": nome, "duracao_meses": duracao, "carga_horaria": carga, "valor_bruto": valor})
                st.success("Curso criado!")
        st.divider()
        st.dataframe(pd.DataFrame(get_cursos()))

    with tab2:
        cursos = get_cursos()
        if not cursos:
            st.warning("Cadastre um curso antes de criar turmas.")
        else:
            opcoes = {c['nome']: c['id'] for c in cursos}
            nome_sel = st.selectbox("Selecione o Curso Pai", list(opcoes.keys()))
            id_sel = opcoes[nome_sel]
            with st.form("form_turma"):
                st.subheader(f"Nova Turma para {nome_sel}")
                c1, c2 = st.columns(2)
                codigo = c1.text_input("Código da Turma")
                formato = c2.selectbox("Formato", ["Digital", "Híbrido", "Presencial"])
                d1, d2 = st.columns(2)
                ini = d1.date_input("Data Início")
                fim = d2.date_input("Data Fim")
                if st.form_submit_button("Criar Turma"):
                    create_turma({"curso_id": id_sel, "codigo_turma": codigo, "formato": formato, "data_inicio": str(ini), "data_fim": str(fim)})
                    st.success("Turma criada!")
            st.dataframe(pd.DataFrame(get_turmas_by_curso(id_sel)))

def tela_gestao_alunos():
    st.header("📇 Cadastro de Alunos")
    cpf_busca = st.text_input("🔍 Buscar por CPF", max_chars=14)
    
    # ID ÚNICO PARA ESTE BOTÃO
    if st.button("Buscar Aluno", key="btn_buscar_unico"):
         with st.spinner("Buscando..."):
             encontrado = get_aluno_by_cpf(cpf_busca)
             st.session_state['dados_aluno_atual'] = encontrado if encontrado else {}

    if 'dados_aluno_atual' in st.session_state:
        dados = st.session_state['dados_aluno_atual']
        if not dados:
            st.info("Novo cadastro.")
        else:
            st.success(f"Editando: {dados.get('nome_completo')}")

        with st.form("form_aluno_completo"):
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome Completo", value=dados.get('nome_completo', ''))
            cpf = c2.text_input("CPF", value=dados.get('cpf', cpf_busca))
            rg = c3.text_input("RG", value=dados.get('rg', ''))
            c4, c5, c6 = st.columns(3)
            email = c4.text_input("E-mail", value=dados.get('email', ''))
            telefone = c5.text_input("Telefone", value=dados.get('telefone', ''))
            
            val_nasc = None
            if dados.get('data_nascimento'):
                try: val_nasc = datetime.strptime(str(dados['data_nascimento']), '%Y-%m-%d')
                except: pass
            data_nasc = c6.date_input("Data Nascimento", value=val_nasc)
            
            st.markdown("---")
            e1, e2 = st.columns([3, 1])
            logradouro = e1.text_input("Logradouro", value=dados.get('logradouro', ''))
            numero = e2.text_input("Número", value=dados.get('numero', ''))
            e3, e4, e5 = st.columns(3)
            bairro = e3.text_input("Bairro", value=dados.get('bairro', ''))
            cidade = e4.text_input("Cidade", value=dados.get('cidade', ''))
            uf = e5.text_input("UF", value=dados.get('uf', ''))
            cep = st.text_input("CEP", value=dados.get('cep', ''))
            
            p1, p2 = st.columns(2)
            crm = p1.text_input("CRM", value=dados.get('crm', ''))
            area = p2.text_input("Área", value=dados.get('area_formacao', ''))
            
            nac = st.text_input("Nacionalidade", value=dados.get('nacionalidade', 'Brasileira'))
            ec = st.selectbox("Estado Civil", ["Solteiro(a)", "Casado(a)", "Divorciado(a)"], index=0)

            if st.form_submit_button("💾 Salvar Aluno"):
                payload = {
                    "nome_completo": nome, "cpf": cpf, "rg": rg, "email": email, "telefone": telefone,
                    "data_nascimento": str(data_nasc), "nacionalidade": nac, "estado_civil": ec,
                    "logradouro": logradouro, "numero": numero, "bairro": bairro, "cidade": cidade,
                    "uf": uf, "cep": cep, "crm": crm, "area_formacao": area
                }
                upsert_aluno(payload)
                st.success("Salvo!")
                time.sleep(1)
                st.rerun()

# --- TELA DE CONTRATOS ---
def tela_novo_contrato():
    st.header("📝 Emissão de Contrato (Completo)")

    # Seleção
    c1, c2 = st.columns(2)
    cpf = c1.text_input("1. CPF Aluno")
    aluno = get_aluno_by_cpf(cpf) if cpf else None
    
    if aluno: st.success(f"Aluno: {aluno['nome_completo']}")
    else: st.warning("Aluno não encontrado.")
    
    cursos = get_cursos()
    nome_curso = c2.selectbox("2. Curso", [c['nome'] for c in cursos] if cursos else [])
    curso_sel = next((c for c in cursos if c['nome'] == nome_curso), None)
    
    turma_sel = None
    if curso_sel:
        turmas = get_turmas_by_curso(curso_sel['id'])
        if turmas:
            cod = st.selectbox("3. Turma", [t['codigo_turma'] for t in turmas])
            turma_sel = next(t for t in turmas if t['codigo_turma'] == cod)

    if not (aluno and curso_sel and turma_sel):
        st.stop()

    # Financeiro
    st.divider()
    st.subheader("💰 Configuração Financeira")
    
    v_base = float(curso_sel['valor_bruto'])
    c1, c2, c3 = st.columns(3)
    c1.metric("Valor Base", f"R$ {v_base:,.2f}")
    perc = c2.number_input("% Desconto", 0.0, 100.0, 0.0, step=0.5)
    v_desc = v_base * (perc/100)
    v_final = v_base - v_desc
    c3.metric("Final", f"R$ {v_final:,.2f}", delta=f"-{v_desc:,.2f}")

    st.markdown("---")
    st.write("### 1. Entrada Detalhada")
    
    ce1, ce2 = st.columns(2)
    # CALLBACKS
    ent_total = ce1.number_input("Total Entrada (R$)", 0.0, v_final, 0.0, step=100.0, key="ent_total_input", on_change=resetar_parcelas)
    ent_qtd = ce2.number_input("Qtd Parcelas", 1, 12, 1, key="ent_qtd_input", on_change=resetar_parcelas)
    
    detalhes_entrada = []
    val_padrao = ent_total / ent_qtd if ent_qtd > 0 else 0
    opcoes_pg = ["PIX", "Boleto", "Cartão", "Dinheiro"]
    
    if ent_qtd > 0:
        for i in range(ent_qtd):
            k_val = f"ent_val_{i}"
            if k_val not in st.session_state: st.session_state[k_val] = val_padrao
            
            c_p1, c_p2, c_p3 = st.columns([1.5, 1.5, 2])
            with c_p1:
                # 1ª Parcela tem Callback Cascata
                if i == 0:
                    vlr = st.number_input(f"Valor {i+1}", step=10.0, key=k_val, on_change=calcular_cascata)
                else:
                    vlr = st.number_input(f"Valor {i+1}", step=10.0, key=k_val)
            with c_p2:
                dt = st.date_input(f"Venc. {i+1}", value=date.today() + relativedelta(months=i), key=f"ent_dt_{i}")
            with c_p3:
                forma = st.selectbox(f"Forma {i+1}", opcoes_pg, key=f"ent_forma_{i}")
            
            detalhes_entrada.append({"numero": i+1, "valor": vlr, "data": dt, "forma": forma})

    # Saldo
    st.markdown("---")
    saldo_rest = v_final - ent_total
    st.info(f"💵 Saldo: **R$ {saldo_rest:,.2f}**")
    
    cs1, cs2, cs3 = st.columns(3)
    s_qtd = cs1.number_input("Parcelas Saldo", 1, 60, 12)
    s_ini = cs2.date_input("1º Venc. Saldo", value=date.today() + relativedelta(months=1))
    s_forma = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão", "PIX"])
    
    # --- AQUI ESTAVA FALTANDO A TABELA DE SALDO! (Recuperada) ---
    if saldo_rest > 0:
        val_parc_saldo = saldo_rest / s_qtd
        lista_saldo = []
        for i in range(s_qtd):
            dt_venc = s_ini + relativedelta(months=i)
            lista_saldo.append({
                "Parcela": f"{i+1}/{s_qtd}",
                "Vencimento": dt_venc.strftime("%d/%m/%Y"),
                "Valor": f"R$ {val_parc_saldo:,.2f}",
                "Forma": s_forma
            })
        
        with st.expander("🔎 Ver Detalhes do Saldo", expanded=False):
            st.dataframe(pd.DataFrame(lista_saldo), use_container_width=True)
    # ------------------------------------------------------------
    
    st.divider()
    cc1, cc2 = st.columns(2)
    is_bolsista = cc1.radio("Bolsista?", ["Não", "Sim"], horizontal=True)
    is_paciente = cc2.radio("Atend. Paciente?", ["Não", "Sim"], horizontal=True)
    
    st.divider()
    if 'contrato_gerado' not in st.session_state: st.session_state['contrato_gerado'] = None

    if st.button("💾 Gerar Contrato", type="primary", use_container_width=True):
        if saldo_rest < 0:
            st.error("Erro matemático.")
        else:
            with st.spinner("Gerando PDF..."):
                dados = {
                    "aluno_id": aluno['id'], "turma_id": turma_sel['id'],
                    "valor_curso": v_base, "percentual_desconto": perc,
                    "valor_desconto": v_desc, "valor_final": v_final,
                    "entrada_valor": ent_total, "entrada_qtd_parcelas": ent_qtd,
                    "saldo_valor": saldo_rest, "saldo_qtd_parcelas": s_qtd,
                    "saldo_forma_pagamento": s_forma,
                    "bolsista": True if is_bolsista=="Sim" else False,
                    "atendimento_paciente": True if is_paciente=="Sim" else False,
                    "formato_curso": turma_sel['formato']
                }
                infos = {"detalhes_entrada": detalhes_entrada, "inicio_saldo": s_ini.strftime("%Y-%m-%d")}
                
                path = gerar_contrato_pdf(aluno, turma_sel, curso_sel, dados, infos)
                if path:
                    if 'entrada_detalhes' in dados: del dados['entrada_detalhes']
                    contrato = create_contrato(dados)
                    st.session_state['contrato_gerado'] = {
                        "token": contrato['token_acesso'], "email": aluno['email'],
                        "path": path, "nome": aluno['nome_completo']
                    }
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Erro PDF. Verifique o template.")

    if st.session_state['contrato_gerado']:
        info = st.session_state['contrato_gerado']
        link = f"https://nexusmed-contratos.streamlit.app/?token={info['token']}"
        
        st.success("Contrato Criado!")
        c1, c2, c3 = st.columns([2,1,1])
        c1.text_input("Link", link)
        with c2:
            with open(info['path'], "rb") as f:
                st.download_button("Baixar PDF", f, "contrato.pdf")
        with c3:
            if st.button("Enviar E-mail"):
                enviar_email(info['email'], info['nome'], link)
                st.toast("Enviado!")
        
        if st.button("Novo Contrato"):
            st.session_state['contrato_gerado'] = None
            st.rerun()

def tela_aceite_aluno(token):
    st.set_page_config(page_title="Assinatura", layout="centered")
    data = get_contrato_by_token(token)
    if not data:
        st.error("Link inválido"); st.stop()
    
    st.title("Assinatura Digital")
    st.write(f"Aluno: {data['alunos']['nome_completo']}")
    
    if data['status'] == 'assinado':
        st.success("Já assinado!"); return

    with st.form("aceite"):
        cpf = st.text_input("Confirme seu CPF")
        chk = st.checkbox("Li e concordo.")
        if st.form_submit_button("Assinar"):
            if cpf == data['alunos']['cpf'] and chk:
                 registrar_aceite(data['id'], {"status": "assinado", "data_aceite": datetime.now().isoformat()})
                 st.success("Assinado!")
            else:
                 st.error("Erro nos dados.")
