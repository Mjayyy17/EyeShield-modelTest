"""
Users management module for EyeShield EMR application.
Provides a GUI for creating, listing, updating and deleting users.
"""

import os
import re
import json
from datetime import date, datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QPushButton, QLineEdit, QComboBox, QMessageBox,
    QGroupBox, QFormLayout, QAbstractItemView, QDialog, QApplication,
    QHeaderView, QInputDialog, QMenu, QCheckBox, QTimeEdit, QTabWidget
)
from PySide6.QtGui import QFont, QAction, QIcon, QColor
from PySide6.QtCore import Qt, QTime
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
_WEEKDAY_OPTIONS = [
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
    ("sat", "Saturday"),
    ("sun", "Sunday"),
]
_WEEKDAY_LABELS = {key: label for key, label in _WEEKDAY_OPTIONS}

# â”€â”€ Shared dialog stylesheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_DIALOG_STYLE = """
    QDialog { background: #ffffff; }
    QLabel  { font-size: 13px; color: #212529; background: transparent; border: none; }
    QLabel#dlgTitle { font-size: 16px; font-weight: 700; color: #212529; margin-bottom: 2px; }
    QLabel#dlgHint  { font-size: 11px; color: #6c757d; }
    QCheckBox {
        font-size: 13px;
        color: #212529;
        spacing: 8px;
        padding: 3px 0;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #adb5bd;
        border-radius: 4px;
        background: #ffffff;
    }
    QCheckBox::indicator:checked {
        border-color: #0d6efd;
        background: #0d6efd;
    }
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
    QTabWidget#usrAdminTabs::pane {
        border: 1px solid #dce5ef;
        border-radius: 12px;
        background: #ffffff;
        top: -1px;
    }
    QTabWidget#usrAdminTabs QTabBar::tab {
        background: #eef3f9;
        color: #4a5563;
        border: 1px solid #d4deea;
        border-bottom: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        padding: 6px 14px;
        min-width: 110px;
        font-size: 12px;
        font-weight: 700;
        margin-right: 6px;
    }
    QTabWidget#usrAdminTabs QTabBar::tab:selected {
        background: #ffffff;
        color: #0d6efd;
        border-color: #c7d8ef;
    }
    QLabel#usrSectionTitle {
        color: #1f2a37;
        font-size: 14px;
        font-weight: 700;
        background: transparent;
    }
    QLabel#usrSectionHint {
        color: #738295;
        font-size: 11px;
        font-weight: 500;
        background: transparent;
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
        availability_json="",
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
            availability_json,
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
        self.dr_prefix_checkbox = QCheckBox("Include honorific title (Dr.)")
        self.dr_prefix_checkbox.setStyleSheet("color:#495057;font-size:12px;font-weight:600;padding:2px 0;")
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
        form.addRow("", self.dr_prefix_checkbox)
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
        create_btn = QPushButton("Proceed")
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
        add_dr_prefix = self.dr_prefix_checkbox.isChecked()
        contact = self.contact_input.text().strip()
        password = self.password_input.text()
        role = self.role_input.currentText()
        specialization = self.specialization_input.currentText().strip()

        if add_dr_prefix and display_name and not display_name.lower().startswith("dr."):
            display_name = f"Dr. {display_name}"

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

        availability_dialog = AvailabilityDialog(self)
        if availability_dialog.exec() != QDialog.Accepted:
            return
        availability_json = "" if availability_dialog.skip_selected else availability_dialog.get_availability_json()

        # ── Create ────────────────────────────────────────────────────
        success = UserManager.create_user(
            username, password, role,
            full_name,
            display_name,
            contact,
            specialization,
            availability_json=availability_json,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )
        if success:
            if hasattr(parent, "refresh_users"):
                parent.refresh_users()
            if hasattr(parent, "log_activity"):
                parent.log_activity(username, f"Account Created ({role})")
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


class AvailabilityDialog(QDialog):
    """Step 2 dialog for setting recurring weekly availability."""

    def __init__(self, parent=None, initial_availability=None):
        super().__init__(parent)
        self.setWindowTitle("Weekly Availability")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)
        self.skip_selected = False
        self._day_checks = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Set Weekly Availability")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)

        subtitle = QLabel("Select available weekdays and time range. This repeats weekly until changed.")
        subtitle.setObjectName("dlgHint")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        time_row = QHBoxLayout()
        time_row.setSpacing(4)
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("hh:mm AP")
        self.start_time.setFixedWidth(110)
        self.start_time.setTime(QTime(9, 0))
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("hh:mm AP")
        self.end_time.setFixedWidth(110)
        self.end_time.setTime(QTime(17, 0))
        time_row.addWidget(QLabel("From"))
        time_row.addWidget(self.start_time)
        time_row.addWidget(QLabel("To"))
        time_row.addWidget(self.end_time)
        time_row.addStretch()
        layout.addLayout(time_row)

        for idx, (day_key, day_label) in enumerate(_WEEKDAY_OPTIONS):
            checkbox = QCheckBox(day_label)
            checkbox.setChecked(idx < 5)
            self._day_checks.append((day_key, checkbox))
            layout.addWidget(checkbox)

        if isinstance(initial_availability, dict):
            start_time = str(initial_availability.get("start_time") or "").strip()
            end_time = str(initial_availability.get("end_time") or "").strip()
            selected_days = initial_availability.get("days") or []

            # Backward compatibility for older date-based availability payloads.
            if not selected_days:
                legacy_dates = initial_availability.get("dates") or []
                if isinstance(legacy_dates, list):
                    resolved_days = []
                    for date_value in legacy_dates:
                        try:
                            parsed_day = datetime.strptime(str(date_value), "%Y-%m-%d").date().strftime("%a").lower()
                            resolved_days.append(parsed_day)
                        except Exception:
                            pass
                    selected_days = resolved_days

            if start_time:
                parsed = self._parse_time_value(start_time)
                if parsed.isValid():
                    self.start_time.setTime(parsed)
            if end_time:
                parsed = self._parse_time_value(end_time)
                if parsed.isValid():
                    self.end_time.setTime(parsed)

            if isinstance(selected_days, list):
                selected_set = {str(value).strip().lower() for value in selected_days}
                for day_key, checkbox in self._day_checks:
                    checkbox.setChecked(day_key in selected_set)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("cancelBtn")
        skip_btn = QPushButton("Skip For Now")
        skip_btn.setObjectName("neutralBtn")
        save_btn = QPushButton("Save Account")
        save_btn.setObjectName("okBtn")
        back_btn.clicked.connect(self.reject)
        skip_btn.clicked.connect(self._skip)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(back_btn)
        btn_row.addWidget(skip_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _skip(self):
        self.skip_selected = True
        self.accept()

    def _save(self):
        selected_days = [day for day, cb in self._day_checks if cb.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "Availability", "Select at least one weekday or choose Skip For Now.")
            return
        if self.end_time.time() <= self.start_time.time():
            QMessageBox.warning(self, "Availability", "End time must be later than start time.")
            return
        self.skip_selected = False
        self.accept()

    def get_availability_json(self) -> str:
        payload = {
            "mode": "weekly-template",
            "start_time": self.start_time.time().toString("hh:mm AP"),
            "end_time": self.end_time.time().toString("hh:mm AP"),
            "days": [day for day, cb in self._day_checks if cb.isChecked()],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

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
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

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

        add_btn = QPushButton("\u002b  New User")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._open_new_user_dialog)
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

        # Users table card
        self._usr_table_group = QGroupBox("Users")
        table_vbox = QVBoxLayout(self._usr_table_group)
        table_vbox.setSpacing(6)

        users_hdr = QHBoxLayout()
        users_hdr.setContentsMargins(2, 0, 2, 2)
        users_title = QLabel("Users")
        users_title.setObjectName("usrSectionTitle")
        users_hint = QLabel("Manage accounts, roles, and weekly availability")
        users_hint.setObjectName("usrSectionHint")
        users_hdr_col = QVBoxLayout()
        users_hdr_col.setSpacing(0)
        users_hdr_col.addWidget(users_title)
        users_hdr_col.addWidget(users_hint)
        users_hdr.addLayout(users_hdr_col)
        users_hdr.addStretch()
        table_vbox.addLayout(users_hdr)

        self.users_table = QTableWidget(0, 7)
        self.users_table.setObjectName("usrUsersTable")
        self.users_table.setHorizontalHeaderLabels([
            "Name", "Username", "Contact", "Availability Time", "Availability Days", "Role", "Status"
        ])
        self.users_table.setColumnCount(7)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setShowGrid(True)
        self.users_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_table.customContextMenuRequested.connect(self._open_user_context_menu)
        self.users_table.itemSelectionChanged.connect(self._sync_status_action_labels)
        self.users_table.cellDoubleClicked.connect(self._edit_availability_from_cell)
        self.users_table.horizontalHeader().setStretchLastSection(False)
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.users_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.users_table.setColumnWidth(1, 140)
        self.users_table.setColumnWidth(3, 165)
        self.users_table.setMinimumHeight(200)
        table_vbox.addWidget(self.users_table)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.change_role_btn = QPushButton("Change Role")
        self.change_role_btn.setObjectName("neutralBtn")
        self.change_role_btn.clicked.connect(self.change_selected_role)
        self.toggle_active_btn = QPushButton("Set Active/Inactive")
        self.toggle_active_btn.setObjectName("neutralBtn")
        self.toggle_active_btn.clicked.connect(self.toggle_selected_user_status)
        self.reset_pw_btn = QPushButton("Reset Password")
        self.reset_pw_btn.setObjectName("warningBtn")
        self.reset_pw_btn.clicked.connect(self.reset_selected_password)
        self.delete_btn = QPushButton("Delete User")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self.delete_user)
        action_row.addWidget(self.change_role_btn)
        action_row.addWidget(self.toggle_active_btn)
        action_row.addWidget(self.reset_pw_btn)
        action_row.addWidget(self.delete_btn)
        table_vbox.addLayout(action_row)

        # Activity log card
        self._usr_log_group = QGroupBox("Activity Log")
        log_vbox = QVBoxLayout(self._usr_log_group)
        log_hdr = QHBoxLayout()
        log_hdr.setContentsMargins(2, 0, 2, 2)
        log_title = QLabel("Activity Log")
        log_title.setObjectName("usrSectionTitle")
        log_hint = QLabel("Latest admin, account, and clinical audit events")
        log_hint.setObjectName("usrSectionHint")
        log_hdr_col = QVBoxLayout()
        log_hdr_col.setSpacing(0)
        log_hdr_col.addWidget(log_title)
        log_hdr_col.addWidget(log_hint)
        log_hdr.addLayout(log_hdr_col)
        log_hdr.addStretch()
        log_vbox.addLayout(log_hdr)

        self.activity_log = QTableWidget(0, 3)
        self.activity_log.setObjectName("usrActivityTable")
        self.activity_log.setHorizontalHeaderLabels(["Username", "Action", "Date-Time"])
        self.activity_log.setSelectionMode(QAbstractItemView.NoSelection)
        self.activity_log.setEditTriggers(QTableWidget.NoEditTriggers)
        self.activity_log.verticalHeader().setVisible(False)
        self.activity_log.setShowGrid(False)
        self.activity_log.horizontalHeader().setStretchLastSection(False)
        self.activity_log.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.activity_log.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.activity_log.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.activity_log.setColumnWidth(1, 190)
        self.activity_log.setColumnWidth(2, 165)
        self.activity_log.setMinimumHeight(175)
        self.activity_log.setSortingEnabled(True)
        log_vbox.addWidget(self.activity_log)

        self.admin_tabs = QTabWidget()
        self.admin_tabs.setObjectName("usrAdminTabs")

        users_tab = QWidget()
        users_tab_layout = QVBoxLayout(users_tab)
        users_tab_layout.setContentsMargins(8, 8, 8, 8)
        users_tab_layout.setSpacing(0)
        users_tab_layout.addWidget(self._usr_table_group)

        activity_tab = QWidget()
        activity_tab_layout = QVBoxLayout(activity_tab)
        activity_tab_layout.setContentsMargins(8, 8, 8, 8)
        activity_tab_layout.setSpacing(0)
        activity_tab_layout.addWidget(self._usr_log_group)

        self.admin_tabs.addTab(users_tab, "Users")
        self.admin_tabs.addTab(activity_tab, "Activity Log")
        self.admin_tabs.currentChanged.connect(self._handle_admin_tab_change)
        main_layout.addWidget(self.admin_tabs, 1)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusBar")
        self.status_label.setStyleSheet("color:#6c757d;font-size:12px;padding:2px 0;")
        main_layout.addWidget(self.status_label)

        self.refresh_users()
        self.load_activity_log()

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _open_new_user_dialog(self):
        NewUserDialog(parent=self).exec()

    def _handle_admin_tab_change(self, index: int):
        if index == 1:
            self.load_activity_log()

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
        edit_availability_action = menu.addAction("Edit Availability")
        menu.addSeparator()
        change_role_action = menu.addAction("Change Role")
        toggle_active_action = menu.addAction(self._status_action_text_for_selected_row())
        reset_password_action = menu.addAction("Reset Password")
        menu.addSeparator()
        delete_action = menu.addAction("Delete User")

        chosen = menu.exec(self.users_table.viewport().mapToGlobal(pos))
        if chosen == edit_availability_action:
            self.edit_selected_availability()
        elif chosen == change_role_action:
            self.change_selected_role()
        elif chosen == toggle_active_action:
            self.toggle_selected_user_status()
        elif chosen == reset_password_action:
            self.reset_selected_password()
        elif chosen == delete_action:
            self.delete_user()

    def _status_action_text_for_selected_row(self) -> str:
        row = self.users_table.currentRow()
        if row < 0:
            return "Set Active/Inactive"
        status_item = self.users_table.item(row, 6)
        if not status_item:
            return "Set Active/Inactive"
        is_active = bool(status_item.data(Qt.UserRole))
        return "Set Inactive" if is_active else "Set Active"

    def _sync_status_action_labels(self):
        if hasattr(self, "toggle_active_btn"):
            self.toggle_active_btn.setText(self._status_action_text_for_selected_row())

    def _edit_availability_from_cell(self, row, column):
        if column in (3, 4):
            self.users_table.selectRow(row)
            self.edit_selected_availability()

    def _get_user_by_username(self, username: str):
        target = str(username or "").strip().lower()
        for user in user_store.get_all_users():
            if str(user.get("username") or "").strip().lower() == target:
                return user
        return None

    def edit_selected_availability(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to edit availability.")
            return

        username_item = self.users_table.item(row, 1)
        if not username_item:
            return
        username = username_item.text().strip()

        user = self._get_user_by_username(username)
        if not user:
            QMessageBox.warning(self, "User Not Found", "Unable to load selected user details.")
            return

        initial_payload = None
        raw_availability = user.get("availability_json")
        if raw_availability:
            try:
                initial_payload = json.loads(raw_availability) if isinstance(raw_availability, str) else raw_availability
            except Exception:
                initial_payload = None

        dialog = AvailabilityDialog(self, initial_availability=initial_payload)
        dialog.setWindowTitle(f"Edit Availability - {username}")
        if dialog.exec() != QDialog.Accepted:
            return

        availability_json = "" if dialog.skip_selected else dialog.get_availability_json()
        acting_username, acting_role = self._actor_context()
        success = user_store.update_user_availability(
            username,
            availability_json,
            acting_username=acting_username,
            acting_role=acting_role,
        )
        if not success:
            QMessageBox.warning(self, "Update Failed", f"Could not update availability for '{username}'.")
            return

        self._set_status(f"Availability updated for '{username}'")
        self.log_activity(username, "Availability Updated")
        if hasattr(self, "show_notification"):
            self.show_notification(f"Schedule updated for {username}.")
        self.refresh_users()

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
            contact_item = QTableWidgetItem(str(user.get("contact") or ""))
            contact_item.setFlags(contact_item.flags() & ~Qt.ItemIsEditable)

            availability_time_text = "Not set"
            availability_days_text = "Not set"
            raw_availability = user.get("availability_json")
            if raw_availability:
                try:
                    payload = json.loads(raw_availability) if isinstance(raw_availability, str) else raw_availability
                except Exception:
                    payload = {}

                if isinstance(payload, dict):
                    start_time = str(payload.get("start_time") or "").strip()
                    end_time = str(payload.get("end_time") or "").strip()
                    if start_time and end_time:
                        parsed_start = AvailabilityDialog._parse_time_value(start_time)
                        parsed_end = AvailabilityDialog._parse_time_value(end_time)
                        if parsed_start.isValid() and parsed_end.isValid():
                            availability_time_text = (
                                f"{parsed_start.toString('hh:mm AP')} - {parsed_end.toString('hh:mm AP')}"
                            )
                        else:
                            availability_time_text = f"{start_time} - {end_time}"

                    selected_days = payload.get("days") or []

                    # Backward compatibility with older payloads that stored concrete dates.
                    if not selected_days:
                        legacy_dates = payload.get("dates") or []
                        if isinstance(legacy_dates, list):
                            derived = []
                            for date_value in legacy_dates:
                                try:
                                    derived.append(datetime.strptime(str(date_value), "%Y-%m-%d").date().strftime("%a").lower())
                                except Exception:
                                    pass
                            selected_days = derived

                    if isinstance(selected_days, list) and selected_days:
                        ordered = []
                        for day_key, _ in _WEEKDAY_OPTIONS:
                            if any(str(value).strip().lower() == day_key for value in selected_days):
                                ordered.append(_WEEKDAY_LABELS[day_key][:3])
                        if ordered:
                            availability_days_text = ", ".join(ordered)

            availability_time_item = QTableWidgetItem(availability_time_text)
            availability_time_item.setFlags(availability_time_item.flags() & ~Qt.ItemIsEditable)
            availability_days_item = QTableWidgetItem(availability_days_text)
            availability_days_item.setFlags(availability_days_item.flags() & ~Qt.ItemIsEditable)

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

            is_active = bool(user.get("is_active", True))
            status_text = "Active" if is_active else "Inactive"
            status_item = QTableWidgetItem(f"  {status_text}  ")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setData(Qt.UserRole, is_active)
            if is_active:
                status_item.setForeground(QColor("#166534"))
                status_item.setBackground(QColor("#dcfce7"))
            else:
                status_item.setForeground(QColor("#991b1b"))
                status_item.setBackground(QColor("#fee2e2"))

            self.users_table.setItem(row, 0, name_item)
            self.users_table.setItem(row, 1, username_item)
            self.users_table.setItem(row, 2, contact_item)
            self.users_table.setItem(row, 3, availability_time_item)
            self.users_table.setItem(row, 4, availability_days_item)
            self.users_table.setItem(row, 5, role_item)
            self.users_table.setItem(row, 6, status_item)
        self.users_table.resizeRowsToContents()
        self._sync_status_action_labels()
        if hasattr(self, "activity_log"):
            self.load_activity_log()

    # â”€â”€ CRUD Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def delete_user(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to delete.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 5)
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
            self.log_activity(username, "Account Deleted")
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
        role_item = self.users_table.item(row, 5)
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
            self.log_activity(username, f"Role Changed ({new_role})")
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
            self.log_activity(username, "Password Reset")
            QMessageBox.information(
                self, "Password Reset",
                f"Password for '{username}' was successfully reset.",
            )
        else:
            self._set_status(f"Failed to reset password for '{username}'", ok=False)
            QMessageBox.warning(self, "Reset Failed", f"Could not reset password for '{username}'.")

    def toggle_selected_user_status(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user first.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 5)
        status_item = self.users_table.item(row, 6)
        if not username_item or not role_item or not status_item:
            return

        username = username_item.text().strip()
        role = str(role_item.data(Qt.UserRole) or "").strip().lower()
        is_active = bool(status_item.data(Qt.UserRole))
        target_state = not is_active
        target_text = "active" if target_state else "inactive"

        current_username, current_role = self._actor_context()
        if role == "admin" and not target_state and username == current_username:
            QMessageBox.warning(self, "Not Allowed", "You cannot deactivate your own admin account.")
            return

        proceed = QMessageBox.question(
            self,
            "Confirm Status Change",
            f"Set '<b>{username}</b>' as <b>{target_text}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(self, f"set '{username}' as {target_text}")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        success = user_store.update_user_active_status(
            username,
            target_state,
            acting_username=current_username,
            acting_role=current_role,
        )
        if success:
            self._set_status(f"Status updated: {username} → {target_text}")
            self.log_activity(username, f"Status Changed ({target_text})")
            self.refresh_users()
            QMessageBox.information(self, "Status Updated", f"'{username}' is now {target_text}.")
        else:
            self._set_status(f"Failed to update status for '{username}'", ok=False)
            QMessageBox.warning(self, "Update Failed", f"Could not update status for '{username}'.")

    def log_activity(self, user, action):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_store.log_activity(user, action, timestamp)
        self.load_activity_log()

    @staticmethod
    def _format_activity_action(action: str) -> str:
        text = str(action or "").strip()
        if not text:
            return "Unknown"
        lowered = text.lower()
        if lowered == "login":
            return "Login"
        if lowered == "logout":
            return "Logout"
        if lowered == "deleted":
            return "Account Deleted"
        if lowered == "password reset":
            return "Password Reset"
        if lowered == "availability updated":
            return "Availability Updated"
        if lowered == "profile updated":
            return "Profile Updated"
        if lowered.startswith("created as "):
            role = text[11:].strip()
            return f"Account Created ({role})" if role else "Account Created"
        if lowered.startswith("role changed to "):
            role = text[16:].strip()
            return f"Role Changed ({role})" if role else "Role Changed"
        if lowered.startswith("report_generated"):
            return "Report PDF Generated"
        if lowered.startswith("referral_generated"):
            return "Referral PDF Generated"
        if lowered.startswith("rescreen_allowed"):
            return "Rescreen Allowed"
        if lowered.startswith("rescreen_blocked"):
            return "Rescreen Blocked"
        return text

    def load_activity_log(self):
        entries = user_store.get_recent_activity(limit=300)
        self.activity_log.setSortingEnabled(False)
        self.activity_log.setRowCount(0)
        for entry in entries:
            row = self.activity_log.rowCount()
            self.activity_log.insertRow(row)

            username = str(entry.get("username") or "").strip()
            action = self._format_activity_action(entry.get("action"))
            timestamp = str(entry.get("time") or "").strip()

            username_item = QTableWidgetItem(username)
            action_item = QTableWidgetItem(action)
            time_item = QTableWidgetItem(timestamp)

            username_item.setFlags(username_item.flags() & ~Qt.ItemIsEditable)
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)

            self.activity_log.setItem(row, 0, username_item)
            self.activity_log.setItem(row, 1, action_item)
            self.activity_log.setItem(row, 2, time_item)

        self.activity_log.setSortingEnabled(True)
        self.activity_log.sortItems(2, Qt.DescendingOrder)

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._usr_title_lbl.setText(pack["usr_title"])
        self._usr_table_group.setTitle(pack["usr_table"])
        self._usr_log_group.setTitle(pack["usr_log"])
        if hasattr(self, "admin_tabs"):
            self.admin_tabs.setTabText(0, pack["usr_table"])
            self.admin_tabs.setTabText(1, pack["usr_log"])

