# config.py
import streamlit as st

# --- Google API Configuration ---
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
# CREDENTIALS_FILE = 'credentials.json' # Kept for reference, but get_google_services uses st.secrets

# --- Google Drive Master Configuration ---
MASTER_DRIVE_FOLDER_NAME = "e-MCM_Root_DAR_App"  # Master folder on Google Drive
MCM_PERIODS_FILENAME_ON_DRIVE = "mcm_periods_config.json"  # Config file on Google Drive
LOG_SHEET_FILENAME_ON_DRIVE = "e-MCM_App_Activity_Log" 
SMART_AUDIT_MASTER_DB_SHEET_NAME = "smart_audit_master_db" # New master DB sheet

SHARED_DRIVE_ID = "1xTUHQPiZtYj84ZJVXpdCRxG70ui18TSG"
# --- User Credentials ---
USER_CREDENTIALS = {
    "planning_officer": "pco_password",
    **{f"audit_group{i}": f"ag{i}_audit" for i in range(1, 31)}
}
USER_ROLES = {
    "planning_officer": "PCO",
    **{f"audit_group{i}": "AuditGroup" for i in range(1, 31)}
}
AUDIT_GROUP_NUMBERS = {
    f"audit_group{i}": i for i in range(1, 31)
}

# --- Gemini API Key ---
# Fetched in app.py or where needed, e.g., YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
# Or directly in gemini_utils.py

# Note: MANDATORY_FIELDS_FOR_SHEET and VALID_CATEGORIES are moved to validation_utils.py
# as they are tightly coupled with the validation logic.
