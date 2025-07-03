# ui_smart_audit_tracker.py
import streamlit as st
from streamlit_option_menu import option_menu

def smart_audit_tracker_dashboard(drive_service, sheets_service):
    """
    Displays the main dashboard for the Smart Audit Tracker module.
    This view is primarily for the Planning & Coordination Officer.
    """
    # --- Back Button ---
    if st.button("⬅️ Back to e-MCM Dashboard", key="back_to_mcm_from_tracker"):
        st.session_state.app_mode = "e-mcm"
        st.rerun()

    st.markdown("<h2 class='page-main-title'>Smart Audit Tracker</h2>", unsafe_allow_html=True)
    st.markdown("<p class='page-app-subtitle'>Manage the complete lifecycle of audit assignments.</p>", unsafe_allow_html=True)

    selected_tab = option_menu(
        menu_title=None,
        options=["Allocate Units to Audit Group", "Re-assign/Edit Allocation", "See Audit Lifecycle", "Commissioner Dashboard"],
        icons=["person-plus-fill", "pencil-square", "diagram-3-fill", "person-video3"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#f0f2f6"},
            "icon": {"color": "#dc3545", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#f8d7da"},
            "nav-link-selected": {"background-color": "#dc3545", "color": "white"},
        }
    )

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    if selected_tab == "Allocate Units to Audit Group":
        st.header("Allocate New Units for Audit")
        st.info("This section will contain the interface to assign new taxpayers/units to specific audit groups for upcoming audit cycles.")
        # Placeholder for allocation UI
        st.selectbox("Select Audit Group", options=[f"Group {i}" for i in range(1, 31)])
        st.text_input("Enter GSTIN of unit to allocate")
        st.date_input("Allocation Date")
        st.button("Allocate Unit", type="primary")

    elif selected_tab == "Re-assign/Edit Allocation":
        st.header("Manage Existing Allocations")
        st.info("This section will allow for viewing, editing, or re-assigning units that have already been allocated.")
        # Placeholder for management UI
        st.text_input("Search by GSTIN or Audit Group to find allocation")
        st.button("Search")

    elif selected_tab == "See Audit Lifecycle":
        st.header("Track Audit Progress Lifecycle")
        st.info("This section will provide a comprehensive view of the audit status for each allocated unit, from assignment to completion.")
        # Placeholder for lifecycle tracking UI
        st.selectbox("Select Audit Group to view lifecycle", options=[f"Group {i}" for i in range(1, 31)])

    elif selected_tab == "Commissioner Dashboard":
        st.header("Commissioner's Dashboard")
        st.info("This section will display high-level summaries, statistics, and visualizations for executive oversight.")
        # Placeholder for high-level dashboard
        st.metric("Total Units Under Audit", "150")
        st.metric("Audits Completed This Month", "25")
        st.metric("Revenue Detected (MTD)", "₹1.2 Cr")

    st.markdown("</div>", unsafe_allow_html=True)


def audit_group_tracker_view(drive_service, sheets_service):
    """
    Displays the Smart Audit Tracker view for an Audit Group user.
    """
    if st.button("⬅️ Back to e-MCM Dashboard", key="back_to_mcm_from_ag_tracker"):
        st.session_state.app_mode = "e-mcm"
        st.rerun()

    st.markdown("<h2 class='page-main-title'>My Smart Audit Tracker</h2>", unsafe_allow_html=True)
    st.info("This section will show your assigned units, deadlines, and allow you to update the status of your audits.")
    # Placeholder for Audit Group's view
    st.write("### My Assigned Units")
    st.dataframe({
        "GSTIN": ["27ABCDE1234F1Z5", "27BCDEF2345F2Z6"],
        "Trade Name": ["ABC Enterprises", "XYZ Corporation"],
        "Allocation Date": ["2025-07-01", "2025-07-03"],
        "Status": ["Pending Acceptance", "In Progress"]
    }, use_container_width=True)
