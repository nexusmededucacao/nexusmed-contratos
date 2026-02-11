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
                        # Ordena para mostrar ativas primeiro
                        turmas_ordenadas = sorted(curso['turmas'], key=lambda x: x.get('ativo', True), reverse=True)
                        
                        for t in turmas_ordenadas:
                            # Tratamento para turmas antigas que podem vir sem o campo 'ativo' preenchido
                            is_active = t.get('ativo', True)
                            icon_turma = "🟢" if is_active else "🔴"
                            style_turma = "**" if is_active else "~~" # Riscado se inativo
                            
                            c_t1, c_t2, c_t3 = st.columns([2, 2, 1])
                            
                            # Exibição Visual do Status
                            c_t1.markdown(f"{icon_turma} {style_turma}{t['codigo_turma']}{style_turma} ({t['formato']})")
                            c_t2.caption(f"De {t['data_inicio']} até {t['data_fim']}")
                            
                            # Botão de Ação (Popover)
                            with c_t3.popover("Gerenciar"):
                                with st.form(key=f"gerenciar_turma_{t['id']}"):
                                    st.write(f"Gerenciar Turma: {t['codigo_turma']}")
                                    
                                    # Inputs de Edição
                                    nova_data_fim = st.date_input("Data Fim", value=datetime.fromisoformat(t['data_fim']) if t['data_fim'] else None)
                                    novo_status = st.checkbox("Turma Ativa?", value=is_active)
                                    
                                    if st.form_submit_button("Salvar Alterações"):
                                        # Atualiza dados e status
                                        CursoRepository.atualizar_turma(t['id'], {
                                            "data_fim": nova_data_fim.isoformat() if nova_data_fim else None,
                                            "ativo": novo_status
                                        })
                                        
                                        # Mensagem baseada na ação
                                        if not novo_status and is_active:
                                            st.warning("Turma inativada! Ela não aparecerá mais para novos contratos.")
                                        else:
                                            st.success("Turma atualizada com sucesso!")
                                            
                                        st.rerun()
                    else:
                        st.caption("Nenhuma turma cadastrada.")

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
