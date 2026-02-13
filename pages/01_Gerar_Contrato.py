import streamlit as st
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# --- IMPORTAÇÕES DO PROJETO ---
from src.database.repo_alunos import AlunoRepository
from src.database.repo_cursos import CursoRepository
from src.database.repo_contratos import ContratoRepository
from src.utils.formatters import format_currency, format_cpf, format_date_br
from src.document_engine.processor import ContractProcessor
from src.document_engine.pdf_converter import PDFManager
from src.utils.storage import StorageService
from src.utils.email_sender import enviar_email_contrato

# URL de Produção
BASE_URL = "https://nexusmed-contratos.streamlit.app" 

def obter_mes_extenso(dt):
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    return meses[dt.month]

# Proteção de Acesso
if not st.session_state.get("authenticated"):
    st.error("Por favor, faça login para acessar esta página.")
    st.stop()

# --- CALLBACK PARA RECÁLCULO DA ENTRADA (Lógica original restaurada) ---
def recalcular_parcelas_entrada():
    total = st.session_state.get('v_entrada_total_safe', 0.0)
    qtd = st.session_state.get('q_entrada_safe', 1)
    soma_acumulada = 0.0
    
    for i in range(qtd):
        key = f"input_ent_{i}"
        if key in st.session_state:
            val_atual = st.session_state[key]
            soma_acumulada += val_atual
            # Lógica de distribuição do saldo restante
            if i < qtd - 1:
                saldo_restante = total - soma_acumulada
                parcelas_restantes = qtd - (i + 1)
                if parcelas_restantes > 0:
                    valor_prox = round(saldo_restante / parcelas_restantes, 2)
                    for j in range(i + 1, qtd):
                        key_prox = f"input_ent_{j}"
                        # A última parcela pega o resto exato para bater o centavo
                        val_prox_final = round(total - (soma_acumulada + (valor_prox * (parcelas_restantes - 1))), 2) if j == qtd - 1 else valor_prox
                        st.session_state[key_prox] = max(0.0, val_prox_final)
                    break

def main():
    st.title("📄 Gerador de Contratos")
    
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}
    if "url_pdf_oficial" not in st.session_state: st.session_state.url_pdf_oficial = None

    # --- PASSO 1: SELECIONAR ALUNO ---
    if st.session_state.step == 1:
        st.subheader("Etapa 1: Selecionar Aluno")
        busca = st.text_input("Buscar Aluno por Nome ou CPF")
        if busca:
            alunos = AlunoRepository.buscar_por_cpf(busca) if any(c.isdigit() for c in busca) else AlunoRepository.filtrar_por_nome(busca)
            if alunos:
                for a in (alunos if isinstance(alunos, list) else [alunos]):
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{a.get('nome_completo')}**")
                        if c2.button("Selecionar", key=f"sel_{a['id']}"):
                            st.session_state.form_data['aluno'] = a
                            st.session_state.step = 2
                            st.rerun()

    # --- PASSO 2: CURSO E TURMA ---
    elif st.session_state.step == 2:
        st.subheader("Etapa 2: Curso e Turma")
        aluno = st.session_state.form_data.get('aluno', {})
        cursos = CursoRepository.listar_todos_com_turmas()
        map_cursos = {c['nome']: c for c in cursos}
        sel_curso = st.selectbox("Selecione o Curso", [""] + list(map_cursos.keys()))
        if sel_curso:
            curso_dados = map_cursos[sel_curso]
            turmas = curso_dados.get('turmas', [])
            if turmas:
                map_turmas = {f"{t['codigo_turma']} ({t.get('formato','-')})": t for t in turmas}
                sel_turma = st.selectbox("Selecione a Turma", list(map_turmas.keys()))
                if st.button("Avançar"):
                    st.session_state.form_data['curso'] = curso_dados
                    st.session_state.form_data['turma'] = map_turmas[sel_turma]
                    st.session_state.step = 3
                    st.rerun()

    # --- PASSO 3: FINANCEIRO E GERAÇÃO ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        dados_turma = st.session_state.form_data['turma']
        
        # 1. CÁLCULOS BASE
        valor_bruto = float(curso.get('valor_bruto', 0))
        valor_material_calc = round(valor_bruto * 0.30, 2)
        
        st.markdown(f"**Valor Bruto do Curso:** {format_currency(valor_bruto)}")
        
        percent_desc = st.number_input("Desconto Comercial (%)", 0.0, 100.0, 0.0, step=0.5)
        
        # Variáveis definidas aqui para uso em todo o escopo
        v_desconto = round(valor_bruto * (percent_desc / 100), 2)
        v_final = round(valor_bruto - v_desconto, 2)
        
        st.success(f"### Valor Final: {format_currency(v_final)}")

        # 2. CONFIGURAÇÃO DE ENTRADA
        st.markdown("#### 1. Entrada")
        c_ent1, c_ent2 = st.columns(2)
        v_entrada_total = c_ent1.number_input("Valor Total Entrada", 0.0, v_final, 0.0, key="v_entrada_total_safe")
        q_entrada = c_ent2.selectbox("Qtd. Parcelas Entrada", [1, 2, 3], key="q_entrada_safe")
        
        # Inicializador dos inputs de entrada (para distribuir valor automaticamente ao mudar total)
        if "last_v_entrada" not in st.session_state or st.session_state.last_v_entrada != v_entrada_total or st.session_state.last_q_entrada != q_entrada:
            st.session_state.last_v_entrada = v_entrada_total
            st.session_state.last_q_entrada = q_entrada
            v_base = round(v_entrada_total / q_entrada, 2) if q_entrada > 0 else 0
            for k in range(q_entrada):
                key_p = f"input_ent_{k}"
                # Ajuste de centavos na última parcela
                val_calc = round(v_entrada_total - (v_base * (q_entrada - 1)), 2) if k == q_entrada - 1 else v_base
                st.session_state[key_p] = max(0.0, val_calc)

        lista_entrada = []
        opcoes_pagto = ["PIX", "Cartão de Crédito", "Boleto", "Transferência"]
        
        if v_entrada_total > 0:
            for i in range(q_entrada):
                cc1, cc2, cc3 = st.columns(3)
                key_val = f"input_ent_{i}"
                
                # Input com callback de recálculo
                v_p = cc1.number_input(f"Valor P{i+1}", 0.0, float(v_final), key=key_val, on_change=recalcular_parcelas_entrada)
                d_p = cc2.date_input(f"Vencimento P{i+1}", date.today() + relativedelta(days=i*30), key=f"dent_{i}")
                f_p = cc3.selectbox(f"Forma P{i+1}", opcoes_pagto, key=f"fent_{i}")
                
                # Guarda dados estruturados
                lista_entrada.append({
                    "numero": i+1, 
                    "data": d_p.strftime("%d/%m/%Y"), 
                    "valor": format_currency(v_p), 
                    "forma": f_p, 
                    "valor_num": v_p
                })

        # 3. CONFIGURAÇÃO DE SALDO
        saldo_restante = round(v_final - v_entrada_total, 2)
        st.markdown(f"#### 2. Saldo: {format_currency(saldo_restante)}")
        
        lista_saldo = []
        if saldo_restante > 0:
            cs1, cs2, cs3 = st.columns(3)
            q_saldo = cs1.number_input("Qtd Parcelas Saldo", 1, 36, 12)
            d_saldo_ini = cs2.date_input("1º Vencimento Saldo", date.today() + relativedelta(months=1))
            f_saldo = cs3.selectbox("Forma Saldo", ["Boleto", "Cartão de Crédito", "PIX"])
            
            v_base_saldo = round(saldo_restante / q_saldo, 2)
            acc_saldo = 0
            
            for i in range(q_saldo):
                # Ajuste de centavos na última parcela
                vp = round(saldo_restante - acc_saldo, 2) if i == q_saldo - 1 else v_base_saldo
                acc_saldo += vp
                dt = d_saldo_ini + relativedelta(months=i)
                
                lista_saldo.append({
                    "Parcela": f"{i+1}/{q_saldo}", 
                    "Vencimento": dt.strftime("%d/%m/%Y"), 
                    "Valor": format_currency(vp), 
                    "Forma": f_saldo, 
                    "valor_num": vp
                })
            
            with st.expander("Ver parcelas do saldo"):
                st.dataframe(lista_saldo)

        # VALIDAÇÃO ANTES DE GERAR
        soma_ent = sum(p['valor_num'] for p in lista_entrada)
        soma_sal = sum(p['valor_num'] for p in lista_saldo)
        total_calculado = soma_ent + soma_sal
        
        valido = abs(total_calculado - v_final) < 0.1 # Margem de erro de centavos
        
        if not valido:
            st.error(f"A soma das parcelas ({format_currency(total_calculado)}) não bate com o Valor Final ({format_currency(v_final)}). Ajuste a entrada.")
        
        if st.button("🚀 Gerar e Sincronizar com Servidor", type="primary", disabled=not valido, use_container_width=True):
            with st.spinner("Processando..."):
                try:
                    token = str(uuid.uuid4())
                    agora = datetime.now()
                    
                    # Helper para evitar None
                    def fmt(val, default=""): return str(val) if val is not None and str(val).strip() != "" else default

                    # === MONTAGEM DO PDF (CHAVES CORRIGIDAS BASEADO NO SEU PDF BOM) ===
                    ctx_doc = {
                        # Pessoais
                        'nome': fmt(aluno.get('nome_completo')).upper(),
                        'cpf': format_cpf(fmt(aluno.get('cpf'))),
                        'rg': fmt(aluno.get('rg'), "___________"),
                        'orgao_emissor': fmt(aluno.get('orgao_emissor'), "SSP/RS"),
                        'data_nascimento': format_date_br(aluno.get('data_nascimento')),
                        'estado_civil': fmt(aluno.get('estado_civil'), "Solteiro(a)"),
                        'nacionalidade': fmt(aluno.get('nacionalidade'), "Brasileira"),
                        'email': fmt(aluno.get('email')),
                        'telefone': fmt(aluno.get('telefone')),
                        'celular': fmt(aluno.get('telefone')), # Backup
                        
                        # Endereço (Correção Crítica: logradouro e uf)
                        'logradouro': fmt(aluno.get('logradouro')), 
                        'numero': fmt(aluno.get('numero')),
                        'complemento': fmt(aluno.get('complemento')),
                        'bairro': fmt(aluno.get('bairro')),
                        'cidade': fmt(aluno.get('cidade')),
                        'uf': fmt(aluno.get('uf')), 
                        'cep': fmt(aluno.get('cep')),
                        'crm': fmt(aluno.get('crm'), "___________"),
                        'area_formacao': fmt(aluno.get('especialidade'), "Médica"),
                        
                        # Curso
                        'curso': fmt(curso.get('nome')),
                        'pos_graduacao': fmt(curso.get('nome')), # Backup
                        'codigo_turma': fmt(dados_turma.get('codigo_turma')),
                        'turma': fmt(dados_turma.get('codigo_turma')), # Backup
                        'formato_curso': fmt(dados_turma.get('formato'), "Digital"),
                        'atendimento': fmt(dados_turma.get('atendimento'), "Sim"),
                        
                        # Financeiro (Correção Crítica: valor_curso)
                        'valor_curso': format_currency(valor_bruto).replace("R$", "").strip(),
                        'valor_bruto': format_currency(valor_bruto).replace("R$", "").strip(), # Backup
                        'percentual_desconto': str(percentual_desconto).replace(".", ","),
                        'valor_desconto': format_currency(v_desconto).replace("R$", "").strip(),
                        'valor_final': format_currency(v_final).replace("R$", "").strip(),
                        'valor_material': format_currency(valor_material_calc).replace("R$", "").strip(),
                        'bolsista': "SIM" if percent_desc > 0 else "NÃO",
                        
                        # Datas
                        'dia': str(agora.day), 
                        'mês': obter_mes_extenso(agora).lower(), 
                        'ano': str(agora.year),
                        'data_atual': format_date_br(agora)
                    }

                    # Tabelas Financeiras (Agora preenchidas corretamente)
                    tbl_ent_pdf = [{"n": str(p["numero"]), "vencimento": p["data"], "valor": p["valor"], "forma": p["forma"]} for p in lista_entrada]
                    tbl_sal_pdf = [{"n": p["Parcela"], "vencimento": p["Vencimento"], "valor": p["Valor"], "forma": p["Forma"]} for p in lista_saldo]

                    # Geração Física
                    processor = ContractProcessor("assets/modelo_contrato_V2.docx")
                    docx_buffer = processor.generate_docx(ctx_doc, tbl_ent_pdf, tbl_sal_pdf) 
                    pdf_buffer = PDFManager.convert_docx_to_pdf(docx_buffer)
                    
                    # Upload
                    url_pdf, erro_upload = StorageService.upload_minuta(pdf_buffer, aluno['nome_completo'], curso['nome'])
                    if erro_upload: raise Exception(f"Erro Upload: {erro_upload}")

                    # Banco de Dados (Correção Crítica: Tipos e Campos Nulos)
                    forma_ent_db = lista_entrada[0]['forma'] if lista_entrada else "N/A"
                    forma_sal_db = f_saldo if 'f_saldo' in locals() else "N/A"

                    dados_db = {
                        "aluno_id": aluno['id'],
                        "turma_id": int(dados_turma['id']),
                        "valor_curso": float(valor_bruto),
                        "valor_desconto": float(v_desconto),
                        "percentual_desconto": float(percent_desc),
                        "valor_final": float(v_final),
                        "valor_material": float(valor_material_calc),
                        "bolsista": True if percent_desc > 0 else False,
                        "atendimento_paciente": True if dados_turma.get('atendimento') == 'Sim' else False,
                        "entrada_valor": float(v_entrada_total),
                        "entrada_qtd_parcelas": int(q_entrada),
                        "saldo_valor": float(saldo_restante),
                        "saldo_qtd_parcelas": int(q_saldo),
                        "token_acesso": token,
                        "status": "Pendente",
                        "caminho_arquivo": url_pdf,
                        "formato_curso": dados_turma.get('formato', 'Digital'),
                        "entrada_forma_pagamento": forma_ent_db,
                        "saldo_forma_pagamento": forma_sal_db,
                        "created_at": agora.isoformat()
                    }
                    
                    res = ContratoRepository.criar_contrato(dados_db)
                    if res and isinstance(res, dict) and 'error' in res: raise Exception(res['error'])

                    st.session_state.url_pdf_oficial = url_pdf
                    st.session_state.ultimo_token = token
                    st.session_state.step = 4
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Erro Crítico: {e}")

    # --- PASSO 4: AUDITORIA E ENVIO ---
    elif st.session_state.step == 4:
        st.success("✅ Contrato Gerado e Salvo!")
        url_oficial = st.session_state.get('url_pdf_oficial')
        token = st.session_state.ultimo_token
        aluno = st.session_state.form_data['aluno']
        curso = st.session_state.form_data['curso']
        
        link_assinatura = f"{BASE_URL}/Assinatura?token={token}"

        with st.container(border=True):
            st.info("Arquivo oficial (Fonte da Verdade) disponível para auditoria:")
            c1, c2 = st.columns(2)
            
            if url_oficial:
                c1.link_button("📥 Baixar PDF Oficial", url_oficial, use_container_width=True)
            
            if c2.button("📧 Enviar para Aluno", type="primary", use_container_width=True):
                with st.spinner("Enviando..."):
                    try:
                        sucesso = enviar_email_contrato(
                            aluno['email'], 
                            aluno['nome_completo'], 
                            link_assinatura, 
                            curso['nome']
                        )
                        if sucesso:
                            st.toast("E-mail enviado!", icon="✅")
                            st.success(f"Link enviado para: {aluno['email']}")
                    except Exception as e: 
                        st.error(f"Erro no envio: {e}")

            st.divider()
            st.text("Link manual de assinatura:")
            st.code(link_assinatura, language="text")

        if st.button("⬅️ Iniciar Novo Contrato"):
            st.session_state.step = 1
            st.session_state.url_pdf_oficial = None
            st.rerun()

if __name__ == "__main__":
    main()
