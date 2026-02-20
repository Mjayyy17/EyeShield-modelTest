from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGroupBox, QScrollArea
from PySide6.QtCore import Qt

class HelpSupportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background: #f8f9fa;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(15)

        title = QLabel("Help & Support")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #007bff;")
        root_layout.addWidget(title)

        subtitle = QLabel("Quick guidance for daily workflows, troubleshooting, and support contacts.")
        subtitle.setStyleSheet("color: #495057; font-size: 13px;")
        root_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.addWidget(self.build_group(
            "Quick Start",
            """
            <ul>
                <li>Log in with your assigned role.</li>
                <li>Use <b>Screening</b> to capture patient details and upload a fundus image.</li>
                <li>Review the result, then save to <b>Patient Records</b>.</li>
                <li>Generate summaries in <b>Reports</b>.</li>
            </ul>
            """
        ))

        content_layout.addWidget(self.build_group(
            "How-to Guides",
            """
            <ul>
                <li><b>New screening:</b> Enter patient info, upload image, analyze, then save.</li>
                <li><b>Edit records:</b> Open a patient in <b>Records</b> and update details.</li>
                <li><b>Export report:</b> Use <b>Reports</b> to create PDF or print summaries.</li>
            </ul>
            """
        ))

        content_layout.addWidget(self.build_group(
            "FAQ",
            """
            <ul>
                <li><b>Cannot log in:</b> Verify username/role and reset password with Admin.</li>
                <li><b>Missing patient:</b> Check spelling, ID format, and date filters.</li>
                <li><b>Image not loading:</b> Use JPG/PNG and confirm file permissions.</li>
            </ul>
            """
        ))

        content_layout.addWidget(self.build_group(
            "Troubleshooting",
            """
            <ul>
                <li>Restart the app if pages are unresponsive.</li>
                <li>Confirm network or storage access for saving reports.</li>
                <li>Check printer settings or switch to PDF export.</li>
            </ul>
            """
        ))

        content_layout.addWidget(self.build_group(
            "Privacy & Compliance",
            """
            <ul>
                <li>Only access patient data needed for care.</li>
                <li>Do not share screenshots or exports outside approved channels.</li>
                <li>Log out when leaving the workstation.</li>
            </ul>
            """
        ))

        content_layout.addWidget(self.build_group(
            "Contact Support",
            """
            <p><b>Email:</b> support@eyeshield.local<br>
            <b>Phone:</b> +1-000-000-0000<br>
            <b>Hours:</b> Mon-Fri, 8:00 AM - 6:00 PM</p>
            """
        ))

        content_layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    @staticmethod
    def build_group(title, body_html):
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 15px;
                font-weight: 700;
                color: #007bff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px 0 8px;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 28, 16, 16)

        body = QLabel(body_html)
        body.setTextFormat(Qt.RichText)
        body.setWordWrap(True)
        body.setStyleSheet("color: #495057; font-size: 13px;")
        layout.addWidget(body)
        return group
