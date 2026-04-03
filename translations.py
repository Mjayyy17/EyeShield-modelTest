"""Centralised translation strings for EyeShield EMR. English only."""

TRANSLATIONS = {
    "English": {
        # Settings page
        "settings_title": "Settings",
        "settings_subtitle": "Local offline preferences for this installation",
        "settings_preferences": "Preferences",
        "settings_theme": "Theme:",
        "settings_language": "Language:",
        "settings_auto_logout": "Enable auto-logout after inactivity",
        "settings_confirm": "Ask confirmation before destructive actions",
        "settings_compact": "Use compact table rows",
        "settings_about": "About",
        "settings_terms": "Terms of Use",
        "settings_privacy": "Privacy Policy",
        "settings_about_text": (
            "EyeShield EMR is an offline clinical screening system for diabetic retinopathy. "
            "It supports patient intake, AI-assisted image analysis, report generation, and "
            "internal referral coordination. AI output is decision support only and must be "
            "reviewed by a qualified clinician before final diagnosis and treatment planning."
        ),
        "settings_terms_text": (
            "By using EyeShield EMR, you agree to use the system only for authorized clinical "
            "screening, documentation, and referral workflows. Users must follow role-based "
            "permissions, maintain accurate records, and avoid unauthorized copying, sharing, "
            "or modification of patient data. Internal referral notes and status updates must "
            "be used for continuity of care. The software is provided as a clinical support "
            "tool and does not replace professional medical judgment."
        ),
        "settings_privacy_text": (
            "EyeShield EMR stores patient and user data locally on this device/database and "
            "does not require internet transfer for core operation. Access must be restricted "
            "to authorized users, with workstation lock/logout on shared devices. Exports and "
            "printed reports should be handled only through approved clinical channels and "
            "according to retention policy. Administrators are responsible for backup, access "
            "control, and secure lifecycle management of local records."
        ),
        "settings_reset": "Reset Defaults",
        "settings_save": "Save Settings",
        # Nav labels
        "nav_dashboard": "Dashboard",
        "nav_screening": "Screening",
        "nav_camera": "Camera",
        "nav_reports": "Reports",
        "nav_users": "Users",
        "nav_settings": "Settings",
        "nav_help": "Help",
        # Dashboard
        "dash_welcome": "Welcome back",
        "dash_kpi_total": "TOTAL SCREENINGS",
        "dash_kpi_flagged": "FLAGGED FOR REVIEW",
        "dash_kpi_pending": "PENDING REVIEW",
        "dash_kpi_conf": "MODEL CONFIDENCE",
        "dash_recent": "RECENT SCREENINGS",
        "dash_actions_title": "QUICK ACTIONS",
        "dash_btn_new": "  New Screening",
        "dash_btn_reports": "  View Reports",
        "dash_insight_title": "CLINICAL INSIGHT",
        "dash_insight_default": "Start a screening to generate insight.",
        "dash_empty": "No screening records yet. Start by running a new screening.",
        "dash_kpi_total_sub": "All saved DR screenings",
        "dash_flagged_cases": "Cases flagged for review",
        "dash_no_flagged": "No cases flagged",
        "dash_awaiting": "Awaiting review",
        "dash_all_reviewed": "All reviews complete",
        "dash_conf_across": "Across {n} record",
        "dash_no_conf": "No confidence data yet",
        "dash_no_screenings": "No screenings yet. Run a new screening to see trends here.",
        "dash_insight_all_clear": "All screenings reviewed — no action needed. Continue routine monitoring.",
        # Camera
        "cam_title": "Camera Integration Sandbox",
        "cam_subtitle": "Camera preview and diagnostics while fundus camera integration is in progress.",
        "cam_stopped": "Camera is stopped.",
        "cam_start": "Start Camera",
        "cam_stop": "Stop Camera",
        # Screening form
        "scr_patient_info": "Patient Information",
        "scr_clinical_history": "Clinical History",
        "scr_image_upload": "Fundus Image Upload",
        "scr_upload_btn": "Upload Image",
        "scr_take_picture_btn": "Take Picture",
        "scr_clear_btn": "Clear",
        "scr_analyze_btn": "Analyze Image",
        "scr_label_pid": "Patient ID:",
        "scr_label_name": "Name:",
        "scr_label_dob": "Date of Birth:",
        "scr_label_age": "Age:",
        "scr_label_sex": "Sex:",
        "scr_label_contact": "Contact:",
        "scr_label_eye": "Eye Screened:",
        "scr_label_diabetes": "Diabetes Type:",
        "scr_label_duration": "Duration:",
        "scr_label_hba1c": "HbA1c:",
        "scr_label_notes": "Notes:",
        # Reports
        "rep_title": "DR Screening Reports",
        "rep_subtitle": "Complete diabetic retinopathy screening outcomes from locally saved records",
        "rep_refresh": "Refresh",
        "rep_export": "Export Results",
        "rep_archived": "Archived Records",
        "rep_archive_sel": "Archive Selected",
        "rep_quick_filters": "Quick Filters",
        "rep_summary": "Summary",
        "rep_all_results": "All Screening Results",
        "rep_stat_total": "Total Screenings",
        "rep_stat_unique": "Unique Patients",
        "rep_stat_no_dr": "No DR",
        "rep_stat_review": "Needs Review",
        "rep_stat_hba1c": "Avg HbA1c",
        # Users
        "usr_title": "User Management",
        "usr_table": "Users",
        "usr_log": "Activity Log",
        # Help & Support
        "hlp_title": "Help & Support",
        "hlp_subtitle": "Complete guidance for screening workflow, result safety checks, reports, and support contacts.",
        "hlp_quick_start": "Quick Start",
        "hlp_quick_start_body": """
            <ul>
                <li>Log in with your assigned role and open <b>Screening</b>.</li>
                <li>Complete all required patient fields, then upload one fundus image (JPG/PNG/JPEG).</li>
                <li>Click <b>Analyze Image</b>, review the AI result, confidence, and recommendations.</li>
                <li><b>Save</b> the eye result; the results window stays open so you can review, export PDF, and continue safely.</li>
                <li>For bilateral workflow, screen and save one eye first, then use <b>Screen Other Eye</b>.</li>
                <li>Use <b>Refer Patient</b> for Moderate, Severe, or Proliferative DR when specialist follow-up is needed.</li>
                <li>Use <b>Reports</b> for filtering, exports, and archived-record management.</li>
                <li>Use <b>Referrals</b> to track pending, in-review, completed, reassigned, and archived referral cases.</li>
            </ul>
            """,
        "hlp_howto": "How-to Guides",
        "hlp_howto_body": """
            <ul>
                <li><b>New screening:</b> Fill patient details, clinical history, and eye side, then upload image and analyze.</li>
                <li><b>Image quality:</b> If image is marked not gradable, capture a clearer, well-lit fundus image and retry.</li>
                <li><b>Duplicate eye record:</b> If the same patient eye already exists, choose <b>Replace Existing</b> or <b>Save as New Session</b>.</li>
                <li><b>Generate PDF report:</b> Save first; if only one eye is screened, you can generate single-eye report or screen the other eye first.</li>
                <li><b>Clinical decision fields:</b> Doctor classification, decision mode, findings, and override justification are included in final records and PDF.</li>
                <li><b>Refer patient:</b> Open referral from screening results, select a receiving facility, and include referral notes.</li>
                <li><b>Referral lifecycle:</b> Update status from pending to viewed/in-review/completed, or use reassigned/rereferred when routing changes.</li>
                <li><b>Trusted hospitals:</b> Maintain referral facilities by adding hospital name, department, and optional contact details.</li>
                <li><b>Reports page:</b> Search, filter, refresh, export, and archive selected records.</li>
                <li><b>Archived records:</b> Restore archived items when needed, or permanently delete only if allowed by policy.</li>
            </ul>
            """,
        "hlp_faq": "FAQ",
        "hlp_faq_body": """
            <ul>
                <li><b>Why can I not continue to analyze?</b> One or more required patient fields or image input is missing.</li>
                <li><b>Can I upload multiple images at once?</b> No. Current workflow supports one image per analysis.</li>
                <li><b>Why can I not generate a report?</b> You must complete analysis and save the current eye result first.</li>
                <li><b>Why did my confidence/result not appear?</b> The model may still be analyzing, or the image failed quality checks.</li>
                <li><b>Cannot find a patient in Reports:</b> Use search/filter, refresh records, and verify if the record was archived.</li>
                <li><b>Why can I not submit a referral?</b> Ensure the result is saved, a target facility is selected, and required referral fields are complete.</li>
                <li><b>Which statuses should I use in Referrals?</b> Use viewed/in-review during active management, completed when closed, and archived for inactive items.</li>
                <li><b>Can unsaved work be recovered?</b> Draft autosave is used for in-progress screening, but you should still save explicitly.</li>
            </ul>
            """,
        "hlp_troubleshoot": "Troubleshooting",
        "hlp_troubleshoot_body": """
            <ul>
                <li><b>Validation warnings:</b> Correct missing fields, invalid name format, age range, and abnormal glucose values before proceeding.</li>
                <li><b>Invalid image message:</b> Confirm file type and choose a valid fundus image path with read permissions.</li>
                <li><b>Unsaved result dialogs:</b> Choose <b>Save First</b> before starting a new patient, going back, or closing the app.</li>
                <li><b>Save failed:</b> Retry save, or select a different save location when prompted.</li>
                <li><b>Export issues:</b> Retry from Reports and verify destination folder permissions and available disk space.</li>
                <li><b>Referral not visible:</b> Refresh Referrals, confirm current status filters, and verify the referral was successfully submitted.</li>
                <li><b>Facility list missing:</b> Add or update entries in trusted hospitals before creating a new referral.</li>
                <li><b>Camera page:</b> Temporary webcam utility only; use screening upload for final DR analysis workflow.</li>
            </ul>
            """,
        "hlp_privacy": "Privacy & Compliance",
        "hlp_privacy_body": """
            <ul>
                <li>Access only patient records required for clinical care and documentation.</li>
                <li>Do not share screenshots, exports, or reports outside approved clinical channels.</li>
                <li>Use local settings such as auto-logout and confirmation prompts for safer operation.</li>
                <li>Always log out or lock the workstation when leaving a shared device.</li>
                <li>Archive records for workflow management, and permanently delete only per retention policy.</li>
            </ul>
            """,
        "hlp_contact": "Contact Support",
        "hlp_contact_body": """
            <p>
            <b>IT/App Support:</b> support@eyeshield.local<br>
            <b>Phone:</b> +1-000-000-0000<br>
            <b>Hours:</b> Mon-Fri, 8:00 AM - 6:00 PM<br><br>
            <b>When contacting support, include:</b><br>
            User role, patient ID (if applicable), page name, exact error message, and time of incident.
            </p>
            """,
    },
}


def get_pack(language: str) -> dict:
    """Return the translation pack for the given language, defaulting to English."""
    return TRANSLATIONS.get(language, TRANSLATIONS["English"])
