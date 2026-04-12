"""Shared project paths for assets, temp data, and configuration."""

import os
import sys


def resource_path(*parts):
	"""Resolve bundled or source-tree resource paths."""
	runtime_base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(runtime_base_dir, *parts)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = resource_path("assets")

APP_ICON_ICO = os.path.join(ASSETS_DIR, "icon.ico")
APP_ICON_PNG = os.path.join(ASSETS_DIR, "icon.png")
APP_ICON = APP_ICON_ICO if os.path.exists(APP_ICON_ICO) else APP_ICON_PNG

QR_PAYPAL = os.path.join(ASSETS_DIR, "QR_Paypal.png")

BUNDLED_FFMPEG_DIR = resource_path("ffmpeg", "bin")
BUNDLED_FFMPEG_EXE = os.path.join(BUNDLED_FFMPEG_DIR, "ffmpeg.exe")
BUNDLED_FFPROBE_EXE = os.path.join(BUNDLED_FFMPEG_DIR, "ffprobe.exe")

# Standard Windows paths (Local AppData) for persistent config and logs
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
APP_DATA_DIR = os.path.join(LOCAL_APP_DATA, "YouTube_Downloader")

LOGS_DIR = os.path.join(APP_DATA_DIR, "Logs")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")

os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
