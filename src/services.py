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

# Função auxiliar para formatar moeda
def format_moeda(valor):
    if valor is None: return "R$ 0,00"
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(valor)

# Função auxiliar para formatar data
def format_data(data_obj):
    try:
        if isinstance(data_obj, str):
            data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except:
        return str(data_obj)

# Gera parcelas automáticas (Usado apenas para o SALDO, que é padrão)
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

def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    # 1. Preparar Dados
    hoje = datetime.now()

    # --- PROCESSAMENTO DA ENTRADA (DETALHADA) ---
    # Aqui pegamos a lista exata que veio do front-end
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
        # Fallback caso não tenha detalhes (compatibilidade)
        vlr = contrato['entrada_valor'] / max(1, contrato['entrada_qtd_parcelas'])
        for i in range(int(contrato['entrada_qtd_parcelas'])):
            tbl_entrada.append({
                "numero": i+1,
                "data_vencimento": "A Definir",
                "valor": format_moeda(vlr),
                "forma_pagamento": contrato['entrada_forma_pagamento']
            })

    # --- PROCESSAMENTO DO SALDO (AUTOMÁTICO) ---
    tbl_saldo = gerar_parcelas_saldo(
        float(contrato['saldo_valor']), 
        int(contrato['saldo_qtd_parcelas']), 
        datas_info.get('inicio_saldo'), 
        contrato['saldo_forma_pagamento']
    )

    # 2. Contexto para o Word (Tags {{ }})
    context = {
        # PESSOAL
        "nome_aluno": aluno['nome_completo'].upper(), # Padronizei chaves com _aluno
        "cpf_aluno": aluno['cpf'],
        "rg_aluno": aluno.get('rg', ''),
        "email_aluno": aluno['email'],
        "telefone_aluno": aluno.get('telefone', ''),
        "estado_civil": aluno.get('estado_civil', ''),
        "nacionalidade": aluno.get('nacionalidade', ''),
        "data_nascimento": format_data(aluno.get('data_nascimento')),
        "crm": aluno.get('crm', ''),
        "area_formacao": aluno.get('area_formacao', ''),
        
        # ENDEREÇO
        "endereco_aluno": f"{aluno.get('logradouro','')}, {aluno.get('numero','')} - {aluno.get('bairro','')}",
        "cidade_aluno": f"{aluno.get('cidade','')} - {aluno.get('uf','')}",
        "cep_aluno": aluno.get('cep', ''),
        
        # CURSO
        "nome_curso": curso['nome'],
        "turma": turma['codigo_turma'],
        "carga_horaria": str(curso.get('carga_horaria', '')),
        "data_inicio": format_data(turma.get('data_inicio')),
        "data_fim": format_data(turma.get('data_fim')),
        "bolsista": "SIM" if contrato['bolsista'] else "NÃO",
        
        # FINANCEIRO - TOTAIS
        "valor_bruto": format_moeda(contrato['valor_curso']),
        "desconto_perc": f"{contrato['percentual_desconto']}%",
        "valor_desconto": format_moeda(contrato['valor_desconto']),
        "valor_final": format_moeda(contrato['valor_final']),
        
        # FINANCEIRO - ENTRADA
        "entrada_total": format_moeda(contrato['entrada_valor']),
        "entrada_qtd": str(contrato['entrada_qtd_parcelas']),
        "tbl_entrada": tbl_entrada, # Lista para o loop no Word
        
        # FINANCEIRO - SALDO
        "saldo_total": format_moeda(contrato['saldo_valor']),
        "saldo_qtd": str(contrato['saldo_qtd_parcelas']),
        "tbl_saldo": tbl_saldo, # Lista para o loop no Word
        
        # DATA HOJE
        "data_hoje": hoje.strftime("%d/%m/%Y")
    }

    # 3. Renderizar DOCX
    template_path = "template_contrato.docx" # Certifique-se que o nome do arquivo está certo
    
    if not os.path.exists(template_path):
        st.error(f"Template não encontrado: {template_path}")
        return None

    try:
        doc = DocxTemplate(template_path)
        doc.render(context)
        
        # Salvar temporário
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        doc.save(docx_path)
        
        # 4. Converter PDF (LibreOffice)
        # Nota: Isso requer LibreOffice instalado no servidor (apt-get install libreoffice)
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if not os.path.exists(pdf_path):
            st.warning("Falha na conversão PDF (LibreOffice). Salvando DOCX no banco.")
            # Fallback: Se falhar o PDF, sobe o DOCX para não perder
            path_storage = f"{hoje.year}/{hoje.month}/{filename}.docx"
            with open(docx_path, "rb") as f:
                supabase.storage.from_("contratos").upload(path_storage, f, {"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "upsert": "true"})
            return path_storage

        # 5. Upload Storage (PDF)
        path_storage = f"{hoje.year}/{hoje.month}/{filename}.pdf"
        with open(pdf_path, "rb") as f:
            supabase.storage.from_("contratos").upload(path_storage, f, {"content-type": "application/pdf", "upsert": "true"})
            
        return path_storage

    except Exception as e:
        st.error(f"Erro ao gerar documento: {e}")
        return None

def aplicar_carimbo_digital(path_original, texto_carimbo):
    """Baixa PDF, aplica carimbo em todas as páginas e re-envia"""
    try:
        # Se for DOCX (fallback), não carimba
        if path_original.endswith(".docx"):
            return path_original

        # Baixar
        data = supabase.storage.from_("contratos").download(path_original)
        pdf_reader = PdfReader(io.BytesIO(data))
        pdf_writer = PdfWriter()
        
        # Criar Carimbo Transparente
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.5, 0.5, 0.5, 0.5) # Cinza transparente
        
        # Desenhar texto no rodapé
        y = 30
        for linha in texto_carimbo.split('\n'):
            c.drawString(20, y, linha.strip())
            y -= 10
        
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
        msg['Subject'] = "Contrato de Prestação de Serviços - NexusMed"
        
        html = f"""
        <html>
            <body>
                <p>Olá, <strong>{nome}</strong>.</p>
                <p>Seu contrato de prestação de serviços educacionais foi gerado com sucesso.</p>
                <p>Por favor, clique no botão abaixo para revisar e assinar digitalmente:</p>
                <br>
                <a href="{link}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 4px;">ASSINAR CONTRATO AGORA</a>
                <br><br>
                <p>Atenciosamente,<br>Equipe NexusMed</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(st.secrets["GMAIL_EMAIL"], st.secrets["GMAIL_PASSWORD"])
        server.sendmail(msg['From'], destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro no envio de e-mail: {e}")
        return False
