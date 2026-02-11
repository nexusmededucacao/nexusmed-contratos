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
        Equivalente a um JOIN entre contratos, alunos e turmas.
        """
        query = """
            id, status, valor_final, created_at,
            alunos(nome_completo, cpf),
            turmas(codigo_turma, cursos(nome))
        """
        response = supabase.table("contratos").select(query).order("created_at", desc=True).execute()
        return response.data

    @staticmethod
    def buscar_por_id_detalhado(contrato_id: str):
        """Busca todos os campos de um contrato para preenchimento do Word."""
        query = "*, alunos(*), turmas(*, cursos(*))"
        response = supabase.table("contratos").select(query).eq("id", contrato_id).execute()
        return response.data[0] if response.data else None

    @staticmethod
    def buscar_por_token(token: str):
        """Busca contrato pelo token de acesso (usado na página de assinatura)."""
        query = "*, alunos(*), turmas(*, cursos(*))"
        response = supabase.table("contratos").select(query).eq("token_acesso", token).execute()
        return response.data[0] if response.data else None

    @staticmethod
    def criar_contrato(dados: dict):
        """
        Insere um novo contrato.
        O campo 'status' deve ser 'Pendente' por padrão.
        """
        if "status" not in dados:
            dados["status"] = "Pendente"
        return supabase.table("contratos").insert(dados).execute()

    @staticmethod
    def registrar_assinatura(contrato_id: str, payload_assinatura: dict):
        """
        Atualiza o contrato com os dados da assinatura digital.
        payload_assinatura deve conter: ip_aceite, hash_aceite, recibo_aceite_texto, data_aceite
        """
        payload_assinatura["status"] = "Assinado"
        payload_assinatura["data_aceite"] = datetime.now().isoformat()
        
        return supabase.table("contratos")\
            .update(payload_assinatura)\
            .eq("id", contrato_id)\
            .execute()

    @staticmethod
    def atualizar_caminho_arquivo(contrato_id: str, caminho: str):
        """Salva o link do PDF gerado no storage."""
        return supabase.table("contratos").update({"caminho_arquivo": caminho}).eq("id", contrato_id).execute()
