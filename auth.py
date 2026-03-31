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
from datetime import datetime
from typing import Optional
from referrals import ReferralService

DB_FILE = "users.db"
VALID_ROLES = {"clinician", "admin", "viewer"}
VALID_SPECIALIZATIONS = {"optometrist", "ophthalmologist"}
ADMIN_ROLE = "admin"
MIN_PASSWORD_LENGTH = 12
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

        # Referral assignments table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referral_id TEXT NOT NULL,
                episode_no INTEGER NOT NULL DEFAULT 1,
                assigned_to_username TEXT NOT NULL,
                assigned_by_username TEXT NOT NULL,
                assigned_at TEXT,
                status TEXT DEFAULT 'pending',
                patient_name TEXT,
                urgency TEXT DEFAULT 'normal',
                notes TEXT,
                FOREIGN KEY (assigned_to_username) REFERENCES users(username),
                FOREIGN KEY (assigned_by_username) REFERENCES users(username),
                UNIQUE(referral_id, episode_no)
            )
            """
        )

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
        json_path = os.path.join(os.path.dirname(__file__), "users_data.json")
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
            SELECT username, full_name, display_name, contact, specialization, availability_json, role, is_active
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
            "role": row[6],
            "is_active": bool(row[7]),
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
    def update_user_role(
        username: str,
        new_role: str,
        acting_username: Optional[str] = None,
        acting_role: Optional[str] = None,
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
    ) -> bool:
        """Delete a user"""
        username = username.strip()
        if not username or not UserManager._can_manage_users(acting_role):
            return False

        conn = get_connection()
        cur = conn.cursor()

        role = UserManager._get_user_role(conn, username)
        if role is None:
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
    ) -> bool:
        username = username.strip()
        if not username or not UserManager._can_manage_users(acting_role):
            return False

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

        UserManager.add_activity_log(username, "Availability Updated")
        return True, "Schedule updated successfully."

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

        UserManager.add_activity_log(target_username, "Profile updated")
        return True, "Account updated successfully.", target_username

    @staticmethod
    def add_activity_log(username: str, action: str, action_time: Optional[str] = None) -> bool:
        username = str(username or "").strip()
        action = str(action or "").strip()
        if not username or not action:
            return False

        timestamp = str(action_time or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO activity_logs (username, action, action_time) VALUES (?, ?, ?)",
                (username, action, timestamp),
            )
            conn.commit()
            success = True
        except sqlite3.Error:
            success = False
        conn.close()
        return success

    @staticmethod
    def get_recent_activity(limit: int = 120) -> list[tuple]:
        safe_limit = max(1, min(int(limit), 500))
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT username, action, action_time
            FROM activity_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def assign_referral(
        referral_id: str,
        assigned_to_username: str,
        assigned_by_username: str,
        patient_name: str = "",
        urgency: str = "normal",
        notes: str = "",
    ) -> bool:
        """Assign a referral to a specific clinician."""
        return ReferralService.assign_referral(
            get_connection=get_connection,
            add_activity_log=UserManager.add_activity_log,
            referral_id=referral_id,
            assigned_to_username=assigned_to_username,
            assigned_by_username=assigned_by_username,
            patient_name=patient_name,
            urgency=urgency,
            notes=notes,
        )

    @staticmethod
    def get_pending_referrals(username: str) -> list[dict]:
        """Get pending and actionable referrals for a clinician."""
        return ReferralService.get_pending_referrals(get_connection=get_connection, username=username)

    @staticmethod
    def get_user_referrals(username: str, limit: int = 100) -> list[dict]:
        """Get referral activity that is private to a user."""
        return ReferralService.get_user_referrals(get_connection=get_connection, username=username, limit=limit)

    @staticmethod
    def get_referral_count(username: str, status: str = "pending") -> int:
        """Get referral count for a clinician by status."""
        return ReferralService.get_referral_count(get_connection=get_connection, username=username, status=status)

    @staticmethod
    def update_referral_status(referral_id: str, new_status: str, actor_username: str = "") -> bool:
        """Update referral status with transition validation and audit trail."""
        return ReferralService.update_referral_status(
            get_connection=get_connection,
            add_activity_log=UserManager.add_activity_log,
            referral_id=referral_id,
            new_status=new_status,
            actor_username=actor_username,
        )

    @staticmethod
    def append_referral_note(referral_id: str, actor_username: str, note: str) -> bool:
        """Append a timestamped note to a referral record."""
        return ReferralService.append_referral_note(
            get_connection=get_connection,
            add_activity_log=UserManager.add_activity_log,
            referral_id=referral_id,
            actor_username=actor_username,
            note=note,
        )

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
    def reassign_referral(
        referral_id: str,
        new_assignee_username: str,
        acting_username: str,
        reason: str = "",
        reason_code: str = "",
    ) -> bool:
        """Reassign referral to another clinician and preserve audit note."""
        return ReferralService.reassign_referral(
            get_connection=get_connection,
            add_activity_log=UserManager.add_activity_log,
            referral_id=referral_id,
            new_assignee_username=new_assignee_username,
            acting_username=acting_username,
            reason=reason,
            reason_code=reason_code,
        )

    @staticmethod
    def get_unread_referral_notifications(username: str, limit: int = 30) -> list[dict]:
        """Return unread referral notifications for a user."""
        return ReferralService.get_unread_notifications(get_connection=get_connection, username=username, limit=limit)

    @staticmethod
    def mark_referral_notification_read(notification_id: int, username: str) -> bool:
        """Mark a referral notification as read."""
        return ReferralService.mark_notification_read(
            get_connection=get_connection,
            notification_id=notification_id,
            username=username,
        )

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
    ) -> bool:
        """Activate or deactivate a user account."""
        target = str(username or "").strip()
        if not target:
            return False
        if not UserManager._can_manage_users(acting_role):
            return False

        conn = get_connection()
        cur = conn.cursor()
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

    @staticmethod
    def get_referral_reason_taxonomy() -> dict:
        return {
            "reassignment": dict(ReferralService.REASSIGNMENT_REASONS),
            "completion": dict(ReferralService.COMPLETION_REASONS),
        }

    @staticmethod
    def get_referral_notifications(username: str, include_read: bool = False, limit: int = 100) -> list[dict]:
        return ReferralService.get_notifications(
            get_connection=get_connection,
            username=username,
            include_read=include_read,
            limit=limit,
        )

    @staticmethod
    def mark_all_referral_notifications_read(username: str) -> int:
        return ReferralService.mark_all_notifications_read(
            get_connection=get_connection,
            username=username,
        )

    @staticmethod
    def get_referral_kpis(username: str) -> dict:
        return ReferralService.get_referral_kpis(get_connection=get_connection, username=username)

    @staticmethod
    def update_referral_status_with_reason(
        referral_id: str,
        new_status: str,
        actor_username: str = "",
        reason_code: str = "",
        reason_note: str = "",
    ) -> bool:
        return ReferralService.update_referral_status(
            get_connection=get_connection,
            add_activity_log=UserManager.add_activity_log,
            referral_id=referral_id,
            new_status=new_status,
            actor_username=actor_username,
            reason_code=reason_code,
            reason_note=reason_note,
        )


