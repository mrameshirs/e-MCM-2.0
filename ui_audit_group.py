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
SHEET_DATA_COLUMNS_ORDER = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading",
    "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para",
]
# --- Caching helper for MCM Periods ---
def get_cached_mcm_periods_ag(drive_service, ttl_seconds=120):
    cache_key_data = 'ag_ui_cached_mcm_periods_data'
    cache_key_ts = 'ag_ui_cached_mcm_periods_timestamp'
    current_time = time.time()
    if (cache_key_data in st.session_state and
            cache_key_ts in st.session_state and
            (current_time - st.session_state[cache_key_ts] < ttl_seconds)):
        return st.session_state[cache_key_data]
    periods = load_mcm_periods(drive_service)
    st.session_state[cache_key_data] = periods
    st.session_state[cache_key_ts] = current_time
    return periods
# --- End Caching helper ---

# Column names as they are in the DataFrame returned by read_from_spreadsheet (matching expected_cols_header in google_utils)
# These are Title Cased
SHEET_COLUMN_NAMES = [
    "Audit Group Number", "Audit Circle Number", "GSTIN", "Trade Name", "Category",
    "Total Amount Detected (Overall Rs)", "Total Amount Recovered (Overall Rs)",
    "Audit Para Number", "Audit Para Heading",
    "Revenue Involved (Lakhs Rs)", "Revenue Recovered (Lakhs Rs)", "Status of para",
    "DAR PDF URL", "Record Created Date" # These are added by append logic or already in sheet
]


# For st.data_editor, keys should match DataFrame columns after extraction (lowercase_with_underscore)
# This list is used for data creation before it goes into the sheet.
# The sheet saving logic then maps these to the SHEET_COLUMN_NAMES order if needed,
# but append_to_spreadsheet just takes a list of lists.
# The `st.data_editor` in the "Upload" tab uses lowercase_with_underscore keys for its `column_config`.
INTERNAL_DF_COLUMNS_FOR_EDIT = [ # Used by editor and for preparing data structure from extraction
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading",
    "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para",
]

# Display order for the editor in "Upload DAR" tab
DISPLAY_COLUMN_ORDER_EDITOR = [
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
    
    mcm_periods_all = get_cached_mcm_periods_ag(drive_service)
    active_periods = {k: v for k, v in mcm_periods_all.items() if v.get("active")}

    YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE_FALLBACK")

    default_ag_states = {
        'ag_current_mcm_key': None,
        'ag_current_uploaded_file_obj': None,
        'ag_current_uploaded_file_name': None,
        'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR), # For the editor
        'ag_pdf_drive_url': None,
        'ag_validation_errors': [],
        'ag_uploader_key_suffix': 0,
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
        if st.button("Logout", key="ag_logout_full_v5", use_container_width=True):
            keys_to_clear = list(default_ag_states.keys()) + ['drive_structure_initialized', 'ag_ui_cached_mcm_periods_data', 'ag_ui_cached_mcm_periods_timestamp']
            for ktd in keys_to_clear:
                if ktd in st.session_state: del st.session_state[ktd]
            st.session_state.logged_in = False; st.session_state.username = ""; st.session_state.role = ""; st.session_state.audit_group_no = None
            st.rerun()
        st.markdown("---")
    # --- Smart Audit Tracker Button in Sidebar ---
        st.markdown(
            """
            <style>
            .stButton>button {
                background-image: linear-gradient(to right, #1D976C 0%, #93F9B9  51%, #1D976C  100%);
                color: white;
                padding: 15px 30px;
                text-align: center;
                text-transform: uppercase;
                transition: 0.5s;
                background-size: 200% auto;
                border: none;
                border-radius: 10px;
                display: block;
                font-weight: bold;
                width: 100%;
            }
            .stButton>button:hover {
                background-position: right center;
                color: #fff;
                text-decoration: none;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        if st.button("🚀 Smart Audit Tracker", key="launch_sat_ag"):
            st.session_state.app_mode = "smart_audit_tracker"
            st.rerun()
        st.markdown("---")
    selected_tab = option_menu(menu_title="e-MCM Menu",
         options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
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
                key=f"ag_mcm_sel_uploader_tab_final_{st.session_state.ag_uploader_key_suffix}"
            )

            if selected_period_str:
                new_mcm_key = period_select_map_rev[selected_period_str]
                mcm_info_current = active_periods[new_mcm_key]

                if st.session_state.ag_current_mcm_key != new_mcm_key:
                    st.session_state.ag_current_mcm_key = new_mcm_key
                    st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
                    st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR); st.session_state.ag_pdf_drive_url = None
                    st.session_state.ag_validation_errors = []; st.session_state.ag_uploader_key_suffix += 1
                    st.rerun()

                st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
                uploaded_file = st.file_uploader("Choose DAR PDF", type="pdf", key=f"ag_uploader_main_final_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}")

                if uploaded_file:
                    if st.session_state.ag_current_uploaded_file_name != uploaded_file.name or st.session_state.ag_current_uploaded_file_obj is None:
                        st.session_state.ag_current_uploaded_file_obj = uploaded_file; st.session_state.ag_current_uploaded_file_name = uploaded_file.name
                        st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR); st.session_state.ag_pdf_drive_url = None
                        st.session_state.ag_validation_errors = []
                        # st.rerun() # Avoid rerun here, let extract button control flow

                extract_button_key = f"extract_data_btn_final_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_yet'}"
                if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data from PDF", key=extract_button_key, use_container_width=True):
                    with st.spinner(f"Processing '{st.session_state.ag_current_uploaded_file_name}'... This might take a moment."):
                        pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
                        st.session_state.ag_pdf_drive_url = None 
                        st.session_state.ag_validation_errors = []

                        dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
                        pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, BytesIO(pdf_bytes),
                                                                           mcm_info_current['drive_folder_id'], dar_filename_on_drive)
                        temp_list_for_df = []
                        if not pdf_drive_id:
                            st.error("Failed to upload PDF to Drive. Cannot proceed with extraction.")
                            base_row_manual = {col: None for col in INTERNAL_DF_COLUMNS_FOR_EDIT}
                            base_row_manual.update({"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no), "audit_para_heading": "Manual Entry - PDF Upload Failed"})
                            temp_list_for_df.append(base_row_manual)
                        else:
                            st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
                            st.success(f"DAR PDF uploaded to Drive: [Link]({st.session_state.ag_pdf_drive_url})")
                            preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))

                            if preprocessed_text.startswith("Error"):
                                st.error(f"PDF Preprocessing Error: {preprocessed_text}")
                                base_row_manual = {col: None for col in INTERNAL_DF_COLUMNS_FOR_EDIT}
                                base_row_manual.update({"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no), "audit_para_heading": "Manual Entry - PDF Error"})
                                temp_list_for_df.append(base_row_manual)
                            else:
                                parsed_data: ParsedDARReport = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
                                if parsed_data.parsing_errors: st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")

                                header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
                                base_info = { # Use INTERNAL_DF_COLUMNS_FOR_EDIT (lowercase_underscore)
                                    "audit_group_number": st.session_state.audit_group_no,
                                    "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                                    "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
                                    "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
                                    "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs"),
                                }
                                if parsed_data.audit_paras:
                                    for para_obj in parsed_data.audit_paras:
                                        para_dict = para_obj.model_dump(); row = base_info.copy(); row.update({k: para_dict.get(k) for k in ["audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para"]}); temp_list_for_df.append(row)
                                elif base_info.get("trade_name"):
                                    row = base_info.copy(); row.update({"audit_para_number": None, "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)", "status_of_para": None}); temp_list_for_df.append(row)
                                else:
                                    st.error("AI failed key header info."); row = base_info.copy(); row.update({"audit_para_heading": "Manual Entry Required", "status_of_para": None}); temp_list_for_df.append(row)
                        
                        if not temp_list_for_df: 
                             base_row_manual = {col: None for col in INTERNAL_DF_COLUMNS_FOR_EDIT}
                             base_row_manual.update({"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no), "audit_para_heading": "Manual Entry - Extraction Issue"})
                             temp_list_for_df.append(base_row_manual)
                        
                        df_extracted = pd.DataFrame(temp_list_for_df)
                        for col in DISPLAY_COLUMN_ORDER_EDITOR: # Ensure columns for editor
                            if col not in df_extracted.columns: df_extracted[col] = None
                        st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR] # Populate session state
                        st.success("Data extraction processed. Review and edit below.")
                        st.rerun() # Rerun to make editor display the new data in ag_editor_data

                # --- Data Editor and Submission ---
                edited_df_local_copy = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR) # Default empty
                if not st.session_state.ag_editor_data.empty:
                    st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
                    col_conf = {
                        "audit_group_number": st.column_config.NumberColumn(disabled=True), "audit_circle_number": st.column_config.NumberColumn(disabled=True),
                        "gstin": st.column_config.TextColumn(width="medium"), "trade_name": st.column_config.TextColumn(width="large"),
                        "category": st.column_config.SelectboxColumn(options=[None] + VALID_CATEGORIES, required=False, width="small"),
                        "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (Rs)", format="%.2f", width="medium"),
                        "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (Rs)", format="%.2f", width="medium"),
                        "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small", help="Integer only"),
                        "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
                        "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", width="small"),
                        "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", width="small"),
                        "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, required=False, width="medium")}
                    final_editor_col_conf = {k: v for k, v in col_conf.items() if k in DISPLAY_COLUMN_ORDER_EDITOR}
                    
                    editor_key = f"data_editor_stable_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_active'}"
                    
                    # The editor reads from st.session_state.ag_editor_data (which is result of last extraction)
                    # Its output `edited_df_local_copy` contains the current visual state including user's edits for this run.
                    edited_df_local_copy = pd.DataFrame(st.data_editor(
                        st.session_state.ag_editor_data.copy(), # Pass a copy of the extracted data
                        column_config=final_editor_col_conf, num_rows="dynamic",
                        key=editor_key, use_container_width=True, hide_index=True, 
                        height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450) if not st.session_state.ag_editor_data.empty else 200
                    ))
                    # Do NOT assign edited_df_local_copy back to st.session_state.ag_editor_data here to prevent blink

                submit_button_key = f"submit_btn_stable_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_active'}"
                # Enable submit button only if there is data in the editor (even if it's just the template row from failed extraction)
                can_submit = not edited_df_local_copy.empty if not st.session_state.ag_editor_data.empty else False
                if st.button("Validate and Submit to MCM Sheet", key=submit_button_key, use_container_width=True, disabled=not can_submit):
                    # Start with the data from the editor
                    df_from_editor = edited_df_local_copy.copy()

                    # 1. Silently drop any completely empty rows
                    df_to_submit = df_from_editor.dropna(how='all').reset_index(drop=True)

                    if df_to_submit.empty and not df_from_editor.empty:
                        # This case handles if the user only created empty rows and nothing else
                        st.error("Submission failed: Only empty rows were found. Please fill in the details.")
                    else:
                        # 2. Check for missing data in essential columns for the remaining rows
                        # The 'audit_para_heading' is critical as it caused the original error
                        required_cols = ['gstin', 'trade_name', 'audit_para_heading']
                        
                        # Create a boolean Series: True for any row that has a null in any required_col
                        missing_required = df_to_submit[required_cols].isnull().any(axis=1)

                        if missing_required.any():
                            st.error("Submission failed: At least one row is missing required information (e.g., GSTIN, Trade Name, or Para Heading). Please complete all fields.")
                        else:
                            # 3. If all checks pass, proceed with the original logic
                            df_to_submit["audit_group_number"] = st.session_state.audit_group_no
                            df_to_submit["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)

                            num_cols_to_convert = ["total_amount_detected_overall_rs", "total_amount_recovered_overall_rs", "audit_para_number", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"]
                            for nc in num_cols_to_convert:
                                if nc in df_to_submit.columns: df_to_submit[nc] = pd.to_numeric(df_to_submit[nc], errors='coerce')
                            
                            st.session_state.ag_validation_errors = validate_data_for_sheet(df_to_submit)
                # if st.button("Validate and Submit to MCM Sheet", key=submit_button_key, use_container_width=True, disabled=not can_submit):
                #     df_to_submit = edited_df_local_copy.copy() # Use the current state from the editor widget
                    
                #     df_to_submit["audit_group_number"] = st.session_state.audit_group_no
                #     df_to_submit["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)

                #     num_cols_to_convert = ["total_amount_detected_overall_rs", "total_amount_recovered_overall_rs", "audit_para_number", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"]
                #     for nc in num_cols_to_convert:
                #         if nc in df_to_submit.columns: df_to_submit[nc] = pd.to_numeric(df_to_submit[nc], errors='coerce')
                    
                #     st.session_state.ag_validation_errors = validate_data_for_sheet(df_to_submit)
   
                    if not st.session_state.ag_validation_errors:
                        if not st.session_state.ag_pdf_drive_url: 
                            st.error("PDF Drive URL missing. This indicates the initial PDF upload with extraction failed. Please re-extract data."); st.stop()

                        with st.spinner("Submitting to Google Sheet..."):
                            rows_for_sheet = []; ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            final_df_for_sheet_upload = df_to_submit.copy() # Start with edited data
                            for sheet_col_name in SHEET_DATA_COLUMNS_ORDER: # Ensure all sheet columns
                                if sheet_col_name not in final_df_for_sheet_upload.columns:
                                    final_df_for_sheet_upload[sheet_col_name] = None
                            # Re-ensure group and circle numbers are consistently from session state for the final sheet data
                            final_df_for_sheet_upload["audit_group_number"] = st.session_state.audit_group_no
                            final_df_for_sheet_upload["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)
                            
                            for _, r_data_submit in final_df_for_sheet_upload.iterrows():
                                sheet_row = [r_data_submit.get(col) for col in SHEET_DATA_COLUMNS_ORDER] + [st.session_state.ag_pdf_drive_url, ts]
                                rows_for_sheet.append(sheet_row)
                            
                            if rows_for_sheet:
                                if append_to_spreadsheet(sheets_service, mcm_info_current['spreadsheet_id'], rows_for_sheet):
                                    st.success("Data submitted successfully!"); st.balloons(); time.sleep(1)
                                    st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
                                    st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR); st.session_state.ag_pdf_drive_url = None
                                    st.session_state.ag_validation_errors = []; st.session_state.ag_uploader_key_suffix += 1
                                    st.rerun()
                                else: st.error("Failed to append to Google Sheet.")
                            else: st.error("No data rows to submit.")
                    else:
                        st.error("Validation Failed! Correct errors.");
                        if st.session_state.ag_validation_errors: st.subheader("⚠️ Validation Errors:"); [st.warning(f"- {err}") for err in st.session_state.ag_validation_errors]
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
                sel_view_key = st.selectbox("Select MCM Period", options=list(view_period_opts_map.keys()), format_func=lambda k: view_period_opts_map[k], key="ag_view_sel_final_corrected")
                if sel_view_key and sheets_service:
                    view_sheet_id = mcm_periods_all[sel_view_key]['spreadsheet_id']
                    with st.spinner("Loading uploads..."): df_sheet_all = read_from_spreadsheet(sheets_service, view_sheet_id)
                    
                    if df_sheet_all is not None and not df_sheet_all.empty:
                        # Use SHEET_COLUMN_NAMES (Title Case) which are expected from read_from_spreadsheet
                        if "Audit Group Number" in df_sheet_all.columns:
                            df_sheet_all["Audit Group Number"] = df_sheet_all["Audit Group Number"].astype(str)
                            my_uploads = df_sheet_all[df_sheet_all["Audit Group Number"] == str(st.session_state.audit_group_no)]
                            if not my_uploads.empty:
                                st.markdown(f"<h4>Your Uploads for {view_period_opts_map[sel_view_key]}:</h4>", unsafe_allow_html=True)
                                my_uploads_disp = my_uploads.copy()
                                if "DAR PDF URL" in my_uploads_disp.columns:
                                    my_uploads_disp['DAR PDF URL Links'] = my_uploads_disp["DAR PDF URL"].apply(lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link")
                                
                                # Define columns to view using Title Case from SHEET_COLUMN_NAMES
                                cols_to_view_final = [ # Ensure these are Title Case
                                    "Audit Circle Number", "GSTIN", "Trade Name", "Category",
                                    "Total Amount Detected (Overall Rs)", "Total Amount Recovered (Overall Rs)",
                                    "Audit Para Number", "Audit Para Heading", "Status of para",
                                    "Revenue Involved (Lakhs Rs)", "Revenue Recovered (Lakhs Rs)",
                                    "DAR PDF URL Links", # This is the derived one
                                    "Record Created Date"
                                ]
                                # Filter for columns that actually exist in the DataFrame
                                existing_cols_to_display = [c for c in cols_to_view_final if c in my_uploads_disp.columns or (c == "DAR PDF URL Links" and c in my_uploads_disp.columns)]
                                
                                if not existing_cols_to_display:
                                    st.warning("No relevant columns found to display for your uploads. Please check sheet structure.")
                                else:
                                    st.markdown(my_uploads_disp[existing_cols_to_display].to_html(escape=False, index=False), unsafe_allow_html=True)
                            else: st.info(f"No DARs by you for {view_period_opts_map[sel_view_key]}.")
                        else: st.warning("Sheet missing 'Audit Group Number' column or data malformed.")
                    elif df_sheet_all is None: st.error("Error reading spreadsheet for viewing.")
                    else: st.info(f"No data in sheet for {view_period_opts_map[sel_view_key]}.")
                elif not sheets_service and sel_view_key: st.error("Google Sheets service unavailable.")

    # ========================== DELETE MY DAR ENTRIES TAB ==========================
    elif selected_tab == "Delete My DAR Entries":
        # This tab uses the existing logic from your provided code, which seemed largely functional.
        # It will operate on data read by the now more robust `read_from_spreadsheet`.
        st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
        st.info("⚠️ This action is irreversible. Deletion removes entries from the Google Sheet; the PDF on Google Drive will remain.")
        if not mcm_periods_all: st.info("No MCM periods found.")
        else:
            del_period_opts_map = {k: f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(mcm_periods_all.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')}
            if not del_period_opts_map and mcm_periods_all: st.warning("Some MCM periods have incomplete data.")
            if not del_period_opts_map: st.info("No valid MCM periods to manage entries.")
            else:
                sel_del_key = st.selectbox("Select MCM Period", options=list(del_period_opts_map.keys()), format_func=lambda k: del_period_opts_map[k], key="ag_del_sel_final_corrected")
                if sel_del_key and sheets_service:
                    del_sheet_id = mcm_periods_all[sel_del_key]['spreadsheet_id']
                    del_sheet_gid = 0
                    try: del_sheet_gid = sheets_service.spreadsheets().get(spreadsheetId=del_sheet_id).execute().get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
                    except Exception as e_gid: st.error(f"Could not get sheet GID: {e_gid}"); st.stop()

                    with st.spinner("Loading entries..."): df_all_del_data = read_from_spreadsheet(sheets_service, del_sheet_id)
                    if df_all_del_data is not None and not df_all_del_data.empty:
                        if 'Audit Group Number' in df_all_del_data.columns: # Column names here are TitleCase
                            df_all_del_data['Audit Group Number'] = df_all_del_data['Audit Group Number'].astype(str)
                            my_entries_del = df_all_del_data[df_all_del_data['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
                            my_entries_del['original_data_index'] = my_entries_del.index 

                            if not my_entries_del.empty:
                                st.markdown(f"<h4>Your Uploads in {del_period_opts_map[sel_del_key]} (Select to delete):</h4>", unsafe_allow_html=True)
                                del_options_disp = ["--Select an entry to delete--"]; st.session_state.ag_deletable_map.clear()
                                for _, del_row in my_entries_del.iterrows():
                                    # Use TitleCase for .get() as df_all_del_data columns are TitleCase
                                    del_ident = f"TN: {str(del_row.get('Trade Name', 'N/A'))[:20]} | Para: {del_row.get('Audit Para Number', 'N/A')} | Date: {del_row.get('Record Created Date', 'N/A')}"
                                    del_options_disp.append(del_ident)
                                    st.session_state.ag_deletable_map[del_ident] = {
                                        "original_df_index": del_row['original_data_index'], # Store the actual DataFrame index
                                        "Trade Name": str(del_row.get('Trade Name')), # Store identifiers for confirmation
                                        "Audit Para Number": str(del_row.get('Audit Para Number')),
                                        "Record Created Date": str(del_row.get('Record Created Date')),
                                        "DAR PDF URL": str(del_row.get('DAR PDF URL'))
                                    }
                                
                                sel_entry_del_str = st.selectbox("Select Entry:", options=del_options_disp, key=f"del_box_final_corrected_{sel_del_key}")
                                if sel_entry_del_str != "--Select an entry to delete--":
                                    entry_info_to_delete = st.session_state.ag_deletable_map.get(sel_entry_del_str)
                                    if entry_info_to_delete is not None :
                                        orig_idx_to_del = entry_info_to_delete["original_df_index"]
                                        st.warning(f"Confirm Deletion: TN: **{entry_info_to_delete.get('Trade Name')}**, Para: **{entry_info_to_delete.get('Audit Para Number')}**")
                                        with st.form(key=f"del_form_final_corrected_{orig_idx_to_del}"):
                                            pwd = st.text_input("Password:", type="password", key=f"del_pwd_final_corrected_{orig_idx_to_del}")
                                            if st.form_submit_button("Yes, Delete This Entry"):
                                                if pwd == USER_CREDENTIALS.get(st.session_state.username):
                                                    if delete_spreadsheet_rows(sheets_service, del_sheet_id, del_sheet_gid, [orig_idx_to_del]): 
                                                        st.success("Entry deleted."); time.sleep(1); st.rerun()
                                                    else: st.error("Failed to delete from sheet.")
                                                else: st.error("Incorrect password.")
                                    else: st.error("Could not identify selected entry. Please refresh and re-select.")
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

# from google_utils import (
#     load_mcm_periods, upload_to_drive, append_to_spreadsheet,
#     read_from_spreadsheet, delete_spreadsheet_rows
# )
# from dar_processor import preprocess_pdf_text
# from gemini_utils import get_structured_data_with_gemini
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# from config import USER_CREDENTIALS, AUDIT_GROUP_NUMBERS
# from models import ParsedDARReport

# from streamlit_option_menu import option_menu

# # --- Caching helper for MCM Periods ---
# def get_cached_mcm_periods_ag(drive_service, ttl_seconds=120): # Added suffix _ag
#     cache_key_data = 'ag_ui_cached_mcm_periods_data' # Unique cache key
#     cache_key_ts = 'ag_ui_cached_mcm_periods_timestamp'
#     current_time = time.time()

#     if (cache_key_data in st.session_state and
#             cache_key_ts in st.session_state and
#             (current_time - st.session_state[cache_key_ts] < ttl_seconds)):
#         return st.session_state[cache_key_data]

#     periods = load_mcm_periods(drive_service)
#     st.session_state[cache_key_data] = periods
#     st.session_state[cache_key_ts] = current_time
#     return periods
# # --- End Caching helper ---

# SHEET_DATA_COLUMNS_ORDER = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
#     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading",
#     "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para",
# ]

# DISPLAY_COLUMN_ORDER = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
#     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
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
    
#     mcm_periods_all = get_cached_mcm_periods_ag(drive_service) # Use cached version
#     active_periods = {k: v for k, v in mcm_periods_all.items() if v.get("active")}

#     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE_FALLBACK")

#     default_ag_states = {
#         'ag_current_mcm_key': None,
#         'ag_current_uploaded_file_obj': None,
#         'ag_current_uploaded_file_name': None,
#         'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER),
#         'ag_pdf_drive_url': None,
#         'ag_validation_errors': [],
#         'ag_uploader_key_suffix': 0,
#         'ag_row_to_delete_details': None,
#         'ag_show_delete_confirm': False,
#         'ag_deletable_map': {}
#     }
#     for key, value in default_ag_states.items():
#         if key not in st.session_state:
#             st.session_state[key] = value

#     with st.sidebar:
#         try: st.image("logo.png", width=80)
#         except Exception: st.sidebar.markdown("*(Logo)*")
#         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
#         if st.button("Logout", key="ag_logout_main_cached", use_container_width=True):
#             keys_to_clear = list(default_ag_states.keys()) + ['drive_structure_initialized', 'ag_ui_cached_mcm_periods_data', 'ag_ui_cached_mcm_periods_timestamp']
#             for ktd in keys_to_clear:
#                 if ktd in st.session_state: del st.session_state[ktd]
#             st.session_state.logged_in = False; st.session_state.username = ""; st.session_state.role = ""; st.session_state.audit_group_no = None
#             st.rerun()
#         st.markdown("---")

#     selected_tab = option_menu(
#         menu_title=None, options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
#         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace", default_index=0, orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#e9ecef"}, "icon": {"color": "#28a745", "font-size": "20px"},
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
#             period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True) if v.get('month_name') and v.get('year')}
#             period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
#             current_mcm_display_val = period_options_disp_map.get(st.session_state.ag_current_mcm_key)
            
#             selected_period_str = st.selectbox(
#                 "Select Active MCM Period", options=list(period_select_map_rev.keys()),
#                 index=list(period_select_map_rev.keys()).index(current_mcm_display_val) if current_mcm_display_val and current_mcm_display_val in period_select_map_rev else 0 if period_select_map_rev else None,
#                 key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
#             )

#             if selected_period_str:
#                 new_mcm_key = period_select_map_rev[selected_period_str]
#                 mcm_info_current = active_periods[new_mcm_key]

#                 if st.session_state.ag_current_mcm_key != new_mcm_key:
#                     st.session_state.ag_current_mcm_key = new_mcm_key
#                     st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
#                     st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER); st.session_state.ag_pdf_drive_url = None
#                     st.session_state.ag_validation_errors = []; st.session_state.ag_uploader_key_suffix += 1
#                     st.rerun()

#                 st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
#                 uploaded_file = st.file_uploader("Choose DAR PDF", type="pdf", key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}")

#                 if uploaded_file:
#                     if st.session_state.ag_current_uploaded_file_name != uploaded_file.name or st.session_state.ag_current_uploaded_file_obj is None:
#                         st.session_state.ag_current_uploaded_file_obj = uploaded_file; st.session_state.ag_current_uploaded_file_name = uploaded_file.name
#                         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER); st.session_state.ag_pdf_drive_url = None
#                         st.session_state.ag_validation_errors = []
#                         # Do not rerun here explicitly, let "Extract" button control data population

#                 extract_button_key = f"extract_data_btn_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file_yet'}"
#                 if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data from PDF", key=extract_button_key, use_container_width=True):
#                     with st.spinner(f"Processing '{st.session_state.ag_current_uploaded_file_name}'... This might take a moment."):
#                         pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
#                         st.session_state.ag_pdf_drive_url = None # Reset PDF URL for this new extraction
#                         st.session_state.ag_validation_errors = []

#                         dar_filename_on_drive = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
#                         pdf_drive_id, pdf_drive_url_temp = upload_to_drive(drive_service, BytesIO(pdf_bytes),
#                                                                            mcm_info_current['drive_folder_id'], dar_filename_on_drive)
#                         temp_list_for_df = [] # Renamed to avoid clash if other temp_list exists
#                         if not pdf_drive_id:
#                             st.error("Failed to upload PDF to Drive. Cannot proceed with extraction.")
#                             temp_list_for_df = [{"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                             "audit_para_heading": "Manual Entry - PDF Upload Failed", "status_of_para": None}]
#                         else:
#                             st.session_state.ag_pdf_drive_url = pdf_drive_url_temp
#                             st.success(f"DAR PDF uploaded to Drive: [Link]({st.session_state.ag_pdf_drive_url})")
#                             preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))

#                             if preprocessed_text.startswith("Error"):
#                                 st.error(f"PDF Preprocessing Error: {preprocessed_text}")
#                                 temp_list_for_df = [{"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                                 "audit_para_heading": "Manual Entry - PDF Error", "status_of_para": None}]
#                             else:
#                                 parsed_data: ParsedDARReport = get_structured_data_with_gemini(YOUR_GEMINI_API_KEY, preprocessed_text)
#                                 if parsed_data.parsing_errors: st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")

#                                 header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
#                                 base_info = {
#                                     "audit_group_number": st.session_state.audit_group_no,
#                                     "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                     "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
#                                     "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
#                                     "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs"),
#                                 }
#                                 if parsed_data.audit_paras:
#                                     for para_obj in parsed_data.audit_paras:
#                                         para_dict = para_obj.model_dump(); row = base_info.copy(); row.update({k: para_dict.get(k) for k in ["audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "status_of_para"]}); temp_list_for_df.append(row)
#                                 elif base_info.get("trade_name"): # Header OK, no paras
#                                     row = base_info.copy(); row.update({"audit_para_number": None, "audit_para_heading": "N/A - Header Info Only (Add Paras Manually)", "status_of_para": None}); temp_list_for_df.append(row)
#                                     st.info("AI extracted header data. No specific paras found, or add them manually.")
#                                 else: # Major extraction failure
#                                     st.error("AI failed to extract key header information. A manual entry template is provided."); row = base_info.copy(); row.update({"audit_para_heading": "Manual Entry Required", "status_of_para": None}); temp_list_for_df.append(row)
                        
#                         if not temp_list_for_df: # Fallback
#                              temp_list_for_df.append({"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                                                       "audit_para_heading": "Manual Entry - Extraction Issue", "status_of_para": None})
                        
#                         df_extracted = pd.DataFrame(temp_list_for_df)
#                         for col in DISPLAY_COLUMN_ORDER:
#                             if col not in df_extracted.columns: df_extracted[col] = None
#                         st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER]
#                         st.success("Data extraction processed. Review and edit below.")
#                         st.rerun() # Rerun to ensure the editor is displayed with the new data

#                 # --- Data Editor and Submission ---
#                 if not st.session_state.ag_editor_data.empty:
#                     st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
                    
#                     # The editor will take st.session_state.ag_editor_data as its initial state for this run.
#                     # User edits will be captured in `edited_df_from_widget` for this specific run.
#                     # `st.session_state.ag_editor_data` itself is the "last extracted" or "last submitted" state.
                    
#                     df_display_in_editor = st.session_state.ag_editor_data.copy() # Use a copy to prevent direct mutation before explicit save

#                     col_conf = {
#                         "audit_group_number": st.column_config.NumberColumn(disabled=True), "audit_circle_number": st.column_config.NumberColumn(disabled=True),
#                         "gstin": st.column_config.TextColumn(width="medium"), "trade_name": st.column_config.TextColumn(width="large"),
#                         "category": st.column_config.SelectboxColumn(options=[None] + VALID_CATEGORIES, required=False, width="small"),
#                         "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (Rs)", format="%.2f", width="medium"),
#                         "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (Rs)", format="%.2f", width="medium"),
#                         "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small", help="Integer only"),
#                         "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                         "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f", width="small"),
#                         "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f", width="small"),
#                         "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, required=False, width="medium")}
#                     final_editor_col_conf = {k: v for k, v in col_conf.items() if k in DISPLAY_COLUMN_ORDER}

#                     editor_key = f"data_editor_final_v2_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
                    
#                     # Capture the current state of the editor for this script run
#                     edited_df_from_widget = st.data_editor(
#                         df_display_in_editor, # Data from last extraction
#                         column_config=final_editor_col_conf, num_rows="dynamic",
#                         key=editor_key, use_container_width=True, hide_index=True, 
#                         height=min(len(df_display_in_editor) * 45 + 70, 450) if not df_display_in_editor.empty else 200
#                     )
#                     # Note: We are NOT immediately writing `edited_df_from_widget` back to `st.session_state.ag_editor_data` here.
#                     # This is the key change to prevent the blink, similar to the user's "previous code" behavior.
#                     # The editor widget itself handles displaying the live edits.
#                     # `st.session_state.ag_editor_data` remains the result of the last *extraction*.

#                     submit_button_key = f"submit_btn_final_v2_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
#                     if st.button("Validate and Submit to MCM Sheet", key=submit_button_key, use_container_width=True):
#                         # FOR SUBMISSION, use the `edited_df_from_widget` which has the latest UI changes
#                         df_to_submit = pd.DataFrame(edited_df_from_widget)
                        
#                         df_to_submit["audit_group_number"] = st.session_state.audit_group_no
#                         df_to_submit["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)

#                         num_cols_to_convert = ["total_amount_detected_overall_rs", "total_amount_recovered_overall_rs", "audit_para_number", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs"]
#                         for nc in num_cols_to_convert:
#                             if nc in df_to_submit.columns: df_to_submit[nc] = pd.to_numeric(df_to_submit[nc], errors='coerce')
                        
#                         st.session_state.ag_validation_errors = validate_data_for_sheet(df_to_submit)

#                         if not st.session_state.ag_validation_errors:
#                             if not st.session_state.ag_pdf_drive_url: # Should have been set during the extraction's PDF upload
#                                 st.error("PDF Drive URL missing. This indicates the initial PDF upload step failed. Please re-extract data."); st.stop()

#                             with st.spinner("Submitting to Google Sheet..."):
#                                 rows_for_sheet = []; ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                                 for sheet_col_name_final in SHEET_DATA_COLUMNS_ORDER:
#                                     if sheet_col_name_final not in df_to_submit.columns:
#                                         df_to_submit[sheet_col_name_final] = None
#                                 df_to_submit["audit_group_number"] = st.session_state.audit_group_no # Ensure again before list creation
#                                 df_to_submit["audit_circle_number"] = calculate_audit_circle(st.session_state.audit_group_no)
                                
#                                 for _, r_data_submit in df_to_submit.iterrows():
#                                     sheet_row = [r_data_submit.get(col) for col in SHEET_DATA_COLUMNS_ORDER] + [st.session_state.ag_pdf_drive_url, ts]
#                                     rows_for_sheet.append(sheet_row)
                                
#                                 if rows_for_sheet:
#                                     if append_to_spreadsheet(sheets_service, mcm_info_current['spreadsheet_id'], rows_for_sheet):
#                                         st.success("Data submitted successfully!"); st.balloons(); time.sleep(1)
#                                         st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
#                                         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER); st.session_state.ag_pdf_drive_url = None
#                                         st.session_state.ag_validation_errors = []; st.session_state.ag_uploader_key_suffix += 1
#                                         st.rerun()
#                                     else: st.error("Failed to append to Google Sheet.")
#                                 else: st.error("No data rows to submit.")
#                         else:
#                             st.error("Validation Failed! Correct errors.");
#                             if st.session_state.ag_validation_errors: st.subheader("⚠️ Validation Errors:"); [st.warning(f"- {err}") for err in st.session_state.ag_validation_errors]
#             elif not period_select_map_rev: st.info("No MCM periods available.")

#     # ========================== VIEW MY UPLOADED DARS TAB ==========================
#     elif selected_tab == "View My Uploaded DARs":
#         st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
#         if not mcm_periods_all: st.info("No MCM periods found.") # Use cached mcm_periods_all
#         else:
#             view_period_opts_map = {k: f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(mcm_periods_all.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')}
#             if not view_period_opts_map and mcm_periods_all: st.warning("Some MCM periods have incomplete data.")
#             if not view_period_opts_map: st.info("No valid MCM periods to view.")
#             else:
#                 sel_view_key = st.selectbox("Select MCM Period", options=list(view_period_opts_map.keys()), format_func=lambda k: view_period_opts_map[k], key="ag_view_sel_cached")
#                 if sel_view_key and sheets_service:
#                     view_sheet_id = mcm_periods_all[sel_view_key]['spreadsheet_id']
#                     with st.spinner("Loading uploads..."): df_sheet_all = read_from_spreadsheet(sheets_service, view_sheet_id) # This uses the improved read_from_spreadsheet
                    
#                     if df_sheet_all is not None and not df_sheet_all.empty:
#                         if 'Audit Group Number' in df_sheet_all.columns:
#                             df_sheet_all['Audit Group Number'] = df_sheet_all['Audit Group Number'].astype(str)
#                             my_uploads = df_sheet_all[df_sheet_all['Audit Group Number'] == str(st.session_state.audit_group_no)]
#                             if not my_uploads.empty:
#                                 st.markdown(f"<h4>Your Uploads for {view_period_opts_map[sel_view_key]}:</h4>", unsafe_allow_html=True)
#                                 my_uploads_disp = my_uploads.copy()
#                                 if 'DAR PDF URL' in my_uploads_disp.columns:
#                                     my_uploads_disp['DAR PDF URL Links'] = my_uploads_disp['DAR PDF URL'].apply(lambda x: f'<a href="{x}" target="_blank">View PDF</a>' if pd.notna(x) and str(x).startswith("http") else "No Link")
                                
#                                 cols_to_view = ["audit_circle_number", "gstin", "trade_name", "category", 
#                                                 "audit_para_number", "audit_para_heading", "status_of_para", 
#                                                 "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs",
#                                                 "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#                                                 "DAR PDF URL Links", "Record Created Date"]
#                                 existing_cols_view = [c for c in cols_to_view if c in my_uploads_disp.columns]
#                                 st.markdown(my_uploads_disp[existing_cols_view].to_html(escape=False, index=False), unsafe_allow_html=True)
#                             else: st.info(f"No DARs by you for {view_period_opts_map[sel_view_key]}.")
#                         else: st.warning("Sheet missing 'Audit Group Number' column or data malformed.")
#                     elif df_sheet_all is None: st.error("Error reading spreadsheet for viewing.")
#                     else: st.info(f"No data in sheet for {view_period_opts_map[sel_view_key]}.")
#                 elif not sheets_service and sel_view_key: st.error("Google Sheets service unavailable.")

#     # ========================== DELETE MY DAR ENTRIES TAB ==========================
#     elif selected_tab == "Delete My DAR Entries":
#         st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#         st.info("⚠️ This action is irreversible. Deletion removes entries from the Google Sheet; the PDF on Google Drive will remain.")
#         if not mcm_periods_all: st.info("No MCM periods found.") # Use cached mcm_periods_all
#         else:
#             del_period_opts_map = {k: f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(mcm_periods_all.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')}
#             if not del_period_opts_map and mcm_periods_all: st.warning("Some MCM periods have incomplete data.")
#             if not del_period_opts_map: st.info("No valid MCM periods to manage entries.")
#             else:
#                 sel_del_key = st.selectbox("Select MCM Period", options=list(del_period_opts_map.keys()), format_func=lambda k: del_period_opts_map[k], key="ag_del_sel_cached")
#                 if sel_del_key and sheets_service:
#                     del_sheet_id = mcm_periods_all[sel_del_key]['spreadsheet_id']
#                     del_sheet_gid = 0
#                     try: del_sheet_gid = sheets_service.spreadsheets().get(spreadsheetId=del_sheet_id).execute().get('sheets', [{}])[0].get('properties', {}).get('sheetId', 0)
#                     except Exception as e_gid: st.error(f"Could not get sheet GID: {e_gid}"); st.stop()

#                     with st.spinner("Loading entries..."): df_all_del_data = read_from_spreadsheet(sheets_service, del_sheet_id) # Uses improved read
#                     if df_all_del_data is not None and not df_all_del_data.empty:
#                         if 'Audit Group Number' in df_all_del_data.columns:
#                             df_all_del_data['Audit Group Number'] = df_all_del_data['Audit Group Number'].astype(str)
#                             my_entries_del = df_all_del_data[df_all_del_data['Audit Group Number'] == str(st.session_state.audit_group_no)].copy()
#                             my_entries_del['original_data_index'] = my_entries_del.index 

#                             if not my_entries_del.empty:
#                                 st.markdown(f"<h4>Your Uploads in {del_period_opts_map[sel_del_key]} (Select to delete):</h4>", unsafe_allow_html=True)
#                                 del_options_disp = ["--Select an entry to delete--"]; st.session_state.ag_deletable_map.clear()
#                                 for _, del_row in my_entries_del.iterrows():
#                                     del_ident = f"TN: {str(del_row.get('Trade Name', 'N/A'))[:20]} | Para: {del_row.get('Audit Para Number', 'N/A')} | Date: {del_row.get('Record Created Date', 'N/A')}"
#                                     del_options_disp.append(del_ident); st.session_state.ag_deletable_map[del_ident] = del_row['original_data_index']
                                
#                                 sel_entry_del_str = st.selectbox("Select Entry:", options=del_options_disp, key=f"del_box_final_cached_{sel_del_key}")
#                                 if sel_entry_del_str != "--Select an entry to delete--":
#                                     orig_idx_to_del = st.session_state.ag_deletable_map.get(sel_entry_del_str)
#                                     if orig_idx_to_del is not None and orig_idx_to_del in df_all_del_data.index : # Check if index is valid
#                                         row_confirm_details = df_all_del_data.loc[orig_idx_to_del]
#                                         st.warning(f"Confirm Deletion: TN: **{row_confirm_details.get('Trade Name')}**, Para: **{row_confirm_details.get('Audit Para Number')}**")
#                                         with st.form(key=f"del_form_final_cached_{orig_idx_to_del}"):
#                                             pwd = st.text_input("Password:", type="password", key=f"del_pwd_final_cached_{orig_idx_to_del}")
#                                             if st.form_submit_button("Yes, Delete This Entry"):
#                                                 if pwd == USER_CREDENTIALS.get(st.session_state.username):
#                                                     if delete_spreadsheet_rows(sheets_service, del_sheet_id, del_sheet_gid, [orig_idx_to_del]): st.success("Entry deleted."); time.sleep(1); st.rerun()
#                                                     else: st.error("Failed to delete from sheet.")
#                                                 else: st.error("Incorrect password.")
#                                     else: st.error("Could not identify selected entry. Please refresh and re-select.")
#                             else: st.info(f"You have no entries in {del_period_opts_map[sel_del_key]} to delete.")
#                         else: st.warning("Sheet missing 'Audit Group Number' column.")
#                     elif df_all_del_data is None: st.error("Error reading sheet for deletion.")
#                     else: st.info(f"No data in sheet for {del_period_opts_map[sel_del_key]}.")
#                 elif not sheets_service and sel_del_key: st.error("Google Sheets service unavailable.")

#     st.markdown("</div>", unsafe_allow_html=True)# # ui_audit_group.py
