import streamlit as st
import pandas as pd
import hashlib
import time
import uuid  # Importante para gerar o token UUID compatível com o banco
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
    total = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    if qtd > 0:
        val_igual = total / qtd
        for i in range(qtd):
            st.session_state[f'ent_val_{i}'] = val_igual

def calcular_cascata():
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
            if st.form_submit_button("Entrar", use_container_width=True):
                user = login_usuario(email, senha)
                if user:
                    st.session_state['usuario'] = user
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

def render_sidebar():
    if 'usuario' not in st.session_state or not st.session_state['usuario']: return None
    user = st.session_state['usuario']
    st.sidebar.title(f"Olá, {user['nome'].split()[0]}")
    opcoes = ["Gerar Contrato", "Gestão de Alunos"]
    if user['perfil'] == 'admin': opcoes.extend(["Gestão de Cursos", "Gestão de Usuários"])
    opcoes.append("Sair")
    escolha = st.sidebar.radio("Navegação", opcoes)
    if escolha == "Sair":
        st.session_state['usuario'] = None
        st.rerun()
    return escolha

# --- TELAS DE GESTÃO ---
def tela_gestao_cursos():
    st.header("📚 Gestão Acadêmica")
    t1, t2 = st.tabs(["Cursos", "Turmas"])
    with t1:
        with st.form("fc"):
            n = st.text_input("Nome"); d = st.number_input("Meses", 1); c = st.number_input("Horas", 0); v = st.number_input("Valor", 0.0)
            if st.form_submit_button("Salvar"): create_curso({"nome":n,"duracao_meses":d,"carga_horaria":c,"valor_bruto":v}); st.success("Ok!")
        st.dataframe(pd.DataFrame(get_cursos()))
    with t2:
        cs = get_cursos()
        if cs:
            ops = {c['nome']:c['id'] for c in cs}; sel = st.selectbox("Curso", list(ops.keys())); id_c = ops[sel]
            with st.form("ft"):
                cod = st.text_input("Cód"); fmt = st.selectbox("Fmt", ["Digital","Híbrido","Presencial"]); i = st.date_input("Ini"); f = st.date_input("Fim")
                if st.form_submit_button("Criar"): create_turma({"curso_id":id_c,"codigo_turma":cod,"formato":fmt,"data_inicio":str(i),"data_fim":str(f)}); st.success("Ok!")
            st.dataframe(pd.DataFrame(get_turmas_by_curso(id_c)))

def tela_gestao_alunos():
    st.header("📇 Alunos")
    cpf = st.text_input("CPF Busca")
    if st.button("Buscar", key="btn_b_uni"):
        found = get_aluno_by_cpf(cpf)
        st.session_state['dad_al'] = found if found else {}
    
    if 'dad_al' in st.session_state:
        d = st.session_state['dad_al']
        if not d: st.info("Novo Aluno")
        else: st.success(f"Editando: {d.get('nome_completo')}")
        
        with st.form("fa"):
            c1,c2 = st.columns(2)
            nm = c1.text_input("Nome", d.get('nome_completo','')); cp = c2.text_input("CPF", d.get('cpf',cpf))
            em = c1.text_input("Email", d.get('email','')); tel = c2.text_input("Tel", d.get('telefone',''))
            rg = c1.text_input("RG", d.get('rg','')); crm = c2.text_input("CRM", d.get('crm',''))
            log = st.text_input("Endereço", d.get('logradouro','')); num = st.text_input("Nº", d.get('numero',''))
            cid = st.text_input("Cidade", d.get('cidade','')); uf = st.text_input("UF", d.get('uf',''))
            cep = st.text_input("CEP", d.get('cep',''))
            
            # Campos extras para compatibilidade
            nac = d.get('nacionalidade', 'Brasileira')
            ec = d.get('estado_civil', 'Solteiro(a)')
            area = d.get('area_formacao', 'Médica')

            if st.form_submit_button("Salvar"):
                upsert_aluno({
                    "nome_completo":nm,"cpf":cp,"email":em,"telefone":tel,"rg":rg,"crm":crm,
                    "logradouro":log,"numero":num,"cidade":cid,"uf":uf,"cep":cep,
                    "nacionalidade": nac, "estado_civil": ec, "area_formacao": area
                })
                st.success("Salvo!"); st.rerun()

# --- TELA DE CONTRATO (AJUSTADA AO BANCO) ---
def tela_novo_contrato():
    st.header("📝 Emissão de Contrato")
    c1, c2 = st.columns(2)
    cpf = c1.text_input("CPF Aluno")
    aluno = get_aluno_by_cpf(cpf) if cpf else None
    if aluno: st.success(aluno['nome_completo'])
    
    cs = get_cursos()
    nc = c2.selectbox("Curso", [c['nome'] for c in cs] if cs else [])
    c_sel = next((c for c in cs if c['nome'] == nc), None)
    
    t_sel = None
    if c_sel:
        ts = get_turmas_by_curso(c_sel['id'])
        if ts:
            cod = st.selectbox("Turma", [t['codigo_turma'] for t in ts])
            t_sel = next(t for t in ts if t['codigo_turma'] == cod)

    if not (aluno and c_sel and t_sel): st.stop()

    # Financeiro
    st.divider()
    vb = float(c_sel['valor_bruto'])
    col1, col2, col3 = st.columns(3)
    col1.metric("Valor", f"R$ {vb:,.2f}")
    perc = col2.number_input("% Desc", 0.0, 100.0, 0.0, step=0.5)
    vd = vb * (perc/100); vf = vb - vd
    col3.metric("Final", f"R$ {vf:,.2f}", delta=f"-{vd:,.2f}")

    # Entrada Detalhada
    st.write("### Entrada")
    ce1, ce2 = st.columns(2)
    et = ce1.number_input("Total Entrada", 0.0, vf, 0.0, step=100.0, key="ent_total_input", on_change=resetar_parcelas)
    eq = ce2.number_input("Qtd Parc", 1, 12, 1, key="ent_qtd_input", on_change=resetar_parcelas)
    
    det_ent = []
    forma_entrada_resumo = "Boleto" # Valor padrão para o banco
    
    vp = et/eq if eq>0 else 0
    if eq>0:
        for i in range(eq):
            k=f"ent_val_{i}"
            if k not in st.session_state: st.session_state[k] = vp
            c1,c2,c3 = st.columns([1,1,2])
            if i==0: v = c1.number_input(f"V{i+1}", step=10.0, key=k, on_change=calcular_cascata)
            else: v = c1.number_input(f"V{i+1}", step=10.0, key=k)
            d = c2.date_input(f"D{i+1}", date.today()+relativedelta(months=i), key=f"dt_{i}")
            f = c3.selectbox(f"F{i+1}", ["PIX","Boleto","Cartão","Dinheiro"], key=f"fm_{i}")
            det_ent.append({"numero":i+1,"valor":v,"data":d,"forma":f})
            
            if i == 0: forma_entrada_resumo = f # Pega a forma da 1ª parcela para salvar no banco

    # Saldo
    st.write("### Saldo")
    sr = vf - et
    st.info(f"Saldo: R$ {sr:,.2f}")
    cs1, cs2, cs3 = st.columns(3)
    sq = cs1.number_input("Qtd Saldo", 1, 60, 12)
    si = cs2.date_input("1º Venc", date.today()+relativedelta(months=1))
    sf = cs3.selectbox("Forma", ["Boleto","Cartão","PIX"])
    
    if sr > 0:
        lp = []
        vps = sr/sq
        for i in range(sq):
            lp.append({"Parc":f"{i+1}/{sq}", "Data":(si+relativedelta(months=i)).strftime("%d/%m/%Y"), "Valor":f"R$ {vps:,.2f}"})
        with st.expander("Ver Parcelas"): st.dataframe(pd.DataFrame(lp))

    cc1, cc2 = st.columns(2)
    bol = cc1.checkbox("Bolsista"); pac = cc2.checkbox("Paciente")

    if st.button("💾 Gerar Contrato", type="primary"):
        if sr < 0: st.error("Erro valores")
        else:
            with st.spinner("Gerando..."):
                # --- GERAÇÃO DO TOKEN NO PYTHON (Seguro e compatível com UUID do banco) ---
                token_novo = str(uuid.uuid4())
                
                # Monta o dicionário EXATAMENTE igual às colunas do banco
                dados = {
                    "aluno_id": aluno['id'], 
                    "turma_id": t_sel['id'],
                    "valor_curso": vb, 
                    "percentual_desconto": perc,
                    "valor_desconto": vd, 
                    "valor_final": vf,
                    "valor_material": 0.0, # Campo obrigatório no banco, enviando 0.0
                    "entrada_valor": et, 
                    "entrada_qtd_parcelas": eq,
                    "entrada_forma_pagamento": forma_entrada_resumo, # Envia resumo (ex: "PIX")
                    "saldo_valor": sr, 
                    "saldo_qtd_parcelas": sq,
                    "saldo_forma_pagamento": sf,
                    "bolsista": bol, 
                    "atendimento_paciente": pac,
                    "formato_curso": t_sel['formato'], # Coluna criada no banco
                    "token_acesso": token_novo, # Coluna criada no banco (UUID)
                    "status": "pendente" # Campo status
                }
                
                # Informações extras para o PDF (não vão pro banco)
                infos = {"detalhes_entrada": det_ent, "inicio_saldo": str(si)}
                
                # Gera PDF
                path = gerar_contrato_pdf(aluno, t_sel, c_sel, dados, infos)
                
                if path:
                    dados['caminho_arquivo'] = path
                    
                    # Salva no Banco
                    res = create_contrato(dados)
                    
                    # Usa o token gerado localmente, independente do retorno do banco
                    st.session_state['contrato_gerado'] = {
                        "token": token_novo,
                        "email": aluno['email'],
                        "path": path, 
                        "nome": aluno['nome_completo']
                    }
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Erro na geração do PDF")

    if st.session_state.get('contrato_gerado'):
        info = st.session_state['contrato_gerado']
        link = f"https://nexusmed-contratos.streamlit.app/?token={info['token']}"
        st.success("Sucesso!")
        st.text_input("Link", link)
        with open(info['path'], "rb") as f: st.download_button("Baixar PDF", f, "contrato.pdf")
        if st.button("Enviar Email"): enviar_email(info['email'],info['nome'],link); st.toast("Enviado!")
        if st.button("Novo"): st.session_state['contrato_gerado']=None; st.rerun()

def tela_aceite_aluno(token):
    st.title("Assinatura"); 
    d = get_contrato_by_token(token)
    if not d: st.error("Link inválido"); return
    st.write(f"Aluno: {d['alunos']['nome_completo']}")
    if d['status']=='assinado': st.success("Assinado!"); return
    if st.button("ASSINAR"):
        registrar_aceite(d['id'], {"status":"assinado","data_aceite":str(datetime.now())})
        st.success("OK!"); st.balloons()
