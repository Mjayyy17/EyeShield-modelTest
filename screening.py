"""
Screening module for EyeShield EMR application.
Handles patient screening functionality and image analysis.

This module has been refactored into separate sub-modules for better organization:
- screening_styles: Stylesheet constants and DR classification constants
- screening_worker: Background worker threads for inference
- screening_widgets: Custom widgets (DrawableZoomLabel, ImageZoomDialog, ClickableImageLabel)
- screening_results: ResultsWindow class for displaying screening results
- screening_form: ScreeningPage class for patient intake and screening workflow
"""

# Import and re-export the public classes for backward compatibility
from screening_form import ScreeningPage
from screening_results import ResultsWindow
from screening_widgets import (
    DrawableZoomLabel,
    ImageZoomDialog,
    ClickableImageLabel
)
from screening_worker import _InferenceWorker
from screening_styles import (
    DR_COLORS,
    DR_RECOMMENDATIONS,
    DR_SUMMARIES,
    SCREENING_PAGE_STYLE,
    LINEEDIT_STYLE,
    TEXTEDIT_STYLE,
    SPINBOX_STYLE,
    DOUBLESPINBOX_STYLE,
    READONLY_SPINBOX_STYLE,
    CHECKBOX_STYLE,
    CALENDAR_STYLE,
    PROGRESSBAR_STYLE
)

__all__ = [
    # Main classes
    "ScreeningPage",
    "ResultsWindow",
    # Widgets
    "DrawableZoomLabel",
    "ImageZoomDialog",
    "ClickableImageLabel",
    # Worker
    "_InferenceWorker",
    # Constants
    "DR_COLORS",
    "DR_RECOMMENDATIONS",
    "DR_SUMMARIES",
    "SCREENING_PAGE_STYLE",
    "LINEEDIT_STYLE",
    "TEXTEDIT_STYLE",
    "SPINBOX_STYLE",
    "DOUBLESPINBOX_STYLE",
    "READONLY_SPINBOX_STYLE",
    "CHECKBOX_STYLE",
    "CALENDAR_STYLE",
    "PROGRESSBAR_STYLE",
]
