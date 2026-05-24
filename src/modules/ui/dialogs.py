"""Settings, dependency-management, support and help dialogs."""

import os

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, pyqtSignal, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from src.modules.core import Config, DEFAULT_QUALITY_OPTIONS, quality_label
from src.services.dependencies import DependencyManager
from src.config.i18n import translate
from src.utils.logging import logger
from src.services.workers import DependencyInstallWorker


class DependenciesDialog(QDialog):
    """Dialog used to review and install dependencies from the app."""

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(translate(self.language, "deps_title"))
        self.setGeometry(100, 100, 600, 400)
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_title = QLabel(translate(self.language, "deps_title"))
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; margin-bottom: 4px;")
        layout.addWidget(lbl_title)

        self.text_info = QTextEdit()
        self.text_info.setObjectName("text_info")
        self.text_info.setReadOnly(True)
        layout.addWidget(self.text_info)

        h_buttons = QHBoxLayout()
        h_buttons.setSpacing(10)

        self.btn_check = QPushButton(translate(self.language, "deps_check"))
        self.btn_check.setObjectName("btn_check")
        self.btn_check.clicked.connect(self.check_dependencies)
        self.btn_check.setMinimumHeight(30)

        self.btn_install = QPushButton(translate(self.language, "deps_install"))
        self.btn_install.setObjectName("btn_save") # Gradient fucsia-violet
        self.btn_install.clicked.connect(self.install_missing)
        self.btn_install.setMinimumHeight(30)

        btn_close = QPushButton(translate(self.language, "deps_close"))
        btn_close.setObjectName("btn_cancel") # Red accent
        btn_close.clicked.connect(self.close)
        btn_close.setMinimumHeight(30)

        h_buttons.addWidget(self.btn_check)
        h_buttons.addWidget(self.btn_install)
        h_buttons.addWidget(btn_close)
        layout.addLayout(h_buttons)

        self.setLayout(layout)
        self.check_dependencies()

    def check_dependencies(self):
        missing = DependencyManager.check_all_dependencies()
        if not missing:
            message = translate(self.language, "deps_all_ok")
        else:
            lines = "\n".join(f"  - {name}" for name in missing.keys())
            message = translate(self.language, "deps_missing", items=lines)
        self.text_info.setText(message)
        logger.log(f"Verificacion de dependencias: {message}", "INFO")

    def install_missing(self):
        if self.worker and self.worker.isRunning():
            return

        self.btn_install.setEnabled(False)
        self.btn_check.setEnabled(False)
        self.text_info.append(translate(self.language, "deps_installing"))

        self.worker = DependencyInstallWorker(self.language)
        self.worker.progress.connect(self.text_info.append)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_finished(self, success, message):
        self.btn_install.setEnabled(True)
        self.btn_check.setEnabled(True)
        self.check_dependencies()

        if success:
            logger.log(message, "SUCCESS")
            QMessageBox.information(self, translate(self.language, "msg_success"), message)
        else:
            logger.log(message, "WARNING")
            QMessageBox.warning(self, translate(self.language, "msg_warning"), message)


class ConfigDialog(QDialog):
    """Persistent user-settings dialog."""

    config_changed = pyqtSignal(dict)

    def __init__(self, config, language, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.language = language
        self.setWindowTitle(translate(self.language, "config_title"))
        self.setGeometry(100, 100, 520, 480)
        self.init_ui()

    def init_ui(self):
        self.resize(540, 580)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Downloads & Quality Card
        card_general = QFrame()
        card_general.setObjectName("group_general")
        general_layout = QVBoxLayout(card_general)
        general_layout.setContentsMargins(16, 16, 16, 16)
        general_layout.setSpacing(10)

        lbl_gen_title = QLabel(translate(self.language, "config_group_downloads"))
        lbl_gen_title.setObjectName("group_header")
        lbl_gen_title.setStyleSheet("font-weight: bold; color: #a855f7; text-transform: uppercase; font-size: 11px; letter-spacing: 1px;")
        general_layout.addWidget(lbl_gen_title)

        lbl_folder = QLabel(translate(self.language, "config_download_folder"))
        general_layout.addWidget(lbl_folder)
        h_folder = QHBoxLayout()
        self.line_folder = QLineEdit(self.config["download_folder"])
        btn_browse = QPushButton(translate(self.language, "config_browse"))
        btn_browse.setObjectName("btn_browse")
        btn_browse.clicked.connect(self.browse_folder)
        btn_browse.setMinimumHeight(30)
        h_folder.addWidget(self.line_folder)
        h_folder.addWidget(btn_browse)
        general_layout.addLayout(h_folder)

        h_row1 = QHBoxLayout()
        v_col1 = QVBoxLayout()
        v_col1.addWidget(QLabel(translate(self.language, "config_default_quality")))
        self.combo_quality = QComboBox()
        self._quality_keys = list(DEFAULT_QUALITY_OPTIONS)
        for quality_key in self._quality_keys:
            self.combo_quality.addItem(quality_label(self.language, quality_key), quality_key)
        current_quality = self.config["quality"]
        if current_quality not in self._quality_keys:
            current_quality = "best"
        current_index = max(0, self._quality_keys.index(current_quality))
        self.combo_quality.setCurrentIndex(current_index)
        v_col1.addWidget(self.combo_quality)
        h_row1.addLayout(v_col1)

        v_col2 = QVBoxLayout()
        v_col2.addWidget(QLabel(translate(self.language, "config_output_format")))
        self.combo_format = QComboBox()
        self.combo_format.addItems(list(Config.MERGE_FORMATS))
        fmt = (self.config.get("format") or "mp4").strip().lstrip(".").lower() or "mp4"
        if fmt not in Config.MERGE_FORMATS:
            fmt = "mp4"
        self.combo_format.setCurrentText(fmt)
        self.combo_format.setToolTip(
            translate(self.language, "config_output_format_tooltip")
        )
        v_col2.addWidget(self.combo_format)
        h_row1.addLayout(v_col2)
        general_layout.addLayout(h_row1)

        # Mix Limit field
        h_mix = QHBoxLayout()
        lbl_mix = QLabel(translate(self.language, "config_mix_max_videos"))
        self.spin_mix_max_videos = QSpinBox()
        self.spin_mix_max_videos.setMinimum(1)
        self.spin_mix_max_videos.setMaximum(100)
        self.spin_mix_max_videos.setValue(int(self.config.get("mix_max_videos", 100)))
        self.spin_mix_max_videos.setToolTip(
            translate(self.language, "config_mix_max_videos_tooltip")
        )
        h_mix.addWidget(lbl_mix)
        h_mix.addWidget(self.spin_mix_max_videos)
        general_layout.addLayout(h_mix)

        main_layout.addWidget(card_general)

        # 2. Clipboard Monitor Card
        card_clipboard = QFrame()
        card_clipboard.setObjectName("group_clipboard")
        clip_layout = QVBoxLayout(card_clipboard)
        clip_layout.setContentsMargins(16, 16, 16, 16)
        clip_layout.setSpacing(10)

        lbl_clip_title = QLabel(translate(self.language, "config_clipboard"))
        lbl_clip_title.setObjectName("group_header")
        lbl_clip_title.setStyleSheet("font-weight: bold; color: #a855f7; text-transform: uppercase; font-size: 11px; letter-spacing: 1px;")
        clip_layout.addWidget(lbl_clip_title)

        self.check_clipboard = QCheckBox(translate(self.language, "config_enable_clipboard"))
        self.check_clipboard.setObjectName("check_clipboard")
        self.check_clipboard.setChecked(self.config["clipboard_enabled"])
        clip_layout.addWidget(self.check_clipboard)

        h_row_clip = QHBoxLayout()
        h_row_clip.addWidget(QLabel(translate(self.language, "config_interval")))
        self.spin_interval = QSpinBox()
        self.spin_interval.setMinimum(1)
        self.spin_interval.setMaximum(60)
        self.spin_interval.setValue(self.config["clipboard_interval"])
        h_row_clip.addWidget(self.spin_interval)
        clip_layout.addLayout(h_row_clip)

        main_layout.addWidget(card_clipboard)

        # 3. Authentication & Cookies Card
        card_cookies = QFrame()
        card_cookies.setObjectName("group_cookies")
        cookies_layout = QVBoxLayout(card_cookies)
        cookies_layout.setContentsMargins(16, 16, 16, 16)
        cookies_layout.setSpacing(10)

        lbl_cook_title = QLabel(translate(self.language, "config_group_auth"))
        lbl_cook_title.setObjectName("group_header")
        lbl_cook_title.setStyleSheet("font-weight: bold; color: #a855f7; text-transform: uppercase; font-size: 11px; letter-spacing: 1px;")
        cookies_layout.addWidget(lbl_cook_title)

        cookies_layout.addWidget(QLabel(translate(self.language, "config_cookies_browser")))
        self.combo_cookies = QComboBox()
        self._browser_keys = ["none", "chrome", "firefox", "edge", "brave", "opera"]
        self.combo_cookies.addItem(translate(self.language, "config_cookies_none"), "none")
        self.combo_cookies.addItem("Chrome", "chrome")
        self.combo_cookies.addItem("Firefox", "firefox")
        self.combo_cookies.addItem("Edge", "edge")
        self.combo_cookies.addItem("Brave", "brave")
        self.combo_cookies.addItem("Opera", "opera")

        current_browser = self.config.get("cookies_browser", "none")
        if current_browser not in self._browser_keys:
            current_browser = "none"
        self.combo_cookies.setCurrentIndex(self._browser_keys.index(current_browser))
        cookies_layout.addWidget(self.combo_cookies)

        cookies_layout.addWidget(QLabel("Archivo de cookies local (cookies.txt / cookies.json):"))
        h_cookies_file = QHBoxLayout()
        btn_import_cookies = QPushButton("Importar cookies...")
        btn_import_cookies.setObjectName("btn_import_cookies")
        btn_import_cookies.clicked.connect(self.import_cookies_file)
        btn_import_cookies.setMinimumHeight(30)
        h_cookies_file.addWidget(btn_import_cookies)

        self.label_cookies_status = QLabel()
        self.label_cookies_status.setObjectName("label_cookies_status")
        self.update_cookies_status()
        h_cookies_file.addWidget(self.label_cookies_status)
        cookies_layout.addLayout(h_cookies_file)

        main_layout.addWidget(card_cookies)

        # Buttons
        h_buttons = QHBoxLayout()
        h_buttons.setSpacing(10)
        btn_save = QPushButton(translate(self.language, "btn_save"))
        btn_save.setObjectName("btn_save") # Gradient fucsia-violet
        btn_cancel = QPushButton(translate(self.language, "btn_cancel"))
        btn_cancel.setObjectName("btn_cancel") # Red accent
        btn_save.clicked.connect(self.save_config)
        btn_cancel.clicked.connect(self.reject)
        btn_save.setMinimumHeight(32)
        btn_cancel.setMinimumHeight(32)
        h_buttons.addWidget(btn_save)
        h_buttons.addWidget(btn_cancel)
        main_layout.addLayout(h_buttons)

        self.setLayout(main_layout)

    def update_cookies_status(self):
        from src.config.paths import BASE_DIR
        cookies_txt = os.path.join(BASE_DIR, "cookies.txt")
        cookies_json = os.path.join(BASE_DIR, "cookies.json")
        
        if os.path.exists(cookies_txt):
            self.label_cookies_status.setText("🟢 Activo (cookies.txt)")
        elif os.path.exists(cookies_json):
            self.label_cookies_status.setText("🟡 Pendiente (cookies.json)")
        else:
            self.label_cookies_status.setText("🔴 Sin archivo de cookies")

    def import_cookies_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Archivo de Cookies",
            "",
            "Archivos de Cookies (*.json *.txt);;Todos los archivos (*)"
        )
        if not file_path:
            return
            
        from src.config.paths import BASE_DIR
        from src.modules.core import check_and_convert_json_cookies
        
        dest_filename = "cookies.json" if file_path.endswith(".json") else "cookies.txt"
        dest_path = os.path.join(BASE_DIR, dest_filename)
        
        try:
            import shutil
            shutil.copy(file_path, dest_path)
            logger.log(f"Archivo de cookies copiado a: {dest_path}", "INFO")
            
            # If it's json, convert it immediately
            if dest_filename == "cookies.json":
                success = check_and_convert_json_cookies()
                if success:
                    QMessageBox.information(self, "Éxito", "Cookies JSON importadas y convertidas a cookies.txt exitosamente.")
                else:
                    QMessageBox.warning(self, "Advertencia", "Se copió el archivo JSON pero falló la conversión. Revisa los logs.")
            else:
                QMessageBox.information(self, "Éxito", "Archivo cookies.txt importado exitosamente.")
                
            self.update_cookies_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al importar el archivo de cookies: {e}")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            translate(self.language, "config_select_folder"),
        )
        if folder:
            self.line_folder.setText(folder)

    def save_config(self):
        self.config["download_folder"] = self.line_folder.text()
        self.config["clipboard_enabled"] = self.check_clipboard.isChecked()
        self.config["clipboard_interval"] = self.spin_interval.value()
        self.config["quality"] = self.combo_quality.currentData()
        fmt = (self.combo_format.currentText() or "mp4").strip().lstrip(".").lower() or "mp4"
        if fmt not in Config.MERGE_FORMATS:
            fmt = "mp4"
        self.config["format"] = fmt
        self.config["mix_max_videos"] = self.spin_mix_max_videos.value()
        self.config["cookies_browser"] = self.combo_cookies.currentData()

        if Config.save(self.config):
            logger.log("Configuracion guardada", "SUCCESS")
            self.config_changed.emit(self.config)
            self.accept()
        else:
            QMessageBox.warning(
                self,
                translate(self.language, "msg_error"),
                translate(self.language, "config_save_failed"),
            )


class SupportDialog(QDialog):
    """Elegant support dialog with generated QR code for Wise (ES/EN) or PIX (PT)."""

    _WISE_URL = "https://wise.com/pay/me/wilkinb3"
    _PIX_KEY = "wilkin.barban@yahoo.com"

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self._is_pt = language == "pt"
        self._target = self._PIX_KEY if self._is_pt else self._WISE_URL
        self._base_dialog_width = 400
        self._base_qr_size = 220
        self._geometry_applied = False
        self._qr_pixmap = None
        self.setWindowTitle(translate(self.language, "support_title"))
        self.setFixedWidth(self._base_dialog_width)
        self.setMinimumHeight(0)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._apply_stylesheet()
        self.init_ui()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0f19;
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1b4b, stop:1 #312e81
                );
                border-radius: 14px;
            }
            QLabel#headingLabel {
                color: #ffffff;
                font-size: 17px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#messageLabel {
                color: #cbd5e1;
                font-size: 12px;
                background: transparent;
            }
            QLabel#noteLabel {
                color: #a78bfa;
                font-size: 11px;
                font-style: italic;
                background: transparent;
            }
            QFrame#qrCard {
                background-color: #0e1320;
                border: 1.5px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
            QLabel#qrImageLabel {
                background: transparent;
            }
            QLabel#hintLabel {
                color: #94a3b8;
                font-size: 11px;
                background: transparent;
            }
            QLabel#targetLabel {
                color: #c084fc;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#copyStatusLabel {
                color: #34d399;
                font-size: 11px;
                font-weight: 600;
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 9px;
                padding: 5px 8px;
            }
            QPushButton#primaryBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 11px;
                min-width: 90px;
                min-height: 28px;
            }
            QPushButton#primaryBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #d946ef);
            }
            QPushButton#secondaryBtn {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 11px;
                min-width: 80px;
                min-height: 28px;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #312e81;
                border-color: #8b5cf6;
            }
            QPushButton#closeBtn {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1.5px solid rgba(255, 255, 255, 0.08);
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 11px;
                min-width: 60px;
                min-height: 28px;
            }
            QPushButton#closeBtn:hover {
                background-color: #312e81;
                border-color: #8b5cf6;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # --- Hero card ---
        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout()
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(8)

        heading = QLabel(translate(self.language, "support_heading"))
        heading.setObjectName("headingLabel")
        heading.setWordWrap(True)
        hero_layout.addWidget(heading)

        message = QLabel(translate(self.language, "support_message"))
        message.setObjectName("messageLabel")
        message.setWordWrap(True)
        hero_layout.addWidget(message)

        note = QLabel(translate(self.language, "support_note"))
        note.setObjectName("noteLabel")
        note.setWordWrap(True)
        hero_layout.addWidget(note)

        hero_card.setLayout(hero_layout)
        main_layout.addWidget(hero_card)

        # --- QR card ---
        qr_card = QFrame()
        qr_card.setObjectName("qrCard")
        qr_layout = QVBoxLayout()
        qr_layout.setContentsMargins(18, 18, 18, 16)
        qr_layout.setSpacing(10)
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.qr_label = QLabel()
        self.qr_label.setObjectName("qrImageLabel")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_qr_size(self._base_qr_size)

        self._qr_pixmap = self._build_qr_pixmap(self._target)
        if self._qr_pixmap and not self._qr_pixmap.isNull():
            self._update_qr_pixmap()
        else:
            self.qr_label.setText(translate(self.language, "support_qr_error"))
            self.qr_label.setWordWrap(True)
            self.qr_label.setStyleSheet("color: #ef4444; font-size: 13px;")

        qr_layout.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.copy_status_label = QLabel("")
        self.copy_status_label.setObjectName("copyStatusLabel")
        self.copy_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.copy_status_label.setWordWrap(False)
        self.copy_status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.copy_status_label.setMinimumHeight(32)
        self.copy_status_label.hide()

        self.copy_status_effect = QGraphicsOpacityEffect(self.copy_status_label)
        self.copy_status_effect.setOpacity(0.0)
        self.copy_status_label.setGraphicsEffect(self.copy_status_effect)

        self.copy_status_animation = QPropertyAnimation(self.copy_status_effect, b"opacity", self)
        self.copy_status_animation.setDuration(260)
        self.copy_status_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        qr_layout.addWidget(self.copy_status_label)

        qr_card.setLayout(qr_layout)
        main_layout.addWidget(qr_card)

        # --- Button row ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        primary_btn = QPushButton(translate(self.language, "support_open"))
        primary_btn.setObjectName("primaryBtn")
        if self._is_pt:
            primary_btn.clicked.connect(self._copy_pix)
        else:
            primary_btn.clicked.connect(self._open_link)
        btn_layout.addWidget(primary_btn)

        if not self._is_pt:
            copy_btn = QPushButton(translate(self.language, "support_copy"))
            copy_btn.setObjectName("secondaryBtn")
            copy_btn.clicked.connect(self._copy_link)
            btn_layout.addWidget(copy_btn)

        close_btn = QPushButton(translate(self.language, "btn_close"))
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
        self._apply_adaptive_geometry()
        self._geometry_applied = True

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_adaptive_geometry()
        self._geometry_applied = True

    def _set_qr_size(self, size):
        self.qr_label.setFixedSize(size, size)

    def _update_qr_pixmap(self):
        if not self._qr_pixmap or self._qr_pixmap.isNull():
            return
        qr_size = self.qr_label.width()
        self.qr_label.setPixmap(
            self._qr_pixmap.scaled(
                qr_size,
                qr_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _adapt_to_available_height(self, available_height):
        frame_margin = 96
        max_height = max(420, available_height - frame_margin)
        qr_size = self._base_qr_size
        self._set_qr_size(qr_size)
        self.layout().activate()

        while self.sizeHint().height() > max_height and qr_size > 180:
            qr_size -= 12
            self._set_qr_size(qr_size)
            self.layout().activate()

        self._update_qr_pixmap()
        self.adjustSize()
        self.resize(self.width(), min(self.sizeHint().height(), max_height))

    def _apply_adaptive_geometry(self):
        target_window = self.parentWidget() if self.parentWidget() is not None else self
        screen = target_window.screen() or self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        self._adapt_to_available_height(screen.availableGeometry().height())

    def _build_qr_pixmap(self, data):
        """Generate a QR code pixmap for the given data string."""
        try:
            import qrcode
            from io import BytesIO

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1e3a8a", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            return pixmap
        except Exception:
            return None

    def _open_link(self):
        QDesktopServices.openUrl(QUrl(self._WISE_URL))

    def _show_copy_feedback(self, message):
        self.copy_status_animation.stop()
        self.copy_status_label.setText(message)
        self.copy_status_label.show()
        self.copy_status_effect.setOpacity(0.0)
        self.copy_status_animation.setStartValue(0.0)
        self.copy_status_animation.setEndValue(1.0)
        self.copy_status_animation.start()
        QTimer.singleShot(1800, self._hide_copy_feedback)

    def _hide_copy_feedback(self):
        if self.copy_status_label.isHidden():
            return
        self.copy_status_animation.stop()
        self.copy_status_animation.setStartValue(self.copy_status_effect.opacity())
        self.copy_status_animation.setEndValue(0.0)
        self.copy_status_animation.finished.connect(self._finalize_copy_feedback_hide)
        self.copy_status_animation.start()

    def _finalize_copy_feedback_hide(self):
        try:
            self.copy_status_animation.finished.disconnect(self._finalize_copy_feedback_hide)
        except TypeError:
            pass
        if self.copy_status_effect.opacity() == 0.0:
            self.copy_status_label.hide()

    def _copy_link(self):
        try:
            import pyperclip
            pyperclip.copy(self._WISE_URL)
            self._show_copy_feedback(translate(self.language, "support_link_copied"))
        except Exception:
            pass

    def _copy_pix(self):
        try:
            import pyperclip
            pyperclip.copy(self._PIX_KEY)
            self._show_copy_feedback(translate(self.language, "support_pix_copied"))
        except Exception:
            pass


class HelpDialog(QDialog):
    """User-friendly help manual dialog shown from the Help menu."""

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(translate(self.language, "help_manual_title"))
        self.setGeometry(120, 80, 860, 680)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_title = QLabel(translate(self.language, "help_manual_title"))
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; margin-bottom: 4px;")
        layout.addWidget(lbl_title)

        self.text_help = QTextEdit()
        self.text_help.setObjectName("text_help")
        self.text_help.setReadOnly(True)
        self.text_help.setPlainText(translate(self.language, "help_manual_body"))
        layout.addWidget(self.text_help)

        btn_close = QPushButton(translate(self.language, "btn_close"))
        btn_close.setObjectName("btn_cancel") # Red style close button
        btn_close.clicked.connect(self.accept)
        btn_close.setMinimumHeight(30)
        layout.addWidget(btn_close)

        self.setLayout(layout)



