def criar_admin_inicial():
    """Cria admin/admin123 se não existir ninguém"""
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
