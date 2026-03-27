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
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QGroupBox, QMessageBox, QProgressBar, QSizePolicy,
    QFrame
)
from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QFont, QShortcut, QKeySequence, QColor, QGuiApplication
from PySide6.QtSvg import QSvgRenderer

from screening import ScreeningPage
from reports import ReportsPage
from users import UsersPage
from settings import SettingsPage, DARK_STYLESHEET
from help_support import HelpSupportPage
from camera import CameraPage
from auth import DB_FILE
from user_auth import get_user_profile


class EyeShieldApp(QMainWindow):
    """Main application window"""

    ROLE_PAGE_ACCESS = {
        "admin": {4, 5, 6},
        "clinician": {0, 1, 2, 3, 5, 6},
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
            label.setFont(EyeShieldApp._make_nav_font(8))
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
                "page_index": 4,
                "requires_admin": True,
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
            w, btn, label = nav_button_with_label(nav_item["icon"], nav_item["label"])
            btn.setProperty("pageIndex", nav_item["page_index"])
            btn.setProperty("navKey", nav_item["label"])
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

        # User info on the right — styled as a pill badge
        user_info = QLabel(f"  {self.display_name}  \u2022  {self.display_title}  ")
        self.user_info_label = user_info
        user_info.setObjectName("userInfo")
        user_info.setStyleSheet(
            "color: #007bff; background: #e8f0fe; border: 1px solid #b8d0f7;"
            "border-radius: 12px; font-size: 12px; font-weight: 600;"
            "padding: 2px 8px; margin-left: 12px; margin-right: 8px;"
        )
        nav_layout.addWidget(user_info)

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
            button.clicked.connect(lambda checked=False, idx=page_index: self._navigate_to(idx))

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
        self.settings_page = SettingsPage()
        self.help_support_page = HelpSupportPage()

        # Dashboard is created after the other pages so it can be refreshed
        self.dashboard_page = self.create_dashboard_page()

        self.users_page.parent_app = self

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.screening_page)
        self.pages.addWidget(self.camera_page)
        self.pages.addWidget(self.reports_page)
        self.pages.addWidget(self.users_page)
        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.help_support_page)
        self.pages.currentChanged.connect(self._on_page_changed)

        main_layout.addWidget(self.pages)
        root_layout.addWidget(main)
        self.setCentralWidget(root)

        self._save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self._save_shortcut.activated.connect(self._global_save_shortcut)

        self.refresh_dashboard()
        self.pages.setCurrentIndex(self._default_page_index())
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

    @classmethod
    def _allowed_pages_for_role(cls, role: str) -> set[int]:
        return set(cls.ROLE_PAGE_ACCESS.get(str(role or "").lower(), cls.ROLE_PAGE_ACCESS["clinician"]))

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
        active_color = "#89b4fa" if dark else "#ffffff"
        inactive_color = "#a6adc8" if dark else "#495057"
        disabled_color = "#6c7086" if dark else "#adb5bd"
        icon_size = QSize(24, 24)
        for btn in self.nav_buttons:
            icon_path = btn.property("navIconPath") or ""
            if not btn.isEnabled():
                color = disabled_color
            elif int(btn.property("pageIndex") or -1) == active_index:
                color = active_color
            else:
                color = inactive_color
            self._set_button_svg_icon(btn, icon_path, color, icon_size)

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

    def _navigate_to(self, index, show_denied_message=True):
        if self._is_screening_navigation_locked() and index != 1:
            if show_denied_message:
                QMessageBox.information(
                    self,
                    "Screening In Progress",
                    "Please wait for the image analysis to finish before changing tabs.",
                )
            if hasattr(self, "pages"):
                self.pages.setCurrentIndex(1)
            return
        if not self._is_page_allowed(index):
            if show_denied_message:
                QMessageBox.warning(self, "Access Denied", "Your account role cannot access this page.")
            return
        self.pages.setCurrentIndex(index)

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
            return
        if not self._is_page_allowed(index):
            self.pages.setCurrentIndex(self._default_page_index())
            return
        self._set_active_nav(index)
        if index == 2:
            self.camera_page.enter_page()
        else:
            self.camera_page.leave_page()
        if index == 3:
            self.reports_page.refresh_report()
        if index == 0:
            self.refresh_dashboard()

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
                    color: #ffffff;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid #005ecb;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 500;
                    background: #007bff;
                    text-decoration: none;
                }
                QPushButton:hover { background: #006fe6; }
                QPushButton:focus { outline: none; border: 1px solid #0056b3; }
            """
            screening_active_btn_style = """
                QPushButton {
                    color: #ffffff;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid #0056b3;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 700;
                    background: #0066ff;
                    text-decoration: none;
                }
                QPushButton:hover { background: #005ce6; }
                QPushButton:focus { outline: none; border: 1px solid #004ba8; }
            """
            inactive_btn_style = self.get_nav_button_style(icon_only=True)
            active_label = "font-size: 10px; color: #005ecb; font-weight: 700; margin-top: 0px; text-decoration: none; border: none;"
            screening_active_label = "font-size: 10px; color: #0066ff; font-weight: 800; margin-top: 0px; text-decoration: none; border: none;"
            inactive_label = "font-size: 10px; color: #495057; margin-top: 0px; text-decoration: none; border: none;"
            disabled_label = "font-size: 10px; color: #adb5bd; margin-top: 0px; text-decoration: none; border: none;"

        for btn in self.nav_buttons:
            btn_index = int(btn.property("pageIndex") or -1)
            is_screening_btn = str(btn.property("navKey") or "") == "Screening"
            if btn_index == index:
                if not dark and is_screening_btn and index == 1:
                    btn.setStyleSheet(screening_active_btn_style)
                else:
                    btn.setStyleSheet(active_btn_style)
            elif not btn.isEnabled():
                btn.setStyleSheet(inactive_btn_style)
            elif btn.isEnabled():
                btn.setStyleSheet(inactive_btn_style)
        for i, label in enumerate(self.nav_labels):
            if int(label.property("pageIndex") or -1) == index:
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
            "Settings": "nav_settings",
            "Help": "nav_help",
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
            user_store.log_activity(self.username, "Logout")
        except Exception:
            pass

        from login import LoginWindow
        self._logging_out = True
        self.login = LoginWindow()
        self.login.show()
        self.close()

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

    def refresh_dashboard(self):
        """Refresh all dashboard widgets with current data and correct theme colors."""
        from translations import get_pack
        _lang = getattr(self, "_current_language", "English")
        get_pack(_lang)
        dark = getattr(self, "_dark_mode", False)

        # Theme palette
        if dark:
            bg_page = "#0f1720"
            card_bg = "#17212b"
            card_border = "#2a3948"
            text_primary = "#e8eef5"
            text_secondary = "#b8c7d9"
            text_muted = "#7f93a8"
            accent_blue = "#5aa9ff"
            sev_green = "#4dd4ac"
            hero_grad_start = "#182738"
            hero_grad_end = "#111e2d"
        else:
            bg_page = "#f3f7fb"
            card_bg = "white"
            card_border = "#dbe4f0"
            text_primary = "#102a43"
            text_secondary = "#486581"
            text_muted = "#7b8794"
            accent_blue = "#0f6cbd"
            sev_green = "#2d9d78"
            hero_grad_start = "#eef6ff"
            hero_grad_end = "#e4f0ff"

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
                f" border: 1px solid {card_border};"
                " border-radius: 14px;"
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
            today = datetime.now().strftime("%A, %B %d, %Y")
            self.dashboard_date_label.setText(today)
            self.dashboard_date_label.setStyleSheet(
                f"color: {accent_blue}; font-size: 13px; font-weight: 700;"
                f"border: 1px solid {accent_blue}; border-radius: 12px;"
                "padding: 6px 12px; background: transparent;"
            )
        if hasattr(self, "welcome_role_label"):
            self.welcome_role_label.setStyleSheet(
                f"color: {text_secondary}; font-size: 12px; font-weight: 700;"
                f"border: 1px solid {card_border}; border-radius: 10px;"
                "padding: 2px 10px; background: transparent;"
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
                    f"  border: 1px solid {card_border}; border-left: 4px solid {accent};"
                    f"  border-radius: 10px; }}"
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
                f"  border: 1px solid {card_border}; border-radius: 10px; }}"
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
                "QWidget#severityCard { background: transparent; border: none; }"
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
                    f" background: {'#eef2f6' if not dark else '#243241'};"
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
                "QWidget#recentCard { background: transparent; border: none; }"
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
                    item_v = QVBoxLayout(item_w)
                    item_v.setContentsMargins(0, 4, 0, 4)
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
                    
                    line = QWidget()
                    line.setFixedHeight(1)
                    line.setStyleSheet(f"background: {card_border};")
                    self.recent_list_layout.addWidget(line)


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
                    background: #e9ecef;
                    color: #007bff;
                }
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
