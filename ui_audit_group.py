# ui_audit_group.py
import streamlit as st
import datetime
import time
import pandas as pd
from io import BytesIO
from streamlit_option_menu import option_menu

# Assuming these utilities are correctly defined and imported
from google_utils import (
    load_mcm_periods, upload_to_drive, append_to_spreadsheet,
    read_from_spreadsheet, delete_spreadsheet_rows
)
from dar_processor import preprocess_pdf_text 
from gemini_utils import get_structured_data_with_gemini
from validation_utils import validate_data_for_sheet, VALID_CATEGORIES # Ensure VALID_CATEGORIES is imported if used
from config import USER_CREDENTIALS 

def audit_group_dashboard(drive_service, sheets_service):
    st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
                unsafe_allow_html=True)
    mcm_periods = load_mcm_periods(drive_service)
    active_periods = {k: v for k, v in mcm_periods.items() if v.get("active")}
    
    YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE") # Ensure this is fetched

    with st.sidebar:
        # Changed to use local logo.png
        try:
            st.image("logo.png", width=80)
        except Exception as e:
            st.sidebar.warning(f"Could not load logo.png: {e}")
            st.sidebar.markdown("*(Logo)*") # Fallback text

        st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}",
                    unsafe_allow_html=True)
        if st.button("Logout", key="ag_logout_styled", use_container_width=True):
            for key_to_del in ['ag_current_extracted_data', 'ag_pdf_drive_url', 'ag_validation_errors',
                               'ag_editor_data', 'ag_current_mcm_key', 'ag_current_uploaded_file_name',
                               'ag_row_to_delete_details', 'ag_show_delete_confirm', 'drive_structure_initialized']: # ensure all relevant keys are cleared
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
            period_options = {
                                 f"{p.get('month_name')} {p.get('year')}": k
                                 for k, p in sorted(active_periods.items(), reverse=True)
                                 if p.get('month_name') and p.get('year')
                             }
            if not period_options and active_periods:
                st.warning("Some active MCM periods have incomplete data (missing month/year) and are not shown as options.")
            
            selected_period_display = st.selectbox("Select Active MCM Period", options=list(period_options.keys()),
                                                   key="ag_select_mcm_upload_key") # Ensure unique key
            if selected_period_display:
                selected_mcm_key = period_options[selected_period_display]
                mcm_info = mcm_periods[selected_mcm_key]
                if st.session_state.get('ag_current_mcm_key') != selected_mcm_key:
                    st.session_state.ag_current_extracted_data = []
                    st.session_state.ag_pdf_drive_url = None
                    st.session_state.ag_validation_errors = []
                    st.session_state.ag_editor_data = pd.DataFrame() # Requires pandas
                    st.session_state.ag_current_mcm_key = selected_mcm_key
                    st.session_state.ag_current_uploaded_file_name = None
                st.info(f"Uploading for: {mcm_info['month_name']} {mcm_info['year']}")
                
                # Ensure uploader_key_suffix is initialized if used
                if 'uploader_key_suffix' not in st.session_state:
                    st.session_state.uploader_key_suffix = 0
                
                uploaded_dar_file = st.file_uploader("Choose DAR PDF", type="pdf",
                                                     key=f"dar_upload_ag_{selected_mcm_key}_{st.session_state.uploader_key_suffix}")

                if uploaded_dar_file:
                    if st.session_state.get('ag_current_uploaded_file_name') != uploaded_dar_file.name:
                        st.session_state.ag_current_extracted_data = []
                        st.session_state.ag_pdf_drive_url = None
                        st.session_state.ag_validation_errors = []
                        st.session_state.ag_editor_data = pd.DataFrame()
                        st.session_state.ag_current_uploaded_file_name = uploaded_dar_file.name

                    if st.button("Extract Data from PDF", key=f"extract_ag_btn_{selected_mcm_key}", use_container_width=True): # ensure unique key
                        st.session_state.ag_validation_errors = []
                        with st.spinner("Processing PDF & AI extraction..."):
                            dar_pdf_bytes = uploaded_dar_file.getvalue()
                            dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{uploaded_dar_file.name}"
                            st.session_state.ag_pdf_drive_url = None # Reset before upload attempt
                            
                            pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, dar_pdf_bytes,
                                                                               mcm_info['drive_folder_id'], dar_filename_on_drive)
                            if not pdf_drive_id:
                                st.error("Failed to upload PDF to Drive.");
                                st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry - PDF Upload Failed"}])
                            else:
                                st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
                                st.success(f"DAR PDF on Drive: [Link]({st.session_state.ag_pdf_drive_url})")
                                
                                preprocessed_text = preprocess_pdf_text(BytesIO(dar_pdf_bytes)) # Assuming preprocess_pdf_text is correctly imported
                                
                                if preprocessed_text.startswith("Error"): # Check for preprocessing error
                                    st.error(f"PDF Preprocessing Error: {preprocessed_text}");
                                    st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry - PDF Error"}])
                                else:
                                    # Assuming get_structured_data_with_gemini is correctly imported
                                    parsed_report_obj = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
                                    temp_list = []
                                    ai_failed = True # Assume failure unless proven otherwise
                                    
                                    if parsed_report_obj.parsing_errors: 
                                        st.warning(f"AI Parsing Issues: {parsed_report_obj.parsing_errors}")
                                    
                                    if parsed_report_obj and parsed_report_obj.header:
                                        h = parsed_report_obj.header
                                        ai_failed = False # Got header, so not a complete failure
                                        if parsed_report_obj.audit_paras: # If there are audit paras
                                            for p_data_item in parsed_report_obj.audit_paras: # Renamed p to p_data_item
                                                temp_list.append({
                                                    "audit_group_number": st.session_state.audit_group_no, 
                                                    "gstin": h.gstin, "trade_name": h.trade_name, "category": h.category, 
                                                    "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs, 
                                                    "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs, 
                                                    "audit_para_number": p_data_item.audit_para_number, 
                                                    "audit_para_heading": p_data_item.audit_para_heading, 
                                                    "revenue_involved_lakhs_rs": p_data_item.revenue_involved_lakhs_rs, 
                                                    "revenue_recovered_lakhs_rs": p_data_item.revenue_recovered_lakhs_rs
                                                })
                                        elif h.trade_name: # Header info present but no paras
                                            temp_list.append({
                                                "audit_group_number": st.session_state.audit_group_no, 
                                                "gstin": h.gstin, "trade_name": h.trade_name, "category": h.category, 
                                                "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs, 
                                                "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs, 
                                                "audit_para_number": None, # No para number
                                                "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)", # Special heading
                                                "revenue_involved_lakhs_rs": None, 
                                                "revenue_recovered_lakhs_rs": None
                                            })
                                        else: # Header info itself is problematic (e.g., no trade_name)
                                            st.error("AI failed to extract key header information (like Trade Name)."); 
                                            ai_failed = True
                                    
                                    if ai_failed or not temp_list: # If AI failed or produced an empty list
                                        st.warning("AI extraction failed or yielded no usable data. Please fill manually.")
                                        st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry Required"}])
                                    else: 
                                        st.session_state.ag_editor_data = pd.DataFrame(temp_list)
                                        st.info("Data extracted. Review & edit below.")
                
                if not isinstance(st.session_state.get('ag_editor_data'), pd.DataFrame): 
                    st.session_state.ag_editor_data = pd.DataFrame() # Ensure it's a DataFrame

                # This condition handles the case where PDF was uploaded, extraction ran, but editor_data is still empty.
                if uploaded_dar_file and st.session_state.ag_editor_data.empty and st.session_state.get('ag_pdf_drive_url'): 
                    st.warning("AI couldn't extract data or no data was previously loaded. A template row is provided for manual entry.")
                    st.session_state.ag_editor_data = pd.DataFrame([{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry"}])

                if not st.session_state.ag_editor_data.empty:
                    st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
                    df_to_edit_ag = st.session_state.ag_editor_data.copy()
                    df_to_edit_ag["audit_group_number"] = st.session_state.audit_group_no # Ensure group number is set
                    
                    col_order = ["audit_group_number", "gstin", "trade_name", "category", 
                                 "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs", 
                                 "audit_para_number", "audit_para_heading", 
                                 "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"]
                    
                    for col_name in col_order: # Ensure all columns exist
                        if col_name not in df_to_edit_ag.columns: 
                            df_to_edit_ag[col_name] = None 
                    
                    col_config = {
                        "audit_group_number": st.column_config.NumberColumn("Audit Group", disabled=True, help="Your Audit Group Number"),
                        "gstin": st.column_config.TextColumn("GSTIN", help="15-digit GSTIN"),
                        "trade_name": st.column_config.TextColumn("Trade Name"),
                        "category": st.column_config.SelectboxColumn("Category", options=VALID_CATEGORIES, required=False), # VALID_CATEGORIES should be imported
                        "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detected (Rs)", format="%.2f", help="Overall detection for the DAR"),
                        "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recovered (Rs)", format="%.2f", help="Overall recovery for the DAR"),
                        "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", help="Para number (integer)"),
                        "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
                        "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", help="Para-specific revenue involved in Lakhs Rs."),
                        "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", help="Para-specific revenue recovered in Lakhs Rs.")
                    }
                    
                    editor_key = f"ag_editor_form_{selected_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_uploaded'}" # ensure unique key
                    edited_df = st.data_editor(
                        df_to_edit_ag.reindex(columns=col_order), # Ensure consistent column order
                        column_config=col_config, 
                        num_rows="dynamic", 
                        key=editor_key, 
                        use_container_width=True, 
                        height=400
                    )

                    if st.button("Validate and Submit to MCM Sheet", key=f"submit_ag_data_{selected_mcm_key}", use_container_width=True): # ensure unique key
                        current_data_to_submit = pd.DataFrame(edited_df) # Use the output from data_editor
                        current_data_to_submit["audit_group_number"] = st.session_state.audit_group_no # Re-ensure audit group number
                        
                        val_errors = validate_data_for_sheet(current_data_to_submit) # Assuming validate_data_for_sheet is imported
                        st.session_state.ag_validation_errors = val_errors
                        
                        if not val_errors:
                            if not st.session_state.ag_pdf_drive_url: 
                                st.error("PDF Drive URL missing. Re-extract data or ensure PDF was uploaded successfully.")
                            else:
                                with st.spinner("Submitting to Google Sheet..."):
                                    rows_to_append = []
                                    created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    for _, row_item in current_data_to_submit.iterrows(): # Renamed 'row' to 'row_item'
                                        rows_to_append.append([row_item.get(c_name) for c_name in col_order] + [st.session_state.ag_pdf_drive_url, created_date])
                                    
                                    if rows_to_append:
                                        # Assuming append_to_spreadsheet is imported
                                        if append_to_spreadsheet(sheets_service, mcm_info['spreadsheet_id'], rows_to_append):
                                            st.success(f"Data for '{st.session_state.ag_current_uploaded_file_name}' submitted!"); 
                                            st.balloons(); 
                                            time.sleep(0.5)
                                            # Reset session state for next upload
                                            st.session_state.ag_current_extracted_data = []
                                            st.session_state.ag_pdf_drive_url = None
                                            st.session_state.ag_editor_data = pd.DataFrame()
                                            st.session_state.ag_current_uploaded_file_name = None
                                            st.session_state.uploader_key_suffix = st.session_state.get('uploader_key_suffix', 0) + 1
                                            st.rerun()
                                        else: 
                                            st.error("Failed to append to Google Sheet.")
                                    else: 
                                        st.error("No data to submit after validation (rows_to_append is empty).")
                        else: 
                            st.error("Validation Failed! Correct errors below.")
                
                if st.session_state.get('ag_validation_errors'):
                    st.markdown("---"); 
                    st.subheader("⚠️ Validation Errors:");
                    for err_msg in st.session_state.ag_validation_errors: # Renamed 'err' to 'err_msg'
                        st.warning(err_msg)

    elif selected_tab == "View My Uploaded DARs":
        st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
        if not mcm_periods: 
            st.info("No MCM periods by PCO yet.")
        else:
            all_period_options = {
                f"{p.get('month_name')} {p.get('year')}": k 
                for k,p in sorted(mcm_periods.items(),key=lambda item:item[0],reverse=True) 
                if p.get('month_name') and p.get('year')
            }
            if not all_period_options and mcm_periods: 
                st.warning("Some MCM periods have incomplete data and are not shown.")
            if not all_period_options: 
                st.info("No valid MCM periods found.")
            else:
                selected_view_period_display = st.selectbox("Select MCM Period", options=list(all_period_options.keys()), key="ag_view_my_dars_period_key") # Unique key

                if selected_view_period_display and sheets_service:
                    selected_view_period_key = all_period_options[selected_view_period_display]
                    sheet_id = mcm_periods[selected_view_period_key]['spreadsheet_id']
                    with st.spinner("Loading your uploads..."): 
                        df_all = read_from_spreadsheet(sheets_service, sheet_id) # Assuming read_from_spreadsheet is imported
                    
                    if not df_all.empty and 'Audit Group Number' in df_all.columns:
                        df_all['Audit Group Number'] = df_all['Audit Group Number'].astype(str) # Ensure consistent type for comparison
                        my_uploads_df = df_all[df_all['Audit Group Number'] == str(st.session_state.audit_group_no)]
                        
                        if not my_uploads_df.empty:
                            st.markdown(f"<h4>Your Uploads for {selected_view_period_display}:</h4>", unsafe_allow_html=True)
                            df_display = my_uploads_df.copy()
                            if 'DAR PDF URL' in df_display.columns: 
                                df_display['DAR PDF URL'] = df_display['DAR PDF URL'].apply(
                                    lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link"
                                )
                            view_cols = ["Trade Name", "Category", "Audit Para Number", "Audit Para Heading", "DAR PDF URL", "Record Created Date"]
                            existing_view_cols = [col for col in view_cols if col in df_display.columns] # Filter for existing columns
                            st.markdown(df_display[existing_view_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
                        else: 
                            st.info(f"No DARs uploaded by you for {selected_view_period_display}.")
                    elif df_all.empty: 
                        st.info(f"No data in MCM sheet for {selected_view_period_display}.")
                    else: # df_all not empty but 'Audit Group Number' column missing
                        st.warning("Spreadsheet missing 'Audit Group Number' column.")
                elif not sheets_service and selected_view_period_display: # If period selected but service is down
                    st.error("Google Sheets service not available.")


    elif selected_tab == "Delete My DAR Entries":
        st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
        st.info("Select MCM period to view entries. Deletion removes entry from Google Sheet; PDF on Drive remains.")
        if not mcm_periods: 
            st.info("No MCM periods created yet.")
        else:
            all_period_options_del = {
                f"{p.get('month_name')} {p.get('year')}": k 
                for k, p in sorted(mcm_periods.items(),key=lambda item:item[0],reverse=True) 
                if p.get('month_name') and p.get('year')
            }
            if not all_period_options_del and mcm_periods: 
                st.warning("Some MCM periods have incomplete data and are not shown.")
            
            selected_del_period_display = st.selectbox("Select MCM Period", options=list(all_period_options_del.keys()), key="ag_del_dars_period_key") # Unique key

            if selected_del_period_display and sheets_service:
                selected_del_period_key = all_period_options_del[selected_del_period_display]
                sheet_id_to_manage = mcm_periods[selected_del_period_key]['spreadsheet_id']
                first_sheet_gid = 0 # Default GID
                try:
                    meta = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_manage).execute()
                    first_sheet_gid = meta.get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
                except Exception as e_gid: 
                    st.error(f"Could not fetch sheet GID: {e_gid}")

                with st.spinner("Loading your uploads..."): 
                    df_all_del = read_from_spreadsheet(sheets_service, sheet_id_to_manage)
                
                if not df_all_del.empty and 'Audit Group Number' in df_all_del.columns:
                    df_all_del['Audit Group Number'] = df_all_del['Audit Group Number'].astype(str)
                    my_uploads_df_del = df_all_del[df_all_del['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
                    my_uploads_df_del.reset_index(inplace=True) # Keep original DataFrame index for internal mapping if needed later
                    my_uploads_df_del.rename(columns={'index': 'original_df_index'}, inplace=True) # Not strictly used here, but good practice

                    if not my_uploads_df_del.empty:
                        st.markdown(f"<h4>Your Uploads in {selected_del_period_display} (Select to delete):</h4>", unsafe_allow_html=True)
                        options_for_del = ["--Select an entry--"]
                        
                        # Initialize ag_deletable_map in session_state if not present
                        if 'ag_deletable_map' not in st.session_state:
                            st.session_state.ag_deletable_map = {}
                        else: # Clear map for the current selection context
                            st.session_state.ag_deletable_map.clear() 

                        for idx, row_data_item_del in my_uploads_df_del.iterrows(): # Renamed 'row'
                            ident_str = f"Entry (TN: {str(row_data_item_del.get('Trade Name', 'N/A'))[:20]}..., Para: {row_data_item_del.get('Audit Para Number', 'N/A')}, Date: {row_data_item_del.get('Record Created Date', 'N/A')})"
                            options_for_del.append(ident_str)
                            # Store identifiable data for matching
                            st.session_state.ag_deletable_map[ident_str] = {
                                "trade_name": str(row_data_item_del.get('Trade Name')),
                                "audit_para_number": str(row_data_item_del.get('Audit Para Number')), # Compare as strings
                                "record_created_date": str(row_data_item_del.get('Record Created Date')),
                                "dar_pdf_url": str(row_data_item_del.get('DAR PDF URL'))
                            }
                        
                        selected_entry_del_display = st.selectbox("Select Entry to Delete:", options_for_del, key=f"del_sel_box_{selected_del_period_key}") # Unique key

                        if selected_entry_del_display != "--Select an entry--":
                            row_ident_data = st.session_state.ag_deletable_map.get(selected_entry_del_display)
                            if row_ident_data:
                                st.warning(f"Selected to delete: **{row_ident_data.get('trade_name')} - Para {row_ident_data.get('audit_para_number')}** (Uploaded: {row_ident_data.get('record_created_date')})")
                                with st.form(key=f"del_ag_form_final_{selected_entry_del_display.replace(' ', '_')}"): # Unique key
                                    ag_pass = st.text_input("Your Password:", type="password", key=f"ag_pass_del_confirm_{selected_entry_del_display.replace(' ', '_')}") # Unique key
                                    submitted_del = st.form_submit_button("Confirm Deletion")
                                    
                                    if submitted_del:
                                        if ag_pass == USER_CREDENTIALS.get(st.session_state.username): # USER_CREDENTIALS should be imported
                                            current_sheet_df = read_from_spreadsheet(sheets_service, sheet_id_to_manage) # Re-fetch
                                            if not current_sheet_df.empty:
                                                indices_to_del_sheet = []
                                                # Exact matching against re-fetched data
                                                for sheet_idx, sheet_row_data in current_sheet_df.iterrows(): # Renamed 'sheet_row'
                                                    match_conditions = [
                                                        str(sheet_row_data.get('Audit Group Number')) == str(st.session_state.audit_group_no),
                                                        str(sheet_row_data.get('Trade Name')) == row_ident_data.get('trade_name'),
                                                        str(sheet_row_data.get('Audit Para Number')) == row_ident_data.get('audit_para_number'),
                                                        str(sheet_row_data.get('Record Created Date')) == row_ident_data.get('record_created_date'),
                                                        str(sheet_row_data.get('DAR PDF URL')) == row_ident_data.get('dar_pdf_url')
                                                    ]
                                                    if all(match_conditions): 
                                                        indices_to_del_sheet.append(sheet_idx) # 0-based index from read_from_spreadsheet (data part)
                                                
                                                if indices_to_del_sheet:
                                                    # Assuming delete_spreadsheet_rows is imported
                                                    if delete_spreadsheet_rows(sheets_service, sheet_id_to_manage, first_sheet_gid, indices_to_del_sheet):
                                                        st.success(f"Entry for '{row_ident_data.get('trade_name')}' deleted."); 
                                                        time.sleep(0.5); 
                                                        st.rerun()
                                                    else: 
                                                        st.error("Failed to delete from sheet.")
                                                else: 
                                                    st.error("Could not find exact entry to delete. It might have been already deleted or modified.")
                                            else: 
                                                st.error("Could not re-fetch sheet data for deletion verification.")
                                        else: 
                                            st.error("Incorrect password.")
                            else: 
                                st.error("Could not retrieve details for selected entry. Please re-select.")
                    else: 
                        st.info(f"You have no uploads in {selected_del_period_display} to delete.")
                elif df_all_del.empty: 
                    st.info(f"No data in MCM sheet for {selected_del_period_display}.")
                else: # df_all_del not empty but 'Audit Group Number' column missing
                    st.warning("Spreadsheet missing 'Audit Group Number' column.")
            elif not sheets_service and selected_del_period_display: # If period selected but service is down
                st.error("Google Sheets service not available.")

    st.markdown("</div>", unsafe_allow_html=True)# # ui_audit_group.py
# import streamlit as st
# import datetime
# import time
# import pandas as pd
# from io import BytesIO
# from streamlit_option_menu import option_menu

# from google_utils import (
#     load_mcm_periods, upload_to_drive, append_to_spreadsheet,
#     read_from_spreadsheet, delete_spreadsheet_rows
# )
# from dar_processor import preprocess_pdf_text  # Assuming dar_processor.py provides this
# from gemini_utils import get_structured_data_with_gemini
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES
# from config import USER_CREDENTIALS  # For password confirmation


# def audit_group_dashboard(drive_service, sheets_service):
#     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>",
#                 unsafe_allow_html=True)
#     mcm_periods = load_mcm_periods(drive_service)
#     active_periods = {k: v for k, v in mcm_periods.items() if v.get("active")}

#     # Fetch Gemini API Key from secrets
#     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

#     with st.sidebar:
#         st.image(
#             "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Indian_Ministry_of_Finance_logo.svg/1200px-Indian_Ministry_of_Finance_logo.svg.png",
#             width=80)
#         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}",
#                     unsafe_allow_html=True)
#         if st.button("Logout", key="ag_logout_styled", use_container_width=True):
#             for key_to_del in ['ag_current_extracted_data', 'ag_pdf_drive_url', 'ag_validation_errors',
#                                'ag_editor_data', 'ag_current_mcm_key', 'ag_current_uploaded_file_name',
#                                'ag_row_to_delete_details', 'ag_show_delete_confirm', 'drive_structure_initialized']:
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
#                 f"{p.get('month_name')} {p.get('year')}": k
#                 for k, p in sorted(active_periods.items(), reverse=True)
#                 if p.get('month_name') and p.get('year')
#             }
#             if not period_options and active_periods:
#                 st.warning(
#                     "Some active MCM periods have incomplete data (missing month/year) and are not shown as options.")

#             selected_period_display = st.selectbox("Select Active MCM Period", options=list(period_options.keys()),
#                                                    key="ag_select_mcm_upload")
#             if selected_period_display:
#                 selected_mcm_key = period_options[selected_period_display]
#                 mcm_info = mcm_periods[selected_mcm_key]
#                 if st.session_state.get('ag_current_mcm_key') != selected_mcm_key:
#                     st.session_state.ag_current_extracted_data = [];
#                     st.session_state.ag_pdf_drive_url = None
#                     st.session_state.ag_validation_errors = [];
#                     st.session_state.ag_editor_data = pd.DataFrame()
#                     st.session_state.ag_current_mcm_key = selected_mcm_key;
#                     st.session_state.ag_current_uploaded_file_name = None
#                 st.info(f"Uploading for: {mcm_info['month_name']} {mcm_info['year']}")
#                 uploaded_dar_file = st.file_uploader("Choose DAR PDF", type="pdf",
#                                                      key=f"dar_upload_ag_{selected_mcm_key}_{st.session_state.get('uploader_key_suffix', 0)}")

#                 if uploaded_dar_file:
#                     if st.session_state.get('ag_current_uploaded_file_name') != uploaded_dar_file.name:
#                         st.session_state.ag_current_extracted_data = [];
#                         st.session_state.ag_pdf_drive_url = None
#                         st.session_state.ag_validation_errors = [];
#                         st.session_state.ag_editor_data = pd.DataFrame()
#                         st.session_state.ag_current_uploaded_file_name = uploaded_dar_file.name

#                     if st.button("Extract Data from PDF", key=f"extract_ag_{selected_mcm_key}",
#                                  use_container_width=True):
#                         st.session_state.ag_validation_errors = []
#                         with st.spinner("Processing PDF & AI extraction..."):
#                             dar_pdf_bytes = uploaded_dar_file.getvalue()
#                             dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{uploaded_dar_file.name}"
#                             st.session_state.ag_pdf_drive_url = None
#                             pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, dar_pdf_bytes,
#                                                                                mcm_info['drive_folder_id'],
#                                                                                dar_filename_on_drive)
#                             if not pdf_drive_id:
#                                 st.error("Failed to upload PDF to Drive.");
#                                 st.session_state.ag_editor_data = pd.DataFrame([{
#                                                                                     "audit_group_number": st.session_state.audit_group_no,
#                                                                                     "audit_para_heading": "Manual Entry - PDF Upload Failed"}])
#                             else:
#                                 st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
#                                 st.success(f"DAR PDF on Drive: [Link]({st.session_state.ag_pdf_drive_url})")
#                                 preprocessed_text = preprocess_pdf_text(BytesIO(dar_pdf_bytes))
#                                 if preprocessed_text.startswith("Error"):
#                                     st.error(f"PDF Preprocessing Error: {preprocessed_text}");
#                                     st.session_state.ag_editor_data = pd.DataFrame([{
#                                                                                         "audit_group_number": st.session_state.audit_group_no,
#                                                                                         "audit_para_heading": "Manual Entry - PDF Error"}])
#                                 else:
#                                     parsed_report_obj = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY,
#                                                                                         preprocessed_text)
#                                     temp_list = []
#                                     ai_failed = True
#                                     if parsed_report_obj.parsing_errors: st.warning(
#                                         f"AI Parsing Issues: {parsed_report_obj.parsing_errors}")
#                                     if parsed_report_obj and parsed_report_obj.header:
#                                         h = parsed_report_obj.header;
#                                         ai_failed = False
#                                         if parsed_report_obj.audit_paras:
#                                             for p in parsed_report_obj.audit_paras: temp_list.append(
#                                                 {"audit_group_number": st.session_state.audit_group_no,
#                                                  "gstin": h.gstin, "trade_name": h.trade_name, "category": h.category,
#                                                  "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs,
#                                                  "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs,
#                                                  "audit_para_number": p.audit_para_number,
#                                                  "audit_para_heading": p.audit_para_heading,
#                                                  "revenue_involved_lakhs_rs": p.revenue_involved_lakhs_rs,
#                                                  "revenue_recovered_lakhs_rs": p.revenue_recovered_lakhs_rs})
#                                         elif h.trade_name:
#                                             temp_list.append({"audit_group_number": st.session_state.audit_group_no,
#                                                               "gstin": h.gstin, "trade_name": h.trade_name,
#                                                               "category": h.category,
#                                                               "total_amount_detected_overall_rs": h.total_amount_detected_overall_rs,
#                                                               "total_amount_recovered_overall_rs": h.total_amount_recovered_overall_rs,
#                                                               "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)"})
#                                         else:
#                                             st.error("AI failed to extract key header info."); ai_failed = True
#                                     if ai_failed or not temp_list:
#                                         st.warning("AI extraction failed or yielded no data. Please fill manually.")
#                                         st.session_state.ag_editor_data = pd.DataFrame([{
#                                                                                             "audit_group_number": st.session_state.audit_group_no,
#                                                                                             "audit_para_heading": "Manual Entry Required"}])
#                                     else:
#                                         st.session_state.ag_editor_data = pd.DataFrame(temp_list); st.info(
#                                             "Data extracted. Review & edit below.")

#                 if not isinstance(st.session_state.get('ag_editor_data'),
#                                   pd.DataFrame): st.session_state.ag_editor_data = pd.DataFrame()
#                 if uploaded_dar_file and st.session_state.ag_editor_data.empty and st.session_state.get(
#                         'ag_pdf_drive_url'):
#                     st.warning("AI couldn't extract data or none loaded. Template row provided.")
#                     st.session_state.ag_editor_data = pd.DataFrame(
#                         [{"audit_group_number": st.session_state.audit_group_no, "audit_para_heading": "Manual Entry"}])

#                 if not st.session_state.ag_editor_data.empty:
#                     st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
#                     df_to_edit_ag = st.session_state.ag_editor_data.copy();
#                     df_to_edit_ag["audit_group_number"] = st.session_state.audit_group_no
#                     col_order = ["audit_group_number", "gstin", "trade_name", "category",
#                                  "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#                                  "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
#                                  "revenue_recovered_lakhs_rs"]
#                     for col in col_order:
#                         if col not in df_to_edit_ag.columns: df_to_edit_ag[col] = None
#                     col_config = {"audit_group_number": st.column_config.NumberColumn("Audit Group", disabled=True),
#                                   "gstin": st.column_config.TextColumn("GSTIN"),
#                                   "trade_name": st.column_config.TextColumn("Trade Name"),
#                                   "category": st.column_config.SelectboxColumn("Category", options=VALID_CATEGORIES),
#                                   "total_amount_detected_overall_rs": st.column_config.NumberColumn(
#                                       "Total Detected (Rs)", format="%.2f"),
#                                   "total_amount_recovered_overall_rs": st.column_config.NumberColumn(
#                                       "Total Recovered (Rs)", format="%.2f"),
#                                   "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d"),
#                                   "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                                   "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)",
#                                                                                              format="%.2f"),
#                                   "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)",
#                                                                                               format="%.2f")}
#                     editor_key = f"ag_editor_{selected_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
#                     edited_df = st.data_editor(df_to_edit_ag.reindex(columns=col_order), column_config=col_config,
#                                                num_rows="dynamic", key=editor_key, use_container_width=True, height=400)

#                     if st.button("Validate and Submit to MCM Sheet", key=f"submit_ag_{selected_mcm_key}",
#                                  use_container_width=True):
#                         current_data = pd.DataFrame(edited_df);
#                         current_data["audit_group_number"] = st.session_state.audit_group_no
#                         val_errors = validate_data_for_sheet(current_data);
#                         st.session_state.ag_validation_errors = val_errors
#                         if not val_errors:
#                             if not st.session_state.ag_pdf_drive_url:
#                                 st.error("PDF Drive URL missing. Re-extract data.")
#                             else:
#                                 with st.spinner("Submitting to Google Sheet..."):
#                                     rows_to_append = []
#                                     created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                                     for _, row in current_data.iterrows(): rows_to_append.append(
#                                         [row.get(c) for c in col_order] + [st.session_state.ag_pdf_drive_url,
#                                                                            created_date])
#                                     if rows_to_append:
#                                         if append_to_spreadsheet(sheets_service, mcm_info['spreadsheet_id'],
#                                                                  rows_to_append):
#                                             st.success(
#                                                 f"Data for '{st.session_state.ag_current_uploaded_file_name}' submitted!");
#                                             st.balloons();
#                                             time.sleep(0.5)
#                                             st.session_state.ag_current_extracted_data = [];
#                                             st.session_state.ag_pdf_drive_url = None;
#                                             st.session_state.ag_editor_data = pd.DataFrame();
#                                             st.session_state.ag_current_uploaded_file_name = None
#                                             st.session_state.uploader_key_suffix = st.session_state.get(
#                                                 'uploader_key_suffix', 0) + 1;
#                                             st.rerun()
#                                         else:
#                                             st.error("Failed to append to Google Sheet.")
#                                     else:
#                                         st.error("No data to submit after validation.")
#                         else:
#                             st.error("Validation Failed! Correct errors below.")
#                 if st.session_state.get('ag_validation_errors'):
#                     st.markdown("---");
#                     st.subheader("⚠️ Validation Errors:");
#                     for err in st.session_state.ag_validation_errors: st.warning(err)

#     elif selected_tab == "View My Uploaded DARs":
#         st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
#         if not mcm_periods:
#             st.info("No MCM periods by PCO yet.")
#         else:
#             all_period_options = {f"{p.get('month_name')} {p.get('year')}": k for k, p in
#                                   sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if
#                                   p.get('month_name') and p.get('year')}
#             if not all_period_options and mcm_periods: st.warning(
#                 "Some MCM periods have incomplete data (missing month/year) and are not shown as options for viewing.")
#             if not all_period_options:
#                 st.info("No MCM periods found.")
#             else:
#                 selected_view_period_display = st.selectbox("Select MCM Period",
#                                                             options=list(all_period_options.keys()),
#                                                             key="ag_view_my_dars_period")
#                 if selected_view_period_display and sheets_service:
#                     selected_view_period_key = all_period_options[selected_view_period_display]
#                     sheet_id = mcm_periods[selected_view_period_key]['spreadsheet_id']
#                     with st.spinner("Loading your uploads..."):
#                         df_all = read_from_spreadsheet(sheets_service, sheet_id)
#                     if not df_all.empty and 'Audit Group Number' in df_all.columns:
#                         df_all['Audit Group Number'] = df_all['Audit Group Number'].astype(str)
#                         my_uploads_df = df_all[df_all['Audit Group Number'] == str(st.session_state.audit_group_no)]
#                         if not my_uploads_df.empty:
#                             st.markdown(f"<h4>Your Uploads for {selected_view_period_display}:</h4>",
#                                         unsafe_allow_html=True)
#                             df_display = my_uploads_df.copy()
#                             if 'DAR PDF URL' in df_display.columns: df_display['DAR PDF URL'] = df_display[
#                                 'DAR PDF URL'].apply(
#                                 lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(
#                                     x).startswith("http") else "No Link")
#                             view_cols = ["Trade Name", "Category", "Audit Para Number", "Audit Para Heading",
#                                          "DAR PDF URL", "Record Created Date"]
#                             st.markdown(df_display[view_cols].to_html(escape=False, index=False),
#                                         unsafe_allow_html=True)
#                         else:
#                             st.info(f"No DARs uploaded by you for {selected_view_period_display}.")
#                     elif df_all.empty:
#                         st.info(f"No data in MCM sheet for {selected_view_period_display}.")
#                     else:
#                         st.warning("Spreadsheet missing 'Audit Group Number' column.")
#                 elif not sheets_service:
#                     st.error("Google Sheets service not available.")

#     elif selected_tab == "Delete My DAR Entries":
#         st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#         st.info("Select MCM period to view entries. Deletion removes entry from Google Sheet; PDF on Drive remains.")
#         if not mcm_periods:
#             st.info("No MCM periods created yet.")
#         else:
#             all_period_options_del = {f"{p.get('month_name')} {p.get('year')}": k for k, p in
#                                       sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if
#                                       p.get('month_name') and p.get('year')}
#             if not all_period_options_del and mcm_periods: st.warning(
#                 "Some MCM periods have incomplete data (missing month/year) and are not shown as options for deletion.")
#             selected_del_period_display = st.selectbox("Select MCM Period", options=list(all_period_options_del.keys()),
#                                                        key="ag_del_dars_period")
#             if selected_del_period_display and sheets_service:
#                 selected_del_period_key = all_period_options_del[selected_del_period_display]
#                 sheet_id_to_manage = mcm_periods[selected_del_period_key]['spreadsheet_id']
#                 first_sheet_gid = 0
#                 try:
#                     meta = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_manage).execute()
#                     first_sheet_gid = meta.get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
#                 except Exception as e_gid:
#                     st.error(f"Could not fetch sheet GID: {e_gid}")

#                 with st.spinner("Loading your uploads..."):
#                     df_all_del = read_from_spreadsheet(sheets_service, sheet_id_to_manage)
#                 if not df_all_del.empty and 'Audit Group Number' in df_all_del.columns:
#                     df_all_del['Audit Group Number'] = df_all_del['Audit Group Number'].astype(str)
#                     my_uploads_df_del = df_all_del[
#                         df_all_del['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
#                     my_uploads_df_del.reset_index(inplace=True);
#                     my_uploads_df_del.rename(columns={'index': 'original_df_index'}, inplace=True)

#                     if not my_uploads_df_del.empty:
#                         st.markdown(f"<h4>Your Uploads in {selected_del_period_display} (Select to delete):</h4>",
#                                     unsafe_allow_html=True)
#                         options_for_del = ["--Select an entry--"]
#                         st.session_state.ag_deletable_map = {}
#                         for idx, row in my_uploads_df_del.iterrows():
#                             ident_str = f"Entry (TN: {str(row.get('Trade Name', 'N/A'))[:20]}..., Para: {row.get('Audit Para Number', 'N/A')}, Date: {row.get('Record Created Date', 'N/A')})"
#                             options_for_del.append(ident_str)
#                             st.session_state.ag_deletable_map[ident_str] = {k: str(row.get(k)) for k in
#                                                                             ["Trade Name", "Audit Para Number",
#                                                                              "Record Created Date", "DAR PDF URL"]}
#                         selected_entry_del_display = st.selectbox("Select Entry to Delete:", options_for_del,
#                                                                   key=f"del_sel_{selected_del_period_key}")

#                         if selected_entry_del_display != "--Select an entry--":
#                             row_ident_data = st.session_state.ag_deletable_map.get(selected_entry_del_display)
#                             if row_ident_data:
#                                 st.warning(
#                                     f"Selected to delete: **{row_ident_data.get('trade_name')} - Para {row_ident_data.get('audit_para_number')}** (Uploaded: {row_ident_data.get('record_created_date')})")
#                                 with st.form(key=f"del_ag_form_{selected_entry_del_display.replace(' ', '_')}"):
#                                     ag_pass = st.text_input("Your Password:", type="password",
#                                                             key=f"ag_pass_del_{selected_entry_del_display.replace(' ', '_')}")
#                                     submitted_del = st.form_submit_button("Confirm Deletion")
#                                     if submitted_del:
#                                         if ag_pass == USER_CREDENTIALS.get(st.session_state.username):
#                                             current_sheet_df = read_from_spreadsheet(sheets_service, sheet_id_to_manage)
#                                             if not current_sheet_df.empty:
#                                                 indices_to_del_sheet = []
#                                                 for sheet_idx, sheet_row in current_sheet_df.iterrows():
#                                                     match = all([str(sheet_row.get('Audit Group Number')) == str(
#                                                         st.session_state.audit_group_no),
#                                                                  str(sheet_row.get('Trade Name')) == row_ident_data.get(
#                                                                      'trade_name'), str(sheet_row.get(
#                                                             'Audit Para Number')) == row_ident_data.get(
#                                                             'audit_para_number'), str(sheet_row.get(
#                                                             'Record Created Date')) == row_ident_data.get(
#                                                             'record_created_date'), str(sheet_row.get(
#                                                             'DAR PDF URL')) == row_ident_data.get('dar_pdf_url')])
#                                                     if match: indices_to_del_sheet.append(sheet_idx)
#                                                 if indices_to_del_sheet:
#                                                     if delete_spreadsheet_rows(sheets_service, sheet_id_to_manage,
#                                                                                first_sheet_gid, indices_to_del_sheet):
#                                                         st.success(
#                                                             f"Entry for '{row_ident_data.get('trade_name')}' deleted.");
#                                                         time.sleep(0.5);
#                                                         st.rerun()
#                                                     else:
#                                                         st.error("Failed to delete from sheet.")
#                                                 else:
#                                                     st.error(
#                                                         "Could not find exact entry to delete. Might be already deleted/modified.")
#                                             else:
#                                                 st.error("Could not re-fetch sheet data for deletion.")
#                                         else:
#                                             st.error("Incorrect password.")
#                             else:
#                                 st.error("Could not retrieve details for selected entry.")
#                     else:
#                         st.info(f"You have no uploads in {selected_del_period_display} to delete.")
#                 elif df_all_del.empty:
#                     st.info(f"No data in MCM sheet for {selected_del_period_display}.")
#                 else:
#                     st.warning("Spreadsheet missing 'Audit Group Number' column.")
#             elif not sheets_service:
#                 st.error("Google Sheets service not available.")
#     st.markdown("</div>", unsafe_allow_html=True)
