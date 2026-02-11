import streamlit as st
from src.database.repo_alunos import AlunoRepository
from src.utils.formatters import format_cpf, format_phone

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

def main():
    st.title("👤 Gestão de Alunos")
    
    tab_listar, tab_cadastrar = st.tabs(["Lista de Alunos", "Cadastrar Novo Aluno"])

    # --- ABA: LISTA DE ALUNOS ---
    with tab_listar:
        busca = st.text_input("Buscar aluno por nome", placeholder="Digite o nome para filtrar...")
        
        if busca:
            alunos = AlunoRepository.filtrar_por_nome(busca)
        else:
            alunos = AlunoRepository.listar_todos()

        if alunos:
            for aluno in alunos:
                with st.expander(f"{aluno['nome_completo']} (CPF: {format_cpf(aluno['cpf'])})"):
                    col1, col2, col3 = st.columns(3)
                    col1.write(f"**Email:** {aluno['email']}")
                    col2.write(f"**Telefone:** {format_phone(aluno.get('telefone', ''))}")
                    col3.write(f"**CRM:** {aluno.get('crm', 'N/A')}")
                    
                    st.write("**Endereço:**")
                    st.write(f"{aluno.get('logradouro')}, {aluno.get('numero')} - {aluno.get('bairro')}")
                    st.write(f"{aluno.get('cidade')} / {aluno.get('uf')} - CEP: {aluno.get('cep')}")
                    
                    if st.button("Editar Dados", key=f"edit_{aluno['id']}"):
                        st.info("Funcionalidade de edição em desenvolvimento.")
        else:
            st.info("Nenhum aluno encontrado.")

    # --- ABA: CADASTRAR ALUNO ---
    with tab_cadastrar:
        with st.form("form_novo_aluno", clear_on_submit=True):
            st.subheader("Informações Pessoais")
            nome = st.text_input("Nome Completo *")
            
            col1, col2, col3 = st.columns(3)
            cpf = col1.text_input("CPF (apenas números) *")
            rg = col2.text_input("RG")
            nascimento = col3.date_input("Data de Nascimento", value=None)
            
            col1, col2 = st.columns(2)
            email = col1.text_input("E-mail *")
            telefone = col2.text_input("Telefone (com DDD)")

            st.write("---")
            st.subheader("Endereço")
            cep = st.text_input("CEP")
            
            col_rua, col_num = st.columns([3, 1])
            rua = col_rua.text_input("Logradouro")
            num = col_num.text_input("Nº")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            bairro = col1.text_input("Bairro")
            cidade = col2.text_input("Cidade")
            uf = col3.selectbox("UF", ["", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"])

            st.write("---")
            st.subheader("Dados Profissionais")
            col1, col2 = st.columns(2)
            crm = col1.text_input("CRM")
            area = col2.text_input("Área de Formação")

            enviar = st.form_submit_button("Salvar Cadastro")

            if enviar:
                if not nome or not cpf or not email:
                    st.error("Por favor, preencha os campos obrigatórios (*).")
                else:
                    # Preparação do dicionário para o Supabase
                    dados_aluno = {
                        "nome_completo": nome,
                        "cpf": "".join(filter(str.isdigit, cpf)),
                        "rg": rg,
                        "email": email,
                        "telefone": telefone,
                        "data_nascimento": nascimento.isoformat() if nascimento else None,
                        "logradouro": rua,
                        "numero": num,
                        "bairro": bairro,
                        "cidade": cidade,
                        "uf": uf,
                        "cep": cep,
                        "crm": crm,
                        "area_formacao": area
                    }
                    
                    resultado = AlunoRepository.criar_aluno(dados_aluno)
                    
                    if isinstance(resultado, dict) and "error" in resultado:
                        st.error(resultado["error"])
                    else:
                        st.success("Aluno cadastrado com sucesso!")
                        st.balloons()

if __name__ == "__main__":
    main()
