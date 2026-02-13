import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

# Função obter_url_app removida pois o link já virá pronto

def enviar_email_contrato(email_destinatario: str, nome_aluno: str, link_assinatura: str, nome_curso: str):
    """
    Envia o link de assinatura para o aluno via SMTP.
    Args:
        link_assinatura: URL completa já montada (ex: https://.../Assinatura?token=xyz)
    """
    try:
        # 1. Configurações SMTP do secrets.toml
        smtp_host = st.secrets["email"]["smtp_host"]
        smtp_port = int(st.secrets["email"]["smtp_port"]) 
        smtp_user = st.secrets["email"]["smtp_user"]
        smtp_pass = st.secrets["email"]["smtp_password"]

        # 2. Cria a Mensagem Multipart
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Assinatura Pendente: Contrato {nome_curso}"
        msg['From'] = f"NexusMed Secretaria <{smtp_user}>"
        msg['To'] = email_destinatario

        # 3. Template HTML estilizado (Usa o link_assinatura direto)
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                <div style="background-color: #0f172a; padding: 20px; text-align: center; color: white;">
                    <h2 style="margin: 0;">NexusMed Educação</h2>
                </div>
                <div style="padding: 30px; background-color: #ffffff;">
                    <p>Olá, <strong>{nome_aluno}</strong>.</p>
                    <p>Seu contrato para o curso de <strong>{nome_curso}</strong> já está disponível para assinatura eletrônica.</p>
                    
                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center; border: 1px solid #e2e8f0;">
                        <p style="margin-bottom: 15px; font-size: 14px; color: #64748b;">Clique abaixo para revisar os dados e assinar:</p>
                        
                        <a href="{link_assinatura}" style="background-color: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                            ✍️ REVISAR E ASSINAR AGORA
                        </a>
                    </div>
                    
                    <p style="font-size: 11px; color: #94a3b8;">Caso o botão não funcione, utilize o link: <br> 
                    <a href="{link_assinatura}">{link_assinatura}</a></p>
                </div>
                <div style="background-color: #f1f5f9; padding: 15px; text-align: center; font-size: 12px; color: #64748b;">
                    <p>Este é um e-mail automático. Por favor, não responda.</p>
                </div>
            </div>
        </body>
        </html>
        """

        part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part)

        # 4. Conexão e Envio
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            # server.set_debuglevel(1) # Descomente para debug se necessário
            server.starttls() 
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return True # Retorna booleano simples para o if sucesso: do app

    except Exception as e:
        print(f"Erro SMTP: {e}")
        return False
