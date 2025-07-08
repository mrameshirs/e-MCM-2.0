# app.py
import streamlit as st
import pandas as pd

# Set page configuration once at the top
st.set_page_config(layout="wide", page_title="e-MCM App - GST Audit 1")

# --- Custom Module Imports ---
from config import MASTER_DRIVE_FOLDER_NAME
from css_styles import load_custom_css
from google_utils import (
    get_google_services, 
    initialize_drive_structure, 
    find_drive_item_by_name, 
    find_or_create_log_sheet, 
    log_activity
)
from ui_login import login_page
from ui_pco import pco_dashboard
from ui_audit_group import audit_group_dashboard
from ui_smart_audit_tracker import smart_audit_tracker_dashboard, audit_group_tracker_view

# Load custom CSS styles
load_custom_css()

# --- Session State Initialization ---
def initialize_session_state():
    """Initializes all required session state variables."""
    states = {
        'logged_in': False,
        'username': "",
        'role': "",
        'audit_group_no': None,
        'ag_current_extracted_data': [],
        'ag_pdf_drive_url': None,
        'ag_validation_errors': [],
        'ag_editor_data': pd.DataFrame(),
        'ag_current_mcm_key': None,
        'ag_current_uploaded_file_name': None,
        'master_drive_folder_id': None,
        'mcm_periods_drive_file_id': None,
        'drive_structure_initialized': False,
        'login_event_logged': False,
        'log_sheet_id': None,
        'app_mode': "e-mcm"  # Default mode: 'e-mcm' or 'smart_audit_tracker'
    }
    for key, value in states.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# --- Main Application Logic ---
if not st.session_state.logged_in:
    login_page()
else:
    # Initialize Google Services if they haven't been already
    if 'drive_service' not in st.session_state or 'sheets_service' not in st.session_state or \
            st.session_state.drive_service is None or st.session_state.sheets_service is None:
        with st.spinner("Initializing Google Services..."):
            st.session_state.drive_service, st.session_state.sheets_service = get_google_services()
            if st.session_state.drive_service and st.session_state.sheets_service:
                st.session_state.drive_structure_initialized = False  # Trigger re-init of Drive structure
                st.rerun()
    # Proceed only if Google services are available
    if st.session_state.drive_service and st.session_state.sheets_service:

        # --- Drive Structure and Log Initialization (Combined) ---
        if not st.session_state.get('drive_structure_initialized'):
            with st.spinner(f"Verifying application structure in Google Drive..."):
                if initialize_drive_structure(st.session_state.drive_service, st.session_state.sheets_service):
                    st.session_state.drive_structure_initialized = True
                    # Log activity *after* structure is confirmed
                    if not st.session_state.get('login_event_logged'):
                        log_sheet_id = st.session_state.get('log_sheet_id')
                        if log_sheet_id:
                           log_activity(st.session_state.sheets_service, log_sheet_id, st.session_state.username, st.session_state.role)
                           st.session_state.login_event_logged = True
                    st.rerun()
                else:
                    st.error("Failed to initialize Google Drive structure. Application cannot proceed.")
                    st.stop()
    # # Proceed only if Google services are available
    # if st.session_state.drive_service and st.session_state.sheets_service:
    #     # --- Activity Logging Logic ---
    #     if not st.session_state.get('login_event_logged'):
    #         if not st.session_state.get('master_drive_folder_id'):
    #             master_id = find_drive_item_by_name(st.session_state.drive_service, MASTER_DRIVE_FOLDER_NAME, 'application/vnd.google-apps.folder')
    #             if master_id:
    #                 st.session_state.master_drive_folder_id = master_id
            
    #         master_folder_id = st.session_state.get('master_drive_folder_id')
    #         if master_folder_id:
    #             log_sheet_id = find_or_create_log_sheet(st.session_state.drive_service, st.session_state.sheets_service, master_folder_id)
    #             if log_sheet_id and log_activity(st.session_state.sheets_service, log_sheet_id, st.session_state.username, st.session_state.role):
    #                 st.session_state.login_event_logged = True

    #     # --- Drive Structure Initialization ---
    #     if not st.session_state.get('drive_structure_initialized'):
    #         with st.spinner(f"Initializing application folder structure on Google Drive ('{MASTER_DRIVE_FOLDER_NAME}')..."):
    #             if initialize_drive_structure(st.session_state.drive_service):
    #                 st.session_state.drive_structure_initialized = True
    #                 st.rerun()
    #             else:
    #                 st.error(f"Failed to initialize Google Drive structure for '{MASTER_DRIVE_FOLDER_NAME}'. Application cannot proceed.")
    #                 if st.button("Logout", key="fail_logout_drive_init"):
    #                     st.session_state.logged_in = False
    #                     st.rerun()
    #                 st.stop()

        # --- View Routing Logic based on App Mode and Role ---
        if st.session_state.get('drive_structure_initialized'):
            drive_service = st.session_state.drive_service
            sheets_service = st.session_state.sheets_service
            
            if st.session_state.app_mode == "smart_audit_tracker":
                if st.session_state.role == "PCO":
                    smart_audit_tracker_dashboard(drive_service, sheets_service)
                elif st.session_state.role == "AuditGroup":
                    audit_group_tracker_view(drive_service, sheets_service)
            else:  # Default to "e-mcm" mode
                if st.session_state.role == "PCO":
                    pco_dashboard(drive_service, sheets_service)
                elif st.session_state.role == "AuditGroup":
                    audit_group_dashboard(drive_service, sheets_service)
                else:
                    st.error("Unknown user role. Please login again.")
                    st.session_state.logged_in = False
                    st.rerun()

    elif st.session_state.logged_in:  # Logged in but services failed to initialize
        st.warning("Google services are not available. Please check configuration and network. Try logging out and back in.")
        if st.button("Logout", key="main_logout_gerror_sa_alt"):
            st.session_state.logged_in = False
            st.rerun()
            # # app.py (Refactored)
# import streamlit as st
# import pandas as pd
# st.set_page_config(layout="wide", page_title="e-MCM App - GST Audit 1")

# # --- Custom Module Imports ---
# from config import MASTER_DRIVE_FOLDER_NAME # Example of using config
# from css_styles import load_custom_css
# from google_utils import get_google_services, initialize_drive_structure, find_drive_item_by_name, find_or_create_log_sheet, log_activity
# from ui_login import login_page
# from ui_pco import pco_dashboard
# from ui_audit_group import audit_group_dashboard
# from ui_smart_audit_tracker import smart_audit_tracker_dashboard, audit_group_tracker_view # IMPORT NEW TRACKER UI

# # --- Streamlit Page Configuration ---
# #st.set_page_config(layout="wide", page_title="e-MCM App - GST Audit 1")
# load_custom_css()

# # --- Session State Initialization ---
# if 'logged_in' not in st.session_state: st.session_state.logged_in = False
# if 'username' not in st.session_state: st.session_state.username = ""
# if 'role' not in st.session_state: st.session_state.role = ""
# if 'audit_group_no' not in st.session_state: st.session_state.audit_group_no = None
# if 'ag_current_extracted_data' not in st.session_state: st.session_state.ag_current_extracted_data = []
# if 'ag_pdf_drive_url' not in st.session_state: st.session_state.ag_pdf_drive_url = None
# if 'ag_validation_errors' not in st.session_state: st.session_state.ag_validation_errors = []
# if 'ag_editor_data' not in st.session_state: st.session_state.ag_editor_data = pd.DataFrame() # Requires import pandas as pd in this file or pass DF correctly
# if 'ag_current_mcm_key' not in st.session_state: st.session_state.ag_current_mcm_key = None
# if 'ag_current_uploaded_file_name' not in st.session_state: st.session_state.ag_current_uploaded_file_name = None
# # For Drive structure
# if 'master_drive_folder_id' not in st.session_state: st.session_state.master_drive_folder_id = None
# if 'mcm_periods_drive_file_id' not in st.session_state: st.session_state.mcm_periods_drive_file_id = None
# if 'drive_structure_initialized' not in st.session_state: st.session_state.drive_structure_initialized = False
# if 'login_event_logged' not in st.session_state: st.session_state.login_event_logged = False
# if 'log_sheet_id' not in st.session_state: st.session_state.log_sheet_id = None
# if 'app_mode' not in st.session_state: st.session_state.app_mode = "e-mcm" # ADD THIS: 'e-mcm' or 'smart_audit_tracker'

# # --- Main App Logic ---
# if not st.session_state.logged_in:
#     login_page()
# else:
#     # Initialize Google Services if not already done
#     if 'drive_service' not in st.session_state or 'sheets_service' not in st.session_state or \
#             st.session_state.drive_service is None or st.session_state.sheets_service is None:
#         with st.spinner("Initializing Google Services..."):
#             st.session_state.drive_service, st.session_state.sheets_service = get_google_services()
#             if st.session_state.drive_service and st.session_state.sheets_service:
#                 st.success("Google Services Initialized.")
#                 st.session_state.drive_structure_initialized = False # Trigger re-init of Drive structure
#                 st.rerun()
#             # Error messages are handled by get_google_services()

#     # Proceed only if Google services are available
#     if st.session_state.drive_service and st.session_state.sheets_service:
#         # --- NEW: ACTIVITY LOGGING LOGIC ---
#         # This runs once per login after services are confirmed to be available.
#         if not st.session_state.get('login_event_logged'):
#             # The master folder ID is needed to find/create the log sheet in the correct location.
#             # We ensure it's available before proceeding with logging.
#             if not st.session_state.get('master_drive_folder_id'):
#                  master_id = find_drive_item_by_name(st.session_state.drive_service, MASTER_DRIVE_FOLDER_NAME, 'application/vnd.google-apps.folder')
#                  if master_id:
#                     st.session_state.master_drive_folder_id = master_id

#             master_folder_id = st.session_state.get('master_drive_folder_id')
#             if master_folder_id:
#                 log_sheet_id = find_or_create_log_sheet(st.session_state.drive_service, st.session_state.sheets_service, master_folder_id)
#                 if log_sheet_id:
#                     if log_activity(st.session_state.sheets_service, log_sheet_id, st.session_state.username, st.session_state.role):
#                         st.session_state.login_event_logged = True # Mark as logged to prevent re-logging
#             # If the master folder isn't found here, the full drive initialization will handle the error message.
#         # --- END OF LOGGING LOGIC ---
#         # Initialize Drive Structure if not already done
#         if not st.session_state.get('drive_structure_initialized'):
#             with st.spinner(
#                     f"Initializing application folder structure on Google Drive ('{MASTER_DRIVE_FOLDER_NAME}')..."):
#                 if initialize_drive_structure(st.session_state.drive_service):
#                     st.session_state.drive_structure_initialized = True
#                     st.rerun()  # Rerun to ensure dashboards load with correct IDs
#                 else:
#                     st.error(
#                         f"Failed to initialize Google Drive structure for '{MASTER_DRIVE_FOLDER_NAME}'. Application cannot proceed safely.")
#                     if st.button("Logout", key="fail_logout_drive_init"):
#                         st.session_state.logged_in = False; st.rerun()
#                     st.stop()

#         # If drive structure is initialized, route to the appropriate dashboard
#         if st.session_state.get('drive_structure_initialized'):
#             if st.session_state.role == "PCO":
#                 pco_dashboard(st.session_state.drive_service, st.session_state.sheets_service)
#             elif st.session_state.role == "AuditGroup":
#                 # For Audit Group, ensure pandas is imported if ag_editor_data is initialized as pd.DataFrame here.
#                 # It's better to initialize it as an empty list/dict and let the audit_group_dashboard handle DataFrame creation if needed.
#                 # Or ensure pandas is imported in this main app.py file.
#                 import pandas as pd # Added for ag_editor_data initialization
#                 audit_group_dashboard(st.session_state.drive_service, st.session_state.sheets_service)
#             else:
#                 st.error("Unknown user role. Please login again.")
#                 st.session_state.logged_in = False
#                 st.rerun()

#     elif st.session_state.logged_in: # Logged in but services failed to initialize
#         st.warning("Google services are not available. Please check configuration and network. Try logging out and back in.")
#         if st.button("Logout", key="main_logout_gerror_sa_alt"):
#             st.session_state.logged_in = False; st.rerun()

# # You might want to add a check for GEMINI_API_KEY in st.secrets at the start of app.py
# # if "GEMINI_API_KEY" not in st.secrets:
# #     st.error("CRITICAL: 'GEMINI_API_KEY' not found in Streamlit Secrets. AI features will fail.")
