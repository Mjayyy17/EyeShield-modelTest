import json
import os
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QMessageBox,
    QFrame,
)

DARK_STYLESHEET = """
    /* ---- Base ---- */
    QWidget {
        background: #1e1e2e;
        color: #cdd6f4;
    }
    QMainWindow, QStackedWidget {
        background: #1e1e2e;
    }

    /* ---- Inputs ---- */
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 8px;
        padding: 8px;
        selection-background-color: #585b70;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {
        border: 1px solid #89b4fa;
    }
    QComboBox QAbstractItemView {
        background: #313244;
        color: #cdd6f4;
        selection-background-color: #45475a;
    }

    /* ---- Tables ---- */
    QTableWidget {
        background: #313244;
        alternate-background-color: #2a2a3c;
        color: #cdd6f4;
        gridline-color: #45475a;
        border: 1px solid #45475a;
        border-radius: 8px;
    }
    QHeaderView::section {
        background: #363649;
        color: #bac2de;
        padding: 8px;
        border: none;
    }
    QTableWidget::item {
        padding: 8px;
    }

    /* ---- Group boxes ---- */
    QGroupBox {
        background: #262637;
        border: 1px solid #45475a;
        border-radius: 8px;
        margin-top: 10px;
        color: #89b4fa;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: #89b4fa;
    }

    /* ---- Buttons ---- */
    QPushButton {
        background: #45475a;
        color: #cdd6f4;
        border: 1px solid #585b70;
        border-radius: 8px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: #585b70;
    }
    QPushButton:focus {
        border: 1px solid #89b4fa;
    }
    QPushButton:disabled {
        background: #313244;
        color: #6c7086;
        border: 1px solid #45475a;
    }
    QPushButton#primaryAction {
        background: #89b4fa;
        color: #1e1e2e;
        border: 1px solid #74c7ec;
    }
    QPushButton#primaryAction:hover {
        background: #74c7ec;
    }
    QPushButton#dangerAction {
        background: #262637;
        color: #f38ba8;
        border: 1px solid #f38ba8;
    }
    QPushButton#dangerAction:hover {
        background: #2e2030;
    }
    QPushButton#logoutBtn {
        background: #f38ba8;
        color: #1e1e2e;
        border: 1px solid #eba0ac;
        border-radius: 8px;
        padding: 8px 16px;
    }
    QPushButton#logoutBtn:hover {
        background: #eba0ac;
    }

    /* ---- Labels ---- */
    QLabel {
        background: transparent;
        color: #cdd6f4;
    }
    QLabel#tileTitle {
        color: #a6adc8;
        letter-spacing: 0.5px;
    }
    QLabel#statusLabel {
        color: #a6adc8;
    }
    QLabel#hintLabel {
        color: #6c7086;
    }
    QLabel#pageHeader {
        color: #89b4fa;
    }
    QLabel#pageSubtitle {
        color: #a6adc8;
    }
    QLabel#appTitle {
        color: #89b4fa;
        margin-right: 24px;
    }
    QLabel#userInfo {
        color: #a6adc8;
        margin-left: 16px;
        margin-right: 8px;
    }
    QLabel#welcomeTitle {
        color: #89b4fa;
    }
    QLabel#bigValue {
        color: #cdd6f4;
    }
    QLabel#quoteLabel {
        color: #a6adc8;
        font-style: italic;
    }
    QLabel#dashDate {
        color: #89b4fa;
    }
    QLabel#insightLabel {
        color: #a6adc8;
    }
    QLabel#activityLabel {
        color: #a6adc8;
    }
    QLabel#notesLabel {
        color: #a6adc8;
    }
    QLabel#statValue {
        color: #cdd6f4;
    }

    /* ---- Keep Settings text metrics identical to light mode ---- */
    QLabel#headerTitle {
        color: #89b4fa;
        font-size: 24px;
        font-weight: 700;
    }
    QLabel#fieldLabel {
        color: #bac2de;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    QLabel#statusLabel {
        color: #a6adc8;
        font-size: 12px;
    }
    QLabel#metaLabel {
        color: #a6adc8;
        font-size: 13px;
    }

    QGroupBox::title {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    /* ---- Checkboxes ---- */
    QCheckBox {
        color: #cdd6f4;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #6c7086;
        border-radius: 4px;
        background: #313244;
    }
    QCheckBox::indicator:checked {
        background: #89b4fa;
        border: 1px solid #74c7ec;
    }

    /* ---- Scroll areas ---- */
    QScrollArea {
        background: #1e1e2e;
        border: none;
    }
    QScrollBar:vertical {
        background: #313244;
        width: 10px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background: #585b70;
        border-radius: 5px;
    }

    /* ---- Calendar ---- */
    QCalendarWidget {
        background: #313244;
        color: #cdd6f4;
    }

    /* ---- Dashboard tiles ---- */
    QWidget#dashTile {
        background: #262637;
        border: 1px solid #45475a;
        border-radius: 8px;
    }
    QWidget#navBar {
        background: #181825;
        border-bottom: 1px solid #45475a;
    }

    /* ---- Video widget ---- */
    QVideoWidget {
        background: #000000;
    }

    /* ---- Dialogs / Message boxes ---- */
    QDialog {
        background: #1e1e2e;
    }
    QMessageBox {
        background: #1e1e2e;
    }
    QMessageBox QLabel {
        color: #cdd6f4;
    }
"""


class SettingsPage(QWidget):
    SETTINGS_FILE = "settings_data.json"

    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget {
                background: #ffffff;
                color: #1f2a37;
                font-size: 13px;
            }
            QLabel#headerTitle {
                color: #0b63ce;
                font-size: 24px;
                font-weight: 700;
                background: transparent;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d7dde5;
                border-radius: 10px;
                margin-top: 12px;
                font-weight: 700;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #0b63ce;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QLabel#fieldLabel {
                color: #2f4054;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #bfd0e0;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 20px;
            }
            QComboBox:hover {
                border: 1px solid #90b4db;
            }
            QComboBox:focus {
                border: 1px solid #0b63ce;
            }
            QPushButton {
                background: #edf2f7;
                color: #243447;
                border: 1px solid #ccd8e5;
                border-radius: 10px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e2eaf2;
            }
            QPushButton:focus {
                border: 1px solid #0b63ce;
            }
            QPushButton#primaryAction {
                background: #0b63ce;
                color: #ffffff;
                border: 1px solid #0a58ca;
            }
            QPushButton#primaryAction:hover {
                background: #0a58ca;
            }
            QLabel#statusLabel {
                color: #3f556e;
                font-size: 12px;
                padding: 2px 0;
                border: none;
                background: transparent;
            }
            QLabel#metaLabel {
                color: #51667d;
                font-size: 13px;
            }
        """)
        _outer = QVBoxLayout(self)
        _outer.setContentsMargins(18, 18, 18, 18)
        _outer.setSpacing(14)

        layout = _outer
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.title_label = QLabel("Settings")
        self.title_label.setObjectName("headerTitle")
        layout.addWidget(self.title_label)

        pref_group = QGroupBox("Preferences")
        self.pref_group = pref_group
        pref_layout = QVBoxLayout(pref_group)
        pref_layout.setSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_label = QLabel("Theme:")
        self.theme_label.setObjectName("fieldLabel")
        pref_layout.addWidget(self.theme_label)
        pref_layout.addWidget(self.theme_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "Filipino"])
        self.language_label = QLabel("Language:")
        self.language_label.setObjectName("fieldLabel")
        pref_layout.addWidget(self.language_label)
        pref_layout.addWidget(self.lang_combo)

        layout.addWidget(pref_group)

        # ── Action buttons (right after preferences) ──────────────────────
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self.reset_defaults)
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("primaryAction")
        self.save_btn.setAutoDefault(True)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save_settings)
        button_row.addWidget(self.reset_btn)
        button_row.addWidget(self.save_btn)
        layout.addLayout(button_row)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        # ── Divider ───────────────────────────────────────────────────────
        divider = QLabel()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background:#dee2e6; margin: 4px 0;")
        layout.addWidget(divider)

        # ── About ─────────────────────────────────────────────────────────
        about_group = QGroupBox("About")
        self.about_group = about_group
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(4)
        self.about_version_label = QLabel("EyeShield EMR v1.0.0")
        self.about_copyright_label = QLabel("© 2026 EyeShield Team")
        self.about_contact_label = QLabel("For support, contact: support@eyeshield.local")
        for lbl in (self.about_version_label, self.about_copyright_label, self.about_contact_label):
            lbl.setObjectName("metaLabel")
        about_layout.addWidget(self.about_version_label)
        about_layout.addWidget(self.about_copyright_label)
        about_layout.addWidget(self.about_contact_label)
        sections_row = QHBoxLayout()
        sections_row.setSpacing(10)
        sections_row.addWidget(about_group, 1)

        # ── Terms of Use ──────────────────────────────────────────────────
        terms_group = QGroupBox("Terms of Use")
        self.terms_group = terms_group
        terms_layout = QVBoxLayout(terms_group)
        self.terms_label = QLabel(
            "By using EyeShield EMR you agree to use the software solely for its "
            "intended medical-records purpose. Unauthorised reproduction, distribution, "
            "or reverse engineering is prohibited. The software is provided 'as is' "
            "without warranty of any kind. The EyeShield Team is not liable for any "
            "loss arising from the use or inability to use this software."
        )
        self.terms_label.setWordWrap(True)
        self.terms_label.setStyleSheet("color:#495057; font-size:12px; line-height:1.5;")
        terms_layout.addWidget(self.terms_label)
        sections_row.addWidget(terms_group, 1)

        # ── Privacy Policy ────────────────────────────────────────────────
        privacy_group = QGroupBox("Privacy Policy")
        self.privacy_group = privacy_group
        privacy_layout = QVBoxLayout(privacy_group)
        self.privacy_label = QLabel(
            "EyeShield EMR stores all patient and user data locally on this device. "
            "No personal information is transmitted to external servers. You are "
            "responsible for securing access to this device and its data. Regular "
            "backups are recommended. For data-deletion requests or privacy concerns, "
            "please contact your system administrator."
        )
        self.privacy_label.setWordWrap(True)
        self.privacy_label.setStyleSheet("color:#495057; font-size:12px; line-height:1.5;")
        privacy_layout.addWidget(self.privacy_label)
        sections_row.addWidget(privacy_group, 1)
        layout.addLayout(sections_row)

        self.load_settings()
        self.theme_combo.currentTextChanged.connect(self.apply_live_preview)
        self.lang_combo.currentTextChanged.connect(self.apply_live_preview)

        self.theme_combo.setFocus()
        self.setTabOrder(self.theme_combo, self.lang_combo)
        self.setTabOrder(self.lang_combo, self.reset_btn)
        self.setTabOrder(self.reset_btn, self.save_btn)

        layout.addStretch()

    def _language_pack(self, language: str) -> dict:
        from translations import get_pack
        p = get_pack(language)
        return {
            "title": p["settings_title"],
            "preferences": p["settings_preferences"],
            "theme": p["settings_theme"],
            "language": p["settings_language"],
            "about": p["settings_about"],
            "terms": p["settings_terms"],
            "privacy": p["settings_privacy"],
            "reset": p["settings_reset"],
            "save": p["settings_save"],
        }

    def apply_live_preview(self, _value=None):
        theme = self.theme_combo.currentText()

        # Delegate theme to the main window which clears local styles
        main_window = self.window()
        if main_window is not self and hasattr(main_window, 'apply_theme'):
            main_window.apply_theme(theme)
        else:
            # Fallback during init (settings page not yet parented)
            app = QApplication.instance()
            if app:
                app.setStyleSheet(DARK_STYLESHEET if theme == "Dark" else "")

        # Update language labels
        pack = self._language_pack(self.lang_combo.currentText())
        self.title_label.setText(pack["title"])
        self.pref_group.setTitle(pack["preferences"])
        self.theme_label.setText(pack["theme"])
        self.language_label.setText(pack["language"])
        self.about_group.setTitle(pack["about"])
        self.terms_group.setTitle(pack["terms"])
        self.privacy_group.setTitle(pack["privacy"])
        self.reset_btn.setText(pack["reset"])
        self.save_btn.setText(pack["save"])

        self.status_label.setText(f"Live preview: {theme} / {self.lang_combo.currentText()}")

        # Propagate language change to all other tabs
        lang = self.lang_combo.currentText()
        main_window = self.window()
        if main_window is not self and hasattr(main_window, 'apply_language'):
            main_window.apply_language(lang)

    def _settings_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), self.SETTINGS_FILE)

    def _default_settings(self) -> dict:
        return {
            "theme": "Light",
            "language": "English",
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
        self.apply_live_preview()
        self.status_label.setText("Settings loaded")

    def save_settings(self):
        settings = {
            "theme": self.theme_combo.currentText(),
            "language": self.lang_combo.currentText(),
        }
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as file:
                json.dump(settings, file, indent=2)
            timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.status_label.setText(f"Saved locally at {timestamp}")
        except OSError as err:
            self.status_label.setText("Save failed")
            QMessageBox.warning(self, "Settings", f"Failed to save settings: {err}")

    def reset_defaults(self):
        defaults = self._default_settings()
        self.theme_combo.setCurrentText(defaults["theme"])
        self.lang_combo.setCurrentText(defaults["language"])
        self.status_label.setText("Defaults restored (not yet saved)")
