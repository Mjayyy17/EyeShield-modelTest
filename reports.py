"""
Reports module for EyeShield EMR application.
Provides offline summary analytics from local patient_records data.
"""

import sqlite3

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt

from auth import DB_FILE


class ReportsPage(QWidget):
    """Reports page with local offline statistics."""

    def __init__(self):
        super().__init__()
        self._summary_cache = {}
        self._recent_rows = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Reports")
        title.setStyleSheet("font-size:20px;font-weight:bold;")
        subtitle = QLabel("Offline analytics from locally saved screening records")
        subtitle.setStyleSheet("font-size:13px;color:#6c757d;")

        top_bar = QHBoxLayout()
        top_bar.addWidget(title)
        top_bar.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_report)
        export_btn = QPushButton("Export Summary")
        export_btn.clicked.connect(self.export_summary)
        top_bar.addWidget(refresh_btn)
        top_bar.addWidget(export_btn)

        root.addLayout(top_bar)
        root.addWidget(subtitle)

        stats_group = QGroupBox("Summary")
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setContentsMargins(16, 18, 16, 16)
        stats_layout.setSpacing(12)

        total_card, self.total_label = self._make_stat_card("Total Screenings", "0")
        unique_card, self.unique_patients_label = self._make_stat_card("Unique Patients", "0")
        no_dr_card, self.no_dr_label = self._make_stat_card("No DR", "0")
        review_card, self.review_label = self._make_stat_card("Needs Review", "0")
        hba1c_card, self.hba1c_label = self._make_stat_card("Avg HbA1c", "0.0%")

        self._stat_cards = [total_card, unique_card, no_dr_card, review_card, hba1c_card]
        for card in self._stat_cards:
            stats_layout.addWidget(card)

        root.addWidget(stats_group)

        recent_group = QGroupBox("Recent Screenings")
        recent_layout = QVBoxLayout(recent_group)
        recent_layout.setContentsMargins(12, 16, 12, 12)

        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(["Patient ID", "Name", "Result", "Confidence"])
        self.recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recent_table.setSelectionMode(QTableWidget.SingleSelection)
        recent_layout.addWidget(self.recent_table)

        root.addWidget(recent_group)

        self.refresh_report()

    def _make_stat_card(self, title: str, value: str) -> tuple[QWidget, QLabel]:
        container = QWidget()
        container.setStyleSheet("background:#ffffff;border:1px solid #dee2e6;border-radius:8px;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:12px;color:#6c757d;")
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size:18px;font-weight:700;color:#343a40;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return container, value_label

    def refresh_report(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT patient_id, name, result, confidence, hba1c
                FROM patient_records
                ORDER BY id DESC
                """
            )
            rows = cur.fetchall()
            conn.close()
        except Exception as err:
            QMessageBox.warning(self, "Reports", f"Failed to load report data: {err}")
            return

        total = len(rows)
        unique_patients = len({str(row[0]).strip() for row in rows if str(row[0]).strip()})
        no_dr = 0
        hba1c_values = []

        for _, _, result, _, hba1c in rows:
            result_text = str(result or "").lower()
            if "no dr" in result_text:
                no_dr += 1
            raw_hba1c = str(hba1c or "").replace("%", "").strip()
            try:
                hba1c_values.append(float(raw_hba1c))
            except ValueError:
                pass

        needs_review = max(0, total - no_dr)
        avg_hba1c = (sum(hba1c_values) / len(hba1c_values)) if hba1c_values else 0.0

        self._summary_cache = {
            "total_screenings": total,
            "unique_patients": unique_patients,
            "no_dr": no_dr,
            "needs_review": needs_review,
            "avg_hba1c": round(avg_hba1c, 1),
        }
        self._recent_rows = rows[:15]

        self.total_label.setText(str(total))
        self.unique_patients_label.setText(str(unique_patients))
        self.no_dr_label.setText(str(no_dr))
        self.review_label.setText(str(needs_review))
        self.hba1c_label.setText(f"{avg_hba1c:.1f}%")

        self.recent_table.setRowCount(0)
        for patient_id, name, result, confidence, _ in self._recent_rows:
            row_idx = self.recent_table.rowCount()
            self.recent_table.insertRow(row_idx)
            self.recent_table.setItem(row_idx, 0, QTableWidgetItem(str(patient_id or "")))
            self.recent_table.setItem(row_idx, 1, QTableWidgetItem(str(name or "")))
            self.recent_table.setItem(row_idx, 2, QTableWidgetItem(str(result or "")))
            self.recent_table.setItem(row_idx, 3, QTableWidgetItem(str(confidence or "")))

        try:
            self.recent_table.resizeColumnsToContents()
        except Exception:
            pass

    def export_summary(self):
        if not self._summary_cache:
            QMessageBox.information(self, "Export", "No report data to export yet.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Report Summary", "", "Text Files (*.txt)")
        if not path:
            return

        lines = [
            "EyeShield Report Summary",
            "========================",
            f"Total Screenings: {self._summary_cache['total_screenings']}",
            f"Unique Patients: {self._summary_cache['unique_patients']}",
            f"No DR: {self._summary_cache['no_dr']}",
            f"Needs Review: {self._summary_cache['needs_review']}",
            f"Avg HbA1c: {self._summary_cache['avg_hba1c']:.1f}%",
            "",
            "Recent Screenings:",
        ]

        for patient_id, name, result, confidence, _ in self._recent_rows:
            lines.append(f"- {patient_id} | {name} | {result} | {confidence}")

        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write("\n".join(lines))
            QMessageBox.information(self, "Export", f"Report summary exported to:\n{path}")
        except OSError as err:
            QMessageBox.warning(self, "Export", f"Failed to export summary: {err}")
