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
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
        limpo = re.sub(r'[^a-zA-Z0-9]', '_', sem_acento)
        return re.sub(r'_{2,}', '_', limpo).strip('_')

    @staticmethod
    def upload_minuta(file_bytes: io.BytesIO, nome_aluno: str, nome_curso: str):
        """
        Sobe o PDF para o bucket 'contratos' e retorna a URL pública.
        """
        try:
            # Prepara o nome do arquivo (Salvaremos na RAIZ do bucket)
            aluno_safe = StorageService.sanitizar_nome(nome_aluno)
            curso_safe = StorageService.sanitizar_nome(nome_curso)
            filename = f"Minuta_{aluno_safe}_{curso_safe}.pdf"
            
            # Garante ponteiro no início antes de ler
            file_bytes.seek(0)
            data = file_bytes.read()

            # Upload Supabase
            # Usamos o filename direto no path para salvar na raiz
            supabase.storage.from_("contratos").upload(
                path=filename,
                file=data,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            
            # Busca a URL pública imediatamente
            url_publica = supabase.storage.from_("contratos").get_public_url(filename)
            
            return url_publica, None

        except Exception as e:
            # Retorna o erro para ser tratado pela página 01_Gerar_Contrato.py
            return None, str(e)

    @staticmethod
    def obter_url_publica(path: str) -> str:
        """Gera a URL pública para acesso ao documento."""
        try:
            res = supabase.storage.from_("contratos").get_public_url(path)
            return res
        except Exception as e:
            print(f"Erro ao obter URL: {e}")
            return None
