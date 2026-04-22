import sqlite3
import json
import os

# Path to the new database
DB_FILE = os.path.join(os.path.dirname(__file__), 'patient_records.db')
# Path to the JSON backup
JSON_FILE = os.path.join(os.path.dirname(__file__), 'backups', 'eyeshield_backup_20260405_205210', 'patient_records.json')

def create_table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS patient_records (
            id INTEGER PRIMARY KEY,
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
            screening_date TEXT,
            operator TEXT,
            follow_up TEXT,
            archived_at TEXT,
            archived_by TEXT,
            archive_reason TEXT,
            visual_acuity_left TEXT,
            visual_acuity_right TEXT,
            blood_pressure_systolic TEXT,
            blood_pressure_diastolic TEXT,
            fasting_blood_sugar TEXT,
            random_blood_sugar TEXT,
            diabetes_diagnosis_date TEXT,
            symptom_blurred_vision TEXT,
            symptom_floaters TEXT,
            symptom_flashes TEXT,
            symptom_vision_loss TEXT,
            screened_at TEXT,
            followup_date TEXT,
            followup_label TEXT,
            source_image_path TEXT,
            heatmap_image_path TEXT,
            image_sha256 TEXT,
            image_saved_at TEXT,
            height TEXT,
            weight TEXT,
            bmi TEXT,
            treatment_regimen TEXT,
            prev_dr_stage TEXT,
            original_screener_username TEXT,
            original_screener_name TEXT,
            ai_classification TEXT,
            doctor_classification TEXT,
            decision_mode TEXT,
            override_justification TEXT,
            final_diagnosis_icdr TEXT,
            doctor_findings TEXT,
            decision_by_username TEXT,
            decision_at TEXT
        )
    ''')
    conn.commit()

def import_json_to_db():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        records = json.load(f)
    conn = sqlite3.connect(DB_FILE)
    create_table(conn)
    for rec in records:
        columns = ', '.join(rec.keys())
        placeholders = ', '.join(['?'] * len(rec))
        values = [rec[k] for k in rec.keys()]
        conn.execute(f'INSERT OR REPLACE INTO patient_records ({columns}) VALUES ({placeholders})', values)
    conn.commit()
    conn.close()
    print(f"Imported {len(records)} records into {DB_FILE}")

if __name__ == '__main__':
    import_json_to_db()
