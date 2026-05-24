import threading
import time
from queue import Queue, Empty
from datetime import datetime
import uuid

from src.modules.core import VideoDownloadTask, Config
from src.services.workers import DownloadWorker
from src.utils.logging import logger
from src.utils.errors import Result, DownloadCancelled, YtdlAppError

class DownloadManager:
    """Thread-safe Singleton para gestionar el estado y la cola de descargas."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DownloadManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.download_queue = Queue()
        self.pending_downloads = []
        self.download_history = []
        self.active_downloads = {}
        
        self.paused = False
        self.state_lock = threading.Lock()
        
        self._progress_callbacks = []
        self._finished_callbacks = []
        self._state_changed_callbacks = []
        self._summary_callbacks = []

        self._process_thread = threading.Thread(target=self._process_queue_loop, daemon=True)
        self._process_thread.start()

    def add_progress_callback(self, cb):
        self._progress_callbacks.append(cb)

    def add_finished_callback(self, cb):
        self._finished_callbacks.append(cb)

    def add_state_changed_callback(self, cb):
        self._state_changed_callbacks.append(cb)
        
    def add_summary_callback(self, cb):
        self._summary_callbacks.append(cb)

    def enqueue_task(self, task: VideoDownloadTask):
        self.enqueue_tasks([task])

    def enqueue_tasks(self, tasks: list[VideoDownloadTask]):
        if not tasks:
            return
        with self.state_lock:
            for task in tasks:
                self.download_queue.put(task)
                self.pending_downloads.append(task)
        self._notify_state_changed()

    def toggle_pause(self):
        with self.state_lock:
            self.paused = not self.paused
        self._notify_state_changed()

    def cancel_all(self):
        with self.state_lock:
            for download_info in self.active_downloads.values():
                download_info["worker"].cancel()
        self._notify_state_changed()

    def clear_history(self):
        with self.state_lock:
            self.download_history.clear()
        self._notify_state_changed()

    def clear_queue(self):
        """Cancel all active workers, clear pending downloads, and drain the queue."""
        with self.state_lock:
            for download_info in self.active_downloads.values():
                download_info["worker"].cancel()
            self.pending_downloads.clear()
            while not self.download_queue.empty():
                try:
                    self.download_queue.get_nowait()
                except Empty:
                    break
        self._notify_state_changed()

    def remove_pending_tasks_by_url(self, urls: list):
        """Remove pending tasks whose URL matches any in the given list."""
        url_set = set(urls)
        with self.state_lock:
            self.pending_downloads = [
                t for t in self.pending_downloads if t.url not in url_set
            ]
            # Rebuild the queue excluding the removed URLs
            remaining = []
            while not self.download_queue.empty():
                try:
                    task = self.download_queue.get_nowait()
                except Empty:
                    break
                if isinstance(task, VideoDownloadTask) and task.url not in url_set:
                    remaining.append(task)
            for task in remaining:
                self.download_queue.put(task)
        self._notify_state_changed()

    def cancel_worker(self, worker_id: str):
        """Cancel a specific active download by its worker ID."""
        with self.state_lock:
            if worker_id in self.active_downloads:
                self.active_downloads[worker_id]["worker"].cancel()
        self._notify_state_changed()

    def get_state(self):
        with self.state_lock:
            return {
                "active_downloads": {k: {**v, "worker": None} for k, v in self.active_downloads.items()},
                "pending_downloads": list(self.pending_downloads),
                "download_history": list(self.download_history),
                "paused": self.paused
            }

    def _notify_state_changed(self):
        for cb in self._state_changed_callbacks:
            try:
                cb()
            except Exception as e:
                logger.log(f"Callback error (state): {e}", "ERROR")

    def _notify_progress(self, worker_id, data):
        for cb in self._progress_callbacks:
            try:
                cb(worker_id, data)
            except Exception as e:
                logger.log(f"Callback error (progress): {e}", "ERROR")

    def _notify_finished(self, worker_id, result):
        for cb in self._finished_callbacks:
            try:
                cb(worker_id, result)
            except Exception as e:
                logger.log(f"Callback error (finished): {e}", "ERROR")

    def _notify_summary(self):
        for cb in self._summary_callbacks:
            try:
                cb()
            except Exception as e:
                logger.log(f"Callback error (summary): {e}", "ERROR")

    def _process_queue_loop(self):
        while True:
            processed_item = False
            task_to_start = None
            with self.state_lock:
                if not self.paused and len(self.active_downloads) < 3:
                    try:
                        task = self.download_queue.get_nowait()
                        processed_item = True
                        if isinstance(task, VideoDownloadTask):
                            if task in self.pending_downloads:
                                self.pending_downloads.remove(task)
                                task_to_start = task
                    except Empty:
                        pass
            
            if task_to_start:
                self.start_download(task_to_start)
                time.sleep(0.01)
            elif processed_item:
                time.sleep(0.01)
            else:
                time.sleep(0.5)

    def start_download(self, task: VideoDownloadTask):
        config = Config.load()
        worker = DownloadWorker(
            task.url,
            config["download_folder"],
            task.quality,
            config.get("format", "mp4"),
            config.get("language", "es")
        )
        worker_id = f"worker_{uuid.uuid4().hex}"
        
        task.state = "descargando"
        task.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.mark_attempt()

        worker.set_callbacks(
            progress_cb=lambda data: self.on_worker_progress(worker_id, data),
            finished_cb=lambda result: self.on_worker_finished(worker_id, result)
        )

        with self.state_lock:
            self.active_downloads[worker_id] = {
                "worker": worker,
                "task": task,
                "url": task.url,
                "title": task.title,
                "quality": task.quality,
                "start_time": time.time(),
                "progress": {}
            }

        worker.start()
        logger.log(f"Iniciando descarga: {task.title or task.url} (intento {task.attempt}/{task.max_attempts})", "INFO")
        self._notify_state_changed()

    def on_worker_progress(self, worker_id, data):
        with self.state_lock:
            if worker_id in self.active_downloads:
                self.active_downloads[worker_id]["progress"] = data
                worker = self.active_downloads[worker_id]["worker"]
                if getattr(worker, "video_title", ""):
                    self.active_downloads[worker_id]["title"] = worker.video_title
        self._notify_progress(worker_id, data)

    def on_worker_finished(self, worker_id, result: Result):
        with self.state_lock:
            if worker_id not in self.active_downloads:
                return

            download_info = self.active_downloads.pop(worker_id)
            task = download_info["task"]
            quality = download_info["quality"]
            title = download_info.get("title") or (result.value.get("title") if result.success else None) or task.url

            task.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if result.success:
                task.state = "completado"
                self.download_history.append({
                    "title": title,
                    "status": "success",
                    "date": task.end_time,
                    "error": None,
                    "quality": quality,
                    "playlist_id": task.playlist_id,
                })
                logger.log(f"Descarga completada: {title}", "SUCCESS")
            else:
                exc = result.error
                cancelled = isinstance(exc, DownloadCancelled)
                
                from src.config.i18n import translate
                config = Config.load()
                lang = config.get("language", "es")
                
                if isinstance(exc, YtdlAppError):
                    code_map = {
                        "DEPENDENCY_ERROR": "error_dependency_ffmpeg",
                        "EXTRACTION_ERROR": "error_extraction_failed",
                        "PRIVATE_VIDEO": "error_private_video",
                        "AGE_RESTRICTED": "error_age_restricted",
                        "BOT_CHALLENGE": "error_bot_challenge",
                        "NETWORK_TIMEOUT": "error_download_network",
                        "DISK_SPACE": "error_disk_space",
                        "PERMISSION_DENIED": "error_permission_denied",
                        "CONFIG_ERROR": "error_config",
                        "INTERNAL_ERROR": "error_unknown",
                        "CANCELLED": "error_unknown",
                    }
                    translation_key = code_map.get(exc.code, "error_unknown")
                    if exc.code == "DEPENDENCY_ERROR" and "node" in getattr(exc, "message", "").lower():
                        translation_key = "error_dependency_node"
                    error_msg = translate(lang, translation_key)
                else:
                    error_msg = str(exc)
                
                if cancelled:
                    task.state = "cancelado"
                    task.error_message = error_msg
                    self.download_history.append({
                        "title": title,
                        "status": "cancelled",
                        "date": task.end_time,
                        "error": error_msg,
                        "quality": quality,
                        "playlist_id": task.playlist_id,
                    })
                    logger.log(f"Descarga cancelada: {title}", "WARNING")
                else:
                    task.state = "error"
                    task.error_message = error_msg
                    if task.can_retry():
                        logger.log(f"Reintentando: {title} ({task.attempt}/{task.max_attempts}) debido a: {error_msg}", "WARNING")
                        task.state = "pendiente"
                        self.download_queue.put(task)
                        self.pending_downloads.append(task)
                        self.download_history.append({
                            "title": title,
                            "status": "retrying",
                            "date": task.end_time,
                            "error": error_msg,
                            "quality": quality,
                            "playlist_id": task.playlist_id,
                        })
                    else:
                        self.download_history.append({
                            "title": title,
                            "status": "error",
                            "date": task.end_time,
                            "error": error_msg[:120],
                            "quality": quality,
                            "playlist_id": task.playlist_id,
                        })
                        logger.log(f"Error final: {title} - {error_msg}", "ERROR")

            empty_queue = self.download_queue.empty() and not self.active_downloads

        self._notify_finished(worker_id, result)
        self._notify_state_changed()
        
        if empty_queue:
            self._notify_summary()
