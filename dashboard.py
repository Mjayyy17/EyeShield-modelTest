"""
Dashboard module for EyeShield EMR application.
Contains main application window and dashboard functionality.
"""

import random

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt

from screening import ScreeningPage
from patient_records import PatientRecordsPage
from reports import ReportsPage
from users import UsersPage
from settings import SettingsPage
from help_support import HelpSupportPage


class EyeShieldApp(QMainWindow):
    """Main application window"""

    def __init__(self, username, role):
        super().__init__()

        self.username = username
        self.role = role

        self.setWindowTitle("EyeShield – DR Screening")
        self.setMinimumSize(1350, 850)

        root = QWidget()
        root_layout = QVBoxLayout(root)

        # Create top navigation bar
        nav_bar = QWidget()
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(10)
        nav_bar.setStyleSheet("background: #f8f9fa; border-bottom: 1px solid #dee2e6;")


        # App title
        title_label = QLabel("EyeShield EMR")
        title_label.setStyleSheet("color: #007bff; font-size: 22px; font-weight: bold; margin-right: 30px;")
        nav_layout.addWidget(title_label)

        # Navigation buttons with icons and small text labels below
        def nav_button_with_label(icon, text):
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            btn = QPushButton(icon)
            btn.setStyleSheet(self.get_nav_button_style(icon_only=True))
            btn.setFixedSize(36, 36)
            label = QLabel(text)
            label.setAlignment(Qt.AlignHCenter)
            label.setStyleSheet("font-size: 10px; color: #495057; margin-top: 0px;")
            v.addWidget(btn)
            v.addWidget(label)
            return w, btn, label

        navs = [
            ("📊", "Dashboard"),
            ("🩺", "Screening"),
            ("📁", "Records"),
            ("📄", "Reports"),
            ("👥", "Users"),
            ("⚙️", "Settings"),
            ("❓", "Help")
        ]
        nav_widgets = []
        nav_buttons = []
        nav_labels = []
        for icon, text in navs:
            w, btn, label = nav_button_with_label(icon, text)
            nav_layout.addWidget(w)
            nav_widgets.append(w)
            nav_buttons.append(btn)
            nav_labels.append(label)


        # User info on the right
        nav_layout.addStretch()
        user_info = QLabel(f"👤 {self.username} ({self.role})")
        user_info.setStyleSheet("color: #495057; font-size: 12px; font-weight: 500; margin-left: 18px; margin-right: 8px;")
        nav_layout.addWidget(user_info)

        logout_btn = QPushButton("Logout")
        logout_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #c82333; }
        """)
        logout_btn.clicked.connect(self.handle_logout)
        nav_layout.addWidget(logout_btn)

        # Connect buttons
        nav_buttons[0].clicked.connect(lambda: self._navigate_to(0))
        nav_buttons[1].clicked.connect(lambda: self._navigate_to(1))
        nav_buttons[2].clicked.connect(lambda: self._navigate_to(2))
        nav_buttons[3].clicked.connect(lambda: self._navigate_to(3))
        nav_buttons[4].clicked.connect(lambda: self._navigate_to(4, requires_admin=True))
        nav_buttons[5].clicked.connect(lambda: self._navigate_to(5))
        nav_buttons[6].clicked.connect(lambda: self._navigate_to(6))

        if self.role != "admin":
            nav_buttons[4].setEnabled(False)
            nav_buttons[4].setToolTip("Admins only")
            nav_labels[4].setStyleSheet("font-size: 10px; color: #adb5bd; margin-top: 0px;")

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
        self.patient_records_page = PatientRecordsPage()
        self.reports_page = ReportsPage()
        self.users_page = UsersPage()
        self.settings_page = SettingsPage()
        self.help_support_page = HelpSupportPage()

        # Dashboard is created after the other pages so it can be refreshed
        self.dashboard_page = self.create_dashboard_page()

        # Allow screening page to add records directly to the patient records page
        # so saved screenings appear immediately in the Records view.
        self.screening_page.patient_records_page = self.patient_records_page
        # Let patient records notify the app when rows are added
        self.patient_records_page.parent_app = self

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.screening_page)
        self.pages.addWidget(self.patient_records_page)
        self.pages.addWidget(self.reports_page)
        self.pages.addWidget(self.users_page)
        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.help_support_page)

        main_layout.addWidget(self.pages)
        root_layout.addWidget(main)
        self.setCentralWidget(root)

    # Sidebar removed; navigation is now in the top bar

    def _navigate_to(self, index, requires_admin=False):
        if requires_admin and self.role != "admin":
            QMessageBox.warning(self, "Access Denied", "Only admins can access the Users tab.")
            return
        self.pages.setCurrentIndex(index)

    def handle_logout(self):
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from login import LoginWindow
            self.login = LoginWindow()
            self.login.show()
            self.close()

    def create_dashboard_page(self):
        """Create dashboard page"""
        from datetime import datetime
        page = QWidget()
        page.setStyleSheet("background: #f8f9fa;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(30)

        # Welcome section
        welcome_widget = QWidget()
        welcome_widget.setStyleSheet("""
            QWidget {
                background: #007bff;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        welcome_layout = QVBoxLayout(welcome_widget)

        welcome_title = QLabel(f"Welcome, {self.username}!")
        welcome_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        welcome_subtitle = QLabel("Electronic Medical Records - Diabetic Retinopathy Screening System")
        welcome_subtitle.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 14px; margin-top: 5px;")

        welcome_layout.addWidget(welcome_title)
        welcome_layout.addWidget(welcome_subtitle)
        layout.addWidget(welcome_widget)

        # Motivational Quote and Today's Date
        quote_box = QWidget()
        quote_layout = QVBoxLayout(quote_box)
        quote_layout.setContentsMargins(0, 0, 0, 0)

        quote = QLabel(self.get_medical_quote())
        quote.setStyleSheet("font-size: 15px; color: #343a40; font-style: italic; background: white; border-radius: 8px; border: 1px solid #dee2e6; padding: 16px 24px;")
        quote.setWordWrap(True)
        quote.setTextFormat(Qt.RichText)
        quote_layout.addWidget(quote)

        today = datetime.now().strftime('%A, %B %d, %Y')
        date_label = QLabel(f"Today: <b>{today}</b>")
        date_label.setStyleSheet("font-size: 13px; color: #007bff; margin-top: 4px;")
        date_label.setTextFormat(Qt.RichText)
        quote_layout.addWidget(date_label)

        layout.addWidget(quote_box)

        # Clinical Actions
        actions_group = QGroupBox("Clinical Actions")
        actions_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #007bff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
            }
        """)
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setContentsMargins(20, 40, 20, 20)
        actions_layout.setSpacing(15)

        def make_action_btn(label, color, hover):
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 12px 18px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: {hover}; }}
            """)
            return btn

        btn_new = make_action_btn("🩺 New Patient Screening", "#28a745", "#218838")
        btn_new.clicked.connect(lambda: self.pages.setCurrentIndex(1))

        btn_records = make_action_btn("📁 Patient Records", "#007bff", "#0056b3")
        btn_records.clicked.connect(lambda: self.pages.setCurrentIndex(2))

        btn_reports = make_action_btn("📄 Reports", "#17a2b8", "#117a8b")
        btn_reports.clicked.connect(lambda: self.pages.setCurrentIndex(3))

        btn_users = make_action_btn("👥 Users", "#6f42c1", "#563d7c")
        btn_users.clicked.connect(lambda: self.pages.setCurrentIndex(4))

        actions_layout.addWidget(btn_new)
        actions_layout.addWidget(btn_records)
        actions_layout.addWidget(btn_reports)
        actions_layout.addWidget(btn_users)
        actions_layout.addStretch()

        layout.addWidget(actions_group)

        # Recent Activity
        activity_group = QGroupBox("Recent Clinical Activity")
        activity_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #007bff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
            }
        """)

        activity_layout = QVBoxLayout(activity_group)
        activity_layout.setContentsMargins(20, 20, 20, 20)

        self.recent_activity_label = QLabel("No recent clinical activity. Ready for patient screenings.")
        self.recent_activity_label.setStyleSheet("color: #6c757d; font-size: 14px; font-style: italic;")
        self.recent_activity_label.setWordWrap(True)
        activity_layout.addWidget(self.recent_activity_label)

        layout.addWidget(activity_group)

        layout.addStretch()

        # After building the page, attempt an initial refresh if data exists
        return page

    @staticmethod
    def get_medical_quote():
        quotes = [
            ("Wherever the art of Medicine is loved, there is also a love of Humanity.", "Hippocrates"),
            ("Healing is a matter of time, but it is sometimes also a matter of opportunity.", "Hippocrates"),
            ("Life is short, art is long, opportunity fleeting, experience treacherous, judgment difficult.", "Hippocrates"),
            ("First, do no harm.", "Hippocrates (attributed)"),
            ("Let food be thy medicine and medicine be thy food.", "Hippocrates (attributed)"),
            ("The good physician treats the disease; the great physician treats the patient who has the disease.", "William Osler"),
            ("Medicine is a science of uncertainty and an art of probability.", "William Osler"),
            ("Listen to the patient, he is telling you the diagnosis.", "William Osler"),
            ("The practice of medicine is an art, based on science.", "William Osler"),
            ("To study the phenomena of disease without books is to sail an uncharted sea; to study books without patients is not to go to sea at all.", "William Osler"),
            ("Cure sometimes, treat often, comfort always.", "Ambroise Pare"),
            ("The art of medicine consists of amusing the patient while nature cures the disease.", "Voltaire"),
            ("The best physician is also a philosopher.", "Galen (attributed)"),
            ("In nothing do men more nearly approach the gods than in giving health to men.", "Cicero"),
            ("The dose makes the poison.", "Paracelsus"),
            ("In the fields of observation, chance favors the prepared mind.", "Louis Pasteur"),
            ("Medicine is a social science, and politics is nothing else but medicine on a large scale.", "Rudolf Virchow"),
            ("He who takes medicine and neglects diet wastes the skill of the physician.", "Hippocrates (attributed)"),
            ("To cure a disease after it has taken hold is like digging a well after one is thirsty.", "Chinese proverb"),
            ("A good laugh and a long sleep are the best cures in the doctor's book.", "Irish proverb"),
        ]
        text, author = random.choice(quotes)
        return f'"{text}"<br><span style=\'color:#007bff;\'>- {author}</span>'

    def refresh_dashboard(self):
        """Refresh recent activity from patient records"""
        try:
            table = self.patient_records_page.patient_table
            total = table.rowCount()
            results_idx = 12

            recent_lines = []
            for r in range(total - 1, max(-1, total - 6), -1):
                pid_item = table.item(r, 0)
                name_item = table.item(r, 1)
                result_item = table.item(r, results_idx)
                pid = pid_item.text() if pid_item else ""
                name = name_item.text() if name_item else ""
                result = result_item.text() if result_item else ""
                recent_lines.append(f"{pid} — {name} — {result}")

            if recent_lines:
                self.recent_activity_label.setStyleSheet("color: #495057; font-size: 14px;")
                self.recent_activity_label.setText("\n".join(recent_lines))
            else:
                self.recent_activity_label.setStyleSheet("color: #6c757d; font-size: 14px; font-style: italic;")
                self.recent_activity_label.setText("No recent clinical activity. Ready for patient screenings.")
        except Exception:
            pass

    @staticmethod
    def get_nav_button_style(icon_only=False):
        """Get navigation button stylesheet. If icon_only, use smaller font and center icon."""
        if icon_only:
            return """
                QPushButton {
                    color: #495057;
                    text-align: center;
                    padding: 8px 10px;
                    border: none;
                    border-radius: 6px;
                    font-size: 18px;
                    font-weight: 500;
                    margin: 2px 6px;
                    min-width: 36px;
                    min-height: 36px;
                    background: transparent;
                }
                QPushButton:hover {
                    background: #e9ecef;
                    color: #007bff;
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
                    margin: 2px 15px;
                    background: transparent;
                }
                QPushButton:hover {
                    background: #e9ecef;
                    color: #007bff;
                }
            """