import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

def obter_url_app():
    """
    Detecta a URL base do aplicativo para gerar links de assinatura.
    """
    try:
        # 1. Prioridade: Configuração manual no secrets.toml
        if "app" in st.secrets and "base_url" in st.secrets["app"]:
            return st.secrets["app"]["base_url"].rstrip('/')
    except: pass
    
    try:
        # 2. Detecção automática via headers do Streamlit (Cloud/Linux)
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            host = st.context.headers.get('Host', '')
            if host: return f"https://{host}"
    except: pass
    
    # 3. Fallback para desenvolvimento local
    return "http://localhost:8501"

def enviar_email_contrato(email_destinatario: str, nome_aluno: str, nome_curso: str, token: str):
    """
    Envia o link de assinatura para o aluno via SMTP.
    """
    try:
        # 1. Monta o Link usando a página oculta 'Assinatura'
        base_url = obter_url_app()
        link_completo = f"{base_url}/Assinatura?token={token}"

        # 2. Configurações SMTP do secrets.toml
        smtp_host = st.secrets["email"]["smtp_host"]
        smtp_port = int(st.secrets["email"]["smtp_port"]) # Garante inteiro
        smtp_user = st.secrets["email"]["smtp_user"]
        smtp_pass = st.secrets["email"]["smtp_password"]

        # 3. Cria a Mensagem Multipart
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Assinatura Pendente: Contrato {nome_curso}"
        msg['From'] = f"NexusMed Secretaria <{smtp_user}>"
        msg['To'] = email_destinatario

        # 4. Template HTML estilizado
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
                        
                        <a href="{link_completo}" style="background-color: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                            ✍️ REVISAR E ASSINAR AGORA
                        </a>
                    </div>
                    
                    <p style="font-size: 11px; color: #94a3b8;">Caso o botão não funcione, utilize o link: <br> {link_completo}</p>
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

        # 5. Conexão e Envio
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.set_debuglevel(0)
            server.starttls() # Criptografia TLS
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return {"success": True, "message": "Link de assinatura enviado com sucesso!"}

    except Exception as e:
        return {"success": False, "message": f"Erro ao enviar e-mail: {str(e)}"}
