import streamlit as st
from datetime import datetime
from src.repository import get_aluno_by_cpf, upsert_aluno

if 'usuario' not in st.session_state or not st.session_state['usuario']:
    st.switch_page("app.py")

st.title("📇 Cadastro de Alunos")

cpf_busca = st.text_input("Buscar por CPF", max_chars=14)
if st.button("Buscar"):
    aluno = get_aluno_by_cpf(cpf_busca)
    if aluno:
        st.session_state['edit_aluno'] = aluno
        st.success("Aluno encontrado!")
    else:
        st.session_state['edit_aluno'] = {}
        st.info("CPF não encontrado. Preencha para cadastrar novo.")

if 'edit_aluno' in st.session_state:
    d = st.session_state['edit_aluno']
    
    with st.form("form_aluno"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome Completo", d.get('nome_completo', ''))
        cpf = c2.text_input("CPF", d.get('cpf', cpf_busca))
        
        c3, c4 = st.columns(2)
        email = c3.text_input("E-mail", d.get('email', ''))
        tel = c4.text_input("Telefone", d.get('telefone', ''))
        
        c5, c6 = st.columns(2)
        rg = c5.text_input("RG", d.get('rg', ''))
        crm = c6.text_input("CRM", d.get('crm', ''))
        
        st.subheader("Endereço")
        e1, e2 = st.columns([3, 1])
        log = e1.text_input("Logradouro", d.get('logradouro', ''))
        num = e2.text_input("Número", d.get('numero', ''))
        
        e3, e4, e5 = st.columns(3)
        bairro = e3.text_input("Bairro", d.get('bairro', ''))
        cidade = e4.text_input("Cidade", d.get('cidade', ''))
        uf = e5.text_input("UF", d.get('uf', ''))
        cep = st.text_input("CEP", d.get('cep', ''))
        
        st.subheader("Outros")
        o1, o2, o3 = st.columns(3)
        nasc_val = datetime.strptime(d['data_nascimento'], '%Y-%m-%d') if d.get('data_nascimento') else None
        nasc = o1.date_input("Nascimento", nasc_val)
        nac = o2.text_input("Nacionalidade", d.get('nacionalidade', 'Brasileira'))
        civil = o3.selectbox("Estado Civil", ["Solteiro(a)", "Casado(a)", "Divorciado(a)"], index=0)
        area = st.text_input("Área de Formação", d.get('area_formacao', 'Médica'))

        if st.form_submit_button("💾 Salvar Aluno"):
            dados_novos = {
                "nome_completo": nome, "cpf": cpf, "email": email, "telefone": tel,
                "rg": rg, "crm": crm, "logradouro": log, "numero": num,
                "bairro": bairro, "cidade": cidade, "uf": uf, "cep": cep,
                "data_nascimento": str(nasc), "nacionalidade": nac,
                "estado_civil": civil, "area_formacao": area
            }
            upsert_aluno(dados_novos)
            st.success("Dados salvos com sucesso!")
            del st.session_state['edit_aluno']
            st.rerun()
