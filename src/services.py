import streamlit as st
import os
import io
import smtplib
import subprocess
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
from docxtpl import DocxTemplate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from src.db import supabase

def format_moeda(valor):
    if valor is None: return "R$ 0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_parcelas(valor_total, qtd, data_ini, forma):
    lista = []
    if qtd <= 0: return lista
    val_p = valor_total / qtd
    for i in range(qtd):
        dt = data_ini + relativedelta(months=+i)
        lista.append({
            "numero": f"{i+1:02d}",
            "data_vencimento": dt.strftime("%d/%m/%Y"),
            "valor": format_moeda(val_p),
            "forma_pagamento": forma
        })
    return lista

def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_venc):
    # 1. Preparar Contexto (Banco -> Template Word)
    hoje = datetime.now()
    
    # Gera tabelas de pagamento
    tbl_entrada = gerar_parcelas(float(contrato['entrada_valor']), int(contrato['entrada_qtd_parcelas']), datas_venc['entrada'], contrato['entrada_forma_pagamento'])
    tbl_saldo = gerar_parcelas(float(contrato['saldo_valor']), int(contrato['saldo_qtd_parcelas']), datas_venc['saldo'], contrato['saldo_forma_pagamento'])

    context = {
        # PESSOAL
        "nome": aluno['nome_completo'],
        "cpf": aluno['cpf'],
        "rg": aluno.get('rg', ''),
        "email": aluno['email'],
        "telefone": aluno.get('telefone', ''),
        "estado_civil": aluno.get('estado_civil', ''),
        "nacionalidade": aluno.get('nacionalidade', ''),
        "data_nascimento": datetime.strptime(aluno['data_nascimento'], '%Y-%m-%d').strftime('%d/%m/%Y') if aluno.get('data_nascimento') else '',
        "crm": aluno.get('crm', ''),
        "área_formação": aluno.get('area_formacao', ''),
        
        # ENDEREÇO
        "logradouro": aluno.get('logradouro', ''),
        "numero": aluno.get('numero', ''),
        "bairro": aluno.get('bairro', ''),
        "complemento": aluno.get('complemento', ''),
        "cidade": aluno.get('cidade', ''),
        "uf": aluno.get('uf', ''),
        "cep": aluno.get('cep', ''),
        
        # PRODUTO
        "pos_graduacao": curso['nome'],
        "formato_curso": turma['formato'],
        "turma": turma['codigo_turma'],
        "atendimento": "SIM" if contrato['atendimento_paciente'] else "NÃO",
        "bolsista": "SIM" if contrato['bolsista'] else "NÃO",
        
        # FINANCEIRO
        "valor_curso": format_moeda(contrato['valor_curso']),
        "valor_desconto": format_moeda(contrato['valor_desconto']),
        "pencentual_desconto": f"{contrato['percentual_desconto']}%",
        "valor_final": format_moeda(contrato['valor_final']),
        "valor_material": format_moeda(contrato['valor_material']),
        
        # TABELAS
        "tbl_entrada": tbl_entrada,
        "tbl_saldo": tbl_saldo,
        
        # DATAS DO DOCUMENTO
        "dia": hoje.strftime("%d"),
        "mês": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"][hoje.month - 1],
        "ano": hoje.strftime("%Y")
    }

    # 2. Renderizar DOCX
    template_path = "assets/modelo_contrato_V2.docx"
    doc = DocxTemplate(template_path)
    doc.render(context)
    
    # Salvar temporário
    filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
    docx_path = f"/tmp/{filename}.docx"
    pdf_path = f"/tmp/{filename}.pdf"
    doc.save(docx_path)
    
    # 3. Converter PDF (LibreOffice)
    cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 4. Upload Storage
    path_storage = f"{hoje.year}/{hoje.month}/{filename}.pdf"
    with open(pdf_path, "rb") as f:
        supabase.storage.from_("contratos").upload(path_storage, f, {"content-type": "application/pdf"})
        
    return path_storage

def aplicar_carimbo_digital(path_original, texto_carimbo):
    """Baixa PDF, aplica carimbo em todas as páginas e re-envia"""
    try:
        # Baixar
        data = supabase.storage.from_("contratos").download(path_original)
        pdf_reader = PdfReader(io.BytesIO(data))
        pdf_writer = PdfWriter()
        
        # Criar Carimbo Transparente
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0, 0, 0, 0.7) # Preto com transparência leve
        
        # Desenhar texto linha a linha no rodapé
        text_obj = c.beginText(20, 50) # x=20, y=50 (rodapé esquerdo)
        for linha in texto_carimbo.split('\n'):
            text_obj.textLine(linha.strip())
        c.drawText(text_obj)
        c.save()
        packet.seek(0)
        
        stamp_reader = PdfReader(packet)
        stamp_page = stamp_reader.pages[0]
        
        # Mesclar
        for page in pdf_reader.pages:
            page.merge_page(stamp_page)
            pdf_writer.add_page(page)
            
        # Salvar e Upload
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        new_path = path_original.replace(".pdf", "_assinado.pdf")
        supabase.storage.from_("contratos").upload(new_path, output, {"content-type": "application/pdf", "upsert": "true"})
        
        return new_path
    except Exception as e:
        st.error(f"Erro no carimbo: {e}")
        return None

def enviar_email(destinatario, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["GMAIL_EMAIL"]
        msg['To'] = destinatario
        msg['Subject'] = "Ação Necessária: Assinatura de Contrato - NexusMed"
        
        html = f"""
        <p>Olá, {nome}.</p>
        <p>Seu contrato está pronto para assinatura digital.</p>
        <a href="{link}">CLIQUE AQUI PARA ASSINAR</a>
        """
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
