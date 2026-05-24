"""Desktop application entry point."""

import sys

from src.services.dependencies import ensure_runtime_dependencies
from src.config.paths import APP_ICON


def main():
    """Initialize dependencies, QApplication, and the main window."""
    from src.modules.core import check_and_convert_json_cookies
    check_and_convert_json_cookies()

    success, message = ensure_runtime_dependencies()
    if not success:
        print(f"Error: {message}")
        print("Por favor instala manualmente las dependencias y vuelve a intentar.")
        return 1

    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from src.modules.ui.main_window import MainWindow
    from src.services.workers import FastApiServerWorker

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON))

    # Lanzar FastAPI en segundo plano
    web_server = FastApiServerWorker(host="127.0.0.1", port=8000)
    web_server.start()

    window = MainWindow()
    window.show()

    exit_code = app.exec()

    # Asegurar el cierre del servidor web al salir
    web_server.stop()
    web_server.wait()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
