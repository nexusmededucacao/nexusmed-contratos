import io
import unicodedata
import re
import streamlit as st
from src.database.connection import supabase

class StorageService:
    @staticmethod
    def sanitizar_nome(texto: str) -> str:
        """Remove acentos, espaços e caracteres especiais para nomes de arquivos."""
        if not texto: return "arquivo"
        # Normaliza (ex: João -> Joao)
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
        # Remove tudo que não for letra ou número e troca espaço por _
        limpo = re.sub(r'[^a-zA-Z0-9]', '_', sem_acento)
        # Remove underscores duplicados
        return re.sub(r'_{2,}', '_', limpo).strip('_')

    @staticmethod
    def upload_minuta(file_bytes: io.BytesIO, nome_aluno: str, nome_curso: str):
        """
        Sobe o PDF para o bucket 'contratos' e retorna o caminho e nome.
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

            # Upload Supabase com tratamento de erro específico
            supabase.storage.from_("contratos").upload(
                path=path,
                file=file_bytes.getvalue(),
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            
            return path, filename
        except Exception as e:
            st.error(f"Erro ao fazer upload para o Storage: {e}")
            return None, None

    @staticmethod
    def obter_url_publica(path: str) -> str:
        """Gera a URL pública para acesso ao documento."""
        try:
            res = supabase.storage.from_("contratos").get_public_url(path)
            return res
        except Exception as e:
            print(f"Erro ao obter URL: {e}")
            return None
