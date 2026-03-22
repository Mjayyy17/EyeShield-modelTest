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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.title_label = QLabel("Results")
        self.title_label.setFont(QFont("Calibri", 16, QFont.Weight.Bold))
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
        main_row.setSpacing(14)

        review_column = QVBoxLayout()
        review_column.setSpacing(12)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)

        source_group = QGroupBox("Source Image")
        source_layout = QVBoxLayout(source_group)
        source_layout.setContentsMargins(14, 16, 14, 14)
        source_layout.setSpacing(10)
        self.source_label = ClickableImageLabel("", "Source Image")
        self.source_label.setObjectName("surfaceLabel")
        self.source_label.setMinimumSize(440, 340)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setWordWrap(True)
        source_layout.addWidget(self.source_label)

        heatmap_group = QGroupBox("Heatmap Output")
        heatmap_layout = QVBoxLayout(heatmap_group)
        heatmap_layout.setContentsMargins(14, 16, 14, 14)
        heatmap_layout.setSpacing(10)
        self.heatmap_label = ClickableImageLabel("", "Heatmap Output")
        self.heatmap_label.setObjectName("heatmapPlaceholder")
        self.heatmap_label.setMinimumSize(440, 340)
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
        stats_row.addWidget(classification_card)
        stats_row.addWidget(confidence_card)
        stats_row.addWidget(recommendation_card)
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
        self.bilateral_first_saved_lbl.setStyleSheet("font-weight:700;font-size:12px;")
        self.bilateral_first_saved_lbl.setObjectName("successLabel")
        first_col.addWidget(self.bilateral_first_eye_lbl)
        first_col.addWidget(self.bilateral_first_result_lbl)
        first_col.addWidget(self.bilateral_first_saved_lbl)
        brow_div = QFrame()
        brow_div.setFrameShape(QFrame.Shape.VLine)
        brow_div.setFrameShadow(QFrame.Shadow.Sunken)
        second_col = QVBoxLayout()
        second_col.setSpacing(4)
        self.bilateral_second_eye_lbl = QLabel("—")
        self.bilateral_second_eye_lbl.setObjectName("resultStatTitle")
        self.bilateral_second_result_lbl = QLabel("—")
        self.bilateral_second_result_lbl.setObjectName("resultStatValue")
        self.bilateral_second_saved_lbl = QLabel("Unsaved")
        self.bilateral_second_saved_lbl.setStyleSheet("font-weight:700;font-size:12px;")
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
        action_layout = QVBoxLayout(action_rail)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setSpacing(10)

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
        self.btn_save.setMinimumHeight(42)
        self.btn_save.setIconSize(QSize(18, 18))
        self.btn_save.clicked.connect(self.save_patient)
        action_layout.addWidget(self.btn_save)

        self.btn_report = QPushButton("Generate Report")
        self.btn_report.setMinimumHeight(42)
        self.btn_report.setIconSize(QSize(18, 18))
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self.generate_report)
        action_layout.addWidget(self.btn_report)

        self.btn_screen_another = QPushButton("Screen Other Eye")
        self.btn_screen_another.setObjectName("secondaryAction")
        self.btn_screen_another.setMinimumHeight(42)
        self.btn_screen_another.setIconSize(QSize(18, 18))
        self.btn_screen_another.clicked.connect(self._on_screen_another)
        action_layout.addWidget(self.btn_screen_another)

        self.btn_new = QPushButton("New Patient")
        self.btn_new.setMinimumHeight(42)
        self.btn_new.setIconSize(QSize(18, 18))
        self.btn_new.clicked.connect(self.new_patient)
        action_layout.addWidget(self.btn_new)

        self.btn_back = QPushButton("Back to Screening")
        self.btn_back.setObjectName("dangerAction")
        self.btn_back.setMinimumHeight(42)
        self.btn_back.setIconSize(QSize(18, 18))
        self.btn_back.clicked.connect(self.go_back)
        action_layout.addWidget(self.btn_back)

        action_layout.addStretch()
        self._apply_action_icons()

        main_row.addWidget(action_rail)
        layout.addLayout(main_row, 1)

        explanation_group = QGroupBox("Clinical Summary")
        explanation_layout = QVBoxLayout(explanation_group)
        explanation_layout.setContentsMargins(14, 16, 14, 14)
        explanation_layout.setSpacing(10)
        self.explanation = QLabel("AI explanation will appear here once available.")
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet("font-size: 11pt; line-height: 1.45;")
        explanation_layout.addWidget(self.explanation)
        self.explanation_hint = QLabel("AI-generated summary based on the DR grade. Always verify results with a qualified clinician before acting on this output.")
        self.explanation_hint.setObjectName("statusLabel")
        self.explanation_hint.setWordWrap(True)
        explanation_layout.addWidget(self.explanation_hint)
        layout.addWidget(explanation_group)

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
            self.bilateral_second_saved_lbl.setStyleSheet("font-weight:700;font-size:12px;")
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

        # Grade-specific recommendation
        recommendation = DR_RECOMMENDATIONS.get(result_class, "Consult a clinician")
        if is_loading:
            recommendation = "—"
        self.recommendation_value.setText(recommendation)

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
            "font-weight:700;font-size:12px;"
            "border-radius:6px;padding:6px 8px;"
        )
        self.save_status_label.setObjectName("successLabel")
        self.save_status_label.show()
        self.btn_save.setText("Saved ✓")
        self.btn_save.setEnabled(False)
        if self.bilateral_frame.isVisible():
            self.bilateral_second_saved_lbl.setText("✓ Saved")
            self.bilateral_second_saved_lbl.setStyleSheet("font-weight:700;font-size:12px;")
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
                    "A follow-up retinal examination in 6 to 12 months is recommended."
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
                320, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            try:
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("src_img"), src_px)
            except AttributeError:
                doc.addResource(QTextDocument.ImageResource, QUrl("src_img"), src_px)
            source_img_html = '<img src="src_img" style="max-width:320px; max-height:260px;" />'

        if self._current_heatmap_path and os.path.isfile(self._current_heatmap_path):
            hmap_px = QPixmap(self._current_heatmap_path).scaled(
                320, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            try:
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("hmap_img"), hmap_px)
            except AttributeError:
                doc.addResource(QTextDocument.ImageResource, QUrl("hmap_img"), hmap_px)
            heatmap_img_html = '<img src="hmap_img" style="max-width:320px; max-height:260px;" />'

        # Check for bilateral (dual-eye) data
        first_eye = None
        first_source_html = ""
        first_heatmap_html = ""
        if self.parent_page and hasattr(self.parent_page, '_first_eye_result'):
            first_eye = self.parent_page._first_eye_result

        if first_eye and first_eye.get('image_path'):
            fe_img = first_eye['image_path']
            if os.path.isfile(fe_img):
                fe_px = QPixmap(fe_img).scaled(
                    280, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                try:
                    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("fe_src_img"), fe_px)
                except AttributeError:
                    doc.addResource(QTextDocument.ImageResource, QUrl("fe_src_img"), fe_px)
                first_source_html = '<img src="fe_src_img" style="max-width:280px; max-height:220px;" />'

        if first_eye and first_eye.get('heatmap_path'):
            fe_hmap = first_eye['heatmap_path']
            if os.path.isfile(fe_hmap):
                fe_hpx = QPixmap(fe_hmap).scaled(
                    280, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                try:
                    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("fe_hmap_img"), fe_hpx)
                except AttributeError:
                    doc.addResource(QTextDocument.ImageResource, QUrl("fe_hmap_img"), fe_hpx)
                first_heatmap_html = '<img src="fe_hmap_img" style="max-width:280px; max-height:220px;" />'

        is_bilateral = bool(first_eye and first_eye.get('result') and first_eye.get('eye'))

        bilateral_second_eye_label_html = (
            '<div class="section-title" style="font-size:9pt;color:#374151;margin-top:10px;border:none;padding:0;">'
            + escape(self._current_eye_label or '')
            + '</div>'
            if is_bilateral
            else ''
        )
        bilateral_first_eye_header_html = (
            '<div style="font-size:9pt;font-weight:600;color:#374151;margin-bottom:4px;">'
            + escape(first_eye.get('eye', 'First Eye'))
            + '</div>'
            if is_bilateral
            else ''
        )
        bilateral_first_eye_images_html = ''
        if is_bilateral:
            first_source_block = first_source_html or "<div class='img-placeholder'>Source image not available</div>"
            first_heatmap_block = first_heatmap_html or "<div class='img-placeholder'>Heatmap not available</div>"
            bilateral_first_eye_images_html = (
                '<table class="img-table"><tr><td>'
                + first_source_block
                + '<div class="img-caption">Source Fundus Image</div></td><td>'
                + first_heatmap_block
                + '<div class="img-caption">Grad-CAM++ Heatmap</div></td></tr></table>'
            )
        bilateral_second_eye_header_html = (
            '<div style="font-size:9pt;font-weight:600;color:#374151;margin-top:8px;margin-bottom:4px;">'
            + escape(self._current_eye_label or 'Second Eye')
            + '</div>'
            if is_bilateral
            else ''
        )

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', 'Calibri', Arial, sans-serif;
    font-size: 10.5pt;
    color: #1f2937;
    background: #ffffff;
    line-height: 1.55;
}}
.page-header {{
    background: #0f3d66;
    color: #ffffff;
    padding: 16px 24px 14px 24px;
}}
.page-header .brand {{ font-size: 16pt; font-weight: 700; letter-spacing: 0.4px; }}
.page-header .brand-sub {{ font-size: 9pt; color: #93c5fd; margin-top: 2px; }}
.page-header .meta {{ font-size: 9pt; color: #bfdbfe; margin-top: 6px; line-height: 1.6; }}
.body {{ padding: 16px 24px 20px 24px; }}
.section-title {{
    font-size: 10pt;
    font-weight: 700;
    color: #0f3d66;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    border-bottom: 1.5px solid #dbeafe;
    padding-bottom: 4px;
    margin: 14px 0 8px 0;
}}
.info-grid {{ width: 100%; border-collapse: collapse; }}
.info-grid td {{
    vertical-align: top;
    padding: 3px 10px 3px 0;
    font-size: 10pt;
    width: 33.3%;
}}
.lbl {{ color: #6b7280; font-weight: 600; font-size: 9pt; white-space: nowrap; }}
.val {{ color: #111827; font-weight: 500; }}
.result-banner {{
    background: {grade_bg};
    border-left: 5px solid {grade_color};
    border-radius: 6px;
    padding: 10px 14px;
    margin: 0;
}}
.result-grade {{ font-size: 14pt; font-weight: 700; color: {grade_color}; }}
.result-meta {{ font-size: 9.5pt; color: #374151; margin-top: 4px; }}
.result-rec {{ font-size: 9.5pt; font-weight: 600; color: {grade_color}; margin-top: 4px; }}
.two-col {{ width: 100%; border-collapse: collapse; }}
.two-col td {{ vertical-align: top; padding: 0; }}
.two-col td:first-child {{ width: 52%; padding-right: 12px; }}
.two-col td:last-child {{ width: 48%; }}
.vitals-box {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
}}
.vitals-inner {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
.vitals-inner td {{ padding: 3px 0; border-bottom: 1px solid #f1f5f9; }}
.vitals-inner tr:last-child td {{ border-bottom: none; }}
.vitals-lbl {{ color: #6b7280; font-weight: 600; }}
.vitals-val {{ color: #111827; font-weight: 500; text-align: right; }}
.symptom-pill {{
    display: inline-block;
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fca5a5;
    border-radius: 999px;
    padding: 2px 9px;
    font-size: 8.5pt;
    font-weight: 600;
    margin: 2px 3px 2px 0;
}}
.img-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
.img-table td {{
    width: 50%;
    border: 1px solid #e2e8f0;
    text-align: center;
    padding: 8px;
    vertical-align: middle;
    background: #f8fafc;
}}
.img-placeholder {{
    min-height: 110px;
    padding-top: 40px;
    font-size: 9pt;
    color: #94a3b8;
    border: 1.5px dashed #cbd5e1;
    border-radius: 4px;
    background: #f1f5f9;
}}
.img-caption {{ margin-top: 6px; font-size: 9pt; color: #6b7280; font-weight: 600; }}
.analysis-box {{
    background: #f0f7ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    padding: 11px 14px;
    font-size: 10pt;
    line-height: 1.65;
    color: #1e3a5f;
    margin-top: 8px;
}}
.notes-box {{
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 9.5pt;
    color: #374151;
    margin-top: 4px;
    min-height: 36px;
}}
.footer {{
    margin-top: 14px;
    padding-top: 8px;
    border-top: 1px solid #e5e7eb;
    font-size: 8.5pt;
    color: #6b7280;
    line-height: 1.6;
}}
.footer-brand {{ text-align: center; margin-top: 6px; font-size: 8pt; color: #9ca3af; }}
</style>
</head>
<body>

<div class="page-header">
    <div class="brand">{escape(clinic_name)}</div>
    <div class="brand-sub">Diabetic Retinopathy Screening Report</div>
    <div class="meta">Generated: {report_date} &nbsp;|&nbsp; Screened by: {screened_by}</div>
</div>

<div class="body">

<div class="section-title">Patient Information</div>
<table class="info-grid">
    <tr>
        <td><span class="lbl">Patient Name</span><br><span class="val">{esc(self._current_patient_name)}</span></td>
        <td><span class="lbl">Record No.</span><br><span class="val">{esc(patient_id)}</span></td>
        <td><span class="lbl">Report Date</span><br><span class="val">{report_date}</span></td>
    </tr>
    <tr>
        <td><span class="lbl">Date of Birth</span><br><span class="val">{esc(dob)}</span></td>
        <td><span class="lbl">Age</span><br><span class="val">{esc_or_dash(age)}</span></td>
        <td><span class="lbl">Sex</span><br><span class="val">{esc_or_dash(sex)}</span></td>
    </tr>
    <tr>
        <td><span class="lbl">Contact</span><br><span class="val">{esc_or_dash(contact)}</span></td>
        <td><span class="lbl">Eye Screened</span><br><span class="val">{'Both Eyes (Bilateral)' if is_bilateral else esc_or_dash(self._current_eye_label)}</span></td>
        <td></td>
    </tr>
</table>

<div class="section-title">Clinical History</div>
<table class="info-grid">
    <tr>
        <td><span class="lbl">Diabetes Type</span><br><span class="val">{esc_or_dash(diabetes_type)}</span></td>
        <td><span class="lbl">Duration</span><br><span class="val">{duration_disp}</span></td>
        <td><span class="lbl">HbA1c</span><br><span class="val">{esc_or_dash(hba1c_disp)}</span></td>
    </tr>
    <tr>
        <td><span class="lbl">Previous DR Treatment</span><br><span class="val">{esc_or_dash(prev_tx)}</span></td>
        <td></td>
        <td></td>
    </tr>
</table>

<div class="section-title">Screening Results &amp; Vital Signs</div>
{'<div class="section-title" style="font-size:9pt;color:#374151;margin-top:6px;border:none;padding:0;">' + escape(first_eye.get('eye','')) + '</div>' if is_bilateral else ''}
{'<table class="two-col"><tr><td>' if is_bilateral else ''}
{'<div class="result-banner" style="background:' + grade_bg_map.get(first_eye.get('result',''),'#f3f4f6') + ';border-left:5px solid ' + DR_COLORS.get(first_eye.get('result',''),'#374151') + ';">' if is_bilateral else ''}
{'<div class="result-grade" style="color:' + DR_COLORS.get(first_eye.get('result',''),'#374151') + ';">' + escape(first_eye.get('result','')) + '</div>' if is_bilateral else ''}
{'<div class="result-meta">Confidence: ' + escape(first_eye.get('confidence','')) + '</div>' if is_bilateral else ''}
{'<div class="result-rec" style="color:' + DR_COLORS.get(first_eye.get('result',''),'#374151') + ';">&#8594; ' + escape(DR_RECOMMENDATIONS.get(first_eye.get('result',''),'Consult a clinician')) + '</div>' if is_bilateral else ''}
{'</div></td></tr></table>' if is_bilateral else ''}

{bilateral_second_eye_label_html}
<table class="two-col">
<tr>
    <td>
        <div class="result-banner">
            <div class="result-grade">{escape(result_raw) if result_raw else "&mdash;"}</div>
            <div class="result-meta">Confidence: {confidence_display}</div>
            <div class="result-rec">&#8594; {recommendation}</div>
        </div>
    </td>
    <td>
        <div class="vitals-box">
            <table class="vitals-inner">
                <tr>
                    <td class="vitals-lbl">Blood Pressure</td>
                    <td class="vitals-val">{bp_display}</td>
                </tr>
                <tr>
                    <td class="vitals-lbl">Visual Acuity (L / R)</td>
                    <td class="vitals-val">{esc_or_dash(va_left)} / {esc_or_dash(va_right)}</td>
                </tr>
                <tr>
                    <td class="vitals-lbl">Fasting Blood Sugar</td>
                    <td class="vitals-val">{fbs_disp}</td>
                </tr>
                <tr>
                    <td class="vitals-lbl">Random Blood Sugar</td>
                    <td class="vitals-val">{rbs_disp}</td>
                </tr>
            </table>
            <div style="margin-top:8px; font-size:8.5pt; color:#6b7280; font-weight:600;">REPORTED SYMPTOMS</div>
            <div style="margin-top:4px;">{symptom_html}</div>
        </div>
    </td>
</tr>
</table>

<div class="section-title">Image Results</div>
{bilateral_first_eye_header_html}
{bilateral_first_eye_images_html}
{bilateral_second_eye_header_html}
<table class="img-table">
    <tr>
        <td>
            {source_img_html}
            <div class="img-caption">Source Fundus Image</div>
        </td>
        <td>
            {heatmap_img_html}
            <div class="img-caption">Grad-CAM++ Heatmap Overlay</div>
        </td>
    </tr>
</table>

<div class="section-title">Clinical Analysis</div>
<div class="analysis-box">{explanation_html}</div>

<div class="section-title">Clinical Notes</div>
<div class="notes-box">{notes_disp}</div>

<div class="footer">
    Screened by: <strong>{screened_by}</strong> &nbsp;|&nbsp; Generated: {report_date}<br>
    This report supports clinical decision-making and does not replace professional medical evaluation.
    Results are generated by an AI model and must be reviewed by a qualified clinician.
</div>
<div class="footer-brand">EyeShield EMR &mdash; {escape(clinic_name)}</div>

</div>
</body>
</html>"""

        doc.setHtml(html)

        writer = QPdfWriter(path)
        try:
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        except Exception:
            pass
        try:
            writer.setPageMargins(QMarginsF(2, 2, 2, 2), QPageLayout.Unit.Millimeter)
        except Exception:
            pass
        doc.print_(writer)

        QMessageBox.information(
            self, "Report Saved",
            f"Screening report saved to:\n{path}"
        )
