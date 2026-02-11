from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def criar():
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(10)

    doc.add_heading('02 DO PRODUTO CONTRATADO', level=2)
    
    # Tabela de Produto (Resolvendo o problema dos campos em branco)
    table = doc.add_table(rows=8, cols=1)
    table.style = 'Table Grid'
    
    dados = [
        "Curso: {{ pos_graduacao }}",
        "Formato: {{ formato_curso }}",
        "Turma: {{ turma }}",
        "Aula com atendimento a paciente real: {{ atendimento }}",
        "Bolsista: {{ bolsista }}",
        "Valor bruto do Curso: R$ {{ valor_curso }}",
        "Desconto concedido: R$ {{ valor_desconto }} ({{ pencentual_desconto }})",
        "Valor Final do Curso: R$ {{ valor_final }}"
    ]
    
    for i, linha in enumerate(dados):
        table.rows[i].cells[0].text = linha

    doc.add_paragraph('\n03. FORMA DE PAGAMENTO - ENTRADA')
    
    # Tabela Entrada (Resolvendo a Sopa de Letras)
    t_ent = doc.add_table(rows=2, cols=4)
    t_ent.style = 'Table Grid'
    hdr = t_ent.rows[0].cells
    hdr[0].text = "PARCELA"; hdr[1].text = "VENCIMENTO"; hdr[2].text = "VALOR"; hdr[3].text = "FORMA"
    
    row = t_ent.rows[1].cells
    # O SEGREDO: O loop começa e termina na mesma linha
    row[0].paragraphs[0].add_run('{% for p in tbl_entrada %}{{ p.numero }}')
    row[1].text = '{{ p.data_vencimento }}'
    row[2].text = '{{ p.valor }}'
    row[3].paragraphs[0].add_run('{{ p.forma_pagamento }}{% endfor %}')

    doc.add_paragraph('\n04. FORMA DE PAGAMENTO - SALDO')
    
    t_sal = doc.add_table(rows=2, cols=4)
    t_sal.style = 'Table Grid'
    hdr2 = t_sal.rows[0].cells
    hdr2[0].text = "PARCELA"; hdr2[1].text = "VENCIMENTO"; hdr2[2].text = "VALOR"; hdr2[3].text = "FORMA"
    
    row2 = t_sal.rows[1].cells
    row2[0].paragraphs[0].add_run('{% for p in tbl_saldo %}{{ p.numero }}')
    row2[1].text = '{{ p.data_vencimento }}'
    row2[2].text = '{{ p.valor }}'
    row2[3].paragraphs[0].add_run('{{ p.forma_pagamento }}{% endfor %}')

    doc.add_paragraph('\nCLÁUSULA MATERIAL DIDÁTICO')
    doc.add_paragraph('O material didático representará R$ {{ valor_material }}, correspondente a 30%...')

    doc.save('assets/modelo_contrato_V2.docx')
    print("Template Limpo Gerado com Sucesso!")

if __name__ == "__main__":
    criar()
