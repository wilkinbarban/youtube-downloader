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

        self.btn_check = QPushButton(translate(self.language, "deps_check"))
        self.btn_check.clicked.connect(self.check_dependencies)
        layout.addWidget(self.btn_check)

        self.btn_install = QPushButton(translate(self.language, "deps_install"))
        self.btn_install.clicked.connect(self.install_missing)
        layout.addWidget(self.btn_install)

        self.text_info = QTextEdit()
        self.text_info.setReadOnly(True)
        layout.addWidget(self.text_info)

        btn_close = QPushButton(translate(self.language, "deps_close"))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

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
        layout = QVBoxLayout()

        layout.addWidget(QLabel(translate(self.language, "config_download_folder")))
        h_folder = QHBoxLayout()
        self.line_folder = QLineEdit(self.config["download_folder"])
        btn_browse = QPushButton(translate(self.language, "config_browse"))
        btn_browse.clicked.connect(self.browse_folder)
        h_folder.addWidget(self.line_folder)
        h_folder.addWidget(btn_browse)
        layout.addLayout(h_folder)

        layout.addWidget(QLabel(translate(self.language, "config_clipboard")))
        self.check_clipboard = QCheckBox(translate(self.language, "config_enable_clipboard"))
        self.check_clipboard.setChecked(self.config["clipboard_enabled"])
        layout.addWidget(self.check_clipboard)

        layout.addWidget(QLabel(translate(self.language, "config_interval")))
        self.spin_interval = QSpinBox()
        self.spin_interval.setMinimum(1)
        self.spin_interval.setMaximum(60)
        self.spin_interval.setValue(self.config["clipboard_interval"])
        layout.addWidget(self.spin_interval)

        layout.addWidget(QLabel(translate(self.language, "config_default_quality")))
        self.combo_quality = QComboBox()
        self._quality_keys = list(DEFAULT_QUALITY_OPTIONS)
        for quality_key in self._quality_keys:
            self.combo_quality.addItem(quality_label(self.language, quality_key), quality_key)
        current_quality = self.config["quality"]
        if current_quality not in self._quality_keys:
            current_quality = "best"
        current_index = max(0, self._quality_keys.index(current_quality))
        self.combo_quality.setCurrentIndex(current_index)
        layout.addWidget(self.combo_quality)

        layout.addWidget(QLabel(translate(self.language, "config_output_format")))
        self.combo_format = QComboBox()
        self.combo_format.addItems(list(Config.MERGE_FORMATS))
        fmt = (self.config.get("format") or "mp4").strip().lstrip(".").lower() or "mp4"
        if fmt not in Config.MERGE_FORMATS:
            fmt = "mp4"
        self.combo_format.setCurrentText(fmt)
        self.combo_format.setToolTip(
            translate(self.language, "config_output_format_tooltip")
        )
        layout.addWidget(self.combo_format)

        layout.addWidget(QLabel(translate(self.language, "config_mix_max_videos")))
        self.spin_mix_max_videos = QSpinBox()
        self.spin_mix_max_videos.setMinimum(1)
        self.spin_mix_max_videos.setMaximum(100)
        self.spin_mix_max_videos.setValue(int(self.config.get("mix_max_videos", 100)))
        self.spin_mix_max_videos.setToolTip(
            translate(self.language, "config_mix_max_videos_tooltip")
        )
        layout.addWidget(self.spin_mix_max_videos)

        h_buttons = QHBoxLayout()
        btn_save = QPushButton(translate(self.language, "btn_save"))
        btn_cancel = QPushButton(translate(self.language, "btn_cancel"))
        btn_save.clicked.connect(self.save_config)
        btn_cancel.clicked.connect(self.reject)
        h_buttons.addWidget(btn_save)
        h_buttons.addWidget(btn_cancel)
        layout.addLayout(h_buttons)

        self.setLayout(layout)

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
        self._base_dialog_width = 480
        self._base_qr_size = 280
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
                background-color: #f8fafc;
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e3a8a, stop:1 #2563eb
                );
                border-radius: 14px;
            }
            QLabel#headingLabel {
                color: #ffffff;
                font-size: 19px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#messageLabel {
                color: #dbeafe;
                font-size: 13px;
                background: transparent;
            }
            QLabel#noteLabel {
                color: #93c5fd;
                font-size: 12px;
                font-style: italic;
                background: transparent;
            }
            QFrame#qrCard {
                background-color: #ffffff;
                border: 1.5px solid #e2e8f0;
                border-radius: 14px;
            }
            QLabel#qrImageLabel {
                background: transparent;
            }
            QLabel#hintLabel {
                color: #64748b;
                font-size: 12px;
                background: transparent;
            }
            QLabel#targetLabel {
                color: #1d4ed8;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#copyStatusLabel {
                color: #0f766e;
                font-size: 12px;
                font-weight: 600;
                background: #ecfeff;
                border: 1px solid #a5f3fc;
                border-radius: 9px;
                padding: 6px 10px;
            }
            QPushButton#primaryBtn {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 12px;
                min-width: 136px;
                min-height: 32px;
            }
            QPushButton#primaryBtn:hover {
                background-color: #1d4ed8;
            }
            QPushButton#primaryBtn:pressed {
                background-color: #1e40af;
            }
            QPushButton#secondaryBtn {
                background-color: #e2e8f0;
                color: #334155;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 12px;
                min-width: 108px;
                min-height: 32px;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #cbd5e1;
            }
            QPushButton#secondaryBtn:pressed {
                background-color: #b2c4d8;
            }
            QPushButton#closeBtn {
                background-color: transparent;
                color: #64748b;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 12px;
                min-width: 74px;
                min-height: 32px;
            }
            QPushButton#closeBtn:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- Hero card ---
        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout()
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(10)

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
        qr_layout.setContentsMargins(24, 24, 24, 20)
        qr_layout.setSpacing(12)
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

        hint = QLabel(translate(self.language, "support_scan_hint"))
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        qr_layout.addWidget(hint)

        target_label = QLabel(
            translate(self.language, "support_target", target=self._target)
        )
        target_label.setObjectName("targetLabel")
        target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        target_label.setWordWrap(True)
        qr_layout.addWidget(target_label)

        self.copy_status_label = QLabel("")
        self.copy_status_label.setObjectName("copyStatusLabel")
        self.copy_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.copy_status_label.setWordWrap(False)
        self.copy_status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.copy_status_label.setMinimumHeight(34)
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

        self.text_help = QTextEdit()
        self.text_help.setReadOnly(True)
        self.text_help.setPlainText(translate(self.language, "help_manual_body"))
        layout.addWidget(self.text_help)

        btn_close = QPushButton(translate(self.language, "btn_close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        self.setLayout(layout)



