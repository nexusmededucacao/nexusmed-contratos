# --- LÓGICA DE BUSCA HÍBRIDA ---
            if any(char.isdigit() for char in busca):
                alunos = AlunoRepository.buscar_por_cpf(busca)
                if not alunos:
                    alunos = AlunoRepository.filtrar_por_nome(busca)
            else:
                alunos = AlunoRepository.filtrar_por_nome(busca)
