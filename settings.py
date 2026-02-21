import json
import os

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QCheckBox,
    QComboBox,
    QMessageBox,
)

class SettingsPage(QWidget):
    SETTINGS_FILE = "settings_data.json"

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: #f8f9fa;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:20px;font-weight:bold;")
        subtitle = QLabel("Local offline preferences for this installation")
        subtitle.setStyleSheet("font-size:13px;color:#6c757d;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        pref_group = QGroupBox("Preferences")
        pref_layout = QVBoxLayout(pref_group)
        pref_layout.setSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        pref_layout.addWidget(QLabel("Theme:"))
        pref_layout.addWidget(self.theme_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "Spanish", "French", "Other"])
        pref_layout.addWidget(QLabel("Language:"))
        pref_layout.addWidget(self.lang_combo)

        self.auto_logout = QCheckBox("Enable auto-logout after inactivity")
        self.confirm_deletions = QCheckBox("Ask confirmation before destructive actions")
        self.compact_tables = QCheckBox("Use compact table rows")
        pref_layout.addWidget(self.auto_logout)
        pref_layout.addWidget(self.confirm_deletions)
        pref_layout.addWidget(self.compact_tables)

        layout.addWidget(pref_group)

        # About/Info
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout(about_group)
        about_layout.addWidget(QLabel("EyeShield EMR v1.0.0"))
        about_layout.addWidget(QLabel("© 2026 EyeShield Team"))
        about_layout.addWidget(QLabel("For support, contact: support@eyeshield.local"))
        layout.addWidget(about_group)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self.reset_defaults)
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        button_row.addWidget(self.reset_btn)
        button_row.addWidget(self.save_btn)
        layout.addLayout(button_row)

        self.load_settings()

        layout.addStretch()

    def _settings_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), self.SETTINGS_FILE)

    def _default_settings(self) -> dict:
        return {
            "theme": "Light",
            "language": "English",
            "auto_logout": True,
            "confirm_deletions": True,
            "compact_tables": False,
        }

    def load_settings(self):
        settings = self._default_settings()
        path = self._settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    settings.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

        self.theme_combo.setCurrentText(settings.get("theme", "Light"))
        self.lang_combo.setCurrentText(settings.get("language", "English"))
        self.auto_logout.setChecked(bool(settings.get("auto_logout", True)))
        self.confirm_deletions.setChecked(bool(settings.get("confirm_deletions", True)))
        self.compact_tables.setChecked(bool(settings.get("compact_tables", False)))

    def save_settings(self):
        settings = {
            "theme": self.theme_combo.currentText(),
            "language": self.lang_combo.currentText(),
            "auto_logout": self.auto_logout.isChecked(),
            "confirm_deletions": self.confirm_deletions.isChecked(),
            "compact_tables": self.compact_tables.isChecked(),
        }
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as file:
                json.dump(settings, file, indent=2)
            QMessageBox.information(self, "Settings", "Settings saved locally.")
        except OSError as err:
            QMessageBox.warning(self, "Settings", f"Failed to save settings: {err}")

    def reset_defaults(self):
        defaults = self._default_settings()
        self.theme_combo.setCurrentText(defaults["theme"])
        self.lang_combo.setCurrentText(defaults["language"])
        self.auto_logout.setChecked(defaults["auto_logout"])
        self.confirm_deletions.setChecked(defaults["confirm_deletions"])
        self.compact_tables.setChecked(defaults["compact_tables"])
