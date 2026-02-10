import streamlit as st
import os
import io
import smtplib
import subprocess
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from docxtpl import DocxTemplate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from src.db import supabase

# --- MÓDULO DE CRIAÇÃO DO TEMPLATE (EMBUTIDO) ---
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def criar_template_temporario():
    caminho_temp = "/tmp/template_limpo.docx"
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(10)

    h = doc.add_heading('CONTRATO DE PRESTAÇÃO DE SERVIÇOS', 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.add_run('CONTRATANTE: ').bold = True
    p.add_run('{{ nome_aluno }} (CPF: {{ cpf_aluno }}), residente em {{ endereco_aluno }} - {{ cidade_aluno }} (CEP: {{ cep_aluno }}).')
    
    p = doc.add_paragraph()
    p.add_run('OBJETO: ').bold = True
    p.add_run('Curso de Pós-Graduação em {{ nome_curso }} (Turma: {{ turma }}).')

    doc.add_heading('Condições Financeiras', level=1)
    p = doc.add_paragraph()
    p.add_run('Valor Bruto: {{ valor_bruto }} | Desconto: {{ desconto_perc }} | ').bold = False
    p.add_run('Final: {{ valor_final }}').bold = True

    doc.add_heading('1. Detalhamento da Entrada', level=2)
    table = doc.add_table(rows=2, cols=4)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text = 'Parc'; hdr[1].text = 'Vencimento'; hdr[2].text = 'Valor'; hdr[3].text = 'Forma'
    
    row = table.rows[1].cells
    row[0].paragraphs[0].add_run('{% for item in tbl_entrada %}{{ item.numero }}')
    row[1].text = '{{ item.data_vencimento }}'
    row[2].text = '{{ item.valor }}'
    row[3].paragraphs[0].add_run('{{ item.forma_pagamento }}{% endfor %}')

    doc.add_heading('2. Detalhamento do Saldo', level=2)
    table2 = doc.add_table(rows=2, cols=4)
    table2.style = 'Table Grid'
    hdr2 = table2.rows[0].cells
    hdr2[0].text = 'Parc'; hdr2[1].text = 'Vencimento'; hdr2[2].text = 'Valor'; hdr2[3].text = 'Forma'
    
    row2 = table2.rows[1].cells
    row2[0].paragraphs[0].add_run('{% for item in tbl_saldo %}{{ item.numero }}')
    row2[1].text = '{{ item.data_vencimento }}'
    row2[2].text = '{{ item.valor }}'
    row2[3].paragraphs[0].add_run('{{ item.forma_pagamento }}{% endfor %}')

    doc.add_paragraph('')
    doc.add_paragraph('_______________________________').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('{{ nome_aluno }}').alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.save(caminho_temp)
    return caminho_temp

# --- FUNÇÕES AUXILIARES ---
def format_moeda(valor):
    if valor is None: return "R$ 0,00"
    try: return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return str(valor)

def format_data(data_obj):
    try:
        if isinstance(data_obj, str): data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except: return str(data_obj)

def gerar_parcelas_saldo(valor_total, qtd, data_ini_str, forma):
    lista = []
    if qtd <= 0: return lista
    try:
        if isinstance(data_ini_str, str): data_ini = datetime.strptime(data_ini_str, "%Y-%m-%d")
        else: data_ini = data_ini_str
    except: data_ini = datetime.now()
    val_p = valor_total / qtd
    for i in range(qtd):
        dt = data_ini + relativedelta(months=+i)
        lista.append({"numero": f"{i+1}/{qtd}", "data_vencimento": dt.strftime("%d/%m/%Y"), "valor": format_moeda(val_p), "forma_pagamento": forma})
    return lista

# --- GERAÇÃO DO PDF ---
def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    hoje = datetime.now()
    try: template_path = criar_template_temporario()
    except Exception as e: st.error(f"Erro Template: {e}"); return None

    tbl_entrada = []
    detalhes_entrada = datas_info.get('detalhes_entrada', [])
    if detalhes_entrada:
        for item in detalhes_entrada:
            tbl_entrada.append({"numero": item['numero'], "data_vencimento": format_data(item['data']), "valor": format_moeda(item['valor']), "forma_pagamento": item['forma']})
    else:
        vlr = contrato['entrada_valor'] / max(1, int(contrato['entrada_qtd_parcelas']))
        for i in range(int(contrato['entrada_qtd_parcelas'])):
            tbl_entrada.append({"numero": i+1, "data_vencimento": "A Definir", "valor": format_moeda(vlr), "forma_pagamento": contrato['entrada_forma_pagamento']})

    tbl_saldo = gerar_parcelas_saldo(float(contrato['saldo_valor']), int(contrato['saldo_qtd_parcelas']), datas_info.get('inicio_saldo'), contrato['saldo_forma_pagamento'])

    context = {
        "nome_aluno": aluno['nome_completo'].upper(), "cpf_aluno": aluno['cpf'],
        "endereco_aluno": f"{aluno.get('logradouro','')}, {aluno.get('numero','')}",
        "cidade_aluno": f"{aluno.get('cidade','')} - {aluno.get('uf','')}", "cep_aluno": aluno.get('cep', ''),
        "nome_curso": curso['nome'], "turma": turma['codigo_turma'], "carga_horaria": str(curso.get('carga_horaria', '')),
        "valor_bruto": format_moeda(contrato['valor_curso']), "desconto_perc": f"{contrato['percentual_desconto']}%",
        "valor_final": format_moeda(contrato['valor_final']), "entrada_total": format_moeda(contrato['entrada_valor']),
        "saldo_total": format_moeda(contrato['saldo_valor']), "saldo_qtd": str(contrato['saldo_qtd_parcelas']),
        "tbl_entrada": tbl_entrada, "tbl_saldo": tbl_saldo, "data_hoje": hoje.strftime("%d/%m/%Y")
    }

    try:
        doc = DocxTemplate(template_path)
        doc.render(context)
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        doc.save(docx_path)
        
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_local_path = pdf_path if os.path.exists(pdf_path) else docx_path
        mime_type = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        storage_path = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        with open(final_local_path, "rb") as f:
            supabase.storage.from_("contratos").upload(storage_path, f, {"content-type": mime_type, "upsert": "true"})
            
        # CORREÇÃO: RETORNA OS DOIS CAMINHOS
        return final_local_path, storage_path

    except Exception as e:
        st.error(f"Erro processar: {e}")
        return None

# --- CARIMBO E EMAIL ---
def aplicar_carimbo_digital(path_original, texto_carimbo):
    if path_original.endswith(".docx"): return path_original
    try:
        data = supabase.storage.from_("contratos").download(path_original)
        pdf_reader = PdfReader(io.BytesIO(data))
        pdf_writer = PdfWriter()
        packet = io.BytesIO(); c = canvas.Canvas(packet, pagesize=letter); c.setFont("Helvetica", 8); c.setFillColorRGB(0.5, 0.5, 0.5, 0.5)
        y = 40
        for linha in texto_carimbo.split('\n'): c.drawString(20, y, linha.strip()); y -= 10
        c.save(); packet.seek(0)
        stamp_page = PdfReader(packet).pages[0]
        for page in pdf_reader.pages: page.merge_page(stamp_page); pdf_writer.add_page(page)
        output = io.BytesIO(); pdf_writer.write(output); output.seek(0)
        new_path = path_original.replace(".pdf", "_assinado.pdf")
        supabase.storage.from_("contratos").upload(new_path, output, {"content-type": "application/pdf", "upsert": "true"})
        return new_path
    except Exception as e: st.error(f"Erro carimbo: {e}"); return None

def enviar_email(destinatario, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["GMAIL_EMAIL"]; msg['To'] = destinatario; msg['Subject'] = "Assinatura - NexusMed"
        msg.attach(MIMEText(f"Assine aqui: {link}", 'html'))
        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(st.secrets["GMAIL_EMAIL"], st.secrets["GMAIL_PASSWORD"])
        server.sendmail(msg['From'], destinatario, msg.as_string()); server.quit()
        return True
    except: return False
