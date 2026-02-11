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

def main():
    st.title("👤 Gestão de Alunos")
    
    tab_listar, tab_cadastrar = st.tabs(["Lista de Alunos", "Cadastrar Novo Aluno"])

    # --- ABA 1: LISTA E BUSCA ---
    with tab_listar:
        col_search1, col_search2 = st.columns([4, 1])
        termo_busca = col_search1.text_input("Buscar Aluno", placeholder="Digite Nome ou CPF")
        
        if col_search2.button("🔍 Buscar"):
            if termo_busca.isdigit():
                alunos = AlunoRepository.buscar_por_cpf(termo_busca)
            else:
                alunos = AlunoRepository.filtrar_por_nome(termo_busca)
        else:
            alunos = AlunoRepository.listar_todos()

        # Verifica se o retorno é válido
        if isinstance(alunos, list):
            st.caption(f"Encontrados: {len(alunos)} registros.")
            
            for aluno in alunos:
                if not isinstance(aluno, dict): continue

                # BLINDAGEM: Usa .get() para evitar o erro KeyError
                # Se o campo estiver vazio no banco, mostra um texto padrão
                nome_display = aluno.get('nome_completo') or "Nome não informado"
                cpf_display = format_cpf(aluno.get('cpf', '00000000000'))
                
                with st.expander(f"{nome_display} - CPF: {cpf_display}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Email:** {aluno.get('email', '-')}")
                    c2.write(f"**Tel:** {format_phone(aluno.get('telefone', ''))}")
                    c3.write(f"**Cidade:** {aluno.get('cidade')}/{aluno.get('uf')}")
                    
                    st.divider()

                    # --- FORMULÁRIO DE EDIÇÃO ---
                    with st.popover("✏️ Editar Cadastro"):
                        st.write(f"Editando: **{nome_display}**")
                        with st.form(key=f"edit_aluno_{aluno.get('id')}"):
                            # 1. Pessoal
                            e_nome = st.text_input("Nome Completo", value=aluno.get('nome_completo', ''))
                            
                            ec1, ec2 = st.columns(2)
                            # Data segura
                            try:
                                dt_val = datetime.fromisoformat(aluno.get('data_nascimento')).date() if aluno.get('data_nascimento') else None
                            except:
                                dt_val = None
                            e_nasc = ec1.date_input("Nascimento", value=dt_val, min_value=date(1940, 1, 1), max_value=date.today())
                            e_nac = ec2.text_input("Nacionalidade", value=aluno.get('nacionalidade', 'Brasileira'))
                            
                            ec3, ec4 = st.columns(2)
                            est_civil = aluno.get('estado_civil', '')
                            idx_civil = LISTA_ESTADO_CIVIL.index(est_civil) if est_civil in LISTA_ESTADO_CIVIL else 0
                            e_civil = ec3.selectbox("Estado Civil", LISTA_ESTADO_CIVIL, index=idx_civil)
                            e_tel = ec4.text_input("Telefone", value=aluno.get('telefone', ''))
                            
                            e_email = st.text_input("Email", value=aluno.get('email', ''))

                            # 2. Endereço
                            e_cep = st.text_input("CEP", value=aluno.get('cep', ''))
                            el1, el2 = st.columns([3, 1])
                            e_log = el1.text_input("Logradouro", value=aluno.get('logradouro', ''))
                            e_num = el2.text_input("Número", value=aluno.get('numero', ''))
                            e_comp = st.text_input("Complemento", value=aluno.get('complemento', ''))
                            
                            el3, el4, el5 = st.columns([2, 2, 1])
                            e_bairro = el3.text_input("Bairro", value=aluno.get('bairro', ''))
                            e_cidade = el4.text_input("Cidade", value=aluno.get('cidade', ''))
                            
                            uf_bd = aluno.get('uf', '')
                            idx_uf = LISTA_ESTADOS.index(uf_bd) if uf_bd in LISTA_ESTADOS else 0
                            e_uf = el5.selectbox("UF", LISTA_ESTADOS, index=idx_uf)

                            # 3. Profissional
                            ep1, ep2 = st.columns(2)
                            e_crm = ep1.text_input("CRM", value=aluno.get('crm', ''))
                            e_area = ep2.text_input("Área Formação", value=aluno.get('area_formacao', ''))

                            if st.form_submit_button("💾 Salvar Alterações"):
                                dados_update = {
                                    "nome_completo": e_nome,
                                    "data_nascimento": e_nasc.isoformat() if e_nasc else None,
                                    "nacionalidade": e_nac,
                                    "estado_civil": e_civil,
                                    "telefone": e_tel,
                                    "email": e_email,
                                    "cep": e_cep,
                                    "logradouro": e_log,
                                    "numero": e_num,
                                    "complemento": e_comp,
                                    "bairro": e_bairro,
                                    "cidade": e_cidade,
                                    "uf": e_uf,
                                    "crm": e_crm,
                                    "area_formacao": e_area
                                }
                                AlunoRepository.atualizar_aluno(aluno['id'], dados_update)
                                st.success("Atualizado!")
                                time.sleep(1.5)
                                st.rerun()
        else:
            st.warning("Não foi possível carregar a lista. Tente recarregar a página.")

    # --- ABA 2: CADASTRAR NOVO ALUNO ---
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
                    # Seção 1
                    nome = st.text_input("Nome Completo *")
                    c1, c2 = st.columns(2)
                    email = c1.text_input("E-mail *")
                    telefone = c2.text_input("Telefone")
                    
                    c3, c4, c5 = st.columns(3)
                    nascimento = c3.date_input("Nascimento", min_value=date(1940, 1, 1), max_value=date.today(), value=date(1990, 1, 1))
                    nacionalidade = c4.text_input("Nacionalidade", value="Brasileira")
                    estado_civil = c5.selectbox("Estado Civil", LISTA_ESTADO_CIVIL)

                    # Seção 2
                    col_cep, col_log = st.columns([1, 3])
                    cep = col_cep.text_input("CEP")
                    logradouro = col_log.text_input("Logradouro")
                    col_num, col_comp = st.columns([1, 2])
                    numero = col_num.text_input("Número")
                    complemento = col_comp.text_input("Complemento")
                    col_bai, col_cid, col_uf = st.columns([2, 2, 1])
                    bairro = col_bai.text_input("Bairro")
                    cidade = col_cid.text_input("Cidade")
                    uf = col_uf.selectbox("UF", LISTA_ESTADOS)

                    # Seção 3
                    cp1, cp2 = st.columns(2)
                    crm = cp1.text_input("CRM")
                    area = cp2.text_input("Área de Formação")

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
