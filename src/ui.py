import streamlit as st
import pandas as pd
import hashlib
import time
import uuid
from datetime import datetime, date
from dateutil.relativedelta import relativedelta 
from src.auth import login_usuario
from src.repository import (
    get_cursos, create_curso, get_turmas_by_curso, create_turma, 
    get_aluno_by_cpf, upsert_aluno, create_contrato, get_contrato_by_token, registrar_aceite
)
from src.services import gerar_contrato_pdf, enviar_email, aplicar_carimbo_digital

# --- LÓGICA DE CÁLCULO ---
def resetar_parcelas():
    total = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    if qtd > 0:
        val_igual = total / qtd
        for i in range(qtd): st.session_state[f'ent_val_{i}'] = val_igual

def calcular_cascata():
    total = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    p1 = st.session_state.get('ent_val_0', 0.0)
    if qtd > 1:
        restante = total - p1
        val_resto = restante / (qtd - 1)
        for i in range(1, qtd): st.session_state[f'ent_val_{i}'] = val_resto

# --- COMPONENTES ---
def render_login():
    st.markdown("<h1 style='text-align: center;'>🔒 NexusMed Portal</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        with st.form("login"):
            email = st.text_input("Email"); senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                user = login_usuario(email, senha)
                if user: st.session_state['usuario'] = user; st.rerun()
                else: st.error("Erro login")

def render_sidebar():
    if 'usuario' not in st.session_state or not st.session_state['usuario']: return None
    st.sidebar.title(f"Olá {st.session_state['usuario']['nome'].split()[0]}")
    op = ["Gerar Contrato", "Gestão de Alunos"]
    if st.session_state['usuario']['perfil'] == 'admin': op.extend(["Gestão de Cursos", "Gestão de Usuários"])
    op.append("Sair")
    esc = st.sidebar.radio("Menu", op)
    if esc == "Sair": st.session_state['usuario'] = None; st.rerun()
    return esc

# --- TELAS ---
def tela_gestao_cursos():
    t1, t2 = st.tabs(["Cursos", "Turmas"])
    with t1:
        with st.form("fc"):
            n = st.text_input("Nome"); d = st.number_input("Meses", 1); c = st.number_input("Horas", 0); v = st.number_input("R$", 0.0)
            if st.form_submit_button("Salvar"): create_curso({"nome":n,"duracao_meses":d,"carga_horaria":c,"valor_bruto":v}); st.success("Ok")
        st.dataframe(pd.DataFrame(get_cursos()))
    with t2:
        cs = get_cursos()
        if cs:
            ops = {c['nome']:c['id'] for c in cs}; sel = st.selectbox("Curso", list(ops.keys())); idc = ops[sel]
            with st.form("ft"):
                cd = st.text_input("Cod"); fmt = st.selectbox("Fmt", ["Digital","Híbrido","Presencial"]); i = st.date_input("Ini"); f = st.date_input("Fim")
                if st.form_submit_button("Criar"): create_turma({"curso_id":idc,"codigo_turma":cd,"formato":fmt,"data_inicio":str(i),"data_fim":str(f)}); st.success("Ok")
            st.dataframe(pd.DataFrame(get_turmas_by_curso(idc)))

def tela_gestao_alunos():
    cpf = st.text_input("Busca CPF")
    if st.button("Buscar", key="bb"):
        f = get_aluno_by_cpf(cpf)
        st.session_state['cur_al'] = f if f else {}
    if 'cur_al' in st.session_state:
        d = st.session_state['cur_al']
        with st.form("fa"):
            c1,c2 = st.columns(2)
            nm = c1.text_input("Nome", d.get('nome_completo','')); cp = c2.text_input("CPF", d.get('cpf',cpf))
            em = c1.text_input("Email", d.get('email','')); tel = c2.text_input("Tel", d.get('telefone',''))
            rg = c1.text_input("RG", d.get('rg','')); crm = c2.text_input("CRM", d.get('crm',''))
            end = st.text_input("Endereço", d.get('logradouro','')); num = st.text_input("Nº", d.get('numero',''))
            cid = st.text_input("Cidade", d.get('cidade','')); uf = st.text_input("UF", d.get('uf','')); cep = st.text_input("CEP", d.get('cep',''))
            if st.form_submit_button("Salvar"):
                upsert_aluno({"nome_completo":nm,"cpf":cp,"email":em,"telefone":tel,"rg":rg,"crm":crm,"logradouro":end,"numero":num,"cidade":cid,"uf":uf,"cep":cep})
                st.success("Salvo"); st.rerun()

def tela_novo_contrato():
    st.header("📝 Novo Contrato")
    c1, c2 = st.columns(2)
    cpf = c1.text_input("CPF Aluno")
    al = get_aluno_by_cpf(cpf) if cpf else None
    if al: st.success(al['nome_completo'])
    
    cs = get_cursos()
    nc = c2.selectbox("Curso", [c['nome'] for c in cs] if cs else [])
    c_sel = next((c for c in cs if c['nome'] == nc), None)
    t_sel = None
    if c_sel:
        ts = get_turmas_by_curso(c_sel['id'])
        if ts:
            cod = st.selectbox("Turma", [t['codigo_turma'] for t in ts])
            t_sel = next(t for t in ts if t['codigo_turma'] == cod)

    if not (al and c_sel and t_sel): st.stop()

    st.divider()
    vb = float(c_sel['valor_bruto'])
    k1, k2, k3 = st.columns(3)
    k1.metric("Valor", f"R$ {vb:,.2f}")
    perc = k2.number_input("% Desc", 0.0, 100.0, 0.0, step=0.5)
    vd = vb*(perc/100); vf = vb-vd
    k3.metric("Final", f"R$ {vf:,.2f}")

    st.write("### Entrada")
    ce1, ce2 = st.columns(2)
    et = ce1.number_input("Total Entrada", 0.0, vf, 0.0, step=100.0, key="ent_total_input", on_change=resetar_parcelas)
    eq = ce2.number_input("Qtd", 1, 12, 1, key="ent_qtd_input", on_change=resetar_parcelas)
    
    det_ent = []
    forma_resumo = "Boleto"
    vp = et/eq if eq>0 else 0
    if eq>0:
        for i in range(eq):
            k = f"ent_val_{i}"
            if k not in st.session_state: st.session_state[k] = vp
            c1,c2,c3 = st.columns([1,1,2])
            v = c1.number_input(f"V{i+1}", step=10.0, key=k, on_change=calcular_cascata if i==0 else None)
            d = c2.date_input(f"D{i+1}", date.today()+relativedelta(months=i), key=f"dt_{i}")
            f = c3.selectbox(f"F{i+1}", ["PIX","Boleto","Cartão"], key=f"fm_{i}")
            det_ent.append({"numero":i+1,"valor":v,"data":d,"forma":f})
            if i==0: forma_resumo=f

    st.write("### Saldo")
    sr = vf-et
    st.info(f"Saldo: R$ {sr:,.2f}")
    cs1, cs2, cs3 = st.columns(3)
    sq = cs1.number_input("Qtd Saldo", 1, 60, 12)
    si = cs2.date_input("1º Venc", date.today()+relativedelta(months=1))
    sf = cs3.selectbox("Forma", ["Boleto","Cartão","PIX"])
    
    cc1, cc2 = st.columns(2)
    bol = cc1.checkbox("Bolsista"); pac = cc2.checkbox("Paciente")

    if st.button("💾 Gerar Contrato", type="primary"):
        with st.spinner("Gerando..."):
            token = str(uuid.uuid4())
            dados = {
                "aluno_id": al['id'], "turma_id": t_sel['id'],
                "valor_curso": vb, "percentual_desconto": perc, "valor_desconto": vd, "valor_final": vf, "valor_material": 0.0,
                "entrada_valor": et, "entrada_qtd_parcelas": eq, "entrada_forma_pagamento": forma_resumo,
                "saldo_valor": sr, "saldo_qtd_parcelas": sq, "saldo_forma_pagamento": sf,
                "bolsista": bol, "atendimento_paciente": pac, "formato_curso": t_sel['formato'],
                "token_acesso": token, "status": "pendente"
            }
            infos = {"detalhes_entrada": det_ent, "inicio_saldo": str(si)}
            
            # RETORNA DOIS CAMINHOS
            retorno_paths = gerar_contrato_pdf(al, t_sel, c_sel, dados, infos)
            
            if retorno_paths:
                local_path, cloud_path = retorno_paths
                dados['caminho_arquivo'] = cloud_path # Salva nuvem no banco
                
                res = create_contrato(dados)
                if res:
                    st.session_state['contrato_gerado'] = {
                        "token": token, "email": al['email'],
                        "local_path": local_path, # Usa local para download
                        "nome": al['nome_completo']
                    }
                    st.balloons(); st.rerun()
                else: st.error("Erro Banco")
            else: st.error("Erro PDF")

    if st.session_state.get('contrato_gerado'):
        info = st.session_state['contrato_gerado']
        link = f"https://nexusmed-contratos.streamlit.app/?token={info['token']}"
        st.success("Sucesso!")
        st.text_input("Link", link)
        
        # Tenta baixar do local, se falhar (refresh), avisa
        try:
            with open(info['local_path'], "rb") as f:
                st.download_button("Baixar PDF", f, "contrato.pdf")
        except FileNotFoundError:
            st.warning("Arquivo temporário expirou. Gere novamente para baixar.")
            
        if st.button("Enviar Email"): enviar_email(info['email'], info['nome'], link); st.toast("Enviado!")
        if st.button("Novo"): st.session_state['contrato_gerado']=None; st.rerun()

def tela_aceite_aluno(token):
    st.title("Assinatura")
    d = get_contrato_by_token(token)
    if not d: st.error("Inválido"); return
    st.write(f"Aluno: {d['alunos']['nome_completo']}")
    if d['status']=='assinado': st.success("Já assinado"); return
    if st.button("ASSINAR"):
        registrar_aceite(d['id'], {"status":"assinado","data_aceite":str(datetime.now())})
        st.success("OK"); st.balloons()
