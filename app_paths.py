"""Shared project paths for assets, temp data, and configuration."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

APP_ICON_ICO = os.path.join(ASSETS_DIR, "icon.ico")
APP_ICON_PNG = os.path.join(ASSETS_DIR, "icon.png")
APP_ICON = APP_ICON_ICO if os.path.exists(APP_ICON_ICO) else APP_ICON_PNG

QR_PAYPAL = os.path.join(ASSETS_DIR, "QR_Paypal.png")

# Standard Windows paths (Local AppData) for persistent config and logs
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
APP_DATA_DIR = os.path.join(LOCAL_APP_DATA, "YouTube_Downloader")

LOGS_DIR = os.path.join(APP_DATA_DIR, "Logs")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")

os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
