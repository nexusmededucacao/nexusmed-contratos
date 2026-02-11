import streamlit as st
import bcrypt
from src.database.repo_usuarios import UsuarioRepository

# Proteção de Acesso: Apenas Admins devem gerenciar usuários
if not st.session_state.get("authenticated"):
    st.error("Acesso negado.")
    st.stop()

if st.session_state.get("user_perfil") != "admin":
    st.warning("Você não tem permissão de administrador para acessar esta página.")
    st.stop()

def main():
    st.title("👥 Gestão de Usuários do Sistema")
    
    tab_lista, tab_novo = st.tabs(["Usuários Ativos", "Cadastrar Novo Usuário"])

    # --- ABA: LISTAGEM ---
    with tab_lista:
        usuarios = UsuarioRepository.listar_todos()
        if usuarios:
            # Cabeçalho da tabela
            col_n, col_e, col_p, col_a = st.columns([2, 2, 1, 1])
            col_n.write("**Nome**")
            col_e.write("**E-mail**")
            col_p.write("**Perfil**")
            col_a.write("**Ações**")
            st.write("---")

            for user in usuarios:
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                c1.write(user['nome'])
                c2.write(user['email'])
                c3.write(f"`{user['perfil']}`")
                
                # Botão para alternar status (Ativo/Inativo)
                label_status = "Desativar" if user['ativo'] else "Ativar"
                if c4.button(label_status, key=f"st_{user['id']}"):
                    UsuarioRepository.atualizar_status(user['id'], not user['ativo'])
                    st.toast(f"Status de {user['nome']} atualizado!")
                    st.rerun()
        else:
            st.info("Nenhum usuário cadastrado.")

    # --- ABA: CADASTRAR NOVO ---
    with tab_novo:
        with st.form("form_registro_user", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            email = st.text_input("E-mail (Será o login)")
            senha = st.text_input("Senha Provisória", type="password")
            perfil = st.selectbox("Perfil de Acesso", ["admin", "operador"])
            
            if st.form_submit_button("Criar Conta"):
                if nome and email and senha:
                    # Engenharia de Segurança: Gerando o Hash antes do Insert
                    hashed = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    
                    dados_user = {
                        "nome": nome,
                        "email": email,
                        "senha_hash": hashed,
                        "perfil": perfil,
                        "ativo": True
                    }
                    
                    try:
                        UsuarioRepository.criar_usuario(dados_user)
                        st.success(f"Usuário {nome} criado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao criar usuário: {e}")
                else:
                    st.warning("Preencha todos os campos obrigatórios.")

if __name__ == "__main__":
    main()
