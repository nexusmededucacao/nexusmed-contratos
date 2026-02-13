from src.database.connection import supabase
from datetime import datetime

class ContratoRepository:
    """
    Repositório para a tabela 'contratos'.
    Lida com a criação, consulta e atualização de assinaturas.
    """

    @staticmethod
    def listar_todos():
        """
        Retorna todos os contratos com dados básicos.
        """
        try:
            query = "id, status, valor_final, created_at, alunos(nome_completo, cpf), turmas(codigo_turma, cursos(nome))"
            
            response = supabase.table("contratos")\
                .select(query)\
                .order("created_at", desc=True)\
                .execute()
            return response.data
        except Exception as e:
            print(f"Erro ao listar contratos: {e}")
            return []

    @staticmethod
    def buscar_por_id_detalhado(contrato_id: str):
        """Busca todos os campos de um contrato."""
        try:
            query = "*, alunos(*), turmas(*, cursos(*))"
            response = supabase.table("contratos").select(query).eq("id", contrato_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Erro ao buscar contrato {contrato_id}: {e}")
            return None

    @staticmethod
    def buscar_por_token(token: str):
        """Busca contrato pelo token de acesso."""
        try:
            query = "*, alunos(*), turmas(*, cursos(*))"
            response = supabase.table("contratos").select(query).eq("token_acesso", token).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Erro ao buscar token {token}: {e}")
            return None

    @staticmethod
    def criar_contrato(dados: dict):
        """
        Insere um novo contrato.
        ALTERAÇÃO CRÍTICA: Se der erro, retorna um dicionário com a chave 'error'
        para que o Streamlit possa exibir o motivo na tela.
        """
        try:
            # Garante status padrão se não vier
            if "status" not in dados:
                dados["status"] = "Pendente"
            
            # Tenta inserir
            response = supabase.table("contratos").insert(dados).execute()
            
            # Se inseriu com sucesso, retorna os dados da linha criada
            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                return {"error": "O Supabase não retornou dados de confirmação."}

        except Exception as e:
            # AQUI ESTÁ A CORREÇÃO:
            # Retornamos o erro como texto para aparecer na tela do usuário
            return {"error": str(e)}

    @staticmethod
    def registrar_assinatura(contrato_id: str, payload_assinatura: dict):
        """
        Atualiza o contrato com os dados da assinatura digital.
        """
        try:
            payload_assinatura["status"] = "Assinado"
            if "data_aceite" not in payload_assinatura:
                payload_assinatura["data_aceite"] = datetime.now().isoformat()
            
            response = supabase.table("contratos")\
                .update(payload_assinatura)\
                .eq("id", contrato_id)\
                .execute()
            return True
        except Exception as e:
            print(f"Erro ao registrar assinatura: {e}")
            return False

    @staticmethod
    def atualizar_caminho_arquivo(contrato_id: str, caminho: str):
        """Salva o link do PDF gerado no storage."""
        try:
            supabase.table("contratos").update({"caminho_arquivo": caminho}).eq("id", contrato_id).execute()
            return True
        except Exception as e:
            print(f"Erro ao atualizar caminho: {e}")
            return False
