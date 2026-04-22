"""
Authentication module for EyeShield EMR application.
Handles user database, login verification, and user management.
"""

import contextlib
import sqlite3
import hashlib
import hmac
import os
import json
import re
import secrets
import shutil
from datetime import timezone
from datetime import datetime
from typing import Any, Optional
from referrals import ReferralService

DB_FILE = "users.db"
VALID_ROLES = {"clinician", "admin", "viewer"}
VALID_SPECIALIZATIONS = {"optometrist", "ophthalmologist"}
ADMIN_ROLE = "admin"
MIN_PASSWORD_LENGTH = 12
MAX_ACTIVITY_QUERY_LIMIT = 500
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


# ============================================================
# DATABASE CONNECTION
# ============================================================

class DatabaseConnection:
    """Manages database connections"""
    
    @staticmethod
    def get_connection() -> sqlite3.Connection:
        """Get a database connection"""
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def get_connection() -> sqlite3.Connection:
    """Get a database connection (legacy function)"""
    return DatabaseConnection.get_connection()


# ============================================================
# PASSWORD HASHING
# ============================================================

class PasswordManager:
    """Manages password hashing and verification"""

    _ALGO = "pbkdf2_sha256"
    _ITERATIONS = 260_000
    _SALT_BYTES = 16
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using PBKDF2-SHA256"""
        salt = secrets.token_bytes(PasswordManager._SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PasswordManager._ITERATIONS,
        )
        return (
            f"{PasswordManager._ALGO}${PasswordManager._ITERATIONS}$"
            f"{salt.hex()}${digest.hex()}"
        )

    @staticmethod
    def needs_upgrade(password_hash: str) -> bool:
        return not password_hash.startswith(f"{PasswordManager._ALGO}$")

    @staticmethod
    def _verify_pbkdf2(password: str, password_hash: str) -> bool:
        try:
            algo, iterations_str, salt_hex, digest_hex = password_hash.split("$")
            if algo != PasswordManager._ALGO:
                return False
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except (ValueError, TypeError):
            return False

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(candidate, expected)

    @staticmethod
    def _verify_legacy_sha256(password: str, password_hash: str) -> bool:
        if not password_hash.startswith("sha256:"):
            return False
        stored_hash = password_hash.split(":", 1)[1]
        password_hash_candidate = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(password_hash_candidate, stored_hash)
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        if password_hash.startswith(f"{PasswordManager._ALGO}$"):
            return PasswordManager._verify_pbkdf2(password, password_hash)
        if password_hash.startswith("sha256:"):
            return PasswordManager._verify_legacy_sha256(password, password_hash)
        return hmac.compare_digest(password, password_hash)


def hash_password(password: str) -> str:
    """Hash a password (legacy function)"""
    return PasswordManager.hash_password(password)


# ============================================================
# USER DATABASE MANAGEMENT
# ============================================================

class UserManager:
    """Manages user database operations"""

    _USER_COLUMNS = {
        "full_name": "TEXT",
        "display_name": "TEXT",
        "contact": "TEXT",
        "specialization": "TEXT",
        "availability_json": "TEXT",
        "preferred_timeout_minutes": "INTEGER",
        "is_active": "INTEGER DEFAULT 1",
    }

    _PATIENT_RECORD_COLUMNS = {
        "archived_at": "TEXT",
        "archived_by": "TEXT",
        "archive_reason": "TEXT",
        "original_screener_username": "TEXT",
        "original_screener_name": "TEXT",
        "screened_at": "TEXT",
        "source_image_path": "TEXT",
        "heatmap_image_path": "TEXT",
        "image_sha256": "TEXT",
        "image_saved_at": "TEXT",
        "visual_acuity_left": "TEXT",
        "visual_acuity_right": "TEXT",
        "blood_pressure_systolic": "TEXT",
        "blood_pressure_diastolic": "TEXT",
        "fasting_blood_sugar": "TEXT",
        "random_blood_sugar": "TEXT",
        "diabetes_diagnosis_date": "TEXT",
        "symptom_blurred_vision": "TEXT",
        "symptom_floaters": "TEXT",
        "symptom_flashes": "TEXT",
        "symptom_vision_loss": "TEXT",
        "height": "TEXT",
        "weight": "TEXT",
        "bmi": "TEXT",
        "treatment_regimen": "TEXT",
        "prev_dr_stage": "TEXT",
        "ai_classification": "TEXT",
        "doctor_classification": "TEXT",
        "decision_mode": "TEXT",
        "override_justification": "TEXT",
        "final_diagnosis_icdr": "TEXT",
        "doctor_findings": "TEXT",
        "decision_by_username": "TEXT",
        "decision_at": "TEXT",
        "follow_up": "TEXT",
        "followup_date": "TEXT",
        "followup_label": "TEXT",
        "screening_type": "TEXT",
        "previous_screening_id": "INTEGER",
    }

    _REFERRAL_HOSPITAL_COLUMNS = {
        "department": "TEXT",
        "contact_person": "TEXT",
        "phone": "TEXT",
        "email": "TEXT",
        "address": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "is_default": "INTEGER DEFAULT 0",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }

    _ACTIVITY_LOG_COLUMNS = {
        "event_type": "TEXT",
        "metadata_json": "TEXT",
    }
    
    def __init__(self):
        self.conn = self._init_db()
    
    @staticmethod
    def _init_db() -> sqlite3.Connection:
        """Initialize the database"""
        first_run = not os.path.exists(DB_FILE)

        conn = get_connection()
        cur = conn.cursor()
        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        UserManager._ensure_user_columns(conn)

        # Patient records table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patient_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                name TEXT,
                birthdate TEXT,
                age TEXT,
                sex TEXT,
                contact TEXT,
                eyes TEXT,
                diabetes_type TEXT,
                duration TEXT,
                hba1c TEXT,
                prev_treatment TEXT,
                notes TEXT,
                result TEXT,
                confidence TEXT,
                archived_at TEXT,
                archived_by TEXT,
                archive_reason TEXT
            )
        """)

        # Activity log table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                action_time TEXT NOT NULL
            )
            """
        )

        UserManager._ensure_activity_log_columns(conn)

        UserManager._ensure_patient_record_columns(conn)
        UserManager._ensure_referral_hospitals_table(conn)
        ReferralService.ensure_schema(conn)

        conn.commit()

        if first_run:
            UserManager._migrate_users_json(conn)
        UserManager._ensure_admin_user(conn, first_run)

        return conn

    @staticmethod
    def _ensure_user_columns(conn: sqlite3.Connection) -> None:
        """Add profile columns for existing users table and backfill safe defaults."""
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        existing_columns = {row[1] for row in cur.fetchall()}

        for column_name, column_type in UserManager._USER_COLUMNS.items():
            if column_name in existing_columns:
                continue
            cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")

        cur.execute("UPDATE users SET full_name = username WHERE full_name IS NULL OR TRIM(full_name) = ''")
        cur.execute("UPDATE users SET display_name = full_name WHERE display_name IS NULL OR TRIM(display_name) = ''")
        cur.execute("UPDATE users SET contact = '' WHERE contact IS NULL")
        cur.execute("UPDATE users SET availability_json = '' WHERE availability_json IS NULL")
        cur.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        cur.execute(
            """
            UPDATE users
            SET specialization = 'Optometrist'
            WHERE role = 'clinician' AND (specialization IS NULL OR TRIM(specialization) = '')
            """
        )

    @staticmethod
    def _ensure_patient_record_columns(conn: sqlite3.Connection) -> None:
        """Add archive-related columns for existing patient_records tables."""
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(patient_records)")
        existing_columns = {row[1] for row in cur.fetchall()}

        for column_name, column_type in UserManager._PATIENT_RECORD_COLUMNS.items():
            if column_name in existing_columns:
                continue
            cur.execute(
                f"ALTER TABLE patient_records ADD COLUMN {column_name} {column_type}"
            )

    @staticmethod
    def _ensure_referral_hospitals_table(conn: sqlite3.Connection) -> None:
        """Create and normalize referral hospital master data."""
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT NOT NULL,
                department TEXT,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                is_active INTEGER DEFAULT 1,
                is_default INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        cur.execute("PRAGMA table_info(referral_hospitals)")
        existing_columns = {row[1] for row in cur.fetchall()}
        for column_name, column_type in UserManager._REFERRAL_HOSPITAL_COLUMNS.items():
            if column_name in existing_columns:
                continue
            cur.execute(
                f"ALTER TABLE referral_hospitals ADD COLUMN {column_name} {column_type}"
            )

    @staticmethod
    def _ensure_activity_log_columns(conn: sqlite3.Connection) -> None:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(activity_logs)")
        existing_columns = {row[1] for row in cur.fetchall()}
        for column_name, column_type in UserManager._ACTIVITY_LOG_COLUMNS.items():
            if column_name in existing_columns:
                continue
            cur.execute(f"ALTER TABLE activity_logs ADD COLUMN {column_name} {column_type}")

    @staticmethod
    def ensure_referral_hospitals_table() -> bool:
        conn = get_connection()
        try:
            UserManager._ensure_referral_hospitals_table(conn)
            conn.commit()
            success = True
        except sqlite3.Error:
            success = False
        conn.close()
        return success

    @staticmethod
    def list_referral_hospitals(active_only: bool = False) -> list[dict]:
        conn = get_connection()
        cur = conn.cursor()
        try:
            UserManager._ensure_referral_hospitals_table(conn)
            if active_only:
                cur.execute(
                    """
                    SELECT id, hospital_name, department, contact_person, phone, email, address, is_active, is_default, created_at, updated_at
                    FROM referral_hospitals
                    WHERE is_active = 1
                    ORDER BY is_default DESC, hospital_name COLLATE NOCASE ASC
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT id, hospital_name, department, contact_person, phone, email, address, is_active, is_default, created_at, updated_at
                    FROM referral_hospitals
                    ORDER BY is_default DESC, hospital_name COLLATE NOCASE ASC
                    """
                )
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
        conn.close()

        return [
            {
                "id": row[0],
                "hospital_name": row[1] or "",
                "department": row[2] or "",
                "contact_person": row[3] or "",
                "phone": row[4] or "",
                "email": row[5] or "",
                "address": row[6] or "",
                "is_active": bool(row[7]),
                "is_default": bool(row[8]),
                "created_at": row[9] or "",
                "updated_at": row[10] or "",
            }
            for row in rows
        ]

    @staticmethod
    def upsert_referral_hospital(
        hospital_name: str,
        department: str = "",
        contact_person: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        is_active: bool = True,
        is_default: bool = False,
        hospital_id: Optional[int] = None,
    ) -> tuple[bool, str, Optional[int]]:
        clean_name = str(hospital_name or "").strip()
        if not clean_name:
            return False, "Hospital name is required.", None

        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_connection()
        cur = conn.cursor()
        try:
            UserManager._ensure_referral_hospitals_table(conn)

            if hospital_id:
                cur.execute(
                    """
                    UPDATE referral_hospitals
                    SET hospital_name = ?, department = ?, contact_person = ?, phone = ?, email = ?, address = ?,
                        is_active = ?, is_default = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        clean_name,
                        str(department or "").strip(),
                        str(contact_person or "").strip(),
                        str(phone or "").strip(),
                        str(email or "").strip(),
                        str(address or "").strip(),
                        1 if is_active else 0,
                        1 if is_default else 0,
                        now_text,
                        int(hospital_id),
                    ),
                )
                if cur.rowcount <= 0:
                    conn.close()
                    return False, "Trusted hospital was not found.", None
                target_id = int(hospital_id)
            else:
                cur.execute(
                    """
                    INSERT INTO referral_hospitals (
                        hospital_name, department, contact_person, phone, email, address,
                        is_active, is_default, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_name,
                        str(department or "").strip(),
                        str(contact_person or "").strip(),
                        str(phone or "").strip(),
                        str(email or "").strip(),
                        str(address or "").strip(),
                        1 if is_active else 0,
                        1 if is_default else 0,
                        now_text,
                        now_text,
                    ),
                )
                target_id = int(cur.lastrowid)

            if is_default:
                cur.execute(
                    "UPDATE referral_hospitals SET is_default = 0 WHERE id <> ?",
                    (target_id,),
                )

            if is_active:
                cur.execute(
                    "UPDATE referral_hospitals SET is_active = 1 WHERE id = ?",
                    (target_id,),
                )

            conn.commit()
        except sqlite3.Error as err:
            conn.close()
            return False, f"Unable to save trusted hospital: {err}", None

        conn.close()
        return True, "Trusted hospital saved.", target_id

    @staticmethod
    def delete_referral_hospital(hospital_id: int) -> tuple[bool, str]:
        conn = get_connection()
        cur = conn.cursor()
        try:
            UserManager._ensure_referral_hospitals_table(conn)
            cur.execute("SELECT is_default FROM referral_hospitals WHERE id = ?", (int(hospital_id),))
            row = cur.fetchone()
            if not row:
                conn.close()
                return False, "Trusted hospital was not found."

            deleting_default = bool(row[0])
            cur.execute("DELETE FROM referral_hospitals WHERE id = ?", (int(hospital_id),))
            if cur.rowcount <= 0:
                conn.close()
                return False, "Trusted hospital was not found."

            if deleting_default:
                cur.execute(
                    """
                    UPDATE referral_hospitals
                    SET is_default = 1
                    WHERE id = (
                        SELECT id FROM referral_hospitals
                        WHERE is_active = 1
                        ORDER BY hospital_name COLLATE NOCASE ASC
                        LIMIT 1
                    )
                    """
                )

            conn.commit()
        except sqlite3.Error as err:
            conn.close()
            return False, f"Unable to delete trusted hospital: {err}"

        conn.close()
        return True, "Trusted hospital deleted."

    @staticmethod
    def _migrate_users_json(conn: sqlite3.Connection) -> None:
        """Migrate legacy JSON users into SQLite (one-time safe import)."""
        json_path = os.path.join(os.path.dirname(__file__), "config", "users_data.json")
        if not os.path.exists(json_path):
            return

        try:
            with open(json_path, "r", encoding="utf-8") as file:
                users = json.load(file)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(users, list):
            return

        cur = conn.cursor()
        for user in users:
            if not isinstance(user, dict):
                continue
            username = str(user.get("username", "")).strip()
            full_name = str(user.get("full_name") or user.get("name") or username).strip()
            display_name = str(user.get("display_name") or full_name or username).strip()
            contact = str(user.get("contact") or "").strip()
            raw_availability = user.get("availability_json")
            if raw_availability is None:
                raw_availability = user.get("availability")
            if isinstance(raw_availability, (dict, list)):
                availability_json = json.dumps(raw_availability, ensure_ascii=True)
            else:
                availability_json = str(raw_availability or "").strip()
            raw_password = str(user.get("password", ""))
            role = str(user.get("role", "clinician") or "clinician")
            specialization = UserManager._normalize_specialization(
                user.get("specialization"),
                role,
            )
            if not username or not raw_password:
                continue

            cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                continue

            if raw_password.startswith("sha256:"):
                password_hash = raw_password
            else:
                password_hash = PasswordManager.hash_password(raw_password)

            cur.execute(
                """
                INSERT INTO users (
                    username,
                    full_name,
                    display_name,
                    contact,
                    specialization,
                    availability_json,
                    password_hash,
                    role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    full_name or username,
                    display_name or full_name or username,
                    contact,
                    specialization,
                    availability_json,
                    password_hash,
                    role,
                ),
            )
        conn.commit()

    @staticmethod
    def _ensure_admin_user(conn: sqlite3.Connection, first_run: bool) -> None:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        if total_users > 0:
            return

        username = os.environ.get("EYESHIELD_DEFAULT_ADMIN_USER", "admin")
        password = os.environ.get("EYESHIELD_DEFAULT_ADMIN_PASS")
        generated_password = False
        if not password:
            password = secrets.token_urlsafe(10)
            generated_password = True

        password_hash = PasswordManager.hash_password(password)
        cur.execute(
            """
            INSERT INTO users (
                username,
                full_name,
                display_name,
                contact,
                specialization,
                availability_json,
                password_hash,
                role
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, "Administrator", "Administrator", "", "", "", password_hash, "admin"),
        )
        conn.commit()

        if generated_password:
            print("[EyeShield] Initial admin account created.")
            print(f"[EyeShield] Username: {username}")
            print(f"[EyeShield] Temporary password: {password}")
            print("[EyeShield] Set EYESHIELD_DEFAULT_ADMIN_PASS to control first-run credentials.")

    @staticmethod
    def _normalize_role(role: str) -> Optional[str]:
        normalized_role = str(role or "clinician").strip().lower()
        return normalized_role if normalized_role in VALID_ROLES else None

    @staticmethod
    def _normalize_specialization(specialization: Optional[str], role: str) -> Optional[str]:
        normalized_role = str(role or "").strip().lower()
        raw = str(specialization or "").strip()

        if normalized_role != "clinician":
            return ""
        if not raw:
            return None

        lower_value = raw.lower()
        if lower_value not in VALID_SPECIALIZATIONS:
            return None
        return "Optometrist" if lower_value == "optometrist" else "Ophthalmologist"

    @staticmethod
    def _is_valid_username(username: str) -> bool:
        return bool(USERNAME_PATTERN.fullmatch(username))

    @staticmethod
    def _is_valid_password(password: str) -> bool:
        if len(password) < MIN_PASSWORD_LENGTH:
            return False

        checks = [
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        ]
        return all(checks)

    @staticmethod
    def _can_manage_users(acting_role: Optional[str]) -> bool:
        return acting_role == ADMIN_ROLE

    @staticmethod
    def _count_admins(conn: sqlite3.Connection) -> int:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role = ?", (ADMIN_ROLE,))
        row = cur.fetchone()
        return row[0] if row else 0

    @staticmethod
    def _get_user_role(conn: sqlite3.Connection, username: str) -> Optional[str]:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        return row[0] if row else None

    @staticmethod
    def resolve_username(username: str) -> str:
        """Return canonical username from DB (case-insensitive lookup) when available."""
        raw = str(username or "").strip()
        if not raw:
            return ""

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT username FROM users WHERE lower(username) = lower(?) LIMIT 1",
                (raw,),
            )
            row = cur.fetchone()
            resolved = str(row[0] or "").strip() if row else ""
            return resolved or raw
        except sqlite3.Error:
            return raw
        finally:
            conn.close()

    @staticmethod
    def _verify_admin_actor(
        conn: sqlite3.Connection,
        acting_username: Optional[str],
        acting_role: Optional[str],
        acting_password: Optional[str],
    ) -> bool:
        if acting_role != ADMIN_ROLE or not acting_username or not acting_password:
            return False

        cur = conn.cursor()
        cur.execute(
            "SELECT password_hash, role FROM users WHERE username = ?",
            (acting_username,),
        )
        row = cur.fetchone()
        if not row:
            return False

        password_hash, stored_role = row
        if stored_role != ADMIN_ROLE:
            return False
        return PasswordManager.verify_password(acting_password, password_hash)

    @staticmethod
    def _verify_admin_identity(
        conn: sqlite3.Connection,
        acting_username: Optional[str],
        acting_role: Optional[str],
    ) -> bool:
        if acting_role != ADMIN_ROLE or not acting_username:
            return False
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username = ?", (acting_username,))
        row = cur.fetchone()
        return bool(row and row[0] == ADMIN_ROLE)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _settings_data_path() -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "settings_data.json")

    @staticmethod
    def _clamp_timeout_minutes(value: Any, default: int = 15) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(default)
        return max(1, min(240, parsed))

    @staticmethod
    def _load_global_inactivity_policy() -> tuple[bool, int]:
        enabled = True
        timeout_minutes = 15
        path = UserManager._settings_data_path()
        if not os.path.exists(path):
            return enabled, timeout_minutes
        try:
            with open(path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                enabled = bool(loaded.get("auto_logout_enabled", True))
                timeout_minutes = UserManager._clamp_timeout_minutes(
                    loaded.get("inactivity_timeout_minutes", 15),
                    default=15,
                )
        except (OSError, json.JSONDecodeError):
            pass
        return enabled, timeout_minutes

    @staticmethod
    def _normalize_action_time(action_time: Optional[str]) -> str:
        text = str(action_time or "").strip()
        if not text:
            return UserManager._utc_now_iso()
        parsed: Optional[datetime] = None
        with contextlib.suppress(ValueError):
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed is None:
            with contextlib.suppress(ValueError):
                parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        if parsed is None:
            with contextlib.suppress(ValueError):
                parsed = datetime.strptime(text, "%Y-%m-%d")
        if parsed is None:
            return UserManager._utc_now_iso()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _normalize_event_type(value: Optional[str]) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return "LEGACY"
        return text

    @staticmethod
    def _normalize_metadata_json(metadata: Optional[dict[str, Any] | str]) -> str:
        if metadata is None:
            return ""
        if isinstance(metadata, str):
            metadata_text = metadata.strip()
            if not metadata_text:
                return ""
            try:
                parsed = json.loads(metadata_text)
                if isinstance(parsed, dict):
                    return json.dumps(parsed, ensure_ascii=True, separators=(",", ":"))
            except json.JSONDecodeError:
                return ""
            return ""
        if isinstance(metadata, dict):
            return json.dumps(metadata, ensure_ascii=True, separators=(",", ":"))
        return ""

    @staticmethod
    def _parse_legacy_action_details(text: str) -> dict[str, str]:
        payload = ""
        if " " in text:
            payload = text.split(" ", 1)[1]
        details: dict[str, str] = {}
        for token in str(payload or "").split(";"):
            piece = token.strip()
            if not piece or "=" not in piece:
                continue
            key, value = piece.split("=", 1)
            details[key.strip().lower()] = value.strip()
        return details

    @staticmethod
    def _infer_event_from_legacy_action(action: str) -> tuple[str, dict[str, Any], str]:
        text = str(action or "").strip()
        if not text:
            return "LEGACY", {}, ""

        lowered = text.lower()
        if lowered == "login":
            return "LOGIN", {}, text
        if lowered == "logout":
            return "LOGOUT", {}, text

        prefix = text.split(" ", 1)[0].strip().upper()
        if prefix in {
            "ACCOUNT_CREATED",
            "ACCOUNT_DELETED",
            "ROLE_CHANGED",
            "PASSWORD_RESET",
            "USER_STATUS_CHANGED",
            "USER_AVAILABILITY_UPDATED",
            "SCREENED_PATIENT",
            "RECORD_OPENED",
            "RECORD_ARCHIVED",
            "RECORD_RESTORED",
            "REPORT_EXPORT_CSV",
            "REPORT_GENERATED",
            "REFERRAL_GENERATED",
            "ACTIVITY_LOG_EXPORT_CSV",
        }:
            details = UserManager._parse_legacy_action_details(text)
            return prefix, details, text

        if lowered.startswith("assigned referral "):
            body = text[len("Assigned referral "):].strip()
            referral_id = body
            assignee = ""
            if " to " in body:
                referral_id, assignee = body.split(" to ", 1)
            metadata = {
                "referral_id": referral_id.strip(),
                "assigned_to": assignee.strip(),
            }
            return "REFERRAL_ASSIGNED", metadata, text

        if lowered.startswith("reassigned referral "):
            body = text[len("Reassigned referral "):].strip()
            referral_id = body
            assignee = ""
            if " to " in body:
                referral_id, assignee = body.split(" to ", 1)
            metadata = {
                "referral_id": referral_id.strip(),
                "assigned_to": assignee.strip(),
            }
            return "REFERRAL_REASSIGNED", metadata, text

        if lowered.startswith("updated referral note "):
            referral_id = text[len("Updated referral note "):].strip()
            return "REFERRAL_NOTE_UPDATED", {"referral_id": referral_id}, text

        if lowered.startswith("updated referral "):
            body = text[len("Updated referral "):].strip()
            referral_id = body
            from_status = ""
            to_status = ""
            if ":" in body:
                referral_id, transition = body.split(":", 1)
                if "->" in transition:
                    left, right = transition.split("->", 1)
                    from_status = left.strip()
                    to_status = right.strip()
            metadata = {
                "referral_id": referral_id.strip(),
                "from_status": from_status,
                "to_status": to_status,
            }
            return "REFERRAL_STATUS_UPDATED", metadata, text

        if lowered.startswith("generated external referral letter "):
            referral_id = text[len("Generated external referral letter "):].strip()
            return "EXTERNAL_REFERRAL_LETTER_GENERATED", {"referral_id": referral_id}, text

        return "LEGACY", {"raw_action": text}, text
    
    @staticmethod
    def create_user(
        username: str,
        password: str,
        role: str = "clinician",
        full_name: Optional[str] = None,
        display_name: Optional[str] = None,
        contact: Optional[str] = None,
        specialization: Optional[str] = None,
        availability_json: Optional[str] = None,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
        acting_password: Optional[str] = None,
    ) -> bool:
        """Create a new user"""
        username = username.strip()
        full_name_value = str(full_name or "").strip()
        display_name_value = str(display_name or full_name or "").strip()
        contact_value = str(contact or "").strip()
        availability_json_value = str(availability_json or "").strip()
        normalized_role = UserManager._normalize_role(role)
        normalized_specialization = UserManager._normalize_specialization(
            specialization,
            normalized_role or "",
        )

        if normalized_role == ADMIN_ROLE:
            availability_json_value = ""

        if not username or not password or not normalized_role:
            return False
        if username.lower() == password.lower():
            return False
        if not full_name_value or not display_name_value:
            return False
        if normalized_role == "clinician" and not normalized_specialization:
            return False
        if not UserManager._is_valid_username(username):
            return False
        if not UserManager._is_valid_password(password):
            return False
        if not UserManager._can_manage_users(acting_role):
            return False
        
        conn = get_connection()
        cur = conn.cursor()

        if not UserManager._verify_admin_actor(conn, acting_username, acting_role, acting_password):
            conn.close()
            return False
        
        pw_hash = PasswordManager.hash_password(password)
        
        try:
            cur.execute(
                """
                INSERT INTO users (
                    username,
                    full_name,
                    display_name,
                    contact,
                    specialization,
                    availability_json,
                    is_active,
                    password_hash,
                    role
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    full_name_value,
                    display_name_value,
                    contact_value,
                    normalized_specialization or "",
                    availability_json_value,
                    pw_hash,
                    normalized_role,
                )
            )
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        
        conn.close()
        return success
    
    @staticmethod
    def verify_user(username: str, password: str) -> Optional[str]:
        """Verify user credentials and return role"""
        if not username or not password:
            return None
        
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, password_hash, role, is_active FROM users WHERE username = ?", (username,))
        
        row = cur.fetchone()
        
        if not row:
            conn.close()
            return None
        
        user_id, pw_hash, role, is_active = row
        if int(is_active or 0) != 1:
            conn.close()
            return None
        
        if PasswordManager.verify_password(password, pw_hash):
            if PasswordManager.needs_upgrade(pw_hash):
                with contextlib.suppress(sqlite3.Error):
                    upgraded_hash = PasswordManager.hash_password(password)
                    cur.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (upgraded_hash, user_id),
                    )
                    conn.commit()
            conn.close()
            return role

        conn.close()
        return None

    @staticmethod
    def get_user_profile(username: str) -> Optional[dict]:
        """Return profile details for a username."""
        username = str(username or "").strip()
        if not username:
            return None

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT username, full_name, display_name, contact, specialization, availability_json, preferred_timeout_minutes, role, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "username": row[0],
            "full_name": row[1] or row[0],
            "display_name": row[2] or row[1] or row[0],
            "contact": row[3] or "",
            "specialization": row[4] or "",
            "availability_json": row[5] or "",
            "preferred_timeout_minutes": row[6],
            "role": row[7],
            "is_active": bool(row[8]),
        }

    @staticmethod
    def get_inactivity_policy(username: str) -> dict[str, Any]:
        username = str(username or "").strip()
        global_enabled, default_minutes = UserManager._load_global_inactivity_policy()
        user_minutes: Optional[int] = None

        if username:
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT preferred_timeout_minutes FROM users WHERE username = ?",
                    (username,),
                )
                row = cur.fetchone()
                if row:
                    raw_user_minutes = row[0]
                    if raw_user_minutes is not None:
                        user_minutes = UserManager._clamp_timeout_minutes(raw_user_minutes, default=default_minutes)
            except sqlite3.Error:
                user_minutes = None
            conn.close()

        effective_minutes = default_minutes
        if user_minutes is not None:
            effective_minutes = min(default_minutes, user_minutes)

        return {
            "enabled": bool(global_enabled),
            "default_minutes": int(default_minutes),
            "user_minutes": user_minutes,
            "effective_minutes": int(effective_minutes),
        }
    
    @staticmethod
    def get_all_users() -> list[tuple]:
        """Get all users"""
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT username, full_name, display_name, contact, specialization, availability_json, role, is_active FROM users"
        )
        users = cur.fetchall()
        
        conn.close()
        return users

    @staticmethod
    def create_fundus_only_backup(
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
    ) -> tuple[bool, str, Optional[str]]:
        """Create a local backup with users, patient records, and fundus images only."""
        if str(acting_role or "").strip().lower() != ADMIN_ROLE:
            return False, "Only admin accounts can create backups.", None

        app_root = os.path.dirname(os.path.abspath(__file__))
        db_dir = os.path.dirname(os.path.abspath(DB_FILE)) or app_root
        backup_root = os.path.join(db_dir, "backups")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(backup_root, f"eyeshield_backup_{timestamp}")
        fundus_dir = os.path.join(backup_dir, "fundus_images")

        try:
            os.makedirs(fundus_dir, exist_ok=False)
        except OSError as err:
            return False, f"Unable to prepare backup folder: {err}", None

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        try:
            cur.execute("SELECT * FROM users")
            users_payload = [dict(row) for row in cur.fetchall()]

            cur.execute("SELECT * FROM patient_records")
            records = [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as err:
            conn.close()
            shutil.rmtree(backup_dir, ignore_errors=True)
            return False, f"Unable to read database for backup: {err}", None

        conn.close()

        copied_fundus = 0
        missing_fundus = 0
        processed_records: list[dict[str, Any]] = []

        for record in records:
            item = dict(record)
            source_rel = str(item.get("source_image_path") or "").strip()
            item["heatmap_image_path"] = ""

            if not source_rel:
                processed_records.append(item)
                continue

            source_abs = source_rel if os.path.isabs(source_rel) else os.path.join(app_root, source_rel)
            source_abs = os.path.abspath(source_abs)
            if not os.path.isfile(source_abs):
                missing_fundus += 1
                processed_records.append(item)
                continue

            patient_id = str(item.get("patient_id") or item.get("id") or "record").strip()
            safe_patient = re.sub(r"[^A-Za-z0-9_.-]", "_", patient_id) or "record"
            filename = os.path.basename(source_abs)
            candidate = os.path.join(fundus_dir, f"{safe_patient}_{filename}")
            suffix = 1
            while os.path.exists(candidate):
                candidate = os.path.join(fundus_dir, f"{safe_patient}_{suffix}_{filename}")
                suffix += 1

            try:
                shutil.copy2(source_abs, candidate)
            except OSError:
                missing_fundus += 1
                processed_records.append(item)
                continue

            copied_fundus += 1
            item["source_image_path"] = os.path.join("fundus_images", os.path.basename(candidate)).replace("\\", "/")
            processed_records.append(item)

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(acting_username or "").strip(),
            "scope": "users + patient_records + fundus_only",
            "users_count": len(users_payload),
            "patient_records_count": len(processed_records),
            "fundus_copied": copied_fundus,
            "fundus_missing": missing_fundus,
            "heatmaps_included": False,
        }

        try:
            with open(os.path.join(backup_dir, "users.json"), "w", encoding="utf-8") as f:
                json.dump(users_payload, f, indent=2)
            with open(os.path.join(backup_dir, "patient_records.json"), "w", encoding="utf-8") as f:
                json.dump(processed_records, f, indent=2)
            with open(os.path.join(backup_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except OSError as err:
            shutil.rmtree(backup_dir, ignore_errors=True)
            return False, f"Unable to write backup files: {err}", None

        return True, "Backup created successfully.", backup_dir
    
    @staticmethod
    def update_user_role(
        username: str,
        new_role: str,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
        acting_password: Optional[str] = None,
    ) -> bool:
        """Update a user's role"""
        normalized_role = UserManager._normalize_role(new_role)
        username = username.strip()

        if not username or not normalized_role:
            return False
        if not UserManager._can_manage_users(acting_role):
            return False
        
        conn = get_connection()
        cur = conn.cursor()

        if not UserManager._verify_admin_actor(conn, acting_username, acting_role, acting_password):
            conn.close()
            return False

        current_role = UserManager._get_user_role(conn, username)
        if current_role is None:
            conn.close()
            return False

        if current_role == normalized_role:
            conn.close()
            return True

        if current_role == ADMIN_ROLE and normalized_role != ADMIN_ROLE and UserManager._count_admins(conn) <= 1:
            conn.close()
            return False
        
        try:
            cur.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                (normalized_role, username)
            )
            updated_role = cur.rowcount > 0
            if normalized_role == ADMIN_ROLE:
                cur.execute(
                    "UPDATE users SET availability_json = '' WHERE username = ?",
                    (username,),
                )
            if normalized_role == "clinician":
                cur.execute(
                    """
                    UPDATE users
                    SET specialization = 'Optometrist'
                    WHERE username = ? AND (specialization IS NULL OR TRIM(specialization) = '')
                    """,
                    (username,),
                )
            conn.commit()
            success = updated_role
        except sqlite3.Error:
            success = False
        
        conn.close()
        return success
    
    @staticmethod
    def delete_user(
        username: str,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
        acting_password: Optional[str] = None,
    ) -> bool:
        """Delete a user"""
        username = username.strip()
        if not username or not UserManager._can_manage_users(acting_role):
            return False

        conn = get_connection()
        cur = conn.cursor()

        if not UserManager._verify_admin_actor(conn, acting_username, acting_role, acting_password):
            conn.close()
            return False

        role = UserManager._get_user_role(conn, username)
        if role is None:
            conn.close()
            return False

        if role == ADMIN_ROLE and acting_username and username.strip().lower() != acting_username.strip().lower():
            conn.close()
            return False

        if role == ADMIN_ROLE and UserManager._count_admins(conn) <= 1:
            conn.close()
            return False
        
        try:
            cur.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        
        conn.close()
        return success

    @staticmethod
    def reset_password(
        username: str,
        new_password: str,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
        acting_password: Optional[str] = None,
    ) -> bool:
        """Reset a user's password"""
        username = username.strip()
        if not username or not new_password:
            return False
        if not UserManager._can_manage_users(acting_role):
            return False
        if not UserManager._is_valid_password(new_password):
            return False

        conn = get_connection()
        cur = conn.cursor()

        if not UserManager._verify_admin_actor(conn, acting_username, acting_role, acting_password):
            conn.close()
            return False

        pw_hash = PasswordManager.hash_password(new_password)

        try:
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (pw_hash, username),
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False

        conn.close()
        return success

    @staticmethod
    def update_user_availability(
        username: str,
        availability_json: str,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
        acting_password: Optional[str] = None,
    ) -> bool:
        username = username.strip()
        if not username or not UserManager._can_manage_users(acting_role):
            return False

        conn = get_connection()
        cur = conn.cursor()

        if not UserManager._verify_admin_actor(conn, acting_username, acting_role, acting_password):
            conn.close()
            return False

        target_role = UserManager._get_user_role(conn, username)
        if target_role is None:
            conn.close()
            return False

        try:
            availability_value = "" if target_role == ADMIN_ROLE else str(availability_json or "")
            cur.execute(
                "UPDATE users SET availability_json = ? WHERE username = ?",
                (availability_value, username),
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()
        return success

    @staticmethod
    def update_own_availability(current_username: str, availability_json: str) -> tuple[bool, str]:
        username = str(current_username or "").strip()
        if not username:
            return False, "User not found."

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE users SET availability_json = ? WHERE username = ?",
                (str(availability_json or ""), username),
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if not success:
            return False, "Could not update your schedule."

        UserManager.add_activity_event(
            username=username,
            event_type="USER_AVAILABILITY_UPDATED",
            metadata={"target": username, "scope": "self"},
            action_text="Availability Updated",
        )
        return True, "Schedule updated successfully."

    @staticmethod
    def update_own_inactivity_timeout(current_username: str, timeout_minutes: Any) -> tuple[bool, str, int]:
        username = str(current_username or "").strip()
        if not username:
            return False, "User not found.", 15

        global_enabled, default_minutes = UserManager._load_global_inactivity_policy()
        requested_minutes = UserManager._clamp_timeout_minutes(timeout_minutes, default=default_minutes)
        effective_minutes = min(default_minutes, requested_minutes)
        # Store NULL when it matches admin default so fallback remains explicit.
        stored_value: Optional[int] = effective_minutes if effective_minutes < default_minutes else None

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE users SET preferred_timeout_minutes = ? WHERE username = ?",
                (stored_value, username),
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if not success:
            return False, "Could not update your inactivity timeout.", default_minutes

        metadata = {
            "target": username,
            "scope": "self",
            "requested_minutes": requested_minutes,
            "effective_minutes": effective_minutes,
            "default_minutes": default_minutes,
            "auto_logout_enabled": bool(global_enabled),
        }
        UserManager.add_activity_event(
            username=username,
            event_type="INACTIVITY_TIMEOUT_PREFERENCE_UPDATED",
            metadata=metadata,
            action_text="Inactivity timeout preference updated",
        )

        if requested_minutes > default_minutes:
            return (
                True,
                f"Saved. Your timeout was capped to {default_minutes} minute(s) by admin policy.",
                effective_minutes,
            )
        return True, "Inactivity timeout preference updated.", effective_minutes

    @staticmethod
    def update_own_account(
        current_username: str,
        current_password: str,
        new_display_name: str,
        new_username: Optional[str] = None,
        new_password: Optional[str] = None,
    ) -> tuple[bool, str, Optional[str]]:
        """Allow a signed-in user to update own account details after password confirmation."""
        current_username = str(current_username or "").strip()
        current_password = str(current_password or "")
        target_username = str(new_username or current_username).strip()
        target_display_name = str(new_display_name or "").strip()
        target_new_password = str(new_password or "").strip()

        if not current_username or not current_password:
            return False, "Current credentials are required.", None
        if not target_display_name:
            return False, "Display name cannot be empty.", None
        if not UserManager._is_valid_username(target_username):
            return False, "Username must be 3-32 chars and use only letters, numbers, _ . -", None

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (current_username,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False, "Current user was not found.", None

        if not PasswordManager.verify_password(current_password, row[0]):
            conn.close()
            return False, "Current password is incorrect.", None

        if target_username != current_username:
            cur.execute("SELECT 1 FROM users WHERE username = ?", (target_username,))
            if cur.fetchone():
                conn.close()
                return False, "That username is already taken.", None

        pw_hash_to_save = row[0]
        if target_new_password:
            if target_new_password.lower() == target_username.lower():
                conn.close()
                return False, "Username and password cannot be the same.", None
            if not UserManager._is_valid_password(target_new_password):
                conn.close()
                return False, (
                    "Password must be 12+ chars with uppercase, lowercase, number, and symbol."
                ), None
            pw_hash_to_save = PasswordManager.hash_password(target_new_password)

        try:
            cur.execute(
                """
                UPDATE users
                SET username = ?, display_name = ?, password_hash = ?
                WHERE username = ?
                """,
                (target_username, target_display_name, pw_hash_to_save, current_username),
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.IntegrityError:
            conn.close()
            return False, "That username is already taken.", None
        except sqlite3.Error:
            conn.close()
            return False, "Unable to save account changes.", None

        conn.close()
        if not success:
            return False, "No account changes were applied.", None

        UserManager.add_activity_event(
            username=target_username,
            event_type="PROFILE_UPDATED",
            metadata={"target": target_username},
            action_text="Profile updated",
        )
        return True, "Account updated successfully.", target_username

    @staticmethod
    def add_activity_event(
        username: str,
        event_type: str,
        metadata: Optional[dict[str, Any] | str] = None,
        action_time: Optional[str] = None,
        action_text: Optional[str] = None,
    ) -> bool:
        actor = str(username or "").strip()
        normalized_event = UserManager._normalize_event_type(event_type)
        metadata_json = UserManager._normalize_metadata_json(metadata)
        text = str(action_text or "").strip() or normalized_event
        if not actor or not text:
            return False

        timestamp = UserManager._normalize_action_time(action_time)
        conn = get_connection()
        cur = conn.cursor()
        try:
            UserManager._ensure_activity_log_columns(conn)
            cur.execute(
                """
                INSERT INTO activity_logs (username, action, action_time, event_type, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (actor, text, timestamp, normalized_event, metadata_json),
            )
            conn.commit()
            success = True
        except sqlite3.Error:
            success = False
        conn.close()
        return success

    @staticmethod
    def add_activity_log(username: str, action: str, action_time: Optional[str] = None) -> bool:
        username = str(username or "").strip()
        action = str(action or "").strip()
        if not username or not action:
            return False
        event_type, metadata, normalized_text = UserManager._infer_event_from_legacy_action(action)
        return UserManager.add_activity_event(
            username=username,
            event_type=event_type,
            metadata=metadata,
            action_time=action_time,
            action_text=normalized_text,
        )

    @staticmethod
    def get_activity_logs(
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        username: Optional[str] = None,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        safe_limit = max(1, min(int(limit), MAX_ACTIVITY_QUERY_LIMIT))
        safe_offset = max(0, int(offset))
        where_parts: list[str] = []
        params: list[Any] = []

        from_text = str(from_time or "").strip()
        to_text = str(to_time or "").strip()
        query_text = str(query or "").strip().lower()
        username_text = str(username or "").strip()
        event_text = str(event_type or "").strip().upper()

        if from_text:
            if len(from_text) == 10:
                where_parts.append(
                    "COALESCE(date(action_time, 'localtime'), SUBSTR(action_time, 1, 10)) >= ?"
                )
            else:
                where_parts.append("action_time >= ?")
            params.append(from_text)
        if to_text:
            if len(to_text) == 10:
                where_parts.append(
                    "COALESCE(date(action_time, 'localtime'), SUBSTR(action_time, 1, 10)) <= ?"
                )
            else:
                where_parts.append("action_time <= ?")
            params.append(to_text)
        if username_text:
            where_parts.append("username = ?")
            params.append(username_text)
        if event_text:
            where_parts.append("event_type = ?")
            params.append(event_text)
        if query_text:
            where_parts.append(
                "(" 
                "LOWER(username) LIKE ? OR "
                "LOWER(action) LIKE ? OR "
                "LOWER(COALESCE(event_type, '')) LIKE ? OR "
                "LOWER(COALESCE(metadata_json, '')) LIKE ?"
                ")"
            )
            like_term = f"%{query_text}%"
            params.extend([like_term, like_term, like_term, like_term])

        where_sql = ""
        if where_parts:
            where_sql = "WHERE " + " AND ".join(where_parts)

        conn = get_connection()
        cur = conn.cursor()
        try:
            UserManager._ensure_activity_log_columns(conn)
            if not UserManager._verify_admin_identity(conn, acting_username, acting_role):
                conn.close()
                return [], 0
            cur.execute(
                f"SELECT COUNT(*) FROM activity_logs {where_sql}",
                tuple(params),
            )
            total = int((cur.fetchone() or [0])[0])

            cur.execute(
                f"""
                SELECT username, action, action_time, COALESCE(event_type, 'LEGACY'), COALESCE(metadata_json, '')
                FROM activity_logs
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params + [safe_limit, safe_offset]),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            conn.close()
            return [], 0
        conn.close()

        entries: list[dict[str, Any]] = []
        for row in rows:
            metadata_raw = str(row[4] or "").strip()
            metadata_value: dict[str, Any] = {}
            if metadata_raw:
                try:
                    parsed = json.loads(metadata_raw)
                    if isinstance(parsed, dict):
                        metadata_value = parsed
                except json.JSONDecodeError:
                    metadata_value = {}
            entries.append(
                {
                    "username": str(row[0] or "").strip(),
                    "action": str(row[1] or "").strip(),
                    "time": str(row[2] or "").strip(),
                    "event_type": str(row[3] or "LEGACY").strip().upper() or "LEGACY",
                    "metadata": metadata_value,
                }
            )
        return entries, total

    @staticmethod
    def get_recent_activity(limit: int = 120) -> list[tuple]:
        entries, _total = UserManager.get_activity_logs(limit=limit, offset=0)
        return [
            (entry.get("username", ""), entry.get("action", ""), entry.get("time", ""))
            for entry in entries
        ]

    @staticmethod
    def list_clinicians(exclude_username: str = "") -> list[dict]:
        """Return active clinician accounts for assignment/reassignment."""
        excluded = str(exclude_username or "").strip()
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT username, full_name, display_name, specialization
                FROM users
                WHERE role = 'clinician' AND is_active = 1
                ORDER BY COALESCE(display_name, full_name, username) COLLATE NOCASE ASC
                """
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
        conn.close()

        clinicians = []
        for row in rows:
            username = str(row[0] or "").strip()
            if not username or (excluded and username == excluded):
                continue
            display_name = str(row[2] or row[1] or username).strip()
            clinicians.append(
                {
                    "username": username,
                    "display_name": display_name,
                    "specialization": str(row[3] or "").strip(),
                }
            )
        return clinicians


    @staticmethod
    def log_external_referral_letter(
        referral_id: str,
        actor_username: str,
        patient_name: str,
        destination_name: str,
        destination_department: str,
        destination_contact: str,
        urgency: str,
        pdf_path: str,
    ) -> bool:
        """Persist audit event for generated external referral letter."""
        return ReferralService.log_external_referral_letter(
            get_connection=get_connection,
            add_activity_log=UserManager.add_activity_log,
            referral_id=referral_id,
            actor_username=actor_username,
            patient_name=patient_name,
            destination_name=destination_name,
            destination_department=destination_department,
            destination_contact=destination_contact,
            urgency=urgency,
            pdf_path=pdf_path,
        )

    @staticmethod
    def update_user_active_status(
        username: str,
        is_active: bool,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
        acting_password: Optional[str] = None,
    ) -> bool:
        """Activate or deactivate a user account."""
        target = str(username or "").strip()
        if not target:
            return False
        if not UserManager._can_manage_users(acting_role):
            return False

        conn = get_connection()
        cur = conn.cursor()

        if not UserManager._verify_admin_actor(conn, acting_username, acting_role, acting_password):
            conn.close()
            return False

        try:
            cur.execute("SELECT role FROM users WHERE username = ?", (target,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return False

            role = str(row[0] or "").strip().lower()
            desired = 1 if bool(is_active) else 0

            if role == ADMIN_ROLE and desired == 0:
                cur.execute("SELECT COUNT(*) FROM users WHERE role = ? AND is_active = 1", (ADMIN_ROLE,))
                active_admins = int((cur.fetchone() or [0])[0])
                if active_admins <= 1:
                    conn.close()
                    return False

            cur.execute("UPDATE users SET is_active = ? WHERE username = ?", (desired, target))
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()
        return success


