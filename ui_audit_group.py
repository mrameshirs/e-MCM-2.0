# ui_audit_group.py
import streamlit as st
import pandas as pd
import datetime
import math # For math.ceil
from io import BytesIO
import time # Added for potential sleep

# Assuming these utilities are correctly defined and imported
from google_utils import (
    load_mcm_periods, upload_to_drive, append_to_spreadsheet,
    read_from_spreadsheet, delete_spreadsheet_rows # Added missing imports from user's commented code
)
from dar_processor import preprocess_pdf_text
from gemini_utils import get_structured_data_with_gemini
from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
from config import USER_CREDENTIALS, AUDIT_GROUP_NUMBERS # Added AUDIT_GROUP_NUMBERS
from models import ParsedDARReport # Added

from streamlit_option_menu import option_menu # Added from user's commented code


# This should be the order of columns for the data that will eventually go into the Google Sheet
# (excluding derived ones like pdf_url and record_created_date which are added at the end)
SHEET_DATA_COLUMNS_ORDER = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading",
    "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para",
]

# This is the order for displaying in the st.data_editor UI
DISPLAY_COLUMN_ORDER = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "audit_para_number", "audit_para_heading", "status_of_para",
    "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs"
]


def calculate_audit_circle(audit_group_number_val):
    try:
        agn = int(audit_group_number_val)
        if 1 <= agn <= 30:
            return math.ceil(agn / 3.0)
        return None
    except (ValueError, TypeError, AttributeError): # Added AttributeError for None
        return None

def audit_group_dashboard(drive_service, sheets_service):
    st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
                unsafe_allow_html=True)
    mcm_periods = load_mcm_periods(drive_service)
    active_periods = {k: v for k, v in mcm_periods.items() if v.get("active")}

    YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

    # --- Initialize session state if not present (enhanced) ---
    default_ag_states = {
        'ag_current_mcm_key': None,
        'ag_current_uploaded_file_name': None,
        'ag_current_extracted_data': [], # List of dicts from AI
        'ag_editor_data': pd.DataFrame(), # DataFrame for st.data_editor
        'ag_pdf_drive_url': None,
        'ag_validation_errors': [],
        'uploader_key_suffix': 0, # For unique file uploader keys
        'ag_row_to_delete_details': None, # For delete tab
        'ag_show_delete_confirm': False, # For delete tab
        'ag_deletable_map': {} # For delete tab
    }
    for key, value in default_ag_states.items():
        if key not in st.session_state:
            st.session_state[key] = value


    with st.sidebar:
        try:
            st.image("logo.png", width=80)
        except Exception as e:
            st.sidebar.warning(f"Could not load logo.png: {e}")
            st.sidebar.markdown("*(Logo)*")

        st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}",
                    unsafe_allow_html=True)
        if st.button("Logout", key="ag_logout_styled", use_container_width=True):
            keys_to_clear_on_logout = list(default_ag_states.keys()) + \
                                    ['ag_current_mcm_key', 'ag_current_uploaded_file_name', # Explicitly list all to be sure
                                     'drive_structure_initialized'] # from app.py
            for key_to_del in keys_to_clear_on_logout:
                if key_to_del in st.session_state: del st.session_state[key_to_del]
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.audit_group_no = None
            st.rerun()
        st.markdown("---")

    selected_tab = option_menu(
        menu_title=None, options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
        icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace", default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#e9ecef"},
            "icon": {"color": "#28a745", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
            "nav-link-selected": {"background-color": "#28a745", "color": "white"},
        })
    st.markdown("<div class='card'>", unsafe_allow_html=True)

    if selected_tab == "Upload DAR for MCM":
        st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
        if not active_periods:
            st.warning("No active MCM periods. Contact Planning Officer.")
        else:
            period_options_display_map = { # Map display string to key
                                k: f"{p.get('month_name')} {p.get('year')}"
                                for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
                                if p.get('month_name') and p.get('year')
                            }
            # Reverse map for selectbox (display string -> key)
            period_options_select_map = {v: k for k, v in period_options_display_map.items()}


            if not period_options_display_map and active_periods:
                st.warning("Some active MCM periods have incomplete data (missing month/year) and are not shown as options.")

            # Gracefully handle if period_options_select_map is empty
            current_selection_display = None
            if st.session_state.ag_current_mcm_key and st.session_state.ag_current_mcm_key in period_options_display_map:
                current_selection_display = period_options_display_map[st.session_state.ag_current_mcm_key]

            selected_period_display_str = st.selectbox(
                "Select Active MCM Period",
                options=list(period_options_select_map.keys()),
                index=list(period_options_select_map.keys()).index(current_selection_display) if current_selection_display and current_selection_display in period_options_select_map else 0
                      if period_options_select_map else None, # Handle empty options
                key="ag_select_mcm_upload_key_str"
            )

            if selected_period_display_str:
                newly_selected_mcm_key = period_options_select_map[selected_period_display_str]
                if st.session_state.ag_current_mcm_key != newly_selected_mcm_key:
                    st.session_state.ag_current_mcm_key = newly_selected_mcm_key
                    # Reset relevant states when MCM period changes
                    st.session_state.ag_current_extracted_data = []
                    st.session_state.ag_pdf_drive_url = None
                    st.session_state.ag_validation_errors = []
                    st.session_state.ag_editor_data = pd.DataFrame()
                    st.session_state.ag_current_uploaded_file_name = None
                    st.session_state.uploader_key_suffix +=1 # Change uploader key to reset it
                    st.rerun() # Rerun to reflect changes and reset file uploader

                mcm_info = mcm_periods[st.session_state.ag_current_mcm_key]
                st.info(f"Uploading for: {mcm_info['month_name']} {mcm_info['year']}")

                uploaded_dar_file = st.file_uploader("Choose DAR PDF", type="pdf",
                                                     key=f"dar_upload_ag_{st.session_state.ag_current_mcm_key}_{st.session_state.uploader_key_suffix}")

                if uploaded_dar_file:
                    if st.session_state.ag_current_uploaded_file_name != uploaded_dar_file.name:
                        # Reset if a new file is uploaded for the same MCM period
                        st.session_state.ag_current_extracted_data = []
                        st.session_state.ag_pdf_drive_url = None
                        st.session_state.ag_validation_errors = []
                        st.session_state.ag_editor_data = pd.DataFrame()
                        st.session_state.ag_current_uploaded_file_name = uploaded_dar_file.name


                    if st.button("Extract Data from PDF", key=f"extract_ag_btn_{st.session_state.ag_current_mcm_key}", use_container_width=True):
                        st.session_state.ag_validation_errors = [] # Clear previous errors
                        with st.spinner("Processing PDF & AI extraction... This may take some time."):
                            dar_pdf_bytes = uploaded_dar_file.getvalue()
                            st.session_state.ag_pdf_drive_url = None # Reset before attempt

                            preprocessed_text = preprocess_pdf_text(BytesIO(dar_pdf_bytes))

                            if preprocessed_text.startswith("Error"):
                                st.error(f"PDF Preprocessing Error: {preprocessed_text}")
                                st.session_state.ag_editor_data = pd.DataFrame([{
                                    "audit_group_number": st.session_state.audit_group_no,
                                    "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                    "audit_para_heading": "Manual Entry - PDF Error",
                                    "status_of_para": None
                                }])
                            else:
                                parsed_report_obj: ParsedDARReport = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
                                temp_list = []
                                ai_extraction_partially_failed = False

                                if parsed_report_obj.parsing_errors:
                                    st.warning(f"AI Parsing Issues: {parsed_report_obj.parsing_errors}")
                                    ai_extraction_partially_failed = True

                                header_data_from_ai = parsed_report_obj.header.model_dump() if parsed_report_obj.header else {}
                                # Ensure audit group and circle are always set from session/calculated
                                final_header = {
                                    "audit_group_number": st.session_state.audit_group_no,
                                    "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                    "gstin": header_data_from_ai.get("gstin"),
                                    "trade_name": header_data_from_ai.get("trade_name"),
                                    "category": header_data_from_ai.get("category"),
                                    "total_amount_detected_overall_rs": header_data_from_ai.get("total_amount_detected_overall_rs"),
                                    "total_amount_recovered_overall_rs": header_data_from_ai.get("total_amount_recovered_overall_rs"),
                                }

                                if parsed_report_obj.audit_paras:
                                    for p_data_item_model in parsed_report_obj.audit_paras:
                                        p_data_item = p_data_item_model.model_dump()
                                        row = final_header.copy() # Start with header info
                                        row.update({ # Add/overwrite with para specific info
                                            "audit_para_number": p_data_item.get("audit_para_number"),
                                            "audit_para_heading": p_data_item.get("audit_para_heading"),
                                            "revenue_involved_lakhs_rs": p_data_item.get("revenue_involved_lakhs_rs"),
                                            "revenue_recovered_lakhs_rs": p_data_item.get("revenue_recovered_lakhs_rs"),
                                            "status_of_para": p_data_item.get("status_of_para") # Crucial addition
                                        })
                                        temp_list.append(row)
                                elif final_header.get("trade_name"): # Header info extracted, but no paras
                                    row = final_header.copy()
                                    row.update({
                                        "audit_para_number": None,
                                        "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)",
                                        "revenue_involved_lakhs_rs": None,
                                        "revenue_recovered_lakhs_rs": None,
                                        "status_of_para": None # Default for header-only
                                    })
                                    temp_list.append(row)
                                    if not ai_extraction_partially_failed : # if no prior warning, inform user
                                       st.info("AI extracted header data. No specific paras found, or provide them manually.")
                                else: # AI failed to get even basic header like trade_name
                                    st.error("AI failed to extract key header information (e.g., Trade Name). A manual entry template is provided.")
                                    row = final_header.copy() # Will have group/circle
                                    row.update({
                                         "audit_para_heading": "Manual Entry Required", "status_of_para": None
                                    })
                                    temp_list.append(row)


                                if not temp_list: # Fallback if temp_list is somehow still empty
                                     st.warning("AI extraction yielded no usable data. A template row is provided.")
                                     temp_list.append({
                                        "audit_group_number": st.session_state.audit_group_no,
                                        "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                        "audit_para_heading": "Manual Entry - AI No Data",
                                        "status_of_para": None
                                     })

                                st.session_state.ag_current_extracted_data = temp_list # Store raw list of dicts
                                df_for_editor = pd.DataFrame(temp_list)

                                # Ensure all columns for the editor are present
                                for col_editor in DISPLAY_COLUMN_ORDER:
                                    if col_editor not in df_for_editor.columns:
                                        df_for_editor[col_editor] = None
                                st.session_state.ag_editor_data = df_for_editor[DISPLAY_COLUMN_ORDER] # Select and order for editor

                                st.info("Data extracted/prepared. Please review and edit below.")
                                st.rerun() # Rerun to show the editor with new data

                # --- Data Editor Section ---
                if not st.session_state.ag_editor_data.empty:
                    st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)

                    # This is the column order defined at the top of the file by the user.
                    # It already includes "status_of_para" and "audit_circle_number".
                    # The DataFrame st.session_state.ag_editor_data should now be structured with these columns.

                    column_config_editor = {
                        "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True, help="Your Audit Group Number"),
                        "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True, help="Calculated Audit Circle"),
                        "gstin": st.column_config.TextColumn("GSTIN", help="15-digit GSTIN", width="medium"),
                        "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
                        "category": st.column_config.SelectboxColumn("Category", options=VALID_CATEGORIES, required=False, width="small"),
                        "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", help="Para number (integer), use empty for N/A", width="small"),
                        "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
                        "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, required=False, width="medium"),
                        "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", width="small"),
                        "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", width="small"),
                        "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detected (Rs)", format="%.2f", width="medium"),
                        "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recovered (Rs)", format="%.2f", width="medium"),
                    }
                    # Filter column_config_editor to only include keys that are actually in DISPLAY_COLUMN_ORDER
                    filtered_column_config = {k: v for k, v in column_config_editor.items() if k in DISPLAY_COLUMN_ORDER}


                    editor_key_dynamic = f"ag_editor_form_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_editor'}"
                    edited_df_from_ui = st.data_editor(
                        st.session_state.ag_editor_data, # Should be correctly ordered by DISPLAY_COLUMN_ORDER
                        column_config=filtered_column_config,
                        num_rows="dynamic",
                        key=editor_key_dynamic,
                        use_container_width=True,
                        height=400, # Adjust as needed
                        hide_index=True
                    )
                    st.session_state.ag_editor_data = pd.DataFrame(edited_df_from_ui) # Update session state with any edits

                    if st.button("Validate and Submit to MCM Sheet", key=f"submit_ag_data_{st.session_state.ag_current_mcm_key}", use_container_width=True):
                        current_data_to_submit = st.session_state.ag_editor_data.copy() # Use the latest edited data

                        # Ensure correct data types before validation, especially for numbers from text input
                        for num_col in ["audit_para_number", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs",
                                        "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs"]:
                            if num_col in current_data_to_submit.columns:
                                current_data_to_submit[num_col] = pd.to_numeric(current_data_to_submit[num_col], errors='coerce')


                        val_errors = validate_data_for_sheet(current_data_to_submit)
                        st.session_state.ag_validation_errors = val_errors

                        if not val_errors:
                            # --- Upload PDF before appending to sheet if not already done or if file changed ---
                            # This check is simplified; in a real scenario, you might want to avoid re-uploading if URL already exists
                            # and file content hasn't changed, but for now, we re-upload if URL is not set.
                            if not st.session_state.ag_pdf_drive_url :
                                st.info("Attempting to upload PDF to Google Drive...")
                                pdf_bytes_for_upload = uploaded_dar_file.getvalue() # Assumes uploaded_dar_file is still in scope
                                dar_filename_on_drive_submit = f"AG{st.session_state.audit_group_no}_{uploaded_dar_file.name}"
                                pdf_drive_id_submit, pdf_drive_url_submit = upload_to_drive(
                                    drive_service, pdf_bytes_for_upload, mcm_info['drive_folder_id'], dar_filename_on_drive_submit
                                )
                                if not pdf_drive_id_submit:
                                    st.error("Failed to upload PDF to Drive during submission. Please re-extract data to ensure PDF is uploaded.")
                                    st.stop()
                                st.session_state.ag_pdf_drive_url = pdf_drive_url_submit
                                st.success(f"PDF for submission uploaded to Drive: [Link]({st.session_state.ag_pdf_drive_url})")


                            if not st.session_state.ag_pdf_drive_url:
                                 st.error("PDF Drive URL missing. This should not happen if PDF upload was successful. Please re-extract data.")
                                 st.stop()


                            with st.spinner("Submitting to Google Sheet..."):
                                rows_to_append = []
                                created_date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                # Ensure the DataFrame for submission has all necessary columns in the correct sheet order
                                final_df_for_sheet = current_data_to_submit.copy()
                                for sheet_col in SHEET_DATA_COLUMNS_ORDER:
                                    if sheet_col not in final_df_for_sheet.columns:
                                        final_df_for_sheet[sheet_col] = None # Add if missing

                                # Fill again group and circle based on session
                                final_df_for_sheet["audit_group_number"] = st.session_state.audit_group_no
                                final_df_for_sheet["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)


                                for _, row_item in final_df_for_sheet.iterrows():
                                    sheet_row_data = [row_item.get(col_name) for col_name in SHEET_DATA_COLUMNS_ORDER]
                                    sheet_row_data.extend([st.session_state.ag_pdf_drive_url, created_date_str])
                                    rows_to_append.append(sheet_row_data)

                                if rows_to_append:
                                    if append_to_spreadsheet(sheets_service, mcm_info['spreadsheet_id'], rows_to_append):
                                        st.success(f"Data for '{st.session_state.ag_current_uploaded_file_name}' submitted successfully!");
                                        st.balloons();
                                        time.sleep(1) # Give user a moment to see success
                                        # Reset state for next upload
                                        st.session_state.ag_current_extracted_data = []
                                        st.session_state.ag_pdf_drive_url = None # Reset as new PDF will be new URL
                                        st.session_state.ag_editor_data = pd.DataFrame()
                                        st.session_state.ag_current_uploaded_file_name = None
                                        st.session_state.ag_validation_errors = []
                                        st.session_state.uploader_key_suffix +=1
                                        st.rerun()
                                    else:
                                        st.error("Failed to append to Google Sheet.")
                                else:
                                    st.error("No data to submit after validation (rows_to_append is empty).")
                        else:
                            st.error("Validation Failed! Please correct the errors highlighted above or in the table.")
                            if st.session_state.get('ag_validation_errors'):
                                st.markdown("---");
                                st.subheader("⚠️ Validation Errors Summary:");
                                for err_msg in st.session_state.ag_validation_errors:
                                    st.warning(err_msg)
            elif not period_options_select_map:
                 st.info("No MCM periods available for selection.")

    # ----- VIEW MY UPLOADED DARS TAB ------
    elif selected_tab == "View My Uploaded DARs":
        st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
        if not mcm_periods:
            st.info("No MCM periods found. Contact PCO.")
        else:
            all_period_options_view = {
                k: f"{p.get('month_name')} {p.get('year')}"
                for k, p in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True)
                if p.get('month_name') and p.get('year')
            }
            if not all_period_options_view and mcm_periods:
                st.warning("Some MCM periods have incomplete data (missing month/year) and are not shown.")

            if not all_period_options_view:
                st.info("No valid MCM periods found to view uploads.")
            else:
                selected_view_period_key_disp = st.selectbox(
                    "Select MCM Period to View Your Uploads",
                    options=list(all_period_options_view.keys()),
                    format_func=lambda k: all_period_options_view[k],
                    key="ag_view_my_dars_period_select_key"
                )

                if selected_view_period_key_disp and sheets_service:
                    sheet_id_view = mcm_periods[selected_view_period_key_disp]['spreadsheet_id']
                    with st.spinner("Loading your uploads..."):
                        df_all_uploads = read_from_spreadsheet(sheets_service, sheet_id_view)

                    if not df_all_uploads.empty:
                        # Ensure 'Audit Group Number' column exists and filter
                        if 'Audit Group Number' in df_all_uploads.columns:
                            df_all_uploads['Audit Group Number'] = df_all_uploads['Audit Group Number'].astype(str)
                            my_group_uploads_df = df_all_uploads[df_all_uploads['Audit Group Number'] == str(st.session_state.audit_group_no)]

                            if not my_group_uploads_df.empty:
                                st.markdown(f"<h4>Your Uploads for {all_period_options_view[selected_view_period_key_disp]}:</h4>", unsafe_allow_html=True)
                                df_display_my_uploads = my_group_uploads_df.copy()
                                if 'DAR PDF URL' in df_display_my_uploads.columns:
                                    df_display_my_uploads['DAR PDF URL'] = df_display_my_uploads['DAR PDF URL'].apply(
                                        lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link"
                                    )
                                # Define columns to show, including new ones if desired
                                view_cols_my_uploads = [
                                    "Trade Name", "Category", "Audit Circle Number", # Added Circle
                                    "Audit Para Number", "Audit Para Heading", "Status of para", # Added Status
                                    "DAR PDF URL", "Record Created Date"
                                ]
                                existing_view_cols = [col for col in view_cols_my_uploads if col in df_display_my_uploads.columns]
                                st.markdown(df_display_my_uploads[existing_view_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
                            else:
                                st.info(f"No DARs uploaded by you for {all_period_options_view[selected_view_period_key_disp]}.")
                        else:
                            st.warning("Spreadsheet is missing the 'Audit Group Number' column. Cannot filter your uploads.")
                    else:
                        st.info(f"No data found in the spreadsheet for {all_period_options_view[selected_view_period_key_disp]}.")
                elif not sheets_service and selected_view_period_key_disp:
                    st.error("Google Sheets service not available.")

    # ----- DELETE MY DAR ENTRIES TAB -----
    elif selected_tab == "Delete My DAR Entries":
        st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
        st.info("⚠️ This action is irreversible. Deletion removes entries from the Google Sheet; the PDF on Google Drive will remain.")
        if not mcm_periods:
            st.info("No MCM periods found. Contact PCO.")
        else:
            all_period_options_delete = {
                 k: f"{p.get('month_name')} {p.get('year')}"
                for k, p in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True)
                if p.get('month_name') and p.get('year')
            }
            if not all_period_options_delete and mcm_periods:
                st.warning("Some MCM periods have incomplete data and are not shown.")

            if not all_period_options_delete:
                st.info("No valid MCM periods found to manage entries.")
            else:
                selected_delete_period_key_disp = st.selectbox(
                    "Select MCM Period to Manage Your Entries",
                    options=list(all_period_options_delete.keys()),
                    format_func=lambda k: all_period_options_delete[k],
                    key="ag_delete_dars_period_select_key"
                )

                if selected_delete_period_key_disp and sheets_service:
                    sheet_id_for_delete = mcm_periods[selected_delete_period_key_disp]['spreadsheet_id']
                    first_sheet_gid_delete = 0 # Default GID
                    try:
                        meta_delete = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_for_delete).execute()
                        first_sheet_gid_delete = meta_delete.get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
                    except Exception as e_gid_del:
                        st.error(f"Could not fetch sheet GID for deletion: {e_gid_del}")
                        st.stop()

                    with st.spinner("Loading your uploads for potential deletion..."):
                        df_all_for_delete = read_from_spreadsheet(sheets_service, sheet_id_for_delete)

                    if not df_all_for_delete.empty:
                        if 'Audit Group Number' in df_all_for_delete.columns:
                            df_all_for_delete['Audit Group Number'] = df_all_for_delete['Audit Group Number'].astype(str)
                            my_entries_for_delete_df = df_all_for_delete[df_all_for_delete['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
                            # Store original DataFrame index (0-based index of rows in the *read data*)
                            my_entries_for_delete_df['original_data_index'] = my_entries_for_delete_df.index

                            if not my_entries_for_delete_df.empty:
                                st.markdown(f"<h4>Your Uploads in {all_period_options_delete[selected_delete_period_key_disp]} (Select to delete):</h4>", unsafe_allow_html=True)
                                options_for_delete_display = ["--Select an entry to delete--"]
                                st.session_state.ag_deletable_map.clear() # Clear map for new selection

                                for df_idx, row_to_delete in my_entries_for_delete_df.iterrows():
                                    # Use a unique combination of fields for display and mapping
                                    ident_str_delete = (
                                        f"TN: {str(row_to_delete.get('Trade Name', 'N/A'))[:25]}..., "
                                        f"Para: {row_to_delete.get('Audit Para Number', 'N/A')}, "
                                        f"DAR: {str(row_to_delete.get('DAR PDF URL', 'N/A'))[-30:]}, " # Last part of URL
                                        f"Uploaded: {row_to_delete.get('Record Created Date', 'N/A')}"
                                    )
                                    options_for_delete_display.append(ident_str_delete)
                                    # Map display string to the original_data_index for accurate deletion from sheet
                                    st.session_state.ag_deletable_map[ident_str_delete] = row_to_delete['original_data_index']


                                selected_entry_to_delete_display_str = st.selectbox(
                                    "Select Entry to Delete:",
                                    options=options_for_delete_display,
                                    key=f"delete_selectbox_{selected_delete_period_key_disp}"
                                )

                                if selected_entry_to_delete_display_str != "--Select an entry to delete--":
                                    original_df_idx_to_delete = st.session_state.ag_deletable_map.get(selected_entry_to_delete_display_str)

                                    if original_df_idx_to_delete is not None:
                                        row_details_for_confirmation = df_all_for_delete.loc[original_df_idx_to_delete] # Get full row from original df_all
                                        st.warning(
                                            f"You are about to delete: Trade Name: **{row_details_for_confirmation.get('Trade Name')}**, "
                                            f"Para: **{row_details_for_confirmation.get('Audit Para Number')}**, "
                                            f"Uploaded: **{row_details_for_confirmation.get('Record Created Date')}**"
                                        )
                                        with st.form(key=f"delete_confirm_form_{original_df_idx_to_delete}"):
                                            user_password_confirm = st.text_input("Enter Your Password to Confirm Deletion:", type="password", key=f"del_pass_{original_df_idx_to_delete}")
                                            submitted_final_delete = st.form_submit_button("Yes, Delete This Entry Permanently")

                                            if submitted_final_delete:
                                                if user_password_confirm == USER_CREDENTIALS.get(st.session_state.username):
                                                    # The index to delete in Google Sheets API is 0-based *within the sheet's data range*,
                                                    # which means if header is row 1, data starts at row 2 (index 1 for API if deleting first data row).
                                                    # `original_df_idx_to_delete` is the 0-based index from the DataFrame read by read_from_spreadsheet,
                                                    # which already excludes the header if read_from_spreadsheet handled it correctly.
                                                    # So this index should directly correspond to the data row index (0 = first data row).
                                                    if delete_spreadsheet_rows(sheets_service, sheet_id_for_delete, first_sheet_gid_delete, [original_df_idx_to_delete]):
                                                        st.success("Entry deleted successfully from Google Sheet.")
                                                        time.sleep(1)
                                                        st.rerun()
                                                    else:
                                                        st.error("Failed to delete entry from Google Sheet.")
                                                else:
                                                    st.error("Incorrect password. Deletion aborted.")
                                    else:
                                        st.error("Could not identify the selected entry for deletion. Please try again.")
                            else:
                                st.info(f"You have no entries in {all_period_options_delete[selected_delete_period_key_disp]} to delete.")
                        else:
                             st.warning("Spreadsheet is missing 'Audit Group Number' column. Cannot identify your entries.")
                    elif df_all_for_delete is None: # read_from_spreadsheet returned None due to error
                        st.error("Could not read data from the spreadsheet to identify entries for deletion.")
                    else: # df_all_for_delete is empty
                        st.info(f"No data found in the spreadsheet for {all_period_options_delete[selected_delete_period_key_disp]}.")
                elif not sheets_service and selected_delete_period_key_disp:
                     st.error("Google Sheets service not available.")


    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)# # ui_audit_group.py
# import streamlit as st
# import datetime
# import time
# import pandas as pd
# from io import BytesIO
# from streamlit_option_menu import option_menu

# # Assuming these utilities are correctly defined and imported
# from google_utils import (
#     load_mcm_periods, upload_to_drive, append_to_spreadsheet,
#     read_from_spreadsheet, delete_spreadsheet_rows
# )
# from dar_processor import preprocess_pdf_text 
# from gemini_utils import get_structured_data_with_gemini
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES # Ensure VALID_CATEGORIES is imported if used
# from config import USER_CREDENTIALS 

# def audit_group_dashboard(drive_service, sheets_service):
#     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
#                 unsafe_allow_html=True)
#     mcm_periods = load_mcm_periods(drive_service)
#     active_periods = {k: v for k, v in mcm_periods.items() if v.get("active")}
    
#     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE") # Ensure this is fetched

#     with st.sidebar:
#         # Changed to use local logo.png
#         try:
#             st.image("logo.png", width=80)
#         except Exception as e:
#             st.sidebar.warning(f"Could not load logo.png: {e}")
#             st.sidebar.markdown("*(Logo)*") # Fallback text

#         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}",
#                     unsafe_allow_html=True)
#         if st.button("Logout", key="ag_logout_styled", use_container_width=True):
#             for key_to_del in ['ag_current_extracted_data', 'ag_pdf_drive_url', 'ag_validation_errors',
#                                'ag_editor_data', 'ag_current_mcm_key', 'ag_current_uploaded_file_name',
#                                'ag_row_to_delete_details', 'ag_show_delete_confirm', 'drive_structure_initialized']: # ensure all relevant keys are cleared
#                 if key_to_del in st.session_state: del st.session_state[key_to_del]
#             st.session_state.logged_in = False
#             st.session_state.username = ""
#             st.session_state.role = ""
#             st.session_state.audit_group_no = None
#             st.rerun()
#         st.markdown("---")

#     selected_tab = option_menu(
#         menu_title=None, options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
#         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace", default_index=0,
#         orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
#             "icon": {"color": "#28a745", "font-size": "20px"},
#             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
#             "nav-link-selected": {"background-color": "#28a745", "color": "white"},
#         })
#     st.markdown("<div class='card'>", unsafe_allow_html=True)

#     if selected_tab == "Upload DAR for MCM":
#         st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
#         if not active_periods:
#             st.warning("No active MCM periods. Contact Planning Officer.")
#         else:
#             period_options = {
#                                  f"{p.get('month_name')} {p.get('year')}": k
#                                  for k, p in sorted(active_periods.items(), reverse=True)
#                                  if p.get('month_name') and p.get('year')
#                              }
#             if not period_options and active_periods:
#                 st.warning("Some active MCM periods have incomplete data (missing month/year) and are not shown as options.")
            
#             selected_period_display = st.selectbox("Select Active MCM Period", options=list(period_options.keys()),
#                                                    key="ag_select_mcm_upload_key") # Ensure unique key
#             if selected_period_display:
#                 selected_mcm_key = period_options[selected_period_display]
#                 mcm_info = mcm_periods[selected_mcm_key]
#                 if st.session_state.get('ag_current_mcm_key') != selected_mcm_key:
#                     st.session_state.ag_current_extracted_data = []
#                     st.session_state.ag_pdf_drive_url = None
#                     st.session_state.ag_validation_errors = []
#                     st.session_state.ag_editor_data = pd.DataFrame() # Requires pandas
#                     st.session_state.ag_current_mcm_key = selected_mcm_key
#                     st.session_state.ag_current_uploaded_file_name = None
#                 st.info(f"Uploading for: {mcm_info['month_name']} {mcm_info['year']}")
                
#                 # Ensure uploader_key_suffix is initialized if used
#                 if 'uploader_key_suffix' not in st.session_state:
#                     st.session_state.uploader_key_suffix = 0
                
#                 uploaded_dar_file = st.file_uploader("Choose DAR PDF", type="pdf",
#                                                      key=f"dar_upload_ag_{selected_mcm_key}_{st.session_state.uploader_key_suffix}")

#                 if uploaded_dar_file:
#                     if st.session_state.get('ag_current_uploaded_file_name') != uploaded_dar_file.name:
#                         st.session_state.ag_current_extracted_data = []
#                         st.session_state.ag_pdf_drive_url = None
#                         st.session_state.ag_validation_errors = []
#                         st.session_state.ag_editor_data = pd.DataFrame()
#                         st.session_state.ag_current_uploaded_file_name = uploaded_dar_file.name

#                     if st.button("Extract Data from PDF", key=f"extract_ag_btn_{selected_mcm_key}", use_container_width=True): # ensure unique key
#                         st.session_state.ag_validation_errors = []
#                         with st.spinner("Processing PDF & AI extraction..."):
#                             dar_pdf_bytes = uploaded_dar_file.getvalue()
#                             dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{uploaded_dar_file.name}"
#                             st.session_state.ag_pdf_drive_url = None # Reset before upload attempt
                            
#                             pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, dar_pdf_bytes,
#                                                                                mcm_info['drive_folder_id'], dar_filename_on_drive)
#                             if not pdf_drive_id:
#                                 st.error("Failed to upload PDF to Drive.");
#                                 st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry - PDF Upload Failed"}])
#                             else:
#                                 st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
#                                 st.success(f"DAR PDF on Drive: [Link]({st.session_state.ag_pdf_drive_url})")
                                
#                                 preprocessed_text = preprocess_pdf_text(BytesIO(dar_pdf_bytes)) # Assuming preprocess_pdf_text is correctly imported
                                
#                                 if preprocessed_text.startswith("Error"): # Check for preprocessing error
#                                     st.error(f"PDF Preprocessing Error: {preprocessed_text}");
#                                     st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry - PDF Error"}])
#                                 else:
#                                     # Assuming get_structured_data_with_gemini is correctly imported
#                                     parsed_report_obj = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
#                                     temp_list = []
#                                     ai_failed = True # Assume failure unless proven otherwise
                                    
#                                     if parsed_report_obj.parsing_errors: 
#                                         st.warning(f"AI Parsing Issues: {parsed_report_obj.parsing_errors}")
                                    
#                                     if parsed_report_obj and parsed_report_obj.header:
#                                         h = parsed_report_obj.header
#                                         ai_failed = False # Got header, so not a complete failure
#                                         if parsed_report_obj.audit_paras: # If there are audit paras
#                                             for p_data_item in parsed_report_obj.audit_paras: # Renamed p to p_data_item
#                                                 temp_list.append({
#                                                     "audit_group_number": st.session_state.audit_group_no, 
#                                                     "gstin": h.gstin, "trade_name": h.trade_name, "category": h.category, 
#                                                     "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs, 
#                                                     "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs, 
#                                                     "audit_para_number": p_data_item.audit_para_number, 
#                                                     "audit_para_heading": p_data_item.audit_para_heading, 
#                                                     "revenue_involved_lakhs_rs": p_data_item.revenue_involved_lakhs_rs, 
#                                                     "revenue_recovered_lakhs_rs": p_data_item.revenue_recovered_lakhs_rs
#                                                 })
#                                         elif h.trade_name: # Header info present but no paras
#                                             temp_list.append({
#                                                 "audit_group_number": st.session_state.audit_group_no, 
#                                                 "gstin": h.gstin, "trade_name": h.trade_name, "category": h.category, 
#                                                 "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs, 
#                                                 "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs, 
#                                                 "audit_para_number": None, # No para number
#                                                 "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)", # Special heading
#                                                 "revenue_involved_lakhs_rs": None, 
#                                                 "revenue_recovered_lakhs_rs": None
#                                             })
#                                         else: # Header info itself is problematic (e.g., no trade_name)
#                                             st.error("AI failed to extract key header information (like Trade Name)."); 
#                                             ai_failed = True
                                    
#                                     if ai_failed or not temp_list: # If AI failed or produced an empty list
#                                         st.warning("AI extraction failed or yielded no usable data. Please fill manually.")
#                                         st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry Required"}])
#                                     else: 
#                                         st.session_state.ag_editor_data = pd.DataFrame(temp_list)
#                                         st.info("Data extracted. Review & edit below.")
                
#                 if not isinstance(st.session_state.get('ag_editor_data'), pd.DataFrame): 
#                     st.session_state.ag_editor_data = pd.DataFrame() # Ensure it's a DataFrame

#                 # This condition handles the case where PDF was uploaded, extraction ran, but editor_data is still empty.
#                 if uploaded_dar_file and st.session_state.ag_editor_data.empty and st.session_state.get('ag_pdf_drive_url'): 
#                     st.warning("AI couldn't extract data or no data was previously loaded. A template row is provided for manual entry.")
#                     st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry"}])

#                 if not st.session_state.ag_editor_data.empty:
#                     st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
#                     df_to_edit_ag = st.session_state.ag_editor_data.copy()
#                     df_to_edit_ag["audit_group_number"] = st.session_state.audit_group_no # Ensure group number is set
                    
#                     col_order = ["audit_group_number", "gstin", "trade_name", "category", 
#                                  "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs", 
#                                  "audit_para_number", "audit_para_heading", 
#                                  "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"]
                    
#                     for col_name in col_order: # Ensure all columns exist
#                         if col_name not in df_to_edit_ag.columns: 
#                             df_to_edit_ag[col_name] = None 
                    
#                     col_config = {
#                         "audit_group_number": st.column_config.NumberColumn("Audit Group", disabled=True, help="Your Audit Group Number"),
#                         "gstin": st.column_config.TextColumn("GSTIN", help="15-digit GSTIN"),
#                         "trade_name": st.column_config.TextColumn("Trade Name"),
#                         "category": st.column_config.SelectboxColumn("Category", options=VALID_CATEGORIES, required=False), # VALID_CATEGORIES should be imported
#                         "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detected (Rs)", format="%.2f", help="Overall detection for the DAR"),
#                         "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recovered (Rs)", format="%.2f", help="Overall recovery for the DAR"),
#                         "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", help="Para number (integer)"),
#                         "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                         "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", help="Para-specific revenue involved in Lakhs Rs."),
#                         "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", help="Para-specific revenue recovered in Lakhs Rs.")
#                     }
                    
#                     editor_key = f"ag_editor_form_{selected_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_uploaded'}" # ensure unique key
#                     edited_df = st.data_editor(
#                         df_to_edit_ag.reindex(columns=col_order), # Ensure consistent column order
#                         column_config=col_config, 
#                         num_rows="dynamic", 
#                         key=editor_key, 
#                         use_container_width=True, 
#                         height=400
#                     )

#                     if st.button("Validate and Submit to MCM Sheet", key=f"submit_ag_data_{selected_mcm_key}", use_container_width=True): # ensure unique key
#                         current_data_to_submit = pd.DataFrame(edited_df) # Use the output from data_editor
#                         current_data_to_submit["audit_group_number"] = st.session_state.audit_group_no # Re-ensure audit group number
                        
#                         val_errors = validate_data_for_sheet(current_data_to_submit) # Assuming validate_data_for_sheet is imported
#                         st.session_state.ag_validation_errors = val_errors
                        
#                         if not val_errors:
#                             if not st.session_state.ag_pdf_drive_url: 
#                                 st.error("PDF Drive URL missing. Re-extract data or ensure PDF was uploaded successfully.")
#                             else:
#                                 with st.spinner("Submitting to Google Sheet..."):
#                                     rows_to_append = []
#                                     created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                                     for _, row_item in current_data_to_submit.iterrows(): # Renamed 'row' to 'row_item'
#                                         rows_to_append.append([row_item.get(c_name) for c_name in col_order] + [st.session_state.ag_pdf_drive_url, created_date])
                                    
#                                     if rows_to_append:
#                                         # Assuming append_to_spreadsheet is imported
#                                         if append_to_spreadsheet(sheets_service, mcm_info['spreadsheet_id'], rows_to_append):
#                                             st.success(f"Data for '{st.session_state.ag_current_uploaded_file_name}' submitted!"); 
#                                             st.balloons(); 
#                                             time.sleep(0.5)
#                                             # Reset session state for next upload
#                                             st.session_state.ag_current_extracted_data = []
#                                             st.session_state.ag_pdf_drive_url = None
#                                             st.session_state.ag_editor_data = pd.DataFrame()
#                                             st.session_state.ag_current_uploaded_file_name = None
#                                             st.session_state.uploader_key_suffix = st.session_state.get('uploader_key_suffix', 0) + 1
#                                             st.rerun()
#                                         else: 
#                                             st.error("Failed to append to Google Sheet.")
#                                     else: 
#                                         st.error("No data to submit after validation (rows_to_append is empty).")
#                         else: 
#                             st.error("Validation Failed! Correct errors below.")
                
#                 if st.session_state.get('ag_validation_errors'):
#                     st.markdown("---"); 
#                     st.subheader("⚠️ Validation Errors:");
#                     for err_msg in st.session_state.ag_validation_errors: # Renamed 'err' to 'err_msg'
#                         st.warning(err_msg)

#     elif selected_tab == "View My Uploaded DARs":
#         st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
#         if not mcm_periods: 
#             st.info("No MCM periods by PCO yet.")
#         else:
#             all_period_options = {
#                 f"{p.get('month_name')} {p.get('year')}": k 
#                 for k,p in sorted(mcm_periods.items(),key=lambda item:item[0],reverse=True) 
#                 if p.get('month_name') and p.get('year')
#             }
#             if not all_period_options and mcm_periods: 
#                 st.warning("Some MCM periods have incomplete data and are not shown.")
#             if not all_period_options: 
#                 st.info("No valid MCM periods found.")
#             else:
#                 selected_view_period_display = st.selectbox("Select MCM Period", options=list(all_period_options.keys()), key="ag_view_my_dars_period_key") # Unique key

#                 if selected_view_period_display and sheets_service:
#                     selected_view_period_key = all_period_options[selected_view_period_display]
#                     sheet_id = mcm_periods[selected_view_period_key]['spreadsheet_id']
#                     with st.spinner("Loading your uploads..."): 
#                         df_all = read_from_spreadsheet(sheets_service, sheet_id) # Assuming read_from_spreadsheet is imported
                    
#                     if not df_all.empty and 'Audit Group Number' in df_all.columns:
#                         df_all['Audit Group Number'] = df_all['Audit Group Number'].astype(str) # Ensure consistent type for comparison
#                         my_uploads_df = df_all[df_all['Audit Group Number'] == str(st.session_state.audit_group_no)]
                        
#                         if not my_uploads_df.empty:
#                             st.markdown(f"<h4>Your Uploads for {selected_view_period_display}:</h4>", unsafe_allow_html=True)
#                             df_display = my_uploads_df.copy()
#                             if 'DAR PDF URL' in df_display.columns: 
#                                 df_display['DAR PDF URL'] = df_display['DAR PDF URL'].apply(
#                                     lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link"
#                                 )
#                             view_cols = ["Trade Name", "Category", "Audit Para Number", "Audit Para Heading", "DAR PDF URL", "Record Created Date"]
#                             existing_view_cols = [col for col in view_cols if col in df_display.columns] # Filter for existing columns
#                             st.markdown(df_display[existing_view_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
#                         else: 
#                             st.info(f"No DARs uploaded by you for {selected_view_period_display}.")
#                     elif df_all.empty: 
#                         st.info(f"No data in MCM sheet for {selected_view_period_display}.")
#                     else: # df_all not empty but 'Audit Group Number' column missing
#                         st.warning("Spreadsheet missing 'Audit Group Number' column.")
#                 elif not sheets_service and selected_view_period_display: # If period selected but service is down
#                     st.error("Google Sheets service not available.")


#     elif selected_tab == "Delete My DAR Entries":
#         st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#         st.info("Select MCM period to view entries. Deletion removes entry from Google Sheet; PDF on Drive remains.")
#         if not mcm_periods: 
#             st.info("No MCM periods created yet.")
#         else:
#             all_period_options_del = {
#                 f"{p.get('month_name')} {p.get('year')}": k 
#                 for k, p in sorted(mcm_periods.items(),key=lambda item:item[0],reverse=True) 
#                 if p.get('month_name') and p.get('year')
#             }
#             if not all_period_options_del and mcm_periods: 
#                 st.warning("Some MCM periods have incomplete data and are not shown.")
            
#             selected_del_period_display = st.selectbox("Select MCM Period", options=list(all_period_options_del.keys()), key="ag_del_dars_period_key") # Unique key

#             if selected_del_period_display and sheets_service:
#                 selected_del_period_key = all_period_options_del[selected_del_period_display]
#                 sheet_id_to_manage = mcm_periods[selected_del_period_key]['spreadsheet_id']
#                 first_sheet_gid = 0 # Default GID
#                 try:
#                     meta = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_manage).execute()
#                     first_sheet_gid = meta.get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
#                 except Exception as e_gid: 
#                     st.error(f"Could not fetch sheet GID: {e_gid}")

#                 with st.spinner("Loading your uploads..."): 
#                     df_all_del = read_from_spreadsheet(sheets_service, sheet_id_to_manage)
                
#                 if not df_all_del.empty and 'Audit Group Number' in df_all_del.columns:
#                     df_all_del['Audit Group Number'] = df_all_del['Audit Group Number'].astype(str)
#                     my_uploads_df_del = df_all_del[df_all_del['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
#                     my_uploads_df_del.reset_index(inplace=True) # Keep original DataFrame index for internal mapping if needed later
#                     my_uploads_df_del.rename(columns={'index': 'original_df_index'}, inplace=True) # Not strictly used here, but good practice

#                     if not my_uploads_df_del.empty:
#                         st.markdown(f"<h4>Your Uploads in {selected_del_period_display} (Select to delete):</h4>", unsafe_allow_html=True)
#                         options_for_del = ["--Select an entry--"]
                        
#                         # Initialize ag_deletable_map in session_state if not present
#                         if 'ag_deletable_map' not in st.session_state:
#                             st.session_state.ag_deletable_map = {}
#                         else: # Clear map for the current selection context
#                             st.session_state.ag_deletable_map.clear() 

#                         for idx, row_data_item_del in my_uploads_df_del.iterrows(): # Renamed 'row'
#                             ident_str = f"Entry (TN: {str(row_data_item_del.get('Trade Name', 'N/A'))[:20]}..., Para: {row_data_item_del.get('Audit Para Number', 'N/A')}, Date: {row_data_item_del.get('Record Created Date', 'N/A')})"
#                             options_for_del.append(ident_str)
#                             # Store identifiable data for matching
#                             st.session_state.ag_deletable_map[ident_str] = {
#                                 "trade_name": str(row_data_item_del.get('Trade Name')),
#                                 "audit_para_number": str(row_data_item_del.get('Audit Para Number')), # Compare as strings
#                                 "record_created_date": str(row_data_item_del.get('Record Created Date')),
#                                 "dar_pdf_url": str(row_data_item_del.get('DAR PDF URL'))
#                             }
                        
#                         selected_entry_del_display = st.selectbox("Select Entry to Delete:", options_for_del, key=f"del_sel_box_{selected_del_period_key}") # Unique key

#                         if selected_entry_del_display != "--Select an entry--":
#                             row_ident_data = st.session_state.ag_deletable_map.get(selected_entry_del_display)
#                             if row_ident_data:
#                                 st.warning(f"Selected to delete: **{row_ident_data.get('trade_name')} - Para {row_ident_data.get('audit_para_number')}** (Uploaded: {row_ident_data.get('record_created_date')})")
#                                 with st.form(key=f"del_ag_form_final_{selected_entry_del_display.replace(' ', '_')}"): # Unique key
#                                     ag_pass = st.text_input("Your Password:", type="password", key=f"ag_pass_del_confirm_{selected_entry_del_display.replace(' ', '_')}") # Unique key
#                                     submitted_del = st.form_submit_button("Confirm Deletion")
                                    
#                                     if submitted_del:
#                                         if ag_pass == USER_CREDENTIALS.get(st.session_state.username): # USER_CREDENTIALS should be imported
#                                             current_sheet_df = read_from_spreadsheet(sheets_service, sheet_id_to_manage) # Re-fetch
#                                             if not current_sheet_df.empty:
#                                                 indices_to_del_sheet = []
#                                                 # Exact matching against re-fetched data
#                                                 for sheet_idx, sheet_row_data in current_sheet_df.iterrows(): # Renamed 'sheet_row'
#                                                     match_conditions = [
#                                                         str(sheet_row_data.get('Audit Group Number')) == str(st.session_state.audit_group_no),
#                                                         str(sheet_row_data.get('Trade Name')) == row_ident_data.get('trade_name'),
#                                                         str(sheet_row_data.get('Audit Para Number')) == row_ident_data.get('audit_para_number'),
#                                                         str(sheet_row_data.get('Record Created Date')) == row_ident_data.get('record_created_date'),
#                                                         str(sheet_row_data.get('DAR PDF URL')) == row_ident_data.get('dar_pdf_url')
#                                                     ]
#                                                     if all(match_conditions): 
#                                                         indices_to_del_sheet.append(sheet_idx) # 0-based index from read_from_spreadsheet (data part)
                                                
#                                                 if indices_to_del_sheet:
#                                                     # Assuming delete_spreadsheet_rows is imported
#                                                     if delete_spreadsheet_rows(sheets_service, sheet_id_to_manage, first_sheet_gid, indices_to_del_sheet):
#                                                         st.success(f"Entry for '{row_ident_data.get('trade_name')}' deleted."); 
#                                                         time.sleep(0.5); 
#                                                         st.rerun()
#                                                     else: 
#                                                         st.error("Failed to delete from sheet.")
#                                                 else: 
#                                                     st.error("Could not find exact entry to delete. It might have been already deleted or modified.")
#                                             else: 
#                                                 st.error("Could not re-fetch sheet data for deletion verification.")
#                                         else: 
#                                             st.error("Incorrect password.")
#                             else: 
#                                 st.error("Could not retrieve details for selected entry. Please re-select.")
#                     else: 
#                         st.info(f"You have no uploads in {selected_del_period_display} to delete.")
#                 elif df_all_del.empty: 
#                     st.info(f"No data in MCM sheet for {selected_del_period_display}.")
#                 else: # df_all_del not empty but 'Audit Group Number' column missing
#                     st.warning("Spreadsheet missing 'Audit Group Number' column.")
#             elif not sheets_service and selected_del_period_display: # If period selected but service is down
#                 st.error("Google Sheets service not available.")

#     st.markdown("</div>", unsafe_allow_html=True)# # ui_audit_group.py
# # import streamlit as st
# # import datetime
# # import time
# # import pandas as pd
# # from io import BytesIO
# # from streamlit_option_menu import option_menu

# # from google_utils import (
# #     load_mcm_periods, upload_to_drive, append_to_spreadsheet,
# #     read_from_spreadsheet, delete_spreadsheet_rows
# # )
# # from dar_processor import preprocess_pdf_text  # Assuming dar_processor.py provides this
# # from gemini_utils import get_structured_data_with_gemini
# # from validation_utils import validate_data_for_sheet, VALID_CATEGORIES
# # from config import USER_CREDENTIALS  # For password confirmation


# # def audit_group_dashboard(drive_service, sheets_service):
# #     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
# #                 unsafe_allow_html=True)
# #     mcm_periods = load_mcm_periods(drive_service)
# #     active_periods = {k: v for k, v in mcm_periods.items() if v.get("active")}

# #     # Fetch Gemini API Key from secrets
# #     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

# #     with st.sidebar:
# #         st.image(
# #             "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Indian_Ministry_of_Finance_logo.svg/1200px-Indian_Ministry_of_Finance_logo.svg.png",
# #             width=80)
# #         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}",
# #                     unsafe_allow_html=True)
# #         if st.button("Logout", key="ag_logout_styled", use_container_width=True):
# #             for key_to_del in ['ag_current_extracted_data', 'ag_pdf_drive_url', 'ag_validation_errors',
# #                                'ag_editor_data', 'ag_current_mcm_key', 'ag_current_uploaded_file_name',
# #                                'ag_row_to_delete_details', 'ag_show_delete_confirm', 'drive_structure_initialized']:
# #                 if key_to_del in st.session_state: del st.session_state[key_to_del]
# #             st.session_state.logged_in = False
# #             st.session_state.username = ""
# #             st.session_state.role = ""
# #             st.session_state.audit_group_no = None
# #             st.rerun()
# #         st.markdown("---")

# #     selected_tab = option_menu(
# #         menu_title=None, options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
# #         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace", default_index=0,
# #         orientation="horizontal",
# #         styles={
# #             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
# #             "icon": {"color": "#28a745", "font-size": "20px"},
# #             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
# #             "nav-link-selected": {"background-color": "#28a745", "color": "white"},
# #         })
# #     st.markdown("<div class='card'>", unsafe_allow_html=True)

# #     if selected_tab == "Upload DAR for MCM":
# #         st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
# #         if not active_periods:
# #             st.warning("No active MCM periods. Contact Planning Officer.")
# #         else:
# #             period_options = {
# #                 f"{p.get('month_name')} {p.get('year')}": k
# #                 for k, p in sorted(active_periods.items(), reverse=True)
# #                 if p.get('month_name') and p.get('year')
# #             }
# #             if not period_options and active_periods:
# #                 st.warning(
# #                     "Some active MCM periods have incomplete data (missing month/year) and are not shown as options.")

# #             selected_period_display = st.selectbox("Select Active MCM Period", options=list(period_options.keys()),
# #                                                    key="ag_select_mcm_upload")
# #             if selected_period_display:
# #                 selected_mcm_key = period_options[selected_period_display]
# #                 mcm_info = mcm_periods[selected_mcm_key]
# #                 if st.session_state.get('ag_current_mcm_key') != selected_mcm_key:
# #                     st.session_state.ag_current_extracted_data = [];
# #                     st.session_state.ag_pdf_drive_url = None
# #                     st.session_state.ag_validation_errors = [];
# #                     st.session_state.ag_editor_data = pd.DataFrame()
# #                     st.session_state.ag_current_mcm_key = selected_mcm_key;
# #                     st.session_state.ag_current_uploaded_file_name = None
# #                 st.info(f"Uploading for: {mcm_info['month_name']} {mcm_info['year']}")
# #                 uploaded_dar_file = st.file_uploader("Choose DAR PDF", type="pdf",
# #                                                      key=f"dar_upload_ag_{selected_mcm_key}_{st.session_state.get('uploader_key_suffix', 0)}")

# #                 if uploaded_dar_file:
# #                     if st.session_state.get('ag_current_uploaded_file_name') != uploaded_dar_file.name:
# #                         st.session_state.ag_current_extracted_data = [];
# #                         st.session_state.ag_pdf_drive_url = None
# #                         st.session_state.ag_validation_errors = [];
# #                         st.session_state.ag_editor_data = pd.DataFrame()
# #                         st.session_state.ag_current_uploaded_file_name = uploaded_dar_file.name

# #                     if st.button("Extract Data from PDF", key=f"extract_ag_{selected_mcm_key}",
# #                                  use_container_width=True):
# #                         st.session_state.ag_validation_errors = []
# #                         with st.spinner("Processing PDF & AI extraction..."):
# #                             dar_pdf_bytes = uploaded_dar_file.getvalue()
# #                             dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{uploaded_dar_file.name}"
# #                             st.session_state.ag_pdf_drive_url = None
# #                             pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, dar_pdf_bytes,
# #                                                                                mcm_info['drive_folder_id'],
# #                                                                                dar_filename_on_drive)
# #                             if not pdf_drive_id:
# #                                 st.error("Failed to upload PDF to Drive.");
# #                                 st.session_state.ag_editor_data = pd.DataFrame([{
# #                                                                                     "audit_group_number": st.session_state.audit_group_no,
# #                                                                                     "audit_para_heading": "Manual Entry - PDF Upload Failed"}])
# #                             else:
# #                                 st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
# #                                 st.success(f"DAR PDF on Drive: [Link]({st.session_state.ag_pdf_drive_url})")
# #                                 preprocessed_text = preprocess_pdf_text(BytesIO(dar_pdf_bytes))
# #                                 if preprocessed_text.startswith("Error"):
# #                                     st.error(f"PDF Preprocessing Error: {preprocessed_text}");
# #                                     st.session_state.ag_editor_data = pd.DataFrame([{
# #                                                                                         "audit_group_number": st.session_state.audit_group_no,
# #                                                                                         "audit_para_heading": "Manual Entry - PDF Error"}])
# #                                 else:
# #                                     parsed_report_obj = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY,
# #                                                                                         preprocessed_text)
# #                                     temp_list = []
# #                                     ai_failed = True
# #                                     if parsed_report_obj.parsing_errors: st.warning(
# #                                         f"AI Parsing Issues: {parsed_report_obj.parsing_errors}")
# #                                     if parsed_report_obj and parsed_report_obj.header:
# #                                         h = parsed_report_obj.header;
# #                                         ai_failed = False
# #                                         if parsed_report_obj.audit_paras:
# #                                             for p in parsed_report_obj.audit_paras: temp_list.append(
# #                                                 {"audit_group_number": st.session_state.audit_group_no,
# #                                                  "gstin": h.gstin, "trade_name": h.trade_name, "category": h.category,
# #                                                  "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs,
# #                                                  "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs,
# #                                                  "audit_para_number": p.audit_para_number,
# #                                                  "audit_para_heading": p.audit_para_heading,
# #                                                  "revenue_involved_lakhs_rs": p.revenue_involved_lakhs_rs,
# #                                                  "revenue_recovered_lakhs_rs": p.revenue_recovered_lakhs_rs})
# #                                         elif h.trade_name:
# #                                             temp_list.append({"audit_group_number": st.session_state.audit_group_no,
# #                                                               "gstin": h.gstin, "trade_name": h.trade_name,
# #                                                               "category": h.category,
# #                                                               "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs,
# #                                                               "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs,
# #                                                               "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)"})
# #                                         else:
# #                                             st.error("AI failed to extract key header info."); ai_failed = True
# #                                     if ai_failed or not temp_list:
# #                                         st.warning("AI extraction failed or yielded no data. Please fill manually.")
# #                                         st.session_state.ag_editor_data = pd.DataFrame([{
# #                                                                                             "audit_group_number": st.session_state.audit_group_no,
# #                                                                                             "audit_para_heading": "Manual Entry Required"}])
# #                                     else:
# #                                         st.session_state.ag_editor_data = pd.DataFrame(temp_list); st.info(
# #                                             "Data extracted. Review & edit below.")

# #                 if not isinstance(st.session_state.get('ag_editor_data'),
# #                                   pd.DataFrame): st.session_state.ag_editor_data = pd.DataFrame()
# #                 if uploaded_dar_file and st.session_state.ag_editor_data.empty and st.session_state.get(
# #                         'ag_pdf_drive_url'):
# #                     st.warning("AI couldn't extract data or none loaded. Template row provided.")
# #                     st.session_state.ag_editor_data = pd.DataFrame(
# #                         [{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry"}])

# #                 if not st.session_state.ag_editor_data.empty:
# #                     st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
# #                     df_to_edit_ag = st.session_state.ag_editor_data.copy();
# #                     df_to_edit_ag["audit_group_number"] = st.session_state.audit_group_no
# #                     col_order = ["audit_group_number", "gstin", "trade_name", "category",
# #                                  "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
# #                                  "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
# #                                  "revenue_recovered_lakhs_rs"]
# #                     for col in col_order:
# #                         if col not in df_to_edit_ag.columns: df_to_edit_ag[col] = None
# #                     col_config = {"audit_group_number": st.column_config.NumberColumn("Audit Group", disabled=True),
# #                                   "gstin": st.column_config.TextColumn("GSTIN"),
# #                                   "trade_name": st.column_config.TextColumn("Trade Name"),
# #                                   "category": st.column_config.SelectboxColumn("Category", options=VALID_CATEGORIES),
# #                                   "total_amount_detected_overall_rs": st.column_config.NumberColumn(
# #                                       "Total Detected (Rs)", format="%.2f"),
# #                                   "total_amount_recovered_overall_rs": st.column_config.NumberColumn(
# #                                       "Total Recovered (Rs)", format="%.2f"),
# #                                   "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d"),
# #                                   "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
# #                                   "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)",
# #                                                                                              format="%.2f"),
# #                                   "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)",
# #                                                                                               format="%.2f")}
# #                     editor_key = f"ag_editor_{selected_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
# #                     edited_df = st.data_editor(df_to_edit_ag.reindex(columns=col_order), column_config=col_config,
# #                                                num_rows="dynamic", key=editor_key, use_container_width=True, height=400)

# #                     if st.button("Validate and Submit to MCM Sheet", key=f"submit_ag_{selected_mcm_key}",
# #                                  use_container_width=True):
# #                         current_data = pd.DataFrame(edited_df);
# #                         current_data["audit_group_number"] = st.session_state.audit_group_no
# #                         val_errors = validate_data_for_sheet(current_data);
# #                         st.session_state.ag_validation_errors = val_errors
# #                         if not val_errors:
# #                             if not st.session_state.ag_pdf_drive_url:
# #                                 st.error("PDF Drive URL missing. Re-extract data.")
# #                             else:
# #                                 with st.spinner("Submitting to Google Sheet..."):
# #                                     rows_to_append = []
# #                                     created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# #                                     for _, row in current_data.iterrows(): rows_to_append.append(
# #                                         [row.get(c) for c in col_order] + [st.session_state.ag_pdf_drive_url,
# #                                                                            created_date])
# #                                     if rows_to_append:
# #                                         if append_to_spreadsheet(sheets_service, mcm_info['spreadsheet_id'],
# #                                                                  rows_to_append):
# #                                             st.success(
# #                                                 f"Data for '{st.session_state.ag_current_uploaded_file_name}' submitted!");
# #                                             st.balloons();
# #                                             time.sleep(0.5)
# #                                             st.session_state.ag_current_extracted_data = [];
# #                                             st.session_state.ag_pdf_drive_url = None;
# #                                             st.session_state.ag_editor_data = pd.DataFrame();
# #                                             st.session_state.ag_current_uploaded_file_name = None
# #                                             st.session_state.uploader_key_suffix = st.session_state.get(
# #                                                 'uploader_key_suffix', 0) + 1;
# #                                             st.rerun()
# #                                         else:
# #                                             st.error("Failed to append to Google Sheet.")
# #                                     else:
# #                                         st.error("No data to submit after validation.")
# #                         else:
# #                             st.error("Validation Failed! Correct errors below.")
# #                 if st.session_state.get('ag_validation_errors'):
# #                     st.markdown("---");
# #                     st.subheader("⚠️ Validation Errors:");
# #                     for err in st.session_state.ag_validation_errors: st.warning(err)

# #     elif selected_tab == "View My Uploaded DARs":
# #         st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
# #         if not mcm_periods:
# #             st.info("No MCM periods by PCO yet.")
# #         else:
# #             all_period_options = {f"{p.get('month_name')} {p.get('year')}": k for k, p in
# #                                   sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if
# #                                   p.get('month_name') and p.get('year')}
# #             if not all_period_options and mcm_periods: st.warning(
# #                 "Some MCM periods have incomplete data (missing month/year) and are not shown as options for viewing.")
# #             if not all_period_options:
# #                 st.info("No MCM periods found.")
# #             else:
# #                 selected_view_period_display = st.selectbox("Select MCM Period",
# #                                                             options=list(all_period_options.keys()),
# #                                                             key="ag_view_my_dars_period")
# #                 if selected_view_period_display and sheets_service:
# #                     selected_view_period_key = all_period_options[selected_view_period_display]
# #                     sheet_id = mcm_periods[selected_view_period_key]['spreadsheet_id']
# #                     with st.spinner("Loading your uploads..."):
# #                         df_all = read_from_spreadsheet(sheets_service, sheet_id)
# #                     if not df_all.empty and 'Audit Group Number' in df_all.columns:
# #                         df_all['Audit Group Number'] = df_all['Audit Group Number'].astype(str)
# #                         my_uploads_df = df_all[df_all['Audit Group Number'] == str(st.session_state.audit_group_no)]
# #                         if not my_uploads_df.empty:
# #                             st.markdown(f"<h4>Your Uploads for {selected_view_period_display}:</h4>",
# #                                         unsafe_allow_html=True)
# #                             df_display = my_uploads_df.copy()
# #                             if 'DAR PDF URL' in df_display.columns: df_display['DAR PDF URL'] = df_display[
# #                                 'DAR PDF URL'].apply(
# #                                 lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(
# #                                     x).startswith("http") else "No Link")
# #                             view_cols = ["Trade Name", "Category", "Audit Para Number", "Audit Para Heading",
# #                                          "DAR PDF URL", "Record Created Date"]
# #                             st.markdown(df_display[view_cols].to_html(escape=False, index=False),
# #                                         unsafe_allow_html=True)
# #                         else:
# #                             st.info(f"No DARs uploaded by you for {selected_view_period_display}.")
# #                     elif df_all.empty:
# #                         st.info(f"No data in MCM sheet for {selected_view_period_display}.")
# #                     else:
# #                         st.warning("Spreadsheet missing 'Audit Group Number' column.")
# #                 elif not sheets_service:
# #                     st.error("Google Sheets service not available.")

# #     elif selected_tab == "Delete My DAR Entries":
# #         st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
# #         st.info("Select MCM period to view entries. Deletion removes entry from Google Sheet; PDF on Drive remains.")
# #         if not mcm_periods:
# #             st.info("No MCM periods created yet.")
# #         else:
# #             all_period_options_del = {f"{p.get('month_name')} {p.get('year')}": k for k, p in
# #                                       sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if
# #                                       p.get('month_name') and p.get('year')}
# #             if not all_period_options_del and mcm_periods: st.warning(
# #                 "Some MCM periods have incomplete data (missing month/year) and are not shown as options for deletion.")
# #             selected_del_period_display = st.selectbox("Select MCM Period", options=list(all_period_options_del.keys()),
# #                                                        key="ag_del_dars_period")
# #             if selected_del_period_display and sheets_service:
# #                 selected_del_period_key = all_period_options_del[selected_del_period_display]
# #                 sheet_id_to_manage = mcm_periods[selected_del_period_key]['spreadsheet_id']
# #                 first_sheet_gid = 0
# #                 try:
# #                     meta = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_manage).execute()
# #                     first_sheet_gid = meta.get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
# #                 except Exception as e_gid:
# #                     st.error(f"Could not fetch sheet GID: {e_gid}")

# #                 with st.spinner("Loading your uploads..."):
# #                     df_all_del = read_from_spreadsheet(sheets_service, sheet_id_to_manage)
# #                 if not df_all_del.empty and 'Audit Group Number' in df_all_del.columns:
# #                     df_all_del['Audit Group Number'] = df_all_del['Audit Group Number'].astype(str)
# #                     my_uploads_df_del = df_all_del[
# #                         df_all_del['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
# #                     my_uploads_df_del.reset_index(inplace=True);
# #                     my_uploads_df_del.rename(columns={'index': 'original_df_index'}, inplace=True)

# #                     if not my_uploads_df_del.empty:
# #                         st.markdown(f"<h4>Your Uploads in {selected_del_period_display} (Select to delete):</h4>",
# #                                     unsafe_allow_html=True)
# #                         options_for_del = ["--Select an entry--"]
# #                         st.session_state.ag_deletable_map = {}
# #                         for idx, row in my_uploads_df_del.iterrows():
# #                             ident_str = f"Entry (TN: {str(row.get('Trade Name', 'N/A'))[:20]}..., Para: {row.get('Audit Para Number', 'N/A')}, Date: {row.get('Record Created Date', 'N/A')})"
# #                             options_for_del.append(ident_str)
# #                             st.session_state.ag_deletable_map[ident_str] = {k: str(row.get(k)) for k in
# #                                                                             ["Trade Name", "Audit Para Number",
# #                                                                              "Record Created Date", "DAR PDF URL"]}
# #                         selected_entry_del_display = st.selectbox("Select Entry to Delete:", options_for_del,
# #                                                                   key=f"del_sel_{selected_del_period_key}")

# #                         if selected_entry_del_display != "--Select an entry--":
# #                             row_ident_data = st.session_state.ag_deletable_map.get(selected_entry_del_display)
# #                             if row_ident_data:
# #                                 st.warning(
# #                                     f"Selected to delete: **{row_ident_data.get('trade_name')} - Para {row_ident_data.get('audit_para_number')}** (Uploaded: {row_ident_data.get('record_created_date')})")
# #                                 with st.form(key=f"del_ag_form_{selected_entry_del_display.replace(' ', '_')}"):
# #                                     ag_pass = st.text_input("Your Password:", type="password",
# #                                                             key=f"ag_pass_del_{selected_entry_del_display.replace(' ', '_')}")
# #                                     submitted_del = st.form_submit_button("Confirm Deletion")
# #                                     if submitted_del:
# #                                         if ag_pass == USER_CREDENTIALS.get(st.session_state.username):
# #                                             current_sheet_df = read_from_spreadsheet(sheets_service, sheet_id_to_manage)
# #                                             if not current_sheet_df.empty:
# #                                                 indices_to_del_sheet = []
# #                                                 for sheet_idx, sheet_row in current_sheet_df.iterrows():
# #                                                     match = all([str(sheet_row.get('Audit Group Number')) == str(
# #                                                         st.session_state.audit_group_no),
# #                                                                  str(sheet_row.get('Trade Name')) == row_ident_data.get(
# #                                                                      'trade_name'), str(sheet_row.get(
# #                                                             'Audit Para Number')) == row_ident_data.get(
# #                                                             'audit_para_number'), str(sheet_row.get(
# #                                                             'Record Created Date')) == row_ident_data.get(
# #                                                             'record_created_date'), str(sheet_row.get(
# #                                                             'DAR PDF URL')) == row_ident_data.get('dar_pdf_url')])
# #                                                     if match: indices_to_del_sheet.append(sheet_idx)
# #                                                 if indices_to_del_sheet:
# #                                                     if delete_spreadsheet_rows(sheets_service, sheet_id_to_manage,
# #                                                                                first_sheet_gid, indices_to_del_sheet):
# #                                                         st.success(
# #                                                             f"Entry for '{row_ident_data.get('trade_name')}' deleted.");
# #                                                         time.sleep(0.5);
# #                                                         st.rerun()
# #                                                     else:
# #                                                         st.error("Failed to delete from sheet.")
# #                                                 else:
# #                                                     st.error(
# #                                                         "Could not find exact entry to delete. Might be already deleted/modified.")
# #                                             else:
# #                                                 st.error("Could not re-fetch sheet data for deletion.")
# #                                         else:
# #                                             st.error("Incorrect password.")
# #                             else:
# #                                 st.error("Could not retrieve details for selected entry.")
# #                     else:
# #                         st.info(f"You have no uploads in {selected_del_period_display} to delete.")
# #                 elif df_all_del.empty:
# #                     st.info(f"No data in MCM sheet for {selected_del_period_display}.")
# #                 else:
# #                     st.warning("Spreadsheet missing 'Audit Group Number' column.")
# #             elif not sheets_service:
# #                 st.error("Google Sheets service not available.")
# #     st.markdown("</div>", unsafe_allow_html=True)
