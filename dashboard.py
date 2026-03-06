"""
Dashboard module for EyeShield EMR application.
Contains main application window and dashboard functionality.
"""

import os
import random
import sqlite3
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QGroupBox, QMessageBox, QGridLayout
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

        self.setWindowTitle("EyeShield – DR Screening")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 860)

        # Set app icon
        _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eyeshield_icon.svg")
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
        title_font = QFont("Segoe UI Variable", 14)
        title_font.setBold(True)
        title_font.setUnderline(False)
        title_label.setFont(title_font)
        title_label.setFixedWidth(118)
        title_icon_layout.addWidget(title_label)

        icon_label = QLabel()
        self.nav_icon_label = icon_label
        self._icon_path = _icon_path
        icon_pixmap = self._load_svg_pixmap_colored(_icon_path, "#007bff", 256).scaled(
            QSize(38, 38), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
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
            lbl_font = QFont("Segoe UI Variable", 8)
            lbl_font.setUnderline(False)
            lbl_font.setStrikeOut(False)
            label.setFont(lbl_font)
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
        for nav_item in navs:
            if nav_item["requires_admin"] and self.role != "admin":
                continue
            w, btn, label = nav_button_with_label(nav_item["icon"], nav_item["label"])
            btn.setProperty("pageIndex", nav_item["page_index"])
            label.setProperty("pageIndex", nav_item["page_index"])
            nav_layout.addWidget(w)
            nav_layout.addStretch(1)
            nav_widgets.append(w)
            nav_buttons.append(btn)
            nav_labels.append(label)

        self.nav_buttons = nav_buttons
        self.nav_labels = nav_labels
        self.nav_widgets = nav_widgets

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
        self.reports_page = ReportsPage()
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
        active_color = "#89b4fa" if dark else "#007bff"
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
            title_font = QFont("Segoe UI Variable", 14)
            title_font.setBold(True)
            title_font.setUnderline(False)
            self.title_label.setFont(title_font)
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
        btn_font = QFont("Segoe UI Variable", 14)
        btn_font.setUnderline(False)
        btn_font.setStrikeOut(False)
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
        lbl_font = QFont("Segoe UI Variable", 8)
        lbl_font.setUnderline(False)
        lbl_font.setStrikeOut(False)
        if hasattr(self, "nav_labels"):
            for lbl in self.nav_labels:
                lbl.setStyleSheet(inactive_lbl)
                lbl.setFont(lbl_font)

    def _update_nav_icon(self, dark: bool):
        """Re-render the nav bar icon to match the current theme."""
        if not hasattr(self, "nav_icon_label") or not hasattr(self, "_icon_path"):
            return
        color = "#cdd6f4" if dark else "#007bff"
        pixmap = self._load_svg_pixmap_colored(self._icon_path, color, 256).scaled(
            QSize(38, 38), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
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
                    color: #007bff;
                    text-align: center;
                    padding: 4px 0px;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    font-size: 22px;
                    font-weight: 500;
                    background: #e8f0fe;
                    text-decoration: none;
                }
                QPushButton:hover { background: #dbe4f8; }
                QPushButton:focus { outline: none; border: 1px solid transparent; }
            """
            inactive_btn_style = self.get_nav_button_style(icon_only=True)
            active_label = "font-size: 10px; color: #007bff; margin-top: 0px; text-decoration: none; border: none;"
            inactive_label = "font-size: 10px; color: #495057; margin-top: 0px; text-decoration: none; border: none;"

        for btn in self.nav_buttons:
            if int(btn.property("pageIndex") or -1) == index:
                btn.setStyleSheet(active_btn_style)
            elif btn.isEnabled():
                btn.setStyleSheet(inactive_btn_style)
        for i, label in enumerate(self.nav_labels):
            if int(label.property("pageIndex") or -1) == index:
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
                ss = widget.styleSheet()
                if ss:
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
                try:
                    widget.setStyleSheet(ss)
                except RuntimeError:
                    pass
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
        """Create the redesigned clinician-focused dashboard page."""
        page = QWidget()
        page.setObjectName("dashboardPage")
        page.setStyleSheet("QWidget#dashboardPage { background: #f8f9fa; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        # ── Colour constants (light-theme defaults; dark overridden in refresh) ──
        # These are used here for initial build; refresh_dashboard re-applies them.

        # ── 0. WELCOME ROW (greeting + role left, date right) ────────
        self.welcome_label = QLabel(f"Welcome back, {self.username}")
        self.welcome_label.setObjectName("welcomeGreeting")
        self.welcome_label.setStyleSheet(
            "color: #212529; font-size: 22px; font-weight: 600; background: transparent;"
        )

        self.welcome_role_label = QLabel(f"{self.role.capitalize()}")
        self.welcome_role_label.setObjectName("welcomeRole")
        self.welcome_role_label.setStyleSheet(
            "color: #6c757d; font-size: 14px; font-weight: 500; background: transparent;"
        )

        self.dashboard_date_label = QLabel("")
        self.dashboard_date_label.setObjectName("dashDate")
        self.dashboard_date_label.setAlignment(Qt.AlignRight)
        self.dashboard_date_label.setStyleSheet(
            "color: #0066cc; font-size: 14px; font-weight: 600; background: transparent;"
        )

        welcome_row = QHBoxLayout()
        welcome_row.setSpacing(0)
        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        left_col.addWidget(self.welcome_label)
        left_col.addWidget(self.welcome_role_label)
        welcome_row.addLayout(left_col)
        welcome_row.addStretch()
        welcome_row.addWidget(self.dashboard_date_label, 0, Qt.AlignVCenter)
        layout.addLayout(welcome_row)

        # ── KPI STRIP (4 equal cards) ───────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(14)

        def make_kpi_card(object_name, title_text, accent):
            """Build a single KPI card with title, big value, and subtitle."""
            card = QWidget()
            card.setObjectName(object_name)
            card.setMinimumHeight(110)
            card.setStyleSheet(f"""
                QWidget#{object_name} {{
                    background: white;
                    border: 1px solid #dee2e6;
                    border-top: 3px solid {accent};
                    border-radius: 8px;
                }}
            """)
            v = QVBoxLayout(card)
            v.setContentsMargins(16, 12, 16, 12)
            v.setSpacing(4)

            title = QLabel(title_text)
            title.setObjectName(f"{object_name}_title")
            title.setStyleSheet(
                "color: #6c757d; font-size: 11px; font-weight: 700;"
                "letter-spacing: 0.5px; text-transform: uppercase; background: transparent;"
            )
            value = QLabel("—")
            value.setObjectName(f"{object_name}_value")
            value.setStyleSheet("font-size: 34px; font-weight: 700; color: #212529; background: transparent;")

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

        # Card 2: Flagged for Review  (the mission-critical number)
        card_flagged, self.high_attention_value, self.high_attention_hint = \
            make_kpi_card("kpiFlagged", "FLAGGED FOR REVIEW", "#d32f2f")

        # Card 3: Pending Review
        card_pending, self.pending_value, self.pending_sub = \
            make_kpi_card("kpiPending", "PENDING REVIEW", "#ed6c02")

        # Card 4: Average Confidence (with progress bar below value)
        card_conf, self.avg_confidence_value, self.conf_sub = \
            make_kpi_card("kpiConf", "MODEL CONFIDENCE", "#0066cc")

        # Add a visual progress bar under the confidence value
        self.conf_bar_track = QWidget()
        self.conf_bar_track.setFixedHeight(6)
        self.conf_bar_track.setStyleSheet(
            "background: #e9ecef; border-radius: 3px;"
        )
        self.conf_bar_fill = QWidget(self.conf_bar_track)
        self.conf_bar_fill.setFixedHeight(6)
        self.conf_bar_fill.setStyleSheet(
            "background: #0066cc; border-radius: 3px;"
        )
        self.conf_bar_fill.setFixedWidth(0)
        card_conf.layout().insertWidget(3, self.conf_bar_track)

        kpi_row.addWidget(card_total, 1)
        kpi_row.addWidget(card_flagged, 1)
        kpi_row.addWidget(card_pending, 1)
        kpi_row.addWidget(card_conf, 1)
        layout.addLayout(kpi_row)

        # ── 3. MAIN CONTENT AREA (two-column) ──────────────────────────
        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        # ── Left: Recent Screenings ──
        activity_card = QWidget()
        activity_card.setObjectName("activityCard")
        activity_card.setMinimumHeight(260)
        activity_card.setStyleSheet("""
            QWidget#activityCard {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        activity_v = QVBoxLayout(activity_card)
        activity_v.setContentsMargins(16, 14, 16, 14)
        activity_v.setSpacing(8)

        activity_header = QHBoxLayout()
        activity_title = QLabel("RECENT SCREENINGS")
        activity_title.setStyleSheet(
            "color: #6c757d; font-size: 11px; font-weight: 700;"
            "letter-spacing: 0.5px; text-transform: uppercase; background: transparent;"
        )
        activity_header.addWidget(activity_title)
        activity_header.addStretch()

        self.activity_count_label = QLabel("")
        self.activity_count_label.setStyleSheet(
            "color: #6c757d; font-size: 11px; background: transparent;"
        )
        activity_header.addWidget(self.activity_count_label)
        activity_v.addLayout(activity_header)

        # Column headers row
        col_header = QWidget()
        col_header.setObjectName("colHeader")
        col_header.setFixedHeight(26)
        col_header.setStyleSheet(
            "QWidget#colHeader { background: #f1f3f5; border-radius: 4px; }"
        )
        ch_layout = QHBoxLayout(col_header)
        ch_layout.setContentsMargins(8, 0, 8, 0)
        ch_layout.setSpacing(0)
        header_style = "font-size: 10px; font-weight: 700; color: #868e96; background: transparent; text-transform: uppercase;"
        for text, stretch in [("", 0), ("Patient ID", 2), ("Name", 3), ("Result", 3), ("Confidence", 2)]:
            lbl = QLabel(text)
            lbl.setStyleSheet(header_style)
            if stretch == 0:
                lbl.setFixedWidth(16)
            ch_layout.addWidget(lbl, stretch)
        self.col_header_widget = col_header
        activity_v.addWidget(col_header)

        # Scrollable rows container
        self.activity_rows_widget = QWidget()
        self.activity_rows_widget.setStyleSheet("background: transparent;")
        self.activity_rows_layout = QVBoxLayout(self.activity_rows_widget)
        self.activity_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.activity_rows_layout.setSpacing(2)
        activity_v.addWidget(self.activity_rows_widget, 1)

        # Empty-state label (hidden when data present)
        self.empty_activity_label = QLabel("No screening records yet. Start by running a new screening.")
        self.empty_activity_label.setObjectName("emptyActivity")
        self.empty_activity_label.setStyleSheet(
            "color: #6c757d; font-size: 13px; font-style: italic; padding: 24px; background: transparent;"
        )
        self.empty_activity_label.setAlignment(Qt.AlignCenter)
        self.empty_activity_label.setWordWrap(True)
        activity_v.addWidget(self.empty_activity_label)

        content_row.addWidget(activity_card, 7)

        # ── Right: Session + Quick Actions + Insight ──
        sidebar = QWidget()
        sidebar.setObjectName("dashSidebar")
        sidebar.setStyleSheet("QWidget#dashSidebar { background: transparent; }")
        sidebar_v = QVBoxLayout(sidebar)
        sidebar_v.setContentsMargins(0, 0, 0, 0)
        sidebar_v.setSpacing(14)

        # Quick Actions card
        actions_card = QWidget()
        actions_card.setObjectName("actionsCard")
        actions_card.setStyleSheet("""
            QWidget#actionsCard {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        actions_v = QVBoxLayout(actions_card)
        actions_v.setContentsMargins(16, 12, 16, 12)
        actions_v.setSpacing(8)

        actions_title = QLabel("QUICK ACTIONS")
        actions_title.setStyleSheet(
            "color: #6c757d; font-size: 11px; font-weight: 700;"
            "letter-spacing: 0.5px; background: transparent;"
        )
        actions_v.addWidget(actions_title)

        btn_new_screening = QPushButton("  New Screening")
        btn_new_screening.setCursor(Qt.PointingHandCursor)
        btn_new_screening.setFixedHeight(36)
        btn_new_screening.setStyleSheet("""
            QPushButton {
                background: #0066cc; color: white; border: none;
                border-radius: 6px; font-size: 13px; font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover { background: #0052a3; }
        """)
        btn_new_screening.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        actions_v.addWidget(btn_new_screening)

        btn_view_reports = QPushButton("  View Reports")
        btn_view_reports.setCursor(Qt.PointingHandCursor)
        btn_view_reports.setFixedHeight(36)
        btn_view_reports.setStyleSheet("""
            QPushButton {
                background: transparent; color: #0066cc;
                border: 1px solid #0066cc; border-radius: 6px;
                font-size: 13px; font-weight: 600; padding: 0 16px;
            }
            QPushButton:hover { background: #e8f0fe; }
        """)
        btn_view_reports.clicked.connect(lambda: self.pages.setCurrentIndex(3))
        actions_v.addWidget(btn_view_reports)
        self._dash_btn_new = btn_new_screening
        self._dash_btn_reports = btn_view_reports
        sidebar_v.addWidget(actions_card)

        # Clinical Insight card
        insight_card = QWidget()
        insight_card.setObjectName("insightCard")
        insight_card.setStyleSheet("""
            QWidget#insightCard {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        insight_v = QVBoxLayout(insight_card)
        insight_v.setContentsMargins(16, 12, 16, 12)
        insight_v.setSpacing(6)
        insight_title = QLabel("CLINICAL INSIGHT")
        insight_title.setStyleSheet(
            "color: #6c757d; font-size: 11px; font-weight: 700;"
            "letter-spacing: 0.5px; background: transparent;"
        )
        self.insight_label = QLabel("Start a screening to generate insight.")
        self.insight_label.setObjectName("insightLabel")
        self.insight_label.setStyleSheet("font-size: 12px; color: #495057; background: transparent;")
        self.insight_label.setWordWrap(True)
        insight_v.addWidget(insight_title)
        insight_v.addWidget(self.insight_label)
        insight_v.addStretch()
        sidebar_v.addWidget(insight_card)

        sidebar_v.addStretch()
        content_row.addWidget(sidebar, 3)
        layout.addLayout(content_row, 1)

        return page

    def refresh_dashboard(self):
        """Refresh all dashboard widgets with current data and correct theme colors."""
        dark = getattr(self, "_dark_mode", False)

        # ── Theme palette ──
        if dark:
            bg_page = "#1e1e2e"
            card_bg = "#313244"
            card_border = "#45475a"
            text_primary = "#cdd6f4"
            text_secondary = "#a6adc8"
            text_muted = "#6c7086"
            accent_blue = "#89b4fa"
            sev_red = "#f38ba8"
            sev_amber = "#fab387"
            sev_green = "#a6e3a1"
            col_header_bg = "#45475a"
            col_header_text = "#a6adc8"
            row_hover = "#3a3a4f"
            bar_track_bg = "#45475a"
            btn_primary_bg = "#89b4fa"
            btn_primary_text = "#1e1e2e"
            btn_primary_hover = "#74a8f7"
            btn_outline_color = "#89b4fa"
            btn_outline_hover_bg = "#313244"
        else:
            bg_page = "#f8f9fa"
            card_bg = "white"
            card_border = "#dee2e6"
            text_primary = "#212529"
            text_secondary = "#6c757d"
            text_muted = "#adb5bd"
            accent_blue = "#0066cc"
            sev_red = "#d32f2f"
            sev_amber = "#ed6c02"
            sev_green = "#2e7d32"
            col_header_bg = "#f1f3f5"
            col_header_text = "#868e96"
            row_hover = "#f1f3f5"
            bar_track_bg = "#e9ecef"
            btn_primary_bg = "#0066cc"
            btn_primary_text = "white"
            btn_primary_hover = "#0052a3"
            btn_outline_color = "#0066cc"
            btn_outline_hover_bg = "#e8f0fe"

        # ── Fetch data ──
        total = 0
        high_attention = 0
        pending_count = 0
        confidence_values = []
        rows = []
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                "SELECT patient_id, name, result, confidence "
                "FROM patient_records ORDER BY id DESC"
            )
            rows = cur.fetchall()
            conn.close()

            total = len(rows)
            for _, _, result, confidence_text in rows:
                result = str(result or "")
                if self._is_high_attention_result(result):
                    high_attention += 1
                if not result or "pending" in result.lower():
                    pending_count += 1
                conf_value = self._extract_confidence_value(str(confidence_text or ""))
                if conf_value is not None:
                    confidence_values.append(conf_value)
        except Exception:
            pass

        avg_conf = sum(confidence_values) / len(confidence_values) if confidence_values else None

        # ── Page background ──
        if hasattr(self, "dashboard_page"):
            self.dashboard_page.setStyleSheet(
                f"QWidget#dashboardPage {{ background: {bg_page}; }}"
            )

        # ── 0. Welcome row ──
        if hasattr(self, "welcome_label"):
            self.welcome_label.setStyleSheet(
                f"color: {text_primary}; font-size: 22px; font-weight: 600; background: transparent;"
            )
        if hasattr(self, "dashboard_date_label"):
            today = datetime.now().strftime("%A, %B %d, %Y")
            self.dashboard_date_label.setText(today)
            self.dashboard_date_label.setStyleSheet(
                f"color: {accent_blue}; font-size: 14px; font-weight: 600; background: transparent;"
            )
        if hasattr(self, "welcome_role_label"):
            self.welcome_role_label.setStyleSheet(
                f"color: {text_secondary}; font-size: 14px; font-weight: 500; background: transparent;"
            )

        # ── KPI cards ──
        kpi_title_style = (
            f"color: {text_secondary}; font-size: 11px; font-weight: 700;"
            "letter-spacing: 0.5px; text-transform: uppercase; background: transparent;"
        )
        kpi_value_style = f"font-size: 34px; font-weight: 700; color: {text_primary}; background: transparent;"
        kpi_sub_style = f"font-size: 11px; color: {text_secondary}; background: transparent;"

        def style_kpi(obj_name, accent, value_widget, sub_widget, value_text, sub_text):
            card = self.findChild(QWidget, obj_name)
            if card:
                card.setStyleSheet(
                    f"QWidget#{obj_name} {{ background: {card_bg};"
                    f"  border: 1px solid {card_border}; border-top: 3px solid {accent};"
                    f"  border-radius: 8px; }}"
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
                  str(total), "All saved DR screenings")

        flagged_accent = sev_red if high_attention > 0 else text_muted
        style_kpi("kpiFlagged", flagged_accent,
                  self.high_attention_value, self.high_attention_hint,
                  str(high_attention),
                  "Cases flagged for follow-up" if high_attention > 0 else "No cases flagged")

        style_kpi("kpiPending", sev_amber if pending_count > 0 else text_muted,
                  self.pending_value, self.pending_sub,
                  str(pending_count),
                  "Awaiting review" if pending_count > 0 else "All reviews complete")

        conf_display = f"{avg_conf:.1f}%" if avg_conf is not None else "—"
        style_kpi("kpiConf", accent_blue,
                  self.avg_confidence_value, self.conf_sub,
                  conf_display,
                  f"Across {len(confidence_values)} record{'s' if len(confidence_values) != 1 else ''}"
                  if confidence_values else "No confidence data yet")

        # Confidence progress bar
        if hasattr(self, "conf_bar_track"):
            self.conf_bar_track.setStyleSheet(
                f"background: {bar_track_bg}; border-radius: 3px;"
            )
            track_w = self.conf_bar_track.width() or 200
            fill_w = int(track_w * (avg_conf / 100.0)) if avg_conf is not None else 0
            bar_color = sev_green if (avg_conf or 0) >= 75 else (sev_amber if (avg_conf or 0) >= 50 else sev_red)
            self.conf_bar_fill.setStyleSheet(
                f"background: {bar_color}; border-radius: 3px;"
            )
            self.conf_bar_fill.setFixedWidth(max(0, min(fill_w, track_w)))

        # ── 3. Recent Screenings table ──
        if hasattr(self, "activity_rows_layout"):
            # Clear existing rows
            while self.activity_rows_layout.count():
                item = self.activity_rows_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Theme the card
            if hasattr(self, "col_header_widget"):
                self.col_header_widget.setStyleSheet(
                    f"QWidget#colHeader {{ background: {col_header_bg}; border-radius: 4px; }}"
                )
                for lbl in self.col_header_widget.findChildren(QLabel):
                    lbl.setStyleSheet(
                        f"font-size: 10px; font-weight: 700; color: {col_header_text};"
                        " background: transparent; text-transform: uppercase;"
                    )

            activity_card = self.findChild(QWidget, "activityCard")
            if activity_card:
                activity_card.setStyleSheet(
                    f"QWidget#activityCard {{ background: {card_bg};"
                    f"  border: 1px solid {card_border}; border-radius: 8px; }}"
                )

            if hasattr(self, "activity_count_label"):
                self.activity_count_label.setText(
                    f"Showing {min(len(rows), 8)} of {total}" if total else ""
                )
                self.activity_count_label.setStyleSheet(
                    f"color: {text_secondary}; font-size: 11px; background: transparent;"
                )

            # Activity title
            for lbl in (self.findChild(QWidget, "activityCard") or QWidget()).findChildren(QLabel):
                if lbl.text() == "RECENT SCREENINGS":
                    lbl.setStyleSheet(
                        f"color: {text_secondary}; font-size: 11px; font-weight: 700;"
                        "letter-spacing: 0.5px; text-transform: uppercase; background: transparent;"
                    )
                    break

            recent = rows[:8]
            if recent:
                self.empty_activity_label.setVisible(False)
                self.col_header_widget.setVisible(True)
                for patient_id, name, result, confidence in recent:
                    row_w = QWidget()
                    row_w.setFixedHeight(32)
                    row_w.setStyleSheet(
                        f"QWidget {{ background: transparent; }}"
                        f"QWidget:hover {{ background: {row_hover}; border-radius: 4px; }}"
                    )
                    rh = QHBoxLayout(row_w)
                    rh.setContentsMargins(8, 0, 8, 0)
                    rh.setSpacing(0)

                    result_str = str(result or "")
                    # Severity dot
                    if self._is_high_attention_result(result_str):
                        dot_color = sev_red
                    elif not result_str or "pending" in result_str.lower():
                        dot_color = sev_amber
                    else:
                        dot_color = sev_green

                    dot = QLabel("\u25cf")
                    dot.setFixedWidth(16)
                    dot.setStyleSheet(f"color: {dot_color}; font-size: 10px; background: transparent;")
                    dot.setAlignment(Qt.AlignCenter)

                    cell_style = f"font-size: 12px; color: {text_primary}; background: transparent;"
                    cell_secondary = f"font-size: 12px; color: {text_secondary}; background: transparent;"

                    pid_lbl = QLabel(str(patient_id or ""))
                    pid_lbl.setStyleSheet(cell_style)

                    name_lbl = QLabel(str(name or ""))
                    name_lbl.setStyleSheet(cell_style)

                    result_lbl = QLabel(result_str or "Pending")
                    if self._is_high_attention_result(result_str):
                        result_lbl.setStyleSheet(
                            f"font-size: 12px; color: {sev_red}; font-weight: 600; background: transparent;"
                        )
                    elif not result_str or "pending" in result_str.lower():
                        result_lbl.setStyleSheet(
                            f"font-size: 12px; color: {sev_amber}; font-style: italic; background: transparent;"
                        )
                    else:
                        result_lbl.setStyleSheet(cell_secondary)

                    conf_val = self._extract_confidence_value(str(confidence or ""))
                    conf_lbl = QLabel(f"{conf_val:.0f}%" if conf_val is not None else "—")
                    conf_lbl.setStyleSheet(cell_secondary)

                    rh.addWidget(dot, 0)
                    rh.addWidget(pid_lbl, 2)
                    rh.addWidget(name_lbl, 3)
                    rh.addWidget(result_lbl, 3)
                    rh.addWidget(conf_lbl, 2)
                    self.activity_rows_layout.addWidget(row_w)
                self.activity_rows_layout.addStretch()
            else:
                self.empty_activity_label.setVisible(True)
                self.col_header_widget.setVisible(False)
                self.empty_activity_label.setStyleSheet(
                    f"color: {text_muted}; font-size: 13px; font-style: italic;"
                    " padding: 24px; background: transparent;"
                )

        # ── 4. Sidebar cards ──
        for card_name in ("actionsCard", "insightCard"):
            card = self.findChild(QWidget, card_name)
            if card:
                card.setStyleSheet(
                    f"QWidget#{card_name} {{ background: {card_bg};"
                    f"  border: 1px solid {card_border}; border-radius: 8px; }}"
                )

        # Style section title labels in sidebar
        for card_name in ("actionsCard", "insightCard"):
            card = self.findChild(QWidget, card_name)
            if card:
                for lbl in card.findChildren(QLabel):
                    if lbl.text() in ("QUICK ACTIONS", "CLINICAL INSIGHT"):
                        lbl.setStyleSheet(
                            f"color: {text_secondary}; font-size: 11px; font-weight: 700;"
                            "letter-spacing: 0.5px; background: transparent;"
                        )

        # Quick-action buttons
        if hasattr(self, "_dash_btn_new"):
            self._dash_btn_new.setStyleSheet(f"""
                QPushButton {{
                    background: {btn_primary_bg}; color: {btn_primary_text}; border: none;
                    border-radius: 6px; font-size: 13px; font-weight: 600; padding: 0 16px;
                }}
                QPushButton:hover {{ background: {btn_primary_hover}; }}
            """)
        if hasattr(self, "_dash_btn_reports"):
            self._dash_btn_reports.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {btn_outline_color};
                    border: 1px solid {btn_outline_color}; border-radius: 6px;
                    font-size: 13px; font-weight: 600; padding: 0 16px;
                }}
                QPushButton:hover {{ background: {btn_outline_hover_bg}; }}
            """)

        # Clinical insight text
        if hasattr(self, "insight_label"):
            if total == 0:
                insight = "No screenings yet. Run a new screening to see trends here."
            elif high_attention > 0:
                pct = (high_attention / total * 100) if total else 0
                insight = (
                    f"{high_attention} of {total} screening{'s' if total != 1 else ''} "
                    f"({pct:.0f}%) flagged. Prioritize report review."
                )
            elif pending_count > 0:
                insight = f"{pending_count} screening{'s' if pending_count != 1 else ''} pending review. Complete assessments to clear the queue."
            else:
                insight = "All screenings reviewed — no action needed. Continue routine monitoring."
            self.insight_label.setText(insight)
            self.insight_label.setStyleSheet(
                f"font-size: 12px; color: {text_secondary}; background: transparent;"
            )

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
