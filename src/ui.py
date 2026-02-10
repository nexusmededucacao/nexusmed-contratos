import streamlit as st
import pandas as pd
import hashlib
import pytz
from datetime import datetime, date
from src.auth import login_usuario
from src.repository import (
    get_cursos, create_curso, 
    get_turmas_by_curso, create_turma, 
    get_aluno_by_cpf, upsert_aluno, 
    create_contrato, get_contrato_by_token, registrar_aceite
)
from src.services import gerar_contrato_pdf, enviar_email, aplicar_carimbo_digital

# --- COMPONENTES AUXILIARES ---

def render_login():
    st.markdown("<h1 style='text-align: center;'>🔒 NexusMed Portal</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            
            if submitted:
                user = login_usuario(email, senha)
                if user:
                    st.session_state['usuario'] = user
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

def render_sidebar():
    if 'usuario' not in st.session_state or not st.session_state['usuario']:
        return None
        
    user = st.session_state['usuario']
    st.sidebar.title(f"Olá, {user['nome'].split()[0]}")
    st.sidebar.caption(f"Perfil: {user['perfil'].upper()}")
    
    opcoes = ["Gerar Contrato", "Gestão de Alunos"]
    
    if user['perfil'] == 'admin':
        opcoes.extend(["Gestão de Cursos", "Gestão de Usuários"])
    
    opcoes.append("Sair")
    
    escolha = st.sidebar.radio("Navegação", opcoes)
    
    if escolha == "Sair":
        st.session_state['usuario'] = None
        st.rerun()
        
    return escolha

# --- TELAS DO SISTEMA ---

def tela_gestao_cursos():
    st.header("📚 Gestão de Oferta Acadêmica")
    tab1, tab2 = st.tabs(["Cursos (Produtos)", "Turmas (Calendário)"])
    
    with tab1:
        with st.form("form_curso"):
            st.subheader("Novo Curso")
            nome = st.text_input("Nome da Pós-Graduação (Ex: Dermatologia)")
            duracao = st.number_input("Duração em Meses", 1, 60, 12)
            carga = st.number_input("Carga Horária", 0, 5000, 360)
            valor = st.number_input("Valor Bruto (R$)", 0.0, format="%.2f")
            
            if st.form_submit_button("Salvar Curso"):
                create_curso({
                    "nome": nome, 
                    "duracao_meses": duracao, 
                    "carga_horaria": carga,
                    "valor_bruto": valor
                })
                st.success("Curso criado com sucesso!")
                
        st.divider()
        st.caption("Cursos Cadastrados:")
        st.dataframe(pd.DataFrame(get_cursos()))

    with tab2:
        cursos = get_cursos()
        if not cursos:
            st.warning("Cadastre um curso antes de criar turmas.")
        else:
            opcoes = {c['nome']: c['id'] for c in cursos}
            nome_curso_sel = st.selectbox("Selecione o Curso Pai", list(opcoes.keys()))
            id_curso_sel = opcoes[nome_curso_sel]
            
            with st.form("form_turma"):
                st.subheader(f"Nova Turma para {nome_curso_sel}")
                col_t1, col_t2 = st.columns(2)
                codigo = col_t1.text_input("Código da Turma (Ex: DERMA-2026.1)")
                formato = col_t2.selectbox("Formato", ["Digital", "Híbrido", "Presencial"])
                
                d1, d2 = st.columns(2)
                ini = d1.date_input("Data Início")
                fim = d2.date_input("Data Fim")
                
                if st.form_submit_button("Criar Turma"):
                    create_turma({
                        "curso_id": id_curso_sel,
                        "codigo_turma": codigo,
                        "formato": formato,
                        "data_inicio": str(ini),
                        "data_fim": str(fim)
                    })
                    st.success("Turma criada!")
            
            st.dataframe(pd.DataFrame(get_turmas_by_curso(id_curso_sel)))

def tela_gestao_alunos():
    st.header("📇 Cadastro Completo de Alunos")
    cpf_busca = st.text_input("🔍 Buscar por CPF (Digite apenas números)", max_chars=14)
    
    # CORREÇÃO: Adicionamos key="btn_buscar_unico" para evitar duplicidade de ID
    if st.button("Buscar Aluno", key="btn_buscar_unico"):
         encontrado = get_aluno_by_cpf(cpf_busca)
         st.session_state['dados_aluno_atual'] = encontrado if encontrado else {}

    if 'dados_aluno_atual' in st.session_state:
        dados = st.session_state['dados_aluno_atual']
        novo = not bool(dados)
        
        if novo:
            st.info("CPF não encontrado. Preencha abaixo para cadastrar um novo aluno.")
        else:
            st.success(f"Aluno encontrado: {dados.get('nome_completo')}. Edite os dados abaixo se necessário.")

        with st.form("form_aluno_completo"):
            st.subheader("1. Dados Pessoais")
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome Completo", value=dados.get('nome_completo', ''))
            cpf = c2.text_input("CPF", value=dados.get('cpf', cpf_busca))
            rg = c3.text_input("RG", value=dados.get('rg', ''))
            
            c4, c5, c6 = st.columns(3)
            email = c4.text_input("E-mail", value=dados.get('email', ''))
            telefone = c5.text_input("Telefone/Celular", value=dados.get('telefone', ''))
            
            val_nasc = None
            if dados.get('data_nascimento'):
                try: val_nasc = datetime.strptime(str(dados['data_nascimento']), '%Y-%m-%d')
                except: val_nasc = None
            
            data_nasc = c6.date_input("Data Nascimento", value=val_nasc, min_value=date(1940, 1, 1))
            
            c7, c8 = st.columns(2)
            nacionalidade = c7.text_input("Nacionalidade", value=dados.get('nacionalidade', 'Brasileira'))
            
            lista_ec = ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"]
            ec_atual = dados.get('estado_civil', 'Solteiro(a)')
            idx_ec = lista_ec.index(ec_atual) if ec_atual in lista_ec else 0
            estado_civil = c8.selectbox("Estado Civil", lista_ec, index=idx_ec)

            st.subheader("2. Endereço Completo")
            e1, e2 = st.columns([3, 1])
            logradouro = e1.text_input("Logradouro (Rua/Av)", value=dados.get('logradouro', ''))
            numero = e2.text_input("Número", value=dados.get('numero', ''))
            
            e3, e4 = st.columns([1, 1])
            complemento = e3.text_input("Complemento", value=dados.get('complemento', ''))
            bairro = e4.text_input("Bairro", value=dados.get('bairro', ''))
            
            e5, e6, e7 = st.columns(3)
            cidade = e5.text_input("Cidade", value=dados.get('cidade', ''))
            uf = e6.text_input("UF", value=dados.get('uf', ''), max_chars=2)
            cep = e7.text_input("CEP", value=dados.get('cep', ''))

            st.subheader("3. Dados Profissionais (Médicos)")
            p1, p2 = st.columns(2)
            crm = p1.text_input("CRM Primário", value=dados.get('crm', ''))
            area = p2.text_input("Área de Formação", value=dados.get('area_formacao', ''))

            if st.form_submit_button("💾 Salvar Cadastro do Aluno"):
                payload = {
                    "nome_completo": nome, "cpf": cpf, "rg": rg, "email": email,
                    "telefone": telefone, "data_nascimento": str(data_nasc),
                    "nacionalidade": nacionalidade, "estado_civil": estado_civil,
                    "logradouro": logradouro, "numero": numero, "complemento": complemento,
                    "bairro": bairro, "cidade": cidade, "uf": uf, "cep": cep,
                    "crm": crm, "area_formacao": area
                }
                upsert_aluno(payload)
                st.success("Dados salvos!")
                del st.session_state['dados_aluno_atual']
                st.rerun()

def tela_novo_contrato():
    st.header("📝 Emissão de Contrato")
    
    col_sel1, col_sel2 = st.columns(2)
    cpf_aluno = col_sel1.text_input("Passo 1: Digite CPF do Aluno cadastrado")
    
    aluno = None
    if cpf_aluno:
        aluno = get_aluno_by_cpf(cpf_aluno)
        if aluno:
            st.success(f"Aluno: **{aluno['nome_completo']}**")
        else:
            st.error("Aluno não encontrado.")
            st.stop()
            
    cursos = get_cursos()
    nome_curso = col_sel2.selectbox("Passo 2: Selecione o Curso", [c['nome'] for c in cursos] if cursos else [])
    
    curso_selecionado = next((c for c in cursos if c['nome'] == nome_curso), None)
    turma_selecionada = None
    
    if curso_selecionado:
        turmas = get_turmas_by_curso(curso_selecionado['id'])
        if turmas:
            cod_turma = st.selectbox("Passo 3: Selecione a Turma", [t['codigo_turma'] for t in turmas])
            turma_selecionada = next(t for t in turmas if t['codigo_turma'] == cod_turma)
        else:
            st.warning("Sem turmas abertas.")
            st.stop()

    if aluno and curso_selecionado and turma_selecionada:
        st.divider()
        st.subheader("Configuração Financeira")
        
        with st.form("form_contrato"):
            valor_base = float(curso_selecionado['valor_bruto'])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor", f"R$ {valor_base:,.2f}")
            percentual = c2.number_input("% Desconto", 0.0, 100.0, 0.0, step=0.5)
            
            valor_desconto = valor_base * (percentual / 100)
            valor_final = valor_base - valor_desconto
            
            c3.metric("Saldo", f"R$ {valor_final:,.2f}")

            st.markdown("---")
            col_ent1, col_ent2, col_ent3 = st.columns(3)
            entrada_val = col_ent1.number_input("Valor Entrada", 0.0, valor_final, 0.0)
            entrada_qtd = col_ent2.number_input("Qtd Parc. Entrada", 1, 3, 1)
            entrada_dt = col_ent3.date_input("Venc. Entrada", value=date.today())
            
            saldo_restante = valor_final - entrada_val
            st.caption(f"Saldo a parcelar: R$ {saldo_restante:,.2f}")
            
            col_sal1, col_sal2 = st.columns(2)
            saldo_qtd = col_sal1.number_input("Qtd Parc. Saldo", 1, 60, 12)
            saldo_dt = col_sal2.date_input("Venc. Saldo", value=date.today())

            st.markdown("---")
            col_opt1, col_opt2 = st.columns(2)
            bolsista = col_opt1.checkbox("Bolsista?")
            atendimento = col_opt2.checkbox("Atendimento Paciente?")
            
            if st.form_submit_button("🚀 Gerar Contrato"):
                with st.spinner("Processando..."):
                    dados_contrato = {
                        "aluno_id": aluno['id'],
                        "turma_id": turma_selecionada['id'],
                        "valor_curso": valor_base,
                        "percentual_desconto": percentual,
                        "valor_desconto": valor_desconto,
                        "valor_final": valor_final,
                        "valor_material": valor_base * 0.3,
                        "entrada_valor": entrada_val,
                        "entrada_qtd_parcelas": entrada_qtd,
                        "entrada_forma_pagamento": "Boleto/Pix",
                        "saldo_valor": saldo_restante,
                        "saldo_qtd_parcelas": saldo_qtd,
                        "saldo_forma_pagamento": "Boleto/Pix",
                        "bolsista": bolsista,
                        "atendimento_paciente": atendimento,
                        "formato_curso": turma_selecionada['formato']
                    }
                    
                    datas = {"entrada": entrada_dt, "saldo": saldo_dt}
                    
                    caminho = gerar_contrato_pdf(aluno, turma_selecionada, curso_selecionado, dados_contrato, datas)
                    
                    if caminho:
                        dados_contrato['caminho_arquivo'] = caminho
                        contrato = create_contrato(dados_contrato)
                        
                        link = f"https://nexusmed-contratos.streamlit.app/?token={contrato['token_acesso']}"
                        enviou = enviar_email(aluno['email'], aluno['nome_completo'], link)
                        
                        if enviou:
                            st.success("Sucesso! E-mail enviado.")
                            st.balloons()
                        else:
                            st.warning("Contrato gerado, mas falha no e-mail.")
                    else:
                        st.error("Erro ao gerar PDF.")

def tela_aceite_aluno(token):
    st.set_page_config(page_title="Assinatura", layout="centered")
    
    contrato_data = get_contrato_by_token(token)
    
    if not contrato_data:
        st.error("Link inválido.")
        st.stop()
        
    contrato = contrato_data
    aluno = contrato_data.get('alunos') or contrato_data.get('aluno')
    
    if not aluno:
        st.error("Erro: Aluno não identificado.")
        st.stop()

    if contrato['status'] == 'assinado':
        st.info("✅ Contrato já assinado.")
        return

    st.title("Assinatura Digital")
    st.write(f"Olá, **{aluno['nome_completo']}**.")
    
    with st.form("form_aceite"):
        st.write("Confirme seus dados:")
        nome_input = st.text_input("Seu Nome")
        cpf_input = st.text_input("Seu CPF")
        check = st.checkbox("Li e concordo com o contrato.")
        
        if st.form_submit_button("ASSINAR"):
            cpf_real = aluno['cpf']
            cpf_limpo = ''.join(filter(str.isdigit, cpf_input))
            
            if cpf_limpo != cpf_real or not check:
                st.error("Dados incorretos ou termo não marcado.")
            else:
                fuso = pytz.timezone('America/Sao_Paulo')
                agora = datetime.now(fuso)
                
                # Simulação de Carimbo
                texto = f"ASSINADO DIGITALMENTE EM {agora}"
                
                # Atualiza Banco
                registrar_aceite(contrato['id'], {
                    "status": "assinado",
                    "data_aceite": agora.isoformat(),
                    "recibo_aceite_texto": texto
                })
                st.balloons()
                st.success("Contrato Assinado!")
