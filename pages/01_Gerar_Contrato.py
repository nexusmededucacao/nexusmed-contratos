import streamlit as st
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
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
    
    # Inicializa variáveis de sessão
    if "step" not in st.session_state: st.session_state.step = 1
    if "form_data" not in st.session_state: st.session_state.form_data = {}

    # --- PASSO 1: SELEÇÃO DE ALUNO ---
    if st.session_state.step == 1:
        st.subheader("Etapa 1: Selecionar Aluno")
        busca = st.text_input("Buscar Aluno por Nome ou CPF", placeholder="Digite...")
        
        if busca:
            # Busca Híbrida
            if any(char.isdigit() for char in busca):
                alunos = AlunoRepository.buscar_por_cpf(busca)
                if not alunos: alunos = AlunoRepository.filtrar_por_nome(busca)
            else:
                alunos = AlunoRepository.filtrar_por_nome(busca)

            if alunos:
                st.success(f"{len(alunos)} aluno(s) encontrado(s).")
                for a in alunos:
                    if not isinstance(a, dict): continue
                    
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{a.get('nome_completo')}**")
                        c1.caption(f"CPF: {format_cpf(a.get('cpf'))} | Email: {a.get('email')}")
                        
                        if c2.button("Selecionar", key=f"sel_{a['id']}"):
                            st.session_state.form_data['aluno'] = a
                            st.session_state.step = 2
                            st.rerun()
            else:
                st.warning("Nenhum aluno encontrado.")
                
        st.info("Dica: Se não encontrar, vá em 'Gestão de Alunos' para cadastrar.")

    # --- PASSO 2: CURSO E TURMA ---
    elif st.session_state.step == 2:
        st.subheader("Etapa 2: Curso e Turma")
        aluno = st.session_state.form_data.get('aluno', {})
        st.write(f"👤 Aluno: **{aluno.get('nome_completo')}**")
        
        cursos = CursoRepository.listar_todos_com_turmas()
        if not cursos:
            st.error("Nenhum curso cadastrado.")
            st.stop()
            
        map_cursos = {c['nome']: c for c in cursos}
        sel_curso = st.selectbox("Selecione o Curso", [""] + list(map_cursos.keys()))
        
        if sel_curso:
            curso_dados = map_cursos[sel_curso]
            turmas = curso_dados.get('turmas', [])
            
            if turmas:
                map_turmas = {f"{t['codigo_turma']} ({t.get('formato','-')})": t for t in turmas}
                sel_turma = st.selectbox("Selecione a Turma", list(map_turmas.keys()))
                
                if st.button("Confirmar e Avançar"):
                    st.session_state.form_data['curso'] = curso_dados
                    st.session_state.form_data['turma'] = map_turmas[sel_turma]
                    st.session_state.step = 3
                    st.rerun()
            else:
                st.warning("Curso sem turmas abertas.")
        
        if st.button("Voltar"):
            st.session_state.step = 1
            st.rerun()

    # --- PASSO 3: FINANCEIRO ---
    elif st.session_state.step == 3:
        st.subheader("Etapa 3: Financeiro")
        
        # 1. VALORES DO CURSO
        curso = st.session_state.form_data['curso']
        valor_bruto = float(curso.get('valor_bruto', 0))
        valor_material_calc = valor_bruto * 0.30
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Valor Curso (Bruto)", format_currency(valor_bruto))
        c2.metric("Material Incluso (30%)", format_currency(valor_material_calc))
        
        percent_desc = c3.number_input("Desconto (%)", 0.0, 100.0, 0.0, step=1.0)
        valor_final = valor_bruto * (1 - (percent_desc/100))
        
        st.markdown(f"""
        <div style="background-color: #dcfce7; padding: 15px; border-radius: 8px; border: 1px solid #22c55e; margin-bottom: 20px;">
            <h3 style="margin:0; color: #14532d;">Valor Final: {format_currency(valor_final)}</h3>
            <small style="color: #166534;">Este é o valor total a ser pago pelo aluno.</small>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # 2. ENTRADA (LÓGICA AUTOMÁTICA RECUPERADA)
        st.markdown("#### 1. Entrada")
        ce1, ce2 = st.columns([2, 1])
        v_entrada_total = ce1.number_input("Valor Total da Entrada", min_value=0.0, max_value=valor_final, value=0.0, step=50.0)
        q_entrada = ce2.selectbox("Parcelas Entrada", [1, 2, 3])
        
        lista_entrada = []
        opcoes_pagamento = ["PIX", "Cartão de Crédito", "Boleto", "Dinheiro", "Cartão de Débito"]

        if v_entrada_total > 0:
            st.caption("Detalhamento da Entrada:")
            
            # --- Parcela 1 (Mestre) ---
            with st.container(border=True):
                # Título fora da coluna para alinhar
                st.markdown("**1ª Parcela**")
                c_ep1, c_ep2, c_ep3 = st.columns(3)
                
                v_sugestao = v_entrada_total / q_entrada
                
                # Inputs da 1ª Parcela
                v_p1 = c_ep1.number_input("Valor", value=v_sugestao, step=10.0, key="v_e1")
                d_p1 = c_ep2.date_input("Vencimento", value=date.today(), key="d_e1")
                f_p1 = c_ep3.selectbox("Forma", opcoes_pagamento, key="f_e1")
                
                lista_entrada.append({"n": 1, "vencimento": d_p1, "valor": v_p1, "forma": f_p1})
                
            # --- Parcelas Seguintes (Escravas da 1ª) ---
            resto = v_entrada_total - v_p1
            
            if q_entrada > 1:
                qtd_restante = q_entrada - 1
                val_restante_base = resto / qtd_restante if resto > 0 else 0
                
                for i in range(qtd_restante):
                    n_parc = i + 2
                    
                    with st.container(border=True):
                        st.markdown(f"**{n_parc}ª Parcela**")
                        col_a, col_b, col_c = st.columns(3)
                        
                        # TRUQUE DO KEY: 
                        # O 'key' depende do valor/data da 1ª parcela. 
                        # Se a 1ª mudar, esse campo reseta e recalcula.
                        key_val = f"v_e{n_parc}_{v_p1}_{v_entrada_total}" 
                        key_date = f"d_e{n_parc}_{d_p1}"
                        key_form = f"f_e{n_parc}_{f_p1}"

                        # Valor (Calculado mas Editável)
                        val_real = col_a.number_input("Valor", value=val_restante_base, step=10.0, key=key_val)
                        
                        # Data (Calculada +30 dias, mas Editável)
                        d_sugestao = d_p1 + relativedelta(months=i+1)
                        d_real = col_b.date_input("Vencimento", value=d_sugestao, key=key_date)
                        
                        # Forma (Copia a anterior, mas Editável)
                        idx_forma = opcoes_pagamento.index(f_p1) if f_p1 in opcoes_pagamento else 0
                        f_real = col_c.selectbox("Forma", opcoes_pagamento, index=idx_forma, key=key_form)
                        
                        lista_entrada.append({
                            "n": n_parc, 
                            "vencimento": d_real, 
                            "valor": val_real, 
                            "forma": f_real 
                        })
            
            # Validação
            soma_ent = sum(p['valor'] for p in lista_entrada)
            if abs(soma_ent - v_entrada_total) > 0.10:
                st.warning(f"⚠️ A soma das parcelas (R$ {soma_ent:.2f}) difere do Total da Entrada.")

        # 3. SALDO RESTANTE
        saldo = valor_final - v_entrada_total
        lista_saldo = []
        
        st.markdown("---")
        st.markdown(f"#### 2. Saldo a Parcelar: {format_currency(saldo)}")
        
        if saldo > 0.01:
            cs1, cs2, cs3 = st.columns(3)
            q_saldo = cs1.number_input("Qtd Parcelas (Máx 36)", min_value=1, max_value=36, value=1)
            d_saldo_ini = cs2.date_input("1º Vencimento Saldo", value=date.today() + relativedelta(months=1))
            f_saldo = cs3.selectbox("Forma de Pagamento Saldo", ["Boleto", "Cartão de Crédito", "PIX"], key="forma_saldo")
            
            # Gerar Lista Automática de Parcelas
            valor_parc_saldo = saldo / q_saldo
            
            with st.expander(f"👁️ Visualizar Parcelas ({q_saldo}x de {format_currency(valor_parc_saldo)})"):
                for i in range(q_saldo):
                    d_venc = d_saldo_ini + relativedelta(months=i)
                    lista_saldo.append({
                        "n": i+1,
                        "vencimento": d_venc,
                        "valor": valor_parc_saldo,
                        "forma": f_saldo
                    })
                    st.write(f"Parcela {i+1}: {d_venc.strftime('%d/%m/%Y')} - {format_currency(valor_parc_saldo)} ({f_saldo})")
        
        else:
            st.success("O contrato foi quitado na entrada!")

        # 4. AÇÃO FINAL
        st.divider()
        cb1, cb2 = st.columns([1, 4])
        
        if cb1.button("Voltar"):
            st.session_state.step = 2
            st.rerun()
            
        if cb2.button("🚀 Gerar Contrato e Link de Assinatura", type="primary", use_container_width=True):
            try:
                # Serialização JSON
                detalhes_entrada_serial = [
                    {**p, "vencimento": p["vencimento"].isoformat()} for p in lista_entrada
                ]
                detalhes_saldo_serial = [
                    {**p, "vencimento": p["vencimento"].isoformat()} for p in lista_saldo
                ]

                novo_contrato = {
                    "aluno_id": st.session_state.form_data['aluno']['id'],
                    "turma_id": st.session_state.form_data['turma']['id'],
                    "valor_curso": valor_bruto,
                    "percentual_desconto": percent_desc,
                    "valor_final": valor_final,
                    "valor_material": valor_material_calc,
                    
                    # Entrada
                    "entrada_valor": v_entrada_total,
                    "entrada_detalhes": detalhes_entrada_serial,
                    
                    # Saldo
                    "saldo_valor": saldo,
                    "saldo_qtd_parcelas": len(lista_saldo),
                    "saldo_forma_pagamento": f_saldo if saldo > 0 else "À Vista",
                    "saldo_detalhes": detalhes_saldo_serial,
                    
                    "token_acesso": str(uuid.uuid4()),
                    "status": "Pendente",
                    "created_at": datetime.now().isoformat()
                }
                
                ContratoRepository.criar_contrato(novo_contrato)
                
                st.session_state.ultimo_token = novo_contrato["token_acesso"]
                st.session_state.step = 4
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro ao salvar contrato: {e}")

    # --- PASSO 4: SUCESSO ---
    elif st.session_state.step == 4:
        st.balloons()
        st.success("Contrato Criado com Sucesso!")
        
        token = st.session_state.get('ultimo_token', '')
        link = f"https://nexusmed-portal.streamlit.app/Assinatura?token={token}"
        
        st.markdown("### 🔗 Link para o Aluno")
        st.code(link, language="text")
        st.info("Envie este link para o aluno assinar digitalmente.")
        
        if st.button("Criar Novo Contrato"):
            st.session_state.step = 1
            st.session_state.form_data = {}
            st.rerun()

if __name__ == "__main__":
    main()
