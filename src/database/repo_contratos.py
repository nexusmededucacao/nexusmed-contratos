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
        Retorna todos os contratos com dados básicos do aluno e da turma.
        """
        try:
            # Query compacta para evitar erros de parsing de string
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
        """Busca todos os campos de um contrato para preenchimento do Word."""
        try:
            # Busca profunda: Contrato -> Aluno, Contrato -> Turma -> Curso
            query = "*, alunos(*), turmas(*, cursos(*))"
            response = supabase.table("contratos").select(query).eq("id", contrato_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Erro ao buscar contrato {contrato_id}: {e}")
            return None

    @staticmethod
    def buscar_por_token(token: str):
        """Busca contrato pelo token de acesso (usado na página de assinatura)."""
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
        Insere um novo contrato e RETORNA OS DADOS CRIADOS (incluindo o ID).
        """
        try:
            if "status" not in dados:
                dados["status"] = "Pendente"
            
            response = supabase.table("contratos").insert(dados).execute()
            
            # Ajuste crítico: Retorna o dado limpo, não o objeto response
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Erro ao criar contrato: {e}")
            return None

    @staticmethod
    def registrar_assinatura(contrato_id: str, payload_assinatura: dict):
        """
        Atualiza o contrato com os dados da assinatura digital.
        """
        try:
            payload_assinatura["status"] = "Assinado"
            # Garante formato ISO para o Supabase (timestamptz)
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
