import bcrypt
from src.db import supabase

def hash_senha(senha_plana):
    """Gera o hash da senha usando bcrypt"""
    return bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha_plana, senha_hash):
    """Verifica se a senha bate com o hash"""
    return bcrypt.checkpw(senha_plana.encode('utf-8'), senha_hash.encode('utf-8'))

def login_usuario(email, senha):
    """Tenta logar e retorna o usuário se sucesso"""
    try:
        # Busca usuário pelo email
        response = supabase.table("usuarios").select("*").eq("email", email).execute()
        
        # Verifica se encontrou alguém
        if not response.data:
            return None
            
        user = response.data[0]
        
        # Verifica a senha
        if verificar_senha(senha, user['senha_hash']):
            return user
        else:
            return None
    except Exception as e:
        print(f"Erro no login: {e}")
        return None

def criar_admin_inicial():
    """Cria admin/admin123 se não existir ninguém (com proteção contra falha de conexão)"""
    try:
        # Tenta verificar se tem usuários
        response = supabase.table("usuarios").select("count", count="exact").execute()
        
        # Se o banco estiver vazio (count = 0), cria o admin
        if response.count == 0:
            hash_admin = hash_senha("admin123")
            supabase.table("usuarios").insert({
                "email": "admin@nexusmed.org",
                "senha_hash": hash_admin,
                "nome": "Administrador",
                "perfil": "admin"
            }).execute()
            print("✅ Usuário Admin criado com sucesso.")
            
    except Exception as e:
        # Se der erro de conexão aqui, APENAS IGNORA e deixa o app abrir.
        # Isso evita o erro "Resource unavailable" na tela inicial.
        print(f"⚠️ Aviso: Não foi possível verificar Admin inicial: {e}")
        pass
