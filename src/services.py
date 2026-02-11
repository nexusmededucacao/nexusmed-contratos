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

# --- CONFIGURAÇÕES ---
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

# --- GERAÇÃO DO CONTRATO ---
def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    if not os.path.exists(TEMPLATE_PATH):
        st.error(f"❌ Arquivo não encontrado: {TEMPLATE_PATH}. Coloque seu arquivo na pasta assets.")
        return None

    # Prepara Tabela Entrada
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
    
    # Prepara Tabela Saldo
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

    # Contexto EXATO do seu Word
    context = {
        "nome": aluno['nome_completo'].upper(),
        "cpf": aluno['cpf'],
        "rg": aluno.get('rg', ''),
        "email": aluno['email'],
        "telefone": aluno.get('telefone', ''),
        "logradouro": aluno.get('logradouro',''),
        "numero": aluno.get('numero',''),
        "bairro": aluno.get('bairro',''),
        "complemento": aluno.get('complemento',''),
        "cidade": aluno.get('cidade',''),
        "uf": aluno.get('uf',''),
        "cep": aluno.get('cep',''),
        "estado_civil": aluno.get('estado_civil', ''),
        "nacionalidade": aluno.get('nacionalidade', ''),
        "crm": aluno.get('crm', ''),
        "área_formação": aluno.get('area_formacao', ''),
        "data_nascimento": format_data(aluno.get('data_nascimento')),
        
        "pos_graduacao": curso['nome'],
        "turma": turma['codigo_turma'],
        "formato_curso": contrato.get('formato_curso', ''),
        "atendimento": "SIM" if contrato['atendimento_paciente'] else "NÃO",
        "bolsista": "SIM" if contrato['bolsista'] else "NÃO",
        
        "valor_curso": format_moeda(contrato['valor_curso']),
        "pencentual_desconto": f"{contrato['percentual_desconto']}%",
        "valor_desconto": format_moeda(contrato['valor_desconto']),
        "valor_final": format_moeda(contrato['valor_final']),
        "valor_material": format_moeda(contrato.get('valor_material', 0)),
        
        # Tabelas para o loop {% for p in ... %}
        "tbl_entrada": tbl_entrada,
        "tbl_saldo": tbl_saldo
    }

    try:
        doc = DocxTemplate(TEMPLATE_PATH)
        doc.render(context)
        
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        
        doc.save(docx_path)
        
        # Conversão PDF
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_local = pdf_path if os.path.exists(pdf_path) else docx_path
        mime = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        # Upload Nuvem
        hoje = datetime.now()
        path_cloud = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        
        with open(final_local, "rb") as f:
            supabase.storage.from_("contratos").upload(path_cloud, f, {"content-type": mime, "upsert": "true"})
            
        return final_local, path_cloud

    except Exception as e:
        st.error(f"Erro ao gerar documento: {e}")
        return None

# --- CARIMBO FORENSE ---
def aplicar_carimbo_digital(path_cloud, metadados):
    """
    Baixa o PDF, aplica o texto de aceite em TODAS as páginas e sobe de volta.
    metadados: Dicionário com IP, Hash, Data, etc.
    """
    if not path_cloud.endswith(".pdf"): return path_cloud
    
    try:
        # 1. Baixar PDF Original
        data = supabase.storage.from_("contratos").download(path_cloud)
        pdf_reader = PdfReader(io.BytesIO(data))
        pdf_writer = PdfWriter()
        
        # 2. Criar o Carimbo (Marca d'água)
        packet = io.BytesIO()
        # A4 Page Size
        c = canvas.Canvas(packet, pagesize=letter)
        c.setFont("Helvetica", 6) # Fonte pequena
        c.setFillColorRGB(0.3, 0.3, 0.3, 0.6) # Cinza escuro, levemente transparente
        
        texto_bloco = f"""
        ACEITE DIGITAL REALIZADO | ID Contrato: {metadados.get('token', 'N/A')}
        Data/Hora: {metadados['data_hora']} | IP: {metadados['ip']}
        Signatário: {metadados['nome']} (CPF: {metadados['cpf']})
        Hash: {metadados['hash']}
        """
        
        # Desenha no rodapé de cada página
        width, height = letter
        text_object = c.beginText(20, 30) # X=20, Y=30 (Rodapé Esquerdo)
        for line in texto_bloco.strip().split('\n'):
            text_object.textLine(line.strip())
        c.drawText(text_object)
        c.save()
        
        packet.seek(0)
        watermark = PdfReader(packet).pages[0]
        
        # 3. Mesclar em TODAS as páginas
        for page in pdf_reader.pages:
            page.merge_page(watermark)
            pdf_writer.add_page(page)
            
        # 4. Salvar e Upload
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        new_path = path_cloud.replace(".pdf", "_assinado.pdf")
        supabase.storage.from_("contratos").upload(new_path, output, {"content-type": "application/pdf", "upsert": "true"})
        
        return new_path

    except Exception as e:
        print(f"Erro Carimbo: {e}")
        return path_cloud

# --- EMAIL PROFISSIONAL ---
def enviar_email(destinatario, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["GMAIL_EMAIL"]
        msg['To'] = destinatario
        msg['Subject'] = "Ação Necessária: Assinatura de Contrato - NexusMed"
        
        # HTML Limpo e Profissional
        html = f"""
        <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px;">
            <div style="background-color: #002B36; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
                <h2 style="color: #ffffff; margin: 0;">NEXUSMED</h2>
            </div>
            <div style="padding: 30px;">
                <p>Olá, <strong>{nome}</strong>.</p>
                <p>Seu contrato de prestação de serviços educacionais foi gerado e aguarda sua assinatura digital.</p>
                <p>Para prosseguir com sua matrícula, clique no botão abaixo:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{link}" style="background-color: #2563EB; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">ASSINAR CONTRATO</a>
                </div>
                <p style="font-size: 12px; color: #666;">Se o botão não funcionar, copie este link: <br>{link}</p>
            </div>
            <div style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #888; border-radius: 0 0 8px 8px;">
                © 2026 NexusMed Educação. Mensagem automática.
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(st.secrets["GMAIL_EMAIL"], st.secrets["GMAIL_PASSWORD"])
        server.sendmail(msg['From'], destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro Email: {e}")
        return False
