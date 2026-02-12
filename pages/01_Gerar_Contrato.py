import streamlit as st
import time
from datetime import date, datetime
from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.services.contract_generator import ContractGenerator
from src.utils.formatters import format_currency, format_cpf

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("📄 Gerador de Contratos")
    st.write("Siga os passos abaixo para criar um novo contrato e enviá-lo para assinatura.")

    # Inicializa variáveis de estado se não existirem
    if "aluno_selecionado" not in st.session_state:
        st.session_state.aluno_selecionado = None
    if "curso_selecionado" not in st.session_state:
        st.session_state.curso_selecionado = None
    if "turma_selecionada" not in st.session_state:
        st.session_state.turma_selecionada = None

    # --- ETAPA 1: SELECIONAR ALUNO ---
    st.subheader("Etapa 1: Selecionar Aluno")
    
    # Campo de busca híbrido
    termo = st.text_input("Buscar Aluno por Nome ou CPF", placeholder="Digite o nome ou os números do CPF")
    
    alunos_encontrados = []
    if termo:
        # Lógica inteligente: Números = CPF, Texto = Nome
        if "".join(filter(str.isdigit, termo)): # Se tem números, tenta limpar e buscar
            # Se o usuário digitou apenas números ou cpf formatado
            alunos_encontrados = AlunoRepository.buscar_por_cpf(termo)
            # Se não achou por CPF, tenta por nome (caso seja um nome com números, raro mas possível)
            if not alunos_encontrados and not termo.isdigit():
                 alunos_encontrados = AlunoRepository.filtrar_por_nome(termo)
        else:
            alunos_encontrados = AlunoRepository.filtrar_por_nome(termo)

    # Exibição dos Resultados
    if termo and not alunos_encontrados:
        st.warning("Nenhum aluno encontrado.")
        st.info("Dica: Cadastre o aluno na página de Gestão de Alunos caso não o encontre.")
    
    elif alunos_encontrados:
        # Mostra opções para o usuário escolher
        for aluno in alunos_encontrados:
            nome = aluno.get('nome_completo', 'Sem Nome')
            cpf = format_cpf(aluno.get('cpf', ''))
            
            # Card de seleção
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"**{nome}** - {cpf}")
                
                # Botão de Seleção
                if st.session_state.aluno_selecionado and st.session_state.aluno_selecionado['id'] == aluno['id']:
                    col2.success("✅ Selecionado")
                else:
                    if col2.button("Selecionar", key=f"sel_{aluno['id']}"):
                        st.session_state.aluno_selecionado = aluno
                        st.rerun()

    # Feedback visual do selecionado
    if st.session_state.aluno_selecionado:
        st.divider()
        st.info(f"👤 Aluno Selecionado: **{st.session_state.aluno_selecionado['nome_completo']}**")
    else:
        st.stop() # Para a execução aqui até selecionar um aluno

    # --- ETAPA 2: SELECIONAR CURSO E TURMA ---
    st.subheader("Etapa 2: Dados do Curso")
    
    cursos = CursoRepository.listar_cursos_ativos()
    opcoes_cursos = {c['nome']: c for c in cursos}
    
    nome_curso = st.selectbox("Selecione o Curso", options=list(opcoes_cursos.keys()))
    
    if nome_curso:
        curso_obj = opcoes_cursos[nome_curso]
        st.session_state.curso_selecionado = curso_obj
        
        # Busca turmas deste curso (apenas ativas)
        turmas = CursoRepository.listar_turmas_por_curso(curso_obj['id'], apenas_ativas=True)
        
        if not turmas:
            st.warning("Este curso não possui turmas ativas.")
            st.stop()
            
        opcoes_turmas = {t['codigo_turma']: t for t in turmas}
        cod_turma = st.selectbox("Selecione a Turma", options=list(opcoes_turmas.keys()))
        
        if cod_turma:
            st.session_state.turma_selecionada = opcoes_turmas[cod_turma]

    # --- ETAPA 3: VALORES E PAGAMENTO ---
    st.subheader("Etapa 3: Valores e Condições")
    
    with st.form("form_contrato"):
        c1, c2 = st.columns(2)
        # Traz o valor padrão do curso, mas permite editar
        valor_final = c1.number_input("Valor do Contrato (R$)", 
                                     value=float(st.session_state.curso_selecionado['valor_bruto']), 
                                     step=100.0)
        
        forma_pagto = c2.selectbox("Forma de Pagamento", 
                                  ["À Vista (Pix/Dinheiro)", "Cartão de Crédito", "Boleto Parcelado", "Financiamento"])
        
        observacoes = st.text_area("Observações Adicionais (Opcional)")
        
        st.markdown("---")
        submitted = st.form_submit_button("🚀 GERAR CONTRATO", type="primary", use_container_width=True)
        
        if submitted:
            if not st.session_state.aluno_selecionado or not st.session_state.turma_selecionada:
                st.error("Faltam dados obrigatórios.")
            else:
                with st.spinner("Gerando documento PDF..."):
                    # Prepara os dados para o gerador
                    dados_contrato = {
                        "aluno": st.session_state.aluno_selecionado,
                        "curso": st.session_state.curso_selecionado,
                        "turma": st.session_state.turma_selecionada,
                        "valor_final": valor_final,
                        "forma_pagamento": forma_pagto,
                        "observacoes": observacoes,
                        "data_atual": date.today().strftime("%d/%m/%Y")
                    }
                    
                    # Chama o serviço de geração
                    caminho_pdf = ContractGenerator.gerar_pdf(dados_contrato)
                    
                    if caminho_pdf:
                        st.balloons()
                        st.success("Contrato gerado com sucesso!")
                        
                        # Botão de Download
                        with open(caminho_pdf, "rb") as f:
                            st.download_button(
                                label="📥 Baixar Contrato (PDF)",
                                data=f,
                                file_name=f"Contrato_{st.session_state.aluno_selecionado['nome_completo']}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.error("Erro ao gerar o arquivo. Verifique os logs.")

if __name__ == "__main__":
    main()
