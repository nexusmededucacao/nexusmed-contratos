import streamlit as st
import time
import hashlib
import pytz
from datetime import datetime
from src.repository import get_contrato_by_token, registrar_aceite
from src.services import aplicar_carimbo_digital

# --- CONFIGURAÇÃO VISUAL (ESCONDER MENU) ---
st.set_page_config(page_title="Assinatura Digital", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;} /* Esconde Barra Lateral */
    #MainMenu {visibility: hidden;} /* Esconde Menu 3 pontos */
    footer {visibility: hidden;} /* Esconde Rodapé */
    .stApp {margin-top: -60px;} /* Sobe o conteúdo */
</style>
""", unsafe_allow_html=True)

# --- LÓGICA ---
def get_ip():
    try: return st.context.headers.get("X-Forwarded-For", "IP_DESCONHECIDO")
    except: return "127.0.0.1"

# Pega o token da URL
token = st.query_params.get("token")

if not token:
    st.error("Link inválido. Token não encontrado.")
    st.stop()

d = get_contrato_by_token(token)

if not d:
    st.error("Contrato não encontrado ou link expirado.")
    st.stop()

# --- INTERFACE ---
st.markdown("<h2 style='text-align: center;'>Assinatura Digital de Contrato</h2>", unsafe_allow_html=True)
st.markdown("---")

if d['status'] == 'assinado':
    st.success(f"✅ Este contrato já foi assinado em {d.get('data_aceite')}.")
    try:
        from src.db import supabase
        data_pdf = supabase.storage.from_("contratos").download(d['caminho_arquivo'])
        st.download_button("📥 Baixar Contrato Assinado", data_pdf, "Contrato_Assinado.pdf", "application/pdf", use_container_width=True)
    except: pass
    st.stop()

# Área de Visualização
c1, c2 = st.columns([2, 1])
with c1:
    st.info("Por favor, leia o documento abaixo.")
    try:
        from src.db import supabase
        data_pdf = supabase.storage.from_("contratos").download(d['caminho_arquivo'])
        st.download_button("📄 CLIQUE PARA BAIXAR/LER O CONTRATO", data_pdf, "Minuta.pdf", "application/pdf", use_container_width=True)
    except: st.warning("Erro ao carregar documento.")

with c2:
    st.markdown("### Seus Dados")
    st.write(f"**Aluno:** {d['alunos']['nome_completo']}")
    st.write(f"**CPF:** {d['alunos']['cpf']}")
    st.write(f"**Curso:** {d['turmas']['codigo_turma']}")
    
    st.markdown("---")
    with st.form("aceite"):
        nome_input = st.text_input("Confirme seu Nome")
        cpf_input = st.text_input("Confirme seu CPF")
        check = st.checkbox("Li, concordo e assino digitalmente.")
        
        if st.form_submit_button("✍️ ASSINAR AGORA", type="primary", use_container_width=True):
            # Validação
            cpf_limpo = ''.join(filter(str.isdigit, cpf_input))
            cpf_real = d['alunos']['cpf']
            nome_real = d['alunos']['nome_completo']
            
            if cpf_limpo != cpf_real:
                st.error("CPF incorreto.")
            elif nome_input.lower().strip() != nome_real.lower().strip():
                st.error("Nome incorreto.")
            elif not check:
                st.error("Marque a caixa de aceite.")
            else:
                with st.spinner("Processando assinatura..."):
                    # Carimbo e Registro
                    fuso = pytz.timezone('America/Sao_Paulo')
                    agora = datetime.now(fuso)
                    ip = get_ip()
                    raw = f"{d['id']}{agora}{cpf_real}{ip}"
                    hash_ass = hashlib.sha256(raw.encode()).hexdigest().upper()
                    
                    lk_origem = f"https://nexusmed-contratos.streamlit.app/?token={token}"
                    meta = {
                        "token": d['id'].split('-')[0], "data_hora": agora.strftime('%d/%m/%Y %H:%M'),
                        "nome": nome_real, "cpf": cpf_real, "ip": ip, "hash": hash_ass
                    }
                    
                    path_assinado = aplicar_carimbo_digital(d['caminho_arquivo'], meta)
                    
                    registrar_aceite(d['id'], {
                        "status": "assinado", "data_aceite": agora.isoformat(),
                        "ip_aceite": ip, "hash_aceite": hash_ass,
                        "recibo_aceite_texto": str(meta), "caminho_arquivo": path_assinado
                    })
                    st.success("Sucesso! Recarregando...")
                    time.sleep(2)
                    st.rerun()
