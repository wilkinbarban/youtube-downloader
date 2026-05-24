"""Shared core: configuration, models, and YouTube utilities."""

from dataclasses import dataclass
from functools import lru_cache
import json
import os
import re
import shutil
import unicodedata
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

from src.config.i18n import translate
from src.utils.logging import logger
from src.config.paths import CONFIG_FILE
from src.utils.errors import Result, map_ytdlp_error, ExtractionError, ConfigError


QUALITY_OPTIONS = ["4k", "1080p", "720p", "480p", "360p", "best", "audio"]
DEFAULT_QUALITY_OPTIONS = ["4k", "1080p", "720p", "480p", "360p", "best"]


def normalize_string(text):
    """Normalize text for safe Windows file names."""
    if not isinstance(text, str):
        return str(text)

    nfkd = unicodedata.normalize("NFKD", text)
    result = "".join(c for c in nfkd if not unicodedata.combining(c))
    for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        result = result.replace(char, "")
    return result.strip()


@lru_cache(maxsize=1)
def ytdlp_js_runtimes():
    for name in ("node", "node.exe"):
        resolved = shutil.which(name)
        if resolved:
            return {"node": {"path": resolved}}
    return {"node": {}}


def parse_youtube_url(url):
    if not isinstance(url, str) or not url.strip():
        return {}

    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query)
    video_id = query.get("v", [None])[0]
    playlist_id = query.get("list", [None])[0]

    path_parts = [part for part in parsed.path.split("/") if part]
    short_id = None
    if parsed.netloc.endswith("youtu.be") and path_parts:
        short_id = path_parts[0]

    if not video_id and short_id:
        video_id = short_id

    return {
        "parsed": parsed,
        "query": query,
        "video_id": video_id,
        "playlist_id": playlist_id,
        "is_mix": bool(playlist_id and playlist_id.startswith("RD")),
    }


def canonical_video_url(url):
    info = parse_youtube_url(url)
    video_id = info.get("video_id")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url.strip()


def canonical_playlist_url(url):
    info = parse_youtube_url(url)
    playlist_id = info.get("playlist_id")
    video_id = info.get("video_id")
    if playlist_id:
        params = {"list": playlist_id}
        if video_id:
            params["v"] = video_id
        return "https://www.youtube.com/playlist?" + urlencode(params)
    return url.strip()


def quality_label(language, quality_key):
    translation_key = {
        "4k": "quality_4k",
        "1080p": "quality_1080p",
        "720p": "quality_720p",
        "480p": "quality_480p",
        "360p": "quality_360p",
        "best": "quality_best",
        "audio": "quality_audio",
    }.get(quality_key, "quality_best")
    return translate(language, translation_key)


def normalize_quality_key(value):
    if value in QUALITY_OPTIONS:
        return value

    legacy_map = {
        "4K (2160p)": "4k",
        "1080p": "1080p",
        "720p": "720p",
        "480p": "480p",
        "360p": "360p",
        "Mejor disponible": "best",
        "Mejor audio": "audio",
        "Best available": "best",
        "Best audio": "audio",
        "Melhor disponível": "best",
        "Melhor áudio": "audio",
    }
    return legacy_map.get(value, "best")


class PlaylistDetector:
    """Classify whether a URL is a playlist/channel or a single video."""

    @staticmethod
    def is_playlist(url):
        if not url:
            return False

        info = parse_youtube_url(url)
        if info.get("playlist_id"):
            return True

        playlist_indicators = [
            "playlist?list=",
            "/channel/",
            "/@",
            "/playlists",
        ]
        return any(indicator in url for indicator in playlist_indicators)


class YouTubeValidator:
    """Validate accepted YouTube URL patterns."""

    YOUTUBE_PATTERNS = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
        r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/channel/[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/@[\w-]+",
    ]

    @staticmethod
    def is_youtube_url(url):
        if not isinstance(url, str):
            return False
        normalized = url.strip()
        return any(re.match(pattern, normalized) for pattern in YouTubeValidator.YOUTUBE_PATTERNS)


@dataclass
class VideoDownloadTask:
    url: str
    title: str = ""
    quality: str = "720p"
    playlist_id: Optional[str] = None
    state: str = "pendiente"
    progress: float = 0.0
    error_message: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    downloaded_size: int = 0
    total_size: int = 0
    attempt: int = 0
    max_attempts: int = 2

    def mark_attempt(self):
        self.attempt += 1

    def can_retry(self):
        return self.attempt < self.max_attempts


def check_and_convert_json_cookies():
    """Convert cookies.json to Netscape cookies.txt format if it exists."""
    from src.config.paths import BASE_DIR
    import time

    json_path = os.path.join(BASE_DIR, "cookies.json")
    txt_path = os.path.join(BASE_DIR, "cookies.txt")

    if not os.path.exists(json_path):
        return False

    try:
        # Check if json was updated after txt, or if txt doesn't exist
        if os.path.exists(txt_path):
            json_time = os.path.getmtime(json_path)
            txt_time = os.path.getmtime(txt_path)
            if txt_time >= json_time:
                # cookies.txt is already up to date
                return True

        with open(json_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        if not isinstance(cookies, list):
            logger.log("El archivo cookies.json no tiene el formato esperado (debe ser una lista).", "WARNING")
            return False

        lines = [
            "# Netscape HTTP Cookie File\n",
            "# This file was automatically converted from cookies.json by YouTube Downloader.\n\n"
        ]

        count = 0
        for cookie in cookies:
            domain = cookie.get("domain", "")
            if not domain:
                continue

            is_httponly = cookie.get("httpOnly", False)
            domain_prefix = "#HttpOnly_" if is_httponly else ""

            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = cookie.get("path", "/")
            secure = "TRUE" if cookie.get("secure", False) else "FALSE"

            expiration = cookie.get("expirationDate")
            if expiration is None:
                expiration = int(time.time() + 31536000) # 1 year default
            else:
                expiration = int(expiration)

            name = cookie.get("name", "")
            value = cookie.get("value", "")

            # Columns: domain, flag, path, secure, expiration, name, value
            lines.append(f"{domain_prefix}{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}\n")
            count += 1

        with open(txt_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        logger.log(f"Cookies importadas con éxito: se convirtieron {count} cookies de cookies.json a Netscape cookies.txt.", "SUCCESS")
        return True
    except Exception as e:
        logger.log(f"Error al importar cookies.json: {e}", "WARNING")
        return False


class PlaylistExtractor:
    """Extract playable entries from playlists or equivalent URLs."""

    @staticmethod
    def _entry_video_id(entry):
        if not entry or not isinstance(entry, dict):
            return None
        entry_id = entry.get("id")
        if entry_id and str(entry_id) != "NA":
            return str(entry_id)
        for key in ("url", "webpage_url", "original_url"):
            url = entry.get(key)
            if not url:
                continue
            match = re.search(r"(?:v=|youtu\.be/|youtube\.com/embed/)([\w-]{11})", str(url))
            if match:
                return match.group(1)
        return None

    @staticmethod
    def extract_videos(url) -> Result[list, ExtractionError]:
        try:
            import yt_dlp

            source_info = parse_youtube_url(url)
            source_url = canonical_playlist_url(url)
            if source_info.get("is_mix"):
                # For RD mix/radio links, yt-dlp can return thousands of entries only
                # when using watch?v=<id>&list=RD...; playlist?list=RD... is often unviewable.
                mix_video_id = source_info.get("video_id")
                mix_playlist_id = source_info.get("playlist_id")
                if mix_video_id and mix_playlist_id:
                    source_url = (
                        f"https://www.youtube.com/watch?v={mix_video_id}&list={mix_playlist_id}"
                    )
                logger.log(
                    f"Mix/Radio detected. Using extraction URL: {source_url}",
                    "INFO",
                )

            from src.config.paths import BASE_DIR
            from src.utils.logging import YtdlpLogger
            check_and_convert_json_cookies()
            config = Config.load()
            browser = config.get("cookies_browser", "none")
            cookies_txt = os.path.join(BASE_DIR, "cookies.txt")
            use_cookies = os.path.exists(cookies_txt)
            ydl_opts = {
                "extract_flat": True,
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 30,
                "ignoreerrors": True,
                "js_runtimes": ytdlp_js_runtimes(),
                "logger": YtdlpLogger(),
            }
            if use_cookies:
                ydl_opts["cookiefile"] = cookies_txt
            elif browser != "none":
                ydl_opts["cookiesfrombrowser"] = (browser, None, None, None)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=False)
                if info is None:
                    return Result.fail(ExtractionError("No se pudo obtener informacion de la URL"))

                entries = info.get("entries")
                if entries is not None:
                    videos = []
                    for idx, entry in enumerate(entries):
                        if not entry:
                            continue
                        vid = PlaylistExtractor._entry_video_id(entry)
                        if not vid:
                            continue
                        videos.append(
                            {
                                "url": f"https://www.youtube.com/watch?v={vid}",
                                "title": entry.get("title") or f"Video {idx + 1}",
                                "index": idx + 1,
                            }
                        )
                    if not videos:
                        return Result.fail(
                            ExtractionError("La lista no tiene videos validos o todos estan no disponibles")
                        )

                    playlist_title = info.get("title", "Playlist")
                    logger.log(
                        f"Playlist detectada: {playlist_title} ({len(videos)} videos)",
                        "INFO",
                    )
                    return Result.ok(videos)

                vid = info.get("id") or PlaylistExtractor._entry_video_id(info)
                single_video = {
                    "url": f"https://www.youtube.com/watch?v={vid}" if vid else url,
                    "title": info.get("title", "Unknown"),
                    "index": 1,
                }
                logger.log(f"Video individual detectado: {single_video['title']}", "INFO")
                return Result.ok([single_video])
        except Exception as exc:
            mapped_err = map_ytdlp_error(exc, "Error extrayendo informacion")
            logger.log(str(mapped_err), "ERROR")
            return Result.fail(mapped_err)


class Config:
    """Load and save persistent application settings."""

    DEFAULT_CONFIG = {
        "download_folder": os.path.expanduser("~\\Downloads\\YouTube"),
        "clipboard_enabled": True,
        "clipboard_interval": 10,
        "quality": "best",
        "format": "mp4",
        "mix_max_videos": 100,
        "language": "es",
        "cookies_browser": "none",
    }

    MERGE_FORMATS = ("mp4", "mkv", "webm", "mov")

    @staticmethod
    def load():
        merged = Config.DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                    user = json.load(handle)
                if isinstance(user, dict):
                    merged.update(user)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                return Config.DEFAULT_CONFIG.copy()
        merged["quality"] = normalize_quality_key(merged.get("quality"))
        try:
            mix_limit = int(merged.get("mix_max_videos", 100))
        except (TypeError, ValueError):
            mix_limit = 100
        merged["mix_max_videos"] = max(1, min(100, mix_limit))
        return merged

    @staticmethod
    def save(config):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=4, ensure_ascii=False)
            return True
        except OSError as exc:
            logger.log(f"Error guardando configuracion: {exc}", "ERROR")
            raise ConfigError(f"Error guardando configuracion: {exc}") from exc
