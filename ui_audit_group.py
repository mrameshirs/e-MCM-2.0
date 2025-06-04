# ui_audit_group.py
import streamlit as st
import pandas as pd
import datetime
import math # For math.ceil
from io import BytesIO
import time

# Assuming these utilities are correctly defined and imported
from google_utils import (
    load_mcm_periods, upload_to_drive, append_to_spreadsheet,
    read_from_spreadsheet, delete_spreadsheet_rows
)
from dar_processor import preprocess_pdf_text
from gemini_utils import get_structured_data_with_gemini
from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
from config import USER_CREDENTIALS, AUDIT_GROUP_NUMBERS
from models import ParsedDARReport

from streamlit_option_menu import option_menu

# This defines the order and names of data columns that are extracted/edited
# and eventually form the core data for the Google Sheet.
SHEET_DATA_COLUMNS_ORDER = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading",
    "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para",
]

# This is the order for displaying columns in the st.data_editor UI (user's latest preference)
DISPLAY_COLUMN_ORDER = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading",
    "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs","status_of_para"
]

def calculate_audit_circle(audit_group_number_val):
    try:
        agn = int(audit_group_number_val)
        if 1 <= agn <= 30:
            return math.ceil(agn / 3.0)
        return None
    except (ValueError, TypeError, AttributeError):
        return None

def audit_group_dashboard(drive_service, sheets_service):
    st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
                unsafe_allow_html=True)
    mcm_periods_all = load_mcm_periods(drive_service)
    active_periods = {k: v for k, v in mcm_periods_all.items() if v.get("active")}

    YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE_FALLBACK")

    # --- Session State Initialization ---
    default_ag_states = {
        'ag_current_mcm_key': None,
        'ag_current_uploaded_file_obj': None,
        'ag_current_uploaded_file_name': None,
        'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER), # Base data after extraction
        'ag_pdf_drive_url': None,
        'ag_validation_errors': [],
        'ag_uploader_key_suffix': 0,
        # For delete tab
        'ag_row_to_delete_details': None,
        'ag_show_delete_confirm': False,
        'ag_deletable_map': {}
    }
    for key, value in default_ag_states.items():
        if key not in st.session_state:
            st.session_state[key] = value

    with st.sidebar:
        try: st.image("logo.png", width=80)
        except Exception: st.sidebar.markdown("*(Logo)*")
        st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
        if st.button("Logout", key="ag_logout_final_v4", use_container_width=True): # Changed key
            keys_to_clear = list(default_ag_states.keys()) + ['drive_structure_initialized']
            for ktd in keys_to_clear:
                if ktd in st.session_state: del st.session_state[ktd]
            st.session_state.logged_in = False; st.session_state.username = ""; st.session_state.role = ""; st.session_state.audit_group_no = None
            st.rerun()
        st.markdown("---")

    selected_tab = option_menu(
        menu_title=None, options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
        icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace", default_index=0, orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#e9ecef"}, "icon": {"color": "#28a745", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
            "nav-link-selected": {"background-color": "#28a745", "color": "white"},
        })
    st.markdown("<div class='card'>", unsafe_allow_html=True)

    # ========================== UPLOAD DAR FOR MCM TAB ==========================
    if selected_tab == "Upload DAR for MCM":
        st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
        if not active_periods:
            st.warning("No active MCM periods. Contact Planning Officer.")
        else:
            period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True) if v.get('month_name') and v.get('year')}
            period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
            current_mcm_display_val = period_options_disp_map.get(st.session_state.ag_current_mcm_key)
            
            selected_period_str = st.selectbox(
                "Select Active MCM Period", options=list(period_select_map_rev.keys()),
                index=list(period_select_map_rev.keys()).index(current_mcm_display_val) if current_mcm_display_val and current_mcm_display_val in period_select_map_rev else 0 if period_select_map_rev else None,
                key=f"ag_mcm_select_key_uploader_tab_{st.session_state.ag_uploader_key_suffix}" # Dynamic key to help reset uploader indirectly
            )

            if selected_period_str:
                new_mcm_key = period_select_map_rev[selected_period_str]
                mcm_info_current = active_periods[new_mcm_key]

                if st.session_state.ag_current_mcm_key != new_mcm_key:
                    st.session_state.ag_current_mcm_key = new_mcm_key
                    st.session_state.ag_current_uploaded_file_obj = None
                    st.session_state.ag_current_uploaded_file_name = None
                    st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER)
                    st.session_state.ag_pdf_drive_url = None
                    st.session_state.ag_validation_errors = []
                    st.session_state.ag_uploader_key_suffix += 1 # Crucial for resetting file_uploader
                    st.rerun()

                st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")

                uploaded_file = st.file_uploader("Choose DAR PDF", type="pdf",
                                                  key=f"ag_uploader_widget_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}")

                if uploaded_file:
                    if st.session_state.ag_current_uploaded_file_name != uploaded_file.name or st.session_state.ag_current_uploaded_file_obj is None:
                        st.session_state.ag_current_uploaded_file_obj = uploaded_file
                        st.session_state.ag_current_uploaded_file_name = uploaded_file.name
                        st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER) # Clear old data
                        st.session_state.ag_pdf_drive_url = None # Reset PDF URL as it's a new file context
                        st.session_state.ag_validation_errors = []
                        # Do not rerun here, let "Extract" button handle the action

                extract_button_key = f"extract_btn_final_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
                if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data from PDF", key=extract_button_key, use_container_width=True):
                    with st.spinner(f"Processing '{st.session_state.ag_current_uploaded_file_name}'... This might take time."):
                        pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
                        st.session_state.ag_pdf_drive_url = None # Reset for this extraction run
                        st.session_state.ag_validation_errors = [] # Clear previous errors

                        # Upload PDF to Drive *first* as per user's original successful flow
                        dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
                        pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, BytesIO(pdf_bytes),
                                                                           mcm_info_current['drive_folder_id'], dar_filename_on_drive)
                        
                        temp_list_for_df = []
                        if not pdf_drive_id:
                            st.error("Failed to upload PDF to Drive. Cannot proceed with extraction.")
                            temp_list_for_df = [{"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                            "audit_para_heading": "Manual Entry - PDF Upload Failed", "status_of_para": None}]
                        else:
                            st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
                            st.success(f"DAR PDF uploaded to Drive: [Link]({st.session_state.ag_pdf_drive_url})")
                            preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))

                            if preprocessed_text.startswith("Error"):
                                st.error(f"PDF Preprocessing Error: {preprocessed_text}")
                                temp_list_for_df = [{"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                                "audit_para_heading": "Manual Entry - PDF Error", "status_of_para": None}]
                            else:
                                parsed_data: ParsedDARReport = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
                                if parsed_data.parsing_errors: st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")

                                header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
                                base_info = {
                                    "audit_group_number": st.session_state.audit_group_no,
                                    "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                    "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
                                    "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
                                    "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs"),
                                }
                                if parsed_data.audit_paras:
                                    for para_obj in parsed_data.audit_paras:
                                        para_dict = para_obj.model_dump()
                                        row = base_info.copy(); row.update({k: para_dict.get(k) for k in ["audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para"]}); temp_list_for_df.append(row)
                                elif base_info.get("trade_name"):
                                    row = base_info.copy(); row.update({"audit_para_heading": "N/A - Header Info Only (Add Paras Manually)", "status_of_para": None}); temp_list_for_df.append(row)
                                else:
                                    st.error("AI failed key header info."); row = base_info.copy(); row.update({"audit_para_heading": "Manual Entry Required", "status_of_para": None}); temp_list_for_df.append(row)
                        
                        if not temp_list_for_df: # Fallback
                             temp_list_for_df.append({"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                                      "audit_para_heading": "Manual Entry - Extraction Issue", "status_of_para": None})
                        
                        df_extracted = pd.DataFrame(temp_list_for_df)
                        for col in DISPLAY_COLUMN_ORDER:
                            if col not in df_extracted.columns: df_extracted[col] = None
                        st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER] # Populate session state
                        st.success("Data extraction processed. Review and edit below.")
                        # NO st.rerun() here. Let natural flow update UI.

                # --- Data Editor and Submission ---
                # This section is displayed if st.session_state.ag_editor_data has been populated by extraction
                if not st.session_state.ag_editor_data.empty:
                    st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
                    
                    # The editor will use the current data in st.session_state.ag_editor_data
                    # When user edits, the editor widget handles the visual change.
                    # The output `edited_df_from_editor` captures the current state of the editor for THIS RUN.
                    # We will NOT immediately write this back to st.session_state.ag_editor_data here to mimic the no-blink behavior.
                    
                    df_for_editor_display = st.session_state.ag_editor_data.copy() # Pass a copy to editor for display

                    col_conf = {
                        "audit_group_number": st.column_config.NumberColumn(disabled=True), "audit_circle_number": st.column_config.NumberColumn(disabled=True),
                        "gstin": st.column_config.TextColumn(width="medium"), "trade_name": st.column_config.TextColumn(width="large"),
                        "category": st.column_config.SelectboxColumn(options=[None] + VALID_CATEGORIES, required=False, width="small"),
                        "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (Rs)", format="%.2f", width="medium"),
                        "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (Rs)", format="%.2f", width="medium"),
                        "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
                        "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
                        "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", width="small"),
                        "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", width="small"),
                        "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, required=False, width="medium")}
                    final_editor_col_conf = {k: v for k, v in col_conf.items() if k in DISPLAY_COLUMN_ORDER}

                    editor_instance_key = f"data_editor_instance_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
                    
                    # Capture the current state of the editor in a local variable for THIS script run
                    edited_data_from_editor_widget = st.data_editor(
                        df_for_editor_display, # Based on last extraction
                        column_config=final_editor_col_conf, num_rows="dynamic",
                        key=editor_instance_key,
                        use_container_width=True, hide_index=True, height=min(len(df_for_editor_display) * 50 + 60, 400) if not df_for_editor_display.empty else 200
                    )

                    if st.button("Validate and Submit to MCM Sheet", key=f"submit_final_data_btn_{st.session_state.ag_current_mcm_key}", use_container_width=True):
                        # Use the 'edited_data_from_editor_widget' which has the latest edits from the UI for this specific run
                        df_to_submit_final = pd.DataFrame(edited_data_from_editor_widget)
                        
                        df_to_submit_final["audit_group_number"] = st.session_state.audit_group_no
                        df_to_submit_final["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)

                        num_cols_to_convert = ["total_amount_detected_overall_rs", "total_amount_recovered_overall_rs", "audit_para_number", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"]
                        for nc in num_cols_to_convert:
                            if nc in df_to_submit_final.columns: df_to_submit_final[nc] = pd.to_numeric(df_to_submit_final[nc], errors='coerce')
                        
                        st.session_state.ag_validation_errors = validate_data_for_sheet(df_to_submit_final)

                        if not st.session_state.ag_validation_errors:
                            if not st.session_state.ag_pdf_drive_url: # Should have been set during extraction's PDF upload
                                st.error("PDF Drive URL missing. This indicates the PDF was not uploaded with the extraction step. Please re-extract data."); st.stop()

                            with st.spinner("Submitting to Google Sheet..."):
                                rows_for_sheet = []
                                submission_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                for sheet_col_name in SHEET_DATA_COLUMNS_ORDER: # Ensure all expected sheet data columns are present
                                    if sheet_col_name not in df_to_submit_final.columns:
                                        df_to_submit_final[sheet_col_name] = None
                                
                                for _, r_data_submit in df_to_submit_final.iterrows():
                                    sheet_row = [r_data_submit.get(col) for col in SHEET_DATA_COLUMNS_ORDER] + [st.session_state.ag_pdf_drive_url, submission_ts]
                                    rows_for_sheet.append(sheet_row)
                                
                                if rows_for_sheet:
                                    if append_to_spreadsheet(sheets_service, mcm_info_current['spreadsheet_id'], rows_for_sheet):
                                        st.success("Data submitted successfully!"); st.balloons(); time.sleep(1)
                                        st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
                                        st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER); st.session_state.ag_pdf_drive_url = None
                                        st.session_state.ag_validation_errors = []; st.session_state.ag_uploader_key_suffix += 1
                                        st.rerun()
                                    else: st.error("Failed to append to Google Sheet.")
                                else: st.error("No data rows to submit.")
                        else:
                            st.error("Validation Failed! Correct errors.");
                            if st.session_state.ag_validation_errors:
                                st.subheader("⚠️ Validation Errors:"); [st.warning(f"- {err}") for err in st.session_state.ag_validation_errors]
            elif not period_select_map_rev: st.info("No MCM periods available.")

    # ========================== VIEW MY UPLOADED DARS TAB ==========================
    elif selected_tab == "View My Uploaded DARs":
        st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
        if not mcm_periods_all: st.info("No MCM periods found.")
        else:
            view_period_opts_map = {k: f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(mcm_periods_all.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')}
            if not view_period_opts_map and mcm_periods_all: st.warning("Some MCM periods have incomplete data.")
            if not view_period_opts_map: st.info("No valid MCM periods to view.")
            else:
                sel_view_key = st.selectbox("Select MCM Period", options=list(view_period_opts_map.keys()), format_func=lambda k: view_period_opts_map[k], key="ag_view_sel_final")
                if sel_view_key and sheets_service:
                    view_sheet_id = mcm_periods_all[sel_view_key]['spreadsheet_id']
                    with st.spinner("Loading uploads..."): df_sheet_all = read_from_spreadsheet(sheets_service, view_sheet_id)
                    
                    if df_sheet_all is not None and not df_sheet_all.empty:
                        if 'Audit Group Number' in df_sheet_all.columns:
                            df_sheet_all['Audit Group Number'] = df_sheet_all['Audit Group Number'].astype(str)
                            my_uploads = df_sheet_all[df_sheet_all['Audit Group Number'] == str(st.session_state.audit_group_no)]
                            if not my_uploads.empty:
                                st.markdown(f"<h4>Your Uploads for {view_period_opts_map[sel_view_key]}:</h4>", unsafe_allow_html=True)
                                my_uploads_disp = my_uploads.copy()
                                if 'DAR PDF URL' in my_uploads_disp.columns:
                                    my_uploads_disp['DAR PDF URL Links'] = my_uploads_disp['DAR PDF URL'].apply(lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link")
                                
                                # Updated columns for viewing
                                cols_to_view = ["audit_circle_number", "gstin", "trade_name", "category", 
                                                "audit_para_number", "audit_para_heading", "status_of_para", 
                                                "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs",
                                                "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
                                                "DAR PDF URL Links", "Record Created Date"]
                                existing_cols_view = [c for c in cols_to_view if c in my_uploads_disp.columns]
                                st.markdown(my_uploads_disp[existing_cols_view].to_html(escape=False, index=False), unsafe_allow_html=True)
                            else: st.info(f"No DARs by you for {view_period_opts_map[sel_view_key]}.")
                        else: st.warning("Sheet missing 'Audit Group Number' column.")
                    elif df_sheet_all is None: st.error("Error reading spreadsheet for viewing.")
                    else: st.info(f"No data in sheet for {view_period_opts_map[sel_view_key]}.")
                elif not sheets_service and sel_view_key: st.error("Google Sheets service unavailable.")

    # ========================== DELETE MY DAR ENTRIES TAB ==========================
    elif selected_tab == "Delete My DAR Entries": # Using your existing logic, slightly tidied
        st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
        st.info("⚠️ This action is irreversible. Deletion removes entries from the Google Sheet; the PDF on Google Drive will remain.")
        if not mcm_periods_all: st.info("No MCM periods found.")
        else:
            del_period_opts_map = {k: f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(mcm_periods_all.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')}
            if not del_period_opts_map and mcm_periods_all: st.warning("Some MCM periods have incomplete data.")
            if not del_period_opts_map: st.info("No valid MCM periods to manage entries.")
            else:
                sel_del_key = st.selectbox("Select MCM Period", options=list(del_period_opts_map.keys()), format_func=lambda k: del_period_opts_map[k], key="ag_del_sel_final")
                if sel_del_key and sheets_service:
                    del_sheet_id = mcm_periods_all[sel_del_key]['spreadsheet_id']
                    del_sheet_gid = 0
                    try: del_sheet_gid = sheets_service.spreadsheets().get(spreadsheetId=del_sheet_id).execute().get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
                    except Exception as e_gid: st.error(f"Could not get sheet GID: {e_gid}"); st.stop()

                    with st.spinner("Loading entries..."): df_all_del_data = read_from_spreadsheet(sheets_service, del_sheet_id)
                    if df_all_del_data is not None and not df_all_del_data.empty:
                        if 'Audit Group Number' in df_all_del_data.columns:
                            df_all_del_data['Audit Group Number'] = df_all_del_data['Audit Group Number'].astype(str)
                            my_entries_del = df_all_del_data[df_all_del_data['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
                            my_entries_del['original_data_index'] = my_entries_del.index

                            if not my_entries_del.empty:
                                st.markdown(f"<h4>Your Uploads in {del_period_opts_map[sel_del_key]} (Select to delete):</h4>", unsafe_allow_html=True)
                                del_options_disp = ["--Select an entry to delete--"]
                                st.session_state.ag_deletable_map.clear()
                                for _, del_row in my_entries_del.iterrows(): # Using _ as index is not used in loop
                                    del_ident = f"TN: {str(del_row.get('Trade Name', 'N/A'))[:20]} | Para: {del_row.get('Audit Para Number', 'N/A')} | Date: {del_row.get('Record Created Date', 'N/A')}"
                                    del_options_disp.append(del_ident)
                                    st.session_state.ag_deletable_map[del_ident] = del_row['original_data_index'] # Map to DataFrame index
                                
                                sel_entry_del_str = st.selectbox("Select Entry:", options=del_options_disp, key=f"del_box_final_{sel_del_key}")
                                if sel_entry_del_str != "--Select an entry to delete--":
                                    orig_idx_to_del = st.session_state.ag_deletable_map.get(sel_entry_del_str)
                                    if orig_idx_to_del is not None:
                                        row_confirm_details = df_all_del_data.loc[orig_idx_to_del] # Use original DataFrame for confirmation
                                        st.warning(f"Confirm Deletion: TN: **{row_confirm_details.get('Trade Name')}**, Para: **{row_confirm_details.get('Audit Para Number')}**")
                                        with st.form(key=f"del_form_final_{orig_idx_to_del}"): # Ensure unique form key
                                            pwd = st.text_input("Password:", type="password", key=f"del_pwd_final_{orig_idx_to_del}")
                                            if st.form_submit_button("Yes, Delete This Entry"):
                                                if pwd == USER_CREDENTIALS.get(st.session_state.username):
                                                    # The orig_idx_to_del is the 0-based index from the DataFrame returned by read_from_spreadsheet.
                                                    # If read_from_spreadsheet correctly handles headers, this index corresponds to the data row.
                                                    if delete_spreadsheet_rows(sheets_service, del_sheet_id, del_sheet_gid, [orig_idx_to_del]):
                                                        st.success("Entry deleted."); time.sleep(1); st.rerun()
                                                    else: st.error("Failed to delete from sheet.")
                                                else: st.error("Incorrect password.")
                                    else: st.error("Could not identify selected entry. Please re-select.")
                            else: st.info(f"You have no entries in {del_period_opts_map[sel_del_key]} to delete.")
                        else: st.warning("Sheet missing 'Audit Group Number' column.")
                    elif df_all_del_data is None: st.error("Error reading sheet for deletion.")
                    else: st.info(f"No data in sheet for {del_period_opts_map[sel_del_key]}.")
                elif not sheets_service and sel_del_key: st.error("Google Sheets service unavailable.")

    st.markdown("</div>", unsafe_allow_html=True)# # ui_audit_group.py
# import streamlit as st
# import pandas as pd
# import datetime
# import math # For math.ceil
# from io import BytesIO
# import time

# # Assuming these utilities are correctly defined and imported
# from google_utils import (
#     load_mcm_periods, upload_to_drive, append_to_spreadsheet,
#     read_from_spreadsheet, delete_spreadsheet_rows
# )
# from dar_processor import preprocess_pdf_text
# from gemini_utils import get_structured_data_with_gemini
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# from config import USER_CREDENTIALS, AUDIT_GROUP_NUMBERS # AUDIT_GROUP_NUMBERS used for default group_no if needed
# from models import ParsedDARReport

# from streamlit_option_menu import option_menu


# # This should be the order of data columns for the Google Sheet
# # (excluding DAR PDF URL and Record Created Date which are added at the end of the list)
# SHEET_DATA_COLUMNS_ORDER = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
#     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading",
#     "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para",
# ]

# # This is the order for displaying columns in the st.data_editor UI
# # User has updated this order.
# DISPLAY_COLUMN_ORDER = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category","total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading",
#     "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs","status_of_para"
# ]


# def calculate_audit_circle(audit_group_number_val):
#     try:
#         agn = int(audit_group_number_val)
#         if 1 <= agn <= 30:
#             return math.ceil(agn / 3.0)
#         return None
#     except (ValueError, TypeError, AttributeError):
#         return None

# def audit_group_dashboard(drive_service, sheets_service):
#     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
#                 unsafe_allow_html=True)
#     mcm_periods_all = load_mcm_periods(drive_service) # Renamed from mcm_periods to avoid conflict
#     active_periods = {k: v for k, v in mcm_periods_all.items() if v.get("active")}

#     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

#     # --- Enhanced Session State Initialization ---
#     default_ag_states = {
#         'ag_current_mcm_key': None,
#         'ag_current_uploaded_file': None, # Store the UploadedFile object
#         'ag_current_uploaded_file_name': None,
#         'ag_editor_data': pd.DataFrame(), # Single source of truth for editor after load
#         'ag_pdf_drive_url': None,
#         'ag_validation_errors': [],
#         'ag_uploader_key_suffix': 0,
#         'ag_extraction_done_for_current_file': False, # Flag to control re-extraction
#         # For delete tab
#         'ag_row_to_delete_details': None,
#         'ag_show_delete_confirm': False,
#         'ag_deletable_map': {}
#     }
#     for key, value in default_ag_states.items():
#         if key not in st.session_state:
#             st.session_state[key] = value

#     with st.sidebar:
#         try:
#             st.image("logo.png", width=80)
#         except Exception as e:
#             st.sidebar.warning(f"Could not load logo.png: {e}")
#             st.sidebar.markdown("*(Logo)*")

#         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}",
#                     unsafe_allow_html=True)
#         if st.button("Logout", key="ag_logout_final", use_container_width=True): # Changed key
#             keys_to_clear_on_logout = list(default_ag_states.keys()) + ['drive_structure_initialized']
#             for key_to_del in keys_to_clear_on_logout:
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

#     # ========================== UPLOAD DAR FOR MCM TAB ==========================
#     if selected_tab == "Upload DAR for MCM":
#         st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
#         if not active_periods:
#             st.warning("No active MCM periods. Contact Planning Officer.")
#         else:
#             period_options_display_map = {
#                 k: f"{p.get('month_name')} {p.get('year')}"
#                 for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
#                 if p.get('month_name') and p.get('year')
#             }
#             period_options_select_map = {v: k for k, v in period_options_display_map.items()}

#             current_selection_display = None
#             if st.session_state.ag_current_mcm_key and st.session_state.ag_current_mcm_key in period_options_display_map:
#                 current_selection_display = period_options_display_map[st.session_state.ag_current_mcm_key]

#             selected_period_display_str = st.selectbox(
#                 "Select Active MCM Period",
#                 options=list(period_options_select_map.keys()),
#                 index=list(period_options_select_map.keys()).index(current_selection_display) if current_selection_display and current_selection_display in period_options_select_map else 0
#                       if period_options_select_map else None,
#                 key="ag_mcm_period_selectbox_final"
#             )

#             if selected_period_display_str:
#                 newly_selected_mcm_key = period_options_select_map[selected_period_display_str]
#                 mcm_info = active_periods[newly_selected_mcm_key] # Get info from active_periods

#                 if st.session_state.ag_current_mcm_key != newly_selected_mcm_key:
#                     st.session_state.ag_current_mcm_key = newly_selected_mcm_key
#                     st.session_state.ag_current_uploaded_file = None
#                     st.session_state.ag_current_uploaded_file_name = None
#                     st.session_state.ag_editor_data = pd.DataFrame()
#                     st.session_state.ag_pdf_drive_url = None
#                     st.session_state.ag_validation_errors = []
#                     st.session_state.ag_extraction_done_for_current_file = False
#                     st.session_state.ag_uploader_key_suffix += 1
#                     st.rerun()

#                 st.info(f"Uploading for: {mcm_info['month_name']} {mcm_info['year']}")

#                 uploaded_file_obj = st.file_uploader( # Renamed variable
#                     "Choose DAR PDF", type="pdf",
#                     key=f"dar_upload_ag_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
#                 )

#                 if uploaded_file_obj:
#                     if st.session_state.ag_current_uploaded_file_name != uploaded_file_obj.name or \
#                        st.session_state.ag_current_uploaded_file is None: # Handle initial upload or new file
#                         st.session_state.ag_current_uploaded_file = uploaded_file_obj
#                         st.session_state.ag_current_uploaded_file_name = uploaded_file_obj.name
#                         st.session_state.ag_editor_data = pd.DataFrame() # Clear old editor data
#                         st.session_state.ag_pdf_drive_url = None
#                         st.session_state.ag_validation_errors = []
#                         st.session_state.ag_extraction_done_for_current_file = False # Mark for re-extraction

#                     if st.button("Extract Data from PDF", key=f"extract_btn_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name}", use_container_width=True):
#                         st.session_state.ag_extraction_done_for_current_file = False # Reset to force extraction
#                         st.session_state.ag_editor_data = pd.DataFrame() # Clear editor before new extraction
#                         st.session_state.ag_validation_errors = []

#                     # Perform extraction if button was clicked OR if a new file is present and extraction wasn't done
#                     if not st.session_state.ag_extraction_done_for_current_file and st.session_state.ag_current_uploaded_file:
#                         with st.spinner(f"Processing '{st.session_state.ag_current_uploaded_file_name}'... This may take some time."):
#                             dar_pdf_bytes = st.session_state.ag_current_uploaded_file.getvalue()
#                             st.session_state.ag_pdf_drive_url = None # Reset for this extraction attempt

#                             preprocessed_text = preprocess_pdf_text(BytesIO(dar_pdf_bytes))
#                             parsed_data_obj: ParsedDARReport = None

#                             if preprocessed_text.startswith("Error"):
#                                 st.error(f"PDF Preprocessing Error: {preprocessed_text}")
#                                 temp_list = [{"audit_group_number": st.session_state.audit_group_no,
#                                               "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                               "audit_para_heading": "Manual Entry - PDF Error", "status_of_para": None}]
#                             else:
#                                 parsed_data_obj = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
#                                 temp_list = []
#                                 ai_parse_issue = False
#                                 if parsed_data_obj.parsing_errors:
#                                     st.warning(f"AI Parsing Issues: {parsed_data_obj.parsing_errors}")
#                                     ai_parse_issue = True

#                                 header_data = parsed_data_obj.header.model_dump() if parsed_data_obj.header else {}
#                                 base_row_info = {
#                                     "audit_group_number": st.session_state.audit_group_no,
#                                     "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                     "gstin": header_data.get("gstin"),
#                                     "trade_name": header_data.get("trade_name"),
#                                     "category": header_data.get("category"),
#                                     "total_amount_detected_overall_rs": header_data.get("total_amount_detected_overall_rs"),
#                                     "total_amount_recovered_overall_rs": header_data.get("total_amount_recovered_overall_rs"),
#                                 }

#                                 if parsed_data_obj.audit_paras:
#                                     for para_model in parsed_data_obj.audit_paras:
#                                         para_item = para_model.model_dump()
#                                         row = base_row_info.copy()
#                                         row.update({
#                                             "audit_para_number": para_item.get("audit_para_number"),
#                                             "audit_para_heading": para_item.get("audit_para_heading"),
#                                             "revenue_involved_lakhs_rs": para_item.get("revenue_involved_lakhs_rs"),
#                                             "revenue_recovered_lakhs_rs": para_item.get("revenue_recovered_lakhs_rs"),
#                                             "status_of_para": para_item.get("status_of_para")
#                                         })
#                                         temp_list.append(row)
#                                 elif base_row_info.get("trade_name"): # Header ok, no paras
#                                     row = base_row_info.copy()
#                                     row.update({"audit_para_number": None, "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)",
#                                                 "status_of_para": None})
#                                     temp_list.append(row)
#                                     if not ai_parse_issue: st.info("AI extracted header. No specific paras found. Add manually if needed.")
#                                 else: # AI failed header
#                                     st.error("AI failed to extract key header information. Manual entry template provided.")
#                                     row = base_row_info.copy()
#                                     row.update({"audit_para_heading": "Manual Entry Required", "status_of_para": None})
#                                     temp_list.append(row)

#                                 if not temp_list: # Should not happen if fallbacks are correct
#                                     temp_list.append({"audit_group_number": st.session_state.audit_group_no,
#                                                       "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                                       "audit_para_heading": "Manual Entry - Extraction Issue", "status_of_para": None})

#                             df_for_editor_init = pd.DataFrame(temp_list)
#                             for col_disp_order in DISPLAY_COLUMN_ORDER: # Ensure all display columns exist
#                                 if col_disp_order not in df_for_editor_init.columns:
#                                     df_for_editor_init[col_disp_order] = None
#                             st.session_state.ag_editor_data = df_for_editor_init[DISPLAY_COLUMN_ORDER]
#                             st.session_state.ag_extraction_done_for_current_file = True
#                             st.success("Data extraction complete. Please review and edit below.")
#                             # No st.rerun() here; let Streamlit flow naturally to display the editor
#                             # The editor will be displayed because ag_editor_data is no longer empty.

#                 # --- Data Editor Section ---
#                 if not st.session_state.ag_editor_data.empty:
#                     st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
#                     col_config_for_editor = {
#                         "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True, help="Your Audit Group Number"),
#                         "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True, help="Calculated Audit Circle"),
#                         "gstin": st.column_config.TextColumn("GSTIN", help="15-digit GSTIN", width="medium"),
#                         "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
#                         "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, required=False, width="small"),
#                         "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detected (Rs)", format="%.2f", help="Overall detection for the DAR", width="medium"),
#                         "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recovered (Rs)", format="%.2f", help="Overall recovery for the DAR", width="medium"),
#                         "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", help="Para number (integer)", width="small"),
#                         "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                         "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", help="Para-specific revenue involved in Lakhs Rs.", width="small"),
#                         "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", help="Para-specific revenue recovered in Lakhs Rs.", width="small"),
#                         "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, required=False, width="medium")
#                     }
#                     final_col_config = {k: v for k, v in col_config_for_editor.items() if k in DISPLAY_COLUMN_ORDER}

#                     # IMPORTANT: Assign the output of st.data_editor back to the session state variable
#                     st.session_state.ag_editor_data = pd.DataFrame(st.data_editor(
#                         st.session_state.ag_editor_data, # This DF is ordered by DISPLAY_COLUMN_ORDER
#                         column_config=final_col_config,
#                         num_rows="dynamic",
#                         key=f"data_editor_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name}",
#                         use_container_width=True,
#                         hide_index=True,
#                         height=400
#                     ))

#                     if st.button("Validate and Submit to MCM Sheet", key=f"submit_btn_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name}", use_container_width=True):
#                         data_for_submission = st.session_state.ag_editor_data.copy()

#                         # Ensure audit_group_number and audit_circle_number are correctly set from session state before validation/submission
#                         data_for_submission["audit_group_number"] = st.session_state.audit_group_no
#                         data_for_submission["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)

#                         # Convert potential string numbers from editor to numeric before validation
#                         numeric_cols_for_validation = [
#                             "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#                             "audit_para_number", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"
#                         ]
#                         for num_col_val in numeric_cols_for_validation:
#                             if num_col_val in data_for_submission.columns:
#                                 data_for_submission[num_col_val] = pd.to_numeric(data_for_submission[num_col_val], errors='coerce')


#                         st.session_state.ag_validation_errors = validate_data_for_sheet(data_for_submission)

#                         if not st.session_state.ag_validation_errors:
#                             # PDF Upload to Drive (if not already successfully done for this file)
#                             if not st.session_state.ag_pdf_drive_url and st.session_state.ag_current_uploaded_file:
#                                 with st.spinner("Uploading PDF to Google Drive..."):
#                                     pdf_bytes_final_upload = st.session_state.ag_current_uploaded_file.getvalue()
#                                     final_dar_filename = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
#                                     pdf_id, pdf_url = upload_to_drive(
#                                         drive_service, BytesIO(pdf_bytes_final_upload),
#                                         mcm_info['drive_folder_id'], final_dar_filename
#                                     )
#                                     if not pdf_id:
#                                         st.error("Critical: Failed to upload PDF to Drive during submission. Cannot proceed.")
#                                         st.stop()
#                                     st.session_state.ag_pdf_drive_url = pdf_url
#                                     st.success(f"PDF for submission confirmed on Drive: [Link]({pdf_url})")
#                             elif not st.session_state.ag_pdf_drive_url: # Should have been uploaded during extraction
#                                  st.error("PDF Drive URL is missing. Please re-extract data to ensure PDF is uploaded first.")
#                                  st.stop()


#                             with st.spinner("Preparing and submitting data to Google Sheet..."):
#                                 rows_to_append_final = []
#                                 submission_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#                                 # Ensure all SHEET_DATA_COLUMNS_ORDER are present before iterating
#                                 for sheet_col_final in SHEET_DATA_COLUMNS_ORDER:
#                                     if sheet_col_final not in data_for_submission.columns:
#                                         data_for_submission[sheet_col_final] = None

#                                 for _, submission_row in data_for_submission.iterrows():
#                                     row_values_for_sheet = [submission_row.get(col) for col in SHEET_DATA_COLUMNS_ORDER]
#                                     row_values_for_sheet.extend([st.session_state.ag_pdf_drive_url, submission_timestamp])
#                                     rows_to_append_final.append(row_values_for_sheet)

#                                 if rows_to_append_final:
#                                     if append_to_spreadsheet(sheets_service, mcm_info['spreadsheet_id'], rows_to_append_final):
#                                         st.success(f"Data for '{st.session_state.ag_current_uploaded_file_name}' submitted successfully!")
#                                         st.balloons()
#                                         time.sleep(1.5) # Allow user to see success
#                                         # Reset for next file
#                                         st.session_state.ag_current_uploaded_file = None
#                                         st.session_state.ag_current_uploaded_file_name = None
#                                         st.session_state.ag_editor_data = pd.DataFrame()
#                                         st.session_state.ag_pdf_drive_url = None
#                                         st.session_state.ag_validation_errors = []
#                                         st.session_state.ag_extraction_done_for_current_file = False
#                                         st.session_state.ag_uploader_key_suffix += 1
#                                         st.rerun()
#                                     else:
#                                         st.error("Failed to append data to Google Sheet.")
#                                 else:
#                                     st.error("No valid data rows to submit.")
#                         else:
#                             st.error("Validation Failed! Please correct the errors indicated.")
#                             if st.session_state.ag_validation_errors:
#                                 st.subheader("⚠️ Validation Errors:")
#                                 for err in st.session_state.ag_validation_errors: st.warning(f"- {err}")
#             elif not period_options_select_map: # Should be period_options_display_map
#                  st.info("No MCM periods available for selection.")


#     # ========================== VIEW MY UPLOADED DARS TAB ==========================
#     elif selected_tab == "View My Uploaded DARs":
#         st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
#         if not mcm_periods_all:
#             st.info("No MCM periods found. Contact PCO.")
#         else:
#             all_period_options_view = {
#                 k: f"{p.get('month_name')} {p.get('year')}"
#                 for k, p in sorted(mcm_periods_all.items(), key=lambda item: item[0], reverse=True)
#                 if p.get('month_name') and p.get('year')
#             }
#             if not all_period_options_view and mcm_periods_all:
#                 st.warning("Some MCM periods have incomplete data (missing month/year) and are not shown.")

#             if not all_period_options_view:
#                 st.info("No valid MCM periods found to view uploads.")
#             else:
#                 selected_view_period_key_disp = st.selectbox(
#                     "Select MCM Period to View Your Uploads",
#                     options=list(all_period_options_view.keys()),
#                     format_func=lambda k: all_period_options_view[k],
#                     key="ag_view_my_dars_selectbox"
#                 )

#                 if selected_view_period_key_disp and sheets_service:
#                     sheet_id_view = mcm_periods_all[selected_view_period_key_disp]['spreadsheet_id']
#                     with st.spinner("Loading your uploads..."):
#                         df_all_uploads = read_from_spreadsheet(sheets_service, sheet_id_view)

#                     if df_all_uploads is not None and not df_all_uploads.empty:
#                         if 'Audit Group Number' in df_all_uploads.columns:
#                             df_all_uploads['Audit Group Number'] = df_all_uploads['Audit Group Number'].astype(str)
#                             my_group_uploads_df = df_all_uploads[df_all_uploads['Audit Group Number'] == str(st.session_state.audit_group_no)]

#                             if not my_group_uploads_df.empty:
#                                 st.markdown(f"<h4>Your Uploads for {all_period_options_view[selected_view_period_key_disp]}:</h4>", unsafe_allow_html=True)
#                                 df_display_my_uploads = my_group_uploads_df.copy()
#                                 if 'DAR PDF URL' in df_display_my_uploads.columns:
#                                     df_display_my_uploads['DAR PDF URL'] = df_display_my_uploads['DAR PDF URL'].apply(
#                                         lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link"
#                                     )
#                                 view_cols_my_uploads = [ # Updated to include new columns
#                                     "audit_circle_number", "gstin", "trade_name", "category",
#                                     "audit_para_number", "audit_para_heading", "status_of_para",
#                                     "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs",
#                                     "DAR PDF URL", "Record Created Date"
#                                 ]
#                                 existing_display_cols = [col for col in view_cols_my_uploads if col in df_display_my_uploads.columns]
#                                 st.markdown(df_display_my_uploads[existing_display_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
#                             else:
#                                 st.info(f"No DARs uploaded by you for {all_period_options_view[selected_view_period_key_disp]}.")
#                         else:
#                             st.warning("Spreadsheet is missing the 'Audit Group Number' column. Cannot filter your uploads.")
#                     elif df_all_uploads is None:
#                         st.error("Error reading spreadsheet data for viewing uploads.")
#                     else: # df_all_uploads is empty
#                         st.info(f"No data found in the spreadsheet for {all_period_options_view[selected_view_period_key_disp]}.")
#                 elif not sheets_service and selected_view_period_key_disp:
#                     st.error("Google Sheets service not available.")

#     # ========================== DELETE MY DAR ENTRIES TAB ==========================
#     elif selected_tab == "Delete My DAR Entries":
#         st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#         st.info("⚠️ This action is irreversible. Deletion removes entries from the Google Sheet; the PDF on Google Drive will remain.")
#         if not mcm_periods_all:
#             st.info("No MCM periods found. Contact PCO.")
#         else:
#             all_period_options_delete = {
#                 k: f"{p.get('month_name')} {p.get('year')}"
#                 for k, p in sorted(mcm_periods_all.items(), key=lambda item: item[0], reverse=True)
#                 if p.get('month_name') and p.get('year')
#             }
#             if not all_period_options_delete and mcm_periods_all:
#                 st.warning("Some MCM periods have incomplete data (missing month/year) and are not shown.")

#             if not all_period_options_delete:
#                 st.info("No valid MCM periods found to manage entries.")
#             else:
#                 selected_delete_period_key_disp = st.selectbox(
#                     "Select MCM Period to Manage Your Entries",
#                     options=list(all_period_options_delete.keys()),
#                     format_func=lambda k: all_period_options_delete[k],
#                     key="ag_delete_dars_selectbox"
#                 )

#                 if selected_delete_period_key_disp and sheets_service:
#                     sheet_id_for_delete = mcm_periods_all[selected_delete_period_key_disp]['spreadsheet_id']
#                     first_sheet_gid_delete = 0
#                     try:
#                         meta_delete = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_for_delete).execute()
#                         first_sheet_gid_delete = meta_delete.get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
#                     except Exception as e_gid_del:
#                         st.error(f"Could not fetch sheet GID for deletion: {e_gid_del}")
#                         st.stop() # Stop if GID cannot be fetched

#                     with st.spinner("Loading your uploads for potential deletion..."):
#                         df_all_for_delete = read_from_spreadsheet(sheets_service, sheet_id_for_delete)

#                     if df_all_for_delete is not None and not df_all_for_delete.empty:
#                         if 'Audit Group Number' in df_all_for_delete.columns:
#                             df_all_for_delete['Audit Group Number'] = df_all_for_delete['Audit Group Number'].astype(str)
#                             my_entries_for_delete_df = df_all_for_delete[df_all_for_delete['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
#                             my_entries_for_delete_df['original_data_index'] = my_entries_for_delete_df.index # This is df index, not necessarily sheet row index

#                             if not my_entries_for_delete_df.empty:
#                                 st.markdown(f"<h4>Your Uploads in {all_period_options_delete[selected_delete_period_key_disp]} (Select to delete):</h4>", unsafe_allow_html=True)
#                                 options_for_delete_display = ["--Select an entry to delete--"]
#                                 st.session_state.ag_deletable_map.clear()

#                                 for _, row_to_delete in my_entries_for_delete_df.iterrows():
#                                     ident_str_delete = (
#                                         f"TN: {str(row_to_delete.get('Trade Name', 'N/A'))[:25]}..., "
#                                         f"Para: {row_to_delete.get('Audit Para Number', 'N/A')}, "
#                                         f"DAR URL: ...{str(row_to_delete.get('DAR PDF URL', 'N/A'))[-20:]}, " # Show end of URL
#                                         f"Date: {row_to_delete.get('Record Created Date', 'N/A')}"
#                                     )
#                                     options_for_delete_display.append(ident_str_delete)
#                                     st.session_state.ag_deletable_map[ident_str_delete] = row_to_delete['original_data_index']

#                                 selected_entry_to_delete_display_str = st.selectbox(
#                                     "Select Entry to Delete:", options=options_for_delete_display,
#                                     key=f"delete_selectbox_final_{selected_delete_period_key_disp}"
#                                 )

#                                 if selected_entry_to_delete_display_str != "--Select an entry to delete--":
#                                     original_df_idx_to_delete = st.session_state.ag_deletable_map.get(selected_entry_to_delete_display_str)
#                                     if original_df_idx_to_delete is not None:
#                                         # Confirm row details based on the full DataFrame read from the sheet
#                                         row_details = df_all_for_delete.loc[original_df_idx_to_delete]
#                                         st.warning(f"Confirm Deletion: Trade Name: **{row_details.get('Trade Name')}**, Para: **{row_details.get('Audit Para Number')}**, Uploaded: **{row_details.get('Record Created Date')}**")

#                                         with st.form(key=f"delete_confirm_form_final_{original_df_idx_to_delete}"):
#                                             user_password_confirm = st.text_input("Your Password:", type="password", key=f"del_pass_final_{original_df_idx_to_delete}")
#                                             submitted_final_delete = st.form_submit_button("Yes, Delete This Entry Permanently")

#                                             if submitted_final_delete:
#                                                 if user_password_confirm == USER_CREDENTIALS.get(st.session_state.username):
#                                                     # The original_df_idx_to_delete is the 0-based index from the DataFrame
#                                                     # returned by read_from_spreadsheet. If this function correctly handles
#                                                     # headers, this index corresponds to the data row.
#                                                     if delete_spreadsheet_rows(sheets_service, sheet_id_for_delete, first_sheet_gid_delete, [original_df_idx_to_delete]):
#                                                         st.success("Entry deleted successfully.")
#                                                         time.sleep(1)
#                                                         st.rerun()
#                                                     else:
#                                                         st.error("Failed to delete entry from Google Sheet.")
#                                                 else:
#                                                     st.error("Incorrect password. Deletion aborted.")
#                                     else:
#                                         st.error("Could not identify the selected entry. Please refresh and try again.")
#                             else:
#                                 st.info(f"You have no entries in {all_period_options_delete[selected_delete_period_key_disp]} to delete.")
#                         else:
#                             st.warning("Spreadsheet is missing 'Audit Group Number' column.")
#                     elif df_all_for_delete is None:
#                         st.error("Error reading spreadsheet data for deletion.")
#                     else: # df_all_for_delete is empty
#                         st.info(f"No data found in spreadsheet for {all_period_options_delete[selected_delete_period_key_disp]}.")
#                 elif not sheets_service and selected_delete_period_key_disp:
#                     st.error("Google Sheets service not available.")

#     st.markdown("</div>", unsafe_allow_html=True)
