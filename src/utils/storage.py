import io
import unicodedata
import re
from src.database.connection import supabase

class StorageService:
    @staticmethod
    def sanitizar_nome(texto: str) -> str:
        if not texto: return "arquivo"
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
        limpo = re.sub(r'[^a-zA-Z0-9]', '_', sem_acento)
        return re.sub(r'_{2,}', '_', limpo).strip('_')

    @staticmethod
    def upload_minuta(pdf_buffer, nome_aluno, nome_curso):
        try:
            aluno_safe = StorageService.sanitizar_nome(nome_aluno)
            curso_safe = StorageService.sanitizar_nome(nome_curso)
            # Adicionamos um timestamp ou ID único no nome para EVITAR CACHE
            import time
            timestamp = int(time.time())
            filename = f"Minuta_{aluno_safe}_{curso_safe}_{timestamp}.pdf"
            
            # Resetamos o buffer para garantir que lemos do início
            pdf_buffer.seek(0)
            conteudo_pdf = pdf_buffer.getvalue() # Pegamos o valor binário real

            # Upload para a raiz do bucket 'contratos'
            res = supabase.storage.from_("contratos").upload(
                path=filename,
                file=conteudo_pdf,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            
            # Pegamos a URL pública gerada para este novo arquivo
            url_res = supabase.storage.from_("contratos").get_public_url(filename)
            
            # No Supabase Python, o get_public_url pode retornar uma string direta ou um objeto
            url_final = url_res if isinstance(url_res, str) else url_res.get('publicURL', url_res)
            
            return url_final, None

        except Exception as e:
            return None, str(e)
