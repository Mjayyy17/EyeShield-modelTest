"""Centralised translation strings for EyeShield EMR. English and Filipino only."""

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
        "cam_title": "Temporary Webcam",
        "cam_subtitle": "Use this while fundus camera integration is in progress.",
        "cam_stopped": "Camera is stopped.",
        "cam_start": "Start Camera",
        "cam_stop": "Stop Camera",
        # Screening form
        "scr_patient_info": "Patient Information",
        "scr_clinical_history": "Clinical History",
        "scr_image_upload": "Fundus Image Upload",
        "scr_upload_btn": "Upload Image",
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
        "hlp_subtitle": "Quick guidance for daily workflows, troubleshooting, and support contacts.",
        "hlp_quick_start": "Quick Start",
        "hlp_quick_start_body": """
            <ul>
                <li>Log in with your assigned role.</li>
                <li>Use <b>Screening</b> to capture patient details and upload a fundus image.</li>
                <li>Review the result, then save the screening outcome.</li>
                <li>Generate summaries in <b>Reports</b>.</li>
            </ul>
            """,
        "hlp_howto": "How-to Guides",
        "hlp_howto_body": """
            <ul>
                <li><b>New screening:</b> Enter patient info, upload image, analyze, then save.</li>
                <li><b>Review results:</b> Open <b>Reports</b> to view all DR screening outcomes.</li>
                <li><b>Export report:</b> Use <b>Reports</b> to export all screening results.</li>
            </ul>
            """,
        "hlp_faq": "FAQ",
        "hlp_faq_body": """
            <ul>
                <li><b>Cannot log in:</b> Verify username/role and reset password with Admin.</li>
                <li><b>Missing patient:</b> Check spelling, ID format, and date filters.</li>
                <li><b>Image not loading:</b> Use JPG/PNG and confirm file permissions.</li>
            </ul>
            """,
        "hlp_troubleshoot": "Troubleshooting",
        "hlp_troubleshoot_body": """
            <ul>
                <li>Restart the app if pages are unresponsive.</li>
                <li>Confirm network or storage access for saving reports.</li>
                <li>Check printer settings or switch to PDF export.</li>
            </ul>
            """,
        "hlp_privacy": "Privacy & Compliance",
        "hlp_privacy_body": """
            <ul>
                <li>Only access patient data needed for care.</li>
                <li>Do not share screenshots or exports outside approved channels.</li>
                <li>Log out when leaving the workstation.</li>
            </ul>
            """,
        "hlp_contact": "Contact Support",
        "hlp_contact_body": """
            <p><b>Email:</b> support@eyeshield.local<br>
            <b>Phone:</b> +1-000-000-0000<br>
            <b>Hours:</b> Mon-Fri, 8:00 AM - 6:00 PM</p>
            """,
    },
    "Filipino": {
        # Settings page
        "settings_title": "Mga Setting",
        "settings_subtitle": "Mga lokal na kagustuhan para sa instalasyong ito",
        "settings_preferences": "Mga Kagustuhan",
        "settings_theme": "Tema:",
        "settings_language": "Wika:",
        "settings_auto_logout": "I-enable ang auto-logout pagkatapos ng kawalan ng aktibidad",
        "settings_confirm": "Humingi ng kumpirmasyon bago magsagawa ng mapanganib na aksyon",
        "settings_compact": "Gumamit ng maigting na mga hilera ng talahanayan",
        "settings_about": "Tungkol sa",
        "settings_terms": "Mga Tuntunin ng Paggamit",
        "settings_privacy": "Patakaran sa Pagkapribado",
        "settings_reset": "I-reset sa Default",
        "settings_save": "I-save ang Mga Setting",
        # Nav labels
        "nav_dashboard": "Dashboard",
        "nav_screening": "Pagsusuri",
        "nav_camera": "Camera",
        "nav_reports": "Ulat",
        "nav_users": "Mga Gumagamit",
        "nav_settings": "Mga Setting",
        "nav_help": "Tulong",
        # Dashboard
        "dash_welcome": "Maligayang pagbabalik",
        "dash_kpi_total": "KABUUANG PAGSUSURI",
        "dash_kpi_flagged": "NAKA-FLAG PARA SA REBYU",
        "dash_kpi_pending": "NAKABINBING REBYU",
        "dash_kpi_conf": "KUMPIYANSA NG MODELO",
        "dash_recent": "KAMAKAILANG PAGSUSURI",
        "dash_actions_title": "MABILIS NA AKSYON",
        "dash_btn_new": "  Bagong Pagsusuri",
        "dash_btn_reports": "  Tingnan ang Ulat",
        "dash_insight_title": "KLINIKAL NA KAALAMAN",
        "dash_insight_default": "Magsimula ng pagsusuri para makakuha ng kaalaman.",
        "dash_empty": "Wala pang rekord ng pagsusuri. Magsimula sa pagpapatakbo ng bagong pagsusuri.",
        "dash_kpi_total_sub": "Lahat ng na-save na DR screening",
        "dash_flagged_cases": "Mga kaso na naka-flag para sa rebyu",
        "dash_no_flagged": "Walang naka-flag na kaso",
        "dash_awaiting": "Naghihintay ng rebyu",
        "dash_all_reviewed": "Lahat ng rebyu ay kumpleto",
        "dash_conf_across": "Mula sa {n} rekord",
        "dash_no_conf": "Walang datos ng kumpiyansa",
        "dash_no_screenings": "Wala pang pagsusuri. Magsimula ng bagong pagsusuri para makita ang mga trend.",
        "dash_insight_all_clear": "Lahat ng pagsusuri ay nasuri — walang kinakailangang aksyon. Magpatuloy sa regular na pagmamatyag.",
        # Camera
        "cam_title": "Pansamantalang Webcam",
        "cam_subtitle": "Gamitin ito habang isinasama ang fundus camera.",
        "cam_stopped": "Naka-stop ang camera.",
        "cam_start": "Simulan ang Camera",
        "cam_stop": "Itigil ang Camera",
        # Screening form
        "scr_patient_info": "Impormasyon ng Pasyente",
        "scr_clinical_history": "Kasaysayang Klinikal",
        "scr_image_upload": "Pag-upload ng Fundus na Larawan",
        "scr_upload_btn": "Mag-upload ng Larawan",
        "scr_clear_btn": "I-clear",
        "scr_analyze_btn": "Suriin ang Larawan",
        "scr_label_pid": "ID ng Pasyente:",
        "scr_label_name": "Pangalan:",
        "scr_label_dob": "Petsa ng Kapanganakan:",
        "scr_label_age": "Edad:",
        "scr_label_sex": "Kasarian:",
        "scr_label_contact": "Kontak:",
        "scr_label_eye": "Matang Sinuri:",
        "scr_label_diabetes": "Uri ng Diyabetes:",
        "scr_label_duration": "Tagal:",
        "scr_label_hba1c": "HbA1c:",
        "scr_label_notes": "Mga Tala:",
        # Reports
        "rep_title": "Mga Ulat ng DR Pagsusuri",
        "rep_subtitle": "Kumpletong mga resulta ng pagsusuri ng diabetic retinopathy mula sa lokal na mga rekord",
        "rep_refresh": "I-refresh",
        "rep_export": "I-export ang mga Resulta",
        "rep_archived": "Mga Naka-archive na Rekord",
        "rep_archive_sel": "I-archive ang Napili",
        "rep_quick_filters": "Mabilis na mga Filter",
        "rep_summary": "Buod",
        "rep_all_results": "Lahat ng Resulta ng Pagsusuri",
        "rep_stat_total": "Kabuuang Pagsusuri",
        "rep_stat_unique": "Natatanging mga Pasyente",
        "rep_stat_no_dr": "Walang DR",
        "rep_stat_review": "Nangangailangan ng Rebyu",
        "rep_stat_hba1c": "Avg HbA1c",
        # Users
        "usr_title": "Pamamahala ng Gumagamit",
        "usr_table": "Mga Gumagamit",
        "usr_log": "Log ng Aktibidad",
        # Help & Support
        "hlp_title": "Tulong at Suporta",
        "hlp_subtitle": "Mabilis na gabay para sa araw-araw na gawain, pag-troubleshoot, at mga contact ng suporta.",
        "hlp_quick_start": "Mabilis na Simula",
        "hlp_quick_start_body": """
            <ul>
                <li>Mag-login gamit ang inyong itinalagang papel.</li>
                <li>Gamitin ang <b>Pagsusuri</b> upang i-record ang impormasyon ng pasyente at mag-upload ng larawan ng retina.</li>
                <li>Suriin ang resulta, pagkatapos ay i-save ang resulta ng pagsusuri.</li>
                <li>Bumuo ng mga buod sa <b>Ulat</b>.</li>
            </ul>
            """,
        "hlp_howto": "Mga Gabay sa Paggamit",
        "hlp_howto_body": """
            <ul>
                <li><b>Bagong pagsusuri:</b> Ilagay ang impormasyon ng pasyente, mag-upload ng larawan, suriin, pagkatapos ay i-save.</li>
                <li><b>Suriin ang mga resulta:</b> Buksan ang <b>Ulat</b> upang makita ang lahat ng mga resulta ng DR screening.</li>
                <li><b>I-export ang ulat:</b> Gamitin ang <b>Ulat</b> upang i-export ang lahat ng mga resulta ng pagsusuri.</li>
            </ul>
            """,
        "hlp_faq": "FAQ",
        "hlp_faq_body": """
            <ul>
                <li><b>Hindi makapag-login:</b> Suriin ang username/papel at i-reset ang password sa Admin.</li>
                <li><b>Nawawalang pasyente:</b> Suriin ang ispeling, format ng ID, at mga filter ng petsa.</li>
                <li><b>Hindi nag-lo-load ang larawan:</b> Gumamit ng JPG/PNG at kumpirmahin ang mga pahintulot ng file.</li>
            </ul>
            """,
        "hlp_troubleshoot": "Pag-aayos ng Problema",
        "hlp_troubleshoot_body": """
            <ul>
                <li>I-restart ang app kung ang mga pahina ay hindi sumasagot.</li>
                <li>Kumpirmahin ang access sa network o storage para sa pag-save ng mga ulat.</li>
                <li>Suriin ang mga setting ng printer o lumipat sa PDF export.</li>
            </ul>
            """,
        "hlp_privacy": "Pagkapribado at Pagsunod",
        "hlp_privacy_body": """
            <ul>
                <li>I-access lamang ang datos ng pasyente na kailangan para sa pangangalaga.</li>
                <li>Huwag ibahagi ang mga screenshot o export sa labas ng mga aprubadong channel.</li>
                <li>Mag-logout kapag umalis sa workstation.</li>
            </ul>
            """,
        "hlp_contact": "Makipag-ugnayan sa Suporta",
        "hlp_contact_body": """
            <p><b>Email:</b> support@eyeshield.local<br>
            <b>Telepono:</b> +1-000-000-0000<br>
            <b>Oras:</b> Lun-Biy, 8:00 AM - 6:00 PM</p>
            """,
    },
}


def get_pack(language: str) -> dict:
    """Return the translation pack for the given language, defaulting to English."""
    return TRANSLATIONS.get(language, TRANSLATIONS["English"])
