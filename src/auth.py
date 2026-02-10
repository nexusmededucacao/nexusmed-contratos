import bcrypt
from src.db import supabase

def hash_senha(senha_plana):
    """Gera o hash da senha usando bcrypt"""
    # Garante que a senha seja string antes de converter para bytes
    senha_bytes = str(senha_plana).encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode('utf-8')

def verificar_senha(senha_plana, senha_hash):
    """Verifica se a senha bate com o hash"""
    try:
        senha_bytes = str(senha_plana).encode('utf-8')
        hash_bytes = str(senha_hash).encode('utf-8')
        return bcrypt.checkpw(senha_bytes, hash_bytes)
    except Exception as e:
        print(f"Erro na verificação de senha: {e}")
        return False

def login_usuario(email, senha):
    """Tenta logar e retorna o usuário se sucesso"""
    try:
        # Busca usuário pelo email
        response = supabase.table("usuarios").select("*").eq("email", email).execute()
        
        # Verifica se encontrou alguém e se a lista não está vazia
        if not response.data or len(response.data) == 0:
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
    """Cria admin/admin123 se não existir ninguém"""
    try:
        # Tenta verificar se tem usuários
        response = supabase.table("usuarios").select("count", count="exact").execute()
        
        # Se o banco estiver vazio (count = 0), cria o admin
        if response.count == 0:
            print("Criando usuário admin inicial...")
            hash_admin = hash_senha("admin123")
            supabase.table("usuarios").insert({
                "email": "admin@nexusmed.org",
                "senha_hash": hash_admin,
                "nome": "Administrador",
                "perfil": "admin"
            }).execute()
            print("✅ Usuário Admin criado com sucesso.")
            
    except Exception as e:
        # Ignora erro de conexão na inicialização para não travar o app
        print(f"⚠️ Aviso (Admin Inicial): {e}")
        pass
