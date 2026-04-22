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
    QFileDialog, QDialog, QMessageBox, QMenu, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter

from auth import DB_FILE, UserManager


def _is_truthy_flag(value) -> bool:
    """Normalize legacy/new boolean-like values stored in SQLite text fields."""
    return str(value or "").strip().lower() in {"true", "1", "yes", "checked", "y"}


_APP_ROOT = Path(__file__).resolve().parent
_SEVERITY_RANK = {
    "No DR": 0,
    "Mild DR": 1,
    "Moderate DR": 2,
    "Severe DR": 3,
    "Proliferative DR": 4,
}


def _parse_datetime_value(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _format_screening_datetime_label(value: str) -> str:
    parsed = _parse_datetime_value(value)
    if parsed is None:
        return str(value or "—").strip() or "—"
    hour = parsed.strftime("%I").lstrip("0") or "0"
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year} - {hour}:{parsed.strftime('%M')} {parsed.strftime('%p').lower()}"


def _normalize_severity(value: str) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if not lower:
        return ""
    if "proliferative" in lower or lower == "pdr":
        return "Proliferative DR"
    if "severe" in lower:
        return "Severe DR"
    if "moderate" in lower:
        return "Moderate DR"
    if "mild" in lower:
        return "Mild DR"
    if "no dr" in lower or lower == "normal":
        return "No DR"
    return text


def _display_severity(record: dict) -> str:
    value = (
        str(record.get("final_diagnosis_icdr") or "").strip()
        or str(record.get("doctor_classification") or "").strip()
        or str(record.get("ai_classification") or "").strip()
        or str(record.get("result") or "").strip()
    )
    return _normalize_severity(value) or "Pending"


def _severity_rank_for(value: str) -> int:
    return _SEVERITY_RANK.get(_normalize_severity(value), -1)


def _risk_status_for(value: str) -> tuple[str, str]:
    rank = _severity_rank_for(value)
    if rank <= 0:
        return "Low risk", "#16a34a"
    if rank == 1:
        return "Watch closely", "#ca8a04"
    return "High risk", "#dc2626"


def _parse_confidence_metrics(confidence_text: str) -> tuple[str, str, float | None, float | None]:
    raw = str(confidence_text or "").strip()
    if not raw:
        return "Confidence: —", "Uncertainty: —", None, None

    conf_match = __import__("re").search(r"confidence\s*:?\s*(\d+(?:\.\d+)?)\s*%", raw, __import__("re").IGNORECASE)
    unc_match = __import__("re").search(r"uncertainty\s*:?\s*(\d+(?:\.\d+)?)\s*%", raw, __import__("re").IGNORECASE)
    conf_pct = float(conf_match.group(1)) if conf_match else None
    unc_pct = float(unc_match.group(1)) if unc_match else (100.0 - conf_pct if conf_pct is not None else None)

    conf_label = f"Confidence: {conf_pct:.1f}%" if conf_pct is not None else f"Confidence: {raw}"
    unc_label = f"Uncertainty: {unc_pct:.1f}%" if unc_pct is not None else "Uncertainty: —"
    return conf_label, unc_label, conf_pct, unc_pct


def _resolve_media_path(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = Path(raw)
    if path.is_absolute() and path.exists():
        return str(path)
    candidate = (_APP_ROOT / raw).resolve()
    if candidate.exists():
        return str(candidate)
    return ""


def _timeline_sort_key(record: dict) -> tuple[datetime, int]:
    parsed = _parse_datetime_value(record.get("screened_at"))
    return (parsed or datetime.min, int(record.get("id") or 0))


class ScreeningComparisonDialog(QDialog):
    def __init__(self, previous_record: dict, latest_record: dict, parent=None):
        super().__init__(parent)
        self.previous_record = previous_record
        self.latest_record = latest_record
        self.setWindowTitle("Compare Latest Two Screenings")
        self.resize(1080, 720)

        previous_result = _display_severity(previous_record)
        latest_result = _display_severity(latest_record)
        previous_rank = _severity_rank_for(previous_result)
        latest_rank = _severity_rank_for(latest_result)
        delta = latest_rank - previous_rank

        if delta > 1:
            trend_text = "Rapid deterioration"
            trend_color = "#dc2626"
        elif delta > 0:
            trend_text = "Worsening"
            trend_color = "#ea580c"
        elif delta < 0:
            trend_text = "Improving"
            trend_color = "#16a34a"
        else:
            trend_text = "Stable"
            trend_color = "#2563eb"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Latest Progression Comparison")
        title.setStyleSheet("font-size:20px;font-weight:700;color:#0f172a;")
        layout.addWidget(title)

        summary = QLabel(
            f"Severity change: <b>{escape(previous_result)}</b> -> <b>{escape(latest_result)}</b> | "
            f"<span style='color:{trend_color};font-weight:700;'>{trend_text}</span>"
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("background:#f8fafc;border:1px solid #dbeafe;border-radius:10px;padding:12px;")
        layout.addWidget(summary)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        layout.addLayout(columns, 1)

        def build_column(record: dict, heading: str) -> QGroupBox:
            result = _display_severity(record)
            conf_label, unc_label, _, _ = _parse_confidence_metrics(record.get("confidence"))
            card = QGroupBox(heading)
            card.setStyleSheet("QGroupBox{font-weight:700;padding-top:16px;} QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px;}")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(10)

            meta = QLabel(
                "<br>".join(
                    [
                        f"<b>Date:</b> {escape(_format_screening_datetime_label(record.get('screened_at')))}",
                        f"<b>Eye:</b> {escape(str(record.get('eyes') or '—'))}",
                        f"<b>Severity:</b> {escape(result)}",
                        f"<b>{escape(conf_label)}</b>",
                        f"<b>{escape(unc_label)}</b>",
                    ]
                )
            )
            meta.setWordWrap(True)
            meta.setStyleSheet("color:#334155;")
            card_layout.addWidget(meta)

            for label_text, path_key in (("Fundus Image", "source_image_path"), ("Grad-CAM", "heatmap_image_path")):
                img = QLabel(label_text)
                img.setAlignment(Qt.AlignCenter)
                img.setMinimumHeight(220)
                img.setStyleSheet("background:#0f172a;color:#e2e8f0;border:1px solid #cbd5e1;border-radius:10px;")
                img_path = _resolve_media_path(record.get(path_key))
                if img_path:
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        img.setPixmap(
                            pixmap.scaled(320, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        )
                card_layout.addWidget(img)

            details = QLabel(
                "<br>".join(
                    [
                        f"<b>AI:</b> {escape(str(record.get('ai_classification') or record.get('result') or '—'))}",
                        f"<b>Doctor:</b> {escape(str(record.get('doctor_classification') or record.get('result') or '—'))}",
                        f"<b>Final:</b> {escape(str(record.get('final_diagnosis_icdr') or result or '—'))}",
                        f"<b>Findings:</b> {escape(str(record.get('doctor_findings') or '—'))}",
                    ]
                )
            )
            details.setWordWrap(True)
            details.setStyleSheet("background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;color:#334155;")
            card_layout.addWidget(details)
            return card

        columns.addWidget(build_column(previous_record, "Previous Screening"), 1)
        columns.addWidget(build_column(latest_record, "Latest Screening"), 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)


class PatientTimelineDialog(QDialog):
    def __init__(
        self,
        patient_summary: dict,
        timeline_records: list[dict],
        parent=None,
        on_follow_up=None,
        on_view_report=None,
        on_compare=None,
        on_export=None,
    ):
        super().__init__(parent)
        self.patient_summary = dict(patient_summary or {})
        self.timeline_records = sorted(list(timeline_records or []), key=_timeline_sort_key)
        self._selected_record = self.timeline_records[-1] if self.timeline_records else {}
        self._node_buttons = {}
        self._on_follow_up = on_follow_up
        self._on_view_report = on_view_report
        self._on_compare = on_compare
        self._on_export = on_export

        patient_name = self.patient_summary.get("name") or "Patient"
        self.setWindowTitle(f"Patient Timeline - {patient_name}")
        self.resize(1320, 840)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel(str(patient_name))
        title.setStyleSheet("font-size:24px;font-weight:700;color:#0f172a;")
        root.addWidget(title)

        split = QHBoxLayout()
        split.setSpacing(16)
        root.addLayout(split, 1)

        left_card = QGroupBox("Patient Summary")
        left_card.setMaximumWidth(320)
        left_layout = QVBoxLayout(left_card)
        left_layout.setSpacing(10)
        split.addWidget(left_card, 0)

        latest_result = _display_severity(self._selected_record)
        risk_text, risk_color = _risk_status_for(latest_result)

        for label_text, value_text in (
            ("Patient ID", self.patient_summary.get("patient_id") or "—"),
            ("Name", self.patient_summary.get("name") or "—"),
            ("Age", self.patient_summary.get("age") or "—"),
            ("Condition", self.patient_summary.get("diabetes_type") or self.patient_summary.get("condition") or "—"),
        ):
            lbl = QLabel(f"<b>{label_text}</b>")
            lbl.setStyleSheet("color:#64748b;font-size:11px;text-transform:uppercase;")
            val = QLabel(str(value_text))
            val.setStyleSheet("color:#1e293b;font-size:14px;font-weight:600;")
            val.setWordWrap(True)
            left_layout.addWidget(lbl)
            left_layout.addWidget(val)
            left_layout.addSpacing(4)

        left_layout.addSpacing(10)
        left_layout.addWidget(QLabel("<b>Latest DR Result</b>"))
        res_lbl = QLabel(latest_result)
        res_lbl.setStyleSheet(f"color:{risk_color};font-size:18px;font-weight:800;")
        left_layout.addWidget(res_lbl)

        risk_badge = QLabel(risk_text.upper())
        risk_badge.setAlignment(Qt.AlignCenter)
        risk_badge.setMinimumHeight(32)
        risk_badge.setStyleSheet(
            f"background:{risk_color}20;color:{risk_color};border:1px solid {risk_color};"
            "border-radius:6px;font-weight:800;font-size:12px;padding:0 8px;"
        )
        left_layout.addWidget(QLabel("<b>Risk Level</b>"))
        left_layout.addWidget(risk_badge)
        left_layout.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        split.addLayout(right_col, 1)

        if len(self.timeline_records) >= 2:
            compare_banner = QFrame()
            compare_banner.setStyleSheet("QFrame{background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;}")
            compare_layout = QHBoxLayout(compare_banner)
            compare_layout.setContentsMargins(14, 10, 14, 10)
            compare_layout.addWidget(QLabel("Would you like to compare latest progression?"), 1)
            compare_btn = QPushButton("Compare Trends")
            compare_btn.clicked.connect(self._handle_compare)
            compare_layout.addWidget(compare_btn)
            right_col.addWidget(compare_banner)

        summary_card = QGroupBox("Clinical Progression Summary")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setSpacing(6)
        for line in self._build_progression_summary_lines():
            label = QLabel(line)
            label.setWordWrap(True)
            label.setStyleSheet("color:#334155;")
            summary_layout.addWidget(label)
        right_col.addWidget(summary_card)

        timeline_title = QLabel("Timeline Summary")
        timeline_title.setStyleSheet("font-size:16px;font-weight:700;color:#0f172a;")
        right_col.addWidget(timeline_title)

        timeline_scroll = QScrollArea()
        timeline_scroll.setWidgetResizable(True)
        timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        timeline_host = QWidget()
        timeline_layout = QVBoxLayout(timeline_host)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(10)

        for record in self.timeline_records:
            button = QPushButton(self._node_text(record))
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.setMinimumHeight(84)
            button.setStyleSheet(self._node_style(record, active=False))
            source_path = _resolve_media_path(record.get("source_image_path"))
            if source_path:
                pixmap = QPixmap(source_path)
                if not pixmap.isNull():
                    button.setIcon(QIcon(pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                    button.setIconSize(QSize(56, 56))
            button.clicked.connect(lambda checked=False, record_id=int(record.get("id") or 0): self._select_record(record_id))
            timeline_layout.addWidget(button)
            self._node_buttons[int(record.get("id") or 0)] = button

        timeline_layout.addStretch(1)
        timeline_scroll.setWidget(timeline_host)
        right_col.addWidget(timeline_scroll, 1)

        self.details_card = QGroupBox("Screening Details")
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setSpacing(10)
        self.details_heading = QLabel("")
        self.details_heading.setStyleSheet("font-size:16px;font-weight:700;color:#0f172a;")
        details_layout.addWidget(self.details_heading)
        self.details_body = QLabel("")
        self.details_body.setWordWrap(True)
        self.details_body.setTextFormat(Qt.RichText)
        self.details_body.setStyleSheet("background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;color:#334155;")
        details_layout.addWidget(self.details_body)

        image_row = QHBoxLayout()
        image_row.setSpacing(10)
        self.source_preview = QLabel("Fundus image preview")
        self.heatmap_preview = QLabel("Grad-CAM preview")
        for preview in (self.source_preview, self.heatmap_preview):
            preview.setAlignment(Qt.AlignCenter)
            preview.setMinimumHeight(220)
            preview.setStyleSheet("background:#0f172a;color:#e2e8f0;border:1px solid #cbd5e1;border-radius:10px;")
            image_row.addWidget(preview, 1)
        details_layout.addLayout(image_row)
        right_col.addWidget(self.details_card)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        follow_up_btn = QPushButton("Add Follow-Up Screening")
        follow_up_btn.clicked.connect(self._handle_follow_up)
        actions.addWidget(follow_up_btn)
        report_btn = QPushButton("View Full Report")
        report_btn.clicked.connect(self._handle_view_report)
        actions.addWidget(report_btn)
        compare_btn = QPushButton("Compare Latest Two Screenings")
        compare_btn.setEnabled(len(self.timeline_records) >= 2)
        compare_btn.clicked.connect(self._handle_compare)
        actions.addWidget(compare_btn)
        export_btn = QPushButton("Export Patient History")
        export_btn.clicked.connect(self._handle_export)
        actions.addWidget(export_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        right_col.addLayout(actions)

        if self._selected_record:
            self._select_record(int(self._selected_record.get("id") or 0))

    def _build_progression_summary_lines(self) -> list[str]:
        if not self.timeline_records:
            return ["No screening history available."]

        severities = [_display_severity(record) for record in self.timeline_records]
        condensed = []
        for severity in severities:
            if not condensed or condensed[-1] != severity:
                condensed.append(severity)

        initial = condensed[0] if condensed else "Pending"
        latest = condensed[-1] if condensed else "Pending"
        risk_text, _ = _risk_status_for(latest)

        # If only one record, don't show progression or trend
        if len(self.timeline_records) < 2:
            return [
                f"Initial condition: {initial}",
                f"Risk status: {risk_text}",
            ]

        latest_date = _parse_datetime_value(self.timeline_records[-1].get("screened_at"))
        first_date = _parse_datetime_value(self.timeline_records[0].get("screened_at"))
        day_span = (latest_date - first_date).days if latest_date and first_date else None

        start_rank = _severity_rank_for(initial)
        end_rank = _severity_rank_for(latest)
        
        if end_rank - start_rank > 1 and day_span is not None and day_span <= 180:
            trend = "Trend: Rapid deterioration"
        elif end_rank > start_rank:
            trend = "Trend: Progressive worsening"
        elif end_rank < start_rank:
            trend = "Trend: Improving"
        else:
            trend = "Trend: Stable disease pattern"

        return [
            f"Initial condition: {initial}",
            f"Progression detected: {' -> '.join(condensed)}",
            trend,
            f"Risk status: {risk_text}",
        ]

    def _node_text(self, record: dict) -> str:
        result = _display_severity(record)
        conf_label, unc_label, _, _ = _parse_confidence_metrics(record.get("confidence"))
        follow_up_flag = str(record.get("screening_type") or "").strip().lower() == "follow_up"
        follow_up_suffix = " | Follow-up" if follow_up_flag else ""
        return "\n".join(
            [
                f"Date: {_format_screening_datetime_label(record.get('screened_at'))}",
                f"{record.get('eyes') or 'Eye not set'} | Result: {result}{follow_up_suffix}",
                f"{conf_label} | {unc_label}",
            ]
        )

    def _node_style(self, record: dict, active: bool) -> str:
        _, color = _risk_status_for(_display_severity(record))
        bg = "#eff6ff" if active else "#ffffff"
        border = color if active else "#dbeafe"
        return (
            "QPushButton{"
            f"background:{bg};color:#0f172a;border:2px solid {border};border-left:8px solid {color};"
            "border-radius:12px;padding:12px;text-align:left;font-weight:600;"
            "}"
            "QPushButton:hover{background:#f8fbff;}"
        )

    def _select_record(self, record_id: int):
        chosen = next((record for record in self.timeline_records if int(record.get("id") or 0) == int(record_id)), None)
        if not chosen:
            return

        self._selected_record = chosen
        for rid, button in self._node_buttons.items():
            is_active = rid == int(record_id)
            button.setChecked(is_active)
            button.setStyleSheet(self._node_style(chosen if is_active else next(record for record in self.timeline_records if int(record.get("id") or 0) == rid), is_active))

        result = _display_severity(chosen)
        conf_label, unc_label, _, _ = _parse_confidence_metrics(chosen.get("confidence"))
        self.details_heading.setText(f"{_format_screening_datetime_label(chosen.get('screened_at'))} - {chosen.get('eyes') or 'Eye'}")

        symptoms = []
        if _is_truthy_flag(chosen.get("symptom_blurred_vision")):
            symptoms.append("Blurred vision")
        if _is_truthy_flag(chosen.get("symptom_floaters")):
            symptoms.append("Floaters")
        if _is_truthy_flag(chosen.get("symptom_flashes")):
            symptoms.append("Flashes")
        if _is_truthy_flag(chosen.get("symptom_vision_loss")):
            symptoms.append("Vision loss")

        details_lines = [
            f"<b>DR Severity:</b> {escape(result)}",
            f"<b>{escape(conf_label)}</b>",
            f"<b>{escape(unc_label)}</b>",
            f"<b>AI Classification:</b> {escape(str(chosen.get('ai_classification') or chosen.get('result') or '—'))}",
            f"<b>Doctor Classification:</b> {escape(str(chosen.get('doctor_classification') or chosen.get('result') or '—'))}",
            f"<b>Final Diagnosis:</b> {escape(str(chosen.get('final_diagnosis_icdr') or result or '—'))}",
            f"<b>Decision Mode:</b> {escape(str(chosen.get('decision_mode') or 'accepted').title())}",
            f"<b>Findings:</b> {escape(str(chosen.get('doctor_findings') or '—'))}",
            f"<b>Symptoms:</b> {escape(', '.join(symptoms) if symptoms else 'None reported')}",
            f"<b>Clinical Notes:</b> {escape(str(chosen.get('notes') or '—'))}",
        ]

        if str(chosen.get("screening_type") or "").strip().lower() == "follow_up":
            details_lines.append("<b>Screening Type:</b> Follow-up")
        previous_ref = chosen.get("previous_screening_id")
        if previous_ref:
            details_lines.append(f"<b>Previous Screening Reference:</b> {escape(str(previous_ref))}")

        self.details_body.setText("<br>".join(details_lines))
        self._set_preview_image(self.source_preview, chosen.get("source_image_path"), "Fundus image preview")
        self._set_preview_image(self.heatmap_preview, chosen.get("heatmap_image_path"), "Grad-CAM preview")

    def _set_preview_image(self, label: QLabel, image_value: str, fallback_text: str):
        label.setPixmap(QPixmap())
        label.setText(fallback_text)
        path = _resolve_media_path(image_value)
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        label.setText("")
        label.setPixmap(pixmap.scaled(420, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _handle_follow_up(self):
        if callable(self._on_follow_up):
            self._on_follow_up(self._selected_record)

    def _handle_view_report(self):
        if callable(self._on_view_report):
            self._on_view_report(self._selected_record)

    def _handle_compare(self):
        if callable(self._on_compare):
            self._on_compare(self.timeline_records)

    def _handle_export(self):
        if callable(self._on_export):
            self._on_export(self.timeline_records)

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
        add_field("Height (cm)", str(patient_record.get("height") or "N/A") + (" cm" if patient_record.get("height") else ""))
        add_field("Weight (kg)", str(patient_record.get("weight") or "N/A") + (" kg" if patient_record.get("weight") else ""))
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
        if _is_truthy_flag(patient_record.get("symptom_blurred_vision")):
            symptoms.append("Blurred vision")
        if _is_truthy_flag(patient_record.get("symptom_floaters")):
            symptoms.append("Floaters")
        if _is_truthy_flag(patient_record.get("symptom_flashes")):
            symptoms.append("Flashes")
        if _is_truthy_flag(patient_record.get("symptom_vision_loss")):
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
        prev_treatment = "Yes" if _is_truthy_flag(patient_record.get("prev_treatment")) else "No"
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
        add_field("Height (cm)", str(patient_record.get("height") or "N/A") + (" cm" if patient_record.get("height") else ""))
        add_field("Weight (kg)", str(patient_record.get("weight") or "N/A") + (" kg" if patient_record.get("weight") else ""))
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

        notes_raw = str(patient_record.get("notes") or "").strip()
        if notes_raw:
            notes_lines = [line.strip() for line in notes_raw.splitlines() if line.strip()]
            message_lines = [line for line in notes_lines if line.lower().startswith("message on this patient")]
            comment_lines = [
                line for line in notes_lines if line.lower().startswith("additional comments:")
            ]
            status_lines = [
                line for line in notes_lines if line not in message_lines and line not in comment_lines
            ]

            if comment_lines:
                add_section("Additional Comments")
                cleaned_comments = [
                    line.split(":", 1)[1].strip() if ":" in line else line for line in comment_lines
                ]
                comments_label = QLabel("\n".join(cleaned_comments))
                comments_label.setWordWrap(True)
                comments_label.setStyleSheet(
                    "color:#1f2937;background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:10px;"
                )
                left_layout.addWidget(comments_label)

            if message_lines:
                add_section("Message History")
                message_label = QLabel("\n".join(reversed(message_lines)))
                message_label.setWordWrap(True)
                message_label.setStyleSheet(
                    "color:#334155;background:#eef6ff;border:1px solid #bfdbfe;border-radius:6px;padding:10px;"
                )
                left_layout.addWidget(message_label)

            if status_lines:
                add_section("Status Notes")
                status_label = QLabel("\n".join(reversed(status_lines)))
                status_label.setWordWrap(True)
                status_label.setStyleSheet(
                    "color:#475569;background:#f6f8fb;border:1px solid #d3dae3;border-radius:6px;padding:10px;"
                )
                left_layout.addWidget(status_label)

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
    """Dialog for reviewing archived patient records."""

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
        record = self._get_selected_record()
        has = record is not None
        can_manage = bool(has and self.reports_page._can_archive_record(record))
        self.restore_btn.setEnabled(can_manage)
        self.delete_btn.setEnabled(can_manage)

    def restore_selected_record(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Restore Record", "Select an archived patient record to restore.")
            return
        if not self.reports_page._can_archive_record(record):
            owner = self.reports_page._record_owner_label(record)
            QMessageBox.warning(
                self,
                "Restore Restricted",
                f"Only the original screening doctor ({owner}) can restore this archived record.",
            )
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
        if not self.reports_page._can_archive_record(record):
            owner = self.reports_page._record_owner_label(record)
            QMessageBox.warning(
                self,
                "Delete Restricted",
                f"Only the original screening doctor ({owner}) can delete this archived record.",
            )
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
        self.can_manage_archives = str(self.role or "").strip().lower() in {"admin", "clinician"}
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
                font-family: 'Segoe UI';
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
            QPushButton:disabled {
                background: #f8fafc;
                border: 1px solid #dbeafe;
                color: #9ca3af;
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

        self._rep_title_lbl = QLabel("")
        self._rep_title_lbl.setObjectName("pageHeader")
        self._rep_title_lbl.setStyleSheet("font-size:26px;font-weight:700;color:#1f6fe5;font-family:'Segoe UI';")
        self._rep_subtitle_lbl = QLabel("")
        self._rep_subtitle_lbl.setObjectName("pageSubtitle")
        self._rep_subtitle_lbl.setStyleSheet("font-size:13px;color:#6b7f95;")
        self._rep_subtitle_lbl.setAlignment(Qt.AlignLeft)

        self._rep_title_lbl.hide()
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setAutoDefault(True)
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self.export_summary)
        if self.can_manage_archives:
            self.archive_btn = QPushButton("Archive Selected")
            self.archive_btn.clicked.connect(self.archive_selected_record)
            self.archive_btn.setEnabled(False)
        else:
            self.archive_btn = None
        if self.can_manage_archives:
            self.archived_records_btn = QPushButton("Archived Records")
            self.archived_records_btn.clicked.connect(self.open_archived_records_window)
        else:
            self.archived_records_btn = None
        self.report_btn = QPushButton("Generate Report")
        self.report_btn.setEnabled(False)
        self.report_btn.clicked.connect(self.generate_report)
        self.referral_btn = QPushButton("Generate Referral")
        self.referral_btn.setEnabled(False)
        self.referral_btn.clicked.connect(self.start_referral_flow)
        self.rescreen_btn = QPushButton("Add Follow-Up Screening")
        self.rescreen_btn.setEnabled(False)
        self.rescreen_btn.clicked.connect(self.rescreen_patient)

        self._rep_subtitle_lbl.hide()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color:#4f637a;background:#eaf1fb;border:1px solid #d4e2f3;border-radius:10px;padding:8px 12px;")
        self.status_label.hide()
        root.addWidget(self.status_label)

        self._controls_group = QGroupBox("")
        cl = QHBoxLayout(self._controls_group)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(14)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self.apply_filters)
        cl.addWidget(self.search_input, 1)
        self.result_filter = QComboBox()
        self.result_filter.addItems(["All","No DR","Mild DR","Moderate DR","Severe DR","Proliferative DR"])
        self.result_filter.setMinimumHeight(40)
        self.result_filter.currentTextChanged.connect(self.apply_filters)
        cl.addWidget(self.result_filter)
        cl.addStretch(1)
        if self.archive_btn is not None:
            cl.addWidget(self.archive_btn)
        if self.archived_records_btn is not None:
            cl.addWidget(self.archived_records_btn)
        cl.addWidget(self.export_btn)
        cl.addWidget(self.report_btn)
        cl.addWidget(self.referral_btn)
        cl.addWidget(self.rescreen_btn)
        root.addWidget(self._controls_group)

        self._results_group = QGroupBox("")
        rl = QVBoxLayout(self._results_group)
        rl.setContentsMargins(18, 16, 18, 18)
        rl.setSpacing(14)

        self.results_table = QTableWidget(0, 8)
        self.results_table.setHorizontalHeaderLabels(["Patient ID","Name","Eye Screened","Screening Date","AI Result","Doctor's Result","Confidence","Screened by"])
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
        self.results_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
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
            base_icon = QIcon(icon_file)
            source = base_icon.pixmap(QSize(24, 24))
            if source.isNull():
                button.setIcon(base_icon)
                button.setIconSize(QSize(24, 24))
                return

            def _tint(color_hex: str) -> QPixmap:
                tinted = QPixmap(source.size())
                tinted.fill(Qt.GlobalColor.transparent)
                painter = QPainter(tinted)
                painter.drawPixmap(0, 0, source)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(tinted.rect(), QColor(color_hex))
                painter.end()
                return tinted

            icon = QIcon()
            icon.addPixmap(_tint("#60a5fa"), QIcon.Mode.Normal, QIcon.State.Off)
            icon.addPixmap(_tint("#3b82f6"), QIcon.Mode.Active, QIcon.State.Off)
            icon.addPixmap(_tint("#bfdbfe"), QIcon.Mode.Disabled, QIcon.State.Off)
            button.setIcon(icon)
            button.setIconSize(QSize(22, 22))

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
        self.rescreen_btn.setToolTip("Add a follow-up screening for the selected patient")
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
        self.status_label.setText("")

    @staticmethod
    def _eye_sort_key(eye_value: str) -> tuple[int, str]:
        eye = str(eye_value or "").strip().lower()
        if "right" in eye:
            return (0, eye)
        if "left" in eye:
            return (1, eye)
        return (2, eye)

    @staticmethod
    def _format_screening_datetime(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "—"

        parsed = None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue

        if parsed is None:
            return raw

        hour = parsed.strftime("%I").lstrip("0") or "0"
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year} - {hour}:{parsed.strftime('%M')} {parsed.strftime('%p').lower()}"

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
            date_values = [str(item.get("screened_at") or "").strip() for item in ordered_rows]
            date_values = [value for value in date_values if value]
            if date_values:
                unique_dates = list(dict.fromkeys(date_values))
                date_text = "\n".join(self._format_screening_datetime(value) for value in unique_dates)
            else:
                date_text = "—"
            ai_result_text = "\n".join(
                str(item.get("ai_classification") or item.get("result") or "—")
                for item in ordered_rows
            )
            doctor_result_text = "\n".join(
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
                    ai_result_text,
                    doctor_result_text,
                    confidence_text,
                    str(primary.get("ai_classification") or ""),
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
                    "ai_result": ai_result_text,
                    "doctor_result": doctor_result_text,
                    "result": doctor_result_text,
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
            ai_item = QTableWidgetItem(str(row.get("ai_result") or ""))
            ai_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 4, ai_item)
            doctor_item = QTableWidgetItem(str(row.get("doctor_result") or ""))
            doctor_item.setTextAlignment(Qt.AlignCenter)
            if any(self._is_high_attention_result(item.get("result")) for item in (row.get("source_rows") or [])):
                doctor_item.setForeground(result_color("high"))
            elif all("no dr" in str(item.get("result") or "").lower() for item in (row.get("source_rows") or [])):
                doctor_item.setForeground(result_color("normal"))
            self.results_table.setItem(i, 5, doctor_item)
            confidence_item = QTableWidgetItem(str(row["confidence"] or ""))
            confidence_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 6, confidence_item)
            screened_by_item = QTableWidgetItem(str(row.get("screened_by") or "--"))
            screened_by_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 7, screened_by_item)
        self.results_table.setSortingEnabled(True)
        self.results_table.resizeRowsToContents()
        if hasattr(self, "filtered_count_label"):
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

    @staticmethod
    def _normalize_owner_name(value: str) -> str:
        name = str(value or "").strip().lower()
        if name.startswith("dr. "):
            return name[4:].strip()
        if name.startswith("dr "):
            return name[3:].strip()
        return name

    def _is_record_owner(self, record: dict | None) -> bool:
        if not record:
            return False
        current_username = str(self.username or "").strip().lower()
        owner_username = str(record.get("original_screener_username") or "").strip().lower()
        if owner_username:
            return bool(current_username and owner_username == current_username)

        owner_name = self._normalize_owner_name(record.get("original_screener_name"))
        if not owner_name:
            return False

        current_display_name = self._normalize_owner_name(self.display_name)
        return bool(owner_name and current_display_name and owner_name == current_display_name)

    def _can_rescreen_record(self, record: dict) -> bool:
        return self._is_record_owner(record)

    def _can_archive_record(self, record: dict | None) -> bool:
        return self._is_record_owner(record)

    def _can_internal_referral_record(self, record: dict) -> bool:
        return False

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
        if self.archive_btn is not None:
            archive_action = menu.addAction("Archive Record")
            archive_action.setEnabled(not bool(record.get("archived_at")) and self._can_archive_record(record))

        chosen = menu.exec(self.results_table.viewport().mapToGlobal(pos))
        if chosen == view_action:
            self._show_patient_details()
        elif chosen == generate_action:
            self.generate_report()
        elif chosen == referral_action:
            self.start_referral_flow()
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
        self.referral_btn.setToolTip("Generate referral letter")
        can_rescreen = bool(record and self._can_rescreen_record(record))
        self.rescreen_btn.setEnabled(can_rescreen)
        if record and not can_rescreen:
            self.rescreen_btn.setToolTip(
                f"Only the original screener ({self._record_owner_label(record)}) can add a follow-up for this case."
            )
        else:
            self.rescreen_btn.setToolTip("Start a new follow-up screening for the selected patient")
        if self.archive_btn is not None:
            can_archive = bool(record and not record.get("archived_at") and self._can_archive_record(record))
            self.archive_btn.setEnabled(can_archive)
            if record and not self._can_archive_record(record):
                self.archive_btn.setToolTip(
                    f"Only the original screening doctor ({self._record_owner_label(record)}) can archive this record."
                )
            else:
                self.archive_btn.setToolTip("Archive the selected active patient record")

    def start_referral_flow(self):
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Referral", "Select a patient record first.")
            return

        self.generate_referral()

    def _on_table_row_double_clicked(self, index):
        """Handle double-click on table row to show patient details."""
        self._show_patient_details()

    def _show_patient_details(self):
        """Open the patient timeline summary dialog from the selected report row."""
        record = self._get_selected_record()
        if not record:
            return

        patient_id = str(record.get("patient_id") or "").strip()
        if not patient_id:
            QMessageBox.warning(self, "Patient Timeline", "Unable to retrieve patient history.")
            return

        timeline_records = self._fetch_patient_timeline_records(patient_id)
        if not timeline_records:
            QMessageBox.warning(self, "Patient Timeline", "Unable to load patient timeline.")
            return

        latest_record = timeline_records[-1]
        UserManager.add_activity_log(
            self.username,
            f"RECORD_OPENED patient_id={patient_id}; record_id={latest_record.get('id')}; source=reports_timeline",
        )

        dialog = PatientTimelineDialog(
            latest_record,
            timeline_records,
            self,
            on_follow_up=self._start_follow_up_from_timeline,
            on_view_report=self._generate_report_for_record,
            on_compare=self._compare_latest_two_screenings,
            on_export=self._export_patient_history,
        )
        dialog.exec()

    def _fetch_patient_timeline_records(self, patient_id: str) -> list[dict]:
        patient_id = str(patient_id or "").strip()
        if not patient_id:
            return []

        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, patient_id, name, birthdate, age, sex, contact, eyes,
                       diabetes_type, duration, hba1c, prev_treatment, notes,
                       result, confidence, screened_at, archived_at, archived_by,
                       archive_reason, original_screener_username, original_screener_name,
                       ai_classification, doctor_classification, decision_mode, override_justification, final_diagnosis_icdr, doctor_findings,
                       height, weight, bmi, visual_acuity_left, visual_acuity_right,
                       blood_pressure_systolic, blood_pressure_diastolic,
                       fasting_blood_sugar, random_blood_sugar,
                       diabetes_diagnosis_date, treatment_regimen, prev_dr_stage,
                       symptom_blurred_vision, symptom_floaters, symptom_flashes, symptom_vision_loss,
                       source_image_path, heatmap_image_path,
                       follow_up, followup_date, followup_label, screening_type, previous_screening_id
                FROM patient_records
                WHERE patient_id = ? AND archived_at IS NULL
                ORDER BY screened_at ASC, id ASC
                """,
                (patient_id,),
            )
            rows = cur.fetchall()
            conn.close()
        except Exception as err:
            QMessageBox.warning(self, "Patient Timeline", f"Failed to load patient history: {err}")
            return []

        timeline = []
        for row in rows:
            timeline.append(
                {
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
                    "source_image_path": row[43],
                    "heatmap_image_path": row[44],
                    "follow_up": row[45],
                    "followup_date": row[46],
                    "followup_label": row[47],
                    "screening_type": row[48],
                    "previous_screening_id": row[49],
                }
            )
        return timeline

    def _start_follow_up_from_timeline(self, record: dict):
        if not record:
            QMessageBox.information(self, "Follow-Up Screening", "Choose a timeline record first.")
            return

        main_window = self.window()
        if not hasattr(main_window, "screening_page") or not hasattr(main_window, "pages"):
            QMessageBox.warning(self, "Follow-Up Screening", "Unable to open the screening page.")
            return

        record_id = int(record.get("id") or 0)
        if record_id <= 0:
            QMessageBox.warning(self, "Follow-Up Screening", "Unable to determine the source screening record.")
            return

        screening_page = main_window.screening_page
        if not hasattr(screening_page, "load_patient_for_followup"):
            QMessageBox.warning(self, "Follow-Up Screening", "Follow-up workflow is not available in this session.")
            return

        if not screening_page.load_patient_for_followup(record_id):
            QMessageBox.warning(self, "Follow-Up Screening", "Unable to prepare the follow-up screening form.")
            return

        main_window.pages.setCurrentIndex(1)
        UserManager.add_activity_log(
            self.username,
            f"FOLLOW_UP_STARTED patient_id={record.get('patient_id')}; previous_record_id={record_id}",
        )

    def _compare_latest_two_screenings(self, timeline_records: list[dict]):
        ordered = sorted(list(timeline_records or []), key=_timeline_sort_key)
        if len(ordered) < 2:
            QMessageBox.information(self, "Compare Screenings", "At least two screenings are required for comparison.")
            return

        dialog = ScreeningComparisonDialog(ordered[-2], ordered[-1], self)
        dialog.exec()

    def _export_patient_history(self, timeline_records: list[dict]):
        ordered = sorted(list(timeline_records or []), key=_timeline_sort_key)
        if not ordered:
            QMessageBox.information(self, "Export Patient History", "No patient history is available to export.")
            return

        patient_name = str(ordered[-1].get("name") or "Patient").strip() or "Patient"
        patient_id = str(ordered[-1].get("patient_id") or "Unknown").strip() or "Unknown"
        default_name = f"EyeShield_History_{patient_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export Patient History", default_name, "CSV Files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Record ID",
                        "Patient ID",
                        "Name",
                        "Screened At",
                        "Eye",
                        "AI Classification",
                        "Doctor Classification",
                        "Final Diagnosis",
                        "Confidence",
                        "Decision Mode",
                        "Screening Type",
                        "Previous Screening ID",
                        "Findings",
                    ]
                )
                for record in ordered:
                    writer.writerow(
                        [
                            record.get("id"),
                            record.get("patient_id"),
                            record.get("name"),
                            record.get("screened_at"),
                            record.get("eyes"),
                            record.get("ai_classification") or record.get("result"),
                            record.get("doctor_classification") or record.get("result"),
                            record.get("final_diagnosis_icdr") or record.get("doctor_classification") or record.get("result"),
                            record.get("confidence"),
                            record.get("decision_mode"),
                            record.get("screening_type") or ("follow_up" if _is_truthy_flag(record.get("follow_up")) else "initial"),
                            record.get("previous_screening_id"),
                            record.get("doctor_findings"),
                        ]
                    )
        except OSError as err:
            QMessageBox.warning(self, "Export Patient History", f"Unable to export history: {err}")
            return

        self.status_label.setText(f"Exported patient history for {patient_name} to {path}")

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
        if not self._can_archive_record(record):
            owner_text = self._record_owner_label(record)
            QMessageBox.warning(
                self,
                "Archive Restricted",
                f"Only the original screening doctor ({owner_text}) can archive this record.",
            )
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
        """Open follow-up screening dialog and navigate to screening page."""
        record = self._get_selected_record()
        if not record:
            QMessageBox.information(self, "Add Follow-Up Screening", "Select a patient record first.")
            return

        if not self._can_rescreen_record(record):
            owner_text = self._record_owner_label(record)
            UserManager.add_activity_log(
                self.username,
                f"FOLLOW_UP_BLOCKED patient_id={record.get('patient_id')}; owner={owner_text}",
            )
            QMessageBox.warning(
                self,
                "Action Restricted",
                f"Only the original screening doctor ({owner_text}) can add a follow-up for this patient.",
            )
            return

        # Get the actual record ID - use first record_id if multiple exist
        record_ids = record.get("record_ids") or [record.get("id")]
        if not record_ids or not record_ids[0]:
            QMessageBox.warning(self, "Add Follow-Up Screening", "Unable to identify patient record ID.")
            return

        actual_record_id = record_ids[0]

        label = f"{record['name'] or 'Unknown Patient'} ({record['patient_id'] or 'No ID'})"
        box = QMessageBox(self)
        box.setWindowTitle("Add Follow-Up Screening")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(
            f"How would you like to add a follow-up screening for <b>{label}</b>?"
        )
        new_btn = box.addButton("Create New Screening Session", QMessageBox.ButtonRole.AcceptRole)
        replace_btn = box.addButton("Replace Previous Record", QMessageBox.ButtonRole.ActionRole)
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
        if not self._can_archive_record(record):
            owner = self._record_owner_label(record)
            QMessageBox.warning(
                self,
                "Restore Restricted",
                f"Only the original screening doctor ({owner}) can restore this archived record.",
            )
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
        if not self._can_archive_record(record):
            return False
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT original_screener_username, original_screener_name
                FROM patient_records
                WHERE id = ? AND archived_at IS NOT NULL
                """,
                (record["id"],),
            )
            owner_row = cur.fetchone()
            owner_record = {
                "original_screener_username": owner_row[0] if owner_row else "",
                "original_screener_name": owner_row[1] if owner_row else "",
            }
            if not self._is_record_owner(owner_record):
                conn.close()
                return False

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
        if not self._filtered_rows:
            self.status_label.setText("No visible report data to export")
            return
        confirm = QMessageBox.question(
            self,
            "Export Reports",
            f"Export {len(self._filtered_rows)} visible report row(s) to CSV?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export DR Screening Results", "", "CSV Files (*.csv)")
        if not path:
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
        self._rep_title_lbl.setText("")
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
        dialog.setFixedSize(520, 160)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        hospital_label = QLabel("Referral Hospital")
        hospital_label.setStyleSheet("font-size:11px;font-weight:700;color:#2f4054;")
        hospital_combo = QComboBox()
        hospital_combo.setMinimumHeight(34)
        for item in hospitals:
            dept = str(item.get("department") or "").strip()
            label = str(item.get("hospital_name") or "").strip()
            if dept:
                label = f"{label} ({dept})"
            if item.get("is_default"):
                label = f"{label}  [Default]"
            hospital_combo.addItem(label, item)
        hospital_combo.addItem("Other (manual entry)", None)
        layout.addWidget(hospital_label)
        layout.addWidget(hospital_combo)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        continue_btn = QPushButton("Continue")
        continue_btn.setObjectName("primaryAction")
        action_row.addWidget(cancel_btn)
        action_row.addWidget(continue_btn)
        layout.addLayout(action_row)

        cancel_btn.clicked.connect(dialog.reject)
        continue_btn.clicked.connect(dialog.accept)

        def _prompt_manual_destination() -> dict | None:
            manual_dialog = QDialog(dialog)
            manual_dialog.setWindowTitle("Manual Referral Destination")
            manual_dialog.setFixedSize(520, 220)

            manual_layout = QVBoxLayout(manual_dialog)
            manual_layout.setContentsMargins(14, 12, 14, 12)
            manual_layout.setSpacing(8)

            name_input = QLineEdit()
            name_input.setPlaceholderText("Hospital or clinic name")
            dept_input = QLineEdit()
            dept_input.setPlaceholderText("Department (optional)")
            contact_input = QLineEdit()
            contact_input.setPlaceholderText("Contact person / phone (optional)")
            manual_layout.addWidget(name_input)
            manual_layout.addWidget(dept_input)
            manual_layout.addWidget(contact_input)

            manual_actions = QHBoxLayout()
            manual_actions.addStretch(1)
            manual_cancel_btn = QPushButton("Cancel")
            manual_save_btn = QPushButton("Use Destination")
            manual_save_btn.setObjectName("primaryAction")
            manual_actions.addWidget(manual_cancel_btn)
            manual_actions.addWidget(manual_save_btn)
            manual_layout.addLayout(manual_actions)

            manual_cancel_btn.clicked.connect(manual_dialog.reject)
            manual_save_btn.clicked.connect(manual_dialog.accept)

            while True:
                if manual_dialog.exec() != QDialog.DialogCode.Accepted:
                    return None
                name = name_input.text().strip()
                if not name:
                    QMessageBox.warning(manual_dialog, "Referral Destination", "Hospital/clinic name is required for manual entry.")
                    continue
                department = dept_input.text().strip()
                contact = contact_input.text().strip()
                display = name if not department else f"{name} ({department})"
                return {
                    "hospital_name": name,
                    "department": department,
                    "contact_person": contact,
                    "display": display,
                }

        while True:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None

            selected = hospital_combo.currentData()
            if selected is None:
                manual_destination = _prompt_manual_destination()
                if manual_destination is not None:
                    return manual_destination
                continue

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

        self._generate_report_for_record(record)

    def _generate_report_for_record(self, record: dict):
        if not record:
            QMessageBox.information(self, "Generate Report", "No patient record is available for report generation.")
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

        severity_rank = {
            "No DR": 0,
            "Mild DR": 1,
            "Moderate DR": 2,
            "Severe DR": 3,
            "Proliferative DR": 4,
        }

        def pick_worst_grade(values: list[str]) -> str:
            best = ""
            best_rank = -1
            for raw in values:
                value = str(raw or "").strip()
                rank = severity_rank.get(value, -1)
                if rank > best_rank:
                    best = value
                    best_rank = rank
            return best

        bilateral_grades = []
        for eye_record in eye_records:
            grade = (
                str(eye_record.get("final_diagnosis_icdr") or "").strip()
                or str(eye_record.get("doctor_classification") or "").strip()
                or str(eye_record.get("ai_classification") or "").strip()
                or str(eye_record.get("result") or "").strip()
            )
            if grade:
                bilateral_grades.append(grade)
        bilateral_worst_grade = pick_worst_grade(bilateral_grades)

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
        if bilateral_worst_grade and severity_rank.get(bilateral_worst_grade, -1) > severity_rank.get(final_dx_raw, -1):
            final_dx_raw = bilateral_worst_grade
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

        report_date = datetime.now().strftime("%B %d, %Y  %I:%M %p")
        screening_date = str(full.get("screened_at") or "").strip() or report_date

        created_by_raw = str(full.get("original_screener_name") or full.get("original_screener_username") or "").strip()
        finalized_by_raw = str(self.display_name or os.environ.get("EYESHIELD_CURRENT_NAME", "") or self.username).strip()
        created_by = escape(self._format_doctor_label(created_by_raw or finalized_by_raw))
        finalized_by = escape(self._format_doctor_label(finalized_by_raw))

        dur_raw  = str(full.get("duration") or "").strip()
        dur_disp = f"{escape(dur_raw)} year(s)" if dur_raw and dur_raw != "0" else "&#8212;"

        notes_raw  = str(full.get("notes") or "").strip()
        other_symptom_lines = []
        note_lines = []
        for raw_line in notes_raw.splitlines():
            line = str(raw_line or "").strip()
            if not line:
                continue
            if line.lower().startswith("other symptom:"):
                value = line.split(":", 1)[1].strip() if ":" in line else ""
                if value:
                    other_symptom_lines.append(value)
                continue
            note_lines.append(line)
        notes_clean = "\n".join(note_lines).strip()
        notes_disp = escape(notes_clean) if notes_clean else '<span style="color:#9ca3af;font-style:italic;">None recorded</span>'
        other_symptom_disp = (
            "<br>".join(escape(item) for item in other_symptom_lines)
            if other_symptom_lines
            else '<span style="color:#9ca3af;font-style:italic;">None recorded</span>'
        )

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
        active_syms = [lbl for k, lbl in sym_map if _is_truthy_flag(full.get(k))]
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

            def image_panel(uri: str, placeholder: str) -> str:
                if uri:
                    img_html = f'<img src="{uri}" style="width:100%;max-width:320px;max-height:230px;height:auto;display:block;margin:0 auto;border-radius:4px;page-break-inside:avoid;break-inside:avoid-page;" />'
                else:
                    img_html = (
                        f'<div style="width:320px;height:230px;background:#f3f4f6;border-radius:4px;'
                        f'display:flex;align-items:center;justify-content:center;margin:0 auto;">'
                        f'<span style="font-size:8pt;color:#9ca3af;font-style:italic;text-align:center;padding:20px;">{placeholder}</span>'
                        f'</div>'
                    )
                return f'<div style="text-align:center;background:#ffffff;padding:8px;border:1px solid #e5e7eb;">{img_html}</div>'

            def titled_image_block(title: str, uri: str, placeholder: str, margin_top: str = "0") -> str:
                return (
                    f'<div style="page-break-inside:avoid;break-inside:avoid-page;margin-top:{margin_top};">'
                    f'<div style="font-size:8pt;font-weight:700;color:#4b5563;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 6px;">{title}</div>'
                    f'{image_panel(uri, placeholder)}'
                    f'</div>'
                )

            return (
                f'<div style="border:1px solid #d1d5db;border-radius:6px;background:#ffffff;margin-bottom:14px;padding:14px 16px;page-break-inside:avoid;break-inside:avoid-page;">'
                f'<div style="margin-bottom:12px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'<td style="font-size:10pt;font-weight:700;color:#111827;">{escape(eye_name)}</td>'
                f'<td align="right">'
                f'<span style="font-size:8pt;color:#6b7280;font-weight:600;">AI Results:&nbsp;</span>'
                f'<span style="font-size:9pt;font-weight:700;color:#111827;">{escape(eye_result) if eye_result else "&#8212;"}</span>'
                f'</td>'
                f'</tr></table>'
                f'</div>'
                f'<div style="font-size:8.5pt;color:#6b7280;margin-bottom:12px;">'
                f'Confidence: <span style="font-weight:600;color:#374151;">{escape(eye_conf) if eye_conf else "&#8212;"}</span>'
                f'</div>'
                f'{titled_image_block("Fundus", src_uri, "Source image not stored")}'
                f'{titled_image_block("Heatmap", heat_uri, "Heatmap not stored", "12px")}'
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

    {sec("Other Symptom Details")}
    <div style="padding:12px;border:1px solid #d1d5db;background:#fafafa;margin-bottom:18px;min-height:44px;">
        <div style="font-size:9pt;color:#4b5563;line-height:1.65;">{other_symptom_disp}</div>
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

    {sec("Doctor Comments")}
    <div style="padding:12px;border:1px solid #d1d5db;background:#fafafa;margin-bottom:18px;min-height:44px;">
        <div style="font-size:9pt;color:#4b5563;line-height:1.65;">{esc(doctor_findings_raw) if doctor_findings_raw else '<span style="color:#9ca3af;font-style:italic;">No doctor comments provided</span>'}</div>
    </div>
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
        eye_records = self._fetch_report_eye_records(
            full.get("patient_id"),
            full.get("screened_at"),
            int(full.get("id") or record["id"]),
        )
        if not eye_records:
            eye_records = [full]

        severity_rank = {
            "No DR": 0,
            "Mild DR": 1,
            "Moderate DR": 2,
            "Severe DR": 3,
            "Proliferative DR": 4,
        }

        def pick_worst_grade(values: list[str]) -> str:
            best = ""
            best_rank = -1
            for raw in values:
                value = str(raw or "").strip()
                rank = severity_rank.get(value, -1)
                if rank > best_rank:
                    best = value
                    best_rank = rank
            return best

        bilateral_grades = []
        for eye_record in eye_records:
            grade = (
                str(eye_record.get("final_diagnosis_icdr") or "").strip()
                or str(eye_record.get("doctor_classification") or "").strip()
                or str(eye_record.get("ai_classification") or "").strip()
                or str(eye_record.get("result") or "").strip()
            )
            if grade:
                bilateral_grades.append(grade)

        result_raw = pick_worst_grade(bilateral_grades) or str(full.get("result") or "").strip()

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
        if not path.lower().endswith(".pdf"):
            path = f"{path}.pdf"

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
        eye_findings = []
        for eye_record in eye_records:
            eye_label = str(eye_record.get("eyes") or "Eye").strip() or "Eye"
            eye_grade = (
                str(eye_record.get("final_diagnosis_icdr") or "").strip()
                or str(eye_record.get("doctor_classification") or "").strip()
                or str(eye_record.get("ai_classification") or "").strip()
                or str(eye_record.get("result") or "").strip()
                or "N/A"
            )
            eye_findings.append(f"{eye_label}: {eye_grade}")
        eye_findings_text = esc("; ".join(eye_findings)) if eye_findings else "&#8212;"

        ai_result_raw = (
            str(full.get("ai_classification") or "").strip()
            or str(full.get("result") or "").strip()
            or result_raw
        )
        patient_name = esc(full.get("name"))
        patient_dob = esc(full.get("birthdate"))
        patient_age = esc(full.get("age"))
        patient_sex = esc(full.get("sex"))
        patient_hba1c = esc(full.get("hba1c"))
        patient_diabetes_type = esc(full.get("diabetes_type"))
        patient_height = esc(full.get("height"))
        patient_weight = esc(full.get("weight"))
        patient_bmi = esc(full.get("bmi"))
        patient_visual_acuity_left = esc(full.get("visual_acuity_left"))
        patient_visual_acuity_right = esc(full.get("visual_acuity_right"))
        patient_notes_raw = str(full.get("notes") or "").strip()
        if len(patient_notes_raw) > 220:
            patient_notes_raw = f"{patient_notes_raw[:217].rstrip()}..."
        patient_notes = esc(patient_notes_raw)

        def _resolve_image_uri(path_value: str) -> str:
            raw = str(path_value or "").strip()
            if not raw:
                return ""
            candidate = raw if os.path.isabs(raw) else os.path.join(os.path.dirname(os.path.abspath(__file__)), raw)
            if not os.path.exists(candidate):
                return ""
            try:
                return Path(candidate).resolve().as_uri()
            except OSError:
                return ""

        def _scaled_referral_image(uri: str, file_path: str, missing_text: str) -> str:
            if not uri:
                return f'<div style="padding:26px 14px;color:#9ca3af;font-style:italic;">{missing_text}</div>'

            max_w, max_h = 380, 280
            width, height = max_w, max_h
            if file_path and os.path.exists(file_path):
                pixmap = QPixmap(file_path)
                if not pixmap.isNull() and pixmap.width() > 0 and pixmap.height() > 0:
                    ratio = min(max_w / pixmap.width(), max_h / pixmap.height())
                    ratio = min(ratio, 1.0)
                    width = max(1, int(pixmap.width() * ratio))
                    height = max(1, int(pixmap.height() * ratio))

            return (
                f'<img src="{uri}" width="{width}" height="{height}" '
                'style="display:block;margin:0 auto;border-radius:2px;" />'
            )

        def _normalize_eye_label(eye_label_value: str) -> str:
            eye_name = str(eye_label_value or "").strip().lower()
            if eye_name in ("left", "left eye", "os"):
                return "Left Eye"
            if eye_name in ("right", "right eye", "od"):
                return "Right Eye"
            return str(eye_label_value or "Eye").strip() or "Eye"

        def _referral_eye_block(eye_label_value: str, source_uri: str, source_path: str) -> str:
            source_html = _scaled_referral_image(source_uri, source_path, "Fundus image not available")
            return f"""
    <div class=\"image-box keep-together\">
        <div style=\"font-size:9.2pt;font-weight:700;color:#1f2937;margin-bottom:10px;\">{esc(_normalize_eye_label(eye_label_value))}</div>
        <div style=\"font-size:8pt;font-weight:700;color:#4b5563;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:6px;\">Fundus Image</div>
        <div style=\"text-align:center;background:#ffffff;padding:8px;border:1px solid #e5e7eb;min-height:230px;\">{source_html}</div>
    </div>
"""

        referral_eye_blocks = []
        seen_eyes = set()
        for eye_record in eye_records:
            eye_label = str(eye_record.get("eyes") or "").strip() or "Eye"
            source_path = str(eye_record.get("source_image_path") or "").strip()
            source_uri = _resolve_image_uri(source_path)
            dedupe_key = (eye_label.lower(), source_path)
            if dedupe_key in seen_eyes:
                continue
            seen_eyes.add(dedupe_key)
            referral_eye_blocks.append(
                _referral_eye_block(eye_label, source_uri, source_path)
            )

        if not referral_eye_blocks:
            fallback_source_path = str(full.get("source_image_path") or "").strip()
            referral_eye_blocks.append(
                _referral_eye_block(
                    str(full.get("eyes") or "Eye").strip() or "Eye",
                    _resolve_image_uri(fallback_source_path),
                    fallback_source_path,
                )
            )

        is_bilateral_referral = len(referral_eye_blocks) > 1
        if is_bilateral_referral:
            referral_images_html = (
                '<div class="subject">Bilateral Fundus Images Captured</div>'
                '<div class="paragraph">The following retinal fundus images from both screened eyes are attached for specialist reference.</div>'
                + "".join(referral_eye_blocks)
            )
        else:
            referral_images_html = (
                '<div class="subject">Fundus Image Captured</div>'
                '<div class="paragraph">The following retinal fundus image was captured during this screening encounter and is attached for specialist reference.</div>'
                + "".join(referral_eye_blocks)
            )

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
    .sheet {{ padding: 20px 30px; }}
    .page-break {{ page-break-before: always; }}
    .header-grid {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; }}
    .header-grid td {{ width: 100%; vertical-align: top; padding: 0; }}
    .header-block {{ font-size: 10.8pt; line-height: 1.65; }}
    .date-line {{ font-size: 10.8pt; line-height: 1.65; margin-bottom: 8px; }}
    .label {{ font-weight: 700; }}
    .subject {{ margin: 10px 0 10px 0; font-size: 11pt; font-weight: 700; }}
    .paragraph {{ margin: 0 0 8px 0; text-align: justify; line-height: 1.45; }}
    .patient-box {{
        border: 1px solid #d1d5db;
        background: #fafafa;
        padding: 12px 14px;
        margin: 10px 0 10px 0;
    }}
    .patient-box table {{ width: 100%; border-collapse: collapse; }}
    .patient-box td {{ padding: 4px 0; vertical-align: top; font-size: 9.5pt; line-height: 1.35; }}
    .closing {{ margin-top: 12px; }}
    .signature-line {{ margin-top: 20px; border-top: 1px solid #374151; width: 260px; }}
    .keep-together {{ page-break-inside: avoid; break-inside: avoid-page; }}
    .image-box {{ border: 1px solid #d1d5db; background: #fafafa; padding: 12px 14px; margin: 10px 0 16px 0; page-break-inside: avoid; break-inside: avoid-page; }}
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
        The current AI screening result indicates <b>{esc(ai_result_raw)}</b>. Final diagnosis based on ICDR by doctor is <b>{esc(result_raw)}</b> with <b>{esc(urgency)}</b> referral priority.
        Screening was performed on {screen_date_text}.
    </div>

    <div class=\"patient-box\">
        <table>
            <tr>
                <td style=\"width:50%;\"><span class=\"label\">Patient Name:</span> {patient_name}</td>
                <td><span class=\"label\">Date of Birth:</span> {patient_dob}</td>
            </tr>
            <tr>
                <td style=\"width:50%;\"><span class=\"label\">Age:</span> {patient_age}</td>
                <td><span class=\"label\">Sex:</span> {patient_sex}</td>
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

    <div class=\"closing keep-together\">
        <div style=\"margin-bottom:8px;\">Sincerely,</div>
        <div class=\"signature-line\"></div>
        <div style="margin-top:8px;"><b>{esc(finalized_by_label)}</b></div>
        <div style=\"font-size:10pt;color:#4b5563;\">Referring Clinician</div>
    </div>
</div>

<div class="page-break"></div>

<div class="sheet">
    {referral_images_html}
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
        del writer
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            QMessageBox.warning(
                self,
                "Generate Referral",
                "Referral PDF was not created. Please choose a writable folder and try again.",
            )
            return
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
