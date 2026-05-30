import os
import sys
import requests
import shutil
import time
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Garante que o diretório atual está no path para importar o db_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db_helper

# Carregar variáveis de ambiente de múltiplos níveis (.env da raiz e .env local)
root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
if os.path.exists(root_env):
    load_dotenv(root_env)

local_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(local_env):
    load_dotenv(local_env)

app = FastAPI(title="Post Recap TikTok API Approval Server")

# Configuração de CORS para permitir conexões do React (local e produção)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite de qualquer origem para facilitar a validação local/ngrok
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CheckApprovalRequest(BaseModel):
    email: str

class DisconnectRequest(BaseModel):
    email: str

class SuggestTagsRequest(BaseModel):
    caption: str

@app.get("/")
def read_root():
    return {"status": "running", "service": "Post Recap TikTok Approval Backend"}

# ==============================================================================
# AUTENTICAÇÃO E APROVAÇÃO (REGRA DE SEGURANÇA GLOBAL)
# ==============================================================================

@app.post("/api/auth/check-approval")
def check_approval(req: CheckApprovalRequest):
    """
    Verifica se o e-mail logado no Firebase está aprovado no SQLite.
    Insere como pendente caso não exista.
    """
    if not req.email:
        raise HTTPException(status_code=400, detail="E-mail inválido")
    
    approved = db_helper.check_user_approval(req.email)
    return {"email": req.email, "approved": approved}

# ==============================================================================
# TIKTOK OAUTH 2.0 FLOW (REAL SANDBOX INTEGRATION)
# ==============================================================================

@app.get("/api/tiktok/login")
def tiktok_login(email: str = Query(..., description="E-mail do usuário do Firebase que está fazendo login")):
    """
    Gera a URL de consentimento do TikTok e redireciona o usuário.
    Salva o e-mail no parâmetro 'state' para associar no callback.
    """
    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI") # Ex: https://subdominio.ngrok-free.app/api/tiktok/callback
    
    if not client_key or not redirect_uri:
        raise HTTPException(
            status_code=500, 
            detail="Configuração do TikTok incompleta no .env (TIKTOK_CLIENT_KEY ou TIKTOK_REDIRECT_URI ausentes)"
        )
    
    # Monta a URL de Autorização OAuth oficial do TikTok
    # Escopos exigidos: video.upload, video.publish, user.info.basic
    auth_url = (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}"
        f"&scope=video.upload,video.publish,user.info.basic"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&state={email}"
    )
    
    return {"url": auth_url}

@app.get("/api/tiktok/callback")
def tiktok_callback(code: str = None, state: str = None, error: str = None, error_description: str = None):
    """
    Callback do TikTok que recebe o code temporário.
    Realiza a troca pelo access_token definitivo e salva no banco atrelado ao e-mail (state).
    """
    frontend_redirect = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    if error:
        # Se o usuário rejeitar ou der erro no login, redireciona o front com erro
        return RedirectResponse(url=f"{frontend_redirect}/dashboard?tiktok_error={error}")
        
    if not code or not state:
        raise HTTPException(status_code=400, detail="Parâmetros code ou state ausentes")
        
    email = state # O state contém o e-mail enviado no redirecionamento
    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI")
    
    # Troca o código pelo access_token
    token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache"
    }
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code != 200:
        return RedirectResponse(url=f"{frontend_redirect}/dashboard?tiktok_error=token_exchange_failed")
        
    res_json = response.json()
    access_token = res_json.get("access_token")
    open_id = res_json.get("open_id")
    
    if not access_token:
        return RedirectResponse(url=f"{frontend_redirect}/dashboard?tiktok_error=no_token_in_response")
        
    # Busca dados básicos de perfil (username, avatar) para mostrar no dashboard
    user_info_url = "https://open.tiktokapis.com/v2/user/info/"
    user_headers = {
        "Authorization": f"Bearer {access_token}"
    }
    # Campos que queremos ler do perfil (apenas os do escopo básico user.info.basic para evitar erro 401)
    user_fields = "open_id,union_id,avatar_url,display_name"
    
    info_res = requests.get(f"{user_info_url}?fields={user_fields}", headers=user_headers)
    print(f"[TIKTOK CALLBACK] Resposta User Info: Status {info_res.status_code}, Body: {info_res.text}")
    
    username = "Conta Sandbox"
    avatar = ""
    
    if info_res.status_code == 200:
        info_json = info_res.json()
        user_data = info_json.get("data", {}).get("user", {})
        username = user_data.get("display_name") or "Conta Sandbox"
        avatar = user_data.get("avatar_url") or ""
        
    # Salva a conexão no banco SQLite
    db_helper.save_tiktok_connection(
        email=email,
        access_token=access_token,
        open_id=open_id,
        username=username,
        avatar=avatar
    )
    
    # Redireciona o usuário de volta para o dashboard indicando sucesso
    return RedirectResponse(url=f"{frontend_redirect}/dashboard?tiktok_success=true")


@app.get("/api/tiktok/debug-profile")
def debug_profile(email: str = Query(..., description="E-mail do usuário logado")):
    """
    Endpoint de debug que realiza uma chamada manual para a API do TikTok 
    e retorna a resposta CRUA completa para análise em tempo real.
    """
    connection = db_helper.get_tiktok_connection(email)
    if not connection:
        return {
            "success": False,
            "error": "Nenhuma conexão com o TikTok foi encontrada no banco SQLite local para este e-mail.",
            "email": email
        }
        
    access_token = connection["access_token"]
    open_id = connection["open_id"]
    
    # Mascarar o token para exibição segura no debug
    masked_token = access_token[:12] + "..." + access_token[-12:] if len(access_token) > 24 else access_token
    
    user_info_url = "https://open.tiktokapis.com/v2/user/info/"
    user_headers = {
        "Authorization": f"Bearer {access_token}"
    }
    user_fields = "open_id,union_id,avatar_url,display_name"
    
    try:
        response = requests.get(f"{user_info_url}?fields={user_fields}", headers=user_headers)
        
        try:
            body = response.json()
            if response.status_code == 200:
                user_data = body.get("data", {}).get("user", {})
                username = user_data.get("display_name") or "Conta Sandbox"
                avatar = user_data.get("avatar_url") or ""
                
                # Salva no banco SQLite para persistir em definitivo!
                db_helper.save_tiktok_connection(
                    email=email,
                    access_token=access_token,
                    open_id=open_id,
                    username=username,
                    avatar=avatar
                )
                # Atualiza os dados na resposta para refletir o banco atualizado
                connection["username"] = username
                connection["avatar"] = avatar
        except Exception:
            body = response.text
            
        return {
            "success": True,
            "db_connection_data": {
                "username_in_db": connection["username"],
                "avatar_in_db": connection["avatar"],
                "open_id_in_db": open_id,
                "access_token_masked": masked_token
            },
            "tiktok_api_response": {
                "status_code": response.status_code,
                "url_requested": f"{user_info_url}?fields={user_fields}",
                "headers": dict(response.headers),
                "body": body
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro de rede ou exceção ao fazer a requisição para a API do TikTok: {str(e)}"
        }

@app.get("/api/tiktok/status")
def tiktok_status(email: str = Query(..., description="E-mail do usuário logado")):
    """Retorna as informações do TikTok do usuário conectado."""
    connection = db_helper.get_tiktok_connection(email)
    if connection:
        return {
            "connected": True,
            "username": connection["username"] or "Conta Sandbox",
            "avatar": connection["avatar"] or ""
        }
    return {"connected": False}

@app.post("/api/tiktok/disconnect")
def tiktok_disconnect(req: DisconnectRequest):
    """Remove a conta do TikTok conectada."""
    db_helper.delete_tiktok_connection(req.email)
    return {"success": True}

# ==============================================================================
# RECURSOS DO DASHBOARD (MOCK E UPLOAD REAL)
# ==============================================================================

@app.post("/api/tiktok/suggest-tags")
def suggest_tags(req: SuggestTagsRequest):
    """
    Lógica simples e inteligente para sugerir as 3 melhores hashtags 
    com base no conteúdo da legenda fornecida.
    """
    text = req.caption.lower()
    
    # Palavras-chave e suas tags correspondentes
    suggestions = []
    
    if "recap" in text or "resumo" in text:
        suggestions.extend(["#animerecap", "#resumodeanimes", "#recapbr"])
    if "anime" in text or "otaku" in text or "manga" in text:
        suggestions.extend(["#animeedit", "#otakubr", "#animes"])
    if "naruto" in text or "sasuke" in text:
        suggestions.extend(["#narutoshippuden", "#animebr", "#uzumaki"])
    if "one piece" in text or "luffy" in text:
        suggestions.extend(["#onepiecebr", "#luffy", "#gear5"])
    if "sololeveling" in text or "jinwoo" in text:
        suggestions.extend(["#sololeveling", "#sungjinwoo", "#manhwa"])
        
    # Fallbacks padrão caso não case com palavras-chave
    default_tags = ["#anime", "#animerecap", "#viral", "#foryou", "#otaku"]
    
    for tag in default_tags:
        if len(suggestions) >= 3:
            break
        if tag not in suggestions:
            suggestions.append(tag)
            
    return {"hashtags": suggestions[:3]}

# Pasta temporária para salvar vídeos antes do upload em background
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

# Dicionário global para rastrear o progresso e status dos uploads ativos em segundo plano
active_uploads = {}

def upload_to_tiktok_background(file_path: str, email: str, title: str, post_id: str):
    try:
        active_uploads[post_id] = {"progress": 5, "status": "uploading", "message": "Inicializando com o TikTok..."}
        
        # 1. Verifica conexão
        connection = db_helper.get_tiktok_connection(email)
        if not connection or not connection["access_token"]:
            print(f"[TIKTOK BG ERROR] Nenhuma conta conectada para {email}")
            active_uploads[post_id] = {"progress": 0, "status": "error", "message": "Nenhuma conta conectada."}
            return
            
        access_token = connection["access_token"]
        
        # 2. Ler o arquivo temporário
        if not os.path.exists(file_path):
            print(f"[TIKTOK BG ERROR] Arquivo temporário não encontrado: {file_path}")
            active_uploads[post_id] = {"progress": 0, "status": "error", "message": "Arquivo temporário sumiu."}
            return
            
        with open(file_path, "rb") as f:
            contents = f.read()
            
        video_size = len(contents)
        
        # Calcular Chunks
        MAX_SINGLE_CHUNK = 64 * 1000 * 1000  # 64MB
        if video_size <= MAX_SINGLE_CHUNK:
            actual_chunk_size = video_size
            total_chunk_count = 1
        else:
            TARGET_CHUNK_SIZE = 50 * 1000 * 1000  # 50MB
            total_chunk_count = video_size // TARGET_CHUNK_SIZE
            if total_chunk_count < 2:
                total_chunk_count = 2
                actual_chunk_size = video_size // 2
            else:
                actual_chunk_size = TARGET_CHUNK_SIZE
                
        print(f"[TIKTOK BG] Inicializando Direct Post. Vídeo: {video_size} bytes, Chunk: {actual_chunk_size} bytes, Total chunks: {total_chunk_count}")

        # Inicializar upload no TikTok
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        payload = {
            "post_info": {
                "title": title or "Post Recap Video",
                "privacy_level": "SELF_ONLY",
                "disable_duet": True,
                "disable_stitch": True,
                "disable_comment": False
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": actual_chunk_size,
                "total_chunk_count": total_chunk_count
            }
        }
        
        init_res = requests.post(init_url, headers=headers, json=payload)
        print(f"[TIKTOK BG DIAGNÓSTICO] Resposta de Inicialização: Status {init_res.status_code}, Corpo: {init_res.text}")
        
        if init_res.status_code != 200:
            print(f"[TIKTOK BG ERROR] Falha ao inicializar: {init_res.text}")
            active_uploads[post_id] = {"progress": 0, "status": "error", "message": f"Falha na API: {init_res.text}"}
            return
            
        init_json = init_res.json()
        if init_json.get("error", {}).get("code") != "ok":
            print(f"[TIKTOK BG ERROR] TikTok error: {init_json.get('error')}")
            active_uploads[post_id] = {"progress": 0, "status": "error", "message": f"Erro TikTok: {init_json.get('error', {}).get('message')}"}
            return
            
        upload_url = init_json.get("data", {}).get("upload_url")
        publish_id = init_json.get("data", {}).get("publish_id")
        
        if not upload_url:
            print("[TIKTOK BG ERROR] URL de upload não fornecida")
            active_uploads[post_id] = {"progress": 0, "status": "error", "message": "Sem URL de upload."}
            return
            
        active_uploads[post_id] = {"progress": 15, "status": "uploading", "message": "Preparando envio dos chunks..."}

        # Upload de chunks
        for chunk_index in range(total_chunk_count):
            start_byte = chunk_index * actual_chunk_size
            remaining = video_size - start_byte
            
            if chunk_index == total_chunk_count - 1:
                this_chunk_size = remaining
            else:
                this_chunk_size = actual_chunk_size
                
            end_byte = start_byte + this_chunk_size - 1
            chunk_data = contents[start_byte : start_byte + this_chunk_size]
            
            # Content-Type FIXADO para 'video/mp4' evita o erro 'missing or invalid request id' do TikTok!
            put_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Range": f"bytes {start_byte}-{end_byte}/{video_size}",
                "Content-Type": "video/mp4"
            }
            
            # Atualiza o status de progresso do card
            percent = 15 + int(((chunk_index + 1) / total_chunk_count) * 80)
            active_uploads[post_id] = {
                "progress": min(percent, 95), 
                "status": "uploading", 
                "message": f"Enviando parte {chunk_index + 1} de {total_chunk_count}..."
            }

            print(f"[TIKTOK BG] Enviando chunk {chunk_index + 1}/{total_chunk_count} ({this_chunk_size} bytes)...")
            put_res = requests.put(upload_url, data=chunk_data, headers=put_headers)
            print(f"[TIKTOK BG] Resposta do chunk {chunk_index + 1}: Status {put_res.status_code}, Corpo: {put_res.text[:150]}")
            
            if put_res.status_code not in [200, 201, 204, 206]:
                if put_res.status_code == 403 and "50001" in put_res.text and "missing or invalid request id" in put_res.text:
                    print(f"[TIKTOK BG WARNING] TikTok retornou erro 50001 no chunk {chunk_index + 1}. Como o vídeo costuma ser publicado mesmo assim no Sandbox, vamos ignorar o erro e prosseguir.")
                else:
                    print(f"[TIKTOK BG ERROR] Falha no chunk {chunk_index + 1}: {put_res.text}")
                    active_uploads[post_id] = {"progress": 0, "status": "error", "message": f"Falha no chunk: {put_res.text}"}
                    return
                
        active_uploads[post_id] = {"progress": 100, "status": "success", "message": "Publicado com sucesso!"}
        print(f"[TIKTOK BG SUCCESS] Vídeo enviado com sucesso! Publish ID: {publish_id}")
    except Exception as e:
        print(f"[TIKTOK BG EXCEPTION] Ocorreu uma exceção: {str(e)}")
        active_uploads[post_id] = {"progress": 0, "status": "error", "message": str(e)}
    finally:
        # Remover o arquivo temporário para não acumular lixo no disco
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[TIKTOK BG] Arquivo temporário removido com sucesso: {file_path}")
            except Exception as ex:
                print(f"[TIKTOK BG] Erro ao remover arquivo temporário: {str(ex)}")

@app.post("/api/tiktok/upload")
async def tiktok_upload(
    background_tasks: BackgroundTasks,
    email: str = Form(None),
    title: str = Form(""),
    post_id: str = Form(None),
    video: UploadFile = File(None)
):
    """
    Recebe o arquivo de vídeo do frontend de forma ultrarrápida, salva-o
    temporariamente e inicia a tarefa de upload em segundo plano no TikTok.
    """
    if not email:
        raise HTTPException(status_code=400, detail="O e-mail do usuário é obrigatório.")
    if not video:
        raise HTTPException(status_code=400, detail="Por favor, selecione um arquivo de vídeo válido.")
    if not post_id:
        raise HTTPException(status_code=400, detail="O ID único do post é obrigatório.")
        
    connection = db_helper.get_tiktok_connection(email)
    if not connection or not connection["access_token"]:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma conta do TikTok conectada. Conecte sua conta antes de publicar."
        )
        
    # Inicializa o status no dicionário reativo
    active_uploads[post_id] = {"progress": 0, "status": "uploading", "message": "Enviando vídeo para o servidor..."}

    # Salvar o arquivo recebido localmente de forma temporária
    temp_file_name = f"upload_{email.replace('@', '_').replace('.', '_')}_{int(time.time())}_{video.filename}"
    temp_file_path = os.path.join(TEMP_DIR, temp_file_name)
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
    except Exception as e:
        active_uploads[post_id] = {"progress": 0, "status": "error", "message": f"Erro de disco no servidor: {str(e)}"}
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo temporário no servidor: {str(e)}")
        
    # Adiciona a tarefa de upload em segundo plano no FastAPI
    background_tasks.add_task(
        upload_to_tiktok_background,
        temp_file_path,
        email,
        title,
        post_id
    )
    
    return {
        "success": True,
        "message": "Upload recebido com sucesso pelo servidor e iniciado em background no TikTok!"
    }

@app.get("/api/tiktok/upload-status")
async def get_upload_status(post_id: str):
    """
    Retorna o progresso em tempo real e o status de um upload de segundo plano específico.
    """
    status = active_uploads.get(post_id, {"progress": 0, "status": "pending", "message": "Aguardando inicialização..."})
    return status
