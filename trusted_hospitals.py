import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QHeaderView,
)

from auth import UserManager
import user_store


class ReferralHospitalDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.setWindowTitle("Trusted Referral")
        self.setModal(True)
        self.setMinimumWidth(520)

        self._item = item or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Add Hospital / Clinic")
        title.setObjectName("headerTitle")
        layout.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)

        self.hospital_name_label = QLabel("Hospital Name")
        self.hospital_name_label.setObjectName("fieldLabel")
        self.hospital_name_input = QLineEdit()
        self.hospital_name_input.setPlaceholderText("e.g., St. Mary's Medical Center")
        form.addWidget(self.hospital_name_label, 0, 0)
        form.addWidget(self.hospital_name_input, 1, 0)

        self.department_label = QLabel("Department")
        self.department_label.setObjectName("fieldLabel")
        self.department_input = QLineEdit()
        self.department_input.setPlaceholderText("e.g., Ophthalmology Department")
        form.addWidget(self.department_label, 0, 1)
        form.addWidget(self.department_input, 1, 1)

        self.contact_label = QLabel("Contact Person (optional)")
        self.contact_label.setObjectName("fieldLabel")
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Optional")
        form.addWidget(self.contact_label, 2, 0)
        form.addWidget(self.contact_input, 3, 0)

        self.phone_label = QLabel("Phone (optional)")
        self.phone_label.setObjectName("fieldLabel")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Optional")
        form.addWidget(self.phone_label, 2, 1)
        form.addWidget(self.phone_input, 3, 1)

        self.email_label = QLabel("Email (optional)")
        self.email_label.setObjectName("fieldLabel")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Optional")
        form.addWidget(self.email_label, 4, 0)
        form.addWidget(self.email_input, 5, 0)

        self.address_label = QLabel("Address")
        self.address_label.setObjectName("fieldLabel")
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("City / complete address")
        form.addWidget(self.address_label, 4, 1)
        form.addWidget(self.address_input, 5, 1)

        layout.addLayout(form)

        flags_row = QHBoxLayout()
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)
        self.default_check = QCheckBox("Set as default")
        flags_row.addWidget(self.active_check)
        flags_row.addWidget(self.default_check)
        flags_row.addStretch(1)
        layout.addLayout(flags_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryAction")
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self.hospital_name_input.setText(str(self._item.get("hospital_name") or ""))
        self.department_input.setText(str(self._item.get("department") or ""))
        self.contact_input.setText(str(self._item.get("contact_person") or ""))
        self.phone_input.setText(str(self._item.get("phone") or ""))
        self.email_input.setText(str(self._item.get("email") or ""))
        self.address_input.setText(str(self._item.get("address") or ""))
        self.active_check.setChecked(bool(self._item.get("is_active", True)))
        self.default_check.setChecked(bool(self._item.get("is_default", False)))

        self.hospital_name_input.returnPressed.connect(self.accept)

    def values(self) -> dict:
        return {
            "hospital_name": self.hospital_name_input.text().strip(),
            "department": self.department_input.text().strip(),
            "contact_person": self.contact_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "address": self.address_input.text().strip(),
            "is_active": self.active_check.isChecked(),
            "is_default": self.default_check.isChecked(),
        }


class TrustedHospitalsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            """
            QWidget {
                background: #ffffff;
                color: #1a1a1a;
                font-size: 13px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-weight: 400;
            }
            QFrame#trustedHero {
                background: #ffffff;
                border: 1px solid #dbeafe;
                border-radius: 12px;
            }
            QLabel#headerTitle {
                color: #1d4ed8;
                font-size: 20px;
                font-weight: 400;
                background: transparent;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #dbeafe;
                border-radius: 12px;
                margin-top: 8px;
                font-weight: 400;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                background: #ffffff;
                color: #1d4ed8;
                font-size: 12px;
                font-weight: 400;
                letter-spacing: 0.5px;
            }
            QLabel#fieldLabel {
                color: #6b7280;
                font-size: 12px;
                font-weight: 400;
                letter-spacing: 0.5px;
            }
            QLabel#metaLabel {
                color: #6b7280;
                font-size: 13px;
                font-weight: 400;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 8px 10px;
                min-height: 22px;
            }
            QLineEdit:hover {
                border: 1px solid #60a5fa;
            }
            QLineEdit:focus {
                border: 1px solid #60a5fa;
            }
            QPushButton {
                background: #ffffff;
                color: #1a1a1a;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 7px 12px;
                font-weight: 400;
            }
            QPushButton:hover {
                background: #eff6ff;
            }
            QPushButton#primaryAction {
                background: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                font-weight: 400;
            }
            QPushButton#primaryAction:hover {
                background: #1d4ed8;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #dbeafe;
                border-radius: 10px;
                gridline-color: transparent;
            }
            QHeaderView::section {
                background: #ffffff;
                color: #1d4ed8;
                border: none;
                border-bottom: 1px solid #dbeafe;
                font-size: 12px;
                font-weight: 400;
                padding: 10px 16px;
            }
            QCheckBox {
                spacing: 8px;
                color: #1a1a1a;
                background: transparent;
                font-size: 13px;
                font-weight: 400;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border: 1px solid #1d4ed8;
            }
            QLabel#statusLabel {
                color: #6b7280;
                font-size: 12px;
                font-weight: 400;
                padding: 2px 0;
                border: none;
                background: transparent;
            }
            QPushButton#ghostAction {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                color: #1a1a1a;
                font-weight: 400;
                padding: 8px 12px;
            }
            QPushButton#ghostAction:hover {
                background: #eff6ff;
            }
            """
        )

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addStretch(1)

        page_container = QWidget()
        page_container.setMinimumWidth(1200)
        page_container.setMaximumWidth(1200)
        root_layout.addWidget(page_container)
        root_layout.addStretch(1)

        root = QVBoxLayout(page_container)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("trustedHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(12, 10, 12, 10)
        hero_layout.setSpacing(2)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("Trusted Referrals")
        title.setObjectName("headerTitle")
        title_col.addWidget(title)
        header_row.addLayout(title_col)
        header_row.addStretch(1)
        self.add_btn = QPushButton("+ Add Hospital / Clinic")
        self.add_btn.setObjectName("ghostAction")
        self.add_btn.clicked.connect(self._add_referral_hospital)
        header_row.addWidget(self.add_btn)
        hero_layout.addLayout(header_row)
        root.addWidget(hero)

        self.referral_hospitals_group = QGroupBox("Hospitals / Clinics")
        referral_layout = QVBoxLayout(self.referral_hospitals_group)
        referral_layout.setSpacing(6)

        self.referral_hospitals_table = QTableWidget(0, 4)
        self.referral_hospitals_table.setHorizontalHeaderLabels(["Hospital / Clinic", "Department", "Contact", "Status"])
        self.referral_hospitals_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.referral_hospitals_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.referral_hospitals_table.setSelectionMode(QTableWidget.SingleSelection)
        self.referral_hospitals_table.verticalHeader().setVisible(False)
        self.referral_hospitals_table.setShowGrid(False)
        self.referral_hospitals_table.setAlternatingRowColors(False)
        self.referral_hospitals_table.horizontalHeader().setStretchLastSection(False)
        self.referral_hospitals_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.referral_hospitals_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.referral_hospitals_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.referral_hospitals_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.referral_hospitals_table.horizontalHeader().setMinimumSectionSize(90)
        self.referral_hospitals_table.setWordWrap(True)
        self.referral_hospitals_table.itemSelectionChanged.connect(self._sync_referral_action_buttons)
        self.referral_hospitals_table.itemDoubleClicked.connect(self._edit_selected_referral_hospital)
        self.referral_hospitals_table.setMinimumHeight(200)
        self.referral_hospitals_table.setSortingEnabled(False)
        referral_layout.addWidget(self.referral_hospitals_table)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_selected_referral_hospital)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected_referral_hospital)
        action_row.addWidget(self.edit_btn)
        action_row.addWidget(self.delete_btn)
        referral_layout.addLayout(action_row)

        root.addWidget(self.referral_hospitals_group)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)
        root.addStretch(1)

        self._referral_hospital_rows = []
        self._referral_hospital_lookup = {}
        self._sync_referral_action_buttons()

        self._configure_referral_hospitals_section()

    def _active_role(self) -> str:
        main_window = self.window()
        role = getattr(main_window, "role", None) if main_window is not self else None
        return str(role or os.environ.get("EYESHIELD_CURRENT_ROLE") or "").strip().lower()

    def _active_username(self) -> str:
        main_window = self.window()
        username = getattr(main_window, "username", None) if main_window is not self else None
        return str(username or os.environ.get("EYESHIELD_CURRENT_USER") or "").strip()

    def _configure_referral_hospitals_section(self):
        show_referrals = self._active_role() == "admin"
        self.referral_hospitals_group.setVisible(show_referrals)
        if not show_referrals:
            self.status_label.setText("Trusted referrals are managed by admin users.")
            return
        if not UserManager.ensure_referral_hospitals_table():
            self.status_label.setText("Unable to prepare trusted referral list")
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
            
            # Apply alternating row background colors for better readability (matching activity log style)
            bg_color = QColor("#ffffff") if row_index % 2 == 0 else QColor("#f3f4f6")
            for col in range(4):
                item_widget = self.referral_hospitals_table.item(row_index, col)
                if item_widget:
                    item_widget.setBackground(bg_color)
        self._sync_referral_action_buttons()

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

    def _add_referral_hospital(self):
        self._open_referral_dialog()

    def _edit_selected_referral_hospital(self, *_args):
        item = self._selected_referral_hospital()
        if not item:
            return
        self._open_referral_dialog(item)

    def _delete_selected_referral_hospital(self):
        if self._active_role() != "admin":
            QMessageBox.warning(self, "Trusted Referrals", "Only admins can manage trusted referrals.")
            return

        item = self._selected_referral_hospital()
        if not item:
            QMessageBox.information(self, "Trusted Referrals", "Select a hospital or clinic first.")
            return

        hospital_label = str(item.get("hospital_name") or "this hospital")
        reply = QMessageBox.question(
            self,
            "Delete Trusted Referral",
            f"Delete {hospital_label} from the trusted referral list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, message = UserManager.delete_referral_hospital(int(item.get("id") or 0))
        if not ok:
            QMessageBox.warning(self, "Trusted Referrals", message)
            return

        self._log_referral_audit(
            "TRUSTED_REFERRAL_DELETED",
            f"Deleted trusted referral: {hospital_label}",
            item,
        )

        self._reload_referral_hospitals()
        self.status_label.setText(f"Removed: {hospital_label}")

    def _sync_referral_action_buttons(self):
        has_selection = self._selected_referral_hospital() is not None
        is_admin = self._active_role() == "admin"
        if hasattr(self, "edit_btn"):
            self.edit_btn.setEnabled(has_selection and is_admin)
        if hasattr(self, "delete_btn"):
            self.delete_btn.setEnabled(has_selection and is_admin)

    def _log_referral_audit(self, event_type: str, action_text: str, item: dict | None = None):
        metadata = {}
        if isinstance(item, dict):
            metadata = {
                "hospital_id": str(item.get("id") or ""),
                "hospital_name": str(item.get("hospital_name") or ""),
                "department": str(item.get("department") or ""),
                "contact_person": str(item.get("contact_person") or ""),
                "status": "active" if item.get("is_active") else "inactive",
                "default": str(bool(item.get("is_default"))),
            }
        user_store.log_activity_event(
            self._active_username(),
            event_type,
            metadata=metadata,
            action_text=action_text,
        )

    def _open_referral_dialog(self, item=None):
        if self._active_role() != "admin":
            QMessageBox.warning(self, "Trusted Referrals", "Only admins can manage trusted referrals.")
            return

        dialog = ReferralHospitalDialog(self, item=item)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        hospital_name = values["hospital_name"]
        if not hospital_name:
            QMessageBox.warning(self, "Validation Error", "Please enter a hospital name.")
            return

        if not values["department"]:
            QMessageBox.warning(self, "Validation Error", "Please enter a department.")
            return

        if not values["address"]:
            QMessageBox.warning(self, "Validation Error", "Please enter an address.")
            return

        selected_id = int(item.get("id") or 0) if item else None
        ok, message, hospital_id = UserManager.upsert_referral_hospital(
            hospital_name=hospital_name,
            department=values["department"],
            contact_person=values["contact_person"],
            phone=values["phone"],
            email=values["email"],
            address=values["address"],
            is_active=values["is_active"],
            is_default=values["is_default"],
            hospital_id=selected_id,
        )
        if not ok:
            QMessageBox.warning(self, "Trusted Referrals", message)
            return

        self._reload_referral_hospitals()
        action_label = "Updated" if selected_id else "Added"
        event_type = "TRUSTED_REFERRAL_UPDATED" if selected_id else "TRUSTED_REFERRAL_ADDED"
        
        # Build audit item with new hospital data
        audit_item = {
            "id": hospital_id,
            "hospital_name": hospital_name,
            "department": values.get("department", ""),
            "contact_person": values.get("contact_person", ""),
            "is_active": values.get("is_active", True),
            "is_default": values.get("is_default", False),
        }
        self._log_referral_audit(event_type, f"{action_label} trusted referral: {hospital_name}", item=audit_item)
        self.status_label.setText(f"{action_label}: {hospital_name}")
        QMessageBox.information(self, "Trusted Referrals", f"{action_label} successfully: {hospital_name}")

        if hospital_id:
            for row_idx in range(self.referral_hospitals_table.rowCount()):
                id_item = self.referral_hospitals_table.item(row_idx, 0)
                if not id_item:
                    continue
                found_id = int(id_item.data(Qt.UserRole) or 0)
                if found_id != int(hospital_id):
                    continue
                self.referral_hospitals_table.selectRow(row_idx)
                break
