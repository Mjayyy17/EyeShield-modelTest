"""
Screening module for EyeShield EMR application.
Handles patient screening functionality and image analysis with fixed UI styling.
"""


from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QFileDialog, QFormLayout, QGroupBox, QComboBox, QDateEdit, QMessageBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit, QCalendarWidget, QStackedWidget,
    QGridLayout
)
from PySide6.QtGui import QPixmap, QFont, QRegularExpressionValidator
from PySide6.QtCore import Qt, QDate, QRegularExpression


class ScreeningPage(QWidget):
    """Patient screening page for DR detection with two-step workflow"""

    def __init__(self):
        super().__init__()
        self.current_image = None
        self.patient_counter = 0
        self.min_dob_date = QDate(1900, 1, 1)
        self.max_dob_date = QDate.currentDate()
        self.last_result_class = "Pending"
        self.last_result_conf = "Pending"
        self.stacked_widget = QStackedWidget()
        self.init_ui()

    def init_ui(self):
        """Initialize the revised UI: patient info and image upload in one window, results in new window"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        # Unified page: Patient Info + Image Upload
        unified_page = self.create_unified_page()
        self.results_page = ResultsWindow(self)
        self.stacked_widget.addWidget(unified_page)
        self.stacked_widget.addWidget(self.results_page)
        main_layout.addWidget(self.stacked_widget)
        self._setup_validators()
    def create_unified_page(self):
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(14)
        grid.setContentsMargins(12, 12, 12, 12)
        # Patient Info
        patient_group = QGroupBox("Patient Information")
        patient_form = QFormLayout()
        patient_form.setContentsMargins(12, 14, 12, 12)
        patient_form.setHorizontalSpacing(14)
        patient_form.setVerticalSpacing(10)
        patient_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        patient_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.p_id = QLineEdit()
        self.p_id.setReadOnly(True)
        self.p_id.setMinimumHeight(34)
        self.generate_patient_id()
        patient_form.addRow("Patient ID:", self.p_id)
        self.p_name = QLineEdit()
        self.p_name.setPlaceholderText("Full name")
        self.p_name.setMinimumHeight(34)
        patient_form.addRow("Name:", self.p_name)
        self.p_dob = QLineEdit()
        self.p_dob.setPlaceholderText("dd/mm/yyyy")
        self.p_dob.setMaxLength(10)
        self.p_dob.setMinimumHeight(34)
        self._dob_default_style = """
            QLineEdit {
                color: #212529;
                background: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """
        self._dob_invalid_style = """
            QLineEdit {
                color: #212529;
                background: #fff5f5;
                border: 1px solid #dc3545;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """
        self.p_dob.setStyleSheet(self._dob_default_style)
        self.p_dob.textChanged.connect(self._on_dob_text_changed)
        patient_form.addRow("Date of Birth:", self.p_dob)
        self.p_age = QSpinBox()
        self.p_age.setRange(0, 120)
        self.p_age.setSuffix(" years")
        self.p_age.setReadOnly(True)
        self.p_age.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.p_age.setSpecialValueText(" ")
        self.p_age.setValue(0)
        self.p_age.setMinimumHeight(34)
        patient_form.addRow("Age:", self.p_age)
        self.p_sex = QComboBox()
        self.p_sex.addItems(["", "Male", "Female", "Prefer not to say"])
        self.p_sex.setMinimumHeight(34)
        patient_form.addRow("Sex:", self.p_sex)
        self.p_contact = QLineEdit()
        self.p_contact.setPlaceholderText("Phone or Email")
        self.p_contact.setMinimumHeight(34)
        patient_form.addRow("Contact:", self.p_contact)
        patient_group.setLayout(patient_form)
        # Clinical History
        clinical_group = QGroupBox("Clinical History")
        clinical_form = QFormLayout()
        self.diabetes_type = QComboBox()
        self.diabetes_type.addItems(["Select", "Type 1", "Type 2", "Gestational", "Other"])
        clinical_form.addRow("Diabetes Type:", self.diabetes_type)
        self.diabetes_duration = QSpinBox()
        self.diabetes_duration.setSuffix(" years")
        self.diabetes_duration.setRange(0, 80)
        clinical_form.addRow("Duration:", self.diabetes_duration)
        self.hba1c = QDoubleSpinBox()
        self.hba1c.setRange(4.0, 15.0)
        self.hba1c.setDecimals(1)
        self.hba1c.setSuffix(" %")
        self.hba1c.setValue(7.0)
        clinical_form.addRow("HbA1c:", self.hba1c)
        self.prev_treatment = QCheckBox("Previous DR Treatment")
        clinical_form.addRow("", self.prev_treatment)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        clinical_form.addRow("Notes:", self.notes)
        clinical_group.setLayout(clinical_form)
        # Image Upload
        image_group = QGroupBox("Fundus Image Upload")
        image_layout = QVBoxLayout()
        self.image_label = QLabel("No image loaded")
        self.image_label.setMinimumSize(450, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed #ccc; background-color: #f9f9f9;")
        image_layout.addWidget(self.image_label)
        btn_layout = QHBoxLayout()
        self.btn_upload = QPushButton("Upload Image")
        self.btn_upload.clicked.connect(self.upload_image)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_image)
        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_clear)
        image_layout.addLayout(btn_layout)
        image_group.setLayout(image_layout)
        # Position widgets in grid
        grid.addWidget(patient_group, 0, 0)
        grid.addWidget(clinical_group, 1, 0)
        grid.addWidget(image_group, 0, 1, 2, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        # Analyze Button at bottom right
        analyze_layout = QHBoxLayout()
        analyze_layout.addStretch()
        self.btn_analyze = QPushButton("Analyze Image")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self.open_results_window)
        analyze_layout.addWidget(self.btn_analyze)
        grid.addLayout(analyze_layout, 2, 1, 1, 1)
        return container

    def _setup_validators(self):
        self.name_regex = QRegularExpression(r"^[A-Za-z][A-Za-z\s\-']*$")
        self.p_name.setValidator(QRegularExpressionValidator(self.name_regex, self))

    def _validate_patient_basics(self):
        name = self.p_name.text().strip()
        dob_date = self._get_dob_date()
        sex = self.p_sex.currentText().strip()
        contact = self.p_contact.text().strip()

        missing_fields = []
        if not name:
            missing_fields.append("Name")
        if not dob_date.isValid():
            missing_fields.append("Date of Birth")
        if not sex:
            missing_fields.append("Sex")
        if not contact:
            missing_fields.append("Contact")

        if missing_fields:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill up every patient information field.\n\nMissing: " + ", ".join(missing_fields),
            )
            return False

        if not self.name_regex.match(name).hasMatch():
            QMessageBox.warning(self, "Error", "Name can only include letters, spaces, hyphens, and apostrophes")
            return False
        return True

    def _on_dob_text_changed(self, text):
        digits = "".join(ch for ch in text if ch.isdigit())[:8]
        if len(digits) <= 2:
            formatted = digits
        elif len(digits) <= 4:
            formatted = f"{digits[:2]}/{digits[2:]}"
        else:
            formatted = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"

        if formatted != text:
            self.p_dob.blockSignals(True)
            self.p_dob.setText(formatted)
            self.p_dob.blockSignals(False)
            self.p_dob.setCursorPosition(len(formatted))

        self._update_dob_input_style(digits)

        self.update_age_from_dob(self._get_dob_date())

    def _update_dob_input_style(self, digits):
        has_invalid_value = False

        if len(digits) >= 1 and int(digits[0]) > 3:
            has_invalid_value = True

        if len(digits) >= 2:
            day = int(digits[:2])
            if day < 1 or day > 31:
                has_invalid_value = True

        if len(digits) >= 3 and int(digits[2]) > 1:
            has_invalid_value = True

        if len(digits) >= 4:
            month = int(digits[2:4])
            if month < 1 or month > 12:
                has_invalid_value = True

        if len(digits) == 8 and not self._get_dob_date().isValid():
            has_invalid_value = True

        self.p_dob.setStyleSheet(self._dob_invalid_style if has_invalid_value else self._dob_default_style)

    def _get_dob_date(self):
        if isinstance(self.p_dob, QDateEdit):
            date = self.p_dob.date()
            if date == self.min_dob_date:
                return QDate()
        else:
            date = QDate.fromString(self.p_dob.text().strip(), "dd/MM/yyyy")

        if not date.isValid():
            return QDate()
        if date < self.min_dob_date or date > QDate.currentDate():
            return QDate()
        return date

    def create_patient_info_page(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        title = QLabel("Step 1: Patient Information")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)

        patient_group = QGroupBox("Patient Information")
        patient_form = QFormLayout()

        self.p_id = QLineEdit()
        self.p_id.setReadOnly(True)
        self.generate_patient_id()
        patient_form.addRow("Patient ID:", self.p_id)

        self.p_name = QLineEdit()
        self.p_name.setPlaceholderText("Full name")
        patient_form.addRow("Name:", self.p_name)

        self.p_dob = QDateEdit()
        self.p_dob.setCalendarPopup(True)
        self.p_dob.setDisplayFormat("yyyy-MM-dd")
        custom_calendar = QCalendarWidget()
        custom_calendar.setGridVisible(True)
        custom_calendar.setStyleSheet("""
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: white;
            }
            QCalendarWidget QToolButton {
                color: black;
                font-weight: bold;
                background-color: white;
            }
            QCalendarWidget QAbstractItemView {
                color: black;
                selection-background-color: #0078d7;
                selection-color: white;
            }
        """)
        self.p_dob.setCalendarWidget(custom_calendar)
        self.p_dob.setMinimumDate(QDate(1900, 1, 1))
        self.p_dob.setSpecialValueText(" ")
        self.p_dob.setDate(self.p_dob.minimumDate())
        self.p_dob.dateChanged.connect(self.update_age_from_dob)
        patient_form.addRow("Date of Birth:", self.p_dob)

        self.p_age = QSpinBox()
        self.p_age.setRange(0, 120)
        self.p_age.setSuffix(" years")
        self.p_age.setReadOnly(True)
        self.p_age.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.p_age.setSpecialValueText(" ")
        self.p_age.setValue(0)
        patient_form.addRow("Age:", self.p_age)

        self.p_sex = QComboBox()
        self.p_sex.addItems(["", "Male", "Female", "Other"])
        patient_form.addRow("Sex:", self.p_sex)

        self.p_contact = QLineEdit()
        self.p_contact.setPlaceholderText("Phone or Email")
        patient_form.addRow("Contact:", self.p_contact)

        self.p_eye = QComboBox()
        self.p_eye.addItems(["", "Both Eyes", "Left Eye", "Right Eye"])
        patient_form.addRow("Eye(s):", self.p_eye)

        patient_group.setLayout(patient_form)
        layout.addWidget(patient_group)

        clinical_group = QGroupBox("Clinical History")
        clinical_form = QFormLayout()

        self.diabetes_type = QComboBox()
        self.diabetes_type.addItems(["Select", "Type 1", "Type 2", "Gestational", "Other"])
        clinical_form.addRow("Diabetes Type:", self.diabetes_type)

        self.diabetes_duration = QSpinBox()
        self.diabetes_duration.setSuffix(" years")
        self.diabetes_duration.setRange(0, 80)
        clinical_form.addRow("Duration:", self.diabetes_duration)

        self.hba1c = QDoubleSpinBox()
        self.hba1c.setRange(4.0, 15.0)
        self.hba1c.setDecimals(1)
        self.hba1c.setSuffix(" %")
        clinical_form.addRow("HbA1c:", self.hba1c)

        self.prev_treatment = QCheckBox("Previous DR Treatment")
        clinical_form.addRow("", self.prev_treatment)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        clinical_form.addRow("Notes:", self.notes)

        clinical_group.setLayout(clinical_form)
        layout.addWidget(clinical_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_screening)
        button_layout.addWidget(self.btn_cancel)
        self.btn_proceed = QPushButton("Proceed to Image")
        self.btn_proceed.clicked.connect(self.validate_and_proceed)
        button_layout.addWidget(self.btn_proceed)
        layout.addLayout(button_layout)
        layout.addStretch()
        return container

    def create_image_analysis_page(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        title = QLabel("Step 2: Image Analysis")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #555; font-size: 11pt;")
        layout.addWidget(self.summary_label)

        image_group = QGroupBox("Fundus Image")
        image_layout = QVBoxLayout()

        self.image_label = QLabel("No image loaded")
        self.image_label.setMinimumSize(450, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed #ccc; background-color: #f9f9f9;")
        image_layout.addWidget(self.image_label)

        btn_layout = QHBoxLayout()
        self.btn_upload = QPushButton("Upload Image")
        self.btn_upload.clicked.connect(self.upload_image)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_image)
        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_clear)
        image_layout.addLayout(btn_layout)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group, 1)

        results_group = QGroupBox("Results")
        results_layout = QFormLayout()
        self.r_class = QLabel("—")
        self.r_class.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        results_layout.addRow("Classification:", self.r_class)
        self.r_conf = QLabel("—")
        results_layout.addRow("Confidence:", self.r_conf)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_analyze = QPushButton("Analyze Image")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self.analyze_image)
        button_layout.addWidget(self.btn_analyze)
        self.btn_save = QPushButton("Save Screening")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_screening)
        button_layout.addWidget(self.btn_save)
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back_to_patient_info)
        button_layout.addWidget(self.btn_back)
        self.btn_new = QPushButton("New Patient")
        self.btn_new.clicked.connect(self.reset_screening)
        button_layout.addWidget(self.btn_new)
        layout.addLayout(button_layout)
        return container

    # ==================== LOGIC FUNCTIONS ====================

    def generate_patient_id(self):
        today = datetime.now().strftime("%Y%m%d")
        self.patient_counter += 1
        pid = f"ES-{today}-{self.patient_counter:04d}"
        self.p_id.setText(pid)

    def update_age_from_dob(self, date):
        if not date.isValid():
            self.p_age.setValue(0)
            return
        today = QDate.currentDate()
        age = today.year() - date.year()
        if (today.month(), today.day()) < (date.month(), date.day()):
            age -= 1
        self.p_age.setValue(max(0, age))

    def validate_and_proceed(self):
        if not self._validate_patient_basics():
            return
        dob_date = self._get_dob_date()
        dob_str = dob_date.toString("yyyy-MM-dd") if dob_date.isValid() else ""
        summary = f"<b>{self.p_name.text()}</b> | ID: {self.p_id.text()} | DOB: {dob_str} | Age: {self.p_age.value()}"
        self.summary_label.setText(summary)
        self.stacked_widget.setCurrentIndex(1)

    def cancel_screening(self):
        reply = QMessageBox.question(
            self, "Cancel", "Are you sure you want to cancel? All data will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_screening()

    def go_back_to_patient_info(self):
        reply = QMessageBox.question(
            self, "Go Back", "Going back will clear the image. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_image()
            self.stacked_widget.setCurrentIndex(0)

    def reset_screening(self):
        self.generate_patient_id()
        self.p_name.clear()
        self.p_contact.clear()
        if isinstance(self.p_dob, QDateEdit):
            self.p_dob.setDate(self.min_dob_date)
        else:
            self.p_dob.clear()
        self.p_age.setValue(0)
        self.p_sex.setCurrentIndex(0)
        self.diabetes_type.setCurrentIndex(0)
        self.diabetes_duration.setValue(0)
        self.hba1c.setValue(7.0)
        self.prev_treatment.setChecked(False)
        self.notes.clear()
        self.current_image = None
        self.image_label.clear()
        self.image_label.setText("No image loaded")
        self.image_label.setStyleSheet("border: 2px dashed #ccc; background-color: #f9f9f9;")
        self.last_result_class = "Pending"
        self.last_result_conf = "Pending"
        self.btn_analyze.setEnabled(False)
        self.stacked_widget.setCurrentIndex(0)

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Fundus Image", "", "Images (*.jpg *.png *.jpeg)"
        )
        if path:
            self.current_image = path
            pixmap = QPixmap(path).scaled(
                450,
                400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(pixmap)
            self.btn_analyze.setEnabled(True)
    def open_results_window(self):
        if not self._validate_patient_basics():
            return
        if not self.current_image:
            QMessageBox.warning(self, "Error", "No image loaded")
            return
        confirm_box = QMessageBox(self)
        confirm_box.setWindowTitle("Confirm Details")
        confirm_box.setText("Please confirm all details are correct before proceeding to results.")
        proceed_button = confirm_box.addButton("Proceed to Results", QMessageBox.ButtonRole.AcceptRole)
        confirm_box.addButton("Edit Information", QMessageBox.ButtonRole.RejectRole)
        confirm_box.exec()
        if confirm_box.clickedButton() != proceed_button:
            return
        # Show results inside the same window
        self.last_result_class = "No DR Detected"
        self.last_result_conf = "Confidence: 93.8%"
        self.results_page.set_results(self.p_name.text(), self.current_image)
        self.stacked_widget.setCurrentIndex(1)

    def clear_image(self):
        self.current_image = None
        self.image_label.clear()
        self.image_label.setText("No image loaded")
        self.image_label.setStyleSheet("border: 2px dashed #ccc; background-color: #f9f9f9;")
        self.btn_analyze.setEnabled(False)

    def save_screening(self):
        if not self._validate_patient_basics():
            return
        name = self.p_name.text().strip()

        pid = self.p_id.text()

        dob_date = self._get_dob_date()
        dob_str = dob_date.toString("yyyy-MM-dd") if dob_date.isValid() else ""

        age = self.p_age.value()
        sex = self.p_sex.currentText()
        contact = self.p_contact.text().strip()
        eye = ""
        diabetes_type = self.diabetes_type.currentText()
        duration = self.diabetes_duration.value()
        hba1c = f"{self.hba1c.value():.1f}%"
        prev_treatment = "Yes" if self.prev_treatment.isChecked() else "No"
        notes = self.notes.toPlainText().strip()
        result = self.last_result_class
        confidence = self.last_result_conf

        patient_data = [
            pid,
            name,
            dob_str,
            age if age > 0 else "",
            sex,
            contact,
            eye,
            diabetes_type if diabetes_type != "Select" else "",
            duration,
            hba1c,
            prev_treatment,
            notes,
            result,
            confidence,
        ]

        try:
            if hasattr(self, "patient_records_page") and self.patient_records_page:
                self.patient_records_page.add_patient_record(patient_data)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Saved but failed to update Patient Records: {e}")

        QMessageBox.information(self, "Saved", f"Screening record for {name} saved.")
        self.reset_screening()
class ResultsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)

        self.title_label = QLabel("Results")
        self.title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        heatmap_group = QGroupBox("Heatmap Output")
        heatmap_layout = QVBoxLayout(heatmap_group)
        self.heatmap_label = QLabel("Heatmap will appear here once the backend is connected.")
        self.heatmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heatmap_label.setStyleSheet("border: 2px dashed #0078d7; background-color: #e6f2ff; font-size: 11pt;")
        self.heatmap_label.setMinimumHeight(260)
        heatmap_layout.addWidget(self.heatmap_label)
        layout.addWidget(heatmap_group)

        explanation_group = QGroupBox("AI Explanation")
        explanation_layout = QVBoxLayout(explanation_group)
        self.explanation = QLabel("AI explanation will appear here once available.")
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet("font-size: 11pt; color: #333;")
        explanation_layout.addWidget(self.explanation)
        layout.addWidget(explanation_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_save = QPushButton("Save Patient")
        self.btn_save.clicked.connect(self.save_patient)
        button_layout.addWidget(self.btn_save)
        self.btn_new = QPushButton("New Patient")
        self.btn_new.clicked.connect(self.new_patient)
        button_layout.addWidget(self.btn_new)
        self.btn_back = QPushButton("Back to Screening")
        self.btn_back.clicked.connect(self.go_back)
        button_layout.addWidget(self.btn_back)
        layout.addLayout(button_layout)

        layout.addStretch()

    def set_results(self, patient_name, image_path):
        if patient_name:
            self.title_label.setText(f"Results for {patient_name}")
        else:
            self.title_label.setText("Results")
        if image_path:
            heatmap_pixmap = QPixmap(image_path).scaled(500, 350, Qt.AspectRatioMode.KeepAspectRatio)
            self.heatmap_label.setPixmap(heatmap_pixmap)
            self.heatmap_label.setText("")
        else:
            self.heatmap_label.setPixmap(QPixmap())
            self.heatmap_label.setText("Heatmap will appear here once the backend is connected.")
        self.explanation.setText("AI explanation will appear here once available.")

    def go_back(self):
        if self.parent_page and hasattr(self.parent_page, "stacked_widget"):
            self.parent_page.stacked_widget.setCurrentIndex(0)

    def save_patient(self):
        if self.parent_page and hasattr(self.parent_page, "save_screening"):
            self.parent_page.save_screening()

    def new_patient(self):
        if self.parent_page and hasattr(self.parent_page, "reset_screening"):
            self.parent_page.reset_screening()
