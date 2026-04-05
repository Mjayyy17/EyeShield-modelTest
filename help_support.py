import json
import os

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea
from PySide6.QtCore import Qt

class HelpSupportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._active_language = "English"
        self.init_ui()

    def init_ui(self):

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 22, 28, 22)
        root_layout.setSpacing(16)
        self.setStyleSheet(
            "QWidget { background: #f5f7fa; color: #1f2937; }"
        )

        # --- Header ---
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        self._help_title_lbl = QLabel("Help & Support")
        self._help_title_lbl.setObjectName("pageHeader")
        self._help_title_lbl.setStyleSheet(
            "font-size: 27px; font-weight: 700; color: #0f172a; letter-spacing: 0.2px;"
        )
        header_layout.addWidget(self._help_title_lbl)

        self._help_subtitle_lbl = QLabel("Find answers, tutorials, and support resources.")
        self._help_subtitle_lbl.setObjectName("pageSubtitle")
        self._help_subtitle_lbl.setWordWrap(True)
        self._help_subtitle_lbl.setStyleSheet(
            "font-size: 13px; line-height: 1.5; color: #475569;"
        )
        header_layout.addWidget(self._help_subtitle_lbl)
        root_layout.addLayout(header_layout)

        # --- Scroll Area for Content ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 6px 0 6px 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 5px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            """
        )

        self._help_content_widget = QWidget()
        self._help_content_widget.setStyleSheet("background-color: transparent;")
        self._help_list_layout = QVBoxLayout(self._help_content_widget)
        self._help_list_layout.setSpacing(16)
        self._help_list_layout.setContentsMargins(0, 8, 0, 10)

        self._build_help_groups("English")

        scroll.setWidget(self._help_content_widget)
        root_layout.addWidget(scroll)

    def _build_help_groups(self, language: str):
        from translations import get_pack
        pack = get_pack(language)

        self._active_language = language

        contact_body = self._contact_body_from_config(pack)

        # Clear existing section cards before rebuilding.
        while self._help_list_layout.count():
            item = self._help_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        topics = [
            ("hlp_quick_start", "hlp_quick_start_body"),
            ("hlp_howto", "hlp_howto_body"),
            ("hlp_faq", "hlp_faq_body"),
            ("hlp_troubleshoot", "hlp_troubleshoot_body"),
            ("hlp_privacy", "hlp_privacy_body"),
            ("hlp_contact", None),
        ]

        for title_key, body_key in topics:
            body_html = contact_body if body_key is None else pack[body_key]
            card = self.build_card(pack[title_key], body_html)
            self._help_list_layout.addWidget(card)

        self._help_list_layout.addStretch(1)

    @staticmethod
    def _contact_body_from_config(pack: dict) -> str:
        default_email = "support@eyeshield.local"
        default_phone = "+1-000-000-0000"
        default_hours = "Mon-Fri, 8:00 AM - 6:00 PM"
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
        email = default_email
        phone = default_phone
        hours = default_hours

        try:
            with open(config_path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                support = loaded.get("support_contact")
                if isinstance(support, dict):
                    email = str(support.get("email") or default_email).strip()
                    phone = str(support.get("phone") or default_phone).strip()
                    hours = str(support.get("hours") or default_hours).strip()
        except (OSError, json.JSONDecodeError):
            pass

        return (
            "<p>"
            f"<b>IT/App Support:</b> {email}<br>"
            f"<b>Phone:</b> {phone}<br>"
            f"<b>Hours:</b> {hours}<br><br>"
            "<b>When contacting support, include:</b><br>"
            "User role, patient ID (if applicable), page name, exact error message, and time of incident."
            "</p>"
        )

    def reload_contact_from_config(self):
        main_window = self.window()
        language = getattr(main_window, "_current_language", "English") if main_window is not self else "English"
        self._build_help_groups(language)

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._active_language = language
        self._help_title_lbl.setText(pack["hlp_title"])
        self._help_subtitle_lbl.setText(pack["hlp_subtitle"])
        self._build_help_groups(language)

    @staticmethod
    def _normalize_help_html(body_html: str) -> str:
        raw = str(body_html or "").strip()
        return (
            "<div style='font-size:13px; line-height:1.72; color:#334155;'>"
            "<style>"
            "ul { margin: 0 0 2px 0; padding-left: 20px; }"
            "li { margin: 0 0 9px 0; }"
            "li p, ul p { margin: 0; padding: 0; }"
            "p { margin: 0 0 9px 0; }"
            "</style>"
            f"{raw}"
            "</div>"
        )

    @staticmethod
    def build_card(title, body_html):
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #d9e2ec;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(14)

        # --- Card Header ---
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: 700;
            color: #1e293b;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(title_label)
        card_layout.addLayout(header_layout)

        # --- Card Body ---
        body_label = QLabel(HelpSupportPage._normalize_help_html(body_html))
        body_label.setTextFormat(Qt.RichText)
        body_label.setWordWrap(True)
        body_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: #334155;
        """)
        card_layout.addWidget(body_label)

        return card
