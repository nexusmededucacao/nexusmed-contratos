import streamlit as st
import pandas as pd
import uuid
import hashlib
import time
import pytz
from datetime import datetime, date
from dateutil.relativedelta import relativedelta 
from src.auth import login_usuario
from src.repository import (
    get_cursos, create_curso, get_turmas_by_curso, create_turma, 
    get_aluno_by_cpf, upsert_aluno, create_contrato, get_contrato_by_token, registrar_aceite
)
from src.services import gerar_contrato_pdf, enviar_email, aplicar_carimbo_digital

# --- UTILS E RESET ---
def get_ip():
    try: return st.context.headers.get("X-Forwarded-For", "IP_DESCONHECIDO")
    except: return "127.0.0.1"

def limpar_sessao():
    # Limpa variáveis de sessão específicas
    keys = ['contrato_gerado', 'ent_total_input', 'ent_qtd_input']
    # Limpa dinâmicas
    for k in list(st.session_state.keys()):
        if k.startswith('ent_val_') or k.startswith('ent_dt_') or k.startswith('ent_forma_'):
            del st.session_state[k]
    for k in keys:
        if k in st.session_state: del st.session_state[k]

# --- CÁLCULOS ---
def resetar_parcelas():
    tot = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    if qtd > 0:
        v = tot/qtd
        for i in range(qtd): st.session_state[f'ent_val_{i}'] = v

def calcular_cascata():
    tot = st.session_state.get('ent_total_input', 0.0)
    qtd = int(st.session_state.get('ent_qtd_input', 1))
    p1 = st.session_state.get('ent_val_0', 0.0)
    if qtd > 1:
        rest = tot - p1
        v = rest/(qtd-1)
        for i in range(1, qtd): st.session_state[f'ent_val_{i}'] = v

# --- TELAS ADMIN ---
def render_login():
    st.markdown("<h1 style='text-align: center;'>NexusMed Admin</h1>", unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,1,1])
    with c2:
        with st.form("l"):
            e=st.text_input("Email"); s=st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                u=login_usuario(e,s)
                if u: st.session_state['usuario']=u; st.rerun()
                else: st.error("Erro")

def render_sidebar():
    if 'usuario' not in st.session_state or not st.session_state['usuario']: return None
    st.sidebar.title(f"Olá {st.session_state['usuario']['nome']}")
    op=["Gerar Contrato", "Gestão de Alunos"]
    if st.session_state['usuario']['perfil']=='admin': op.extend(["Gestão Cursos", "Gestão Usuários"])
    op.append("Sair")
    esc = st.sidebar.radio("Menu", op)
    if esc=="Sair": st.session_state['usuario']=None; st.rerun()
    return esc

def tela_gestao_cursos():
    t1,t2=st.tabs(["Cursos","Turmas"])
    with t1:
        with st.form("fc"):
            n=st.text_input("Nome"); d=st.number_input("Meses",1); c=st.number_input("Horas",0); v=st.number_input("R$",0.0)
            if st.form_submit_button("Salvar"): create_curso({"nome":n,"duracao_meses":d,"carga_horaria":c,"valor_bruto":v}); st.success("OK")
        st.dataframe(pd.DataFrame(get_cursos()))
    with t2:
        cs=get_cursos()
        if cs:
            ops={c['nome']:c['id'] for c in cs}; s=st.selectbox("Curso",list(ops.keys())); idc=ops[s]
            with st.form("ft"):
                cd=st.text_input("Cod"); fm=st.selectbox("Fmt",["Digital","Híbrido"]); i=st.date_input("Ini"); f=st.date_input("Fim")
                if st.form_submit_button("Criar"): create_turma({"curso_id":idc,"codigo_turma":cd,"formato":fm,"data_inicio":str(i),"data_fim":str(f)}); st.success("OK")
            st.dataframe(pd.DataFrame(get_turmas_by_curso(idc)))

def tela_gestao_alunos():
    cpf=st.text_input("CPF"); 
    if st.button("Buscar"): 
        f=get_aluno_by_cpf(cpf); st.session_state['ca']=f if f else {}
    if 'ca' in st.session_state:
        d=st.session_state['ca']
        with st.form("fa"):
            c1,c2=st.columns(2)
            nm=c1.text_input("Nome",d.get('nome_completo','')); cp=c2.text_input("CPF",d.get('cpf',cpf))
            em=c1.text_input("Email",d.get('email','')); tl=c2.text_input("Tel",d.get('telefone',''))
            rg=c1.text_input("RG",d.get('rg','')); cr=c2.text_input("CRM",d.get('crm',''))
            lg=st.text_input("Endereço",d.get('logradouro','')); nu=st.text_input("Nº",d.get('numero',''))
            ci=st.text_input("Cidade",d.get('cidade','')); uf=st.text_input("UF",d.get('uf','')); ce=st.text_input("CEP",d.get('cep',''))
            na=st.text_input("Nacionalidade",d.get('nacionalidade','Brasileira')); ec=st.selectbox("Est. Civil", ["Solteiro(a)","Casado(a)"], index=0)
            ar=st.text_input("Área", d.get('area_formacao','Médica'))
            if st.form_submit_button("Salvar"):
                upsert_aluno({"nome_completo":nm,"cpf":cp,"email":em,"telefone":tl,"rg":rg,"crm":cr,"logradouro":lg,"numero":nu,"cidade":ci,"uf":uf,"cep":ce,"nacionalidade":na,"estado_civil":ec,"area_formacao":ar})
                st.success("OK"); st.rerun()

# --- TELA DE CONTRATO (PRINCIPAL) ---
def tela_novo_contrato():
    st.header("📝 Emissão de Contrato")
    c1,c2=st.columns(2)
    cpf=c1.text_input("CPF Aluno"); al=get_aluno_by_cpf(cpf) if cpf else None
    if al: st.success(al['nome_completo'])
    cs=get_cursos(); nc=c2.selectbox("Curso",[c['nome'] for c in cs] if cs else [])
    c_sel=next((c for c in cs if c['nome']==nc),None); t_sel=None
    if c_sel:
        ts=get_turmas_by_curso(c_sel['id']); cd=st.selectbox("Turma",[t['codigo_turma'] for t in ts])
        t_sel=next(t for t in ts if t['codigo_turma']==cd)
    if not (al and c_sel and t_sel): st.stop()

    st.divider(); vb=float(c_sel['valor_bruto'])
    k1,k2,k3=st.columns(3); k1.metric("Valor",f"R$ {vb:,.2f}"); pc=k2.number_input("% Desc",0.0,100.0,0.0,0.5)
    vd=vb*(pc/100); vf=vb-vd; k3.metric("Final",f"R$ {vf:,.2f}")

    st.write("### Entrada")
    ce1,ce2=st.columns(2); et=ce1.number_input("Total",0.0,vf,0.0,step=100.0,key="ent_total_input",on_change=resetar_parcelas)
    eq=ce2.number_input("Qtd",1,12,1,key="ent_qtd_input",on_change=resetar_parcelas)
    
    det=[]; frm_res="Boleto"; vp=et/eq if eq>0 else 0
    if eq>0:
        for i in range(eq):
            k=f"ent_val_{i}"; 
            if k not in st.session_state: st.session_state[k]=vp
            c1,c2,c3=st.columns([1,1,2])
            v=c1.number_input(f"V{i+1}",step=10.0,key=k,on_change=calcular_cascata if i==0 else None)
            d=c2.date_input(f"D{i+1}",date.today()+relativedelta(months=i),key=f"dt_{i}")
            f=c3.selectbox(f"F{i+1}",["PIX","Boleto","Cartão"],key=f"fm_{i}")
            det.append({"numero":i+1,"valor":v,"data":d,"forma":f}); 
            if i==0: frm_res=f

    st.write("### Saldo"); sr=vf-et; st.info(f"Saldo: R$ {sr:,.2f}")
    cs1,cs2,cs3=st.columns(3); sq=cs1.number_input("Qtd",1,60,12); si=cs2.date_input("1º Venc",date.today()+relativedelta(months=1))
    sf=cs3.selectbox("Forma",["Boleto","Cartão"])
    cc1,cc2=st.columns(2); bol=cc1.checkbox("Bolsista"); pac=cc2.checkbox("Paciente")

    # BOTÃO GERAR
    if st.button("💾 Gerar Contrato", type="primary", use_container_width=True):
        with st.spinner("Gerando..."):
            tk=str(uuid.uuid4())
            dd={
                "aluno_id":al['id'],"turma_id":t_sel['id'],"valor_curso":vb,"percentual_desconto":pc,"valor_desconto":vd,"valor_final":vf,
                "valor_material":0.0,"entrada_valor":et,"entrada_qtd_parcelas":eq,"entrada_forma_pagamento":frm_res,
                "saldo_valor":sr,"saldo_qtd_parcelas":sq,"saldo_forma_pagamento":sf,"bolsista":bol,"atendimento_paciente":pac,
                "formato_curso":t_sel['formato'],"token_acesso":tk,"status":"pendente"
            }
            inf={"detalhes_entrada":det,"inicio_saldo":str(si)}
            paths=gerar_contrato_pdf(al,t_sel,c_sel,dd,inf)
            if paths:
                local,cloud=paths; dd['caminho_arquivo']=cloud; create_contrato(dd)
                st.session_state['contrato_gerado']={"token":tk,"email":al['email'],"local_path":local,"nome":al['nome_completo']}
                st.balloons(); st.rerun()
            else: st.error("Erro ao gerar PDF.")

    # PÓS-GERAÇÃO
    if st.session_state.get('contrato_gerado'):
        inf=st.session_state['contrato_gerado']; lk=f"https://nexusmed-contratos.streamlit.app/?token={inf['token']}"
        st.success("✅ Contrato Gerado!"); st.text_input("Link",lk)
        try:
            with open(inf['local_path'],"rb") as f: st.download_button("📥 Baixar Contrato",f,"Contrato.pdf")
        except: st.warning("Arquivo expirou.")
        
        if st.button("📧 Enviar Email"): enviar_email(inf['email'],inf['nome'],lk); st.toast("Enviado")
        
        # BOTÃO NOVO (Com callback para limpar)
        st.button("🔄 Novo Contrato", on_click=limpar_sessao)

# --- PÁGINA DE ACEITE (CSS AGRESSIVO + VALIDAÇÃO) ---
def tela_aceite_aluno(token):
    # CSS BLINDADO: Esconde Menu, Footer e o botão MANAGE APP
    st.markdown("""
        <style>
            /* Esconde o Menu Superior (Hamburger) */
            #MainMenu {visibility: hidden;}
            
            /* Esconde o Rodapé padrão */
            footer {visibility: hidden;}
            
            /* Esconde o Cabeçalho superior */
            header {visibility: hidden;}
            [data-testid="stHeader"] {visibility: hidden;}
            
            /* CRÍTICO: Esconde o botão 'Manage App' e 'Deploy' */
            .stDeployButton {display: none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            [data-testid="stDecoration"] {display: none;}
            
            /* Sobe o conteúdo para o topo da página */
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 1rem !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    d = get_contrato_by_token(token)
    if not d: st.error("Link inválido ou expirado."); return

    # Título centralizado
    st.markdown("<h2 style='text-align: center;'>Assinatura Digital</h2>", unsafe_allow_html=True)
    st.markdown("---")

    # 1. STATUS: Se já assinado
    if d['status'] == 'assinado':
        st.success(f"✅ Contrato assinado em {d.get('data_aceite')}.")
        try:
            from src.db import supabase
            data_pdf = supabase.storage.from_("contratos").download(d['caminho_arquivo'])
            st.download_button("📥 Baixar Contrato Assinado", data_pdf, "Contrato_Assinado.pdf", "application/pdf", use_container_width=True)
        except: pass
        return

    # 2. ÁREA DE LEITURA (VISUALIZAÇÃO)
    st.info(f"Olá, **{d['alunos']['nome_completo']}**. Por favor, leia o contrato abaixo antes de assinar.")
    
    try:
        from src.db import supabase
        data_pdf = supabase.storage.from_("contratos").download(d['caminho_arquivo'])
        # Botão largo para download/visualização
        st.download_button("📄 CLIQUE AQUI PARA BAIXAR E LER O PDF", data_pdf, "Minuta_Contrato.pdf", "application/pdf", use_container_width=True)
    except: st.warning("Erro ao carregar pré-visualização.")

    st.markdown("---")
    
    # 3. FORMULÁRIO DE ASSINATURA
    st.subheader("Confirmação de Identidade")
    
    with st.form("aceite"):
        st.write("Para assinar, confirme seus dados exatos:")
        c1, c2 = st.columns(2)
        nome_input = c1.text_input("Nome Completo")
        cpf_input = c2.text_input("CPF (apenas números)")
        
        st.markdown("<br>", unsafe_allow_html=True)
        check_termos = st.checkbox("Declaro que li o contrato acima, concordo com todas as cláusulas e assino digitalmente este documento.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        btn_assinar = st.form_submit_button("✍️ ASSINAR CONTRATO AGORA", use_container_width=True, type="primary")
        
        if btn_assinar:
            # VALIDAÇÃO RIGOROSA
            cpf_limpo = ''.join(filter(str.isdigit, cpf_input))
            cpf_real = d['alunos']['cpf']
            nome_real = d['alunos']['nome_completo']
            
            # Validação flexível de nome (remove espaços extras e ignora maiúsculas)
            nome_valido = nome_input.strip().lower() == nome_real.strip().lower()
            
            if cpf_limpo != cpf_real:
                st.error("❌ CPF incorreto. Verifique seus dados.")
            elif not nome_valido:
                st.error(f"❌ Nome incorreto. Por favor, digite exatamente: {nome_real}")
            elif not check_termos:
                st.warning("⚠️ Você precisa marcar a caixa de 'Declaro que li e concordo' para prosseguir.")
            else:
                with st.spinner("Registrando assinatura e carimbando documento..."):
                    # Coleta Dados Forenses
                    fuso = pytz.timezone('America/Sao_Paulo')
                    agora = datetime.now(fuso)
                    ip = get_ip()
                    
                    # Gera Hash Único (ID + Hora + CPF + IP)
                    raw = f"{d['id']}{agora}{cpf_real}{ip}"
                    hash_ass = hashlib.sha256(raw.encode()).hexdigest().upper()
                    
                    lk_origem = f"https://nexusmed-contratos.streamlit.app/?token={token}"
                    
                    meta = {
                        "token": d['id'].split('-')[0],
                        "data_hora": agora.strftime('%d/%m/%Y às %H:%M:%S (GMT-3)'),
                        "nome": nome_real, "cpf": cpf_real, "email": d['alunos']['email'],
                        "ip": ip, "link": lk_origem, "hash": hash_ass
                    }
                    
                    # Backend: Carimba o PDF na nuvem
                    path_assinado = aplicar_carimbo_digital(d['caminho_arquivo'], meta)
                    
                    # Backend: Atualiza Banco de Dados
                    registrar_aceite(d['id'], {
                        "status": "assinado", 
                        "data_aceite": agora.isoformat(),
                        "ip_aceite": ip, 
                        "hash_aceite": hash_ass,
                        "recibo_aceite_texto": str(meta), 
                        "caminho_arquivo": path_assinado
                    })
                    
                    st.balloons()
                    st.success("✅ Assinatura realizada com sucesso! A página irá recarregar.")
                    time.sleep(3)
                    st.rerun()
