"""Qt workers for downloads, playlists, clipboard monitoring, and installs."""

import os
import time

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.modules.core import (
    PlaylistExtractor,
    YouTubeValidator,
    canonical_video_url,
    normalize_string,
    ytdlp_js_runtimes,
)
from src.services.dependencies import DependencyManager
from src.utils.logging import logger
from src.config.i18n import translate


from src.utils.errors import Result, map_ytdlp_error, DownloadCancelled, DownloadError


class PlaylistExtractWorker(QThread):
    """Run playlist extraction outside the main thread."""

    finished = pyqtSignal(bool, object, object)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        result = PlaylistExtractor.extract_videos(self.url)
        if result.success:
            self.finished.emit(True, result.value, None)
        else:
            self.finished.emit(False, [], result.error)


import threading

class DownloadWorker(threading.Thread):
    """yt-dlp download worker with progress reporting and cancellation."""

    def __init__(self, url, output_path, quality, format_type, language="es"):
        super().__init__(daemon=True)
        self.url = canonical_video_url(url)
        self.output_path = output_path
        self.quality = quality
        self.format_type = format_type
        self.language = language
        self.video_title = ""
        self._cancel_requested = False
        self._progress_cb = None
        self._finished_cb = None
        self._last_progress_time = 0

    def set_callbacks(self, progress_cb, finished_cb):
        self._progress_cb = progress_cb
        self._finished_cb = finished_cb

    def cancel(self):
        self._cancel_requested = True
        logger.log(f"Cancelacion solicitada: {self.url}", "INFO")

    def run(self):
        try:
            success = self._download_with_ytdlp()
            if success:
                return
            if self._finished_cb:
                self._finished_cb(
                    Result.fail(DownloadError("La descarga falló o yt-dlp no está disponible"))
                )
        except DownloadCancelled as exc:
            if self._finished_cb:
                self._finished_cb(Result.fail(exc))
        except Exception as exc:
            mapped_err = map_ytdlp_error(exc, "Error en descarga")
            logger.log(str(mapped_err), "ERROR")
            if self._finished_cb:
                self._finished_cb(Result.fail(mapped_err))

    def _get_yt_dlp_format(self):
        quality_map = {
            "4k": "bestvideo[height<=2160]+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best",
            "720p": "bestvideo[height<=720]+bestaudio/best",
            "480p": "bestvideo[height<=480]+bestaudio/best",
            "360p": "bestvideo[height<=360]+bestaudio/best",
            "best": "bestvideo+bestaudio/best",
            "audio": "bestaudio/best",
        }
        return quality_map.get(self.quality, "bestvideo+bestaudio/best")

    def _ensure_not_cancelled(self):
        if self._cancel_requested:
            raise DownloadCancelled()

    def _download_with_ytdlp(self):
        import yt_dlp

        self._ensure_not_cancelled()
        ffmpeg_location = DependencyManager.get_ffmpeg_location()

        # Phase 1: fetch metadata only to obtain the video title.
        # noplaylist=True ensures a single-video result even when the URL
        # contains a list= parameter (e.g. from a playlist or radio link).
        from src.modules.core import Config, check_and_convert_json_cookies
        from src.config.paths import BASE_DIR
        from src.utils.logging import YtdlpLogger
        
        check_and_convert_json_cookies()
        config = Config.load()
        browser = config.get("cookies_browser", "none")
        cookies_txt = os.path.join(BASE_DIR, "cookies.txt")
        use_cookies = os.path.exists(cookies_txt)

        ydl_extract_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "js_runtimes": ytdlp_js_runtimes(),
            "logger": YtdlpLogger(),
        }
        if ffmpeg_location:
            ydl_extract_opts["ffmpeg_location"] = ffmpeg_location
        if use_cookies:
            ydl_extract_opts["cookiefile"] = cookies_txt
        elif browser != "none":
            ydl_extract_opts["cookiesfrombrowser"] = (browser, None, None, None)

        with yt_dlp.YoutubeDL(ydl_extract_opts) as ydl_extract:
            info_only = ydl_extract.extract_info(self.url, download=False)
            self._ensure_not_cancelled()
            self.video_title = info_only.get("title", "Unknown")

        safe_title = normalize_string(self.video_title) or "youtube_video"
        merge_fmt = (self.format_type or "mp4").strip().lstrip(".").lower() or "mp4"
        ydl_opts = {
            "format": self._get_yt_dlp_format(),
            "outtmpl": os.path.join(self.output_path, safe_title + ".%(ext)s"),
            "quiet": False,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook_ytdlp],
            "socket_timeout": 30,
            "retries": 2,
            "noplaylist": True,
            "restrictfilenames": True,
            "js_runtimes": ytdlp_js_runtimes(),
            "logger": YtdlpLogger(),
        }
        if ffmpeg_location:
            ydl_opts["ffmpeg_location"] = ffmpeg_location
        if self.quality != "audio":
            ydl_opts["merge_output_format"] = merge_fmt
        if use_cookies:
            ydl_opts["cookiefile"] = cookies_txt
        elif browser != "none":
            ydl_opts["cookiesfrombrowser"] = (browser, None, None, None)

        # Phase 2: download using a fresh extract_info call (not process_ie_result).
        # Passing pre-extracted info across YoutubeDL instances via process_ie_result
        # is unreliable in yt-dlp 2024+: the second instance may ignore noplaylist
        # and attempt to download all entries from a playlist structure embedded in
        # the info dict, producing one huge concatenated file instead of a single video.
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=True)
            self._ensure_not_cancelled()
            title = (info or info_only).get("title", self.video_title or "Unknown")
            logger.log(f"Descarga exitosa: {title}", "SUCCESS")
            if self._finished_cb:
                self._finished_cb(
                    Result.ok({
                        "title": title,
                    })
                )
            return True

    def _progress_hook_ytdlp(self, data):
        self._ensure_not_cancelled()
        if data["status"] == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes", 0)
            percent = (downloaded / total) * 100 if total > 0 else 0
            
            now = time.time()
            # Allow progress callback only if 0.3s has elapsed or percent is near 100%
            if now - self._last_progress_time < 0.3 and percent < 99.9:
                return
            
            self._last_progress_time = now
            speed = data.get("speed", 0)
            eta = data.get("eta", 0)
            if self._progress_cb:
                self._progress_cb(
                    {
                        "downloaded": downloaded,
                        "total": total,
                        "speed": speed,
                        "eta": eta,
                        "percent": percent,
                        "status_key": "status_downloading",
                    }
                )
        elif data["status"] == "finished":
            if self._progress_cb:
                self._progress_cb(
                    {
                        "downloaded": data.get("downloaded_bytes", 0),
                        "total": data.get("total_bytes", 0),
                        "speed": 0,
                        "eta": 0,
                        "percent": 100,
                        "status_key": "status_processing",
                    }
                )


class ClipboardMonitor(QThread):
    """Lightweight clipboard monitor to detect YouTube URLs."""

    url_detected = pyqtSignal(str)

    def __init__(self, interval=10):
        super().__init__()
        self.interval = interval
        self.is_running = True
        self.last_clipboard = ""

    def run(self):
        import pyperclip

        error_logged = False
        while self.is_running:
            try:
                clipboard_content = pyperclip.paste()
                if error_logged:
                    logger.log("Monitor de portapapeles recuperado.", "INFO")
                    error_logged = False

                if clipboard_content and isinstance(clipboard_content, str) and clipboard_content != self.last_clipboard:
                    self.last_clipboard = clipboard_content
                    # Guard length to avoid processing very large text and regex stalls
                    if len(clipboard_content) < 2000 and YouTubeValidator.is_youtube_url(clipboard_content):
                        logger.log(
                            f"URL de YouTube detectada en portapapeles: {clipboard_content}",
                            "INFO",
                        )
                        self.url_detected.emit(clipboard_content)
            except Exception as exc:
                if not error_logged:
                    logger.log(f"Aviso temporal en monitor de portapapeles (se reintentara): {exc}", "WARNING")
                    error_logged = True

            # Non-blocking wait so stop requests are handled quickly
            waited = 0.0
            while waited < self.interval and self.is_running:
                time.sleep(0.5)
                waited += 0.5

    def stop(self):
        self.is_running = False


class DependencyInstallWorker(QThread):
    """Dependency-install worker that avoids blocking the UI."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, language="es"):
        super().__init__()
        self.language = language

    def run(self):
        def report(index, total, name):
            self.progress.emit(
                translate(
                    self.language,
                    "deps_installing_item",
                    index=index,
                    total=total,
                    name=name,
                )
            )

        success, message = DependencyManager.install_all_missing(progress_callback=report)
        self.finished.emit(success, message)


import asyncio
import uvicorn


class FolderPickerRequest:
    """Thread-safe container for a folder picker request from the web."""
    def __init__(self):
        self.event = threading.Event()
        self.result = None


class WebBridge(QObject):
    """Thread-safe bridge between FastAPI HTTP threads and the PyQt6 main thread."""
    browse_folder_requested = pyqtSignal(object)
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance


class FastApiServerWorker(QThread):
    """Hilo secundario dedicado a mantener vivo el servidor FastAPI sin congelar PyQt6."""

    def __init__(self, host="127.0.0.1", port=8000):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None

    def run(self):
        logger.log(f"Iniciando API Web en http://{self.host}:{self.port}", "INFO")
        from src.web.app import app
        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            loop="asyncio",
            log_level="info",
            ws_ping_interval=None,
            ws_ping_timeout=None
        )
        self.server = uvicorn.Server(config)
        asyncio.run(self.server.serve())

    def stop(self):
        if self.server:
            self.server.should_exit = True
            logger.log("Servidor FastAPI detenido.", "INFO")

