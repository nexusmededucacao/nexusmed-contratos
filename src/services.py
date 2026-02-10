import streamlit as st
import os
import io
import smtplib
import subprocess
from pathlib import Path
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from docxtpl import DocxTemplate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from src.db import supabase

# --- IMPORTS PARA RECRIAR O WORD (AUTO-FIX) ---
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- FUNÇÃO DE AUTO-REPARO DO TEMPLATE ---
def restaurar_template_padrao():
    """Cria um novo template_contrato.docx se ele estiver faltando ou corrompido"""
    caminho = "assets/modelo_contrato_V2.docx"
    
    # Garante pasta assets
    if not os.path.exists("assets"):
        os.makedirs("assets")

    doc = Document()
    
    # Estilos
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(11)

    # Conteúdo
    h = doc.add_heading('CONTRATO DE PRESTAÇÃO DE SERVIÇOS', 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.add_run('CONTRATANTE: ').bold = True
    p.add_run('{{ nome_aluno }}')
    
    p = doc.add_paragraph()
    p.add_run('CPF: ').bold = True
    p.add_run('{{ cpf_aluno }}  ')
    p.add_run('RG: ').bold = True
    p.add_run('{{ rg_aluno }}')
    
    p = doc.add_paragraph()
    p.add_run('ENDEREÇO: ').bold = True
    p.add_run('{{ endereco_aluno }} - {{ cidade_aluno }} (CEP: {{ cep_aluno }})')

    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.add_run('OBJETO: ').bold = True
    p.add_run('Curso de Pós-Graduação em {{ nome_curso }} (Turma: {{ turma }}).')
    
    doc.add_heading('Condições Financeiras', level=1)
    
    # Tabela Entrada
    doc.add_heading('1. Entrada Detalhada', level=2)
    table = doc.add_table(rows=2, cols=4)
    table.style = 'Table Grid'
    
    # Cabeçalho
    hdr = table.rows[0].cells
    hdr[0].text = 'Parc.'
    hdr[1].text = 'Vencimento'
    hdr[2].text = 'Valor'
    hdr[3].text = 'Forma'
    
    # Linha Loop (CORRIGIDA)
    row = table.rows[1].cells
    row[0].paragraphs[0].add_run('{% tr for item in tbl_entrada %}{{ item.numero }}')
    row[1].text = '{{ item.data_vencimento }}'
    row[2].text = '{{ item.valor }}'
    row[3].paragraphs[0].add_run('{{ item.forma_pagamento }}{% tr endfor %}')

    doc.add_paragraph('')

    # Tabela Saldo
    doc.add_heading('2. Saldo Restante', level=2)
    table2 = doc.add_table(rows=2, cols=4)
    table2.style = 'Table Grid'
    
    hdr2 = table2.rows[0].cells
    hdr2[0].text = 'Parc.'
    hdr2[1].text = 'Vencimento'
    hdr2[2].text = 'Valor'
    hdr2[3].text = 'Forma'
    
    row2 = table2.rows[1].cells
    row2[0].paragraphs[0].add_run('{% tr for item in tbl_saldo %}{{ item.numero }}')
    row2[1].text = '{{ item.data_vencimento }}'
    row2[2].text = '{{ item.valor }}'
    row2[3].paragraphs[0].add_run('{{ item.forma_pagamento }}{% tr endfor %}')

    doc.add_paragraph('')
    doc.add_paragraph('___________________________________________').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('{{ nome_aluno }}').alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.save(caminho)
    return caminho

# --- FUNÇÕES AUXILIARES ---

def format_moeda(valor):
    if valor is None: return "R$ 0,00"
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(valor)

def format_data(data_obj):
    try:
        if isinstance(data_obj, str):
            data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except:
        return str(data_obj)

def gerar_parcelas_saldo(valor_total, qtd, data_ini_str, forma):
    lista = []
    if qtd <= 0: return lista
    try:
        if isinstance(data_ini_str, str):
            data_ini = datetime.strptime(data_ini_str, "%Y-%m-%d")
        else:
            data_ini = data_ini_str
    except:
        data_ini = datetime.now()

    val_p = valor_total / qtd
    for i in range(qtd):
        dt = data_ini + relativedelta(months=+i)
        lista.append({
            "numero": f"{i+1}/{qtd}",
            "data_vencimento": dt.strftime("%d/%m/%Y"),
            "valor": format_moeda(val_p),
            "forma_pagamento": forma
        })
    return lista

# --- GERAÇÃO DO PDF ---

def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    hoje = datetime.now()

    # 1. AUTO-CORREÇÃO: Recria o template sempre que chamar, para garantir que está limpo
    template_path = restaurar_template_padrao()

    # 2. Dados da Entrada
    tbl_entrada = []
    detalhes_entrada = datas_info.get('detalhes_entrada', [])
    
    if detalhes_entrada:
        for item in detalhes_entrada:
            tbl_entrada.append({
                "numero": item['numero'],
                "data_vencimento": format_data(item['data']),
                "valor": format_moeda(item['valor']),
                "forma_pagamento": item['forma']
            })
    else:
        vlr = contrato['entrada_valor'] / max(1, int(contrato['entrada_qtd_parcelas']))
        for i in range(int(contrato['entrada_qtd_parcelas'])):
            tbl_entrada.append({
                "numero": i+1,
                "data_vencimento": "A Definir",
                "valor": format_moeda(vlr),
                "forma_pagamento": contrato['entrada_forma_pagamento']
            })

    # 3. Dados do Saldo
    tbl_saldo = gerar_parcelas_saldo(
        float(contrato['saldo_valor']), 
        int(contrato['saldo_qtd_parcelas']), 
        datas_info.get('inicio_saldo'), 
        contrato['saldo_forma_pagamento']
    )

    # 4. Contexto
    context = {
        "nome_aluno": aluno['nome_completo'].upper(),
        "cpf_aluno": aluno['cpf'],
        "rg_aluno": aluno.get('rg', ''),
        "email_aluno": aluno['email'],
        "telefone_aluno": aluno.get('telefone', ''),
        "endereco_aluno": f"{aluno.get('logradouro','')}, {aluno.get('numero','')}",
        "cidade_aluno": f"{aluno.get('cidade','')} - {aluno.get('uf','')}",
        "cep_aluno": aluno.get('cep', ''),
        "nome_curso": curso['nome'],
        "turma": turma['codigo_turma'],
        "carga_horaria": str(curso.get('carga_horaria', '')),
        "data_inicio": format_data(turma.get('data_inicio')),
        "data_fim": format_data(turma.get('data_fim')),
        "valor_bruto": format_moeda(contrato['valor_curso']),
        "desconto_perc": f"{contrato['percentual_desconto']}%",
        "valor_desconto": format_moeda(contrato['valor_desconto']),
        "valor_final": format_moeda(contrato['valor_final']),
        "entrada_total": format_moeda(contrato['entrada_valor']),
        "tbl_entrada": tbl_entrada,
        "saldo_total": format_moeda(contrato['saldo_valor']),
        "saldo_qtd": str(contrato['saldo_qtd_parcelas']),
        "tbl_saldo": tbl_saldo,
        "data_hoje": hoje.strftime("%d/%m/%Y")
    }

    try:
        # 5. Renderizar
        doc = DocxTemplate(template_path)
        doc.render(context)
        
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        
        doc.save(docx_path)
        
        # Converter PDF
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_path = pdf_path if os.path.exists(pdf_path) else docx_path
        mime_type = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        storage_path = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        with open(final_path, "rb") as f:
            supabase.storage.from_("contratos").upload(
                storage_path, f, {"content-type": mime_type, "upsert": "true"}
            )
            
        return storage_path

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None

# --- ASSINATURA E E-MAIL ---

def aplicar_carimbo_digital(path_original, texto_carimbo):
    if path_original.endswith(".docx"): return path_original
    
    try:
        data = supabase.storage.from_("contratos").download(path_original)
        pdf_reader = PdfReader(io.BytesIO(data))
        pdf_writer = PdfWriter()
        
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.5, 0.5, 0.5, 0.5)
        
        y = 40
        for linha in texto_carimbo.split('\n'):
            c.drawString(20, y, linha.strip())
            y -= 10
        c.save()
        packet.seek(0)
        
        stamp_reader = PdfReader(packet)
        stamp_page = stamp_reader.pages[0]
        
        for page in pdf_reader.pages:
            page.merge_page(stamp_page)
            pdf_writer.add_page(page)
            
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        new_path = path_original.replace(".pdf", "_assinado.pdf")
        supabase.storage.from_("contratos").upload(new_path, output, {"content-type": "application/pdf", "upsert": "true"})
        return new_path
    except Exception as e:
        st.error(f"Erro carimbo: {e}")
        return None

def enviar_email(destinatario, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["GMAIL_EMAIL"]
        msg['To'] = destinatario
        msg['Subject'] = "Contrato NexusMed - Assinatura Pendente"
        
        html = f"""<p>Olá, {nome}. <a href="{link}">Clique aqui para assinar</a></p>"""
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(st.secrets["GMAIL_EMAIL"], st.secrets["GMAIL_PASSWORD"])
        server.sendmail(msg['From'], destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro email: {e}")
        return False
