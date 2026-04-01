"""
Temporary camera page for EyeShield EMR.
Uses system webcam until fundus camera integration is available.Includes patient handoff safety, device resilience, and capture workflow."""

from datetime import datetime
import json
import os
import secrets
import shutil

# On Windows, prefer the native multimedia backend for webcam reliability.
if os.name == "nt" and not os.environ.get("QT_MEDIA_BACKEND"):
    os.environ["QT_MEDIA_BACKEND"] = "windows"

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
    QSizePolicy,
    QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QIcon, QImage, QPainter, QColor, QBrush
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QImageCapture
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtSvg import QSvgRenderer
from typing import Optional
from safety_runtime import write_activity


class CameraPage(QWidget):
    """Camera integration sandbox with simulation, webcam, and mock device modes."""

    MODE_SIMULATION = "Sample Images"
    MODE_WEBCAM = "Webcam"
    MODE_MOCK = "Device Mock"

    def __init__(self):
        super().__init__()
        self.camera = None
        self.capture_session = None
        self.image_capture = None
        self._video_sink = None
        self._first_frame_seen = False
        self._preview_watchdog_timer = None
        self.video_widget = None
        self.preview_stack = None
        self.simulation_preview = None
        self.status_label = None
        self.mode_combo = None
        self.connect_btn = None
        self.start_btn = None
        self.stop_btn = None
        self.capture_btn = None
        self.validate_btn = None
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
        self._saved_capture_image_path = ""
        self._captured_preview_pixmap = QPixmap()
        self._capture_reviewed_by_clinician = False
        self._capture_quality_validated = False
        self._recapture_btn = None
        self._pending_webcam_capture = False
        self._capture_session_id = ""
        self._mode_change_guard = False
        
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

        # Screening handoff context
        self._capture_context = {
            "patient_id": "",
            "patient_name": "",
            "eye_label": "",
            "operator": "",
        }
        self._on_saved_callback = None
        self.ctx_patient_id_value = None
        self.ctx_patient_name_value = None
        self.ctx_eye_value = None
        self.ctx_operator_value = None
        
        self.init_ui()
        self._load_camera_settings()
        self._set_mode(self.MODE_SIMULATION)

    def init_ui(self):
        self.setObjectName("cameraPageRoot")
        self.setStyleSheet(
            """
            QWidget#cameraPageRoot { background: #f2f7fd; color: #1e2a36; }
            QLabel { background: transparent; }
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
                padding: 4px 10px;
                font-weight: 600;
                font-size: 14px;
                min-height: 28px;
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
        self.video_widget.setMinimumSize(420, 230)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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

        right_panel = QWidget()
        right_col = QVBoxLayout(right_panel)
        right_col.setSpacing(12)

        controls_group = QGroupBox("Capture Controls")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setContentsMargins(14, 14, 14, 14)
        controls_layout.setSpacing(10)

        mode_label = QLabel("Mode")
        mode_label.setObjectName("diagLabel")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_SIMULATION, self.MODE_WEBCAM, self.MODE_MOCK])
        self.mode_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mode_combo.currentTextChanged.connect(self._set_mode)
        controls_layout.addWidget(mode_label)
        controls_layout.addWidget(self.mode_combo)

        self.start_btn = QPushButton("Start Camera")
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                background: #18a558;
                color: white;
                border: 1px solid #138546;
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 14px;
                font-weight: 700;
                min-height: 28px;
            }
            QPushButton:hover { background: #15924d; }
            """
        )
        self.start_btn.clicked.connect(self._toggle_camera)
        self.start_btn.setIcon(self._button_icon("start_camera.svg", tint="#ffffff"))
        self.start_btn.setIconSize(QSize(18, 18))
        controls_layout.addWidget(self.start_btn)

        capture_validate_row = QHBoxLayout()
        capture_validate_row.setSpacing(8)

        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.clicked.connect(self._capture_frame)
        self.capture_btn.setIcon(self._button_icon("capture.svg", "camera.svg", tint="#1f6fe5"))
        self.capture_btn.setIconSize(QSize(18, 18))
        capture_validate_row.addWidget(self.capture_btn)

        self.validate_btn = QPushButton("Quality Check")
        self.validate_btn.clicked.connect(self._validate_capture_placeholder)
        self.validate_btn.setIcon(self._button_icon("validate.svg", "analyze.svg", tint="#1f6fe5"))
        self.validate_btn.setIconSize(QSize(18, 18))
        capture_validate_row.addWidget(self.validate_btn)

        controls_layout.addLayout(capture_validate_row)

        # Capture workflow buttons: Preview + ReCapture
        capture_workflow_row = QHBoxLayout()
        capture_workflow_row.setSpacing(6)

        preview_btn = QPushButton("Preview Saved Image")
        preview_btn.setEnabled(False)
        preview_btn.clicked.connect(self._preview_saved_capture)
        preview_btn.setIcon(self._button_icon("preview.svg", tint="#1f6fe5"))
        preview_btn.setIconSize(QSize(18, 18))
        self._preview_capture_btn = preview_btn
        capture_workflow_row.addWidget(preview_btn)

        recapture_btn = QPushButton("Retake Image")
        recapture_btn.setEnabled(False)
        recapture_btn.clicked.connect(self._retry_capture)
        recapture_btn.setIcon(self._button_icon("retake_image.svg", tint="#1f6fe5"))
        recapture_btn.setIconSize(QSize(18, 18))
        self._recapture_btn = recapture_btn
        capture_workflow_row.addWidget(recapture_btn)

        self.send_btn = QPushButton("Send to Screening")
        self.send_btn.clicked.connect(self._send_to_screening)
        self.send_btn.setIcon(self._button_icon("send_to_screening.svg", tint="#1f6fe5"))
        self.send_btn.setIconSize(QSize(18, 18))

        # Keep control buttons readable even if app-level styles override sizing.
        for btn in (
            self.start_btn,
            self.capture_btn,
            self.validate_btn,
            preview_btn,
            recapture_btn,
            self.send_btn,
        ):
            btn.setMinimumHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._format_button_with_right_icon(btn)

        quality_label = QLabel("Capture Quality")
        quality_label.setObjectName("diagLabel")
        self.quality_bar = QProgressBar()
        self.quality_bar.setRange(0, 100)
        self.quality_bar.setValue(0)
        self.quality_bar.setFormat("%p%")
        self.quality_bar.setMinimumHeight(20)
        self.quality_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls_layout.addWidget(quality_label)
        controls_layout.addWidget(self.quality_bar)

        controls_layout.addStretch(1)

        bottom_actions_row = QHBoxLayout()
        bottom_actions_row.setSpacing(8)
        bottom_actions_row.addWidget(preview_btn)
        bottom_actions_row.addWidget(recapture_btn)
        bottom_actions_row.addWidget(self.send_btn)
        controls_layout.addLayout(bottom_actions_row)

        self._sync_start_button()

        right_col.addWidget(controls_group)

        patient_group = QGroupBox("Patient Context")
        patient_group.setFlat(True)
        patient_layout = QVBoxLayout(patient_group)
        patient_layout.setContentsMargins(14, 14, 14, 14)
        patient_layout.setSpacing(8)
        self.ctx_patient_id_value = self._diag_row(patient_layout, "Patient ID")
        self.ctx_patient_name_value = self._diag_row(patient_layout, "Patient")
        self.ctx_eye_value = self._diag_row(patient_layout, "Eye")
        self.ctx_operator_value = self._diag_row(patient_layout, "Operator")
        right_col.addWidget(patient_group)

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

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setWidget(right_panel)
        main_row.addWidget(right_scroll, 2)

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

    def _audit_context(self) -> str:
        patient_id = str(self._capture_context.get("patient_id") or "").strip() or "-"
        eye = self._normalize_eye_label(self._capture_context.get("eye_label")) or "-"
        operator = str(self._capture_context.get("operator") or "").strip() or "-"
        mode = self.mode_combo.currentText() if self.mode_combo is not None else "-"
        return f"patient_id={patient_id}; eye={eye}; operator={operator}; mode={mode}"

    def _log_event(self, level: str, action: str, details: str):
        try:
            write_activity(level, action, details)
        except Exception:
            pass

    @staticmethod
    def _normalize_eye_label(value: str) -> str:
        text = str(value or "").strip().lower()
        if text in ("od", "right eye", "right"):
            return "OD"
        if text in ("os", "left eye", "left"):
            return "OS"
        return ""

    def _update_capture_context_display(self):
        if self.ctx_patient_id_value is not None:
            self.ctx_patient_id_value.setText(self._capture_context.get("patient_id") or "-")
        if self.ctx_patient_name_value is not None:
            self.ctx_patient_name_value.setText(self._capture_context.get("patient_name") or "-")
        if self.ctx_eye_value is not None:
            eye = self._normalize_eye_label(self._capture_context.get("eye_label"))
            self.ctx_eye_value.setText(eye or "-")
        if self.ctx_operator_value is not None:
            self.ctx_operator_value.setText(self._capture_context.get("operator") or "-")

    def _set_mode(self, mode_text: str):
        if self._mode_change_guard:
            return

        if self.has_active_screening_session() and mode_text != self.MODE_WEBCAM:
            self._mode_change_guard = True
            idx = self.mode_combo.findText(self.MODE_WEBCAM)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
            self._mode_change_guard = False
            QMessageBox.information(
                self,
                "Webcam Required",
                "Clinical capture from Screening requires Webcam mode.",
            )
            mode_text = self.MODE_WEBCAM

        self._capture_ready = False
        self.quality_bar.setValue(0)
        self.diag_mode_value.setText(mode_text)

        if mode_text == self.MODE_WEBCAM:
            if self.camera is None:
                self._show_webcam_placeholder()
            else:
                self.preview_stack.setCurrentWidget(self.video_widget)
            self.start_btn.setEnabled(True)
            self._sync_start_button()
            self.capture_btn.setEnabled(True)
            self.send_btn.setEnabled(False)
            self.status_label.setText("Webcam mode selected. Use Start/Stop Camera to control preview.")
            self.diag_connection_value.setText("Waiting for device detection")
        elif mode_text == self.MODE_MOCK:
            self.stop_camera()
            self.preview_stack.setCurrentWidget(self.simulation_preview)
            self.simulation_preview.setText("Device Mock Preview")
            self.start_btn.setEnabled(True)
            self._sync_start_button()
            self.capture_btn.setEnabled(True)
            self.send_btn.setEnabled(False)
            self.status_label.setText("Device Mock mode ready.")
            self.diag_device_value.setText("Mock Fundus Device v1")
            self.diag_connection_value.setText("Idle")
        else:
            self.stop_camera()
            self.preview_stack.setCurrentWidget(self.simulation_preview)
            self.start_btn.setEnabled(True)
            self._sync_start_button()
            self.capture_btn.setEnabled(True)
            self.send_btn.setEnabled(False)
            self.status_label.setText("Sample Images mode ready. Click Capture Image to choose a sample.")
            self.diag_device_value.setText("Sample Library")
            self.diag_connection_value.setText("Ready")

        self._save_camera_settings()
        self._stamp_action(f"Mode changed to {mode_text}")
        self._update_send_button_state()

    def _show_webcam_placeholder(self):
        self.simulation_preview.setPixmap(QPixmap())
        self.simulation_preview.setText(
            "Webcam preview is idle.\n\n"
            "Click Start Camera to begin live preview."
        )
        self.preview_stack.setCurrentWidget(self.simulation_preview)

    def _button_icon(self, *candidates: str, tint: Optional[str] = None) -> QIcon:
        """
        Load an icon from the icons/ directory next to this file.

        SVG tinting strategy:
          1. Render the SVG onto a transparent ARGB image using QSvgRenderer.
          2. Paint a solid tint colour over a *second* image using
             CompositionMode_SourceIn so only pixels that already have alpha > 0
             are coloured â€” this preserves the icon shape exactly.
          3. Return a QIcon from the composited result.

        The old pixel-by-pixel loop set every pixel to the tint colour regardless
        of the SVG shape, producing a solid coloured square instead of an icon.
        """
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        tint_color = QColor(tint) if tint else None
        SIZE = 20  # render size in pixels

        for name in candidates:
            path = os.path.join(icon_dir, name)
            if not os.path.isfile(path):
                continue

            if path.lower().endswith(".svg"):
                try:
                    renderer = QSvgRenderer(path)
                    if not renderer.isValid():
                        continue

                    # Step 1 â€“ render SVG onto a transparent canvas.
                    base = QImage(SIZE, SIZE, QImage.Format_ARGB32_Premultiplied)
                    base.fill(Qt.transparent)
                    p = QPainter(base)
                    renderer.render(p)
                    p.end()

                    if tint_color is None:
                        return QIcon(QPixmap.fromImage(base))

                    # Step 2 â€“ paint the tint colour only where the SVG has pixels
                    # (CompositionMode_SourceIn keeps dst alpha, replaces dst colour).
                    tint_layer = QImage(SIZE, SIZE, QImage.Format_ARGB32_Premultiplied)
                    tint_layer.fill(Qt.transparent)
                    p2 = QPainter(tint_layer)
                    # Draw the rendered SVG first so we have an alpha mask.
                    p2.drawImage(0, 0, base)
                    # Now flood the tint colour through that mask.
                    p2.setCompositionMode(QPainter.CompositionMode_SourceIn)
                    p2.fillRect(tint_layer.rect(), tint_color)
                    p2.end()

                    return QIcon(QPixmap.fromImage(tint_layer))

                except Exception:
                    pass

            # Non-SVG fallback (PNG/BMP etc.)
            icon = QIcon(path)
            if not icon.isNull():
                return icon

        return QIcon()

    def _format_button_with_right_icon(self, button: QPushButton):
        if button is None:
            return
        # Icon appears on left by default (LTR layout)

    def _sync_start_button(self):
        if self.start_btn is None:
            return
        is_streaming = self.camera is not None
        if is_streaming:
            self.start_btn.setText("Stop Camera")
            self.start_btn.setIcon(self._button_icon("stop_camera.svg", tint="#ffffff"))
            self.start_btn.setStyleSheet(
                """
                QPushButton {
                    background: #dc3545;
                    color: white;
                    border: 1px solid #bb2d3b;
                    border-radius: 10px;
                    padding: 4px 10px;
                    font-size: 14px;
                    font-weight: 700;
                    min-height: 28px;
                }
                QPushButton:hover { background: #c82333; }
                """
            )
        else:
            self.start_btn.setText("Start Camera")
            self.start_btn.setIcon(self._button_icon("start_camera.svg", tint="#ffffff"))
            self.start_btn.setStyleSheet(
                """
                QPushButton {
                    background: #18a558;
                    color: white;
                    border: 1px solid #138546;
                    border-radius: 10px;
                    padding: 4px 10px;
                    font-size: 14px;
                    font-weight: 700;
                    min-height: 28px;
                }
                QPushButton:hover { background: #15924d; }
                """
            )
        self.start_btn.setIconSize(QSize(18, 18))
        self._format_button_with_right_icon(self.start_btn)

    def _toggle_camera(self):
        if self.mode_combo.currentText() != self.MODE_WEBCAM:
            webcam_idx = self.mode_combo.findText(self.MODE_WEBCAM)
            if webcam_idx >= 0:
                self.mode_combo.setCurrentIndex(webcam_idx)
            self.status_label.setText("Switched to Webcam mode. Starting camera...")
        if self.camera is None:
            self.start_camera()
        else:
            self.stop_camera()

    def _validate_capture_placeholder(self):
        if not self._saved_capture_metadata:
            QMessageBox.information(self, "Quality Check", "Capture and save an image first.")
            return

        quality = int(self.quality_bar.value())
        minimum_quality = 70
        if quality < minimum_quality:
            self._capture_quality_validated = False
            self._update_send_button_state()
            QMessageBox.warning(
                self,
                "Quality Check Failed",
                f"Image quality is {quality}%. Minimum required quality is {minimum_quality}%.",
            )
            self._stamp_action("Capture quality check failed")
            self._log_event("WARNING", "CAMERA_QUALITY_CHECK_FAILED", f"quality={quality}; min={minimum_quality}; {self._audit_context()}")
            return

        self._capture_quality_validated = True
        self._update_send_button_state()
        QMessageBox.information(self, "Quality Check", f"Image quality passed at {quality}%.")
        self._stamp_action("Capture quality check passed")
        self._log_event("INFO", "CAMERA_QUALITY_CHECK_PASSED", f"quality={quality}; {self._audit_context()}")

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
        captured_pixmap = QPixmap()

        if self.has_active_screening_session() and mode != self.MODE_WEBCAM:
            QMessageBox.warning(self, "Webcam Required", "Clinical capture requires Webcam mode.")
            return

        if mode == self.MODE_WEBCAM:
            if self.camera is None:
                QMessageBox.information(self, "Capture", "Start the webcam preview before capturing.")
                return
            if self.image_capture is None:
                QMessageBox.warning(self, "Capture", "Camera capture pipeline is not ready. Restart the camera and try again.")
                return
            self._pending_webcam_capture = True
            self.capture_btn.setEnabled(False)
            self.status_label.setText("Capturing live frame...")
            self._stamp_action("Webcam frame capture requested")
            self._log_event("INFO", "CAMERA_CAPTURE_REQUESTED", self._audit_context())
            self.image_capture.capture()
            return
        elif mode == self.MODE_SIMULATION:
            if not self._current_sample_path:
                self._load_sample_image()
                if not self._current_sample_path:
                    QMessageBox.information(self, "Capture", "Select a sample fundus image before capturing.")
                    return
            pixmap = QPixmap(self._current_sample_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Capture", "Loaded sample image is no longer available.")
                return
            captured_pixmap = pixmap
            quality = min(97, max(62, int((pixmap.width() + pixmap.height()) / 50)))
            self.status_label.setText("Sample frame captured and validated.")
        else:
            captured_pixmap = self.simulation_preview.grab()
            quality = 88
            self.status_label.setText("Mock frame captured from virtual device.")

        if captured_pixmap.isNull():
            QMessageBox.warning(self, "Capture", "Capture failed. Please retry.")
            return

        self._finalize_capture_and_save(captured_pixmap, quality)

    def _finalize_capture_and_save(self, captured_pixmap: QPixmap, quality: int):
        if captured_pixmap.isNull():
            QMessageBox.warning(self, "Capture", "Capture failed. Please retry.")
            return

        self._captured_preview_pixmap = captured_pixmap
        self._saved_capture = None
        self._saved_capture_metadata = None
        self._saved_capture_timestamp = None
        self._saved_capture_image_path = ""
        self._capture_reviewed_by_clinician = False
        self._capture_quality_validated = False
        self.quality_bar.setValue(max(0, min(100, int(quality))))
        self._capture_ready = True
        self._preview_capture_btn.setEnabled(False)
        if self._recapture_btn is not None:
            self._recapture_btn.setEnabled(True)
        self._update_send_button_state()
        self._save_capture()

    def _on_webcam_image_captured(self, _capture_id: int, preview_image):
        if not self._pending_webcam_capture:
            return
        self._pending_webcam_capture = False
        self.capture_btn.setEnabled(True)
        captured_pixmap = QPixmap.fromImage(preview_image)
        if captured_pixmap.isNull():
            QMessageBox.warning(self, "Capture", "Unable to capture a valid webcam frame. Try again.")
            return
        quality = 82
        self.status_label.setText("Live frame captured successfully.")
        self._stamp_action("Webcam frame captured")
        self._finalize_capture_and_save(captured_pixmap, quality)

    def _on_webcam_capture_error(self, _capture_id: int, _error, error_string: str):
        if not self._pending_webcam_capture:
            return
        self._pending_webcam_capture = False
        self.capture_btn.setEnabled(True)
        message = error_string.strip() or "Unknown webcam capture error"
        QMessageBox.warning(self, "Capture", f"Failed to capture webcam frame:\n\n{message}")
        self.status_label.setText("Webcam capture failed. Please retry.")
        self._stamp_action("Webcam capture failed")

    def _on_camera_runtime_error(self, _error, error_string: str):
        message = str(error_string or "").strip() or "Unknown camera runtime error"
        self.status_label.setText(f"Camera error: {message}")
        self.diag_connection_value.setText("Error")
        self._stamp_action("Webcam runtime error")
        self._log_event("ERROR", "CAMERA_RUNTIME_ERROR", f"message={message}; {self._audit_context()}")

    def _on_preview_frame_changed(self, frame):
        if frame is None:
            return
        if not frame.isValid():
            return
        self._first_frame_seen = True
        if self._preview_watchdog_timer is not None and self._preview_watchdog_timer.isActive():
            self._preview_watchdog_timer.stop()
        if self.diag_connection_value is not None:
            self.diag_connection_value.setText("Streaming")

    def _on_preview_watchdog_timeout(self):
        if self.camera is None:
            return
        if self._first_frame_seen:
            return
        self.diag_connection_value.setText("No frames")
        self.status_label.setText("Camera started but no live frames received.")
        self._stamp_action("No webcam frames received")
        self._log_event("WARNING", "CAMERA_NO_FRAMES", self._audit_context())
        QMessageBox.warning(
            self,
            "Camera Preview Unavailable",
            "The camera started, but no live frames were received.\n\n"
            "Check Windows camera privacy permissions and close other apps using the camera, then try Start Camera again.",
        )

    def _send_to_screening(self):
        if not self._saved_capture_metadata:
            QMessageBox.information(self, "Send to Screening", "Capture a frame first.")
            return

        if not self.has_active_screening_session():
            QMessageBox.warning(
                self,
                "No Active Screening Session",
                "No active Screening session was found. Return to Screening and start capture from there.",
            )
            self._stamp_action("Send blocked: no active screening session")
            self._log_event("WARNING", "CAMERA_SEND_BLOCKED_NO_SESSION", self._audit_context())
            self._update_send_button_state()
            return

        if not self._capture_reviewed_by_clinician:
            QMessageBox.information(
                self,
                "Review Required",
                "Preview and review the saved capture before sending it to Screening.",
            )
            return

        if not self._capture_quality_validated:
            QMessageBox.information(
                self,
                "Quality Check Required",
                "Run Quality Check and pass it before sending to Screening.",
            )
            return

        if self._on_saved_callback:
            try:
                if not self._saved_capture_image_path or not os.path.isfile(self._saved_capture_image_path):
                    self._saved_capture_image_path = self._create_capture_asset()
                packet = {
                    **self._saved_capture_metadata,
                    "captured_at": self._saved_capture_timestamp.isoformat() if self._saved_capture_timestamp else "",
                    "image_path": self._saved_capture_image_path,
                }
                self._on_saved_callback(packet)
                self.status_label.setText("Capture sent back to Screening.")
                self._stamp_action("Capture sent to screening handoff")
                self._log_event("INFO", "CAMERA_CAPTURE_SENT", f"path={self._saved_capture_image_path}; {self._audit_context()}")
                self._clear_screening_session()
            except Exception as exc:
                QMessageBox.warning(self, "Send to Screening", f"Failed to send capture to Screening:\n\n{exc}")
                self._stamp_action("Capture send failed")
                self._log_event("ERROR", "CAMERA_CAPTURE_SEND_FAILED", f"error={type(exc).__name__}:{exc}; {self._audit_context()}")
                return
        else:
            QMessageBox.warning(
                self,
                "No Active Screening Session",
                "Cannot complete handoff because Screening is not actively linked.",
            )
            self._stamp_action("Send blocked: callback missing")
            self._log_event("WARNING", "CAMERA_SEND_BLOCKED_CALLBACK_MISSING", self._audit_context())

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
        self.image_capture = QImageCapture(self.camera)
        self.capture_session.setImageCapture(self.image_capture)
        self.image_capture.imageCaptured.connect(self._on_webcam_image_captured)
        self.image_capture.errorOccurred.connect(self._on_webcam_capture_error)
        if hasattr(self.camera, "errorOccurred"):
            self.camera.errorOccurred.connect(self._on_camera_runtime_error)

        self._video_sink = self.video_widget.videoSink() if self.video_widget is not None else None
        self._first_frame_seen = False
        if self._video_sink is not None:
            self._video_sink.videoFrameChanged.connect(self._on_preview_frame_changed)

        if self._preview_watchdog_timer is None:
            self._preview_watchdog_timer = QTimer(self)
            self._preview_watchdog_timer.setSingleShot(True)
            self._preview_watchdog_timer.timeout.connect(self._on_preview_watchdog_timeout)
        self._preview_watchdog_timer.start(3000)
        self.camera.start()

        self.preview_stack.setCurrentWidget(self.video_widget)
        self.status_label.setText(f"Streaming: {cameras[0].description()}")
        self.diag_device_value.setText(cameras[0].description())
        self.diag_connection_value.setText("Streaming")
        self.start_btn.setEnabled(True)
        self._sync_start_button()
        self.send_btn.setEnabled(False)
        self._capture_ready = False
        self._stamp_action("Webcam started")

    def stop_camera(self):
        if self.camera is None:
            if self.mode_combo.currentText() == self.MODE_WEBCAM:
                self._show_webcam_placeholder()
            return

        if self._preview_watchdog_timer is not None and self._preview_watchdog_timer.isActive():
            self._preview_watchdog_timer.stop()
        if self._video_sink is not None:
            try:
                self._video_sink.videoFrameChanged.disconnect(self._on_preview_frame_changed)
            except Exception:
                pass
            self._video_sink = None
        self._first_frame_seen = False

        self.camera.stop()
        self.camera.deleteLater()
        self.camera = None
        self.capture_session = None

        self.status_label.setText("Camera is stopped.")
        self.diag_connection_value.setText("Stopped")
        self.start_btn.setEnabled(True)
        self._sync_start_button()
        self.capture_btn.setEnabled(True)
        self._pending_webcam_capture = False
        self.image_capture = None
        if self.mode_combo.currentText() == self.MODE_WEBCAM:
            self._show_webcam_placeholder()
        self._stamp_action("Webcam stopped")

    def enter_page(self):
        if self.mode_combo.currentText() == self.MODE_WEBCAM and self.camera is None:
            self._show_webcam_placeholder()
            self.status_label.setText("Webcam mode ready. Click Start Camera to begin live preview.")
            self._stamp_action("Camera page opened")

    def leave_page(self):
        self.stop_camera()

    def set_capture_context(
        self,
        patient_id: str,
        patient_name: str,
        eye_label: str,
        operator: str = "",
        on_saved_callback=None,
    ):
        self._capture_context = {
            "patient_id": str(patient_id or "").strip(),
            "patient_name": str(patient_name or "").strip(),
            "eye_label": str(eye_label or "").strip(),
            "operator": str(operator or "").strip(),
        }
        self._capture_session_id = secrets.token_hex(8)
        self._on_saved_callback = on_saved_callback
        self._capture_quality_validated = False
        self._update_capture_context_display()
        self._refresh_mode_lock()

        if self.has_active_screening_session():
            webcam_idx = self.mode_combo.findText(self.MODE_WEBCAM)
            if webcam_idx >= 0:
                self.mode_combo.setCurrentIndex(webcam_idx)
            self.status_label.setText("Clinical capture session started. Webcam mode is required.")
            self._stamp_action("Clinical capture session started")
            self._log_event("INFO", "CAMERA_SESSION_STARTED", f"session={self._capture_session_id}; {self._audit_context()}")

    def has_required_capture_context(self) -> bool:
        patient_id = str(self._capture_context.get("patient_id") or "").strip()
        eye_label = self._normalize_eye_label(self._capture_context.get("eye_label"))
        return bool(patient_id and eye_label)

    def has_active_screening_session(self) -> bool:
        return bool(self._on_saved_callback and self._capture_session_id and self.has_required_capture_context())

    def _clear_screening_session(self):
        self._on_saved_callback = None
        self._capture_session_id = ""
        self._refresh_mode_lock()
        self._update_send_button_state()

    def _refresh_mode_lock(self):
        if self.mode_combo is None:
            return
        self.mode_combo.setEnabled(not self.has_active_screening_session())

    def _update_send_button_state(self):
        if self.send_btn is None:
            return
        can_send = (
            bool(self._saved_capture_metadata)
            and self._capture_reviewed_by_clinician
            and self._capture_quality_validated
            and self.has_active_screening_session()
        )
        self.send_btn.setEnabled(can_send)

    def _build_capture_file_path(self) -> str:
        patient_id = self._capture_context.get("patient_id") or "UNLINKED"
        eye_label = self._normalize_eye_label(self._capture_context.get("eye_label")) or "EYE"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stored_images", "pending", patient_id)
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, f"{stamp}_{eye_label.lower()}_camera_source.png")

    def _create_capture_asset(self) -> str:
        destination = self._build_capture_file_path()
        source = str(self._current_sample_path or "").strip()

        if hasattr(self, "_captured_preview_pixmap") and not self._captured_preview_pixmap.isNull():
            if self._captured_preview_pixmap.save(destination, "PNG"):
                return destination

        if source and os.path.isfile(source):
            shutil.copy2(source, destination)
            return destination

        pixmap = QPixmap(1280, 960)
        pixmap.fill(Qt.black)
        if not pixmap.save(destination, "PNG"):
            raise OSError("Failed to create simulated capture image")
        return destination

    def _save_capture(self):
        if not self._capture_ready:
            QMessageBox.information(self, "Save Capture", "Capture a frame before saving.")
            return

        if self._on_saved_callback:
            patient_id = str(self._capture_context.get("patient_id") or "").strip()
            eye_label = self._normalize_eye_label(self._capture_context.get("eye_label"))
            if not patient_id:
                QMessageBox.warning(self, "Patient Required", "Link this image to a patient before saving.")
                return
            if not eye_label:
                QMessageBox.warning(self, "Eye Label Required", "Set eye label (OD/OS) before saving.")
                return

        self._saved_capture_timestamp = datetime.now()
        self._saved_capture_metadata = {
            "mode": self.mode_combo.currentText(),
            "quality": self.quality_bar.value(),
            "timestamp": self._saved_capture_timestamp.isoformat(),
            "device": self.diag_device_value.text(),
            "patient_id": self._capture_context.get("patient_id") or "",
            "patient_name": self._capture_context.get("patient_name") or "",
            "eye_label": self._normalize_eye_label(self._capture_context.get("eye_label")),
            "operator": self._capture_context.get("operator") or "",
        }
        self._saved_capture = "capture_saved"
        self._capture_reviewed_by_clinician = False

        try:
            self._saved_capture_image_path = self._create_capture_asset()
        except Exception as exc:
            QMessageBox.warning(self, "Save Capture", f"Failed to save captured image:\n\n{exc}")
            self._stamp_action("Capture save failed")
            self._log_event("ERROR", "CAMERA_CAPTURE_SAVE_FAILED", f"error={type(exc).__name__}:{exc}; {self._audit_context()}")
            return

        self.status_label.setText(f"Capture saved at quality {self.quality_bar.value()}%")
        self._preview_capture_btn.setEnabled(True)
        if self._recapture_btn is not None:
            self._recapture_btn.setEnabled(True)
        self._update_send_button_state()
        self._stamp_action("Capture saved")
        self._log_event("INFO", "CAMERA_CAPTURE_SAVED", f"path={self._saved_capture_image_path}; quality={self.quality_bar.value()}; {self._audit_context()}")
        if self._on_saved_callback:
            self.status_label.setText("Capture saved. Run Quality Check and Preview, then Send to Screening.")
            self._stamp_action("Capture saved and awaiting clinician review")

    def _preview_saved_capture(self):
        if not self._saved_capture_metadata:
            QMessageBox.information(self, "Preview Capture", "No saved capture to preview.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Saved Capture Preview")
        dlg.setModal(True)
        dlg.setMinimumSize(720, 520)
        layout = QVBoxLayout(dlg)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(680, 420)
        image_label.setStyleSheet("background:#0c1620;border:1px solid #2a3a4d;border-radius:8px;")

        preview_pixmap = QPixmap(self._saved_capture_image_path)
        if preview_pixmap.isNull() and hasattr(self, "_captured_preview_pixmap"):
            preview_pixmap = self._captured_preview_pixmap
        if preview_pixmap.isNull():
            QMessageBox.warning(self, "Preview Capture", "Saved image could not be loaded.")
            return

        scaled = preview_pixmap.scaled(
            image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        image_label.setPixmap(scaled)
        layout.addWidget(image_label, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        dlg.exec()

        self._capture_reviewed_by_clinician = True
        self.status_label.setText("Capture reviewed. Click Send to Screening to confirm handoff.")

        self._stamp_action("Saved capture previewed")
        self._log_event("INFO", "CAMERA_CAPTURE_REVIEWED", self._audit_context())
        self._update_send_button_state()

    def _retry_capture(self):
        self._saved_capture = None
        self._saved_capture_metadata = None
        self._saved_capture_timestamp = None
        self._saved_capture_image_path = ""
        self._captured_preview_pixmap = QPixmap()
        self._capture_reviewed_by_clinician = False
        self._capture_quality_validated = False
        self._capture_ready = False
        self._update_send_button_state()
        self._preview_capture_btn.setEnabled(False)
        if self._recapture_btn is not None:
            self._recapture_btn.setEnabled(False)
        self.quality_bar.setValue(0)
        self.status_label.setText("Capture reset. Capture a new frame.")
        self._stamp_action("Capture reset for retry")
        self._log_event("INFO", "CAMERA_CAPTURE_RESET", self._audit_context())

    def set_inactivity_context(self, timeout_enabled: bool, timeout_minutes: int, remaining_seconds: int | None = None):
        self._inactivity_timeout_enabled = bool(timeout_enabled)
        self._inactivity_timeout_minutes = max(1, int(timeout_minutes or 1))
        if remaining_seconds is not None:
            self._inactivity_remaining_sec = max(0, int(remaining_seconds))
        else:
            self._inactivity_remaining_sec = self._inactivity_timeout_minutes * 60
        self._update_inactivity_display()

    def _update_inactivity_display(self):
        if not self._inactivity_label:
            return
        if not self._inactivity_timeout_enabled:
            self._inactivity_label.setText("Session timeout monitoring: disabled")
            self._inactivity_label.setStyleSheet("color: #6d8298; font-size: 13px; font-weight: 600;")
            return

        mins = self._inactivity_remaining_sec // 60
        secs = self._inactivity_remaining_sec % 60
        self._inactivity_label.setText(f"Auto-logout in {mins:02d}:{secs:02d}")
        if self._inactivity_remaining_sec <= max(60, int(self._inactivity_timeout_minutes * 60 * 0.2)):
            self._inactivity_label.setStyleSheet("color: #b42318; font-size: 13px; font-weight: 700;")
        else:
            self._inactivity_label.setStyleSheet("color: #6d8298; font-size: 13px; font-weight: 600;")

    def _load_camera_settings(self):
        if not os.path.exists(self._settings_cache_file):
            return
        try:
            with open(self._settings_cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            mode = str(data.get("last_mode", self.MODE_SIMULATION))
            if mode in (self.MODE_SIMULATION, self.MODE_WEBCAM, self.MODE_MOCK):
                idx = self.mode_combo.findText(mode)
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
        except Exception:
            # Non-critical cache read failure should not block camera page.
            pass

    def _save_camera_settings(self):
        try:
            data = {"last_mode": self.mode_combo.currentText()}
            with open(self._settings_cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)
        except Exception:
            # Non-critical cache write failure should not block camera page.
            pass

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)

    def apply_language(self, language: str):
        from translations import get_pack
        pack = get_pack(language)
        if hasattr(self, "_cam_title_lbl"):
            self._cam_title_lbl.setText(pack.get("cam_title", "Camera Integration Sandbox"))
        if hasattr(self, "_cam_subtitle_lbl"):
            self._cam_subtitle_lbl.setText(
                pack.get("cam_subtitle", "Camera preview and diagnostics while hardware integration is in progress.")
            )
        if self.camera is None and hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(pack.get("cam_stopped", "Camera is stopped."))
        if self.camera is None and self.mode_combo.currentText() == self.MODE_WEBCAM and hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(pack.get("cam_stopped", "Camera is stopped."))
        if hasattr(self, "start_btn") and self.start_btn:
            self._sync_start_button()
        if hasattr(self, "capture_btn") and self.capture_btn:
            self.capture_btn.setText(pack.get("cam_capture_save", "Capture Image"))
        if hasattr(self, "validate_btn") and self.validate_btn:
            self.validate_btn.setText(pack.get("cam_validate_capture", "Quality Check"))
        if hasattr(self, "_preview_capture_btn") and self._preview_capture_btn:
            self._preview_capture_btn.setText(pack.get("cam_preview_saved_image", "Preview Saved Image"))
        if hasattr(self, "_recapture_btn") and self._recapture_btn:
            self._recapture_btn.setText(pack.get("cam_retake_image", "Retake Image"))
        if hasattr(self, "send_btn") and self.send_btn:
            self.send_btn.setText(pack.get("cam_send", "Send to Screening"))
