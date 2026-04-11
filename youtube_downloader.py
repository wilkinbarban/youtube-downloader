"""Desktop application entry point."""

import sys

from app_dependencies import ensure_runtime_dependencies
from app_paths import APP_ICON


def main():
    """Initialize dependencies, QApplication, and the main window."""
    success, message = ensure_runtime_dependencies()
    if not success:
        print(f"Error: {message}")
        print("Por favor instala manualmente las dependencias y vuelve a intentar.")
        return 1

    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from app_main_window import MainWindow

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
