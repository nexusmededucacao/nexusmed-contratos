import streamlit as st
from src.database.repo_cursos import CursoRepository
from src.utils.formatters import format_currency

# Verificação de Segurança (Proteção da página)
if not st.session_state.get("authenticated"):
    st.error("Acesso negado. Por favor, faça login no menu principal.")
    st.stop()

def main():
    st.title("📚 Gestão de Cursos e Turmas")
    st.write("Gerencie o catálogo de cursos e as turmas disponíveis para matrícula.")

    tab_lista, tab_novo_curso, tab_nova_turma = st.tabs([
        "Cursos & Turmas Ativas", "Cadastrar Curso", "Abrir Nova Turma"
    ])

    # --- ABA: LISTAGEM ---
    with tab_lista:
        cursos = CursoRepository.listar_todos_com_turmas()
        if not cursos:
            st.info("Nenhum curso cadastrado no sistema.")
        else:
            for curso in cursos:
                with st.expander(f"📖 {curso['nome']} - {format_currency(curso['valor_bruto'])}"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**Duração:** {curso['duracao_meses']} meses")
                    col1.write(f"**Carga Horária:** {curso['carga_horaria']}h")
                    
                    st.write("---")
                    st.subheader("📅 Turmas deste Curso")
                    if curso['turmas']:
                        for t in curso['turmas']:
                            st.write(f"🔹 Código: `{t['codigo_turma']}` | Início: {t['data_inicio']} | Formato: {t['formato']}")
                    else:
                        st.write("Nenhuma turma aberta para este curso.")

    # --- ABA: NOVO CURSO ---
    with tab_novo_curso:
        with st.form("form_curso"):
            nome = st.text_input("Nome do Curso")
            col1, col2, col3 = st.columns(3)
            duracao = col1.number_input("Duração (Meses)", min_value=1)
            carga = col2.number_input("Carga Horária", min_value=1)
            valor = col3.number_input("Valor Bruto (R$)", min_value=0.0, step=100.0)
            
            if st.form_submit_button("Salvar Curso"):
                if nome:
                    dados = {
                        "nome": nome,
                        "duracao_meses": duracao,
                        "carga_horaria": carga,
                        "valor_bruto": valor,
                        "ativo": True
                    }
                    CursoRepository.criar_curso(dados)
                    st.success("Curso criado!")
                    st.rerun()

    # --- ABA: NOVA TURMA ---
    with tab_nova_turma:
        cursos_ativos = CursoRepository.listar_cursos_ativos()
        if not cursos_ativos:
            st.warning("Crie um curso antes de abrir uma turma.")
        else:
            with st.form("form_turma"):
                # Mapeia nome para ID para o selectbox
                lista_nomes = {c['nome']: c['id'] for c in cursos_ativos}
                curso_nome = st.selectbox("Selecione o Curso", options=list(lista_nomes.keys()))
                
                col1, col2 = st.columns(2)
                cod_turma = col1.text_input("Código da Turma (Ex: MED-2024-01)")
                formato = col1.selectbox("Formato", ["Presencial", "Digital", "Híbrido"])
                
                data_in = col1.date_input("Data de Início")
                data_fim = col1.date_input("Data de Término")
                
                if st.form_submit_button("Abrir Turma"):
                    if cod_turma:
                        dados_turma = {
                            "curso_id": lista_nomes[curso_nome],
                            "codigo_turma": cod_turma,
                            "formato": formato,
                            "data_inicio": data_in.isoformat(),
                            "data_fim": data_fim.isoformat()
                        }
                        CursoRepository.criar_turma(dados_turma)
                        st.success("Turma aberta com sucesso!")
                        st.rerun()

if __name__ == "__main__":
    main()
