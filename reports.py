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
    QFileDialog, QDialog, QMessageBox, QMenu,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon

from auth import DB_FILE


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
        subtitle = QLabel("Review archived screenings and restore them back into the active dashboard and reports.")
        subtitle.setStyleSheet("font-size:13px;color:#6c757d;")
        subtitle.setWordWrap(True)
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
            self.table.setItem(i, 0, item)
            self.table.setItem(i, 1, QTableWidgetItem(str(row["name"] or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["result"] or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(row["archived_at"] or "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(row["archived_by"] or "")))
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
            QWidget{background:#f8f9fa;color:#212529;font-family:'Calibri','Inter','Arial';}
            QGroupBox{background:#fff;border:1px solid #dee2e6;border-radius:8px;}
            QLineEdit,QComboBox,QTableWidget{background:#fff;border:1px solid #ced4da;border-radius:8px;}
            QPushButton:focus,QTableWidget:focus{border:1px solid #0d6efd;}
            QPushButton{background:#e9ecef;color:#212529;border:1px solid #ced4da;border-radius:8px;padding:8px 16px;font-weight:600;}
            QPushButton:hover{background:#dee2e6;}
            QPushButton#primaryAction{background:#0d6efd;color:#fff;border:1px solid #0b5ed7;border-radius:8px;padding:8px 16px;font-weight:600;}
            QLabel#statusLabel{color:#495057;font-size:12px;}
            QLabel#hintLabel{color:#6c757d;font-size:12px;}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        self._rep_title_lbl = QLabel("DR Screening Reports")
        self._rep_title_lbl.setObjectName("pageHeader")
        self._rep_title_lbl.setStyleSheet("font-size:24px;font-weight:700;color:#007bff;font-family:'Calibri','Inter','Arial';")
        self._rep_subtitle_lbl = QLabel("")
        self._rep_subtitle_lbl.setObjectName("pageSubtitle")
        self._rep_subtitle_lbl.setStyleSheet("font-size:13px;color:#6c757d;")

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
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
        root.addLayout(top_bar)

        self._rep_subtitle_lbl.setVisible(False)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        self._controls_group = QGroupBox("")
        cl = QHBoxLayout(self._controls_group)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by patient ID, name, eye screened, result, or confidence")
        self.search_input.setMinimumHeight(36)
        self.search_input.textChanged.connect(self.apply_filters)
        cl.addWidget(self.search_input, 1)
        self.result_filter = QComboBox()
        self.result_filter.addItems(["All","No DR","Mild DR","Moderate DR","Severe DR","Proliferative DR"])
        self.result_filter.setMinimumHeight(36)
        self.result_filter.currentTextChanged.connect(self.apply_filters)
        cl.addWidget(self.result_filter)
        self.filtered_count_label = QLabel("Total: 0")
        self.filtered_count_label.setObjectName("hintLabel")
        self.filtered_count_label.setStyleSheet("color:#6c757d;font-size:12px;background:transparent;border:none;padding:0;margin:0;")
        cl.addWidget(self.filtered_count_label)
        root.addWidget(self._controls_group)

        self._results_group = QGroupBox("")
        rl = QVBoxLayout(self._results_group)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(12)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(["Patient ID","Name","Eye Screened","Screening Date","Result","Confidence"])
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self._update_action_buttons)
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._open_results_context_menu)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        rl.addWidget(self.results_table)
        root.addWidget(self._results_group)

        self.setTabOrder(self.export_btn, self.report_btn)
        self.setTabOrder(self.report_btn, self.search_input)
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
        self.export_btn.setText("Export")
        self.report_btn.setText("Report")
        self.export_btn.setToolTip("Export currently visible report rows to CSV")
        self.report_btn.setToolTip("Generate a detailed PDF report for the selected patient")
        if self.archived_records_btn is not None:
            self._set_button_icon(self.archived_records_btn, "archives.svg")
            self.archived_records_btn.setText("Archived Records")
            self.archived_records_btn.setToolTip("Open archived records and restore or delete entries")
        if self.archive_btn is not None:
            self._set_button_icon(self.archive_btn, "archive.svg")
            self.archive_btn.setText("Archive")
            self.archive_btn.setToolTip("Archive the selected active patient record")

        top_icon_buttons = [self.export_btn, self.report_btn]
        if self.archive_btn is not None:
            top_icon_buttons.append(self.archive_btn)
        if self.archived_records_btn is not None:
            top_icon_buttons.append(self.archived_records_btn)

        for button in top_icon_buttons:
            button.setMinimumHeight(34)
            button.setStyleSheet(
                "QPushButton{background:#0d6efd;color:#ffffff;border:1px solid #0b5ed7;border-radius:8px;padding:6px 10px;font-weight:600;}"
                "QPushButton:hover{background:#0b5ed7;}"
                "QPushButton:disabled{background:#6ea8fe;border:1px solid #6ea8fe;}"
            )

    def refresh_report(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, patient_id, name, eyes, screened_at, result, confidence, diabetes_type, hba1c,
                       archived_at, archived_by, archive_reason
                FROM patient_records ORDER BY id DESC
            """)
            rows = [{"id":r[0],"patient_id":r[1],"name":r[2],"eyes":r[3],"screened_at":r[4],"result":r[5],"confidence":r[6],
                     "diabetes_type":r[7],"hba1c":r[8],"archived_at":r[9],"archived_by":r[10],"archive_reason":r[11]}
                    for r in cur.fetchall()]
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
            self.status_label.setText(f"Updated {len(active)} active and {archived_count} archived records at {datetime.now().strftime('%H:%M:%S')}")
        else:
            self.status_label.setText(f"Updated {len(active)} screenings at {datetime.now().strftime('%H:%M:%S')}")

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
            record_ids = [int(item.get("id") or 0) for item in ordered_rows if int(item.get("id") or 0)]
            selection_key = f"{key[0]}|{key[1]}|{'-'.join(str(i) for i in record_ids)}"
            eyes_text = "\n".join(str(item.get("eyes") or "—") for item in ordered_rows)
            date_text = "\n".join(str(item.get("screened_at") or "—") for item in ordered_rows)
            result_text = "\n".join(str(item.get("result") or "—") for item in ordered_rows)
            confidence_text = "\n".join(str(item.get("confidence") or "—") for item in ordered_rows)
            combined_search = " ".join(
                [
                    str(primary.get("patient_id") or ""),
                    str(primary.get("name") or ""),
                    eyes_text,
                    date_text,
                    result_text,
                    confidence_text,
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
                    "diabetes_type": primary.get("diabetes_type"),
                    "hba1c": primary.get("hba1c"),
                    "archived_at": primary.get("archived_at"),
                    "archived_by": primary.get("archived_by"),
                    "archive_reason": primary.get("archive_reason"),
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
            self.results_table.setItem(i, 0, item)
            self.results_table.setItem(i, 1, QTableWidgetItem(str(row["name"] or "")))
            self.results_table.setItem(i, 2, QTableWidgetItem(str(row.get("eyes") or "")))
            self.results_table.setItem(i, 3, QTableWidgetItem(str(row.get("screened_at") or "")))
            ri = QTableWidgetItem(str(row["result"] or ""))
            if any(self._is_high_attention_result(item.get("result")) for item in (row.get("source_rows") or [])):
                ri.setForeground(result_color("high"))
            elif all("no dr" in str(item.get("result") or "").lower() for item in (row.get("source_rows") or [])):
                ri.setForeground(result_color("normal"))
            self.results_table.setItem(i, 4, ri)
            self.results_table.setItem(i, 5, QTableWidgetItem(str(row["confidence"] or "")))
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

    def _open_results_context_menu(self, pos):
        item = self.results_table.itemAt(pos)
        if item is None:
            return
        self.results_table.selectRow(item.row())
        record = self._get_selected_record()
        if not record:
            return

        menu = QMenu(self)
        generate_action = menu.addAction("Generate Report")
        archive_action = None
        if self.is_admin:
            archive_action = menu.addAction("Archive Record")
            archive_action.setEnabled(not bool(record.get("archived_at")))

        chosen = menu.exec(self.results_table.viewport().mapToGlobal(pos))
        if chosen == generate_action:
            self.generate_report()
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
        if self.is_admin:
            self.archive_btn.setEnabled(bool(record and not record["archived_at"]))

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
            if archived:
                placeholders = ",".join("?" for _ in valid_ids)
                cur.execute(
                    f"UPDATE patient_records SET archived_at=?,archived_by=?,archive_reason=? WHERE id IN ({placeholders})",
                    [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor, None, *valid_ids],
                )
            else:
                placeholders = ",".join("?" for _ in valid_ids)
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
                w.writerow(["Patient ID","Name","Eye Screened","Screening Date","Result","Confidence","Diabetes Type","HbA1c","Record Status","Archived At","Archived By"])
                for row in self._filtered_rows:
                    w.writerow([row["patient_id"],row["name"],row.get("eyes", ""),row.get("screened_at", ""),row["result"],row["confidence"],
                                row["diabetes_type"],row["hba1c"],
                                "Archived" if row["archived_at"] else "Active",
                                row["archived_at"],row["archived_by"]])
            self.status_label.setText(f"Exported {len(self._filtered_rows)} rows to {path}")
        except OSError as err:
            QMessageBox.warning(self, "Export", f"Failed to export summary: {err}")

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._rep_title_lbl.setText(pack["rep_title"])
        self._rep_subtitle_lbl.setText("")
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
                       visual_acuity_left, visual_acuity_right,
                       blood_pressure_systolic, blood_pressure_diastolic,
                       fasting_blood_sugar, random_blood_sugar,
                       symptom_blurred_vision, symptom_floaters,
                      symptom_flashes, symptom_vision_loss,
                      source_image_path, heatmap_image_path,
                      image_sha256, image_saved_at
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
                "va_left":row[16],"va_right":row[17],
                "bp_systolic":row[18],"bp_diastolic":row[19],
                "fbs":row[20],"rbs":row[21],
                "symptom_blurred":row[22],"symptom_floaters":row[23],
                "symptom_flashes":row[24],"symptom_vision_loss":row[25],
                "source_image_path":row[26],"heatmap_image_path":row[27],
                "image_sha256":row[28],"image_saved_at":row[29],
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
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
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
        result_raw = str(full.get("result") or "").strip()

        GRADE_META = {
            "No DR":            {"color": "#166534", "bg": "#f0fdf4", "border": "#16a34a", "badge_bg": "#15803d",
                                 "rec": "Annual screening recommended.",
                                 "summary": "No signs of diabetic retinopathy were detected in this fundus image. Continue standard diabetes management, maintain optimal glycaemic and blood pressure control, and schedule routine annual retinal screening."},
            "Mild DR":          {"color": "#92400e", "bg": "#fefce8", "border": "#d97706", "badge_bg": "#b45309",
                                 "rec": "Repeat screening in 6&#8211;12 months.",
                                 "summary": "Early microaneurysms consistent with mild non-proliferative diabetic retinopathy (NPDR) were identified. Intensify glycaemic and blood pressure management. A repeat retinal examination in 6&#8211;12 months is recommended."},
            "Moderate DR":      {"color": "#7c2d12", "bg": "#fff7ed", "border": "#ea580c", "badge_bg": "#c2410c",
                                 "rec": "Ophthalmology referral within 3 months.",
                                 "summary": "Features consistent with moderate non-proliferative diabetic retinopathy (NPDR) were detected, including microaneurysms, haemorrhages, and/or hard exudates. Referral to an ophthalmologist within 3 months is advised. Reassess systemic metabolic control."},
            "Severe DR":        {"color": "#ffffff", "bg": "#7f1d1d", "border": "#991b1b", "badge_bg": "#450a0a",
                                 "rec": "Urgent ophthalmology referral required.",
                                 "summary": "Findings consistent with severe non-proliferative diabetic retinopathy (NPDR) were detected. The risk of progression to proliferative disease within 12 months is high. Urgent ophthalmology referral is required."},
            "Proliferative DR": {"color": "#ffffff", "bg": "#6b1a1a", "border": "#7f1d1d", "badge_bg": "#3b0606",
                                 "rec": "Immediate ophthalmology referral required.",
                                 "summary": "Proliferative diabetic retinopathy (PDR) was detected &#8212; a sight-threatening condition. Immediate ophthalmology referral is required for evaluation and potential intervention, such as laser photocoagulation or intravitreal anti-VEGF therapy."},
        }
        meta = GRADE_META.get(result_raw, {
            "color": "#1e3a5f", "bg": "#f0f4ff", "border": "#2563eb", "badge_bg": "#1d4ed8",
            "rec": "Consult a qualified ophthalmologist.",
            "summary": "Please consult a qualified ophthalmologist for further evaluation.",
        })
        gc        = meta["color"]
        gbg       = meta["bg"]
        gb        = meta["border"]
        rec       = meta["rec"]
        summary   = meta["summary"]
        badge_bg  = meta["badge_bg"]
        is_dark_card = result_raw in ("Severe DR", "Proliferative DR")
        divider_color = "rgba(255,255,255,0.3)" if is_dark_card else gb

        report_date    = datetime.now().strftime("%B %d, %Y  %I:%M %p")
        screening_date = str(full.get("screened_at") or "").strip() or report_date

        screened_by_name  = str(self.display_name or os.environ.get("EYESHIELD_CURRENT_NAME", "") or self.username).strip()
        screened_by_title = str(self.display_title or os.environ.get("EYESHIELD_CURRENT_TITLE", "")).strip()
        screened_by_raw   = (f"{screened_by_name} ({screened_by_title})" if screened_by_name and screened_by_title else screened_by_name)
        screened_by       = escape(screened_by_raw) if screened_by_raw else "&#8212;"

        dur_raw  = str(full.get("duration") or "").strip()
        dur_disp = f"{escape(dur_raw)} year(s)" if dur_raw and dur_raw != "0" else "&#8212;"

        notes_raw  = str(full.get("notes") or "").strip()
        notes_disp = escape(notes_raw) if notes_raw else '<span style="color:#9ca3af;font-style:italic;">None recorded</span>'

        bp_s    = str(full.get("bp_systolic") or "").strip()
        bp_d    = str(full.get("bp_diastolic") or "").strip()
        bp_disp = f"{escape(bp_s)}/{escape(bp_d)} mmHg" if bp_s and bp_s != "0" and bp_d and bp_d != "0" else "&#8212;"
        va_l    = esc(full.get("va_left"))
        va_r    = esc(full.get("va_right"))
        fbs_r   = str(full.get("fbs") or "").strip()
        rbs_r   = str(full.get("rbs") or "").strip()
        fbs_disp = f"{escape(fbs_r)} mg/dL" if fbs_r and fbs_r != "0" else "&#8212;"
        rbs_disp = f"{escape(rbs_r)} mg/dL" if rbs_r and rbs_r != "0" else "&#8212;"

        sym_map = [
            ("symptom_blurred",     "Blurred Vision"),
            ("symptom_floaters",    "Floaters"),
            ("symptom_flashes",     "Flashes"),
            ("symptom_vision_loss", "Vision Loss"),
        ]
        active_syms = [lbl for k, lbl in sym_map if str(full.get(k) or "").strip().lower() in ("true", "1", "yes", "checked")]
        sym_html = (
            "".join(
                f'<span style="display:inline-block;background:#fee2e2;color:#991b1b;'
                f'border:1px solid #fca5a5;border-radius:6px;padding:3px 10px;'
                f'font-size:8pt;font-weight:700;margin:2px 4px 2px 0;">{escape(s)}</span>'
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
                f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0 10px 0;">'
                f'<tr>'
                f'<td width="4" bgcolor="#2563eb">&nbsp;</td>'
                f'<td width="8">&nbsp;</td>'
                f'<td style="font-size:8pt;font-weight:bold;color:#1e3a5f;letter-spacing:1.5px;'
                f'text-transform:uppercase;white-space:nowrap;">{title}</td>'
                f'<td width="12">&nbsp;</td>'
                f'<td style="border-bottom:2px solid #dbeafe;">&nbsp;</td>'
                f'</tr>'
                f'</table>'
            )

        # ── info table helpers ────────────────────────────────────────────────
        def info_cell(label: str, value: str, bg: str = "#ffffff") -> str:
            return (
                f'<td bgcolor="{bg}" style="padding:10px 16px;border:1px solid #e5e7eb;vertical-align:top;width:25%;">'
                f'<div style="font-size:7pt;font-weight:bold;color:#6b7280;letter-spacing:1px;'
                f'text-transform:uppercase;margin-bottom:5px;">{label}</div>'
                f'<div style="font-size:10pt;font-weight:600;color:#111827;line-height:1.4;">{value}</div>'
                f'</td>'
            )

        def info_row(cells: list, bg: str = "#ffffff") -> str:
            return "<tr>" + "".join(info_cell(lbl, val, bg) for lbl, val in cells) + "</tr>"

        # ── vitals row helper ─────────────────────────────────────────────────
        def vrow(label: str, value: str) -> str:
            return (
                f'<tr>'
                f'<td style="padding:9px 14px;font-size:9pt;color:#374151;border-bottom:1px solid #f3f4f6;">{label}</td>'
                f'<td style="padding:9px 14px;font-size:9pt;color:#111827;font-weight:700;'
                f'text-align:right;border-bottom:1px solid #f3f4f6;">{value}</td>'
                f'</tr>'
            )

        # ── eye result block (per-eye images + result) ────────────────────────
        def eye_result_block(eye_record: dict) -> str:
            eye_name   = str(eye_record.get("eyes") or "Eye").strip() or "Eye"
            eye_result = str(eye_record.get("result") or "").strip()
            eye_conf   = str(eye_record.get("confidence") or "").strip()
            if eye_conf.lower().startswith("confidence:"):
                eye_conf = eye_conf[len("confidence:"):].strip()
            eye_meta   = GRADE_META.get(eye_result, meta)
            e_bg       = eye_meta["bg"]
            e_border   = eye_meta["border"]
            e_col      = eye_meta["color"]

            src_uri  = resolve_image_uri(eye_record.get("source_image_path", ""))
            heat_uri = resolve_image_uri(eye_record.get("heatmap_image_path", ""))

            def image_panel(title: str, uri: str, placeholder: str) -> str:
                if uri:
                    img_html = (
                        f'<img src="{uri}" '
                        f'style="width:100%;max-width:220px;height:auto;display:block;margin:0 auto;" />'
                    )
                else:
                    img_html = (
                        f'<table width="220" cellpadding="0" cellspacing="0" align="center">'
                        f'<tr><td height="180" bgcolor="#f3f4f6" align="center" valign="middle" '
                        f'style="border-radius:6px;">'
                        f'<div style="font-size:8pt;color:#9ca3af;font-style:italic;padding:12px;">'
                        f'{placeholder}</div>'
                        f'</td></tr></table>'
                    )
                return (
                    f'<td width="50%" valign="top" style="padding:0 6px;">'
                    f'<table width="100%" cellpadding="0" cellspacing="0" '
                    f'style="border:1px solid #e5e7eb;border-radius:8px;background:#fafafa;">'
                    f'<tr><td bgcolor="#1e3a5f" style="padding:7px 12px;">'
                    f'<span style="font-size:7.5pt;font-weight:bold;color:#93c5fd;'
                    f'letter-spacing:1px;text-transform:uppercase;">{title}</span>'
                    f'</td></tr>'
                    f'<tr><td align="center" style="padding:10px 8px 12px;">'
                    f'{img_html}'
                    f'</td></tr>'
                    f'</table>'
                    f'</td>'
                )

            return (
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="border:2px solid {e_border};border-radius:10px;'
                f'background:{e_bg};margin-bottom:14px;">'
                # Eye header
                f'<tr><td style="padding:12px 16px 10px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'<td>'
                f'<div style="font-size:11pt;font-weight:800;color:#0f172a;">{escape(eye_name)}</div>'
                f'</td>'
                f'<td align="right">'
                f'<span style="background:{e_border};color:#ffffff;font-size:8pt;font-weight:700;'
                f'padding:3px 10px;border-radius:20px;">{escape(eye_result) if eye_result else "&#8212;"}</span>'
                f'</td>'
                f'</tr></table>'
                f'</td></tr>'
                # Confidence bar
                f'<tr><td style="padding:0 16px 10px;">'
                f'<span style="font-size:9pt;color:{e_col};font-weight:600;">'
                f'Confidence:&nbsp;<strong>{escape(eye_conf) if eye_conf else "&#8212;"}</strong>'
                f'</span>'
                f'</td></tr>'
                # Images side by side
                f'<tr><td style="padding:0 10px 14px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'{image_panel("Fundus Photograph", src_uri, "Source image not stored in this record")}'
                f'{image_panel("AI Attention Heatmap", heat_uri, "Heatmap not stored in this record")}'
                f'</tr></table>'
                f'</td></tr>'
                f'</table>'
            )

        eye_names            = [str(r.get("eyes") or "").strip() for r in eye_records if str(r.get("eyes") or "").strip()]
        combined_eye_display = ", ".join(eye_names) if eye_names else str(full.get("eyes") or "")
        image_results_html   = "".join(eye_result_block(r) for r in eye_records)

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

<!-- ═══════════════════════════════════════════════════════════ HEADER -->
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
  <td bgcolor="#0a2540" style="padding:18px 28px 14px;">
    <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td>
        <div style="font-size:22pt;font-weight:900;color:#ffffff;letter-spacing:0.5px;">
          Patient Screening Report
        </div>
        <div style="font-size:9pt;color:#94a3b8;margin-top:3px;">{escape(clinic_name)}</div>
      </td>
      <td align="right" valign="middle">
        <div style="background:#1e3a5f;border-radius:8px;padding:10px 16px;display:inline-block;">
          <div style="font-size:7.5pt;color:#93c5fd;font-weight:bold;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">Report Generated</div>
          <div style="font-size:9pt;color:#e2e8f0;font-weight:600;">{report_date}</div>
        </div>
      </td>
    </tr>
    </table>
  </td>
</tr>
<tr>
  <td bgcolor="#0d2d4a" style="padding:8px 28px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:8.5pt;color:#94a3b8;">
        <b style="color:#cbd5e1;">Screened by:</b>&nbsp;{screened_by}
      </td>
      <td align="right" style="font-size:8.5pt;color:#94a3b8;">
        <b style="color:#cbd5e1;">Screening date:</b>&nbsp;{escape(screening_date)}
      </td>
    </tr></table>
  </td>
</tr>
<!-- accent stripe -->
<tr><td height="4" bgcolor="#2563eb"></td></tr>
</table>

<!-- ═══════════════════════════════════════════════════════════ BODY -->
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:6px 20px 20px;">

  {sec("Patient Information")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
  {info_row([("Full Name", esc(full.get("name"))), ("Date of Birth", esc(full.get("birthdate"))),
             ("Age", esc(full.get("age"))), ("Sex", esc(full.get("sex")))], "#ffffff")}
  {info_row([("Record No.", esc(full.get("patient_id"))), ("Contact", esc(full.get("contact"))),
             ("Eye(s) Screened", esc(combined_eye_display)), ("Screening Date", esc(screening_date))], "#f8fafc")}
  </table>

  {sec("AI Classification Result")}
  <!-- Result card -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:2px solid {gb};border-radius:10px;background:{gbg};">
  <tr>
    <td style="padding:18px 22px;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td valign="top" width="60%">
          <!-- badge -->
          <div style="display:inline-block;background:{badge_bg};color:#ffffff;
                      font-size:7pt;font-weight:bold;letter-spacing:1.2px;
                      text-transform:uppercase;padding:4px 11px;border-radius:20px;
                      margin-bottom:10px;">AI Classification</div>
          <!-- grade -->
          <div style="font-size:18pt;font-weight:900;color:{gc};line-height:1.2;margin-bottom:6px;">
            {escape(result_raw) if result_raw else "&#8212;"}
          </div>
          <!-- confidence -->
          <div style="font-size:9.5pt;color:{gc};margin-bottom:14px;opacity:0.9;">
            Confidence:&nbsp;<strong>{conf_display}</strong>
          </div>
          <!-- divider -->
          <div style="border-top:1px solid {divider_color};margin-bottom:12px;"></div>
          <!-- recommendation label -->
          <div style="font-size:7pt;font-weight:bold;color:{gc};letter-spacing:1px;
                      text-transform:uppercase;margin-bottom:5px;opacity:0.85;">
            Clinical Recommendation
          </div>
          <div style="font-size:10pt;font-weight:700;color:{gc};line-height:1.5;">
            &#8594;&nbsp;{rec}
          </div>
        </td>
        <!-- right column: vitals card -->
        <td valign="top" width="4%" style="padding:0 10px;"></td>
        <td valign="top" width="36%">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;overflow:hidden;">
          <tr><td bgcolor="#1e3a5f" style="padding:8px 14px;">
            <span style="font-size:7.5pt;font-weight:bold;color:#93c5fd;
                         letter-spacing:1.2px;text-transform:uppercase;">Vital Signs</span>
          </td></tr>
          <tr><td>
            <table width="100%" cellpadding="0" cellspacing="0">
            {vrow("Blood Pressure", bp_disp)}
            {vrow("Visual Acuity L / R", f"{va_l}&nbsp;/&nbsp;{va_r}")}
            {vrow("Fasting Blood Sugar", fbs_disp)}
            {vrow("Random Blood Sugar", rbs_disp)}
            </table>
          </td></tr>
          <tr><td bgcolor="#f9fafb" style="padding:10px 14px;border-top:1px solid #e5e7eb;">
            <div style="font-size:7pt;font-weight:bold;color:#6b7280;letter-spacing:1px;
                        text-transform:uppercase;margin-bottom:6px;">Reported Symptoms</div>
            <div>{sym_html}</div>
          </td></tr>
          </table>
        </td>
      </tr></table>
    </td>
  </tr>
  </table>

  {sec("Image Results")}
  {image_results_html}

  {sec("Clinical History")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
  {info_row([("Diabetes Type", esc(full.get("diabetes_type"))), ("Duration", dur_disp),
             ("HbA1c", esc(full.get("hba1c"))), ("Previous DR Treatment", esc(full.get("prev_treatment")))], "#ffffff")}
  </table>

  {sec("Clinical Analysis")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #bfdbfe;border-left:5px solid #2563eb;
                border-radius:0 8px 8px 0;background:#eff6ff;">
  <tr><td style="padding:16px 20px;font-size:10pt;line-height:1.8;color:#1e3a5f;">
    {summary}
  </td></tr>
  </table>

  {sec("Clinical Notes")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e5e7eb;border-radius:8px;background:#fafafa;">
  <tr><td style="padding:14px 18px;font-size:10pt;color:#374151;
               font-style:italic;line-height:1.7;">
    {notes_disp}
  </td></tr>
  </table>

  <!-- ═══════════════════════════════════════════════════════ FOOTER -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="margin-top:28px;border-top:2px solid #e5e7eb;">
  <tr><td style="padding-top:14px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td valign="top" style="font-size:8pt;color:#6b7280;line-height:2;">
        <b>Screened by:</b>&nbsp;{screened_by}&nbsp;&nbsp;
        <b>Generated:</b>&nbsp;{report_date}
      </td>
      <td valign="top" align="right" style="font-size:8pt;color:#94a3b8;">
        Powered by {escape(clinic_name)}
      </td>
    </tr></table>
    <div style="margin-top:8px;font-size:7.5pt;color:#9ca3af;font-style:italic;line-height:1.6;">
      This report is AI-assisted and does not replace the judgment of a licensed eye care professional.
      All findings must be reviewed and confirmed by a qualified healthcare professional before any clinical action is taken.
    </div>
  </td></tr>
  </table>

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
        QMessageBox.information(self, "Report Saved", f"Patient report saved to:\n{path}")