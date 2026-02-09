import streamlit as st
import os
import subprocess
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
from docxtpl import DocxTemplate
from src.db import supabase
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- FUNÇÕES AUXILIARES ---

def format_moeda(valor):
    """Formata float para R$ 1.234,56"""
    if valor is None:
        return "R$ 0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def data_por_extenso(data_obj):
    """Retorna dicionário com dia, mês e ano para o template"""
    # Meses em português
    meses = {
        1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
        5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
        9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
    }
    return {
        "dia": data_obj.strftime("%d"),
        "mês": meses[data_obj.month],
        "ano": data_obj.strftime("%Y"),
        "data_completa": f"{data_obj.day} de {meses[data_obj.month]} de {data_obj.year}"
    }

# --- LÓGICA DE GERAÇÃO DO CONTRATO ---

def gerar_parcelas(valor_total, qtd_parcelas, data_primeiro_vencimento, forma_pagamento):
    """
    Gera a lista de parcelas calculando as datas subsequentes.
    Retorna uma lista de dicionários pronta para o template.
    """
    lista_parcelas = []
    
    # Evita divisão por zero
    if qtd_parcelas <= 0:
        return lista_parcelas
        
    valor_parcela = valor_total / qtd_parcelas
    
    for i in range(qtd_parcelas):
        # Calcula data: Data 1ª parcela + i meses
        data_venc = data_primeiro_vencimento + relativedelta(months=+i)
        
        lista_parcelas.append({
            "numero": f"{i+1:02d}", # 01, 02...
            "data_vencimento": data_venc.strftime("%d/%m/%Y"),
            "valor": format_moeda(valor_parcela),
            "forma_pagamento": forma_pagamento
        })
    
    return lista_parcelas

def gerar_contrato_pdf(aluno, turma, curso, contrato_dados, datas_vencimento):
    """
    1. Prepara o contexto (variáveis).
    2. Renderiza o DOCX.
    3. Converte para PDF (LibreOffice).
    4. Upload para o Supabase Storage.
    5. Retorna a URL pública/assinada do arquivo.
    """
    
    # 1. Preparar Contexto (Mapear Banco -> Template)
    # -----------------------------------------------
    hoje = datetime.now()
    data_extenso = data_por_extenso(hoje)
    
    # Cálculos Financeiros Finais
    val_bruto = float(contrato_dados['valor_curso'])
    val_desc = float(contrato_dados['valor_desconto'])
    val_final = float(contrato_dados['valor_final'])
    val_material = val_bruto * 0.30
    
    # Gerar Listas de Parcelas
    # Entrada
    parcelas_entrada = gerar_parcelas(
        valor_total=float(contrato_dados['entrada_valor']),
        qtd_parcelas=int(contrato_dados['entrada_qtd_parcelas']),
        data_primeiro_vencimento=datas_vencimento['entrada'],
        forma_pagamento=contrato_dados['entrada_forma_pagamento']
    )
    
    # Saldo
    parcelas_saldo = gerar_parcelas(
        valor_total=float(contrato_dados['saldo_valor']),
        qtd_parcelas=int(contrato_dados['saldo_qtd_parcelas']),
        data_primeiro_vencimento=datas_vencimento['saldo'],
        forma_pagamento=contrato_dados['saldo_forma_pagamento']
    )

    context = {
        # Aluno
        "nome": aluno['nome_completo'],
        "cpf": aluno['cpf'],
        "rg": aluno.get('rg', ''),
        "email": aluno['email'],
        "telefone": aluno.get('telefone', ''),
        "estado_civil": aluno.get('estado_civil', ''),
        "nacionalidade": aluno.get('nacionalidade', ''),
        "data_nascimento": datetime.strptime(aluno['data_nascimento'], '%Y-%m-%d').strftime('%d/%m/%Y') if aluno.get('data_nascimento') else '',
        
        # Endereço
        "logradouro": aluno.get('logradouro', ''),
        "numero": aluno.get('numero', ''),
        "bairro": aluno.get('bairro', ''),
        "complemento": aluno.get('complemento', ''),
        "cidade": aluno.get('cidade', ''),
        "uf": aluno.get('uf', ''),
        "cep": aluno.get('cep', ''),
        
        # Dados Médicos
        "crm": aluno.get('crm', ''),
        "área_formação": aluno.get('area_formacao', ''),
        
        # Curso/Turma
        "pos_graduacao": curso['nome'],
        "turma": turma['codigo_turma'],
        "formato_curso": contrato_dados['formato_curso'],
        "atendimento": "SIM" if contrato_dados['atendimento_paciente'] else "NÃO",
        "bolsista": "SIM" if contrato_dados['bolsista'] else "NÃO",
        
        # Valores Totais
        "valor_curso": format_moeda(val_bruto),
        "valor_desconto": format_moeda(val_desc),
        "pencentual_desconto": f"{contrato_dados['percentual_desconto']}%",
        "valor_final": format_moeda(val_final),
        "valor_material": format_moeda(val_material),
        
        # Tabelas de Pagamento (Listas para o Jinja2 no Word)
        "tbl_entrada": parcelas_entrada,
        "tbl_saldo": parcelas_saldo,
        
        # Datas de Assinatura
        "dia": data_extenso['dia'],
        "mês": data_extenso['mês'],
        "ano": data_extenso['ano']
    }

    # 2. Renderizar DOCX
    # -----------------------------------------------
    template_path = "assets/modelo_contrato_V2.docx"
    doc = DocxTemplate(template_path)
    doc.render(context)
    
    # Salvar temporariamente
    output_filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}.docx"
    temp_docx_path = f"/tmp/{output_filename}"
    doc.save(temp_docx_path)
    
    # 3. Converter para PDF (LibreOffice)
    # -----------------------------------------------
    # O comando --outdir define onde o PDF será salvo
    cmd = [
        "soffice", "--headless", "--convert-to", "pdf", 
        "--outdir", "/tmp", temp_docx_path
    ]
    
    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            st.error(f"Erro no LibreOffice: {process.stderr.decode()}")
            return None
    except Exception as e:
        st.error(f"Erro ao executar LibreOffice: {e}")
        return None

    # O nome do arquivo PDF gerado será o mesmo do docx, mas com extensão .pdf
    temp_pdf_path = temp_docx_path.replace(".docx", ".pdf")
    nome_arquivo_pdf = output_filename.replace(".docx", ".pdf")

    # 4. Upload para Supabase Storage
    # -----------------------------------------------
    try:
        with open(temp_pdf_path, "rb") as f:
            # Caminho no bucket: contratos/ANO/MES/NomeArquivo.pdf
            caminho_storage = f"{hoje.year}/{hoje.month}/{nome_arquivo_pdf}"
            
            supabase.storage.from_("contratos").upload(
                path=caminho_storage,
                file=f,
                file_options={"content-type": "application/pdf"}
            )
            
        # Pega a URL pública (ou assinada se o bucket for privado)
        # Como configuramos bucket privado, precisamos criar uma Signed URL válida por muito tempo (ex: 1 ano) ou baixar via API
        # Para simplificar o envio por e-mail, vamos gerar uma Signed URL de 7 dias
        res_url = supabase.storage.from_("contratos").create_signed_url(caminho_storage, 604800) # 7 dias
        url_final = res_url['signedURL']
            
    except Exception as e:
        st.error(f"Erro no upload para Storage: {e}")
        return None
    
    # Limpeza
    if os.path.exists(temp_docx_path): os.remove(temp_docx_path)
    if os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
    
    return {
        "caminho_storage": caminho_storage,
        "url_assinada": url_final
    }

# --- ENVIO DE E-MAIL ---

def enviar_email_contrato(destinatario_email, nome_aluno, link_aceite):
    """
    Envia o e-mail transacional usando Gmail SMTP.
    Retorna True se sucesso, False se erro.
    """
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    remetente_email = st.secrets["GMAIL_EMAIL"]
    remetente_senha = st.secrets["GMAIL_PASSWORD"]

    assunto = "Ação Necessária: Assinatura de Contrato Educacional - NexusMed"

    # Corpo do E-mail em HTML para ficar profissional
    corpo_html = f"""
    <html>
    <body>
        <h2>Olá, {nome_aluno}.</h2>
        <p>Seu contrato de prestação de serviços educacionais com a <strong>NexusMed</strong> já está disponível.</p>
        <p>Para concluir sua matrícula, por favor clique no botão abaixo para revisar os termos e realizar o aceite digital:</p>
        
        <br>
        <a href="{link_aceite}" style="background-color: #008CBA; color: white; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 16px;">
            REVISAR E ASSINAR CONTRATO
        </a>
        <br><br>
        
        <p>Ou copie e cole o link abaixo no seu navegador:</p>
        <p>{link_aceite}</p>
        
        <hr>
        <p><small>Este é um e-mail automático. Por favor, não responda.</small></p>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = remetente_email
        msg['To'] = destinatario_email
        msg['Subject'] = assunto

        msg.attach(MIMEText(corpo_html, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls() # Criptografia TLS
        server.login(remetente_email, remetente_senha)
        text = msg.as_string()
        server.sendmail(remetente_email, destinatario_email, text)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False
