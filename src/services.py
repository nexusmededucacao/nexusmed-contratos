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

# --- CONFIGURAÇÃO ---
TEMPLATE_PATH = "assets/modelo_contrato_V2.docx"

# --- HELPER: CONVERTER MOEDA (TEXTO -> FLOAT) ---
def parse_moeda(valor):
    """Converte 'R$ 1.500,00' ou float 1500.0 para float puro"""
    if not valor: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    try:
        # Remove R$, pontos de milhar e troca vírgula por ponto
        limpo = str(valor).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(limpo)
    except: return 0.0

# --- HELPER: FORMATAR (FLOAT -> TEXTO) ---
def format_moeda(valor):
    try: return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

def format_data(data_obj):
    try:
        if isinstance(data_obj, str):
            data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except: return str(data_obj)

# --- GERAÇÃO DO PDF ---
def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    if not os.path.exists(TEMPLATE_PATH):
        st.error(f"❌ Template não encontrado: {TEMPLATE_PATH}")
        return None

    # 1. PREPARAÇÃO DAS TABELAS
    tbl_entrada = []
    detalhes = datas_info.get('detalhes_entrada', [])
    if detalhes:
        for x in detalhes:
            tbl_entrada.append({
                "numero": str(x['numero']),
                "data_vencimento": format_data(x['data']),
                "valor": format_moeda(x['valor']),
                "forma_pagamento": str(x['forma'])
            })
    
    tbl_saldo = []
    qtd_s = int(contrato['saldo_qtd_parcelas'])
    if qtd_s > 0:
        val_s = parse_moeda(contrato['saldo_valor']) / qtd_s
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

    # 2. CÁLCULOS FINANCEIROS CORRIGIDOS
    v_bruto = parse_moeda(contrato['valor_curso'])
    v_desc_val = parse_moeda(contrato['valor_desconto'])
    v_final = parse_moeda(contrato['valor_final'])
    
    # Cálculo dos 30% do material sobre o valor bruto
    v_material = v_bruto * 0.30

    # 3. CONTEXTO (PREENCHIMENTO DO WORD)
    hoje = datetime.now()
    meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    
    context = {
        # PESSOAL
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

        # CURSO (Nomes exatos do seu print)
        "pos_graduacao": curso['nome'], 
        "formato_curso": contrato.get('formato_curso', 'Digital'),
        "turma": turma['codigo_turma'],
        "atendimento": "SIM" if contrato['atendimento_paciente'] else "NÃO",
        "bolsista": "SIM" if contrato['bolsista'] else "NÃO",

        # FINANCEIRO
        "valor_curso": format_moeda(v_bruto),
        "valor_desconto": format_moeda(v_desc_val),
        "pencentual_desconto": f"{contrato['percentual_desconto']}", # Mantido 'pencentual' conforme seu Word
        "valor_final": format_moeda(v_final),
        "valor_material": format_moeda(v_material), # Agora vai preenchido!

        # TABELAS
        "tbl_entrada": tbl_entrada,
        "tbl_saldo": tbl_saldo,

        # DATA
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
        
        # Upload
        path_cloud = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        with open(final_local, "rb") as f:
            supabase.storage.from_("contratos").upload(path_cloud, f, {"content-type": mime, "upsert": "true"})
            
        return final_local, path_cloud

    except Exception as e:
        st.error(f"Erro Template: {e}")
        return None

# --- E-MAIL E CARIMBO (Mantidos) ---
def aplicar_carimbo_digital(path, meta):
    if not path.endswith(".pdf"): return path
    try:
        d = supabase.storage.from_("contratos").download(path)
        r = PdfReader(io.BytesIO(d)); w = PdfWriter()
        p = io.BytesIO(); c = canvas.Canvas(p, pagesize=letter)
        c.setFont("Helvetica",6); c.setFillColorRGB(0.5,0.5,0.5,0.5)
        txt = f"ACEITE DIGITAL | {meta['data_hora']} | {meta['nome']} | IP:{meta['ip']} | Hash:{meta['hash'][:15]}..."
        c.drawString(20,20,txt); c.save(); p.seek(0)
        wm = PdfReader(p).pages[0]
        for pg in r.pages: pg.merge_page(wm); w.add_page(pg)
        out = io.BytesIO(); w.write(out); out.seek(0)
        np = path.replace(".pdf","_assinado.pdf")
        supabase.storage.from_("contratos").upload(np, out, {"content-type":"application/pdf","upsert":"true"})
        return np
    except: return path

def enviar_email(dest, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From']=st.secrets["GMAIL_EMAIL"]; msg['To']=dest; msg['Subject']="Assinatura NexusMed"
        msg.attach(MIMEText(f"Olá {nome}, assine aqui: {link}",'html'))
        s=smtplib.SMTP("smtp.gmail.com",587); s.starttls(); s.login(st.secrets["GMAIL_EMAIL"],st.secrets["GMAIL_PASSWORD"])
        s.sendmail(msg['From'],dest,msg.as_string()); s.quit(); return True
    except: return False
