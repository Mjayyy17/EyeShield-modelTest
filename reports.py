"""
Reports module for EyeShield EMR application.
Provides offline summary analytics from local patient_records data.
"""

import csv
import json
from html import escape
import os
from pathlib import Path
import sqlite3
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QHeaderView,
    QFileDialog, QDialog, QMessageBox, QMenu, QScrollArea,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap

from auth import DB_FILE, UserManager


class PatientDetailsDialog(QDialog):
    """Read-only dialog displaying full patient screening details without fundus image."""

    def __init__(self, patient_record: dict, parent=None):
        super().__init__(parent)
        self.record = patient_record
        self.setWindowTitle(f"Patient Details - {patient_record.get('name', 'Unknown')}")
        self.resize(700, 700)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel(f"{patient_record.get('name', 'N/A')}")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#1f4f77;")
        layout.addWidget(title)

        # Create scrollable content area
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Helper function to create field rows
        def add_field(label_text: str, value_text: str):
            row = QHBoxLayout()
            row.setSpacing(12)
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-weight:600;color:#3f7ca7;min-width:150px;")
            value = QLabel(value_text)
            value.setStyleSheet("color:#475569;word-wrap:on;")
            value.setWordWrap(True)
            row.addWidget(label)
            row.addWidget(value, 1)
            content_layout.addLayout(row)
        
        def add_section(section_title: str):
            sep = QLabel(section_title.upper())
            sep.setStyleSheet("font-size:12px;font-weight:700;color:#3f7ca7;margin-top:8px;letter-spacing:1px;")
            content_layout.addWidget(sep)
        
        # Patient Information Section
        add_section("Patient Information")
        add_field("Patient ID", str(patient_record.get("patient_id") or "N/A"))
        add_field("Name", str(patient_record.get("name") or "N/A"))
        add_field("Age", str(patient_record.get("age") or "N/A"))
        add_field("Date of Birth", str(patient_record.get("birthdate") or "N/A"))
        add_field("Sex", str(patient_record.get("sex") or "N/A"))
        add_field("Contact", str(patient_record.get("contact") or "N/A"))
        add_field("Eye Screened", str(patient_record.get("eyes") or "N/A"))
        
        # Vital Signs Section
        add_section("Vital Signs & Measurements")
        add_field("Height", str(patient_record.get("height") or "N/A") + (" cm" if patient_record.get("height") else ""))
        add_field("Weight", str(patient_record.get("weight") or "N/A") + (" kg" if patient_record.get("weight") else ""))
        add_field("BMI", str(patient_record.get("bmi") or "N/A"))
        add_field("Visual Acuity - Left", str(patient_record.get("visual_acuity_left") or "N/A"))
        add_field("Visual Acuity - Right", str(patient_record.get("visual_acuity_right") or "N/A"))
        
        bp_sys = patient_record.get("blood_pressure_systolic") or "—"
        bp_dia = patient_record.get("blood_pressure_diastolic") or "—"
        add_field("Blood Pressure", f"{bp_sys}/{bp_dia} mmHg")
        
        fbs = patient_record.get("fasting_blood_sugar") or "N/A"
        rbs = patient_record.get("random_blood_sugar") or "N/A"
        add_field("Blood Glucose (FBS/RBS)", f"{fbs} / {rbs} mg/dL")
        
        # Symptoms Section
        add_section("Symptoms")
        symptoms = []
        if patient_record.get("symptom_blurred_vision") == "True":
            symptoms.append("Blurred vision")
        if patient_record.get("symptom_floaters") == "True":
            symptoms.append("Floaters")
        if patient_record.get("symptom_flashes") == "True":
            symptoms.append("Flashes")
        if patient_record.get("symptom_vision_loss") == "True":
            symptoms.append("Vision loss")
        symptom_text = ", ".join(symptoms) if symptoms else "None reported"
        add_field("Reported Symptoms", symptom_text)
        
        # Clinical History Section
        add_section("Clinical History")
        add_field("Diabetes Type", str(patient_record.get("diabetes_type") or "N/A"))
        add_field("Diagnosis Date", str(patient_record.get("diabetes_diagnosis_date") or "N/A"))
        add_field("Duration", str(patient_record.get("duration") or "N/A"))
        add_field("HbA1c", str(patient_record.get("hba1c") or "N/A") + ("%" if patient_record.get("hba1c") else ""))
        add_field("Treatment Regimen", str(patient_record.get("treatment_regimen") or "N/A"))
        add_field("Previous DR Stage", str(patient_record.get("prev_dr_stage") or "N/A"))
        prev_treatment = "Yes" if patient_record.get("prev_treatment") == "True" else "No"
        add_field("Previous DR Treatment", prev_treatment)
        
        # Screening Result Section
        add_section("Screening Result")
        add_field("AI Classification", str(patient_record.get("ai_classification") or patient_record.get("result") or "N/A"))
        add_field("Doctor Classification", str(patient_record.get("doctor_classification") or patient_record.get("result") or "N/A"))
        add_field("Final Diagnosis", "Based on ICDR Severity Scale")
        add_field("Decision Mode", str(patient_record.get("decision_mode") or "accepted").title())
        findings_text = str(patient_record.get("doctor_findings") or "").strip()
        if findings_text:
            add_field("Doctor Findings", findings_text)
        override_reason = str(patient_record.get("override_justification") or "").strip()
        if override_reason:
            add_field("Override Justification", override_reason)
        add_field("Confidence", str(patient_record.get("confidence") or "N/A"))
        add_field("Screened At", str(patient_record.get("screened_at") or "N/A"))
        add_field("Screened By", str(patient_record.get("original_screener_name") or patient_record.get("original_screener_username") or "N/A"))
        
        # Clinical Notes Section
        notes = patient_record.get("notes") or ""
        if notes and notes.strip():
            add_section("Clinical Notes")
            notes_label = QLabel(str(notes))
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("color:#475569;background:#f6f8fb;border:1px solid #d3dae3;border-radius:6px;padding:10px;")
            content_layout.addWidget(notes_label)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet(
            "QPushButton{background:#1f6fe5;color:#ffffff;border:1px solid #1a5fc4;border-radius:6px;}"
            "QPushButton:hover{background:#1b63cf;}"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setStyleSheet("QDialog{background:#ffffff;}")


class ReferralDetailDialog(QDialog):
    """Dialog displaying referred patient details WITH fundus image for review."""

    def __init__(self, patient_record: dict, parent=None):
        super().__init__(parent)
        self.record = patient_record
        self.setWindowTitle(f"Referral Review - {patient_record.get('name', 'Unknown')}")
        self.resize(1000, 700)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Left side: Patient Details (scrollable)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(left_scroll.Shape.NoFrame)
        left_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        left_scroll.setMaximumWidth(400)

        left_content = QWidget()
        left_content.setStyleSheet("background:transparent;")
        left_layout = QVBoxLayout(left_content)
        left_layout.setSpacing(14)
        left_layout.setContentsMargins(0, 0, 0, 0)

        def add_field(label_text: str, value_text: str):
            row = QHBoxLayout()
            row.setSpacing(12)
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-weight:600;color:#3f7ca7;min-width:120px;")
            value = QLabel(value_text)
            value.setStyleSheet("color:#475569;word-wrap:on;")
            value.setWordWrap(True)
            row.addWidget(label)
            row.addWidget(value, 1)
            left_layout.addLayout(row)

        def add_section(section_title: str):
            sep = QLabel(section_title.upper())
            sep.setStyleSheet("font-size:11px;font-weight:700;color:#3f7ca7;margin-top:6px;letter-spacing:0.8px;")
            left_layout.addWidget(sep)

        add_section("Patient Information")
        add_field("Patient ID", str(patient_record.get("patient_id") or "N/A"))
        add_field("Name", str(patient_record.get("name") or "N/A"))
        add_field("Age", str(patient_record.get("age") or "N/A"))
        add_field("Sex", str(patient_record.get("sex") or "N/A"))

        add_section("Vital Signs")
        add_field("Height", str(patient_record.get("height") or "N/A") + (" cm" if patient_record.get("height") else ""))
        add_field("Weight", str(patient_record.get("weight") or "N/A") + (" kg" if patient_record.get("weight") else ""))
        add_field("BMI", str(patient_record.get("bmi") or "N/A"))

        bp_sys = patient_record.get("blood_pressure_systolic") or "-"
        bp_dia = patient_record.get("blood_pressure_diastolic") or "-"
        add_field("Blood Pressure", f"{bp_sys}/{bp_dia} mmHg")

        add_section("Clinical History")
        add_field("Diabetes Type", str(patient_record.get("diabetes_type") or "N/A"))
        add_field("HbA1c", str(patient_record.get("hba1c") or "N/A") + ("%" if patient_record.get("hba1c") else ""))
        add_field("Treatment", str(patient_record.get("treatment_regimen") or "N/A"))
        add_field("Previous DR", str(patient_record.get("prev_dr_stage") or "N/A"))

        add_section("Screening Result")
        add_field("AI Classification", str(patient_record.get("ai_classification") or patient_record.get("result") or "N/A"))
        add_field("Doctor Classification", str(patient_record.get("doctor_classification") or patient_record.get("result") or "N/A"))
        add_field("Final Diagnosis", "Based on ICDR Severity Scale")
        add_field("Decision Mode", str(patient_record.get("decision_mode") or "accepted").title())
        findings_text = str(patient_record.get("doctor_findings") or "").strip()
        if findings_text:
            add_field("Doctor Findings", findings_text)
        override_reason = str(patient_record.get("override_justification") or "").strip()
        if override_reason:
            add_field("Override Justification", override_reason)
        add_field("Confidence", str(patient_record.get("confidence") or "N/A"))
        add_field("Screened By", str(patient_record.get("original_screener_name") or patient_record.get("original_screener_username") or "N/A"))
        add_field("Screened At", str(patient_record.get("screened_at") or "N/A"))

        left_layout.addStretch()
        left_scroll.setWidget(left_content)
        layout.addWidget(left_scroll)

        # Right side: Fundus Image
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(0, 0, 0, 0)

        image_title = QLabel("FUNDUS IMAGE")
        image_title.setStyleSheet("font-size:11px;font-weight:700;color:#3f7ca7;letter-spacing:0.8px;")
        right_layout.addWidget(image_title)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("border:1px solid #d3dae3;border-radius:6px;background:#f6f8fb;")
        image_label.setMinimumSize(500, 500)

        source_image = patient_record.get("source_image_path") or ""
        if source_image and os.path.isfile(source_image):
            try:
                pixmap = QPixmap(source_image)
                if not pixmap.isNull():
                    scaled = pixmap.scaledToHeight(500, Qt.SmoothTransformation)
                    image_label.setPixmap(scaled)
                else:
                    image_label.setText("Image could not be loaded")
            except Exception:
                image_label.setText("Error loading image")
        else:
            image_label.setText("No fundus image available")

        right_layout.addWidget(image_label, 1)

        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet(
            "QPushButton{background:#1f6fe5;color:#ffffff;border:1px solid #1a5fc4;border-radius:6px;}"
            "QPushButton:hover{background:#1b63cf;}"
        )
        close_btn.clicked.connect(self.accept)
        right_layout.addWidget(close_btn)

        layout.addWidget(right_container)
        self.setStyleSheet("QDialog{background:#ffffff;}")


class ArchivedRecordsDialog(QDialog):
    """Admin-only dialog for reviewing and restoring archived patient records."""

    def __init__(self, reports_page: "ReportsPage"):
        super().__init__(reports_page)
        self.reports_page = reports_page
        self._rows = []
        self._filtered_rows = []
        self._record_lookup = {}

        self.setWindowTitle("Archived Patient Records")
        self.resize(980, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Archived Patient Records")
        title.setStyleSheet("font-size:22px;font-weight:700;color:#007bff;")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Review archived screenings and restore them back into the active dashboard and reports.")
        subtitle.setStyleSheet("font-size:13px;color:#6c757d;")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search archived records by patient ID, name, result, or archived by")
        self.search_input.textChanged.connect(self.apply_filters)
        controls.addWidget(self.search_input, 1)
        self.count_label = QLabel("0 archived")
        self.count_label.setStyleSheet("color:#6c757d;font-size:12px;")
        self.count_label.setAlignment(Qt.AlignCenter)
        controls.addWidget(self.count_label)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Patient ID", "Name", "Result", "Archived At", "Archived By"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_restore_button)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet(
            "QPushButton{background:#dc3545;color:#fff;border:1px solid #bb2d3b;}"
            "QPushButton:hover{background:#c82333;}"
            "QPushButton:disabled{background:#f1aeb5;color:#fff;border:1px solid #ea868f;}"
        )
        self.delete_btn.clicked.connect(self.delete_selected_record)
        actions.addWidget(self.delete_btn)
        self.restore_btn = QPushButton("Restore Selected")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self.restore_selected_record)
        actions.addWidget(self.restore_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        layout.addLayout(actions)
        self.reload_rows()

    def reload_rows(self):
        self._rows = [r for r in self.reports_page._all_result_rows if r["archived_at"]]
        self._record_lookup = {r["id"]: r for r in self._rows}
        self.apply_filters()

    def apply_filters(self):
        query = self.search_input.text().strip().lower()
        filtered = []
        for row in self._rows:
            haystack = " ".join([str(row[k] or "") for k in ("patient_id","name","result","archived_at","archived_by")]).lower()
            if query and query not in haystack:
                continue
            filtered.append(row)
        self._filtered_rows = filtered
        self._render_table()

    def _render_table(self):
        self.table.setRowCount(0)
        for row in self._filtered_rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            item = QTableWidgetItem(str(row["patient_id"] or ""))
            item.setData(Qt.UserRole, row["id"])
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, item)
            name_item = QTableWidgetItem(str(row["name"] or ""))
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, name_item)
            result_item = QTableWidgetItem(str(row["result"] or ""))
            result_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, result_item)
            archived_at_item = QTableWidgetItem(str(row["archived_at"] or ""))
            archived_at_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 3, archived_at_item)
            archived_by_item = QTableWidgetItem(str(row["archived_by"] or ""))
            archived_by_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 4, archived_by_item)
        self.count_label.setText(f"{len(self._filtered_rows)} archived")
        self._update_restore_button()

    def _get_selected_record(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        item = self.table.item(r, 0)
        return self._record_lookup.get(item.data(Qt.UserRole)) if item else None

    def _update_restore_button(self):
        has = self._get_selected_record() is not None
        self.restore_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def restore_selected_record(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Restore Record", "Select an archived patient record to restore.")
            return
        if not self.reports_page.restore_record(record):
            return
        self.reports_page.refresh_report()
        self.reload_rows()

    def delete_selected_record(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Delete Record", "Select an archived patient record to delete.")
            return
        label = f"{record['name'] or 'Unknown Patient'} ({record['patient_id'] or 'No ID'})"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Delete Archived Record")
        box.setText(f"Permanently delete {label}?")
        box.setInformativeText("This action cannot be undone.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        if not self.reports_page.delete_archived_record(record):
            QMessageBox.warning(self, "Delete Record", "Unable to permanently delete the selected record.")
            return
        self.reports_page.refresh_report()
        self.reload_rows()


class ReportsPage(QWidget):
    """Reports page with local offline statistics."""

    def __init__(self, username: str = "", role: str = "clinician", display_name: str = "", specialization: str = ""):
        super().__init__()
        self.username = username or os.environ.get("EYESHIELD_CURRENT_USER", "")
        self.display_name = display_name or os.environ.get("EYESHIELD_CURRENT_NAME", "") or self.username
        self.role = role or os.environ.get("EYESHIELD_CURRENT_ROLE", "clinician")
        self.specialization = str(specialization or os.environ.get("EYESHIELD_CURRENT_SPECIALIZATION", "")).strip()
        self.display_title = self.specialization if self.role == "clinician" and self.specialization else self.role
        self.is_admin = self.role == "admin"
        self.records_changed_callback = None
        self.archived_records_dialog = None
        self._summary_cache = {}
        self._all_result_rows = []
        self._filtered_rows = []
        self._record_lookup = {}
        self._display_row_lookup = {}

        self.setStyleSheet("""
            QWidget {
                background: #f2f6fb;
                color: #1f2a37;
                font-family: 'Calibri', 'Inter', 'Arial';
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d8e2ee;
                border-radius: 14px;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #c7d5e6;
                border-radius: 10px;
                padding: 8px 12px;
            }
            QLineEdit:hover, QComboBox:hover {
                border: 1px solid #9eb9d8;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #1f6fe5;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #d3deeb;
                border-radius: 12px;
                gridline-color: #edf2f7;
                alternate-background-color: #f7fafd;
                selection-background-color: #e8f0ff;
                selection-color: #1f2a37;
                padding: 4px;
            }
            QTableWidget::item {
                padding: 10px 8px;
                border: none;
            }
            QHeaderView::section {
                background: #f3f7fc;
                color: #3d526b;
                border: none;
                border-bottom: 1px solid #dbe6f2;
                padding: 12px 8px;
                font-weight: 700;
            }
            QPushButton:focus, QTableWidget:focus {
                border: 1px solid #1f6fe5;
            }
            QPushButton {
                background: #eef3f9;
                color: #1f2a37;
                border: 1px solid #c9d6e6;
                border-radius: 10px;
                padding: 9px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e4edf7;
            }
            QPushButton#primaryAction {
                background: #1f6fe5;
                color: #ffffff;
                border: 1px solid #1a5fc4;
                border-radius: 10px;
                padding: 9px 16px;
                font-weight: 700;
            }
            QLabel#statusLabel {
                color: #4f637a;
                font-size: 12px;
            }
            QLabel#hintLabel {
                color: #62788f;
                font-size: 12px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        self._rep_title_lbl = QLabel("DR Screening Reports")
        self._rep_title_lbl.setObjectName("pageHeader")
        self._rep_title_lbl.setStyleSheet("font-size:26px;font-weight:700;color:#1f6fe5;font-family:'Calibri','Inter','Arial';")
        self._rep_subtitle_lbl = QLabel("View, filter, and export diabetic retinopathy screening outcomes.")
        self._rep_subtitle_lbl.setObjectName("pageSubtitle")
        self._rep_subtitle_lbl.setStyleSheet("font-size:13px;color:#6b7f95;")
        self._rep_subtitle_lbl.setAlignment(Qt.AlignLeft)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        top_bar.addWidget(self._rep_title_lbl)
        top_bar.addStretch(1)
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setObjectName("primaryAction")
        self.export_btn.setAutoDefault(True)
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self.export_summary)
        if self.is_admin:
            self.archive_btn = QPushButton("Archive Selected")
            self.archive_btn.clicked.connect(self.archive_selected_record)
            self.archive_btn.setEnabled(False)
            top_bar.addWidget(self.archive_btn)
        else:
            self.archive_btn = None
        if self.is_admin:
            self.archived_records_btn = QPushButton("Archived Records")
            self.archived_records_btn.clicked.connect(self.open_archived_records_window)
            top_bar.addWidget(self.archived_records_btn)
        else:
            self.archived_records_btn = None
        top_bar.addWidget(self.export_btn)
        self.report_btn = QPushButton("Generate Report")
        self.report_btn.setEnabled(False)
        self.report_btn.clicked.connect(self.generate_report)
        top_bar.addWidget(self.report_btn)
        self.referral_btn = QPushButton("Generate Referral")
        self.referral_btn.setEnabled(False)
        self.referral_btn.clicked.connect(self.generate_referral)
        top_bar.addWidget(self.referral_btn)
        self.rescreen_btn = QPushButton("Rescreen")
        self.rescreen_btn.setEnabled(False)
        self.rescreen_btn.clicked.connect(self.rescreen_patient)
        top_bar.addWidget(self.rescreen_btn)
        root.addLayout(top_bar)

        root.addWidget(self._rep_subtitle_lbl)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color:#4f637a;background:#eaf1fb;border:1px solid #d4e2f3;border-radius:10px;padding:8px 12px;")
        root.addWidget(self.status_label)

        self._controls_group = QGroupBox("")
        cl = QHBoxLayout(self._controls_group)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(14)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by patient ID, name, eye screened, result, or confidence")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self.apply_filters)
        cl.addWidget(self.search_input, 1)
        self.result_filter = QComboBox()
        self.result_filter.addItems(["All","No DR","Mild DR","Moderate DR","Severe DR","Proliferative DR"])
        self.result_filter.setMinimumHeight(40)
        self.result_filter.currentTextChanged.connect(self.apply_filters)
        cl.addWidget(self.result_filter)
        self.filtered_count_label = QLabel("Total: 0")
        self.filtered_count_label.setObjectName("hintLabel")
        self.filtered_count_label.setAlignment(Qt.AlignCenter)
        self.filtered_count_label.setStyleSheet("color:#62788f;font-size:12px;background:#f3f8ff;border:1px solid #dbe7f5;border-radius:8px;padding:6px 10px;")
        cl.addWidget(self.filtered_count_label)
        root.addWidget(self._controls_group)

        self._results_group = QGroupBox("")
        rl = QVBoxLayout(self._results_group)
        rl.setContentsMargins(18, 16, 18, 18)
        rl.setSpacing(14)

        self.results_table = QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels(["Patient ID","Name","Eye Screened","Screening Date","Result","Confidence","Screened by"])
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setShowGrid(False)
        self.results_table.setSortingEnabled(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(42)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self._update_action_buttons)
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._open_results_context_menu)
        self.results_table.doubleClicked.connect(self._on_table_row_double_clicked)
        self.results_table.setMinimumHeight(420)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        rl.addWidget(self.results_table)
        root.addWidget(self._results_group)

        self.setTabOrder(self.export_btn, self.report_btn)
        self.setTabOrder(self.report_btn, self.referral_btn)
        self.setTabOrder(self.referral_btn, self.search_input)
        self.setTabOrder(self.search_input, self.result_filter)
        self.setTabOrder(self.result_filter, self.results_table)
        self._setup_action_buttons_ui()
        self.refresh_report()

    def _icon_path(self, filename: str) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", filename)

    def _set_button_icon(self, button: QPushButton, icon_name: str):
        icon_file = self._icon_path(icon_name)
        if os.path.exists(icon_file):
            button.setIcon(QIcon(icon_file))
            button.setIconSize(QSize(18, 18))

    def _setup_action_buttons_ui(self):
        self._set_button_icon(self.export_btn, "export.svg")
        self._set_button_icon(self.report_btn, "generate_report.svg")
        self._set_button_icon(self.referral_btn, "referral.svg")
        self._set_button_icon(self.rescreen_btn, "rescreen.svg")
        self.export_btn.setText("Export")
        self.report_btn.setText("Report")
        self.referral_btn.setText("Referral")
        self.rescreen_btn.setText("Rescreen")
        self.export_btn.setToolTip("Export currently visible report rows to CSV")
        self.report_btn.setToolTip("Generate a detailed PDF report for the selected patient")
        self.referral_btn.setToolTip("Generate a referral letter PDF for the selected patient")
        self.rescreen_btn.setToolTip("Rescreen the selected patient")
        if self.archived_records_btn is not None:
            self._set_button_icon(self.archived_records_btn, "archives.svg")
            self.archived_records_btn.setText("Archived Records")
            self.archived_records_btn.setToolTip("Open archived records and restore or delete entries")
        if self.archive_btn is not None:
            self._set_button_icon(self.archive_btn, "archive.svg")
            self.archive_btn.setText("Archive")
            self.archive_btn.setToolTip("Archive the selected active patient record")

        top_icon_buttons = [self.export_btn, self.report_btn, self.referral_btn, self.rescreen_btn]
        if self.archive_btn is not None:
            top_icon_buttons.append(self.archive_btn)
        if self.archived_records_btn is not None:
            top_icon_buttons.append(self.archived_records_btn)

        for button in top_icon_buttons:
            button.setMinimumHeight(40)
            button.setStyleSheet(
                "QPushButton{background:#1f6fe5;color:#ffffff;border:1px solid #1a5fc4;border-radius:10px;padding:8px 14px;font-weight:700;}"
                "QPushButton:hover{background:#1b63cf;}"
                "QPushButton:disabled{background:#8fb5f2;border:1px solid #8fb5f2;color:#edf4ff;}"
            )

    def refresh_report(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, patient_id, name, eyes, screened_at, result, confidence, diabetes_type, hba1c,
                       ai_classification, doctor_classification, decision_mode, override_justification, final_diagnosis_icdr, doctor_findings,
                       archived_at, archived_by, archive_reason,
                       original_screener_username, original_screener_name
                FROM patient_records ORDER BY id DESC
            """)
            rows = [{"id":r[0],"patient_id":r[1],"name":r[2],"eyes":r[3],"screened_at":r[4],"result":r[5],"confidence":r[6],
                     "diabetes_type":r[7],"hba1c":r[8],
                     "ai_classification":r[9],"doctor_classification":r[10],"decision_mode":r[11],"override_justification":r[12],"final_diagnosis_icdr":r[13],"doctor_findings":r[14],
                     "archived_at":r[15],"archived_by":r[16],"archive_reason":r[17],
                     "original_screener_username":r[18],"original_screener_name":r[19]}
                    for r in cur.fetchall()]
            for row in rows:
                row["result"] = row.get("final_diagnosis_icdr") or row.get("doctor_classification") or row.get("result") or ""
            conn.close()
        except Exception as err:
            QMessageBox.warning(self, "Reports", f"Failed to load report data: {err}")
            return
        self._all_result_rows = rows
        self._record_lookup = {r["id"]: r for r in rows}
        self.apply_filters()
        if self.archived_records_dialog is not None:
            self.archived_records_dialog.reload_rows()
        active = [r for r in rows if not r["archived_at"]]
        archived_count = len(rows) - len(active)
        if self.is_admin:
            self.status_label.setText(f"Updated {len(active)} active and {archived_count} archived records at {datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")
        else:
            self.status_label.setText(f"Updated {len(active)} screenings at {datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")

    @staticmethod
    def _eye_sort_key(eye_value: str) -> tuple[int, str]:
        eye = str(eye_value or "").strip().lower()
        if "right" in eye:
            return (0, eye)
        if "left" in eye:
            return (1, eye)
        return (2, eye)

    def _build_display_rows(self, rows: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            key = (str(row.get("patient_id") or "").strip(), str(row.get("screened_at") or "").strip())
            grouped.setdefault(key, []).append(row)

        display_rows = []
        for key, grouped_rows in grouped.items():
            ordered_rows = sorted(
                grouped_rows,
                key=lambda item: (self._eye_sort_key(item.get("eyes")), -int(item.get("id") or 0)),
            )
            primary = ordered_rows[0]
            owner_name = str(primary.get("original_screener_name") or "").strip()
            owner_username = str(primary.get("original_screener_username") or "").strip()
            screened_by_display = self._format_doctor_label(owner_name or owner_username)
            record_ids = [int(item.get("id") or 0) for item in ordered_rows if int(item.get("id") or 0)]
            selection_key = f"{key[0]}|{key[1]}|{'-'.join(str(i) for i in record_ids)}"
            eyes_text = "\n".join(str(item.get("eyes") or "—") for item in ordered_rows)
            date_text = "\n".join(str(item.get("screened_at") or "—") for item in ordered_rows)
            result_text = "\n".join(
                str(item.get("final_diagnosis_icdr") or item.get("doctor_classification") or item.get("result") or "—")
                for item in ordered_rows
            )
            confidence_text = "\n".join(str(item.get("confidence") or "—") for item in ordered_rows)
            combined_search = " ".join(
                [
                    str(primary.get("patient_id") or ""),
                    str(primary.get("name") or ""),
                    eyes_text,
                    date_text,
                    result_text,
                    confidence_text,
                    str(primary.get("final_diagnosis_icdr") or ""),
                    str(primary.get("doctor_classification") or ""),
                    str(primary.get("doctor_findings") or ""),
                    screened_by_display,
                ]
            ).lower()
            display_rows.append(
                {
                    "selection_key": selection_key,
                    "id": primary.get("id"),
                    "patient_id": primary.get("patient_id"),
                    "name": primary.get("name"),
                    "eyes": eyes_text,
                    "screened_at": date_text,
                    "result": result_text,
                    "confidence": confidence_text,
                    "final_diagnosis_icdr": primary.get("final_diagnosis_icdr"),
                    "doctor_classification": primary.get("doctor_classification"),
                    "decision_mode": primary.get("decision_mode"),
                    "override_justification": primary.get("override_justification"),
                    "doctor_findings": primary.get("doctor_findings"),
                    "screened_by": screened_by_display,
                    "diabetes_type": primary.get("diabetes_type"),
                    "hba1c": primary.get("hba1c"),
                    "archived_at": primary.get("archived_at"),
                    "archived_by": primary.get("archived_by"),
                    "archive_reason": primary.get("archive_reason"),
                    "original_screener_username": primary.get("original_screener_username"),
                    "original_screener_name": primary.get("original_screener_name"),
                    "record_ids": record_ids,
                    "source_rows": ordered_rows,
                    "_search_text": combined_search,
                }
            )

        display_rows.sort(key=lambda item: max(item.get("record_ids") or [0]), reverse=True)
        self._display_row_lookup = {row["selection_key"]: row for row in display_rows}
        return display_rows

    def apply_filters(self):
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        mode = self.result_filter.currentText() if hasattr(self, "result_filter") else "All"
        active_rows = [row for row in self._all_result_rows if not row["archived_at"]]
        display_rows = self._build_display_rows(active_rows)
        filtered = []
        for row in display_rows:
            source_rows = row.get("source_rows") or []
            if not source_rows:
                continue
            if query and query not in str(row.get("_search_text") or ""):
                continue
            result_blob = " ".join(str(item.get("result") or "") for item in source_rows).lower()
            if mode == "No DR" and "no dr" not in result_blob:
                continue
            if mode == "Mild DR" and "mild" not in result_blob:
                continue
            if mode == "Moderate DR" and "moderate" not in result_blob:
                continue
            if mode == "Severe DR" and "severe" not in result_blob:
                continue
            if mode == "Proliferative DR" and "proliferative" not in result_blob:
                continue
            filtered.append(row)
        self._filtered_rows = filtered
        self._update_summary_cards(filtered)
        self._render_results_table()

    def _render_results_table(self):
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        result_color = self._result_color_for_current_theme
        for row in self._filtered_rows:
            i = self.results_table.rowCount()
            self.results_table.insertRow(i)
            item = QTableWidgetItem(str(row["patient_id"] or ""))
            item.setData(Qt.UserRole, row["selection_key"])
            item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 0, item)
            name_item = QTableWidgetItem(str(row["name"] or ""))
            name_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 1, name_item)
            eyes_item = QTableWidgetItem(str(row.get("eyes") or ""))
            eyes_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 2, eyes_item)
            screened_at_item = QTableWidgetItem(str(row.get("screened_at") or ""))
            screened_at_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 3, screened_at_item)
            ri = QTableWidgetItem(str(row["result"] or ""))
            ri.setTextAlignment(Qt.AlignCenter)
            if any(self._is_high_attention_result(item.get("result")) for item in (row.get("source_rows") or [])):
                ri.setForeground(result_color("high"))
            elif all("no dr" in str(item.get("result") or "").lower() for item in (row.get("source_rows") or [])):
                ri.setForeground(result_color("normal"))
            self.results_table.setItem(i, 4, ri)
            confidence_item = QTableWidgetItem(str(row["confidence"] or ""))
            confidence_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 5, confidence_item)
            screened_by_item = QTableWidgetItem(str(row.get("screened_by") or "--"))
            screened_by_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 6, screened_by_item)
        self.results_table.setSortingEnabled(True)
        self.results_table.resizeRowsToContents()
        self.filtered_count_label.setText(f"Total: {len(self._filtered_rows)}")
        self._update_action_buttons()

    def _result_color_for_current_theme(self, level: str) -> QColor:
        window = self.palette().color(self.backgroundRole())
        is_dark = window.value() < 128
        if level == "high":
            return QColor("#fca5a5") if is_dark else QColor("#991b1b")
        return QColor("#86efac") if is_dark else QColor("#166534")

    def _update_summary_cards(self, rows):
        total = len(rows)
        self._summary_cache = {"total_screenings": total}

    @staticmethod
    def _format_doctor_label(name_value: str) -> str:
        name = str(name_value or "").strip()
        if not name:
            return "--"
        if name.lower().startswith("dr"):
            return name
        return f"Dr. {name}"

    def _can_rescreen_record(self, record: dict) -> bool:
        owner_username = str(record.get("original_screener_username") or "").strip().lower()
        if not owner_username:
            return True
        return owner_username == str(self.username or "").strip().lower()

    def _record_owner_label(self, record: dict) -> str:
        owner_name = str(record.get("original_screener_name") or "").strip()
        owner_username = str(record.get("original_screener_username") or "").strip()
        return owner_name or owner_username or "original screener"

    def _open_results_context_menu(self, pos):
        item = self.results_table.itemAt(pos)
        if item is None:
            return
        self.results_table.selectRow(item.row())
        record = self._get_selected_record()
        if not record:
            return

        menu = QMenu(self)
        view_action = menu.addAction("View Details")
        menu.addSeparator()
        generate_action = menu.addAction("Generate Report")
        referral_action = menu.addAction("Generate Referral")
        rescreen_action = menu.addAction("Rescreen Patient")
        rescreen_action.setEnabled(self._can_rescreen_record(record))
        archive_action = None
        if self.is_admin:
            archive_action = menu.addAction("Archive Record")
            archive_action.setEnabled(not bool(record.get("archived_at")))

        chosen = menu.exec(self.results_table.viewport().mapToGlobal(pos))
        if chosen == view_action:
            self._show_patient_details()
        elif chosen == generate_action:
            self.generate_report()
        elif chosen == referral_action:
            self.generate_referral()
        elif chosen == rescreen_action:
            self.rescreen_patient()
        elif archive_action is not None and chosen == archive_action:
            self.archive_selected_record()

    def _get_selected_record(self):
        r = self.results_table.currentRow()
        if r < 0: return None
        item = self.results_table.item(r, 0)
        return self._display_row_lookup.get(item.data(Qt.UserRole)) if item else None

    def _update_action_buttons(self):
        record = self._get_selected_record()
        self.report_btn.setEnabled(bool(record))
        self.referral_btn.setEnabled(bool(record))
        can_rescreen = bool(record and self._can_rescreen_record(record))
        self.rescreen_btn.setEnabled(can_rescreen)
        if record and not can_rescreen:
            self.rescreen_btn.setToolTip(
                f"Only the original screener ({self._record_owner_label(record)}) can rescreen this case."
            )
        else:
            self.rescreen_btn.setToolTip("Start a new screening for the selected patient")
        if self.is_admin:
            self.archive_btn.setEnabled(bool(record and not record["archived_at"]))

    def _on_table_row_double_clicked(self, index):
        """Handle double-click on table row to show patient details."""
        self._show_patient_details()

    def _show_patient_details(self):
        """Show view-only patient details dialog."""
        record = self._get_selected_record()
        if not record:
            return
        
        record_id = record.get("id") or (record.get("record_ids")[0] if record.get("record_ids") else None)
        if not record_id:
            QMessageBox.warning(self, "Patient Details", "Unable to retrieve patient record.")
            return
        
        full_record = self._fetch_full_patient_record(record_id)
        if not full_record:
            QMessageBox.warning(self, "Patient Details", "Unable to load patient details.")
            return

        UserManager.add_activity_log(
            self.username,
            f"RECORD_OPENED patient_id={full_record.get('patient_id')}; record_id={record_id}; source=reports",
        )
        
        dialog = PatientDetailsDialog(full_record, self)
        dialog.exec()

    def _fetch_full_patient_record(self, record_id: int) -> dict:
        """Fetch complete patient record from database."""
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, patient_id, name, birthdate, age, sex, contact, eyes, 
                       diabetes_type, duration, hba1c, prev_treatment, notes, 
                       result, confidence, screened_at, archived_at, archived_by, 
                       archive_reason, original_screener_username, original_screener_name,
                       ai_classification, doctor_classification, decision_mode, override_justification, final_diagnosis_icdr, doctor_findings,
                       height, weight, bmi, visual_acuity_left, visual_acuity_right,
                       blood_pressure_systolic, blood_pressure_diastolic,
                       fasting_blood_sugar, random_blood_sugar,
                       diabetes_diagnosis_date, treatment_regimen, prev_dr_stage,
                       symptom_blurred_vision, symptom_floaters, symptom_flashes,
                       symptom_vision_loss
                FROM patient_records
                WHERE id = ?
            """, (record_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "patient_id": row[1],
                "name": row[2],
                "birthdate": row[3],
                "age": row[4],
                "sex": row[5],
                "contact": row[6],
                "eyes": row[7],
                "diabetes_type": row[8],
                "duration": row[9],
                "hba1c": row[10],
                "prev_treatment": row[11],
                "notes": row[12],
                "result": row[13],
                "confidence": row[14],
                "screened_at": row[15],
                "archived_at": row[16],
                "archived_by": row[17],
                "archive_reason": row[18],
                "original_screener_username": row[19],
                "original_screener_name": row[20],
                "ai_classification": row[21],
                "doctor_classification": row[22],
                "decision_mode": row[23],
                "override_justification": row[24],
                "final_diagnosis_icdr": row[25],
                "doctor_findings": row[26],
                "height": row[27],
                "weight": row[28],
                "bmi": row[29],
                "visual_acuity_left": row[30],
                "visual_acuity_right": row[31],
                "blood_pressure_systolic": row[32],
                "blood_pressure_diastolic": row[33],
                "fasting_blood_sugar": row[34],
                "random_blood_sugar": row[35],
                "diabetes_diagnosis_date": row[36],
                "treatment_regimen": row[37],
                "prev_dr_stage": row[38],
                "symptom_blurred_vision": row[39],
                "symptom_floaters": row[40],
                "symptom_flashes": row[41],
                "symptom_vision_loss": row[42],
            }
        except Exception as err:
            print(f"Error fetching patient record: {err}")
            return None

    def open_archived_records_window(self):
        self.refresh_report()
        if self.archived_records_dialog is None:
            self.archived_records_dialog = ArchivedRecordsDialog(self)
        self.archived_records_dialog.reload_rows()
        self.archived_records_dialog.show()
        self.archived_records_dialog.raise_()
        self.archived_records_dialog.activateWindow()

    def archive_selected_record(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Archive Record", "Select a patient record to archive.")
            return
        if record["archived_at"]:
            QMessageBox.information(self, "Archive Record", "The selected patient record is already archived.")
            return
        label = f"{record['name'] or 'Unknown Patient'} ({record['patient_id'] or 'No ID'})"
        if QMessageBox.question(self, "Archive Record", f"Archive {label}?",
                                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if not self._set_records_archive_state(record.get("record_ids") or [record["id"]], archived=True):
            QMessageBox.warning(self, "Archive Record", "Unable to archive the selected patient record.")
            return
        self.refresh_report()

    def rescreen_patient(self):
        """Open rescreen dialog and navigate to screening page."""
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Rescreen Patient", "Select a patient record to rescreen.")
            return

        if not self._can_rescreen_record(record):
            owner_text = self._record_owner_label(record)
            UserManager.add_activity_log(
                self.username,
                f"RESCREEN_BLOCKED patient_id={record.get('patient_id')}; owner={owner_text}",
            )
            QMessageBox.warning(
                self,
                "Rescreen Restricted",
                f"Only the original screening doctor ({owner_text}) can rescreen this patient.",
            )
            return

        # Get the actual record ID - use first record_id if multiple exist
        record_ids = record.get("record_ids") or [record.get("id")]
        if not record_ids or not record_ids[0]:
            QMessageBox.warning(self, "Rescreen Patient", "Unable to identify patient record ID.")
            return

        actual_record_id = record_ids[0]

        label = f"{record['name'] or 'Unknown Patient'} ({record['patient_id'] or 'No ID'})"
        box = QMessageBox(self)
        box.setWindowTitle("Rescreen Patient")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(
            f"How would you like to rescreen <b>{label}</b>?"
        )
        new_btn = box.addButton("Create New Screening", QMessageBox.ButtonRole.AcceptRole)
        replace_btn = box.addButton("Replace Screening Record", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()

        chosen = box.clickedButton()
        if chosen == cancel_btn:
            return

        replace_mode = chosen == replace_btn

        # Get main window and screening page
        main_window = self.window()
        if not hasattr(main_window, 'screening_page') or not hasattr(main_window, 'pages'):
            QMessageBox.warning(self, "Navigation Error", "Unable to navigate to screening page.")
            return

        screening_page = main_window.screening_page
        if not screening_page.load_patient_for_rescreen(actual_record_id, replace_mode=replace_mode):
            QMessageBox.warning(self, "Load Patient", f"Failed to load patient data for rescreening.\n\nRecord ID: {actual_record_id}")
            return

        # Navigate to screening page
        main_window.pages.setCurrentIndex(1)
        UserManager.add_activity_log(
            self.username,
            f"RESCREEN_ALLOWED patient_id={record.get('patient_id')}; record_id={actual_record_id}; replace_mode={replace_mode}",
        )


    def restore_record(self, record):
        if not record or not record["archived_at"]:
            QMessageBox.information(self, "Restore Record", "The selected patient record is already active.")
            return False
        label = f"{record['name'] or 'Unknown Patient'} ({record['patient_id'] or 'No ID'})"
        if QMessageBox.question(self, "Restore Record", f"Restore {label}?",
                                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        if not self._set_record_archive_state(record["id"], archived=False):
            QMessageBox.warning(self, "Restore Record", "Unable to restore the selected patient record.")
            return False
        return True

    def delete_archived_record(self, record):
        if not record or not record["archived_at"]:
            return False
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("DELETE FROM patient_records WHERE id=? AND archived_at IS NOT NULL", (record["id"],))
            conn.commit()
            success = cur.rowcount > 0
            conn.close()
        except Exception:
            return False
        if success and callable(self.records_changed_callback):
            self.records_changed_callback()
        return success

    def _set_record_archive_state(self, record_id, archived: bool) -> bool:
        return self._set_records_archive_state([record_id], archived=archived)

    def _set_records_archive_state(self, record_ids, archived: bool) -> bool:
        actor_name = self.display_name or os.environ.get("EYESHIELD_CURRENT_NAME", "") or self.username
        actor_title = self.display_title or os.environ.get("EYESHIELD_CURRENT_TITLE", "")
        actor = f"{actor_name} ({actor_title})" if actor_name and actor_title else actor_name
        valid_ids = [int(record_id) for record_id in record_ids if int(record_id)]
        if not valid_ids:
            return False
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            placeholders = ",".join("?" for _ in valid_ids)
            cur.execute(
                f"SELECT id, patient_id FROM patient_records WHERE id IN ({placeholders})",
                valid_ids,
            )
            affected_rows = cur.fetchall()
            if archived:
                cur.execute(
                    f"UPDATE patient_records SET archived_at=?,archived_by=?,archive_reason=? WHERE id IN ({placeholders})",
                    [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor, None, *valid_ids],
                )
            else:
                cur.execute(
                    f"UPDATE patient_records SET archived_at=NULL,archived_by=NULL,archive_reason=NULL WHERE id IN ({placeholders})",
                    valid_ids,
                )
            conn.commit()
            success = cur.rowcount > 0
            conn.close()
        except Exception:
            return False
        if success and callable(self.records_changed_callback):
            self.records_changed_callback()
        if success:
            event = "RECORD_ARCHIVED" if archived else "RECORD_RESTORED"
            for rec_id, patient_id in affected_rows:
                UserManager.add_activity_log(
                    self.username,
                    f"{event} patient_id={patient_id}; record_id={rec_id}",
                )
        return success

    @staticmethod
    def _is_high_attention_result(result_text):
        return any(k in str(result_text or "").lower() for k in ("moderate","severe","proliferative","refer","urgent","dr detected"))

    def export_summary(self):
        if not self._summary_cache:
            self.status_label.setText("No report data to export")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export DR Screening Results", "", "CSV Files (*.csv)")
        if not path:
            return
        if not self._filtered_rows:
            self.status_label.setText("No visible report data to export")
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Patient ID","Name","Eye Screened","Screening Date","AI Classification","Doctor Classification","Final Diagnosis (ICDR)","Doctor Findings","Decision Mode","Override Justification","Confidence","Diabetes Type","HbA1c","Record Status","Archived At","Archived By"])
                for row in self._filtered_rows:
                    w.writerow([row["patient_id"],row["name"],row.get("eyes", ""),row.get("screened_at", ""),
                                row.get("ai_classification",""), row.get("doctor_classification",""), row.get("final_diagnosis_icdr",""),
                                row.get("doctor_findings",""),
                                row.get("decision_mode",""), row.get("override_justification",""),
                                row["confidence"],
                                row["diabetes_type"],row["hba1c"],
                                "Archived" if row["archived_at"] else "Active",
                                row["archived_at"],row["archived_by"]])
            self.status_label.setText(f"Exported {len(self._filtered_rows)} rows to {path}")
            UserManager.add_activity_log(
                self.username,
                f"REPORT_EXPORT_CSV rows={len(self._filtered_rows)}; path={os.path.basename(path)}",
            )
        except OSError as err:
            QMessageBox.warning(self, "Export", f"Failed to export summary: {err}")

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._rep_title_lbl.setText(pack["rep_title"])
        self._rep_subtitle_lbl.setText(pack["rep_subtitle"])
        self._controls_group.setTitle("")
        self._results_group.setTitle("")
        self._setup_action_buttons_ui()

    # ── Report generation ──────────────────────────────────────────────────────

    def _fetch_full_record(self, record_id: int) -> "dict | None":
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, patient_id, name, birthdate, age, sex, contact, eyes,
                      diabetes_type, duration, hba1c, prev_treatment, notes,
                      result, confidence, screened_at,
                      ai_classification, doctor_classification, decision_mode, override_justification, final_diagnosis_icdr, doctor_findings,
                       visual_acuity_left, visual_acuity_right,
                       blood_pressure_systolic, blood_pressure_diastolic,
                       fasting_blood_sugar, random_blood_sugar,
                       symptom_blurred_vision, symptom_floaters,
                      symptom_flashes, symptom_vision_loss,
                      source_image_path, heatmap_image_path,
                      image_sha256, image_saved_at,
                      original_screener_username, original_screener_name
                FROM patient_records WHERE id=?
            """, (record_id,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return None
            return {
                "id":row[0],"patient_id":row[1],"name":row[2],"birthdate":row[3],
                "age":row[4],"sex":row[5],"contact":row[6],"eyes":row[7],
                "diabetes_type":row[8],"duration":row[9],"hba1c":row[10],
                "prev_treatment":row[11],"notes":row[12],"result":row[13],"confidence":row[14],"screened_at":row[15],
                "ai_classification":row[16],"doctor_classification":row[17],"decision_mode":row[18],
                "override_justification":row[19],"final_diagnosis_icdr":row[20],"doctor_findings":row[21],
                "va_left":row[22],"va_right":row[23],
                "bp_systolic":row[24],"bp_diastolic":row[25],
                "fbs":row[26],"rbs":row[27],
                "symptom_blurred":row[28],"symptom_floaters":row[29],
                "symptom_flashes":row[30],"symptom_vision_loss":row[31],
                "source_image_path":row[32],"heatmap_image_path":row[33],
                "image_sha256":row[34],"image_saved_at":row[35],
                "original_screener_username":row[36],"original_screener_name":row[37],
            }
        except Exception:
            return None

    def _fetch_report_eye_records(self, patient_id: str, screened_at: str, fallback_record_id: int) -> list[dict]:
        def eye_sort_key(record: dict) -> tuple[int, str]:
            eye = str(record.get("eyes") or "").strip().lower()
            if "right" in eye:
                return (0, eye)
            if "left" in eye:
                return (1, eye)
            return (2, eye)

        patient_id = str(patient_id or "").strip()
        screened_at = str(screened_at or "").strip()
        if not patient_id:
            single = self._fetch_full_record(fallback_record_id)
            return [single] if single else []

        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            if screened_at:
                cur.execute(
                    """
                    SELECT id
                    FROM patient_records
                    WHERE patient_id = ? AND screened_at = ?
                    ORDER BY id ASC
                    """,
                    (patient_id, screened_at),
                )
            else:
                cur.execute(
                    """
                    SELECT id
                    FROM patient_records
                    WHERE patient_id = ?
                    ORDER BY id DESC
                    LIMIT 2
                    """,
                    (patient_id,),
                )
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        records = []
        for row in rows:
            full_record = self._fetch_full_record(int(row[0]))
            if full_record:
                records.append(full_record)

        if not records:
            single = self._fetch_full_record(fallback_record_id)
            records = [single] if single else []

        unique_records = []
        seen_ids = set()
        for record in records:
            record_id = record.get("id")
            if record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            unique_records.append(record)
        return sorted(unique_records, key=eye_sort_key)

    def _prompt_referral_destination(self) -> "dict | None":
        hospitals = UserManager.list_referral_hospitals(active_only=True)

        dialog = QDialog(self)
        dialog.setWindowTitle("Referral Destination")
        dialog.resize(560, 320)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        subtitle = QLabel("Choose a trusted referral hospital or use Other for one-time manual entry.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#4f637a;font-size:12px;")
        layout.addWidget(subtitle)

        hospital_label = QLabel("Referral Hospital")
        hospital_label.setStyleSheet("font-size:11px;font-weight:700;color:#2f4054;")
        hospital_combo = QComboBox()
        hospital_combo.setMinimumHeight(36)
        for item in hospitals:
            dept = str(item.get("department") or "").strip()
            label = str(item.get("hospital_name") or "").strip()
            if dept:
                label = f"{label} ({dept})"
            if item.get("is_default"):
                label = f"{label}  [Default]"
            hospital_combo.addItem(label, item)
        hospital_combo.addItem("Other (manual entry)", None)
        if not hospitals:
            hospital_combo.setCurrentIndex(0)
        layout.addWidget(hospital_label)
        layout.addWidget(hospital_combo)

        manual_wrap = QWidget()
        manual_layout = QVBoxLayout(manual_wrap)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)

        manual_name = QLineEdit()
        manual_name.setPlaceholderText("Hospital name")
        manual_department = QLineEdit()
        manual_department.setPlaceholderText("Department (optional)")
        manual_contact = QLineEdit()
        manual_contact.setPlaceholderText("Contact person or phone (optional)")

        manual_layout.addWidget(QLabel("Manual Referral Destination"))
        manual_layout.addWidget(manual_name)
        manual_layout.addWidget(manual_department)
        manual_layout.addWidget(manual_contact)
        layout.addWidget(manual_wrap)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        continue_btn = QPushButton("Continue")
        continue_btn.setObjectName("primaryAction")
        action_row.addWidget(cancel_btn)
        action_row.addWidget(continue_btn)
        layout.addLayout(action_row)

        cancel_btn.clicked.connect(dialog.reject)
        continue_btn.clicked.connect(dialog.accept)

        def _is_manual_selected() -> bool:
            return hospital_combo.currentData() is None

        def _sync_manual_visibility():
            manual_wrap.setVisible(_is_manual_selected())

        hospital_combo.currentIndexChanged.connect(_sync_manual_visibility)
        _sync_manual_visibility()

        while True:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None

            selected = hospital_combo.currentData()
            if selected is None:
                name = manual_name.text().strip()
                if not name:
                    QMessageBox.warning(dialog, "Referral Destination", "Hospital name is required for manual entry.")
                    continue
                department = manual_department.text().strip()
                contact = manual_contact.text().strip()
                display = name
                if department:
                    display = f"{display} ({department})"
                return {
                    "hospital_name": name,
                    "department": department,
                    "contact_person": contact,
                    "display": display,
                }

            hospital_name = str(selected.get("hospital_name") or "").strip()
            department = str(selected.get("department") or "").strip()
            contact = str(selected.get("contact_person") or selected.get("phone") or "").strip()
            display = hospital_name
            if department:
                display = f"{display} ({department})"
            return {
                "hospital_name": hospital_name,
                "department": department,
                "contact_person": contact,
                "display": display,
            }

    def generate_report(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Generate Report", "Select a patient record to generate a report for.")
            return

        patient_name_raw = str(record.get("name") or "Patient").strip()
        default_name = f"EyeShield_Report_{patient_name_raw}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save Patient Report", default_name, "PDF Files (*.pdf)")
        if not path:
            return

        try:
            from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QTextDocument
            from PySide6.QtCore import QMarginsF
        except ImportError:
            QMessageBox.warning(self, "Generate Report", "PDF generation requires PySide6 PDF support.")
            return

        full = self._fetch_full_record(record["id"]) or record
        eye_records = self._fetch_report_eye_records(
            full.get("patient_id"),
            full.get("screened_at"),
            int(full.get("id") or record["id"]),
        )
        if not eye_records:
            eye_records = [full]

        # ── helpers ──────────────────────────────────────────────────────────
        def esc(v) -> str:
            s = str(v or "").strip()
            return escape(s) if s and s not in ("0", "None", "Select", "-") else "&#8212;"

        # ── clinic name ───────────────────────────────────────────────────────
        clinic_name = "EyeShield EMR"
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            clinic_name = cfg.get("clinic_name") or clinic_name
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # ── confidence ────────────────────────────────────────────────────────
        raw_conf = str(full.get("confidence") or "").strip()
        if raw_conf.lower().startswith("confidence:"):
            raw_conf = raw_conf[len("confidence:"):].strip()
        conf_display = escape(raw_conf) if raw_conf else "&#8212;"

        # ── grade maps ────────────────────────────────────────────────────────
        ai_result_raw = str(full.get("ai_classification") or full.get("result") or "").strip()
        doctor_result_raw = str(full.get("doctor_classification") or full.get("result") or "").strip()
        decision_mode_raw = str(full.get("decision_mode") or "accepted").strip().lower()
        override_reason_raw = str(full.get("override_justification") or "").strip()
        final_dx_raw = str(full.get("final_diagnosis_icdr") or doctor_result_raw or ai_result_raw).strip()
        doctor_findings_raw = str(full.get("doctor_findings") or "").strip()
        result_raw = final_dx_raw or doctor_result_raw or ai_result_raw

        # Recommendation and summary based on result
        if result_raw == "No DR":
            rec = "Annual screening recommended."
            summary = "No signs of diabetic retinopathy were detected in this fundus image. Continue standard diabetes management, maintain optimal glycaemic and blood pressure control, and schedule routine annual retinal screening."
        elif result_raw == "Mild DR":
            rec = "Repeat screening in 6&#8211;12 months."
            summary = "Early microaneurysms consistent with mild non-proliferative diabetic retinopathy (NPDR) were identified. Intensify glycaemic and blood pressure management. A repeat retinal examination in 6&#8211;12 months is recommended."
        elif result_raw == "Moderate DR":
            rec = "Ophthalmology referral within 3 months."
            summary = "Features consistent with moderate non-proliferative diabetic retinopathy (NPDR) were detected, including microaneurysms, haemorrhages, and/or hard exudates. Referral to an ophthalmologist within 3 months is advised. Reassess systemic metabolic control."
        elif result_raw == "Severe DR":
            rec = "Urgent ophthalmology referral required."
            summary = "Findings consistent with severe non-proliferative diabetic retinopathy (NPDR) were detected. The risk of progression to proliferative disease within 12 months is high. Urgent ophthalmology referral is required."
        elif result_raw == "Proliferative DR":
            rec = "Immediate ophthalmology referral required."
            summary = "Proliferative diabetic retinopathy (PDR) was detected &#8212; a sight-threatening condition. Immediate ophthalmology referral is required for evaluation and potential intervention, such as laser photocoagulation or intravitreal anti-VEGF therapy."
        else:
            rec = "Consult a qualified ophthalmologist."
            summary = "Please consult a qualified ophthalmologist for further evaluation."

        referral_destination = "&#8212;"
        if final_dx_raw in ("Moderate DR", "Severe DR", "Proliferative DR"):
            selected_destination = self._prompt_referral_destination()
            if selected_destination is None:
                return
            referral_destination = esc(selected_destination.get("display"))

        report_date = datetime.now().strftime("%B %d, %Y  %I:%M %p")
        screening_date = str(full.get("screened_at") or "").strip() or report_date

        created_by_raw = str(full.get("original_screener_name") or full.get("original_screener_username") or "").strip()
        finalized_by_raw = str(self.display_name or os.environ.get("EYESHIELD_CURRENT_NAME", "") or self.username).strip()
        created_by = escape(self._format_doctor_label(created_by_raw or finalized_by_raw))
        finalized_by = escape(self._format_doctor_label(finalized_by_raw))

        dur_raw  = str(full.get("duration") or "").strip()
        dur_disp = f"{escape(dur_raw)} year(s)" if dur_raw and dur_raw != "0" else "&#8212;"

        notes_raw  = str(full.get("notes") or "").strip()
        notes_disp = escape(notes_raw) if notes_raw else '<span style="color:#9ca3af;font-style:italic;">None recorded</span>'

        bp_s    = str(full.get("blood_pressure_systolic") or full.get("bp_systolic") or "").strip()
        bp_d    = str(full.get("blood_pressure_diastolic") or full.get("bp_diastolic") or "").strip()
        bp_disp = f"{escape(bp_s)}/{escape(bp_d)} mmHg" if bp_s and bp_s != "0" and bp_d and bp_d != "0" else "&#8212;"
        va_l    = esc(full.get("visual_acuity_left") or full.get("va_left"))
        va_r    = esc(full.get("visual_acuity_right") or full.get("va_right"))
        fbs_r   = str(full.get("fasting_blood_sugar") or full.get("fbs") or "").strip()
        rbs_r   = str(full.get("random_blood_sugar") or full.get("rbs") or "").strip()
        fbs_disp = f"{escape(fbs_r)} mg/dL" if fbs_r and fbs_r != "0" else "&#8212;"
        rbs_disp = f"{escape(rbs_r)} mg/dL" if rbs_r and rbs_r != "0" else "&#8212;"

        # Phase 1 additions
        height_r = str(full.get("height") or "").strip()
        weight_r = str(full.get("weight") or "").strip()
        bmi_r = str(full.get("bmi") or "").strip()
        height_disp = f"{escape(height_r)} cm" if height_r and height_r != "0" else "&#8212;"
        weight_disp = f"{escape(weight_r)} kg" if weight_r and weight_r != "0" else "&#8212;"
        
        # BMI with classification
        def get_bmi_category(bmi_value: str) -> tuple:
            """Return (category, color) based on WHO BMI classification."""
            try:
                bmi = float(bmi_value)
                if bmi < 18.5:
                    return ("Underweight", "#ea580c")
                elif bmi < 25.0:
                    return ("Normal", "#16a34a")
                elif bmi < 30.0:
                    return ("Overweight", "#d97706")
                else:
                    return ("Obese", "#dc2626")
            except (ValueError, TypeError):
                return ("", "#6b7280")
        
        if bmi_r and bmi_r != "0":
            bmi_category, bmi_color = get_bmi_category(bmi_r)
            bmi_disp = f'{escape(bmi_r)} <span style="color:{bmi_color};font-weight:600;">({bmi_category})</span>'
        else:
            bmi_disp = "&#8212;"
        
        treatment_regimen_r = str(full.get("treatment_regimen") or "").strip()
        treatment_regimen_disp = esc(treatment_regimen_r)
        prev_dr_stage_r = str(full.get("prev_dr_stage") or "").strip()
        prev_dr_stage_disp = esc(prev_dr_stage_r)

        sym_map = [
            ("symptom_blurred_vision", "Blurred Vision"),
            ("symptom_floaters", "Floaters"),
            ("symptom_flashes", "Flashes"),
            ("symptom_vision_loss", "Vision Loss"),
        ]
        active_syms = [lbl for k, lbl in sym_map if str(full.get(k) or "").strip().lower() in ("true", "1", "yes", "checked")]
        sym_html = (
            " ".join(
                f'<span style="display:inline-block;background:#f3f4f6;color:#374151;'
                f'border:1px solid #d1d5db;border-radius:4px;padding:3px 10px;'
                f'font-size:8pt;font-weight:600;margin:2px 4px 2px 0;">{escape(s)}</span>'
                for s in active_syms
            )
            if active_syms
            else '<span style="color:#9ca3af;font-style:italic;font-size:9pt;">None reported</span>'
        )

        # ── image helpers ─────────────────────────────────────────────────────
        def resolve_image_uri(path_value: str) -> str:
            raw = str(path_value or "").strip()
            if not raw:
                return ""
            candidate = raw if os.path.isabs(raw) else os.path.join(os.path.dirname(os.path.abspath(__file__)), raw)
            if not os.path.isfile(candidate):
                return ""
            try:
                return Path(candidate).resolve().as_uri()
            except OSError:
                return ""

        # ── section heading ───────────────────────────────────────────────────
        def sec(title: str) -> str:
            return (
                f'<div style="margin:18px 0 10px;padding-bottom:6px;border-bottom:2px solid #1f2937;">'
                f'<span style="font-size:9pt;font-weight:700;color:#1f2937;letter-spacing:1.2px;text-transform:uppercase;">{title}</span>'
                f'</div>'
            )

        # ── info table helpers ────────────────────────────────────────────────
        def field_row(label: str, value: str, border: bool = True) -> str:
            border_style = 'border-bottom:1px solid #e5e7eb;' if border else ''
            return (
                f'<tr>'
                f'<td style="padding:8px 12px;{border_style}font-size:9pt;color:#4b5563;font-weight:500;width:35%;">{label}</td>'
                f'<td style="padding:8px 12px;{border_style}font-size:9pt;color:#111827;font-weight:600;">{value}</td>'
                f'</tr>'
            )

        def field_grid_2col(fields: list) -> str:
            """Generate 2-column grid layout for fields"""
            rows_html = ""
            for i in range(0, len(fields), 2):
                left_label, left_value = fields[i]
                if i + 1 < len(fields):
                    right_label, right_value = fields[i + 1]
                else:
                    right_label, right_value = "", "&#8212;"
                
                rows_html += (
                    f'<tr>'
                    f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:8.5pt;color:#6b7280;font-weight:500;width:18%;">{left_label}</td>'
                    f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:9pt;color:#111827;font-weight:600;width:32%;">{left_value}</td>'
                    f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:8.5pt;color:#6b7280;font-weight:500;width:18%;">{right_label}</td>'
                    f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:9pt;color:#111827;font-weight:600;width:32%;">{right_value}</td>'
                    f'</tr>'
                )
            return rows_html

        # Build result badge - minimal style
        ai_result_label = escape(ai_result_raw) if ai_result_raw else "—"
        doctor_result_label = escape(doctor_result_raw) if doctor_result_raw else "—"
        final_dx_label = escape(final_dx_raw) if final_dx_raw else "—"
        if result_raw == "No DR":
            result_badge_color = "#059669"
        elif result_raw == "Mild DR":
            result_badge_color = "#d97706"
        elif result_raw in ("Moderate DR", "Severe DR"):
            result_badge_color = "#dc2626"
        elif result_raw == "Proliferative DR":
            result_badge_color = "#991b1b"
        else:
            result_badge_color = "#6b7280"

        # ── eye result block (per-eye images + result) ────────────────────────
        def eye_result_block(eye_record: dict) -> str:
            eye_name = str(eye_record.get("eyes") or "Eye").strip() or "Eye"
            eye_result = str(eye_record.get("result") or "").strip()
            eye_conf = str(eye_record.get("confidence") or "").strip()
            if eye_conf.lower().startswith("confidence:"):
                eye_conf = eye_conf[len("confidence:"):].strip()

            src_uri = resolve_image_uri(eye_record.get("source_image_path", ""))
            heat_uri = resolve_image_uri(eye_record.get("heatmap_image_path", ""))

            def image_panel(title: str, uri: str, placeholder: str) -> str:
                if uri:
                    img_html = f'<img src="{uri}" style="width:100%;max-width:280px;height:auto;display:block;margin:0 auto;border-radius:4px;" />'
                else:
                    img_html = (
                        f'<div style="width:280px;height:280px;background:#f3f4f6;border-radius:4px;'
                        f'display:flex;align-items:center;justify-content:center;margin:0 auto;">'
                        f'<span style="font-size:8pt;color:#9ca3af;font-style:italic;text-align:center;padding:20px;">{placeholder}</span>'
                        f'</div>'
                    )
                return (
                    f'<td width="50%" valign="top" style="padding:0 8px;">'
                    f'<div style="border:1px solid #e5e7eb;border-radius:4px;background:#fafafa;padding:8px;">'
                    f'<div style="font-size:7.5pt;font-weight:600;color:#6b7280;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:8px;padding:0 4px;">{title}</div>'
                    f'<div style="padding:0;">{img_html}</div>'
                    f'</div>'
                    f'</td>'
                )

            return (
                f'<div style="border:1px solid #d1d5db;border-radius:6px;background:#ffffff;margin-bottom:14px;padding:14px 16px;">'
                f'<div style="margin-bottom:12px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'<td style="font-size:10pt;font-weight:700;color:#111827;">{escape(eye_name)}</td>'
                f'<td align="right">'
                f'<span style="font-size:8pt;color:#6b7280;font-weight:600;">Result:&nbsp;</span>'
                f'<span style="font-size:9pt;font-weight:700;color:#111827;">{escape(eye_result) if eye_result else "&#8212;"}</span>'
                f'</td>'
                f'</tr></table>'
                f'</div>'
                f'<div style="font-size:8.5pt;color:#6b7280;margin-bottom:12px;">'
                f'Confidence: <span style="font-weight:600;color:#374151;">{escape(eye_conf) if eye_conf else "&#8212;"}</span>'
                f'</div>'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'{image_panel("Fundus Photograph", src_uri, "Source image not stored")}'
                f'{image_panel("AI Attention Heatmap", heat_uri, "Heatmap not stored")}'
                f'</tr></table>'
                f'</div>'
            )

        eye_names = [str(r.get("eyes") or "").strip() for r in eye_records if str(r.get("eyes") or "").strip()]
        combined_eye_display = ", ".join(eye_names) if eye_names else str(full.get("eyes") or "")
        image_results_html = "".join(eye_result_block(r) for r in eye_records)

        # ── assemble HTML ─────────────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: 'Segoe UI', 'Calibri', Arial, sans-serif;
    font-size: 10pt;
    color: #111827;
    background: #ffffff;
    margin: 0;
    padding: 0;
    line-height: 1.5;
  }}
  table {{ border-collapse: collapse; }}
  td, div, span {{ word-break: break-word; }}
  img {{ max-width: 100%; height: auto; border: 0; }}
</style>
</head>
<body>

<!-- HEADER -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
<tr>
  <td style="padding:16px 20px;background:#f9fafb;border-bottom:3px solid #1f2937;">
    <div style="font-size:18pt;font-weight:700;color:#111827;margin-bottom:4px;">DIABETIC RETINOPATHY SCREENING REPORT</div>
    <div style="font-size:8.5pt;color:#6b7280;">
            <b>Generated:</b> {report_date} &nbsp;|&nbsp; <b>Created by:</b> {created_by}
    </div>
  </td>
</tr>
</table>

<!-- BODY -->
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:0 20px;">

  {sec("Patient Information")}
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d1d5db;margin-bottom:18px;">
  {field_grid_2col([
      ("Full Name", esc(full.get("name"))),
      ("Date of Birth", esc(full.get("birthdate"))),
      ("Age", esc(full.get("age"))),
      ("Sex", esc(full.get("sex"))),
      ("Patient ID", esc(full.get("patient_id"))),
      ("Contact", esc(full.get("contact"))),
      ("Height", height_disp),
      ("Weight", weight_disp),
      ("BMI", bmi_disp),
      ("Eye(s) Screened", esc(combined_eye_display)),
      ("Screening Date", esc(screening_date)),
      ("", "")
  ])}
  </table>

  {sec("Clinical History & Diabetes Management")}
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d1d5db;margin-bottom:18px;">
  {field_row("Diabetes Type", esc(full.get("diabetes_type")))}
  {field_row("Diagnosis Date", esc(full.get("diabetes_diagnosis_date")))}
  {field_row("Duration", dur_disp)}
  {field_row("HbA1c", esc(full.get("hba1c")))}
  {field_row("Treatment Regimen", treatment_regimen_disp)}
  {field_row("Previous DR Stage", prev_dr_stage_disp)}
  {field_row("Previous DR Treatment", esc(full.get("prev_treatment")), False)}
  </table>

  {sec("Vital Signs")}
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d1d5db;margin-bottom:18px;">
  {field_grid_2col([
      ("Blood Pressure", bp_disp),
      ("Fasting Blood Sugar", fbs_disp),
      ("Visual Acuity (Left)", va_l),
      ("Visual Acuity (Right)", va_r),
      ("Random Blood Sugar", rbs_disp),
      ("", "")
  ])}
  </table>

  {sec("Reported Symptoms")}
  <div style="padding:10px 12px;border:1px solid #d1d5db;margin-bottom:18px;background:#fafafa;">
    <div style="font-size:9pt;color:#374151;">{sym_html}</div>
  </div>

  {sec("AI Classification Result")}
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d1d5db;margin-bottom:18px;">
  {field_row("Classification", ai_result_label)}
  {field_row("Confidence", conf_display, False)}
  </table>

  {sec("Doctor Decision")}
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d1d5db;margin-bottom:18px;">
  {field_row("Doctor Classification", doctor_result_label)}
  {field_row("Decision Mode", esc(decision_mode_raw.title()))}
  {field_row("Doctor Findings", esc(doctor_findings_raw or "—"))}
  {field_row("Final Diagnosis", final_dx_label)}
  {field_row("Final Diagnosis Scale", "Based on ICDR Severity Scale", False)}
  </table>
"""
        if decision_mode_raw == "override":
            html += f"""
  <div style="padding:10px 12px;border:1px solid #fecaca;margin-bottom:18px;background:#fff1f2;">
    <div style="font-size:8.5pt;color:#7f1d1d;">
      <b>Override Justification:</b> {esc(override_reason_raw or "No justification provided")}
    </div>
  </div>
"""
        html += f"""

  {sec("Image Results")}
  {image_results_html}

  {sec("Clinical Analysis")}
  <div style="padding:14px;border:1px solid #d1d5db;background:#f9fafb;margin-bottom:18px;">
    <div style="font-size:8pt;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Clinical Recommendation</div>
    <div style="font-size:9.5pt;color:#111827;font-weight:600;line-height:1.6;margin-bottom:14px;">&rarr; {rec}</div>
        <div style="font-size:8.8pt;color:#374151;font-weight:600;margin-bottom:10px;">Referral Destination: <span style="font-weight:700;color:#111827;">{referral_destination}</span></div>
    <div style="border-top:1px solid #d1d5db;padding-top:12px;margin-top:12px;">
      <div style="font-size:9.5pt;color:#374151;line-height:1.75;">{summary}</div>
    </div>
  </div>

  {sec("Clinical Notes")}
  <div style="padding:12px;border:1px solid #d1d5db;background:#fafafa;margin-bottom:18px;min-height:50px;">
    <div style="font-size:9pt;color:#4b5563;font-style:italic;line-height:1.65;">{notes_disp}</div>
  </div>

  <!-- FOOTER -->
  <div style="margin-top:24px;padding-top:14px;border-top:2px solid #e5e7eb;">
    <div style="font-size:7.5pt;color:#9ca3af;line-height:1.8;">
            <b>Created by:</b> {created_by}<br>
            <b>Finalized by:</b> {finalized_by}<br>
            <b>Generated:</b> {report_date}<br>
      <i>This report is AI-assisted and does not replace the judgment of a licensed eye care professional. All findings must be reviewed and confirmed by a qualified healthcare professional before any clinical action is taken.</i>
    </div>
  </div>

</td></tr>
</table>

</body>
</html>"""

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html)

        writer = QPdfWriter(path)
        writer.setResolution(150)
        try:
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        except Exception:
            pass
        try:
            writer.setPageMargins(QMarginsF(14, 10, 14, 16), QPageLayout.Unit.Millimeter)
        except Exception:
            pass

        doc.print_(writer)
        self.status_label.setText(f"Report saved: {os.path.basename(path)}")
        UserManager.add_activity_log(
            self.username,
            (
                f"REPORT_GENERATED patient_id={full.get('patient_id')}; "
                f"record_id={full.get('id')}; "
                f"created_by={created_by_raw or finalized_by_raw}; "
                f"finalized_by={finalized_by_raw}; "
                f"file={os.path.basename(path)}"
            ),
        )
        QMessageBox.information(self, "Report Saved", f"Patient report saved to:\n{path}")

    def generate_referral(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Generate Referral", "Select a patient record to generate a referral letter.")
            return

        full = self._fetch_full_record(record["id"]) or record
        result_raw = str(full.get("result") or "").strip()

        if result_raw in ("No DR", "Mild DR"):
            confirm = QMessageBox.question(
                self,
                "Generate Referral",
                "This result is usually not urgent for specialist referral. Generate referral letter anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        selected_destination = self._prompt_referral_destination()
        if selected_destination is None:
            return

        patient_name_raw = str(full.get("name") or "Patient").strip()
        default_name = f"EyeShield_Referral_{patient_name_raw}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save Referral Letter", default_name, "PDF Files (*.pdf)")
        if not path:
            return

        try:
            from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QTextDocument
            from PySide6.QtCore import QMarginsF
        except ImportError:
            QMessageBox.warning(self, "Generate Referral", "PDF generation requires PySide6 PDF support.")
            return

        def esc(v) -> str:
            s = str(v or "").strip()
            return escape(s) if s and s not in ("0", "None", "Select", "-") else "&#8212;"

        def _to_long_date(value: str) -> str:
            raw = str(value or "").strip()
            if not raw:
                return ""
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%B %d, %Y",
            ):
                try:
                    return datetime.strptime(raw, fmt).strftime("%B %d, %Y")
                except ValueError:
                    continue
            return raw

        referral_map = {
            "No DR": ("Routine", "Annual follow-up and routine retinal screening."),
            "Mild DR": ("Routine", "Repeat retinal assessment in 6-12 months is advised."),
            "Moderate DR": ("Priority", "Refer to ophthalmology within 3 months for specialist evaluation."),
            "Severe DR": ("Urgent", "Urgent ophthalmology review is advised due to high progression risk."),
            "Proliferative DR": ("Immediate", "Immediate specialist referral is required for potential sight-threatening disease."),
        }
        urgency, rationale = referral_map.get(result_raw, ("Clinical Review", "Please evaluate for diabetic retinopathy management."))

        report_date = datetime.now().strftime("%B %d, %Y")
        profile = UserManager.get_user_profile(self.username) or {}
        finalized_by_raw = str(profile.get("full_name") or self.display_name or os.environ.get("EYESHIELD_CURRENT_NAME", "") or self.username).strip()
        created_by_raw = str(full.get("original_screener_name") or full.get("original_screener_username") or "").strip()
        created_by_label = self._format_doctor_label(created_by_raw or finalized_by_raw)
        finalized_by_label = self._format_doctor_label(finalized_by_raw)

        destination_name = esc(selected_destination.get("hospital_name"))
        destination_dept = esc(selected_destination.get("department"))
        destination_contact = esc(selected_destination.get("contact_person"))

        # Get doctor's contact info (email preferred, fallback to phone/contact)
        doctor_contact = str(profile.get("contact") or "").strip()

        screen_date_text = esc(_to_long_date(full.get("screened_at") or report_date))
        patient_name = esc(full.get("name"))
        patient_age = esc(full.get("age"))
        patient_sex = esc(full.get("sex"))
        patient_hba1c = esc(full.get("hba1c"))
        patient_diabetes_type = esc(full.get("diabetes_type"))
        patient_height = esc(full.get("height"))
        patient_weight = esc(full.get("weight"))
        patient_bmi = esc(full.get("bmi"))
        patient_visual_acuity_left = esc(full.get("visual_acuity_left"))
        patient_visual_acuity_right = esc(full.get("visual_acuity_right"))
        patient_notes = esc(full.get("notes"))

        referral_image_uri = ""
        image_path = str(full.get("source_image_path") or "").strip()
        if image_path and os.path.exists(image_path):
            referral_image_uri = Path(image_path).resolve().as_uri()
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset=\"utf-8\">
<style>
  body {{
        font-family: 'Times New Roman', 'Georgia', serif;
        font-size: 11pt;
        color: #1f2937;
    margin: 0;
    padding: 0;
        line-height: 1.6;
  }}
    .sheet {{ padding: 26px 36px; }}
    .page-break {{ page-break-before: always; }}
    .header-grid {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; }}
    .header-grid td {{ width: 100%; vertical-align: top; padding: 0; }}
    .header-block {{ font-size: 10.8pt; line-height: 1.65; }}
    .date-line {{ font-size: 10.8pt; line-height: 1.65; margin-bottom: 8px; }}
    .label {{ font-weight: 700; }}
    .subject {{ margin: 14px 0 14px 0; font-size: 11.5pt; font-weight: 700; }}
    .paragraph {{ margin: 0 0 12px 0; text-align: justify; line-height: 1.7; }}
    .patient-box {{
        border: 1px solid #d1d5db;
        background: #fafafa;
        padding: 12px 14px;
        margin: 16px 0 16px 0;
    }}
    .patient-box table {{ width: 100%; border-collapse: collapse; }}
    .patient-box td {{ padding: 5px 0; vertical-align: top; font-size: 10pt; line-height: 1.6; }}
    .closing {{ margin-top: 24px; }}
    .signature-line {{ margin-top: 34px; border-top: 1px solid #374151; width: 260px; }}
    .image-box {{ border: 1px solid #d1d5db; background: #fafafa; padding: 12px 14px; margin: 10px 0 16px 0; }}
    .image-caption {{ font-size: 9pt; color: #4b5563; margin-top: 8px; text-align: center; }}
</style>
</head>
<body>

<div class=\"sheet\">
    <div class=\"date-line\"><span class=\"label\">Date:</span> {esc(report_date)}</div>
    <table class=\"header-grid\">
        <tr>
            <td>
                <div class=\"header-block\"><span class=\"label\">To:</span> {destination_name}</div>
                <div class=\"header-block\"><span class=\"label\">Department:</span> {destination_dept}</div>
                <div class=\"header-block\"><span class=\"label\">Attention:</span> {destination_contact}</div>
            </td>
        </tr>
    </table>

    <div class=\"subject\">Subject: Referral for Ophthalmology Evaluation - {patient_name}</div>

    <div class=\"paragraph\">Dear Colleague,</div>

    <div class=\"paragraph\">
        I am referring this patient for specialist ophthalmology assessment following diabetic retinopathy screening.
        The current screening result indicates <b>{esc(result_raw)}</b> with <b>{esc(urgency)}</b> referral priority.
        Screening was performed on {screen_date_text}.
    </div>

    <div class=\"patient-box\">
        <table>
            <tr>
                <td style=\"width:50%;\"><span class=\"label\">Patient Name:</span> {patient_name}</td>
                <td><span class=\"label\">Age / Sex:</span> {patient_age} / {patient_sex}</td>
            </tr>
            <tr>
                <td><span class=\"label\">Diabetes Type:</span> {patient_diabetes_type}</td>
                <td><span class=\"label\">HbA1c:</span> {patient_hba1c}</td>
            </tr>
            <tr>
                <td><span class=\"label\">Height:</span> {patient_height}</td>
                <td><span class=\"label\">Weight:</span> {patient_weight}</td>
            </tr>
            <tr>
                <td><span class=\"label\">BMI:</span> {patient_bmi}</td>
                <td><span class=\"label\">Visual Acuity:</span> {patient_visual_acuity_left} / {patient_visual_acuity_right}</td>
            </tr>
            <tr>
                <td colspan=\"2\"><span class=\"label\">Clinical History & Symptoms:</span> {patient_notes}</td>
            </tr>
            <tr>
                <td colspan=\"2\"><span class=\"label\">Referral Reason:</span> {esc(rationale)}</td>
            </tr>
        </table>
    </div>

    <div class=\"paragraph\">
        Kindly perform comprehensive ophthalmic evaluation and initiate management as
        clinically indicated. Please provide recommendations and follow-up plan after
        assessment. If you need to reach me, contact me at {esc(doctor_contact)}.
    </div>

    <div class=\"closing\">
        <div style=\"margin-bottom:8px;\">Sincerely,</div>
        <div class=\"signature-line\"></div>
        <div style="margin-top:8px;"><b>{esc(finalized_by_label)}</b></div>
        <div style=\"font-size:10pt;color:#4b5563;\">Referring Clinician</div>
    </div>
</div>

<div class="page-break"></div>

<div class="sheet">
    <div class="subject">Fundus Image Captured</div>
    <div class="paragraph">
        The following retinal fundus image was captured during this screening encounter and is attached for specialist reference.
    </div>
    <div class="image-box">
        <div style="text-align:center;background:#ffffff;padding:8px;border:1px solid #e5e7eb;">
            {f'<img src="{referral_image_uri}" style="max-width:100%;max-height:560px;width:auto;height:auto;" />' if referral_image_uri else '<div style="padding:80px 20px;color:#9ca3af;font-style:italic;">Fundus image not available</div>'}
        </div>
        <div class="image-caption">Captured fundus image</div>
    </div>
    <div style="font-size:10pt;color:#4b5563;margin-top:20px;line-height:1.8;">
        <span><b>Created by:</b> {esc(created_by_label)}</span><br>
        <span><b>Finalized by:</b> {esc(finalized_by_label)}</span>
    </div>
</div>

</body>
</html>"""

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html)

        writer = QPdfWriter(path)
        writer.setResolution(150)
        try:
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        except Exception:
            pass
        try:
            writer.setPageMargins(QMarginsF(14, 10, 14, 16), QPageLayout.Unit.Millimeter)
        except Exception:
            pass

        doc.print_(writer)
        self.status_label.setText(f"Referral saved: {os.path.basename(path)}")
        UserManager.add_activity_log(
            self.username,
            (
                f"REFERRAL_GENERATED patient_id={full.get('patient_id')}; "
                f"record_id={full.get('id')}; "
                f"created_by={created_by_raw or finalized_by_raw}; "
                f"finalized_by={finalized_by_raw}; "
                f"file={os.path.basename(path)}"
            ),
        )
        QMessageBox.information(self, "Referral Saved", f"Referral letter saved to:\n{path}")
        
        # Ask if user wants to assign referral to a clinician
        assign_reply = QMessageBox.question(
            self,
            "Assign Referral",
            "Do you want to assign this referral to a clinician for follow-up?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        
        if assign_reply == QMessageBox.StandardButton.Yes:
            try:
                from login import AssignReferralDialog
            except ImportError:
                from .login import AssignReferralDialog
            
            dialog = AssignReferralDialog(patient_name_raw, self, exclude_username=self.username)
            if dialog.exec() == QDialog.Accepted:
                if dialog.selected_clinician == self.username:
                    QMessageBox.warning(self, "Error", "You cannot assign a referral to yourself.")
                    return
                # Create referral assignment
                referral_id = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{full.get('id', 'NA')}"
                success = UserManager.assign_referral(
                    referral_id=referral_id,
                    assigned_to_username=dialog.selected_clinician,
                    assigned_by_username=self.username,
                    patient_name=patient_name_raw,
                    urgency=dialog.urgency_level,
                    notes=f"Generated from patient record ID: {full.get('id', 'N/A')}"
                )
                if success:
                    QMessageBox.information(
                        self,
                        "Referral Assigned",
                        f"Referral has been assigned to the clinician for follow-up."
                    )
                    self.status_label.setText("Referral assigned successfully")
                else:
                    QMessageBox.warning(self, "Error", "Failed to assign referral. It may already be assigned.")
