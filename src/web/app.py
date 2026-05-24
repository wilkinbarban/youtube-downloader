from contextlib import asynccontextmanager
from dataclasses import asdict
import asyncio
import os
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config.paths import WEB_STATIC_DIR
from src.modules.core import VideoDownloadTask, Config, PlaylistExtractor
from src.services.download_manager import DownloadManager
from src.utils.logging import logger
from src.utils.errors import YtdlAppError

loop = None

class ConnectionManager:
    """Manage active WebSocket connections and thread-safe broadcasts."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

ws_manager = ConnectionManager()

def serialize_state(state):
    """Serialize DownloadManager state for JSON transmission."""
    serialized_active = {}
    for k, v in state["active_downloads"].items():
        serialized_active[k] = {
            "url": v["url"],
            "title": v["title"],
            "quality": v["quality"],
            "start_time": v["start_time"],
            "progress": v["progress"],
            "task": asdict(v["task"]) if v["task"] else None
        }
    serialized_pending = [asdict(t) for t in state["pending_downloads"]]
    serialized_history = state["download_history"]
    return {
        "active_downloads": serialized_active,
        "pending_downloads": serialized_pending,
        "download_history": serialized_history,
        "paused": state["paused"]
    }

def on_state_changed():
    """DownloadManager callback for general state changes."""
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_state(), loop)

def on_progress(worker_id, data):
    """DownloadManager callback for task progress updates."""
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_progress(worker_id, data), loop)

async def broadcast_state():
    state = DownloadManager().get_state()
    await ws_manager.broadcast({
        "event": "state_changed",
        "data": serialize_state(state)
    })

async def broadcast_progress(worker_id, progress_data):
    await ws_manager.broadcast({
        "event": "progress",
        "data": {
            "worker_id": worker_id,
            "progress": progress_data
        }
    })

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop
    loop = asyncio.get_running_loop()
    
    # Bind callbacks to the DownloadManager singleton
    manager = DownloadManager()
    manager.add_state_changed_callback(on_state_changed)
    manager.add_progress_callback(on_progress)
    
    logger.log("FastAPI backend callbacks bound to DownloadManager.", "INFO")
    yield
    logger.log("FastAPI backend stopping.", "INFO")

app = FastAPI(
    title="YouTube Downloader Web Backend",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(YtdlAppError)
async def ytdl_exception_handler(request: Request, exc: YtdlAppError):
    logger.log(f"Excepción capturada en API Web: [{exc.code}] {exc.message}", "WARNING")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )

class DownloadRequest(BaseModel):
    url: str
    quality: str = "720p"

def background_extract_and_enqueue(url: str, quality: str):
    """Extract videos from URL and enqueue them in the DownloadManager (runs in background thread)."""
    logger.log(f"Extrayendo videos en segundo plano para la web: {url}", "INFO")
    result = PlaylistExtractor.extract_videos(url)
    if not result.success:
        err_msg = getattr(result.error, "message", str(result.error))
        logger.log(f"Error extrayendo videos para la web: {err_msg}", "ERROR")
        return
        
    videos = result.value
        
    manager = DownloadManager()
    config = Config.load()
    playlist_id = None
    
    if len(videos) > 1:
        import time
        playlist_id = f"web_batch_{int(time.time())}"
        limit = config.get("mix_max_videos", 100)
        if len(videos) > limit:
            logger.log(f"Límite de lote web aplicado: reduciendo de {len(videos)} a {limit}", "WARNING")
            videos = videos[:limit]
            
    tasks = []
    for item in videos:
        task = VideoDownloadTask(
            url=item["url"],
            title=item["title"],
            quality=quality,
            playlist_id=playlist_id
        )
        tasks.append(task)
    manager.enqueue_tasks(tasks)
    logger.log(f"Cola web: Encolados {len(videos)} videos con calidad {quality}.", "INFO")

@app.post("/api/downloads/add")
async def add_download(payload: DownloadRequest):
    if not payload.url:
        raise HTTPException(status_code=400, detail="La URL es obligatoria")
    # Use an independent daemon thread instead of Starlette BackgroundTasks
    # to avoid blocking the FastAPI/uvicorn event loop that runs inside QThread.
    t = threading.Thread(
        target=background_extract_and_enqueue,
        args=(payload.url, payload.quality),
        daemon=True
    )
    t.start()
    return {"success": True, "message": "Procesando URL y extrayendo metadatos en segundo plano"}

@app.get("/api/downloads/status")
async def get_status():
    manager = DownloadManager()
    state = manager.get_state()
    return serialize_state(state)

@app.post("/api/downloads/pause")
async def toggle_pause():
    manager = DownloadManager()
    manager.toggle_pause()
    return {"success": True, "paused": manager.paused}

@app.post("/api/downloads/cancel")
async def cancel_downloads():
    manager = DownloadManager()
    manager.cancel_all()
    return {"success": True}

@app.post("/api/downloads/clear")
async def clear_history():
    manager = DownloadManager()
    manager.clear_history()
    return {"success": True}

@app.post("/api/downloads/clear-queue")
async def clear_queue():
    manager = DownloadManager()
    manager.clear_queue()
    return {"success": True}

@app.post("/api/config/browse")
async def browse_folder():
    """Open a native folder picker dialog via the Qt main thread."""
    try:
        from src.services.workers import WebBridge, FolderPickerRequest
        bridge = WebBridge.get_instance()
        request = FolderPickerRequest()
        bridge.browse_folder_requested.emit(request)
        # Wait for the Qt main thread to process the dialog (max 60s)
        request.event.wait(timeout=60)
        if request.result:
            return {"success": True, "path": request.result}
        return {"success": False, "cancelled": True}
    except Exception as exc:
        logger.log(f"Error en browse_folder: {exc}", "ERROR")
        return {"success": False, "error": str(exc)}

@app.get("/api/config")
async def get_config():
    return Config.load()

@app.post("/api/config")
async def update_config(request: Request):
    try:
        data = await request.json()
        config = Config.load()
        config.update(data)
        success = Config.save(config)
        return {"success": success, "config": config}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/logs")
async def get_logs():
    return {"logs": logger.get_logs()}

@app.get("/api/config/cookies/status")
async def get_cookies_status():
    from src.config.paths import BASE_DIR
    cookies_txt = os.path.join(BASE_DIR, "cookies.txt")
    cookies_json = os.path.join(BASE_DIR, "cookies.json")
    
    status_text = "Sin archivo"
    if os.path.exists(cookies_txt):
        status_text = "Activo (cookies.txt)"
    elif os.path.exists(cookies_json):
        status_text = "Pendiente (cookies.json)"
        
    return {
        "cookies_txt": os.path.exists(cookies_txt),
        "cookies_json": os.path.exists(cookies_json),
        "status_text": status_text
    }

@app.post("/api/config/cookies")
async def upload_cookies(file: UploadFile = File(...)):
    from src.config.paths import BASE_DIR
    from src.modules.core import check_and_convert_json_cookies
    import shutil
    
    filename = file.filename.lower()
    if not (filename.endswith(".json") or filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .json o .txt")
        
    dest_filename = "cookies.json" if filename.endswith(".json") else "cookies.txt"
    dest_path = os.path.join(BASE_DIR, dest_filename)
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.log(f"Archivo de cookies subido a la web: {dest_path}", "INFO")
        
        # If it's json, try to convert it
        if dest_filename == "cookies.json":
            success = check_and_convert_json_cookies()
            if not success:
                return {
                    "success": False,
                    "error": "El archivo cookies.json fue subido pero falló la conversión a Netscape. Revisa los logs."
                }
            return {
                "success": True,
                "message": "Archivo cookies.json subido y convertido a Netscape cookies.txt con éxito."
            }
        else:
            return {
                "success": True,
                "message": "Archivo cookies.txt subido con éxito."
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial state to the client upon connection
        manager = DownloadManager()
        state = manager.get_state()
        await websocket.send_json({
            "event": "state_changed",
            "data": serialize_state(state)
        })
        while True:
            # Keep connection alive; clients can send messages or keep-alives
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

import string
import sys

def get_windows_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            drives.append(drive_path)
    return drives

@app.get("/api/filesystem/browse")
async def browse_filesystem(path: str = None):
    from src.config.paths import BASE_DIR
    if not path:
        config = Config.load()
        path = config.get("download_folder") or BASE_DIR

    path = os.path.abspath(path)
    if not os.path.exists(path) or not os.path.isdir(path):
        path = BASE_DIR

    try:
        items = os.listdir(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo acceder al directorio: {exc}")

    directories = []
    for item in items:
        full_path = os.path.join(path, item)
        try:
            if os.path.isdir(full_path):
                directories.append({
                    "name": item,
                    "path": full_path
                })
        except Exception:
            continue

    directories.sort(key=lambda d: d["name"].lower())

    drives = []
    if sys.platform == "win32":
        drives = get_windows_drives()

    return {
        "current_path": path,
        "parent_path": os.path.dirname(path) if os.path.dirname(path) != path else None,
        "directories": directories,
        "drives": drives
    }

class CreateFolderRequest(BaseModel):
    parent_path: str
    folder_name: str

@app.post("/api/filesystem/create-folder")
async def create_folder(payload: CreateFolderRequest):
    if not payload.parent_path or not payload.folder_name:
        raise HTTPException(status_code=400, detail="Ruta principal y nombre de carpeta requeridos")

    clean_name = os.path.basename(payload.folder_name)
    new_dir_path = os.path.join(payload.parent_path, clean_name)

    try:
        os.makedirs(new_dir_path, exist_ok=True)
        return {"success": True, "path": new_dir_path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al crear carpeta: {exc}")

@app.post("/api/downloads/{worker_id}/cancel")
async def cancel_specific_download(worker_id: str):
    manager = DownloadManager()
    with manager.state_lock:
        exists = worker_id in manager.active_downloads
    if exists:
        manager.cancel_worker(worker_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Descarga activa no encontrada")

class RemovePendingRequest(BaseModel):
    url: str

@app.post("/api/downloads/remove-pending")
async def remove_specific_pending(payload: RemovePendingRequest):
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL es requerida")
    manager = DownloadManager()
    manager.remove_pending_tasks_by_url([payload.url])
    return {"success": True}

@app.get("/api/i18n/{lang}")
async def get_i18n_translations(lang: str):
    from src.config.i18n import TRANSLATIONS
    return TRANSLATIONS.get(lang, TRANSLATIONS.get("es", {}))

# Mount static files folder last so it doesn't mask API routes
if os.path.exists(WEB_STATIC_DIR):
    app.mount("/", StaticFiles(directory=WEB_STATIC_DIR, html=True), name="static")
else:
    # Create empty directory if it doesn't exist yet to prevent startup crashes
    os.makedirs(WEB_STATIC_DIR, exist_ok=True)
    app.mount("/", StaticFiles(directory=WEB_STATIC_DIR, html=True), name="static")
