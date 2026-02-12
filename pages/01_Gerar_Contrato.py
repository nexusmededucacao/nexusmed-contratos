import streamlit as st
import uuid
from datetime import datetime
from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.database.repo_contratos import ContratoRepository
from src.utils.formatters import format_currency, format_cpf

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("📄 Gerador de Contratos")
    st.write("Siga os passos abaixo para criar um novo contrato e enviá-lo para assinatura.")

    # Inicialização do Passo no Session State
    if "step" not in st.session_state:
        st.session_state.step = 1
    if "form_data" not in st.session_state:
        st.session_state.form_data = {}

    # --- PASSO 1: SELEÇÃO DE ALUNO (CORRIGIDO) ---
    if st.session_state.step == 1:
        st.subheader("Etapa 1: Selecionar Aluno")
        busca = st.text_input("Buscar Aluno por Nome ou CPF", placeholder="Digite Nome ou CPF...")
        
        if busca:
            # --- LÓGICA DE BUSCA HÍBRIDA ---
            # Se o usuário digitou números, tentamos buscar pelo CPF primeiro
            if any(char.isdigit() for char in busca):
                alunos = AlunoRepository.buscar_por_cpf(busca)
                # Se não achou por CPF, tenta por nome (caso seja um nome com números)
                if not alunos:
                    alunos = AlunoRepository.filtrar_por_nome(busca)
            else:
                # Se não tem números, busca apenas por nome
                alunos = AlunoRepository.filtrar_por_nome(busca)
            # -------------------------------

            if alunos:
                st.info(f"Encontrados: {len(alunos)} alunos.")
                for a in alunos:
                    # Proteção para garantir que 'a' é um dicionário válido
                    if not isinstance(a, dict): continue

                    col1, col2 = st.columns([3, 1])
                    
                    # Formatação segura para exibição
                    nome = a.get('nome_completo', 'Sem Nome')
                    cpf_fmt = format_cpf(a.get('cpf', ''))
                    
                    col1.write(f"**{nome}** - CPF: {cpf_fmt}")
                    
                    if col2.button("Selecionar", key=f"sel_aluno_{a.get('id')}"):
                        st.session_state.form_data['aluno'] = a
                        st.session_state.step = 2
                        st.rerun()
            else:
                st.warning("Nenhum aluno encontrado.")
                
        st.markdown("---")
        st.info("Dica: Cadastre o aluno na página de Gestão de Alunos caso não o encontre.")

    # --- PASSO 2: SELEÇÃO DE CURSO E TURMA ---
    elif st.session_state.step == 2:
        st.subheader("Etapa 2: Curso e Turma")
        st.write(f"Aluno selecionado: **{st.session_state.form_data['aluno']['nome_completo']}**")
        
        cursos = CursoRepository.listar_todos_com_turmas()
        
        if not cursos:
            st.error("Nenhum curso cadastrado.")
            if st.button("Voltar"):
                st.session_state.step = 1
                st.rerun()
            st.stop()

        lista_cursos = {c['nome']: c for c in cursos}
        
        curso_sel_nome = st.selectbox("Escolha o Curso", options=[""] + list(lista_cursos.keys()))
        
        if curso_sel_nome:
            curso_data = lista_cursos[curso_sel_nome]
            turmas = curso_data.get('turmas', [])
            
            if turmas:
                lista_turmas = {f"{t['codigo_turma']} ({t.get('formato', 'Presencial')})": t for t in turmas}
                turma_sel_label = st.selectbox("Escolha a Turma", options=list(lista_turmas.keys()))
                
                if st.button("Confirmar Curso e Turma"):
                    st.session_state.form_data['curso'] = curso_data
                    st.session_state.form_data['turma'] = lista_turmas[turma_sel_label]
                    st.session_state.step = 3
                    st.rerun()
            else:
                st.error("Este curso não possui turmas abertas.")
        
        if st.button("Voltar"):
            st.session_state.step = 1
            st.rerun()

    # --- PASSO 3: CONDIÇÕES FINANCEIRAS ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        
        # Recupera valor bruto (garante float)
        val_base = float(st.session_state.form_data['curso'].get('valor_bruto', 0))
        
        col1, col2 = st.columns(2)
        desc_perc = col1.number_input("Desconto (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
        valor_material = col2.number_input("Valor Material (R$)", min_value=0.0, value=0.0, step=10.0)
        
        valor_final = val_base * (1 - (desc_perc/100))
        st.info(f"Valor Original: {format_currency(val_base)} | **Valor Final: {format_currency(valor_final)}**")

        st.write("---")
        col_ent, col_sal = st.columns(2)
        
        with col_ent:
            st.markdown("##### Entrada")
            v_entrada = st.number_input("Valor Entrada (R$)", min_value=0.0, value=0.0, step=50.0)
            f_entrada = st.selectbox("Forma (Entrada)", ["PIX", "Cartão", "Boleto", "Dinheiro"])
            
        with col_sal:
            st.markdown("##### Saldo Restante")
            v_saldo = valor_final - v_entrada
            st.write(f"A Parcelar: **{format_currency(v_saldo)}**")
            
            if v_saldo > 0:
                q_saldo = st.number_input("Qtd Parcelas", min_value=1, max_value=24, value=1)
                f_saldo = st.selectbox("Forma (Saldo)", ["Boleto", "Cartão de Crédito", "Recorrente"])
            else:
                q_saldo = 0
                f_saldo = "-"

        st.write("---")
        c_btn1, c_btn2 = st.columns([1, 5])
        if c_btn1.button("Voltar"):
            st.session_state.step = 2
            st.rerun()

        if c_btn2.button("🚀 Gerar Contrato", type="primary"):
            # Preparar dados para o banco
            novo_contrato = {
                "aluno_id": st.session_state.form_data['aluno']['id'],
                "turma_id": st.session_state.form_data['turma']['id'],
                "valor_curso": val_base,
                "percentual_desconto": desc_perc,
                "valor_final": valor_final,
                "valor_material": valor_material,
                "entrada_valor": v_entrada,
                "entrada_forma_pagamento": f_entrada,
                "saldo_valor": v_saldo,
                "saldo_qtd_parcelas": q_saldo,
                "saldo_forma_pagamento": f_saldo,
                "token_acesso": str(uuid.uuid4()),
                "status": "Pendente",
                "caminho_arquivo": "", # Será preenchido na geração do PDF se houver
                "created_at": datetime.now().isoformat()
            }
            
            # Salva no Banco
            res = ContratoRepository.criar_contrato(novo_contrato)
            
            # Salva o token na sessão para mostrar o link na próxima tela
            st.session_state.ultimo_token = novo_contrato["token_acesso"]
            
            st.success("Contrato registrado no banco de dados!")
            st.session_state.step = 4
            st.rerun()

    # --- PASSO 4: FINALIZAÇÃO ---
    elif st.session_state.step == 4:
        st.balloons()
        st.success("Contrato pronto para assinatura!")
        st.write("Envie este link para o aluno assinar:")
        
        token = st.session_state.get('ultimo_token', 'ERRO_TOKEN')
        # URL Genérica - Ajuste conforme seu domínio real
        link = f"https://nexusmed-portal.streamlit.app/Assinatura?token={token}"
        
        st.code(link, language="text")
        st.info("O aluno poderá acessar este link, revisar os valores e assinar digitalmente.")
        
        if st.button("Criar Novo Contrato"):
            st.session_state.step = 1
            st.session_state.form_data = {}
            st.rerun()

if __name__ == "__main__":
    main()
