"""
Users management module for EyeShield EMR application.
Provides a GUI for creating, listing, updating and deleting users.
"""

import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QPushButton, QLineEdit, QComboBox, QMessageBox,
    QGroupBox, QFormLayout, QAbstractItemView, QDialog, QApplication,
    QHeaderView, QGridLayout, QInputDialog, QMenu
)
from PySide6.QtGui import QFont, QAction, QIcon, QColor
from PySide6.QtCore import Qt
import user_store


# â”€â”€ Role badge colours â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_ROLE_COLORS = {
    "admin":     ("#c0392b", "#fdf2f2"),
    "clinician": ("#0d6efd", "#eef3ff"),
    "viewer":    ("#6c757d", "#f3f4f6"),
}

_ROLE_COLORS_DARK = {
    "admin":     ("#f38ba8", "#3d1f2d"),
    "clinician": ("#89b4fa", "#1f2f4f"),
    "viewer":    ("#bac2de", "#2f3348"),
}

_SPECIALIZATION_OPTIONS = ["Optometrist", "Ophthalmologist"]

# â”€â”€ Shared dialog stylesheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_DIALOG_STYLE = """
    QDialog { background: #ffffff; }
    QLabel  { font-size: 13px; color: #212529; background: transparent; border: none; }
    QLabel#dlgTitle { font-size: 16px; font-weight: 700; color: #212529; margin-bottom: 2px; }
    QLabel#dlgHint  { font-size: 11px; color: #6c757d; }
    QLineEdit, QComboBox {
        background: #f8f9fa;
        border: 1px solid #ced4da;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1.5px solid #0d6efd;
        background: #ffffff;
    }
    QPushButton {
        border-radius: 8px; padding: 8px 20px;
        font-size: 13px; font-weight: 600; border: none; min-width: 90px;
    }
    QPushButton#okBtn     { background: #0d6efd; color: white; }
    QPushButton#okBtn:hover { background: #0b5ed7; }
    QPushButton#cancelBtn { background: #e9ecef; color: #495057; border: 1px solid #ced4da; }
    QPushButton#cancelBtn:hover { background: #dee2e6; }
"""

# â”€â”€ Page stylesheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_PAGE_STYLE = """
    QWidget#usersPage {
        background: #f0f2f5;
        font-family: 'Segoe UI', 'Inter', 'Arial';
    }
    QGroupBox {
        background: #ffffff;
        border: 1px solid #dde1e7;
        border-radius: 10px;
        padding: 14px;
        margin-top: 8px;
        font-weight: 600;
        font-size: 13px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
        color: #495057;
    }
    QLineEdit, QComboBox {
        background: #ffffff;
        border: 1px solid #ced4da;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus { border: 1.5px solid #0d6efd; }
    QTableWidget {
        background: #ffffff;
        gridline-color: #ecf0f4;
        border: 1px solid #e3e8ef;
        border-radius: 10px;
        font-size: 13px;
        alternate-background-color: #f8fbff;
        selection-background-color: #e6f0ff;
        selection-color: #0a58ca;
    }
    QTableWidget#usrUsersTable::item { padding: 12px 10px; border-bottom: 1px solid #eef2f7; }
    QTableWidget#usrActivityTable::item { padding: 10px 8px; border-bottom: 1px solid #f1f3f6; }
    QTableWidget::item:selected { background: #e7f1ff; color: #0a58ca; }
    QHeaderView::section {
        background: #f6f9fc;
        padding: 11px 10px;
        border: none;
        border-bottom: 1px solid #d7dfe8;
        font-weight: 700;
        font-size: 11px;
        color: #5f6b7a;
        letter-spacing: 0.4px;
        text-transform: uppercase;
    }
    QPushButton {
        border-radius: 8px; padding: 8px 16px;
        font-size: 13px; font-weight: 600; border: none;
    }
    QPushButton#primaryBtn   { background: #0d6efd; color: #ffffff; }
    QPushButton#primaryBtn:hover { background: #0b5ed7; }
    QPushButton#primaryBtn:disabled { background: #b8d0f8; color: #e8f0fe; }
    QPushButton#dangerBtn    { background: #dc3545; color: #ffffff; }
    QPushButton#dangerBtn:hover  { background: #b02a37; }
    QPushButton#warningBtn   { background: #fd7e14; color: #ffffff; }
    QPushButton#warningBtn:hover { background: #dc6a0a; }
    QPushButton#neutralBtn   { background: #e9ecef; color: #495057; border: 1px solid #ced4da; }
    QPushButton#neutralBtn:hover { background: #dee2e6; }
    QLineEdit#usrSearchInput {
        background: #ffffff;
        border: 1px solid #cfe0f2;
        border-radius: 12px;
        padding: 8px 12px;
        font-size: 13px;
        color: #1f2937;
        min-height: 34px;
    }
    QLineEdit#usrSearchInput:focus {
        border: 1.5px solid #0d6efd;
        background: #f8fbff;
    }
    QLabel#usrStatTotal,
    QLabel#usrStatAdmin,
    QLabel#usrStatSpecialists,
    QLabel#usrStatViewer {
        border-radius: 12px;
        padding: 7px 12px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid transparent;
    }
    QLabel#usrStatTotal {
        color: #0b5ed7;
        background: #eaf2ff;
        border-color: #cfe0ff;
    }
    QLabel#usrStatAdmin {
        color: #842029;
        background: #fdecef;
        border-color: #f5c2c7;
    }
    QLabel#usrStatSpecialists {
        color: #0f5132;
        background: #e8f7ef;
        border-color: #b7e4c7;
    }
    QLabel#usrStatViewer {
        color: #495057;
        background: #f1f3f5;
        border-color: #dee2e6;
    }
    QWidget#usrNotifyBar {
        background: #e8f5ee;
        border: 1px solid #b7e4c7;
        border-radius: 10px;
    }
    QLabel#usrNotifyText {
        color: #0f5132;
        font-size: 12px;
        font-weight: 600;
        background: transparent;
    }
    QPushButton#usrNotifyClose {
        background: transparent;
        color: #0f5132;
        border: none;
        font-size: 14px;
        font-weight: 700;
        padding: 0 4px;
        min-width: 18px;
    }
    QPushButton#usrNotifyClose:hover {
        color: #0a3622;
    }
"""


def _password_meets_policy(password):
    return (
        len(password) >= 12
        and any(c.islower() for c in password)
        and any(c.isupper() for c in password)
        and any(c.isdigit() for c in password)
        and any(not c.isalnum() for c in password)
    )


def _assignable_roles():
    return ["clinician", "viewer", "admin"]


def _add_eye_toggle(field):
    """Attach a show/hide password toggle to the trailing edge of a QLineEdit."""
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


def _verify_acting_admin(current_username, acting_password):
    """Return True if acting_password matches the stored hash for current_username."""
    try:
        from auth import get_connection, PasswordManager
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = ?", (current_username,))
        row = cur.fetchone()
        conn.close()
        return bool(row and PasswordManager.verify_password(acting_password, row[0]))
    except Exception:
        return False


# â”€â”€ User Manager â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class UserManager:
    """Thin UI-layer wrapper around user_store."""

    @staticmethod
    def create_user(
        username,
        password,
        role,
        full_name,
        display_name,
        contact,
        specialization,
        acting_username=None,
        acting_role=None,
        acting_password=None,
    ):
        return user_store.add_user(
            username,
            password,
            role,
            full_name,
            display_name,
            contact,
            specialization,
            acting_username,
            acting_role,
            acting_password,
        )

    @staticmethod
    def get_all_users():
        return [(u["username"], u["role"]) for u in user_store.get_all_users()]

    @staticmethod
    def delete_user(username, acting_username=None, acting_role=None):
        return user_store.delete_user(username, acting_username, acting_role)

    @staticmethod
    def update_user_role(username, new_role, acting_username=None, acting_role=None):
        return user_store.update_user_role(username, new_role, acting_username, acting_role)

    @staticmethod
    def reset_password(username, new_password, acting_username=None, acting_role=None):
        return user_store.reset_password(username, new_password, acting_username, acting_role)


# â”€â”€ Dialogs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class NewUserDialog(QDialog):
    """Modal dialog for creating a new user."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New User")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Create New User")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label_style = "color:#344054;font-size:12px;font-weight:600;background:transparent;border:none;"

        def _lbl(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(label_style)
            return lbl

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("3â€“32 chars: letters, digits, _ . -")
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Legal or full professional name")
        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Display name shown across the app and reports")
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Phone or email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Min 12 chars")
        self.password_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.password_input)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Re-type password")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.confirm_password_input)
        self.role_input = QComboBox()
        self.role_input.addItems(_assignable_roles())
        self.specialization_input = QComboBox()
        self.specialization_input.addItems(_SPECIALIZATION_OPTIONS)
        self.role_input.currentTextChanged.connect(self._on_role_changed)
        
        form.addRow(_lbl("Full Name:"), self.full_name_input)
        form.addRow(_lbl("Display Name:"), self.display_name_input)
        form.addRow(_lbl("Contact:"), self.contact_input)
        form.addRow(_lbl("Username:"), self.username_input)
        form.addRow(_lbl("Password:"), self.password_input)
        form.addRow(_lbl("Confirm:"), self.confirm_password_input)
        form.addRow(_lbl("Role:"), self.role_input)
        form.addRow(_lbl("Specialization:"), self.specialization_input)
        layout.addLayout(form)
        self._on_role_changed(self.role_input.currentText())

        hint = QLabel("Password must be 12+ chars with uppercase, lowercase, number & symbol.")
        hint.setObjectName("dlgHint")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        create_btn = QPushButton("Create Account")
        create_btn.setObjectName("okBtn")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._create_user)
        cancel_btn.clicked.connect(self.reject)
        self.confirm_password_input.returnPressed.connect(self._create_user)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

    def _on_role_changed(self, role_value):
        is_clinician = str(role_value or "").strip().lower() == "clinician"
        self.specialization_input.setEnabled(is_clinician)

    def _create_user(self):
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        display_name = self.display_name_input.text().strip()
        contact = self.contact_input.text().strip()
        password = self.password_input.text()
        role = self.role_input.currentText()
        specialization = self.specialization_input.currentText().strip()

        # ── Field presence ────────────────────────────────────────────
        if not username or not full_name or not display_name or not password:
            QMessageBox.warning(self, "Missing Fields", "Full name, display name, username, and password are required.")
            return

        if role == "clinician" and not specialization:
            QMessageBox.warning(self, "Missing Specialization", "Select a specialization for clinician accounts.")
            return

        # ── Username format (mirrors auth.py USERNAME_PATTERN) ────────
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{3,32}", username):
            QMessageBox.warning(
                self, "Invalid Username",
                "Username must be 3–32 characters and may only contain\n"
                "letters, digits, underscores (_), dots (.) and hyphens (-).",
            )
            return

        if username.lower() == password.lower():
            QMessageBox.warning(
                self,
                "Invalid Credentials",
                "Username and password cannot be the same.",
            )
            return

        # ── Password checks ───────────────────────────────────────────
        if password != self.confirm_password_input.text():
            QMessageBox.warning(self, "Password Mismatch", "The passwords you entered do not match.")
            return
        if not _password_meets_policy(password):
            QMessageBox.warning(
                self, "Weak Password",
                "Password must be at least 12 characters and include\n"
                "uppercase, lowercase, a number, and a symbol.",
            )
            return

        # ── Resolve acting admin context ──────────────────────────────
        parent = self.parent()
        parent_app = getattr(parent, "parent_app", None)
        acting_username = (
            getattr(parent_app, "username", None)
            or os.environ.get("EYESHIELD_CURRENT_USER")
        )
        acting_role = (
            getattr(parent_app, "role", None)
            or os.environ.get("EYESHIELD_CURRENT_ROLE")
        )

        if not acting_username or acting_role != "admin":
            QMessageBox.warning(
                self, "Permission Denied",
                "Only administrators can create user accounts.\n"
                "Please log in as an admin and try again.",
            )
            return

        # ── Duplicate check ───────────────────────────────────────────
        existing_names = {u["username"].lower() for u in user_store.get_all_users()}
        if username.lower() in existing_names:
            QMessageBox.warning(
                self, "Username Taken",
                f"The username '{username}' is already in use.\n"
                "Please choose a different username.",
            )
            return

        # ── Admin password confirmation ───────────────────────────────
        proceed = QMessageBox.question(
            self,
            "Confirm Account Creation",
            f"Create account for <b>{display_name}</b> with role <b>{role}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = UsersPage.prompt_for_admin_password(self, "create this account")
        if acting_password is None:
            return
        if not _verify_acting_admin(acting_username, acting_password):
            QMessageBox.warning(
                self, "Incorrect Password",
                "The admin password you entered is incorrect.\n"
                "Please try again.",
            )
            return

        # ── Create ────────────────────────────────────────────────────
        success = UserManager.create_user(
            username, password, role,
            full_name,
            display_name,
            contact,
            specialization,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )
        if success:
            if hasattr(parent, "refresh_users"):
                parent.refresh_users()
            if hasattr(parent, "log_activity"):
                parent.log_activity(username, f"Created as {role}")
            if hasattr(parent, "_set_status"):
                parent._set_status(f"User '{username}' created successfully")
            if hasattr(parent, "show_notification"):
                parent.show_notification(f"Account created: {display_name} ({role}).")
            self.accept()
        else:
            QMessageBox.warning(
                self, "Creation Failed",
                "An unexpected error occurred while saving the account.\n"
                "Please check the application logs for details.",
            )


class ChangeRoleDialog(QDialog):
    """Modal dialog for changing a user's role."""

    def __init__(self, username, current_role, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Change Role \u2014 {username}")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Change User Role")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Select a new role for <b>{username}</b>:"))

        self.role_input = QComboBox()
        self.role_input.addItems(_assignable_roles())
        self.role_input.setCurrentText(current_role)
        layout.addWidget(self.role_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        ok_btn = QPushButton("Apply Change")
        ok_btn.setObjectName("okBtn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def selected_role(self):
        return self.role_input.currentText()


class ResetPasswordDialog(QDialog):
    """Modal dialog for resetting a user's password."""

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Reset Password \u2014 {username}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Reset Password")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Set a new password for <b>{username}</b>:"))

        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("New password")
        self.pw_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.pw_input)
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm new password")
        self.confirm_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.confirm_input)
        layout.addWidget(self.pw_input)
        layout.addWidget(self.confirm_input)

        hint = QLabel("Password must be 12+ chars with uppercase, lowercase, number & symbol.")
        hint.setObjectName("dlgHint")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        ok_btn = QPushButton("Reset Password")
        ok_btn.setObjectName("okBtn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        self.confirm_input.returnPressed.connect(self._validate)

    def _validate(self):
        if not self.pw_input.text():
            QMessageBox.warning(self, "Empty Password", "Password cannot be empty.")
            return
        if not _password_meets_policy(self.pw_input.text()):
            QMessageBox.warning(
                self, "Weak Password",
                "Password must be at least 12 characters and include\n"
                "uppercase, lowercase, a number, and a symbol.",
            )
            return
        if self.pw_input.text() != self.confirm_input.text():
            QMessageBox.warning(self, "Password Mismatch", "The passwords do not match.")
            return
        self.accept()

    def new_password(self):
        return self.pw_input.text()


# â”€â”€ Users Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class UsersPage(QWidget):
    """User Management page."""

    def __init__(self):
        super().__init__()
        self.setObjectName("usersPage")
        self.setStyleSheet(_PAGE_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        header_row = QHBoxLayout()
        self._usr_title_lbl = QLabel("User Management")
        self._usr_title_lbl.setStyleSheet(
            "font-size:22px;font-weight:700;color:#0d6efd;"
            "font-family:'Segoe UI','Inter','Arial';"
        )
        self.count_label = QLabel("User Directory")
        self.count_label.setStyleSheet("color:#6c757d;font-size:13px;font-weight:600;margin-left:10px;")
        header_row.addWidget(self._usr_title_lbl)
        header_row.addWidget(self.count_label)
        header_row.addStretch()

        refresh_btn = QPushButton("\u27f3  Refresh")
        refresh_btn.setObjectName("neutralBtn")
        refresh_btn.clicked.connect(self.refresh_users)
        add_btn = QPushButton("\u002b  New User")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._open_new_user_dialog)
        header_row.addWidget(refresh_btn)
        header_row.addWidget(add_btn)
        main_layout.addLayout(header_row)

        self.notify_bar = QWidget()
        self.notify_bar.setObjectName("usrNotifyBar")
        notify_layout = QHBoxLayout(self.notify_bar)
        notify_layout.setContentsMargins(10, 8, 10, 8)
        notify_layout.setSpacing(8)
        self.notify_text = QLabel("")
        self.notify_text.setObjectName("usrNotifyText")
        notify_layout.addWidget(self.notify_text, 1)
        self.notify_close_btn = QPushButton("×")
        self.notify_close_btn.setObjectName("usrNotifyClose")
        self.notify_close_btn.clicked.connect(self.notify_bar.hide)
        notify_layout.addWidget(self.notify_close_btn)
        self.notify_bar.hide()
        main_layout.addWidget(self.notify_bar)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("usrSearchInput")
        self.search_input.setPlaceholderText("Search by name, username, role, specialization, or contact")
        self.search_input.textChanged.connect(self.refresh_users)
        controls_row.addWidget(self.search_input, 1)

        self.total_chip = QLabel("Total 0")
        self.total_chip.setObjectName("usrStatTotal")
        controls_row.addWidget(self.total_chip)

        self.admin_chip = QLabel("Admin 0")
        self.admin_chip.setObjectName("usrStatAdmin")
        controls_row.addWidget(self.admin_chip)

        self.specialists_chip = QLabel("Specialists 0")
        self.specialists_chip.setObjectName("usrStatSpecialists")
        controls_row.addWidget(self.specialists_chip)

        self.viewer_chip = QLabel("Viewer 0")
        self.viewer_chip.setObjectName("usrStatViewer")
        controls_row.addWidget(self.viewer_chip)

        main_layout.addLayout(controls_row)

        # â”€â”€ Grid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        # Users table card
        self._usr_table_group = QGroupBox("Users")
        table_vbox = QVBoxLayout(self._usr_table_group)
        table_vbox.setSpacing(8)

        self.users_table = QTableWidget(0, 3)
        self.users_table.setObjectName("usrUsersTable")
        self.users_table.setHorizontalHeaderLabels(["Name", "Username", "Role"])
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setShowGrid(True)
        self.users_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_table.customContextMenuRequested.connect(self._open_user_context_menu)
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.users_table.setMinimumHeight(240)
        table_vbox.addWidget(self.users_table)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.change_role_btn = QPushButton("Change Role")
        self.change_role_btn.setObjectName("neutralBtn")
        self.change_role_btn.clicked.connect(self.change_selected_role)
        self.reset_pw_btn = QPushButton("Reset Password")
        self.reset_pw_btn.setObjectName("warningBtn")
        self.reset_pw_btn.clicked.connect(self.reset_selected_password)
        self.delete_btn = QPushButton("Delete User")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self.delete_user)
        action_row.addWidget(self.change_role_btn)
        action_row.addWidget(self.reset_pw_btn)
        action_row.addWidget(self.delete_btn)
        table_vbox.addLayout(action_row)
        grid.addWidget(self._usr_table_group, 0, 0)

        # Activity log card
        self._usr_log_group = QGroupBox("Activity Log")
        log_vbox = QVBoxLayout(self._usr_log_group)
        self.activity_log = QTableWidget(0, 3)
        self.activity_log.setObjectName("usrActivityTable")
        self.activity_log.setHorizontalHeaderLabels(["User", "Action", "Time"])
        self.activity_log.setSelectionMode(QAbstractItemView.NoSelection)
        self.activity_log.setEditTriggers(QTableWidget.NoEditTriggers)
        self.activity_log.verticalHeader().setVisible(False)
        self.activity_log.setShowGrid(False)
        self.activity_log.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity_log.setMinimumHeight(240)
        log_vbox.addWidget(self.activity_log)
        grid.addWidget(self._usr_log_group, 0, 1)

        main_layout.addLayout(grid)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusBar")
        self.status_label.setStyleSheet("color:#6c757d;font-size:12px;padding:2px 0;")
        main_layout.addWidget(self.status_label)

        self.refresh_users()

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _open_new_user_dialog(self):
        NewUserDialog(parent=self).exec()

    def _set_status(self, message, ok=True):
        color = "#198754" if ok else "#dc3545"
        icon = "\u2713" if ok else "\u2717"
        self.status_label.setStyleSheet(
            f"color:{color};font-size:12px;font-weight:600;padding:2px 0;"
        )
        self.status_label.setText(f"{icon}  {message}")

    def show_notification(self, message: str):
        self.notify_text.setText(message)
        self.notify_bar.show()

    def _open_user_context_menu(self, pos):
        item = self.users_table.itemAt(pos)
        if item is None:
            return
        self.users_table.selectRow(item.row())

        menu = QMenu(self)
        change_role_action = menu.addAction("Change Role")
        reset_password_action = menu.addAction("Reset Password")
        menu.addSeparator()
        delete_action = menu.addAction("Delete User")

        chosen = menu.exec(self.users_table.viewport().mapToGlobal(pos))
        if chosen == change_role_action:
            self.change_selected_role()
        elif chosen == reset_password_action:
            self.reset_selected_password()
        elif chosen == delete_action:
            self.delete_user()

    def _actor_context(self):
        parent_app = getattr(self, "parent_app", None)
        username = getattr(parent_app, "username", None) or os.environ.get("EYESHIELD_CURRENT_USER")
        role = getattr(parent_app, "role", None) or os.environ.get("EYESHIELD_CURRENT_ROLE")
        return username, role

    @staticmethod
    def prompt_for_admin_password(parent, action="perform this action"):
        pw, accepted = QInputDialog.getText(
            parent,
            "Admin Confirmation",
            f"Enter your admin password to {action}:",
            QLineEdit.Password,
        )
        if not accepted:
            return None
        if not pw:
            QMessageBox.warning(parent, "Missing Password", "Admin password is required.")
            return None
        return pw

    def _check_admin_password(self, acting_password):
        """Verify the acting admin's password and show an error if wrong. Returns True on success."""
        current_username, _ = self._actor_context()
        if not _verify_acting_admin(current_username, acting_password):
            QMessageBox.warning(self, "Incorrect Password", "Your admin password is incorrect.")
            return False
        return True

    # â”€â”€ User Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def refresh_users(self):
        self.users_table.setRowCount(0)
        users = user_store.get_all_users()
        app = QApplication.instance()
        app_stylesheet = app.styleSheet() if app else ""
        dark_mode = "#1e1e2e" in app_stylesheet
        role_colors = _ROLE_COLORS_DARK if dark_mode else _ROLE_COLORS

        total_count = len(users)
        admin_count = sum(1 for user in users if user.get("role") == "admin")
        clinician_count = sum(1 for user in users if user.get("role") == "clinician")
        viewer_count = sum(1 for user in users if user.get("role") == "viewer")

        if hasattr(self, "total_chip"):
            self.total_chip.setText(f"Total {total_count}")
            self.admin_chip.setText(f"Admin {admin_count}")
            self.specialists_chip.setText(f"Specialists {clinician_count}")
            self.viewer_chip.setText(f"Viewer {viewer_count}")

        query = ""
        if hasattr(self, "search_input"):
            query = self.search_input.text().strip().lower()

        filtered_users = []
        for user in users:
            role = str(user.get("role") or "")
            specialization = str(user.get("specialization") or "")
            haystack = " ".join(
                [
                    str(user.get("full_name") or ""),
                    str(user.get("display_name") or ""),
                    str(user.get("username") or ""),
                    str(user.get("contact") or ""),
                    role,
                    specialization,
                ]
            ).lower()
            if query and query not in haystack:
                continue
            filtered_users.append(user)

        shown = len(filtered_users)
        self.count_label.setText(f"Showing {shown} of {total_count} users")

        for user in filtered_users:
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)

            name_item = QTableWidgetItem(user.get("full_name") or user["username"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            username_item = QTableWidgetItem(user["username"])
            username_item.setFlags(username_item.flags() & ~Qt.ItemIsEditable)

            role = user["role"]
            specialization = str(user.get("specialization") or "").strip()
            display_role = specialization if role == "clinician" and specialization else role
            role_item = QTableWidgetItem(f"  {display_role}  ")
            role_item.setFlags(role_item.flags() & ~Qt.ItemIsEditable)
            role_item.setTextAlignment(Qt.AlignCenter)
            role_item.setData(Qt.UserRole, role)
            fg, bg = role_colors.get(role, ("#212529", "#f8f9fa"))
            role_item.setForeground(QColor(fg))
            role_item.setBackground(QColor(bg))

            self.users_table.setItem(row, 0, name_item)
            self.users_table.setItem(row, 1, username_item)
            self.users_table.setItem(row, 2, role_item)
        self.users_table.resizeRowsToContents()

    # â”€â”€ CRUD Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def delete_user(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to delete.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 2)
        if not username_item or not role_item:
            return

        username = username_item.text()
        role = str(role_item.data(Qt.UserRole) or role_item.text().strip())
        current_username, current_role = self._actor_context()

        if role == "admin" and current_role == "admin" and username != current_username:
            QMessageBox.warning(
                self, "Not Allowed",
                "Admins cannot delete other admin accounts.",
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to permanently delete user '<b>{username}</b>'?<br>"
            "<br><i>This action cannot be undone.</i>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(self, f"delete user '{username}'")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        success = user_store.delete_user(username, acting_username=current_username, acting_role=current_role)
        if success:
            self._set_status(f"User '{username}' deleted")
            self.log_activity(username, "Deleted")
            self.refresh_users()
            QMessageBox.information(self, "User Deleted", f"User '{username}' was successfully deleted.")
        else:
            self._set_status(f"Failed to delete '{username}'", ok=False)
            QMessageBox.warning(self, "Deletion Failed", f"Could not delete user '{username}'.")

    def change_selected_role(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to change their role.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 2)
        if not username_item or not role_item:
            return

        username = username_item.text()
        current_role_val = str(role_item.data(Qt.UserRole) or role_item.text().strip())

        dlg = ChangeRoleDialog(username, current_role_val, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_role = dlg.selected_role()
        if new_role == current_role_val:
            return

        proceed = QMessageBox.question(
            self,
            "Confirm Role Change",
            f"Change role for '<b>{username}</b>' from <b>{current_role_val}</b> to <b>{new_role}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(
            self, f"change '{username}' to {new_role}"
        )
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        acting_username, acting_role = self._actor_context()
        success = user_store.update_user_role(
            username, new_role, acting_username=acting_username, acting_role=acting_role
        )
        if success:
            self._set_status(f"Role updated: {username} \u2192 {new_role}")
            self.log_activity(username, f"Role changed to {new_role}")
            self.refresh_users()
            QMessageBox.information(
                self, "Role Updated",
                f"'{username}' has been changed to <b>{new_role}</b>.",
            )
        else:
            self._set_status(f"Failed to update role for '{username}'", ok=False)
            QMessageBox.warning(self, "Update Failed", f"Could not update role for '{username}'.")

    def reset_selected_password(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to reset their password.")
            return
        username_item = self.users_table.item(row, 1)
        if not username_item:
            return
        username = username_item.text()

        dlg = ResetPasswordDialog(username, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        proceed = QMessageBox.question(
            self,
            "Confirm Password Reset",
            f"Reset password for '<b>{username}</b>' now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(self, f"reset '{username}' password")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        acting_username, acting_role = self._actor_context()
        success = user_store.reset_password(
            username, dlg.new_password(),
            acting_username=acting_username, acting_role=acting_role,
        )
        if success:
            self._set_status(f"Password reset for '{username}'")
            self.log_activity(username, "Password reset")
            QMessageBox.information(
                self, "Password Reset",
                f"Password for '{username}' was successfully reset.",
            )
        else:
            self._set_status(f"Failed to reset password for '{username}'", ok=False)
            QMessageBox.warning(self, "Reset Failed", f"Could not reset password for '{username}'.")

    def log_activity(self, user, action):
        from datetime import datetime
        row = self.activity_log.rowCount()
        self.activity_log.insertRow(row)
        self.activity_log.setItem(row, 0, QTableWidgetItem(user))
        self.activity_log.setItem(row, 1, QTableWidgetItem(action))
        self.activity_log.setItem(row, 2, QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._usr_title_lbl.setText(pack["usr_title"])
        self._usr_table_group.setTitle(pack["usr_table"])
        self._usr_log_group.setTitle(pack["usr_log"])

