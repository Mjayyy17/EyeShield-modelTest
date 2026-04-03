import json
import os
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QMessageBox,
    QFrame,
    QScrollArea,
    QDialog,
    QTimeEdit,
    QSpinBox,
    QAbstractSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QTime, Qt

import user_store
from auth import UserManager
from user_auth import get_user_profile

_WEEKDAY_OPTIONS = [
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
    ("sat", "Saturday"),
    ("sun", "Sunday"),
]

DARK_STYLESHEET = """
    /* ---- Base ---- */
    QWidget {
        background: #20242b;
        color: #d6dbe4;
    }
    QMainWindow, QStackedWidget {
        background: #20242b;
    }

    /* ---- Inputs ---- */
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: #2a3038;
        color: #d6dbe4;
        border: 1px solid #3e4652;
        border-radius: 8px;
        padding: 8px;
        selection-background-color: #4b5563;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {
        border: 1px solid #7ea6d9;
    }
    QComboBox QAbstractItemView {
        background: #2a3038;
        color: #d6dbe4;
        selection-background-color: #3e4652;
    }

    /* ---- Tables ---- */
    QTableWidget {
        background: #2a3038;
        alternate-background-color: #252b33;
        color: #d6dbe4;
        gridline-color: #3e4652;
        border: 1px solid #3e4652;
        border-radius: 8px;
    }
    QHeaderView::section {
        background: #303744;
        color: #c7cfdb;
        padding: 8px;
        border: none;
    }
    QTableWidget::item {
        padding: 8px;
    }

    /* ---- Group boxes ---- */
    QGroupBox {
        background: #242a33;
        border: 1px solid #3e4652;
        border-radius: 8px;
        margin-top: 10px;
        color: #7ea6d9;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: #7ea6d9;
    }

    /* ---- Buttons ---- */
    QPushButton {
        background: #3e4652;
        color: #d6dbe4;
        border: 1px solid #4b5563;
        border-radius: 8px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: #4b5563;
    }
    QPushButton:focus {
        border: 1px solid #7ea6d9;
    }
    QPushButton:disabled {
        background: #2a3038;
        color: #7a8594;
        border: 1px solid #3e4652;
    }
    QPushButton#primaryAction {
        background: #5f8fc4;
        color: #f4f7fb;
        border: 1px solid #6ea0d8;
    }
    QPushButton#primaryAction:hover {
        background: #6a9bd3;
    }
    QPushButton#dangerAction {
        background: #2b2a31;
        color: #e4a1b1;
        border: 1px solid #d18a9a;
    }
    QPushButton#dangerAction:hover {
        background: #35303a;
    }
    QPushButton#logoutBtn {
        background: #cf7288;
        color: #f7f9fc;
        border: 1px solid #bf667c;
        border-radius: 8px;
        padding: 8px 16px;
    }
    QPushButton#logoutBtn:hover {
        background: #d47f94;
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
        color: #7ea6d9;
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
        color: #7ea6d9;
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
        color: #7ea6d9;
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
        border: 1px solid #758192;
        border-radius: 4px;
        background: #2a3038;
    }
    QCheckBox::indicator:checked {
        background: #7ea6d9;
        border: 1px solid #6ea0d8;
    }

    /* ---- Scroll areas ---- */
    QScrollArea {
        background: #20242b;
        border: none;
    }
    QScrollBar:vertical {
        background: #2a3038;
        width: 10px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background: #4b5563;
        border-radius: 5px;
    }

    /* ---- Calendar ---- */
    QCalendarWidget {
        background: #2a3038;
        color: #d6dbe4;
    }

    /* ---- Dashboard tiles ---- */
    QWidget#dashTile {
        background: #242a33;
        border: 1px solid #3e4652;
        border-radius: 8px;
    }
    QWidget#navBar {
        background: #1c2128;
        border-bottom: 1px solid #3e4652;
    }

    /* ---- Video widget ---- */
    QVideoWidget {
        background: #000000;
    }

    /* ---- Dialogs / Message boxes ---- */
    QDialog {
        background: #20242b;
    }
    QMessageBox {
        background: #20242b;
    }
    QMessageBox QLabel {
        color: #d6dbe4;
    }
"""


def _add_eye_toggle(field: QLineEdit):
    """Attach a show/hide password toggle icon to a QLineEdit."""
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    show_icon = QIcon(os.path.join(icon_dir, "eye_open.svg"))
    hide_icon = QIcon(os.path.join(icon_dir, "eye_closed.svg"))

    action = QAction(show_icon, "", field)
    action.setCheckable(True)
    action.setToolTip("Show / hide password")

    def _toggle(visible: bool):
        action.setIcon(hide_icon if visible else show_icon)
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    action.toggled.connect(_toggle)
    field.addAction(action, QLineEdit.TrailingPosition)


class SettingsPage(QWidget):
    SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "settings_data.json")
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")

    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget {
                background: #ffffff;
                color: #1f2a37;
                font-size: 13px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QWidget#settingsCanvas {
                background: #ffffff;
            }
            QFrame#settingsHero {
                background: #ffffff;
                border: 1px solid #dbe7f5;
                border-radius: 12px;
            }
            QLabel#headerTitle {
                color: #1e40af;
                font-size: 24px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#headerSubtitle {
                color: #64748b;
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #dbe7f5;
                border-radius: 12px;
                margin-top: 8px;
                font-weight: 700;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                background: #ffffff;
                color: #1e3a8a;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QLabel#fieldLabel {
                color: #324a67;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QComboBox, QSpinBox, QTimeEdit {
                background: #ffffff;
                border: 1px solid #c7d8ec;
                border-radius: 9px;
                padding: 6px 8px;
                min-height: 20px;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #c7d8ec;
                border-radius: 9px;
                padding: 8px 10px;
                min-height: 22px;
            }
            QLineEdit:hover {
                border: 1px solid #93c5fd;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox:hover, QSpinBox:hover, QTimeEdit:hover {
                border: 1px solid #93c5fd;
            }
            QComboBox:focus, QSpinBox:focus, QTimeEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                color: #0f172a;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
                font-family: 'Segoe UI';
                font-weight: 600;
            }
            QPushButton:hover {
                background: #eff6ff;
                border: 1px solid #93c5fd;
            }
            QPushButton:focus {
                border: 1px solid #1f6fe5;
            }
            QPushButton:disabled {
                background: #f8fafc;
                border: 1px solid #dbeafe;
                color: #9ca3af;
            }
            QPushButton#primaryAction {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                color: #0f172a;
            }
            QPushButton#primaryAction:hover {
                background: #eff6ff;
                border: 1px solid #93c5fd;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #dbe7f5;
                border-radius: 10px;
                gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background: #ffffff;
                color: #1e3a8a;
                border: none;
                border-bottom: 1px solid #dbe7f5;
                font-size: 11px;
                font-weight: 700;
                padding: 8px;
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
            QCheckBox {
                spacing: 8px;
                color: #23354c;
                background: transparent;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #9fb6d1;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border: 1px solid #2563eb;
            }
        """)
        _outer = QVBoxLayout(self)
        _outer.setContentsMargins(0, 0, 0, 0)
        _outer.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("settingsCanvas")
        self.scroll_area.setWidget(content)
        _outer.addWidget(self.scroll_area)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hero_card = QFrame()
        hero_card.setObjectName("settingsHero")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(12, 10, 12, 10)
        hero_layout.setSpacing(2)

        self.title_label = QLabel("Settings")
        self.title_label.setObjectName("headerTitle")
        hero_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Configuration hub for preferences, security, and support")
        self.subtitle_label.setObjectName("headerSubtitle")
        hero_layout.addWidget(self.subtitle_label)
        layout.addWidget(hero_card)

        pref_group = QGroupBox("Preferences")
        self.pref_group = pref_group
        pref_layout = QGridLayout(pref_group)
        pref_layout.setHorizontalSpacing(8)
        pref_layout.setVerticalSpacing(6)
        pref_layout.setColumnStretch(0, 1)
        pref_layout.setColumnStretch(1, 1)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_label = QLabel("Theme:")
        self.theme_label.setObjectName("fieldLabel")
        pref_layout.addWidget(self.theme_label, 0, 0)
        pref_layout.addWidget(self.theme_combo, 1, 0)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English"])
        self.language_label = QLabel("Language:")
        self.language_label.setObjectName("fieldLabel")
        pref_layout.addWidget(self.language_label, 0, 1)
        pref_layout.addWidget(self.lang_combo, 1, 1)

        self.session_group = QGroupBox("Session Settings")
        session_layout = QVBoxLayout(self.session_group)
        session_layout.setSpacing(8)

        self.auto_logout_check = QCheckBox("Enable auto-logout after inactivity")
        session_layout.addWidget(self.auto_logout_check)

        timeout_grid = QGridLayout()
        timeout_grid.setHorizontalSpacing(8)
        timeout_grid.setVerticalSpacing(6)

        self.timeout_label = QLabel("Inactivity timeout (minutes):")
        self.timeout_label.setObjectName("fieldLabel")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 240)
        self.timeout_spin.setValue(15)
        self.timeout_spin.setSuffix(" min")
        self.timeout_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.timeout_spin.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.timeout_spin.setMinimumHeight(34)
        timeout_grid.addWidget(self.timeout_label, 0, 0)
        timeout_grid.addWidget(self.timeout_spin, 1, 0)

        self.warning_label = QLabel("Inactivity warning countdown (seconds):")
        self.warning_label.setObjectName("fieldLabel")
        self.warning_spin = QSpinBox()
        self.warning_spin.setRange(10, 300)
        self.warning_spin.setValue(30)
        self.warning_spin.setSuffix(" sec")
        self.warning_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.warning_spin.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.warning_spin.setMinimumHeight(34)
        timeout_grid.addWidget(self.warning_label, 0, 1)
        timeout_grid.addWidget(self.warning_spin, 1, 1)
        session_layout.addLayout(timeout_grid)

        self.timeout_help_label = QLabel("")
        self.timeout_help_label.setObjectName("metaLabel")
        self.timeout_help_label.setWordWrap(True)
        session_layout.addWidget(self.timeout_help_label)

        self.support_group = QGroupBox("Support")
        support_layout = QGridLayout(self.support_group)
        support_layout.setHorizontalSpacing(8)
        support_layout.setVerticalSpacing(6)
        support_layout.setColumnStretch(0, 1)
        support_layout.setColumnStretch(1, 1)

        self.support_email_label = QLabel("Help Support Email:")
        self.support_email_label.setObjectName("fieldLabel")
        self.support_email_input = QLineEdit()
        self.support_email_input.setPlaceholderText("support@eyeshield.local")

        self.support_phone_label = QLabel("Help Support Phone:")
        self.support_phone_label.setObjectName("fieldLabel")
        self.support_phone_input = QLineEdit()
        self.support_phone_input.setPlaceholderText("+1-000-000-0000")

        self.support_hours_label = QLabel("Help Support Hours:")
        self.support_hours_label.setObjectName("fieldLabel")
        self.support_hours_input = QLineEdit()
        self.support_hours_input.setPlaceholderText("Mon-Fri, 8:00 AM - 6:00 PM")

        support_layout.addWidget(self.support_email_label, 0, 0)
        support_layout.addWidget(self.support_phone_label, 0, 1)
        support_layout.addWidget(self.support_hours_label, 2, 0, 1, 2)
        support_layout.addWidget(self.support_email_input, 1, 0)
        support_layout.addWidget(self.support_phone_input, 1, 1)
        support_layout.addWidget(self.support_hours_input, 3, 0, 1, 2)

        self.admin_contact_group = QGroupBox("Admin Details")
        admin_contact_layout = QGridLayout(self.admin_contact_group)
        admin_contact_layout.setHorizontalSpacing(8)
        admin_contact_layout.setVerticalSpacing(6)
        admin_contact_layout.setColumnStretch(0, 1)
        admin_contact_layout.setColumnStretch(1, 1)

        self.admin_contact_name_label = QLabel("Admin Name:")
        self.admin_contact_name_label.setObjectName("fieldLabel")
        self.admin_contact_name_input = QLineEdit()
        self.admin_contact_name_input.setPlaceholderText("Name shown in Contact Admin")
        admin_contact_layout.addWidget(self.admin_contact_name_label, 0, 0)
        admin_contact_layout.addWidget(self.admin_contact_name_input, 1, 0)

        self.admin_contact_email_label = QLabel("Admin Email:")
        self.admin_contact_email_label.setObjectName("fieldLabel")
        self.admin_contact_email_input = QLineEdit()
        self.admin_contact_email_input.setPlaceholderText("admin@example.com")
        admin_contact_layout.addWidget(self.admin_contact_email_label, 0, 1)
        admin_contact_layout.addWidget(self.admin_contact_email_input, 1, 1)

        self.admin_contact_phone_label = QLabel("Admin Phone:")
        self.admin_contact_phone_label.setObjectName("fieldLabel")
        self.admin_contact_phone_input = QLineEdit()
        self.admin_contact_phone_input.setPlaceholderText("+63 900 000 0000")
        admin_contact_layout.addWidget(self.admin_contact_phone_label, 2, 0)
        admin_contact_layout.addWidget(self.admin_contact_phone_input, 3, 0)

        self.admin_contact_location_label = QLabel("Admin Location:")
        self.admin_contact_location_label.setObjectName("fieldLabel")
        self.admin_contact_location_input = QLineEdit()
        self.admin_contact_location_input.setPlaceholderText("Office / Department")
        admin_contact_layout.addWidget(self.admin_contact_location_label, 2, 1)
        admin_contact_layout.addWidget(self.admin_contact_location_input, 3, 1)

        self.referral_hospitals_group = QGroupBox("Trusted referred hospitals")
        referral_layout = QVBoxLayout(self.referral_hospitals_group)
        referral_layout.setSpacing(6)

        self.referral_hospitals_hint = QLabel("Maintain an approved destination list for referral letters and reports.")
        self.referral_hospitals_hint.setObjectName("metaLabel")
        self.referral_hospitals_hint.setWordWrap(True)
        referral_layout.addWidget(self.referral_hospitals_hint)

        self.referral_hospitals_table = QTableWidget(0, 4)
        self.referral_hospitals_table.setHorizontalHeaderLabels(["Hospital", "Department", "Contact", "Status"])
        self.referral_hospitals_table.setAlternatingRowColors(True)
        self.referral_hospitals_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.referral_hospitals_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.referral_hospitals_table.setSelectionMode(QTableWidget.SingleSelection)
        self.referral_hospitals_table.verticalHeader().setVisible(False)
        self.referral_hospitals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.referral_hospitals_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.referral_hospitals_table.itemSelectionChanged.connect(self._on_referral_hospital_selected)
        self.referral_hospitals_table.setMinimumHeight(180)
        self.referral_hospitals_table.setStyleSheet(
            "QTableWidget::item { padding: 6px; border: none; background-color: #ffffff; }"
            "QTableWidget::item:alternate { background-color: #f8fbff; }"
            "QTableWidget::item:selected { background-color: #e7f0ff; color: #1f2937; }"
        )
        referral_layout.addWidget(self.referral_hospitals_table)

        hospital_form_grid = QGridLayout()
        hospital_form_grid.setHorizontalSpacing(8)
        hospital_form_grid.setVerticalSpacing(6)
        hospital_form_grid.setColumnStretch(0, 1)
        hospital_form_grid.setColumnStretch(1, 1)

        self.hospital_name_label = QLabel("Hospital Name:")
        self.hospital_name_label.setObjectName("fieldLabel")
        self.hospital_name_input = QLineEdit()
        self.hospital_name_input.setPlaceholderText("e.g., St. Mary's Medical Center")
        hospital_form_grid.addWidget(self.hospital_name_label, 0, 0)
        hospital_form_grid.addWidget(self.hospital_name_input, 1, 0)

        self.hospital_department_label = QLabel("Department:")
        self.hospital_department_label.setObjectName("fieldLabel")
        self.hospital_department_input = QLineEdit()
        self.hospital_department_input.setPlaceholderText("e.g., Ophthalmology Department")
        hospital_form_grid.addWidget(self.hospital_department_label, 0, 1)
        hospital_form_grid.addWidget(self.hospital_department_input, 1, 1)

        self.hospital_contact_label = QLabel("Contact Person:")
        self.hospital_contact_label.setObjectName("fieldLabel")
        self.hospital_contact_input = QLineEdit()
        self.hospital_contact_input.setPlaceholderText("Name of referral contact")
        hospital_form_grid.addWidget(self.hospital_contact_label, 2, 0)
        hospital_form_grid.addWidget(self.hospital_contact_input, 3, 0)

        self.hospital_phone_label = QLabel("Phone:")
        self.hospital_phone_label.setObjectName("fieldLabel")
        self.hospital_phone_input = QLineEdit()
        self.hospital_phone_input.setPlaceholderText("+63 900 000 0000")
        hospital_form_grid.addWidget(self.hospital_phone_label, 2, 1)
        hospital_form_grid.addWidget(self.hospital_phone_input, 3, 1)

        self.hospital_email_label = QLabel("Email:")
        self.hospital_email_label.setObjectName("fieldLabel")
        self.hospital_email_input = QLineEdit()
        self.hospital_email_input.setPlaceholderText("referrals@hospital.org")
        hospital_form_grid.addWidget(self.hospital_email_label, 4, 0)
        hospital_form_grid.addWidget(self.hospital_email_input, 5, 0)

        self.hospital_address_label = QLabel("Address:")
        self.hospital_address_label.setObjectName("fieldLabel")
        self.hospital_address_input = QLineEdit()
        self.hospital_address_input.setPlaceholderText("City / complete address")
        hospital_form_grid.addWidget(self.hospital_address_label, 4, 1)
        hospital_form_grid.addWidget(self.hospital_address_input, 5, 1)
        referral_layout.addLayout(hospital_form_grid)

        compact_controls = [
            self.theme_combo,
            self.lang_combo,
            self.timeout_spin,
            self.warning_spin,
            self.support_email_input,
            self.support_phone_input,
            self.support_hours_input,
            self.admin_contact_name_input,
            self.admin_contact_email_input,
            self.admin_contact_phone_input,
            self.admin_contact_location_input,
            self.hospital_name_input,
            self.hospital_department_input,
            self.hospital_contact_input,
            self.hospital_phone_input,
            self.hospital_email_input,
            self.hospital_address_input,
        ]
        for control in compact_controls:
            control.setMaximumWidth(440)

        flags_row = QHBoxLayout()
        self.hospital_active_check = QCheckBox("Active")
        self.hospital_active_check.setChecked(True)
        self.hospital_default_check = QCheckBox("Set as default")
        flags_row.addWidget(self.hospital_active_check)
        flags_row.addWidget(self.hospital_default_check)
        flags_row.addStretch(1)
        referral_layout.addLayout(flags_row)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        self.hospital_clear_btn = QPushButton("Clear")
        self.hospital_clear_btn.clicked.connect(self._clear_referral_hospital_form)
        self.hospital_save_btn = QPushButton("Save Hospital")
        self.hospital_save_btn.setObjectName("primaryAction")
        self.hospital_save_btn.clicked.connect(self._save_referral_hospital)
        self.hospital_delete_btn = QPushButton("Delete")
        self.hospital_delete_btn.clicked.connect(self._delete_referral_hospital)
        actions_row.addWidget(self.hospital_clear_btn)
        actions_row.addWidget(self.hospital_save_btn)
        actions_row.addWidget(self.hospital_delete_btn)
        referral_layout.addLayout(actions_row)

        self._referral_hospital_rows = []
        self._referral_hospital_lookup = {}
        self._selected_referral_hospital_id = None
        self._policy_default_timeout_minutes = 15
        self._policy_auto_logout_enabled = True
        self._policy_warning_seconds = 30

        self.account_group = QGroupBox("My Account")
        account_layout = QVBoxLayout(self.account_group)
        account_layout.setSpacing(8)

        account_form_grid = QGridLayout()
        account_form_grid.setHorizontalSpacing(8)
        account_form_grid.setVerticalSpacing(6)
        account_form_grid.setColumnStretch(0, 1)
        account_form_grid.setColumnStretch(1, 1)

        self.display_name_label = QLabel("Display Name:")
        self.display_name_label.setObjectName("fieldLabel")
        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Display name")
        account_form_grid.addWidget(self.display_name_label, 0, 0)
        account_form_grid.addWidget(self.display_name_input, 1, 0)

        self.dr_prefix_check = QCheckBox("Add Dr.")
        account_form_grid.addWidget(self.dr_prefix_check, 2, 0)

        self.username_label = QLabel("Username:")
        self.username_label.setObjectName("fieldLabel")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        account_form_grid.addWidget(self.username_label, 0, 1)
        account_form_grid.addWidget(self.username_input, 1, 1)

        self.new_password_label = QLabel("New Password (optional):")
        self.new_password_label.setObjectName("fieldLabel")
        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("Leave blank to keep current password")
        self.new_password_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.new_password_input)
        account_form_grid.addWidget(self.new_password_label, 3, 0, 1, 2)
        account_form_grid.addWidget(self.new_password_input, 4, 0, 1, 2)
        account_layout.addLayout(account_form_grid)

        account_btn_row = QHBoxLayout()
        account_btn_row.addStretch(1)
        self.account_save_btn = QPushButton("Update Account")
        self.account_save_btn.setObjectName("primaryAction")
        self.account_save_btn.clicked.connect(self.update_account)
        account_btn_row.addWidget(self.account_save_btn)
        account_layout.addLayout(account_btn_row)

        self.schedule_group = QGroupBox("My Schedule")
        schedule_layout = QVBoxLayout(self.schedule_group)
        schedule_layout.setSpacing(6)

        self.schedule_hint_label = QLabel("Set your weekly clinic availability shown on your dashboard.")
        self.schedule_hint_label.setObjectName("metaLabel")
        self.schedule_hint_label.setWordWrap(True)
        schedule_layout.addWidget(self.schedule_hint_label)

        schedule_time_row = QHBoxLayout()
        schedule_time_row.setSpacing(6)
        self.schedule_start_label = QLabel("From:")
        self.schedule_start_label.setObjectName("fieldLabel")
        self.schedule_start_time = QTimeEdit()
        self.schedule_start_time.setDisplayFormat("hh:mm AP")
        self.schedule_start_time.setTime(QTime(9, 0))
        self.schedule_end_label = QLabel("To:")
        self.schedule_end_label.setObjectName("fieldLabel")
        self.schedule_end_time = QTimeEdit()
        self.schedule_end_time.setDisplayFormat("hh:mm AP")
        self.schedule_end_time.setTime(QTime(17, 0))
        for control in (
            self.display_name_input,
            self.username_input,
            self.new_password_input,
            self.schedule_start_time,
            self.schedule_end_time,
        ):
            control.setMaximumWidth(460)
        schedule_time_row.addWidget(self.schedule_start_label)
        schedule_time_row.addWidget(self.schedule_start_time)
        schedule_time_row.addSpacing(12)
        schedule_time_row.addWidget(self.schedule_end_label)
        schedule_time_row.addWidget(self.schedule_end_time)
        schedule_time_row.addStretch(1)
        schedule_layout.addLayout(schedule_time_row)

        self.schedule_days_label = QLabel("Available Days:")
        self.schedule_days_label.setObjectName("fieldLabel")
        schedule_layout.addWidget(self.schedule_days_label)

        days_grid = QGridLayout()
        days_grid.setHorizontalSpacing(8)
        days_grid.setVerticalSpacing(4)
        self.schedule_day_checks = []
        for idx, (day_key, day_label) in enumerate(_WEEKDAY_OPTIONS):
            checkbox = QCheckBox(day_label)
            checkbox.setChecked(idx < 5)
            self.schedule_day_checks.append((day_key, checkbox))
            row = idx // 4
            col = idx % 4
            days_grid.addWidget(checkbox, row, col)
        schedule_layout.addLayout(days_grid)

        for card in (
            pref_group,
            self.session_group,
            self.support_group,
            self.admin_contact_group,
            self.account_group,
            self.schedule_group,
        ):
            card.setMaximumWidth(640)
        for wide_card in (self.referral_hospitals_group,):
            wide_card.setMaximumWidth(1020)

        schedule_btn_row = QHBoxLayout()
        schedule_btn_row.addStretch(1)
        self.schedule_save_btn = QPushButton("Update Schedule")
        self.schedule_save_btn.setObjectName("primaryAction")
        self.schedule_save_btn.clicked.connect(self.update_schedule)
        schedule_btn_row.addWidget(self.schedule_save_btn)
        schedule_layout.addLayout(schedule_btn_row)

        top_bento_grid = QGridLayout()
        top_bento_grid.setHorizontalSpacing(10)
        top_bento_grid.setVerticalSpacing(10)
        top_bento_grid.addWidget(pref_group, 0, 0)
        top_bento_grid.addWidget(self.session_group, 0, 1)
        top_bento_grid.addWidget(self.support_group, 1, 0)
        top_bento_grid.addWidget(self.admin_contact_group, 1, 1)
        top_bento_grid.addWidget(self.account_group, 2, 0)
        top_bento_grid.addWidget(self.schedule_group, 2, 1)
        top_bento_grid.setColumnStretch(0, 1)
        top_bento_grid.setColumnStretch(1, 1)
        layout.addLayout(top_bento_grid)

        # Global settings actions.
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
        self.about_contact_label = QLabel(
            "EyeShield EMR is an offline clinical screening system for diabetic retinopathy. "
            "It supports patient intake, AI-assisted image analysis, report generation, and "
            "internal referral coordination. AI output is decision support only and must be "
            "reviewed by a qualified clinician before final diagnosis and treatment planning."
        )
        self.about_contact_label.setWordWrap(True)
        for lbl in (self.about_version_label, self.about_copyright_label, self.about_contact_label):
            lbl.setObjectName("metaLabel")
        about_layout.addWidget(self.about_version_label)
        about_layout.addWidget(self.about_copyright_label)
        about_layout.addWidget(self.about_contact_label)
        sections_row = QGridLayout()
        sections_row.setHorizontalSpacing(14)
        sections_row.setVerticalSpacing(14)
        sections_row.addWidget(about_group, 0, 0)

        # ── Terms of Use ──────────────────────────────────────────────────
        terms_group = QGroupBox("Terms of Use")
        self.terms_group = terms_group
        terms_layout = QVBoxLayout(terms_group)
        self.terms_label = QLabel(
            "By using EyeShield EMR, you agree to use the system only for authorized clinical "
            "screening, documentation, and referral workflows. Users must follow role-based "
            "permissions, maintain accurate records, and avoid unauthorized copying, sharing, "
            "or modification of patient data. Internal referral notes and status updates must "
            "be used for continuity of care. The software is provided as a clinical support "
            "tool and does not replace professional medical judgment."
        )
        self.terms_label.setWordWrap(True)
        self.terms_label.setStyleSheet("color:#495057; font-size:12px; line-height:1.5;")
        terms_layout.addWidget(self.terms_label)
        sections_row.addWidget(terms_group, 0, 1)

        # ── Privacy Policy ────────────────────────────────────────────────
        privacy_group = QGroupBox("Privacy Policy")
        self.privacy_group = privacy_group
        privacy_layout = QVBoxLayout(privacy_group)
        self.privacy_label = QLabel(
            "EyeShield EMR stores patient and user data locally on this device/database and "
            "does not require internet transfer for core operation. Access must be restricted "
            "to authorized users, with workstation lock/logout on shared devices. Exports and "
            "printed reports should be handled only through approved clinical channels and "
            "according to retention policy. Administrators are responsible for backup, access "
            "control, and secure lifecycle management of local records."
        )
        self.privacy_label.setWordWrap(True)
        self.privacy_label.setStyleSheet("color:#495057; font-size:12px; line-height:1.5;")
        privacy_layout.addWidget(self.privacy_label)
        sections_row.addWidget(privacy_group, 1, 0, 1, 2)
        sections_row.setColumnStretch(0, 1)
        sections_row.setColumnStretch(1, 1)
        layout.addLayout(sections_row)

        self.load_settings()
        self.theme_combo.currentTextChanged.connect(self.apply_live_preview)
        self.lang_combo.currentTextChanged.connect(self.apply_live_preview)
        self.auto_logout_check.toggled.connect(self._sync_timeout_enabled_state)
        self._configure_account_section()
        self._configure_schedule_section()
        self._configure_session_support_section()
        self._configure_admin_contact_section()
        self._sync_timeout_enabled_state()

        self.theme_combo.setFocus()
        self.setTabOrder(self.theme_combo, self.lang_combo)
        self.setTabOrder(self.lang_combo, self.reset_btn)
        self.setTabOrder(self.reset_btn, self.save_btn)

        layout.addStretch()

    def _active_role(self) -> str:
        main_window = self.window()
        role = getattr(main_window, "role", None) if main_window is not self else None
        return str(role or os.environ.get("EYESHIELD_CURRENT_ROLE") or "").strip().lower()

    def _active_username(self) -> str:
        main_window = self.window()
        username = getattr(main_window, "username", None) if main_window is not self else None
        return str(username or os.environ.get("EYESHIELD_CURRENT_USER") or "").strip()

    def _configure_account_section(self):
        role = self._active_role()
        show_account = role == "clinician"
        self.account_group.setVisible(show_account)
        if not show_account:
            return

        username = self._active_username()
        profile = get_user_profile(username) or {}
        display_name = str(profile.get("display_name") or username)
        self.display_name_input.setText(display_name)
        self.dr_prefix_check.setChecked(display_name.strip().lower().startswith("dr. "))
        self.username_input.setText(str(profile.get("username") or username))
        self.new_password_input.clear()

    def _configure_schedule_section(self):
        show_schedule = self._active_role() == "clinician"
        self.schedule_group.setVisible(show_schedule)
        if not show_schedule:
            return
        self._load_schedule_fields()

    def _configure_admin_contact_section(self):
        show_admin_contact = self._active_role() == "admin"
        self.admin_contact_group.setVisible(show_admin_contact)
        if not show_admin_contact:
            return
        self._load_admin_contact_into_fields()

    def _configure_session_support_section(self):
        role = self._active_role()
        show_session_support = role in {"admin", "clinician", "viewer"}
        is_admin = role == "admin"
        self.session_group.setVisible(show_session_support)
        self.support_group.setVisible(is_admin)
        if not show_session_support:
            return

        self.support_email_label.setVisible(is_admin)
        self.support_email_input.setVisible(is_admin)
        self.support_phone_label.setVisible(is_admin)
        self.support_phone_input.setVisible(is_admin)
        self.support_hours_label.setVisible(is_admin)
        self.support_hours_input.setVisible(is_admin)
        self.auto_logout_check.setVisible(is_admin)

        if is_admin:
            self.timeout_label.setText("Default inactivity timeout (minutes):")
            self.timeout_help_label.setText(
                "Default applies to all accounts. Users can set a personal timeout equal to or lower than this value."
            )
            self.auto_logout_check.setEnabled(True)
            self.warning_label.setVisible(True)
            self.warning_spin.setVisible(True)
            self._load_support_contact_into_fields()
            return

        self.timeout_label.setText("My inactivity timeout (minutes):")
        self.timeout_help_label.setText(
            "Set your personal timeout. It cannot exceed the admin default."
        )
        self.auto_logout_check.setEnabled(False)
        self.warning_label.setVisible(True)
        self.warning_spin.setVisible(True)

    def _configure_referral_hospitals_section(self):
        show_referrals = self._active_role() == "admin"
        self.referral_hospitals_group.setVisible(show_referrals)
        if not show_referrals:
            return
        if not UserManager.ensure_referral_hospitals_table():
            self.status_label.setText("Unable to prepare referral hospital list")
            return
        self._reload_referral_hospitals()

    def _reload_referral_hospitals(self):
        self._referral_hospital_rows = UserManager.list_referral_hospitals(active_only=False)
        self._referral_hospital_lookup = {
            int(item.get("id")): item
            for item in self._referral_hospital_rows
            if item.get("id") is not None
        }
        self.referral_hospitals_table.setRowCount(0)
        for item in self._referral_hospital_rows:
            row_index = self.referral_hospitals_table.rowCount()
            self.referral_hospitals_table.insertRow(row_index)

            hospital_item = QTableWidgetItem(str(item.get("hospital_name") or ""))
            hospital_item.setData(Qt.UserRole, int(item.get("id") or 0))
            self.referral_hospitals_table.setItem(row_index, 0, hospital_item)
            self.referral_hospitals_table.setItem(row_index, 1, QTableWidgetItem(str(item.get("department") or "")))
            contact_label = str(item.get("contact_person") or item.get("phone") or item.get("email") or "")
            self.referral_hospitals_table.setItem(row_index, 2, QTableWidgetItem(contact_label))
            status_chunks = ["Active" if item.get("is_active") else "Inactive"]
            if item.get("is_default"):
                status_chunks.append("Default")
            self.referral_hospitals_table.setItem(row_index, 3, QTableWidgetItem(" / ".join(status_chunks)))

        self._selected_referral_hospital_id = None
        self.hospital_delete_btn.setEnabled(False)
        self._clear_referral_hospital_form(reset_default=True)

    def _selected_referral_hospital(self):
        row = self.referral_hospitals_table.currentRow()
        if row < 0:
            return None
        id_item = self.referral_hospitals_table.item(row, 0)
        if id_item is None:
            return None
        hospital_id = int(id_item.data(Qt.UserRole) or 0)
        if not hospital_id:
            return None
        return self._referral_hospital_lookup.get(hospital_id)

    def _on_referral_hospital_selected(self):
        item = self._selected_referral_hospital()
        if not item:
            self._selected_referral_hospital_id = None
            self.hospital_delete_btn.setEnabled(False)
            return

        self._selected_referral_hospital_id = int(item.get("id") or 0)
        self.hospital_name_input.setText(str(item.get("hospital_name") or ""))
        self.hospital_department_input.setText(str(item.get("department") or ""))
        self.hospital_contact_input.setText(str(item.get("contact_person") or ""))
        self.hospital_phone_input.setText(str(item.get("phone") or ""))
        self.hospital_email_input.setText(str(item.get("email") or ""))
        self.hospital_address_input.setText(str(item.get("address") or ""))
        self.hospital_active_check.setChecked(bool(item.get("is_active")))
        self.hospital_default_check.setChecked(bool(item.get("is_default")))
        self.hospital_delete_btn.setEnabled(True)

    def _clear_referral_hospital_form(self, reset_default: bool = False):
        self._selected_referral_hospital_id = None
        self.hospital_name_input.clear()
        self.hospital_department_input.clear()
        self.hospital_contact_input.clear()
        self.hospital_phone_input.clear()
        self.hospital_email_input.clear()
        self.hospital_address_input.clear()
        self.hospital_active_check.setChecked(True)
        self.hospital_default_check.setChecked(False if reset_default else self.hospital_default_check.isChecked())
        self.hospital_delete_btn.setEnabled(False)
        self.referral_hospitals_table.clearSelection()

    def _save_referral_hospital(self):
        if self._active_role() != "admin":
            QMessageBox.warning(self, "Trusted Hospitals", "Only admins can manage trusted hospitals.")
            return

        hospital_name = self.hospital_name_input.text().strip()
        if not hospital_name:
            QMessageBox.warning(self, "Validation Error", "Please enter a hospital name.")
            self.hospital_name_input.setFocus()
            return

        ok, message, hospital_id = UserManager.upsert_referral_hospital(
            hospital_name=hospital_name,
            department=self.hospital_department_input.text().strip(),
            contact_person=self.hospital_contact_input.text().strip(),
            phone=self.hospital_phone_input.text().strip(),
            email=self.hospital_email_input.text().strip(),
            address=self.hospital_address_input.text().strip(),
            is_active=self.hospital_active_check.isChecked(),
            is_default=self.hospital_default_check.isChecked(),
            hospital_id=self._selected_referral_hospital_id,
        )
        if not ok:
            QMessageBox.warning(self, "Trusted Hospitals", message)
            return

        action_label = "Updated" if self._selected_referral_hospital_id else "Added"
        self._reload_referral_hospitals()
        self.status_label.setText(f"Hospital {action_label.lower()}: {hospital_name}")
        QMessageBox.information(self, "Trusted Hospitals", f"Hospital {action_label.lower()} successfully: {hospital_name}")
        self._clear_referral_hospital_form(reset_default=True)
        
        if hospital_id:
            for row_idx in range(self.referral_hospitals_table.rowCount()):
                id_item = self.referral_hospitals_table.item(row_idx, 0)
                if not id_item:
                    continue
                found_id = int(id_item.data(Qt.UserRole) or 0)
                if found_id != int(hospital_id):
                    continue
                self.referral_hospitals_table.selectRow(row_idx)
                self._on_referral_hospital_selected()
                break

    def _delete_referral_hospital(self):
        item = self._selected_referral_hospital()
        if not item:
            QMessageBox.information(self, "Trusted Hospitals", "Select a hospital to delete.")
            return

        hospital_label = str(item.get("hospital_name") or "this hospital")
        reply = QMessageBox.question(
            self,
            "Delete Trusted Hospital",
            f"Delete {hospital_label} from the trusted referral list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, message = UserManager.delete_referral_hospital(int(item.get("id") or 0))
        if not ok:
            QMessageBox.warning(self, "Trusted Hospitals", message)
            return

        self._reload_referral_hospitals()
        self.status_label.setText(f"Hospital removed: {hospital_label}")
        QMessageBox.information(self, "Trusted Hospitals", f"Hospital removed successfully: {hospital_label}")
        self._clear_referral_hospital_form(reset_default=True)

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
            "about_text": p.get("settings_about_text", ""),
            "terms_text": p.get("settings_terms_text", ""),
            "privacy_text": p.get("settings_privacy_text", ""),
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
        if pack["about_text"]:
            self.about_contact_label.setText(pack["about_text"])
        if pack["terms_text"]:
            self.terms_label.setText(pack["terms_text"])
        if pack["privacy_text"]:
            self.privacy_label.setText(pack["privacy_text"])
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

    def _config_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), self.CONFIG_FILE)

    def _default_settings(self) -> dict:
        return {
            "theme": "Light",
            "language": "English",
            "auto_logout_enabled": True,
            "inactivity_timeout_minutes": 15,
            "inactivity_warning_seconds": 30,
        }

    @staticmethod
    def _default_admin_contact() -> dict:
        return {
            "name": "",
            "email": "",
            "phone": "",
            "location": "",
        }

    def _load_admin_contact_data(self) -> dict:
        data = self._default_admin_contact()
        path = self._config_path()
        if not os.path.exists(path):
            return data
        try:
            with open(path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                contact = loaded.get("admin_contact")
                if isinstance(contact, dict):
                    for key in data:
                        data[key] = str(contact.get(key, "") or "").strip()
        except (OSError, json.JSONDecodeError):
            pass
        return data

    @staticmethod
    def _default_support_contact() -> dict:
        return {
            "email": "support@eyeshield.local",
            "phone": "+1-000-000-0000",
            "hours": "Mon-Fri, 8:00 AM - 6:00 PM",
        }

    def _load_support_contact_data(self) -> dict:
        data = self._default_support_contact()
        path = self._config_path()
        if not os.path.exists(path):
            return data
        try:
            with open(path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                support = loaded.get("support_contact")
                if isinstance(support, dict):
                    for key in data:
                        data[key] = str(support.get(key, data[key]) or data[key]).strip()
        except (OSError, json.JSONDecodeError):
            pass
        return data

    def _load_support_contact_into_fields(self):
        support = self._load_support_contact_data()
        self.support_email_input.setText(support["email"])
        self.support_phone_input.setText(support["phone"])
        self.support_hours_input.setText(support["hours"])

    def _save_support_contact_data(self) -> tuple[bool, str]:
        path = self._config_path()
        config = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    config = loaded
            except (OSError, json.JSONDecodeError):
                config = {}
        config["support_contact"] = {
            "email": self.support_email_input.text().strip() or self._default_support_contact()["email"],
            "phone": self.support_phone_input.text().strip() or self._default_support_contact()["phone"],
            "hours": self.support_hours_input.text().strip() or self._default_support_contact()["hours"],
        }
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(config, file, indent=2)
            return True, ""
        except OSError as err:
            return False, str(err)

    def _current_support_contact_values(self) -> dict:
        return {
            "email": self.support_email_input.text().strip(),
            "phone": self.support_phone_input.text().strip(),
            "hours": self.support_hours_input.text().strip(),
        }

    def _sync_timeout_enabled_state(self):
        if self._active_role() == "admin":
            enabled = self.auto_logout_check.isChecked()
        else:
            enabled = bool(self._policy_auto_logout_enabled)
        self.timeout_label.setEnabled(enabled)
        self.timeout_spin.setEnabled(enabled)
        self.warning_label.setEnabled(enabled)
        self.warning_spin.setEnabled(enabled and self._active_role() == "admin")
        self.timeout_help_label.setEnabled(True)

    def _resolve_inactivity_policy(self) -> dict:
        username = self._active_username()
        role = self._active_role()
        if role == "admin":
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
            default_minutes = int(settings.get("inactivity_timeout_minutes", 15) or 15)
            return {
                "enabled": bool(settings.get("auto_logout_enabled", True)),
                "default_minutes": max(1, min(240, default_minutes)),
                "user_minutes": None,
                "effective_minutes": max(1, min(240, default_minutes)),
            }
        return user_store.get_inactivity_policy(username) or {
            "enabled": True,
            "default_minutes": 15,
            "user_minutes": None,
            "effective_minutes": 15,
        }

    def get_runtime_inactivity_settings(self) -> tuple[bool, int, int]:
        policy = self._resolve_inactivity_policy()
        enabled = bool(policy.get("enabled", True))
        effective = int(policy.get("effective_minutes", policy.get("default_minutes", 15)) or 15)
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
        warning_seconds = settings.get("inactivity_warning_seconds", self._policy_warning_seconds)
        try:
            warning_seconds = int(warning_seconds)
        except (TypeError, ValueError):
            warning_seconds = 30
        warning_seconds = max(10, min(300, warning_seconds))
        return enabled, max(1, min(240, effective)), warning_seconds

    def _load_admin_contact_into_fields(self):
        contact = self._load_admin_contact_data()
        self.admin_contact_name_input.setText(contact["name"])
        self.admin_contact_email_input.setText(contact["email"])
        self.admin_contact_phone_input.setText(contact["phone"])
        self.admin_contact_location_input.setText(contact["location"])

    def _save_admin_contact_data(self) -> tuple[bool, str]:
        path = self._config_path()
        config = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    config = loaded
            except (OSError, json.JSONDecodeError):
                config = {}
        config["admin_contact"] = {
            "name": self.admin_contact_name_input.text().strip(),
            "email": self.admin_contact_email_input.text().strip(),
            "phone": self.admin_contact_phone_input.text().strip(),
            "location": self.admin_contact_location_input.text().strip(),
        }
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(config, file, indent=2)
            return True, ""
        except OSError as err:
            return False, str(err)

    def _current_admin_contact_values(self) -> dict:
        return {
            "name": self.admin_contact_name_input.text().strip(),
            "email": self.admin_contact_email_input.text().strip(),
            "phone": self.admin_contact_phone_input.text().strip(),
            "location": self.admin_contact_location_input.text().strip(),
        }

    @staticmethod
    def _default_schedule_payload() -> dict:
        return {
            "mode": "weekly-template",
            "start_time": "09:00 AM",
            "end_time": "05:00 PM",
            "days": ["mon", "tue", "wed", "thu", "fri"],
        }

    @staticmethod
    def _parse_time_value(value: str) -> QTime:
        text = str(value or "").strip()
        if not text:
            return QTime()
        for fmt in ("hh:mm AP", "h:mm AP", "hh:mm ap", "h:mm ap", "HH:mm"):
            parsed = QTime.fromString(text, fmt)
            if parsed.isValid():
                return parsed
        return QTime()

    def _load_schedule_fields(self):
        payload = self._default_schedule_payload()
        profile = get_user_profile(self._active_username()) or {}
        raw_availability = profile.get("availability_json")
        try:
            loaded = json.loads(raw_availability) if isinstance(raw_availability, str) and raw_availability else raw_availability
        except Exception:
            loaded = None
        if isinstance(loaded, dict):
            payload.update({
                "start_time": str(loaded.get("start_time") or payload["start_time"]),
                "end_time": str(loaded.get("end_time") or payload["end_time"]),
                "days": loaded.get("days") or payload["days"],
            })

        start_time = self._parse_time_value(payload.get("start_time"))
        end_time = self._parse_time_value(payload.get("end_time"))
        if start_time.isValid():
            self.schedule_start_time.setTime(start_time)
        if end_time.isValid():
            self.schedule_end_time.setTime(end_time)

        selected_days = payload.get("days") or []
        selected_set = {str(day).strip().lower() for day in selected_days} if isinstance(selected_days, list) else set()
        for day_key, checkbox in self.schedule_day_checks:
            checkbox.setChecked(day_key in selected_set)

    def _current_schedule_payload(self) -> dict:
        return {
            "mode": "weekly-template",
            "start_time": self.schedule_start_time.time().toString("hh:mm AP"),
            "end_time": self.schedule_end_time.time().toString("hh:mm AP"),
            "days": [day for day, checkbox in self.schedule_day_checks if checkbox.isChecked()],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _prompt_current_password(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Confirm Account Update")
        dialog.setModal(True)
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        label = QLabel("Enter your current password to continue:")
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("Current password")
        _add_eye_toggle(password_input)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("Confirm")
        ok_btn.setObjectName("primaryAction")
        ok_btn.setDefault(True)

        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        password_input.returnPressed.connect(dialog.accept)

        button_row.addWidget(cancel_btn)
        button_row.addWidget(ok_btn)

        layout.addWidget(label)
        layout.addWidget(password_input)
        layout.addLayout(button_row)

        confirmed = dialog.exec() == QDialog.DialogCode.Accepted
        return password_input.text(), confirmed

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
        saved_language = settings.get("language", "English")
        if saved_language not in {self.lang_combo.itemText(i) for i in range(self.lang_combo.count())}:
            saved_language = "English"
        self.lang_combo.setCurrentText(saved_language)
        role = self._active_role()
        if role == "admin":
            self.auto_logout_check.setChecked(bool(settings.get("auto_logout_enabled", True)))
            timeout_minutes = settings.get("inactivity_timeout_minutes", 15)
            warning_seconds = settings.get("inactivity_warning_seconds", 30)
            try:
                timeout_minutes = int(timeout_minutes)
            except (TypeError, ValueError):
                timeout_minutes = 15
            try:
                warning_seconds = int(warning_seconds)
            except (TypeError, ValueError):
                warning_seconds = 30
            timeout_minutes = max(1, min(240, timeout_minutes))
            warning_seconds = max(10, min(300, warning_seconds))
            self.timeout_spin.setValue(timeout_minutes)
            self.warning_spin.setValue(warning_seconds)
            self._policy_default_timeout_minutes = timeout_minutes
            self._policy_auto_logout_enabled = bool(self.auto_logout_check.isChecked())
            self._policy_warning_seconds = warning_seconds
        else:
            policy = self._resolve_inactivity_policy()
            self._policy_default_timeout_minutes = int(policy.get("default_minutes", 15) or 15)
            self._policy_auto_logout_enabled = bool(policy.get("enabled", True))
            warning_seconds = settings.get("inactivity_warning_seconds", 30)
            try:
                warning_seconds = int(warning_seconds)
            except (TypeError, ValueError):
                warning_seconds = 30
            self._policy_warning_seconds = max(10, min(300, warning_seconds))
            user_minutes = policy.get("user_minutes")
            effective_minutes = int(policy.get("effective_minutes", self._policy_default_timeout_minutes) or self._policy_default_timeout_minutes)
            display_minutes = int(user_minutes) if user_minutes is not None else effective_minutes
            self.auto_logout_check.setChecked(self._policy_auto_logout_enabled)
            self.timeout_spin.setValue(max(1, min(240, display_minutes)))
            self.warning_spin.setValue(self._policy_warning_seconds)
        self._sync_timeout_enabled_state()
        if self._active_role() == "admin":
            self._load_admin_contact_into_fields()
            self._load_support_contact_into_fields()
        if self._active_role() == "clinician":
            self._load_schedule_fields()
        self.apply_live_preview()
        self.status_label.setText("Settings loaded")

    def save_settings(self):
        is_admin = self._active_role() == "admin"
        admin_contact_changed = False
        support_contact_changed = False
        if is_admin:
            existing_contact = self._load_admin_contact_data()
            pending_contact = self._current_admin_contact_values()
            admin_contact_changed = pending_contact != existing_contact
            if admin_contact_changed:
                reply = QMessageBox.question(
                    self,
                    "Confirm Admin Contact Update",
                    "Apply updated Contact Admin details to the login page?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self.status_label.setText("Save cancelled")
                    return

        if is_admin:
            existing_support = self._load_support_contact_data()
            pending_support = self._current_support_contact_values()
            support_contact_changed = any(
                pending_support.get(key, "").strip() != existing_support.get(key, "").strip()
                for key in ("email", "phone", "hours")
            )

        persisted = self._default_settings()
        path = self._settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    persisted.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

        if is_admin:
            auto_logout_enabled = self.auto_logout_check.isChecked()
            inactivity_timeout_minutes = int(self.timeout_spin.value())
            inactivity_warning_seconds = int(self.warning_spin.value())
        else:
            auto_logout_enabled = bool(persisted.get("auto_logout_enabled", True))
            timeout_value = persisted.get("inactivity_timeout_minutes", 15)
            warning_value = persisted.get("inactivity_warning_seconds", 30)
            try:
                timeout_value = int(timeout_value)
            except (TypeError, ValueError):
                timeout_value = 15
            try:
                warning_value = int(warning_value)
            except (TypeError, ValueError):
                warning_value = 30
            inactivity_timeout_minutes = max(1, min(240, timeout_value))
            inactivity_warning_seconds = max(10, min(300, warning_value))

            preferred_timeout = int(self.timeout_spin.value())
            ok, message, effective_minutes = user_store.update_own_inactivity_timeout(
                current_username=self._active_username(),
                timeout_minutes=preferred_timeout,
            )
            if not ok:
                QMessageBox.warning(self, "Settings", message)
                self.status_label.setText("Save failed")
                return

        settings = {
            "theme": self.theme_combo.currentText(),
            "language": self.lang_combo.currentText(),
            "auto_logout_enabled": auto_logout_enabled,
            "inactivity_timeout_minutes": inactivity_timeout_minutes,
            "inactivity_warning_seconds": inactivity_warning_seconds,
        }
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as file:
                json.dump(settings, file, indent=2)
            if is_admin:
                ok, error_message = self._save_admin_contact_data()
                if not ok:
                    self.status_label.setText("Save failed")
                    QMessageBox.warning(self, "Settings", f"Failed to save admin contact: {error_message}")
                    return
            if is_admin:
                ok, error_message = self._save_support_contact_data()
                if not ok:
                    self.status_label.setText("Save failed")
                    QMessageBox.warning(self, "Settings", f"Failed to save help support contact: {error_message}")
                    return

            main_window = self.window()
            if is_admin and main_window is not self and hasattr(main_window, "apply_inactivity_settings"):
                main_window.apply_inactivity_settings(
                    auto_logout_enabled,
                    inactivity_timeout_minutes,
                    inactivity_warning_seconds,
                )
            if (not is_admin) and main_window is not self and hasattr(main_window, "apply_inactivity_settings"):
                runtime_enabled, runtime_minutes, warning_seconds = self.get_runtime_inactivity_settings()
                main_window.apply_inactivity_settings(runtime_enabled, runtime_minutes, warning_seconds)
            if is_admin and main_window is not self and hasattr(main_window, "help_support_page") and hasattr(main_window.help_support_page, "reload_contact_from_config"):
                main_window.help_support_page.reload_contact_from_config()
            timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.status_label.setText(f"Saved locally at {timestamp}")
            if admin_contact_changed:
                QMessageBox.information(
                    self,
                    "Settings Updated",
                    "Contact Admin information was updated successfully.",
                )
            if support_contact_changed:
                QMessageBox.information(
                    self,
                    "Settings Updated",
                    "Help support contact details were updated successfully.",
                )
            if not is_admin:
                QMessageBox.information(self, "Settings Updated", message)
        except OSError as err:
            self.status_label.setText("Save failed")
            QMessageBox.warning(self, "Settings", f"Failed to save settings: {err}")

    def update_account(self):
        if self._active_role() != "clinician":
            QMessageBox.warning(self, "Account", "Only clinicians can update this section.")
            return

        current_username = self._active_username()
        new_display_name = self.display_name_input.text().strip()
        new_username = self.username_input.text().strip()
        new_password = self.new_password_input.text()

        current_password, confirmed = self._prompt_current_password()
        if not confirmed:
            return
        current_password = str(current_password or "")

        if self.dr_prefix_check.isChecked() and new_display_name:
            if not new_display_name.lower().startswith("dr. "):
                new_display_name = f"Dr. {new_display_name}"

        if not new_display_name:
            QMessageBox.warning(self, "Account", "Display name cannot be empty.")
            return
        if not new_username:
            QMessageBox.warning(self, "Account", "Username cannot be empty.")
            return
        if not current_password:
            QMessageBox.warning(self, "Account", "Enter your current password to continue.")
            return

        ok, message, updated_username = user_store.update_own_account(
            current_username=current_username,
            current_password=current_password,
            new_display_name=new_display_name,
            new_username=new_username,
            new_password=new_password,
        )
        if not ok:
            QMessageBox.warning(self, "Account", message)
            return

        updated_username = str(updated_username or current_username)
        os.environ["EYESHIELD_CURRENT_USER"] = updated_username
        os.environ["EYESHIELD_CURRENT_NAME"] = new_display_name

        main_window = self.window()
        if main_window is not self:
            if hasattr(main_window, "username"):
                main_window.username = updated_username
            if hasattr(main_window, "display_name"):
                main_window.display_name = new_display_name
            if hasattr(main_window, "user_info_label"):
                display_title = getattr(main_window, "display_title", "")
                main_window.user_info_label.setText(f"  {new_display_name}  •  {display_title}  ")

        self.new_password_input.clear()
        self.username_input.setText(updated_username)
        self.status_label.setText("Account updated")
        requires_relogin = (updated_username != current_username) or bool(new_password)
        if requires_relogin:
            QMessageBox.information(
                self,
                "Account",
                f"{message}\n\nPlease re-login to apply all account changes.",
            )
        else:
            QMessageBox.information(
                self,
                "Account",
                f"{message}\n\nDisplay name changes are applied immediately.",
            )

    def update_schedule(self):
        if self._active_role() != "clinician":
            QMessageBox.warning(self, "Schedule", "Only clinicians can update this section.")
            return

        selected_days = [day for day, checkbox in self.schedule_day_checks if checkbox.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "Schedule", "Select at least one available weekday.")
            return
        if self.schedule_end_time.time() <= self.schedule_start_time.time():
            QMessageBox.warning(self, "Schedule", "End time must be later than start time.")
            return

        availability_json = json.dumps(
            self._current_schedule_payload(),
            ensure_ascii=True,
            separators=(",", ":"),
        )
        ok, message = user_store.update_own_availability(
            current_username=self._active_username(),
            availability_json=availability_json,
        )
        if not ok:
            QMessageBox.warning(self, "Schedule", message)
            return

        self.status_label.setText("Schedule updated")
        main_window = self.window()
        if main_window is not self and hasattr(main_window, "refresh_dashboard"):
            main_window.refresh_dashboard()
        QMessageBox.information(
            self,
            "Schedule Updated",
            message,
        )

    def reset_defaults(self):
        defaults = self._default_settings()
        self.theme_combo.setCurrentText(defaults["theme"])
        self.lang_combo.setCurrentText(defaults["language"])
        if self._active_role() == "admin":
            self.auto_logout_check.setChecked(bool(defaults["auto_logout_enabled"]))
            self.timeout_spin.setValue(int(defaults["inactivity_timeout_minutes"]))
            self.warning_spin.setValue(int(defaults["inactivity_warning_seconds"]))
            support_defaults = self._default_support_contact()
            self.support_email_input.setText(support_defaults["email"])
            self.support_phone_input.setText(support_defaults["phone"])
            self.support_hours_input.setText(support_defaults["hours"])
        else:
            self.timeout_spin.setValue(int(self._policy_default_timeout_minutes or defaults["inactivity_timeout_minutes"]))
            self.auto_logout_check.setChecked(bool(self._policy_auto_logout_enabled))
            self.warning_spin.setValue(int(self._policy_warning_seconds or defaults["inactivity_warning_seconds"]))
        self._sync_timeout_enabled_state()
        if self._active_role() == "admin":
            admin_defaults = self._default_admin_contact()
            self.admin_contact_name_input.setText(admin_defaults["name"])
            self.admin_contact_email_input.setText(admin_defaults["email"])
            self.admin_contact_phone_input.setText(admin_defaults["phone"])
            self.admin_contact_location_input.setText(admin_defaults["location"])
        if self._active_role() == "clinician":
            default_schedule = self._default_schedule_payload()
            start_time = self._parse_time_value(default_schedule["start_time"])
            end_time = self._parse_time_value(default_schedule["end_time"])
            if start_time.isValid():
                self.schedule_start_time.setTime(start_time)
            if end_time.isValid():
                self.schedule_end_time.setTime(end_time)
            selected_days = set(default_schedule["days"])
            for day_key, checkbox in self.schedule_day_checks:
                checkbox.setChecked(day_key in selected_days)
        self.status_label.setText("Defaults restored (not yet saved)")
