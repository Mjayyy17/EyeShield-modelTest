"""
Screening form page for EyeShield EMR application.
Extracted from screening.py for better modularity.
"""

from datetime import datetime
from html import escape
import hashlib
import os
import re
import secrets
import shutil
import sqlite3

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QFileDialog, QFormLayout, QGroupBox, QComboBox, QDateEdit, QMessageBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit, QCalendarWidget, QStackedWidget,
    QGridLayout, QFrame, QSizePolicy, QScrollArea, QSplitter
)
from PySide6.QtGui import QPixmap, QFont, QRegularExpressionValidator, QIcon, QPainter, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, QDate, QRegularExpression, QSize, Signal

from screening_styles import (
    SCREENING_PAGE_STYLE,
    LINEEDIT_STYLE,
    TEXTEDIT_STYLE,
    SPINBOX_STYLE,
    DOUBLESPINBOX_STYLE,
    READONLY_SPINBOX_STYLE,
    CHECKBOX_STYLE,
    CALENDAR_STYLE
)
from screening_worker import _InferenceWorker
from screening_widgets import ClickableImageLabel
from screening_results import ResultsWindow
from logic_improvements import (
    ScreeningFlowGuard,
    DuplicateDetector,
)
from auth import DB_FILE


class SymptomTag(QPushButton):
    """Toggleable pill tag used by the redesigned symptoms section."""

    _OFF = (
        "QPushButton {"
        "  background:#ffffff; color:#1f4f77;"
        "  border:1.5px solid transparent; border-radius:999px;"
        "  padding:5px 14px; font-size:12px; font-weight:500;"
        "}"
        "QPushButton:hover { border-color:#3f7ca7; }"
    )
    _ON = (
        "QPushButton {"
        "  background:#3f7ca7; color:#ffffff;"
        "  border:1.5px solid #3f7ca7; border-radius:999px;"
        "  padding:5px 14px; font-size:12px; font-weight:500;"
        "}"
    )

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setStyleSheet(self._OFF)
        self.toggled.connect(lambda on: self.setStyleSheet(self._ON if on else self._OFF))


class DropZoneLabel(QLabel):
    """Dashed image drop zone that emits file path on valid image drop."""

    file_dropped = Signal(str)

    _IDLE = (
        "QLabel { border:2px dashed #c6d2df; border-radius:10px;"
        " background:#ffffff; color:#3f7ca7;"
        " font-size:13px; font-weight:500; }"
    )
    _HOVER = (
        "QLabel { border:2px dashed #3f7ca7; border-radius:10px;"
        " background:#f8fbff; color:#3f7ca7;"
        " font-size:13px; font-weight:500; }"
    )
    _LOADED = (
        "QLabel { border:2px solid #3f7ca7; border-radius:10px;"
        " background:#000000; }"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pixmap_full = QPixmap()
        self._reset_placeholder()

    def set_image(self, path: str):
        px = QPixmap(path)
        if px.isNull():
            return
        self._pixmap_full = px
        self.setStyleSheet(self._LOADED)
        self.setText("")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh()

    def clear_image(self):
        self._pixmap_full = QPixmap()
        self._reset_placeholder()

    def has_image(self) -> bool:
        return not self._pixmap_full.isNull()

    def _reset_placeholder(self):
        self.setStyleSheet(self._IDLE)
        self.setPixmap(QPixmap())
        self.setText(
            "Drop fundus image here or click to browse\n\n"
            "Supports JPG, PNG, JPEG"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _refresh(self):
        if self._pixmap_full.isNull():
            return
        scaled = self._pixmap_full.scaled(
            max(1, self.width() - 4),
            max(1, self.height() - 4),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._pixmap_full.isNull():
            self._refresh()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._HOVER)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._LOADED if self.has_image() else self._IDLE)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith((".jpg", ".jpeg", ".png")):
                self.file_dropped.emit(path)
        self.setStyleSheet(self._LOADED if self.has_image() else self._IDLE)


_REDESIGN_STYLESHEET = """
QWidget { background:#ffffff; color:#1f2937; font-family:"Segoe UI","Inter","Calibri",sans-serif; font-size:13px; }
QFrame#card { background:#ffffff; border:1px solid #dde3ea; border-radius:14px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    background:#ffffff; border:1.5px solid #d3dae3; border-radius:6px; padding:6px 10px;
    color:#1f2937; min-height:28px; selection-background-color:#3f7ca7;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border:1.5px solid #3f7ca7; background:#ffffff;
}
QLineEdit:read-only { background:#f6f8fb; color:#475569; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width:24px;
    border-left:1px solid #d3dae3;
    background:#f6f8fb;
    border-top-right-radius:6px;
    border-bottom-right-radius:6px;
}
QComboBox::down-arrow { width:10px; height:10px; }
QComboBox#sexDropdown, QComboBox#eyeDropdown, QComboBox#diabetesTypeDropdown {
    padding-right: 34px;
}
QComboBox#sexDropdown::drop-down, QComboBox#eyeDropdown::drop-down, QComboBox#diabetesTypeDropdown::drop-down {
    width: 28px;
    border-left: 1px solid #9fb4cc;
    background: #e8f1ff;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox#sexDropdown::down-arrow, QComboBox#eyeDropdown::down-arrow, QComboBox#diabetesTypeDropdown::down-arrow {
    width: 12px;
    height: 12px;
    margin-right: 6px;
}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:18px; border:none; background:transparent; }
QScrollArea { border:none; background:transparent; }
QScrollBar:vertical { background:#f2f5f8; width:6px; border-radius:3px; }
QScrollBar::handle:vertical { background:#c2ccd8; border-radius:3px; min-height:20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QSplitter::handle { background:#e7ecf1; width:1px; }
QPushButton#btnPrimary { background:#007bff; color:#ffffff; border:1px solid #0066d4; border-radius:6px; padding:8px 16px; font-weight:700; font-size:13px; }
QPushButton#btnPrimary:hover { background:#006ee6; }
QPushButton#btnDanger { background:#fef2f2; color:#ef4444; border:1.5px solid #fecaca; border-radius:6px; padding:8px 16px; font-weight:600; font-size:13px; }
QPushButton#btnDanger:hover { background:#fee2e2; }
QPushButton#btnAnalyze {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0066ff,stop:0.6 #007bff,stop:1 #2a9dff);
    color:#ffffff; border:1px solid #005bd9; border-radius:6px; padding:11px 16px; font-weight:800; font-size:14px;
}
QPushButton#btnAnalyze:hover {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #005ce6,stop:1 #0077f0);
}
QCheckBox { color:#475569; spacing:8px; font-size:12px; }
QCheckBox::indicator { width:16px; height:16px; border:1.5px solid #94a3b8; border-radius:3px; background:#ffffff; }
QCheckBox::indicator:checked { background:#3f7ca7; border-color:#3f7ca7; }
"""


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
        self._flow_guard = ScreeningFlowGuard(self)
        self._duplicate_detector = DuplicateDetector()
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

    def _resolve_icon_path(self, *filenames: str) -> str:
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        for name in filenames:
            path = os.path.join(icon_dir, name)
            if os.path.isfile(path):
                return path
        return ""

    def _tinted_icon(self, icon_path: str, color_hex: str, size: int = 20) -> QIcon:
        if not icon_path:
            return QIcon()

        source = QIcon(icon_path).pixmap(QSize(size, size))
        if source.isNull():
            return QIcon(icon_path)

        tinted = QPixmap(source.size())
        tinted.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color_hex))
        painter.end()

        return QIcon(tinted)

    def _apply_ui_polish(self):
        self.setStyleSheet(_REDESIGN_STYLESHEET)

    def _apply_visible_dropdown_style(self, combo: QComboBox):
        arrow_icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "icons",
            "dropdown_arrow.svg",
        ).replace("\\", "/")
        combo.setStyleSheet(
            f"""
            QComboBox {{
                background:#ffffff;
                border:1.5px solid #c5d2e0;
                border-radius:6px;
                padding:6px 34px 6px 10px;
                color:#1f2937;
                min-height:28px;
            }}
            QComboBox:focus {{
                border:1.5px solid #3f7ca7;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width:28px;
                border-left:1px solid #9fb4cc;
                background:#e8f1ff;
                border-top-right-radius:6px;
                border-bottom-right-radius:6px;
            }}
            QComboBox::down-arrow {{
                image: url(\"{arrow_icon_path}\");
                width:12px;
                height:8px;
            }}
            """
        )

    def create_unified_page(self):
        root = QWidget()
        root.setStyleSheet(_REDESIGN_STYLESHEET)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        root_layout.addWidget(splitter)

        def make_card():
            frame = QFrame()
            frame.setObjectName("card")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(24, 20, 24, 22)
            layout.setSpacing(14)
            return frame, layout

        def section_title(layout, text):
            row = QHBoxLayout()
            row.setSpacing(8)
            title = QLabel(text.upper())
            title.setStyleSheet(
                "font-size:10px;font-weight:700;letter-spacing:1.4px;"
                "color:#3f7ca7;background:transparent;"
            )
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("background:#dde3ea;max-height:1px;")
            row.addWidget(title)
            row.addWidget(line, 1)
            layout.addLayout(row)

        def lbl(text):
            w = QLabel(text)
            w.setStyleSheet("font-size:11px;font-weight:500;color:#475569;background:transparent;")
            return w

        def field(label_text, widget):
            v = QVBoxLayout()
            v.setSpacing(5)
            v.addWidget(lbl(label_text))
            v.addWidget(widget)
            return v

        def row2(*fields):
            h = QHBoxLayout()
            h.setSpacing(14)
            for f in fields:
                h.addLayout(f, 1)
            return h

        def row3(*fields):
            h = QHBoxLayout()
            h.setSpacing(10)
            for f in fields:
                h.addLayout(f, 1)
            return h

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_content = QWidget()
        left_content.setStyleSheet("background:transparent;")
        left_col = QVBoxLayout(left_content)
        left_col.setContentsMargins(0, 0, 8, 0)
        left_col.setSpacing(14)
        left_scroll.setWidget(left_content)

        card1, c1 = make_card()
        section_title(c1, "Patient Information")

        self.p_id = QLineEdit()
        self.p_id.setReadOnly(True)
        self.p_id.setStyleSheet(
            "QLineEdit{background:#f6f8fb;color:#3f7ca7;border:1px solid #d3dae3;"
            "border-radius:999px;padding:4px 14px;font-family:monospace;font-size:12px;font-weight:600;}"
        )
        self.generate_patient_id()
        pid_row = QHBoxLayout()
        pid_row.setSpacing(10)
        pid_row.addWidget(lbl("Patient ID"))
        pid_row.addWidget(self.p_id, 1)
        c1.addLayout(pid_row)

        self.p_name = QLineEdit()
        self.p_name.setPlaceholderText("Full name")
        self.p_dob = QLineEdit()
        self.p_dob.setPlaceholderText("dd/mm/yyyy")
        self.p_dob.setMaxLength(10)
        self._dob_default_style = ""
        self._dob_invalid_style = "QLineEdit{border:1.5px solid #ef4444;border-radius:6px;}"
        self.p_dob.textChanged.connect(self._on_dob_text_changed)
        c1.addLayout(row2(field("Full Name", self.p_name), field("Date of Birth", self.p_dob)))

        self.p_age = QSpinBox()
        self.p_age.setRange(0, 120)
        self.p_age.setSuffix(" yrs")
        self.p_age.setReadOnly(True)
        self.p_age.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.p_age.setSpecialValueText(" ")

        self.p_sex = QComboBox()
        self.p_sex.setObjectName("sexDropdown")
        self.p_sex.addItems(["", "Male", "Female", "Prefer not to say"])
        self._apply_visible_dropdown_style(self.p_sex)
        self.p_eye = QComboBox()
        self.p_eye.setObjectName("eyeDropdown")
        self.p_eye.addItems(["", "Right Eye", "Left Eye"])
        self._apply_visible_dropdown_style(self.p_eye)
        c1.addLayout(row3(field("Age", self.p_age), field("Sex", self.p_sex), field("Eye to be Screened", self.p_eye)))

        self.p_contact = QLineEdit()
        self.p_contact.setPlaceholderText("Phone or Email")
        c1.addLayout(field("Contact", self.p_contact))

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#dde3ea;max-height:1px;margin-top:4px;")
        c1.addWidget(sep)
        section_title(c1, "Vital Signs & Symptoms")

        self.va_left = QLineEdit()
        self.va_left.setPlaceholderText("e.g. 20/20")
        self.va_right = QLineEdit()
        self.va_right.setPlaceholderText("e.g. 20/20")
        c1.addLayout(row2(field("Visual Acuity — Left", self.va_left), field("Visual Acuity — Right", self.va_right)))

        self.bp_systolic = QSpinBox()
        self.bp_systolic.setRange(0, 300)
        self.bp_systolic.setSpecialValueText(" ")
        self.bp_diastolic = QSpinBox()
        self.bp_diastolic.setRange(0, 200)
        self.bp_diastolic.setSpecialValueText(" ")
        bp_w = QWidget()
        bp_w.setStyleSheet("background:transparent;")
        bp_h = QHBoxLayout(bp_w)
        bp_h.setContentsMargins(0, 0, 0, 0)
        bp_h.setSpacing(6)
        _sl = QLabel("/")
        _sl.setStyleSheet("color:#94a3b8;background:transparent;font-size:14px;")
        _ul = QLabel("mmHg")
        _ul.setStyleSheet("color:#94a3b8;font-size:11px;background:transparent;")
        bp_h.addWidget(self.bp_systolic, 1)
        bp_h.addWidget(_sl)
        bp_h.addWidget(self.bp_diastolic, 1)
        bp_h.addWidget(_ul)

        self.fbs = QSpinBox()
        self.fbs.setRange(0, 600)
        self.fbs.setSpecialValueText(" ")
        self.rbs = QSpinBox()
        self.rbs.setRange(0, 800)
        self.rbs.setSpecialValueText(" ")
        bg_w = QWidget()
        bg_w.setStyleSheet("background:transparent;")
        bg_h = QHBoxLayout(bg_w)
        bg_h.setContentsMargins(0, 0, 0, 0)
        bg_h.setSpacing(6)
        _fl = QLabel("FBS")
        _fl.setStyleSheet("font-size:11px;color:#475569;background:transparent;")
        _rl = QLabel("RBS")
        _rl.setStyleSheet("font-size:11px;color:#475569;background:transparent;")
        bg_h.addWidget(_fl)
        bg_h.addWidget(self.fbs, 1)
        bg_h.addWidget(_rl)
        bg_h.addWidget(self.rbs, 1)
        c1.addLayout(row2(field("Blood Pressure", bp_w), field("Blood Glucose", bg_w)))

        c1.addWidget(lbl("Symptoms"))
        tags_h = QHBoxLayout()
        tags_h.setSpacing(8)
        tags_h.setContentsMargins(0, 0, 0, 0)
        self.symptom_blurred = SymptomTag("Blurred vision")
        self.symptom_floaters = SymptomTag("Floaters")
        self.symptom_flashes = SymptomTag("Flashes")
        self.symptom_vision_loss = SymptomTag("Vision loss")
        for t in (self.symptom_blurred, self.symptom_floaters, self.symptom_flashes, self.symptom_vision_loss):
            tags_h.addWidget(t)
        self.symptom_other = QLineEdit()
        self.symptom_other.setPlaceholderText("Other…")
        self.symptom_other.setStyleSheet(
            "QLineEdit{background:#ffffff;border:1.5px solid #d3dae3;border-radius:999px;padding:4px 12px;"
            "font-size:12px;min-height:0;max-width:110px;}QLineEdit:focus{border-color:#3f7ca7;background:#fff;}"
        )
        tags_h.addWidget(self.symptom_other)
        tags_h.addStretch()
        c1.addLayout(tags_h)
        left_col.addWidget(card1)

        card2, c2 = make_card()
        section_title(c2, "Clinical History")
        self.diabetes_type = QComboBox()
        self.diabetes_type.setObjectName("diabetesTypeDropdown")
        self.diabetes_type.addItems(["Select", "Type 1", "Type 2", "Gestational", "Other"])
        self._apply_visible_dropdown_style(self.diabetes_type)
        self.diabetes_diagnosis_date = QLineEdit()
        self.diabetes_diagnosis_date.setPlaceholderText("dd/mm/yyyy")
        self.diabetes_diagnosis_date.setMaxLength(10)
        self.diabetes_diagnosis_date.textChanged.connect(self._on_diagnosis_date_changed)
        c2.addLayout(row2(field("Diabetes Type", self.diabetes_type), field("Diagnosis Date", self.diabetes_diagnosis_date)))

        self.diabetes_duration = QSpinBox()
        self.diabetes_duration.setSuffix(" years")
        self.diabetes_duration.setRange(0, 80)
        self.diabetes_duration.setReadOnly(True)
        self.diabetes_duration.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.diabetes_duration.setStyleSheet(
            "QSpinBox{background:#f6f8fb;color:#475569;border:1.5px solid #d3dae3;border-radius:6px;padding:6px 10px;}"
        )
        self.hba1c = QDoubleSpinBox()
        self.hba1c.setRange(4.0, 15.0)
        self.hba1c.setDecimals(1)
        self.hba1c.setSuffix(" %")
        self.hba1c.setValue(7.0)
        c2.addLayout(row2(field("Duration", self.diabetes_duration), field("HbA1c (%)", self.hba1c)))

        self.prev_treatment = QCheckBox("Previous DR Treatment")
        c2.addWidget(self.prev_treatment)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Enter clinical notes…")
        self.notes.setMinimumHeight(72)
        self.notes.setMaximumHeight(90)
        c2.addLayout(field("Clinical Notes", self.notes))
        left_col.addWidget(card2)
        left_col.addStretch()
        splitter.addWidget(left_scroll)

        card3 = QFrame()
        card3.setObjectName("card")
        card3.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(24, 20, 24, 22)
        c3.setSpacing(12)
        section_title(c3, "Fundus Image Upload")

        self.image_label = DropZoneLabel()
        self.image_label.file_dropped.connect(self._on_image_dropped)

        def _dz_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.upload_image()

        self.image_label.mousePressEvent = _dz_click
        c3.addWidget(self.image_label, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_upload = QPushButton("Upload Image")
        self.btn_upload.setObjectName("btnPrimary")
        self.btn_upload.setMinimumHeight(36)
        self.btn_upload.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        upload_icon = self._resolve_icon_path("upload.svg", "camera.svg")
        if upload_icon:
            self.btn_upload.setIcon(self._tinted_icon(upload_icon, "#ffffff", 18))
            self.btn_upload.setIconSize(QSize(18, 18))
        self.btn_upload.clicked.connect(self.upload_image)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("btnDanger")
        self.btn_clear.setMinimumHeight(36)
        self.btn_clear.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        clear_icon = self._resolve_icon_path("discard.svg")
        if clear_icon:
            self.btn_clear.setIcon(self._tinted_icon(clear_icon, "#ef4444", 18))
            self.btn_clear.setIconSize(QSize(18, 18))
        self.btn_clear.clicked.connect(self.clear_image)
        btn_row.addWidget(self.btn_upload)
        btn_row.addWidget(self.btn_clear)
        c3.addLayout(btn_row)

        self.btn_analyze = QPushButton("Analyze Image")
        self.btn_analyze.setObjectName("btnAnalyze")
        self.btn_analyze.setMinimumHeight(42)
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self.open_results_window)
        c3.addWidget(self.btn_analyze)

        splitter.addWidget(card3)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([640, 520])
        handle = splitter.handle(1)
        handle.setDisabled(True)
        handle.setCursor(Qt.CursorShape.ArrowCursor)
        self._set_tab_order_unified()
        return root

    def _apply_upload_placeholder_style(self):
        if hasattr(self, "image_label") and hasattr(self.image_label, "clear_image"):
            self.image_label.clear_image()
            return
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Upload a fundus image\nJPG, PNG, JPEG")
        self.image_label.setStyleSheet(
            f"""
            QLabel {{
                border: 2px dashed #9ec5fe;
                border-radius: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f8fbff, stop:1 #eef5ff);
                color: #0b5ed7;
                padding: 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            """
        )

    def _apply_upload_loaded_style(self):
        if hasattr(self, "image_label") and hasattr(self.image_label, "set_image"):
            return
        self.image_label.setStyleSheet(
            f"""
            QLabel {{
                border: 1px solid #cfe2ff;
                border-radius: 12px;
                background: #ffffff;
                padding: 8px;
            }}
            """
        )

    def _form_label_stylesheet(self):
        return (
            "color: #212529;"
            "background: transparent; border: none;"
            "font-size: 13px; font-weight: 600;"
        )

    def _apply_flat_form_label_style(self, form_layout: QFormLayout):
        for row in range(form_layout.rowCount()):
            item = form_layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setStyleSheet(self._form_label_stylesheet())

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
        self.setTabOrder(self.symptom_vision_loss, self.symptom_other)
        self.setTabOrder(self.symptom_other, self.btn_upload)
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
                border: 1.5px solid #dc3545;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """
        self.diabetes_diagnosis_date.setStyleSheet(invalid_style if has_invalid_value else LINEEDIT_STYLE)

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
        custom_calendar.setStyleSheet(CALENDAR_STYLE)
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
        self.prev_treatment.setStyleSheet(CHECKBOX_STYLE)
        clinical_form.addRow("", self.prev_treatment)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Enter clinical notes")
        self.notes.setStyleSheet(TEXTEDIT_STYLE)
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
        self.summary_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(self.summary_label)

        image_group = QGroupBox("Fundus Image")
        image_layout = QVBoxLayout()

        self.image_label = QLabel("No image loaded")
        self.image_label.setMinimumSize(450, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed currentColor;")
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
        self.symptom_blurred.setChecked(False)
        self.symptom_floaters.setChecked(False)
        self.symptom_flashes.setChecked(False)
        self.symptom_vision_loss.setChecked(False)
        self.symptom_other.clear()
        self.notes.clear()
        self.current_image = None
        self._apply_upload_placeholder_style()
        self.last_result_class = "Pending"
        self.last_result_conf = "Pending"
        self._current_eye_saved = False
        self._first_eye_result = None
        self._flow_guard.reset()
        self.btn_analyze.setEnabled(False)
        self.stacked_widget.setCurrentIndex(0)

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Fundus Image", "", "Image Files (*.jpg *.jpeg *.png)"
        )
        if path:
            self.current_image = path
            if hasattr(self.image_label, "set_image"):
                self.image_label.set_image(path)
            else:
                self._set_preview_image(path)
            self.btn_analyze.setEnabled(True)

    def _on_image_dropped(self, path: str):
        self.current_image = path
        if hasattr(self.image_label, "set_image"):
            self.image_label.set_image(path)
        else:
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
        if hasattr(self.image_label, "set_image"):
            self.image_label.set_image(path)
            return
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

        ok, message = self._flow_guard.validate()
        if not ok:
            QMessageBox.warning(self, "Incomplete Form", message)
            return

        self._resolve_duplicate_patient()

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

    def _resolve_duplicate_patient(self):
        match = self._duplicate_detector.find_duplicate(
            name=self.p_name.text().strip(),
            dob=self.p_dob.text().strip(),
            contact=self.p_contact.text().strip(),
        )
        if not match or not match.get("patient_id"):
            return

        matched_id = str(match["patient_id"]).strip()
        if not matched_id:
            return

        current_id = self.p_id.text().strip()
        if current_id != matched_id:
            self.p_id.setText(matched_id)

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
        if eye_label:
            self._flow_guard.mark_eye_done(eye_label)
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
        symptom_other = self.symptom_other.text().strip()
        if symptom_other:
            symptoms.append(f"Other: {symptom_other}")

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
        if hasattr(self.image_label, "clear_image"):
            self.image_label.clear_image()
        else:
            self._apply_upload_placeholder_style()
        self.btn_analyze.setEnabled(False)

    def _persist_screening_assets(self, patient_id: str, eye_label: str) -> tuple[str, str, str, str]:
        """Copy source/heatmap images into app-managed storage and return DB-ready metadata."""
        source_path = str(getattr(self, "current_image", "") or "").strip()
        heatmap_path = str(getattr(self.results_page, "_current_heatmap_path", "") or "").strip()

        if not source_path or not os.path.isfile(source_path):
            raise FileNotFoundError("Source fundus image is missing and cannot be saved.")

        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stored_images", patient_id)
        os.makedirs(base_dir, exist_ok=True)

        eye_tag = re.sub(r"[^a-z0-9]+", "_", eye_label.lower()).strip("_") or "eye"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        src_ext = os.path.splitext(source_path)[1].lower() or ".jpg"
        dst_source = os.path.join(base_dir, f"{stamp}_{eye_tag}_source{src_ext}")
        shutil.copy2(source_path, dst_source)

        dst_heatmap = ""
        if heatmap_path and os.path.isfile(heatmap_path):
            h_ext = os.path.splitext(heatmap_path)[1].lower() or ".png"
            dst_heatmap = os.path.join(base_dir, f"{stamp}_{eye_tag}_heatmap{h_ext}")
            shutil.copy2(heatmap_path, dst_heatmap)

        hasher = hashlib.sha256()
        with open(dst_source, "rb") as src_file:
            for chunk in iter(lambda: src_file.read(1024 * 1024), b""):
                hasher.update(chunk)

        app_root = os.path.dirname(os.path.abspath(__file__))
        rel_source = os.path.relpath(dst_source, app_root).replace("\\", "/")
        rel_heatmap = os.path.relpath(dst_heatmap, app_root).replace("\\", "/") if dst_heatmap else ""
        image_sha256 = hasher.hexdigest()
        image_saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return rel_source, rel_heatmap, image_sha256, image_saved_at

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
        if not pid:
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
        symptom_other = self.symptom_other.text().strip()
        if symptom_other:
            notes = (notes + f"\nOther symptom: {symptom_other}").strip() if notes else f"Other symptom: {symptom_other}"

        try:
            source_image_path, heatmap_image_path, image_sha256, image_saved_at = self._persist_screening_assets(
                pid,
                eye,
            )
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Save Failed", f"Unable to store screening images:\n\n{exc}")
            return

        screened_at = datetime.now().strftime("%Y-%m-%d")

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
            screened_at,
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
            source_image_path,
            heatmap_image_path,
            image_sha256,
            image_saved_at,
        ]

        if not self._save_screening_to_db(patient_data):
            QMessageBox.warning(self, "Save Failed", "Unable to save screening record. Please try again.")
            return

        self._current_eye_saved = True
        if reset_after:
            self.reset_screening()
        else:
            eye_label = eye or "eye"
            # Store first eye result with image/heatmap paths for dual-eye reports
            self._first_eye_result = {
                "eye": eye_label,
                "result": self.last_result_class,
                "confidence": self.last_result_conf,
                "image_path": getattr(self, 'current_image', '') or '',
                "heatmap_path": getattr(self.results_page, '_current_heatmap_path', '') or '',
            }
            self.results_page.mark_saved(self.p_name.text().strip(), eye_label, self.last_result_class)

            # Auto-prompt to screen the other eye (only if first eye, not second)
            if not self._first_eye_result.get('_is_second_eye'):
                opposite_eye = "Left Eye" if eye_label == "Right Eye" else "Right Eye"
                box = QMessageBox(self)
                box.setWindowTitle("Screen Other Eye")
                box.setIcon(QMessageBox.Icon.Question)
                box.setText(
                    f"<b>{eye_label}</b> screening saved successfully.\n\n"
                    f"Would you like to screen the <b>{opposite_eye}</b> now?"
                )
                continue_btn = box.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
                box.addButton("Finish", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() == continue_btn:
                    self.screen_other_eye()

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

        # Capture current patient demographics and patient_id before resetting
        saved_pid = self.p_id.text().strip()
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

        # Capture vitals
        va_l = self.va_left.text()
        va_r = self.va_right.text()
        bp_s = self.bp_systolic.value()
        bp_d = self.bp_diastolic.value()
        fbs_v = self.fbs.value()
        rbs_v = self.rbs.value()
        diag_date_text = self.diabetes_diagnosis_date.text() if hasattr(self, 'diabetes_diagnosis_date') else ""
        sym_blurred = self.symptom_blurred.isChecked()
        sym_floaters = self.symptom_floaters.isChecked()
        sym_flashes = self.symptom_flashes.isChecked()
        sym_vision_loss = self.symptom_vision_loss.isChecked()
        sym_other = self.symptom_other.text()

        # Preserve first eye result across reset so results page can show bilateral comparison
        saved_first_eye_result = self._first_eye_result

        # Full reset (generates new patient ID, clears everything)
        self.reset_screening()

        # Restore first eye result and mark second eye
        self._first_eye_result = saved_first_eye_result
        if self._first_eye_result:
            self._first_eye_result['_is_second_eye'] = True

        # Restore the same patient_id so both eyes share one ID
        self.p_id.setText(saved_pid)

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

        # Restore vitals
        self.va_left.setText(va_l)
        self.va_right.setText(va_r)
        self.bp_systolic.setValue(bp_s)
        self.bp_diastolic.setValue(bp_d)
        self.fbs.setValue(fbs_v)
        self.rbs.setValue(rbs_v)
        if hasattr(self, 'diabetes_diagnosis_date'):
            self.diabetes_diagnosis_date.setText(diag_date_text)
        self.symptom_blurred.setChecked(sym_blurred)
        self.symptom_floaters.setChecked(sym_floaters)
        self.symptom_flashes.setChecked(sym_flashes)
        self.symptom_vision_loss.setChecked(sym_vision_loss)
        self.symptom_other.setText(sym_other)

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
                    result, confidence, screened_at,
                    visual_acuity_left, visual_acuity_right,
                    blood_pressure_systolic, blood_pressure_diastolic,
                    fasting_blood_sugar, random_blood_sugar,
                    diabetes_diagnosis_date,
                    symptom_blurred_vision, symptom_floaters,
                    symptom_flashes, symptom_vision_loss,
                    source_image_path, heatmap_image_path,
                    image_sha256, image_saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                item.widget().setStyleSheet(self._form_label_stylesheet())
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
                item.widget().setStyleSheet(self._form_label_stylesheet())

