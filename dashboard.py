"""
Dashboard module for EyeShield EMR application.
Contains main application window and dashboard functionality.
"""

import contextlib
import os
import random
import sqlite3
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QGroupBox, QMessageBox, QGridLayout, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QFont
from PySide6.QtSvg import QSvgRenderer

from screening import ScreeningPage
from reports import ReportsPage
from users import UsersPage
from settings import SettingsPage, DARK_STYLESHEET
from help_support import HelpSupportPage
from camera import CameraPage
from auth import DB_FILE


class EyeShieldApp(QMainWindow):
    """Main application window"""

    def __init__(self, username, role):
        super().__init__()

        self.username = username
        self.role = role
        self._dark_mode = False
        self._saved_styles = {}
        self._logging_out = False
        self._current_language = "English"

        self.setWindowTitle("EyeShield – DR Screening")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 860)

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
            if nav_item["requires_admin"] and self.role != "admin":
                continue
            w, btn, label = nav_button_with_label(nav_item["icon"], nav_item["label"])
            btn.setProperty("pageIndex", nav_item["page_index"])
            btn.setProperty("navKey", nav_item["label"])
            label.setProperty("pageIndex", nav_item["page_index"])
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
        user_info = QLabel(f"  {self.username}  \u2022  {self.role}  ")
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
            requires_admin = page_index == 4
            button.clicked.connect(
                lambda checked=False, idx=page_index, admin_only=requires_admin: self._navigate_to(idx, requires_admin=admin_only)
            )

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
        self.reports_page = ReportsPage(self.username, self.role)
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
        self.refresh_dashboard()
        self._set_active_nav(0)

        # Ensure nav bar styles are correct for the initial theme
        self._apply_nav_theme(False)

        # Apply saved theme from settings (must run after all pages are parented)
        saved_theme = self.settings_page.theme_combo.currentText()
        if saved_theme == "Dark":
            self.apply_theme("Dark")

        # Apply saved language to all tabs
        saved_lang = self.settings_page.lang_combo.currentText()
        if saved_lang != "English":
            self.apply_language(saved_lang)

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
        svg_text = svg_text.replace('stroke="currentColor"', f'stroke="{color}"')
        svg_text = svg_text.replace('fill="currentColor"', f'fill="{color}"')
        svg_text = svg_text.replace('stroke="black"', f'stroke="{color}"')
        svg_text = svg_text.replace('fill="black"', f'fill="{color}"')
        svg_text = svg_text.replace('stroke="#000"', f'stroke="{color}"')
        svg_text = svg_text.replace('fill="#000"', f'fill="{color}"')
        svg_text = svg_text.replace('stroke="#000000"', f'stroke="{color}"')
        svg_text = svg_text.replace('fill="#000000"', f'fill="{color}"')
        svg_text = svg_text.replace('stroke="#e3e3e3"', f'stroke="{color}"')
        svg_text = svg_text.replace('fill="#e3e3e3"', f'fill="{color}"')
        svg_text = svg_text.replace('fill="white"', 'fill="transparent"')
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
        pixmap = self._load_svg_pixmap_colored(svg_path, color, 256)
        if pixmap.isNull():
            button.setIcon(QIcon())
            return
        button.setIcon(QIcon(pixmap))
        button.setIconSize(size)

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

    def _navigate_to(self, index, requires_admin=False):
        if requires_admin and self.role != "admin":
            QMessageBox.warning(self, "Access Denied", "Only admins can access the Users tab.")
            return
        self.pages.setCurrentIndex(index)

    def _on_page_changed(self, index):
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

        for btn in self.nav_buttons:
            btn_index = int(btn.property("pageIndex") or -1)
            is_screening_btn = str(btn.property("navKey") or "") == "Screening"
            if btn_index == index:
                if not dark and is_screening_btn and index == 1:
                    btn.setStyleSheet(screening_active_btn_style)
                else:
                    btn.setStyleSheet(active_btn_style)
            elif btn.isEnabled():
                btn.setStyleSheet(inactive_btn_style)
        for i, label in enumerate(self.nav_labels):
            if int(label.property("pageIndex") or -1) == index:
                is_screening_label = str(self.nav_buttons[i].property("navKey") or "") == "Screening"
                if not dark and is_screening_label and index == 1:
                    label.setStyleSheet(screening_active_label)
                else:
                    label.setStyleSheet(active_label)
            elif self.nav_buttons[i].isEnabled():
                label.setStyleSheet(inactive_label)
        self._refresh_nav_button_icons(index)

    def apply_theme(self, theme: str):
        """Apply theme across the entire application by clearing local stylesheets."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()

        # Widgets that belong to the nav bar — we manage these explicitly in
        # _apply_nav_theme so they must never be wiped or blindly restored.
        nav_protected = set()
        if hasattr(self, "nav_bar"):
            nav_protected.add(id(self.nav_bar))
            for w in self.nav_bar.findChildren(QWidget):
                nav_protected.add(id(w))

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
                    widget.setStyleSheet("")
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
            self.welcome_label.setText(f"{pack['dash_welcome']}, {self.username}")

        # Dashboard section headers
        if hasattr(self, "_dash_severity_title_lbl"):
            self._dash_severity_title_lbl.setText("SCREENED PATIENTS")
        if hasattr(self, "_dash_impact_title_lbl"):
            self._dash_impact_title_lbl.setText("CLINICAL IMPACT")
        if hasattr(self, "impact_cta_btn"):
            self.impact_cta_btn.setText("Review High-Risk Cases")

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

        self.welcome_label = QLabel(f"Welcome back, {self.username}")
        self.welcome_label.setObjectName("welcomeGreeting")
        self.welcome_label.setStyleSheet(
            "color: #212529; font-size: 25px; font-weight: 700; background: transparent;"
        )

        self.welcome_role_label = QLabel(f"{self.role.capitalize()}")
        self.welcome_role_label.setObjectName("welcomeRole")
        self.welcome_role_label.setStyleSheet(
            "color: #6c757d; font-size: 13px; font-weight: 600; background: transparent;"
        )

        self.welcome_hint_label = QLabel("Track screening quality and triage priorities at a glance.")
        self.welcome_hint_label.setObjectName("welcomeHint")
        self.welcome_hint_label.setStyleSheet(
            "color: #486581; font-size: 12px; font-weight: 500; background: transparent;"
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
        left_col.addWidget(self.welcome_hint_label)
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
            """Build a single KPI card with title, value, and secondary line."""
            card = QWidget()
            card.setObjectName(object_name)
            card.setMinimumHeight(126)
            card.setStyleSheet(f"""
                QWidget#{object_name} {{
                    background: white;
                    border: 1px solid #dee2e6;
                    border-left: 4px solid {accent};
                    border-radius: 12px;
                }}
            """)
            v = QVBoxLayout(card)
            v.setContentsMargins(16, 12, 16, 12)
            v.setSpacing(6)

            title = QLabel(title_text)
            title.setObjectName(f"{object_name}_title")
            title.setStyleSheet(
                "color: #6c757d; font-size: 10px; font-weight: 700;"
                "letter-spacing: 0.9px; text-transform: uppercase; background: transparent;"
            )
            value = QLabel("—")
            value.setObjectName(f"{object_name}_value")
            value.setStyleSheet("font-size: 32px; font-weight: 700; color: #212529; background: transparent;")

            subtitle = QLabel("")
            subtitle.setObjectName(f"{object_name}_sub")
            subtitle.setStyleSheet("font-size: 11px; color: #6c757d; background: transparent;")

            v.addWidget(title)
            v.addWidget(value)
            v.addWidget(subtitle)
            v.addStretch()
            return card, value, subtitle

        # Card 1: Total Screenings
        card_total, self.total_screenings_value, self.total_sub = \
            make_kpi_card("kpiTotal", "TOTAL SCREENINGS", "#0066cc")

        # Card 2: No DR Cases
        card_patients, self.unique_patients_value, self.unique_patients_sub = \
            make_kpi_card("kpiPatients", "NO DR CASES", "#2e7d32")

        # Card 3: Abnormal Cases
        card_abnormal, self.abnormal_cases_value, self.abnormal_cases_sub = \
            make_kpi_card("kpiAbnormal", "ABNORMAL CASES", "#f59e0b")

        # Card 4: High Risk Cases
        card_high_risk, self.high_risk_cases_value, self.high_risk_cases_sub = \
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

        # Right: impact panel
        sidebar = QWidget()
        sidebar.setObjectName("dashSidebar")
        sidebar.setStyleSheet("QWidget#dashSidebar { background: transparent; }")
        sidebar_v = QVBoxLayout(sidebar)
        sidebar_v.setContentsMargins(0, 0, 0, 0)
        sidebar_v.setSpacing(12)

        impact_card = QWidget()
        impact_card.setObjectName("impactCard")
        impact_card.setStyleSheet("""
            QWidget#impactCard {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 12px;
            }
        """)
        impact_v = QVBoxLayout(impact_card)
        impact_v.setContentsMargins(16, 12, 16, 12)
        impact_v.setSpacing(10)

        self._dash_impact_title_lbl = QLabel("CLINICAL IMPACT")
        self._dash_impact_title_lbl.setStyleSheet(
            "color: #6c757d; font-size: 10px; font-weight: 700;"
            "letter-spacing: 0.9px; background: transparent;"
        )
        impact_v.addWidget(self._dash_impact_title_lbl)

        self.impact_priority_label = QLabel("No urgent cases in the current queue")
        self.impact_priority_label.setWordWrap(True)
        self.impact_priority_label.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1d4f91;"
            "background: #eaf3ff; border: 1px solid #c9dffc; border-radius: 10px;"
            "padding: 10px 12px;"
        )
        impact_v.addWidget(self.impact_priority_label)

        self.impact_summary_label = QLabel("No screenings yet")
        self.impact_summary_label.setWordWrap(True)
        self.impact_summary_label.setStyleSheet("font-size: 12px; color: #486581; background: transparent;")
        impact_v.addWidget(self.impact_summary_label)

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(8)
        metric_grid.setVerticalSpacing(8)

        def make_metric_chip(name, title_text):
            chip = QWidget()
            chip.setObjectName(name)
            chip.setMinimumHeight(88)
            chip_v = QVBoxLayout(chip)
            chip_v.setContentsMargins(10, 8, 10, 8)
            chip_v.setSpacing(3)

            title = QLabel(title_text)
            title.setObjectName(f"{name}_title")
            value = QLabel("0")
            value.setObjectName(f"{name}_value")
            sub = QLabel("0.0%")
            sub.setObjectName(f"{name}_sub")

            chip_v.addWidget(title)
            chip_v.addWidget(value)
            chip_v.addWidget(sub)
            return chip, value, sub

        chip_high, self.impact_high_value, self.impact_high_sub = make_metric_chip("impactHigh", "High Risk")
        chip_abnormal, self.impact_abnormal_value, self.impact_abnormal_sub = make_metric_chip("impactAbnormal", "Abnormal")
        chip_clear, self.impact_clear_value, self.impact_clear_sub = make_metric_chip("impactClear", "No DR")

        metric_grid.addWidget(chip_high, 0, 0)
        metric_grid.addWidget(chip_abnormal, 0, 1)
        metric_grid.addWidget(chip_clear, 1, 0, 1, 2)
        impact_v.addLayout(metric_grid)

        self.impact_recent_label = QLabel("Latest record: none")
        self.impact_recent_label.setWordWrap(True)
        self.impact_recent_label.setStyleSheet("font-size: 12px; color: #486581; background: transparent;")
        impact_v.addWidget(self.impact_recent_label)

        self.impact_cta_btn = QPushButton("Review High-Risk Cases")
        self.impact_cta_btn.setCursor(Qt.PointingHandCursor)
        self.impact_cta_btn.setFixedHeight(40)
        self.impact_cta_btn.clicked.connect(lambda: self.pages.setCurrentIndex(3))
        impact_v.addWidget(self.impact_cta_btn)
        impact_v.addStretch(1)

        sidebar_v.addWidget(impact_card, 1)

        content_row.addWidget(sidebar, 3)
        layout.addLayout(content_row, 1)

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
            btn_primary_bg = "#5aa9ff"
            btn_primary_text = "#0f1720"
            btn_primary_hover = "#3e95f6"
            btn_outline_color = "#7fc0ff"
            btn_outline_hover_bg = "#213140"
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
            btn_primary_bg = "#0f6cbd"
            btn_primary_text = "white"
            btn_primary_hover = "#0b5b9e"
            btn_outline_color = "#0f6cbd"
            btn_outline_hover_bg = "#ebf4ff"
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
            "letter-spacing: 0.9px; text-transform: uppercase; background: transparent;"
        )
        kpi_value_style = f"font-size: 32px; font-weight: 700; color: {text_primary}; background: transparent;"
        kpi_sub_style = f"font-size: 11px; color: {text_secondary}; background: transparent;"

        def _pct(value):
            return f"{(value / total) * 100:.1f}%" if total else "0.0%"

        def style_kpi(obj_name, accent, value_widget, sub_widget, value_text, sub_text):
            card = self.findChild(QWidget, obj_name)
            if card:
                card.setStyleSheet(
                    f"QWidget#{obj_name} {{ background: {card_bg};"
                    f"  border: 1px solid {card_border}; border-left: 4px solid {accent};"
                    f"  border-radius: 12px; }}"
                )
            title_w = self.findChild(QLabel, f"{obj_name}_title")
            if title_w:
                title_w.setStyleSheet(kpi_title_style)
            if value_widget:
                value_widget.setStyleSheet(kpi_value_style)
                value_widget.setText(value_text)
            if sub_widget:
                sub_widget.setStyleSheet(kpi_sub_style)
                sub_widget.setText(sub_text)

        style_kpi("kpiTotal", accent_blue,
                  self.total_screenings_value, self.total_sub,
                  str(total), "All active screenings")

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
        style_kpi("kpiPatients", sev_green,
                  self.unique_patients_value, self.unique_patients_sub,
                  str(no_dr_count), f"{_pct(no_dr_count)} of total")

        style_kpi("kpiAbnormal", "#f59e0b",
                  self.abnormal_cases_value, self.abnormal_cases_sub,
                  str(abnormal_count), f"{_pct(abnormal_count)} need review")

        style_kpi("kpiHighRisk", "#dc3545",
                  self.high_risk_cases_value, self.high_risk_cases_sub,
                  str(high_risk_count), f"{_pct(high_risk_count)} urgent review")

        # Severity chart card
        severity_card = self.findChild(QWidget, "severityCard")
        if severity_card:
            severity_card.setStyleSheet(
                f"QWidget#severityCard {{ background: {card_bg};"
                f"  border: 1px solid {card_border}; border-radius: 12px; }}"
            )
        if hasattr(self, "_dash_severity_title_lbl"):
            self._dash_severity_title_lbl.setStyleSheet(
                f"color: {text_secondary}; font-size: 10px; font-weight: 700;"
                "letter-spacing: 0.9px; text-transform: uppercase; background: transparent;"
            )
        if hasattr(self, "_dash_severity_hint_lbl"):
            self._dash_severity_hint_lbl.setStyleSheet(
                f"color: {text_muted}; font-size: 12px; font-weight: 500; background: transparent;"
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
                    f" background: {card_border};"
                    f" border: 0; border-radius: 8px;"
                    f" }}"
                    f"QProgressBar::chunk {{"
                    f" background: {severity_colors[level]};"
                    f" border-radius: 8px;"
                    f" }}"
                )
                count_lbl.setText(str(count))
                count_lbl.setStyleSheet(
                    f"font-size: 15px; font-weight: 800; color: {text_primary};"
                    "background: transparent; padding-right: 4px;"
                )

        # Impact card and content
        impact_card = self.findChild(QWidget, "impactCard")
        if impact_card:
            impact_card.setStyleSheet(
                f"QWidget#impactCard {{ background: {card_bg};"
                f"  border: 1px solid {card_border}; border-radius: 12px; }}"
            )
        if hasattr(self, "_dash_impact_title_lbl"):
            self._dash_impact_title_lbl.setStyleSheet(
                f"color: {text_secondary}; font-size: 10px; font-weight: 700;"
                "letter-spacing: 0.9px; background: transparent;"
            )

        if total == 0:
            priority_text = "No urgent cases in the current queue"
            summary_text = "Start a screening to generate triage insights and risk distribution."
        elif high_risk_count > 0:
            priority_text = f"Immediate review needed: {high_risk_count} high-risk case(s)"
            summary_text = f"{abnormal_count} abnormal case(s) require review across {total} active screenings."
        elif abnormal_count > 0:
            priority_text = f"Review queue active: {abnormal_count} abnormal case(s)"
            summary_text = "No severe/proliferative alerts right now, but moderate findings need attention."
        else:
            priority_text = "All current records are low risk"
            summary_text = "No abnormal findings in the current active screening set."

        if hasattr(self, "impact_priority_label"):
            priority_bg = "#2a3948" if dark else "#eaf3ff"
            priority_text_color = "#e8eef5" if dark else "#1d4f91"
            self.impact_priority_label.setText(priority_text)
            self.impact_priority_label.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color: {priority_text_color};"
                f"background: {priority_bg}; border: 1px solid {accent_blue};"
                "border-radius: 10px; padding: 10px 12px;"
            )
        if hasattr(self, "impact_summary_label"):
            self.impact_summary_label.setText(summary_text)
            self.impact_summary_label.setStyleSheet(
                f"font-size: 12px; color: {text_secondary}; background: transparent;"
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
                    f"QWidget#{chip_name} {{ background: {card_bg};"
                    f" border: 1px solid {card_border}; border-left: 4px solid {accent};"
                    " border-radius: 10px; }}"
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

        if hasattr(self, "impact_recent_label"):
            if rows:
                latest_name = rows[0][1] or "Unknown"
                latest_result = self._normalize_severity_label(rows[0][2]) or "Pending"
                self.impact_recent_label.setText(f"Latest record: {latest_name} - {latest_result}")
            else:
                self.impact_recent_label.setText("Latest record: none")
            self.impact_recent_label.setStyleSheet(
                f"font-size: 12px; color: {text_secondary}; background: transparent;"
            )

        if hasattr(self, "impact_cta_btn"):
            self.impact_cta_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {btn_primary_bg}; color: {btn_primary_text}; border: none;
                    border-radius: 10px; font-size: 13px; font-weight: 700; padding: 0 16px;
                }}
                QPushButton:hover {{ background: {btn_primary_hover}; }}
            """)

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
