import re
from datetime import datetime
from decimal import Decimal

def format_cpf(cpf: str) -> str:
    """Aplica a máscara de CPF: 000.000.000-00"""
    if not cpf: return ""
    # Remove qualquer caractere não numérico
    numbers = re.sub(r'\D', '', cpf)
    if len(numbers) != 11:
        return numbers  # Retorna o original se não tiver 11 dígitos
    return f"{numbers[:3]}.{numbers[3:6]}.{numbers[6:9]}-{numbers[9:]}"

def format_currency(value) -> str:
    """Formata valor numérico para o padrão monetário brasileiro (R$ 1.234,56)"""
    if value is None: value = 0.0
    
    # Converte Decimal (comum no retorno do Supabase) para float
    if isinstance(value, Decimal):
        value = float(value)
        
    # Usa um truque de substituição para formatar milhar com ponto e decimal com vírgula
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def format_date_br(date_input) -> str:
    """Converte objeto date ou string ISO (YYYY-MM-DD) para padrão brasileiro (DD/MM/YYYY)"""
    if not date_input: return ""
    try:
        if isinstance(date_input, str):
            # Trata strings que podem vir com timestamp do banco
            date_input = datetime.strptime(date_input[:10], "%Y-%m-%d")
        return date_input.strftime("%d/%m/%Y")
    except Exception:
        return str(date_input)

def get_full_date_ptbr() -> str:
    """Retorna a data atual por extenso para o fechamento do contrato"""
    months = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho", 
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    now = datetime.now()
    return f"{now.day} de {months[now.month - 1]} de {now.year}"

def format_phone(phone: str) -> str:
    """Formata telefone: (00) 00000-0000 ou (00) 0000-0000"""
    if not phone: return ""
    numbers = re.sub(r'\D', '', phone)
    if len(numbers) == 11:
        return f"({numbers[:2]}) {numbers[2:7]}-{numbers[7:]}"
    elif len(numbers) == 10:
        return f"({numbers[:2]}) {numbers[2:6]}-{numbers[6:]}"
    return numbers
