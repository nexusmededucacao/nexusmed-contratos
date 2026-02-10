import bcrypt
import streamlit as st
from src.db import supabase

def hash_senha(senha_plana):
    return bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha_plana, hash_banco):
    return bcrypt.checkpw(senha_plana.encode('utf-8'), hash_banco.encode('utf-8'))

def login_usuario(email, senha):
    try:
        response = supabase.table("usuarios").select("*").eq("email", email).eq("ativo", True).maybe_single().execute()
        usuario = response.data
        if usuario and verificar_senha(senha, usuario['senha_hash']):
            return usuario
        return None
    except Exception as e:
        st.error(f"Erro no login: {e}")
        return None

def criar_admin_inicial():
    """Cria admin/admin123 se não existir ninguém"""
    users = supabase.table("usuarios").select("count", count="exact").execute()
    if users.count == 0:
        hash_admin = hash_senha("admin123")
        supabase.table("usuarios").insert({
            "nome": "Administrador",
            "email": "admin@nexusmed.org",
            "senha_hash": hash_admin,
            "perfil": "admin"
        }).execute()
