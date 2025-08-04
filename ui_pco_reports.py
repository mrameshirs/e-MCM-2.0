# ui_pco_reports.py
import streamlit as st
import pandas as pd
from reports_utils import get_log_data, generate_login_report
# ui_pco_reports.py
import streamlit as st
from reports_utils import get_log_data, generate_login_report

def pco_reports_dashboard(dbx):
    """
    Dashboard for the PCO to view reports, now using Dropbox.
    """
    st.markdown("<h3>Reports Dashboard</h3>", unsafe_allow_html=True)
    
    if not dbx:
        st.error("Dropbox client is not available. Reporting is unavailable.")
        st.stop()
    
    report_options = ["Login Activity Report"]
    selected_report = st.selectbox("Select a report to view:", report_options)

    if selected_report == "Login Activity Report":
        st.markdown("<h4>Login Activity Report</h4>", unsafe_allow_html=True)
        st.markdown("This report shows the number of times each user has logged in within a selected period.")

        days_option = st.selectbox(
            "Select time period (in days):",
            (7, 15, 30, 60, 90),
            index=2  # Default to 30 days
        )

        with st.spinner("Fetching and processing log data from Dropbox..."):
            # Use the data fetching function adapted for Dropbox
            log_df = get_log_data(dbx)
            
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
