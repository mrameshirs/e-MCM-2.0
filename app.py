# app.py (Refactored)
import streamlit as st
import pandas as pd
st.set_page_config(layout="wide", page_title="e-MCM App - GST Audit 1")

# --- Custom Module Imports ---
from config import MASTER_DRIVE_FOLDER_NAME # Example of using config
from css_styles import load_custom_css
from google_utils import get_google_services, initialize_drive_structure
from ui_login import login_page
from ui_pco import pco_dashboard
from ui_audit_group import audit_group_dashboard

# --- Streamlit Page Configuration ---
#st.set_page_config(layout="wide", page_title="e-MCM App - GST Audit 1")
load_custom_css()

# --- Session State Initialization ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'role' not in st.session_state: st.session_state.role = ""
if 'audit_group_no' not in st.session_state: st.session_state.audit_group_no = None
if 'ag_current_extracted_data' not in st.session_state: st.session_state.ag_current_extracted_data = []
if 'ag_pdf_drive_url' not in st.session_state: st.session_state.ag_pdf_drive_url = None
if 'ag_validation_errors' not in st.session_state: st.session_state.ag_validation_errors = []
if 'ag_editor_data' not in st.session_state: st.session_state.ag_editor_data = pd.DataFrame() # Requires import pandas as pd in this file or pass DF correctly
if 'ag_current_mcm_key' not in st.session_state: st.session_state.ag_current_mcm_key = None
if 'ag_current_uploaded_file_name' not in st.session_state: st.session_state.ag_current_uploaded_file_name = None
# For Drive structure
if 'master_drive_folder_id' not in st.session_state: st.session_state.master_drive_folder_id = None
if 'mcm_periods_drive_file_id' not in st.session_state: st.session_state.mcm_periods_drive_file_id = None
if 'drive_structure_initialized' not in st.session_state: st.session_state.drive_structure_initialized = False

# --- Main App Logic ---
if not st.session_state.logged_in:
    login_page()
else:
    # Initialize Google Services if not already done
    if 'drive_service' not in st.session_state or 'sheets_service' not in st.session_state or \
            st.session_state.drive_service is None or st.session_state.sheets_service is None:
        with st.spinner("Initializing Google Services..."):
            st.session_state.drive_service, st.session_state.sheets_service = get_google_services()
            if st.session_state.drive_service and st.session_state.sheets_service:
                st.success("Google Services Initialized.")
                st.session_state.drive_structure_initialized = False # Trigger re-init of Drive structure
                st.rerun()
            # Error messages are handled by get_google_services()

    # Proceed only if Google services are available
    if st.session_state.drive_service and st.session_state.sheets_service:
        # Initialize Drive Structure if not already done
        if not st.session_state.get('drive_structure_initialized'):
            with st.spinner(
                    f"Initializing application folder structure on Google Drive ('{MASTER_DRIVE_FOLDER_NAME}')..."):
                if initialize_drive_structure(st.session_state.drive_service):
                    st.session_state.drive_structure_initialized = True
                    st.rerun()  # Rerun to ensure dashboards load with correct IDs
                else:
                    st.error(
                        f"Failed to initialize Google Drive structure for '{MASTER_DRIVE_FOLDER_NAME}'. Application cannot proceed safely.")
                    if st.button("Logout", key="fail_logout_drive_init"):
                        st.session_state.logged_in = False; st.rerun()
                    st.stop()

        # If drive structure is initialized, route to the appropriate dashboard
        if st.session_state.get('drive_structure_initialized'):
            if st.session_state.role == "PCO":
                pco_dashboard(st.session_state.drive_service, st.session_state.sheets_service)
            elif st.session_state.role == "AuditGroup":
                # For Audit Group, ensure pandas is imported if ag_editor_data is initialized as pd.DataFrame here.
                # It's better to initialize it as an empty list/dict and let the audit_group_dashboard handle DataFrame creation if needed.
                # Or ensure pandas is imported in this main app.py file.
                import pandas as pd # Added for ag_editor_data initialization
                audit_group_dashboard(st.session_state.drive_service, st.session_state.sheets_service)
            else:
                st.error("Unknown user role. Please login again.")
                st.session_state.logged_in = False
                st.rerun()

    elif st.session_state.logged_in: # Logged in but services failed to initialize
        st.warning("Google services are not available. Please check configuration and network. Try logging out and back in.")
        if st.button("Logout", key="main_logout_gerror_sa_alt"):
            st.session_state.logged_in = False; st.rerun()

# You might want to add a check for GEMINI_API_KEY in st.secrets at the start of app.py
# if "GEMINI_API_KEY" not in st.secrets:
#     st.error("CRITICAL: 'GEMINI_API_KEY' not found in Streamlit Secrets. AI features will fail.")
