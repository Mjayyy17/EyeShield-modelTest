"""
Users management module for EyeShield EMR application.
Provides a GUI for creating, listing, updating and deleting users.
"""

import re
import json
import csv
import os
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QPushButton, QLineEdit, QComboBox, QMessageBox,
    QGroupBox, QFormLayout, QAbstractItemView, QDialog, QApplication,
    QHeaderView, QInputDialog, QMenu, QCheckBox, QTimeEdit,
    QFileDialog, QDateEdit, QGridLayout, QCalendarWidget, QSpinBox,
    QSizePolicy, QFrame
)
from PySide6.QtGui import QFont, QAction, QIcon, QColor
from PySide6.QtCore import Qt, QTime, QDate, QTimer
import user_store


# â”€â”€ Role badge colours â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_ROLE_COLORS = {
    "admin":     ("#c0392b", "#fdf2f2"),
    "clinician": ("#0d6efd", "#eef3ff"),
    "viewer":    ("#6c757d", "#f3f4f6"),
}

_ROLE_COLORS_DARK = {
    "admin":     ("#f38ba8", "#3d1f2d"),
    "clinician": ("#89b4fa", "#1f2f4f"),
    "viewer":    ("#bac2de", "#2f3348"),
}

_SPECIALIZATION_OPTIONS = ["Optometrist", "Ophthalmologist"]
_WEEKDAY_OPTIONS = [
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
    ("sat", "Saturday"),
    ("sun", "Sunday"),
]
_WEEKDAY_LABELS = {key: label for key, label in _WEEKDAY_OPTIONS}

# â”€â”€ Shared dialog stylesheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_DIALOG_STYLE = """
    QDialog { background: #ffffff; }
    QLabel  { font-size: 13px; color: #212529; background: transparent; border: none; }
    QLabel#dlgTitle { font-size: 16px; font-weight: 700; color: #212529; margin-bottom: 2px; }
    QLabel#dlgHint  { font-size: 11px; color: #6c757d; }
    QCheckBox {
        font-size: 13px;
        color: #212529;
        spacing: 8px;
        padding: 3px 0;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #adb5bd;
        border-radius: 4px;
        background: #ffffff;
    }
    QCheckBox::indicator:checked {
        border-color: #0d6efd;
        background: #0d6efd;
    }
    QLineEdit, QComboBox {
        background: #f8f9fa;
        border: 1px solid #ced4da;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1.5px solid #0d6efd;
        background: #ffffff;
    }
    QPushButton {
        border-radius: 8px; padding: 8px 20px;
        font-size: 13px; font-weight: 600; border: none; min-width: 90px;
    }
    QPushButton#okBtn     { background: #0d6efd; color: white; }
    QPushButton#okBtn:hover { background: #0b5ed7; }
    QPushButton#cancelBtn { background: #e9ecef; color: #495057; border: 1px solid #ced4da; }
    QPushButton#cancelBtn:hover { background: #dee2e6; }
"""


class ModernCalendarDateEdit(QDateEdit):
    """Date picker styled to match screening DOB calendar behavior."""

    def __init__(self, min_date: QDate, max_date: QDate, default_date: QDate | None = None, parent=None):
        super().__init__(parent)
        self._min_date = min_date
        self._max_date = max_date

        self.setDisplayFormat("yyyy-MM-dd")
        self.setCalendarPopup(True)
        self.setMinimumDate(min_date)
        self.setMaximumDate(max_date)
        self.setDate(default_date or max_date)

        cal = QCalendarWidget(self)
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setMinimumSize(410, 320)
        cal.currentPageChanged.connect(self._sync_year_dropdown)
        self.setCalendarWidget(cal)

        self.setStyleSheet(
            """
            QDateEdit {
                background: #ffffff;
                color: #1f2933;
                border: 1px solid #ced4da;
                border-radius: 8px;
                padding: 4px 28px 4px 10px;
                min-height: 24px;
            }
            QDateEdit:focus {
                border: 1.5px solid #0d6efd;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #dbe2ea;
                background: #f8f9fa;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
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
            """
        )

        cal.setStyleSheet(
            """
            QCalendarWidget {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 10px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background: #f7f9fc;
                border-bottom: 1px solid #dce5ef;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 4px 6px;
            }
            QCalendarWidget QToolButton {
                color: #1f2933;
                background: transparent;
                border: none;
                border-radius: 5px;
                font-size: 13px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QCalendarWidget QToolButton:hover {
                background: #eef3f8;
            }
            QCalendarWidget QToolButton::menu-indicator {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6c757d;
                width: 0;
                height: 0;
                right: 5px;
            }
            QCalendarWidget QComboBox#qt_calendar_yearcombo {
                background: #ffffff;
                color: #1f2933;
                border: 1px solid #d7dde6;
                border-radius: 5px;
                padding: 2px 20px 2px 8px;
                min-width: 76px;
            }
            QCalendarWidget QComboBox#qt_calendar_yearcombo::drop-down {
                border: none;
                width: 18px;
            }
            QCalendarWidget QComboBox#qt_calendar_yearcombo::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6c757d;
                width: 0;
                height: 0;
                margin-right: 6px;
            }
            QCalendarWidget QComboBox#qt_calendar_yearcombo QAbstractItemView {
                background: #ffffff;
                color: #1f2933;
                border: 1px solid #dce5ef;
                selection-background-color: #dbe5f0;
                selection-color: #1f2933;
            }
            QCalendarWidget QAbstractItemView {
                background: #ffffff;
                color: #1f2933;
                selection-background-color: #dbe5f0;
                selection-color: #1f2933;
                outline: none;
                gridline-color: transparent;
            }
            QCalendarWidget QTableView::item {
                border: none;
                border-radius: 5px;
                padding: 3px;
                margin: 1px;
            }
            QCalendarWidget QTableView::item:hover {
                background: #eef3f8;
            }
            QCalendarWidget QTableView::item:selected {
                background: #dbe5f0;
                color: #1f2933;
            }
            QCalendarWidget QTableView::item:today {
                background: #eef3f8;
                color: #1f2933;
                font-weight: 600;
            }
            """
        )

        QTimer.singleShot(0, self._setup_year_dropdown)

    def _setup_year_dropdown(self):
        cal = self.calendarWidget()
        if not cal:
            return

        nav = cal.findChild(QWidget, "qt_calendar_navigationbar")
        if not nav:
            QTimer.singleShot(0, self._setup_year_dropdown)
            return

        year_spin = nav.findChild(QSpinBox, "qt_calendar_yearedit")
        if not year_spin:
            return

        year_combo = nav.findChild(QComboBox, "qt_calendar_yearcombo")
        if year_combo is None:
            year_combo = QComboBox(nav)
            year_combo.setObjectName("qt_calendar_yearcombo")
            year_combo.setMinimumWidth(92)
            year_combo.setMaxVisibleItems(12)
            year_combo.setEditable(False)
            year_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

            for year in range(self._min_date.year(), self._max_date.year() + 1):
                year_combo.addItem(str(year), year)

            year_combo.currentIndexChanged.connect(self._on_year_dropdown_changed)

            nav_layout = nav.layout()
            if nav_layout is not None:
                idx = nav_layout.indexOf(year_spin)
                if idx >= 0:
                    nav_layout.insertWidget(idx, year_combo)
                else:
                    nav_layout.addWidget(year_combo)

        year_spin.hide()
        year_spin.setEnabled(False)

        year_button = nav.findChild(QWidget, "qt_calendar_yearbutton")
        if year_button is not None:
            year_button.hide()
            year_button.setEnabled(False)

        self._sync_year_dropdown()

    def _sync_year_dropdown(self, year: int | None = None, _month: int | None = None):
        cal = self.calendarWidget()
        if not cal:
            return

        if year is None:
            year = cal.yearShown()

        nav = cal.findChild(QWidget, "qt_calendar_navigationbar")
        if not nav:
            return

        year_combo = nav.findChild(QComboBox, "qt_calendar_yearcombo")
        if not year_combo:
            return

        idx = year_combo.findData(int(year))
        if idx >= 0 and year_combo.currentIndex() != idx:
            prev_state = year_combo.blockSignals(True)
            year_combo.setCurrentIndex(idx)
            year_combo.blockSignals(prev_state)

    def _on_year_dropdown_changed(self, index: int):
        cal = self.calendarWidget()
        if not cal or index < 0:
            return

        nav = cal.findChild(QWidget, "qt_calendar_navigationbar")
        if not nav:
            return

        year_combo = nav.findChild(QComboBox, "qt_calendar_yearcombo")
        if not year_combo:
            return

        year = year_combo.itemData(index)
        if year is None:
            return

        cal.setCurrentPage(int(year), cal.monthShown())

# â”€â”€ Page stylesheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_PAGE_STYLE = """
    QWidget#usersPage {
        background: #f0f2f5;
        font-family: 'Segoe UI', 'Inter', 'Arial';
    }
    QGroupBox {
        background: #ffffff;
        border: 1px solid #dde1e7;
        border-radius: 10px;
        padding: 14px;
        margin-top: 8px;
        font-weight: 600;
        font-size: 13px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
        color: #495057;
    }
    QTabWidget#usrAdminTabs::pane {
        border: 1px solid #dce5ef;
        border-radius: 12px;
        background: #ffffff;
        top: -1px;
    }
    QTabWidget#usrAdminTabs QTabBar::tab {
        background: #eef3f9;
        color: #4a5563;
        border: 1px solid #d4deea;
        border-bottom: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        padding: 6px 14px;
        min-width: 110px;
        font-size: 12px;
        font-weight: 700;
        margin-right: 6px;
    }
    QTabWidget#usrAdminTabs QTabBar::tab:selected {
        background: #ffffff;
        color: #0d6efd;
        border-color: #c7d8ef;
    }
    QLabel#usrSectionTitle {
        color: #1f2a37;
        font-size: 14px;
        font-weight: 700;
        background: transparent;
    }
    QLabel#usrSectionHint {
        color: #738295;
        font-size: 11px;
        font-weight: 500;
        background: transparent;
    }
    QLabel#usrActivityTitle {
        color: #0b4aa2;
        font-size: 24px;
        font-weight: 800;
        font-family: 'Bahnschrift', 'Segoe UI Semibold', 'Trebuchet MS';
        letter-spacing: 0.2px;
    }
    QGroupBox#usrAuditSummary {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding-top: 12px;
    }
    QGroupBox#usrAuditSummary::title {
        color: #6b7280;
        font-size: 12px;
        font-weight: 500;
    }
    QGroupBox#usrActivityPanel {
        border-radius: 12px;
        border: 1px solid #dce5ef;
        padding-top: 12px;
    }
    QWidget#usrActivityFilters {
        background: #f7fbff;
        border: 1px solid #d8e7f7;
        border-radius: 12px;
    }
    QLabel#usrFilterLabel {
        color: #4f637b;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    QLineEdit, QComboBox {
        background: #ffffff;
        border: 1px solid #ced4da;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus { border: 1.5px solid #0d6efd; }
    QTableWidget {
        background: #ffffff;
        gridline-color: #ecf0f4;
        border: 1px solid #e3e8ef;
        border-radius: 10px;
        font-size: 13px;
        alternate-background-color: #f8fbff;
        selection-background-color: #e6f0ff;
        selection-color: #0a58ca;
    }
    QTableWidget#usrUsersTable::item { padding: 12px 10px; border-bottom: 1px solid #eef2f7; }
    QTableWidget#usrActivityTable::item { padding: 10px 8px; border-bottom: 1px solid #f1f3f6; }
    QTableWidget::item:selected { background: #e7f1ff; color: #0a58ca; }
    QHeaderView::section {
        background: #f6f9fc;
        padding: 11px 10px;
        border: none;
        border-bottom: 1px solid #d7dfe8;
        font-weight: 700;
        font-size: 11px;
        color: #5f6b7a;
        letter-spacing: 0.4px;
        text-transform: uppercase;
    }
    QPushButton {
        border-radius: 8px; padding: 8px 16px;
        font-size: 13px; font-weight: 600; border: none;
    }
    QPushButton#primaryBtn   { background: #0d6efd; color: #ffffff; }
    QPushButton#primaryBtn:hover { background: #0b5ed7; }
    QPushButton#primaryBtn:disabled { background: #b8d0f8; color: #e8f0fe; }
    QPushButton#dangerBtn    { background: #dc3545; color: #ffffff; }
    QPushButton#dangerBtn:hover  { background: #b02a37; }
    QPushButton#warningBtn   { background: #fd7e14; color: #ffffff; }
    QPushButton#warningBtn:hover { background: #dc6a0a; }
    QPushButton#neutralBtn   { background: #e9ecef; color: #495057; border: 1px solid #ced4da; }
    QPushButton#neutralBtn:hover { background: #dee2e6; }
    QPushButton#smallBtn {
        background: #ffffff;
        color: #35506f;
        border: 1px solid #c5d8ec;
        border-radius: 9px;
        padding: 6px 10px;
        font-size: 11px;
        font-weight: 700;
    }
    QPushButton#smallBtn:hover {
        background: #edf5ff;
        border-color: #aecaeb;
    }
    QPushButton#pagerBtn {
        background: #f8fafc;
        color: #3f5168;
        border: 1px solid #d6e0ea;
        min-width: 64px;
    }
    QPushButton#pagerBtn:hover {
        background: #edf2f7;
    }
    QLineEdit#usrSearchInput {
        background: #ffffff;
        border: 1px solid #cfe0f2;
        border-radius: 12px;
        padding: 8px 12px;
        font-size: 13px;
        color: #1f2937;
        min-height: 34px;
    }
    QLineEdit#usrSearchInput:focus {
        border: 1.5px solid #0d6efd;
        background: #f8fbff;
    }
    QLabel#usrStatTotal,
    QLabel#usrStatAdmin,
    QLabel#usrStatSpecialists,
    QLabel#usrStatViewer,
    QPushButton#usrStatTotal,
    QPushButton#usrStatAdmin,
    QPushButton#usrStatSpecialists,
    QPushButton#usrStatViewer {
        border-radius: 12px;
        padding: 6px 10px;
        font-size: 11px;
        font-weight: 700;
        border: 1px solid transparent;
    }
    QLabel#usrStatTotal,
    QPushButton#usrStatTotal {
        color: #0b5ed7;
        background: #eaf2ff;
        border-color: #cfe0ff;
    }
    QLabel#usrStatAdmin,
    QPushButton#usrStatAdmin {
        color: #842029;
        background: #fdecef;
        border-color: #f5c2c7;
    }
    QLabel#usrStatSpecialists,
    QPushButton#usrStatSpecialists {
        color: #0f5132;
        background: #e8f7ef;
        border-color: #b7e4c7;
    }
    QLabel#usrStatViewer,
    QPushButton#usrStatViewer {
        color: #495057;
        background: #f1f3f5;
        border-color: #dee2e6;
    }
    QLabel#usrActivityMeta {
        color: #3d5b7a;
        background: #ebf3ff;
        border: 1px solid #d3e1f3;
        border-radius: 12px;
        padding: 6px 10px;
        font-size: 11px;
        font-weight: 700;
    }
    QPushButton#usrStatTotal:checked,
    QPushButton#usrStatAdmin:checked,
    QPushButton#usrStatSpecialists:checked,
    QPushButton#usrStatViewer:checked {
        border-width: 2px;
    }
    QPushButton#usrStatTotal:hover,
    QPushButton#usrStatAdmin:hover,
    QPushButton#usrStatSpecialists:hover,
    QPushButton#usrStatViewer:hover {
        border-width: 2px;
    }
    QWidget#usrNotifyBar {
        background: #e8f5ee;
        border: 1px solid #b7e4c7;
        border-radius: 10px;
    }
    QLabel#usrNotifyText {
        color: #0f5132;
        font-size: 12px;
        font-weight: 600;
        background: transparent;
    }
    QPushButton#usrNotifyClose {
        background: transparent;
        color: #0f5132;
        border: none;
        font-size: 14px;
        font-weight: 700;
        padding: 0 4px;
        min-width: 18px;
    }
    QPushButton#usrNotifyClose:hover {
        color: #0a3622;
    }
"""

_ACTIVITY_LOG_STYLE = """
    QWidget#usersPage {
        background: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    QWidget#usrActivityContainer {
        background: #ffffff;
    }
    QLabel#usrActivityTitle {
        color: #1d4ed8;
        font-size: 20px;
        font-weight: 500;
    }
    QLabel#usrSectionHint {
        color: #64748b;
        font-size: 13px;
        font-weight: 400;
    }
    QFrame#usrSummaryCard {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 12px;
    }
    QFrame#usrSummaryCard QLabel {
        background: transparent;
    }
    QLabel#usrSummaryLabel {
        color: #6b7280;
        font-size: 12px;
        font-weight: 400;
    }
    QLabel#usrSummaryValue {
        color: #1a1a1a;
        font-size: 22px;
        font-weight: 500;
    }
    QLabel#usrSummaryValuePrimary {
        color: #2563eb;
        font-size: 22px;
        font-weight: 500;
    }
    QLabel#usrSummaryValueSmall {
        color: #1a1a1a;
        font-size: 15px;
        font-weight: 500;
    }
    QFrame#usrActivityPanel {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 12px;
    }
    QWidget#usrActivityFilters {
        background: #ffffff;
        border: none;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }
    QLabel#usrFilterLabel {
        color: #6b7280;
        font-size: 12px;
        font-weight: 400;
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
    }
    QLineEdit#usrSearchInput {
        background: #ffffff;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        min-height: 34px;
        font-size: 13px;
        color: #1a1a1a;
        padding: 0 10px;
    }
    QLineEdit#usrSearchInput:focus {
        border: 1px solid #60a5fa;
    }
    QDateEdit#usrDateInput, QComboBox#usrEventFilter {
        background: #ffffff;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        min-height: 34px;
        font-size: 12px;
        color: #1a1a1a;
        padding: 0 10px;
    }
    QDateEdit#usrDateInput::drop-down,
    QComboBox#usrEventFilter::drop-down {
        border: none;
        background: #ffffff;
        width: 18px;
    }
    QDateEdit#usrDateInput::down-arrow,
    QComboBox#usrEventFilter::down-arrow {
        width: 8px;
        height: 8px;
    }
    QPushButton#smallBtn {
        border-radius: 999px;
        height: 30px;
        padding: 0 12px;
        font-size: 12px;
        font-weight: 500;
        background: #ffffff;
        border: 1px solid #bfdbfe;
        color: #1d4ed8;
    }
    QPushButton#smallBtn:hover {
        background: #eff6ff;
    }
    QPushButton#smallBtn:checked {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #2563eb;
    }
    QPushButton#neutralBtn {
        background: #ffffff;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        min-height: 34px;
        padding: 0 14px;
        font-size: 12px;
        font-weight: 500;
        color: #1a1a1a;
    }
    QPushButton#neutralBtn:hover {
        background: #eff6ff;
    }
    QPushButton#ghostAction {
        background: #ffffff;
        border: 1px solid #bfdbfe;
        color: #1a1a1a;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
        font-family: 'Segoe UI';
        font-weight: 400;
    }
    QPushButton#ghostAction:hover {
        background: #eff6ff;
    }
    QTableWidget#usrActivityTable {
        background: #ffffff;
        border: none;
        gridline-color: transparent;
        font-size: 13px;
        alternate-background-color: #ffffff;
    }
    QTableWidget#usrActivityTable::item {
        padding: 11px 16px;
        border-bottom: 1px solid #f3f4f6;
    }
    QTableWidget#usrActivityTable::item:hover {
        background: #eff6ff;
    }
    QHeaderView::section {
        background: #ffffff;
        border: none;
        border-bottom: 1px solid #dbeafe;
        padding: 10px 16px;
        color: #1d4ed8;
        font-size: 12px;
        font-weight: 700;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }
    QWidget#usrPaginationRow {
        border-top: 1px solid #dbeafe;
        background: #ffffff;
    }
    QLabel#usrPaginationText {
        color: #6b7280;
        font-size: 12px;
        font-weight: 400;
        background: transparent;
        border: none;
    }
    QPushButton#pagerBtn {
        height: 30px;
        padding: 0 12px;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        background: #ffffff;
        color: #1d4ed8;
        font-size: 12px;
        font-weight: 500;
    }
    QPushButton#pagerBtn:hover {
        background: #eff6ff;
    }
    QPushButton#pagerBtn:checked {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #2563eb;
    }
    QPushButton#pagerBtn:disabled {
        color: #d1d5db;
        border: 1px solid #f3f4f6;
        background: #ffffff;
    }
    QWidget#usrUserCell {
        background: transparent;
        border: none;
    }
    QLabel#usrAvatarBlue, QLabel#usrAvatarPink {
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 14px;
        font-size: 11px;
        font-weight: 500;
        qproperty-alignment: AlignCenter;
    }
    QLabel#usrAvatarBlue {
        background: #eff6ff;
        color: #2563eb;
    }
    QLabel#usrAvatarPink {
        background: #fdf2f8;
        color: #9d174d;
    }
    QLabel#usrUserName {
        color: #1a1a1a;
        font-size: 13px;
        font-weight: 500;
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
    }
    QLabel#usrBadgeLogin, QLabel#usrBadgeLogout, QLabel#usrBadgeUpdate {
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 500;
    }
    QLabel#usrBadgeLogin {
        background: #f0fdf4;
        color: #166534;
    }
    QLabel#usrBadgeLogout {
        background: #fffbeb;
        color: #92400e;
    }
    QLabel#usrBadgeUpdate {
        background: #eff6ff;
        color: #1e40af;
    }
    QGroupBox#usrUsersPanel {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 12px;
        padding-top: 12px;
    }
    QGroupBox#usrUsersPanel::title {
        color: #1d4ed8;
        font-size: 12px;
        font-weight: 700;
        left: 14px;
        padding: 0 6px;
        background: #ffffff;
    }
    QTableWidget#usrUsersTable {
        background: #ffffff;
        border: none;
        gridline-color: transparent;
        font-size: 13px;
        font-family: 'Segoe UI';
        alternate-background-color: #f3f4f6;
    }
    QTableWidget#usrUsersTable::item {
        background: #ffffff;
        padding: 11px 16px;
        border-bottom: 1px solid #f3f4f6;
    }
    QTableWidget#usrUsersTable::item:alternate {
        background: #f3f4f6;
    }
    QTableWidget#usrUsersTable::item:hover {
        background: #eff6ff;
    }
    QLabel#usrStatTotal,
    QLabel#usrStatAdmin,
    QLabel#usrStatSpecialists,
    QLabel#usrStatViewer,
    QPushButton#usrStatTotal,
    QPushButton#usrStatAdmin,
    QPushButton#usrStatSpecialists,
    QPushButton#usrStatViewer {
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid #bfdbfe;
        background: #ffffff;
        color: #1d4ed8;
    }
    QPushButton#usrStatTotal:checked,
    QPushButton#usrStatAdmin:checked,
    QPushButton#usrStatSpecialists:checked,
    QPushButton#usrStatViewer:checked {
        background: #eff6ff;
        color: #2563eb;
        border-color: #93c5fd;
    }
    QPushButton#usrStatTotal:hover,
    QPushButton#usrStatAdmin:hover,
    QPushButton#usrStatSpecialists:hover,
    QPushButton#usrStatViewer:hover {
        background: #eff6ff;
    }
    QPushButton#primaryBtn {
        background: #1d4ed8;
        color: #ffffff;
    }
    QPushButton#primaryBtn:hover {
        background: #1e40af;
    }
    QPushButton#warningBtn {
        background: #ffffff;
        border: 1px solid #bfdbfe;
        color: #1d4ed8;
    }
    QPushButton#warningBtn:hover {
        background: #eff6ff;
    }
    QPushButton#dangerBtn {
        background: #ffffff;
        border: 1px solid #fecaca;
        color: #b91c1c;
    }
    QPushButton#dangerBtn:hover {
        background: #fef2f2;
    }
    QWidget#usrNotifyBar {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
    }
    QLabel#usrNotifyText {
        color: #1e3a8a;
    }
    QPushButton#usrNotifyClose {
        color: #1d4ed8;
    }
    QPushButton#usrNotifyClose:hover {
        color: #1e3a8a;
    }
    QLabel#statusBar {
        color: #64748b;
        background: transparent;
    }
"""


def _password_meets_policy(password):
    return (
        len(password) >= 12
        and any(c.islower() for c in password)
        and any(c.isupper() for c in password)
        and any(c.isdigit() for c in password)
        and any(not c.isalnum() for c in password)
    )


def _assignable_roles():
    return ["clinician", "viewer", "admin"]


def _add_eye_toggle(field):
    """Attach a show/hide password toggle to the trailing edge of a QLineEdit."""
    import os as _os
    _icon_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "icons")
    _show_icon = QIcon(_os.path.join(_icon_dir, "eye_open.svg"))
    _hide_icon = QIcon(_os.path.join(_icon_dir, "eye_closed.svg"))
    action = QAction(_show_icon, "", field)
    action.setCheckable(True)
    action.setToolTip("Show / hide password")

    def _toggle(visible):
        action.setIcon(_hide_icon if visible else _show_icon)
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    action.toggled.connect(_toggle)
    field.addAction(action, QLineEdit.TrailingPosition)


def _verify_acting_admin(current_username, acting_password):
    """Return True if acting_password matches the stored hash for current_username."""
    try:
        from auth import get_connection, PasswordManager
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = ?", (current_username,))
        row = cur.fetchone()
        conn.close()
        return bool(row and PasswordManager.verify_password(acting_password, row[0]))
    except Exception:
        return False


def _parse_activity_timestamp(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00").strip()
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    normalized = text.replace("T", " ").replace("Z", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# â”€â”€ User Manager â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class UserManager:
    """Thin UI-layer wrapper around user_store."""

    @staticmethod
    def create_user(
        username,
        password,
        role,
        full_name,
        display_name,
        contact,
        specialization,
        availability_json="",
        acting_username=None,
        acting_role=None,
        acting_password=None,
    ):
        return user_store.add_user(
            username,
            password,
            role,
            full_name,
            display_name,
            contact,
            specialization,
            availability_json,
            acting_username,
            acting_role,
            acting_password,
        )

    @staticmethod
    def get_all_users():
        return [(u["username"], u["role"]) for u in user_store.get_all_users()]

    @staticmethod
    def delete_user(username, acting_username=None, acting_role=None, acting_password=None):
        return user_store.delete_user(username, acting_username, acting_role, acting_password)

    @staticmethod
    def update_user_role(username, new_role, acting_username=None, acting_role=None, acting_password=None):
        return user_store.update_user_role(username, new_role, acting_username, acting_role, acting_password)

    @staticmethod
    def reset_password(username, new_password, acting_username=None, acting_role=None, acting_password=None):
        return user_store.reset_password(username, new_password, acting_username, acting_role, acting_password)


# â”€â”€ Dialogs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class NewUserDialog(QDialog):
    """Modal dialog for creating a new user."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New User")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Create New User")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label_style = "color:#344054;font-size:12px;font-weight:600;background:transparent;border:none;"

        def _lbl(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(label_style)
            return lbl

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("3â€“32 chars: letters, digits, _ . -")
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Legal or full professional name")
        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Display name shown across the app and reports")
        self.dr_prefix_checkbox = QCheckBox("Include honorific title (Dr.)")
        self.dr_prefix_checkbox.setStyleSheet("color:#495057;font-size:12px;font-weight:600;padding:2px 0;")
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Phone or email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Min 12 chars")
        self.password_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.password_input)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Re-type password")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.confirm_password_input)
        self.role_input = QComboBox()
        self.role_input.addItems(_assignable_roles())
        self.specialization_input = QComboBox()
        self.specialization_input.addItems(_SPECIALIZATION_OPTIONS)
        self.role_input.currentTextChanged.connect(self._on_role_changed)
        
        form.addRow(_lbl("Full Name:"), self.full_name_input)
        form.addRow(_lbl("Display Name:"), self.display_name_input)
        form.addRow("", self.dr_prefix_checkbox)
        form.addRow(_lbl("Contact:"), self.contact_input)
        form.addRow(_lbl("Username:"), self.username_input)
        form.addRow(_lbl("Password:"), self.password_input)
        form.addRow(_lbl("Confirm:"), self.confirm_password_input)
        form.addRow(_lbl("Role:"), self.role_input)
        form.addRow(_lbl("Specialization:"), self.specialization_input)
        layout.addLayout(form)
        self._on_role_changed(self.role_input.currentText())

        hint = QLabel("Password must be 12+ chars with uppercase, lowercase, number & symbol.")
        hint.setObjectName("dlgHint")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        create_btn = QPushButton("Proceed")
        create_btn.setObjectName("okBtn")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._create_user)
        cancel_btn.clicked.connect(self.reject)
        self.confirm_password_input.returnPressed.connect(self._create_user)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

    def _on_role_changed(self, role_value):
        is_clinician = str(role_value or "").strip().lower() == "clinician"
        self.specialization_input.setEnabled(is_clinician)

    def _create_user(self):
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        display_name = self.display_name_input.text().strip()
        add_dr_prefix = self.dr_prefix_checkbox.isChecked()
        contact = self.contact_input.text().strip()
        password = self.password_input.text()
        role = self.role_input.currentText()
        specialization = self.specialization_input.currentText().strip()

        if add_dr_prefix and display_name and not display_name.lower().startswith("dr."):
            display_name = f"Dr. {display_name}"

        # ── Field presence ────────────────────────────────────────────
        if not username or not full_name or not display_name or not password:
            QMessageBox.warning(self, "Missing Fields", "Full name, display name, username, and password are required.")
            return

        if role == "clinician" and not specialization:
            QMessageBox.warning(self, "Missing Specialization", "Select a specialization for clinician accounts.")
            return

        # ── Username format (mirrors auth.py USERNAME_PATTERN) ────────
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{3,32}", username):
            QMessageBox.warning(
                self, "Invalid Username",
                "Username must be 3–32 characters and may only contain\n"
                "letters, digits, underscores (_), dots (.) and hyphens (-).",
            )
            return

        if username.lower() == password.lower():
            QMessageBox.warning(
                self,
                "Invalid Credentials",
                "Username and password cannot be the same.",
            )
            return

        # ── Password checks ───────────────────────────────────────────
        if password != self.confirm_password_input.text():
            QMessageBox.warning(self, "Password Mismatch", "The passwords you entered do not match.")
            return
        if not _password_meets_policy(password):
            QMessageBox.warning(
                self, "Weak Password",
                "Password must be at least 12 characters and include\n"
                "uppercase, lowercase, a number, and a symbol.",
            )
            return

        # ── Resolve acting admin context ──────────────────────────────
        parent = self.parent()
        parent_app = getattr(parent, "parent_app", None)
        acting_username = getattr(parent_app, "username", None)
        acting_role = getattr(parent_app, "role", None)

        if not acting_username or acting_role != "admin":
            QMessageBox.warning(
                self, "Permission Denied",
                "Only administrators can create user accounts.\n"
                "Please log in as an admin and try again.",
            )
            return

        # ── Duplicate check ───────────────────────────────────────────
        existing_names = {u["username"].lower() for u in user_store.get_all_users()}
        if username.lower() in existing_names:
            QMessageBox.warning(
                self, "Username Taken",
                f"The username '{username}' is already in use.\n"
                "Please choose a different username.",
            )
            return

        # ── Admin password confirmation ───────────────────────────────
        proceed = QMessageBox.question(
            self,
            "Confirm Account Creation",
            f"Create account for <b>{display_name}</b> with role <b>{role}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = UsersPage.prompt_for_admin_password(self, "create this account")
        if acting_password is None:
            return
        if not _verify_acting_admin(acting_username, acting_password):
            QMessageBox.warning(
                self, "Incorrect Password",
                "The admin password you entered is incorrect.\n"
                "Please try again.",
            )
            return

        availability_dialog = AvailabilityDialog(self)
        if availability_dialog.exec() != QDialog.Accepted:
            return
        availability_json = "" if availability_dialog.skip_selected else availability_dialog.get_availability_json()

        # ── Create ────────────────────────────────────────────────────
        success = UserManager.create_user(
            username, password, role,
            full_name,
            display_name,
            contact,
            specialization,
            availability_json=availability_json,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )
        if success:
            if hasattr(parent, "refresh_users"):
                parent.refresh_users()
            if hasattr(parent, "log_activity"):
                parent.log_activity(
                    acting_username,
                    "ACCOUNT_CREATED",
                    {
                        "target": username,
                        "role": role,
                    },
                    action_text=f"Account Created ({role})",
                )
            if hasattr(parent, "_set_status"):
                parent._set_status(f"User '{username}' created successfully")
            if hasattr(parent, "show_notification"):
                parent.show_notification(f"Account created: {display_name} ({role}).")
            self.accept()
        else:
            QMessageBox.warning(
                self, "Creation Failed",
                "An unexpected error occurred while saving the account.\n"
                "Please check the application logs for details.",
            )


class AvailabilityDialog(QDialog):
    """Step 2 dialog for setting recurring weekly availability."""

    def __init__(self, parent=None, initial_availability=None):
        super().__init__(parent)
        self.setWindowTitle("Weekly Availability")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)
        self.skip_selected = False
        self._day_checks = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Set Weekly Availability")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)

        subtitle = QLabel("Select available weekdays and time range. This repeats weekly until changed.")
        subtitle.setObjectName("dlgHint")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        time_row = QHBoxLayout()
        time_row.setSpacing(4)
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("hh:mm AP")
        self.start_time.setFixedWidth(110)
        self.start_time.setTime(QTime(9, 0))
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("hh:mm AP")
        self.end_time.setFixedWidth(110)
        self.end_time.setTime(QTime(17, 0))
        time_row.addWidget(QLabel("From"))
        time_row.addWidget(self.start_time)
        time_row.addWidget(QLabel("To"))
        time_row.addWidget(self.end_time)
        time_row.addStretch()
        layout.addLayout(time_row)

        for idx, (day_key, day_label) in enumerate(_WEEKDAY_OPTIONS):
            checkbox = QCheckBox(day_label)
            checkbox.setChecked(idx < 5)
            self._day_checks.append((day_key, checkbox))
            layout.addWidget(checkbox)

        if isinstance(initial_availability, dict):
            start_time = str(initial_availability.get("start_time") or "").strip()
            end_time = str(initial_availability.get("end_time") or "").strip()
            selected_days = initial_availability.get("days") or []

            # Backward compatibility for older date-based availability payloads.
            if not selected_days:
                legacy_dates = initial_availability.get("dates") or []
                if isinstance(legacy_dates, list):
                    resolved_days = []
                    for date_value in legacy_dates:
                        try:
                            parsed_day = datetime.strptime(str(date_value), "%Y-%m-%d").date().strftime("%a").lower()
                            resolved_days.append(parsed_day)
                        except Exception:
                            pass
                    selected_days = resolved_days

            if start_time:
                parsed = self._parse_time_value(start_time)
                if parsed.isValid():
                    self.start_time.setTime(parsed)
            if end_time:
                parsed = self._parse_time_value(end_time)
                if parsed.isValid():
                    self.end_time.setTime(parsed)

            if isinstance(selected_days, list):
                selected_set = {str(value).strip().lower() for value in selected_days}
                for day_key, checkbox in self._day_checks:
                    checkbox.setChecked(day_key in selected_set)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("cancelBtn")
        skip_btn = QPushButton("Skip For Now")
        skip_btn.setObjectName("neutralBtn")
        save_btn = QPushButton("Save Account")
        save_btn.setObjectName("okBtn")
        back_btn.clicked.connect(self.reject)
        skip_btn.clicked.connect(self._skip)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(back_btn)
        btn_row.addWidget(skip_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _skip(self):
        self.skip_selected = True
        self.accept()

    def _save(self):
        selected_days = [day for day, cb in self._day_checks if cb.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "Availability", "Select at least one weekday or choose Skip For Now.")
            return
        if self.end_time.time() <= self.start_time.time():
            QMessageBox.warning(self, "Availability", "End time must be later than start time.")
            return
        self.skip_selected = False
        self.accept()

    def get_availability_json(self) -> str:
        payload = {
            "mode": "weekly-template",
            "start_time": self.start_time.time().toString("hh:mm AP"),
            "end_time": self.end_time.time().toString("hh:mm AP"),
            "days": [day for day, cb in self._day_checks if cb.isChecked()],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _parse_time_value(value: str) -> QTime:
        text = str(value or "").strip()
        if not text:
            return QTime()
        for fmt in ("hh:mm AP", "h:mm AP", "hh:mm ap", "h:mm ap", "HH:mm"):
            parsed = QTime.fromString(text, fmt)
            if parsed.isValid():
                return parsed
        return QTime()


class ChangeRoleDialog(QDialog):
    """Modal dialog for changing a user's role."""

    def __init__(self, username, current_role, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Change Role \u2014 {username}")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Change User Role")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Select a new role for <b>{username}</b>:"))

        self.role_input = QComboBox()
        self.role_input.addItems(_assignable_roles())
        self.role_input.setCurrentText(current_role)
        layout.addWidget(self.role_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        ok_btn = QPushButton("Apply Change")
        ok_btn.setObjectName("okBtn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def selected_role(self):
        return self.role_input.currentText()


class ResetPasswordDialog(QDialog):
    """Modal dialog for resetting a user's password."""

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Reset Password \u2014 {username}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Reset Password")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Set a new password for <b>{username}</b>:"))

        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("New password")
        self.pw_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.pw_input)
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm new password")
        self.confirm_input.setEchoMode(QLineEdit.Password)
        _add_eye_toggle(self.confirm_input)
        layout.addWidget(self.pw_input)
        layout.addWidget(self.confirm_input)

        hint = QLabel("Password must be 12+ chars with uppercase, lowercase, number & symbol.")
        hint.setObjectName("dlgHint")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        ok_btn = QPushButton("Reset Password")
        ok_btn.setObjectName("okBtn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        self.confirm_input.returnPressed.connect(self._validate)

    def _validate(self):
        if not self.pw_input.text():
            QMessageBox.warning(self, "Empty Password", "Password cannot be empty.")
            return
        if not _password_meets_policy(self.pw_input.text()):
            QMessageBox.warning(
                self, "Weak Password",
                "Password must be at least 12 characters and include\n"
                "uppercase, lowercase, a number, and a symbol.",
            )
            return
        if self.pw_input.text() != self.confirm_input.text():
            QMessageBox.warning(self, "Password Mismatch", "The passwords do not match.")
            return
        self.accept()

    def new_password(self):
        return self.pw_input.text()


# â”€â”€ Users Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class UsersPage(QWidget):
    """User Management page."""

    def __init__(self):
        super().__init__()
        self.setObjectName("usersPage")
        self.setStyleSheet(f"{_PAGE_STYLE}\n{_ACTIVITY_LOG_STYLE}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        page_container = QWidget()
        page_container.setObjectName("usrActivityContainer")
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(14, 12, 14, 12)
        page_layout.setSpacing(10)
        main_layout.addWidget(page_container)

        # â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        header_row = QHBoxLayout()
        self._usr_title_lbl = QLabel("User Management")
        self._usr_title_lbl.setObjectName("usrActivityTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("usrSectionHint")
        self.count_label.hide()
        header_row.addWidget(self._usr_title_lbl)
        header_row.addWidget(self.count_label)
        header_row.addStretch()
        page_layout.addLayout(header_row)

        self.notify_bar = QWidget()
        self.notify_bar.setObjectName("usrNotifyBar")
        notify_layout = QHBoxLayout(self.notify_bar)
        notify_layout.setContentsMargins(10, 8, 10, 8)
        notify_layout.setSpacing(8)
        self.notify_text = QLabel("")
        self.notify_text.setObjectName("usrNotifyText")
        notify_layout.addWidget(self.notify_text, 1)
        self.notify_close_btn = QPushButton("×")
        self.notify_close_btn.setObjectName("usrNotifyClose")
        self.notify_close_btn.clicked.connect(self.notify_bar.hide)
        notify_layout.addWidget(self.notify_close_btn)
        self.notify_bar.hide()
        page_layout.addWidget(self.notify_bar)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("usrSearchInput")
        self.search_input.setPlaceholderText("Search by name, username, role, specialization, or contact")
        self.search_input.textChanged.connect(self.refresh_users)

        self.active_role_filter = "all"
        self.total_chip = QPushButton("Total 0")
        self.total_chip.setObjectName("usrStatTotal")
        self.total_chip.setCheckable(True)
        self.total_chip.clicked.connect(lambda _checked=False: self._set_role_filter("all"))

        self.admin_chip = QPushButton("Admin 0")
        self.admin_chip.setObjectName("usrStatAdmin")
        self.admin_chip.setCheckable(True)
        self.admin_chip.clicked.connect(lambda _checked=False: self._set_role_filter("admin"))

        self.specialists_chip = QPushButton("Clinician 0")
        self.specialists_chip.setObjectName("usrStatSpecialists")
        self.specialists_chip.setCheckable(True)
        self.specialists_chip.clicked.connect(lambda _checked=False: self._set_role_filter("clinician"))

        self.viewer_chip = QPushButton("Viewer 0")
        self.viewer_chip.setObjectName("usrStatViewer")
        self.viewer_chip.setCheckable(True)
        self.viewer_chip.clicked.connect(lambda _checked=False: self._set_role_filter("viewer"))

        self._role_filter_buttons = {
            "all": self.total_chip,
            "admin": self.admin_chip,
            "clinician": self.specialists_chip,
            "viewer": self.viewer_chip,
        }
        self._sync_role_filter_buttons()

        # Users table card
        self._usr_table_group = QGroupBox("Users")
        self._usr_table_group.setObjectName("usrUsersPanel")
        table_vbox = QVBoxLayout(self._usr_table_group)
        table_vbox.setSpacing(6)

        users_hdr = QHBoxLayout()
        users_hdr.setContentsMargins(2, 0, 2, 2)
        users_hdr_col = QVBoxLayout()
        users_hdr_col.setSpacing(0)
        users_hdr.addLayout(users_hdr_col)
        table_vbox.addLayout(users_hdr)

        users_toolbar_host = QWidget()
        users_toolbar_host.setObjectName("usrActivityFilters")
        users_toolbar = QHBoxLayout(users_toolbar_host)
        users_toolbar.setContentsMargins(10, 8, 10, 8)
        users_toolbar.setSpacing(8)

        self.search_input.setMinimumWidth(170)
        self.search_input.setMaximumWidth(260)
        self.search_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        users_toolbar.addWidget(self.search_input)

        for chip in (self.total_chip, self.admin_chip, self.specialists_chip, self.viewer_chip):
            chip.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            users_toolbar.addWidget(chip)

        users_toolbar.addStretch()

        self.new_user_btn = QPushButton("\u002b  New User")
        self.new_user_btn.setObjectName("ghostAction")
        self.new_user_btn.clicked.connect(self._open_new_user_dialog)
        self.new_user_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        users_toolbar.addWidget(self.new_user_btn)

        table_vbox.addWidget(users_toolbar_host)

        self.users_table = QTableWidget(0, 7)
        self.users_table.setObjectName("usrUsersTable")
        self.users_table.setHorizontalHeaderLabels([
            "Name", "Username", "Contact", "Availability Time", "Availability Days", "Role", "Status"
        ])
        self.users_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        for col_idx in range(self.users_table.columnCount()):
            hdr_item = self.users_table.horizontalHeaderItem(col_idx)
            if hdr_item is not None:
                hdr_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.users_table.setColumnCount(7)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setShowGrid(True)
        self.users_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_table.customContextMenuRequested.connect(self._open_user_context_menu)
        self.users_table.itemSelectionChanged.connect(self._sync_status_action_labels)
        self.users_table.cellDoubleClicked.connect(self._edit_availability_from_cell)
        self.users_table.horizontalHeader().setStretchLastSection(False)
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.users_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.users_table.setColumnWidth(1, 140)
        self.users_table.setColumnWidth(3, 165)
        self.users_table.verticalHeader().setDefaultSectionSize(44)
        self.users_table.setMinimumHeight(200)
        table_vbox.addWidget(self.users_table)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.change_role_btn = QPushButton("Change Role")
        self.change_role_btn.setObjectName("neutralBtn")
        self.change_role_btn.clicked.connect(self.change_selected_role)
        self.toggle_active_btn = QPushButton("Set Active/Inactive")
        self.toggle_active_btn.setObjectName("neutralBtn")
        self.toggle_active_btn.clicked.connect(self.toggle_selected_user_status)
        self.reset_pw_btn = QPushButton("Reset Password")
        self.reset_pw_btn.setObjectName("warningBtn")
        self.reset_pw_btn.clicked.connect(self.reset_selected_password)
        self.delete_btn = QPushButton("Delete User")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self.delete_user)
        action_row.addWidget(self.change_role_btn)
        action_row.addWidget(self.toggle_active_btn)
        action_row.addWidget(self.reset_pw_btn)
        action_row.addWidget(self.delete_btn)
        table_vbox.addLayout(action_row)

        page_layout.addWidget(self._usr_table_group, 1)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusBar")
        self.status_label.setStyleSheet("color:#6c757d;font-size:12px;padding:2px 0;")
        self.status_label.hide()

        self.refresh_users()
        

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _open_new_user_dialog(self):
        NewUserDialog(parent=self).exec()

    def _set_status(self, message, ok=True):
        color = "#198754" if ok else "#dc3545"
        icon = "\u2713" if ok else "\u2717"
        self.status_label.setStyleSheet(
            f"color:{color};font-size:12px;font-weight:600;padding:2px 0;"
        )
        self.status_label.setText(f"{icon}  {message}")

    def _make_summary_card(self, label: str, value: str, value_object: str = "usrSummaryValue"):
        card = QFrame()
        card.setObjectName("usrSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(6)

        label_widget = QLabel(label)
        label_widget.setObjectName("usrSummaryLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName(value_object)

        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        card_layout.addStretch()
        return card, value_widget

    def _set_active_preset(self, key: str):
        for name, btn in self._preset_buttons.items():
            btn.setChecked(name == key)

    def _go_to_page(self, page: int):
        if page < 1 or page > self.total_pages:
            return
        self.current_page = page
        self.load_activity_log()

    def _username_initials(self, username: str) -> str:
        value = str(username or "").strip()
        if not value:
            return "--"
        if len(value) <= 2:
            return value.upper()
        letters = [ch for ch in value if ch.isalpha()]
        if len(letters) >= 2:
            return f"{letters[0]}{letters[1]}".upper()
        return value[:2].upper()

    def _avatar_variant(self, username: str) -> str:
        key = str(username or "").strip().lower()
        if not key:
            return "usrAvatarBlue"
        if key not in self._avatar_palette:
            self._avatar_palette[key] = "usrAvatarBlue" if len(self._avatar_palette) % 2 == 0 else "usrAvatarPink"
        return self._avatar_palette[key]

    def _user_cell_widget(self, username: str) -> QWidget:
        cell = QWidget()
        cell.setObjectName("usrUserCell")
        row = QHBoxLayout(cell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        avatar = QLabel(self._username_initials(username))
        avatar.setObjectName(self._avatar_variant(username))
        name_lbl = QLabel(str(username or "").strip())
        name_lbl.setObjectName("usrUserName")

        row.addWidget(avatar)
        row.addWidget(name_lbl)
        row.addStretch()
        return cell

    def _event_badge_widget(self, event_type: str) -> QLabel:
        event = str(event_type or "").strip().upper()
        label = QLabel("Update")
        label.setObjectName("usrBadgeUpdate")
        if event == "LOGIN":
            label.setText("Login")
            label.setObjectName("usrBadgeLogin")
        elif event == "LOGOUT":
            label.setText("Logout")
            label.setObjectName("usrBadgeLogout")
        return label

    def _format_action_for_grid(self, action: str, event_type: str = "", metadata=None) -> str:
        event = str(event_type or "").strip().upper()
        if event == "LOGIN":
            return "Logged into the system"
        if event == "LOGOUT":
            return "Logged out of the system"
        return UsersPage._format_activity_action(action, event_type=event_type, metadata=metadata)

    def _format_timestamp_for_grid(self, raw_timestamp: str) -> str:
        raw = str(raw_timestamp or "").strip()
        if not raw:
            return ""
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            month_name = parsed.strftime("%B")
            day_number = parsed.day
            year_number = parsed.year
            hour_text = parsed.strftime("%I").lstrip("0") or "0"
            minute_text = parsed.strftime("%M")
            meridiem = parsed.strftime("%p").lower()
            return f"{month_name} {day_number}, {year_number} - {hour_text}:{minute_text} {meridiem}"
        except ValueError:
            return raw.replace("T", " - ")

    def show_notification(self, message: str):
        self.notify_text.setText(message)
        self.notify_bar.show()

    def _open_user_context_menu(self, pos):
        item = self.users_table.itemAt(pos)
        if item is None:
            return
        self.users_table.selectRow(item.row())

        menu = QMenu(self)
        edit_availability_action = menu.addAction("Edit Availability")
        menu.addSeparator()
        change_role_action = menu.addAction("Change Role")
        toggle_active_action = menu.addAction(self._status_action_text_for_selected_row())
        reset_password_action = menu.addAction("Reset Password")
        menu.addSeparator()
        delete_action = menu.addAction("Delete User")

        chosen = menu.exec(self.users_table.viewport().mapToGlobal(pos))
        if chosen == edit_availability_action:
            self.edit_selected_availability()
        elif chosen == change_role_action:
            self.change_selected_role()
        elif chosen == toggle_active_action:
            self.toggle_selected_user_status()
        elif chosen == reset_password_action:
            self.reset_selected_password()
        elif chosen == delete_action:
            self.delete_user()

    def _status_action_text_for_selected_row(self) -> str:
        row = self.users_table.currentRow()
        if row < 0:
            return "Set Active/Inactive"
        status_item = self.users_table.item(row, 6)
        if not status_item:
            return "Set Active/Inactive"
        is_active = bool(status_item.data(Qt.UserRole))
        return "Set Inactive" if is_active else "Set Active"

    def _sync_status_action_labels(self):
        if hasattr(self, "toggle_active_btn"):
            self.toggle_active_btn.setText(self._status_action_text_for_selected_row())

    def _edit_availability_from_cell(self, row, column):
        if column in (3, 4):
            self.users_table.selectRow(row)
            self.edit_selected_availability()

    def _get_user_by_username(self, username: str):
        target = str(username or "").strip().lower()
        for user in user_store.get_all_users():
            if str(user.get("username") or "").strip().lower() == target:
                return user
        return None

    def edit_selected_availability(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to edit availability.")
            return

        username_item = self.users_table.item(row, 1)
        if not username_item:
            return
        username = username_item.text().strip()

        user = self._get_user_by_username(username)
        if not user:
            QMessageBox.warning(self, "User Not Found", "Unable to load selected user details.")
            return

        initial_payload = None
        raw_availability = user.get("availability_json")
        if raw_availability:
            try:
                initial_payload = json.loads(raw_availability) if isinstance(raw_availability, str) else raw_availability
            except Exception:
                initial_payload = None

        dialog = AvailabilityDialog(self, initial_availability=initial_payload)
        dialog.setWindowTitle(f"Edit Availability - {username}")
        if dialog.exec() != QDialog.Accepted:
            return

        availability_json = "" if dialog.skip_selected else dialog.get_availability_json()
        acting_username, acting_role = self._actor_context()
        acting_password = self.prompt_for_admin_password(self, f"update availability for '{username}'")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        success = user_store.update_user_availability(
            username,
            availability_json,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )
        if not success:
            QMessageBox.warning(self, "Update Failed", f"Could not update availability for '{username}'.")
            return

        self._set_status(f"Availability updated for '{username}'")
        actor_username = str(acting_username or "system").strip() or "system"
        self.log_activity(
            actor_username,
            "USER_AVAILABILITY_UPDATED",
            {"target": username},
            action_text=f"USER_AVAILABILITY_UPDATED target={username}",
        )
        if hasattr(self, "show_notification"):
            self.show_notification(f"Schedule updated for {username}.")
        self.refresh_users()

    def _actor_context(self):
        parent_app = getattr(self, "parent_app", None)
        username = getattr(parent_app, "username", None)
        role = getattr(parent_app, "role", None)
        return username, role

    @staticmethod
    def prompt_for_admin_password(parent, action="perform this action"):
        pw, accepted = QInputDialog.getText(
            parent,
            "Admin Confirmation",
            f"Enter your admin password to {action}:",
            QLineEdit.Password,
        )
        if not accepted:
            return None
        if not pw:
            QMessageBox.warning(parent, "Missing Password", "Admin password is required.")
            return None
        return pw

    def _check_admin_password(self, acting_password):
        """Verify the acting admin's password and show an error if wrong. Returns True on success."""
        current_username, _ = self._actor_context()
        if not _verify_acting_admin(current_username, acting_password):
            QMessageBox.warning(self, "Incorrect Password", "Your admin password is incorrect.")
            return False
        return True

    def _sync_role_filter_buttons(self):
        selected = str(getattr(self, "active_role_filter", "all") or "all").strip().lower()
        for role_key, button in getattr(self, "_role_filter_buttons", {}).items():
            button.blockSignals(True)
            button.setChecked(role_key == selected)
            button.blockSignals(False)

    def _set_role_filter(self, role_key: str):
        normalized = str(role_key or "all").strip().lower()
        if normalized not in {"all", "admin", "clinician", "viewer"}:
            normalized = "all"
        self.active_role_filter = normalized
        self._sync_role_filter_buttons()
        self.refresh_users()

    # â”€â”€ User Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def refresh_users(self):
        self.users_table.setRowCount(0)
        users = user_store.get_all_users()
        app = QApplication.instance()
        app_stylesheet = app.styleSheet() if app else ""
        dark_mode = "#1e1e2e" in app_stylesheet
        role_colors = _ROLE_COLORS_DARK if dark_mode else _ROLE_COLORS

        total_count = len(users)
        admin_count = sum(1 for user in users if user.get("role") == "admin")
        clinician_count = sum(1 for user in users if user.get("role") == "clinician")
        viewer_count = sum(1 for user in users if user.get("role") == "viewer")

        if hasattr(self, "total_chip"):
            self.total_chip.setText(f"Total {total_count}")
            self.admin_chip.setText(f"Admin {admin_count}")
            self.specialists_chip.setText(f"Clinician {clinician_count}")
            self.viewer_chip.setText(f"Viewer {viewer_count}")
            self._sync_role_filter_buttons()

        query = ""
        if hasattr(self, "search_input"):
            query = self.search_input.text().strip().lower()

        filtered_users = []
        active_role_filter = str(getattr(self, "active_role_filter", "all") or "all").strip().lower()
        for user in users:
            role = str(user.get("role") or "")
            specialization = str(user.get("specialization") or "")
            if active_role_filter != "all" and role != active_role_filter:
                continue
            haystack = " ".join(
                [
                    str(user.get("full_name") or ""),
                    str(user.get("display_name") or ""),
                    str(user.get("username") or ""),
                    str(user.get("contact") or ""),
                    role,
                    specialization,
                ]
            ).lower()
            if query and query not in haystack:
                continue
            filtered_users.append(user)

        for user in filtered_users:
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)

            name_item = QTableWidgetItem(user.get("full_name") or user["username"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            username_item = QTableWidgetItem(user["username"])
            username_item.setFlags(username_item.flags() & ~Qt.ItemIsEditable)
            username_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            contact_item = QTableWidgetItem(str(user.get("contact") or ""))
            contact_item.setFlags(contact_item.flags() & ~Qt.ItemIsEditable)
            contact_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

            availability_time_text = "Not set"
            availability_days_text = "Not set"
            raw_availability = user.get("availability_json")
            if raw_availability:
                try:
                    payload = json.loads(raw_availability) if isinstance(raw_availability, str) else raw_availability
                except Exception:
                    payload = {}

                if isinstance(payload, dict):
                    start_time = str(payload.get("start_time") or "").strip()
                    end_time = str(payload.get("end_time") or "").strip()
                    if start_time and end_time:
                        parsed_start = AvailabilityDialog._parse_time_value(start_time)
                        parsed_end = AvailabilityDialog._parse_time_value(end_time)
                        if parsed_start.isValid() and parsed_end.isValid():
                            availability_time_text = (
                                f"{parsed_start.toString('hh:mm AP')} - {parsed_end.toString('hh:mm AP')}"
                            )
                        else:
                            availability_time_text = f"{start_time} - {end_time}"

                    selected_days = payload.get("days") or []

                    # Backward compatibility with older payloads that stored concrete dates.
                    if not selected_days:
                        legacy_dates = payload.get("dates") or []
                        if isinstance(legacy_dates, list):
                            derived = []
                            for date_value in legacy_dates:
                                try:
                                    derived.append(datetime.strptime(str(date_value), "%Y-%m-%d").date().strftime("%a").lower())
                                except Exception:
                                    pass
                            selected_days = derived

                    if isinstance(selected_days, list) and selected_days:
                        ordered = []
                        for day_key, _ in _WEEKDAY_OPTIONS:
                            if any(str(value).strip().lower() == day_key for value in selected_days):
                                ordered.append(_WEEKDAY_LABELS[day_key][:3])
                        if ordered:
                            availability_days_text = ", ".join(ordered)

            availability_time_item = QTableWidgetItem(availability_time_text)
            availability_time_item.setFlags(availability_time_item.flags() & ~Qt.ItemIsEditable)
            availability_time_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            availability_days_item = QTableWidgetItem(availability_days_text)
            availability_days_item.setFlags(availability_days_item.flags() & ~Qt.ItemIsEditable)
            availability_days_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

            role = user["role"]
            specialization = str(user.get("specialization") or "").strip()
            display_role = specialization if role == "clinician" and specialization else role
            role_item = QTableWidgetItem(f"  {display_role}  ")
            role_item.setFlags(role_item.flags() & ~Qt.ItemIsEditable)
            role_item.setTextAlignment(Qt.AlignCenter)
            role_item.setData(Qt.UserRole, role)
            fg, bg = role_colors.get(role, ("#212529", "#f8f9fa"))
            role_item.setForeground(QColor(fg))
            role_item.setBackground(QColor(bg))

            is_active = bool(user.get("is_active", True))
            status_text = "Active" if is_active else "Inactive"
            status_item = QTableWidgetItem(f"  {status_text}  ")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setData(Qt.UserRole, is_active)
            if is_active:
                status_item.setForeground(QColor("#166534"))
                status_item.setBackground(QColor("#dcfce7"))
            else:
                status_item.setForeground(QColor("#991b1b"))
                status_item.setBackground(QColor("#fee2e2"))

            self.users_table.setItem(row, 0, name_item)
            self.users_table.setItem(row, 1, username_item)
            self.users_table.setItem(row, 2, contact_item)
            self.users_table.setItem(row, 3, availability_time_item)
            self.users_table.setItem(row, 4, availability_days_item)
            self.users_table.setItem(row, 5, role_item)
            self.users_table.setItem(row, 6, status_item)
            
        self.users_table.resizeRowsToContents()
        self._sync_status_action_labels()

    # â”€â”€ CRUD Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def delete_user(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to delete.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 5)
        if not username_item or not role_item:
            return

        username = username_item.text()
        role = str(role_item.data(Qt.UserRole) or role_item.text().strip())
        current_username, current_role = self._actor_context()

        if role == "admin" and current_role == "admin" and username != current_username:
            QMessageBox.warning(
                self, "Not Allowed",
                "Admins cannot delete other admin accounts.",
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to permanently delete user '<b>{username}</b>'?<br>"
            "<br><i>This action cannot be undone.</i>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(self, f"delete user '{username}'")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        success = user_store.delete_user(
            username,
            acting_username=current_username,
            acting_role=current_role,
            acting_password=acting_password,
        )
        if success:
            self._set_status(f"User '{username}' deleted")
            actor_username = str(current_username or "system").strip() or "system"
            self.log_activity(
                actor_username,
                "ACCOUNT_DELETED",
                {"target": username, "target_role": role},
                action_text=f"ACCOUNT_DELETED target={username};target_role={role}",
            )
            self.refresh_users()
            QMessageBox.information(self, "User Deleted", f"User '{username}' was successfully deleted.")
        else:
            self._set_status(f"Failed to delete '{username}'", ok=False)
            QMessageBox.warning(self, "Deletion Failed", f"Could not delete user '{username}'.")

    def change_selected_role(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to change their role.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 5)
        if not username_item or not role_item:
            return

        username = username_item.text()
        current_role_val = str(role_item.data(Qt.UserRole) or role_item.text().strip())
        acting_username, _ = self._actor_context()

        if acting_username and username.strip().lower() == acting_username.strip().lower():
            QMessageBox.warning(
                self,
                "Not Allowed",
                "For safety, you cannot change your own role.",
            )
            return

        dlg = ChangeRoleDialog(username, current_role_val, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_role = dlg.selected_role()
        if new_role == current_role_val:
            return

        proceed = QMessageBox.question(
            self,
            "Confirm Role Change",
            f"Change role for '<b>{username}</b>' from <b>{current_role_val}</b> to <b>{new_role}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(
            self, f"change '{username}' to {new_role}"
        )
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        acting_username, acting_role = self._actor_context()
        success = user_store.update_user_role(
            username,
            new_role,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )
        if success:
            self._set_status(f"Role updated: {username} \u2192 {new_role}")
            actor_username = str(acting_username or "system").strip() or "system"
            self.log_activity(
                actor_username,
                "ROLE_CHANGED",
                {
                    "target": username,
                    "new_role": new_role,
                    "previous_role": current_role_val,
                },
                action_text=(
                    f"ROLE_CHANGED target={username};new_role={new_role};"
                    f"previous_role={current_role_val}"
                ),
            )
            self.refresh_users()
            QMessageBox.information(
                self, "Role Updated",
                f"'{username}' has been changed to <b>{new_role}</b>.",
            )
        else:
            self._set_status(f"Failed to update role for '{username}'", ok=False)
            QMessageBox.warning(self, "Update Failed", f"Could not update role for '{username}'.")

    def reset_selected_password(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user to reset their password.")
            return
        username_item = self.users_table.item(row, 1)
        if not username_item:
            return
        username = username_item.text()

        dlg = ResetPasswordDialog(username, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        proceed = QMessageBox.question(
            self,
            "Confirm Password Reset",
            f"Reset password for '<b>{username}</b>' now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(self, f"reset '{username}' password")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        acting_username, acting_role = self._actor_context()
        success = user_store.reset_password(
            username, dlg.new_password(),
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )
        if success:
            self._set_status(f"Password reset for '{username}'")
            actor_username = str(acting_username or "system").strip() or "system"
            self.log_activity(
                actor_username,
                "PASSWORD_RESET",
                {"target": username},
                action_text=f"PASSWORD_RESET target={username}",
            )
            QMessageBox.information(
                self, "Password Reset",
                f"Password for '{username}' was successfully reset.",
            )
        else:
            self._set_status(f"Failed to reset password for '{username}'", ok=False)
            QMessageBox.warning(self, "Reset Failed", f"Could not reset password for '{username}'.")

    def toggle_selected_user_status(self):
        row = self.users_table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a user first.")
            return

        username_item = self.users_table.item(row, 1)
        role_item = self.users_table.item(row, 5)
        status_item = self.users_table.item(row, 6)
        if not username_item or not role_item or not status_item:
            return

        username = username_item.text().strip()
        role = str(role_item.data(Qt.UserRole) or "").strip().lower()
        is_active = bool(status_item.data(Qt.UserRole))
        target_state = not is_active
        target_text = "active" if target_state else "inactive"

        current_username, current_role = self._actor_context()
        if role == "admin" and not target_state and username == current_username:
            QMessageBox.warning(self, "Not Allowed", "You cannot deactivate your own admin account.")
            return

        proceed = QMessageBox.question(
            self,
            "Confirm Status Change",
            f"Set '<b>{username}</b>' as <b>{target_text}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if proceed != QMessageBox.Yes:
            return

        acting_password = self.prompt_for_admin_password(self, f"set '{username}' as {target_text}")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        success = user_store.update_user_active_status(
            username,
            target_state,
            acting_username=current_username,
            acting_role=current_role,
            acting_password=acting_password,
        )
        if success:
            self._set_status(f"Status updated: {username} → {target_text}")
            actor_username = str(current_username or "system").strip() or "system"
            self.log_activity(
                actor_username,
                "USER_STATUS_CHANGED",
                {"target": username, "status": target_text},
                action_text=f"USER_STATUS_CHANGED target={username};status={target_text}",
            )
            self.refresh_users()
            QMessageBox.information(self, "Status Updated", f"'{username}' is now {target_text}.")
        else:
            self._set_status(f"Failed to update status for '{username}'", ok=False)
            QMessageBox.warning(self, "Update Failed", f"Could not update status for '{username}'.")

    def log_activity(self, user, event_type, metadata=None, action_text=None):
        timestamp = _utc_now_iso()
        user_store.log_activity_event(
            user,
            event_type,
            metadata=metadata,
            action_time=timestamp,
            action_text=action_text,
        )
        parent_app = getattr(self, "parent_app", None)
        activity_page = getattr(parent_app, "activity_log_page", None)
        if activity_page and hasattr(activity_page, "load_activity_log"):
            activity_page.load_activity_log()

    @staticmethod
    def _format_activity_action(action: str, event_type: str = "", metadata=None) -> str:
        text = str(action or "").strip()
        if not text:
            text = "Unknown"

        details = {}
        if isinstance(metadata, dict):
            details = {str(k).strip().lower(): str(v).strip() for k, v in metadata.items()}

        if not details:
            event = text
            payload = ""
            if " " in text:
                event, payload = text.split(" ", 1)
            for token in str(payload or "").split(";"):
                piece = token.strip()
                if not piece or "=" not in piece:
                    continue
                key, value = piece.split("=", 1)
                details[key.strip().lower()] = value.strip()

        event_upper = str(event_type or "").strip().upper()
        if not event_upper or event_upper == "LEGACY":
            event_upper = text.split(" ", 1)[0].strip().upper() if text else "LEGACY"

        lowered = text.lower()
        if event_upper == "LOGIN":
            return "Login"
        if event_upper == "LOGOUT":
            return "Logout"
        if event_upper == "PROFILE_UPDATED":
            return "Profile Updated"
        if lowered == "login":
            return "Login"
        if lowered == "logout":
            return "Logout"
        if lowered == "deleted":
            return "Account Deleted"
        if lowered == "password reset":
            return "Password Reset"
        if lowered == "availability updated":
            return "Availability Updated"
        if lowered == "profile updated":
            return "Profile Updated"
        if event_upper == "ACCOUNT_DELETED":
            target = details.get("target") or "Unknown"
            role_name = details.get("target_role")
            if role_name:
                return f"Deleted account {target} ({role_name})"
            return f"Deleted account {target}"
        if event_upper == "ROLE_CHANGED":
            target = details.get("target") or "Unknown"
            new_role = details.get("new_role")
            previous_role = details.get("previous_role")
            if previous_role and new_role:
                return f"Changed role for {target}: {previous_role} → {new_role}"
            if new_role:
                return f"Changed role for {target} to {new_role}"
            return f"Changed role for {target}"
        if event_upper == "PASSWORD_RESET":
            target = details.get("target") or "Unknown"
            return f"Reset password for {target}"
        if event_upper == "USER_STATUS_CHANGED":
            target = details.get("target") or "Unknown"
            status_name = details.get("status") or "unknown"
            return f"Changed status for {target} to {status_name}"
        if event_upper == "USER_AVAILABILITY_UPDATED":
            target = details.get("target") or "Unknown"
            return f"Updated availability for {target}"
        if event_upper == "ACCOUNT_CREATED":
            target = details.get("target") or "Unknown"
            role_name = details.get("role")
            if role_name:
                return f"Created account {target} ({role_name})"
            return f"Created account {target}"
        if lowered.startswith("created as "):
            role = text[11:].strip()
            return f"Account Created ({role})" if role else "Account Created"
        if lowered.startswith("role changed to "):
            role = text[16:].strip()
            return f"Role Changed ({role})" if role else "Role Changed"
        if lowered.startswith("report_generated"):
            patient_id = details.get("patient_id")
            by_user = details.get("finalized_by")
            file_name = details.get("file")
            if patient_id and by_user:
                message = f"Generated report PDF for {patient_id} ({by_user})"
                if file_name:
                    message += f" - {file_name}"
                return message
            if patient_id:
                message = f"Generated report PDF for {patient_id}"
                if file_name:
                    message += f" - {file_name}"
                return message
            return "Report PDF Generated"
        if lowered.startswith("referral_generated"):
            patient_id = details.get("patient_id")
            by_user = details.get("finalized_by")
            file_name = details.get("file")
            if patient_id and by_user:
                message = f"Generated referral PDF for {patient_id} ({by_user})"
                if file_name:
                    message += f" - {file_name}"
                return message
            if patient_id:
                message = f"Generated referral PDF for {patient_id}"
                if file_name:
                    message += f" - {file_name}"
                return message
            return "Referral PDF Generated"
        if event_upper == "SCREENED_PATIENT":
            patient_id = details.get("patient_id") or "Unknown"
            eye = details.get("eye") or "Eye not specified"
            result = details.get("result") or "Result not specified"
            confidence = details.get("confidence")
            mode = details.get("mode")
            suffix = f" ({mode})" if mode else ""
            if confidence:
                return f"Screened patient {patient_id}: {eye}, {result} ({confidence}%){suffix}"
            return f"Screened patient {patient_id}: {eye}, {result}{suffix}"
        if event_upper == "RECORD_OPENED":
            patient_id = details.get("patient_id") or "Unknown"
            source = details.get("source") or "reports"
            return f"Opened patient record {patient_id} ({source})"
        if event_upper == "RECORD_ARCHIVED":
            patient_id = details.get("patient_id") or "Unknown"
            return f"Archived patient record {patient_id}"
        if event_upper == "RECORD_RESTORED":
            patient_id = details.get("patient_id") or "Unknown"
            return f"Restored patient record {patient_id}"
        if event_upper == "REPORT_EXPORT_CSV":
            rows = details.get("rows") or "0"
            return f"Exported reports to CSV ({rows} rows)"
        if event_upper == "ACTIVITY_LOG_EXPORT_CSV":
            rows = details.get("rows") or "0"
            return f"Exported activity log to CSV ({rows} rows)"
        if event_upper == "REFERRAL_ASSIGNED":
            referral_id = details.get("referral_id") or "Unknown"
            assigned_to = details.get("assigned_to") or "Unknown"
            return f"Assigned referral {referral_id} to {assigned_to}"
        if event_upper == "REFERRAL_REASSIGNED":
            referral_id = details.get("referral_id") or "Unknown"
            assigned_to = details.get("assigned_to") or "Unknown"
            return f"Reassigned referral {referral_id} to {assigned_to}"
        if event_upper == "REFERRAL_STATUS_UPDATED":
            referral_id = details.get("referral_id") or "Unknown"
            from_status = details.get("from_status") or "Unknown"
            to_status = details.get("to_status") or "Unknown"
            return f"Updated referral {referral_id}: {from_status} -> {to_status}"
        if event_upper == "REFERRAL_NOTE_UPDATED":
            referral_id = details.get("referral_id") or "Unknown"
            return f"Added clinical note to referral {referral_id}"
        if event_upper == "EXTERNAL_REFERRAL_LETTER_GENERATED":
            referral_id = details.get("referral_id") or "Unknown"
            return f"Generated external referral letter {referral_id}"
        if event_upper == "TRUSTED_REFERRAL_ADDED":
            hospital_name = details.get("hospital_name") or "Unknown"
            return f"Added trusted referral {hospital_name}"
        if event_upper == "TRUSTED_REFERRAL_UPDATED":
            hospital_name = details.get("hospital_name") or "Unknown"
            return f"Updated trusted referral {hospital_name}"
        if event_upper == "TRUSTED_REFERRAL_DELETED":
            hospital_name = details.get("hospital_name") or "Unknown"
            return f"Deleted trusted referral {hospital_name}"
        if lowered.startswith("assigned referral "):
            body = text[len("Assigned referral "):].strip()
            if " to " in body:
                referral_id, assignee = body.split(" to ", 1)
                return f"Assigned referral {referral_id.strip()} to {assignee.strip()}"
            return "Assigned referral"
        if lowered.startswith("updated referral "):
            body = text[len("Updated referral "):].strip()
            if ":" in body:
                referral_id, transition = body.split(":", 1)
                return f"Updated referral {referral_id.strip()} ({transition.strip()})"
            return "Updated referral status"
        if lowered.startswith("updated referral note "):
            referral_id = text[len("Updated referral note "):].strip()
            if referral_id:
                return f"Added clinical note to referral {referral_id}"
            return "Added clinical referral note"
        if lowered.startswith("rescreen_allowed"):
            patient_id = details.get("patient_id") or "Unknown"
            mode = "replace" if details.get("replace_mode") == "True" else "new"
            return f"Rescreen allowed for {patient_id} ({mode})"
        if lowered.startswith("rescreen_blocked"):
            patient_id = details.get("patient_id") or "Unknown"
            owner = details.get("owner") or "Unknown"
            return f"Rescreen blocked for {patient_id} (owner: {owner})"
        return text

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        self._usr_title_lbl.setText(pack["usr_title"])
        self._usr_table_group.setTitle(pack["usr_table"])


class ActivityLogPage(QWidget):
    """Standalone admin activity log page."""

    MAX_EXPORT_ROWS = 10000
    LARGE_EXPORT_THRESHOLD = 2000
    PAGE_SIZE = 100
    EVENT_FILTERS = [
        ("All Events", ""),
        ("Login", "LOGIN"),
        ("Logout", "LOGOUT"),
        ("Update", "PROFILE_UPDATED"),
        ("Screened Patient", "SCREENED_PATIENT"),
        ("Role Changed", "ROLE_CHANGED"),
        ("User Status Changed", "USER_STATUS_CHANGED"),
        ("Report Export", "REPORT_EXPORT_CSV"),
        ("Referral Assigned", "REFERRAL_ASSIGNED"),
        ("Referral Status Updated", "REFERRAL_STATUS_UPDATED"),
        ("Trusted Referral Added", "TRUSTED_REFERRAL_ADDED"),
        ("Trusted Referral Updated", "TRUSTED_REFERRAL_UPDATED"),
        ("Trusted Referral Deleted", "TRUSTED_REFERRAL_DELETED"),
    ]

    @staticmethod
    def _ph_tz():
        if ZoneInfo is not None:
            try:
                return ZoneInfo("Asia/Manila")
            except Exception:
                pass
        return timezone(timedelta(hours=8))

    def __init__(self):
        super().__init__()
        self.setObjectName("usersPage")
        self.setStyleSheet(f"{_PAGE_STYLE}\n{_ACTIVITY_LOG_STYLE}")
        self.current_page = 1
        self.total_events = 0
        self.total_pages = 1
        self._avatar_palette = {}
        self._selected_event_filter = ""

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addStretch(1)

        page_container = QWidget()
        page_container.setObjectName("usrActivityContainer")
        page_container.setMaximumWidth(1200)
        root_layout.addWidget(page_container)
        root_layout.addStretch(1)

        main_layout = QVBoxLayout(page_container)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(16)

        header_row = QHBoxLayout()
        self._title_lbl = QLabel("Activity log")
        self._title_lbl.setObjectName("usrActivityTitle")
        header_row.addWidget(self._title_lbl)
        header_row.addStretch()
        main_layout.addLayout(header_row)

        self._section_hint = QLabel("Latest admin, account, and clinical audit events")
        self._section_hint.setObjectName("usrSectionHint")
        main_layout.addWidget(self._section_hint)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(12)
        for col in range(2):
            summary_grid.setColumnStretch(col, 1)

        total_card, self._summary_total_lbl = self._make_summary_card("Total events", "261", value_object="usrSummaryValuePrimary")
        export_card, self._summary_last_export_lbl = self._make_summary_card("Last export", "Never", value_object="usrSummaryValueSmall")

        summary_grid.addWidget(total_card, 0, 0)
        summary_grid.addWidget(export_card, 0, 1)
        main_layout.addLayout(summary_grid)

        self._log_group = QFrame()
        self._log_group.setObjectName("usrActivityPanel")
        log_vbox = QVBoxLayout(self._log_group)
        log_vbox.setContentsMargins(0, 0, 0, 0)
        log_vbox.setSpacing(0)

        controls = QWidget()
        controls.setObjectName("usrActivityFilters")
        controls_row = QHBoxLayout(controls)
        controls_row.setContentsMargins(16, 14, 16, 14)
        controls_row.setSpacing(10)

        self.log_search_input = QLineEdit()
        self.log_search_input.setObjectName("usrSearchInput")
        self.log_search_input.setPlaceholderText("Search activity log...")
        self.log_search_input.setMinimumWidth(160)
        self.log_search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.log_search_input.textChanged.connect(self._reset_and_reload)
        search_icon = QIcon.fromTheme("edit-find")
        if search_icon.isNull():
            search_icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "activity_log.svg"))
        self.log_search_input.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)

        self.date_from = ModernCalendarDateEdit(
            QDate(2000, 1, 1),
            QDate.currentDate().addYears(20),
            QDate.currentDate().addDays(-7),
            self,
        )
        self.date_from.setObjectName("usrDateInput")
        self.date_from.setMinimumWidth(120)
        self.date_from.setMaximumWidth(120)
        self.date_from.setStyleSheet(
            "QDateEdit#usrDateInput {background:#ffffff;border:1px solid #e9ecef;border-radius:8px;padding:0 10px;color:#1a1a1a;}"
            "QDateEdit#usrDateInput::drop-down {background:#ffffff;border:none;width:18px;}"
        )
        self.date_from.dateChanged.connect(self._reset_and_reload)

        self.date_to = ModernCalendarDateEdit(
            QDate(2000, 1, 1),
            QDate.currentDate().addYears(20),
            QDate.currentDate(),
            self,
        )
        self.date_to.setObjectName("usrDateInput")
        self.date_to.setMinimumWidth(120)
        self.date_to.setMaximumWidth(120)
        self.date_to.setStyleSheet(
            "QDateEdit#usrDateInput {background:#ffffff;border:1px solid #e9ecef;border-radius:8px;padding:0 10px;color:#1a1a1a;}"
            "QDateEdit#usrDateInput::drop-down {background:#ffffff;border:none;width:18px;}"
        )
        self.date_to.dateChanged.connect(self._reset_and_reload)

        self.event_type_filter = QComboBox()
        self.event_type_filter.setObjectName("usrEventFilter")
        self.event_type_filter.setMinimumWidth(120)
        self.event_type_filter.setMaximumWidth(140)
        for label, value in self.EVENT_FILTERS:
            self.event_type_filter.addItem(label, value)
        self.event_type_filter.currentTextChanged.connect(self._on_event_filter_changed)

        preset_today_btn = QPushButton("Today")
        preset_today_btn.setObjectName("smallBtn")
        preset_today_btn.setCheckable(True)
        preset_today_btn.clicked.connect(self._set_preset_today)

        preset_7d_btn = QPushButton("7 Days")
        preset_7d_btn.setObjectName("smallBtn")
        preset_7d_btn.setCheckable(True)
        preset_7d_btn.clicked.connect(self._set_preset_7d)

        preset_30d_btn = QPushButton("30 Days")
        preset_30d_btn.setObjectName("smallBtn")
        preset_30d_btn.setCheckable(True)
        preset_30d_btn.clicked.connect(self._set_preset_30d)
        self._preset_buttons = {
            "today": preset_today_btn,
            "7d": preset_7d_btn,
            "30d": preset_30d_btn,
        }

        self.export_activity_btn = QPushButton("Export CSV")
        self.export_activity_btn.setObjectName("neutralBtn")
        self.export_activity_btn.clicked.connect(self.export_activity_log_csv)
        self.export_activity_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons", "export.svg")))

        self.prev_page_btn = QPushButton("<- Prev")
        self.prev_page_btn.setObjectName("pagerBtn")
        self.prev_page_btn.clicked.connect(self._go_prev_page)

        self.next_page_btn = QPushButton("Next ->")
        self.next_page_btn.setObjectName("pagerBtn")
        self.next_page_btn.clicked.connect(self._go_next_page)

        self.page_btn_1 = QPushButton("1")
        self.page_btn_1.setObjectName("pagerBtn")
        self.page_btn_1.setCheckable(True)
        self.page_btn_1.clicked.connect(lambda: self._go_to_page(1))

        self.page_btn_2 = QPushButton("2")
        self.page_btn_2.setObjectName("pagerBtn")
        self.page_btn_2.setCheckable(True)
        self.page_btn_2.clicked.connect(lambda: self._go_to_page(2))

        self.page_btn_3 = QPushButton("3")
        self.page_btn_3.setObjectName("pagerBtn")
        self.page_btn_3.setCheckable(True)
        self.page_btn_3.clicked.connect(lambda: self._go_to_page(3))

        self._page_buttons = [self.page_btn_1, self.page_btn_2, self.page_btn_3]

        controls_row.addWidget(self.log_search_input)
        from_lbl = QLabel("From")
        from_lbl.setObjectName("usrFilterLabel")
        controls_row.addWidget(from_lbl)
        controls_row.addWidget(self.date_from)
        to_lbl = QLabel("To")
        to_lbl.setObjectName("usrFilterLabel")
        controls_row.addWidget(to_lbl)
        controls_row.addWidget(self.date_to)
        controls_row.addWidget(self.event_type_filter)
        controls_row.addWidget(preset_today_btn)
        controls_row.addWidget(preset_7d_btn)
        controls_row.addWidget(preset_30d_btn)
        controls_row.addWidget(self.export_activity_btn)
        log_vbox.addWidget(controls)

        self.activity_log = QTableWidget(0, 4)
        self.activity_log.setObjectName("usrActivityTable")
        self.activity_log.setHorizontalHeaderLabels(["User", "Action", "Event Type", "Date & Time"])
        action_header_item = self.activity_log.horizontalHeaderItem(1)
        if action_header_item is not None:
            action_header_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        header_item = self.activity_log.horizontalHeaderItem(3)
        if header_item is not None:
            header_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.activity_log.setSelectionMode(QAbstractItemView.NoSelection)
        self.activity_log.setEditTriggers(QTableWidget.NoEditTriggers)
        self.activity_log.verticalHeader().setVisible(False)
        self.activity_log.setShowGrid(False)
        self.activity_log.setAlternatingRowColors(False)
        self.activity_log.horizontalHeader().setStretchLastSection(False)
        self.activity_log.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.activity_log.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.activity_log.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.activity_log.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.activity_log.horizontalHeader().setMinimumSectionSize(90)
        self.activity_log.setColumnWidth(0, 220)
        self.activity_log.setColumnWidth(2, 120)
        self.activity_log.setColumnWidth(3, 180)
        self.activity_log.setWordWrap(True)
        self.activity_log.setMinimumHeight(200)
        self.activity_log.setSortingEnabled(False)
        log_vbox.addWidget(self.activity_log)

        pagination_row = QWidget()
        pagination_row.setObjectName("usrPaginationRow")
        pagination_layout = QHBoxLayout(pagination_row)
        pagination_layout.setContentsMargins(16, 12, 16, 12)
        pagination_layout.setSpacing(8)

        self.pagination_meta_lbl = QLabel("0 events · Page 1 of 1")
        self.pagination_meta_lbl.setObjectName("usrPaginationText")
        pagination_layout.addWidget(self.pagination_meta_lbl)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.page_btn_1)
        pagination_layout.addWidget(self.page_btn_2)
        pagination_layout.addWidget(self.page_btn_3)
        pagination_layout.addWidget(self.next_page_btn)
        log_vbox.addWidget(pagination_row)

        main_layout.addWidget(self._log_group, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusBar")
        self.status_label.setStyleSheet("color:#6b7280;font-size:12px;padding:2px 0;")
        self.status_label.hide()

        self._selected_event_filter = self._resolve_event_filter_value(self.event_type_filter.currentText())
        self._set_active_preset("7d")
        self.load_activity_log()

    def _actor_context(self):
        parent_app = getattr(self, "parent_app", None)
        if parent_app is None:
            parent_app = self.window() if self.window() is not self else None
        username = getattr(parent_app, "username", None)
        role = getattr(parent_app, "role", None)
        if not username:
            username = os.environ.get("EYESHIELD_CURRENT_USER")
        if not role:
            role = os.environ.get("EYESHIELD_CURRENT_ROLE")
        return username, role

    def _check_admin_password(self, acting_password):
        current_username, _ = self._actor_context()
        if not _verify_acting_admin(current_username, acting_password):
            QMessageBox.warning(self, "Incorrect Password", "Your admin password is incorrect.")
            return False
        return True

    def _set_status(self, message, ok=True):
        color = "#198754" if ok else "#dc3545"
        icon = "\u2713" if ok else "\u2717"
        self.status_label.setStyleSheet(
            f"color:{color};font-size:12px;font-weight:600;padding:2px 0;"
        )
        self.status_label.setText(f"{icon}  {message}")

    def _resolve_event_filter_value(self, label: str) -> str:
        del label
        return str(self.event_type_filter.currentData() or "").strip().upper()

    def _on_event_filter_changed(self, *_args):
        self._selected_event_filter = self._resolve_event_filter_value(self.event_type_filter.currentText())
        self._reset_and_reload()

    def _make_summary_card(self, label: str, value: str, value_object: str = "usrSummaryValue"):
        card = QFrame()
        card.setObjectName("usrSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(6)

        label_widget = QLabel(label)
        label_widget.setObjectName("usrSummaryLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName(value_object)

        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        card_layout.addStretch()
        return card, value_widget

    def _set_active_preset(self, key: str):
        for name, btn in self._preset_buttons.items():
            btn.setChecked(name == key)

    def _go_to_page(self, page: int):
        if page < 1 or page > self.total_pages:
            return
        self.current_page = page
        self.load_activity_log()

    def _username_initials(self, username: str) -> str:
        value = str(username or "").strip()
        if not value:
            return "--"
        if len(value) <= 2:
            return value.upper()
        letters = [ch for ch in value if ch.isalpha()]
        if len(letters) >= 2:
            return f"{letters[0]}{letters[1]}".upper()
        return value[:2].upper()

    def _avatar_variant(self, username: str) -> str:
        key = str(username or "").strip().lower()
        if not key:
            return "usrAvatarBlue"
        if key not in self._avatar_palette:
            self._avatar_palette[key] = "usrAvatarBlue" if len(self._avatar_palette) % 2 == 0 else "usrAvatarPink"
        return self._avatar_palette[key]

    def _user_cell_widget(self, username: str) -> QWidget:
        cell = QWidget()
        cell.setObjectName("usrUserCell")
        row = QHBoxLayout(cell)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(8)

        username_text = str(username or "").strip()
        avatar = QLabel(self._username_initials(username_text))
        avatar.setObjectName(self._avatar_variant(username))
        avatar.setAlignment(Qt.AlignCenter)

        name_lbl = QLabel()
        name_lbl.setObjectName("usrUserName")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_lbl.setToolTip(username_text)

        available = max(40, self.activity_log.columnWidth(0) - 28 - 8 - 20)
        elided = name_lbl.fontMetrics().elidedText(username_text, Qt.TextElideMode.ElideRight, available)
        name_lbl.setText(elided)

        row.addWidget(avatar)
        row.addWidget(name_lbl)
        row.addStretch()
        return cell

    def _event_badge_widget(self, event_type: str) -> QLabel:
        event = str(event_type or "").strip().upper()
        label = QLabel("Update")
        label.setObjectName("usrBadgeUpdate")
        if event == "LOGIN":
            label.setText("Login")
            label.setObjectName("usrBadgeLogin")
        elif event == "LOGOUT":
            label.setText("Logout")
            label.setObjectName("usrBadgeLogout")
        return label

    def _format_action_for_grid(self, action: str, event_type: str = "", metadata=None) -> str:
        event = str(event_type or "").strip().upper()
        if event == "LOGIN":
            return "Logged into the system"
        if event == "LOGOUT":
            return "Logged out of the system"
        return UsersPage._format_activity_action(action, event_type=event_type, metadata=metadata)

    def _format_timestamp_for_grid(self, raw_timestamp: str) -> str:
        raw = str(raw_timestamp or "").strip()
        if not raw:
            return ""
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(self._ph_tz())
            month_name = parsed.strftime("%B")
            day_number = parsed.day
            year_number = parsed.year
            hour_text = parsed.strftime("%I").lstrip("0") or "0"
            minute_text = parsed.strftime("%M")
            meridiem = parsed.strftime("%p").lower()
            return f"{month_name} {day_number}, {year_number} - {hour_text}:{minute_text} {meridiem}"
        except ValueError:
            return raw.replace("T", " - ")

    def _current_filters(self):
        search_text = self.log_search_input.text().strip()
        start_date = self.date_from.date()
        end_date = self.date_to.date()
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        return {
            "query": search_text,
            "from_time": start_date.toString("yyyy-MM-dd"),
            "to_time": end_date.toString("yyyy-MM-dd"),
            "event_type": str(self._selected_event_filter or "").strip().upper(),
        }

    def _clear_filters(self):
        self.log_search_input.clear()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())
        self.event_type_filter.setCurrentIndex(0)
        self._set_active_preset("30d")
        self._reset_and_reload()

    def _reset_and_reload(self):
        self.current_page = 1
        self.load_activity_log()

    def _go_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_activity_log()

    def _go_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_activity_log()

    def _set_preset_today(self):
        today = QDate.currentDate()
        self.log_search_input.clear()
        self.event_type_filter.setCurrentIndex(0)
        self.date_from.setDate(today)
        self.date_to.setDate(today)
        self._set_active_preset("today")
        self._reset_and_reload()

    def _set_preset_7d(self):
        today = QDate.currentDate()
        self.log_search_input.clear()
        self.event_type_filter.setCurrentIndex(0)
        self.date_from.setDate(today.addDays(-7))
        self.date_to.setDate(today)
        self._set_active_preset("7d")
        self._reset_and_reload()

    def _set_preset_30d(self):
        today = QDate.currentDate()
        self.log_search_input.clear()
        self.event_type_filter.setCurrentIndex(0)
        self.date_from.setDate(today.addDays(-30))
        self.date_to.setDate(today)
        self._set_active_preset("30d")
        self._reset_and_reload()

    def load_activity_log(self):
        filters = self._current_filters()
        offset = (self.current_page - 1) * self.PAGE_SIZE
        acting_username, acting_role = self._actor_context()
        entries, total = user_store.get_activity_logs(
            from_time=filters["from_time"],
            to_time=filters["to_time"],
            query=filters["query"],
            event_type=filters["event_type"],
            limit=self.PAGE_SIZE,
            offset=offset,
            acting_username=acting_username,
            acting_role=acting_role,
        )

        self.total_events = total
        self.total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
            offset = (self.current_page - 1) * self.PAGE_SIZE
            entries, total = user_store.get_activity_logs(
                from_time=filters["from_time"],
                to_time=filters["to_time"],
                query=filters["query"],
                event_type=filters["event_type"],
                limit=self.PAGE_SIZE,
                offset=offset,
                acting_username=acting_username,
                acting_role=acting_role,
            )
            self.total_events = total

        self.pagination_meta_lbl.setText(f"{self.total_events} events · Page {self.current_page} of {self.total_pages}")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
        for idx, page_btn in enumerate(self._page_buttons, start=1):
            page_btn.setEnabled(idx <= self.total_pages)
            page_btn.setVisible(idx <= max(3, self.total_pages))
            page_btn.setChecked(idx == self.current_page)

        self.activity_log.setSortingEnabled(False)
        self.activity_log.setRowCount(0)
        for entry in entries:
            row = self.activity_log.rowCount()
            self.activity_log.insertRow(row)

            username = str(entry.get("username") or "").strip()
            action = self._format_action_for_grid(
                entry.get("action"),
                event_type=entry.get("event_type"),
                metadata=entry.get("metadata"),
            )
            event_type = str(entry.get("event_type") or "LEGACY").strip().upper() or "LEGACY"
            timestamp = self._format_timestamp_for_grid(str(entry.get("time") or "").strip())

            action_item = QTableWidgetItem(action)
            time_item = QTableWidgetItem(timestamp)

            username_item = QTableWidgetItem("")
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            username_item.setFlags(username_item.flags() & ~Qt.ItemIsEditable)
            username_item.setToolTip(username)
            action_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            time_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.activity_log.setItem(row, 0, username_item)
            self.activity_log.setItem(row, 1, action_item)
            self.activity_log.setItem(row, 2, QTableWidgetItem(event_type))
            self.activity_log.setItem(row, 3, time_item)
            self.activity_log.setCellWidget(row, 0, self._user_cell_widget(username))
            self.activity_log.setCellWidget(row, 2, self._event_badge_widget(event_type))

            action_item.setForeground(QColor("#6b7280"))
            time_item.setForeground(QColor("#9ca3af"))
            
            # Apply alternating row background colors for better readability
            bg_color = QColor("#ffffff") if row % 2 == 0 else QColor("#f3f4f6")
            for col in range(4):
                item = self.activity_log.item(row, col)
                if item:
                    item.setBackground(bg_color)

        if not entries:
            self.activity_log.setRowCount(1)
            empty_item = QTableWidgetItem("No audit events found for the selected filters.")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
            empty_item.setForeground(QColor("#6b7280"))
            self.activity_log.setItem(0, 0, empty_item)
            self.activity_log.setSpan(0, 0, 1, 4)

        self.activity_log.setSortingEnabled(False)
        self.activity_log.resizeRowsToContents()

        self._update_compliance_summary(entries)

    def _update_compliance_summary(self, entries):
        """Update the audit compliance summary card with stats from the current view."""
        if not entries:
            self._summary_total_lbl.setText("0")
            self._summary_last_export_lbl.setText("Never")
            return

        last_export_time = None

        for entry in entries:
            event_type = str(entry.get("event_type") or "").strip().upper()

            if event_type == "ACTIVITY_LOG_EXPORT_CSV" and last_export_time is None:
                last_export_time = str(entry.get("time") or "").strip()

        self._summary_total_lbl.setText(str(self.total_events))
        if last_export_time:
            self._summary_last_export_lbl.setText(self._format_timestamp_for_grid(last_export_time))
        else:
            self._summary_last_export_lbl.setText("Never")

    def export_activity_log_csv(self):
        current_username, current_role = self._actor_context()
        if str(current_role or "").strip().lower() != "admin":
            QMessageBox.warning(self, "Access Denied", "Only admin users can export activity logs.")
            return

        filters = self._current_filters()
        entries = []
        offset = 0
        while len(entries) < self.MAX_EXPORT_ROWS:
            batch, _total = user_store.get_activity_logs(
                from_time=filters["from_time"],
                to_time=filters["to_time"],
                query=filters["query"],
                event_type=filters["event_type"],
                limit=500,
                offset=offset,
                acting_username=current_username,
                acting_role=current_role,
            )
            if not batch:
                break
            entries.extend(batch)
            offset += len(batch)
            if len(batch) < 500:
                break

        if not entries:
            QMessageBox.information(self, "Export Activity Log", "No activity log entries to export.")
            return

        export_reason = ""
        if len(entries) > self.LARGE_EXPORT_THRESHOLD:
            reason, accepted = QInputDialog.getText(
                self,
                "Export Reason Required",
                (
                    f"You are exporting {len(entries)} entries.\n"
                    "Enter a brief reason for this large export:"
                ),
            )
            if not accepted:
                return
            export_reason = str(reason or "").strip()
            if not export_reason:
                QMessageBox.warning(self, "Export Activity Log", "Reason is required for large exports.")
                return

        acting_password = UsersPage.prompt_for_admin_password(self, "export the activity log")
        if acting_password is None:
            return
        if not self._check_admin_password(acting_password):
            return

        start_date = filters["from_time"]
        end_date = filters["to_time"]
        default_name = f"EyeShield_ActivityLog_{start_date}_to_{end_date}_{datetime.now().strftime('%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export Activity Log", default_name, "CSV Files (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path = f"{path}.csv"

        try:
            with open(path, "w", newline="", encoding="utf-8") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(["Username", "Action", "Date-Time", "Event Type", "Metadata JSON", "Raw Event"])
                for entry in entries:
                    writer.writerow(
                        [
                            str(entry.get("username") or "").strip(),
                            UsersPage._format_activity_action(
                                entry.get("action"),
                                event_type=entry.get("event_type"),
                                metadata=entry.get("metadata"),
                            ),
                            str(entry.get("time") or "").strip(),
                            str(entry.get("event_type") or "LEGACY").strip(),
                            json.dumps(entry.get("metadata") or {}, ensure_ascii=True, separators=(",", ":")),
                            str(entry.get("action") or "").strip(),
                        ]
                    )
        except OSError as err:
            QMessageBox.warning(self, "Export Activity Log", f"Failed to export activity log: {err}")
            return

        search_text = filters["query"].strip()
        user_store.log_activity_event(
            str(current_username or "system").strip(),
            "ACTIVITY_LOG_EXPORT_CSV",
            metadata={
                "rows": len(entries),
                "query": search_text or "<none>",
                "from": start_date,
                "to": end_date,
                "path": os.path.basename(path),
                "reason": export_reason or "<not-required>",
            },
            action_time=_utc_now_iso(),
            action_text=(
                "ACTIVITY_LOG_EXPORT_CSV "
                f"rows={len(entries)};"
                f"query={search_text or '<none>'};"
                f"from={start_date};"
                f"to={end_date};"
                f"path={os.path.basename(path)};"
                f"reason={export_reason or '<not-required>'}"
            ),
        )
        self.load_activity_log()
        self._set_status(f"Exported activity log ({len(entries)} rows)")
        QMessageBox.information(
            self,
            "Export Activity Log",
            f"Exported {len(entries)} entries to:\n{path}",
        )

    def apply_language(self, language: str):
        from translations import get_pack

        pack = get_pack(language)
        self._title_lbl.setText(pack["usr_log"])
        self._log_group.setTitle(pack["usr_log"])

