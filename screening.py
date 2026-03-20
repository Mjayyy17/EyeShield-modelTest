"""
Screening module for EyeShield EMR application.
Handles patient screening functionality and image analysis with fixed UI styling.
"""


from datetime import datetime
from html import escape
import secrets
import sqlite3
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QFileDialog, QFormLayout, QGroupBox, QComboBox, QDateEdit, QMessageBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit, QCalendarWidget, QStackedWidget,
    QGridLayout, QFrame, QStyle, QDialog, QScrollArea, QProgressBar, QSizePolicy
)
from PySide6.QtGui import QPixmap, QFont, QRegularExpressionValidator, QPainter, QPen, QColor, QIcon, QPalette
from PySide6.QtCore import Qt, QDate, QRegularExpression, QSize, QEvent, QThread, Signal
import os
import re
from auth import DB_FILE

# ── Per-grade clinical constants ──────────────────────────────────────────────
_DR_COLORS = {
    "No DR":              "#198754",
    "Mild DR":            "#b35a00",
    "Moderate DR":        "#c1540a",
    "Severe DR":          "#dc3545",
    "Proliferative DR":   "#842029",
}

_DR_RECOMMENDATIONS = {
    "No DR":            "Annual screening recommended",
    "Mild DR":          "6–12 month follow-up",
    "Moderate DR":      "Ophthalmology referral within 3 months",
    "Severe DR":        "Urgent ophthalmology referral",
    "Proliferative DR": "Immediate ophthalmology referral",
}

_DR_SUMMARIES = {
    "No DR": (
        "No signs of diabetic retinopathy were detected in this fundus image. "
        "Continue standard diabetes management, maintain optimal glycemic and blood pressure control, "
        "and schedule routine annual retinal screening."
    ),
    "Mild DR": (
        "Early microaneurysms consistent with mild non-proliferative diabetic retinopathy (NPDR) were identified. "
        "Intensify glycemic and blood pressure management. "
        "A follow-up retinal examination in 6–12 months is recommended."
    ),
    "Moderate DR": (
        "Features consistent with moderate non-proliferative diabetic retinopathy (NPDR) were detected, "
        "including microaneurysms, haemorrhages, and/or hard exudates. "
        "Referral to an ophthalmologist within 3 months is advised. "
        "Reassess systemic metabolic control."
    ),
    "Severe DR": (
        "Findings consistent with severe non-proliferative diabetic retinopathy (NPDR) were detected. "
        "The risk of progression to proliferative disease within 12 months is high. "
        "Urgent ophthalmology referral is required for further evaluation and possible treatment."
    ),
    "Proliferative DR": (
        "Proliferative diabetic retinopathy (PDR) was detected — a sight-threatening condition. "
        "Immediate ophthalmology referral is required for evaluation and potential intervention, "
        "such as laser photocoagulation or intravitreal anti-VEGF therapy."
    ),
}

# ── Pen annotation colour palette ─────────────────────────────────────────────
_PEN_COLORS = [
    ("#c81e1e", "Red"),
    ("#fde910", "Yellow"),
    ("#ffffff", "White"),
]


class _InferenceWorker(QThread):
    """Run model_inference.run_inference() on a background thread."""
    result_ready = Signal(str, str)      # label, confidence_text
    finished   = Signal(str, str, str)  # label, confidence_text, heatmap_path
    error      = Signal(str)            # hard error message
    ungradable = Signal(str)            # image quality / gradability failure

    def __init__(self, image_path: str):
        super().__init__()
        self._image_path = image_path

    def run(self):
        try:
            from model_inference import generate_heatmap, predict_image, ImageUngradableError
            try:
                label, conf, class_idx = predict_image(self._image_path)
                self.result_ready.emit(label, conf)
                heatmap_path = generate_heatmap(self._image_path, class_idx)
                self.finished.emit(label, conf, heatmap_path)
            except ImageUngradableError as exc:
                self.ungradable.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))


class DrawableZoomLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_pixmap = QPixmap()
        self.zoom_factor = 1.0
        self.draw_enabled = False
        self.pen_color = QColor("#c81e1e")
        self.strokes = []
        self.current_stroke = []
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_base_pixmap(self, pixmap):
        self.base_pixmap = pixmap
        self.strokes = []
        self.current_stroke = []
        self._update_display()

    def set_zoom_factor(self, factor):
        self.zoom_factor = factor
        self._update_display()

    def set_draw_enabled(self, enabled):
        self.draw_enabled = enabled
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_pen_color(self, color: QColor):
        self.pen_color = color

    def clear_drawings(self):
        self.strokes = []
        self.current_stroke = []
        self._update_display()

    def _map_to_image_point(self, position):
        if self.base_pixmap.isNull():
            return (0.0, 0.0)

        max_x = max(0.0, float(self.base_pixmap.width() - 1))
        max_y = max(0.0, float(self.base_pixmap.height() - 1))
        point_x = min(max(position.x() / self.zoom_factor, 0.0), max_x)
        point_y = min(max(position.y() / self.zoom_factor, 0.0), max_y)
        return (point_x, point_y)

    def _update_display(self):
        if self.base_pixmap.isNull():
            self.setPixmap(QPixmap())
            return

        canvas = self.base_pixmap.scaled(
            max(1, int(self.base_pixmap.width() * self.zoom_factor)),
            max(1, int(self.base_pixmap.height() * self.zoom_factor)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.pen_color, max(2, int(2 * self.zoom_factor)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        for stroke in self.strokes + ([self.current_stroke] if self.current_stroke else []):
            for index in range(1, len(stroke)):
                start_x, start_y = stroke[index - 1]
                end_x, end_y = stroke[index]
                painter.drawLine(
                    int(start_x * self.zoom_factor),
                    int(start_y * self.zoom_factor),
                    int(end_x * self.zoom_factor),
                    int(end_y * self.zoom_factor),
                )

        painter.end()
        self.setPixmap(canvas)
        self.resize(canvas.size())

    def mousePressEvent(self, event):
        if self.draw_enabled and event.button() == Qt.MouseButton.LeftButton and not self.base_pixmap.isNull():
            self.current_stroke = [self._map_to_image_point(event.position())]
            self._update_display()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.draw_enabled and event.buttons() & Qt.MouseButton.LeftButton and self.current_stroke:
            self.current_stroke.append(self._map_to_image_point(event.position()))
            self._update_display()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.draw_enabled and event.button() == Qt.MouseButton.LeftButton and self.current_stroke:
            self.current_stroke.append(self._map_to_image_point(event.position()))
            self.strokes.append(self.current_stroke)
            self.current_stroke = []
            self._update_display()
            return
        super().mouseReleaseEvent(event)


class ImageZoomDialog(QDialog):
    ZOOM_STEP = 1.2

    def __init__(self, pixmap, title, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.zoom_factor = 1.0

        self.setWindowTitle(title)
        self.resize(1100, 800)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        zoom_in_btn = QPushButton()
        zoom_in_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        zoom_in_btn.setIconSize(QSize(18, 18))
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.setFixedSize(38, 38)
        zoom_in_btn.clicked.connect(self.zoom_in)
        controls.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton()
        zoom_out_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        zoom_out_btn.setIconSize(QSize(18, 18))
        zoom_out_btn.setToolTip("Zoom out")
        zoom_out_btn.setFixedSize(38, 38)
        zoom_out_btn.clicked.connect(self.zoom_out)
        controls.addWidget(zoom_out_btn)

        reset_btn = QPushButton()
        reset_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        reset_btn.setIconSize(QSize(18, 18))
        reset_btn.setToolTip("Reset zoom")
        reset_btn.setFixedSize(38, 38)
        reset_btn.clicked.connect(self.reset_zoom)
        controls.addWidget(reset_btn)

        draw_btn = QPushButton("✏")
        draw_btn.setCheckable(True)
        draw_btn.setToolTip("Draw annotations")
        draw_btn.setFixedSize(38, 38)
        draw_btn.setStyleSheet("font-size: 16px;")
        draw_btn.toggled.connect(self.toggle_draw_mode)
        controls.addWidget(draw_btn)
        self._draw_btn = draw_btn

        self._swatches = []
        for _hex, _name in _PEN_COLORS:
            _sw = QPushButton()
            _sw.setFixedSize(22, 22)
            _sw.setToolTip(_name)
            _border = "3px solid #0d6efd" if _hex == _PEN_COLORS[0][0] else "2px solid #adb5bd"
            _sw.setStyleSheet(f"background:{_hex};border-radius:11px;border:{_border};")
            _sw.clicked.connect(lambda checked=False, h=_hex: self._set_pen_color(h))
            controls.addWidget(_sw)
            self._swatches.append((_sw, _hex))

        clear_draw_btn = QPushButton()
        clear_draw_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        clear_draw_btn.setIconSize(QSize(18, 18))
        clear_draw_btn.setToolTip("Clear drawings")
        clear_draw_btn.setFixedSize(38, 38)
        clear_draw_btn.clicked.connect(self.clear_drawings)
        controls.addWidget(clear_draw_btn)

        controls.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        controls.addWidget(close_btn)

        layout.addLayout(controls)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.scroll_area, 1)

        self.image_label = DrawableZoomLabel()
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.viewport().installEventFilter(self)
        self.image_label.installEventFilter(self)
        self.image_label.set_base_pixmap(self.original_pixmap)

        self._update_preview()

    def eventFilter(self, watched, event):
        if watched in (self.scroll_area.viewport(), self.image_label) and event.type() == QEvent.Type.Wheel:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            return True
        return super().eventFilter(watched, event)

    def _update_preview(self):
        if self.original_pixmap.isNull():
            self.image_label.setPixmap(QPixmap())
            return
        self.image_label.set_zoom_factor(self.zoom_factor)

    def zoom_in(self):
        self.zoom_factor = min(5.0, self.zoom_factor * self.ZOOM_STEP)
        self._update_preview()

    def zoom_out(self):
        self.zoom_factor = max(0.2, self.zoom_factor / self.ZOOM_STEP)
        self._update_preview()

    def reset_zoom(self):
        self.zoom_factor = 1.0
        self._update_preview()

    def toggle_draw_mode(self, enabled):
        self.image_label.set_draw_enabled(enabled)

    def clear_drawings(self):
        self.image_label.clear_drawings()

    def _set_pen_color(self, hex_color: str):
        self.image_label.set_pen_color(QColor(hex_color))
        for sw, h in self._swatches:
            border = "3px solid #0d6efd" if h == hex_color else "2px solid #adb5bd"
            sw.setStyleSheet(f"background:{h};border-radius:11px;border:{border};")
        # Clicking a color automatically activates draw mode
        self._draw_btn.setChecked(True)


class ClickableImageLabel(QLabel):
    def __init__(self, empty_text="", viewer_title="Image Viewer", parent=None):
        super().__init__(empty_text, parent)
        self.viewer_title = viewer_title
        self.full_pixmap = QPixmap()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.open_badge = QLabel(self)
        self.open_badge.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon).pixmap(16, 16))
        self.open_badge.setFixedSize(28, 28)
        self.open_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.open_badge.setStyleSheet("background: rgba(13, 110, 253, 0.92); border-radius: 14px; border: 1px solid rgba(255, 255, 255, 0.65);")
        self.open_badge.hide()

    def set_viewable_pixmap(self, pixmap, max_width, max_height):
        self.full_pixmap = pixmap
        scaled = pixmap.scaled(
            max_width,
            max_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setText("")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to open and zoom")
        self.open_badge.show()
        self.open_badge.raise_()
        self._position_badge()

    def clear_view(self, text):
        self.full_pixmap = QPixmap()
        self.setPixmap(QPixmap())
        self.setText(text)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip("")
        self.open_badge.hide()

    def resizeEvent(self, event):
        self._position_badge()
        super().resizeEvent(event)

    def _position_badge(self):
        self.open_badge.move(
            max(8, self.width() - self.open_badge.width() - 10),
            max(8, self.height() - self.open_badge.height() - 10),
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.full_pixmap.isNull():
            dialog = ImageZoomDialog(self.full_pixmap, self.viewer_title, self)
            dialog.exec()
            return
        super().mousePressEvent(event)


class ScreeningPage(QWidget):
    """Patient screening page for DR detection with two-step workflow"""

    def __init__(self):
        super().__init__()
        self.current_image = None
        self.patient_counter = 0
        self.min_dob_date = QDate(1900, 1, 1)
        self.max_dob_date = QDate.currentDate()
        self.last_result_class = "Pending"
        self.last_result_conf = "Pending"
        self._current_eye_saved = False
        self._first_eye_result = None
        self.stacked_widget = QStackedWidget()
        self.init_ui()

    def init_ui(self):
        """Initialize the revised UI: patient info and image upload in one window, results in new window"""
        self._apply_ui_polish()
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        # Unified page: Patient Info + Image Upload
        unified_page = self.create_unified_page()
        self.results_page = ResultsWindow(self)
        self.stacked_widget.addWidget(unified_page)
        self.stacked_widget.addWidget(self.results_page)
        main_layout.addWidget(self.stacked_widget)
        self._setup_validators()

    def _apply_ui_polish(self):
        self.setStyleSheet("""
            QWidget {
                background: #f8f9fa;
                color: #212529;
                font-size: 13px;
                font-family: "Calibri", "Inter", "Arial";
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 8px;
                font-size: 16px;
                font-weight: 700;
                color: #007bff;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #007bff;
                letter-spacing: 0.2px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
                background: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 8px;
                padding: 2px 8px;
                min-height: 24px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
                border: 1px solid #0d6efd;
            }
            QPushButton {
                background: #e9ecef;
                color: #212529;
                border: 1px solid #ced4da;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #dee2e6;
            }
            QPushButton:focus {
                border: 1px solid #0d6efd;
            }
            QPushButton:disabled {
                background: #f1f3f5;
                color: #adb5bd;
                border: 1px solid #e9ecef;
            }
            QPushButton#primaryAction {
                background: #0d6efd;
                color: #ffffff;
                border: 1px solid #0b5ed7;
            }
            QPushButton#primaryAction:hover {
                background: #0b5ed7;
            }
            QPushButton#secondaryAction {
                background: #ffffff;
                color: #0d6efd;
                border: 1px solid #0d6efd;
            }
            QPushButton#secondaryAction:hover {
                background: #e8f0fe;
            }
            QPushButton#dangerAction {
                background: #ffffff;
                color: #dc3545;
                border: 1px solid #dc3545;
            }
            QPushButton#dangerAction:hover {
                background: #fff5f5;
            }
            QLabel#pageHeader {
                font-size: 22px;
                font-weight: 700;
                color: #007bff;
                letter-spacing: 0.2px;
                font-family: "Calibri", "Inter", "Arial";
            }
            QLabel#statusLabel {
                color: #495057;
                font-size: 12px;
            }
            QLabel#pageSubtitle {
                color: #6c757d;
                font-size: 13px;
            }
            QFrame#resultHero, QFrame#resultStatCard, QFrame#actionRail {
                background: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 12px;
            }
            QFrame#resultHero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffffff, stop:1 #f3f8ff);
            }
            QLabel#resultChip {
                background: #e8f1ff;
                color: #0b5ed7;
                border: 1px solid #cfe2ff;
                border-radius: 999px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#resultStatTitle {
                color: #6c757d;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#resultStatValue {
                color: #1f2937;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#surfaceLabel {
                border: 2px dashed #ced4da;
                background: #f8f9fa;
                border-radius: 12px;
                color: #6c757d;
                padding: 16px;
                font-size: 12px;
            }
            QLabel#heatmapPlaceholder {
                border: 2px dashed #9ec5fe;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eef5ff, stop:1 #e2ecff);
                border-radius: 12px;
                color: #0b5ed7;
                padding: 16px;
                font-size: 12px;
            }
            QFrame#actionRail {
                background: #f8fbff;
            }
        """)

    def create_unified_page(self):
        container = QWidget()
        root_layout = QHBoxLayout(container)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(14)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        left_content = QWidget()
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setContentsMargins(0, 0, 6, 0)
        left_content_layout.setSpacing(12)
        left_scroll.setWidget(left_content)
        # Patient Info
        self._scr_patient_group = QGroupBox("Patient Information")
        self._scr_patient_group.setMinimumWidth(300)
        self._scr_patient_group.setMaximumWidth(640)
        self._scr_patient_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._scr_patient_form = QFormLayout()
        self._scr_patient_form.setContentsMargins(12, 14, 12, 12)
        self._scr_patient_form.setHorizontalSpacing(14)
        self._scr_patient_form.setVerticalSpacing(6)
        self._scr_patient_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._scr_patient_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.p_id = QLineEdit()
        self.p_id.setReadOnly(True)
        self.p_id.setMinimumHeight(24)
        self.generate_patient_id()
        self._scr_patient_form.addRow("Patient ID:", self.p_id)
        self.p_name = QLineEdit()
        self.p_name.setPlaceholderText("Full name")
        self.p_name.setMinimumHeight(24)
        self._scr_patient_form.addRow("Name:", self.p_name)
        self.p_dob = QLineEdit()
        self.p_dob.setPlaceholderText("dd/mm/yyyy")
        self.p_dob.setMaxLength(10)
        self.p_dob.setMinimumHeight(24)
        self._dob_default_style = ""
        self._dob_invalid_style = """
            QLineEdit {
                border: 1.5px solid #dc3545;
                border-radius: 8px;
                padding: 8px;
            }
        """
        self.p_dob.setStyleSheet(self._dob_default_style)
        self.p_dob.textChanged.connect(self._on_dob_text_changed)
        self._scr_patient_form.addRow("Date of Birth:", self.p_dob)
        self.p_age = QSpinBox()
        self.p_age.setRange(0, 120)
        self.p_age.setSuffix(" years")
        self.p_age.setReadOnly(True)
        self.p_age.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.p_age.setSpecialValueText(" ")
        self.p_age.setValue(0)
        self.p_age.setMinimumHeight(24)
        self._scr_patient_form.addRow("Age:", self.p_age)
        self.p_sex = QComboBox()
        self.p_sex.addItems(["", "Male", "Female", "Prefer not to say"])
        self.p_sex.setMinimumHeight(24)
        self._scr_patient_form.addRow("Sex:", self.p_sex)
        self.p_contact = QLineEdit()
        self.p_contact.setPlaceholderText("Phone or Email")
        self.p_contact.setMinimumHeight(24)
        self._scr_patient_form.addRow("Contact:", self.p_contact)
        self.p_eye = QComboBox()
        self.p_eye.addItems(["", "Right Eye", "Left Eye"])
        self.p_eye.setMinimumHeight(24)
        self._scr_patient_form.addRow("Eye Screened:", self.p_eye)
        self._scr_patient_group.setLayout(self._scr_patient_form)
        # Clinical History
        self._scr_clinical_group = QGroupBox("Clinical History")
        self._scr_clinical_group.setMinimumWidth(300)
        self._scr_clinical_group.setMaximumWidth(640)
        self._scr_clinical_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._scr_clinical_form = QFormLayout()
        self.diabetes_type = QComboBox()
        self.diabetes_type.addItems(["Select", "Type 1", "Type 2", "Gestational", "Other"])
        self._scr_clinical_form.addRow("Diabetes Type:", self.diabetes_type)

        # Diagnosis Date field
        self.diabetes_diagnosis_date = QLineEdit()
        self.diabetes_diagnosis_date.setPlaceholderText("dd/mm/yyyy")
        self.diabetes_diagnosis_date.setMaxLength(10)
        self.diabetes_diagnosis_date.setMinimumHeight(24)
        self.diabetes_diagnosis_date.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 6px;
                padding: 0 8px;
            }
            QLineEdit:focus {
                border: 1px solid #0d6efd;
            }
        """)
        self.diabetes_diagnosis_date.textChanged.connect(self._on_diagnosis_date_changed)
        self._scr_clinical_form.addRow("Diagnosis Date:", self.diabetes_diagnosis_date)

        # Duration (now auto-calculated, read-only)
        self.diabetes_duration = QSpinBox()
        self.diabetes_duration.setSuffix(" years")
        self.diabetes_duration.setRange(0, 80)
        self.diabetes_duration.setReadOnly(True)
        self.diabetes_duration.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.diabetes_duration.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.diabetes_duration.setStyleSheet("""
            QSpinBox {
                background: #e9ecef;
                border: 1px solid #adb5bd;
                border-radius: 6px;
                padding: 0 8px;
                color: #495057;
            }
        """)
        self._scr_clinical_form.addRow("Duration:", self.diabetes_duration)
        self.hba1c = QDoubleSpinBox()
        self.hba1c.setRange(4.0, 15.0)
        self.hba1c.setDecimals(1)
        self.hba1c.setSuffix(" %")
        self.hba1c.setValue(7.0)
        self.hba1c.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.hba1c.setStyleSheet("""
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
            }
        """)
        self._scr_clinical_form.addRow("HbA1c:", self.hba1c)
        self.prev_treatment = QCheckBox("Previous DR Treatment")
        self.prev_treatment.setStyleSheet("""
            QCheckBox {
                color: #212529;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #6c757d;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #007bff;
                border: 1px solid #0056b3;
            }
        """)
        self._scr_clinical_form.addRow("", self.prev_treatment)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Enter clinical notes")
        self.notes.setStyleSheet("""
            QTextEdit {
                background: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QTextEdit:focus {
                border: 1px solid #0d6efd;
            }
        """)
        self._scr_clinical_form.addRow("Notes:", self.notes)
        self._scr_clinical_group.setLayout(self._scr_clinical_form)
        self._apply_flat_form_label_style(self._scr_patient_form)
        self._apply_flat_form_label_style(self._scr_clinical_form)

        # Vital Signs & Symptoms
        self._scr_vitals_group = QGroupBox("Vital Signs & Symptoms")
        self._scr_vitals_group.setMinimumWidth(300)
        self._scr_vitals_group.setMaximumWidth(640)
        self._scr_vitals_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._scr_vitals_form = QFormLayout()

        # Visual Acuity (Left / Right)
        va_layout = QHBoxLayout()
        self.va_left = QLineEdit()
        self.va_left.setPlaceholderText("e.g., 20/20")
        self.va_left.setMaxLength(10)
        self.va_left.setMinimumHeight(24)
        self.va_left.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 6px;
                padding: 0 8px;
            }
            QLineEdit:focus {
                border: 1px solid #0d6efd;
            }
        """)
        self.va_right = QLineEdit()
        self.va_right.setPlaceholderText("e.g., 20/20")
        self.va_right.setMaxLength(10)
        self.va_right.setMinimumHeight(24)
        self.va_right.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 6px;
                padding: 0 8px;
            }
            QLineEdit:focus {
                border: 1px solid #0d6efd;
            }
        """)
        va_left_label = QLabel("Left:")
        va_left_label.setStyleSheet("color: #495057; font-weight: 500;")
        va_right_label = QLabel("Right:")
        va_right_label.setStyleSheet("color: #495057; font-weight: 500;")
        va_layout.addWidget(va_left_label)
        va_layout.addWidget(self.va_left, 1)
        va_layout.addSpacing(10)
        va_layout.addWidget(va_right_label)
        va_layout.addWidget(self.va_right, 1)
        self._scr_vitals_form.addRow("Visual Acuity:", va_layout)

        # Blood Pressure (Systolic / Diastolic)
        bp_layout = QHBoxLayout()
        self.bp_systolic = QSpinBox()
        self.bp_systolic.setRange(0, 250)
        self.bp_systolic.setSpecialValueText(" ")
        self.bp_systolic.setMinimumHeight(24)
        self.bp_systolic.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.bp_systolic.setStyleSheet("""
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
            }
        """)
        self.bp_diastolic = QSpinBox()
        self.bp_diastolic.setRange(0, 180)
        self.bp_diastolic.setSpecialValueText(" ")
        self.bp_diastolic.setMinimumHeight(24)
        self.bp_diastolic.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.bp_diastolic.setStyleSheet("""
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
            }
        """)
        bp_separator = QLabel("/")
        bp_separator.setStyleSheet("color: #495057; font-weight: 500;")
        bp_unit = QLabel("mmHg")
        bp_unit.setStyleSheet("color: #6c757d; font-size: 9pt;")
        bp_layout.addWidget(self.bp_systolic, 1)
        bp_layout.addWidget(bp_separator)
        bp_layout.addWidget(self.bp_diastolic, 1)
        bp_layout.addWidget(bp_unit)
        bp_layout.addStretch()
        self._scr_vitals_form.addRow("Blood Pressure:", bp_layout)

        # Blood Glucose (FBS / RBS)
        bg_layout = QHBoxLayout()
        fbs_label = QLabel("FBS:")
        fbs_label.setStyleSheet("color: #495057; font-weight: 500;")
        self.fbs = QSpinBox()
        self.fbs.setRange(0, 600)
        self.fbs.setSuffix(" mg/dL")
        self.fbs.setSpecialValueText(" ")
        self.fbs.setMinimumHeight(24)
        self.fbs.setMinimumWidth(110)
        self.fbs.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.fbs.setStyleSheet("""
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
            }
        """)
        rbs_label = QLabel("RBS:")
        rbs_label.setStyleSheet("color: #495057; font-weight: 500;")
        self.rbs = QSpinBox()
        self.rbs.setRange(0, 800)
        self.rbs.setSuffix(" mg/dL")
        self.rbs.setSpecialValueText(" ")
        self.rbs.setMinimumHeight(24)
        self.rbs.setMinimumWidth(110)
        self.rbs.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.rbs.setStyleSheet("""
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
            }
        """)
        bg_layout.addWidget(fbs_label)
        bg_layout.addWidget(self.fbs)
        bg_layout.addSpacing(10)
        bg_layout.addWidget(rbs_label)
        bg_layout.addWidget(self.rbs)
        bg_layout.addStretch()
        self._scr_vitals_form.addRow("Blood Glucose:", bg_layout)

        # Symptoms Checklist
        symptoms_layout = QVBoxLayout()
        symptoms_layout.setSpacing(6)
        self.symptom_blurred = QCheckBox("Blurred vision")
        self.symptom_blurred.setStyleSheet("""
            QCheckBox {
                color: #212529;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #6c757d;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #007bff;
                border: 1px solid #0056b3;
            }
        """)
        self.symptom_floaters = QCheckBox("Floaters")
        self.symptom_floaters.setStyleSheet("""
            QCheckBox {
                color: #212529;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #6c757d;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #007bff;
                border: 1px solid #0056b3;
            }
        """)
        self.symptom_flashes = QCheckBox("Flashes")
        self.symptom_flashes.setStyleSheet("""
            QCheckBox {
                color: #212529;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #6c757d;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #007bff;
                border: 1px solid #0056b3;
            }
        """)
        self.symptom_vision_loss = QCheckBox("Vision loss")
        self.symptom_vision_loss.setStyleSheet("""
            QCheckBox {
                color: #212529;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #6c757d;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #007bff;
                border: 1px solid #0056b3;
            }
        """)
        symptoms_layout.addWidget(self.symptom_blurred)
        symptoms_layout.addWidget(self.symptom_floaters)
        symptoms_layout.addWidget(self.symptom_flashes)
        symptoms_layout.addWidget(self.symptom_vision_loss)
        self._scr_vitals_form.addRow("Symptoms:", symptoms_layout)

        self._scr_vitals_group.setLayout(self._scr_vitals_form)
        self._apply_flat_form_label_style(self._scr_vitals_form)

        # Image Upload
        self._scr_image_group = QGroupBox("Fundus Image Upload")
        self._scr_image_group.setMinimumWidth(520)
        self._scr_image_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        image_layout = QVBoxLayout()
        image_layout.setContentsMargins(12, 14, 12, 12)
        image_layout.setSpacing(10)
        self.image_label = QLabel()
        self.image_label.setMinimumSize(480, 340)
        self.image_label.setMaximumHeight(460)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self._apply_upload_placeholder_style()
        image_layout.addWidget(self.image_label, 1)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 2, 0, 0)
        btn_layout.setSpacing(8)
        self.btn_upload = QPushButton("Upload Image")
        self.btn_upload.setObjectName("primaryAction")
        self.btn_upload.setMinimumHeight(28)
        self.btn_upload.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_upload.clicked.connect(self.upload_image)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("dangerAction")
        self.btn_clear.setMinimumHeight(28)
        self.btn_clear.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_clear.clicked.connect(self.clear_image)
        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_clear)
        image_layout.addLayout(btn_layout)
        self._scr_image_group.setLayout(image_layout)

        # Left side remains scrollable in smaller windows.
        left_content_layout.addWidget(self._scr_patient_group)
        left_content_layout.addWidget(self._scr_clinical_group)
        left_content_layout.addWidget(self._scr_vitals_group)
        left_content_layout.addStretch()

        # Keep form fields compact in width so inputs don't stretch too long.
        compact_inputs = [
            self.p_id,
            self.p_name,
            self.p_dob,
            self.p_age,
            self.p_sex,
            self.p_contact,
            self.p_eye,
            self.diabetes_type,
            self.diabetes_diagnosis_date,
            self.diabetes_duration,
            self.hba1c,
            self.va_left,
            self.va_right,
            self.bp_systolic,
            self.bp_diastolic,
            self.fbs,
            self.rbs,
            self.notes,
        ]
        for widget in compact_inputs:
            widget.setMaximumWidth(360)

        # Build responsive right column
        right_col = QWidget()
        right_col_layout = QVBoxLayout(right_col)
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(12)
        right_col_layout.addWidget(self._scr_image_group, 1)
        right_col_layout.addStretch()

        analyze_layout = QHBoxLayout()
        analyze_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_analyze = QPushButton("Analyze Image")
        self.btn_analyze.setObjectName("primaryAction")
        self.btn_analyze.setMinimumHeight(32)
        self.btn_analyze.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setAutoDefault(True)
        self.btn_analyze.setDefault(True)
        self.btn_analyze.clicked.connect(self.open_results_window)
        analyze_layout.addWidget(self.btn_analyze)
        right_col_layout.addLayout(analyze_layout)

        # Keep upload area fixed (not inside scroll).
        root_layout.addWidget(left_scroll, 1)
        root_layout.addWidget(right_col, 1)

        self._set_tab_order_unified()
        return container

    def _apply_upload_placeholder_style(self):
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Upload a fundus image\nJPG, PNG, JPEG")
        self.image_label.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #9ec5fe;
                border-radius: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f8fbff, stop:1 #eef5ff);
                color: #0b5ed7;
                padding: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            """
        )

    def _apply_upload_loaded_style(self):
        self.image_label.setStyleSheet(
            """
            QLabel {
                border: 1px solid #cfe2ff;
                border-radius: 12px;
                background: #ffffff;
                padding: 8px;
            }
            """
        )

    def _apply_flat_form_label_style(self, form_layout: QFormLayout):
        for row in range(form_layout.rowCount()):
            item = form_layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setStyleSheet(
                    "color: #212529; background: transparent; border: none;"
                    "font-size: 13px; font-weight: 600;"
                )

    def _set_tab_order_unified(self):
        self.setTabOrder(self.p_name, self.p_dob)
        self.setTabOrder(self.p_dob, self.p_sex)
        self.setTabOrder(self.p_sex, self.p_contact)
        self.setTabOrder(self.p_contact, self.p_eye)
        self.setTabOrder(self.p_eye, self.diabetes_type)
        self.setTabOrder(self.diabetes_type, self.diabetes_diagnosis_date)
        self.setTabOrder(self.diabetes_diagnosis_date, self.diabetes_duration)
        self.setTabOrder(self.diabetes_duration, self.hba1c)
        self.setTabOrder(self.hba1c, self.prev_treatment)
        self.setTabOrder(self.prev_treatment, self.notes)
        self.setTabOrder(self.notes, self.va_left)
        self.setTabOrder(self.va_left, self.va_right)
        self.setTabOrder(self.va_right, self.bp_systolic)
        self.setTabOrder(self.bp_systolic, self.bp_diastolic)
        self.setTabOrder(self.bp_diastolic, self.fbs)
        self.setTabOrder(self.fbs, self.rbs)
        self.setTabOrder(self.rbs, self.symptom_blurred)
        self.setTabOrder(self.symptom_blurred, self.symptom_floaters)
        self.setTabOrder(self.symptom_floaters, self.symptom_flashes)
        self.setTabOrder(self.symptom_flashes, self.symptom_vision_loss)
        self.setTabOrder(self.symptom_vision_loss, self.btn_upload)
        self.setTabOrder(self.btn_upload, self.btn_clear)
        self.setTabOrder(self.btn_clear, self.btn_analyze)

    def _setup_validators(self):
        self.name_regex = QRegularExpression(r"^[A-Za-z][A-Za-z\s\-']*$")
        self.p_name.setValidator(QRegularExpressionValidator(self.name_regex, self))

        # Visual acuity validator (20/XX or 6/XX format)
        self.va_regex = QRegularExpression(r"^(20|6)/\d{1,3}$")
        va_validator = QRegularExpressionValidator(self.va_regex, self)
        self.va_left.setValidator(va_validator)
        self.va_right.setValidator(va_validator)

        # Connect blood pressure and glucose validation
        self.bp_systolic.editingFinished.connect(self._validate_blood_pressure)
        self.bp_diastolic.editingFinished.connect(self._validate_blood_pressure)
        self.fbs.editingFinished.connect(self._validate_blood_glucose)
        self.rbs.editingFinished.connect(self._validate_blood_glucose)

    def _validate_patient_basics(self):
        name = self.p_name.text().strip()
        dob_date = self._get_dob_date()
        sex = self.p_sex.currentText().strip()
        contact = self.p_contact.text().strip()

        missing_fields = []
        if not name:
            missing_fields.append("Name")
        if not dob_date.isValid():
            missing_fields.append("Date of Birth")
        if not sex:
            missing_fields.append("Sex")
        if not contact:
            missing_fields.append("Contact")

        if missing_fields:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill up every patient information field.\n\nMissing: " + ", ".join(missing_fields),
            )
            return False

        if not self.name_regex.match(name).hasMatch():
            QMessageBox.warning(self, "Error", "Name can only include letters, spaces, hyphens, and apostrophes")
            return False
        return True

    def _on_dob_text_changed(self, text):
        digits = "".join(ch for ch in text if ch.isdigit())[:8]
        if len(digits) <= 2:
            formatted = digits
        elif len(digits) <= 4:
            formatted = f"{digits[:2]}/{digits[2:]}"
        else:
            formatted = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"

        if formatted != text:
            self.p_dob.blockSignals(True)
            self.p_dob.setText(formatted)
            self.p_dob.blockSignals(False)
            self.p_dob.setCursorPosition(len(formatted))

        self._update_dob_input_style(digits)

        self.update_age_from_dob(self._get_dob_date())

    def _update_dob_input_style(self, digits):
        has_invalid_value = False

        if len(digits) >= 1 and int(digits[0]) > 3:
            has_invalid_value = True

        if len(digits) >= 2:
            day = int(digits[:2])
            if day < 1 or day > 31:
                has_invalid_value = True

        if len(digits) >= 3 and int(digits[2]) > 1:
            has_invalid_value = True

        if len(digits) >= 4:
            month = int(digits[2:4])
            if month < 1 or month > 12:
                has_invalid_value = True

        if len(digits) == 8 and not self._get_dob_date().isValid():
            has_invalid_value = True

        self.p_dob.setStyleSheet(self._dob_invalid_style if has_invalid_value else self._dob_default_style)

    def _get_dob_date(self):
        if isinstance(self.p_dob, QDateEdit):
            date = self.p_dob.date()
            if date == self.min_dob_date:
                return QDate()
        else:
            date = QDate.fromString(self.p_dob.text().strip(), "dd/MM/yyyy")

        if not date.isValid():
            return QDate()
        if date < self.min_dob_date or date > QDate.currentDate():
            return QDate()
        return date

    def _on_diagnosis_date_changed(self, text):
        """Format diagnosis date input and auto-calculate duration."""
        digits = "".join(ch for ch in text if ch.isdigit())[:8]

        if len(digits) <= 2:
            formatted = digits
        elif len(digits) <= 4:
            formatted = f"{digits[:2]}/{digits[2:]}"
        else:
            formatted = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"

        if formatted != text:
            self.diabetes_diagnosis_date.blockSignals(True)
            self.diabetes_diagnosis_date.setText(formatted)
            self.diabetes_diagnosis_date.blockSignals(False)
            self.diabetes_diagnosis_date.setCursorPosition(len(formatted))

        # Validate and style
        self._update_diagnosis_date_style(digits)

        # Auto-calculate duration
        self._update_duration_from_diagnosis_date()

    def _update_diagnosis_date_style(self, digits):
        """Apply red border if invalid diagnosis date."""
        has_invalid_value = False

        # Check day first digit
        if len(digits) >= 1 and int(digits[0]) > 3:
            has_invalid_value = True

        # Check day range (1-31)
        if len(digits) >= 2:
            day = int(digits[:2])
            if day < 1 or day > 31:
                has_invalid_value = True

        # Check month first digit
        if len(digits) >= 3 and int(digits[2]) > 1:
            has_invalid_value = True

        # Check month range (1-12)
        if len(digits) >= 4:
            month = int(digits[2:4])
            if month < 1 or month > 12:
                has_invalid_value = True

        # Full validation
        if len(digits) == 8:
            diag_date = self._get_diagnosis_date()
            dob_date = self._get_dob_date()
            if not diag_date.isValid():
                has_invalid_value = True
            elif diag_date > QDate.currentDate():
                has_invalid_value = True
            elif dob_date.isValid() and diag_date < dob_date:
                has_invalid_value = True

        # Apply styling
        invalid_style = """
            QLineEdit {
                background: #ffffff;
                border: 1.5px solid #dc3545;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """
        default_style = """
            QLineEdit {
                background: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #0d6efd;
            }
        """
        self.diabetes_diagnosis_date.setStyleSheet(invalid_style if has_invalid_value else default_style)

    def _get_diagnosis_date(self):
        """Parse and validate diagnosis date from text field."""
        date = QDate.fromString(self.diabetes_diagnosis_date.text().strip(), "dd/MM/yyyy")

        if not date.isValid():
            return QDate()
        if date < QDate(1900, 1, 1) or date > QDate.currentDate():
            return QDate()

        # Check if diagnosis date is after birth date
        dob_date = self._get_dob_date()
        if dob_date.isValid() and date < dob_date:
            return QDate()

        return date

    def _update_duration_from_diagnosis_date(self):
        """Auto-calculate diabetes duration from diagnosis date."""
        diag_date = self._get_diagnosis_date()
        if not diag_date.isValid():
            self.diabetes_duration.setValue(0)
            return

        today = QDate.currentDate()
        years = today.year() - diag_date.year()
        if (today.month(), today.day()) < (diag_date.month(), diag_date.day()):
            years -= 1

        self.diabetes_duration.setValue(max(0, years))

    def _validate_blood_pressure(self):
        """Validate blood pressure ranges."""
        sys = self.bp_systolic.value()
        dia = self.bp_diastolic.value()

        # Both must be zero or both must be filled
        if (sys == 0) != (dia == 0):
            QMessageBox.warning(
                self, "Blood Pressure",
                "Please enter both systolic and diastolic values, or leave both empty."
            )
            return False

        # If filled, check ranges
        if sys > 0:
            if sys < 80 or sys > 200:
                QMessageBox.warning(
                    self, "Blood Pressure",
                    "Systolic pressure should be between 80-200 mmHg.\nIf this reading is correct, please document in clinical notes."
                )
                return False
            if dia < 50 or dia > 130:
                QMessageBox.warning(
                    self, "Blood Pressure",
                    "Diastolic pressure should be between 50-130 mmHg.\nIf this reading is correct, please document in clinical notes."
                )
                return False
            if dia >= sys:
                QMessageBox.warning(
                    self, "Blood Pressure",
                    "Diastolic pressure must be lower than systolic pressure."
                )
                return False

        return True

    def _validate_blood_glucose(self):
        """Validate blood glucose ranges."""
        fbs = self.fbs.value()
        rbs = self.rbs.value()

        if fbs > 0 and (fbs < 70 or fbs > 400):
            QMessageBox.warning(
                self, "Blood Glucose",
                "Fasting blood sugar should be between 70-400 mg/dL.\nIf this reading is correct, please document in clinical notes."
            )
            return False

        if rbs > 0 and (rbs < 70 or rbs > 600):
            QMessageBox.warning(
                self, "Blood Glucose",
                "Random blood sugar should be between 70-600 mg/dL.\nIf this reading is correct, please document in clinical notes."
            )
            return False

        return True

    def create_patient_info_page(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        title = QLabel("Step 1: Patient Information")
        title_font = QFont("Calibri", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setObjectName("pageHeader")
        layout.addWidget(title)

        patient_group = QGroupBox("Patient Information")
        patient_form = QFormLayout()

        self.p_id = QLineEdit()
        self.p_id.setReadOnly(True)
        self.generate_patient_id()
        patient_form.addRow("Patient ID:", self.p_id)

        self.p_name = QLineEdit()
        self.p_name.setPlaceholderText("Full name")
        patient_form.addRow("Name:", self.p_name)

        self.p_dob = QDateEdit()
        self.p_dob.setCalendarPopup(True)
        self.p_dob.setDisplayFormat("yyyy-MM-dd")
        custom_calendar = QCalendarWidget()
        custom_calendar.setGridVisible(True)
        custom_calendar.setStyleSheet("""
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: white;
            }
            QCalendarWidget QToolButton {
                color: black;
                font-weight: bold;
                background-color: white;
            }
            QCalendarWidget QAbstractItemView {
                color: black;
                selection-background-color: #0078d7;
                selection-color: white;
            }
        """)
        self.p_dob.setCalendarWidget(custom_calendar)
        self.p_dob.setMinimumDate(QDate(1900, 1, 1))
        self.p_dob.setSpecialValueText(" ")
        self.p_dob.setDate(self.p_dob.minimumDate())
        self.p_dob.dateChanged.connect(self.update_age_from_dob)
        patient_form.addRow("Date of Birth:", self.p_dob)

        self.p_age = QSpinBox()
        self.p_age.setRange(0, 120)
        self.p_age.setSuffix(" years")
        self.p_age.setReadOnly(True)
        self.p_age.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.p_age.setSpecialValueText(" ")
        self.p_age.setValue(0)
        patient_form.addRow("Age:", self.p_age)

        self.p_sex = QComboBox()
        self.p_sex.addItems(["", "Male", "Female", "Other"])
        patient_form.addRow("Sex:", self.p_sex)

        self.p_contact = QLineEdit()
        self.p_contact.setPlaceholderText("Phone or Email")
        patient_form.addRow("Contact:", self.p_contact)

        self.p_eye = QComboBox()
        self.p_eye.addItems(["", "Both Eyes", "Left Eye", "Right Eye"])
        patient_form.addRow("Eye(s):", self.p_eye)

        patient_group.setLayout(patient_form)
        layout.addWidget(patient_group)

        clinical_group = QGroupBox("Clinical History")
        clinical_form = QFormLayout()

        self.diabetes_type = QComboBox()
        self.diabetes_type.addItems(["Select", "Type 1", "Type 2", "Gestational", "Other"])
        clinical_form.addRow("Diabetes Type:", self.diabetes_type)

        self.diabetes_duration = QSpinBox()
        self.diabetes_duration.setSuffix(" years")
        self.diabetes_duration.setRange(0, 80)
        clinical_form.addRow("Duration:", self.diabetes_duration)

        self.hba1c = QDoubleSpinBox()
        self.hba1c.setRange(4.0, 15.0)
        self.hba1c.setDecimals(1)
        self.hba1c.setSuffix(" %")
        clinical_form.addRow("HbA1c:", self.hba1c)

        self.prev_treatment = QCheckBox("Previous DR Treatment")
        self.prev_treatment.setStyleSheet("""
            QCheckBox {
                color: #212529;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #6c757d;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #007bff;
                border: 1px solid #0056b3;
            }
        """)
        clinical_form.addRow("", self.prev_treatment)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Enter clinical notes")
        self.notes.setStyleSheet("""
            QTextEdit {
                background: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QTextEdit:focus {
                border: 1px solid #0d6efd;
            }
        """)
        clinical_form.addRow("Notes:", self.notes)

        clinical_group.setLayout(clinical_form)
        layout.addWidget(clinical_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_screening)
        button_layout.addWidget(self.btn_cancel)
        self.btn_proceed = QPushButton("Proceed to Image")
        self.btn_proceed.clicked.connect(self.validate_and_proceed)
        button_layout.addWidget(self.btn_proceed)
        layout.addLayout(button_layout)
        layout.addStretch()
        return container

    def create_image_analysis_page(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        title = QLabel("Step 2: Image Analysis")
        title_font = QFont("Calibri", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setObjectName("pageHeader")
        layout.addWidget(title)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #555; font-size: 11pt;")
        layout.addWidget(self.summary_label)

        image_group = QGroupBox("Fundus Image")
        image_layout = QVBoxLayout()

        self.image_label = QLabel("No image loaded")
        self.image_label.setMinimumSize(450, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed #ccc; background-color: #f9f9f9;")
        image_layout.addWidget(self.image_label)

        btn_layout = QHBoxLayout()
        self.btn_upload = QPushButton("Upload Image")
        self.btn_upload.clicked.connect(self.upload_image)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_image)
        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_clear)
        image_layout.addLayout(btn_layout)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group, 1)

        results_group = QGroupBox("Results")
        results_layout = QFormLayout()
        self.r_class = QLabel("—")
        self.r_class.setFont(QFont("Calibri", 16, QFont.Weight.Bold))
        results_layout.addRow("Classification:", self.r_class)
        self.r_conf = QLabel("—")
        results_layout.addRow("Confidence:", self.r_conf)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_analyze = QPushButton("Analyze Image")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self.analyze_image)
        button_layout.addWidget(self.btn_analyze)
        self.btn_save = QPushButton("Save Screening")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_screening)
        button_layout.addWidget(self.btn_save)
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back_to_patient_info)
        button_layout.addWidget(self.btn_back)
        self.btn_new = QPushButton("New Patient")
        self.btn_new.clicked.connect(self.reset_screening)
        button_layout.addWidget(self.btn_new)
        layout.addLayout(button_layout)
        return container

    # ==================== LOGIC FUNCTIONS ====================

    def generate_patient_id(self):
        pid = self._next_unique_patient_id()
        self.p_id.setText(pid)
        return pid

    def _next_unique_patient_id(self):
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        for _ in range(25):
            # Short, readable ID: ES-YYMMDD-XXXXX (e.g., ES-260316-A9K2M)
            stamp = datetime.now().strftime("%y%m%d")
            suffix = "".join(secrets.choice(alphabet) for _ in range(5))
            candidate = f"ES-{stamp}-{suffix}"
            if not self._patient_id_exists(candidate):
                return candidate

        # Fallback uses a longer, high-entropy suffix if repeated collisions happen.
        fallback = datetime.now().strftime("%y%m%d")
        return f"ES-{fallback}-{secrets.token_hex(4).upper()}"

    def _patient_id_exists(self, patient_id):
        patient_id = str(patient_id or "").strip()
        if not patient_id:
            return False

        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM patient_records WHERE patient_id = ? LIMIT 1", (patient_id,))
            exists = cur.fetchone() is not None
            conn.close()
            return exists
        except Exception:
            return False

    def update_age_from_dob(self, date):
        if not date.isValid():
            self.p_age.setValue(0)
            return
        today = QDate.currentDate()
        age = today.year() - date.year()
        if (today.month(), today.day()) < (date.month(), date.day()):
            age -= 1
        self.p_age.setValue(max(0, age))

    def validate_and_proceed(self):
        if not self._validate_patient_basics():
            return
        dob_date = self._get_dob_date()
        dob_str = dob_date.toString("yyyy-MM-dd") if dob_date.isValid() else ""
        summary = f"<b>{self.p_name.text()}</b> | ID: {self.p_id.text()} | DOB: {dob_str} | Age: {self.p_age.value()}"
        self.summary_label.setText(summary)
        self.stacked_widget.setCurrentIndex(1)

    def cancel_screening(self):
        reply = QMessageBox.question(
            self, "Cancel", "Are you sure you want to cancel? All data will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_screening()

    def go_back_to_patient_info(self):
        reply = QMessageBox.question(
            self, "Go Back", "Going back will clear the image. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_image()
            self.stacked_widget.setCurrentIndex(0)

    def reset_screening(self):
        self.generate_patient_id()
        self.p_name.clear()
        self.p_contact.clear()
        if isinstance(self.p_dob, QDateEdit):
            self.p_dob.setDate(self.min_dob_date)
        else:
            self.p_dob.clear()
        self.p_age.setValue(0)
        self.p_sex.setCurrentIndex(0)
        self.p_eye.setCurrentIndex(0)
        self.diabetes_type.setCurrentIndex(0)
        self.diabetes_duration.setValue(0)
        self.hba1c.setValue(7.0)
        self.prev_treatment.setChecked(False)
        self.notes.clear()
        self.current_image = None
        self._apply_upload_placeholder_style()
        self.last_result_class = "Pending"
        self.last_result_conf = "Pending"
        self._current_eye_saved = False
        self._first_eye_result = None
        self.btn_analyze.setEnabled(False)
        self.stacked_widget.setCurrentIndex(0)

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Fundus Image", "", "Images (*.jpg *.png *.jpeg)"
        )
        if path:
            self.current_image = path
            self._set_preview_image(path)
            self.btn_analyze.setEnabled(True)

    def screen_another_image(self):
        """Pick a new image from the results page, re-run analysis, update results in place."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Fundus Image", "", "Images (*.jpg *.png *.jpeg)"
        )
        if not path:
            return
        self.current_image = path
        # Update the upload panel too so it stays in sync
        self._set_preview_image(path)
        self.btn_analyze.setEnabled(True)

        # Re-run inference with the new image
        self.results_page.set_results(
            self.p_name.text(), path,
            "Analyzing…", "Please wait",
        )
        patient_data = self._collect_patient_data()
        self._worker = _InferenceWorker(path)
        self._worker.result_ready.connect(
            lambda label, conf: self._on_prediction_ready(
                label, conf, self.p_eye.currentText(), patient_data
            )
        )
        self._worker.finished.connect(
            lambda label, conf, hmap: self._on_inference_done(
                label, conf, hmap, self.p_eye.currentText(), patient_data
            )
        )
        self._worker.error.connect(self._on_inference_error)
        self._worker.ungradable.connect(self._on_image_ungradable)
        self._worker.start()

    def _set_preview_image(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        target_size = self.image_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = QSize(320, 260)
        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setText("")
        self._apply_upload_loaded_style()
        self.image_label.setPixmap(scaled)

    def open_results_window(self):
        if not self._validate_patient_basics():
            return
        if not self.current_image:
            QMessageBox.warning(self, "Error", "No image loaded")
            return
        confirm_box = QMessageBox(self)
        confirm_box.setWindowTitle("Confirm Details")
        confirm_box.setText("Please confirm all patient information is correct before proceeding to results.")
        proceed_button = confirm_box.addButton("Proceed to Results", QMessageBox.ButtonRole.AcceptRole)
        confirm_box.addButton("Edit Information", QMessageBox.ButtonRole.RejectRole)

        confirm_box.exec()
        if confirm_box.clickedButton() != proceed_button:
            return

        self._current_eye_saved = False
        eye_label = self.p_eye.currentText()

        # Show the results page immediately with a loading state
        self.results_page.set_results(
            self.p_name.text(),
            self.current_image,
            "Analyzing…",
            "Please wait",
            eye_label=eye_label,
            first_eye_result=self._first_eye_result,
        )
        self.stacked_widget.setCurrentIndex(1)
        self.btn_analyze.setEnabled(False)

        # Run inference on a background thread
        patient_data = self._collect_patient_data()
        self._worker = _InferenceWorker(self.current_image)
        self._worker.result_ready.connect(
            lambda label, conf: self._on_prediction_ready(label, conf, eye_label, patient_data)
        )
        self._worker.finished.connect(
            lambda label, conf, hmap: self._on_inference_done(label, conf, hmap, eye_label, patient_data)
        )
        self._worker.error.connect(self._on_inference_error)
        self._worker.ungradable.connect(self._on_image_ungradable)
        self._worker.start()

    def _on_prediction_ready(self, label: str, conf: str, eye_label: str, patient_data: dict | None = None):
        self.last_result_class = label
        self.last_result_conf = conf
        self.results_page.set_results(
            self.p_name.text(),
            self.current_image,
            label,
            conf,
            eye_label=eye_label,
            first_eye_result=self._first_eye_result,
            patient_data=patient_data,
            heatmap_pending=True,
        )

    def _on_inference_done(self, label: str, conf: str, heatmap_path: str, eye_label: str, patient_data: dict | None = None):
        self.last_result_class = label
        self.last_result_conf = conf
        self.btn_analyze.setEnabled(True)
        self.results_page.set_results(
            self.p_name.text(),
            self.current_image,
            label,
            conf,
            eye_label=eye_label,
            first_eye_result=self._first_eye_result,
            heatmap_path=heatmap_path,
            patient_data=patient_data,
            heatmap_pending=False,
        )

    def _on_inference_error(self, message: str):
        self.btn_analyze.setEnabled(True)
        self.stacked_widget.setCurrentIndex(0)
        QMessageBox.critical(
            self, "Analysis Failed",
            f"Could not run the DR model:\n\n{message}"
        )

    def _on_image_ungradable(self, message: str):
        """Called when the quality check rejects the uploaded image."""
        self.btn_analyze.setEnabled(True)
        self.stacked_widget.setCurrentIndex(0)
        msg = QMessageBox(self)
        msg.setWindowTitle("Image Not Gradable")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            "<b>The uploaded image does not meet the minimum quality "
            "requirements for DR screening.</b>"
        )
        msg.setInformativeText(
            message + "\n\nPlease upload a clearer, well-lit fundus photograph and try again."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _collect_patient_data(self) -> dict:
        """Snapshot the current intake form into a plain dict for the explanation generator."""
        # Collect symptoms
        symptoms = []
        if self.symptom_blurred.isChecked():
            symptoms.append("Blurred vision")
        if self.symptom_floaters.isChecked():
            symptoms.append("Floaters")
        if self.symptom_flashes.isChecked():
            symptoms.append("Flashes")
        if self.symptom_vision_loss.isChecked():
            symptoms.append("Vision loss")

        return {
            "age":            self.p_age.value(),
            "hba1c":          self.hba1c.value(),
            "duration":       self.diabetes_duration.value(),
            "prev_treatment": self.prev_treatment.isChecked(),
            "diabetes_type":  self.diabetes_type.currentText(),
            "eye":            self.p_eye.currentText(),
            # New fields
            "va_left":        self.va_left.text().strip(),
            "va_right":       self.va_right.text().strip(),
            "bp_systolic":    self.bp_systolic.value() if self.bp_systolic.value() > 0 else None,
            "bp_diastolic":   self.bp_diastolic.value() if self.bp_diastolic.value() > 0 else None,
            "fbs":            self.fbs.value() if self.fbs.value() > 0 else None,
            "rbs":            self.rbs.value() if self.rbs.value() > 0 else None,
            "symptoms":       symptoms,
        }


    def clear_image(self):
        self.current_image = None
        self._apply_upload_placeholder_style()
        self.btn_analyze.setEnabled(False)

    def save_screening(self, reset_after=True):
        if not self._validate_patient_basics():
            return

        # Validate new fields
        if not self._validate_blood_pressure():
            return
        if not self._validate_blood_glucose():
            return

        name = self.p_name.text().strip()

        pid = self.p_id.text().strip()
        if not pid or self._patient_id_exists(pid):
            pid = self.generate_patient_id()

        dob_date = self._get_dob_date()
        dob_str = dob_date.toString("yyyy-MM-dd") if dob_date.isValid() else ""

        diag_date = self._get_diagnosis_date()
        diag_date_str = diag_date.toString("yyyy-MM-dd") if diag_date.isValid() else ""

        age = self.p_age.value()
        sex = self.p_sex.currentText()
        contact = self.p_contact.text().strip()
        eye = self.p_eye.currentText()
        diabetes_type = self.diabetes_type.currentText()
        duration = self.diabetes_duration.value()
        hba1c = f"{self.hba1c.value():.1f}%"
        prev_treatment = "Yes" if self.prev_treatment.isChecked() else "No"
        notes = self.notes.toPlainText().strip()
        result = self.last_result_class
        confidence = self.last_result_conf

        # New fields
        va_left = self.va_left.text().strip()
        va_right = self.va_right.text().strip()
        bp_sys = str(self.bp_systolic.value()) if self.bp_systolic.value() > 0 else ""
        bp_dia = str(self.bp_diastolic.value()) if self.bp_diastolic.value() > 0 else ""
        fbs_val = str(self.fbs.value()) if self.fbs.value() > 0 else ""
        rbs_val = str(self.rbs.value()) if self.rbs.value() > 0 else ""

        # Symptoms as Yes/No flags
        symptom_blurred_flag = "Yes" if self.symptom_blurred.isChecked() else "No"
        symptom_floaters_flag = "Yes" if self.symptom_floaters.isChecked() else "No"
        symptom_flashes_flag = "Yes" if self.symptom_flashes.isChecked() else "No"
        symptom_vision_loss_flag = "Yes" if self.symptom_vision_loss.isChecked() else "No"

        patient_data = [
            pid,
            name,
            dob_str,
            age if age > 0 else "",
            sex,
            contact,
            eye,
            diabetes_type if diabetes_type != "Select" else "",
            duration,
            hba1c,
            prev_treatment,
            notes,
            result,
            confidence,
            # New fields (11 columns)
            va_left,
            va_right,
            bp_sys,
            bp_dia,
            fbs_val,
            rbs_val,
            diag_date_str,
            symptom_blurred_flag,
            symptom_floaters_flag,
            symptom_flashes_flag,
            symptom_vision_loss_flag,
        ]

        if not self._save_screening_to_db(patient_data):
            QMessageBox.warning(self, "Save Failed", "Unable to save screening record. Please try again.")
            return

        self._current_eye_saved = True
        if reset_after:
            self.reset_screening()
        else:
            eye_label = eye or "eye"
            self._first_eye_result = {
                "eye": eye_label,
                "result": self.last_result_class,
                "confidence": self.last_result_conf,
            }
            self.results_page.mark_saved(self.p_name.text().strip(), eye_label, self.last_result_class)

    def screen_other_eye(self):
        """Save the current eye's result and switch to the same patient's other eye."""
        current_eye = self.p_eye.currentText().strip()
        opposite_eye = "Left Eye" if current_eye == "Right Eye" else "Right Eye"

        if not self._current_eye_saved:
            eye_label = current_eye or "current eye"
            reply = QMessageBox.question(
                self,
                "Save Before Switching",
                f"The screening for the <b>{eye_label}</b> has not been saved yet.\n\n"
                f"Save it now before screening the {opposite_eye}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.save_screening(reset_after=False)
                if not self._current_eye_saved:
                    return  # save failed, abort

        # Capture current patient demographics before resetting
        name = self.p_name.text()
        dob_text = self.p_dob.text() if not isinstance(self.p_dob, QDateEdit) else ""
        age = self.p_age.value()
        sex = self.p_sex.currentText()
        contact = self.p_contact.text()
        d_type = self.diabetes_type.currentText()
        d_dur = self.diabetes_duration.value()
        hba1c_val = self.hba1c.value()
        prev = self.prev_treatment.isChecked()
        notes_text = self.notes.toPlainText()

        # Preserve first eye result across reset so results page can show bilateral comparison
        saved_first_eye_result = self._first_eye_result

        # Full reset (generates new patient ID, clears everything)
        self.reset_screening()

        # Restore first eye result
        self._first_eye_result = saved_first_eye_result

        # Restore demographics for the same patient
        self.p_name.setText(name)
        if not isinstance(self.p_dob, QDateEdit):
            self.p_dob.setText(dob_text)
        self.p_age.setValue(age)
        self.p_sex.setCurrentText(sex)
        self.p_contact.setText(contact)
        self.diabetes_type.setCurrentText(d_type)
        self.diabetes_duration.setValue(d_dur)
        self.hba1c.setValue(hba1c_val)
        self.prev_treatment.setChecked(prev)
        self.notes.setPlainText(notes_text)

        # Pre-select the other eye
        self.p_eye.setCurrentText(opposite_eye)

        # Return to intake form — only the image needs to be uploaded
        self.stacked_widget.setCurrentIndex(0)

    def _save_screening_to_db(self, patient_data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO patient_records (
                    patient_id, name, birthdate, age, sex, contact, eyes,
                    diabetes_type, duration, hba1c, prev_treatment, notes,
                    result, confidence,
                    visual_acuity_left, visual_acuity_right,
                    blood_pressure_systolic, blood_pressure_diastolic,
                    fasting_blood_sugar, random_blood_sugar,
                    diabetes_diagnosis_date,
                    symptom_blurred_vision, symptom_floaters,
                    symptom_flashes, symptom_vision_loss
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                patient_data,
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._scr_patient_group.setTitle(pack["scr_patient_info"])
        self._scr_clinical_group.setTitle(pack["scr_clinical_history"])
        self._scr_image_group.setTitle(pack["scr_image_upload"])
        self.btn_upload.setText(pack["scr_upload_btn"])
        self.btn_clear.setText(pack["scr_clear_btn"])
        self.btn_analyze.setText(pack["scr_analyze_btn"])
        patient_labels = [
            pack["scr_label_pid"], pack["scr_label_name"], pack["scr_label_dob"],
            pack["scr_label_age"], pack["scr_label_sex"], pack["scr_label_contact"],
            pack["scr_label_eye"],
        ]
        for row, text in enumerate(patient_labels):
            item = self._scr_patient_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setText(text)
                item.widget().setStyleSheet(
                    "color: #212529; background: transparent; border: none;"
                    "font-size: 13px; font-weight: 600;"
                )
        clinical_labels = [
            pack["scr_label_diabetes"], pack["scr_label_duration"], pack["scr_label_hba1c"],
            None,
            pack["scr_label_notes"],
        ]
        for row, text in enumerate(clinical_labels):
            if text is None:
                continue
            item = self._scr_clinical_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setText(text)
                item.widget().setStyleSheet(
                    "color: #212529; background: transparent; border: none;"
                    "font-size: 13px; font-weight: 600;"
                )

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
                            f"(PDR) \u2014 a sight-threatening condition \u2014 was detected in {eye_phrase}",
    }
    paragraphs = [
        opening_map.get(result_class, f"{result_class} was detected in {eye_phrase}")
        + f" ({confidence_text.lower()})."
    ]

    # ── Patient context ────────────────────────────────────────────────────────
    ctx = []
    if age > 0:
        ctx.append(f"{age}\u2011year\u2011old")
    if d_type and d_type.lower() not in ("select", ""):
        ctx.append(f"{d_type} diabetes")
    if duration > 0:
        ctx.append(f"{duration}\u2011year diabetes duration")
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
            f"HbA1c of <b>{hba1c:.1f}%</b> is above the recommended target (\u22647.0\u20137.5%). "
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
                            "Schedule a repeat retinal examination in 6\u201312 months.",
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
        bilateral_title = QLabel("\u2194  Bilateral Screening Comparison")
        bilateral_title.setObjectName("resultStatTitle")
        bilateral_layout.addWidget(bilateral_title)
        brow = QHBoxLayout()
        brow.setSpacing(20)
        first_col = QVBoxLayout()
        first_col.setSpacing(4)
        self.bilateral_first_eye_lbl = QLabel("\u2014")
        self.bilateral_first_eye_lbl.setObjectName("resultStatTitle")
        self.bilateral_first_result_lbl = QLabel("\u2014")
        self.bilateral_first_result_lbl.setObjectName("resultStatValue")
        self.bilateral_first_saved_lbl = QLabel("\u2713 Saved")
        self.bilateral_first_saved_lbl.setStyleSheet("color:#198754;font-weight:700;font-size:12px;")
        first_col.addWidget(self.bilateral_first_eye_lbl)
        first_col.addWidget(self.bilateral_first_result_lbl)
        first_col.addWidget(self.bilateral_first_saved_lbl)
        brow_div = QFrame()
        brow_div.setFrameShape(QFrame.Shape.VLine)
        brow_div.setFrameShadow(QFrame.Shadow.Sunken)
        second_col = QVBoxLayout()
        second_col.setSpacing(4)
        self.bilateral_second_eye_lbl = QLabel("\u2014")
        self.bilateral_second_eye_lbl.setObjectName("resultStatTitle")
        self.bilateral_second_result_lbl = QLabel("\u2014")
        self.bilateral_second_result_lbl.setObjectName("resultStatValue")
        self.bilateral_second_saved_lbl = QLabel("Unsaved")
        self.bilateral_second_saved_lbl.setStyleSheet("color:#dc3545;font-weight:700;font-size:12px;")
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
        self.explanation.setStyleSheet("font-size: 11pt; color: #333; line-height: 1.45;")
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
            eye_suffix = f" \u2014 {eye_label}" if eye_label else ""
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
            self.bilateral_first_eye_lbl.setText(first_eye_result.get("eye", "\u2014"))
            self.bilateral_first_result_lbl.setText(first_eye_result.get("result", "\u2014"))
            self.bilateral_second_eye_lbl.setText(eye_label or "Current Eye")
            self.bilateral_second_result_lbl.setText(result_class)
            self.bilateral_second_saved_lbl.setText("Unsaved")
            self.bilateral_second_saved_lbl.setStyleSheet("color:#dc3545;font-weight:700;font-size:12px;")
            self.bilateral_frame.show()
        else:
            self.bilateral_frame.hide()

        # Classification with severity colour
        self.classification_value.setText(result_class)
        grade_color = _DR_COLORS.get(result_class, "#1f2937")
        self.classification_value.setStyleSheet(
            f"color:{grade_color};font-size:20px;font-weight:700;"
        )

        self.confidence_value.setText(confidence_text)

        # Grade-specific recommendation
        recommendation = _DR_RECOMMENDATIONS.get(result_class, "Consult a clinician")
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
                "Review the fundus image, Grad-CAM\u207a\u207a heatmap, and clinical summary below."
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
        self.save_status_label.setText(f"\u2713  Saved \u2014 {name} ({eye_label}): {result_class}")
        self.save_status_label.setStyleSheet(
            "color:#0f5132;font-weight:700;font-size:12px;"
            "background:#d1e7dd;border-radius:6px;padding:6px 8px;"
        )
        self.save_status_label.show()
        self.btn_save.setText("Saved \u2713")
        self.btn_save.setEnabled(False)
        if self.bilateral_frame.isVisible():
            self.bilateral_second_saved_lbl.setText("\u2713 Saved")
            self.bilateral_second_saved_lbl.setStyleSheet("color:#198754;font-weight:700;font-size:12px;")

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
        patient_id    = pp.p_id.text().strip()               if pp and hasattr(pp, "p_id")              else ""
        dob           = pp.p_dob.text()                      if pp and hasattr(pp, "p_dob") and hasattr(pp.p_dob, "text") else ""
        age           = str(pp.p_age.value())                if pp and hasattr(pp, "p_age")             else ""
        sex           = pp.p_sex.currentText()               if pp and hasattr(pp, "p_sex")             else ""
        contact       = pp.p_contact.text().strip()          if pp and hasattr(pp, "p_contact")         else ""
        diabetes_type = pp.diabetes_type.currentText()       if pp and hasattr(pp, "diabetes_type")     else ""
        duration      = str(pp.diabetes_duration.value())    if pp and hasattr(pp, "diabetes_duration") else ""
        hba1c_val     = f"{pp.hba1c.value():.1f}"            if pp and hasattr(pp, "hba1c")             else ""
        prev_tx       = "Yes" if pp and hasattr(pp, "prev_treatment") and pp.prev_treatment.isChecked() else "No"
        notes         = pp.notes.toPlainText().strip()       if pp and hasattr(pp, "notes")             else ""

        # Collect new fields
        va_left       = pp.va_left.text().strip()            if pp and hasattr(pp, "va_left")           else ""
        va_right      = pp.va_right.text().strip()           if pp and hasattr(pp, "va_right")          else ""
        bp_sys        = str(pp.bp_systolic.value())          if pp and hasattr(pp, "bp_systolic") and pp.bp_systolic.value() > 0 else ""
        bp_dia        = str(pp.bp_diastolic.value())         if pp and hasattr(pp, "bp_diastolic") and pp.bp_diastolic.value() > 0 else ""
        fbs_val       = str(pp.fbs.value())                  if pp and hasattr(pp, "fbs") and pp.fbs.value() > 0 else ""
        rbs_val       = str(pp.rbs.value())                  if pp and hasattr(pp, "rbs") and pp.rbs.value() > 0 else ""
        diag_date     = pp.diabetes_diagnosis_date.text().strip() if pp and hasattr(pp, "diabetes_diagnosis_date") else ""

        # Collect symptoms
        symptoms = []
        if pp:
            if hasattr(pp, "symptom_blurred") and pp.symptom_blurred.isChecked():
                symptoms.append("Blurred vision")
            if hasattr(pp, "symptom_floaters") and pp.symptom_floaters.isChecked():
                symptoms.append("Floaters")
            if hasattr(pp, "symptom_flashes") and pp.symptom_flashes.isChecked():
                symptoms.append("Flashes")
            if hasattr(pp, "symptom_vision_loss") and pp.symptom_vision_loss.isChecked():
                symptoms.append("Vision loss")
        symptoms_str = ", ".join(symptoms)

        recommendation = _DR_RECOMMENDATIONS.get(self._current_result_class, "Consult a clinician")
        grade_color    = _DR_COLORS.get(self._current_result_class, "#1f2937")
        explanation    = self.explanation.text()
        screening_date = datetime.now().strftime("%B %d, %Y  %I:%M %p")

        def _safe(value: str) -> str:
            text = str(value or "").strip()
            return escape(text) if text else "&mdash;"

        patient_id_safe = _safe(patient_id)
        patient_name_safe = _safe(self._current_patient_name)
        dob_safe = _safe(dob)
        age_safe = _safe(age)
        sex_safe = _safe(sex)
        contact_safe = _safe(contact)
        eye_safe = _safe(self._current_eye_label)
        screening_date_safe = _safe(screening_date)
        diabetes_type_safe = _safe(diabetes_type)
        duration_safe = _safe(f"{duration} year(s)" if duration else "")
        hba1c_safe = _safe(f"{hba1c_val}%" if hba1c_val else "")
        prev_tx_safe = _safe(prev_tx)
        notes_safe = _safe(notes)
        result_safe = _safe(self._current_result_class)
        confidence_safe = _safe(self._current_confidence)
        recommendation_safe = _safe(recommendation)
        notes_compact_safe = _safe((notes[:220] + "...") if len(notes) > 220 else notes)

        # Format new fields
        va_left_safe = _safe(va_left)
        va_right_safe = _safe(va_right)
        bp_safe = _safe(f"{bp_sys}/{bp_dia} mmHg" if bp_sys and bp_dia else "")
        fbs_safe = _safe(f"{fbs_val} mg/dL" if fbs_val else "")
        rbs_safe = _safe(f"{rbs_val} mg/dL" if rbs_val else "")
        diag_date_safe = _safe(diag_date)
        symptoms_safe = _safe(symptoms_str)

        explanation_text = (explanation or "No clinical analysis available.").strip()
        explanation_html = explanation_text
        explanation_html = explanation_html.replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>").replace("&lt;br /&gt;", "<br>")
        explanation_html = explanation_html.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        explanation_html = explanation_html.replace("</b>1", "</b> ")
        explanation_html = re.sub(r"\s+", " ", explanation_html).strip()
        if "<br" not in explanation_html.lower() and "<p" not in explanation_html.lower():
            explanation_html = escape(explanation_text).replace("\n\n", "<br><br>").replace("\n", "<br>")

        # Build QTextDocument with embedded images
        doc = QTextDocument()
        source_img_html  = "<div class='image-empty'>Source image not available</div>"
        heatmap_img_html = "<div class='image-empty'>Heatmap not available</div>"

        if self._current_image_path and os.path.isfile(self._current_image_path):
            src_px = QPixmap(self._current_image_path).scaled(
                320, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            try:
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("src_img"), src_px)
            except AttributeError:
                doc.addResource(QTextDocument.ImageResource, QUrl("src_img"), src_px)
            source_img_html = '<img src="src_img" />'

        if self._current_heatmap_path and os.path.isfile(self._current_heatmap_path):
            hmap_px = QPixmap(self._current_heatmap_path).scaled(
                320, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            try:
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("hmap_img"), hmap_px)
            except AttributeError:
                doc.addResource(QTextDocument.ImageResource, QUrl("hmap_img"), hmap_px)
            heatmap_img_html = '<img src="hmap_img" />'

        html = f"""<!DOCTYPE html><html><head><style>
body {{
    margin: 0;
    padding: 0;
    color: #1f2937;
    background: #ffffff;
    font-family: 'Inter', 'Roboto', 'Open Sans', 'Segoe UI', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
}}
.report {{ padding: 0 20px 14px 20px; }}
.header {{
    background: #eef4fb;
    color: #1f2937;
    padding: 14px 20px 12px 20px;
    border-bottom: 2px solid #d7e3f1;
}}
.header h1 {{
    margin: 0;
    font-size: 17pt;
    font-weight: 700;
    letter-spacing: 0.3px;
    color: #1f2937;
}}
.header p {{ margin: 4px 0 0 0; font-size: 10pt; color: #475569; }}
.section {{ margin-top: 14px; padding-top: 12px; border-top: 1px solid #dbe3ea; }}
.section-title {{
    margin: 0 0 10px 0;
    font-size: 13pt;
    color: #0f3d66;
    font-weight: 700;
}}
.cards {{ width: 100%; }}
.card {{
    display: inline-block;
    width: 48.7%;
    vertical-align: top;
    border: 1px solid #dce4ec;
    border-radius: 8px;
    background: #fbfdff;
    margin-right: 2.6%;
}}
.card:last-child {{ margin-right: 0; }}
.card-title {{
    margin: 0;
    padding: 9px 12px;
    font-size: 11pt;
    font-weight: 700;
    color: #0f3d66;
    border-bottom: 1px solid #e6edf5;
    background: #f3f8ff;
}}
.fact {{
    padding: 8px 12px;
    border-bottom: 1px solid #edf2f8;
    font-size: 10.5pt;
    line-height: 1.5;
}}
.fact:last-child {{ border-bottom: none; }}
.fact-label {{ color: #334155; font-weight: 600; }}
.fact-value {{ color: #111827; font-weight: 500; }}
.result-pill {{ color: {grade_color}; font-weight: 700; font-size: 11.5pt; }}
.analysis {{
    border: 1px solid #dce4ec;
    background: #f8fbff;
    padding: 12px 14px;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    font-size: 10.5pt;
    line-height: 1.6;
}}
table.images {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
table.images td {{
    width: 50%;
    border: 1px solid #dce4ec;
    vertical-align: top;
    text-align: center;
    padding: 8px;
}}
.image-caption {{ margin-top: 6px; color: #475569; font-size: 9.5pt; font-weight: 600; }}
.image-empty {{
    min-height: 120px;
    padding-top: 44px;
    font-size: 9.5pt;
    color: #64748b;
    border: 1px dashed #cbd5e1;
    background: #f8fafc;
}}
.footer {{
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid #dce4ec;
    font-size: 9.5pt;
    color: #4b5563;
}}
</style></head><body>
<div class="header">
    <h1>Patient Report</h1>
    <p>Generated: {screening_date_safe}</p>
</div>
<div class="report">

<div class="section">
    <div class="cards">
        <div class="card">
            <h3 class="card-title">Patient Information</h3>
            <div class="fact"><span class="fact-label">Patient Name:</span> <span class="fact-value">{patient_name_safe}</span></div>
            <div class="fact"><span class="fact-label">Patient Record:</span> <span class="fact-value">{patient_id_safe}</span></div>
            <div class="fact"><span class="fact-label">Date of Birth:</span> <span class="fact-value">{dob_safe}</span></div>
            <div class="fact"><span class="fact-label">Age:</span> <span class="fact-value">{age_safe}</span></div>
            <div class="fact"><span class="fact-label">Sex:</span> <span class="fact-value">{sex_safe}</span></div>
            <div class="fact"><span class="fact-label">Contact:</span> <span class="fact-value">{contact_safe}</span></div>
            <div class="fact"><span class="fact-label">Eye Screened:</span> <span class="fact-value">{eye_safe}</span></div>
            <div class="fact"><span class="fact-label">Screening Date:</span> <span class="fact-value">{screening_date_safe}</span></div>
            <div class="fact"><span class="fact-label">Diabetes Type:</span> <span class="fact-value">{diabetes_type_safe}</span></div>
            <div class="fact"><span class="fact-label">Duration:</span> <span class="fact-value">{duration_safe}</span></div>
            <div class="fact"><span class="fact-label">HbA1c:</span> <span class="fact-value">{hba1c_safe}</span></div>
            <div class="fact"><span class="fact-label">Previous Treatment:</span> <span class="fact-value">{prev_tx_safe}</span></div>
        </div><div class="card">
            <h3 class="card-title">Screening Results</h3>
            <div class="fact"><span class="fact-label">Classification:</span> <span class="fact-value"><span class="result-pill">{result_safe}</span></span></div>
            <div class="fact"><span class="fact-label">Confidence:</span> <span class="fact-value">{confidence_safe}</span></div>
            <div class="fact"><span class="fact-label">Recommendation:</span> <span class="fact-value">{recommendation_safe}</span></div>
        </div>
    </div>

</div>

<div class="section">
    <h2 class="section-title">Image Results</h2>
    <table class="images">
  <tr>
        <td>{source_img_html}<div class="image-caption">Source Fundus Image</div></td>
        <td>{heatmap_img_html}<div class="image-caption">Grad-CAM++ Heatmap Overlay</div></td>
  </tr>
</table>

</div>

<div class="section">
    <h2 class="section-title">Clinical Analysis</h2>
    <div class="card" style="display:block; width:100%; margin-right:0;">
        <div class="fact"><span class="fact-label">Clinical Notes:</span> <span class="fact-value">{notes_compact_safe}</span></div>
    </div>
    <div class="analysis" style="margin-top: 6px;">{explanation_html}</div>
</div>

</div></body></html>"""

        doc.setHtml(html)

        writer = QPdfWriter(path)
        try:
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        except Exception:
            pass
        try:
            writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)
        except Exception:
            pass
        doc.print_(writer)

        QMessageBox.information(
            self, "Report Saved",
            f"Screening report saved to:\n{path}"
        )
