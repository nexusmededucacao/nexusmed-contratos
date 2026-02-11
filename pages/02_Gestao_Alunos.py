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

    # --- ÁREA DE DIAGNÓSTICO (Remova após corrigir) ---
    with st.expander("🕵️ DEBUG: Ver Colunas do Banco"):
        try:
            from src.database.connection import supabase
            # Tenta pegar 1 aluno qualquer para ver as chaves (colunas)
            resp = supabase.table("alunos").select("*").limit(1).execute()
            if resp.data:
                st.write("Colunas encontradas:", list(resp.data[0].keys()))
            else:
                st.warning("Tabela vazia. Cadastre um aluno manualmente no Supabase para ver as colunas.")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")
    # --------------------------------------------------
    
    tab_listar, tab_cadastrar = st.tabs(["Lista de Alunos", "Cadastrar Novo Aluno"])

    # --- ABA 1: LISTA E EDIÇÃO ---
    with tab_listar:
        col_search1, col_search2 = st.columns([4, 1])
        termo_busca = col_search1.text_input("Buscar Aluno", placeholder="Digite Nome ou CPF (apenas números)")
        
        # Lógica de Busca Híbrida
        if col_search2.button("🔍 Buscar"):
            if termo_busca.isdigit():
                alunos = AlunoRepository.buscar_por_cpf(termo_busca) # Busca Exata
            else:
                alunos = AlunoRepository.filtrar_por_nome(termo_busca) # Busca Parcial
        else:
            alunos = AlunoRepository.listar_todos()

        if alunos:
            st.caption(f"Encontrados: {len(alunos)} registros.")
            for aluno in alunos:
                # BLINDAGEM: Usa .get() para evitar erro se a coluna não existir ou tiver outro nome
                nome_display = aluno.get('nome_completo', 'Sem Nome (Verificar Banco)')
                cpf_display = format_cpf(aluno.get('cpf', '00000000000'))
                
                # Cabeçalho do Card
                titulo = f"{nome_display} - CPF: {cpf_display}"
                
                with st.expander(titulo):
                    # Visualização Rápida
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Email:** {aluno.get('email', '-')}")
                    c2.write(f"**Tel:** {format_phone(aluno.get('telefone', ''))}")
                    c3.write(f"**Cidade:** {aluno.get('cidade')}/{aluno.get('uf')}")
                    
                    st.divider()

                    # --- FORMULÁRIO DE EDIÇÃO (Pop-over) ---
                    with st.popover("✏️ Editar Cadastro Completo"):
                        st.write(f"Editando: **{nome_display}**")
                        
                        with st.form(key=f"edit_aluno_{aluno['id']}"):
                            # 1. Dados Pessoais
                            st.caption("Dados Pessoais")
                            e_nome = st.text_input("Nome Completo", value=aluno.get('nome_completo', ''))
                            
                            ec1, ec2 = st.columns(2)
                            # Tratamento de data seguro
                            data_bd = aluno.get('data_nascimento')
                            dt_val = datetime.fromisoformat(data_bd).date() if data_bd else None
                            e_nasc = ec1.date_input("Nascimento", value=dt_val, min_value=date(1940, 1, 1), max_value=date.today())
                            e_nac = ec2.text_input("Nacionalidade", value=aluno.get('nacionalidade', 'Brasileira'))
                            
                            ec3, ec4 = st.columns(2)
                            # Indexação segura para dropdowns
                            est_civil_bd = aluno.get('estado_civil', '')
                            idx_civil = LISTA_ESTADO_CIVIL.index(est_civil_bd) if est_civil_bd in LISTA_ESTADO_CIVIL else 0
                            e_civil = ec3.selectbox("Estado Civil", LISTA_ESTADO_CIVIL, index=idx_civil)
                            e_tel = ec4.text_input("Telefone", value=aluno.get('telefone', ''))
                            
                            e_email = st.text_input("Email", value=aluno.get('email', ''))

                            # 2. Endereço
                            st.caption("Endereço")
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
                            st.caption("Profissional")
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
                                st.success("Cadastro atualizado!")
                                time.sleep(1.5)
                                st.rerun()
        else:
            st.info("Nenhum aluno encontrado.")

    # --- ABA 2: CADASTRAR NOVO ALUNO ---
    with tab_cadastrar:
        st.subheader("Cadastro de Novo Aluno")
        
        # 1. Validação Inicial de CPF (Regra de Negócio)
        cpf_input = st.text_input("Informe o CPF para iniciar (Somente Números)", max_chars=14)
        
        if cpf_input:
            # Verifica duplicidade
            existe = AlunoRepository.buscar_por_cpf(cpf_input)
            
            if existe:
                # --- CORREÇÃO FEITA AQUI ---
                # Mensagem fixa e amigável, sem acessar colunas dinâmicas que podem falhar
                st.warning("⚠️ Aluno já cadastrado. Para atualizar o cadastro, acesse a aba 'Lista de Alunos'.")
            else:
                st.success("CPF Novo! Preencha os dados abaixo.")
                
                with st.form("form_novo", clear_on_submit=True):
                    # Seção Pessoal
                    st.markdown("### 1. Dados Pessoais")
                    nome = st.text_input("Nome Completo *")
                    
                    c1, c2 = st.columns(2)
                    email = c1.text_input("E-mail *")
                    telefone = c2.text_input("Telefone")
                    
                    c3, c4, c5 = st.columns(3)
                    # Data começando em 1990 para facilitar a UX
                    nascimento = c3.date_input("Data Nascimento", min_value=date(1940, 1, 1), max_value=date.today(), value=date(1990, 1, 1))
                    nacionalidade = c4.text_input("Nacionalidade", value="Brasileira")
                    estado_civil = c5.selectbox("Estado Civil", LISTA_ESTADO_CIVIL)

                    # Seção Endereço
                    st.markdown("### 2. Endereço")
                    col_cep, col_log = st.columns([1, 3])
                    cep = col_cep.text_input("CEP")
                    logradouro = col_log.text_input("Logradouro (Rua, Av...)")
                    
                    col_num, col_comp = st.columns([1, 2])
                    numero = col_num.text_input("Número")
                    complemento = col_comp.text_input("Complemento (Apto, Bloco...)")
                    
                    col_bai, col_cid, col_uf = st.columns([2, 2, 1])
                    bairro = col_bai.text_input("Bairro")
                    cidade = col_cid.text_input("Cidade")
                    uf = col_uf.selectbox("UF", LISTA_ESTADOS)

                    # Seção Profissional
                    st.markdown("### 3. Profissional")
                    cp1, cp2 = st.columns(2)
                    crm = cp1.text_input("CRM")
                    area = cp2.text_input("Área de Formação")

                    st.markdown("---")
                    btn_salvar = st.form_submit_button("✅ Salvar Aluno")
                    
                    if btn_salvar:
                        if not nome or not email:
                            st.error("Nome e E-mail são obrigatórios.")
                        else:
                            # Monta dicionário EXATAMENTE com os campos do banco
                            novo_aluno = {
                                "nome_completo": nome,
                                "cpf": "".join(filter(str.isdigit, cpf_input)), # Limpa pontuação
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
                                st.success("Aluno cadastrado com sucesso!")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()

if __name__ == "__main__":
    main()
