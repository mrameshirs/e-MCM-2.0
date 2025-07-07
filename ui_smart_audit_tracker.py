# ui_smart_audit_tracker.py
import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import re
import datetime
from io import BytesIO
import time

# Assuming google_utils.py and config.py are correctly set up
from google_utils import (
    read_from_spreadsheet,
    find_or_create_spreadsheet,
    update_spreadsheet_from_df,
    upload_to_drive,
    find_drive_item_by_name
)
from config import SMART_AUDIT_MASTER_DB_SHEET_NAME, MASTER_DRIVE_FOLDER_NAME

# --- Helper Functions ---

def generate_excel_template():
    """Generates an in-memory Excel file template for download."""
    template_df = pd.DataFrame({
        "GSTIN": ["12ABCDE1234F5GH"],
        "Trade Name": ["Sample Trade Name"],
        "Category": ["Large"],
        "Allocated Audit Group Number": [15],
        "Allocated Circle": [7]
    })
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        template_df.to_excel(writer, index=False, sheet_name='Allocations')
    processed_data = output.getvalue()
    return processed_data

def validate_gstin(gstin):
    """Validates the GSTIN format."""
    if not gstin or not isinstance(gstin, str):
        return False
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    return re.match(pattern, gstin) is not None

def get_current_financial_year():
    """Gets the current financial year based on the system date."""
    now = datetime.datetime.now()
    if now.month >= 4:
        return f"{now.year}-{now.year + 1}"
    else:
        return f"{now.year - 1}-{now.year}"

# --- Main Dashboard Function ---

def smart_audit_tracker_dashboard(drive_service, sheets_service):
    """
    Displays the main dashboard for the Smart Audit Tracker module.
    This view is primarily for the Planning & Coordination Officer.
    """
    if st.button("⬅️ Back to e-MCM Dashboard", key="back_to_mcm_from_tracker"):
        st.session_state.app_mode = "e-mcm"
        st.rerun()

    st.markdown("<h2 class='page-main-title'>Smart Audit Tracker</h2>", unsafe_allow_html=True)
    st.markdown("<p class='page-app-subtitle'>Manage the complete lifecycle of audit assignments.</p>", unsafe_allow_html=True)

    # --- Initialize Master DB Sheet ---
    if 'master_db_sheet_id' not in st.session_state or not st.session_state.master_db_sheet_id:
        with st.spinner("Initializing Smart Audit Master Database..."):
            master_folder_id = st.session_state.get('master_drive_folder_id')
            if master_folder_id:
                sheet_id = find_or_create_spreadsheet(
                    drive_service, sheets_service, SMART_AUDIT_MASTER_DB_SHEET_NAME, master_folder_id
                )
                st.session_state.master_db_sheet_id = sheet_id
            else:
                st.error("Master Drive Folder not found. Cannot initialize database.")
                st.stop()
    
    master_db_sheet_id = st.session_state.get('master_db_sheet_id')

    selected_tab = option_menu(
        menu_title=None,
        options=["Allocate Units to Groups", "Edit/Reassign Units", "Audit Lifecycle", "Commissioner View"],
        icons=["person-plus-fill", "pencil-square", "diagram-3-fill", "person-video3"],
        menu_icon="cast", default_index=0, orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#f0f2f6"},
            "icon": {"color": "#dc3545", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#f8d7da"},
            "nav-link-selected": {"background-color": "#dc3545", "color": "white"},
        }
    )

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    if selected_tab == "Allocate Units to Groups":
        render_allocate_units_tab(drive_service, sheets_service, master_db_sheet_id)
    elif selected_tab == "Edit/Reassign Units":
        render_reassign_units_tab(drive_service, sheets_service, master_db_sheet_id)
    # ... other tabs
    
    st.markdown("</div>", unsafe_allow_html=True)

# --- Tab Rendering Functions ---

def render_allocate_units_tab(drive_service, sheets_service, db_sheet_id):
    """Renders the UI for allocating units."""
    st.markdown("<h3>Allocate Units to Groups</h3>", unsafe_allow_html=True)
    
    # --- Guidance and Template Download ---
    c1, c2 = st.columns([3, 1])
    with c1:
        st.info("Upload an Excel sheet to allocate GSTIN units to audit groups and circles. Ensure the sheet follows the provided format.")
    with c2:
        st.download_button(
            label="📥 Download Sample Excel",
            data=generate_excel_template(),
            file_name="allocation_template.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )

    with st.form("allocation_form", clear_on_submit=True):
        # --- Form Fields ---
        current_fy = get_current_financial_year()
        fy_options = [f"{y}-{y+1}" for y in range(2023, datetime.datetime.now().year + 2)]
        
        col1, col2 = st.columns(2)
        with col1:
            financial_year = st.selectbox("Financial Year", options=fy_options, index=fy_options.index(current_fy))
            allocated_date = st.date_input("Office Order Allocation Date", value=datetime.date.today())
        with col2:
            uploaded_excel = st.file_uploader("Upload Excel Allocation File (.xlsx)", type=["xlsx"])
            office_order_pdf = st.file_uploader("Upload Office Order PDF", type=["pdf"])

        submitted = st.form_submit_button("Validate and Allocate Units", type="primary", use_container_width=True)

    if submitted:
        # --- Form Submission Logic ---
        if not uploaded_excel:
            st.error("Please upload the Excel allocation file.")
        elif not office_order_pdf:
            st.error("Please upload the office order PDF.")
        elif not allocated_date:
            st.error("Please select the allocation date.")
        else:
            process_allocation_upload(drive_service, sheets_service, db_sheet_id, uploaded_excel, office_order_pdf, financial_year, allocated_date)

    # --- Display Previous Allocations ---
    st.markdown("---")
    st.markdown("<h4>Previously Allocated Batches</h4>", unsafe_allow_html=True)
    with st.spinner("Loading allocation history..."):
        master_df = read_from_spreadsheet(sheets_service, db_sheet_id)
        if master_df is not None and not master_df.empty:
            # Display summary of allocations
            alloc_summary = master_df.groupby(['Financial Year', 'Allocated Date', 'Office Order PDF Path', 'Uploaded Date']).size().reset_index(name='No of GSTINs Allocated')
            alloc_summary = alloc_summary.sort_values(by="Uploaded Date", ascending=False)
            alloc_summary['Office Order Link'] = alloc_summary['Office Order PDF Path'].apply(lambda x: f"[View PDF]({x})" if x else "No Link")
            
            st.dataframe(alloc_summary[[
                'Financial Year', 'No of GSTINs Allocated', 'Allocated Date', 'Uploaded Date', 'Office Order Link'
            ]], use_container_width=True, hide_index=True)
        else:
            st.info("No allocation history found.")


def process_allocation_upload(drive_service, sheets_service, db_sheet_id, excel_file, pdf_file, fin_year, alloc_date):
    """Validates and processes the uploaded allocation files."""
    with st.spinner("Processing file... This may take a moment."):
        try:
            df = pd.read_excel(excel_file)
            master_df = read_from_spreadsheet(sheets_service, db_sheet_id)
            if master_df is None: # Handle case where sheet is new/unreadable
                master_df = pd.DataFrame()

        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
            return

        errors = []
        valid_rows = []
        required_cols = ["GSTIN", "Trade Name", "Category", "Allocated Circle"]
        
        # --- Validation Loop ---
        for col in required_cols:
            if col not in df.columns:
                errors.append(f"Missing mandatory column in Excel: '{col}'")
        
        if errors:
            for error in errors: st.error(error)
            return

        for index, row in df.iterrows():
            gstin = str(row.get("GSTIN", "")).strip()
            # Validation checks
            if not validate_gstin(gstin):
                errors.append(f"Row {index + 2}: Invalid GSTIN format for '{gstin}'.")
                continue
            if not row.get("Trade Name"):
                errors.append(f"Row {index + 2}: 'Trade Name' cannot be empty.")
            if row.get("Category") not in ["Large", "Medium", "Small"]:
                errors.append(f"Row {index + 2}: 'Category' must be one of 'Large', 'Medium', 'Small'.")
            
            try:
                circle = int(row.get("Allocated Circle"))
                if not (1 <= circle <= 10):
                    errors.append(f"Row {index + 2}: 'Allocated Circle' must be an integer between 1 and 10.")
            except (ValueError, TypeError):
                errors.append(f"Row {index + 2}: 'Allocated Circle' must be a valid integer.")

            if 'Allocated Audit Group Number' in row and pd.notna(row['Allocated Audit Group Number']):
                try:
                    group = int(row['Allocated Audit Group Number'])
                    if not (1 <= group <= 30):
                        errors.append(f"Row {index + 2}: 'Allocated Audit Group Number' must be an integer between 1 and 30.")
                except (ValueError, TypeError):
                    errors.append(f"Row {index + 2}: 'Allocated Audit Group Number' must be a valid integer.")

            # Duplicate check in master DB
            if not master_df.empty and gstin in master_df[master_df['Financial Year'] == fin_year]['GSTIN'].values:
                 errors.append(f"Row {index + 2}: GSTIN '{gstin}' already exists for {fin_year}. Use the Reassign option to update.")
                 continue
            
            if not errors: # If no errors for this row so far
                valid_rows.append(row)

        if errors:
            st.error("Validation failed. Please correct the errors below and re-upload:")
            for error in errors:
                st.write(error)
            return
        
        # --- Upload PDF and Save Data ---
        st.info("Validation successful. Uploading office order and saving data...")
        master_folder_id = st.session_state.get('master_drive_folder_id')
        pdf_filename = f"OfficeOrder_{fin_year.replace('-', '_')}_{int(time.time())}.pdf"
        pdf_id, pdf_url = upload_to_drive(drive_service, pdf_file.getvalue(), master_folder_id, pdf_filename)

        if not pdf_url:
            st.error("Failed to upload Office Order PDF. Aborting data save.")
            return

        new_data_df = pd.DataFrame(valid_rows)
        new_data_df['Financial Year'] = fin_year
        new_data_df['Allocated Date'] = alloc_date.strftime("%Y-%m-%d")
        new_data_df['Uploaded Date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_data_df['Office Order PDF Path'] = pdf_url
        new_data_df['Reassigned Flag'] = False
        new_data_df['Old Group Number'] = None
        new_data_df['Old Circle Number'] = None

        # Combine with master and save
        final_df = pd.concat([master_df, new_data_df], ignore_index=True)
        success = update_spreadsheet_from_df(sheets_service, db_sheet_id, final_df)

        if success:
            st.success("Excel data validated and saved successfully!")
            st.balloons()
        else:
            st.error("Failed to save data to the master database.")


def render_reassign_units_tab(drive_service, sheets_service, db_sheet_id):
    """Renders the UI for editing and reassigning units."""
    st.markdown("<h3>Edit/Reassign Units</h3>", unsafe_allow_html=True)
    st.info("Search for a GSTIN to edit or reassign its audit group and circle. Ensure you upload the reallocation office order PDF.")

    # --- Search Form ---
    with st.form("search_gstin_form"):
        current_fy = get_current_financial_year()
        fy_options = [f"{y}-{y+1}" for y in range(2023, datetime.datetime.now().year + 2)]
        
        col1, col2 = st.columns([2,1])
        with col1:
            search_fy = st.selectbox("Financial Year", options=fy_options, index=fy_options.index(current_fy), key="reassign_fy")
        with col2:
            search_gstin = st.text_input("Enter GSTIN to Search")
        
        search_button = st.form_submit_button("Search GSTIN", use_container_width=True)

    if search_button and search_gstin:
        master_df = read_from_spreadsheet(sheets_service, db_sheet_id)
        if master_df is not None and not master_df.empty:
            result_df = master_df[(master_df['GSTIN'] == search_gstin.strip()) & (master_df['Financial Year'] == search_fy)]
            if not result_df.empty:
                st.session_state.found_gstin_details = result_df.iloc[0].to_dict()
                st.session_state.show_reassign_form = True
            else:
                st.error(f"GSTIN '{search_gstin}' not found for Financial Year {search_fy}.")
                st.session_state.show_reassign_form = False
        else:
            st.error("Master database is empty or could not be read.")
            st.session_state.show_reassign_form = False

    # --- Reassignment Form (if GSTIN found) ---
    if st.session_state.get('show_reassign_form', False):
        details = st.session_state.found_gstin_details
        st.markdown("---")
        st.write(f"**Editing Details for GSTIN:** `{details['GSTIN']}`")
        
        # Display existing details
        st.write(f"**Trade Name:** {details['Trade Name']} | **Category:** {details['Category']}")
        st.write(f"**Current Group:** {details.get('Allocated Audit Group Number', 'N/A')} | **Current Circle:** {details['Allocated Circle']}")
        st.write(f"**Original Allocation Date:** {details['Allocated Date']}")
        if details.get('Office Order PDF Path'):
            st.markdown(f"**Original Office Order:** [View PDF]({details['Office Order PDF Path']})", unsafe_allow_html=True)

        with st.form("reassignment_form"):
            st.markdown("<h5>Enter New Allocation Details:</h5>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                new_group = st.number_input("New Allocated Audit Group Number", min_value=1, max_value=30, step=1, value=int(details.get('Allocated Audit Group Number', 1) or 1))
            with col2:
                new_circle = st.number_input("New Allocated Circle", min_value=1, max_value=10, step=1, value=int(details.get('Allocated Circle', 1) or 1))

            realloc_date = st.date_input("Reallocation Office Order Date", value=datetime.date.today())
            realloc_pdf = st.file_uploader("Upload Reallocation Office Order PDF", type=["pdf"])

            reassign_submit = st.form_submit_button("Confirm Reassignment", type="primary", use_container_width=True)

            if reassign_submit:
                if not realloc_pdf:
                    st.error("Please upload the reallocation office order PDF.")
                else:
                    process_reassignment(drive_service, sheets_service, db_sheet_id, details, new_group, new_circle, realloc_date, realloc_pdf)
    
    # --- Display Reassignment History ---
    st.markdown("---")
    st.markdown("<h4>Reassigned Units History</h4>", unsafe_allow_html=True)
    with st.spinner("Loading reassignment history..."):
        master_df = read_from_spreadsheet(sheets_service, db_sheet_id)
        if master_df is not None and not master_df.empty and 'Reassigned Flag' in master_df.columns:
            reassigned_df = master_df[master_df['Reassigned Flag'] == True].copy()
            if not reassigned_df.empty:
                reassigned_df['Reallocation Office Order PDF Link'] = reassigned_df['Office Order PDF Path'].apply(lambda x: f"[View PDF]({x})" if x else "No Link")
                # Rename columns for display
                reassigned_df.rename(columns={
                    'Allocated Audit Group Number': 'New Group Number',
                    'Allocated Circle': 'New Circle Number',
                    'Allocated Date': 'Reallocation Date'
                }, inplace=True)

                st.dataframe(reassigned_df[[
                    'Financial Year', 'GSTIN', 'Trade Name', 'Old Group Number', 'Old Circle Number',
                    'New Group Number', 'New Circle Number', 'Reallocation Date', 'Reallocation Office Order PDF Link'
                ]], use_container_width=True, hide_index=True)
            else:
                st.info("No reassignment history found.")
        else:
            st.info("No reassignment history found.")


def process_reassignment(drive_service, sheets_service, db_sheet_id, old_details, new_group, new_circle, realloc_date, realloc_pdf):
    """Processes the reassignment submission."""
    with st.spinner("Processing reassignment..."):
        master_df = read_from_spreadsheet(sheets_service, db_sheet_id)
        if master_df is None:
            st.error("Could not read master database. Aborting.")
            return

        # Find the index of the row to update
        idx = master_df[(master_df['GSTIN'] == old_details['GSTIN']) & (master_df['Financial Year'] == old_details['Financial Year'])].index
        if idx.empty:
            st.error("Could not find the original record to update. It may have been modified.")
            return
        
        record_index = idx[0]

        # Upload new PDF
        master_folder_id = st.session_state.get('master_drive_folder_id')
        pdf_filename = f"ReallocOrder_{old_details['Financial Year'].replace('-', '_')}_{old_details['GSTIN']}_{int(time.time())}.pdf"
        pdf_id, pdf_url = upload_to_drive(drive_service, realloc_pdf.getvalue(), master_folder_id, pdf_filename)

        if not pdf_url:
            st.error("Failed to upload Reallocation Office Order PDF. Aborting update.")
            return

        # Update the DataFrame row
        master_df.loc[record_index, 'Reassigned Flag'] = True
        master_df.loc[record_index, 'Old Group Number'] = old_details.get('Allocated Audit Group Number')
        master_df.loc[record_index, 'Old Circle Number'] = old_details.get('Allocated Circle')
        master_df.loc[record_index, 'Allocated Audit Group Number'] = new_group
        master_df.loc[record_index, 'Allocated Circle'] = new_circle
        master_df.loc[record_index, 'Allocated Date'] = realloc_date.strftime("%Y-%m-%d")
        master_df.loc[record_index, 'Office Order PDF Path'] = pdf_url

        # Save back to sheet
        success = update_spreadsheet_from_df(sheets_service, db_sheet_id, master_df)

        if success:
            st.success(f"GSTIN '{old_details['GSTIN']}' reassigned successfully!")
            st.session_state.show_reassign_form = False
            st.balloons()
            time.sleep(1)
            st.rerun()
        else:
            st.error("Failed to save the updated record to the master database.")

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
# # ui_smart_audit_tracker.py
# import streamlit as st
# from streamlit_option_menu import option_menu

# def smart_audit_tracker_dashboard(drive_service, sheets_service):
#     """
#     Displays the main dashboard for the Smart Audit Tracker module.
#     This view is primarily for the Planning & Coordination Officer.
#     """
#     # --- Back Button ---
#     if st.button("⬅️ Back to e-MCM Dashboard", key="back_to_mcm_from_tracker"):
#         st.session_state.app_mode = "e-mcm"
#         st.rerun()

#     st.markdown("<h2 class='page-main-title'>Smart Audit Tracker</h2>", unsafe_allow_html=True)
#     st.markdown("<p class='page-app-subtitle'>Manage the complete lifecycle of audit assignments.</p>", unsafe_allow_html=True)

#     selected_tab = option_menu(
#         menu_title=None,
#         options=["Allocate Units to Audit Group", "Re-assign/Edit Allocation", "See Audit Lifecycle", "Commissioner Dashboard"],
#         icons=["person-plus-fill", "pencil-square", "diagram-3-fill", "person-video3"],
#         menu_icon="cast",
#         default_index=0,
#         orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#f0f2f6"},
#             "icon": {"color": "#dc3545", "font-size": "20px"},
#             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#f8d7da"},
#             "nav-link-selected": {"background-color": "#dc3545", "color": "white"},
#         }
#     )

#     st.markdown("<div class='card'>", unsafe_allow_html=True)
#     if selected_tab == "Allocate Units to Audit Group":
#         st.header("Allocate New Units for Audit")
#         st.info("This section will contain the interface to assign new taxpayers/units to specific audit groups for upcoming audit cycles.")
#         # Placeholder for allocation UI
#         st.selectbox("Select Audit Group", options=[f"Group {i}" for i in range(1, 31)])
#         st.text_input("Enter GSTIN of unit to allocate")
#         st.date_input("Allocation Date")
#         st.button("Allocate Unit", type="primary")

#     elif selected_tab == "Re-assign/Edit Allocation":
#         st.header("Manage Existing Allocations")
#         st.info("This section will allow for viewing, editing, or re-assigning units that have already been allocated.")
#         # Placeholder for management UI
#         st.text_input("Search by GSTIN or Audit Group to find allocation")
#         st.button("Search")

#     elif selected_tab == "See Audit Lifecycle":
#         st.header("Track Audit Progress Lifecycle")
#         st.info("This section will provide a comprehensive view of the audit status for each allocated unit, from assignment to completion.")
#         # Placeholder for lifecycle tracking UI
#         st.selectbox("Select Audit Group to view lifecycle", options=[f"Group {i}" for i in range(1, 31)])

#     elif selected_tab == "Commissioner Dashboard":
#         st.header("Commissioner's Dashboard")
#         st.info("This section will display high-level summaries, statistics, and visualizations for executive oversight.")
#         # Placeholder for high-level dashboard
#         st.metric("Total Units Under Audit", "150")
#         st.metric("Audits Completed This Month", "25")
#         st.metric("Revenue Detected (MTD)", "₹1.2 Cr")

#     st.markdown("</div>", unsafe_allow_html=True)


# def audit_group_tracker_view(drive_service, sheets_service):
#     """
#     Displays the Smart Audit Tracker view for an Audit Group user.
#     """
#     if st.button("⬅️ Back to e-MCM Dashboard", key="back_to_mcm_from_ag_tracker"):
#         st.session_state.app_mode = "e-mcm"
#         st.rerun()

#     st.markdown("<h2 class='page-main-title'>My Smart Audit Tracker</h2>", unsafe_allow_html=True)
#     st.info("This section will show your assigned units, deadlines, and allow you to update the status of your audits.")
#     # Placeholder for Audit Group's view
#     st.write("### My Assigned Units")
#     st.dataframe({
#         "GSTIN": ["27ABCDE1234F1Z5", "27BCDEF2345F2Z6"],
#         "Trade Name": ["ABC Enterprises", "XYZ Corporation"],
#         "Allocation Date": ["2025-07-01", "2025-07-03"],
#         "Status": ["Pending Acceptance", "In Progress"]
#     }, use_container_width=True)
