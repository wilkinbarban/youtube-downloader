"""Settings and dependency-management dialogs."""

import os

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from app_core import Config, DEFAULT_QUALITY_OPTIONS, quality_label
from app_dependencies import DependencyManager
from app_i18n import translate
from app_logging import logger
from app_workers import DependencyInstallWorker


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


class DonationDialog(QDialog):
    """Professional donation dialog with PayPal QR code."""

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(translate(self.language, "donation_title"))
        self.setMinimumSize(380, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1f2937;
            }
            QPushButton#donationCloseButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QPushButton#donationCloseButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#donationCloseButton:pressed {
                background-color: #1e40af;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(24, 22, 24, 22)

        qr_label = QLabel()
        qr_label.setMinimumHeight(280)
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        from app_paths import QR_PAYPAL
        if QR_PAYPAL and os.path.exists(QR_PAYPAL):
            pixmap = QPixmap(QR_PAYPAL)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    260,
                    260,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                qr_label.setPixmap(scaled_pixmap)

        layout.addWidget(qr_label)

        btn_close = QPushButton(translate(self.language, "btn_close"))
        btn_close.setObjectName("donationCloseButton")
        btn_close.setFixedSize(96, 30)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)



