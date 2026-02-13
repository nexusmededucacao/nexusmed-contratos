import io
import subprocess
import os
import tempfile
import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import black, white # Alterado para usar preto e branco
from datetime import datetime

class PDFManager:
    """
    Gerenciador de PDF: Responsável pela conversão DOCX -> PDF no Linux
    e aplicação do carimbo de assinatura.
    """

    @staticmethod
    def convert_docx_to_pdf(docx_bytes: io.BytesIO) -> io.BytesIO:
        """
        Converte DOCX para PDF usando o LibreOffice (Headless).
        (LÓGICA PRESERVADA)
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_docx_path = os.path.join(temp_dir, "temp_contract.docx")
            
            with open(temp_docx_path, "wb") as f:
                f.write(docx_bytes.getbuffer())

            try:
                # O comando 'soffice' é o binário padrão para o LibreOffice Headless
                subprocess.run([
                    'soffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', temp_dir, temp_docx_path
                ], check=True, capture_output=True)
                
                pdf_path = os.path.join(temp_dir, "temp_contract.pdf")
                
                if not os.path.exists(pdf_path):
                    # Tenta novamente com o comando 'libreoffice' caso 'soffice' falhe no ambiente
                    subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', temp_dir, temp_docx_path], check=True)

                with open(pdf_path, "rb") as f:
                    pdf_bytes = io.BytesIO(f.read())
                
                return pdf_bytes
            except Exception as e:
                st.error(f"Erro na conversão PDF. Verifique se o LibreOffice está instalado no servidor: {e}")
                return None

    @staticmethod
    def create_signature_stamp(data_assinatura: datetime, nome_aluno: str, cpf: str, email: str, ip: str, link: str, hash_auth: str) -> io.BytesIO:
        """
        Cria o carimbo com fundo branco para rodapé, contendo todos os dados solicitados.
        """
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        
        # --- CONFIGURAÇÃO VISUAL ---
        can.setFont("Helvetica", 7)
        can.setFillColor(black)
        
       
        # 2. Dados do Texto
        can.setFillColor(black)
        data_str = data_assinatura.strftime("%d/%m/%Y às %H:%M:%S (GMT-3)")
        
        # Barra de blocos (Unicode)
        barra = "■" * 95 # Ajustado para a largura

        # Lista de linhas para impressão
        linhas = [
            f"ACEITE DIGITAL REALIZADO",
            f"Data/Hora: {data_str}",
            f"Nome: {nome_aluno}",
            f"CPF: {cpf}",
            f"E-mail: {email}",
            f"IP: {ip}",
            f"Link: {link}",
            f"Hash: {hash_auth}",
            barra
        ]

        # 3. Desenho das linhas (Alinhado à Esquerda com margem, subindo de baixo para cima)
        # Começamos na posição Y = 90 e descemos
        x_pos = 45
        y_pos = 90
        line_height = 9

        for linha in linhas:
            can.drawString(x_pos, y_pos, linha)
            y_pos -= line_height

        can.save()
        packet.seek(0)
        return packet

    @staticmethod
    def apply_stamp_to_pdf(pdf_original_bytes: io.BytesIO, stamp_bytes: io.BytesIO) -> io.BytesIO:
        """
        Faz o merge do carimbo com todas as páginas do PDF usando pypdf.
        (LÓGICA PRESERVADA)
        """
        try:
            pdf_original_bytes.seek(0)
            existing_pdf = PdfReader(pdf_original_bytes)
            stamp_pdf = PdfReader(stamp_bytes)
            stamp_page = stamp_pdf.pages[0]
            output = PdfWriter()
            
            for page in existing_pdf.pages:
                page.merge_page(stamp_page)
                output.add_page(page)
            
            result_stream = io.BytesIO()
            output.write(result_stream)
            result_stream.seek(0)
            return result_stream
        except Exception as e:
            st.error(f"Erro ao aplicar carimbo: {e}")
            return pdf_original_bytes
