"""
Stylesheet constants for the screening module.
Extracted to avoid duplication and improve maintainability.
"""

# ── Per-grade clinical constants ──────────────────────────────────────────────
DR_COLORS = {
    "No DR":              "#198754",
    "Mild DR":            "#b35a00",
    "Moderate DR":        "#c1540a",
    "Severe DR":          "#dc3545",
    "Proliferative DR":   "#842029",
}

DR_RECOMMENDATIONS = {
    "No DR":            "Annual screening recommended",
    "Mild DR":          "Repeat screening in 6–12 months",
    "Moderate DR":      "Ophthalmology referral within 3 months",
    "Severe DR":        "Urgent ophthalmology referral",
    "Proliferative DR": "Immediate ophthalmology referral",
}

DR_SUMMARIES = {
    "No DR": (
        "No signs of diabetic retinopathy were detected in this fundus image. "
        "Continue standard diabetes management, maintain optimal glycemic and blood pressure control, "
        "and schedule routine annual retinal screening."
    ),
    "Mild DR": (
        "Early microaneurysms consistent with mild non-proliferative diabetic retinopathy (NPDR) were identified. "
        "Intensify glycemic and blood pressure management. "
        "A repeat retinal examination in 6–12 months is recommended."
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

# ── Main page stylesheet ──────────────────────────────────────────────────────
# Note: Removed hard-coded colors to allow dark mode to work properly.
# The global theme (light or dark) will provide appropriate colors.
SCREENING_PAGE_STYLE = """
    QWidget {
        background: #f8f9fa;
        color: #212529;
        font-size: 13px;
        font-family: "Calibri", "Inter", "Arial";
    }
    QGroupBox {
        border: 1px solid #dee2e6;
        background: #ffffff;
        border-radius: 8px;
        margin-top: 8px;
        font-size: 16px;
        font-weight: 700;
        padding-top: 8px;
        color: #0d6efd;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        letter-spacing: 0.2px;
        color: #0d6efd;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
        border: 1px solid #ced4da;
        background: #ffffff;
        color: #212529;
        border-radius: 8px;
        padding: 2px 8px;
        min-height: 24px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
        border: 1px solid #0d6efd;
    }
    QPushButton {
        border: 1px solid #ced4da;
        background: #e9ecef;
        color: #212529;
        border-radius: 8px;
        padding: 6px 12px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #dee2e6;
    }
    QLabel#pageHeader {
        color: #007bff;
        font-size: 22px;
        font-weight: 700;
        margin: 5px 0 2px 0;
    }
    QLabel#pageSubtitle {
        color: #6c757d;
        font-size: 12px;
        margin-bottom: 8px;
    }
    QLabel#sectionTitle {
        font-size: 14px;
        font-weight: 700;
        margin-top: 10px;
    }
    QLabel#statusLabel {
        color: #6c757d;
        font-size: 11px;
        font-style: italic;
    }
    QLabel#surfaceLabel {
        color: #495057;
        font-size: 11px;
        border: 1px dashed #cfd8e3;
        background: #ffffff;
        border-radius: 8px;
    }
    QLabel#heatmapPlaceholder {
        color: #495057;
        font-size: 11px;
        border: 1px dashed #cfd8e3;
        background: #ffffff;
        border-radius: 8px;
    }
    QFrame#resultStatCard {
        border: 1px solid #dee2e6;
        background: #ffffff;
        border-radius: 8px;
    }
    QLabel#resultStatTitle {
        color: #6c757d;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    QLabel#resultStatValue {
        color: #212529;
        font-size: 17px;
        font-weight: 700;
    }
    QFrame#actionRail {
        border: 1px solid #dee2e6;
        background: #ffffff;
        border-radius: 8px;
        min-width: 220px;
        max-width: 240px;
    }
    QDateEdit {
        border: 1px solid #ced4da;
        background: #ffffff;
        color: #212529;
        border-radius: 8px;
        padding: 2px 8px;
        min-height: 24px;
    }
    QDateEdit::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 28px;
    }
    QDateEdit::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid #495057;
        width: 0;
        height: 0;
        margin-right: 6px;
    }

    QPushButton#primaryAction {
        background: #0d6efd;
        color: #ffffff;
        border: 1px solid #0b5ed7;
    }
    QPushButton#primaryAction:hover {
        background: #0b5ed7;
    }
    QPushButton#dangerAction {
        background: #ffffff;
        color: #dc3545;
        border: 1px solid #dc3545;
    }
    QPushButton#dangerAction:hover {
        background: #fff5f5;
    }
    QLabel#successLabel {
        color: #198754;
        background: #e9f7ef;
        border: 1px solid #b7ebc6;
        border-radius: 6px;
    }
    QLabel#errorLabel {
        color: #dc3545;
        background: #fdecec;
        border: 1px solid #f4c2c2;
        border-radius: 6px;
    }
"""

# ── Form input stylesheets ────────────────────────────────────────────────────
# Note: Removed hard-coded colors to allow dark mode to work properly
LINEEDIT_STYLE = """
    QLineEdit {
        border-radius: 6px;
        padding: 0 8px;
    }
"""

TEXTEDIT_STYLE = """
    QTextEdit {
        border-radius: 6px;
        padding: 6px 8px;
    }
"""

SPINBOX_STYLE = """
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
"""

DOUBLESPINBOX_STYLE = """
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
"""

READONLY_SPINBOX_STYLE = """
    QSpinBox {
        border-radius: 6px;
        padding: 0 8px;
    }
"""

CHECKBOX_STYLE = """
    QCheckBox {
        color: #212529;
        font-size: 13px;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 3px;
        border: 1px solid #6c757d;
        background: #ffffff;
    }
    QCheckBox::indicator:checked {
        background: #0d6efd;
        border: 1px solid #0b5ed7;
    }
"""

CALENDAR_STYLE = """
    QCalendarWidget QWidget#qt_calendar_navigationbar {
        background-color: transparent;
    }
    QCalendarWidget QToolButton {
        font-weight: bold;
    }
"""

PROGRESSBAR_STYLE = """
    QProgressBar {
        border: none;
        border-radius: 3px;
    }
    QProgressBar::chunk {
        border-radius: 3px;
    }
"""
