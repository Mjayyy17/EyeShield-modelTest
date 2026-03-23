"""
Results window module for EyeShield EMR application.
Contains the ResultsWindow class and clinical explanation generation.
"""

from datetime import datetime
from html import escape
import json
import os
import re

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QMessageBox, QFileDialog, QStyle
)
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QIcon, QPalette
from PySide6.QtCore import Qt, QSize, QEvent

from screening_styles import DR_COLORS, DR_RECOMMENDATIONS, PROGRESSBAR_STYLE
from screening_widgets import ClickableImageLabel


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
        self.setMinimumSize(980, 700)
        self._icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

        # Report generation state — updated by set_results()
        self._current_image_path   = ""
        self._current_heatmap_path = ""
        self._current_result_class = "Pending"
        self._current_confidence   = ""
        self._current_eye_label    = ""
        self._current_patient_name = ""

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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self.title_label = QLabel("Results")
        self.title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.title_label.setObjectName("pageHeader")
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Review the screening summary, image preview, and heatmap output area.")
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)   # indeterminate / marquee
        self._loading_bar.setFixedHeight(6)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setStyleSheet("""
            QProgressBar {
                background: #e9ecef;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #0d6efd;
                border-radius: 3px;
            }
        """)
        self._loading_bar.hide()
        layout.addWidget(self._loading_bar)

        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        review_column = QVBoxLayout()
        review_column.setSpacing(14)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)

        source_group = QGroupBox("Source Image")
        source_group.setObjectName("resultGroupCard")
        source_layout = QVBoxLayout(source_group)
        source_layout.setContentsMargins(14, 14, 14, 14)
        source_layout.setSpacing(10)
        self.source_label = ClickableImageLabel("", "Source Image")
        self.source_label.setObjectName("surfaceLabel")
        self.source_label.setMinimumSize(420, 320)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setWordWrap(True)
        source_layout.addWidget(self.source_label)

        heatmap_group = QGroupBox("Heatmap Output")
        heatmap_group.setObjectName("resultGroupCard")
        heatmap_layout = QVBoxLayout(heatmap_group)
        heatmap_layout.setContentsMargins(14, 14, 14, 14)
        heatmap_layout.setSpacing(10)
        self.heatmap_label = ClickableImageLabel("", "Heatmap Output")
        self.heatmap_label.setObjectName("heatmapPlaceholder")
        self.heatmap_label.setMinimumSize(420, 320)
        self.heatmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heatmap_label.setWordWrap(True)
        heatmap_layout.addWidget(self.heatmap_label)

        preview_row.addWidget(source_group, 1)
        preview_row.addWidget(heatmap_group, 1)
        review_column.addLayout(preview_row, 1)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        classification_card, self.classification_value = self._create_stat_card("Classification")
        confidence_card, self.confidence_value = self._create_stat_card("Confidence")
        recommendation_card, self.recommendation_value = self._create_stat_card("Recommendation")
        self.confidence_value.setStyleSheet("color:#334155;font-size:15px;font-weight:700;")
        self.recommendation_value.setStyleSheet(
            "color:#334155;font-size:13px;font-weight:600;line-height:1.4;"
        )
        stats_row.addWidget(classification_card, 1)
        stats_row.addWidget(confidence_card, 1)
        stats_row.addWidget(recommendation_card, 2)
        review_column.addLayout(stats_row)

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
        review_column.addWidget(self.bilateral_frame)

        main_row.addLayout(review_column, 1)

        action_rail = QFrame()
        action_rail.setObjectName("actionRail")
        action_rail.setFixedWidth(280)
        action_layout = QVBoxLayout(action_rail)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setSpacing(12)

        rail_label = QLabel("Actions")
        rail_label.setObjectName("resultStatTitle")
        action_layout.addWidget(rail_label)

        self.save_status_label = QLabel("")
        self.save_status_label.setWordWrap(True)
        self.save_status_label.hide()
        action_layout.addWidget(self.save_status_label)

        self.btn_save = QPushButton("Save Patient")
        self.btn_save.setObjectName("primaryAction")
        self.btn_save.setAutoDefault(True)
        self.btn_save.setDefault(True)
        self.btn_save.setMinimumHeight(44)
        self.btn_save.setIconSize(QSize(18, 18))
        self.btn_save.clicked.connect(self.save_patient)
        action_layout.addWidget(self.btn_save)

        self.btn_report = QPushButton("Generate Report")
        self.btn_report.setMinimumHeight(44)
        self.btn_report.setIconSize(QSize(18, 18))
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self.generate_report)
        action_layout.addWidget(self.btn_report)

        self.btn_screen_another = QPushButton("Screen Other Eye")
        self.btn_screen_another.setObjectName("secondaryAction")
        self.btn_screen_another.setMinimumHeight(44)
        self.btn_screen_another.setIconSize(QSize(18, 18))
        self.btn_screen_another.clicked.connect(self._on_screen_another)
        action_layout.addWidget(self.btn_screen_another)

        self.btn_new = QPushButton("New Patient")
        self.btn_new.setMinimumHeight(44)
        self.btn_new.setIconSize(QSize(18, 18))
        self.btn_new.clicked.connect(self.new_patient)
        action_layout.addWidget(self.btn_new)

        self.btn_back = QPushButton("Back to Screening")
        self.btn_back.setObjectName("dangerAction")
        self.btn_back.setMinimumHeight(44)
        self.btn_back.setIconSize(QSize(18, 18))
        self.btn_back.clicked.connect(self.go_back)
        action_layout.addWidget(self.btn_back)

        action_layout.addStretch()
        self._apply_action_icons()

        main_row.addWidget(action_rail)
        layout.addLayout(main_row, 1)

        explanation_group = QGroupBox("Clinical Summary")
        explanation_group.setObjectName("resultGroupCard")
        explanation_layout = QVBoxLayout(explanation_group)
        explanation_layout.setContentsMargins(16, 18, 16, 16)
        explanation_layout.setSpacing(12)
        self.explanation_lead = QLabel("Interpretation and recommended next clinical action")
        self.explanation_lead.setObjectName("summaryLead")
        self.explanation_lead.setWordWrap(True)
        explanation_layout.addWidget(self.explanation_lead)
        self.explanation = QLabel("AI explanation will appear here once available.")
        self.explanation.setWordWrap(True)
        self.explanation.setObjectName("summaryBody")
        explanation_layout.addWidget(self.explanation)
        self.explanation_hint = QLabel("AI-generated summary based on the DR grade. Always verify results with a qualified clinician before acting on this output.")
        self.explanation_hint.setObjectName("statusLabel")
        self.explanation_hint.setWordWrap(True)
        explanation_layout.addWidget(self.explanation_hint)
        layout.addWidget(explanation_group)

        self.setStyleSheet("""
            QWidget {
                background: #f3f7fb;
                color: #1f2937;
                font-family: "Segoe UI", "Inter", "Calibri", sans-serif;
                font-size: 13px;
            }
            QLabel#pageHeader {
                font-size: 28px;
                font-weight: 700;
                color: #0f3d66;
                letter-spacing: 0.2px;
            }
            QLabel#pageSubtitle {
                color: #4b5b6c;
                font-size: 14px;
            }
            QGroupBox#resultGroupCard {
                background: #ffffff;
                border: 1px solid #d6e2ee;
                border-radius: 12px;
                margin-top: 10px;
                font-weight: 700;
                color: #334155;
            }
            QGroupBox#resultGroupCard::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #2f4e70;
                background: #ffffff;
                font-size: 14px;
            }
            QLabel#surfaceLabel, QLabel#heatmapPlaceholder {
                background: #fbfdff;
                border: 1px solid #d9e5f2;
                border-radius: 8px;
                color: #4b5b6c;
                font-size: 13px;
            }
            QFrame#resultStatCard {
                background: #ffffff;
                border: 1px solid #d6e2ee;
                border-radius: 12px;
            }
            QLabel#resultStatTitle {
                color: #5a6f84;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }
            QLabel#resultStatValue {
                color: #111827;
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#summaryLead {
                color: #2f4e70;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#summaryBody {
                background: #f7fbff;
                border: 1px solid #d8e7f7;
                border-radius: 10px;
                color: #1e293b;
                font-size: 14px;
                font-weight: 500;
                line-height: 1.55;
                padding: 12px 14px;
            }
            QFrame#actionRail {
                background: #ffffff;
                border: 1px solid #d6e2ee;
                border-radius: 12px;
            }
            QLabel#statusLabel {
                color: #6b7280;
                font-size: 13px;
            }
            QLabel#successLabel {
                color: #166534;
            }
            QLabel#errorLabel {
                color: #b91c1c;
            }
            QPushButton {
                background: #eaf3ff;
                color: #005ecb;
                border: 1px solid #b4d0ff;
                border-radius: 8px;
                padding: 10px 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #d7e8ff;
            }
            QPushButton:disabled {
                background: #eef2f7;
                color: #94a3b8;
                border-color: #dbe3ec;
            }
            QPushButton#primaryAction {
                background: #007bff;
                color: #ffffff;
                border: 1px solid #0066d4;
            }
            QPushButton#primaryAction:hover {
                background: #006ee6;
            }
            QPushButton#secondaryAction {
                background: #dcecff;
                color: #005ecb;
                border: 1px solid #a9c7ff;
            }
            QPushButton#secondaryAction:hover {
                background: #cfe3ff;
            }
            QPushButton#dangerAction {
                background: #fff1f2;
                color: #b91c1c;
                border: 1px solid #fecdd3;
            }
            QPushButton#dangerAction:hover {
                background: #ffe4e6;
            }
        """)

        main_row.setStretch(0, 3)
        main_row.setStretch(1, 1)

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
        self.btn_report.setIcon(self._build_action_icon("generate.svg", QStyle.StandardPixmap.SP_FileDialogDetailedView))
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

    def set_results(self, patient_name, image_path, result_class="Pending", confidence_text="Pending", eye_label="", first_eye_result=None, heatmap_path="", patient_data=None, heatmap_pending=False):
        is_loading = result_class in ("Analyzing…", "Pending")
        is_busy = is_loading or heatmap_pending

        if patient_name:
            eye_suffix = f" — {eye_label}" if eye_label else ""
            self.title_label.setText(f"Results for {patient_name}{eye_suffix}")
        else:
            self.title_label.setText("Results")

        # Loading bar
        if is_busy:
            self._loading_bar.show()
        else:
            self._loading_bar.hide()

        # Reset save feedback state
        self.save_status_label.hide()
        self.save_status_label.setText("")
        self.btn_save.setEnabled(not is_busy)
        self.btn_save.setText("Save Patient")
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
        self.classification_value.setStyleSheet(
            f"color:{grade_color};font-size:20px;font-weight:700;"
        )

        self.confidence_value.setText(confidence_text)
        self.confidence_value.setStyleSheet("color:#334155;font-size:17px;font-weight:700;")

        # Grade-specific recommendation
        recommendation = DR_RECOMMENDATIONS.get(result_class, "Consult a clinician")
        if is_loading:
            recommendation = "—"
        self.recommendation_value.setText(recommendation)
        self.recommendation_value.setStyleSheet(
            "color:#334155;font-size:14px;font-weight:600;line-height:1.45;"
        )

        # Subtitle
        if is_loading:
            self.subtitle_label.setText("Running DR analysis — please wait…")
        elif heatmap_pending:
            conf_part = f" with {confidence_text.lower()}" if confidence_text else ""
            self.subtitle_label.setText(
                f"Screening complete — {result_class}{conf_part}. "
                "Generating the Grad-CAM++ heatmap now."
            )
        else:
            conf_part = f" with {confidence_text.lower()}" if not is_loading else ""
            self.subtitle_label.setText(
                f"Screening complete — {result_class}{conf_part}. "
                "Review the fundus image, Grad-CAM⁺⁺ heatmap, and clinical summary below."
            )

        # Image and heatmap panels
        if image_path:
            source_pixmap = QPixmap(image_path)
            self.source_label.set_viewable_pixmap(source_pixmap, 460, 360)
            if is_loading:
                self.heatmap_label.clear_view("")
            elif heatmap_pending:
                self.heatmap_label.clear_view("")
            elif heatmap_path and os.path.isfile(heatmap_path):
                hmap_pixmap = QPixmap(heatmap_path)
                self.heatmap_label.set_viewable_pixmap(hmap_pixmap, 460, 360)
            else:
                self.heatmap_label.clear_view("")
        else:
            self.source_label.clear_view("")
            self.heatmap_label.clear_view("")

        # Clinical summary
        if is_loading:
            self.explanation.setText("Awaiting model output…")
        else:
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
        self.save_status_label.setText(f"✓  Saved — {name} ({eye_label}): {result_class}")
        self.save_status_label.setStyleSheet(
            "font-weight:700;font-size:13px;"
            "border-radius:6px;padding:6px 8px;"
        )
        self.save_status_label.setObjectName("successLabel")
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
            reply = QMessageBox.question(
                self, "Unsaved Screening",
                "This screening has not been saved yet.\n\nGo back to the intake form without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        if hasattr(page, "stacked_widget"):
            page.stacked_widget.setCurrentIndex(0)

    def save_patient(self):
        if self.parent_page and hasattr(self.parent_page, "save_screening"):
            self.parent_page.save_screening(reset_after=False)

    def new_patient(self):
        if not self.parent_page:
            return
        page = self.parent_page
        if not getattr(page, "_current_eye_saved", True):
            reply = QMessageBox.question(
                self, "Unsaved Screening",
                "This screening has not been saved yet.\n\nDiscard it and start a new patient?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Discard:
                return
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

        default_name = (
            f"EyeShield_Report_{self._current_patient_name or 'Patient'}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Screening Report", default_name, "PDF Files (*.pdf)"
        )
        if not path:
            return

        try:
            from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QTextDocument
            from PySide6.QtCore import QUrl, QMarginsF
        except ImportError:
            QMessageBox.warning(self, "Generate Report", "PDF generation requires PySide6 PDF support.")
            return

        # Collect full patient data from the parent form
        pp = self.parent_page
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

        recommendation = escape(DR_RECOMMENDATIONS.get(result_raw, "Consult a qualified clinician"))

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
        screened_by_raw = str(os.environ.get("EYESHIELD_CURRENT_USER", "")).strip()
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

        # Build QTextDocument with embedded images
        doc = QTextDocument()
        source_img_html = "<div class='img-placeholder'>Source image not available</div>"
        heatmap_img_html = "<div class='img-placeholder'>Heatmap not available</div>"

        if self._current_image_path and os.path.isfile(self._current_image_path):
            src_px = QPixmap(self._current_image_path).scaled(
                260, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            try:
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("src_img"), src_px)
            except AttributeError:
                doc.addResource(QTextDocument.ImageResource, QUrl("src_img"), src_px)
            source_img_html = '<img src="src_img" style="max-width:92%; max-height:145px; height:auto; display:block; margin:0 auto;" />'

        if self._current_heatmap_path and os.path.isfile(self._current_heatmap_path):
            hmap_px = QPixmap(self._current_heatmap_path).scaled(
                260, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            try:
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("hmap_img"), hmap_px)
            except AttributeError:
                doc.addResource(QTextDocument.ImageResource, QUrl("hmap_img"), hmap_px)
            heatmap_img_html = '<img src="hmap_img" style="max-width:92%; max-height:145px; height:auto; display:block; margin:0 auto;" />'

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
        rec = _REC.get(result_raw, "Consult a qualified clinician")
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
            confidence_color = "#374151"
            divider_color = gb
            reco_label_opacity = "0.8"

        def sec(title):
            return (
                f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0 10px;">'
                f'<tr>'
                f'<td width="3" bgcolor="#2563eb" style="border-radius:2px;">&nbsp;</td>'
                f'<td width="10">&nbsp;</td>'
                f'<td style="font-size:8pt;font-weight:bold;color:#374151;letter-spacing:1.5px;white-space:nowrap;text-transform:uppercase;">{title}</td>'
                f'<td width="14">&nbsp;</td>'
                f'<td style="border-bottom:1px solid #e5e7eb;">&nbsp;</td>'
                f'</tr></table>'
            )

        def img_cell(caption, placeholder_text, image_html):
            body = image_html or placeholder_text
            return (
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">'
                f'<tr><td bgcolor="#f9fafb" align="center" valign="middle" '
                f'style="font-size:9pt;color:#9ca3af;font-style:italic;padding:16px;">'
                f'{body}</td></tr>'
                f'<tr><td bgcolor="#f3f4f6" style="border-top:1px solid #e5e7eb;padding:6px 12px;'
                f'font-size:7.5pt;font-weight:bold;color:#6b7280;text-align:center;'
                f'letter-spacing:0.8px;text-transform:uppercase;">{caption}</td></tr>'
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
<tr><td style="padding:18px 0 24px;">

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
<tr><td valign="top" style="padding:0 0 10px 0;">
    {img_cell("Source Fundus Image", "Source image not stored in this record", source_img_html)}
</td></tr>
<tr><td valign="top" style="padding:0;">
    {img_cell("Grad-CAM++ Heatmap", "Heatmap not stored in this record", heatmap_img_html)}
</td></tr>
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
    <i>This report is AI-assisted and does not replace the judgment of a licensed clinician.
    All findings must be reviewed and confirmed by a qualified healthcare professional
    before any clinical action is taken.</i>
</td>
<td valign="top" align="right">
</td>
</tr>
</table>

</td></tr>
</table>

</body></html>"""

        doc.setHtml(html)

        writer = QPdfWriter(path)
        writer.setResolution(150)
        try:
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        except Exception:
            pass
        try:
            writer.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Unit.Millimeter)
        except Exception:
            pass
        doc.print_(writer)

        QMessageBox.information(
            self, "Report Saved",
            f"Screening report saved to:\n{path}"
        )
