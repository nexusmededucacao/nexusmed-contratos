import streamlit as st
import time
from datetime import date, datetime
from src.database.repo_alunos import AlunoRepository
from src.utils.formatters import format_cpf, format_phone

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

# Listas Auxiliares
LISTA_ESTADOS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
LISTA_ESTADO_CIVIL = ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"]

def formatar_data_br(data_iso):
    """Converte YYYY-MM-DD para DD/MM/YYYY"""
    if not data_iso: return "-"
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
    except:
        return data_iso

def main():
    st.title("👤 Gestão de Alunos")
    
    tab_listar, tab_cadastrar = st.tabs(["Lista de Alunos", "Cadastrar Novo Aluno"])

    # --- ABA 1: LISTA (FOCO EM EXIBIÇÃO VERTICAL) ---
    with tab_listar:
        st.subheader("Consultar Alunos")
        termo_busca = st.text_input("Buscar por Nome ou CPF", placeholder="Digite aqui...")
        
        if st.button("🔍 Buscar Aluno", type="primary", use_container_width=True):
            if termo_busca.isdigit():
                alunos = AlunoRepository.buscar_por_cpf(termo_busca)
            else:
                alunos = AlunoRepository.filtrar_por_nome(termo_busca)
        else:
            alunos = AlunoRepository.listar_todos()

        st.divider()

        if isinstance(alunos, list) and alunos:
            st.caption(f"Encontrados: {len(alunos)} registros.")
            
            for aluno in alunos:
                if not isinstance(aluno, dict): continue

                nome = aluno.get('nome_completo') or "Nome não informado"
                cpf = format_cpf(aluno.get('cpf', ''))
                
                with st.expander(f"👤 {nome} | CPF: {cpf}"):
                    # --- DADOS UM EMBAIXO DO OUTRO (SEM COLUNAS) ---
                    
                    st.markdown("#### 📄 Dados Pessoais")
                    st.markdown(f"**Nascimento:** {formatar_data_br(aluno.get('data_nascimento'))}")
                    st.markdown(f"**Nacionalidade:** {aluno.get('nacionalidade', '-')}")
                    st.markdown(f"**Estado Civil:** {aluno.get('estado_civil', '-')}")
                    st.markdown(f"**Email:** {aluno.get('email', '-')}")
                    st.markdown(f"**Telefone:** {format_phone(aluno.get('telefone', ''))}")

                    st.markdown("---")
                    st.markdown("#### 📍 Endereço")
                    st.markdown(f"**Logradouro:** {aluno.get('logradouro', '-')}, {aluno.get('numero', '-')}")
                    st.markdown(f"**Complemento:** {aluno.get('complemento', '-')}")
                    st.markdown(f"**Bairro:** {aluno.get('bairro', '-')}")
                    st.markdown(f"**Cidade/UF:** {aluno.get('cidade', '-')}/{aluno.get('uf', '-')}")
                    st.markdown(f"**CEP:** {aluno.get('cep', '-')}")

                    st.markdown("---")
                    st.markdown("#### 💼 Profissional")
                    st.markdown(f"**CRM:** {aluno.get('crm', '-')}")
                    st.markdown(f"**Área de Formação:** {aluno.get('area_formacao', '-')}")
                    
                    st.write("") 

                    # Botão de Edição no final do cartão
                    with st.popover("✏️ Editar Cadastro Completo", use_container_width=True):
                        with st.form(key=f"edit_{aluno.get('id')}"):
                            # Formulário também segue o fluxo vertical
                            e_nome = st.text_input("Nome Completo", value=aluno.get('nome_completo', ''))
                            e_email = st.text_input("Email", value=aluno.get('email', ''))
                            e_tel = st.text_input("Telefone", value=aluno.get('telefone', ''))
                            
                            try:
                                dt_atual = datetime.fromisoformat(aluno.get('data_nascimento')).date() if aluno.get('data_nascimento') else None
                            except: dt_atual = None
                            
                            e_nasc = st.date_input("Nascimento", value=dt_atual, min_value=date(1940, 1, 1))
                            e_nac = st.text_input("Nacionalidade", value=aluno.get('nacionalidade', 'Brasileira'))
                            
                            civ_at = aluno.get('estado_civil', '')
                            idx_civ = LISTA_ESTADO_CIVIL.index(civ_at) if civ_at in LISTA_ESTADO_CIVIL else 0
                            e_civil = st.selectbox("Estado Civil", LISTA_ESTADO_CIVIL, index=idx_civ)

                            st.divider()
                            e_log = st.text_input("Logradouro", value=aluno.get('logradouro', ''))
                            e_num = st.text_input("Número", value=aluno.get('numero', ''))
                            e_comp = st.text_input("Complemento", value=aluno.get('complemento', ''))
                            e_bai = st.text_input("Bairro", value=aluno.get('bairro', ''))
                            e_cid = st.text_input("Cidade", value=aluno.get('cidade', ''))
                            
                            uf_at = aluno.get('uf', '')
                            idx_uf = LISTA_ESTADOS.index(uf_at) if uf_at in LISTA_ESTADOS else 0
                            e_uf = st.selectbox("UF", LISTA_ESTADOS, index=idx_uf)

                            st.divider()
                            e_crm = st.text_input("CRM", value=aluno.get('crm', ''))
                            e_area = st.text_input("Área Formação", value=aluno.get('area_formacao', ''))

                            if st.form_submit_button("💾 Salvar Alterações"):
                                dados = {
                                    "nome_completo": e_nome, "email": e_email, "telefone": e_tel,
                                    "data_nascimento": e_nasc.isoformat(), "nacionalidade": e_nac,
                                    "estado_civil": e_civil, "logradouro": e_log, "numero": e_num,
                                    "complemento": e_comp, "bairro": e_bai, "cidade": e_cid,
                                    "uf": e_uf, "crm": e_crm, "area_formacao": e_area
                                }
                                AlunoRepository.atualizar_aluno(aluno['id'], dados)
                                st.success("Atualizado!")
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("Nenhum aluno encontrado.")

    # --- ABA 2: CADASTRAR NOVO ALUNO (Mantido Vertical) ---
    with tab_cadastrar:
        st.subheader("Cadastro de Novo Aluno")
        cpf_input = st.text_input("Informe o CPF para iniciar (Somente Números)", max_chars=14)
        
        if cpf_input:
            existe = AlunoRepository.buscar_por_cpf(cpf_input)
            
            if isinstance(existe, list) and len(existe) > 0:
                st.warning("⚠️ Aluno já cadastrado. Acesse a aba 'Lista de Alunos' para editar.")
            else:
                st.success("CPF Novo! Preencha os dados.")
                with st.form("form_novo", clear_on_submit=True):
                    st.markdown("### 1. Dados Pessoais")
                    nome = st.text_input("Nome Completo *")
                    email = st.text_input("E-mail *")
                    telefone = st.text_input("Telefone")
                    nascimento = st.date_input("Nascimento", min_value=date(1940, 1, 1), value=date(1990, 1, 1))
                    nacionalidade = st.text_input("Nacionalidade", value="Brasileira")
                    estado_civil = st.selectbox("Estado Civil", LISTA_ESTADO_CIVIL)

                    st.markdown("### 2. Endereço")
                    cep = st.text_input("CEP")
                    logradouro = st.text_input("Logradouro")
                    numero = st.text_input("Número")
                    complemento = st.text_input("Complemento")
                    bairro = st.text_input("Bairro")
                    cidade = st.text_input("Cidade")
                    uf = st.selectbox("UF", LISTA_ESTADOS)

                    st.markdown("### 3. Profissional")
                    crm = st.text_input("CRM")
                    area = st.text_input("Área de Formação")

                    if st.form_submit_button("✅ Salvar Aluno"):
                        if not nome or not email:
                            st.error("Nome e E-mail são obrigatórios.")
                        else:
                            novo_aluno = {
                                "nome_completo": nome,
                                "cpf": "".join(filter(str.isdigit, cpf_input)),
                                "email": email,
                                "telefone": telefone,
                                "data_nascimento": nascimento.isoformat(),
                                "estado_civil": estado_civil,
                                "nacionalidade": nacionalidade,
                                "cep": cep,
                                "logradouro": logradouro,
                                "numero": numero,
                                "complemento": complemento,
                                "bairro": bairro,
                                "cidade": cidade,
                                "uf": uf,
                                "crm": crm,
                                "area_formacao": area
                            }
                            res = AlunoRepository.criar_aluno(novo_aluno)
                            if isinstance(res, dict) and "error" in res:
                                st.error(res["error"])
                            else:
                                st.success("Cadastrado com sucesso!")
                                st.balloons()
                                time.sleep(1.5)
                                st.rerun()

if __name__ == "__main__":
    main()
