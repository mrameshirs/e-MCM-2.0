# ui_pco_reports.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Utility imports
from google_utils import find_or_create_log_sheet
from reports_utils import generate_login_report, get_log_data

def pco_reports_dashboard(drive_service, sheets_service):
    """
    Dashboard for the Planning & Coordination Officer to view various reports.
    """
    st.markdown("<h3>Reports Dashboard</h3>", unsafe_allow_html=True)

    # The master folder ID is required to find or create the log sheet within it.
    master_folder_id = st.session_state.get('master_drive_folder_id')
    if not master_folder_id:
        st.error("Master Drive Folder ID is not initialized. Cannot access logs.")
        st.stop()
        
    log_sheet_id = find_or_create_log_sheet(drive_service, sheets_service, master_folder_id)
    
    if not log_sheet_id:
        st.error("Could not find or create the application Log Sheet. Reporting is unavailable.")
        st.stop()
    
    report_options = ["Login Activity Report"]
    selected_report = st.selectbox("Select a report to view:", report_options)

    if selected_report == "Login Activity Report":
        st.markdown("<h4>Login Activity Report</h4>", unsafe_allow_html=True)
        st.markdown("This report shows the number of times each user has logged in within a selected period.")

        days_option = st.selectbox(
            "Select time period (in days):",
            (7, 15, 30, 60, 90),
            index=2 # Default to 30 days
        )

        with st.spinner("Fetching and processing log data..."):
            # Use the cached data fetching function
            log_df = get_log_data(sheets_service, log_sheet_id)
            
            if log_df.empty:
                st.info("No log data has been recorded yet.")
            else:
                report_df = generate_login_report(log_df, days_option)
                if report_df.empty:
                    st.info(f"No login activity was recorded in the last {days_option} days.")
                else:
                    st.write(f"Displaying login counts for the last **{days_option} days**.")
                    st.dataframe(
                        report_df,
                        use_container_width=True,
                        hide_index=True
                    )
