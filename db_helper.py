import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
DB_PATH = os.path.join(DB_DIR, "users.db")

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de usuários e status de aprovação
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS approved_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        approved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Tabela de conexões do TikTok OAuth 2.0 por e-mail de usuário
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tiktok_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        access_token TEXT NOT NULL,
        refresh_token TEXT,
        open_id TEXT,
        username TEXT,
        avatar TEXT,
        connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(email) REFERENCES approved_users(email)
    )
    """)
    
    # Tabela de conexões do YouTube por e-mail de usuário
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS youtube_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        access_token TEXT NOT NULL,
        refresh_token TEXT,
        channel_id TEXT,
        channel_name TEXT,
        avatar TEXT,
        connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(email) REFERENCES approved_users(email)
    )
    """)
    
    # Tenta adicionar a coluna refresh_token caso a tabela já exista sem ela
    try:
        cursor.execute("ALTER TABLE tiktok_connections ADD COLUMN refresh_token TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE youtube_connections ADD COLUMN refresh_token TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()
    print("[DB] Banco de dados inicializado com sucesso em:", DB_PATH)

def check_user_approval(email: str) -> bool:
    """
    Verifica se o e-mail do Firebase está na lista de aprovados.
    Se não estiver registrado, insere como pendente (approved = 0).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT approved FROM approved_users WHERE email = ?", (email,))
    row = cursor.fetchone()
    
    if row is None:
        # Registra novo usuário como pendente
        cursor.execute("INSERT INTO approved_users (email, approved) VALUES (?, 0)", (email,))
        conn.commit()
        conn.close()
        print(f"[DB] Novo usuário registrado como pendente: {email}")
        return False
        
    conn.close()
    return row[0] == 1

def set_user_approval(email: str, approved_status: int) -> bool:
    """
    Aprova (1) ou desaprova (0) um e-mail de usuário.
    Retorna True se alterado com sucesso.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Garante que o usuário existe
    cursor.execute("SELECT id FROM approved_users WHERE email = ?", (email,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO approved_users (email, approved) VALUES (?, ?)", (email, approved_status))
    else:
        cursor.execute("UPDATE approved_users SET approved = ?, updated_at = CURRENT_TIMESTAMP WHERE email = ?", (approved_status, email))
        
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def list_users():
    """Retorna a lista de todos os usuários registrados no sistema."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, approved, created_at FROM approved_users ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"email": r[0], "approved": bool(r[1]), "created_at": r[2]} for r in rows]

def save_tiktok_connection(email: str, access_token: str, refresh_token: str = None, open_id: str = None, username: str = None, avatar: str = None):
    """Salva ou atualiza os tokens e detalhes da conta do TikTok do usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM tiktok_connections WHERE email = ?", (email,))
    row = cursor.fetchone()
    
    if row:
        if refresh_token:
            cursor.execute("""
            UPDATE tiktok_connections 
            SET access_token = ?, refresh_token = ?, open_id = ?, username = ?, avatar = ?, connected_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """, (access_token, refresh_token, open_id, username, avatar, email))
        else:
            cursor.execute("""
            UPDATE tiktok_connections 
            SET access_token = ?, open_id = ?, username = ?, avatar = ?, connected_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """, (access_token, open_id, username, avatar, email))
    else:
        cursor.execute("""
        INSERT INTO tiktok_connections (email, access_token, refresh_token, open_id, username, avatar)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (email, access_token, refresh_token, open_id, username, avatar))
        
    conn.commit()
    conn.close()
    print(f"[DB] Conexão TikTok salva para o usuário: {email}")

def get_tiktok_connection(email: str):
    """Busca as credenciais conectadas do TikTok para o e-mail do usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT access_token, refresh_token, open_id, username, avatar FROM tiktok_connections WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "access_token": row[0],
            "refresh_token": row[1],
            "open_id": row[2],
            "username": row[3],
            "avatar": row[4]
        }
    return None

def delete_tiktok_connection(email: str):
    """Remove a conexão do TikTok do usuário (Disconnect)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tiktok_connections WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    print(f"[DB] Conexão TikTok removida para o usuário: {email}")

def save_youtube_connection(email: str, access_token: str, refresh_token: str = None, channel_id: str = None, channel_name: str = None, avatar: str = None):
    """Salva ou atualiza os tokens e detalhes da conta do YouTube do usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM youtube_connections WHERE email = ?", (email,))
    row = cursor.fetchone()
    
    if row:
        if refresh_token:
            cursor.execute("""
            UPDATE youtube_connections 
            SET access_token = ?, refresh_token = ?, channel_id = ?, channel_name = ?, avatar = ?, connected_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """, (access_token, refresh_token, channel_id, channel_name, avatar, email))
        else:
            cursor.execute("""
            UPDATE youtube_connections 
            SET access_token = ?, channel_id = ?, channel_name = ?, avatar = ?, connected_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """, (access_token, channel_id, channel_name, avatar, email))
    else:
        cursor.execute("""
        INSERT INTO youtube_connections (email, access_token, refresh_token, channel_id, channel_name, avatar)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (email, access_token, refresh_token, channel_id, channel_name, avatar))
        
    conn.commit()
    conn.close()
    print(f"[DB] Conexão YouTube salva para o usuário: {email}")

def get_youtube_connection(email: str):
    """Busca as credenciais conectadas do YouTube para o e-mail do usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT access_token, refresh_token, channel_id, channel_name, avatar FROM youtube_connections WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "access_token": row[0],
            "refresh_token": row[1],
            "channel_id": row[2],
            "channel_name": row[3],
            "avatar": row[4]
        }
    return None

def delete_youtube_connection(email: str):
    """Remove a conexão do YouTube do usuário (Disconnect)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM youtube_connections WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    print(f"[DB] Conexão YouTube removida para o usuário: {email}")

# Inicializa o banco de dados local
init_db()
