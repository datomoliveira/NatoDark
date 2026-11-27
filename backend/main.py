import os
import uuid
import shutil
import asyncio
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Carrega .env antes de importar modulos que leem variaveis de ambiente.
load_dotenv()

import database
from database import (
    init_db, create_project, get_project, list_projects,
    update_project_timeline, update_project_script, update_project_audio,
    update_project_script_json, update_project_status,
    delete_project_row, add_clip, get_clips, create_batch, get_batch,
    update_batch_progress, create_cutter_job, get_cutter_job, update_cutter_job
)
from storage import (
    upload_file, download_file, delete_file, 
    delete_project_files, generate_download_url, LOCAL_STORAGE_DIR,
    IS_B2_CONFIGURED
)
from compiler import (
    compile_project_pipeline, process_cutter_job, get_media_duration,
    log_compile, get_compile_logs
)
from script_generator import generate_script, listar_provedores
import llm_router
from model_agents import listar_agentes, nome_agente
from media_scout import build_auto_timeline
from transcriber import sincronizar_projeto
from hype_research import pesquisar_hype
import youtube_api
import youtube_clips
import local_tools

# Sequential background job queue
compilation_queue = asyncio.Queue()

async def compilation_worker():
    print("Compilation Worker: Sequential queue worker started.")
    while True:
        job = await compilation_queue.get()
        try:
            job_type = job.get("type")
            if job_type == "single":
                project_id = job["project_id"]
                try:
                    compile_project_pipeline(project_id)
                except Exception as e:
                    print(f"Worker Error: Project {project_id} failed to compile: {e}")
            elif job_type == "batch":
                batch_id = job["batch_id"]
                try:
                    await run_batch_compilation(batch_id)
                except Exception as e:
                    print(f"Worker Error: Batch {batch_id} failed to compile: {e}")
        except asyncio.CancelledError:
            print("Compilation Worker: Sequential queue worker stopped.")
            break
        except Exception as e:
            print(f"Worker Loop Error: {e}")
        finally:
            compilation_queue.task_done()

async def run_batch_compilation(batch_id: str):
    print(f"Batch Compiler: Starting batch {batch_id}")
    batch = get_batch(batch_id)
    if not batch:
        print(f"Batch Compiler Error: Batch {batch_id} not found.")
        return
        
    update_batch_progress(batch_id, "processing", 0.0)
    projects_list = batch["projects"]
    total = len(projects_list)
    compiled_project_ids = []
    
    for idx, p_config in enumerate(projects_list):
        p_id = p_config["id"]
        log_compile(p_id, f"Iniciando compilação do projeto {idx+1}/{total} do lote {batch_id}.")
        
        try:
            # Trigger compile pipeline
            compile_project_pipeline(p_id)
            compiled_project_ids.append(p_id)
        except Exception as e:
            print(f"Batch Compiler: Project {p_id} failed during batch execution: {e}")
            
        progress = ((idx + 1) / total) * 100
        status = "completed" if idx == total - 1 else "processing"
        update_batch_progress(batch_id, status, progress)
        
    # ZIP the output files together
    if compiled_project_ids:
        import zipfile
        log_compile(compiled_project_ids[0], f"Lote concluído. Criando arquivo ZIP com os vídeos do lote...")
        
        batch_temp_dir = os.path.join(os.path.dirname(__file__), "temp", f"batch_{batch_id}")
        os.makedirs(batch_temp_dir, exist_ok=True)
        zip_path = os.path.join(batch_temp_dir, "videos.zip")
        
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for p_id in compiled_project_ids:
                p_details = get_project(p_id)
                p_name = p_details.get("name", p_id)
                # Clean name for zip inclusion
                safe_name = "".join([c if c.isalnum() or c in (" ", "_", "-") else "" for c in p_name]).strip()
                safe_name = safe_name.replace(" ", "_")
                if not safe_name:
                    safe_name = p_id
                    
                local_dest = os.path.join(batch_temp_dir, f"{p_id}_final.mp4")
                try:
                    download_file(f"projects/{p_id}/output/final.mp4", local_dest)
                    zipf.write(local_dest, arcname=f"{safe_name}.mp4")
                except Exception as e:
                    print(f"Batch Compiler: Failed to fetch output for {p_id}: {e}")
                    
        # Upload batch zip
        zip_key = f"batches/{batch_id}/all_videos.zip"
        upload_file(zip_path, zip_key)
        
        # Clean local batch files
        try:
            shutil.rmtree(batch_temp_dir)
        except Exception as cleanup_err:
            print(f"Batch Compiler cleanup error: {cleanup_err}")

async def download_cutter_video_task(job_id: str, url: str):
    import subprocess
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", "cutter")
    os.makedirs(temp_dir, exist_ok=True)
    video_path = os.path.join(temp_dir, f"raw_{job_id}.mp4")
    
    # Run yt-dlp
    cmd = [
        "python", "-m", "yt_dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", video_path,
        url
    ]
    
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            error_msg = res.stderr or "Erro desconhecido ao baixar vídeo da URL."
            # Clean up yt-dlp details
            if "Unsupported URL" in error_msg:
                error_msg = "URL não suportada. Por favor, verifique se o link é válido e público (YouTube, TikTok ou Instagram)."
            update_cutter_job(job_id, "failed", error_message=error_msg)
            return
            
        # Get duration
        duration = get_media_duration(video_path)
        
        # Upload raw video for cutter processing
        storage_key = f"cutter/{job_id}/raw.mp4"
        upload_file(video_path, storage_key)
        
        preview_url = generate_download_url(storage_key)
        update_cutter_job(job_id, "analyzed", file_url=preview_url, duration=duration)
        
        # Delete local downloaded raw
        if os.path.exists(video_path):
            os.remove(video_path)
    except Exception as e:
        update_cutter_job(job_id, "failed", error_message=str(e))
        if os.path.exists(video_path):
            os.remove(video_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    init_db()
    # Clean up any leftover temp folder
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
    worker_task = asyncio.create_task(compilation_worker())
    yield
    # Shutdown tasks
    worker_task.cancel()

app = FastAPI(title="NatoDark API", lifespan=lifespan)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API schemas
class ProjectCreate(BaseModel):
    name: str
    format: str

class TimelineSave(BaseModel):
    timeline: List[dict]

class ScriptSave(BaseModel):
    script: str
    subtitle_mode: str
    subtitle_style: dict

class ScriptGenerateRequest(BaseModel):
    tema: str
    publico: str = "brasileiros que consomem conteúdo dark/dramático no YouTube"
    duracao_segundos: float = 60.0
    formato: str = "shorts"
    tom: str = "dark, dramático e direto"
    provider: str = "auto"
    model: Optional[str] = None
    fallback: bool = True
    projeto_id: Optional[str] = None

class AutoMediaRequest(BaseModel):
    tema: Optional[str] = None
    fontes: List[str] = ["youtube", "unsplash", "openverse", "wikimedia"]
    youtube_urls: Optional[List[str]] = None  # uma URL por bloco; vazia = busca ytsearch
    youtube_licenca: Optional[str] = None
    usar_gemini: bool = True
    usar_cenas: bool = True  # PySceneDetect: evita cortar no meio de uma cena
    max_blocos: int = 12

class TranscribeRequest(BaseModel):
    model_size: Optional[str] = None
    compute_type: Optional[str] = None
    language: Optional[str] = None
    alinhar: bool = True

class HypeRequest(BaseModel):
    tema: str
    periodo: str = "week"
    limite: int = 10
    usar_llm: bool = True

class AudioParameters(BaseModel):
    volume: float
    fade_in: float
    fade_out: float

class CutRequest(BaseModel):
    start_time: float
    duration: float
    add_to_bank: bool = False
    clip_name: Optional[str] = None

class BatchCreate(BaseModel):
    projects: List[dict] # Configs containing name, format, script, subtitle_mode, audio_key, clip_ids (with their orders)

class AnalyzeUrlRequest(BaseModel):
    url: str

class ModelHealthRequest(BaseModel):
    provider: Optional[str] = None
    modelo: Optional[str] = None
    servico: Optional[str] = None
    tentativas: Optional[int] = None
    testar_todos: bool = False


# Serve static storage files if Backblaze B2 is fallback local
if os.path.exists(LOCAL_STORAGE_DIR):
    app.mount("/api/storage", StaticFiles(directory=LOCAL_STORAGE_DIR), name="storage")

# Endpoints
@app.post("/api/projects")
async def create_new_project(proj: ProjectCreate):
    project_id = str(uuid.uuid4())
    create_project(project_id, proj.name, proj.format)
    return {"id": project_id, "name": proj.name, "format": proj.format}

@app.get("/api/projects")
async def get_projects_list():
    return list_projects()

@app.get("/api/projects/{id}")
async def get_project_details(id: str):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return p

@app.delete("/api/projects/{id}")
async def delete_project(id: str):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    delete_project_files(id)
    delete_project_row(id)
    return {"status": "sucesso", "message": "Projeto deletado."}

@app.post("/api/projects/{id}/upload/video")
async def upload_project_video(id: str, file: UploadFile = File(...)):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", id)
    os.makedirs(temp_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}{file_ext}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Read duration
        duration = get_media_duration(temp_file_path)
        if duration == 0:
            duration = 5.0 # fallback
            
        # Upload
        storage_key = f"projects/{id}/uploads/{uuid.uuid4()}{file_ext}"
        upload_file(temp_file_path, storage_key)
        url = generate_download_url(storage_key)
        
        # Clean local
        os.remove(temp_file_path)
        
        return {
            "id": str(uuid.uuid4()),
            "type": "video",
            "key": storage_key,
            "url": url,
            "duration": duration,
            "trim_start": 0.0,
            "trim_end": duration
        }
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Erro ao processar upload: {str(e)}")

@app.post("/api/projects/{id}/upload/image")
async def upload_project_image(id: str, file: UploadFile = File(...)):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", id)
    os.makedirs(temp_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    if not file_ext:
        file_ext = ".png"
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}{file_ext}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Upload
        storage_key = f"projects/{id}/uploads/{uuid.uuid4()}{file_ext}"
        upload_file(temp_file_path, storage_key)
        url = generate_download_url(storage_key)
        
        os.remove(temp_file_path)
        
        return {
            "id": str(uuid.uuid4()),
            "type": "image",
            "key": storage_key,
            "url": url,
            "duration": 5.0, # default image duration is 5s
            "trim_start": 0.0,
            "trim_end": 0.0
        }
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Erro ao processar upload: {str(e)}")

@app.post("/api/projects/{id}/upload/audio")
async def upload_project_audio_file(id: str, file: UploadFile = File(...)):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", id)
    os.makedirs(temp_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}{file_ext}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Upload
        storage_key = f"projects/{id}/uploads/{uuid.uuid4()}{file_ext}"
        upload_file(temp_file_path, storage_key)
        url = generate_download_url(storage_key)
        
        os.remove(temp_file_path)
        
        # Save to DB
        update_project_audio(id, storage_key, 1.0, 0.0, 0.0)
        
        return {
            "key": storage_key,
            "url": url
        }
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Erro ao processar áudio: {str(e)}")

@app.post("/api/projects/{id}/timeline")
async def save_project_timeline(id: str, body: TimelineSave):
    update_project_timeline(id, body.timeline)
    return {"status": "sucesso", "message": "Timeline salva."}

@app.post("/api/projects/{id}/script")
async def save_project_script(id: str, body: ScriptSave):
    atual = get_project(id)
    if not atual:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    estilo = dict(atual.get("subtitle_style") or {})
    estilo.update(body.subtitle_style or {})
    # Preserva o srt_key salvo pelo /transcribe quando o frontend salva so o
    # estilo visual novamente — senao a legenda sincronizada seria perdida.
    update_project_script(id, body.script, body.subtitle_mode, estilo)
    return {"status": "sucesso", "message": "Configurações de legenda salvas."}

@app.get("/api/providers")
def listar_provedores_endpoint():
    """Mostra quais provedores de IA estao configurados (sem expor chaves)."""
    return {
        "padrao": os.environ.get("SCRIPT_PROVIDER", "auto"),
        "provedores": listar_provedores(),
    }

@app.get("/api/models/agents")
def listar_agentes_endpoint():
    """Agentes de IA (nome + sobrenome) por servico, com titulares e reservas."""
    return {"agentes": listar_agentes()}

@app.post("/api/models/health")
def health_modelos_endpoint(body: ModelHealthRequest = ModelHealthRequest()):
    """
    Testa modelos de verdade e devolve aprovados/reprovados.

    - Ollama: 3 tentativas antes de reprovar.
    - Demais: 2 tentativas.
    - Se `testar_todos` for True, varre todos os candidatos conhecidos.
    - Nunca devolve chaves.
    """
    try:
        if body.testar_todos:
            return llm_router.testar_candidatos(
                provider=body.provider, so_configurados=True, servico=body.servico,
            )
        if not body.provider or not body.modelo:
            raise HTTPException(status_code=400, detail="Informe provider e modelo, ou use testar_todos.")
        resultado = llm_router.testar_modelo(
            body.provider, body.modelo,
            tentativas=body.tentativas, servico=body.servico,
        )
        return {
            "resultados": [resultado],
            "aprovados": [resultado] if resultado["status"] == "aprovado" else [],
            "instaveis": [resultado] if resultado["status"] == "instavel" else [],
            "reprovados": [resultado] if resultado["status"] == "reprovado" else [],
        }
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as err:
        raise HTTPException(status_code=400, detail=str(err))

@app.post("/api/scripts/generate")
def generate_script_endpoint(body: ScriptGenerateRequest):
    """
    Gera um roteiro de alta retenção em pt-BR via router multi-provider.

    Padrão: 'auto' (gemini -> groq -> openrouter -> cloudflare -> openai ->
    anthropic -> ollama). Escolha um `provider` e/ou `model` para fixar.
    Se projeto_id for informado, salva o texto como roteiro do projeto e ajusta
    o `sec_per_block` das legendas com base na duração dos blocos gerados.
    """
    try:
        resultado = generate_script(
            body.tema,
            publico=body.publico,
            duracao_segundos=body.duracao_segundos,
            formato=body.formato,
            tom=body.tom,
            provider=body.provider,
            model=body.model,
            fallback=body.fallback,
        )
    except (ValueError, RuntimeError) as err:
        raise HTTPException(status_code=400, detail=str(err))

    if body.projeto_id:
        projeto = get_project(body.projeto_id)
        if not projeto:
            raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        estilo = dict(projeto.get("subtitle_style") or {})
        estilo["sec_per_block"] = resultado["sec_per_block"]
        update_project_script(
            body.projeto_id,
            resultado["roteiro_texto"],
            projeto.get("subtitle_mode") or "none",
            estilo,
        )
        update_project_script_json(body.projeto_id, resultado["roteiro_json"])

    return resultado

@app.post("/api/projects/{id}/media/auto")
def auto_media(id: str, body: AutoMediaRequest):
    """
    Busca midia para cada bloco do roteiro e monta a timeline.
    Prioridade: YouTube (yt-dlp local) -> Unsplash -> Openverse ->
    Wikimedia -> slide local. Use apenas clipes proprios/autorizados.
    Quando disponivel, PySceneDetect alinha o corte ao limite de cena.
    """
    projeto = get_project(id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")

    roteiro = dict(projeto.get("script_json") or {
        "roteiro_texto": projeto.get("script", ""),
        "sec_per_block": (projeto.get("subtitle_style") or {}).get("sec_per_block", 3.0),
    })

    # URLs do YouTube coladas no frontend: uma por bloco, na mesma ordem.
    if body.youtube_urls or body.youtube_licenca:
        blocos = [
            dict(b) if isinstance(b, dict) else b
            for b in (roteiro.get("blocos") or [])
        ]
        for i, bloco in enumerate(blocos):
            if not isinstance(bloco, dict):
                continue
            if body.youtube_urls and i < len(body.youtube_urls):
                url = (body.youtube_urls[i] or "").strip()
                if url:
                    bloco["youtube_url"] = url
            if body.youtube_licenca:
                bloco["youtube_licenca"] = body.youtube_licenca.strip()
        roteiro["blocos"] = blocos

    try:
        return build_auto_timeline(
            id,
            roteiro,
            script_texto=projeto.get("script", ""),
            tema=body.tema or projeto.get("name", ""),
            fontes=body.fontes,
            usar_gemini=body.usar_gemini,
            usar_cenas=body.usar_cenas,
            max_blocos=body.max_blocos,
        )
    except (ValueError, RuntimeError) as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Falha ao buscar mídia: {err}")

@app.post("/api/projects/{id}/transcribe")
def transcribe_project(id: str, body: TranscribeRequest = TranscribeRequest()):
    """
    Ouve a VOZ enviada pelo usuario (faster-whisper, local) e sincroniza as
    legendas com os timestamps reais da narração.

    Salva o SRT sincronizado no storage (`subtitle_style.srt_key`) e os timings
    em `script_json`. O compiler passa a preferir esse SRT. Roda em thread
    separada pelo FastAPI (endpoint sync) para nao travar o servidor.
    """
    if not get_project(id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    try:
        return sincronizar_projeto(
            id,
            model_size=body.model_size,
            compute_type=body.compute_type,
            language=body.language,
            alinhar=body.alinhar,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Falha na transcrição: {err}")

@app.post("/api/hype/research")
def hype_research_endpoint(body: HypeRequest):
    """
    Pesquisa o que está bombando via HTML do YouTube + DuckDuckGo (sem API key)
    e sugere angulos originais via router de LLMs.
    """
    try:
        return pesquisar_hype(
            body.tema,
            periodo=body.periodo,
            limite=body.limite,
            usar_llm=body.usar_llm,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Falha na pesquisa de hype: {err}")

@app.get("/api/youtube/config")
def youtube_config():
    """Informa se a API oficial do YouTube está disponível (sem expor a chave)."""
    return {
        "configurada": youtube_api.configurado(),
        "fonte": "YOUTUBE_API_KEY / YOUTUBE_DATA_API_KEY",
        "observacao": (
            "A API nao expoe o grafico de retencao; isso so existe no YouTube Studio. "
            "A pesquisa de hype continua usando HTML do navegador, sem cota."
        ),
    }

@app.get("/api/media/config")
def media_config():
    """
    Mostra quais fontes de midia estao disponiveis no BACKEND LOCAL (sem expor valores).
    Secrets do Cloudflare nao aparecem aqui: o download/render e local.
    """
    return {
        "fontes_default": ["youtube", "unsplash", "openverse", "wikimedia"],
        "sem_chave": ["youtube", "openverse", "wikimedia"],
        "chaves_locais": {
            nome: bool(os.environ.get(nome, "").strip())
            for nome in (
                "UNSPLASH_ACCESS_KEY",
                "PEXELS_API_KEY",
                "PIXABAY_API_KEY",
                "YOUTUBE_API_KEY",
                "YOUTUBE_DATA_API_KEY",
            )
        },
        "observacao": (
            "UNSPLASH_ACCESS_KEY precisa existir no ambiente do backend local "
            "(backend/.env) para o auto-scout usar; Secret do Pages serve para "
            "as rotas de IA nao para o download de midia."
        ),
    }

@app.get("/api/tools")
def tools_status():
    """
    Ferramentas locais disponiveis (backend), com licenca/custo e estado real.
    Nao expoe chaves, tokens nem caminhos de arquivos sensiveis.
    """
    return local_tools.status()

@app.get("/api/youtube/clips/search")
def youtube_clips_search(q: str, limite: int = 3):
    """
    Busca candidatos de clipe por HTML (ytsearch), sem chave de API.
    O download/recorte acontece depois, no /media/auto.
    """
    if not youtube_clips.configurado():
        raise HTTPException(
            status_code=400,
            detail="yt-dlp nao instalado no backend (pip install -r requirements.txt).",
        )
    return {
        "configurado": True,
        "candidatos": youtube_clips.buscar(q, limite=limite),
        "observacao": "Use apenas videos proprios ou autorizados; creditos gravados em credits.json.",
    }

@app.get("/api/youtube/video/{video_id}")
def youtube_video(video_id: str):
    """Metadados e estatisticas de um video (usa API oficial, se configurada)."""
    try:
        return youtube_api.video_info(video_id)
    except RuntimeError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

@app.get("/api/youtube/video/{video_id}/comments")
def youtube_comments(video_id: str, limite: int = 20):
    """Comentarios de um video para extrair dor do publico."""
    try:
        return {"comentarios": youtube_api.comentarios(video_id, limite)}
    except RuntimeError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

@app.get("/api/youtube/channel/{channel_id}/videos")
def youtube_channel_videos(channel_id: str, limite: int = 10):
    """Ultimos videos de um canal (para comparar com a sua producao)."""
    try:
        return {"videos": youtube_api.canal_videos(channel_id, limite)}
    except RuntimeError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

@app.post("/api/projects/{id}/audio-parameters")
async def save_audio_parameters(id: str, body: AudioParameters):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    update_project_audio(id, p["audio_file"], body.volume, body.fade_in, body.fade_out)
    return {"status": "sucesso", "message": "Parâmetros de áudio salvos."}

@app.post("/api/projects/{id}/compile")
async def compile_project_endpoint(id: str):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    if p["status"] == "compilando":
        return {"status": "compilando", "message": "Projeto já está na fila/compilando."}
        
    # Queue single compilation job
    update_project_status(id, "compilando")
    # Clean compile log file if exists
    log_dir = os.path.join(os.path.dirname(__file__), "temp", id)
    if os.path.exists(log_dir):
        log_path = os.path.join(log_dir, "compile.log")
        if os.path.exists(log_path):
            os.remove(log_path)
            
    await compilation_queue.put({"type": "single", "project_id": id})
    return {"status": "enfileirado", "message": "Projeto adicionado à fila de compilação sequencial."}

@app.get("/api/projects/{id}/compile/status")
async def get_project_compile_status(id: str):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    logs = get_compile_logs(id)
    return {
        "status": p["status"],
        "logs": logs
    }

@app.get("/api/projects/{id}/download")
async def get_project_download_url(id: str):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    if p["status"] != "pronto":
        raise HTTPException(status_code=400, detail="Vídeo final não está compilado ou pronto.")
        
    output_key = f"projects/{id}/output/final.mp4"
    url = generate_download_url(output_key, expires_in=3600)
    return {"url": url}

@app.post("/api/projects/{id}/cleanup")
async def cleanup_project_endpoint(id: str):
    p = get_project(id)
    if not p:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    delete_project_files(id)
    update_project_status(id, "expirado")
    return {"status": "sucesso", "message": "Todos os arquivos do projeto foram apagados do storage."}


# Clip Bank Endpoints
@app.get("/api/clips")
async def get_bank_clips():
    return get_clips()

@app.post("/api/clips/upload")
async def upload_bank_clip(name: str = Form(...), file: UploadFile = File(...)):
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", "clips")
    os.makedirs(temp_dir, exist_ok=True)
    
    clip_id = f"clip_{uuid.uuid4().hex[:12]}"
    file_ext = os.path.splitext(file.filename)[1]
    temp_file_path = os.path.join(temp_dir, f"{clip_id}{file_ext}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        duration = get_media_duration(temp_file_path)
        if duration == 0:
            duration = 5.0
            
        storage_key = f"clips/{clip_id}{file_ext}"
        upload_file(temp_file_path, storage_key)
        url = generate_download_url(storage_key)
        
        add_clip(clip_id, name, url, storage_key, duration)
        
        os.remove(temp_file_path)
        
        return {
            "id": clip_id,
            "name": name,
            "file_url": url,
            "storage_key": storage_key,
            "duration": duration
        }
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Erro no upload do clipe: {str(e)}")


# Batch compiling endpoints
@app.post("/api/batch/create")
async def create_compilation_batch(batch_data: BatchCreate):
    batch_id = str(uuid.uuid4())
    
    # Convert batch configuration to standard project rows
    created_projects = []
    
    for idx, p_config in enumerate(batch_data.projects):
        p_id = str(uuid.uuid4())
        name = p_config.get("name", f"Lote {idx+1}")
        fmt = p_config.get("format", "shorts")
        
        # Save project draft
        create_project(p_id, name, fmt)
        
        # Audio configuration
        audio_key = p_config.get("audio_key")
        if audio_key:
            update_project_audio(p_id, audio_key, 1.0, 0.0, 0.0)
            
        # Script and Legendas configuration
        script = p_config.get("script", "")
        burn = p_config.get("burn_subtitles", False)
        sub_mode = "burn" if burn else "none"
        
        style = {
            "FontName": "Arial",
            "FontSize": 48,
            "PrimaryColour": "#FFFFFF",
            "OutlineColour": "#000000",
            "Outline": 3,
            "Alignment": 2
        }
        update_project_script(p_id, script, sub_mode, style)
        
        # Timeline items (using chosen reusable clips in sequential order)
        timeline = []
        clip_ids = p_config.get("clip_ids", []) # list of clip ID strings
        
        # Query existing clips to copy metadata
        clips_bank = get_clips()
        clips_dict = {c["id"]: c for c in clips_bank}
        
        for item_idx, clip_id in enumerate(clip_ids):
            c_meta = clips_dict.get(clip_id)
            if c_meta:
                timeline.append({
                    "id": f"clip_{uuid.uuid4().hex[:8]}",
                    "type": "video",
                    "key": c_meta["storage_key"],
                    "url": c_meta["file_url"],
                    "duration": c_meta["duration"],
                    "trim_start": 0.0,
                    "trim_end": c_meta["duration"]
                })
                
        update_project_timeline(p_id, timeline)
        
        created_projects.append({
            "id": p_id,
            "name": name,
            "format": fmt
        })
        
    create_batch(batch_id, created_projects)
    return {"batch_id": batch_id, "projects": created_projects}

@app.post("/api/batch/{batch_id}/compile")
async def compile_batch_endpoint(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
        
    if batch["status"] == "processing":
        return {"status": "processing", "message": "Lote já está sendo processado."}
        
    # Mark all inner projects as compilando
    for p in batch["projects"]:
        update_project_status(p["id"], "compilando")
        
    update_batch_progress(batch_id, "processing", 0.0)
    await compilation_queue.put({"type": "batch", "batch_id": batch_id})
    return {"status": "enfileirado", "message": "Lote adicionado à fila sequencial."}

@app.get("/api/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
        
    # Query current details for all projects in this batch
    projects_status = []
    for p in batch["projects"]:
        p_details = get_project(p["id"])
        if p_details:
            projects_status.append({
                "id": p["id"],
                "name": p_details["name"],
                "format": p_details["format"],
                "status": p_details["status"]
            })
            
    zip_url = None
    if batch["status"] == "completed":
        zip_url = generate_download_url(f"batches/{batch_id}/all_videos.zip")
        
    return {
        "id": batch_id,
        "status": batch["status"],
        "progress": batch["progress"],
        "projects": projects_status,
        "zip_url": zip_url
    }


# Video Cutter Endpoints
@app.post("/api/cutter/analyze-url")
async def analyze_url_for_cutter(req: AnalyzeUrlRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    create_cutter_job(job_id, "downloading", req.url)
    background_tasks.add_task(download_cutter_video_task, job_id, req.url)
    return {"job_id": job_id, "status": "downloading"}

@app.post("/api/cutter/upload")
async def upload_for_cutter(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    create_cutter_job(job_id, "downloading")
    
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", "cutter")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    video_path = os.path.join(temp_dir, f"raw_{job_id}{file_ext}")
    
    try:
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        duration = get_media_duration(video_path)
        storage_key = f"cutter/{job_id}/raw{file_ext}"
        upload_file(video_path, storage_key)
        
        preview_url = generate_download_url(storage_key)
        update_cutter_job(job_id, "analyzed", file_url=preview_url, duration=duration)
        
        # Clean local
        os.remove(video_path)
        
        return {"job_id": job_id, "status": "analyzed", "duration": duration, "preview_url": preview_url}
    except Exception as e:
        if os.path.exists(video_path):
            os.remove(video_path)
        update_cutter_job(job_id, "failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao fazer upload do vídeo: {str(e)}")

@app.get("/api/cutter/{job_id}/status")
async def get_cutter_job_status(job_id: str):
    job = get_cutter_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabalho de corte não encontrado.")
    return job

@app.post("/api/cutter/{job_id}/cut")
async def cut_video_segment(job_id: str, req: CutRequest, background_tasks: BackgroundTasks):
    job = get_cutter_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabalho de corte não encontrado.")
        
    if job["status"] not in ("analyzed", "completed", "failed"):
        raise HTTPException(status_code=400, detail="Vídeo de origem ainda não está pronto para ser cortado.")
        
    update_cutter_job(job_id, "processing")
    
    # Download raw video from storage to local temp for cutting
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", "cutter")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Find original key. We assume the raw file key matches cutter/{job_id}/raw*
    raw_key = None
    if IS_B2_CONFIGURED:
        # In B2, the URL or key is stored. The key is cutter/{job_id}/raw.mp4 or cutter/{job_id}/raw{ext}
        # We can extract it or reconstruct it.
        # Let's inspect the job file_url or try cutter/{job_id}/raw.mp4
        raw_key = f"cutter/{job_id}/raw.mp4"
    else:
        # Check files under local storage folder cutter/{job_id}/
        job_storage_dir = os.path.join(LOCAL_STORAGE_DIR, "cutter", job_id)
        if os.path.exists(job_storage_dir):
            for file in os.listdir(job_storage_dir):
                if file.startswith("raw"):
                    raw_key = f"cutter/{job_id}/{file}"
                    break
                    
    if not raw_key:
        raw_key = f"cutter/{job_id}/raw.mp4"
        
    local_raw_path = os.path.join(temp_dir, f"raw_download_{job_id}.mp4")
    
    try:
        download_file(raw_key, local_raw_path)
    except Exception as e:
        update_cutter_job(job_id, "failed", error_message=f"Falha ao baixar vídeo original para processamento: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao buscar vídeo original do storage.")
        
    # Process cutter in a background task
    def cutter_background():
        try:
            process_cutter_job(
                job_id=job_id,
                input_path=local_raw_path,
                start_time=req.start_time,
                duration=req.duration,
                add_to_bank=req.add_to_bank,
                clip_name=req.clip_name
            )
        finally:
            if os.path.exists(local_raw_path):
                try:
                    os.remove(local_raw_path)
                except Exception:
                    pass
                    
    background_tasks.add_task(cutter_background)
    return {"status": "processando", "message": "Iniciando corte do clipe."}

@app.get("/api/cutter/{job_id}/download")
async def get_cut_download_url(job_id: str):
    job = get_cutter_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabalho de corte não encontrado.")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="O corte ainda não foi concluído.")
        
    storage_key = f"cutter/{job_id}/output.mp4"
    url = generate_download_url(storage_key, expires_in=3600)
    return {"url": url}
