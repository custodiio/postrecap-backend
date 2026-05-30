import sys
import os

# Adiciona o diretório atual ao path para importação local do db_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db_helper

def print_help():
    print("\n--- Utilitário de Aprovação de Usuários (Post Recap) ---")
    print("Uso:")
    print("  python approve_user.py aprovar <email>   - Aprova o acesso do e-mail ao sistema")
    print("  python approve_user.py revogar <email>   - Bloqueia o acesso do e-mail ao sistema")
    print("  python approve_user.py listar            - Mostra todos os usuários e status")
    print("----------------------------------------------------\n")

def main():
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "listar":
        users = db_helper.list_users()
        if not users:
            print("\n[INFO] Nenhum usuário registrado no banco de dados ainda.")
            return
            
        print("\n--- Lista de Usuários ---")
        print(f"{'E-mail':<40} | {'Status':<12} | {'Registrado em':<20}")
        print("-" * 78)
        for user in users:
            status = "APROVADO" if user["approved"] else "PENDENTE"
            print(f"{user['email']:<40} | {status:<12} | {user['created_at']:<20}")
        print("-" * 78)
        print()

    elif command in ["aprovar", "revogar"]:
        if len(sys.argv) < 3:
            print("\n[ERRO] E-mail não especificado!")
            print(f"Uso correto: python approve_user.py {command} <email>")
            return
            
        email = sys.argv[2].strip()
        status_value = 1 if command == "aprovar" else 0
        status_name = "APROVADO" if status_value == 1 else "PENDENTE/REVOGADO"
        
        success = db_helper.set_user_approval(email, status_value)
        if success:
            print(f"\n[SUCESSO] Usuário '{email}' definido como {status_name} com sucesso!")
        else:
            print(f"\n[ERRO] Não foi possível atualizar o status do usuário '{email}'.")
            
    else:
        print(f"\n[ERRO] Comando '{command}' desconhecido.")
        print_help()

if __name__ == "__main__":
    main()
