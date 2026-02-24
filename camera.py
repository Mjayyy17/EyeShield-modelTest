"""
Temporary camera page for EyeShield EMR.
Uses system webcam until fundus camera integration is available.
"""

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget


class CameraPage(QWidget):
    """Temporary camera page that streams the default webcam."""

    def __init__(self):
        super().__init__()
        self.camera = None
        self.capture_session = None
        self.video_widget = None
        self.status_label = None
        self.start_btn = None
        self.stop_btn = None
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background: #f8f9fa;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Temporary Webcam")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #007bff;")

        subtitle = QLabel("Use this while fundus camera integration is in progress.")
        subtitle.setStyleSheet("font-size: 13px; color: #495057;")

        self.status_label = QLabel("Camera is stopped.")
        self.status_label.setStyleSheet("font-size: 12px; color: #6c757d;")

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(900, 520)
        self.video_widget.setStyleSheet("background: #000000; border: 1px solid #dee2e6; border-radius: 8px;")

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.start_btn = QPushButton("Start Camera")
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #218838; }
            """
        )
        self.start_btn.clicked.connect(self.start_camera)

        self.stop_btn = QPushButton("Stop Camera")
        self.stop_btn.setStyleSheet(
            """
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #c82333; }
            """
        )
        self.stop_btn.clicked.connect(self.stop_camera)
        self.stop_btn.setEnabled(False)

        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addStretch()

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.status_label)
        layout.addWidget(self.video_widget, 1)
        layout.addLayout(controls)

    def start_camera(self):
        if self.camera is not None:
            return

        cameras = QMediaDevices.videoInputs()
        if not cameras:
            self.status_label.setText("No camera device detected.")
            QMessageBox.warning(self, "Camera Unavailable", "No webcam was detected on this device.")
            return

        self.camera = QCamera(cameras[0])
        self.capture_session = QMediaCaptureSession()
        self.capture_session.setCamera(self.camera)
        self.capture_session.setVideoOutput(self.video_widget)
        self.camera.start()

        self.status_label.setText(f"Streaming: {cameras[0].description()}")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_camera(self):
        if self.camera is None:
            return

        self.camera.stop()
        self.camera.deleteLater()
        self.camera = None
        self.capture_session = None

        self.status_label.setText("Camera is stopped.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def enter_page(self):
        self.start_camera()

    def leave_page(self):
        self.stop_camera()

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)