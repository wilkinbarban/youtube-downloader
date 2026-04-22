"""Main application window and UI orchestration."""

from datetime import datetime
import os
import time
import webbrowser
from queue import Empty, Queue

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
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
from src.services.workers import ClipboardMonitor, DownloadWorker, PlaylistExtractWorker


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

        self.download_queue = Queue()
        self.pending_downloads = []
        self.download_history = []
        self.clipboard_monitor = None
        self.paused = False
        self.active_downloads = {}
        self._playlist_extract_worker = None
        self._closing = False

        logger.log("Aplicacion iniciada", "INFO")

        self.init_ui()
        self._apply_platform_runtime_checks()

        if self.config["clipboard_enabled"]:
            self.start_clipboard_monitor()

        self.timer = QTimer()
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(1000)

    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()

        # Barra superior de controles y estado
        control_layout = QHBoxLayout()
        
        self.btn_add_url = QPushButton()
        self.btn_add_url.clicked.connect(self.add_url_manual)
        self.btn_add_url.setMinimumHeight(30)
        
        self.btn_pause = QPushButton()
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_pause.setMinimumHeight(30)
        
        self.btn_cancel = QPushButton()
        self.btn_cancel.clicked.connect(self.cancel_active_downloads)
        self.btn_cancel.setMinimumHeight(30)
        
        self.btn_settings = QPushButton()
        self.btn_settings.clicked.connect(self.open_config)
        self.btn_settings.setMinimumHeight(30)

        control_layout.addWidget(self.btn_add_url)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_cancel)
        control_layout.addWidget(self.btn_settings)
        control_layout.addStretch()

        self.monitor_status_title = QLabel()
        self.monitor_status_light = QFrame()
        self.monitor_status_light.setFixedSize(14, 14)
        self.monitor_status_light.setFrameShape(QFrame.Shape.StyledPanel)
        self.monitor_status_text = QLabel()
        
        # Group monitor status widgets on the right side
        monitor_layout = QHBoxLayout()
        monitor_layout.addWidget(self.monitor_status_title)
        monitor_layout.addWidget(self.monitor_status_light)
        monitor_layout.addWidget(self.monitor_status_text)
        monitor_frame = QFrame()
        monitor_frame.setLayout(monitor_layout)
        
        control_layout.addWidget(monitor_frame)
        main_layout.addLayout(control_layout)

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
            self.download_queue.put(task)
            self.pending_downloads.append(task)
        return len(videos)

    def _enqueue_single_video(self, url, quality, source_label):
        normalized_url = canonical_video_url(url)
        task = VideoDownloadTask(
            url=normalized_url,
            title=self.t("loading_title"),
            quality=quality,
        )
        self.download_queue.put(task)
        self.pending_downloads.append(task)
        logger.log(
            f"Video agregado desde {source_label}: {normalized_url} (Calidad: {quality})",
            "INFO",
        )
        self.update_downloads_table()
        return normalized_url

    def _remove_pending_task(self, task):
        for idx, pending_task in enumerate(self.pending_downloads):
            if pending_task is task:
                self.pending_downloads.pop(idx)
                break

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
                err = (error or "Error desconocido").strip() or "Error desconocido"
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
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("add_url_title"))
        dialog.setGeometry(200, 200, 500, 200)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(self.t("youtube_url_label")))
        line_url = QLineEdit()
        layout.addWidget(line_url)

        layout.addWidget(QLabel(self.t("quality_label")))
        combo_quality = QComboBox()
        for quality_key in QUALITY_OPTIONS:
            combo_quality.addItem(quality_label(self.language, quality_key), quality_key)
        combo_quality.setCurrentIndex(max(0, combo_quality.findData(self.config["quality"])))
        layout.addWidget(combo_quality)

        h_buttons = QHBoxLayout()
        btn_add = QPushButton(self.t("btn_add_url"))
        btn_cancel = QPushButton(self.t("btn_cancel"))

        def add_to_queue():
            url = line_url.text().strip()
            if not url:
                QMessageBox.warning(dialog, self.t("msg_error"), self.t("error_enter_url"))
                return
            if not YouTubeValidator.is_youtube_url(url):
                QMessageBox.warning(
                    dialog,
                    self.t("msg_error"),
                    self.t("error_invalid_youtube_url"),
                )
                return

            quality = combo_quality.currentData()
            if PlaylistDetector.is_playlist(url):
                self._begin_playlist_extract(
                    url,
                    quality,
                    add_dialog=dialog,
                    log_prefix="Playlist agregada manualmente",
                )
                return

            normalized_url = canonical_video_url(url)
            self._enqueue_single_video(url, quality, "entrada manual")
            dialog.close()

        btn_add.clicked.connect(add_to_queue)
        btn_cancel.clicked.connect(dialog.close)
        h_buttons.addWidget(btn_add)
        h_buttons.addWidget(btn_cancel)
        layout.addLayout(h_buttons)

        dialog.setLayout(layout)
        dialog.exec()

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

    def process_queue(self):
        if self.paused or self.download_queue.empty():
            return

        while len(self.active_downloads) < 3:
            try:
                task = self.download_queue.get_nowait()
            except Empty:
                break
            if isinstance(task, VideoDownloadTask):
                self._remove_pending_task(task)
                self.start_download(task)

        self.update_downloads_table()

    def start_download(self, task):
        if not isinstance(task, VideoDownloadTask):
            logger.log("Error: tarea invalida en start_download", "ERROR")
            return

        worker = DownloadWorker(
            task.url,
            self.config["download_folder"],
            task.quality,
            self.config.get("format", "mp4"),
            self.language,
        )
        worker_id = f"{task.url}_{time.time()}"

        task.state = "descargando"
        task.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.mark_attempt()

        self.active_downloads[worker_id] = {
            "worker": worker,
            "task": task,
            "url": task.url,
            "title": task.title,
            "quality": task.quality,
            "start_time": time.time(),
        }

        worker.progress.connect(lambda data: self.on_download_progress(worker_id, data))
        worker.finished.connect(lambda result: self.on_download_finished(worker_id, result))
        worker.start()

        logger.log(
            f"Iniciando descarga: {task.title or task.url} (intento {task.attempt}/{task.max_attempts})",
            "INFO",
        )
        self.update_downloads_table()

    def on_download_progress(self, worker_id, data):
        if worker_id in self.active_downloads:
            self.active_downloads[worker_id]["progress"] = data
            worker = self.active_downloads[worker_id]["worker"]
            if getattr(worker, "video_title", ""):
                self.active_downloads[worker_id]["title"] = worker.video_title
        self.update_downloads_table()

    def on_download_finished(self, worker_id, result):
        if worker_id not in self.active_downloads:
            return

        download_info = self.active_downloads.pop(worker_id)
        task = download_info["task"]
        title = download_info.get("title") or result.get("title") or task.url
        quality = download_info["quality"]
        cancelled = bool(result.get("cancelled"))

        task.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result["success"]:
            task.state = "completado"
            self.download_history.append(
                {
                    "title": result["title"],
                    "status": "success",
                    "date": task.end_time,
                    "error": None,
                    "quality": quality,
                    "playlist_id": task.playlist_id,
                }
            )
            logger.log(f"Descarga completada: {result['title']}", "SUCCESS")
        elif cancelled:
            task.state = "cancelado"
            task.error_message = result["error"]
            self.download_history.append(
                {
                    "title": title,
                    "status": "cancelled",
                    "date": task.end_time,
                    "error": result["error"],
                    "quality": quality,
                    "playlist_id": task.playlist_id,
                }
            )
            logger.log(f"Descarga cancelada: {title}", "WARNING")
        else:
            task.state = "error"
            task.error_message = result["error"]
            if task.can_retry():
                logger.log(
                    f"Reintentando: {title} ({task.attempt}/{task.max_attempts})",
                    "WARNING",
                )
                task.state = "pendiente"
                self.download_queue.put(task)
                self.pending_downloads.append(task)
                self.download_history.append(
                    {
                        "title": title,
                        "status": "retrying",
                        "date": task.end_time,
                        "error": result["error"],
                        "quality": quality,
                        "playlist_id": task.playlist_id,
                    }
                )
            else:
                self.download_history.append(
                    {
                        "title": title,
                        "status": "error",
                        "date": task.end_time,
                        "error": (result["error"] or "Error desconocido")[:120],
                        "quality": quality,
                        "playlist_id": task.playlist_id,
                    }
                )
                logger.log(f"Error final: {title} - {result['error']}", "ERROR")

        self.update_downloads_table()
        self.update_history_table()

        if self.download_queue.empty() and not self.active_downloads and not self._closing:
            self._show_download_summary()

    def _show_download_summary(self):
        if not self.download_history:
            return
        successful = len([entry for entry in self.download_history if entry["status"] == "success"])
        failed = len([entry for entry in self.download_history if entry["status"] == "error"])
        cancelled = len([entry for entry in self.download_history if entry["status"] == "cancelled"])

        summary = self.t(
            "summary_body",
            successful=successful,
            failed=failed,
            cancelled=cancelled,
        )
        logger.log(summary, "INFO")
        QMessageBox.information(self, self.t("summary_title"), summary)

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            logger.log(self.t("pause_log"), "INFO")
        else:
            logger.log(self.t("resume_log"), "INFO")
        self.action_pause.setText(self.t("btn_resume_all") if self.paused else self.t("btn_pause_all"))
        self.btn_pause.setText(self.t("btn_resume_all") if self.paused else self.t("btn_pause_all"))

    def cancel_active_downloads(self):
        if not self.active_downloads:
            QMessageBox.information(self, self.t("msg_cancel"), self.t("no_active_downloads"))
            return
        for download_info in self.active_downloads.values():
            download_info["worker"].cancel()
        logger.log("Se solicito cancelacion de todas las descargas activas", "WARNING")

    def clear_history(self):
        reply = QMessageBox.question(
            self,
            self.t("msg_confirm"),
            self.t("clear_history_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.download_history = []
            logger.log("Historial de descargas limpiado", "INFO")
            self.update_history_table()

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
        self.action_pause.setText(self.t("btn_resume_all") if self.paused else self.t("btn_pause_all"))
        self.action_cancel_active.setText(self.t("btn_cancel_active"))
        self.action_show_downloads.setText(self.t("action_show_downloads"))
        self.action_show_history.setText(self.t("action_show_history"))
        self.action_show_logs.setText(self.t("action_show_logs"))
        self.action_clear_history.setText(self.t("btn_clear_history"))
        self.action_refresh_logs.setText(self.t("btn_refresh_logs"))
        self.action_clear_logs.setText(self.t("btn_clear_logs"))
        self.action_config.setText(self.t("btn_config"))
        self.action_dependencies.setText(self.t("btn_dependencies"))
        self.action_help_manual.setText(self.t("menu_help_manual"))
        self.action_check_updates.setText(self.t("action_updates"))
        self.action_donate.setText(self.t("action_support_project"))
        self.action_about.setText(self.t("menu_about"))
        
        self.btn_add_url.setText(self.t("btn_add_url"))
        self.btn_pause.setText(self.t("btn_resume_all") if self.paused else self.t("btn_pause_all"))
        self.btn_cancel.setText(self.t("btn_cancel_active"))
        self.btn_settings.setText(self.t("btn_config"))

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
        self.table_downloads.setRowCount(0)
        row_idx = 0

        for download_info in self.active_downloads.values():
            idx = row_idx
            self.table_downloads.insertRow(idx)

            title = download_info.get("title", self.t("loading_short"))
            if len(title) > 50:
                title = title[:47] + "..."
            self.table_downloads.setItem(idx, 0, QTableWidgetItem(title))

            progress_data = download_info.get("progress", {})
            percent = progress_data.get("percent", 0)
            self.table_downloads.setItem(idx, 1, QTableWidgetItem(f"{percent:.1f}%"))

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
        for task in self.pending_downloads:
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
                self.table_downloads.setItem(idx, 0, QTableWidgetItem(title))
                self.table_downloads.setItem(idx, 1, QTableWidgetItem("0.0%"))
                self.table_downloads.setItem(idx, 2, QTableWidgetItem("-- MB/s"))
                self.table_downloads.setItem(idx, 3, QTableWidgetItem("--"))
                self.table_downloads.setItem(idx, 4, QTableWidgetItem("--"))
                self.table_downloads.setItem(idx, 5, QTableWidgetItem(self.t("status_pending")))
                row_idx += 1

    def update_history_table(self):
        self.table_history.setRowCount(0)
        for idx, entry in enumerate(reversed(self.download_history)):
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
        self.timer.stop()
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

        for download_info in list(self.active_downloads.values()):
            download_info["worker"].cancel()
        QApplication.processEvents()

        deadline = time.time() + 10
        for download_info in list(self.active_downloads.values()):
            remaining_ms = max(0, int((deadline - time.time()) * 1000))
            download_info["worker"].wait(remaining_ms)
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
            import subprocess
            
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
