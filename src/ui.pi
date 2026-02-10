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
    user = st.session_state['usuario']
    st.sidebar.title(f"Olá, {user['nome'].split()[0]}")
    st.sidebar.caption(f"Perfil: {user['perfil'].upper()}")
    
    opcoes = ["Gerar Contrato", "Gestão de Alunos"]
    
    # Apenas Admin vê a gestão do produto (Cursos/Turmas/Usuários)
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
    
    # Busca para evitar duplicidade
    cpf_busca = st.text_input("🔍 Buscar por CPF (Digite apenas números)", max_chars=14)
    
    # Estado local para carregar dados
    if st.button("Buscar") or 'dados_aluno_atual' in st.session_state:
        # Se clicou buscar, vai no banco. Se já tem na sessão, mantém (para não perder o que digitou)
        if 'dados_aluno_atual' not in st.session_state or st.button("Buscar"): 
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
            # Mapeamento exato do Template Word
            nome = c1.text_input("Nome Completo {{ nome }}", value=dados.get('nome_completo', ''))
            cpf = c2.text_input("CPF {{ cpf }}", value=dados.get('cpf', cpf_busca))
            rg = c3.text_input("RG {{ rg }}", value=dados.get('rg', ''))
            
            c4, c5, c6 = st.columns(3)
            email = c4.text_input("E-mail {{ email }}", value=dados.get('email', ''))
            telefone = c5.text_input("Telefone/Celular {{ telefone }}", value=dados.get('telefone', ''))
            
            # Tratamento de data para o date_input
            val_nasc = None
            if dados.get('data_nascimento'):
                val_nasc = datetime.strptime(str(dados['data_nascimento']), '%Y-%m-%d')
            
            data_nasc = c6.date_input("Data Nascimento {{ data_nascimento }}", value=val_nasc, min_value=date(1940, 1, 1))
            
            c7, c8 = st.columns(2)
            nacionalidade = c7.text_input("Nacionalidade {{ nacionalidade }}", value=dados.get('nacionalidade', 'Brasileira'))
            estado_civil = c8.selectbox("Estado Civil {{ estado_civil }}", 
                                        ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"],
                                        index=["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"].index(dados.get('estado_civil', 'Solteiro(a)')))

            st.subheader("2. Endereço Completo")
            e1, e2 = st.columns([3, 1])
            logradouro = e1.text_input("Logradouro (Rua/Av) {{ logradouro }}", value=dados.get('logradouro', ''))
            numero = e2.text_input("Número {{ numero }}", value=dados.get('numero', ''))
            
            e3, e4 = st.columns([1, 1])
            complemento = e3.text_input("Complemento {{ complemento }}", value=dados.get('complemento', ''))
            bairro = e4.text_input("Bairro {{ bairro }}", value=dados.get('bairro', ''))
            
            e5, e6, e7 = st.columns(3)
            cidade = e5.text_input("Cidade {{ cidade }}", value=dados.get('cidade', ''))
            uf = e6.text_input("UF {{ uf }}", value=dados.get('uf', ''), max_chars=2)
            cep = e7.text_input("CEP {{ cep }}", value=dados.get('cep', ''))

            st.subheader("3. Dados Profissionais (Médicos)")
            p1, p2 = st.columns(2)
            crm = p1.text_input("CRM Primário {{ crm }}", value=dados.get('crm', ''))
            area = p2.text_input("Área de Formação {{ área_formação }}", value=dados.get('area_formacao', ''))

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
                st.success("Dados do aluno salvos com sucesso! Agora você pode gerar o contrato.")
                # Limpa sessão para forçar recarregamento se necessário
                del st.session_state['dados_aluno_atual']

def tela_novo_contrato():
    st.header("📝 Emissão de Contrato")
    
    # ETAPA 1: SELEÇÃO
    col_sel1, col_sel2 = st.columns(2)
    cpf_aluno = col_sel1.text_input("Passo 1: Digite CPF do Aluno cadastrado")
    
    aluno = None
    if cpf_aluno:
        aluno = get_aluno_by_cpf(cpf_aluno)
        if aluno:
            st.success(f"Aluno Selecionado: **{aluno['nome_completo']}**")
        else:
            st.error("Aluno não encontrado. Vá em 'Gestão de Alunos' primeiro.")
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
            st.warning("Este curso não possui turmas abertas.")
            st.stop()

    # ETAPA 2: FINANCEIRO
    if aluno and curso_selecionado and turma_selecionada:
        st.divider()
        st.subheader("Configuração Financeira")
        
        with st.form("form_contrato"):
            # Valores Base
            valor_base = float(curso_selecionado['valor_bruto'])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor do Curso {{ valor_curso }}", f"R$ {valor_base:,.2f}")
            percentual = c2.number_input("% Desconto {{ pencentual_desconto }}", 0.0, 100.0, 0.0, step=0.5)
            
            # Cálculos em tempo real (dentro do submit ou via session state, aqui simplificado)
            valor_desconto = valor_base * (percentual / 100)
            valor_final = valor_base - valor_desconto
            
            c3.metric("Valor Final (Saldo) {{ valor_final }}", f"R$ {valor_final:,.2f}")
            st.caption(f"Desconto calculado: R$ {valor_desconto:,.2f}")

            st.markdown("---")
            st.write("**Entrada**")
            col_ent1, col_ent2, col_ent3 = st.columns(3)
            entrada_val = col_ent1.number_input("Valor da Entrada", 0.0, valor_final, 0.0)
            entrada_qtd = col_ent2.number_input("Nº Parcelas Entrada", 1, 3, 1)
            entrada_dt = col_ent3.date_input("Vencimento 1ª Entrada", value=date.today())
            
            st.write("**Saldo Restante**")
            saldo_restante = valor_final - entrada_val
            st.info(f"Saldo a parcelar: R$ {saldo_restante:,.2f}")
            
            col_sal1, col_sal2 = st.columns(2)
            saldo_qtd = col_sal1.number_input("Nº Parcelas Saldo", 1, 60, 12)
            saldo_dt = col_sal2.date_input("Vencimento 1ª Saldo (As demais serão +30 dias)", value=date.today())

            st.markdown("---")
            col_opt1, col_opt2 = st.columns(2)
            bolsista = col_opt1.checkbox("É Bolsista? {{ bolsista }}")
            atendimento = col_opt2.checkbox("Atendimento a Paciente? {{ atendimento }}")
            
            # Botão de Geração
            btn_gerar = st.form_submit_button("🚀 Gerar Contrato e Enviar E-mail")
            
            if btn_gerar:
                with st.spinner("Gerando PDF, salvando no banco e enviando e-mail..."):
                    # Prepara dados para salvar no banco (Tabela Contratos)
                    dados_contrato = {
                        "aluno_id": aluno['id'],
                        "turma_id": turma_selecionada['id'],
                        "valor_curso": valor_base,
                        "percentual_desconto": percentual,
                        "valor_desconto": valor_desconto,
                        "valor_final": valor_final,
                        "valor_material": valor_base * 0.3, # Regra de Negócio Fixa
                        "entrada_valor": entrada_val,
                        "entrada_qtd_parcelas": entrada_qtd,
                        "entrada_forma_pagamento": "Boleto/Pix", # Padrão ou adicionar selectbox
                        "saldo_valor": saldo_restante,
                        "saldo_qtd_parcelas": saldo_qtd,
                        "saldo_forma_pagamento": "Boleto/Pix",
                        "bolsista": bolsista,
                        "atendimento_paciente": atendimento,
                        "formato_curso": turma_selecionada['formato']
                    }
                    
                    datas_vencimento = {
                        "entrada": entrada_dt,
                        "saldo": saldo_dt
                    }
                    
                    # 1. Gera PDF e Sobe no Storage
                    caminho_pdf = gerar_contrato_pdf(aluno, turma_selecionada, curso_selecionado, dados_contrato, datas_vencimento)
                    
                    if caminho_pdf:
                        # 2. Salva registro no Banco
                        dados_contrato['caminho_arquivo'] = caminho_pdf
                        contrato_salvo = create_contrato(dados_contrato)
                        
                        # 3. Envia E-mail
                        # AJUSTE SUA URL FINAL AQUI QUANDO FIZER O DEPLOY
                        link_acesso = f"https://SEU-APP-NAME.streamlit.app/?token={contrato_salvo['token_acesso']}"
                        enviou = enviar_email(aluno['email'], aluno['nome_completo'], link_acesso)
                        
                        if enviou:
                            st.success("✅ Processo concluído! O aluno recebeu o link para assinatura.")
                            st.balloons()
                        else:
                            st.warning("Contrato gerado, mas houve erro no envio do e-mail.")
                    else:
                        st.error("Erro na geração do PDF.")

def tela_aceite_aluno(token):
    st.set_page_config(page_title="Assinatura Digital", layout="centered")
    
    contrato_data = get_contrato_by_token(token)
    
    if not contrato_data:
        st.error("🚫 Link inválido ou expirado.")
        st.stop()
        
    contrato = contrato_data
    aluno = contrato_data['alunos'] # Supabase traz o join
    
    if contrato['status'] == 'assinado':
        st.info(f"✅ Este contrato já foi assinado em {contrato.get('data_aceite')}.")
        return

    st.title("Documento Pendente de Assinatura")
    st.markdown(f"Olá, **{aluno['nome_completo']}**.")
    st.write("Por favor, revise os termos do contrato enviado para o seu e-mail e confirme abaixo.")
    
    st.info("ℹ️ O PDF do contrato foi enviado em anexo no e-mail de notificação.")

    st.divider()
    st.subheader("✍️ Assinatura Digital")
    
    with st.form("form_aceite_digital"):
        st.write("Para validar sua assinatura, confirme seus dados cadastrais:")
        
        col_a1, col_a2 = st.columns(2)
        nome_input = col_a1.text_input("Seu Nome Completo")
        cpf_input = col_a2.text_input("Seu CPF (apenas números)")
        
        st.markdown("<br>", unsafe_allow_html=True)
        check_termos = st.checkbox("Declaro que li o contrato, concordo com todas as cláusulas e autorizo a assinatura digital.")
        
        btn_assinar = st.form_submit_button("✅ ASSINAR CONTRATO")
        
        if btn_assinar:
            # Validações de Segurança
            cpf_real = aluno['cpf']
            cpf_digitado = ''.join(filter(str.isdigit, cpf_input))
            
            if cpf_digitado != cpf_real:
                st.error("CPF incorreto. A assinatura só pode ser realizada pelo titular do contrato.")
            elif nome_input.lower().strip() != aluno['nome_completo'].lower().strip():
                st.warning("O nome digitado não confere exatamente com o cadastro. Verifique acentos ou espaços.")
            elif not check_termos:
                st.error("Você precisa marcar a caixa concordando com os termos.")
            else:
                # PROCESSO DE ASSINATURA E CARIMBO
                with st.spinner("Registrando assinatura na Blockchain (simulado) e aplicando carimbo..."):
                    
                    # 1. Dados do Carimbo
                    fuso = pytz.timezone('America/Sao_Paulo')
                    agora = datetime.now(fuso)
                    ip = "IP_DO_CLIENTE" # Streamlit Cloud nem sempre passa o IP real, usamos placeholder ou headers
                    try:
                        ip = st.context.headers.get("X-Forwarded-For", "0.0.0.0")
                    except:
                        pass
                    
                    # Gerar Hash Único
                    raw_data = f"{contrato['id']}|{agora}|{cpf_real}"
                    hash_ass = hashlib.sha256(raw_data.encode()).hexdigest().upper()
                    
                    link_validacao = f"https://SEU-APP.streamlit.app/?token={token}"
                    
                    # Texto Exato solicitado
                    texto_carimbo = f"""ACEITE DIGITAL REALIZADO
Data/Hora: {agora.strftime('%d/%m/%Y às %H:%M:%S')} (GMT-3)
Nome: {aluno['nome_completo']}
CPF: {cpf_real}
E-mail: {aluno['email']}
IP: {ip}
Link: {link_validacao}
Hash: {hash_ass}"""

                    # 2. Aplicar Carimbo no PDF
                    caminho_original = contrato['caminho_arquivo']
                    novo_caminho = aplicar_carimbo_digital(caminho_original, texto_carimbo)
                    
                    if novo_caminho:
                        # 3. Atualizar Banco de Dados
                        registrar_aceite(contrato['id'], {
                            "status": "assinado",
                            "data_aceite": agora.isoformat(),
                            "ip_aceite": ip,
                            "hash_aceite": hash_ass,
                            "recibo_aceite_texto": texto_carimbo,
                            "caminho_arquivo": novo_caminho # Atualiza para o PDF assinado
                        })
                        
                        st.balloons()
                        st.success("Contrato assinado com sucesso! Uma cópia autenticada foi salva.")
                        st.code(texto_carimbo, language="text")
                    else:
                        st.error("Erro técnico ao aplicar assinatura no documento.")
