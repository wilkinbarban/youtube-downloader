"""Runtime and Python dependency checks and installation helpers."""

import importlib.util
import os
import shutil
import subprocess
import sys

from app_paths import BUNDLED_FFMPEG_DIR, BUNDLED_FFMPEG_EXE, BUNDLED_FFPROBE_EXE
from app_logging import logger


class DependencyManager:
    """Utilities to validate Python dependencies and runtime environment state."""

    DEPENDENCIES = {
        "pyperclip": ("pyperclip", "pyperclip"),
        "PyQt6": ("PyQt6", "PyQt6"),
        "yt-dlp": ("yt_dlp", "yt-dlp"),
        "psutil": ("psutil", "psutil"),
    }

    @staticmethod
    def check_dependency(import_name):
        return importlib.util.find_spec(import_name) is not None

    @classmethod
    def check_all_dependencies(cls):
        missing = {}
        for display_name, (import_name, pip_name) in cls.DEPENDENCIES.items():
            if not cls.check_dependency(import_name):
                missing[display_name] = pip_name
        return missing

    @staticmethod
    def install_dependency(package_name):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            logger.log(f"Dependencia '{package_name}' instalada exitosamente", "SUCCESS")
            return True
        except subprocess.CalledProcessError as exc:
            logger.log(f"Error instalando '{package_name}': {exc}", "ERROR")
            return False

    @classmethod
    def install_all_missing(cls, progress_callback=None):
        missing = cls.check_all_dependencies()
        if not missing:
            return True, "Todas las dependencias estan instaladas"

        success_count = 0
        total = len(missing)
        for index, (name, pip_name) in enumerate(missing.items(), start=1):
            if progress_callback:
                progress_callback(index, total, name)
            if cls.install_dependency(pip_name):
                success_count += 1

        success = success_count == total
        return success, f"Instaladas {success_count}/{total} dependencias"

    @staticmethod
    def clipboard_backend_available():
        if not DependencyManager.check_dependency("pyperclip"):
            return False
        try:
            import pyperclip

            pyperclip.determine_clipboard()
            return True
        except Exception:
            return False

    @staticmethod
    def has_ffmpeg_binary():
        return DependencyManager.get_ffmpeg_location() is not None

    @staticmethod
    def get_ffmpeg_location():
        """Return a usable ffmpeg location for yt-dlp or None if unavailable."""
        if os.path.exists(BUNDLED_FFMPEG_EXE) and os.path.exists(BUNDLED_FFPROBE_EXE):
            return BUNDLED_FFMPEG_DIR

        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return os.path.dirname(ffmpeg_path)

        return None


def ensure_runtime_dependencies():
    """Try to install missing dependencies before launching the UI."""
    missing = DependencyManager.check_all_dependencies()
    if not missing:
        return True, "Todas las dependencias estan instaladas"

    print("Dependencias faltantes detectadas:")
    for dependency in missing:
        print(f"  - {dependency}")

    print("\nIntentando instalar dependencias faltantes...")
    return DependencyManager.install_all_missing()
