import streamlit as st
import os
import io
import smtplib
import subprocess
import pytz
from datetime import datetime
from docxtpl import DocxTemplate
from docx import Document # Manipulação direta
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from src.db import supabase

# --- CONFIGURAÇÃO ---
TEMPLATE_PATH = "assets/modelo_contrato_V2.docx"

# --- HELPER: FORMATAÇÃO ---
def format_moeda(valor):
    if valor is None: return "R$ 0,00"
    try:
        # Se vier texto (ex: R$ 1.000,00), limpa para float primeiro
        if isinstance(valor, str):
            valor = float(valor.replace("R$", "").replace(".", "").replace(",", ".").strip())
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

def format_data(data_obj):
    try:
        if isinstance(data_obj, str):
            data_obj = datetime.strptime(data_obj, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except: return str(data_obj)

def parse_float(valor):
    try:
        if isinstance(valor, (float, int)): return float(valor)
        return float(str(valor).replace("R$", "").replace(".", "").replace(",", ".").strip())
    except: return 0.0

# --- FUNÇÃO MÁGICA: INJETAR LINHAS NA TABELA ---
def preencher_tabelas_word(docx_path, dados_entrada, dados_saldo):
    """
    Abre o DOCX já preenchido com textos e adiciona as linhas nas tabelas financeiras.
    Assume que:
    - Tabela índice 2 = Entrada (Item 03)
    - Tabela índice 3 = Saldo (Item 04)
    Baseado na ordem visual do seu documento.
    """
    doc = Document(docx_path)
    
    # Estilo padrão para as células novas
    def formatar_celula(cell, texto):
        cell.text = texto
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.name = 'Arial'
                run.font.size = Pt(9)

    # --- 1. PREENCHER ENTRADA (Tabela 2) ---
    try:
        tbl_ent = doc.tables[2] # Terceira tabela do documento
        for item in dados_entrada:
            row = tbl_ent.add_row() # Cria linha nova
            # Preenche células (0=Parc, 1=Venc, 2=Valor, 3=Forma)
            formatar_celula(row.cells[0], str(item['numero']))
            formatar_celula(row.cells[1], format_data(item['data']))
            formatar_celula(row.cells[2], format_moeda(item['valor']))
            formatar_celula(row.cells[3], str(item['forma']))
    except Exception as e:
        print(f"Erro ao preencher tabela entrada: {e}")

    # --- 2. PREENCHER SALDO (Tabela 3) ---
    try:
        tbl_sal = doc.tables[3] # Quarta tabela do documento
        for item in dados_saldo:
            row = tbl_sal.add_row()
            formatar_celula(row.cells[0], str(item['numero']))
            formatar_celula(row.cells[1], item['data_vencimento']) # Já vem formatada da lógica
            formatar_celula(row.cells[2], item['valor'])           # Já vem formatada
            formatar_celula(row.cells[3], str(item['forma_pagamento']))
    except Exception as e:
        print(f"Erro ao preencher tabela saldo: {e}")

    doc.save(docx_path)

# --- GERAÇÃO PRINCIPAL ---
def gerar_contrato_pdf(aluno, turma, curso, contrato, datas_info):
    if not os.path.exists(TEMPLATE_PATH):
        st.error(f"❌ Template não encontrado: {TEMPLATE_PATH}")
        return None

    # 1. Preparar Dados para a Injeção (Listas Puras)
    lista_entrada = datas_info.get('detalhes_entrada', [])
    
    lista_saldo = []
    qtd_s = int(contrato['saldo_qtd_parcelas'])
    if qtd_s > 0:
        val_s = parse_float(contrato['saldo_valor']) / qtd_s
        try: ini_s = datetime.strptime(datas_info.get('inicio_saldo'), "%Y-%m-%d")
        except: ini_s = datetime.now()
        
        from dateutil.relativedelta import relativedelta
        for i in range(qtd_s):
            dt = ini_s + relativedelta(months=i)
            lista_saldo.append({
                "numero": f"{i+1}/{qtd_s}",
                "data_vencimento": dt.strftime("%d/%m/%Y"),
                "valor": format_moeda(val_s),
                "forma_pagamento": contrato['saldo_forma_pagamento']
            })

    # 2. Cálculos Financeiros
    v_bruto = parse_float(contrato['valor_curso'])
    v_desc = parse_float(contrato['valor_desconto'])
    v_final = parse_float(contrato['valor_final'])
    v_material = v_bruto * 0.30 # Cálculo Correto

    # 3. Contexto (Apenas Variáveis de Texto)
    hoje = datetime.now()
    meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    
    context = {
        # PESSOAL
        "nome": aluno['nome_completo'].upper(), "cpf": aluno['cpf'],
        "estado_civil": aluno.get('estado_civil', ''), "email": aluno['email'],
        "área_formação": aluno.get('area_formacao', ''), "data_nascimento": format_data(aluno.get('data_nascimento')),
        "nacionalidade": aluno.get('nacionalidade', ''), "crm": aluno.get('crm', ''),
        "telefone": aluno.get('telefone', ''), "logradouro": aluno.get('logradouro',''),
        "numero": aluno.get('numero',''), "bairro": aluno.get('bairro',''),
        "complemento": aluno.get('complemento',''), "cidade": aluno.get('cidade',''),
        "uf": aluno.get('uf',''), "cep": aluno.get('cep',''),

        # CURSO
        "pos_graduacao": curso['nome'], 
        "formato_curso": contrato.get('formato_curso', 'Digital'),
        "turma": turma['codigo_turma'],
        "atendimento": "SIM" if contrato['atendimento_paciente'] else "NÃO",
        "bolsista": "SIM" if contrato['bolsista'] else "NÃO",

        # FINANCEIRO
        "valor_curso": format_moeda(v_bruto).replace("R$ ", ""), # Remove R$ pois template já tem
        "valor_desconto": format_moeda(v_desc).replace("R$ ", ""),
        "pencentual_desconto": f"{contrato['percentual_desconto']}", 
        "valor_final": format_moeda(v_final).replace("R$ ", ""),
        "valor_material": format_moeda(v_material).replace("R$ ", ""),

        # DATA
        "dia": hoje.day, "mês": meses[hoje.month - 1], "ano": hoje.year
    }

    try:
        # A. Preenche Textos com docxtpl
        doc = DocxTemplate(TEMPLATE_PATH)
        doc.render(context)
        
        filename = f"Contrato_{aluno['cpf']}_{turma['codigo_turma']}"
        docx_path = f"/tmp/{filename}.docx"
        pdf_path = f"/tmp/{filename}.pdf"
        
        doc.save(docx_path) # Salva o arquivo com textos preenchidos e tabelas vazias
        
        # B. Injeta as Linhas das Tabelas com python-docx
        preencher_tabelas_word(docx_path, lista_entrada, lista_saldo)
        
        # C. Converte para PDF
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", "/tmp", docx_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_local = pdf_path if os.path.exists(pdf_path) else docx_path
        mime = "application/pdf" if os.path.exists(pdf_path) else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".pdf" if os.path.exists(pdf_path) else ".docx"
        
        # D. Upload
        path_cloud = f"{hoje.year}/{hoje.month}/{filename}{ext}"
        with open(final_local, "rb") as f:
            supabase.storage.from_("contratos").upload(path_cloud, f, {"content-type": mime, "upsert": "true"})
            
        return final_local, path_cloud

    except Exception as e:
        st.error(f"Erro Processamento: {e}")
        return None

# --- CARIMBO E EMAIL (Mantidos) ---

def enviar_email(dest, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From']=st.secrets["GMAIL_EMAIL"]; msg['To']=dest; msg['Subject']="Assinatura NexusMed"
        html = f"""<div style="font-family:Arial;padding:20px;border:1px solid #ddd;border-radius:5px;"><h2 style="color:#004B8D;">Olá, {nome}</h2><p>Seu contrato está disponível.</p><br><a href="{link}" style="background:#004B8D;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;">ASSINAR CONTRATO</a></div>"""
        msg.attach(MIMEText(html, 'html'))
        s=smtplib.SMTP("smtp.gmail.com",587); s.starttls(); s.login(st.secrets["GMAIL_EMAIL"],st.secrets["GMAIL_PASSWORD"])
        s.sendmail(msg['From'],dest,msg.as_string()); s.quit(); return True
    except: return False
