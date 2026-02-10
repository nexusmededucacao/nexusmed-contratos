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
    """Gera a lista de parcelas do saldo para o PDF"""
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

    # 1. Definir caminho do Template (CORREÇÃO AQUI)
    template_path = "assets/modelo_contrato_V2.docx"
    
    # Fallback: Se não achar na pasta assets, tenta na raiz
    if not os.path.exists(template_path):
        if os.path.exists("modelo_contrato_V2.docx"):
            template_path = "modelo_contrato_V2.docx"
        elif os.path.exists("template_contrato.docx"):
            template_path = "template_contrato.docx"
        else:
            st.error(f"❌ ERRO CRÍTICO: O arquivo '{template_path}' não foi encontrado na pasta do projeto.")
            return None

    # 2. Processar Entrada (Detalhada vinda do UI)
    tbl_entrada = []
    detalhes_entrada = datas_info.get('detalhes_entrada', [])
    
    if detalhes_entrada:
        # Se veio detalhado do UI (V6/V7), usa isso
        for item in detalhes_entrada:
            tbl_entrada.append({
                "numero": item['numero'],
                "data_vencimento": format_data(item['data']),
                "valor": format_moeda(item['valor']),
                "forma_pagamento": item['forma']
            })
    else:
        # Fallback para contratos antigos
        vlr = contrato['entrada_valor'] / max(1, int(contrato['entrada_qtd_parcelas']))
        for i in range(int(contrato['entrada_qtd_parcelas'])):
            tbl_entrada.append({
                "numero": i+1,
                "data_vencimento": "A Definir",
                "valor": format_moeda(vlr),
                "forma_pagamento": contrato['entrada_forma_pagamento']
            })

    # 3. Processar Saldo (Calculado Agora)
    tbl_saldo = gerar_parcelas_saldo(
        float(contrato['saldo_valor']), 
        int(contrato['saldo_qtd_parcelas']), 
        datas_info.get('inicio_saldo'), 
        contrato['saldo_forma_pagamento']
    )

    # 4. Montar Contexto (Dicionário para o Word)
    context = {
        # PESSOAL
        "nome_aluno": aluno['nome_completo'].upper(),
        "cpf_aluno": aluno['cpf'],
        "rg_aluno": aluno.get('rg', ''),
        "email_aluno": aluno['email'],
        "telefone_aluno": aluno.get('telefone', ''),
        "endereco_aluno": f"{aluno.get('logradouro','')}, {aluno.get('numero','')}",
        "cidade_aluno": f"{aluno.get('cidade','')} - {aluno.get('uf','')}",
        "cep_aluno": aluno.get('cep', ''),
        
        # CURSO
        "nome_curso": curso['nome'],
        "turma": turma['codigo_turma'],
        "carga_horaria": str(curso.get('carga_horaria', '')),
        "data_inicio": format_data(turma.get('data_inicio')),
        "data_fim": format_data(turma.get('data_fim')),
        
        # FINANCEIRO
        "valor_bruto": format_moeda(contrato['valor_curso']),
        "desconto_perc": f"{contrato['percentual_desconto']}%",
        "valor_desconto": format_moeda(contrato['valor_desconto']),
        "valor_final": format_moeda(contrato['valor_final']),
        "entrada_total": format_moeda(contrato['entrada_valor']),
        "saldo_total": format_moeda(contrato['saldo_valor']),
        "saldo_qtd": str(contrato['saldo_qtd_parcelas']),
        
        # TABELAS
        "tbl_entrada": tbl_entrada,
        "tbl_saldo": tbl_saldo,
        
        # DATA
        "data_hoje": hoje.strftime("%d/%m/%Y")
    }

    try:
        # 5. Renderizar e Converter
        doc = DocxTemplate(template_path)
        doc.render(context)
        
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        
        doc.save(docx_path)
        
        # Tenta converter com LibreOffice
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Verifica se gerou PDF, senão usa DOCX
        final_path = pdf_path if os.path.exists(pdf_path) else docx_path
        mime_type = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        # Upload Supabase
        storage_path = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        with open(final_path, "rb") as f:
            supabase.storage.from_("contratos").upload(
                storage_path, f, {"content-type": mime_type, "upsert": "true"}
            )
            
        return storage_path

    except Exception as e:
        st.error(f"Erro ao processar documento: {e}")
        return None

# --- ASSINATURA E E-MAIL ---

def aplicar_carimbo_digital(path_original, texto_carimbo):
    if path_original.endswith(".docx"): return path_original # Não carimba docx
    
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
        
        html = f"""
        <p>Olá, {nome}.</p>
        <p>Clique abaixo para assinar seu contrato:</p>
        <a href="{link}"><b>ASSINAR CONTRATO AGORA</b></a>
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
