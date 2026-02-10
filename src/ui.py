import streamlit as st
import pandas as pd
import hashlib
import pytz
import time
from datetime import datetime, date
from datetime import timedelta
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
    
    if st.button("Buscar Aluno", key="btn_buscar_cpf"):
         with st.spinner("Buscando..."):
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

            submitted = st.form_submit_button("💾 Salvar Cadastro do Aluno")

            if submitted:
                # 1. Validação básica de campos obrigatórios
                if not nome or not cpf:
                    st.error("Erro: Nome e CPF são obrigatórios.")
                else:
                    payload = {
                        "nome_completo": nome, "cpf": cpf, "rg": rg, "email": email,
                        "telefone": telefone, "data_nascimento": str(data_nasc),
                        "nacionalidade": nacionalidade, "estado_civil": estado_civil,
                        "logradouro": logradouro, "numero": numero, "complemento": complemento,
                        "bairro": bairro, "cidade": cidade, "uf": uf, "cep": cep,
                        "crm": crm, "area_formacao": area
                    }
                    
                    # 2. Chama o banco e espera o retorno
                    resultado = upsert_aluno(payload)
                    
                    # 3. Verifica se salvou de verdade
                    if resultado:
                        st.toast("✅ Aluno salvo com sucesso!", icon="🎉")
                        st.success("Dados salvos! Recarregando...")
                        
                        # Remove dados da sessão para limpar o formulário
                        if 'dados_aluno_atual' in st.session_state:
                            del st.session_state['dados_aluno_atual']
                        
                        # 4. PAUSA IMPORTANTE: Espera 2 segundos para você ver a mensagem
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Erro ao salvar! Verifique se o CPF já existe ou se o banco está conectado.")

# --- SUBSTITUIR A FUNÇÃO tela_novo_contrato INTEIRA POR ESTA ---
def tela_novo_contrato():
    st.header("🔥🔥🔥 VERSÃO NOVA ATIVADA 🔥🔥🔥")

    # --- SELEÇÃO DE ALUNO E CURSO ---
    col_sel1, col_sel2 = st.columns(2)
    cpf_aluno = col_sel1.text_input("Passo 1: Digite CPF do Aluno", placeholder="Apenas números")
    
    aluno = None
    if cpf_aluno:
        aluno = get_aluno_by_cpf(cpf_aluno)
        if aluno:
            st.success(f"🎓 Aluno: **{aluno['nome_completo']}**")
        else:
            st.warning("Aluno não encontrado. Cadastre-o primeiro.")
            st.stop()
            
    cursos = get_cursos()
    nome_curso = col_sel2.selectbox("Passo 2: Selecione o Curso", [c['nome'] for c in cursos] if cursos else [])
    
    curso_sel = next((c for c in cursos if c['nome'] == nome_curso), None)
    turma_sel = None
    
    if curso_sel:
        turmas = get_turmas_by_curso(curso_sel['id'])
        if turmas:
            cod_turma = st.selectbox("Passo 3: Selecione a Turma", [t['codigo_turma'] for t in turmas])
            turma_sel = next(t for t in turmas if t['codigo_turma'] == cod_turma)
        else:
            st.error("Curso sem turmas cadastradas.")
            st.stop()

    if not (aluno and curso_sel and turma_sel):
        st.info("Selecione aluno, curso e turma para prosseguir.")
        st.stop()

    st.markdown("---")
    st.subheader("💰 Configuração Financeira (Cálculos Reais)")

    # --- BLOCO 1: VALOR E DESCONTO ---
    # Removemos o st.form para permitir calculo em tempo real
    valor_base = float(curso_sel['valor_bruto'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Valor Tabela", f"R$ {valor_base:,.2f}")
    
    # Input do desconto com atualização imediata
    percentual = c2.number_input("% Desconto", 0.0, 100.0, 0.0, step=0.5)
    valor_desconto = valor_base * (percentual / 100)
    
    valor_final = valor_base - valor_desconto
    c3.metric("Valor Negociado (Final)", f"R$ {valor_final:,.2f}", delta=f"- R$ {valor_desconto:,.2f}")

    st.markdown("---")
    
    # --- BLOCO 2: ENTRADA ---
    st.write("### 1. Entrada")
    col_e1, col_e2, col_e3 = st.columns(3)
    
    entrada_val = col_e1.number_input("Valor da Entrada (R$)", 0.0, valor_final, 0.0, step=100.0)
    entrada_qtd = col_e2.number_input("Qtd Parcelas Entrada", 1, 12, 1)
    entrada_forma = col_e3.selectbox("Forma Pagto Entrada", ["PIX", "Boleto", "Cartão de Crédito", "Dinheiro"])
    
    # Datas dinâmicas da entrada
    datas_entrada = []
    if entrada_qtd > 0:
        st.caption("📅 Vencimentos da Entrada:")
        cols_datas = st.columns(min(entrada_qtd, 4)) # Mostra até 4 por linha
        for i in range(entrada_qtd):
            # Lógica para quebra de linha visual se tiver muitas parcelas
            with cols_datas[i % 4]:
                dt = st.date_input(f"Parc. {i+1}", value=date.today() + timedelta(days=i*30), key=f"ent_dt_{i}")
                datas_entrada.append(dt)

    # --- BLOCO 3: SALDO ---
    st.markdown("---")
    st.write("### 2. Saldo Remanescente")
    
    saldo_restante = valor_final - entrada_val
    
    # Validação visual
    if saldo_restante < 0:
        st.error(f"Erro: A entrada (R$ {entrada_val}) é maior que o valor final (R$ {valor_final})!")
        st.stop()
    
    st.info(f"💵 Saldo a Parcelar: **R$ {saldo_restante:,.2f}**")
    
    col_s1, col_s2, col_s3 = st.columns(3)
    saldo_qtd = col_s1.number_input("Nº Parcelas do Saldo", 1, 60, 12)
    primeiro_venc_saldo = col_s2.date_input("1º Vencimento Saldo", value=date.today() + timedelta(days=30))
    saldo_forma = col_s3.selectbox("Forma Pagto Saldo", ["Boleto", "Cartão de Crédito Recorrente", "Cheque"])

    # Simulação da Tabela de Parcelas
    if saldo_restante > 0:
        valor_parcela_saldo = saldo_restante / saldo_qtd
        lista_parcelas = []
        for i in range(saldo_qtd):
            venc = primeiro_venc_saldo + timedelta(days=i*30)
            lista_parcelas.append({
                "Parcela": f"{i+1}/{saldo_qtd}",
                "Vencimento": venc.strftime("%d/%m/%Y"),
                "Valor": f"R$ {valor_parcela_saldo:,.2f}",
                "Forma": saldo_forma
            })
        
        with st.expander("🔎 Ver Detalhes das Parcelas do Saldo", expanded=False):
            st.dataframe(pd.DataFrame(lista_parcelas), use_container_width=True)

    # --- BLOCO 4: CHECKBOXES E OPÇÕES ---
    st.markdown("---")
    col_check1, col_check2 = st.columns(2)
    is_bolsista = col_check1.radio("É Bolsista?", ["Não", "Sim"], horizontal=True)
    is_paciente = col_check2.radio("Atendimento a Paciente?", ["Não", "Sim"], horizontal=True)

    # --- BLOCO 5: AÇÃO FINAL ---
    st.markdown("### 🚀 Finalização")
    
    # Variável de controle para não resetar a tela ao clicar nos botões de ação
    if 'contrato_gerado' not in st.session_state:
        st.session_state['contrato_gerado'] = None

    if st.button("💾 Gerar Contrato e Link", type="primary", use_container_width=True):
        if saldo_restante < 0:
            st.error("Valores inconsistentes.")
        else:
            with st.spinner("Criando registro e gerando PDF..."):
                # Prepara dados
                dados_contrato = {
                    "aluno_id": aluno['id'],
                    "turma_id": turma_sel['id'],
                    "valor_curso": valor_base,
                    "percentual_desconto": percentual,
                    "valor_desconto": valor_desconto,
                    "valor_final": valor_final,
                    "valor_material": 0, # Ajustar regra se tiver
                    "entrada_valor": entrada_val,
                    "entrada_qtd_parcelas": entrada_qtd,
                    "entrada_forma_pagamento": entrada_forma,
                    "saldo_valor": saldo_restante,
                    "saldo_qtd_parcelas": saldo_qtd,
                    "saldo_forma_pagamento": saldo_forma,
                    "bolsista": True if is_bolsista == "Sim" else False,
                    "atendimento_paciente": True if is_paciente == "Sim" else False,
                    "formato_curso": turma_sel['formato']
                }
                
                # datas_vencimento simplificado para o PDF (passamos a lista da entrada e inicio do saldo)
                datas_info = {
                    "datas_entrada": [d.strftime("%Y-%m-%d") for d in datas_entrada],
                    "inicio_saldo": primeiro_venc_saldo.strftime("%Y-%m-%d")
                }
                
                # Gera PDF
                caminho_pdf = gerar_contrato_pdf(aluno, turma_sel, curso_sel, dados_contrato, datas_info)
                
                if caminho_pdf:
                    dados_contrato['caminho_arquivo'] = caminho_pdf
                    # Salva no banco
                    novo_contrato = create_contrato(dados_contrato)
                    
                    if novo_contrato:
                        # Salva na sessão para exibir as opções abaixo sem perder estado
                        st.session_state['contrato_gerado'] = {
                            "token": novo_contrato['token_acesso'],
                            "email": aluno['email'],
                            "nome": aluno['nome_completo'],
                            "path": caminho_pdf
                        }
                        st.balloons()
                        st.success("Contrato Gerado com Sucesso!")
                        st.rerun() # Recarrega para mostrar o bloco abaixo
                else:
                    st.error("Falha ao gerar PDF.")

    # --- TELA DE SUCESSO E AÇÕES PÓS-GERAÇÃO ---
    if st.session_state['contrato_gerado']:
        info = st.session_state['contrato_gerado']
        link_unico = f"https://nexusmed-contratos.streamlit.app/?token={info['token']}"
        
        st.divider()
        st.markdown("#### ✅ Contrato Pronto! O que deseja fazer?")
        
        c_link, c_down, c_mail = st.columns([2, 1, 1])
        
        with c_link:
            st.text_input("🔗 Link para o Aluno (WhatsApp):", value=link_unico, read_only=True)
            
        with c_down:
            try:
                with open(info['path'], "rb") as pdf_file:
                    st.download_button(
                        label="📥 Baixar PDF",
                        data=pdf_file,
                        file_name=f"Contrato_{info['nome']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            except:
                st.warning("Arquivo PDF não localizado.")

        with c_mail:
            if st.button("📧 Enviar por E-mail", use_container_width=True):
                with st.spinner("Enviando..."):
                    sucesso = enviar_email(info['email'], info['nome'], link_unico)
                    if sucesso:
                        st.toast("E-mail enviado!", icon="📩")
                    else:
                        st.error("Erro no envio.")
        
        if st.button("🔄 Iniciar Novo Contrato"):
            st.session_state['contrato_gerado'] = None
            st.rerun()

def tela_aceite_aluno(token):
    st.set_page_config(page_title="Assinatura Digital", layout="centered")
    
    contrato_data = get_contrato_by_token(token)
    
    if not contrato_data:
        st.error("🚫 Link inválido ou expirado.")
        st.stop()
        
    contrato = contrato_data
    aluno = contrato_data.get('alunos') or contrato_data.get('aluno')
    
    if not aluno:
        st.error("Erro nos dados do aluno.")
        st.stop()

    if contrato['status'] == 'assinado':
        st.info(f"✅ Este contrato já foi assinado em {contrato.get('data_aceite')}.")
        return

    st.title("Documento Pendente de Assinatura")
    st.markdown(f"Olá, **{aluno['nome_completo']}**.")
    st.write("Por favor, revise os termos do contrato enviado para o seu e-mail e confirme abaixo.")
    
    st.divider()
    st.subheader("✍️ Assinatura Digital")
    
    with st.form("form_aceite_digital"):
        st.write("Para validar sua assinatura, confirme seus dados cadastrais:")
        col_a1, col_a2 = st.columns(2)
        nome_input = col_a1.text_input("Seu Nome Completo")
        cpf_input = col_a2.text_input("Seu CPF (apenas números)")
        
        check_termos = st.checkbox("Declaro que li o contrato e concordo com todas as cláusulas.")
        
        btn_assinar = st.form_submit_button("✅ ASSINAR CONTRATO")
        
        if btn_assinar:
            cpf_real = aluno['cpf']
            cpf_digitado = ''.join(filter(str.isdigit, cpf_input))
            
            if cpf_digitado != cpf_real:
                st.error("CPF incorreto.")
            elif nome_input.lower().strip() != aluno['nome_completo'].lower().strip():
                st.warning("O nome digitado não confere exatamente com o cadastro.")
            elif not check_termos:
                st.error("Você precisa marcar a caixa concordando com os termos.")
            else:
                with st.spinner("Registrando assinatura e carimbando..."):
                    fuso = pytz.timezone('America/Sao_Paulo')
                    agora = datetime.now(fuso)
                    ip = "IP_CLIENTE"
                    try: ip = st.context.headers.get("X-Forwarded-For", "0.0.0.0")
                    except: pass
                    
                    raw_data = f"{contrato['id']}|{agora}|{cpf_real}"
                    hash_ass = hashlib.sha256(raw_data.encode()).hexdigest().upper()
                    
                    link_validacao = f"https://nexusmed-contratos.streamlit.app/?token={token}"
                    
                    texto_carimbo = f"""ACEITE DIGITAL REALIZADO
Data/Hora: {agora.strftime('%d/%m/%Y às %H:%M:%S')} (GMT-3)
Nome: {aluno['nome_completo']}
CPF: {cpf_real}
E-mail: {aluno['email']}
IP: {ip}
Link: {link_validacao}
Hash: {hash_ass}"""

                    caminho_original = contrato['caminho_arquivo']
                    novo_caminho = aplicar_carimbo_digital(caminho_original, texto_carimbo)
                    
                    if novo_caminho:
                        registrar_aceite(contrato['id'], {
                            "status": "assinado",
                            "data_aceite": agora.isoformat(),
                            "ip_aceite": ip,
                            "hash_aceite": hash_ass,
                            "recibo_aceite_texto": texto_carimbo,
                            "caminho_arquivo": novo_caminho
                        })
                        st.balloons()
                        st.success("Contrato assinado com sucesso!")
                        st.code(texto_carimbo, language="text")
                    else:
                        st.error("Erro técnico ao aplicar assinatura.")
