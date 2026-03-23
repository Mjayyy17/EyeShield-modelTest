from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from auth import DB_FILE
except ImportError:
    DB_FILE = "users.db"


class ScreeningFlowGuard:
    """Validate screening inputs and enforce one analysis per eye per session."""

    REQUIRED_FIELDS: list[tuple[str, str]] = [
        ("p_name", "Patient name"),
        ("p_dob", "Date of birth"),
        ("p_eye", "Eye screened"),
    ]
    _DOB_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

    def __init__(self, page: QWidget):
        self._page = page

    def validate(self) -> tuple[bool, str]:
        for attr, label in self.REQUIRED_FIELDS:
            widget = getattr(self._page, attr, None)
            if widget is None:
                continue

            value = (
                widget.currentText().strip()
                if hasattr(widget, "currentText")
                else widget.text().strip()
            )
            if not value:
                return False, f"Please fill in: {label}"

        dob_text = self._page.p_dob.text().strip()
        if dob_text and not self._DOB_RE.match(dob_text):
            return False, "Date of birth must be in dd/mm/yyyy format."

        eye = self._page.p_eye.currentText().strip()
        if not eye:
            return False, "Please select which eye is being screened."

        if not getattr(self._page, "current_image", None):
            return False, "Please upload a fundus image before analyzing."

        if self._eye_already_done(eye):
            return False, (
                f"'{eye}' has already been analyzed in this session.\n"
                "Screen the other eye or start a new patient."
            )

        return True, ""

    def mark_eye_done(self, eye: str) -> None:
        if not hasattr(self._page, "_analyzed_eyes"):
            self._page._analyzed_eyes = set()
        self._page._analyzed_eyes.add(eye.strip().lower())

    def reset(self) -> None:
        self._page._analyzed_eyes = set()

    def _eye_already_done(self, eye: str) -> bool:
        analyzed = getattr(self._page, "_analyzed_eyes", set())
        return eye.strip().lower() in analyzed


class DuplicateDetector:
    """Find likely duplicate patients using DOB/contact prefilter and fuzzy name match."""

    SIMILARITY_THRESHOLD = 0.82

    def find_duplicate(self, name: str, dob: str, contact: str = "") -> Optional[dict]:
        if not name or not dob:
            return None

        candidates = self._fetch_by_dob(dob)
        if not candidates and contact:
            candidates = self._fetch_by_contact(contact)
        if not candidates:
            return None

        best_score = 0.0
        best_match: Optional[dict] = None

        for row in candidates:
            score = self._name_similarity(name, row.get("name", ""))
            if contact and row.get("contact") and self._contacts_match(contact, row["contact"]):
                score = min(1.0, score + 0.1)

            if score > best_score:
                best_score = score
                best_match = row

        return best_match if best_score >= self.SIMILARITY_THRESHOLD else None

    @staticmethod
    def _fetch_by_dob(dob: str) -> list[dict]:
        query = """
            SELECT patient_id, name, birthdate, contact, result,
                   COALESCE(screened_at, '') AS screened_at
            FROM patient_records
            WHERE birthdate = ?
              AND (archived_at IS NULL OR archived_at = '')
            ORDER BY id DESC
        """
        return DuplicateDetector._fetch_rows(query, (dob,))

    @staticmethod
    def _fetch_by_contact(contact: str) -> list[dict]:
        query = """
            SELECT patient_id, name, birthdate, contact, result,
                   COALESCE(screened_at, '') AS screened_at
            FROM patient_records
            WHERE contact = ?
              AND (archived_at IS NULL OR archived_at = '')
            ORDER BY id DESC
        """
        return DuplicateDetector._fetch_rows(query, (contact,))

    @staticmethod
    def _fetch_rows(query: str, params: tuple) -> list[dict]:
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except sqlite3.Error as exc:
            print(f"[DuplicateDetector] Query error: {exc}")
            return []

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def _contacts_match(a: str, b: str) -> bool:
        def normalize(s: str) -> str:
            stripped = re.sub(r"[\s\-\+\(\)]", "", s)
            return stripped[-9:] if stripped.isdigit() and len(stripped) >= 9 else stripped.lower()

        return normalize(a) == normalize(b)


class DuplicateDialog(QDialog):
    """Prompt user to reuse existing patient ID or keep a new patient record."""

    USE_EXISTING = QDialog.DialogCode.Accepted
    SAVE_NEW = QDialog.DialogCode.Rejected

    _STYLE = """
    QDialog  { background:#ffffff; }
    QLabel   { color:#0f172a; font-size:13px; }
    QFrame#card {
        background:#f0f4f9; border:1px solid #dde6f0;
        border-radius:10px;
    }
    QPushButton {
        border-radius:6px; padding:8px 18px;
        font-weight:600; font-size:13px;
    }
    QPushButton#btnUse {
        background:#2563eb; color:#fff; border:none;
    }
    QPushButton#btnUse:hover  { background:#1d4ed8; }
    QPushButton#btnNew {
        background:#fef2f2; color:#ef4444;
        border:1.5px solid #fecaca;
    }
    QPushButton#btnNew:hover  { background:#fee2e2; }
    """

    def __init__(self, match: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Possible Duplicate Patient")
        self.setFixedWidth(440)
        self.setStyleSheet(self._STYLE)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Possible existing patient found")
        title.setStyleSheet("font-size:15px;font-weight:700;color:#0f172a;")
        layout.addWidget(title)

        sub = QLabel(
            "A similar patient profile already exists.\n"
            "Would you like to add this screening to the existing patient?"
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#475569;font-size:12px;")
        layout.addWidget(sub)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)

        def info_row(label: str, value: str):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#64748b;font-size:11px;min-width:110px;")
            val = QLabel(value or "-")
            val.setStyleSheet("color:#0f172a;font-size:12px;font-weight:500;")
            row.addWidget(lbl)
            row.addWidget(val, 1)
            card_layout.addLayout(row)

        info_row("Patient ID", match.get("patient_id", ""))
        info_row("Name", match.get("name", ""))
        info_row("Date of Birth", match.get("birthdate", ""))
        info_row("Contact", match.get("contact", ""))
        info_row("Last Result", match.get("result", ""))
        screened = match.get("screened_at", "")
        info_row("Last Screened", screened[:10] if screened else "")

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_use = QPushButton("Use Existing Patient")
        btn_use.setObjectName("btnUse")
        btn_use.clicked.connect(self.accept)

        btn_new = QPushButton("Save as New Patient")
        btn_new.setObjectName("btnNew")
        btn_new.clicked.connect(self.reject)

        btn_row.addWidget(btn_use, 1)
        btn_row.addWidget(btn_new, 1)
        layout.addLayout(btn_row)
