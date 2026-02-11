import streamlit as st
import os
import io
import smtplib
import subprocess
import pytz
from datetime import datetime
from docxtpl import DocxTemplate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from src.db import supabase

# --- CAMINHO DO SEU TEMPLATE ---
TEMPLATE_PATH = "assets/modelo_contrato_V2.docx"

# --- FORMATAÇÃO ---
def format_moeda(valor):
    try: return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def format_data(data_obj):
    try:
        if isinstance(data_obj, str):
            data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except: return str(data_obj)

# --- GERAÇÃO DO WORD/PDF ---
def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    # Verifica se o arquivo existe
    if not os.path.exists(TEMPLATE_PATH):
        st.error(f"❌ ARQUIVO NÃO ENCONTRADO: {TEMPLATE_PATH}. Verifique se ele está na pasta assets.")
        return None

    # 1. Prepara Tabela Entrada
    tbl_entrada = []
    detalhes = datas_info.get('detalhes_entrada', [])
    if detalhes:
        for x in detalhes:
            tbl_entrada.append({
                "numero": x['numero'],
                "data_vencimento": format_data(x['data']),
                "valor": format_moeda(x['valor']),
                "forma_pagamento": x['forma']
            })
    
    # 2. Prepara Tabela Saldo
    tbl_saldo = []
    qtd_s = int(contrato['saldo_qtd_parcelas'])
    if qtd_s > 0:
        val_s = float(contrato['saldo_valor']) / qtd_s
        try: ini_s = datetime.strptime(datas_info.get('inicio_saldo'), "%Y-%m-%d")
        except: ini_s = datetime.now()
        
        from dateutil.relativedelta import relativedelta
        for i in range(qtd_s):
            dt = ini_s + relativedelta(months=i)
            tbl_saldo.append({
                "numero": f"{i+1}/{qtd_s}",
                "data_vencimento": dt.strftime("%d/%m/%Y"),
                "valor": format_moeda(val_s),
                "forma_pagamento": contrato['saldo_forma_pagamento']
            })

    # 3. Mapeamento EXATO das variáveis do seu Word
    hoje = datetime.now()
    meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    
    context = {
        # DADOS PESSOAIS
        "nome": aluno['nome_completo'].upper(),
        "cpf": aluno['cpf'],
        "estado_civil": aluno.get('estado_civil', ''),
        "email": aluno['email'],
        "área_formação": aluno.get('area_formacao', ''), # Com acento conforme seu Word
        "data_nascimento": format_data(aluno.get('data_nascimento')),
        "nacionalidade": aluno.get('nacionalidade', ''),
        "crm": aluno.get('crm', ''),
        "telefone": aluno.get('telefone', ''),
        "logradouro": aluno.get('logradouro',''),
        "numero": aluno.get('numero',''),
        "bairro": aluno.get('bairro',''),
        "complemento": aluno.get('complemento',''),
        "cidade": aluno.get('cidade',''),
        "uf": aluno.get('uf',''),
        "cep": aluno.get('cep',''),

        # DADOS DO CURSO
        "pos_graduacao": curso['nome'],
        "formato_curso": contrato.get('formato_curso', ''),
        "turma": turma['codigo_turma'],
        "atendimento": "SIM" if contrato['atendimento_paciente'] else "NÃO",
        "bolsista": "SIM" if contrato['bolsista'] else "NÃO",

        # FINANCEIRO
        "valor_curso": format_moeda(contrato['valor_curso']),
        "valor_desconto": format_moeda(contrato['valor_desconto']),
        "pencentual_desconto": f"{contrato['percentual_desconto']}%", # Mantido o typo do seu Word 'pencentual'
        "valor_final": format_moeda(contrato['valor_final']),
        "valor_material": format_moeda(contrato.get('valor_material', 0)),

        # TABELAS
        "tbl_entrada": tbl_entrada,
        "tbl_saldo": tbl_saldo,

        # DATA FINAL
        "dia": hoje.day,
        "mês": meses[hoje.month - 1], # Com acento
        "ano": hoje.year
    }

    try:
        # Renderiza o Template
        doc = DocxTemplate(TEMPLATE_PATH)
        doc.render(context)
        
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        
        doc.save(docx_path)
        
        # Converte para PDF
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Verifica qual arquivo foi gerado
        final_local = pdf_path if os.path.exists(pdf_path) else docx_path
        mime = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        # Upload para o Supabase
        path_cloud = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        
        with open(final_local, "rb") as f:
            supabase.storage.from_("contratos").upload(path_cloud, f, {"content-type": mime, "upsert": "true"})
            
        return final_local, path_cloud

    except Exception as e:
        st.error(f"Erro ao processar template: {e}")
        return None

# --- CARIMBO FORENSE (EM TODAS AS PÁGINAS) ---
def aplicar_carimbo_digital(path_cloud, metadados):
    if not path_cloud.endswith(".pdf"): return path_cloud
    
    try:
        # 1. Baixa o PDF original
        data = supabase.storage.from_("contratos").download(path_cloud)
        pdf_reader = PdfReader(io.BytesIO(data))
        pdf_writer = PdfWriter()
        
        # 2. Cria o Carimbo
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.2, 0.2, 0.2, 0.8) # Cinza escuro
        
        # Texto Forense
        texto = (
            f"ACEITE DIGITAL REALIZADO | Data: {metadados['data_hora']} | IP: {metadados['ip']}\n"
            f"Nome: {metadados['nome']} | CPF: {metadados['cpf']} | Email: {metadados['email']}\n"
            f"Hash: {metadados['hash']} | ID: {metadados['token']}"
        )
        
        # Escreve no rodapé (margem esquerda)
        y = 30
        for linha in texto.split('\n'):
            c.drawString(30, y, linha)
            y -= 10
            
        c.save()
        packet.seek(0)
        watermark = PdfReader(packet).pages[0]
        
        # 3. Aplica em TODAS as páginas
        for page in pdf_reader.pages:
            page.merge_page(watermark)
            pdf_writer.add_page(page)
            
        # 4. Salva e substitui no banco
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        new_path = path_cloud.replace(".pdf", "_assinado.pdf")
        supabase.storage.from_("contratos").upload(new_path, output, {"content-type": "application/pdf", "upsert": "true"})
        
        return new_path

    except Exception as e:
        print(f"Erro Carimbo: {e}")
        return path_cloud

# --- EMAIL PROFISSIONAL (HTML) ---
def enviar_email(destinatario, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["GMAIL_EMAIL"]
        msg['To'] = destinatario
        msg['Subject'] = "Ação Necessária: Assinatura de Contrato - NexusMed"
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee;">
            <div style="background-color: #002B36; padding: 20px; text-align: center;">
                <h2 style="color: #fff; margin: 0;">NEXUSMED</h2>
            </div>
            <div style="padding: 30px;">
                <p>Olá, <strong>{nome}</strong>.</p>
                <p>Seu contrato de prestação de serviços educacionais está pronto.</p>
                <p>Para garantir sua vaga, clique no botão abaixo para revisar e assinar digitalmente:</p>
                <br>
                <div style="text-align: center;">
                    <a href="{link}" style="background-color: #2563EB; color: #fff; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">ASSINAR CONTRATO</a>
                </div>
                <br><br>
                <p style="font-size: 12px; color: #666;">Se o botão não funcionar, copie este link: {link}</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        
        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(st.secrets["GMAIL_EMAIL"], st.secrets["GMAIL_PASSWORD"])
        s.sendmail(msg['From'], destinatario, msg.as_string())
        s.quit()
        return True
    except: return FalseFalse
