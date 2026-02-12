import re
from datetime import datetime
from decimal import Decimal

def format_cpf(cpf: str) -> str:
    """Aplica a máscara de CPF: 000.000.000-00."""
    if not cpf: return ""
    numbers = re.sub(r'\D', '', cpf)
    if len(numbers) != 11:
        return numbers
    return f"{numbers[:3]}.{numbers[3:6]}.{numbers[6:9]}-{numbers[9:]}"

def format_currency(value) -> str:
    """Formata para o padrão monetário brasileiro (R$ 1.234,56)."""
    if value is None: 
        value = 0.0
    # Converte Decimal (do Supabase) para float para evitar erro de formatação
    if isinstance(value, Decimal):
        value = float(value)
        
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def format_date_br(date_input) -> str:
    """Converte objeto date ou string ISO para DD/MM/YYYY."""
    if not date_input: return ""
    try:
        if isinstance(date_input, str):
            # Tenta converter string ISO (YYYY-MM-DD)
            date_input = datetime.strptime(date_input[:10], "%Y-%m-%d")
        return date_input.strftime("%d/%m/%Y")
    except:
        return str(date_input)

def get_full_date_ptbr() -> str:
    """Retorna a data atual por extenso para a assinatura do contrato."""
    months = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho", 
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    now = datetime.now()
    return f"{now.day} de {months[now.month - 1]} de {now.year}"

def format_phone(phone: str) -> str:
    """Formata telefone: (00) 00000-0000 ou (00) 0000-0000."""
    if not phone: return ""
    numbers = re.sub(r'\D', '', phone)
    if len(numbers) == 11:
        return f"({numbers[:2]}) {numbers[2:7]}-{numbers[7:]}"
    elif len(numbers) == 10:
        return f"({numbers[:2]}) {numbers[2:6]}-{numbers[6:]}"
    return numbers
