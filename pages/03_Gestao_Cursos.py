import streamlit as st
import pandas as pd
from src.repository import get_cursos, create_curso, get_turmas_by_curso, create_turma

# --- SEGURANÇA ---
if 'usuario' not in st.session_state or not st.session_state['usuario']:
    st.switch_page("app.py")

# Apenas admin pode ver isso? Se sim:
if st.session_state['usuario']['perfil'] != 'admin':
    st.error("Acesso negado.")
    st.stop()

st.title("📚 Gestão de Cursos e Turmas")

tab1, tab2 = st.tabs(["Cursos (Produtos)", "Turmas (Calendário)"])

with tab1:
    with st.form("novo_curso"):
        st.subheader("Cadastrar Novo Curso")
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome do Curso")
        valor = c2.number_input("Valor Bruto (R$)", 0.0, step=100.0)
        c3, c4 = st.columns(2)
        duracao = c3.number_input("Duração (Meses)", 1)
        carga = c4.number_input("Carga Horária", 0)
        
        if st.form_submit_button("Salvar Curso"):
            create_curso({"nome": nome, "valor_bruto": valor, "duracao_meses": duracao, "carga_horaria": carga})
            st.success("Curso salvo!")
            st.rerun()
            
    st.divider()
    st.dataframe(pd.DataFrame(get_cursos()), use_container_width=True)

with tab2:
    cursos = get_cursos()
    if cursos:
        nome_curso = st.selectbox("Selecione o Curso", [c['nome'] for c in cursos])
        curso_id = next(c['id'] for c in cursos if c['nome'] == nome_curso)
        
        with st.form("nova_turma"):
            st.subheader(f"Nova Turma para {nome_curso}")
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código da Turma (Ex: DERM2026)")
            formato = c2.selectbox("Formato", ["Digital", "Híbrido", "Presencial"])
            d1, d2 = st.columns(2)
            ini = d1.date_input("Data Início")
            fim = d2.date_input("Data Fim")
            
            if st.form_submit_button("Criar Turma"):
                create_turma({
                    "curso_id": curso_id, "codigo_turma": codigo, 
                    "formato": formato, "data_inicio": str(ini), "data_fim": str(fim)
                })
                st.success("Turma criada!")
                st.rerun()
        
        st.write("Turmas Existentes:")
        st.dataframe(pd.DataFrame(get_turmas_by_curso(curso_id)), use_container_width=True)
    else:
        st.warning("Cadastre um curso primeiro.")
