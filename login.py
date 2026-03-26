"""Login module for EyeShield application."""

import os
import json

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QCheckBox, QMessageBox, QDialog, QFrame
)
from PySide6.QtGui import QAction, QIcon, QDesktopServices, QPixmap
from PySide6.QtCore import Qt, QUrl, QSize, QTimer

try:
    from user_auth import verify_user, get_user_profile
except Exception:
    from .user_auth import verify_user, get_user_profile


def _load_admin_contact():
    """Load admin contact info from config.json located next to this file."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
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

        subtitle = QLabel("Reach out to request an account or reset access.")
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