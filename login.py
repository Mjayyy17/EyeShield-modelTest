"""Login module for EyeShield application."""

import os

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QMessageBox
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt

try:
    from user_auth import verify_user
except Exception:
    from .user_auth import verify_user


def _add_eye_toggle(field):
    """Attach a show/hide password toggle icon to the trailing edge of a QLineEdit."""
    import os as _os
    _icon_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "icons")
    _show_icon = QIcon(_os.path.join(_icon_dir, "eye_open.svg"))
    _hide_icon = QIcon(_os.path.join(_icon_dir, "eye_closed.svg"))
    action = QAction(_show_icon, "", field)
    action.setCheckable(True)
    action.setToolTip("Show / hide password")

    def _toggle(visible):
        action.setIcon(_hide_icon if visible else _show_icon)
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    action.toggled.connect(_toggle)
    field.addAction(action, QLineEdit.TrailingPosition)


class LoginWindow(QWidget):
    """Login window for user authentication"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("EyeShield - Login")
        self.setFixedSize(500, 420)
        self.setStyleSheet("""
            QWidget {
                background: #f8f9fa;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("EyeShield")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 700;
            color: #007bff;
            margin-bottom: 8px;
        """)

        subtitle = QLabel("Clinical Screening System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #6c757d;
            margin-bottom: 24px;
        """)

        form_widget = QWidget()
        form_widget.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 8px;
                border: 1px solid #dee2e6;
                padding: 16px;
            }
        """)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(16)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setMinimumHeight(40)
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                background: white;
                min-width: 250px;
            }
            QLineEdit:focus {
                border-color: #0d6efd;
            }
        """)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                background: white;
                min-width: 250px;
            }
            QLineEdit:focus {
                border-color: #0d6efd;
            }
        """)

        btn = QPushButton("Sign In")
        btn.setMinimumHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background: #0d6efd;
                color: white;
                border: 1px solid #0b5ed7;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0b5ed7;
            }
        """)
        btn.clicked.connect(self.handle_login)

        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)
        _add_eye_toggle(self.password_input)

        form_layout.addWidget(self.username_input)
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(btn)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(form_widget)

    def handle_login(self):
        """Handle login button click"""
        from dashboard import EyeShieldApp
        
        role = verify_user(
            self.username_input.text(),
            self.password_input.text()
        )

        if role:
            os.environ["EYESHIELD_CURRENT_USER"] = self.username_input.text().strip()
            os.environ["EYESHIELD_CURRENT_ROLE"] = role
            self.main = EyeShieldApp(self.username_input.text(), role)
            self.main.show()
            self.close()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid credentials.")
