from src.database.connection import supabase

class AlunoRepository:
    """
    Repositório para a tabela 'alunos'.
    Campos principais: id (uuid), nome_completo, cpf, email, crm, etc.
    """

    @staticmethod
    def buscar_por_cpf(cpf: str):
        """Verifica se um CPF já existe na base."""
        # Remove pontos e traços antes de consultar, caso venha formatado
        cpf_limpo = "".join(filter(str.isdigit, cpf))
        response = supabase.table("alunos").select("*").eq("cpf", cpf_limpo).execute()
        return response.data[0] if response.data else None

    @staticmethod
    def listar_todos():
        """Lista todos os alunos para a tela de gestão."""
        response = supabase.table("alunos").select("*").order("nome_completo").execute()
        return response.data

    @staticmethod
    def criar_aluno(dados: dict):
        """
        Insere um aluno. 
        O dicionário 'dados' deve mapear exatamente os nomes das colunas no Supabase.
        """
        # Verificação defensiva
        existente = AlunoRepository.buscar_por_cpf(dados.get('cpf'))
        if existente:
            return {"error": "CPF já cadastrado no sistema."}
        
        return supabase.table("alunos").insert(dados).execute()

    @staticmethod
    def atualizar_aluno(aluno_id: str, dados: dict):
        """Atualiza os dados de um aluno existente."""
        return supabase.table("alunos").update(dados).eq("id", aluno_id).execute()

    @staticmethod
    def filtrar_por_nome(nome: str):
        """Busca dinâmica para facilitar a seleção no Gerador de Contratos."""
        response = supabase.table("alunos")\
            .select("id, nome_completo, cpf")\
            .ilike("nome_completo", f"%{nome}%")\
            .limit(10)\
            .execute()
        return response.data
