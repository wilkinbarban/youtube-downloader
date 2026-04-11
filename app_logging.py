from datetime import datetime
import os
import unicodedata

from app_paths import LOGS_DIR


def clean_console_string(text):
    """Sanitize console output text without stripping valid characters."""
    if not isinstance(text, str):
        return str(text)

    normalized = unicodedata.normalize("NFKD", text)
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).strip()


class Logger:
    """Simple logger that writes to both file and console."""

    def __init__(self, log_dir=LOGS_DIR):
        self.log_dir = log_dir
        self.log_file = os.path.join(
            log_dir,
            f"youtube_downloader_{datetime.now().strftime('%Y%m%d')}.log",
        )
        os.makedirs(log_dir, exist_ok=True)

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"

        try:
            with open(self.log_file, "a", encoding="utf-8") as handle:
                handle.write(log_message + "\n")
        except OSError as exc:
            print(f"Error escribiendo log: {exc}")

        print(f"[{timestamp}] [{level}] {clean_console_string(str(message))}")

    def get_logs(self):
        try:
            with open(self.log_file, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return "No hay logs disponibles"

    def clear_logs(self):
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            return True
        except OSError:
            return False


logger = Logger()
