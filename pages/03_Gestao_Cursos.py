import streamlit as st
import time  # <--- IMPORTANTE PARA O DELAY VISUAL
from datetime import datetime
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
                # Ícone visual do status do curso
                status_icon = "🟢" if curso.get('ativo', True) else "🔴"
                
                with st.expander(f"{status_icon} {curso['nome']} - {format_currency(curso['valor_bruto'])}"):
                    col1, col2, col3 = st.columns(3)
                    col1.write(f"**Duração:** {curso['duracao_meses']} meses")
                    col2.write(f"**Carga Horária:** {curso['carga_horaria']}h")
                    
                    # --- ÁREA DE EDIÇÃO DO CURSO ---
                    with col3.popover("⚙️ Editar Curso"):
                        st.write(f"Editando: **{curso['nome']}**")
                        with st.form(key=f"edit_curso_{curso['id']}"):
                            # Preenche com dados atuais
                            e_nome = st.text_input("Nome", value=curso['nome'])
                            e_valor = st.number_input("Valor", value=float(curso['valor_bruto']))
                            e_duracao = st.number_input("Meses", value=int(curso['duracao_meses']))
                            e_ativo = st.checkbox("Curso Ativo?", value=curso.get('ativo', True))
                            
                            if st.form_submit_button("Salvar Curso"):
                                CursoRepository.atualizar_curso(curso['id'], {
                                    "nome": e_nome,
                                    "valor_bruto": e_valor,
                                    "duracao_meses": e_duracao,
                                    "ativo": e_ativo
                                })
                                st.success("Curso atualizado com sucesso!")
                                time.sleep(1) # Pausa para ler a mensagem
                                st.rerun()

                    st.divider()
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
                            
                            # --- ÁREA DE EDIÇÃO DA TURMA ---
                            with c_t3.popover("Gerenciar Turma"):
                                with st.form(key=f"gerenciar_turma_{t['id']}"):
                                    st.write(f"Turma: {t['codigo_turma']}")
                                    
                                    # Inputs de Edição
                                    # Converte string ISO para objeto date, se existir
                                    data_fim_obj = datetime.fromisoformat(t['data_fim']).date() if t['data_fim'] else None
                                    
                                    nova_data_fim = st.date_input("Data Fim", value=data_fim_obj)
                                    novo_status = st.checkbox("Turma Ativa?", value=is_active)
                                    
                                    if st.form_submit_button("Salvar Alterações"):
                                        # Atualiza dados e status
                                        CursoRepository.atualizar_turma(t['id'], {
                                            "data_fim": nova_data_fim.isoformat() if nova_data_fim else None,
                                            "ativo": novo_status
                                        })
                                        
                                        # Mensagem baseada na ação
                                        if not novo_status and is_active:
                                            st.warning("Turma inativada! Ela não aparecerá para novos contratos.")
                                        else:
                                            st.success("Turma atualizada com sucesso!")
                                        
                                        time.sleep(1.5) # Pausa maior para ler o aviso
                                        st.rerun()
                    else:
                        st.caption("Nenhuma turma cadastrada.")

    # --- ABA: NOVO CURSO ---
    with tab_novo_curso:
        with st.form("form_curso", clear_on_submit=True):
            st.subheader("Cadastrar Novo Curso")
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
                    st.success("Curso criado com sucesso!")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.warning("O nome do curso é obrigatório.")

    # --- ABA: NOVA TURMA ---
    with tab_nova_turma:
        cursos_ativos = CursoRepository.listar_cursos_ativos()
        if not cursos_ativos:
            st.warning("Crie um curso antes de abrir uma turma.")
        else:
            with st.form("form_turma", clear_on_submit=True):
                st.subheader("Abrir Nova Turma")
                # Mapeia nome para ID para o selectbox
                lista_nomes = {c['nome']: c['id'] for c in cursos_ativos}
                curso_nome = st.selectbox("Selecione o Curso", options=list(lista_nomes.keys()))
                
                # Layout melhorado: Formato na Coluna 2
                col1, col2 = st.columns(2)
                cod_turma = col1.text_input("Código da Turma (Ex: MED-2024-01)")
                formato = col2.selectbox("Formato", ["Presencial", "Digital", "Híbrido"])
                
                data_in = col1.date_input("Data de Início")
                data_fim = col2.date_input("Data de Término")
                
                if st.form_submit_button("Abrir Turma"):
                    if cod_turma:
                        dados_turma = {
                            "curso_id": lista_nomes[curso_nome],
                            "codigo_turma": cod_turma,
                            "formato": formato,
                            "data_inicio": data_in.isoformat(),
                            "data_fim": data_fim.isoformat(),
                            "ativo": True # Garante que nasce ativa
                        }
                        CursoRepository.criar_turma(dados_turma)
                        st.success("Turma aberta com sucesso!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.warning("Código da turma é obrigatório.")

if __name__ == "__main__":
    main()
