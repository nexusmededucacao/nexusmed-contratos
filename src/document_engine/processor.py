import io
from docxtpl import DocxTemplate
from docx import Document

class ContractProcessor:
    """
    Motor de processamento de documentos.
    Responsável por transformar o template .docx em um contrato preenchido.
    """

    def __init__(self, template_path: str):
        self.template_path = template_path

    def generate_docx(self, context: dict, payment_rows: list) -> io.BytesIO:
        """
        Gera o documento preenchido e retorna um buffer de memória (BytesIO).
        context: Dicionário com as variáveis {{ nome }}, {{ cpf }}, etc.
        payment_rows: Lista de dicionários para a tabela de parcelas.
        """
        # 1. Primeiro usamos o DocxTemplate para variáveis simples
        doc = DocxTemplate(self.template_path)
        doc.render(context)
        
        # Salva em um buffer temporário para a segunda fase
        temp_buffer = io.BytesIO()
        doc.save(temp_buffer)
        temp_buffer.seek(0)

        # 2. Usamos python-docx para manipular a tabela sem quebrar o estilo
        return self._inject_payment_table(temp_buffer, payment_rows)

    def _inject_payment_table(self, doc_stream: io.BytesIO, rows: list) -> io.BytesIO:
        """
        Localiza a tabela de pagamentos e adiciona as linhas dinamicamente.
        Assume-se que a tabela já existe no template com o cabeçalho.
        """
        doc = Document(doc_stream)
        
        # Identificação da tabela (ex: a tabela que contém o texto 'Vencimento')
        target_table = None
        for table in doc.tables:
            if "Vencimento" in table.rows[0].cells[1].text:
                target_table = table
                break
        
        if target_table and rows:
            for item in rows:
                row_cells = target_table.add_row().cells
                row_cells[0].text = str(item.get('parcela', ''))
                row_cells[1].text = str(item.get('vencimento', ''))
                row_cells[2].text = str(item.get('valor', ''))
                # Opcional: Aplicar alinhamento ou estilo específico nas células aqui

        final_buffer = io.BytesIO()
        doc.save(final_buffer)
        final_buffer.seek(0)
        return final_buffer
