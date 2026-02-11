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

# --- CAMINHO DO ARQUIVO ---
TEMPLATE_PATH = "assets/modelo_contrato_V2.docx"

# --- FORMATAÇÃO ---
def format_moeda(valor):
    if valor is None: return "R$ 0,00"
    try: return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def format_data(data_obj):
    try:
        if isinstance(data_obj, str):
            data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except: return str(data_obj)

# --- GERAÇÃO DO PDF ---
def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    if not os.path.exists(TEMPLATE_PATH):
        st.error(f"❌ Template não encontrado em: {TEMPLATE_PATH}")
        return None

    # 1. Tabela Entrada
    tbl_entrada = []
    detalhes = datas_info.get('detalhes_entrada', [])
    if detalhes:
        for x in detalhes:
            tbl_entrada.append({
                "numero": str(x['numero']), 
                "data_vencimento": format_data(x['data']),
                "valor": format_moeda(x['valor']).replace("R$ ", ""), # Remove R$ para caber na tabela
                "forma_pagamento": str(x['forma'])
            })
    
    # 2. Tabela Saldo
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
                "valor": format_moeda(val_s).replace("R$ ", ""),
                "forma_pagamento": str(contrato['saldo_forma_pagamento'])
            })

    # 3. CÁLCULO DO MATERIAL (30%) - CORREÇÃO DO R$ 0,00
    valor_bruto = float(contrato['valor_curso'])
    valor_material = valor_bruto * 0.30

    # 4. Contexto (Mapeamento EXATO para o seu Word)
    hoje = datetime.now()
    meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    
    # Lógica de SIM/NÃO
    txt_atendimento = "SIM" if contrato['atendimento_paciente'] else "NÃO"
    txt_bolsista = "SIM" if contrato['bolsista'] else "NÃO"

    context = {
        # DADOS PESSOAIS
        "nome": aluno['nome_completo'].upper(),
        "cpf": aluno['cpf'],
        "estado_civil": aluno.get('estado_civil', ''),
        "email": aluno['email'],
        "área_formação": aluno.get('area_formacao', ''),
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

        # DADOS DO CURSO (Corrigido conforme seu print)
        "pos_graduacao": curso['nome'],  # No Word está {{ pos_graduacao }}
        "formato_curso": contrato.get('formato_curso', ''),
        "turma": turma['codigo_turma'],
        "atendimento": txt_atendimento,
        "bolsista": txt_bolsista,

        # FINANCEIRO
        "valor_curso": format_moeda(valor_bruto).replace("R$ ", ""), # O Word já tem o R$
        "valor_desconto": format_moeda(contrato['valor_desconto']).replace("R$ ", ""),
        "pencentual_desconto": f"{contrato['percentual_desconto']}%", # Mantido erro de digitação do Word 'pencentual'
        "valor_final": format_moeda(contrato['valor_final']).replace("R$ ", ""),
        "valor_material": format_moeda(valor_material).replace("R$ ", ""), # Corrigido

        # TABELAS
        "tbl_entrada": tbl_entrada,
        "tbl_saldo": tbl_saldo,

        # ASSINATURA
        "dia": hoje.day,
        "mês": meses[hoje.month - 1],
        "ano": hoje.year
    }

    try:
        doc = DocxTemplate(TEMPLATE_PATH)
        doc.render(context)
        
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        
        doc.save(docx_path)
        
        # Converte PDF
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_local = pdf_path if os.path.exists(pdf_path) else docx_path
        mime = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        path_cloud = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        
        with open(final_local, "rb") as f:
            supabase.storage.from_("contratos").upload(path_cloud, f, {"content-type": mime, "upsert": "true"})
            
        return final_local, path_cloud

    except Exception as e:
        st.error(f"Erro Template: {e}")
        return None

# --- CARIMBO E EMAIL (Mantidos) ---
def aplicar_carimbo_digital(path_cloud, metadados):
    if not path_cloud.endswith(".pdf"): return path_cloud
    try:
        data = supabase.storage.from_("contratos").download(path_cloud)
        pdf_reader = PdfReader(io.BytesIO(data)); pdf_writer = PdfWriter()
        packet = io.BytesIO(); c = canvas.Canvas(packet, pagesize=letter)
        c.setFont("Helvetica", 6); c.setFillColorRGB(0.2, 0.2, 0.2, 0.5)
        
        txt = f"ACEITE DIGITAL | Data: {metadados['data_hora']} | IP: {metadados['ip']} | CPF: {metadados['cpf']} | Hash: {metadados['hash']}"
        
        # Carimbo no rodapé esquerdo
        c.drawString(20, 20, txt)
        c.save(); packet.seek(0)
        watermark = PdfReader(packet).pages[0]
        
        for page in pdf_reader.pages:
            page.merge_page(watermark)
            pdf_writer.add_page(page)
            
        out = io.BytesIO(); pdf_writer.write(out); out.seek(0)
        new_path = path_cloud.replace(".pdf", "_assinado.pdf")
        supabase.storage.from_("contratos").upload(new_path, out, {"content-type": "application/pdf", "upsert": "true"})
        return new_path
    except: return path_cloud

def enviar_email(destinatario, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["GMAIL_EMAIL"]; msg['To'] = destinatario
        msg['Subject'] = "Assinatura Pendente - NexusMed"
        html = f"""
        <div style="font-family:Arial; padding:20px; border:1px solid #ccc;">
            <h2 style="color:#003366;">Olá, {nome}</h2>
            <p>Seu contrato está pronto para assinatura.</p>
            <a href="{link}" style="background-color:#003366; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">ASSINAR AGORA</a>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        s = smtplib.SMTP("smtp.gmail.com", 587); s.starttls()
        s.login(st.secrets["GMAIL_EMAIL"], st.secrets["GMAIL_PASSWORD"])
        s.sendmail(msg['From'], destinatario, msg.as_string()); s.quit()
        return True
    except: return False
