"""Main application window and UI orchestration."""

from datetime import datetime
import os
import time
import webbrowser
from queue import Empty, Queue

from PyQt6.QtCore import QTimer, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.modules.core import (
    Config,
    PlaylistDetector,
    QUALITY_OPTIONS,
    VideoDownloadTask,
    YouTubeValidator,
    canonical_playlist_url,
    canonical_video_url,
    parse_youtube_url,
    quality_label,
)
from src.modules.ui.dialogs import ConfigDialog, DependenciesDialog, HelpDialog, SupportDialog
from src.services.dependencies import DependencyManager
from src.services.update_service import UpdateService
from src.config.i18n import LANGUAGES, normalize_language, translate
from src.utils.logging import logger
from src.config.paths import APP_ICON
from src.constants import VERSION

from src.services.download_manager import DownloadManager
from src.services.workers import ClipboardMonitor, PlaylistExtractWorker, WebBridge, FolderPickerRequest


class UIDispatcher(QObject):
    state_changed = pyqtSignal()
    summary_ready = pyqtSignal()
    progress = pyqtSignal(str, dict)


class MainWindow(QMainWindow):
    """Coordinate menus, tabs, download queue, and global UI state."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader - Gestor de Descargas")
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowIcon(QIcon(APP_ICON))

        self.config = Config.load()
        self.language = normalize_language(self.config.get("language"))
        self.config["language"] = self.language
        os.makedirs(self.config["download_folder"], exist_ok=True)

        self.clipboard_monitor = None
        self._playlist_extract_worker = None
        self._closing = False
        self.active_row_mapping = {}
        
        self.dispatcher = UIDispatcher()
        self.dispatcher.state_changed.connect(self.on_state_changed)
        self.dispatcher.summary_ready.connect(self._show_download_summary)
        self.dispatcher.progress.connect(self.on_download_progress)

        self.manager = DownloadManager()
        self.manager.add_state_changed_callback(self.dispatcher.state_changed.emit)
        self.manager.add_summary_callback(self.dispatcher.summary_ready.emit)
        self.manager.add_progress_callback(lambda w_id, data: self.dispatcher.progress.emit(w_id, data))

        logger.log("Aplicacion iniciada", "INFO")

        self.init_ui()
        self._apply_platform_runtime_checks()

        # Connect the WebBridge to allow web UI to trigger native folder picker
        self._web_bridge = WebBridge.get_instance()
        self._web_bridge.browse_folder_requested.connect(self._handle_browse_folder_request)

        if self.config["clipboard_enabled"]:
            self.start_clipboard_monitor()
            
    def on_state_changed(self):
        self.update_downloads_table()
        self.update_history_table()

    def on_download_progress(self, worker_id, data):
        row = self.active_row_mapping.get(worker_id)
        if row is None or row >= self.table_downloads.rowCount():
            return

        percent = data.get("percent", 0)
        progress_bar = self.table_downloads.cellWidget(row, 1)
        if isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(int(percent))
            progress_bar.setFormat(f"{percent:.1f}%")

        speed = data.get("speed", 0)
        speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "-- MB/s"
        self.table_downloads.setItem(row, 2, QTableWidgetItem(speed_text))

        eta = data.get("eta", 0)
        eta_text = f"{int(eta)} s" if eta else "--"
        self.table_downloads.setItem(row, 3, QTableWidgetItem(eta_text))

        downloaded = data.get("downloaded", 0)
        total = data.get("total", 0)
        if total > 0:
            size_text = f"{downloaded / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB"
        else:
            size_text = "--"
        self.table_downloads.setItem(row, 4, QTableWidgetItem(size_text))

        status_key = data.get("status_key", "status_downloading")
        self.table_downloads.setItem(row, 5, QTableWidgetItem(self.t(status_key)))

    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Cabecera Unificada (header_card)
        self.header_card = QFrame()
        self.header_card.setObjectName("header_card")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 10, 12, 10)

        # Parte izquierda: Icono + Título/Subtítulo
        left_header_layout = QHBoxLayout()
        left_header_layout.setSpacing(10)
        self.header_icon_label = QLabel()
        pixmap = QPixmap(APP_ICON)
        if not pixmap.isNull():
            self.header_icon_label.setPixmap(
                pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.header_icon_label.setText("📥")
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_layout.setContentsMargins(0, 0, 0, 0)
        self.header_title = QLabel("YouTube Downloader")
        self.header_title.setObjectName("header_title")
        self.header_subtitle = QLabel()
        self.header_subtitle.setObjectName("header_subtitle")
        title_layout.addWidget(self.header_title)
        title_layout.addWidget(self.header_subtitle)
        
        left_header_layout.addWidget(self.header_icon_label)
        left_header_layout.addLayout(title_layout)

        # Parte derecha: Píldoras de estado
        right_header_layout = QHBoxLayout()
        right_header_layout.setSpacing(8)
        right_header_layout.setContentsMargins(0, 0, 0, 0)

        # Cápsula de Monitor de Portapapeles
        self.capsule_monitor = QFrame()
        self.capsule_monitor.setObjectName("capsule_monitor")
        capsule_monitor_layout = QHBoxLayout()
        capsule_monitor_layout.setContentsMargins(10, 5, 10, 5)
        capsule_monitor_layout.setSpacing(6)
        
        self.monitor_status_title = QLabel()
        self.monitor_status_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8;")
        self.monitor_status_light = QFrame()
        self.monitor_status_light.setFixedSize(8, 8)
        self.monitor_status_light.setFrameShape(QFrame.Shape.StyledPanel)
        self.monitor_status_text = QLabel()
        self.monitor_status_text.setObjectName("monitor_status_text")
        
        capsule_monitor_layout.addWidget(self.monitor_status_title)
        capsule_monitor_layout.addWidget(self.monitor_status_light)
        capsule_monitor_layout.addWidget(self.monitor_status_text)
        self.capsule_monitor.setLayout(capsule_monitor_layout)

        # Cápsula de Descargas Activas
        self.capsule_active = QFrame()
        self.capsule_active.setObjectName("capsule_active")
        capsule_active_layout = QHBoxLayout()
        capsule_active_layout.setContentsMargins(10, 5, 10, 5)
        capsule_active_layout.setSpacing(6)
        self.active_icon_lbl = QLabel("⚡")
        self.active_icon_lbl.setStyleSheet("font-size: 10px;")
        self.active_text = QLabel()
        self.active_text.setObjectName("active_text")
        capsule_active_layout.addWidget(self.active_icon_lbl)
        capsule_active_layout.addWidget(self.active_text)
        self.capsule_active.setLayout(capsule_active_layout)

        # Cápsula de Tareas en Cola
        self.capsule_queued = QFrame()
        self.capsule_queued.setObjectName("capsule_queued")
        capsule_queued_layout = QHBoxLayout()
        capsule_queued_layout.setContentsMargins(10, 5, 10, 5)
        capsule_queued_layout.setSpacing(6)
        self.queued_icon_lbl = QLabel("⏳")
        self.queued_icon_lbl.setStyleSheet("font-size: 10px;")
        self.queued_text = QLabel()
        self.queued_text.setObjectName("queued_text")
        capsule_queued_layout.addWidget(self.queued_icon_lbl)
        capsule_queued_layout.addWidget(self.queued_text)
        self.capsule_queued.setLayout(capsule_queued_layout)

        right_header_layout.addWidget(self.capsule_monitor)
        right_header_layout.addWidget(self.capsule_active)
        right_header_layout.addWidget(self.capsule_queued)

        header_layout.addLayout(left_header_layout)
        header_layout.addStretch()
        header_layout.addLayout(right_header_layout)
        self.header_card.setLayout(header_layout)
        main_layout.addWidget(self.header_card)

        # 2. Formulario Inline "Añadir Descarga"
        self.add_task_panel = QFrame()
        self.add_task_panel.setObjectName("add_task_panel")
        add_task_layout = QVBoxLayout()
        add_task_layout.setContentsMargins(12, 10, 12, 10)
        add_task_layout.setSpacing(6)

        self.add_task_title = QLabel()
        self.add_task_title.setObjectName("add_task_title")
        add_task_layout.addWidget(self.add_task_title)

        fields_layout = QHBoxLayout()
        fields_layout.setSpacing(8)
        self.line_url = QLineEdit()
        self.line_url.setObjectName("task_url")
        self.line_url.setMinimumHeight(32)

        self.combo_quality = QComboBox()
        self.combo_quality.setObjectName("task_quality")
        self.combo_quality.setMinimumHeight(32)
        for quality_key in QUALITY_OPTIONS:
            self.combo_quality.addItem(quality_label(self.language, quality_key), quality_key)
        self.combo_quality.setCurrentIndex(max(0, self.combo_quality.findData(self.config["quality"])))

        self.btn_start_download = QPushButton()
        self.btn_start_download.setObjectName("btn_start_download")
        self.btn_start_download.setMinimumHeight(32)
        self.btn_start_download.clicked.connect(self.add_url_inline)

        fields_layout.addWidget(self.line_url, stretch=4)
        fields_layout.addWidget(self.combo_quality, stretch=1)
        fields_layout.addWidget(self.btn_start_download, stretch=1)
        add_task_layout.addLayout(fields_layout)
        self.add_task_panel.setLayout(add_task_layout)
        main_layout.addWidget(self.add_task_panel)

        # 3. Banda de Controles Globales (controls_card)
        self.controls_card = QFrame()
        self.controls_card.setObjectName("controls_card")
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(12, 6, 12, 6)
        controls_layout.setSpacing(8)

        self.lbl_global_controls = QLabel()
        self.lbl_global_controls.setObjectName("lbl_global_controls")
        self.lbl_global_controls.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; text-transform: uppercase;")

        self.btn_pause = QPushButton()
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_pause.setMinimumHeight(28)

        self.btn_cancel = QPushButton()
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self.cancel_active_downloads)
        self.btn_cancel.setMinimumHeight(28)

        self.btn_clear_history = QPushButton()
        self.btn_clear_history.setObjectName("btn_clear_history")
        self.btn_clear_history.clicked.connect(self.clear_history)
        self.btn_clear_history.setMinimumHeight(28)

        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.clicked.connect(self.open_config)
        self.btn_settings.setMinimumHeight(28)

        self.btn_web_manager = QPushButton()
        self.btn_web_manager.setObjectName("btn_web_manager")
        self.btn_web_manager.clicked.connect(self.open_web_manager)
        self.btn_web_manager.setMinimumHeight(28)

        self.btn_clear_queue = QPushButton()
        self.btn_clear_queue.setObjectName("btn_clear_queue")
        self.btn_clear_queue.clicked.connect(self.clear_queue_dialog)
        self.btn_clear_queue.setMinimumHeight(28)
        self.btn_clear_queue.setStyleSheet(
            "background-color: #78350f; color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.2);"
        )

        controls_layout.addWidget(self.lbl_global_controls)
        controls_layout.addSpacing(10)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_cancel)
        controls_layout.addWidget(self.btn_clear_history)
        controls_layout.addWidget(self.btn_clear_queue)
        controls_layout.addWidget(self.btn_settings)
        controls_layout.addWidget(self.btn_web_manager)
        controls_layout.addStretch()
        self.controls_card.setLayout(controls_layout)
        main_layout.addWidget(self.controls_card)

        # 4. Tabs principales
        self.tabs = QTabWidget()
        self.tab_downloads = QWidget()
        self.init_downloads_tab()
        self.tabs.addTab(self.tab_downloads, "Descargas")

        self.tab_history = QWidget()
        self.init_history_tab()
        self.tabs.addTab(self.tab_history, "Historial")

        self.tab_logs = QWidget()
        self.init_logs_tab()
        self.tabs.addTab(self.tab_logs, "Logs")

        main_layout.addWidget(self.tabs)

        central.setLayout(main_layout)
        self.setCentralWidget(central)
        self.init_menu_bar()
        self.update_ui_texts()
        self.update_monitor_indicator()
        self._apply_theme_stylesheet()

    def _apply_theme_stylesheet(self):
        QApplication.instance().setStyleSheet("""
            /* Global Window and Widget Background */
            QMainWindow, QDialog {
                background-color: #070913;
                color: #f1f5f9;
            }

            QWidget {
                font-family: 'Outfit', 'Segoe UI', sans-serif;
                color: #cbd5e1;
            }

            /* Menu Bar and Menus */
            QMenuBar {
                background-color: #070913;
                color: #cbd5e1;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }

            QMenuBar::item {
                background: transparent;
                padding: 6px 12px;
            }

            QMenuBar::item:selected {
                background-color: #1e1b4b;
                color: #ffffff;
                border-radius: 6px;
            }

            QMenu {
                background-color: #0a0d1d;
                border: 1px solid rgba(168, 85, 247, 0.2);
                border-radius: 10px;
                padding: 6px;
            }

            QMenu::item {
                padding: 6px 24px;
                border-radius: 6px;
                color: #cbd5e1;
            }

            QMenu::item:selected {
                background-color: #8b5cf6;
                color: #ffffff;
            }

            /* Header Card & Status Capsules */
            QFrame#header_card {
                background-color: rgba(11, 15, 30, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 16px;
            }

            QLabel#header_title {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
                font-family: 'Outfit', 'Segoe UI', sans-serif;
            }

            QLabel#header_subtitle {
                font-size: 10px;
                font-weight: 700;
                color: #a855f7;
                text-transform: uppercase;
                letter-spacing: 1.5px;
            }

            QFrame#capsule_monitor, QFrame#capsule_active, QFrame#capsule_queued {
                background-color: rgba(15, 23, 42, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
            }

            QLabel#monitor_status_text, QLabel#active_text, QLabel#queued_text {
                font-size: 10px;
                font-weight: 600;
                color: #e2e8f0;
            }

            /* Add Task Inline Panel */
            QFrame#add_task_panel {
                background-color: rgba(11, 15, 30, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-top: 3px solid #8b5cf6;
                border-radius: 16px;
            }

            QLabel#add_task_title {
                font-size: 11px;
                font-weight: bold;
                color: #f1f5f9;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            QLineEdit#task_url {
                background-color: rgba(15, 23, 42, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }

            QLineEdit#task_url:focus {
                border: 1px solid #a855f7;
            }

            QComboBox#task_quality {
                background-color: rgba(15, 23, 42, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }

            QComboBox#task_quality:focus {
                border: 1px solid #a855f7;
            }

            QPushButton#btn_start_download {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 8px;
            }

            QPushButton#btn_start_download:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #f43f5e);
            }

            /* Controls Card */
            QFrame#controls_card {
                background-color: rgba(15, 23, 42, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
            }

            /* Tab Widget Pane and Tabs */
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 16px;
                background-color: rgba(11, 15, 30, 0.55);
            }

            QTabBar::tab {
                background-color: #070913;
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 20px;
                font-weight: 500;
                margin-right: 4px;
            }

            QTabBar::tab:hover {
                background-color: #111827;
                color: #f1f5f9;
            }

            QTabBar::tab:selected {
                background-color: rgba(11, 15, 30, 0.55);
                color: #a855f7;
                border-bottom: 2px solid #a855f7;
                font-weight: bold;
            }

            /* Push Buttons */
            QPushButton {
                background-color: #1e1b4b;
                color: #f8fafc;
                border: 1px solid rgba(168, 85, 247, 0.2);
                border-radius: 10px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 11px;
            }

            QPushButton:hover {
                background-color: #312e81;
                border-color: #a855f7;
            }

            QPushButton:pressed {
                background-color: #4c1d95;
                border-color: #f43f5e;
            }

            QPushButton:disabled {
                background-color: rgba(15, 23, 42, 0.6);
                color: #475569;
                border-color: rgba(255, 255, 255, 0.02);
            }

            /* Specific Accent buttons */
            QPushButton#btn_save, QPushButton#primaryBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }

            QPushButton#btn_save:hover, QPushButton#primaryBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #f43f5e);
            }

            QPushButton#btn_cancel {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: 1px solid rgba(239, 68, 68, 0.25);
            }

            QPushButton#btn_cancel:hover {
                background-color: #b91c1c;
                color: #ffffff;
                border-color: #fca5a5;
            }

            /* Text Editors & Line Inputs */
            QLineEdit, QSpinBox, QComboBox {
                background-color: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 7px 12px;
                color: #f8fafc;
                selection-background-color: rgba(168, 85, 247, 0.35);
                selection-color: #f8fafc;
            }

            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #a855f7;
            }

            QTextEdit {
                background-color: rgba(15, 23, 42, 0.65);
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 12px;
                font-family: 'Outfit', 'Segoe UI', sans-serif;
                font-size: 12px;
            }

            QTextEdit#text_logs, QTextEdit#text_info {
                background-color: rgba(5, 5, 10, 0.85);
                color: #34d399; /* Neon Emerald for terminal */
                border: 1px solid rgba(168, 85, 247, 0.15);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                selection-background-color: rgba(52, 211, 153, 0.2);
                selection-color: #34d399;
            }

            /* Dialog Settings Card Frames */
            QFrame#group_general, QFrame#group_clipboard, QFrame#group_cookies {
                background-color: rgba(11, 15, 30, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 12px;
            }

            /* Custom CheckBox styling with portable SVG base64 checkmark */
            QCheckBox {
                spacing: 8px;
                color: #cbd5e1;
                font-size: 11px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
            }

            QCheckBox::indicator:hover {
                border: 1px solid #a855f7;
            }

            QCheckBox::indicator:checked {
                background-color: #8b5cf6;
                border: 1px solid #a855f7;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPgogIDxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPgo8L3N2Zz4=");
            }


            QComboBox::drop-down {
                border: none;
                background: transparent;
            }

            QComboBox QAbstractItemView {
                background-color: #0a0d1d;
                border: 1px solid rgba(168, 85, 247, 0.2);
                selection-background-color: #a855f7;
                selection-color: #ffffff;
                color: #cbd5e1;
                border-radius: 8px;
            }

            /* Table Widgets */
            QTableWidget {
                background-color: rgba(15, 23, 42, 0.4);
                gridline-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                color: #e2e8f0;
            }

            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            }

            QTableWidget::item:selected {
                background-color: rgba(168, 85, 247, 0.16);
                color: #ffffff;
                border-left: 3px solid #f43f5e;
            }

            QHeaderView::section {
                background-color: #0a0d1d;
                color: #94a3b8;
                padding: 10px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }

            /* Progress Bar inside Table */
            QProgressBar {
                background-color: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 10px;
            }

            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #f43f5e);
                border-radius: 4px;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                border: none;
                background: #070913;
                width: 6px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background: rgba(168, 85, 247, 0.2);
                min-height: 20px;
                border-radius: 3px;
            }

            QScrollBar::handle:vertical:hover {
                background: rgba(168, 85, 247, 0.5);
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }

            QScrollBar:horizontal {
                border: none;
                background: #070913;
                height: 6px;
                margin: 0px;
            }

            QScrollBar::handle:horizontal {
                background: rgba(168, 85, 247, 0.2);
                min-width: 20px;
                border-radius: 3px;
            }

            QScrollBar::handle:horizontal:hover {
                background: rgba(168, 85, 247, 0.5);
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
            }
        """)

    def init_downloads_tab(self):
        layout = QVBoxLayout()
        self.table_downloads = QTableWidget()
        self.table_downloads.setColumnCount(6)
        self.table_downloads.setHorizontalHeaderLabels(
            ["Titulo", "Progreso", "Velocidad", "Tiempo Est.", "Tamano", "Estado"]
        )
        self.table_downloads.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        # Enable selection of multiple rows and right-click context menu
        self.table_downloads.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_downloads.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table_downloads.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_downloads.customContextMenuRequested.connect(self.on_downloads_context_menu)
        layout.addWidget(self.table_downloads)
        self.tab_downloads.setLayout(layout)

    def init_history_tab(self):
        layout = QVBoxLayout()
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(5)
        self.table_history.setHorizontalHeaderLabels(
            ["Titulo", "Estado", "Calidad", "Fecha", "Error"]
        )
        self.table_history.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table_history)
        self.tab_history.setLayout(layout)

    def init_logs_tab(self):
        layout = QVBoxLayout()
        self.text_logs = QTextEdit()
        self.text_logs.setObjectName("text_logs")
        self.text_logs.setReadOnly(True)
        layout.addWidget(self.text_logs)
        self.tab_logs.setLayout(layout)
        self.refresh_logs()

    def init_menu_bar(self):
        style = self.style()

        self.menu_file = self.menuBar().addMenu("")
        self.menu_downloads = self.menuBar().addMenu("")
        self.menu_view = self.menuBar().addMenu("")
        self.menu_tools = self.menuBar().addMenu("")
        self.menu_language = self.menuBar().addMenu("")
        self.menu_help = self.menuBar().addMenu("")

        self.action_add_url = QAction(self)
        self.action_add_url.triggered.connect(self.add_url_manual)
        self.action_add_url.setShortcut(QKeySequence("Ctrl+N"))
        self.action_add_url.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        self.action_quit = QAction(self)
        self.action_quit.triggered.connect(self.close)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))

        self.action_pause = QAction(self)
        self.action_pause.triggered.connect(self.toggle_pause)
        self.action_pause.setShortcut(QKeySequence("Ctrl+P"))
        self.action_pause.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))

        self.action_cancel_active = QAction(self)
        self.action_cancel_active.triggered.connect(self.cancel_active_downloads)
        self.action_cancel_active.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))

        self.action_show_downloads = QAction(self)
        self.action_show_downloads.triggered.connect(lambda: self.tabs.setCurrentWidget(self.tab_downloads))
        self.action_show_downloads.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))

        self.action_show_history = QAction(self)
        self.action_show_history.triggered.connect(lambda: self.tabs.setCurrentWidget(self.tab_history))
        self.action_show_history.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))

        self.action_show_logs = QAction(self)
        self.action_show_logs.triggered.connect(lambda: self.tabs.setCurrentWidget(self.tab_logs))
        self.action_show_logs.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))

        self.action_clear_history = QAction(self)
        self.action_clear_history.triggered.connect(self.clear_history)
        self.action_clear_history.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        self.action_refresh_logs = QAction(self)
        self.action_refresh_logs.triggered.connect(self.refresh_logs)
        self.action_refresh_logs.setShortcut(QKeySequence.StandardKey.Refresh)
        self.action_refresh_logs.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

        self.action_clear_logs = QAction(self)
        self.action_clear_logs.triggered.connect(self.clear_logs_dialog)
        self.action_clear_logs.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        self.language_actions = {}
        for code in LANGUAGES:
            action = QAction(self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, lang_code=code: self.apply_language(lang_code))
            action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            self.language_actions[code] = action

        self.action_config = QAction(self)
        self.action_config.triggered.connect(self.open_config)
        self.action_config.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))

        self.action_dependencies = QAction(self)
        self.action_dependencies.triggered.connect(self.open_dependencies)
        self.action_dependencies.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        self.action_web_manager = QAction(self)
        self.action_web_manager.triggered.connect(self.open_web_manager)
        self.action_web_manager.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        self.action_about = QAction(self)
        self.action_about.triggered.connect(self.show_about_dialog)
        self.action_about.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))

        self.action_help_manual = QAction(self)
        self.action_help_manual.triggered.connect(self.show_help_dialog)
        self.action_help_manual.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton))

        self.action_check_updates = QAction(self)
        self.action_check_updates.triggered.connect(self._action_check_updates)
        self.action_check_updates.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

        self.action_donate = QAction(self)
        self.action_donate.triggered.connect(self.show_support_dialog)
        self.action_donate.setText(self.t("action_support_project"))
        self.action_donate.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))

        self.menu_file.addAction(self.action_add_url)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_quit)

        self.menu_downloads.addAction(self.action_pause)
        self.menu_downloads.addAction(self.action_cancel_active)
        self.menu_downloads.addSeparator()
        self.menu_downloads.addAction(self.action_clear_history)

        self.menu_view.addAction(self.action_show_downloads)
        self.menu_view.addAction(self.action_show_history)
        self.menu_view.addAction(self.action_show_logs)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.action_refresh_logs)
        self.menu_view.addAction(self.action_clear_logs)

        self.menu_tools.addAction(self.action_config)
        self.menu_tools.addAction(self.action_dependencies)
        self.menu_tools.addAction(self.action_web_manager)

        for code in LANGUAGES:
            self.menu_language.addAction(self.language_actions[code])

        self.menu_help.addAction(self.action_help_manual)
        self.menu_help.addAction(self.action_check_updates)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.action_donate)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.action_about)

    def _enqueue_playlist_tasks(self, videos, quality):
        playlist_id = f"playlist_{int(time.time())}"
        for video in videos:
            task = VideoDownloadTask(
                url=video["url"],
                title=video["title"],
                quality=quality,
                playlist_id=playlist_id,
            )
            self.manager.enqueue_task(task)
        return len(videos)

    def _enqueue_single_video(self, url, quality, source_label):
        normalized_url = canonical_video_url(url)
        task = VideoDownloadTask(
            url=normalized_url,
            title=self.t("loading_title"),
            quality=quality,
        )
        self.manager.enqueue_task(task)
        logger.log(
            f"Video agregado desde {source_label}: {normalized_url} (Calidad: {quality})",
            "INFO",
        )
        self.update_downloads_table()
        return normalized_url


    def _begin_playlist_extract(self, url, quality, add_dialog=None, log_prefix="Playlist agregada"):
        parent = add_dialog if add_dialog is not None else self
        normalized_url = canonical_playlist_url(url)
        url_info = parse_youtube_url(url)
        is_mix = bool(url_info.get("is_mix"))
        extract_url = url if is_mix else normalized_url
        if self._playlist_extract_worker is not None and self._playlist_extract_worker.isRunning():
            QMessageBox.warning(
                parent,
                self.t("playlist_title"),
                self.t("playlist_extract_in_progress"),
            )
            return

        if is_mix:
            logger.log(
                "Mix/Radio URL detected. Trying playlist extraction first.",
                "INFO",
            )
        if normalized_url != url:
            logger.log(f"URL de playlist normalizada: {normalized_url}", "INFO")

        progress = QProgressDialog(
            self.t("playlist_progress"),
            None,
            0,
            0,
            parent,
        )
        progress.setWindowTitle(self.t("playlist_title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        worker = PlaylistExtractWorker(extract_url)
        self._playlist_extract_worker = worker

        def on_done(success, videos, error):
            progress.close()
            self._playlist_extract_worker = None
            if not success:
                if is_mix:
                    logger.log(
                        f"RD extraction result for {extract_url}: detected_videos=0 (error)",
                        "WARNING",
                    )
                    logger.log(
                        "Mix/Radio extraction failed. Falling back to current video.",
                        "WARNING",
                    )
                    single_url = self._enqueue_single_video(url, quality, "mix/radio fallback")
                    QMessageBox.information(
                        parent,
                        self.t("mix_detected_title"),
                        self.t("mix_detected_message", url=single_url),
                    )
                    if add_dialog is not None:
                        try:
                            add_dialog.accept()
                        except RuntimeError:
                            pass
                    return
                err = self._localize_error(error)
                logger.log(f"Error extrayendo playlist: {err}", "ERROR")
                QMessageBox.warning(
                    parent,
                    self.t("playlist_title"),
                    self.t("playlist_extract_failed", error=err),
                )
                return
            if not videos:
                if is_mix:
                    logger.log(
                        f"RD extraction result for {extract_url}: detected_videos=0",
                        "WARNING",
                    )
                    logger.log(
                        "Mix/Radio returned no entries. Falling back to current video.",
                        "WARNING",
                    )
                    single_url = self._enqueue_single_video(url, quality, "mix/radio fallback")
                    QMessageBox.information(
                        parent,
                        self.t("mix_detected_title"),
                        self.t("mix_detected_message", url=single_url),
                    )
                    if add_dialog is not None:
                        try:
                            add_dialog.accept()
                        except RuntimeError:
                            pass
                    return
                QMessageBox.warning(
                    parent,
                    self.t("playlist_title"),
                    self.t("playlist_no_videos"),
                )
                return
            if is_mix:
                logger.log(
                    f"RD extraction result for {extract_url}: detected_videos={len(videos)}",
                    "INFO",
                )
                mix_limit = int(self.config.get("mix_max_videos", 100))
                mix_limit = max(1, min(100, mix_limit))
                original_count = len(videos)
                if original_count > mix_limit:
                    videos = videos[:mix_limit]
                    logger.log(
                        f"RD queue limit applied: {mix_limit}/{original_count} videos enqueued",
                        "INFO",
                    )
            count = self._enqueue_playlist_tasks(videos, quality)
            logger.log(f"{log_prefix}: {count} videos", "INFO")
            self.update_downloads_table()
            if add_dialog is not None:
                try:
                    add_dialog.accept()
                except RuntimeError:
                    pass

        worker.finished.connect(on_done)
        worker.start()

    def add_url_manual(self):
        self.line_url.setFocus()
        self.line_url.selectAll()

    def add_url_inline(self):
        url = self.line_url.text().strip()
        if not url:
            QMessageBox.warning(self, self.t("msg_error"), self.t("error_enter_url"))
            return
        if not YouTubeValidator.is_youtube_url(url):
            QMessageBox.warning(
                self,
                self.t("msg_error"),
                self.t("error_invalid_youtube_url"),
            )
            return

        quality = self.combo_quality.currentData()
        if PlaylistDetector.is_playlist(url):
            self._begin_playlist_extract(
                url,
                quality,
                add_dialog=None,
                log_prefix="Playlist agregada manualmente",
            )
        else:
            self._enqueue_single_video(url, quality, "manual input inline")
            self.update_downloads_table()
        
        self.line_url.clear()

    def start_clipboard_monitor(self):
        self.clipboard_monitor = ClipboardMonitor(self.config["clipboard_interval"])
        self.clipboard_monitor.url_detected.connect(self.on_clipboard_url_detected)
        self.clipboard_monitor.start()
        logger.log("Monitor de portapapeles iniciado", "INFO")
        self.update_monitor_indicator(True)

    def stop_clipboard_monitor(self):
        if self.clipboard_monitor:
            self.clipboard_monitor.stop()
            self.clipboard_monitor.wait()
            self.clipboard_monitor = None
            logger.log("Monitor de portapapeles detenido", "INFO")
        self.update_monitor_indicator(False)

    def on_clipboard_url_detected(self, url):
        is_playlist = PlaylistDetector.is_playlist(url)
        label = self.t("kind_playlist") if is_playlist else self.t("kind_video")
        reply = QMessageBox.question(
            self,
            self.t("clipboard_detected_title", kind=label),
            self.t(
                "clipboard_detected_message",
                url=url[:50],
                quality=quality_label(self.language, self.config["quality"]),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if is_playlist:
            self._begin_playlist_extract(url, self.config["quality"])
            return

        normalized_url = canonical_video_url(url)
        self._enqueue_single_video(url, self.config["quality"], "portapapeles")

    def _show_download_summary(self):
        state = self.manager.get_state()
        history = state["download_history"]
        if not history:
            return
        successful = len([entry for entry in history if entry["status"] == "success"])
        failed = len([entry for entry in history if entry["status"] == "error"])
        cancelled = len([entry for entry in history if entry["status"] == "cancelled"])

        summary = self.t(
            "summary_body",
            successful=successful,
            failed=failed,
            cancelled=cancelled,
        )
        logger.log(summary, "INFO")
        QMessageBox.information(self, self.t("summary_title"), summary)

    def toggle_pause(self):
        self.manager.toggle_pause()
        paused = self.manager.get_state()['paused']
        if paused:
            logger.log(self.t("pause_log"), "INFO")
        else:
            logger.log(self.t("resume_log"), "INFO")
        self.action_pause.setText(self.t("btn_resume_all") if paused else self.t("btn_pause_all"))
        self.btn_pause.setText(self.t("btn_resume_all") if paused else self.t("btn_pause_all"))

    def cancel_active_downloads(self):
        state = self.manager.get_state()
        if not state["active_downloads"]:
            QMessageBox.information(self, self.t("msg_cancel"), self.t("no_active_downloads"))
            return
        self.manager.cancel_all()
        logger.log("Se solicito cancelacion de todas las descargas activas", "WARNING")

    def clear_history(self):
        reply = QMessageBox.question(
            self,
            self.t("msg_confirm"),
            self.t("clear_history_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.clear_history()
            logger.log("Historial de descargas limpiado", "INFO")

    def clear_queue_dialog(self):
        """Ask user to confirm clearing the entire download queue."""
        reply = QMessageBox.question(
            self,
            self.t("msg_confirm"),
            self.t("confirm_clear_queue"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.clear_queue()
            self.active_row_mapping.clear()
            logger.log(self.t("clear_queue_done"), "INFO")

    def on_downloads_context_menu(self, position):
        """Show a context menu with option to remove selected videos from the queue."""
        selected_rows = self.table_downloads.selectionModel().selectedRows()
        if not selected_rows:
            return
        menu = QMenu(self)
        remove_action = menu.addAction(self.t("menu_remove_videos"))
        action = menu.exec(self.table_downloads.viewport().mapToGlobal(position))
        if action == remove_action:
            count = len(selected_rows)
            reply = QMessageBox.question(
                self,
                self.t("msg_confirm"),
                self.t("confirm_remove_selected", count=count),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            # Collect URLs from selected rows (column 0 = title item stores URL in data role)
            urls_to_remove = []
            for index in selected_rows:
                row = index.row()
                item = self.table_downloads.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole):
                    urls_to_remove.append(item.data(Qt.ItemDataRole.UserRole))
            if urls_to_remove:
                self.manager.remove_pending_tasks_by_url(urls_to_remove)
                self.active_row_mapping.clear()
                logger.log(f"Eliminados {count} videos de la cola", "INFO")

    def _handle_browse_folder_request(self, request):
        """Handle folder picker request from the web interface via WebBridge."""
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                self.t("lbl_download_folder"),
                self.config.get("download_folder", ""),
            )
            request.result = folder if folder else None
        except Exception as e:
            logger.log(f"Error en folder picker: {e}", "ERROR")
            request.result = None
        finally:
            request.event.set()

    def refresh_logs(self):
        self.text_logs.setText(logger.get_logs())
        self.text_logs.verticalScrollBar().setValue(
            self.text_logs.verticalScrollBar().maximum()
        )

    def clear_logs_dialog(self):
        reply = QMessageBox.question(
            self,
            self.t("msg_confirm"),
            self.t("clear_logs_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if logger.clear_logs():
            logger.log("Logs limpiados", "INFO")
            self.refresh_logs()
            QMessageBox.information(self, self.t("msg_success"), self.t("clear_logs_ok"))
        else:
            QMessageBox.warning(self, self.t("msg_error"), self.t("clear_logs_failed"))

    def open_config(self):
        config_dialog = ConfigDialog(self.config, self.language, self)
        config_dialog.config_changed.connect(self.on_config_changed)
        config_dialog.exec()

    def on_config_changed(self, new_config):
        self.config = new_config
        os.makedirs(self.config["download_folder"], exist_ok=True)
        if self.clipboard_monitor:
            self.stop_clipboard_monitor()
        if self.config["clipboard_enabled"]:
            self.start_clipboard_monitor()
        else:
            self.update_monitor_indicator(False)
        logger.log("Configuracion actualizada", "INFO")

    def open_dependencies(self):
        dialog = DependenciesDialog(self.language, self)
        dialog.exec()

    def open_web_manager(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000")
        logger.log("Abriendo gestor asincrono web en el navegador predeterminado.", "INFO")

    def apply_language(self, language):
        self.language = normalize_language(language)
        self.config["language"] = self.language
        Config.save(self.config)
        self.update_ui_texts()
        self.update_downloads_table()
        self.update_history_table()
        QMessageBox.information(self, self.t("btn_language"), self.t("language_saved"))

    def t(self, key, **kwargs):
        return translate(self.language, key, **kwargs)

    def _action_check_updates(self):
        """Manually check latest GitHub release and compare with local version."""
        result = UpdateService.check_for_updates(current_version=VERSION)
        status = result.get("status")

        if status == "error":
            QMessageBox.warning(
                self,
                self.t("version_title"),
                self.t("update_check_error"),
            )
            return

        if status == "available":
            reply = QMessageBox.information(
                self,
                self.t("update_available_title"),
                self.t(
                    "update_available_message",
                    latest=result.get("latest", "-"),
                    current=result.get("current", "-"),
                ),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Ok,
            )
            if reply == QMessageBox.StandardButton.Ok:
                webbrowser.open(result.get("url", "https://github.com/wilkinbarban/youtube-downloader/releases/latest"))
            return

        QMessageBox.information(
            self,
            self.t("version_title"),
            self.t("update_up_to_date"),
        )

    def update_ui_texts(self):
        self.setWindowTitle(self.t("app_title"))
        self.monitor_status_title.setText(self.t("monitor_status_label"))
        self.menu_file.setTitle(self.t("menu_file"))
        self.menu_downloads.setTitle(self.t("menu_downloads"))
        self.menu_view.setTitle(self.t("menu_view"))
        self.menu_tools.setTitle(self.t("menu_tools"))
        self.menu_language.setTitle(self.t("menu_language"))
        self.menu_help.setTitle(self.t("menu_help"))

        self.action_add_url.setText(self.t("btn_add_url"))
        self.action_quit.setText(self.t("action_quit"))
        paused = self.manager.get_state()['paused']
        self.action_pause.setText(self.t("btn_resume_all") if paused else self.t("btn_pause_all"))
        self.action_cancel_active.setText(self.t("btn_cancel_active"))
        self.action_show_downloads.setText(self.t("action_show_downloads"))
        self.action_show_history.setText(self.t("action_show_history"))
        self.action_show_logs.setText(self.t("action_show_logs"))
        self.action_clear_history.setText(self.t("btn_clear_history"))
        self.action_refresh_logs.setText(self.t("btn_refresh_logs"))
        self.action_clear_logs.setText(self.t("btn_clear_logs"))
        self.action_config.setText(self.t("btn_config"))
        self.action_dependencies.setText(self.t("btn_dependencies"))
        self.action_web_manager.setText(self.t("btn_web_manager"))
        self.action_help_manual.setText(self.t("menu_help_manual"))
        self.action_check_updates.setText(self.t("action_updates"))
        self.action_donate.setText(self.t("action_support_project"))
        self.action_about.setText(self.t("menu_about"))
        
        self.add_task_title.setText("🔗 " + self.t("btn_add_url"))
        self.line_url.setPlaceholderText(self.t("placeholder_url"))
        self.btn_start_download.setText(self.t("btn_add_url"))
        
        self.lbl_global_controls.setText(self.t("lbl_global_controls"))
        self.btn_pause.setText(self.t("btn_resume_all") if paused else self.t("btn_pause_all"))
        self.btn_cancel.setText(self.t("btn_cancel_active"))
        self.btn_clear_history.setText(self.t("btn_clear_history"))
        self.btn_clear_queue.setText(self.t("btn_clear_queue"))
        self.btn_settings.setText(self.t("btn_config"))
        self.btn_web_manager.setText(self.t("btn_web_manager"))
        self.header_subtitle.setText(self.t("desktop_manager"))
        
        state = self.manager.get_state()
        active_count = len(state.get('active_downloads', {}))
        pending_count = len(state.get('pending_downloads', []))
        self.active_text.setText(self.t("status_active_capsule", count=active_count))
        self.queued_text.setText(self.t("status_queued_capsule", count=pending_count))

        for code, action in self.language_actions.items():
            action.setText(LANGUAGES[code])
            action.setChecked(code == self.language)
        self.tabs.setTabText(self.tabs.indexOf(self.tab_downloads), self.t("tab_downloads"))
        self.tabs.setTabText(self.tabs.indexOf(self.tab_history), self.t("tab_history"))
        self.tabs.setTabText(self.tabs.indexOf(self.tab_logs), self.t("tab_logs"))
        self.table_downloads.setHorizontalHeaderLabels(
            [
                self.t("downloads_title"),
                self.t("downloads_progress"),
                self.t("downloads_speed"),
                self.t("downloads_eta"),
                self.t("downloads_size"),
                self.t("downloads_status"),
            ]
        )
        self.table_history.setHorizontalHeaderLabels(
            [
                self.t("history_title"),
                self.t("history_status"),
                self.t("history_quality"),
                self.t("history_date"),
                self.t("history_error"),
            ]
        )
        self.update_monitor_indicator()

    def update_downloads_table(self):
        state = self.manager.get_state()
        active_downloads = state["active_downloads"]
        pending_downloads = state["pending_downloads"]

        # Update stats capsules
        active_count = len(active_downloads)
        pending_count = len(pending_downloads)
        self.active_text.setText(self.t("status_active_capsule", count=active_count))
        self.queued_text.setText(self.t("status_queued_capsule", count=pending_count))

        self.active_row_mapping = {}
        self.table_downloads.setRowCount(0)
        row_idx = 0

        for worker_id, download_info in active_downloads.items():
            idx = row_idx
            self.active_row_mapping[worker_id] = idx
            self.table_downloads.insertRow(idx)

            title = download_info.get("title", self.t("loading_short"))
            if len(title) > 50:
                title = title[:47] + "..."
            title_item = QTableWidgetItem(title)
            title_item.setData(Qt.ItemDataRole.UserRole, download_info.get("url", ""))
            self.table_downloads.setItem(idx, 0, title_item)

            progress_data = download_info.get("progress", {})
            percent = progress_data.get("percent", 0)
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(int(percent))
            progress_bar.setTextVisible(True)
            progress_bar.setFormat(f"{percent:.1f}%")
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 4px;
                    background-color: #0e1320;
                    text-align: center;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 10px;
                    height: 16px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #d946ef);
                    border-radius: 3px;
                }
            """)
            self.table_downloads.setCellWidget(idx, 1, progress_bar)

            speed = progress_data.get("speed", 0)
            speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "-- MB/s"
            self.table_downloads.setItem(idx, 2, QTableWidgetItem(speed_text))

            eta = progress_data.get("eta", 0)
            eta_text = f"{int(eta)} s" if eta else "--"
            self.table_downloads.setItem(idx, 3, QTableWidgetItem(eta_text))

            downloaded = progress_data.get("downloaded", 0)
            total = progress_data.get("total", 0)
            if total > 0:
                size_text = f"{downloaded / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB"
            else:
                size_text = "--"
            self.table_downloads.setItem(idx, 4, QTableWidgetItem(size_text))

            status_key = progress_data.get("status_key", "status_downloading")
            status = self.t(status_key)
            self.table_downloads.setItem(idx, 5, QTableWidgetItem(status))
            row_idx += 1

        grouped_pending = {}
        for task in pending_downloads:
            group_key = task.playlist_id or "__single__"
            grouped_pending.setdefault(group_key, []).append(task)

        for group_key, tasks in grouped_pending.items():
            batch_label = None
            if group_key == "__single__":
                group_title = self.t("downloads_group_single", count=len(tasks))
            else:
                batch_label = str(group_key).split("_", 1)[-1]
                group_title = self.t(
                    "downloads_group_playlist",
                    batch=batch_label,
                    count=len(tasks),
                )

            header_idx = row_idx
            self.table_downloads.insertRow(header_idx)
            header_item = QTableWidgetItem(group_title)
            header_item.setBackground(QColor(225, 225, 225))
            self.table_downloads.setItem(header_idx, 0, header_item)
            self.table_downloads.setItem(header_idx, 1, QTableWidgetItem("--"))
            self.table_downloads.setItem(header_idx, 2, QTableWidgetItem("--"))
            self.table_downloads.setItem(header_idx, 3, QTableWidgetItem("--"))
            self.table_downloads.setItem(header_idx, 4, QTableWidgetItem("--"))
            header_status = QTableWidgetItem(self.t("status_pending"))
            header_status.setBackground(QColor(225, 225, 225))
            self.table_downloads.setItem(header_idx, 5, header_status)
            row_idx += 1

            for task in tasks:
                idx = row_idx
                self.table_downloads.insertRow(idx)

                title = task.title or self.t("loading_short")
                if batch_label:
                    title = f"[{batch_label}] {title}"
                if len(title) > 50:
                    title = title[:47] + "..."
                title_item = QTableWidgetItem(title)
                title_item.setData(Qt.ItemDataRole.UserRole, task.url)
                self.table_downloads.setItem(idx, 0, title_item)
                self.table_downloads.setItem(idx, 1, QTableWidgetItem("0.0%"))
                self.table_downloads.setItem(idx, 2, QTableWidgetItem("-- MB/s"))
                self.table_downloads.setItem(idx, 3, QTableWidgetItem("--"))
                self.table_downloads.setItem(idx, 4, QTableWidgetItem("--"))
                self.table_downloads.setItem(idx, 5, QTableWidgetItem(self.t("status_pending")))
                row_idx += 1

    def update_history_table(self):
        self.table_history.setRowCount(0)
        state = self.manager.get_state()
        for idx, entry in enumerate(reversed(state["download_history"])):
            self.table_history.insertRow(idx)
            title = entry["title"][:50]
            self.table_history.setItem(idx, 0, QTableWidgetItem(title))

            status_text = self.t(f"status_{entry['status']}")
            status_item = QTableWidgetItem(status_text)
            if entry["status"] == "success":
                status_item.setBackground(QColor(144, 238, 144))
            elif entry["status"] == "error":
                status_item.setBackground(QColor(255, 107, 107))
            elif entry["status"] == "retrying":
                status_item.setBackground(QColor(255, 200, 100))
            elif entry["status"] == "cancelled":
                status_item.setBackground(QColor(211, 211, 211))
            self.table_history.setItem(idx, 1, status_item)

            quality_text = quality_label(self.language, entry.get("quality", "best"))
            self.table_history.setItem(idx, 2, QTableWidgetItem(quality_text))
            self.table_history.setItem(idx, 3, QTableWidgetItem(entry["date"]))

            error_text = entry["error"] if entry["error"] else "--"
            if isinstance(error_text, str) and len(error_text) > 50:
                error_text = error_text[:47] + "..."
            self.table_history.setItem(idx, 4, QTableWidgetItem(error_text))

    def _kill_child_processes(self):
        try:
            import psutil
            import os
            
            logger.log("Limpiando procesos huerfanos del sistema...", "INFO")
            current_process = psutil.Process(os.getpid())
            children = current_process.children(recursive=True)
            
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            _, alive = psutil.wait_procs(children, timeout=2)
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
        except Exception as e:
            logger.log(f"Error limpiando procesos hijos: {e}", "ERROR")

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            self.t("close_confirm_title"),
            self.t("close_confirm_message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        self._closing = True
        closing_dialog = QProgressDialog(
            self.t("closing_message"),
            None,
            0,
            0,
            None,
        )
        closing_dialog.setWindowTitle(self.t("closing_title"))
        closing_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        closing_dialog.setMinimumDuration(0)
        closing_dialog.setCancelButton(None)
        closing_dialog.setAutoClose(False)
        closing_dialog.setAutoReset(False)
        closing_dialog.setMinimumWidth(360)
        closing_dialog.setValue(0)
        closing_dialog.show()
        closing_dialog.repaint()
        QApplication.processEvents()

        if self.clipboard_monitor:
            self.stop_clipboard_monitor()
            QApplication.processEvents()

        self.manager.cancel_all()
        QApplication.processEvents()
        
        # Simple wait for daemon threads to finish cancel requests safely
        time.sleep(1)
        QApplication.processEvents()

        if self._playlist_extract_worker and self._playlist_extract_worker.isRunning():
            self._playlist_extract_worker.wait(3000)
            QApplication.processEvents()

        self._kill_child_processes()

        closing_dialog.close()
        logger.log("Aplicacion cerrada", "INFO")
        event.accept()

    def show_about_dialog(self):
        QMessageBox.information(self, self.t("about_title"), self.t("about_body"))

    def show_help_dialog(self):
        """Open user guide in selected language."""
        dialog = HelpDialog(self.language, self)
        dialog.exec()

    def show_support_dialog(self):
        """Open support dialog with QR code for Wise (ES/EN) or PIX (PT)."""
        dialog = SupportDialog(self.language, self)
        dialog.exec()


    def _apply_platform_runtime_checks(self):
        if not DependencyManager.has_ffmpeg_binary():
            logger.log(self.t("ffmpeg_missing"), "WARNING")
            import sys
            import shutil
            
            if sys.platform == "win32" and shutil.which("winget"):
                reply = QMessageBox.question(
                    self,
                    self.t("ffmpeg_install_prompt_title"),
                    self.t("ffmpeg_install_prompt"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._install_ffmpeg_windows()

    def _install_ffmpeg_windows(self):
        import subprocess
        logger.log(self.t("ffmpeg_installing"), "INFO")
        try:
            # CREATE_NEW_CONSOLE = 0x00000010 (opens a new cmd window to show progress)
            proc = subprocess.Popen(
                ["winget", "install", "--id", "Gyan.FFmpeg", "--accept-source-agreements", "--accept-package-agreements"],
                creationflags=0x00000010
            )
            proc.wait()
            
            QMessageBox.information(
                self,
                self.t("ffmpeg_install_prompt_title"),
                self.t("ffmpeg_install_success")
            )
            logger.log("FFmpeg instalado via winget.", "SUCCESS")
        except Exception as e:
            logger.log(f"Error instalando FFmpeg: {e}", "ERROR")
            QMessageBox.warning(
                self,
                self.t("ffmpeg_install_prompt_title"),
                self.t("ffmpeg_install_fail")
            )

    def is_clipboard_monitor_active(self):
        return self.clipboard_monitor is not None and self.clipboard_monitor.isRunning()

    def update_monitor_indicator(self, active=None):
        if active is None:
            active = self.is_clipboard_monitor_active()

        if active:
            color = "#2eaf4a"
            border = "#1d6f2f"
            text = self.t("monitor_status_on")
        else:
            color = "#cf3d3d"
            border = "#8f2424"
            text = self.t("monitor_status_off")

        self.monitor_status_light.setStyleSheet(
            f"background-color: {color}; border: 1px solid {border}; border-radius: 7px;"
        )
        self.monitor_status_text.setText(text)

    def _localize_error(self, error):
        from src.utils.errors import YtdlAppError
        if isinstance(error, YtdlAppError):
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
            }
            translation_key = code_map.get(error.code, "error_unknown")
            if error.code == "DEPENDENCY_ERROR" and "node" in getattr(error, "message", "").lower():
                translation_key = "error_dependency_node"
            return self.t(translation_key)
        elif error is not None:
            return str(error)
        return self.t("error_unknown")
