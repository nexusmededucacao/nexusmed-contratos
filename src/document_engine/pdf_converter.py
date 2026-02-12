import io
import subprocess
import os
import tempfile
import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import grey
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
    def create_signature_stamp(data_assinatura: datetime, nome_aluno: str, cpf: str, ip: str, hash_auth: str) -> io.BytesIO:
        """Cria o carimbo transparente para rodapé."""
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFont("Helvetica", 8)
        can.setFillColor(grey)
        
        # Formatação dos dados para o rodapé
        data_str = data_assinatura.strftime("%d/%m/%Y %H:%M:%S")
        texto = f"Assinado eletronicamente por {nome_aluno.upper()} (CPF: {cpf}) em {data_str}"
        texto_tecnico = f"IP: {ip} | Autenticação Hash: {hash_auth}"
        
        # Centralizado no rodapé (A4 tem largura 595.27 pontos)
        can.drawCentredString(297, 30, texto)
        can.drawCentredString(297, 20, texto_tecnico)
        can.save()
        packet.seek(0)
        return packet

    @staticmethod
    def apply_stamp_to_pdf(pdf_original_bytes: io.BytesIO, stamp_bytes: io.BytesIO) -> io.BytesIO:
        """Faz o merge do carimbo com todas as páginas do PDF."""
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
