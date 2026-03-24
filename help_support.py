from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QScrollArea
from PySide6.QtCore import Qt

class HelpSupportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(30, 20, 30, 20)
        root_layout.setSpacing(20)

        # --- Header ---
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        self._help_title_lbl = QLabel("Help & Support")
        self._help_title_lbl.setObjectName("pageHeader")
        self._help_title_lbl.setStyleSheet("font-weight: 600;")
        header_layout.addWidget(self._help_title_lbl)

        self._help_subtitle_lbl = QLabel("Find answers, tutorials, and support resources.")
        self._help_subtitle_lbl.setObjectName("pageSubtitle")
        self._help_subtitle_lbl.setStyleSheet("")
        header_layout.addWidget(self._help_subtitle_lbl)
        root_layout.addLayout(header_layout)

        # --- Scroll Area for Content ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        self._help_content_widget = QWidget()
        self._help_content_widget.setStyleSheet("background-color: transparent;")
        self._help_grid_layout = QGridLayout(self._help_content_widget)
        self._help_grid_layout.setSpacing(20)
        self._help_grid_layout.setContentsMargins(0, 10, 0, 10)

        self._build_help_groups("English")

        scroll.setWidget(self._help_content_widget)
        root_layout.addWidget(scroll)

    def _build_help_groups(self, language: str):
        from translations import get_pack
        pack = get_pack(language)

        # Clear existing items from grid
        while self._help_grid_layout.count():
            item = self._help_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        topics = [
            ("hlp_quick_start", "hlp_quick_start_body"),
            ("hlp_howto", "hlp_howto_body"),
            ("hlp_faq", "hlp_faq_body"),
            ("hlp_troubleshoot", "hlp_troubleshoot_body"),
            ("hlp_privacy", "hlp_privacy_body"),
            ("hlp_contact", "hlp_contact_body"),
        ]

        row, col = 0, 0
        for title_key, body_key in topics:
            card = self.build_card(pack[title_key], pack[body_key])
            self._help_grid_layout.addWidget(card, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._help_title_lbl.setText(pack["hlp_title"])
        self._help_subtitle_lbl.setText(pack["hlp_subtitle"])
        self._build_help_groups(language)

    @staticmethod
    def build_card(title, body_html):
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: rgba(128, 128, 128, 0.1);
                border-radius: 8px;
                border: 1px solid rgba(128, 128, 128, 0.2);
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)

        # --- Card Header ---
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("""
            font-weight: 600;
            color: #2196F3;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(title_label)
        card_layout.addLayout(header_layout)

        # --- Card Body ---
        body_label = QLabel(body_html)
        body_label.setTextFormat(Qt.RichText)
        body_label.setWordWrap(True)
        body_label.setStyleSheet("""
            background: transparent;
            border: none;
        """)
        card_layout.addWidget(body_label)
        card_layout.addStretch()

        return card
