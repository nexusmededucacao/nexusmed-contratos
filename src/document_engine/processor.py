import io
from docxtpl import DocxTemplate
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

class ContractProcessor:
    def __init__(self, template_path: str):
        self.template_path = template_path

    def generate_docx(self, context: dict, entry_rows: list, installment_rows: list) -> io.BytesIO:
        # Fase 1: Preenchimento de variáveis {{ }}
        doc_tpl = DocxTemplate(self.template_path)
        doc_tpl.render(context)
        
        temp_buffer = io.BytesIO()
        doc_tpl.save(temp_buffer)
        temp_buffer.seek(0)

        # Fase 2: Injeção das Tabelas (Seção 03 e 04)
        return self._inject_payment_tables(temp_buffer, entry_rows, installment_rows)

    def _inject_payment_tables(self, doc_stream: io.BytesIO, entry_data: list, installment_data: list) -> io.BytesIO:
        doc = Document(doc_stream)
        
        # Filtra tabelas financeiras (aquelas que têm 'Vencimento' no cabeçalho)
        payment_tables = []
        for table in doc.tables:
            try:
                header_text = table.rows[0].cells[1].text.upper()
                if "VENCIMENTO" in header_text:
                    payment_tables.append(table)
            except:
                continue
        
        # 1ª Tabela encontrada no Word = Entrada (Cláusula 5ª)
        if len(payment_tables) > 0 and entry_data:
            self._fill_table_rows(payment_tables[0], entry_data)

        # 2ª Tabela encontrada no Word = Saldo (Cláusula 6ª)
        if len(payment_tables) > 1 and installment_data:
            self._fill_table_rows(payment_tables[1], installment_data)

        final_buffer = io.BytesIO()
        doc.save(final_buffer)
        final_buffer.seek(0)
        return final_buffer

    def _fill_table_rows(self, table, data_rows: list):
        # Limpa linhas residuais mantendo apenas o cabeçalho
        while len(table.rows) > 1:
            table._element.remove(table.rows[-1]._element)

        for item in data_rows:
            row = table.add_row()
            # Mapeia para as colunas: Parcela | Vencimento | Valor | Forma
            valores = [
                str(item.get('numero', item.get('n', ''))),
                str(item.get('data', item.get('vencimento', ''))),
                str(item.get('valor', '')),
                str(item.get('forma', ''))
            ]

            for i, texto in enumerate(valores):
                cell = row.cells[i]
                paragraph = cell.paragraphs[0]
                paragraph.clear()
                run = paragraph.add_run(texto)
                run.font.name = 'Arial'
                run.font.size = Pt(10)
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
