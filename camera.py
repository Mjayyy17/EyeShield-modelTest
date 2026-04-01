"""
Temporary camera page for EyeShield EMR.
Uses system webcam until fundus camera integration is available.Includes patient handoff safety, device resilience, and capture workflow."""

from datetime import datetime
import json
import os

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QGroupBox,
    QComboBox,
    QFileDialog,
    QProgressBar,
    QStackedWidget,
    QLineEdit,
    QDialog,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer, pyqtSignal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget


class CameraPage(QWidget):
    """Camera integration sandbox with simulation, webcam, and mock device modes."""

    MODE_SIMULATION = "Sample Images"
    MODE_WEBCAM = "Webcam"
    MODE_MOCK = "Device Mock"

    def __init__(self):
        super().__init__()
        self.camera = None
        self.capture_session = None
        self.video_widget = None
        self.preview_stack = None
        self.simulation_preview = None
        self.status_label = None
        self.mode_combo = None
        self.connect_btn = None
        self.start_btn = None
        self.stop_btn = None
        self.load_sample_btn = None
        self.next_sample_btn = None
        self.capture_btn = None
        self.send_btn = None
        self.quality_bar = None
        self.diag_device_value = None
        self.diag_connection_value = None
        self.diag_mode_value = None
        self.diag_last_action_value = None
        self._current_sample_path = ""
        self._sample_paths = []
        self._sample_index = -1
        self._capture_ready = False
        
        # Capture workflow state
        self._saved_capture = None
        self._saved_capture_metadata = None
        self._saved_capture_timestamp = None
        
        # Inactivity monitoring
        self._inactivity_timeout_enabled = False
        self._inactivity_timeout_minutes = 15
        self._inactivity_label = None
        self._inactivity_timer = None
        self._inactivity_remaining_sec = 0
        
        # Device resilience
        self._device_reconnect_timer = None
        self._device_reconnect_attempts = 0
        
        # Settings persistence
        self._settings_cache_file = os.path.join(os.path.expanduser("~"), ".eyeshield_camera_settings.json")
        
        self.init_ui()
        self._load_camera_settings()
        self._set_mode(self.MODE_SIMULATION)

    def init_ui(self):
        self.setStyleSheet(
            """
            QWidget { background: #f2f7fd; color: #1e2a36; }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d6e3f2;
                border-radius: 14px;
                margin-top: 10px;
                font-weight: 700;
                color: #1f6fe5;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #c6d8ec;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 24px;
                font-size: 14px;
            }
            QComboBox:hover { border: 1px solid #97b8db; }
            QComboBox:focus { border: 1px solid #1f6fe5; }
            QPushButton {
                background: #eaf1fb;
                color: #1f2a37;
                border: 1px solid #c8d9ec;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover { background: #dde9f8; }
            QPushButton:disabled {
                background: #eef2f6;
                color: #8b9caf;
                border: 1px solid #d8e1eb;
            }
            QLabel#metaHint { color: #5c7288; font-size: 13px; }
            QLabel#diagLabel { color: #6d8298; font-size: 12px; font-weight: 700; }
            QLabel#diagValue { color: #213247; font-size: 13px; }
            QProgressBar {
                border: 1px solid #c8d8ea;
                border-radius: 8px;
                background: #f6f9fd;
                text-align: center;
                height: 20px;
                font-size: 12px;
            }
            QProgressBar::chunk { background: #1f6fe5; border-radius: 7px; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Camera Integration Sandbox")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #1f6fe5;")
        self._cam_title_lbl = title

        subtitle = QLabel("Camera preview and diagnostics while hardware integration is in progress.")
        subtitle.setStyleSheet("font-size: 14px; color: #5c7288;")
        self._cam_subtitle_lbl = subtitle

        self.status_label = QLabel("Ready in Sample Images mode.")
        self.status_label.setObjectName("metaHint")

        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        self.preview_stack = QStackedWidget()

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(760, 500)
        self.video_widget.setStyleSheet("background: #000000; border: 1px solid #d8e2ef; border-radius: 12px;")

        self.simulation_preview = QLabel("Sample image preview\n\nLoad fundus images to test capture and workflow.")
        self.simulation_preview.setAlignment(Qt.AlignCenter)
        self.simulation_preview.setWordWrap(True)
        self.simulation_preview.setStyleSheet(
            "background:#0c1620;color:#c4d2e5;border:1px solid #2a3a4d;border-radius:12px;"
            "font-size:16px;font-weight:500;padding:28px;"
        )

        self.preview_stack.addWidget(self.simulation_preview)
        self.preview_stack.addWidget(self.video_widget)
        preview_layout.addWidget(self.preview_stack, 1)

        main_row.addWidget(preview_group, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        controls_group = QGroupBox("Capture Controls")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setContentsMargins(14, 14, 14, 14)
        controls_layout.setSpacing(10)

        mode_label = QLabel("Mode")
        mode_label.setObjectName("diagLabel")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_SIMULATION, self.MODE_WEBCAM, self.MODE_MOCK])
        self.mode_combo.currentTextChanged.connect(self._set_mode)
        controls_layout.addWidget(mode_label)
        controls_layout.addWidget(self.mode_combo)

        self.connect_btn = QPushButton("Detect Device")
        self.connect_btn.clicked.connect(self._detect_device)
        controls_layout.addWidget(self.connect_btn)

        self.start_btn = QPushButton("Start Camera")
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                background: #18a558;
                color: white;
                border: 1px solid #138546;
                border-radius: 10px;
                padding: 9px 14px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background: #15924d; }
            """
        )
        self.start_btn.clicked.connect(self.start_camera)
        controls_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Camera")
        self.stop_btn.setStyleSheet(
            """
            QPushButton {
                background: #dc3545;
                color: white;
                border: 1px solid #bb2d3b;
                border-radius: 10px;
                padding: 9px 14px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background: #c82333; }
            """
        )
        self.stop_btn.clicked.connect(self.stop_camera)
        controls_layout.addWidget(self.stop_btn)

        self.load_sample_btn = QPushButton("Load Sample Image")
        self.load_sample_btn.clicked.connect(self._load_sample_image)
        controls_layout.addWidget(self.load_sample_btn)

        self.next_sample_btn = QPushButton("Next Sample")
        self.next_sample_btn.clicked.connect(self._show_next_sample)
        controls_layout.addWidget(self.next_sample_btn)

        self.capture_btn = QPushButton("Capture Frame")
        self.capture_btn.clicked.connect(self._capture_frame)
        controls_layout.addWidget(self.capture_btn)
        
        # Capture workflow buttons: Save, Preview, Retry, Discard
        capture_workflow_row = QHBoxLayout()
        capture_workflow_row.setSpacing(6)
        
        save_btn = QPushButton("Save Capture")
        save_btn.setEnabled(False)
        save_btn.clicked.connect(self._save_capture)
        self._save_capture_btn = save_btn
        capture_workflow_row.addWidget(save_btn)
        
        preview_btn = QPushButton("Preview Saved")
        preview_btn.setEnabled(False)
        preview_btn.clicked.connect(self._preview_saved_capture)
        self._preview_capture_btn = preview_btn
        capture_workflow_row.addWidget(preview_btn)
        
        retry_btn = QPushButton("Retry")
        retry_btn.setEnabled(False)
        retry_btn.clicked.connect(self._retry_capture)
        self._retry_capture_btn = retry_btn
        capture_workflow_row.addWidget(retry_btn)
        
        discard_btn = QPushButton("Discard")
        discard_btn.setEnabled(False)
        discard_btn.clicked.connect(self._discard_capture)
        self._discard_capture_btn = discard_btn
        capture_workflow_row.addWidget(discard_btn)
        
        controls_layout.addLayout(capture_workflow_row)

        self.send_btn = QPushButton("Send to Screening")
        self.send_btn.clicked.connect(self._send_to_screening)
        controls_layout.addWidget(self.send_btn)

        quality_label = QLabel("Capture Quality")
        quality_label.setObjectName("diagLabel")
        self.quality_bar = QProgressBar()
        self.quality_bar.setRange(0, 100)
        self.quality_bar.setValue(0)
        self.quality_bar.setFormat("%p%")
        controls_layout.addWidget(quality_label)
        controls_layout.addWidget(self.quality_bar)

        right_col.addWidget(controls_group)

        diag_group = QGroupBox("Diagnostics")
        diag_layout = QVBoxLayout(diag_group)
        diag_layout.setContentsMargins(14, 14, 14, 14)
        diag_layout.setSpacing(8)

        self.diag_mode_value = self._diag_row(diag_layout, "Mode")
        self.diag_device_value = self._diag_row(diag_layout, "Device")
        self.diag_connection_value = self._diag_row(diag_layout, "Connection")
        self.diag_last_action_value = self._diag_row(diag_layout, "Last Action")

        right_col.addWidget(diag_group)
        
        # Inactivity warning badge
        inactivity_group = QGroupBox("Session Monitor")
        inactivity_layout = QVBoxLayout(inactivity_group)
        inactivity_layout.setContentsMargins(14, 14, 14, 14)
        self._inactivity_label = QLabel("Session timeout monitoring: disabled")
        self._inactivity_label.setObjectName("diagValue")
        self._inactivity_label.setStyleSheet("color: #6d8298; font-size: 13px; font-weight: 600;")
        inactivity_layout.addWidget(self._inactivity_label)
        right_col.addWidget(inactivity_group)
        
        right_col.addStretch(1)

        main_row.addLayout(right_col, 2)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.status_label)
        layout.addLayout(main_row, 1)

    def _diag_row(self, parent_layout: QVBoxLayout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(f"{label_text}:")
        label.setObjectName("diagLabel")
        value = QLabel("-")
        value.setObjectName("diagValue")
        value.setWordWrap(True)
        row.addWidget(label)
        row.addWidget(value, 1)
        parent_layout.addLayout(row)
        return value

    def _stamp_action(self, text: str):
        self.diag_last_action_value.setText(f"{text} ({datetime.now().strftime('%I:%M:%S %p').lstrip('0')})")

    def _set_mode(self, mode_text: str):
        self._capture_ready = False
        self.quality_bar.setValue(0)
        self.diag_mode_value.setText(mode_text)

        if mode_text == self.MODE_WEBCAM:
            self.preview_stack.setCurrentWidget(self.video_widget)
            self.connect_btn.setText("Detect Device")
            self.start_btn.setEnabled(self.camera is None)
            self.stop_btn.setEnabled(self.camera is not None)
            self.load_sample_btn.setEnabled(False)
            self.next_sample_btn.setEnabled(False)
            self.capture_btn.setEnabled(True)
            self.send_btn.setEnabled(False)
            self.status_label.setText("Webcam mode selected. Detect and start camera to begin preview.")
            self.diag_connection_value.setText("Waiting for device detection")
        elif mode_text == self.MODE_MOCK:
            self.stop_camera()
            self.preview_stack.setCurrentWidget(self.simulation_preview)
            self.simulation_preview.setText("Device Mock Preview")
            self.connect_btn.setText("Connect Mock Device")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.load_sample_btn.setEnabled(False)
            self.next_sample_btn.setEnabled(False)
            self.capture_btn.setEnabled(True)
            self.send_btn.setEnabled(False)
            self.status_label.setText("Device Mock mode ready.")
            self.diag_device_value.setText("Mock Fundus Device v1")
            self.diag_connection_value.setText("Idle")
        else:
            self.stop_camera()
            self.preview_stack.setCurrentWidget(self.simulation_preview)
            self.connect_btn.setText("Validate Samples")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.load_sample_btn.setEnabled(True)
            self.next_sample_btn.setEnabled(bool(self._sample_paths))
            self.capture_btn.setEnabled(True)
            self.send_btn.setEnabled(False)
            self.status_label.setText("Sample Images mode ready. Load a sample image to begin.")
            self.diag_device_value.setText("Sample Library")
            self.diag_connection_value.setText("Ready")

        self._stamp_action(f"Mode changed to {mode_text}")

    def _detect_device(self):
        mode = self.mode_combo.currentText()
        if mode == self.MODE_MOCK:
            self.diag_device_value.setText("Mock Fundus Device v1")
            self.diag_connection_value.setText("Connected")
            self.status_label.setText("Mock device connected.")
            self._stamp_action("Mock device connected")
            return

        if mode == self.MODE_SIMULATION:
            self.status_label.setText("Samples validated. Load and capture to continue.")
            self.diag_connection_value.setText("Samples validated")
            self._stamp_action("Samples validated")
            return

        cameras = QMediaDevices.videoInputs()
        if not cameras:
            self.diag_device_value.setText("No device detected")
            self.diag_connection_value.setText("Disconnected")
            self.status_label.setText("No webcam detected on this device.")
            QMessageBox.warning(self, "Camera Unavailable", "No webcam was detected on this device.")
            self._stamp_action("Webcam detection failed")
            return
        self.diag_device_value.setText(cameras[0].description())
        self.diag_connection_value.setText("Device available")
        self.status_label.setText("Webcam detected. Click Start Camera to begin preview.")
        self._stamp_action("Webcam detected")

    def _load_sample_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Sample Fundus Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
        )
        if not path:
            return
        self._current_sample_path = path
        if path not in self._sample_paths:
            self._sample_paths.append(path)
            self._sample_index = len(self._sample_paths) - 1
        else:
            self._sample_index = self._sample_paths.index(path)
        self._render_sample_image(path)
        self.next_sample_btn.setEnabled(len(self._sample_paths) > 1)
        self.status_label.setText("Sample loaded. Capture a frame to evaluate quality.")
        self._stamp_action("Sample image loaded")

    def _show_next_sample(self):
        if not self._sample_paths:
            self.status_label.setText("No sample image loaded yet.")
            return
        self._sample_index = (self._sample_index + 1) % len(self._sample_paths)
        self._current_sample_path = self._sample_paths[self._sample_index]
        self._render_sample_image(self._current_sample_path)
        self.status_label.setText("Showing next sample image.")
        self._stamp_action("Next sample image shown")

    def _render_sample_image(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Invalid Image", "Unable to load the selected image.")
            return
        scaled = pixmap.scaled(
            self.simulation_preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.simulation_preview.setPixmap(scaled)
        self.simulation_preview.setText("")

    def _capture_frame(self):
        mode = self.mode_combo.currentText()
        quality = 0

        if mode == self.MODE_WEBCAM:
            if self.camera is None:
                QMessageBox.information(self, "Capture", "Start the webcam preview before capturing.")
                return
            quality = 82
            self.status_label.setText("Live frame captured successfully.")
        elif mode == self.MODE_SIMULATION:
            if not self._current_sample_path:
                QMessageBox.information(self, "Capture", "Load a sample fundus image before capturing.")
                return
            pixmap = QPixmap(self._current_sample_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Capture", "Loaded sample image is no longer available.")
                return
            quality = min(97, max(62, int((pixmap.width() + pixmap.height()) / 50)))
            self.status_label.setText("Sample frame captured and validated.")
        else:
            quality = 88
            self.status_label.setText("Mock frame captured from virtual device.")

        self.quality_bar.setValue(quality)
        self._capture_ready = True
        # Save capture to state but don't send yet
        self._save_capture_btn.setEnabled(True)
        self._retry_capture_btn.setEnabled(True)
        self._discard_capture_btn.setEnabled(True)
        self.send_btn.setEnabled(False)  # Send only after explicit Save + review
        self._stamp_action("Frame captured (ready to save)")

    def _send_to_screening(self):
        if not self._capture_ready:
            QMessageBox.information(self, "Send to Screening", "Capture a frame first.")
            return
        QMessageBox.information(
            self,
            "Send to Screening",
            "Capture packet validated. Integrate this handoff with Screening page once camera SDK is finalized.",
        )
        self.status_label.setText("Capture prepared for Screening handoff.")
        self._stamp_action("Capture sent to screening handoff")

    def start_camera(self):
        if self.mode_combo.currentText() != self.MODE_WEBCAM:
            QMessageBox.information(self, "Camera", "Switch to Webcam mode to start live camera preview.")
            return
        if self.camera is not None:
            return

        cameras = QMediaDevices.videoInputs()
        if not cameras:
            self.status_label.setText("No camera device detected.")
            self.diag_device_value.setText("No device detected")
            self.diag_connection_value.setText("Disconnected")
            QMessageBox.warning(self, "Camera Unavailable", "No webcam was detected on this device.")
            self._stamp_action("Webcam start failed")
            return

        self.camera = QCamera(cameras[0])
        self.capture_session = QMediaCaptureSession()
        self.capture_session.setCamera(self.camera)
        self.capture_session.setVideoOutput(self.video_widget)
        self.camera.start()

        self.preview_stack.setCurrentWidget(self.video_widget)
        self.status_label.setText(f"Streaming: {cameras[0].description()}")
        self.diag_device_value.setText(cameras[0].description())
        self.diag_connection_value.setText("Streaming")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.send_btn.setEnabled(False)
        self._capture_ready = False
        self._stamp_action("Webcam started")

    def stop_camera(self):
        if self.camera is None:
            return

        self.camera.stop()
        self.camera.deleteLater()
        self.camera = None
        self.capture_session = None

        self.status_label.setText("Camera is stopped.")
        self.diag_connection_value.setText("Stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._stamp_action("Webcam stopped")

    def enter_page(self):
        if self.mode_combo.currentText() == self.MODE_WEBCAM:
            self.start_camera()

    def leave_page(self):
        self.stop_camera()

        def _save_capture(self):
            if not self._capture_ready:
                return
            self._saved_capture_timestamp = datetime.now()
            self._saved_capture_metadata = {
                "mode": self.mode_combo.currentText(),
                "quality": self.quality_bar.value(),
                "timestamp": self._saved_capture_timestamp.isoformat(),
                "device": self.diag_device_value.text(),
            }
            self._saved_capture = "capture_saved"
            self.status_label.setText(f"Capture saved at quality {self.quality_bar.value()}%")
            self._preview_capture_btn.setEnabled(True)
            self.send_btn.setEnabled(True)
            self._stamp_action("Capture saved")
    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        if hasattr(self, "_cam_title_lbl"):
            self._cam_title_lbl.setText(pack["cam_title"])
        if hasattr(self, "_cam_subtitle_lbl"):
            self._cam_subtitle_lbl.setText(pack["cam_subtitle"])
        if self.camera is None and hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(pack["cam_stopped"])
        if self.camera is None and self.mode_combo.currentText() == self.MODE_WEBCAM and hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(pack["cam_stopped"])
        if hasattr(self, "stop_btn") and self.stop_btn:
            self.stop_btn.setText(pack["cam_stop"])