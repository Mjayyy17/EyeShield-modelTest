"""
Dashboard module for EyeShield EMR application.
Contains main application window and dashboard functionality.
"""

import contextlib
import json
import os
import random
import re
import sqlite3
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

try:
    import winsound
except Exception:  # pragma: no cover - platform specific
    winsound = None

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QGroupBox, QMessageBox, QProgressBar, QSizePolicy,
    QFrame, QMenu, QInputDialog, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QDialog, QApplication
)
from PySide6.QtCore import Qt, QSize, QByteArray, QEvent, QTimer, QCoreApplication
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QFont, QShortcut, QKeySequence, QColor, QGuiApplication
from PySide6.QtSvg import QSvgRenderer

from screening import ScreeningPage
from reports import ReportsPage
from users import UsersPage, ActivityLogPage
from settings import SettingsPage, DARK_STYLESHEET
from help_support import HelpSupportPage
from trusted_hospitals import TrustedHospitalsPage
from camera import CameraPage
from auth import DB_FILE, UserManager
from user_auth import get_user_profile


class EyeShieldApp(QMainWindow):
    """Main application window"""

    ROLE_PAGE_ACCESS = {
        "admin": {4, 5, 6, 8, 9},
        "clinician": {0, 1, 2, 3, 5, 6, 7},
        "viewer": {0, 5, 6},
    }

    def __init__(self, username, role, display_name=None, full_name=None, specialization=None, contact=None):
        super().__init__()

        self.username = username
        self.role = role
        self.full_name = str(full_name or "").strip()
        self.display_name = str(display_name or os.environ.get("EYESHIELD_CURRENT_NAME") or username).strip()
        self.specialization = str(specialization or os.environ.get("EYESHIELD_CURRENT_SPECIALIZATION") or "").strip()
        self.contact = str(contact or os.environ.get("EYESHIELD_CURRENT_CONTACT") or "").strip()
        self.display_title = self.specialization if self.role == "clinician" and self.specialization else self.role
        self.allowed_pages = self._allowed_pages_for_role(role)
        self._dark_mode = False
        self._saved_styles = {}
        self._logging_out = False
        self._current_language = "English"
        self._inactivity_timeout_enabled = True
        self._inactivity_timeout_minutes = 15
        self._inactivity_warning_seconds = 30
        self._inactivity_warning_remaining_sec = 0
        self._inactivity_warning_dialog = None
        self._inactivity_warning_text_label = None
        self._inactivity_warning_timer = None
        self._inactivity_warning_active = False
        self._dashboard_clock_timer = None
        self._active_nav_key = ""

        self.setWindowTitle("EyeShield – DR Screening")
        self.setMinimumSize(900, 560)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            target_width = min(1400, max(1024, int(available.width() * 0.95)))
            target_height = min(860, max(620, int(available.height() * 0.92)))
            self.resize(target_width, target_height)
        else:
            self.resize(1280, 720)

        # Set app icon
        _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "eyeshield_icon.svg")
        self._brand_logo_path = self._resolve_existing_path(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "Logo.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "logo.png"),
            _icon_path,
        )
        self._brand_title_path = self._resolve_existing_path(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "title.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "Title.png"),
        )
        self._app_icon_pixmap = self._load_svg_pixmap(_icon_path, 256)
        self._app_icon = QIcon(self._app_icon_pixmap)
        self.setWindowIcon(self._app_icon)
        icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

        root = QWidget()
        root_layout = QVBoxLayout(root)

        # Create top navigation bar
        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_bar.setFixedHeight(78)
        self.nav_bar = nav_bar
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(12, 4, 12, 4)
        nav_layout.setSpacing(4)
        nav_bar.setStyleSheet("""
            QWidget#navBar {
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)


        # App title + icon in a fixed-width container so they never shift
        title_icon_container = QWidget()
        title_icon_container.setFixedSize(165, 70)
        title_icon_container.setStyleSheet("background: transparent;")
        title_icon_layout = QHBoxLayout(title_icon_container)
        title_icon_layout.setContentsMargins(0, 0, 0, 0)
        title_icon_layout.setSpacing(2)

        self.title_label = QLabel("EyeShield")
        title_label = self.title_label
        title_label.setObjectName("appTitle")
        title_label.setStyleSheet("color: #007bff; font-size: 20px; font-weight: 700; text-decoration: none;")
        self._apply_title_label_font(title_label)
        title_label.setFixedWidth(118)
        if self._brand_title_path and os.path.isfile(self._brand_title_path):
            title_pixmap = QPixmap(self._brand_title_path).scaled(
                QSize(118, 32), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            if not title_pixmap.isNull():
                title_label.setText("")
                title_label.setPixmap(title_pixmap)
        title_icon_layout.addWidget(title_label)

        icon_label = QLabel()
        self.nav_icon_label = icon_label
        self._icon_path = _icon_path
        icon_pixmap = QPixmap()
        if self._brand_logo_path and self._brand_logo_path.lower().endswith(".svg"):
            icon_pixmap = self._load_svg_pixmap_colored(self._brand_logo_path, "#007bff", 256)
        elif self._brand_logo_path:
            icon_pixmap = QPixmap(self._brand_logo_path)
        if icon_pixmap.isNull():
            icon_pixmap = self._load_svg_pixmap_colored(_icon_path, "#007bff", 256)
        icon_pixmap = icon_pixmap.scaled(QSize(38, 38), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background: transparent;")
        title_icon_layout.addWidget(icon_label)

        self.title_icon_container = title_icon_container
        nav_layout.addWidget(title_icon_container)
        nav_layout.addStretch(1)

        # Navigation buttons with icons and small text labels below
        def nav_button_with_label(icon_path, text):
            w = QWidget()
            w.setFixedSize(60, 66)
            w.setStyleSheet("QWidget { background: transparent; }")
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 2, 0, 2)
            v.setSpacing(2)

            btn = QPushButton("")
            btn.setProperty("navIconPath", icon_path)
            btn.setStyleSheet(self.get_nav_button_style(icon_only=True))
            btn.setFixedSize(50, 40)
            btn.setIconSize(QSize(24, 24))

            label = QLabel(text)
            label.setAlignment(Qt.AlignHCenter)
            label.setFixedWidth(60)
            label.setWordWrap(True)
            label.setFont(EyeShieldApp._make_nav_font(8))
            if str(self.role or "").strip().lower() == "admin":
                label.setFont(QFont("Segoe UI", 8))
            label.setStyleSheet("font-size: 10px; color: #495057; margin-top: 0px; text-decoration: none; border: none;")

            v.addWidget(btn, 0, Qt.AlignHCenter)
            v.addWidget(label, 0, Qt.AlignHCenter)
            return w, btn, label

        navs = [
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "dashboard.svg"), os.path.join(icons_dir, "dasboard.svg")),
                "label": "Dashboard",
                "page_index": 0,
                "requires_admin": False,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "screening.svg")),
                "label": "Screening",
                "page_index": 1,
                "requires_admin": False,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "camera.svg")),
                "label": "Camera",
                "page_index": 2,
                "requires_admin": False,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "reports.svg")),
                "label": "Reports",
                "page_index": 3,
                "requires_admin": False,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "users.svg")),
                "label": "Users",
                "display_label": "Users",
                "page_index": 4,
                "nav_key": "users",
                "requires_admin": True,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "activity_log.svg")),
                "label": "Activity Log",
                "display_label": "Activity\nLog",
                "page_index": 8,
                "requires_admin": True,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "trusted referred hospitals.svg")),
                "label": "Trusted Referrals",
                "display_label": "Trusted\nReferrals",
                "page_index": 9,
                "nav_key": "trusted_referrals",
                "requires_admin": True,
            },
            {
                "icon": self._resolve_existing_path(
                    os.path.join(icons_dir, "refferal_assignments.svg"),
                    os.path.join(icons_dir, "referral_assignments.svg"),
                    os.path.join(icons_dir, "referral.svg"),
                ),
                "label": "Referrals",
                "page_index": 7,
                "requires_admin": False,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "settings.svg")),
                "label": "Settings",
                "page_index": 5,
                "requires_admin": False,
            },
            {
                "icon": self._resolve_existing_path(os.path.join(icons_dir, "help.svg")),
                "label": "Help",
                "page_index": 6,
                "requires_admin": False,
            },
        ]
        nav_widgets = []
        nav_buttons = []
        nav_labels = []
        nav_label_originals = []
        for nav_item in navs:
            if nav_item["page_index"] not in self.allowed_pages:
                continue
            w, btn, label = nav_button_with_label(nav_item["icon"], nav_item.get("display_label", nav_item["label"]))
            btn.setProperty("pageIndex", nav_item["page_index"])
            btn.setProperty("navKey", nav_item.get("nav_key", nav_item["label"]))
            label.setProperty("pageIndex", nav_item["page_index"])

            # Seed icon immediately so first paint never shows a missing nav icon.
            self._set_button_svg_icon(btn, nav_item["icon"], "#495057", QSize(24, 24))

            nav_layout.addWidget(w)
            nav_layout.addStretch(1)
            nav_widgets.append(w)
            nav_buttons.append(btn)
            nav_labels.append(label)
            nav_label_originals.append(nav_item["label"])

        self.nav_buttons = nav_buttons
        self.nav_labels = nav_labels
        self.nav_widgets = nav_widgets
        self._nav_label_originals = nav_label_originals

        logout_btn = QPushButton("")
        self.logout_btn = logout_btn
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setFixedSize(44, 44)
        logout_btn.setIconSize(QSize(20, 20))
        logout_btn.setToolTip("Shutdown / Log out")
        logout_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: 1px solid #bb2d3b;
                border-radius: 8px;
                padding: 0px;
                font-size: 18px;
                font-weight: 600;
                text-decoration: none;
            }
            QPushButton:hover { background: #c82333; }
            QPushButton:focus { outline: none; border: 1px solid #bb2d3b; }
        """)
        self._logout_icon_path = self._resolve_existing_path(os.path.join(icons_dir, "logout.svg"))
        self._update_logout_icon()
        logout_btn.clicked.connect(self.handle_logout)
        nav_layout.addWidget(logout_btn)

        for button in nav_buttons:
            page_index = int(button.property("pageIndex"))
            nav_key = str(button.property("navKey") or "")
            button.clicked.connect(lambda checked=False, idx=page_index, key=nav_key: self._navigate_to(idx, nav_key=key))

        # (All navigation button connections are now handled via nav_buttons list above)

        root_layout.addWidget(nav_bar)

        # Main content area
        main = QWidget()
        main.setStyleSheet("background: #f8f9fa;")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.pages = QStackedWidget()

        # Create main pages first so dashboard can query live data
        self.screening_page = ScreeningPage()
        self.camera_page = CameraPage()
        self.reports_page = ReportsPage(
            self.username,
            self.role,
            display_name=self.display_name,
            specialization=self.specialization,
        )
        self.reports_page.records_changed_callback = self.refresh_dashboard
        self.users_page = UsersPage()
        self.activity_log_page = ActivityLogPage()
        self.settings_page = SettingsPage()
        self.help_support_page = HelpSupportPage()
        self.referrals_page = self.create_referrals_page()
        self.trusted_hospitals_page = TrustedHospitalsPage()

        # Dashboard is created after the other pages so it can be refreshed
        self.dashboard_page = self.create_dashboard_page()

        self.users_page.parent_app = self
        self.activity_log_page.parent_app = self

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.screening_page)
        self.pages.addWidget(self.camera_page)
        self.pages.addWidget(self.reports_page)
        self.pages.addWidget(self.users_page)
        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.help_support_page)
        self.pages.addWidget(self.referrals_page)
        self.pages.addWidget(self.activity_log_page)
        self.pages.addWidget(self.trusted_hospitals_page)
        self.pages.currentChanged.connect(self._on_page_changed)

        main_layout.addWidget(self.pages)
        root_layout.addWidget(main)
        self.setCentralWidget(root)

        self._save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self._save_shortcut.activated.connect(self._global_save_shortcut)

        self.refresh_dashboard()
        default_page_index = self._default_page_index()
        self._active_nav_key = self._default_nav_key_for_page(default_page_index)
        self.pages.setCurrentIndex(default_page_index)
        self._set_active_nav(self.pages.currentIndex())

        # Ensure nav bar styles are correct for the initial theme
        self._apply_nav_theme(False)
        # Re-apply active state after theme bootstrap so startup icons/buttons are visible.
        self._set_active_nav(self.pages.currentIndex())

        # Apply saved theme from settings (must run after all pages are parented)
        saved_theme = self.settings_page.theme_combo.currentText()
        if saved_theme == "Dark":
            self.apply_theme("Dark")

        # Apply saved language to all tabs
        saved_lang = self.settings_page.lang_combo.currentText()
        if saved_lang != "English":
            self.apply_language(saved_lang)

        self._setup_inactivity_timeout()
        self._setup_dashboard_clock()

        # Check for pending referrals and show notification if clinician
        if self.role == "clinician":
            QTimer.singleShot(500, self._show_pending_referrals_notification)

    def _show_pending_referrals_notification(self):
        """Show notification dialog if clinician has pending referrals"""
        referrals = UserManager.get_pending_referrals(self.username)
        if referrals:
            try:
                from login import PendingReferralsDialog
            except ImportError:
                from .login import PendingReferralsDialog
            
            dialog = PendingReferralsDialog(self.username, referrals, self)
            result = dialog.exec()
            if result == 1:  # Accept button clicked
                # Mark all pending referrals as viewed
                for referral in referrals:
                    UserManager.update_referral_status(referral["referral_id"], "viewed", self.username)
                if getattr(dialog, "go_to_referrals", False):
                    self._navigate_to(7)

    @classmethod
    def _allowed_pages_for_role(cls, role: str) -> set[int]:
        return set(cls.ROLE_PAGE_ACCESS.get(str(role or "").lower(), cls.ROLE_PAGE_ACCESS["viewer"]))

    def _is_page_allowed(self, index: int) -> bool:
        return index in self.allowed_pages

    def _default_page_index(self) -> int:
        return 0 if 0 in self.allowed_pages else min(self.allowed_pages)

    @staticmethod
    def _load_svg_pixmap(svg_path: str, size: int = 64) -> QPixmap:
        """Render an SVG file to a QPixmap at the requested size."""
        renderer = QSvgRenderer(svg_path)
        if not renderer.isValid():
            return QPixmap()
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return QPixmap.fromImage(image)

    @staticmethod
    def _load_svg_pixmap_colored(svg_path: str, color: str, size: int = 64) -> QPixmap:
        """Render an SVG with all black strokes/fills replaced by the given color."""
        try:
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_text = f.read()
        except OSError:
            return QPixmap()

        def _replace_paint(match: re.Match) -> str:
            attr = match.group(1)
            value = match.group(2)
            if value.lower() in {"none", "transparent"}:
                return match.group(0)
            return f'{attr}="{color}"'

        svg_text = re.sub(r'(fill|stroke)=["\']([^"\']+)["\']', _replace_paint, svg_text, flags=re.IGNORECASE)

        data = QByteArray(svg_text.encode("utf-8"))
        renderer = QSvgRenderer(data)
        if not renderer.isValid():
            return QPixmap()
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return QPixmap.fromImage(image)

    @staticmethod
    def _resolve_existing_path(*paths: str) -> str:
        """Return the first existing path, or the first candidate as fallback."""
        for path in paths:
            if path and os.path.exists(path):
                return path
        return paths[0] if paths else ""

    def _set_button_svg_icon(self, button: QPushButton, svg_path: str, color: str, size: QSize):
        """Apply a recolored SVG icon to a button."""
        if not svg_path:
            button.setIcon(QIcon())
            return
        is_users_icon = os.path.basename(str(svg_path or "")).lower() == "users.svg"
        pixmap = self._load_svg_pixmap_colored(svg_path, color, 256)
        if is_users_icon and not self._pixmap_has_visible_pixels(pixmap):
            pixmap = QPixmap()
        if pixmap.isNull():
            # Fallback: rasterize first, then tint non-transparent pixels so icons remain visible.
            base_pixmap = self._load_svg_pixmap(svg_path, 256)
            if not base_pixmap.isNull():
                pixmap = self._tint_pixmap(base_pixmap, color)
                if is_users_icon and not self._pixmap_has_visible_pixels(pixmap):
                    pixmap = QPixmap()
            if pixmap.isNull() and is_users_icon:
                pixmap = self._build_users_fallback_pixmap(color, 256)
            if pixmap.isNull():
                # Last-resort fallback to native loading.
                button.setIcon(QIcon(svg_path))
                button.setIconSize(size)
                return
        button.setIcon(QIcon(pixmap))
        button.setIconSize(size)

    @staticmethod
    def _pixmap_has_visible_pixels(pixmap: QPixmap, min_alpha: int = 24, min_coverage: float = 0.008) -> bool:
        if pixmap.isNull():
            return False
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        width = image.width()
        height = image.height()
        if width <= 0 or height <= 0:
            return False
        visible = 0
        total = width * height
        for y in range(height):
            for x in range(width):
                if image.pixelColor(x, y).alpha() >= min_alpha:
                    visible += 1
        return (visible / float(total)) >= float(min_coverage)

    @staticmethod
    def _build_users_fallback_pixmap(color: str, size: int = 64) -> QPixmap:
        """Draw a simple users glyph as a hard fallback when SVG rendering is unreliable."""
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))

        # Main avatar
        painter.drawEllipse(int(size * 0.34), int(size * 0.17), int(size * 0.32), int(size * 0.32))
        painter.drawRoundedRect(int(size * 0.20), int(size * 0.52), int(size * 0.60), int(size * 0.28), 12, 12)

        # Secondary avatar
        painter.drawEllipse(int(size * 0.10), int(size * 0.27), int(size * 0.22), int(size * 0.22))
        painter.drawRoundedRect(int(size * 0.06), int(size * 0.58), int(size * 0.28), int(size * 0.19), 8, 8)

        painter.end()
        return QPixmap.fromImage(image)

    @staticmethod
    def _tint_pixmap(source: QPixmap, color: str) -> QPixmap:
        """Tint a source pixmap using SourceIn composition to preserve alpha shape."""
        if source.isNull():
            return QPixmap()
        tinted = QPixmap(source.size())
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return tinted

    def _refresh_nav_button_icons(self, active_index: int):
        """Recolor navigation SVG icons to match active/inactive and theme state."""
        if not hasattr(self, "nav_buttons"):
            return
        dark = getattr(self, "_dark_mode", False)
        active_color = "#89b4fa" if dark else "#1d5fa8"
        inactive_color = "#a6adc8" if dark else "#495057"
        disabled_color = "#6c7086" if dark else "#adb5bd"
        icon_size = QSize(24, 24)
        for btn in self.nav_buttons:
            icon_path = btn.property("navIconPath") or ""
            if not btn.isEnabled():
                color = disabled_color
            elif self._is_nav_button_active(btn, active_index):
                color = active_color
            else:
                color = inactive_color
            self._set_button_svg_icon(btn, icon_path, color, icon_size)

    def _default_nav_key_for_page(self, index: int) -> str:
        if not hasattr(self, "nav_buttons"):
            return ""
        for btn in self.nav_buttons:
            if int(btn.property("pageIndex") or -1) == index:
                return str(btn.property("navKey") or "")
        return ""

    def _is_nav_button_active(self, button: QPushButton, active_index: int) -> bool:
        btn_index = int(button.property("pageIndex") or -1)
        if btn_index != active_index:
            return False
        same_index_buttons = [b for b in self.nav_buttons if int(b.property("pageIndex") or -1) == active_index]
        if len(same_index_buttons) <= 1:
            return True
        active_key = str(getattr(self, "_active_nav_key", "") or "").strip().lower()
        if not active_key:
            return button is same_index_buttons[0]
        return str(button.property("navKey") or "").strip().lower() == active_key

    @staticmethod
    def _apply_title_label_font(label):
        title_font = QFont("Segoe UI Variable", 14)
        title_font.setBold(True)
        title_font.setUnderline(False)
        label.setFont(title_font)

    @staticmethod
    def _make_nav_font(size: int) -> QFont:
        font = QFont("Segoe UI Variable", size)
        font.setUnderline(False)
        font.setStrikeOut(False)
        return font

    def _update_logout_icon(self):
        """Render the logout SVG icon using white for the red button."""
        if hasattr(self, "logout_btn"):
            self._set_button_svg_icon(self.logout_btn, getattr(self, "_logout_icon_path", ""), "#ffffff", QSize(20, 20))

    def _apply_nav_theme(self, dark: bool):
        """Explicitly re-apply nav bar styles so sizes never change between themes."""
        if dark:
            nav_bg       = "background: #181825; border-bottom: 1px solid #45475a;"
            title_style  = "color: #89b4fa; font-size: 20px; font-weight: 700; text-decoration: none;"
            user_style   = (
                "color: #cdd6f4; background: #313244; border: 1px solid #45475a;"
                "border-radius: 12px; font-size: 12px; font-weight: 600;"
                "padding: 2px 8px; margin-left: 12px; margin-right: 8px;"
            )
            inactive_lbl = "font-size: 10px; color: #a6adc8; margin-top: 0px; text-decoration: none; border: none;"
        else:
            nav_bg       = "background: #f8f9fa; border-bottom: 1px solid #dee2e6;"
            title_style  = "color: #007bff; font-size: 20px; font-weight: 700; text-decoration: none;"
            user_style   = (
                "color: #007bff; background: #e8f0fe; border: 1px solid #b8d0f7;"
                "border-radius: 12px; font-size: 12px; font-weight: 600;"
                "padding: 2px 8px; margin-left: 12px; margin-right: 8px;"
            )
            inactive_lbl = "font-size: 10px; color: #495057; margin-top: 0px; text-decoration: none; border: none;"

        if hasattr(self, "nav_bar"):
            self.nav_bar.setFixedHeight(78)
            self.nav_bar.setStyleSheet(f"QWidget#navBar {{ {nav_bg} }}")
        if hasattr(self, "title_icon_container"):
            self.title_icon_container.setFixedSize(165, 70)
            self.title_icon_container.setStyleSheet("background: transparent;")
        if hasattr(self, "title_label"):
            self.title_label.setFixedWidth(118)
            self.title_label.setStyleSheet(title_style)
            self._apply_title_label_font(self.title_label)
        if hasattr(self, "nav_icon_label"):
            self.nav_icon_label.setFixedSize(38, 38)
            self.nav_icon_label.setAlignment(Qt.AlignCenter)
            self.nav_icon_label.setStyleSheet("background: transparent;")
        if hasattr(self, "user_info_label"):
            self.user_info_label.setStyleSheet(user_style)

        # Transparent container so nav-bar background always shows through
        # Also re-assert fixed sizes so layout cannot shift
        if hasattr(self, "nav_widgets"):
            for w in self.nav_widgets:
                w.setFixedSize(60, 66)
                w.setStyleSheet("QWidget { background: transparent; }")

        # Re-apply button QSS so nav buttons stay visually consistent across theme switches
        btn_font = self._make_nav_font(14)
        if hasattr(self, "nav_buttons"):
            for btn in self.nav_buttons:
                btn.setFixedSize(50, 40)
                if btn.isEnabled():
                    btn.setStyleSheet(self.get_nav_button_style(icon_only=True))
                    btn.setFont(btn_font)
            active_index = self.pages.currentIndex() if hasattr(self, "pages") else 0
            self._refresh_nav_button_icons(active_index)
        self._update_logout_icon()

        # Re-apply label QSS + fresh QFont
        lbl_font = self._make_nav_font(8)
        if hasattr(self, "nav_labels"):
            for lbl in self.nav_labels:
                lbl.setStyleSheet(inactive_lbl)
                lbl.setFont(lbl_font)

    def _update_nav_icon(self, dark: bool):
        """Re-render the nav bar icon to match the current theme."""
        if not hasattr(self, "nav_icon_label"):
            return
        color = "#cdd6f4" if dark else "#007bff"
        pixmap = QPixmap()
        logo_path = getattr(self, "_brand_logo_path", "")
        if logo_path and logo_path.lower().endswith(".svg"):
            pixmap = self._load_svg_pixmap_colored(logo_path, color, 256)
        elif logo_path:
            pixmap = QPixmap(logo_path)
        elif hasattr(self, "_icon_path"):
            pixmap = self._load_svg_pixmap_colored(self._icon_path, color, 256)

        pixmap = pixmap.scaled(QSize(38, 38), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not pixmap.isNull():
            self.nav_icon_label.setPixmap(pixmap)

    # Sidebar removed; navigation is now in the top bar

    def _is_screening_navigation_locked(self) -> bool:
        return bool(
            hasattr(self, "screening_page")
            and hasattr(self.screening_page, "is_navigation_locked")
            and self.screening_page.is_navigation_locked()
        )

    def _refresh_navigation_lock(self):
        if not hasattr(self, "nav_buttons"):
            return
        locked = self._is_screening_navigation_locked()
        for btn in self.nav_buttons:
            page_index = int(btn.property("pageIndex") or -1)
            btn.setEnabled((not locked) or page_index == 1)
        current_index = self.pages.currentIndex() if hasattr(self, "pages") else 0
        self._set_active_nav(current_index)

    def _navigate_to(self, index, show_denied_message=True, nav_key=""):
        if self._is_screening_navigation_locked() and index != 1:
            if show_denied_message:
                QMessageBox.information(
                    self,
                    "Screening In Progress",
                    "Please wait for the image analysis to finish before changing tabs.",
                )
            if hasattr(self, "pages"):
                self.pages.setCurrentIndex(1)
                self._active_nav_key = self._default_nav_key_for_page(1)
                self._set_active_nav(1)
            return
        if index == 2 and hasattr(self, "camera_page") and hasattr(self, "screening_page"):
            has_context = True
            if hasattr(self.camera_page, "has_active_screening_session"):
                has_context = bool(self.camera_page.has_active_screening_session())
            elif hasattr(self.camera_page, "has_required_capture_context"):
                has_context = bool(self.camera_page.has_required_capture_context())
            if not has_context:
                response = QMessageBox.question(
                    self,
                    "Screening Context Required",
                    "No patient screening context was found for Camera capture.\n\n"
                    "Go to Screening first to select patient and eye?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if response == QMessageBox.StandardButton.Yes:
                    self._active_nav_key = self._default_nav_key_for_page(1)
                    self.pages.setCurrentIndex(1)
                    self._set_active_nav(1)
                else:
                    current_index = int(self.pages.currentIndex()) if hasattr(self, "pages") else 0
                    self._active_nav_key = self._default_nav_key_for_page(current_index)
                    self._set_active_nav(current_index)
                return
        if not self._is_page_allowed(index):
            if show_denied_message:
                QMessageBox.warning(self, "Access Denied", "Your account role cannot access this page.")
            if hasattr(self, "pages"):
                current_index = int(self.pages.currentIndex())
                self._active_nav_key = self._default_nav_key_for_page(current_index)
                self._set_active_nav(current_index)
            return
        self._active_nav_key = str(nav_key or self._default_nav_key_for_page(index) or "")
        self.pages.setCurrentIndex(index)
        # Force immediate refresh so same-index nav targets (Users/Activity Log)
        # never leave a stale active background when index does not change.
        self._set_active_nav(self.pages.currentIndex())
        QTimer.singleShot(0, lambda: self._set_active_nav(self.pages.currentIndex()))

    def _global_save_shortcut(self):
        if not hasattr(self, "pages") or not hasattr(self, "screening_page"):
            return
        if self.pages.currentIndex() != 1:
            return
        if hasattr(self.screening_page, "stacked_widget") and self.screening_page.stacked_widget.currentIndex() == 1:
            if hasattr(self.screening_page, "results_page") and hasattr(self.screening_page.results_page, "save_patient"):
                self.screening_page.results_page.save_patient()

    def _on_page_changed(self, index):
        if self._is_screening_navigation_locked() and index != 1:
            self.pages.setCurrentIndex(1)
            self._active_nav_key = self._default_nav_key_for_page(1)
            self._set_active_nav(1)
            return
        if not self._is_page_allowed(index):
            fallback_index = self._default_page_index()
            self.pages.setCurrentIndex(fallback_index)
            self._active_nav_key = self._default_nav_key_for_page(fallback_index)
            self._set_active_nav(fallback_index)
            return
        self._active_nav_key = self._default_nav_key_for_page(index)
        self._set_active_nav(index)
        if index == 2:
            self.camera_page.enter_page()
        else:
            self.camera_page.leave_page()
        if index == 3:
            self.reports_page.refresh_report()
        if index == 0:
            self.refresh_dashboard()
        if index == 7:
            self.refresh_referrals_page()
        if index == 8 and hasattr(self, "activity_log_page") and hasattr(self.activity_log_page, "load_activity_log"):
            self.activity_log_page.load_activity_log()

    def _set_active_nav(self, index: int):
        """Highlight the active navigation button and dim the rest."""
        if not hasattr(self, "nav_buttons"):
            return
        dark = getattr(self, '_dark_mode', False)
        if dark:
            active_btn_style = """
                QPushButton {
                    color: #89b4fa;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 500;
                    background: #313244;
                    text-decoration: none;
                }
                QPushButton:hover { background: #3a3a4f; }
                QPushButton:focus { outline: none; border: 1px solid transparent; }
            """
            inactive_btn_style = """
                QPushButton {
                    color: #a6adc8;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 500;
                    background: transparent;
                    text-decoration: none;
                }
                QPushButton:hover {
                    background: #45475a;
                    color: #89b4fa;
                }
                QPushButton:focus { outline: none; border: 1px solid transparent; }
            """
            active_label = "font-size: 10px; color: #89b4fa; margin-top: 0px; text-decoration: none; border: none;"
            inactive_label = "font-size: 10px; color: #a6adc8; margin-top: 0px; text-decoration: none; border: none;"
            disabled_label = "font-size: 10px; color: #6c7086; margin-top: 0px; text-decoration: none; border: none;"
        else:
            active_btn_style = """
                QPushButton {
                    color: #1d5fa8;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid #a7ccf7;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 600;
                    background: #deefff;
                    text-decoration: none;
                }
                QPushButton:hover { background: #d1e8ff; }
                QPushButton:pressed { background: #c1dcfb; }
                QPushButton:focus { outline: none; border: 1px solid #86bbea; }
            """
            screening_active_btn_style = """
                QPushButton {
                    color: #14528f;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid #8cbfeb;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 700;
                    background: #d4eaff;
                    text-decoration: none;
                }
                QPushButton:hover { background: #c8e3ff; }
                QPushButton:pressed { background: #b9d8fa; }
                QPushButton:focus { outline: none; border: 1px solid #7cb1e4; }
            """
            inactive_btn_style = self.get_nav_button_style(icon_only=True)
            active_label = "font-size: 10px; color: #1d5fa8; font-weight: 700; margin-top: 0px; text-decoration: none; border: none;"
            screening_active_label = "font-size: 10px; color: #14528f; font-weight: 800; margin-top: 0px; text-decoration: none; border: none;"
            inactive_label = "font-size: 10px; color: #495057; margin-top: 0px; text-decoration: none; border: none;"
            disabled_label = "font-size: 10px; color: #adb5bd; margin-top: 0px; text-decoration: none; border: none;"

        for btn in self.nav_buttons:
            is_active = self._is_nav_button_active(btn, index)
            is_screening_btn = str(btn.property("navKey") or "") == "Screening"
            if is_active:
                if not dark and is_screening_btn and index == 1:
                    btn.setStyleSheet(screening_active_btn_style)
                else:
                    btn.setStyleSheet(active_btn_style)
            elif not btn.isEnabled():
                btn.setStyleSheet(inactive_btn_style)
            elif btn.isEnabled():
                btn.setStyleSheet(inactive_btn_style)
        for i, label in enumerate(self.nav_labels):
            if self._is_nav_button_active(self.nav_buttons[i], index):
                is_screening_label = str(self.nav_buttons[i].property("navKey") or "") == "Screening"
                if not dark and is_screening_label and index == 1:
                    label.setStyleSheet(screening_active_label)
                else:
                    label.setStyleSheet(active_label)
            elif not self.nav_buttons[i].isEnabled():
                label.setStyleSheet(disabled_label)
            elif self.nav_buttons[i].isEnabled():
                label.setStyleSheet(inactive_label)
        self._refresh_nav_button_icons(index)

    def apply_theme(self, theme: str):
        """Apply theme across the entire application while preserving tab layout metrics."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()

        # Widgets that belong to the nav bar — we manage these explicitly in
        # _apply_nav_theme so they must never be wiped or blindly restored.
        nav_protected = set()
        if hasattr(self, "nav_bar"):
            nav_protected.add(id(self.nav_bar))
            for w in self.nav_bar.findChildren(QWidget):
                nav_protected.add(id(w))

        def _strip_color_rules(stylesheet: str) -> str:
            # Keep spacing/size/weight rules intact and strip only color paints
            # so dark mode can recolor without changing layout/text metrics.
            color_props = {
                "color",
                "background",
                "background-color",
                "selection-background-color",
                "alternate-background-color",
                "gridline-color",
                "border-color",
            }
            border_like_props = {
                "border",
                "border-top",
                "border-right",
                "border-bottom",
                "border-left",
                "outline",
            }
            color_token_pattern = re.compile(
                r"(#(?:[0-9a-fA-F]{3,8})\\b|rgba?\([^\)]*\)|hsla?\([^\)]*\))"
            )

            def _rewrite_declaration(match: re.Match) -> str:
                prop = match.group("prop")
                value = match.group("value")
                prop_lower = prop.lower()
                if prop_lower in color_props:
                    return ""
                if prop_lower in border_like_props:
                    if color_token_pattern.search(value):
                        stripped_value = color_token_pattern.sub("", value)
                        stripped_value = re.sub(r"\s+", " ", stripped_value).strip()
                        if not stripped_value:
                            return ""
                        return f"{prop}: {stripped_value};"
                return match.group(0)

            decl_pattern = re.compile(
                r"(?P<prop>[a-zA-Z\-]+)\s*:\s*(?P<value>[^;{}]+)\s*;"
            )
            return decl_pattern.sub(_rewrite_declaration, stylesheet)

        if theme == "Dark":
            if self._dark_mode:
                return
            self._dark_mode = True
            # Lock nav sizes BEFORE the global stylesheet can affect them
            self._apply_nav_theme(True)
            self._saved_styles = {}
            for widget in self.findChildren(QWidget):
                if id(widget) in nav_protected:
                    continue
                if ss := widget.styleSheet():
                    self._saved_styles[id(widget)] = (widget, ss)
                    widget.setStyleSheet(_strip_color_rules(ss))
            app.setStyleSheet(DARK_STYLESHEET)
            # Re-apply after stylesheet to ensure our values win
            self._apply_nav_theme(True)
        else:
            if not self._dark_mode:
                return
            self._dark_mode = False
            # Lock nav sizes BEFORE clearing global stylesheet
            self._apply_nav_theme(False)
            app.setStyleSheet("")
            for _, (widget, ss) in self._saved_styles.items():
                with contextlib.suppress(RuntimeError):
                    widget.setStyleSheet(ss)
            self._saved_styles = {}
            # Re-apply after restore
            self._apply_nav_theme(False)

        # Force layout recalculation on nav bar
        if hasattr(self, "nav_bar"):
            self.nav_bar.updateGeometry()
            self.nav_bar.update()

        current_idx = self.pages.currentIndex()
        self._set_active_nav(current_idx)

        if hasattr(self, "screening_page") and hasattr(self.screening_page, "apply_theme"):
            self.screening_page.apply_theme(theme)

        # Update nav icon for the new theme
        self._update_nav_icon(self._dark_mode)

        # Refresh entire dashboard with correct theme colors
        self.refresh_dashboard()

    def apply_language(self, language: str):
        """Apply the selected language to all tabs and the navigation bar."""
        from translations import get_pack
        self._current_language = language
        pack = get_pack(language)

        # Navigation bar labels
        _nav_key_map = {
            "Dashboard": "nav_dashboard",
            "Screening": "nav_screening",
            "Camera": "nav_camera",
            "Reports": "nav_reports",
            "Users": "nav_users",
            "Activity Log": "usr_log",
            "Settings": "nav_settings",
            "Help": "nav_help",
            "Referrals": "Referrals",
        }
        if hasattr(self, "nav_labels") and hasattr(self, "_nav_label_originals"):
            for label, orig in zip(self.nav_labels, self._nav_label_originals):
                key = _nav_key_map.get(orig, "")
                if key:
                    label.setText(pack.get(key, orig))

        # Dashboard welcome label
        if hasattr(self, "welcome_label"):
            self.welcome_label.setText(f"{pack['dash_welcome']}, {self.display_name}")

        # Dashboard section headers
        if hasattr(self, "_dash_severity_title_lbl"):
            self._dash_severity_title_lbl.setText("SCREENED PATIENTS")
        if hasattr(self, "_dash_recent_title_lbl"):
            self._dash_recent_title_lbl.setText(pack.get("dash_recent", "RECENT SCREENINGS"))

        # KPI card title labels (stored with objectName pattern)
        kpi_map = {
            "kpiTotal": "dash_kpi_total",
        }
        for obj_name, key in kpi_map.items():
            title_w = self.findChild(QLabel, f"{obj_name}_title")
            if title_w:
                title_w.setText(pack[key])

        # Propagate to all sub-pages
        for page in (
            self.camera_page,
            self.screening_page,
            self.reports_page,
            self.users_page,
            self.activity_log_page,
            self.help_support_page,
        ):
            if hasattr(page, "apply_language"):
                page.apply_language(language)

        # Refresh dashboard dynamic content
        self.refresh_dashboard()

    def closeEvent(self, event):
        """Ask for confirmation before closing the application."""
        if getattr(self, '_logging_out', False):
            event.accept()
            return
        if hasattr(self, "screening_page") and hasattr(self.screening_page, "has_unsaved_result"):
            if self.screening_page.has_unsaved_result():
                box = QMessageBox(self)
                box.setWindowTitle("Unsaved Results")
                box.setIcon(QMessageBox.Icon.Warning)
                box.setText("You have unsaved results. Close anyway?")
                save_close_btn = box.addButton("Save and Close", QMessageBox.ButtonRole.AcceptRole)
                close_btn = box.addButton("Close Without Saving", QMessageBox.ButtonRole.DestructiveRole)
                cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(cancel_btn)
                box.exec()

                chosen = box.clickedButton()
                if chosen == save_close_btn:
                    if hasattr(self.screening_page, "save_screening"):
                        result = self.screening_page.save_screening(reset_after=False)
                        if isinstance(result, dict) and result.get("status") == "saved":
                            event.accept()
                        else:
                            event.ignore()
                    else:
                        event.ignore()
                    return
                if chosen == close_btn:
                    event.accept()
                else:
                    event.ignore()
                return
        reply = QMessageBox.question(
            self,
            "Quit EyeShield",
            "Are you sure you want to quit EyeShield?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    def handle_logout(self):
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            import user_store
            user_store.log_activity_event(
                self.username,
                "LOGOUT",
                metadata={"source": "manual"},
                action_text="Logout",
            )
        except Exception:
            pass

        from login import LoginWindow
        self._logging_out = True
        self.login = LoginWindow()
        self.login.show()
        self.close()

    def _setup_inactivity_timeout(self):
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.timeout.connect(self._on_inactivity_timeout)

        self._inactivity_warning_timer = QTimer(self)
        self._inactivity_warning_timer.setInterval(1000)
        self._inactivity_warning_timer.timeout.connect(self._tick_inactivity_warning)

        runtime_enabled = bool(self.settings_page.auto_logout_check.isChecked())
        runtime_minutes = int(self.settings_page.timeout_spin.value())
        runtime_warning_seconds = int(getattr(self.settings_page, "warning_spin", None).value()) if hasattr(self.settings_page, "warning_spin") else 30
        if hasattr(self.settings_page, "get_runtime_inactivity_settings"):
            runtime_enabled, runtime_minutes, runtime_warning_seconds = self.settings_page.get_runtime_inactivity_settings()

        self.apply_inactivity_settings(runtime_enabled, runtime_minutes, runtime_warning_seconds)

        app = QGuiApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def apply_inactivity_settings(self, enabled: bool, timeout_minutes: int, warning_seconds: int = 30):
        self._inactivity_timeout_enabled = bool(enabled)
        self._inactivity_timeout_minutes = max(1, int(timeout_minutes or 1))
        self._inactivity_warning_seconds = max(10, min(300, int(warning_seconds or 30)))
        self._dismiss_inactivity_warning(restart_timer=False)
        if self._inactivity_timeout_enabled:
            self._restart_inactivity_timer()
        elif hasattr(self, "_inactivity_timer"):
            self._inactivity_timer.stop()

    def _restart_inactivity_timer(self):
        if not hasattr(self, "_inactivity_timer"):
            return
        if not self._inactivity_timeout_enabled:
            return
        self._inactivity_timer.start(self._inactivity_timeout_minutes * 60 * 1000)

    def _on_inactivity_timeout(self):
        if not self._inactivity_timeout_enabled:
            return
        if not self.isVisible():
            self._restart_inactivity_timer()
            return
        self._show_inactivity_warning()

    def _show_inactivity_warning(self):
        if self._inactivity_warning_active:
            return

        self._inactivity_warning_active = True
        self._inactivity_warning_remaining_sec = max(10, int(self._inactivity_warning_seconds or 30))

        box = QDialog(self)
        box.setObjectName("inactivityWarningToast")
        box.setWindowTitle("Inactivity Warning")
        box.setModal(False)
        box.setWindowModality(Qt.WindowModality.NonModal)
        box.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        box.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        box.setStyleSheet(
            """
            QDialog#inactivityWarningToast {
                background: #fff4e5;
                border: 1px solid #f59e0b;
                border-radius: 12px;
            }
            QLabel#warningTitle {
                color: #92400e;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#warningBody {
                color: #7c2d12;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#warningStayBtn {
                background: #ffffff;
                border: 1px solid #f59e0b;
                border-radius: 8px;
                color: #92400e;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#warningStayBtn:hover {
                background: #fff7ed;
            }
            QPushButton#warningLogoutBtn {
                background: #f59e0b;
                border: 1px solid #d97706;
                border-radius: 8px;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#warningLogoutBtn:hover {
                background: #d97706;
            }
            """
        )

        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("Inactivity warning")
        title.setObjectName("warningTitle")
        layout.addWidget(title)

        self._inactivity_warning_text_label = QLabel()
        self._inactivity_warning_text_label.setObjectName("warningBody")
        self._inactivity_warning_text_label.setWordWrap(True)
        layout.addWidget(self._inactivity_warning_text_label)

        actions = QHBoxLayout()
        actions.addStretch()
        stay_btn = QPushButton("Stay Signed In")
        stay_btn.setObjectName("warningStayBtn")
        logout_btn = QPushButton("Log Out Now")
        logout_btn.setObjectName("warningLogoutBtn")
        actions.addWidget(stay_btn)
        actions.addWidget(logout_btn)
        layout.addLayout(actions)

        stay_btn.clicked.connect(self._continue_session_after_warning)
        logout_btn.clicked.connect(self._trigger_auto_logout)
        box.destroyed.connect(lambda *_: self._clear_warning_dialog_reference())

        self._inactivity_warning_dialog = box
        self._refresh_inactivity_warning_text()
        self._play_inactivity_alert_sound(urgent=False)
        if self._inactivity_warning_timer is not None:
            self._inactivity_warning_timer.start()
        box.adjustSize()
        self._position_inactivity_warning()
        box.show()

    def _clear_warning_dialog_reference(self):
        self._inactivity_warning_dialog = None
        self._inactivity_warning_text_label = None

    def _position_inactivity_warning(self):
        if self._inactivity_warning_dialog is None:
            return
        anchor = self.geometry().topRight()
        margin = 16
        x = anchor.x() - self._inactivity_warning_dialog.width() - margin
        y = self.geometry().top() + margin
        self._inactivity_warning_dialog.move(max(0, x), max(0, y))

    def _play_inactivity_alert_sound(self, urgent: bool = False):
        played = False
        if winsound is not None:
            try:
                tone = winsound.MB_ICONHAND if urgent else winsound.MB_ICONEXCLAMATION
                winsound.MessageBeep(tone)
                played = True
            except Exception:
                played = False
        if not played:
            with contextlib.suppress(Exception):
                QApplication.beep()

    def _refresh_inactivity_warning_text(self):
        if self._inactivity_warning_dialog is None or self._inactivity_warning_text_label is None:
            return
        mins = self._inactivity_warning_remaining_sec // 60
        secs = self._inactivity_warning_remaining_sec % 60
        self._inactivity_warning_text_label.setText(
            "No activity detected in your session. "
            f"Automatic logout in {mins:02d}:{secs:02d}."
        )

    def _tick_inactivity_warning(self):
        if not self._inactivity_warning_active:
            if self._inactivity_warning_timer is not None:
                self._inactivity_warning_timer.stop()
            return

        self._inactivity_warning_remaining_sec = max(0, self._inactivity_warning_remaining_sec - 1)
        self._refresh_inactivity_warning_text()
        if self._inactivity_warning_remaining_sec in {20, 10, 5, 4, 3, 2, 1}:
            self._play_inactivity_alert_sound(urgent=self._inactivity_warning_remaining_sec <= 5)
        if self._inactivity_warning_remaining_sec <= 0:
            self._trigger_auto_logout()

    def _dismiss_inactivity_warning(self, restart_timer: bool = True):
        if self._inactivity_warning_timer is not None:
            self._inactivity_warning_timer.stop()
        self._inactivity_warning_active = False
        self._inactivity_warning_remaining_sec = 0
        if self._inactivity_warning_dialog is not None:
            self._inactivity_warning_dialog.close()
            self._inactivity_warning_dialog = None
        self._inactivity_warning_text_label = None
        if restart_timer:
            self._restart_inactivity_timer()

    def _continue_session_after_warning(self):
        self._dismiss_inactivity_warning(restart_timer=True)

    def _trigger_auto_logout(self):
        self._dismiss_inactivity_warning(restart_timer=False)

        try:
            import user_store
            user_store.log_activity_event(
                self.username,
                "LOGOUT",
                metadata={"source": "inactivity_timeout"},
                action_text="Logout (Inactivity Timeout)",
            )
        except Exception:
            pass

        self._logging_out = True
        from login import LoginWindow
        self.login = LoginWindow()
        self.login.show()
        self.close()

    def eventFilter(self, watched, event):
        if hasattr(self, "_inactivity_timer") and self._inactivity_timeout_enabled:
            if self._inactivity_warning_active:
                return super().eventFilter(watched, event)
            event_type = event.type()
            reset_types = {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.MouseMove,
                QEvent.Type.KeyPress,
                QEvent.Type.KeyRelease,
                QEvent.Type.Wheel,
                QEvent.Type.TouchBegin,
                QEvent.Type.TouchUpdate,
                QEvent.Type.TouchEnd,
            }
            if event_type in reset_types and self.isVisible():
                self._restart_inactivity_timer()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_inactivity_warning()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_inactivity_warning()

    @staticmethod
    def _format_dashboard_datetime(now: datetime) -> str:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(EyeShieldApp._ph_now().tzinfo)
        hour = now.strftime("%I").lstrip("0") or "0"
        return f"{now.strftime('%A , %B %d, %Y  -  ')}{hour}:{now.strftime('%M')} {now.strftime('%p').lower()}"

    @staticmethod
    def _ph_now() -> datetime:
        if ZoneInfo is not None:
            try:
                return datetime.now(ZoneInfo("Asia/Manila"))
            except Exception:
                pass
        return datetime.now(timezone(timedelta(hours=8)))

    def _update_dashboard_datetime_label(self):
        if hasattr(self, "dashboard_date_label"):
            self.dashboard_date_label.setText(self._format_dashboard_datetime(self._ph_now()))

    def _setup_dashboard_clock(self):
        self._dashboard_clock_timer = QTimer(self)
        self._dashboard_clock_timer.setInterval(1000)
        self._dashboard_clock_timer.timeout.connect(self._update_dashboard_datetime_label)
        self._dashboard_clock_timer.start()
        self._update_dashboard_datetime_label()

    def create_dashboard_page(self):
        """Create the dashboard page layout."""
        page = QWidget()
        page.setObjectName("dashboardPage")
        page.setStyleSheet("QWidget#dashboardPage { background: #f8f9fa; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Hero header
        hero_card = QWidget()
        hero_card.setObjectName("heroCard")
        hero_card.setMinimumHeight(112)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(12)

        self.welcome_label = QLabel(f"Welcome back, {self.display_name}")
        self.welcome_label.setObjectName("welcomeGreeting")
        self.welcome_label.setStyleSheet(
            "color: #212529; font-size: 25px; font-weight: 700; background: transparent;"
        )

        self.welcome_role_label = QLabel(f"{self.display_title.capitalize()}")
        self.welcome_role_label.setObjectName("welcomeRole")
        self.welcome_role_label.setStyleSheet(
            "color: #6c757d; font-size: 13px; font-weight: 600; background: transparent;"
        )


        self.dashboard_date_label = QLabel("")
        self.dashboard_date_label.setObjectName("dashDate")
        self.dashboard_date_label.setAlignment(Qt.AlignCenter)
        self.dashboard_date_label.setStyleSheet(
            "color: #0f6cbd; font-size: 13px; font-weight: 700; background: transparent;"
        )
        self.dashboard_date_label.setMinimumWidth(250)

        welcome_row = QHBoxLayout()
        welcome_row.setSpacing(8)
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        left_col.addWidget(self.welcome_label)
        left_col.addWidget(self.welcome_role_label)
        left_col.addStretch(1)
        welcome_row.addLayout(left_col)
        welcome_row.addStretch()
        welcome_row.addWidget(self.dashboard_date_label, 0, Qt.AlignVCenter)
        hero_layout.addLayout(welcome_row)
        layout.addWidget(hero_card)

        # Top metrics row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(16)

        def make_kpi_card(object_name, title_text, accent):
            """Build a single KPI card with title and value."""
            card = QWidget()
            card.setObjectName(object_name)
            card.setMinimumHeight(96)
            card.setStyleSheet(f"""
                QWidget#{object_name} {{
                    background: white;
                    border: 1px solid #dee2e6;
                    border-left: 4px solid {accent};
                    border-radius: 10px;
                }}
            """)
            v = QVBoxLayout(card)
            v.setContentsMargins(14, 10, 14, 10)
            v.setSpacing(4)

            title = QLabel(title_text)
            title.setObjectName(f"{object_name}_title")
            title.setStyleSheet(
                "color: #6c757d; font-size: 10px; font-weight: 700;"
                "letter-spacing: 0.7px; text-transform: uppercase; background: transparent;"
            )
            value = QLabel("—")
            value.setObjectName(f"{object_name}_value")
            value.setStyleSheet("font-size: 24px; font-weight: 800; color: #212529; background: transparent;")

            v.addWidget(title)
            v.addWidget(value)
            v.addStretch()
            return card, value

        # Card 1: Total Screenings
        card_total, self.total_screenings_value = \
            make_kpi_card("kpiTotal", "TOTAL SCREENINGS", "#0066cc")

        # Card 2: No DR Cases
        card_patients, self.unique_patients_value = \
            make_kpi_card("kpiPatients", "NO DR CASES", "#2e7d32")

        # Card 3: Abnormal Cases
        card_abnormal, self.abnormal_cases_value = \
            make_kpi_card("kpiAbnormal", "ABNORMAL CASES", "#f59e0b")

        # Card 4: High Risk Cases
        card_high_risk, self.high_risk_cases_value = \
            make_kpi_card("kpiHighRisk", "HIGH RISK CASES", "#dc3545")

        kpi_row.addWidget(card_total, 1)
        kpi_row.addWidget(card_patients, 1)
        kpi_row.addWidget(card_abnormal, 1)
        kpi_row.addWidget(card_high_risk, 1)
        layout.addLayout(kpi_row)

        # Main content area
        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        # Left: Severity distribution chart card
        severity_card = QWidget()
        severity_card.setObjectName("severityCard")
        severity_card.setMinimumHeight(410)
        severity_card.setStyleSheet("""
            QWidget#severityCard {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 12px;
            }
        """)
        severity_v = QVBoxLayout(severity_card)
        severity_v.setContentsMargins(18, 10, 18, 16)
        severity_v.setSpacing(8)

        self._dash_severity_title_lbl = QLabel("SCREENED PATIENTS")
        self._dash_severity_title_lbl.setStyleSheet(
            "color: #6c757d; font-size: 10px; font-weight: 700;"
            "letter-spacing: 0.9px; text-transform: uppercase; background: transparent;"
        )
        severity_v.addWidget(self._dash_severity_title_lbl)

        self._dash_severity_hint_lbl = QLabel("Distribution by diagnosed severity")
        self._dash_severity_hint_lbl.setStyleSheet(
            "color: #7b8794; font-size: 12px; font-weight: 500; background: transparent;"
        )
        severity_v.addWidget(self._dash_severity_hint_lbl)

        scale_row = QWidget()
        scale_row_layout = QHBoxLayout(scale_row)
        scale_row_layout.setContentsMargins(0, 0, 0, 0)
        scale_row_layout.setSpacing(8)

        scale_left_spacer = QWidget()
        scale_left_spacer.setFixedWidth(124)
        scale_left_spacer.setStyleSheet("background: transparent;")
        scale_row_layout.addWidget(scale_left_spacer)

        scale_bar_spacer = QWidget()
        scale_bar_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        scale_bar_spacer.setStyleSheet("background: transparent;")
        scale_row_layout.addWidget(scale_bar_spacer)

        scale_right_spacer = QWidget()
        scale_right_spacer.setFixedWidth(62)
        scale_right_spacer.setStyleSheet("background: transparent;")
        scale_row_layout.addWidget(scale_right_spacer)

        severity_v.addWidget(scale_row)

        scale_line = QWidget()
        scale_line.setFixedHeight(1)
        scale_line.setStyleSheet("background: #e9ecef;")
        severity_v.addWidget(scale_line)

        self.severity_bars = {}
        self._severity_order = [
            "No DR",
            "Mild DR",
            "Moderate DR",
            "Severe DR",
            "Proliferative DR",
        ]
        for level in self._severity_order:
            row = QWidget()
            row.setMinimumHeight(40)
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            level_lbl = QLabel(level)
            level_lbl.setFixedWidth(124)
            level_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #495057; background: transparent;")

            bar = QProgressBar()
            bar.setMinimum(0)
            bar.setMaximum(100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(18)
            bar.setMinimumWidth(220)
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar.setFormat("")

            count_lbl = QLabel("0")
            count_lbl.setFixedWidth(62)
            count_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_lbl.setStyleSheet(
                "font-size: 15px; font-weight: 800; color: #212529; background: transparent;"
                "padding-right: 4px;"
            )

            row_layout.addWidget(level_lbl)
            row_layout.addWidget(bar)
            row_layout.addWidget(count_lbl)
            severity_v.addWidget(row, 1)
            self.severity_bars[level] = (bar, count_lbl)

        content_row.addWidget(severity_card, 7)

        # Right sidebar: My Availability & Recent Screenings
        sidebar = QWidget()
        sidebar.setObjectName("dashSidebar")
        sidebar.setStyleSheet("QWidget#dashSidebar { background: transparent; }")
        sidebar_v = QVBoxLayout(sidebar)
        sidebar_v.setContentsMargins(0, 0, 0, 0)
        sidebar_v.setSpacing(12)

        # My Availability
        availability_card = QWidget()
        availability_card.setObjectName("availabilityCard")
        availability_v = QVBoxLayout(availability_card)
        availability_v.setContentsMargins(16, 12, 16, 12)
        availability_v.setSpacing(8)

        self._dash_availability_title_lbl = QLabel("MY AVAILABILITY")
        availability_v.addWidget(self._dash_availability_title_lbl)

        self.availability_days_label = QLabel("Days: Not set")
        self.availability_days_label.setWordWrap(True)
        availability_v.addWidget(self.availability_days_label)

        self.availability_time_label = QLabel("Hours: Not set")
        self.availability_time_label.setWordWrap(True)
        availability_v.addWidget(self.availability_time_label)

        self.availability_updated_label = QLabel("Update this from Users > Edit Availability")
        self.availability_updated_label.setWordWrap(True)
        availability_v.addWidget(self.availability_updated_label)

        sidebar_v.addWidget(availability_card)

        # Recent Screenings
        recent_card = QWidget()
        recent_card.setObjectName("recentCard")
        recent_v = QVBoxLayout(recent_card)
        recent_v.setContentsMargins(16, 12, 16, 12)
        recent_v.setSpacing(10)

        self._dash_recent_title_lbl = QLabel("RECENT SCREENINGS")
        recent_v.addWidget(self._dash_recent_title_lbl)

        self.recent_list_layout = QVBoxLayout()
        self.recent_list_layout.setSpacing(8)
        recent_v.addLayout(self.recent_list_layout)
        recent_v.addStretch(1)

        sidebar_v.addWidget(recent_card, 1)
        content_row.addWidget(sidebar, 3)

        layout.addLayout(content_row, 1)
        layout.addStretch(1)

        return page

    def create_referrals_page(self):
        """Create the private referrals page for each signed-in user."""
        page = QWidget()
        page.setObjectName("referralsPage")
        page.setStyleSheet("QWidget#referralsPage { background: #f8f9fa; }")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("REFERRALS")
        title.setStyleSheet("color: #2b3a4a; font-size: 22px; font-weight: 800; background: transparent;")
        layout.addWidget(title)

        subtitle = QLabel("Private referral activity for your account only.")
        subtitle.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(subtitle)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        actions_row.addStretch(1)

        self.referral_inbox_btn = QPushButton("Inbox")
        self.referral_inbox_btn.setCursor(Qt.PointingHandCursor)
        self.referral_inbox_btn.setMinimumHeight(32)
        self.referral_inbox_btn.setStyleSheet(
            "QPushButton {"
            "background: #ffffff; color: #1f2937; border: 1px solid #d1dae6;"
            "border-radius: 7px; padding: 6px 14px; font-weight: 700;"
            "}"
            "QPushButton:hover { background: #f8fafc; border-color: #9fb2cc; }"
        )
        self.referral_inbox_btn.clicked.connect(self._open_referral_inbox_dialog)
        actions_row.addWidget(self.referral_inbox_btn)
        layout.addLayout(actions_row)

        split_row = QHBoxLayout()
        split_row.setSpacing(12)

        def build_referral_table() -> QTableWidget:
            table = QTableWidget(0, 6)
            table.setHorizontalHeaderLabels(
                ["Patient", "Status", "Urgency", "Referred By", "Assigned To", "Date of Referral"]
            )
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.setContextMenuPolicy(Qt.CustomContextMenu)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(34)
            header = table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
            table.setStyleSheet(
                """
                QTableWidget {
                    border: 1px solid #e5edf7;
                    border-radius: 8px;
                    gridline-color: #edf2f7;
                    background: #ffffff;
                    alternate-background-color: #f8fbff;
                    color: #1f2937;
                    font-size: 11px;
                }
                QHeaderView::section {
                    background: #f1f5f9;
                    color: #475569;
                    font-weight: 700;
                    font-size: 10px;
                    border: none;
                    border-right: 1px solid #e2e8f0;
                    padding: 6px;
                }
                """
            )
            return table

        assigned_feed_card = QWidget()
        assigned_feed_card.setObjectName("refAssignedFeedCard")
        assigned_feed_card.setStyleSheet(
            "QWidget#refAssignedFeedCard {"
            "background: white; border: 1px solid #dbe3ee; border-radius: 10px;"
            "}"
        )
        assigned_feed_v = QVBoxLayout(assigned_feed_card)
        assigned_feed_v.setContentsMargins(14, 12, 14, 12)
        assigned_feed_v.setSpacing(8)
        assigned_feed_title = QLabel("ASSIGNED TO ME")
        assigned_feed_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; background: transparent;")
        assigned_feed_v.addWidget(assigned_feed_title)
        self.referrals_assigned_table = build_referral_table()
        self.referrals_assigned_table.itemDoubleClicked.connect(
            lambda item: self._handle_referral_table_double_click(item, self.referrals_assigned_table)
        )
        self.referrals_assigned_table.customContextMenuRequested.connect(
            lambda pos: self._show_referral_table_context_menu(self.referrals_assigned_table, pos)
        )
        assigned_feed_v.addWidget(self.referrals_assigned_table)
        split_row.addWidget(assigned_feed_card, 1)

        created_feed_card = QWidget()
        created_feed_card.setObjectName("refCreatedFeedCard")
        created_feed_card.setStyleSheet(
            "QWidget#refCreatedFeedCard {"
            "background: white; border: 1px solid #dbe3ee; border-radius: 10px;"
            "}"
        )
        created_feed_v = QVBoxLayout(created_feed_card)
        created_feed_v.setContentsMargins(14, 12, 14, 12)
        created_feed_v.setSpacing(8)
        created_feed_title = QLabel("CREATED BY ME")
        created_feed_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; background: transparent;")
        created_feed_v.addWidget(created_feed_title)
        self.referrals_created_table = build_referral_table()
        self.referrals_created_table.itemDoubleClicked.connect(
            lambda item: self._handle_referral_table_double_click(item, self.referrals_created_table)
        )
        self.referrals_created_table.customContextMenuRequested.connect(
            lambda pos: self._show_referral_table_context_menu(self.referrals_created_table, pos)
        )
        created_feed_v.addWidget(self.referrals_created_table)
        split_row.addWidget(created_feed_card, 1)

        layout.addLayout(split_row, 1)
        return page

    def refresh_referrals_page(self):
        """Refresh referral activity page with private user data."""
        if not hasattr(self, "referrals_assigned_table") or not hasattr(self, "referrals_created_table"):
            return

        unread_notifications = UserManager.get_unread_referral_notifications(self.username, limit=300)
        unread_count = len(unread_notifications)
        if hasattr(self, "referral_inbox_btn"):
            if unread_count > 0:
                self.referral_inbox_btn.setText(f"Inbox ({unread_count})")
            else:
                self.referral_inbox_btn.setText("Inbox")

        referrals = UserManager.get_user_referrals(self.username, limit=200)
        assigned_referrals = [item for item in referrals if item.get("relation") == "assigned_to_me"]
        created_referrals = [item for item in referrals if item.get("relation") == "created_by_me"]

        def populate_table(table: QTableWidget, rows: list[dict], empty_message: str):
            table.clearContents()
            table.setRowCount(0)
            if not rows:
                table.setRowCount(1)
                empty = QTableWidgetItem(empty_message)
                empty.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(0, 0, empty)
                for col in range(1, table.columnCount()):
                    cell = QTableWidgetItem("")
                    cell.setFlags(Qt.ItemIsEnabled)
                    table.setItem(0, col, cell)
                return

            table_rows = rows[:60]
            table.setRowCount(len(table_rows))
            for row_index, referral in enumerate(table_rows):
                patient_name = str(referral.get("patient_name") or "Unknown Patient").strip() or "Unknown Patient"
                urgency = str(referral.get("urgency") or "normal").capitalize()
                status_raw = str(referral.get("status") or "pending").strip()
                status = status_raw.replace("_", " ").title()
                assigned_at = str(referral.get("assigned_at") or "").strip()
                assigned_by = str(referral.get("assigned_by") or "").strip()
                assigned_to = str(referral.get("assigned_to") or "").strip()
                row_values = [patient_name, status, urgency, assigned_by or "-", assigned_to or "-", assigned_at or "-"]
                for col_index, value in enumerate(row_values):
                    item = QTableWidgetItem(value)
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    if col_index == 0:
                        item.setData(Qt.UserRole, referral)
                    if col_index == 1:
                        normalized = status_raw.lower()
                        if normalized in {"pending", "viewed"}:
                            item.setForeground(QColor("#0e6fcd"))
                        elif normalized in {"in_review", "reassigned", "rereferred"}:
                            item.setForeground(QColor("#b45309"))
                        elif normalized in {"completed", "archived"}:
                            item.setForeground(QColor("#2e7d32"))
                    table.setItem(row_index, col_index, item)
                table.setRowHeight(row_index, 34)

        populate_table(self.referrals_assigned_table, assigned_referrals, "No referrals assigned to you.")
        populate_table(self.referrals_created_table, created_referrals, "No referrals created by you.")

    def _open_referral_details(self, referral: dict):
        patient_name = str(referral.get("patient_name") or "").strip()
        if not patient_name:
            QMessageBox.warning(self, "Referral", "This referral does not contain a valid patient name.")
            return

        referral_id = str(referral.get("referral_id") or "").strip()
        relation = str(referral.get("relation") or "")
        status = str(referral.get("status") or "").lower()
        if referral_id and relation == "assigned_to_me" and status == "pending":
            UserManager.update_referral_status(referral_id, "viewed", self.username)

        self._show_referral_details(patient_name)
        self.refresh_referrals_page()

    def _show_referral_context_menu(self, row_widget: QWidget, referral: dict, local_pos):
        patient_name = str(referral.get("patient_name") or "Unknown Patient").strip() or "Unknown Patient"
        referral_id = str(referral.get("referral_id") or "").strip()
        relation = str(referral.get("relation") or "")

        menu = QMenu(self)
        view_action = menu.addAction("View Details")
        viewed_action = None
        review_action = None
        complete_action = None
        note_action = None
        reassign_action = None

        if relation == "assigned_to_me" and referral_id:
            menu.addSeparator()
            viewed_action = menu.addAction("Mark as Viewed")
            review_action = menu.addAction("Start Review")
            complete_action = menu.addAction("Complete Referral")
            note_action = menu.addAction("Add Clinical Note")
            menu.addSeparator()
            reassign_action = menu.addAction("Reassign Referral")

        chosen = menu.exec(row_widget.mapToGlobal(local_pos))
        if chosen == view_action:
            self._open_referral_details(referral)
            return
        if chosen == viewed_action:
            self._apply_referral_status(referral, "viewed")
            return
        if chosen == review_action:
            self._apply_referral_status(referral, "in_review")
            return
        if chosen == complete_action:
            self._apply_referral_status(referral, "completed", require_note=True)
            return
        if chosen == note_action:
            note, ok = QInputDialog.getMultiLineText(
                self,
                "Clinical Note",
                f"Add note for {patient_name}:",
                "",
            )
            if ok and str(note).strip():
                if UserManager.append_referral_note(referral_id, self.username, note.strip()):
                    QMessageBox.information(self, "Referral", "Clinical note saved.")
                    self.refresh_referrals_page()
                else:
                    QMessageBox.warning(self, "Referral", "Unable to save clinical note.")
            return
        if chosen == reassign_action:
            self._reassign_referral(referral)

    def _referral_for_selected_table_row(self, table: QTableWidget, row_index: int) -> dict | None:
        if not table:
            return None
        if row_index < 0 or row_index >= table.rowCount():
            return None

        patient_item = table.item(row_index, 0)
        if not patient_item:
            return None

        referral = patient_item.data(Qt.UserRole)
        return referral if isinstance(referral, dict) else None

    def _handle_referral_table_double_click(self, item: QTableWidgetItem, table: QTableWidget):
        referral = self._referral_for_selected_table_row(table, item.row())
        if referral:
            self._open_referral_details(referral)

    def _show_referral_table_context_menu(self, table: QTableWidget, local_pos):
        if not table:
            return
        item = table.itemAt(local_pos)
        if not item:
            return
        referral = self._referral_for_selected_table_row(table, item.row())
        if not referral:
            return

        self._show_referral_context_menu(table.viewport(), referral, local_pos)

    def _apply_referral_status(self, referral: dict, new_status: str, require_note: bool = False):
        referral_id = str(referral.get("referral_id") or "").strip()
        if not referral_id:
            QMessageBox.warning(self, "Referral", "Referral ID is missing.")
            return

        note_text = ""
        reason_code = ""
        if require_note:
            taxonomy = UserManager.get_referral_reason_taxonomy()
            completion_reasons = taxonomy.get("completion", {})
            reason_labels = list(completion_reasons.values())
            selected_reason, picked = QInputDialog.getItem(
                self,
                "Completion Reason",
                "Select completion reason:",
                reason_labels,
                0,
                False,
            )
            if not picked or not selected_reason:
                return
            inverse = {label: code for code, label in completion_reasons.items()}
            reason_code = inverse.get(selected_reason, "")
            note_text, ok = QInputDialog.getMultiLineText(
                self,
                "Complete Referral",
                "Provide completion summary (required):",
                "",
            )
            if not ok:
                return
            note_text = str(note_text).strip()
            if not note_text:
                QMessageBox.warning(self, "Referral", "Completion summary is required.")
                return

        if new_status == "completed":
            success = UserManager.update_referral_status_with_reason(
                referral_id=referral_id,
                new_status=new_status,
                actor_username=self.username,
                reason_code=reason_code,
                reason_note=note_text,
            )
        else:
            success = UserManager.update_referral_status(referral_id, new_status, self.username)
        if not success:
            QMessageBox.warning(self, "Referral", "Failed to update referral status.")
            return

        if note_text:
            UserManager.append_referral_note(referral_id, self.username, note_text)

        self.refresh_referrals_page()
        QMessageBox.information(self, "Referral", f"Referral marked as {new_status.replace('_', ' ')}.")

    def _reassign_referral(self, referral: dict):
        referral_id = str(referral.get("referral_id") or "").strip()
        patient_name = str(referral.get("patient_name") or "Unknown Patient").strip() or "Unknown Patient"
        if not referral_id:
            QMessageBox.warning(self, "Referral", "Referral ID is missing.")
            return

        clinicians = UserManager.list_clinicians(exclude_username=self.username)
        if not clinicians:
            QMessageBox.information(self, "Referral", "No other clinicians available for reassignment.")
            return

        options = [f"{item.get('display_name')} (@{item.get('username')})" for item in clinicians]
        selected, ok = QInputDialog.getItem(
            self,
            "Reassign Referral",
            f"Select clinician for {patient_name}:",
            options,
            0,
            False,
        )
        if not ok or not selected:
            return

        index = options.index(selected)
        target = clinicians[index].get("username")

        taxonomy = UserManager.get_referral_reason_taxonomy()
        reassignment_reasons = taxonomy.get("reassignment", {})
        reason_labels = list(reassignment_reasons.values())
        selected_reason, ok = QInputDialog.getItem(
            self,
            "Reassignment Reason",
            "Select reassignment reason:",
            reason_labels,
            0,
            False,
        )
        if not ok or not selected_reason:
            return
        inverse = {label: code for code, label in reassignment_reasons.items()}
        reason_code = inverse.get(selected_reason, "")
        reason, ok = QInputDialog.getMultiLineText(
            self,
            "Reassignment Reason",
            "Additional context (required):",
            "",
        )
        if not ok:
            return
        reason = str(reason).strip()
        if not reason:
            QMessageBox.warning(self, "Referral", "Reassignment reason is required.")
            return

        if UserManager.reassign_referral(referral_id, target, self.username, reason, reason_code):
            QMessageBox.information(self, "Referral", "Referral reassigned successfully.")
            self.refresh_referrals_page()
        else:
            QMessageBox.warning(self, "Referral", "Unable to reassign referral.")

    def _open_referral_inbox_dialog(self):
        notifications = UserManager.get_referral_notifications(self.username, include_read=True, limit=300)
        dialog = QDialog(self)
        dialog.setWindowTitle("Referral Notification Inbox")
        dialog.resize(820, 480)
        v = QVBoxLayout(dialog)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)
        title = QLabel("Referral Notifications")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1f2937;")
        v.addWidget(title)
        if not notifications:
            empty_label = QLabel("No referral messages yet. Messages from clinicians will appear here.")
            empty_label.setWordWrap(True)
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet(
                "padding: 18px; border: 1px dashed #cbd5e1; border-radius: 8px;"
                "color: #64748b; background: #f8fafc; font-size: 13px;"
            )
            v.addWidget(empty_label)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Status", "Title", "Message", "Referral ID", "Created At"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.setRowCount(len(notifications))
        for idx, item in enumerate(notifications):
            status = "Read" if item.get("is_read") else "Unread"
            row_values = [
                status,
                str(item.get("title") or ""),
                str(item.get("message") or ""),
                str(item.get("referral_id") or "-"),
                str(item.get("created_at") or ""),
            ]
            for col, value in enumerate(row_values):
                qitem = QTableWidgetItem(value)
                qitem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                if col == 0 and status == "Unread":
                    qitem.setForeground(QColor("#b45309"))
                table.setItem(idx, col, qitem)
        v.addWidget(table, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        mark_selected_btn = QPushButton("Mark Selected Read")
        close_btn = QPushButton("Close")
        mark_selected_btn.setEnabled(bool(notifications))
        buttons.addWidget(mark_selected_btn)
        buttons.addWidget(close_btn)
        v.addLayout(buttons)

        def _mark_selected():
            row = table.currentRow()
            if row < 0:
                return
            notif_id = notifications[row].get("id")
            if notif_id and UserManager.mark_referral_notification_read(int(notif_id), self.username):
                self.refresh_referrals_page()
                dialog.accept()

        mark_selected_btn.clicked.connect(_mark_selected)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def _mark_all_referral_notifications_read(self):
        updated = UserManager.mark_all_referral_notifications_read(self.username)
        if updated > 0:
            QMessageBox.information(self, "Referral Inbox", f"Marked {updated} notification(s) as read.")
        self.refresh_referrals_page()

    def _show_referral_details(self, patient_name: str):
        """Fetch patient record by name and display referral details with fundus image."""
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, patient_id, name, birthdate, age, sex, contact, eyes,
                       diabetes_type, duration, hba1c, prev_treatment, notes,
                       result, confidence, screened_at, archived_at, archived_by,
                       archive_reason, original_screener_username, original_screener_name,
                       height, weight, bmi, visual_acuity_left, visual_acuity_right,
                       blood_pressure_systolic, blood_pressure_diastolic,
                       fasting_blood_sugar, random_blood_sugar,
                       diabetes_diagnosis_date, treatment_regimen, prev_dr_stage,
                       symptom_blurred_vision, symptom_floaters, symptom_flashes,
                       symptom_vision_loss, source_image_path
                FROM patient_records
                WHERE name = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (patient_name,),
            )
            row = cur.fetchone()
            conn.close()

            if not row:
                QMessageBox.warning(self, "Patient Not Found", f"Could not find patient record for {patient_name}")
                return

            record = {
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
                "height": row[21],
                "weight": row[22],
                "bmi": row[23],
                "visual_acuity_left": row[24],
                "visual_acuity_right": row[25],
                "blood_pressure_systolic": row[26],
                "blood_pressure_diastolic": row[27],
                "fasting_blood_sugar": row[28],
                "random_blood_sugar": row[29],
                "diabetes_diagnosis_date": row[30],
                "treatment_regimen": row[31],
                "prev_dr_stage": row[32],
                "symptom_blurred_vision": row[33],
                "symptom_floaters": row[34],
                "symptom_flashes": row[35],
                "symptom_vision_loss": row[36],
                "source_image_path": row[37],
            }

            UserManager.add_activity_log(
                self.username,
                f"RECORD_OPENED patient_id={record.get('patient_id')}; record_id={record.get('id')}; source=referrals",
            )

            from reports import ReferralDetailDialog

            dialog = ReferralDetailDialog(record, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load referral details: {str(e)}")

    def refresh_dashboard(self):
        """Refresh all dashboard widgets with current data and correct theme colors."""
        from translations import get_pack

        _lang = getattr(self, "_current_language", "English")
        get_pack(_lang)
        dark = getattr(self, "_dark_mode", False)

        # Theme palette
        if dark:
            bg_page = "#0b1321"
            card_bg = "#152235"
            card_border = "transparent"
            text_primary = "#e6edf7"
            text_secondary = "#b7c6da"
            text_muted = "#8799b1"
            accent_blue = "#6db6ff"
            sev_green = "#4dd4ac"
            hero_grad_start = "#1a2c43"
            hero_grad_end = "#102036"
        else:
            bg_page = "#eef4fb"
            card_bg = "#ffffff"
            card_border = "transparent"
            text_primary = "#11283f"
            text_secondary = "#3f5f80"
            text_muted = "#6e829a"
            accent_blue = "#0e6fcd"
            sev_green = "#2d9d78"
            hero_grad_start = "#f2f7ff"
            hero_grad_end = "#e5f1ff"

        severity_colors = {
            "No DR": sev_green,
            "Mild DR": "#76b7ff" if dark else "#2b8de0",
            "Moderate DR": "#f2c96d" if dark else "#d99610",
            "Severe DR": "#ff9f6e" if dark else "#e26d31",
            "Proliferative DR": "#ff6b6b" if dark else "#ce3e3e",
        }

        # Fetch data
        total = 0
        rows = []
        with contextlib.suppress(Exception):
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                "SELECT patient_id, name, result, confidence "
                "FROM patient_records WHERE archived_at IS NULL ORDER BY id DESC"
            )
            rows = cur.fetchall()
            conn.close()
        total = len(rows)

        # Page background
        if hasattr(self, "dashboard_page"):
            self.dashboard_page.setStyleSheet(
                "QWidget#dashboardPage {"
                f" background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_page}, stop:1 {card_bg});"
                "}"
            )

        hero_card = self.findChild(QWidget, "heroCard")
        if hero_card:
            hero_card.setStyleSheet(
                "QWidget#heroCard {"
                f" background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {hero_grad_start}, stop:1 {hero_grad_end});"
                " border: none;"
                " border-radius: 16px;"
                "}"
            )

        # Welcome row
        if hasattr(self, "welcome_label"):
            self.welcome_label.setStyleSheet(
                f"color: {text_primary}; font-size: 25px; font-weight: 700; background: transparent;"
            )
        if hasattr(self, "welcome_hint_label"):
            self.welcome_hint_label.setStyleSheet(
                f"color: {text_secondary}; font-size: 12px; font-weight: 500; background: transparent;"
            )
        if hasattr(self, "dashboard_date_label"):
            self._update_dashboard_datetime_label()
            self.dashboard_date_label.setStyleSheet(
                f"color: {accent_blue}; font-size: 13px; font-weight: 700;"
                "border: none; border-radius: 0px;"
                "padding: 0px; background: transparent;"
            )
        if hasattr(self, "welcome_role_label"):
            self.welcome_role_label.setStyleSheet(
                f"color: {text_secondary}; font-size: 12px; font-weight: 700;"
                "border: none; border-radius: 0px;"
                "padding: 0px; background: transparent;"
            )

        # KPI cards
        kpi_title_style = (
            f"color: {text_secondary}; font-size: 10px; font-weight: 700;"
            "letter-spacing: 0.7px; text-transform: uppercase; background: transparent;"
        )
        kpi_value_style = f"font-size: 24px; font-weight: 800; color: {text_primary}; background: transparent;"

        def style_kpi(obj_name, accent, value_widget, value_text):
            card = self.findChild(QWidget, obj_name)
            if card:
                card.setStyleSheet(
                    f"QWidget#{obj_name} {{ background: {card_bg};"
                    f"  border: none; border-top: 3px solid {accent};"
                    f"  border-radius: 12px; }}"
                )
            title_w = self.findChild(QLabel, f"{obj_name}_title")
            if title_w:
                title_w.setStyleSheet(kpi_title_style)
            if value_widget:
                value_widget.setStyleSheet(kpi_value_style)
                value_widget.setText(value_text)

        style_kpi("kpiTotal", accent_blue, self.total_screenings_value, str(total))

        no_dr_count = 0
        abnormal_count = 0
        high_risk_count = 0
        for _, _, result, _ in rows:
            level = self._normalize_severity_label(result)
            if level == "No DR":
                no_dr_count += 1
            else:
                abnormal_count += 1
                if level in ("Severe DR", "Proliferative DR"):
                    high_risk_count += 1

        style_kpi("kpiPatients", sev_green, self.unique_patients_value, str(no_dr_count))
        style_kpi("kpiAbnormal", "#f59e0b", self.abnormal_cases_value, str(abnormal_count))
        style_kpi("kpiHighRisk", "#dc3545", self.high_risk_cases_value, str(high_risk_count))

        # My availability card
        availability_card = self.findChild(QWidget, "availabilityCard")
        if availability_card:
            availability_card.setStyleSheet(
                f"QWidget#availabilityCard {{ background: {card_bg};"
                "  border: none; border-radius: 12px; }}"
            )
        if hasattr(self, "_dash_availability_title_lbl"):
            self._dash_availability_title_lbl.setStyleSheet(
                f"color: {text_secondary}; font-size: 11px; font-weight: 800;"
                "letter-spacing: 0.8px; text-transform: uppercase; background: transparent;"
            )
        if hasattr(self, "_dash_availability_hint_lbl"):
            self._dash_availability_hint_lbl.setStyleSheet(
                f"color: {text_muted}; font-size: 12px; font-weight: 600; background: transparent;"
            )
        if hasattr(self, "availability_days_label"):
            self.availability_days_label.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {text_primary}; background: transparent;"
            )
        if hasattr(self, "availability_time_label"):
            self.availability_time_label.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {text_primary}; background: transparent;"
            )
        if hasattr(self, "availability_updated_label"):
            self.availability_updated_label.setStyleSheet(
                f"font-size: 12px; color: {text_muted}; font-weight: 600; background: transparent;"
            )

        availability_days_text, availability_time_text, availability_updated_text = self._get_dashboard_availability_text()
        if hasattr(self, "availability_days_label"):
            self.availability_days_label.setText(f"Days: {availability_days_text}")
        if hasattr(self, "availability_time_label"):
            self.availability_time_label.setText(f"Hours: {availability_time_text}")
        if hasattr(self, "availability_updated_label"):
            self.availability_updated_label.setText(availability_updated_text)

        # Severity chart card
        severity_card = self.findChild(QWidget, "severityCard")
        if severity_card:
            severity_card.setStyleSheet(
                f"QWidget#severityCard {{ background: {card_bg}; border: none; border-radius: 12px; }}"
            )
        if hasattr(self, "_dash_severity_title_lbl"):
            self._dash_severity_title_lbl.setStyleSheet(
                f"color: {text_secondary}; font-size: 11px; font-weight: 800;"
                "letter-spacing: 0.8px; text-transform: uppercase; background: transparent;"
            )
        if hasattr(self, "_dash_severity_hint_lbl"):
            self._dash_severity_hint_lbl.setStyleSheet(
                f"color: {text_muted}; font-size: 12px; font-weight: 600; background: transparent;"
            )

        severity_counts = {level: 0 for level in getattr(self, "_severity_order", [])}
        for _, _, result, _ in rows:
            level = self._normalize_severity_label(result)
            if level not in severity_counts:
                continue
            severity_counts[level] += 1

        if hasattr(self, "severity_bars"):
            total_count = sum(severity_counts.values()) if severity_counts else 0
            for level in self._severity_order:
                bar, count_lbl = self.severity_bars[level]
                count = severity_counts.get(level, 0)
                bar.setMaximum(max(1, total_count))
                bar.setValue(count)
                bar.setStyleSheet(
                    f"QProgressBar {{"
                    f" background: {'#e8eef5' if not dark else '#22344a'};"
                    f" border: 0; border-radius: 6px;"
                    f" }}"
                    f"QProgressBar::chunk {{"
                    f" background: {severity_colors[level]};"
                    f" border-radius: 6px;"
                    f" }}"
                )
                count_lbl.setText(str(count))
                count_lbl.setStyleSheet(
                    f"font-size: 14px; font-weight: 800; color: {text_primary};"
                    "background: transparent; padding-right: 4px;"
                )

        recent_card = self.findChild(QWidget, "recentCard")
        if recent_card:
            recent_card.setStyleSheet(
                f"QWidget#recentCard {{ background: {card_bg}; border: none; border-radius: 12px; }}"
            )
        if hasattr(self, "_dash_recent_title_lbl"):
            self._dash_recent_title_lbl.setStyleSheet(
                f"color: {text_secondary}; font-size: 11px; font-weight: 800;"
                "letter-spacing: 0.8px; text-transform: uppercase; background: transparent;"
            )

        metric_defs = {
            "impactHigh": ("High Risk", high_risk_count, "#ce3e3e" if not dark else "#ff6b6b"),
            "impactAbnormal": ("Abnormal", abnormal_count, "#d99610" if not dark else "#f2c96d"),
            "impactClear": ("No DR", no_dr_count, sev_green),
        }
        for chip_name, (title_text, value, accent) in metric_defs.items():
            chip = self.findChild(QWidget, chip_name)
            title = self.findChild(QLabel, f"{chip_name}_title")
            value_lbl = self.findChild(QLabel, f"{chip_name}_value")
            sub_lbl = self.findChild(QLabel, f"{chip_name}_sub")
            if chip:
                chip.setStyleSheet(
                    f"QWidget#{chip_name} {{ background-color: {card_bg};"
                    f" border: 1px solid {card_border};"
                    " border-radius: 10px; }"
                )
            if title:
                title.setText(title_text)
                title.setStyleSheet(
                    f"font-size: 10px; color: {text_secondary}; font-weight: 700;"
                    "text-transform: uppercase; letter-spacing: 0.8px; background: transparent;"
                )
            if value_lbl:
                value_lbl.setText(str(value))
                value_lbl.setStyleSheet(
                    f"font-size: 24px; color: {text_primary}; font-weight: 800; background: transparent;"
                )
            if sub_lbl:
                pct = (value / total) * 100 if total else 0.0
                sub_lbl.setText(f"{pct:.1f}% of total")
                sub_lbl.setStyleSheet(
                    f"font-size: 11px; color: {text_muted}; font-weight: 600; background: transparent;"
                )

        # Populate Recent Screenings list
        if hasattr(self, "recent_list_layout"):
            # Clear old items
            while self.recent_list_layout.count():
                item = self.recent_list_layout.takeAt(0)
                if w := item.widget():
                    w.deleteLater()

            if not rows:
                empty_lbl = QLabel("No screenings available.")
                empty_lbl.setStyleSheet(
                    f"font-size: 12px; color: {text_muted}; font-weight: 600; background: transparent; padding: 8px 0;"
                )
                self.recent_list_layout.addWidget(empty_lbl)
            else:
                for row_data in rows[:4]:
                    patient_id = row_data[0]
                    name = row_data[1] or "Unknown"
                    result = self._normalize_severity_label(row_data[2]) or "Pending"
                    
                    item_w = QWidget()
                    item_w.setStyleSheet(
                        "QWidget {"
                        "background: transparent;"
                        "border: none;"
                        "border-radius: 0px;"
                        "}"
                    )
                    item_v = QVBoxLayout(item_w)
                    item_v.setContentsMargins(10, 8, 10, 8)
                    item_v.setSpacing(4)
                    
                    name_lbl = QLabel(name)
                    name_lbl.setStyleSheet(
                        f"font-size: 13px; font-weight: 700; color: {text_primary}; background: transparent;"
                    )
                    
                    sub_row = QHBoxLayout()
                    sub_row.setContentsMargins(0, 0, 0, 0)
                    sub_row.setSpacing(8)
                    
                    id_lbl = QLabel(patient_id)
                    id_lbl.setStyleSheet(
                        f"font-size: 12px; font-weight: 600; color: {text_muted}; background: transparent;"
                    )
                    
                    res_lbl = QLabel(result)
                    res_color = severity_colors.get(result, text_secondary)
                    res_lbl.setStyleSheet(
                        f"font-size: 12px; font-weight: 700; color: {res_color}; background: transparent;"
                    )
                    
                    sub_row.addWidget(id_lbl)
                    sub_row.addStretch()
                    sub_row.addWidget(res_lbl)
                    
                    item_v.addWidget(name_lbl)
                    item_v.addLayout(sub_row)
                    
                    self.recent_list_layout.addWidget(item_w)

    @staticmethod
    def _normalize_severity_label(result_text):
        text = str(result_text or "").strip().lower()
        if not text or "pending" in text:
            return ""
        if "proliferative" in text:
            return "Proliferative DR"
        if "severe" in text:
            return "Severe DR"
        if "moderate" in text:
            return "Moderate DR"
        if "mild" in text:
            return "Mild DR"
        if "no dr" in text or "no diabetic retinopathy" in text or "normal" in text:
            return "No DR"
        return ""

    @staticmethod
    def _is_high_attention_result(result_text):
        text = str(result_text or "").lower()
        keywords = ("moderate", "severe", "proliferative", "refer", "urgent", "dr detected")
        return any(word in text for word in keywords)

    @staticmethod
    def _extract_confidence_value(conf_text):
        text = str(conf_text or "")
        numeric = "".join(ch for ch in text if ch.isdigit() or ch == ".")
        if not numeric:
            return None
        try:
            return float(numeric)
        except ValueError:
            return None

    def _get_dashboard_availability_text(self):
        profile = get_user_profile(self.username) or {}
        raw_availability = profile.get("availability_json")
        if not raw_availability:
            return "Not set", "Not set", "Update this from Users > Edit Availability"

        try:
            payload = json.loads(raw_availability) if isinstance(raw_availability, str) else raw_availability
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            return "Not set", "Not set", "Update this from Users > Edit Availability"

        start_time = str(payload.get("start_time") or "").strip()
        end_time = str(payload.get("end_time") or "").strip()
        time_text = "Not set"
        if start_time and end_time:
            formatted_start = self._format_availability_time(start_time)
            formatted_end = self._format_availability_time(end_time)
            time_text = f"{formatted_start} - {formatted_end}"

        selected_days = payload.get("days") or []
        weekday_order = [
            ("mon", "Mon"),
            ("tue", "Tue"),
            ("wed", "Wed"),
            ("thu", "Thu"),
            ("fri", "Fri"),
            ("sat", "Sat"),
            ("sun", "Sun"),
        ]
        day_text = "Not set"
        if isinstance(selected_days, list) and selected_days:
            selected_set = {str(value).strip().lower() for value in selected_days}
            ordered_days = [label for key, label in weekday_order if key in selected_set]
            if ordered_days:
                day_text = ", ".join(ordered_days)

        updated_at = str(payload.get("updated_at") or "").strip()
        updated_text = "Update this from Users > Edit Availability"
        if updated_at:
            with contextlib.suppress(Exception):
                parsed_updated_at = datetime.fromisoformat(updated_at)
                updated_text = f"Last updated: {parsed_updated_at.strftime('%b %d, %Y %I:%M %p')}"

        return day_text, time_text, updated_text

    @staticmethod
    def _format_availability_time(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        for candidate, fmt in (
            (text.upper(), "%I:%M %p"),
            (text, "%H:%M"),
        ):
            with contextlib.suppress(ValueError):
                return datetime.strptime(candidate, fmt).strftime("%I:%M %p").lstrip("0")
        return text

    @staticmethod
    def get_nav_button_style(icon_only=False):
        """Get navigation button stylesheet. If icon_only, use smaller font and center icon."""
        if icon_only:
            return """
                QPushButton {
                    color: #495057;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 500;
                    background: transparent;
                    text-decoration: none;
                }
                QPushButton:hover {
                    background: #eef6ff;
                    color: #1d5fa8;
                }
                QPushButton:pressed { background: #e2f0ff; }
                QPushButton:focus {
                    outline: none;
                    border: 1px solid transparent;
                }
            """
        else:
            return """
                QPushButton {
                    color: #495057;
                    text-align: left;
                    padding: 15px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                    background: transparent;
                }
                QPushButton:hover {
                    background: #e9ecef;
                    color: #007bff;
                }
                QPushButton:focus {
                    outline: none;
                    border: none;
                }
            """
