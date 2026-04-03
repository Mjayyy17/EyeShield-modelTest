"""Referral domain service for workflow state, audit events, and notifications."""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Callable


class ReferralService:
    """Encapsulates referral workflow rules and persistence helpers."""

    VALID_URGENCY = {"normal", "urgent", "critical"}
    ACTIVE_DUPLICATE_STATUSES = ("pending", "viewed", "in_review", "rereferred")
    STATUS_TRANSITIONS = {
        "pending": {"viewed", "in_review", "reassigned", "rereferred", "archived"},
        "viewed": {"in_review", "completed", "reassigned", "rereferred", "archived"},
        "in_review": {"completed", "reassigned", "rereferred", "archived"},
        "reassigned": {"viewed", "in_review", "completed", "archived"},
        "rereferred": {"viewed", "in_review", "completed", "archived"},
        "completed": {"archived"},
        "archived": set(),
    }
    NOTIFY_VISIBLE_STATUSES = ("pending", "viewed")
    REASSIGNMENT_REASONS = {
        "subspecialty_needed": "Subspecialty expertise needed",
        "workload_rebalance": "Workload rebalance",
        "schedule_unavailable": "Schedule unavailable",
        "urgent_escalation": "Urgent escalation",
        "other": "Other clinical reason",
    }
    COMPLETION_REASONS = {
        "treated_referred_out": "Treated / referred out",
        "follow_up_plan_set": "Follow-up plan set",
        "diagnosis_confirmed": "Diagnosis confirmed",
        "no_action_required": "No action required",
        "other": "Other completion reason",
    }

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _as_doctor_name(name: str) -> str:
        value = str(name or "").strip()
        if not value:
            return "Dr. Unknown"
        lowered = value.lower()
        if lowered in {"clinician", "admin", "viewer", "system", "__legacy_unknown__", "unknown"}:
            return "Unknown"
        if " " not in value and any(char.isdigit() for char in value):
            return value
        if lowered.startswith("dr. ") or lowered.startswith("dr "):
            return value
        return f"Dr. {value}"

    @staticmethod
    def _default_due_at(urgency: str, assigned_at: str) -> str:
        urgency_value = str(urgency or "normal").strip().lower()
        try:
            base = datetime.strptime(str(assigned_at or ""), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            base = datetime.now()
        if urgency_value == "critical":
            due = base + timedelta(hours=24)
        elif urgency_value == "urgent":
            due = base + timedelta(hours=72)
        else:
            due = base + timedelta(days=30)
        return due.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _is_clinician(conn: sqlite3.Connection, username: str) -> bool:
        user = str(username or "").strip()
        if not user:
            return False
        cur = conn.cursor()
        cur.execute("SELECT role, is_active FROM users WHERE username = ?", (user,))
        row = cur.fetchone()
        return bool(
            row
            and str(row[0] or "").strip().lower() == "clinician"
            and int(row[1] or 0) == 1
        )

    @staticmethod
    def _current_episode_no(conn: sqlite3.Connection, referral_id: str) -> int:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(episode_no), 0) FROM referral_assignments WHERE referral_id = ?", (referral_id,))
        row = cur.fetchone()
        return int(row[0] or 0)

    @staticmethod
    def _has_legacy_unique_referral_id(conn: sqlite3.Connection) -> bool:
        cur = conn.cursor()
        cur.execute("PRAGMA index_list(referral_assignments)")
        for index_row in cur.fetchall():
            index_name = str(index_row[1] or "")
            is_unique = int(index_row[2] or 0) == 1
            if not is_unique:
                continue
            cur.execute(f"PRAGMA index_info({index_name})")
            columns = [str(col[2] or "") for col in cur.fetchall()]
            if columns == ["referral_id"]:
                return True
        return False

    @staticmethod
    def _migrate_referral_assignments_schema(conn: sqlite3.Connection) -> None:
        ReferralService._ensure_migration_users_exist(conn)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_assignments_new (
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
                created_at TEXT,
                updated_at TEXT,
                last_status_at TEXT,
                due_at TEXT,
                closed_at TEXT,
                closed_by_username TEXT,
                FOREIGN KEY (assigned_to_username) REFERENCES users(username),
                FOREIGN KEY (assigned_by_username) REFERENCES users(username),
                FOREIGN KEY (closed_by_username) REFERENCES users(username),
                UNIQUE(referral_id, episode_no)
            )
            """
        )
        cur.execute(
            """
            INSERT INTO referral_assignments_new
            (
                id, referral_id, episode_no, assigned_to_username, assigned_by_username, assigned_at, status, patient_name,
                urgency, notes, created_at, updated_at, last_status_at, due_at, closed_at, closed_by_username
            )
            SELECT
                id,
                referral_id,
                COALESCE(episode_no, 1),
                COALESCE(NULLIF(TRIM(assigned_to_username), ''), '__legacy_unknown__'),
                COALESCE(NULLIF(TRIM(assigned_by_username), ''), '__legacy_unknown__'),
                assigned_at,
                status,
                patient_name,
                urgency,
                notes,
                COALESCE(created_at, assigned_at),
                COALESCE(updated_at, assigned_at),
                COALESCE(last_status_at, assigned_at),
                due_at,
                closed_at,
                NULLIF(TRIM(closed_by_username), '')
            FROM referral_assignments
            """
        )
        cur.execute("DROP TABLE referral_assignments")
        cur.execute("ALTER TABLE referral_assignments_new RENAME TO referral_assignments")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_referral_assignments_referral ON referral_assignments(referral_id, episode_no DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_referral_assignments_assignee_status ON referral_assignments(assigned_to_username, status)")

    @staticmethod
    def _ensure_migration_users_exist(conn: sqlite3.Connection) -> None:
        cur = conn.cursor()
        usernames = set()
        cur.execute(
            """
            SELECT DISTINCT COALESCE(NULLIF(TRIM(assigned_to_username), ''), '__legacy_unknown__')
            FROM referral_assignments
            UNION
            SELECT DISTINCT COALESCE(NULLIF(TRIM(assigned_by_username), ''), '__legacy_unknown__')
            FROM referral_assignments
            UNION
            SELECT DISTINCT NULLIF(TRIM(closed_by_username), '')
            FROM referral_assignments
            """
        )
        for row in cur.fetchall():
            username = str(row[0] or "").strip()
            if username:
                usernames.add(username)

        if not usernames:
            return

        for username in sorted(usernames):
            cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, 'viewer')
                """,
                (username, "!legacy-migrated-user"),
            )

    @staticmethod
    def ensure_schema(conn: sqlite3.Connection) -> None:
        """Create referral hardening tables and add missing columns."""
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referral_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_username TEXT,
                from_status TEXT,
                to_status TEXT,
                details TEXT,
                event_time TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                referral_id TEXT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                read_at TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_referral_events_referral ON referral_events(referral_id, event_time DESC)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_inbox_user_read ON notification_inbox(username, is_read, created_at DESC)"
        )

        cur.execute("PRAGMA table_info(referral_assignments)")
        existing_columns = {row[1] for row in cur.fetchall()}
        required_columns = {
            "episode_no": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT",
            "updated_at": "TEXT",
            "last_status_at": "TEXT",
            "due_at": "TEXT",
            "closed_at": "TEXT",
            "closed_by_username": "TEXT",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            cur.execute(f"ALTER TABLE referral_assignments ADD COLUMN {column_name} {column_type}")

        now = ReferralService._now()
        cur.execute("UPDATE referral_assignments SET created_at = COALESCE(created_at, assigned_at, ?)", (now,))
        cur.execute("UPDATE referral_assignments SET updated_at = COALESCE(updated_at, assigned_at, ?)", (now,))
        cur.execute("UPDATE referral_assignments SET last_status_at = COALESCE(last_status_at, assigned_at, ?)", (now,))
        cur.execute("UPDATE referral_assignments SET episode_no = COALESCE(episode_no, 1)")

        if ReferralService._has_legacy_unique_referral_id(conn):
            ReferralService._migrate_referral_assignments_schema(conn)

    @staticmethod
    def _record_event(
        conn: sqlite3.Connection,
        referral_id: str,
        event_type: str,
        actor_username: str = "",
        from_status: str = "",
        to_status: str = "",
        details: str = "",
    ) -> None:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO referral_events
            (referral_id, event_type, actor_username, from_status, to_status, details, event_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(referral_id or "").strip(),
                str(event_type or "").strip(),
                str(actor_username or "").strip(),
                str(from_status or "").strip(),
                str(to_status or "").strip(),
                str(details or "").strip(),
                ReferralService._now(),
            ),
        )

    @staticmethod
    def _notify(
        conn: sqlite3.Connection,
        username: str,
        referral_id: str,
        title: str,
        message: str,
        category: str = "referral",
    ) -> None:
        user = str(username or "").strip()
        if not user:
            return
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notification_inbox
            (username, referral_id, category, title, message, is_read, created_at, read_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
            """,
            (
                user,
                str(referral_id or "").strip(),
                str(category or "referral"),
                str(title or "Referral update"),
                str(message or ""),
                ReferralService._now(),
            ),
        )

    @staticmethod
    def assign_referral(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        assigned_to_username: str,
        assigned_by_username: str,
        patient_name: str = "",
        urgency: str = "normal",
        notes: str = "",
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        assigned_to = str(assigned_to_username or "").strip()
        assigned_by = str(assigned_by_username or "").strip()
        urgency_value = str(urgency or "normal").strip().lower()
        if not referral_key or not assigned_to or not assigned_by:
            return False
        if assigned_to == assigned_by:
            return False
        if urgency_value not in ReferralService.VALID_URGENCY:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            if not ReferralService._is_clinician(conn, assigned_to):
                conn.close()
                return False
            now = ReferralService._now()
            next_episode = ReferralService._current_episode_no(conn, referral_key) + 1
            cur.execute(
                """
                INSERT INTO referral_assignments
                (referral_id, episode_no, assigned_to_username, assigned_by_username, assigned_at, patient_name, urgency, notes, status,
                 created_at, updated_at, last_status_at, due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    referral_key,
                    next_episode,
                    assigned_to,
                    assigned_by,
                    now,
                    str(patient_name or "").strip(),
                    urgency_value,
                    str(notes or "").strip(),
                    now,
                    now,
                    now,
                    ReferralService._default_due_at(urgency_value, now),
                ),
            )
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="assigned",
                actor_username=assigned_by,
                to_status="pending",
                details=f"Assigned to {assigned_to} (episode {next_episode})",
            )
            ReferralService._notify(
                conn,
                assigned_to,
                referral_key,
                title="New referral assigned",
                message=f"Referral {referral_key} has been assigned to you by {assigned_by}.",
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.IntegrityError:
            conn.close()
            return False
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(assigned_by, f"Assigned referral {referral_key} to {assigned_to}")
        return success

    @staticmethod
    def find_active_duplicate_referral(
        get_connection: Callable[[], sqlite3.Connection],
        patient_name: str,
        assigned_to_username: str,
    ) -> dict | None:
        patient_key = str(patient_name or "").strip().lower()
        assigned_to = str(assigned_to_username or "").strip()
        if not patient_key or not assigned_to:
            return None

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            placeholders = ", ".join(["?"] * len(ReferralService.ACTIVE_DUPLICATE_STATUSES))
            params = [patient_key, assigned_to, *ReferralService.ACTIVE_DUPLICATE_STATUSES]
            cur.execute(
                f"""
                SELECT referral_id, episode_no, status, assigned_at
                FROM referral_assignments
                WHERE LOWER(TRIM(patient_name)) = ?
                    AND assigned_to_username = ?
                    AND status IN ({placeholders})
                ORDER BY assigned_at DESC, id DESC
                LIMIT 1
                """,
                params,
            )
            row = cur.fetchone()
        except sqlite3.Error:
            row = None
        conn.close()

        if not row:
            return None
        return {
            "referral_id": str(row[0] or "").strip(),
            "episode_no": int(row[1] or 1),
            "status": str(row[2] or "").strip().lower(),
            "assigned_at": str(row[3] or "").strip(),
        }

    @staticmethod
    def get_pending_referrals(get_connection: Callable[[], sqlite3.Connection], username: str) -> list[dict]:
        user = str(username or "").strip()
        if not user:
            return []

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT
                    ra.id,
                    ra.referral_id,
                    ra.assigned_by_username,
                    COALESCE(NULLIF(TRIM(ub.display_name), ''), NULLIF(TRIM(ub.full_name), ''), ra.assigned_by_username) AS assigned_by_name,
                    ra.assigned_at,
                    ra.patient_name,
                    ra.urgency,
                    ra.notes,
                    ra.status,
                    ra.due_at
                FROM referral_assignments ra
                LEFT JOIN users ub ON ub.username = ra.assigned_by_username
                WHERE ra.assigned_to_username = ? AND ra.status IN ('pending', 'viewed')
                ORDER BY
                    CASE LOWER(ra.urgency)
                        WHEN 'critical' THEN 0
                        WHEN 'urgent' THEN 1
                        ELSE 2
                    END,
                    ra.assigned_at DESC
                """,
                (user,),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
        conn.close()

        return [
            {
                "id": row[0],
                "referral_id": row[1],
                "assigned_by_username": row[2],
                "assigned_by": ReferralService._as_doctor_name(row[3]),
                "assigned_at": row[4],
                "patient_name": row[5],
                "urgency": row[6],
                "notes": row[7],
                "status": row[8],
                "due_at": row[9],
            }
            for row in rows
        ]

    @staticmethod
    def get_user_referrals(get_connection: Callable[[], sqlite3.Connection], username: str, limit: int = 100) -> list[dict]:
        user = str(username or "").strip()
        if not user:
            return []

        safe_limit = max(1, min(int(limit), 500))
        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT
                    ra.id,
                    ra.referral_id,
                    ra.assigned_to_username,
                    COALESCE(NULLIF(TRIM(ut.display_name), ''), NULLIF(TRIM(ut.full_name), ''), ra.assigned_to_username) AS assigned_to_name,
                    ra.assigned_by_username,
                    COALESCE(NULLIF(TRIM(ub.display_name), ''), NULLIF(TRIM(ub.full_name), ''), ra.assigned_by_username) AS assigned_by_name,
                    ra.assigned_at,
                    ra.patient_name,
                    ra.urgency,
                    ra.notes,
                    ra.status
                FROM referral_assignments ra
                LEFT JOIN users ut ON ut.username = ra.assigned_to_username
                LEFT JOIN users ub ON ub.username = ra.assigned_by_username
                WHERE ra.assigned_to_username = ? OR ra.assigned_by_username = ?
                ORDER BY ra.assigned_at DESC
                LIMIT ?
                """,
                (user, user, safe_limit),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
        conn.close()

        result = []
        for row in rows:
            assigned_to_username = row[2]
            assigned_to_name = row[3]
            assigned_by_username = row[4]
            assigned_by_name = row[5]
            relation = "assigned_to_me" if assigned_to_username == user else "created_by_me"
            result.append(
                {
                    "id": row[0],
                    "referral_id": row[1],
                    "assigned_to_username": assigned_to_username,
                    "assigned_to": ReferralService._as_doctor_name(assigned_to_name),
                    "assigned_by_username": assigned_by_username,
                    "assigned_by": ReferralService._as_doctor_name(assigned_by_name),
                    "assigned_at": row[6],
                    "patient_name": row[7],
                    "urgency": row[8],
                    "notes": row[9],
                    "status": row[10],
                    "relation": relation,
                }
            )
        return result

    @staticmethod
    def get_referral_count(get_connection: Callable[[], sqlite3.Connection], username: str, status: str = "pending") -> int:
        user = str(username or "").strip()
        status_value = str(status or "").strip()
        if not user or not status_value:
            return 0

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT COUNT(*) FROM referral_assignments
                WHERE assigned_to_username = ? AND status = ?
                """,
                (user, status_value),
            )
            row = cur.fetchone()
            count = int(row[0]) if row else 0
        except sqlite3.Error:
            count = 0
        conn.close()
        return count

    @staticmethod
    def update_referral_status(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        new_status: str,
        actor_username: str = "",
        reason_code: str = "",
        reason_note: str = "",
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        target_status = str(new_status or "").strip().lower()
        actor = str(actor_username or "").strip()
        if not referral_key or target_status not in ReferralService.STATUS_TRANSITIONS:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT status, assigned_to_username, episode_no
                FROM referral_assignments
                WHERE referral_id = ?
                ORDER BY episode_no DESC, id DESC
                LIMIT 1
                """,
                (referral_key,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False

            current_status = str(row[0] or "").strip().lower()
            assigned_to = str(row[1] or "").strip()
            episode_no = int(row[2] or 1)
            if target_status not in ReferralService.STATUS_TRANSITIONS.get(current_status, set()):
                conn.close()
                return False
            reason_value = str(reason_code or "").strip().lower()
            reason_text = str(reason_note or "").strip()
            if target_status == "completed" and reason_value not in ReferralService.COMPLETION_REASONS:
                conn.close()
                return False

            now = ReferralService._now()
            close_time = now if target_status in {"completed", "archived"} else None
            close_actor = actor if close_time else None
            cur.execute(
                """
                UPDATE referral_assignments
                SET status = ?, updated_at = ?, last_status_at = ?, closed_at = COALESCE(?, closed_at),
                    closed_by_username = COALESCE(?, closed_by_username)
                WHERE referral_id = ? AND episode_no = ?
                """,
                (target_status, now, now, close_time, close_actor, referral_key, episode_no),
            )
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="status_changed",
                actor_username=actor,
                from_status=current_status,
                to_status=target_status,
                details=json.dumps(
                    {
                        "from_status": current_status,
                        "to_status": target_status,
                        "reason_code": reason_value,
                        "reason_label": ReferralService.COMPLETION_REASONS.get(reason_value, ""),
                        "reason_note": reason_text,
                    }
                ),
            )
            if assigned_to and actor and assigned_to != actor:
                ReferralService._notify(
                    conn,
                    assigned_to,
                    referral_key,
                    title="Referral status updated",
                    message=f"Referral {referral_key} is now {target_status.replace('_', ' ')}.",
                )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if success and actor:
            add_activity_log(actor, f"Updated referral {referral_key}: {current_status} -> {target_status}")
        return success

    @staticmethod
    def append_referral_note(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        actor_username: str,
        note: str,
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        actor = str(actor_username or "").strip()
        note_text = str(note or "").strip()
        if not referral_key or not actor or not note_text:
            return False
        if len(note_text) > 5000:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT notes, assigned_to_username, assigned_by_username, patient_name, episode_no, status
                FROM referral_assignments
                WHERE referral_id = ?
                ORDER BY episode_no DESC, id DESC
                LIMIT 1
                """,
                (referral_key,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False
            existing = str(row[0] or "").strip()
            assigned_to = str(row[1] or "").strip()
            assigned_by = str(row[2] or "").strip()
            patient_name = str(row[3] or "").strip()
            episode_no = int(row[4] or 1)
            status = str(row[5] or "").strip().lower()

            # Clinical note exchange is constrained to clinicians directly involved in the referral handoff.
            if actor not in {assigned_to, assigned_by}:
                conn.close()
                return False
            if status not in {"pending", "viewed", "in_review"}:
                conn.close()
                return False

            timestamp = ReferralService._now()
            try:
                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.now()
            pretty_date = dt.strftime("%Y-%m-%d")
            pretty_hour = dt.strftime("%H:%M")
            entry = f"Message on this patient on {pretty_date} at {pretty_hour} by {actor}: {note_text}"
            merged = f"{existing}\n{entry}".strip() if existing else entry
            cur.execute(
                "UPDATE referral_assignments SET notes = ?, updated_at = ? WHERE referral_id = ? AND episode_no = ?",
                (merged, timestamp, referral_key, episode_no),
            )
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="note_added",
                actor_username=actor,
                details=note_text,
            )
            patient_label = patient_name or f"referral {referral_key}"
            notification_title = "Clinical note added"
            notification_message = (
                f"{actor} added a clinical note for {patient_label} "
                f"(Referral ID: {referral_key}) on {pretty_date} at {pretty_hour}: {note_text}"
            )
            recipients = {assigned_to, assigned_by}
            for recipient in recipients:
                if recipient and recipient != actor:
                    ReferralService._notify(
                        conn,
                        recipient,
                        referral_key,
                        title=notification_title,
                        message=notification_message,
                    )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(actor, f"Updated referral note {referral_key}")
        return success

    @staticmethod
    def reassign_referral(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        new_assignee_username: str,
        acting_username: str,
        reason: str = "",
        reason_code: str = "",
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        new_assignee = str(new_assignee_username or "").strip()
        actor = str(acting_username or "").strip()
        reason_text = str(reason or "").strip() or "Reassigned for workflow continuity"
        reason_code_value = str(reason_code or "").strip().lower()
        if not referral_key or not new_assignee or not actor:
            return False
        if new_assignee == actor:
            return False
        if reason_code_value not in ReferralService.REASSIGNMENT_REASONS:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            if not ReferralService._is_clinician(conn, new_assignee):
                conn.close()
                return False
            cur.execute(
                """
                SELECT assigned_to_username, assigned_by_username, patient_name, urgency, notes, status, episode_no
                FROM referral_assignments
                WHERE referral_id = ?
                ORDER BY episode_no DESC, id DESC
                LIMIT 1
                """,
                (referral_key,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False

            current_assignee = str(row[0] or "").strip()
            if current_assignee == new_assignee:
                conn.close()
                return False
            if actor == new_assignee:
                conn.close()
                return False
            current_assigned_by = str(row[1] or "").strip()
            current_patient_name = str(row[2] or "").strip()
            current_urgency = str(row[3] or "normal").strip().lower() or "normal"
            existing_notes = str(row[4] or "").strip()
            current_status = str(row[5] or "").strip().lower()
            current_episode = int(row[6] or 1)
            if "reassigned" not in ReferralService.STATUS_TRANSITIONS.get(current_status, set()):
                conn.close()
                return False

            timestamp = ReferralService._now()
            note_line = (
                f"[{timestamp}] {actor}: Reassigned from {current_assignee or 'N/A'} "
                f"to {new_assignee}. Reason: [{ReferralService.REASSIGNMENT_REASONS[reason_code_value]}] {reason_text}"
            )
            merged_notes = f"{existing_notes}\n{note_line}".strip() if existing_notes else note_line
            cur.execute(
                """
                UPDATE referral_assignments
                SET assigned_to_username = ?, status = 'reassigned', notes = ?, updated_at = ?, last_status_at = ?
                WHERE referral_id = ? AND episode_no = ?
                """,
                (current_assignee, merged_notes, timestamp, timestamp, referral_key, current_episode),
            )
            next_episode = current_episode + 1
            cur.execute(
                """
                INSERT INTO referral_assignments
                (
                    referral_id, episode_no, assigned_to_username, assigned_by_username, assigned_at, status,
                    patient_name, urgency, notes, created_at, updated_at, last_status_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    referral_key,
                    next_episode,
                    new_assignee,
                    actor or current_assigned_by,
                    timestamp,
                    current_patient_name,
                    current_urgency,
                    merged_notes,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="reassigned",
                actor_username=actor,
                from_status=current_status,
                to_status="reassigned",
                details=json.dumps(
                    {
                        "from_assignee": current_assignee,
                        "to_assignee": new_assignee,
                        "reason_code": reason_code_value,
                        "reason_label": ReferralService.REASSIGNMENT_REASONS[reason_code_value],
                        "reason": reason_text,
                    }
                ),
            )
            ReferralService._notify(
                conn,
                new_assignee,
                referral_key,
                title="Referral reassigned to you",
                message=f"Referral {referral_key} was reassigned by {actor}.",
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(actor, f"Reassigned referral {referral_key} to {new_assignee}")
        return success

    @staticmethod
    def update_referral_details(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        actor_username: str,
        urgency: str = "",
        notes: str = "",
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        actor = str(actor_username or "").strip()
        urgency_value = str(urgency or "").strip().lower()
        notes_value = str(notes or "").strip()
        if not referral_key or not actor:
            return False
        if not urgency_value and not notes_value:
            return False
        if urgency_value and urgency_value not in ReferralService.VALID_URGENCY:
            return False
        if len(notes_value) > 5000:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT assigned_by_username, urgency, notes, status, episode_no
                FROM referral_assignments
                WHERE referral_id = ?
                ORDER BY episode_no DESC, id DESC
                LIMIT 1
                """,
                (referral_key,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False

            assigned_by = str(row[0] or "").strip()
            current_urgency = str(row[1] or "normal").strip().lower() or "normal"
            current_notes = str(row[2] or "").strip()
            current_status = str(row[3] or "").strip().lower()
            current_episode = int(row[4] or 1)

            if assigned_by != actor:
                conn.close()
                return False
            if current_status in {"completed", "archived"}:
                conn.close()
                return False

            new_urgency = urgency_value or current_urgency
            new_notes = notes_value if notes_value else current_notes
            now = ReferralService._now()
            cur.execute(
                """
                UPDATE referral_assignments
                SET urgency = ?, notes = ?, updated_at = ?, due_at = ?
                WHERE referral_id = ? AND episode_no = ?
                """,
                (
                    new_urgency,
                    new_notes,
                    now,
                    ReferralService._default_due_at(new_urgency, now),
                    referral_key,
                    current_episode,
                ),
            )
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="details_updated",
                actor_username=actor,
                from_status=current_status,
                to_status=current_status,
                details=json.dumps(
                    {
                        "urgency_from": current_urgency,
                        "urgency_to": new_urgency,
                        "notes_updated": bool(notes_value),
                    }
                ),
            )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(actor, f"Updated referral details {referral_key}")
        return success

    @staticmethod
    def delete_referral(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        actor_username: str,
        reason: str = "",
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        actor = str(actor_username or "").strip()
        reason_text = str(reason or "").strip() or "Archived by referral creator"
        if not referral_key or not actor:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT assigned_by_username, assigned_to_username, status, notes, episode_no
                FROM referral_assignments
                WHERE referral_id = ?
                ORDER BY episode_no DESC, id DESC
                LIMIT 1
                """,
                (referral_key,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False

            assigned_by = str(row[0] or "").strip()
            assigned_to = str(row[1] or "").strip()
            current_status = str(row[2] or "").strip().lower()
            existing_notes = str(row[3] or "").strip()
            current_episode = int(row[4] or 1)

            if assigned_by != actor:
                conn.close()
                return False
            if current_status == "archived":
                conn.close()
                return False
            if current_status != "completed":
                conn.close()
                return False

            now = ReferralService._now()
            note_line = f"[{now}] {actor}: Referral archived. Reason: {reason_text}"
            merged_notes = f"{existing_notes}\n{note_line}".strip() if existing_notes else note_line

            cur.execute(
                """
                UPDATE referral_assignments
                SET status = 'archived', notes = ?, updated_at = ?, last_status_at = ?, closed_at = ?, closed_by_username = ?
                WHERE referral_id = ? AND episode_no = ?
                """,
                (merged_notes, now, now, now, actor, referral_key, current_episode),
            )
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="archived",
                actor_username=actor,
                from_status=current_status,
                to_status="archived",
                details=reason_text,
            )
            if assigned_to and assigned_to != actor:
                ReferralService._notify(
                    conn,
                    assigned_to,
                    referral_key,
                    title="Referral archived",
                    message=f"Referral {referral_key} was archived by {actor}.",
                )
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(actor, f"Archived referral {referral_key}")
        return success

    @staticmethod
    def purge_archived_referral(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        actor_username: str,
        note: str = "",
    ) -> bool:
        referral_key = str(referral_id or "").strip()
        actor = str(actor_username or "").strip()
        note_text = str(note or "").strip()
        if not referral_key or not actor:
            return False
        if len(note_text) > 5000:
            return False

        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT assigned_by_username, status
                FROM referral_assignments
                WHERE referral_id = ?
                ORDER BY episode_no DESC, id DESC
                LIMIT 1
                """,
                (referral_key,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False

            assigned_by = str(row[0] or "").strip()
            current_status = str(row[1] or "").strip().lower()
            if assigned_by != actor or current_status != "archived":
                conn.close()
                return False

            ReferralService._record_event(
                conn,
                referral_key,
                event_type="purged",
                actor_username=actor,
                from_status="archived",
                to_status="deleted",
                details=note_text or "Deleted archived referral",
            )
            cur.execute("DELETE FROM notification_inbox WHERE referral_id = ?", (referral_key,))
            cur.execute("DELETE FROM referral_events WHERE referral_id = ?", (referral_key,))
            cur.execute("DELETE FROM referral_assignments WHERE referral_id = ?", (referral_key,))
            conn.commit()
            success = cur.rowcount > 0
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(actor, f"Deleted archived referral {referral_key}")
        return success

    @staticmethod
    def log_external_referral_letter(
        get_connection: Callable[[], sqlite3.Connection],
        add_activity_log: Callable[[str, str], bool],
        referral_id: str,
        actor_username: str,
        patient_name: str,
        destination_name: str,
        destination_department: str,
        destination_contact: str,
        urgency: str,
        pdf_path: str,
    ) -> bool:
        """Persist an audit event for externally generated referral letters."""
        referral_key = str(referral_id or "").strip()
        actor = str(actor_username or "").strip()
        if not referral_key or not actor:
            return False

        details = json.dumps(
            {
                "patient_name": str(patient_name or "").strip(),
                "destination_name": str(destination_name or "").strip(),
                "destination_department": str(destination_department or "").strip(),
                "destination_contact": str(destination_contact or "").strip(),
                "urgency": str(urgency or "").strip(),
                "pdf_path": str(pdf_path or "").strip(),
            }
        )
        conn = get_connection()
        try:
            ReferralService.ensure_schema(conn)
            ReferralService._record_event(
                conn,
                referral_key,
                event_type="external_letter_generated",
                actor_username=actor,
                to_status="letter_generated",
                details=details,
            )
            conn.commit()
            success = True
        except sqlite3.Error:
            success = False
        conn.close()

        if success:
            add_activity_log(actor, f"Generated external referral letter {referral_key}")
        return success

    @staticmethod
    def get_unread_notifications(
        get_connection: Callable[[], sqlite3.Connection], username: str, limit: int = 30
    ) -> list[dict]:
        user = str(username or "").strip()
        if not user:
            return []
        safe_limit = max(1, min(int(limit), 200))
        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT id, referral_id, category, title, message, created_at
                FROM notification_inbox
                WHERE username = ? AND is_read = 0
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user, safe_limit),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
        conn.close()
        return [
            {
                "id": row[0],
                "referral_id": row[1],
                "category": row[2],
                "title": row[3],
                "message": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    @staticmethod
    def get_notifications(
        get_connection: Callable[[], sqlite3.Connection],
        username: str,
        include_read: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        user = str(username or "").strip()
        if not user:
            return []
        safe_limit = max(1, min(int(limit), 500))
        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            if include_read:
                cur.execute(
                    """
                    SELECT id, referral_id, category, title, message, is_read, created_at, read_at
                    FROM notification_inbox
                    WHERE username = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (user, safe_limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, referral_id, category, title, message, is_read, created_at, read_at
                    FROM notification_inbox
                    WHERE username = ? AND is_read = 0
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (user, safe_limit),
                )
            rows = cur.fetchall()
        except sqlite3.Error:
            rows = []
        conn.close()
        return [
            {
                "id": row[0],
                "referral_id": row[1],
                "category": row[2],
                "title": row[3],
                "message": row[4],
                "is_read": bool(row[5]),
                "created_at": row[6],
                "read_at": row[7] or "",
            }
            for row in rows
        ]

    @staticmethod
    def mark_notification_read(get_connection: Callable[[], sqlite3.Connection], notification_id: int, username: str) -> bool:
        user = str(username or "").strip()
        if not user:
            return False
        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                UPDATE notification_inbox
                SET is_read = 1, read_at = ?
                WHERE id = ? AND username = ?
                """,
                (ReferralService._now(), int(notification_id), user),
            )
            conn.commit()
            success = cur.rowcount > 0
        except (sqlite3.Error, ValueError, TypeError):
            success = False
        conn.close()
        return success

    @staticmethod
    def mark_all_notifications_read(get_connection: Callable[[], sqlite3.Connection], username: str) -> int:
        user = str(username or "").strip()
        if not user:
            return 0
        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                UPDATE notification_inbox
                SET is_read = 1, read_at = ?
                WHERE username = ? AND is_read = 0
                """,
                (ReferralService._now(), user),
            )
            conn.commit()
            updated = int(cur.rowcount or 0)
        except sqlite3.Error:
            updated = 0
        conn.close()
        return updated

    @staticmethod
    def get_referral_kpis(get_connection: Callable[[], sqlite3.Connection], username: str) -> dict:
        user = str(username or "").strip()
        if not user:
            return {"avg_turnaround_hours": 0.0, "reassignment_rate_pct": 0.0, "overdue_count": 0}
        conn = get_connection()
        cur = conn.cursor()
        try:
            ReferralService.ensure_schema(conn)
            cur.execute(
                """
                SELECT assigned_at, closed_at
                FROM referral_assignments
                WHERE (assigned_to_username = ? OR assigned_by_username = ?)
                  AND status = 'completed'
                  AND assigned_at IS NOT NULL
                  AND closed_at IS NOT NULL
                """,
                (user, user),
            )
            rows = cur.fetchall()
            durations = []
            for row in rows:
                try:
                    start = datetime.strptime(str(row[0] or ""), "%Y-%m-%d %H:%M:%S")
                    end = datetime.strptime(str(row[1] or ""), "%Y-%m-%d %H:%M:%S")
                    durations.append((end - start).total_seconds() / 3600.0)
                except ValueError:
                    continue
            avg_turnaround = round(sum(durations) / len(durations), 2) if durations else 0.0

            cur.execute(
                """
                SELECT COUNT(*)
                FROM referral_assignments
                WHERE assigned_by_username = ?
                """,
                (user,),
            )
            total_created = int((cur.fetchone() or [0])[0])
            cur.execute(
                """
                SELECT COUNT(*)
                FROM referral_events
                WHERE actor_username = ? AND event_type = 'reassigned'
                """,
                (user,),
            )
            reassign_events = int((cur.fetchone() or [0])[0])
            reassignment_rate = round((reassign_events / total_created) * 100.0, 2) if total_created > 0 else 0.0

            cur.execute(
                """
                SELECT COUNT(*)
                FROM referral_assignments
                WHERE assigned_to_username = ?
                  AND status NOT IN ('completed', 'archived')
                  AND due_at IS NOT NULL
                  AND TRIM(due_at) <> ''
                  AND due_at < ?
                """,
                (user, ReferralService._now()),
            )
            overdue_count = int((cur.fetchone() or [0])[0])
        except sqlite3.Error:
            avg_turnaround = 0.0
            reassignment_rate = 0.0
            overdue_count = 0
        conn.close()
        return {
            "avg_turnaround_hours": avg_turnaround,
            "reassignment_rate_pct": reassignment_rate,
            "overdue_count": overdue_count,
        }
