"""Login module for EyeShield application."""

import os
import json

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QCheckBox, QMessageBox, QDialog, QFrame,
    QTextEdit,
    QScrollArea, QTableWidget, QTableWidgetItem, QStyle
)
from PySide6.QtGui import QAction, QIcon, QDesktopServices, QPixmap, QColor
from PySide6.QtCore import Qt, QUrl, QSize, QTimer

try:
    from user_auth import verify_user, get_user_profile
    from auth import UserManager
except Exception:
    from .user_auth import verify_user, get_user_profile
    from .auth import UserManager


def _load_admin_contact():
    """Load admin contact info from config.json located next to this file."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("admin_contact", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _add_eye_toggle(field):
    """Attach a show/hide password toggle icon to the trailing edge of a QLineEdit."""
    _icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    _show_icon = QIcon(os.path.join(_icon_dir, "eye_open.svg"))
    _hide_icon = QIcon(os.path.join(_icon_dir, "eye_closed.svg"))
    action = QAction(_show_icon, "", field)
    action.setCheckable(True)
    action.setToolTip("Show / hide password")

    def _toggle(visible):
        action.setIcon(_hide_icon if visible else _show_icon)
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    action.toggled.connect(_toggle)
    field.addAction(action, QLineEdit.TrailingPosition)


class PendingReferralsDialog(QDialog):
    """Dialog showing pending referrals assigned to clinician on login"""

    def __init__(self, username, referrals, parent=None):
        super().__init__(parent)
        self.go_to_referrals = False
        self.setWindowTitle("Pending Clinical Handoffs")
        self.setFixedSize(600, 400)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel(f"You have {len(referrals)} pending referral(s)")
        header.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 16px;
                font-weight: 700;
            }
        """)
        layout.addWidget(header)

        # Referrals table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Patient", "Priority", "Referred By", "Assigned At"])
        table.horizontalHeader().setStretchLastSection(False)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(2, 120)
        table.setColumnWidth(3, 140)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #374151;
                padding: 8px;
                border: none;
                font-weight: 600;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
        """)

        # Add referral rows
        for i, referral in enumerate(referrals):
            table.insertRow(i)
            
            patient_name = referral.get("patient_name", "Unknown")
            table.setItem(i, 0, QTableWidgetItem(patient_name))
            
            urgency = referral.get("urgency", "normal").capitalize()
            urgency_item = QTableWidgetItem(urgency)
            if urgency == "Urgent":
                urgency_item.setBackground(QColor("#fee2e2"))
                urgency_item.setForeground(QColor("#dc2626"))
            elif urgency == "Critical":
                urgency_item.setBackground(QColor("#fef2f2"))
                urgency_item.setForeground(QColor("#991b1b"))
            table.setItem(i, 1, urgency_item)
            
            assigned_by = referral.get("assigned_by", "Admin")
            table.setItem(i, 2, QTableWidgetItem(assigned_by))
            
            assigned_at = referral.get("assigned_at", "Unknown")
            # Format timestamp
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(assigned_at)
                formatted_date = dt.strftime("%b %d, %H:%M")
            except:
                formatted_date = assigned_at
            table.setItem(i, 3, QTableWidgetItem(formatted_date))

        layout.addWidget(table)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        view_btn = QPushButton("Open Referral Worklist")
        view_btn.setMinimumHeight(36)
        view_btn.setStyleSheet("""
            QPushButton {
                background: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0056b3;
            }
        """)
        view_btn.clicked.connect(self._accept_and_open_referrals)
        button_layout.addWidget(view_btn)
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #e5e7eb;
                color: #374151;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #d1d5db;
            }
        """)
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

    def _accept_and_open_referrals(self):
        self.go_to_referrals = True
        self.accept()


class ReferralOptionsDialog(QDialog):
    """Dialog to choose between internal referral or generating a letter"""

    def __init__(self, patient_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Referral")
        self.setMinimumSize(560, 380)
        self.setModal(True)
        self.selected_option = None  # "internal" or "letter"
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Header
        title = QLabel("Choose referral workflow")
        title.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 16px;
                font-weight: 700;
                background: transparent;
            }
        """)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel(f"Patient: {patient_name}")
        subtitle.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 13px;
                background: transparent;
            }
        """)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        # Option 1: Internal Referral
        internal_btn = QPushButton()
        internal_btn.setCursor(Qt.PointingHandCursor)
        internal_btn.setMinimumHeight(118)
        internal_btn.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #dbe3ee;
                border-radius: 10px;
                padding: 14px;
                text-align: left;
                color: #374151;
            }
            QPushButton:hover {
                border: 1px solid #3b82f6;
                background: #f0f9ff;
            }
            QPushButton:pressed {
                background: #e0f2fe;
            }
        """)

        internal_layout = QHBoxLayout(internal_btn)
        internal_layout.setContentsMargins(0, 0, 0, 0)
        internal_layout.setSpacing(12)

        internal_icon = QLabel()
        internal_icon.setFixedSize(28, 28)
        internal_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView).pixmap(QSize(22, 22)))
        internal_icon.setStyleSheet("background: transparent;")
        internal_icon.setAlignment(Qt.AlignCenter)
        internal_layout.addWidget(internal_icon, 0, Qt.AlignTop)

        internal_text = QVBoxLayout()
        internal_text.setSpacing(6)
        internal_title = QLabel("Internal Clinical Handoff")
        internal_title.setStyleSheet("color: #0f172a; font-weight: 700; font-size: 14px; background: transparent;")
        internal_text.addWidget(internal_title)

        internal_desc = QLabel("Assign this case to another EyeShield clinician for ongoing clinical review.")
        internal_desc.setWordWrap(True)
        internal_desc.setStyleSheet("color: #475569; font-size: 12px; line-height: 1.3; background: transparent;")
        internal_text.addWidget(internal_desc)

        internal_hint = QLabel("Use for doctor-to-doctor handoff inside EyeShield")
        internal_hint.setStyleSheet("color: #1d4ed8; font-size: 11px; font-weight: 600; background: transparent;")
        internal_text.addWidget(internal_hint)
        internal_layout.addLayout(internal_text, 1)
        internal_btn.clicked.connect(lambda: self._set_option("internal"))
        layout.addWidget(internal_btn)

        # Option 2: Generate Letter
        letter_btn = QPushButton()
        letter_btn.setCursor(Qt.PointingHandCursor)
        letter_btn.setMinimumHeight(118)
        letter_btn.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #dbe3ee;
                border-radius: 10px;
                padding: 14px;
                text-align: left;
                color: #374151;
            }
            QPushButton:hover {
                border: 1px solid #10b981;
                background: #f0fdf4;
            }
            QPushButton:pressed {
                background: #dcfce7;
            }
        """)

        letter_layout = QHBoxLayout(letter_btn)
        letter_layout.setContentsMargins(0, 0, 0, 0)
        letter_layout.setSpacing(12)

        letter_icon = QLabel()
        letter_icon.setFixedSize(28, 28)
        letter_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton).pixmap(QSize(22, 22)))
        letter_icon.setStyleSheet("background: transparent;")
        letter_icon.setAlignment(Qt.AlignCenter)
        letter_layout.addWidget(letter_icon, 0, Qt.AlignTop)

        letter_text = QVBoxLayout()
        letter_text.setSpacing(6)
        letter_title = QLabel("External Referral Letter")
        letter_title.setStyleSheet("color: #0f172a; font-weight: 700; font-size: 14px; background: transparent;")
        letter_text.addWidget(letter_title)

        letter_desc = QLabel("Generate a formal referral document for external ophthalmology services.")
        letter_desc.setWordWrap(True)
        letter_desc.setStyleSheet("color: #475569; font-size: 12px; line-height: 1.3; background: transparent;")
        letter_text.addWidget(letter_desc)

        letter_hint = QLabel("Use when sending the case outside EyeShield")
        letter_hint.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600; background: transparent;")
        letter_text.addWidget(letter_hint)
        letter_layout.addLayout(letter_text, 1)

        letter_btn.clicked.connect(lambda: self._set_option("letter"))
        layout.addWidget(letter_btn)

        layout.addStretch(1)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e5e7eb;
                color: #374151;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #d1d5db;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _set_option(self, option):
        """Set the selected option and accept the dialog"""
        self.selected_option = option
        self.accept()


class AssignReferralDialog(QDialog):
    """Dialog for assigning referral to a clinician"""

    def __init__(self, patient_name, parent=None, exclude_username: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Assign Clinical Handoff")
        self.setMinimumSize(560, 520)
        self.setModal(True)
        self.selected_clinician = None
        self.urgency_level = "normal"
        self.notes_text = ""
        self.go_back = False
        self._urgency_buttons = []
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel(f"Assign clinical handoff for {patient_name}")
        header.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        layout.addWidget(header)

        # Get all clinicians
        try:
            from auth import UserManager
        except ImportError:
            from .auth import UserManager

        excluded = str(exclude_username or "").strip().lower()
        all_users = UserManager.get_all_users()
        clinicians = [
            u
            for u in all_users
            if (
                str(u[6] or "").strip().lower() == "clinician"
                and int(u[7] or 0) == 1
                and str(u[0] or "").strip().lower() != excluded
            )
        ]  # role at index 6, username at index 0

        if not clinicians:
            QMessageBox.warning(self, "Clinical Handoff", "No other active clinicians are available for handoff.")
            self.reject()
            return

        # Clinician selection
        clinician_label = QLabel("Receiving Clinician:")
        clinician_label.setStyleSheet("color: #374151; font-weight: 600; font-size: 12px;")
        layout.addWidget(clinician_label)

        clinician_combo = QLineEdit()
        clinician_combo.setReadOnly(True)
        clinician_combo.setPlaceholderText("Choose receiving clinician...")
        clinician_combo.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                color: #374151;
            }
        """)
        layout.addWidget(clinician_combo)

        # Clinician dropdown (button list for quick choose)
        clinician_buttons_layout = QVBoxLayout()
        clinician_buttons_layout.setSpacing(6)
        clinician_buttons_layout.setContentsMargins(0, 0, 0, 0)

        def select_clinician(username, display_name):
            self.selected_clinician = username
            clinician_combo.setText(display_name)

        sorted_clinicians = sorted(
            clinicians,
            key=lambda u: (
                str(u[2] or u[1] or u[0]).strip().lower(),
                str(u[4] or "").strip().lower(),
            ),
        )
        for clinician in sorted_clinicians:
            username, full_name, display_name, _, specialization = clinician[0], clinician[1], clinician[2], clinician[3], clinician[4]
            label_name = str(display_name or full_name or username).strip()
            label_title = str(specialization or "Clinician").strip()
            btn = QPushButton(f"{label_name} ({label_title})")
            btn.setMinimumHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background: white;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    color: #374151;
                    font-size: 12px;
                    text-align: left;
                    padding-left: 12px;
                }
                QPushButton:hover {
                    background: #f3f4f6;
                }
            """)
            btn.clicked.connect(lambda checked, u=username, d=label_name: select_clinician(u, d))
            clinician_buttons_layout.addWidget(btn)

        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_widget.setLayout(clinician_buttons_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(220)
        layout.addWidget(scroll)

        # Urgency level
        urgency_label = QLabel("Clinical Priority:")
        urgency_label.setStyleSheet("color: #374151; font-weight: 600; font-size: 12px; margin-top: 8px;")
        layout.addWidget(urgency_label)

        urgency_layout = QHBoxLayout()
        urgency_layout.setSpacing(10)
        for level in ["Normal", "Urgent", "Critical"]:
            urgency_btn = QPushButton(level)
            urgency_btn.setFixedWidth(110)
            urgency_btn.setStyleSheet("""
                QPushButton {
                    background: #ffffff;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    color: #374151;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #e5e7eb;
                }
            """)
            urgency_btn.clicked.connect(
                lambda checked, l=level.lower(), b=urgency_btn: self._set_urgency(l, b, urgency_layout)
            )
            self._urgency_buttons.append(urgency_btn)
            urgency_layout.addWidget(urgency_btn)
        urgency_layout.addStretch()
        layout.addLayout(urgency_layout)
        self._set_urgency("normal", self._urgency_buttons[0], urgency_layout)

        comments_label = QLabel("Additional Comments (Optional):")
        comments_label.setStyleSheet("color: #374151; font-weight: 600; font-size: 12px; margin-top: 8px;")
        layout.addWidget(comments_label)

        self.comments_input = QTextEdit()
        self.comments_input.setPlaceholderText("Add optional referral context for the receiving clinician...")
        self.comments_input.setMinimumHeight(88)
        self.comments_input.setStyleSheet(
            """
            QTextEdit {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                color: #374151;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #93c5fd;
            }
            """
        )
        layout.addWidget(self.comments_input)

        layout.addStretch()

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        assign_btn = QPushButton("Confirm Handoff")
        assign_btn.setMinimumHeight(36)
        assign_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        assign_btn.clicked.connect(self._on_assign)
        button_layout.addWidget(assign_btn)

        back_btn = QPushButton("Back to Options")
        back_btn.setMinimumHeight(36)
        back_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #374151;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
        """)
        back_btn.clicked.connect(self._on_back)
        button_layout.addWidget(back_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e5e7eb;
                color: #374151;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #d1d5db;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _set_urgency(self, level, button, layout):
        self.urgency_level = level
        # Update button styling
        for i in range(layout.count() - 1):  # Exclude stretch item
            btn = layout.itemAt(i).widget()
            if btn:
                if btn == button:
                    btn.setStyleSheet("""
                        QPushButton {
                            background: #007bff;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            font-weight: 600;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background: #ffffff;
                            border: 1px solid #dee2e6;
                            border-radius: 4px;
                            color: #374151;
                            font-size: 12px;
                        }
                        QPushButton:hover {
                            background: #e5e7eb;
                        }
                    """)

    def _on_assign(self):
        if not self.selected_clinician:
            QMessageBox.warning(self, "Clinical Handoff", "Please select the receiving clinician.")
            return
        self.notes_text = str(self.comments_input.toPlainText() or "").strip()
        self.accept()

    def _on_back(self):
        self.go_back = True
        self.reject()


class ContactAdminDialog(QDialog):
    """Popup dialog showing admin contact information from config.json."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contact Administrator")
        self.setFixedWidth(380)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1b2a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(0)
        
        # Title
        title = QLabel("Contact Administrator")
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: 700;
                background: transparent;
                margin-bottom: 4px;
            }
        """)

        subtitle = QLabel("Use the details below to request an account or reset access.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.35);
                font-size: 12px;
                background: transparent;
                margin-bottom: 24px;
            }
        """)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: rgba(255,255,255,0.08); margin-bottom: 20px;")
        layout.addWidget(divider)

        # Load contact info
        contact = _load_admin_contact()

        field_label_style = """
            QLabel {
                color: rgba(255,255,255,0.38);
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
                background: transparent;
                margin-top: 14px;
                margin-bottom: 2px;
            }
        """
        value_style = """
            QLabel {
                color: #ffffff;
                font-size: 14px;
                background: transparent;
            }
        """
        placeholder_style = """
            QLabel {
                color: rgba(255,255,255,0.2);
                font-size: 14px;
                font-style: italic;
                background: transparent;
            }
        """

        fields = [
            ("NAME",     contact.get("name",     "")),
            ("EMAIL",    contact.get("email",    "")),
            ("PHONE",    contact.get("phone",    "")),
            ("LOCATION", contact.get("location", "")),
        ]

        self._email = contact.get("email", "")

        for label_text, value in fields:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(field_label_style)
            layout.addWidget(lbl)

            if value:
                val = QLabel(value)
                val.setStyleSheet(value_style)
                val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            else:
                val = QLabel("Not configured")
                val.setStyleSheet(placeholder_style)
            layout.addWidget(val)

        layout.addSpacing(28)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        if self._email:
            email_btn = QPushButton("Open Email")
            email_btn.setMinimumHeight(40)
            email_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #378ADD, stop:1 #185FA5);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4a96e8, stop:1 #1e6fb8);
                }
            """)
            email_btn.clicked.connect(self._open_email)
            btn_row.addWidget(email_btn)

        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(40)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.6);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: #ffffff;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _open_email(self):
        """Open the default mail client with a pre-filled subject."""
        if self._email:
            QDesktopServices.openUrl(
                QUrl(f"mailto:{self._email}?subject=EyeShield%20Account%20Request")
            )


class LoginWindow(QWidget):
    """Login window for user authentication"""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_SECONDS = 30

    def __init__(self):
        super().__init__()

        self.failed_attempts = 0
        self.lockout_remaining_seconds = 0
        self._allow_close_without_prompt = False
        self.lockout_timer = QTimer(self)
        self.lockout_timer.setInterval(1000)
        self.lockout_timer.timeout.connect(self._update_lockout_countdown)

        self.setWindowTitle("EyeShield - Login")
        self.setFixedSize(500, 480)
        self.setStyleSheet("""
            QWidget#LoginWindow {
                background-color: #f4f8fc;
            }
        """)
        self.setObjectName("LoginWindow")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 44, 48, 40)
        layout.setSpacing(0)

        # --- Header block (title above logo) ---
        header_col = QVBoxLayout()
        header_col.setSpacing(8)
        header_col.setAlignment(Qt.AlignHCenter)

        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        logo_path = os.path.join(icon_dir, "Logo.png")
        title_path = os.path.join(icon_dir, "title.png")

        logo_box = QLabel("👁")
        logo_box.setFixedSize(64, 64)
        logo_box.setAlignment(Qt.AlignCenter)
        logo_box.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #cbe6ff, stop:1 #b7f0df);
                border-radius: 18px;
                border: 1px solid #b5d6f5;
                font-size: 24px;
            }
        """)
        if os.path.isfile(logo_path):
            logo_pixmap = QPixmap(logo_path).scaled(QSize(54, 54), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not logo_pixmap.isNull():
                logo_box.setText("")
                logo_box.setPixmap(logo_pixmap)
                logo_box.setStyleSheet("QLabel { background: transparent; border: none; }")

        title = QLabel("Eye<span style='color:#378ADD;'>Shield</span>")
        title.setTextFormat(Qt.RichText)
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("""
            QLabel {
                color: #12355b;
                font-size: 28px;
                font-weight: 700;
                background: transparent;
            }
        """)
        if os.path.isfile(title_path):
            title_pixmap = QPixmap(title_path).scaled(QSize(220, 52), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not title_pixmap.isNull():
                title.setText("")
                title.setPixmap(title_pixmap)

        header_col.addWidget(title, 0, Qt.AlignHCenter)
        header_col.addWidget(logo_box, 0, Qt.AlignHCenter)


        # --- Field label style ---
        field_label_style = """
            QLabel {
                color: #5d7590;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
                background: transparent;
                margin-bottom: 2px;
            }
        """

        # --- Input style ---
        input_style = """
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cfe0f2;
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 14px;
                color: #102a43;
                min-height: 28px;
            }
            QLineEdit:focus {
                border: 1px solid #3d8fd6;
                background-color: #f4faff;
            }
        """

        # Username
        username_label = QLabel("USERNAME")
        username_label.setStyleSheet(field_label_style)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setMinimumHeight(48)
        self.username_input.setStyleSheet(input_style)

        # Password
        password_label = QLabel("PASSWORD")
        password_label.setStyleSheet(field_label_style)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(48)
        self.password_input.setStyleSheet(input_style)
  
        # --- Sign In button ---
        btn = QPushButton("Sign In")
        btn.setMinimumHeight(50)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4394dc, stop:1 #2f76bf);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #57a4ea, stop:1 #3785d1);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2f76bf, stop:1 #245f9a);
            }
        """)
        btn.clicked.connect(self.handle_login)
        self.sign_in_btn = btn

        self.login_feedback = QLabel("")
        self.login_feedback.setAlignment(Qt.AlignHCenter)
        self.login_feedback.setStyleSheet("color: #7d93ab; font-size: 12px; background: transparent;")

        # --- Footer ---
        footer_row = QHBoxLayout()
        footer_row.setAlignment(Qt.AlignCenter)

        footer = QLabel("Forgot password or need a new account?")
        footer.setStyleSheet("color: #7d93ab; font-size: 12px; background: transparent;")

        contact_btn = QPushButton("Contact admin")
        contact_btn.setCursor(Qt.PointingHandCursor)
        contact_btn.setFlat(True)
        contact_btn.setStyleSheet("""
            QPushButton {
                color: #2f76bf;
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 0;
                margin-left: 4px;
            }
            QPushButton:hover {
                color: #4294dd;
                text-decoration: underline;
            }
        """)
        contact_btn.clicked.connect(self.show_contact_dialog)

        footer_row.addWidget(footer)
        footer_row.addWidget(contact_btn)

        # --- Key bindings ---
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)
        _add_eye_toggle(self.password_input)

        # --- Assemble layout ---
        layout.addLayout(header_col)
        layout.addWidget(username_label)
        layout.addWidget(self.username_input)
        layout.addSpacing(14)
        layout.addWidget(password_label)
        layout.addWidget(self.password_input)
        layout.addSpacing(14)
        layout.addSpacing(24)
        layout.addWidget(btn)
        layout.addSpacing(8)
        layout.addWidget(self.login_feedback)
        layout.addSpacing(16)
        layout.addLayout(footer_row)
        layout.addStretch()

    def show_contact_dialog(self):
        """Open the Contact Administrator dialog."""
        dlg = ContactAdminDialog(self)
        dlg.exec()

    def handle_login(self):
        """Handle login button click"""
        from dashboard import EyeShieldApp

        if self.lockout_remaining_seconds > 0:
            QMessageBox.warning(
                self,
                "Login Locked",
                f"Too many failed attempts. Please wait {self.lockout_remaining_seconds} seconds.",
            )
            return

        username = self.username_input.text().strip()
        role = verify_user(
            username,
            self.password_input.text()
        )

        if role:
            self.failed_attempts = 0
            self.login_feedback.setText("")
            profile = get_user_profile(username) or {}
            full_name = str(profile.get("full_name") or username).strip()
            display_name = str(profile.get("display_name") or full_name or username).strip()
            specialization = str(profile.get("specialization") or "").strip()
            contact = str(profile.get("contact") or "").strip()
            display_title = specialization if role == "clinician" and specialization else role

            os.environ["EYESHIELD_CURRENT_USER"] = username
            os.environ["EYESHIELD_CURRENT_ROLE"] = role
            os.environ["EYESHIELD_CURRENT_NAME"] = display_name
            os.environ["EYESHIELD_CURRENT_SPECIALIZATION"] = specialization
            os.environ["EYESHIELD_CURRENT_TITLE"] = display_title
            os.environ["EYESHIELD_CURRENT_CONTACT"] = contact

            try:
                import user_store
                user_store.log_activity(username, "Login")
            except Exception:
                pass

            self.main = EyeShieldApp(
                username,
                role,
                display_name=display_name,
                full_name=full_name,
                specialization=specialization,
                contact=contact,
            )
            self.main.show()
            self._allow_close_without_prompt = True
            self.close()
        else:
            self.failed_attempts += 1
            remaining_attempts = self.MAX_FAILED_ATTEMPTS - self.failed_attempts
            if remaining_attempts <= 0:
                self._start_lockout()
                return

            self.login_feedback.setText(f"Attempts remaining: {remaining_attempts}")
            QMessageBox.warning(
                self,
                "Login Failed",
                f"Invalid credentials. You have {remaining_attempts} attempt(s) remaining.",
            )

    def _set_login_inputs_enabled(self, enabled: bool):
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.sign_in_btn.setEnabled(enabled)

    def _start_lockout(self):
        self.lockout_remaining_seconds = self.LOCKOUT_SECONDS
        self._set_login_inputs_enabled(False)
        self._update_lockout_feedback()
        self.lockout_timer.start()
        QMessageBox.warning(
            self,
            "Too Many Attempts",
            f"Too many failed login attempts. Login is locked for {self.LOCKOUT_SECONDS} seconds.",
        )

    def _update_lockout_feedback(self):
        self.login_feedback.setText(f"Login locked. Try again in {self.lockout_remaining_seconds}s")

    def _update_lockout_countdown(self):
        self.lockout_remaining_seconds -= 1
        if self.lockout_remaining_seconds > 0:
            self._update_lockout_feedback()
            return

        self.lockout_timer.stop()
        self.failed_attempts = 0
        self.lockout_remaining_seconds = 0
        self._set_login_inputs_enabled(True)
        self.login_feedback.setText("You can try signing in again.")

    def closeEvent(self, event):
        if self._allow_close_without_prompt:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Quit EyeShield",
            "Are you sure you want to quit EyeShield?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
