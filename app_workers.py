"""Qt workers for downloads, playlists, clipboard monitoring, and installs."""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from app_core import (
    PlaylistExtractor,
    YouTubeValidator,
    canonical_video_url,
    normalize_string,
    ytdlp_js_runtimes,
)
from app_dependencies import DependencyManager
from app_logging import logger
from app_i18n import translate


class DownloadCancelled(Exception):
    pass


class PlaylistExtractWorker(QThread):
    """Run playlist extraction outside the main thread."""

    finished = pyqtSignal(bool, object, object)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        success, videos, err = PlaylistExtractor.extract_videos(self.url)
        self.finished.emit(success, videos, err)


class DownloadWorker(QThread):
    """yt-dlp download worker with progress reporting and cancellation."""

    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)

    def __init__(self, url, output_path, quality, format_type, language="es"):
        super().__init__()
        self.url = canonical_video_url(url)
        self.output_path = output_path
        self.quality = quality
        self.format_type = format_type
        self.language = language
        self.video_title = ""
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True
        logger.log(f"Cancelacion solicitada: {self.url}", "INFO")

    def run(self):
        try:
            success = self._download_with_ytdlp()
            if success:
                return
            self.finished.emit(
                {
                    "success": False,
                    "title": self.video_title or self.url,
                    "error": "yt-dlp no esta disponible o la descarga fallo",
                    "cancelled": self._cancel_requested,
                }
            )
        except DownloadCancelled:
            self.finished.emit(
                {
                    "success": False,
                    "title": self.video_title or self.url,
                    "error": "Descarga cancelada por el usuario",
                    "cancelled": True,
                }
            )
        except Exception as exc:
            logger.log(f"Error en descarga: {exc}", "ERROR")
            self.finished.emit(
                {
                    "success": False,
                    "title": self.video_title or self.url,
                    "error": str(exc),
                    "cancelled": self._cancel_requested,
                }
            )

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

        # Phase 1: fetch metadata only to obtain the video title.
        # noplaylist=True ensures a single-video result even when the URL
        # contains a list= parameter (e.g. from a playlist or radio link).
        ydl_extract_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "js_runtimes": ytdlp_js_runtimes(),
        }

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
        }
        if self.quality != "audio":
            ydl_opts["merge_output_format"] = merge_fmt

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
            self.finished.emit(
                {
                    "success": True,
                    "title": title,
                    "error": None,
                    "cancelled": False,
                }
            )
            return True

    def _progress_hook_ytdlp(self, data):
        self._ensure_not_cancelled()
        if data["status"] == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes", 0)
            speed = data.get("speed", 0)
            eta = data.get("eta", 0)
            percent = (downloaded / total) * 100 if total > 0 else 0
            self.progress.emit(
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
            self.progress.emit(
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
