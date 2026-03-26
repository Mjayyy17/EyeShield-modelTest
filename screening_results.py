"""
Results window module for EyeShield EMR application.
Contains the ResultsWindow class and clinical explanation generation.
"""

from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
import re

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QMessageBox, QFileDialog, QStyle, QProgressDialog, QApplication
)
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QIcon, QPalette
from PySide6.QtCore import Qt, QSize, QEvent, QTimer, QByteArray, QBuffer, QIODevice

from screening_styles import DR_COLORS, DR_RECOMMENDATIONS, PROGRESSBAR_STYLE
from screening_widgets import ClickableImageLabel
from safety_runtime import can_write_directory, get_free_space_mb, write_activity


def _generate_explanation(
    result_class: str,
    confidence_text: str,
    patient_data: dict | None = None,
) -> str:
    """
    Build a personalised clinical explanation from the DR grade,
    model confidence, and the patient's clinical profile.
    Returns HTML-ready text (paragraphs separated by <br><br>).
    """
    pd       = patient_data or {}
    age      = int(pd.get("age",  0))
    hba1c    = float(pd.get("hba1c", 0.0))
    duration = int(pd.get("duration", 0))
    prev_tx  = bool(pd.get("prev_treatment", False))
    d_type   = str(pd.get("diabetes_type", "")).strip()
    eye      = str(pd.get("eye", "")).strip()

    eye_phrase = f"the {eye.lower()}" if eye and eye.lower() not in ("", "select") else "the screened eye"

    # ── Opening sentence: finding ─────────────────────────────────────────────
    opening_map = {
        "No DR":            f"No signs of diabetic retinopathy were detected in {eye_phrase}",
        "Mild DR":          f"Early microaneurysms consistent with mild non-proliferative diabetic "
                            f"retinopathy (NPDR) were identified in {eye_phrase}",
        "Moderate DR":      f"Microaneurysms, haemorrhages, and/or hard exudates consistent with "
                            f"moderate non-proliferative diabetic retinopathy (NPDR) were detected "
                            f"in {eye_phrase}",
        "Severe DR":        f"Extensive haemorrhages, venous beading, or intraretinal microvascular "
                            f"abnormalities consistent with severe NPDR were detected in {eye_phrase}",
        "Proliferative DR": f"Neovascularisation indicative of proliferative diabetic retinopathy "
                            f"(PDR) — a sight-threatening condition — was detected in {eye_phrase}",
    }
    paragraphs = [
        opening_map.get(result_class, f"{result_class} was detected in {eye_phrase}")
        + f" ({confidence_text.lower()})."
    ]

    # ── Patient context ────────────────────────────────────────────────────────
    ctx = []
    if age > 0:
        ctx.append(f"{age}‑year‑old")
    if d_type and d_type.lower() not in ("select", ""):
        ctx.append(f"{d_type} diabetes")
    if duration > 0:
        ctx.append(f"{duration}‑year diabetes duration")
    if ctx:
        paragraphs.append("<b>Patient profile:</b> " + ", ".join(ctx) + ".")

    # ── Risk factor commentary ─────────────────────────────────────────────────
    risk = []
    if hba1c >= 9.0:
        risk.append(
            f"HbA1c of <b>{hba1c:.1f}%</b> indicates poor glycaemic control, which substantially "
            "increases the risk of retinopathy progression and macular oedema."
        )
    elif hba1c >= 7.5:
        risk.append(
            f"HbA1c of <b>{hba1c:.1f}%</b> is above the recommended target (≤7.0–7.5%). "
            "Tighter glycaemic management is advised to slow disease progression."
        )
    elif hba1c > 0.0:
        risk.append(
            f"HbA1c of <b>{hba1c:.1f}%</b> is within an acceptable range. "
            "Continue current glycaemic management strategy."
        )

    if duration >= 15 and result_class != "No DR":
        risk.append(
            f"A diabetes duration of <b>{duration} years</b> is a recognised risk factor for "
            "bilateral retinal involvement; bilateral screening is recommended if not already performed."
        )
    elif result_class in ("Severe DR", "Proliferative DR") and duration >= 10:
        risk.append(
            f"Diabetes duration of <b>{duration} years</b> is consistent with the advanced retinal findings observed."
        )

    if prev_tx and result_class != "No DR":
        risk.append(
            "A history of prior DR treatment requires close monitoring for recurrence, "
            "progression, or treatment-related complications."
        )

    if risk:
        paragraphs.append("<br>".join(risk))

    # ── Recommendation ─────────────────────────────────────────────────────────
    rec_map = {
        "No DR":            "Maintain optimal glycaemic and blood pressure control. "
                            "Annual retinal screening is recommended.",
        "Mild DR":          "Intensify glycaemic and blood pressure management. "
                            "Schedule a repeat retinal examination in 6–12 months.",
        "Moderate DR":      "Ophthalmology referral within 3 months is advised. "
                            "Reassess systemic metabolic control and consider treatment intensification.",
        "Severe DR":        "Urgent ophthalmology referral is required. "
                            "The 1-year risk of progression to proliferative disease is high without intervention.",
        "Proliferative DR": "Immediate ophthalmology referral is required. "
                            "Treatment may include laser photocoagulation, intravitreal anti-VEGF therapy, "
                            "or vitreoretinal surgery.",
    }
    paragraphs.append(
        "<b>Recommendation:</b> "
        + rec_map.get(result_class, "Consult a qualified ophthalmologist for further evaluation.")
    )

    return "<br><br>".join(paragraphs)


class ResultsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.setMinimumSize(1080, 760)
        self._icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

        # Report generation state — updated by set_results()
        self._current_image_path   = ""
        self._current_heatmap_path = ""
        self._current_result_class = "Pending"
        self._current_confidence   = ""
        self._current_eye_label    = ""
        self._current_patient_name = ""
        self._save_state_timer = QTimer(self)
        self._save_state_timer.setSingleShot(True)
        self._save_state_timer.timeout.connect(self._reset_save_button_default)
        self._uncertainty_pct = 0.0

        # Outer layout holds only the scroll area so the whole page is scrollable.
        _outer = QVBoxLayout(self)
        _outer.setContentsMargins(0, 0, 0, 0)
        _outer.setSpacing(0)

        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setFrameShape(QFrame.Shape.NoFrame)
        _outer.addWidget(_scroll)

        _container = QWidget()
        _scroll.setWidget(_container)

        layout = QVBoxLayout(_container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        heading_col = QVBoxLayout()
        heading_col.setSpacing(8)
        self.breadcrumb_label = QLabel("SCREENING RESULTS")
        self.breadcrumb_label.setObjectName("crumbLabel")
        heading_col.addWidget(self.breadcrumb_label)

        self.title_label = QLabel("Results")
        self.title_label.setFont(QFont("DM Sans", 26, QFont.Weight.Bold))
        self.title_label.setObjectName("pageHeader")
        heading_col.addWidget(self.title_label)

        self.subtitle_label = QLabel("Review model output, confidence, and clinical support notes.")
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setWordWrap(True)
        heading_col.addWidget(self.subtitle_label)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)
        self.eye_badge_label = QLabel("\u2022 Right Eye")
        self.eye_badge_label.setObjectName("infoPill")
        self.eye_badge_label.setMinimumHeight(30)
        pills_row.addWidget(self.eye_badge_label)

        self.save_status_label = QLabel("Saved \u2713")
        self.save_status_label.setObjectName("savedPill")
        self.save_status_label.setMinimumHeight(30)
        self.save_status_label.hide()
        pills_row.addWidget(self.save_status_label)
        pills_row.addStretch(1)
        heading_col.addLayout(pills_row)
        top_row.addLayout(heading_col, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_back = QPushButton("\u2190 Back")
        self.btn_back.setObjectName("dangerAction")
        self.btn_back.setMinimumHeight(36)
        self.btn_back.setIconSize(QSize(18, 18))
        self.btn_back.clicked.connect(self.go_back)
        action_row.addWidget(self.btn_back)

        self.btn_save = QPushButton("Save Result")
        self.btn_save.setObjectName("primaryAction")
        self.btn_save.setMinimumHeight(36)
        self.btn_save.setIconSize(QSize(18, 18))
        self.btn_save.clicked.connect(self.save_patient)
        action_row.addWidget(self.btn_save)

        self.btn_report = QPushButton("Generate Report")
        self.btn_report.setObjectName("neutralAction")
        self.btn_report.setMinimumHeight(36)
        self.btn_report.setIconSize(QSize(18, 18))
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self.generate_report)
        action_row.addWidget(self.btn_report)

        self.btn_screen_another = QPushButton("Screen Other Eye")
        self.btn_screen_another.setObjectName("neutralAction")
        self.btn_screen_another.setMinimumHeight(36)
        self.btn_screen_another.setIconSize(QSize(18, 18))
        self.btn_screen_another.clicked.connect(self._on_screen_another)
        action_row.addWidget(self.btn_screen_another)

        self.btn_new = QPushButton("+ New Patient")
        self.btn_new.setObjectName("primaryAction")
        self.btn_new.setMinimumHeight(36)
        self.btn_new.setIconSize(QSize(18, 18))
        self.btn_new.clicked.connect(self.new_patient)
        action_row.addWidget(self.btn_new)

        top_row.addLayout(action_row)
        layout.addLayout(top_row)

        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)   # indeterminate / marquee
        self._loading_bar.setFixedHeight(4)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setStyleSheet("""
            QProgressBar {
                background: #e5e7eb;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 2px;
            }
        """)
        self._loading_bar.hide()
        layout.addWidget(self._loading_bar)

        self.save_note_label = QLabel("")
        self.save_note_label.setObjectName("metaText")
        self.save_note_label.hide()
        layout.addWidget(self.save_note_label)

        image_row = QHBoxLayout()
        image_row.setSpacing(12)

        source_card = QGroupBox("")
        source_card.setObjectName("resultGroupCard")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(12, 12, 12, 12)
        source_layout.setSpacing(8)
        source_head = QHBoxLayout()
        source_head.setSpacing(6)
        source_title = QLabel("Source Image - Fundus")
        source_title.setObjectName("cardHeaderLabel")
        source_head.addWidget(source_title)
        source_head.addStretch(1)
        source_expand = QLabel("\u2922")
        source_expand.setObjectName("expandGlyph")
        source_head.addWidget(source_expand)
        source_layout.addLayout(source_head)
        self.source_label = ClickableImageLabel("", "Source Image - Fundus")
        self.source_label.setObjectName("sourceImageSurface")
        self.source_label.setMinimumHeight(320)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setWordWrap(True)
        source_layout.addWidget(self.source_label)

        heatmap_card = QGroupBox("")
        heatmap_card.setObjectName("resultGroupCard")
        heatmap_layout = QVBoxLayout(heatmap_card)
        heatmap_layout.setContentsMargins(12, 12, 12, 12)
        heatmap_layout.setSpacing(8)
        heatmap_head = QHBoxLayout()
        heatmap_head.setSpacing(6)
        heatmap_title = QLabel("Grad-CAM++ Heatmap")
        heatmap_title.setObjectName("cardHeaderLabel")
        heatmap_head.addWidget(heatmap_title)
        heatmap_head.addStretch(1)
        heatmap_expand = QLabel("\u2922")
        heatmap_expand.setObjectName("expandGlyph")
        heatmap_head.addWidget(heatmap_expand)
        heatmap_layout.addLayout(heatmap_head)
        self.heatmap_label = ClickableImageLabel("", "Grad-CAM++ Heatmap")
        self.heatmap_label.setObjectName("heatmapImageSurface")
        self.heatmap_label.setMinimumHeight(320)
        self.heatmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heatmap_label.setWordWrap(True)
        heatmap_layout.addWidget(self.heatmap_label)

        image_row.addWidget(source_card, 1)
        image_row.addWidget(heatmap_card, 1)
        layout.addLayout(image_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        class_card = QFrame()
        class_card.setObjectName("resultStatCard")
        class_layout = QVBoxLayout(class_card)
        class_layout.setContentsMargins(14, 14, 14, 14)
        class_layout.setSpacing(6)
        class_title = QLabel("CLASSIFICATION")
        class_title.setObjectName("resultStatTitle")
        self.classification_value = QLabel("Pending")
        self.classification_value.setObjectName("classificationValue")
        self.classification_subtitle = QLabel("Awaiting model result")
        self.classification_subtitle.setObjectName("metaText")
        self.classification_subtitle.setWordWrap(True)
        class_layout.addWidget(class_title)
        class_layout.addWidget(self.classification_value)
        class_layout.addWidget(self.classification_subtitle)

        confidence_card = QFrame()
        confidence_card.setObjectName("resultStatCard")
        confidence_layout = QVBoxLayout(confidence_card)
        confidence_layout.setContentsMargins(14, 14, 14, 14)
        confidence_layout.setSpacing(6)
        confidence_title = QLabel("CONFIDENCE")
        confidence_title.setObjectName("resultStatTitle")
        self.confidence_value = QLabel("0.0%")
        self.confidence_value.setObjectName("monoValue")
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 1000)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setObjectName("confidenceBar")
        self.confidence_bar.setFixedHeight(6)
        self.uncertainty_value = QLabel("UNCERTAINTY 0.0%")
        self.uncertainty_value.setObjectName("uncertaintyValue")
        self.uncertainty_bar = QProgressBar()
        self.uncertainty_bar.setRange(0, 1000)
        self.uncertainty_bar.setValue(0)
        self.uncertainty_bar.setTextVisible(False)
        self.uncertainty_bar.setObjectName("uncertaintyBar")
        self.uncertainty_bar.setFixedHeight(6)
        confidence_layout.addWidget(confidence_title)
        confidence_layout.addWidget(self.confidence_value)
        confidence_layout.addWidget(self.confidence_bar)
        confidence_layout.addWidget(self.uncertainty_value)
        confidence_layout.addWidget(self.uncertainty_bar)

        reco_card = QFrame()
        reco_card.setObjectName("resultStatCard")
        reco_layout = QVBoxLayout(reco_card)
        reco_layout.setContentsMargins(14, 14, 14, 14)
        reco_layout.setSpacing(6)
        reco_title = QLabel("RECOMMENDATION")
        reco_title.setObjectName("resultStatTitle")
        self.recommendation_value = QLabel("Consult eye care specialist")
        self.recommendation_value.setObjectName("resultStatValue")
        self.recommendation_value.setWordWrap(True)
        self.recommendation_badge = QLabel("Routine follow-up")
        self.recommendation_badge.setObjectName("okBadge")
        reco_layout.addWidget(reco_title)
        reco_layout.addWidget(self.recommendation_value)
        reco_layout.addWidget(self.recommendation_badge, 0, Qt.AlignmentFlag.AlignLeft)

        stats_row.addWidget(class_card, 1)
        stats_row.addWidget(confidence_card, 1)
        stats_row.addWidget(reco_card, 1)
        layout.addLayout(stats_row)

        # Bilateral comparison card (hidden until second eye is being reviewed)
        self.bilateral_frame = QFrame()
        self.bilateral_frame.setObjectName("resultStatCard")
        bilateral_layout = QVBoxLayout(self.bilateral_frame)
        bilateral_layout.setContentsMargins(14, 12, 14, 12)
        bilateral_layout.setSpacing(8)
        bilateral_title = QLabel("↔  Bilateral Screening Comparison")
        bilateral_title.setObjectName("resultStatTitle")
        bilateral_layout.addWidget(bilateral_title)
        brow = QHBoxLayout()
        brow.setSpacing(20)
        first_col = QVBoxLayout()
        first_col.setSpacing(4)
        self.bilateral_first_eye_lbl = QLabel("—")
        self.bilateral_first_eye_lbl.setObjectName("resultStatTitle")
        self.bilateral_first_result_lbl = QLabel("—")
        self.bilateral_first_result_lbl.setObjectName("resultStatValue")
        self.bilateral_first_saved_lbl = QLabel("✓ Saved")
        self.bilateral_first_saved_lbl.setStyleSheet("font-weight:700;font-size:13px;")
        self.bilateral_first_saved_lbl.setObjectName("successLabel")
        first_col.addWidget(self.bilateral_first_eye_lbl)
        first_col.addWidget(self.bilateral_first_result_lbl)
        first_col.addWidget(self.bilateral_first_saved_lbl)
        brow_div = QFrame()
        brow_div.setFrameShape(QFrame.Shape.VLine)
        brow_div.setFrameShadow(QFrame.Shadow.Plain)
        brow_div.setStyleSheet("color:#d9e5f2;")
        second_col = QVBoxLayout()
        second_col.setSpacing(4)
        self.bilateral_second_eye_lbl = QLabel("—")
        self.bilateral_second_eye_lbl.setObjectName("resultStatTitle")
        self.bilateral_second_result_lbl = QLabel("—")
        self.bilateral_second_result_lbl.setObjectName("resultStatValue")
        self.bilateral_second_saved_lbl = QLabel("Unsaved")
        self.bilateral_second_saved_lbl.setStyleSheet("font-weight:700;font-size:13px;")
        self.bilateral_second_saved_lbl.setObjectName("errorLabel")
        second_col.addWidget(self.bilateral_second_eye_lbl)
        second_col.addWidget(self.bilateral_second_result_lbl)
        second_col.addWidget(self.bilateral_second_saved_lbl)
        brow.addLayout(first_col)
        brow.addWidget(brow_div)
        brow.addLayout(second_col)
        bilateral_layout.addLayout(brow)
        self.bilateral_frame.hide()
        layout.addWidget(self.bilateral_frame)

        self._apply_action_icons()

        explanation_group = QGroupBox("Clinical Summary")
        explanation_group.setObjectName("resultGroupCard")
        explanation_layout = QVBoxLayout(explanation_group)
        explanation_layout.setContentsMargins(14, 14, 14, 14)
        explanation_layout.setSpacing(10)

        self.summary_line_1 = QLabel("No signs of diabetic retinopathy detected")
        self.summary_line_1.setObjectName("summaryRowSuccess")
        self.summary_line_1.setWordWrap(True)
        explanation_layout.addWidget(self.summary_line_1)

        self.summary_line_2 = QLabel("Patient profile: awaiting demographic and glycaemic context")
        self.summary_line_2.setObjectName("summaryRowInfo")
        self.summary_line_2.setWordWrap(True)
        explanation_layout.addWidget(self.summary_line_2)

        self.summary_line_3 = QLabel("Model uncertainty note: calibrate with specialist review")
        self.summary_line_3.setObjectName("summaryRowWarn")
        self.summary_line_3.setWordWrap(True)
        explanation_layout.addWidget(self.summary_line_3)

        self.explanation = QLabel("")
        self.explanation.setWordWrap(True)
        self.explanation.setObjectName("summaryBody")
        explanation_layout.addWidget(self.explanation)

        layout.addWidget(explanation_group)

        self.footer_label = QLabel(
            "Grad-CAM++ \u2022 Automated DR Screening v2.1 \u2022 Results are decision-support tools, not a clinical diagnosis"
        )
        self.footer_label.setObjectName("footerLabel")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setWordWrap(True)
        layout.addWidget(self.footer_label)

        self.setStyleSheet("""
            QWidget {
                background: #f3f4f6;
                color: #1f2937;
                font-family: "DM Sans", "Segoe UI", "Inter", sans-serif;
                font-size: 14px;
            }
            QScrollArea { border: none; }
            QLabel#crumbLabel {
                color: #6b7280;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.3px;
            }
            QLabel#pageHeader {
                font-size: 34px;
                font-weight: 700;
                color: #111827;
                letter-spacing: 0.1px;
            }
            QLabel#pageSubtitle {
                color: #6b7280;
                font-size: 13px;
            }
            QLabel#infoPill {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 20px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#savedPill {
                background: #ecfdf3;
                color: #166534;
                border: 1px solid #86efac;
                border-radius: 20px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QGroupBox#resultGroupCard {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                margin-top: 0;
            }
            QGroupBox#resultGroupCard::title {
                color: transparent;
                subcontrol-origin: margin;
                left: 0;
                padding: 0;
            }
            QLabel#cardHeaderLabel {
                color: #374151;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#expandGlyph {
                color: #6b7280;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#sourceImageSurface {
                background: #000000;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #9ca3af;
                font-size: 13px;
            }
            QLabel#heatmapImageSurface {
                background: #0b0f19;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #9ca3af;
                font-size: 14px;
            }
            QFrame#resultStatCard {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 12px;
            }
            QLabel#resultStatTitle {
                color: #6b7280;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.9px;
            }
            QLabel#classificationValue {
                color: #166534;
                font-size: 33px;
                font-weight: 800;
            }
            QLabel#resultStatValue {
                color: #111827;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#monoValue {
                color: #1f2937;
                font-family: "DM Mono", "Consolas", monospace;
                font-size: 24px;
                font-weight: 700;
            }
            QProgressBar#confidenceBar {
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                background: #eff6ff;
            }
            QProgressBar#confidenceBar::chunk {
                background: #2563eb;
                border-radius: 4px;
            }
            QProgressBar#uncertaintyBar {
                border: 1px solid #fde68a;
                border-radius: 4px;
                background: #fffbeb;
            }
            QProgressBar#uncertaintyBar::chunk {
                background: #d97706;
                border-radius: 4px;
            }
            QLabel#metaText {
                color: #4b5563;
                font-size: 12px;
                font-weight: 500;
            }
            QFrame#uncertaintyPanel {
                background: #fffbeb;
                border: 1px solid #f59e0b;
                border-radius: 8px;
            }
            QLabel#uncertaintyValue {
                color: #92400e;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 0.4px;
            }
            QLabel#okBadge {
                background: #ecfdf3;
                color: #166534;
                border: 1px solid #86efac;
                border-radius: 20px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#summaryBody {
                background: transparent;
                border: none;
                border-radius: 0;
                color: #374151;
                font-size: 12px;
                font-weight: 500;
                line-height: 1.45;
                padding: 0;
            }
            QLabel#summaryRowSuccess {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 2px 0;
                color: #166534;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#summaryRowInfo {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 2px 0;
                color: #1d4ed8;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#summaryRowWarn {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 2px 0;
                color: #b45309;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#footerLabel {
                color: #6b7280;
                font-size: 11px;
                padding-top: 6px;
            }
            QPushButton {
                background: #ffffff;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #f9fafb;
            }
            QPushButton:disabled {
                background: #f3f4f6;
                color: #94a3b8;
                border-color: #e5e7eb;
            }
            QPushButton#primaryAction {
                background: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
            }
            QPushButton#primaryAction:hover {
                background: #1d4ed8;
            }
            QPushButton#neutralAction {
                background: #ffffff;
                color: #1f2937;
                border: 1px solid #d1d5db;
            }
            QPushButton#neutralAction:hover {
                background: #f9fafb;
            }
            QPushButton#dangerAction {
                background: #fef2f2;
                color: #b91c1c;
                border: 1px solid #fca5a5;
            }
            QPushButton#dangerAction:hover {
                background: #fee2e2;
            }
        """)

    def _is_dark_theme(self) -> bool:
        bg = self.palette().color(QPalette.ColorRole.Window)
        fg = self.palette().color(QPalette.ColorRole.WindowText)
        return bg.lightness() < fg.lightness()

    def _build_action_icon(self, filename: str, fallback: QStyle.StandardPixmap) -> QIcon:
        icon_path = os.path.join(self._icons_dir, filename)
        base_icon = QIcon(icon_path) if os.path.isfile(icon_path) else self.style().standardIcon(fallback)
        source = base_icon.pixmap(QSize(24, 24))
        if source.isNull():
            return base_icon

        tint = QColor("#f8fafc") if self._is_dark_theme() else QColor("#1f2937")
        tinted = QPixmap(source.size())
        tinted.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), tint)
        painter.end()

        icon = QIcon()
        icon.addPixmap(tinted, QIcon.Mode.Normal)
        icon.addPixmap(tinted, QIcon.Mode.Active)

        disabled = QPixmap(tinted)
        p2 = QPainter(disabled)
        p2.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p2.fillRect(disabled.rect(), QColor(tint.red(), tint.green(), tint.blue(), 110))
        p2.end()
        icon.addPixmap(disabled, QIcon.Mode.Disabled)
        return icon

    def _apply_action_icons(self):
        self.btn_save.setIcon(self._build_action_icon("save_patient.svg", QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_report.setIcon(self._build_action_icon("generate.svg", QStyle.StandardPixmap.SP_ArrowDown))
        self.btn_screen_another.setIcon(self._build_action_icon("another_eye.svg", QStyle.StandardPixmap.SP_FileDialogStart))
        self.btn_new.setIcon(self._build_action_icon("new_patient.svg", QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.btn_back.setIcon(self._build_action_icon("back_to_screening.svg", QStyle.StandardPixmap.SP_ArrowBack))

    def changeEvent(self, event):
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self._apply_action_icons()
        super().changeEvent(event)

    def _create_stat_card(self, title_text):
        card = QFrame()
        card.setObjectName("resultStatCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(4)

        title = QLabel(title_text)
        title.setObjectName("resultStatTitle")
        value = QLabel("Pending")
        value.setObjectName("resultStatValue")
        value.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(value)
        return card, value

    @staticmethod
    def _extract_percent_value(value_text: str) -> float:
        txt = str(value_text or "")
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", txt)
        if not match:
            return 0.0
        try:
            return max(0.0, min(100.0, float(match.group(1))))
        except ValueError:
            return 0.0

    @staticmethod
    def _format_percent(value: float) -> str:
        return f"{max(0.0, min(100.0, value)):.1f}%"

    def _reset_save_button_default(self):
        self.btn_save.setEnabled(True)
        self.btn_save.setText("Save Result")
        self.btn_save.setObjectName("primaryAction")
        self.btn_save.setStyle(self.btn_save.style())
        self.save_note_label.hide()

    def _set_save_state(self, state: str, details: str = ""):
        if state == "writing":
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Saving to disk...")
            self.save_note_label.setText(details or "Writing local record...")
            self.save_note_label.show()
            return

        if state == "success":
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Saved ✓")
            self.save_note_label.setText(details)
            self.save_note_label.show()
            self._save_state_timer.start(4000)
            return

        if state == "unchanged":
            self.btn_save.setEnabled(True)
            self.btn_save.setText("Save Result")
            self.save_note_label.setText("No changes since last save")
            self.save_note_label.show()
            self._save_state_timer.start(4000)
            return

        if state == "failed":
            self.btn_save.setEnabled(True)
            self.btn_save.setText("Save Failed")
            self.save_note_label.setText(details)
            self.save_note_label.show()
            return

        self._reset_save_button_default()

    def is_uncertainty_blocking(self) -> bool:
        return False

    def _acknowledge_uncertainty(self):
        return

    def set_results(self, patient_name, image_path, result_class="Pending", confidence_text="Pending", eye_label="", first_eye_result=None, heatmap_path="", patient_data=None, heatmap_pending=False):
        is_loading = result_class in ("Analyzing…", "Pending")
        is_busy = is_loading or heatmap_pending

        if patient_name:
            self.title_label.setText(f"Results for {patient_name}")
        else:
            self.title_label.setText("Results")
        self.eye_badge_label.setText(f"• {eye_label or 'Screened Eye'}")

        # Loading bar
        if is_busy:
            self._loading_bar.show()
        else:
            self._loading_bar.hide()

        # Reset save feedback state
        self.save_status_label.hide()
        self.save_status_label.setText("Saved ✓")
        self.btn_save.setEnabled(not is_busy)
        self.btn_save.setText("Save Result")
        self.btn_save.setObjectName("primaryAction")
        self.btn_save.setStyle(self.btn_save.style())
        self.btn_screen_another.setEnabled(not is_busy)

        # Bilateral comparison
        if first_eye_result:
            self.bilateral_first_eye_lbl.setText(first_eye_result.get("eye", "—"))
            self.bilateral_first_result_lbl.setText(first_eye_result.get("result", "—"))
            self.bilateral_second_eye_lbl.setText(eye_label or "Current Eye")
            self.bilateral_second_result_lbl.setText(result_class)
            self.bilateral_second_saved_lbl.setText("Unsaved")
            self.bilateral_second_saved_lbl.setStyleSheet("font-weight:700;font-size:13px;")
            self.bilateral_second_saved_lbl.setObjectName("errorLabel")
            self.bilateral_frame.show()
        else:
            self.bilateral_frame.hide()

        # Classification with severity colour
        self.classification_value.setText(result_class)
        grade_color = DR_COLORS.get(result_class, "#1f2937")
        self.classification_value.setStyleSheet(f"color:{grade_color};font-size:33px;font-weight:800;")

        class_subtitles = {
            "No DR": "No diabetic retinopathy detected",
            "Mild DR": "Mild non-proliferative diabetic retinopathy",
            "Moderate DR": "Moderate non-proliferative diabetic retinopathy",
            "Severe DR": "Severe non-proliferative diabetic retinopathy",
            "Proliferative DR": "Proliferative diabetic retinopathy",
        }
        self.classification_subtitle.setText(class_subtitles.get(result_class, "Clinical review advised"))

        confidence_pct = self._extract_percent_value(confidence_text)
        confidence_display = self._format_percent(confidence_pct)
        self.confidence_value.setText(confidence_display)
        self.confidence_bar.setValue(int(round(confidence_pct * 10)))

        uncertainty_match = re.search(r"uncertainty\s*:?\s*(\d+(?:\.\d+)?)\s*%", str(confidence_text or ""), re.IGNORECASE)
        if uncertainty_match:
            uncertainty_pct = max(0.0, min(100.0, float(uncertainty_match.group(1))))
        else:
            uncertainty_pct = max(0.0, min(100.0, 100.0 - confidence_pct))
        self._uncertainty_pct = uncertainty_pct
        self.uncertainty_value.setText(f"Uncertainty {self._format_percent(uncertainty_pct)}")
        self.uncertainty_bar.setValue(int(round(uncertainty_pct * 10)))

        # Grade-specific recommendation
        recommendation = DR_RECOMMENDATIONS.get(result_class, "Consult an eye care specialist")
        if is_loading:
            recommendation = "—"
        self.recommendation_value.setText(recommendation)
        self.recommendation_badge.setText("Routine follow-up" if result_class == "No DR" else "Clinical follow-up")

        # Subtitle
        if is_loading:
            self.subtitle_label.setText("Running DR analysis — please wait…")
        elif heatmap_pending:
            conf_part = f" with confidence {confidence_display}" if confidence_text else ""
            self.subtitle_label.setText(
                f"Screening complete — {result_class}{conf_part}. "
                "Generating the Grad-CAM++ heatmap now."
            )
        else:
            conf_part = f" with confidence {confidence_display}" if not is_loading else ""
            self.subtitle_label.setText(
                f"Screening complete — {result_class}{conf_part}. "
                "Review source fundus, Grad-CAM++ heatmap, and the clinical summary below."
            )

        # Image and heatmap panels
        if image_path:
            source_pixmap = QPixmap(image_path)
            self.source_label.set_viewable_pixmap(source_pixmap, 520, 390)
            if is_loading:
                self.heatmap_label.clear_view("")
            elif heatmap_pending:
                self.heatmap_label.clear_view("")
            elif heatmap_path and os.path.isfile(heatmap_path):
                hmap_pixmap = QPixmap(heatmap_path)
                self.heatmap_label.set_viewable_pixmap(hmap_pixmap, 520, 390)
            else:
                self.heatmap_label.clear_view("")
        else:
            self.source_label.clear_view("")
            self.heatmap_label.clear_view("")

        # Clinical summary
        if is_loading:
            self.summary_line_1.setText("■ No signs of diabetic retinopathy detected")
            self.summary_line_2.setText("■ Patient profile: awaiting demographic and glycaemic context")
            self.summary_line_3.setText("■ Model uncertainty note: update after analysis")
            self.explanation.setText("Awaiting model output…")
        else:
            pd = patient_data or {}
            age = pd.get("age")
            hba1c = pd.get("hba1c")
            age_txt = f"{age}-year-old" if age not in (None, "", 0, "0") else "Patient"
            hba1c_txt = f"{hba1c}%" if hba1c not in (None, "", "0", 0) else "unavailable"

            self.summary_line_1.setText(
                "■ No signs of diabetic retinopathy detected — high uncertainty requires clinical correlation"
                if result_class == "No DR"
                else f"■ {result_class} detected — confirm with clinical examination"
            )
            self.summary_line_2.setText(
                f"■ Patient profile: {age_txt}; HbA1c {hba1c_txt}. Continue glycaemic strategy based on clinical targets"
            )
            self.summary_line_3.setText(
                f"■ Model uncertainty note: clinical review is advised (uncertainty {self._format_percent(uncertainty_pct)}); "
                "annual screening recommended unless specialist suggests shorter follow-up"
            )
            self.explanation.setText(_generate_explanation(result_class, confidence_text, patient_data))

        # Keep state current so generate_report always has the latest values
        self._current_image_path   = image_path or ""
        self._current_heatmap_path = heatmap_path or ""
        self._current_result_class = result_class
        self._current_confidence   = confidence_text
        self._current_eye_label    = eye_label
        self._current_patient_name = patient_name or ""
        _report_ready = (
            not is_busy
            and bool(image_path)
            and result_class not in ("Analyzing…", "Pending")
        )
        self.btn_report.setEnabled(_report_ready)

    def mark_saved(self, name, eye_label, result_class):
        """Called by ScreeningPage after a successful save to update this panel."""
        self.save_status_label.setText("Saved ✓")
        self.save_status_label.show()
        self.btn_save.setText("Saved ✓")
        self.btn_save.setEnabled(False)
        if self.bilateral_frame.isVisible():
            self.bilateral_second_saved_lbl.setText("✓ Saved")
            self.bilateral_second_saved_lbl.setStyleSheet("font-weight:700;font-size:13px;")
            self.bilateral_second_saved_lbl.setObjectName("successLabel")

    def go_back(self):
        if not self.parent_page:
            return
        page = self.parent_page
        if not getattr(page, "_current_eye_saved", True):
            box = QMessageBox(self)
            box.setWindowTitle("Back to Screening")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText("Unsaved changes will be lost. Are you sure you want to go back?")
            stay_btn = box.addButton("Stay", QMessageBox.ButtonRole.RejectRole)
            go_back_btn = box.addButton("Go Back", QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(stay_btn)
            box.exec()
            if box.clickedButton() != go_back_btn:
                write_activity("INFO", "DIALOG_BACK_TO_SCREENING", "Stay")
                return
            write_activity("WARNING", "DIALOG_BACK_TO_SCREENING", "Go Back")
        if hasattr(page, "stacked_widget"):
            page.stacked_widget.setCurrentIndex(0)

    def save_patient(self):
        if not self.parent_page or not hasattr(self.parent_page, "save_screening"):
            return

        self._set_save_state("writing", "Saving to local records...")
        QApplication.processEvents()
        result = self.parent_page.save_screening(reset_after=True)

        if not isinstance(result, dict):
            self._set_save_state("failed", "Save failed due to an unexpected response.")
            return

        status = result.get("status")
        if status == "saved":
            saved_path = str(result.get("path") or "")
            details = f"Saved ✓ {saved_path}" if saved_path else "Saved ✓"
            self._set_save_state("success", details)
            return

        if status == "unchanged":
            self._set_save_state("unchanged")
            return

        if status in ("error", "blocked"):
            self._set_save_state("failed", str(result.get("error") or "Save failed"))
            box = QMessageBox(self)
            box.setWindowTitle("Save Failed")
            box.setIcon(QMessageBox.Icon.Critical)
            box.setText(str(result.get("error") or "Save failed"))
            retry_btn = box.addButton("Retry", QMessageBox.ButtonRole.AcceptRole)
            change_btn = box.addButton("Change Save Location", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() == retry_btn:
                self.save_patient()
                return
            if box.clickedButton() == change_btn:
                folder = QFileDialog.getExistingDirectory(self, "Choose Save Location")
                if folder:
                    self.parent_page._custom_storage_root = folder
                    self.save_patient()
            return

        self._set_save_state("failed", "Save was not completed.")

    def new_patient(self):
        if not self.parent_page:
            return
        page = self.parent_page
        if not getattr(page, "_current_eye_saved", True):
            box = QMessageBox(self)
            box.setWindowTitle("Unsaved Screening Result")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(
                "This screening result has not been saved. Starting a new patient will permanently discard it."
            )
            save_first_btn = box.addButton("Save First", QMessageBox.ButtonRole.AcceptRole)
            discard_btn = box.addButton("Discard and Continue", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel_btn)
            box.exec()
            choice = box.clickedButton()
            if choice == save_first_btn:
                self.save_patient()
                if getattr(page, "_current_eye_saved", False):
                    write_activity("INFO", "DIALOG_NEW_PATIENT", "Save First")
                    page.reset_screening()
                return
            if choice != discard_btn:
                write_activity("INFO", "DIALOG_NEW_PATIENT", "Cancel")
                return
            write_activity("WARNING", "DIALOG_NEW_PATIENT", "Discard and Continue")
        if hasattr(page, "reset_screening"):
            page.reset_screening()

    def _on_screen_another(self):
        if self.parent_page and hasattr(self.parent_page, "screen_other_eye"):
            self.parent_page.screen_other_eye()

    # ── Report generation ──────────────────────────────────────────────────────

    def generate_report(self):
        """Generate a PDF screening report for the current patient."""
        if self._current_result_class in ("Pending", "Analyzing…") or not self._current_image_path:
            QMessageBox.information(self, "Generate Report", "No completed screening results to report.")
            return

        if self.parent_page and not getattr(self.parent_page, "_current_eye_saved", False):
            QMessageBox.warning(self, "Generate Report", "Please save the result before generating a report")
            return

        if not self.bilateral_frame.isVisible():
            box = QMessageBox(self)
            box.setWindowTitle("Single-Eye Report")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText("Only one eye has been screened. Generate a single-eye report, or screen the other eye first?")
            generate_btn = box.addButton("Generate Anyway", QMessageBox.ButtonRole.AcceptRole)
            other_eye_btn = box.addButton("Screen Other Eye First", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() == other_eye_btn:
                self._on_screen_another()
                return
            if box.clickedButton() != generate_btn:
                return

        pp = self.parent_page
        missing_profile = []
        if pp:
            if not pp.p_name.text().strip():
                missing_profile.append("Name")
            if pp.p_age.value() <= 0:
                missing_profile.append("Age")
            if pp.hba1c.value() <= 0:
                missing_profile.append("HbA1c")
        if missing_profile:
            QMessageBox.warning(
                self,
                "Profile Incomplete",
                "Patient profile is incomplete. Missing fields will appear blank in the report.\n\nMissing: " + ", ".join(missing_profile),
            )

        default_name = (
            f"EyeShield_Report_{self._current_patient_name or 'Patient'}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Screening Report", default_name, "PDF Files (*.pdf)"
        )
        if not path:
            return

        out_dir = os.path.dirname(path)
        writable, write_err = can_write_directory(out_dir)
        if not writable:
            QMessageBox.warning(
                self,
                "Generate Report",
                f"Cannot write to {out_dir}. Choose a different save location.\n\n{write_err}",
            )
            return

        free_mb = get_free_space_mb(out_dir)
        if free_mb < 50:
            QMessageBox.warning(
                self,
                "Low Disk Space",
                f"Low disk space ({free_mb} MB remaining). The report may fail to save.",
            )

        try:
            from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QTextDocument
            from PySide6.QtCore import QMarginsF
        except ImportError:
            QMessageBox.warning(self, "Generate Report", "PDF generation requires PySide6 PDF support.")
            return

        # Collect full patient data from the parent form
        patient_id = pp.p_id.text().strip() if pp and hasattr(pp, "p_id") else ""
        dob = pp.p_dob.text() if pp and hasattr(pp, "p_dob") and hasattr(pp.p_dob, "text") else ""
        age = str(pp.p_age.value()) if pp and hasattr(pp, "p_age") else ""
        sex = pp.p_sex.currentText() if pp and hasattr(pp, "p_sex") else ""
        contact = pp.p_contact.text().strip() if pp and hasattr(pp, "p_contact") else ""
        diabetes_type = pp.diabetes_type.currentText() if pp and hasattr(pp, "diabetes_type") else ""
        duration_val = pp.diabetes_duration.value() if pp and hasattr(pp, "diabetes_duration") else 0
        hba1c_num = pp.hba1c.value() if pp and hasattr(pp, "hba1c") else 0.0
        prev_tx = "Yes" if pp and hasattr(pp, "prev_treatment") and pp.prev_treatment.isChecked() else "No"
        notes = pp.notes.toPlainText().strip() if pp and hasattr(pp, "notes") else ""

        va_left = pp.va_left.text().strip() if pp and hasattr(pp, "va_left") else ""
        va_right = pp.va_right.text().strip() if pp and hasattr(pp, "va_right") else ""
        bp_sys = str(pp.bp_systolic.value()) if pp and hasattr(pp, "bp_systolic") and pp.bp_systolic.value() > 0 else ""
        bp_dia = str(pp.bp_diastolic.value()) if pp and hasattr(pp, "bp_diastolic") and pp.bp_diastolic.value() > 0 else ""
        fbs_val = str(pp.fbs.value()) if pp and hasattr(pp, "fbs") and pp.fbs.value() > 0 else ""
        rbs_val = str(pp.rbs.value()) if pp and hasattr(pp, "rbs") and pp.rbs.value() > 0 else ""

        # Collect symptoms for pill display
        symptoms = []
        if pp:
            if hasattr(pp, "symptom_blurred") and pp.symptom_blurred.isChecked():
                symptoms.append("Blurred Vision")
            if hasattr(pp, "symptom_floaters") and pp.symptom_floaters.isChecked():
                symptoms.append("Floaters")
            if hasattr(pp, "symptom_flashes") and pp.symptom_flashes.isChecked():
                symptoms.append("Flashes")
            if hasattr(pp, "symptom_vision_loss") and pp.symptom_vision_loss.isChecked():
                symptoms.append("Vision Loss")

        # Helpers
        def esc(value) -> str:
            return escape(str(value or "").strip()) or "&mdash;"

        def esc_or_dash(value) -> str:
            v = str(value or "").strip()
            return escape(v) if v and v not in ("0", "None", "Select") else "&mdash;"

        # Clinic branding from config.json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        clinic_name = "EyeShield EMR"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            clinic_name = cfg.get("clinic_name") or cfg.get("admin_contact", {}).get("location", "EyeShield EMR")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # Clean confidence text and derive result-specific report colors/content
        raw_confidence = str(self._current_confidence or "").strip()
        if raw_confidence.lower().startswith("confidence:"):
            raw_confidence = raw_confidence[len("confidence:"):].strip()
        confidence_display = escape(raw_confidence) if raw_confidence else "&mdash;"

        result_raw = str(self._current_result_class or "").strip()
        grade_color = DR_COLORS.get(result_raw, "#374151")
        grade_bg_map = {
            "No DR": "#d1f5e0",
            "Mild DR": "#fef3e2",
            "Moderate DR": "#fde8d8",
            "Severe DR": "#fde8ea",
            "Proliferative DR": "#f5d5d8",
        }
        grade_bg = grade_bg_map.get(result_raw, "#f3f4f6")

        recommendation = escape(DR_RECOMMENDATIONS.get(result_raw, "Consult a qualified ophthalmologist"))

        explanation_text = (self.explanation.text() or "").strip()
        if explanation_text:
            explanation_html = escape(explanation_text).replace("\n\n", "<br><br>").replace("\n", "<br>")
        else:
            summary_map = {
                "No DR": (
                    "No signs of diabetic retinopathy were detected in this fundus image. "
                    "Continue standard diabetes management and schedule routine annual retinal screening."
                ),
                "Mild DR": (
                    "Early microaneurysms consistent with mild non-proliferative diabetic retinopathy (NPDR) were identified. "
                    "A repeat retinal examination in 6 to 12 months is recommended."
                ),
                "Moderate DR": (
                    "Features consistent with moderate NPDR were detected. "
                    "Referral to an ophthalmologist within 3 months is advised."
                ),
                "Severe DR": (
                    "Findings are consistent with severe NPDR. "
                    "Urgent ophthalmology referral is required for further evaluation."
                ),
                "Proliferative DR": (
                    "Proliferative diabetic retinopathy was detected, a sight-threatening condition. "
                    "Immediate ophthalmology referral is required."
                ),
            }
            explanation_html = escape(summary_map.get(result_raw, "Please consult a qualified ophthalmologist."))

        report_date = datetime.now().strftime("%B %d, %Y %I:%M %p")
        screened_by_name = str(
            os.environ.get("EYESHIELD_CURRENT_NAME", "")
            or os.environ.get("EYESHIELD_CURRENT_USER", "")
        ).strip()
        screened_by_title = str(os.environ.get("EYESHIELD_CURRENT_TITLE", "")).strip()
        screened_by_raw = (
            f"{screened_by_name} ({screened_by_title})"
            if screened_by_name and screened_by_title
            else screened_by_name
        )
        screened_by = escape(screened_by_raw) if screened_by_raw else "&mdash;"

        duration_disp = f"{escape(str(duration_val))} year(s)" if duration_val and duration_val > 0 else "&mdash;"
        notes_disp = escape(notes) if notes else "&mdash;"
        hba1c_disp = f"{hba1c_num:.1f}%" if hba1c_num and hba1c_num > 0 else "&mdash;"

        bp_display = (
            f"{escape(bp_sys)}/{escape(bp_dia)} mmHg"
            if bp_sys and bp_dia
            else "&mdash;"
        )
        fbs_disp = f"{escape(fbs_val)} mg/dL" if fbs_val else "&mdash;"
        rbs_disp = f"{escape(rbs_val)} mg/dL" if rbs_val else "&mdash;"

        symptom_html = (
            " ".join(f'<span class="symptom-pill">{escape(s)}</span>' for s in symptoms)
            if symptoms
            else '<span style="color:#6b7280;">None reported</span>'
        )

        def resolve_image_path(path_value: str) -> str:
            raw = str(path_value or "").strip()
            if not raw:
                return ""
            if os.path.isabs(raw):
                candidate = raw
            else:
                candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), raw)
            if not os.path.isfile(candidate):
                return ""
            try:
                return str(Path(candidate).resolve())
            except OSError:
                return ""

        def build_embedded_image_uri(path_value: str, width: int = 150, height: int = 150) -> str:
            resolved = resolve_image_path(path_value)
            if not resolved:
                return ""

            src = QImage(resolved)
            if src.isNull():
                return ""

            fitted = src.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            canvas = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            canvas.fill(QColor("#ffffff"))
            painter = QPainter(canvas)
            x = (width - fitted.width()) // 2
            y = (height - fitted.height()) // 2
            painter.drawImage(x, y, fitted)
            painter.end()

            ba = QByteArray()
            buffer = QBuffer(ba)
            if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
                return ""
            canvas.save(buffer, "PNG")
            buffer.close()

            b64 = bytes(ba.toBase64()).decode("ascii")
            return f"data:image/png;base64,{b64}"

        source_image_uri = build_embedded_image_uri(self._current_image_path)
        heatmap_image_uri = build_embedded_image_uri(self._current_heatmap_path)

        # Report-tab-matching palette and structure
        _COL = {
            "No DR": "#166534",
            "Mild DR": "#92400e",
            "Moderate DR": "#9a3412",
            "Severe DR": "#7f1d1d",
            "Proliferative DR": "#6b1a1a",
        }
        _BG = {
            "No DR": "#f0fdf4",
            "Mild DR": "#fefce8",
            "Moderate DR": "#fff7ed",
            "Severe DR": "#fff8f8",
            "Proliferative DR": "#fff8f8",
        }
        _BORDER = {
            "No DR": "#16a34a",
            "Mild DR": "#d97706",
            "Moderate DR": "#ea580c",
            "Severe DR": "#c24141",
            "Proliferative DR": "#b91c1c",
        }
        _REC = {
            "No DR": "Annual screening recommended",
            "Mild DR": "Repeat screening in 6&#8211;12 months",
            "Moderate DR": "Ophthalmology referral within 3 months",
            "Severe DR": "Urgent ophthalmology referral",
            "Proliferative DR": "Immediate ophthalmology referral",
        }
        _SUM = {
            "No DR": "No signs of diabetic retinopathy were detected in this fundus image. Continue standard diabetes management, maintain optimal glycaemic and blood pressure control, and schedule routine annual retinal screening.",
            "Mild DR": "Early microaneurysms consistent with mild non-proliferative diabetic retinopathy (NPDR) were identified. Intensify glycaemic and blood pressure management. A repeat retinal examination in 6&#8211;12 months is recommended.",
            "Moderate DR": "Features consistent with moderate non-proliferative diabetic retinopathy (NPDR) were detected, including microaneurysms, haemorrhages, and/or hard exudates. Referral to an ophthalmologist within 3 months is advised. Reassess systemic metabolic control.",
            "Severe DR": "Findings consistent with severe non-proliferative diabetic retinopathy (NPDR) were detected. The risk of progression to proliferative disease within 12 months is high. Urgent ophthalmology referral is required.",
            "Proliferative DR": "Proliferative diabetic retinopathy (PDR) was detected &#8212; a sight-threatening condition. Immediate ophthalmology referral is required for evaluation and potential intervention, such as laser photocoagulation or intravitreal anti-VEGF therapy.",
        }
        gc = _COL.get(result_raw, "#1e3a5f")
        gbg = _BG.get(result_raw, "#f8faff")
        gb = _BORDER.get(result_raw, "#2563eb")
        rec = _REC.get(result_raw, "Consult a qualified ophthalmologist")
        summary = _SUM.get(result_raw, "Please consult a qualified ophthalmologist.")
        conf_display = confidence_display

        is_critical_grade = result_raw in ("Severe DR", "Proliferative DR")
        if is_critical_grade:
            gbg = "#b91c1c"
            gc = "#ffffff"
            gb = "#991b1b"
            badge_bg = "#7f1d1d"
            confidence_color = "#ffffff"
            divider_color = "#fecaca"
            reco_label_opacity = "1"
        else:
            badge_bg = gb
            confidence_color = "#ffffff"
            divider_color = "#ffffff"
            reco_label_opacity = "0.95"
            gc = "#ffffff"
            gbg = gb

        def sec(title):
            return (
                f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:14px 0 8px;">'
                f'<tr>'
                f'<td width="3" bgcolor="#2563eb" style="border-radius:2px;">&nbsp;</td>'
                f'<td width="10">&nbsp;</td>'
                f'<td style="font-size:8pt;font-weight:bold;color:#374151;letter-spacing:1.5px;white-space:nowrap;text-transform:uppercase;">{title}</td>'
                f'<td width="14">&nbsp;</td>'
                f'<td style="border-bottom:1px solid #e5e7eb;">&nbsp;</td>'
                f'</tr></table>'
            )

        def img_cell(label_text, caption_text, placeholder_text, image_uri: str):
            if image_uri:
                media = (
                    f'<table cellpadding="0" cellspacing="0" '
                    f'style="width:150px;background:#ffffff;border-radius:8px;overflow:hidden;">'
                    f'<tr><td align="center" valign="middle" style="padding:0;">'
                    f'<img src="{image_uri}" width="150" height="150" style="width:150px;height:150px;display:block;border:0;" />'
                    f'</td></tr></table>'
                )
            else:
                media = (
                    f'<table cellpadding="0" cellspacing="0" '
                    f'style="width:150px;height:150px;background:#f3f4f6;border-radius:8px;overflow:hidden;">'
                    f'<tr><td align="center" valign="middle" '
                    f'style="font-size:9pt;color:#9ca3af;font-style:italic;padding:8px;">'
                    f'{placeholder_text}'
                    f'</td></tr></table>'
                )
            return (
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="background:#fafafa;border:0.5px solid #d9dee5;border-radius:8px;overflow:hidden;">'
                f'<tr><td style="padding:10px 12px 0;">'
                f'<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;color:#185FA5;'
                f'border-left:3px solid #185FA5;padding-left:8px;text-transform:uppercase;">{label_text}</div>'
                f'</td></tr>'
                f'<tr><td align="center" style="padding:8px 8px;">'
                f'{media}'
                f'<div style="font-size:9px;color:#666;font-style:italic;text-align:center;margin-top:6px;">{caption_text}</div>'
                f'</td></tr>'
                f'</table>'
            )

        def info_row(cells, bg="#ffffff"):
            tds = "".join(
                f'<td width="25%" bgcolor="{bg}" style="padding:10px 14px;border-right:1px solid #e5e7eb;'
                f'border-bottom:1px solid #e5e7eb;vertical-align:top;">'
                f'<div style="font-size:7.5pt;font-weight:bold;color:#9ca3af;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">{lbl}</div>'
                f'<div style="font-size:10pt;font-weight:600;color:#111827;line-height:1.4;">{val}</div>'
                f'</td>'
                for lbl, val in cells
            )
            return f'<tr>{tds}</tr>'

        def vrow(label, value):
            return (
                f'<tr>'
                f'<td style="padding:9px 14px;font-size:9.5pt;color:#6b7280;font-weight:500;border-bottom:1px solid #f3f4f6;">{label}</td>'
                f'<td style="padding:9px 14px;font-size:9.5pt;color:#111827;font-weight:700;text-align:right;border-bottom:1px solid #f3f4f6;">{value}</td>'
                f'</tr>'
            )

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:'Segoe UI','Calibri',Arial,sans-serif;font-size:10pt;color:#111827;
     background:#ffffff;margin:0;padding:0;line-height:1.5;}}
td, div, span{{overflow-wrap:anywhere;word-break:break-word;white-space:normal;}}
img{{max-width:100%;height:auto;}}
</style></head><body>

<table width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding-top:4px;">

<table width="100%" cellpadding="0" cellspacing="0">
<tr><td bgcolor="#0a2540" align="center" style="padding:12px 24px 10px;">
    <div style="font-size:20pt;font-weight:bold;color:#ffffff;letter-spacing:1px;">Patient Record</div>
</td></tr>
<tr><td bgcolor="#0d2d4a">
    <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
        <td style="padding:8px 24px;font-size:8.5pt;color:#94a3b8;">
            <b style="color:#cbd5e1;">Generated:</b> {report_date}
        </td>
        <td style="padding:8px 24px;font-size:8.5pt;color:#94a3b8;text-align:right;">
            <b style="color:#cbd5e1;">Screened by:</b> {screened_by}
        </td>
    </tr>
    </table>
</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:8px 6px 14px;">

{sec("Patient Information")}
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e5e7eb;border-radius:8px;border-collapse:collapse;overflow:hidden;">
{info_row([("Full Name", esc(self._current_patient_name)), ("Date of Birth", esc(dob)), ("Age", esc(age)), ("Sex", esc(sex))], "#ffffff")}
{info_row([("Record No.", esc(patient_id)), ("Contact", esc(contact)), ("Eye Screened", esc(self._current_eye_label or "—")), ("Screening Date", report_date)], "#f9fafb")}
</table>

{sec("Clinical History")}
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e5e7eb;border-radius:8px;border-collapse:collapse;overflow:hidden;">
{info_row([("Diabetes Type", esc(diabetes_type)), ("Duration", duration_disp), ("HbA1c", esc_or_dash(hba1c_disp)), ("Previous DR Treatment", esc(prev_tx))], "#ffffff")}
</table>

{sec("Screening Results &amp; Vital Signs")}
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td width="50%" valign="top" style="padding-right:12px;">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid {gb};border-left:4px solid {gb};
                  border-radius:8px;background:{gbg};">
    <tr><td style="padding:16px 18px;">
        <div style="display:inline-block;background:{badge_bg};color:#ffffff;font-size:7.5pt;
                    font-weight:bold;letter-spacing:1px;text-transform:uppercase;
                    padding:3px 9px;border-radius:4px;margin-bottom:12px;">AI Classification</div>
        <div style="font-size:14pt;font-weight:800;color:{gc};line-height:1.35;margin-bottom:4px;">
            {escape(result_raw) if result_raw else "&#8212;"}
        </div>
        <div style="font-size:9pt;color:{confidence_color};margin-bottom:12px;line-height:1.45;">Confidence: {conf_display}</div>
        <div style="border-top:1px solid {divider_color};opacity:0.35;margin-bottom:12px;"></div>
        <div style="font-size:7.5pt;font-weight:bold;color:{gc};letter-spacing:1px;
                    text-transform:uppercase;margin-bottom:4px;opacity:{reco_label_opacity};">Recommendation</div>
        <div style="font-size:9.5pt;font-weight:700;color:{gc};line-height:1.45;">&#8594;&nbsp;{rec}</div>
    </td></tr>
    </table>
</td>
<td width="50%" valign="top" style="padding-left:12px;">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
    <tr><td bgcolor="#1e3a5f" style="padding:9px 14px;font-size:8pt;font-weight:bold;
            color:#93c5fd;letter-spacing:1.2px;text-transform:uppercase;">Vital Signs</td></tr>
    <tr><td style="padding:0;">
        <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#ffffff">
        {vrow("Blood Pressure", bp_display)}
        {vrow("Visual Acuity (L / R)", f"{esc_or_dash(va_left)}&nbsp;/&nbsp;{esc_or_dash(va_right)}")}
        {vrow("Fasting Blood Sugar", fbs_disp)}
        <tr>
        <td style="padding:9px 14px;font-size:9.5pt;color:#6b7280;font-weight:500;">Random Blood Sugar</td>
        <td style="padding:9px 14px;font-size:9.5pt;color:#111827;font-weight:700;text-align:right;">{rbs_disp}</td>
        </tr>
        </table>
    </td></tr>
    <tr><td bgcolor="#f9fafb" style="padding:9px 14px;border-top:1px solid #e5e7eb;">
        <div style="font-size:7.5pt;font-weight:bold;color:#9ca3af;letter-spacing:1px;
                    text-transform:uppercase;margin-bottom:6px;">Reported Symptoms</div>
        <div>{symptom_html}</div>
    </td></tr>
    </table>
</td>
</tr>
</table>

{sec("Image Results")}
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td width="50%" valign="top" style="padding:0 6px 0 0;">
    {img_cell("SOURCE FUNDUS IMAGE", f"{esc(self._current_eye_label or 'Right eye')} &#8212; fundus photograph", "Source image not stored in this record", source_image_uri)}
</td>
<td width="50%" valign="top" style="padding:0 0 0 6px;">
    {img_cell("GRAD-CAM++ HEATMAP", "Model attention overlay", "Heatmap not stored in this record", heatmap_image_uri)}
</td>
</tr>
</table>

{sec("Clinical Analysis")}
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #bfdbfe;border-left:4px solid #2563eb;
              border-radius:0 8px 8px 0;background:#eff6ff;">
<tr><td style="padding:14px 18px;font-size:10pt;line-height:1.75;color:#1e3a5f;">{summary}</td></tr>
</table>

{sec("Clinical Notes")}
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e5e7eb;border-radius:8px;background:#fafafa;">
<tr><td style="padding:12px 16px;font-size:10pt;color:#374151;
            font-style:italic;line-height:1.65;min-height:40px;">{notes_disp}</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-top:24px;border-top:2px solid #e5e7eb;padding-top:14px;">
<tr>
<td valign="top" style="font-size:8pt;color:#9ca3af;line-height:1.8;">
    <span style="color:#6b7280;font-weight:600;">Screened by:</span>&nbsp;{screened_by}&nbsp;&nbsp;
    <span style="color:#6b7280;font-weight:600;">Generated:</span>&nbsp;{report_date}<br>
    <i>This report is AI-assisted and does not replace the judgment of a licensed eye care professional.
    All findings must be reviewed and confirmed by a qualified healthcare professional
    before any clinical action is taken.</i>
</td>
<td valign="top" align="right">
</td>
</tr>
</table>

</td></tr>
</table>

</td></tr></table>

</body></html>"""

        progress = QProgressDialog("Rendering images...", "", 0, 4, self)
        progress.setWindowTitle("Generating Report")
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html)
        progress.setValue(1)
        progress.setLabelText("Composing layout...")
        QApplication.processEvents()

        progress.setValue(2)
        progress.setLabelText("Writing PDF...")
        QApplication.processEvents()

        try:
            writer = QPdfWriter(path)
            writer.setResolution(150)
            try:
                writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            except Exception:
                pass
            try:
                writer.setPageMargins(QMarginsF(14, 8, 14, 14), QPageLayout.Unit.Millimeter)
            except Exception:
                pass
            doc.print_(writer)
            if not os.path.isfile(path) or os.path.getsize(path) == 0:
                raise OSError("Output PDF was not written correctly.")
        except OSError as err:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            progress.close()
            write_activity("ERROR", "REPORT_FAILED", str(err))
            QMessageBox.critical(self, "Generate Report", f"Disk full - PDF generation stopped. Free up space and try again.\n\n{err}")
            return

        progress.setValue(4)
        progress.setLabelText("Done")
        progress.close()

        write_activity("INFO", "REPORT_GENERATED", f"path={path}")
        done_box = QMessageBox(self)
        done_box.setWindowTitle("Report Saved")
        done_box.setIcon(QMessageBox.Icon.Information)
        done_box.setText(f"Screening report saved to:\n{path}")
        open_pdf_btn = done_box.addButton("Open PDF", QMessageBox.ButtonRole.ActionRole)
        open_folder_btn = done_box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        done_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        done_box.exec()
        if done_box.clickedButton() == open_pdf_btn:
            try:
                os.startfile(path)
            except Exception:
                pass
        elif done_box.clickedButton() == open_folder_btn:
            try:
                os.startfile(os.path.dirname(path))
            except Exception:
                pass
