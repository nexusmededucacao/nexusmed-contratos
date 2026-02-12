import io
import unicodedata
import re
from src.database.connection import supabase

class StorageService:
    @staticmethod
    def sanitizar_nome(texto: str) -> str:
        """Remove acentos, espaços e caracteres especiais."""
        # Normaliza (ex: João -> Joao)
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
        # Remove tudo que não for letra ou número e troca espaço por _
        limpo = re.sub(r'[^a-zA-Z0-9]', '_', sem_acento)
        return limpo

    @staticmethod
    def upload_minuta(file_bytes: io.BytesIO, nome_aluno: str, nome_curso: str) -> str:
        """
        Sobe o PDF para o bucket 'contratos' e retorna o caminho.
        Nome formato: Minuta_NomeAluno_NomeCurso.pdf
        """
        try:
            # Prepara o nome do arquivo
            aluno_safe = StorageService.sanitizar_nome(nome_aluno)
            curso_safe = StorageService.sanitizar_nome(nome_curso)
            filename = f"Minuta_{aluno_safe}_{curso_safe}.pdf"
            path = f"minutas/{filename}"

            # Garante ponteiro no início
            file_bytes.seek(0)

            # Upload Supabase
            supabase.storage.from_("contratos").upload(
                path=path,
                file=file_bytes.getvalue(),
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            
            return path, filename
        except Exception as e:
            print(f"Erro Storage: {e}")
            return None, None
