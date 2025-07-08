
# ui_pco.py
import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
import math  # For math.ceil if needed
from ui_mcm_agenda import mcm_agenda_tab # <--- IMPORT THE NEW TAB FUNCTION
from ui_pco_reports import pco_reports_dashboard

# Assuming google_utils.py and config.py are in the same directory and correctly set up
from google_utils import (
    load_mcm_periods, save_mcm_periods, create_drive_folder,
    create_spreadsheet, read_from_spreadsheet,update_spreadsheet_from_df,test_permissions_debug
)
from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE
def test_root_spreadsheet_creation(sheets_service, drive_service):
    """Test creating spreadsheet in root Drive"""
    st.subheader("🧪 Test Spreadsheet Creation in Root")
    
    if st.button("Test Create in Root Drive"):
        test_title = f"TEST_ROOT_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with st.spinner("Testing..."):
            try:
                # Create without any parent folder
                spreadsheet_body = {'properties': {'title': test_title}}
                spreadsheet = sheets_service.spreadsheets().create(
                    body=spreadsheet_body,
                    fields='spreadsheetId,spreadsheetUrl'
                ).execute()
                
                spreadsheet_id = spreadsheet.get('spreadsheetId')
                spreadsheet_url = spreadsheet.get('spreadsheetUrl')
                
                if spreadsheet_id:
                    st.success("✅ SUCCESS! Spreadsheet created in root Drive")
                    st.info(f"**ID:** {spreadsheet_id}")
                    st.info(f"**URL:** {spreadsheet_url}")
                    
                    # Clean up test file
                    try:
                        drive_service.files().delete(fileId=spreadsheet_id).execute()
                        st.success("✅ Test file cleaned up")
                    except:
                        st.warning("⚠️ Test file created but not cleaned up")
                        st.info("You can manually delete it from your Drive")
                else:
                    st.error("❌ No spreadsheet ID returned")
                    
            except Exception as e:
                st.error(f"❌ Test failed: {e}")
def pco_dashboard(drive_service, sheets_service):
    st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
    mcm_periods = load_mcm_periods(drive_service)  # Direct load, no caching

    with st.sidebar:
        try:
            st.image("logo.png", width=80)  # Use local logo
        except Exception as e:
            st.sidebar.warning(f"Could not load logo.png: {e}")
            st.sidebar.markdown("*(Logo)*")

        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        if st.button("Logout", key="pco_logout_full_final_v2", use_container_width=True):  # Unique key
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.drive_structure_initialized = False
            keys_to_clear = ['period_to_delete', 'show_delete_confirm', 'num_paras_to_show_pco']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        st.markdown("---")
        # --- Smart Audit Tracker Button in Sidebar ---
        st.markdown(
            """
            <style>
            .stButton>button {
                background-image: linear-gradient(to right, #FF512F 0%, #DD2476  51%, #FF512F  100%);
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
        if st.button("🚀 Smart Audit Tracker", key="launch_sat_pco"):
            st.session_state.app_mode = "smart_audit_tracker"
            st.rerun()
        st.markdown("---")
    selected_tab = option_menu(
        menu_title=None,
         options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", 
                 "MCM Agenda", "Visualizations", "Reports"],
        icons=["calendar-plus-fill", "sliders", "eye-fill", 
               "journal-richtext", # <--- ADDED ICON for MCM Agenda (Example icon)
               "bar-chart-fill"],
        menu_icon="gear-wide-connected", 
        default_index=0, # You might want to adjust this if MCM Agenda should be default
        orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#e9ecef"},
            "icon": {"color": "#007bff", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
            "nav-link-selected": {"background-color": "#007bff", "color": "white"},
        })

    st.markdown("<div class='card'>", unsafe_allow_html=True)
  

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    # ========================== CREATE MCM PERIOD TAB ==========================
    if selected_tab == "Create MCM Period":
        st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
        current_year = datetime.datetime.now().year
        years = list(range(current_year - 1, current_year + 3))
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                  "November", "December"]
        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year), key="pco_year_create_tab")
        with col2:
            selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1,
                                               key="pco_month_create_tab")
        selected_month_num = months.index(selected_month_name) + 1
        period_key = f"{selected_year}-{selected_month_num:02d}"

        # Operate on a copy for potential modifications before saving
        mcm_periods_local_copy_create = mcm_periods.copy()

        if period_key in mcm_periods_local_copy_create:
            st.warning(f"MCM Period for {selected_month_name} {selected_year} already exists.")
        else:
            if st.button(f"Create MCM for {selected_month_name} {selected_year}", key="pco_btn_create_mcm",
                         use_container_width=True):
                if not drive_service or not sheets_service or not st.session_state.get('master_drive_folder_id'):
                    st.error("Google Services or Master Drive Folder not available. Cannot create MCM period.")
                else:
                    with st.spinner("Creating Google Drive folder and Spreadsheet..."):
                        master_folder_id = st.session_state.master_drive_folder_id
                        folder_name = f"MCM_DARs_{selected_month_name}_{selected_year}"
                        spreadsheet_title = f"MCM_Audit_Paras_{selected_month_name}_{selected_year}"

                        folder_id, folder_url = create_drive_folder(drive_service, folder_name, parent_id=master_folder_id)
                        sheet_id, sheet_url = create_spreadsheet(sheets_service, drive_service, spreadsheet_title, parent_folder_id=master_folder_id)

                        if folder_id and sheet_id:
                            mcm_periods_local_copy_create[period_key] = {
                                "year": selected_year, "month_num": selected_month_num, "month_name": selected_month_name,
                                "drive_folder_id": folder_id, "drive_folder_url": folder_url,
                                "spreadsheet_id": sheet_id, "spreadsheet_url": sheet_url, "active": True
                            }
                            if save_mcm_periods(drive_service, mcm_periods_local_copy_create):  # Save the updated dict
                                st.success(f"Successfully created MCM period for {selected_month_name} {selected_year}!")
                                st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>", unsafe_allow_html=True)
                                st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>", unsafe_allow_html=True)
                                st.balloons(); time.sleep(0.5); st.rerun()  # Rerun to reflect new period
                            else:
                                st.error("Failed to save MCM period configuration to Drive.")
                        else:
                            st.error("Failed to create Drive folder or Spreadsheet.")
        st.markdown("---")
        test_permissions_debug(drive_service, sheets_service)
        st.markdown("---")
        test_root_spreadsheet_creation(sheets_service, drive_service)
    # ========================== MANAGE MCM PERIODS TAB ==========================
    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: red;'>Pls Note ,Deleting the records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: green;'>Only the Months which are marked as 'Active' by Planning officer, will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
        
        mcm_periods_manage_local_copy = mcm_periods.copy()  # Work with a copy

        if not mcm_periods_manage_local_copy:
            st.info("No MCM periods created yet.")
        else:
            sorted_periods_keys_mng = sorted(mcm_periods_manage_local_copy.keys(), reverse=True)
            for period_key_for_manage in sorted_periods_keys_mng:
                data_for_manage = mcm_periods_manage_local_copy[period_key_for_manage]
                month_name_disp_mng = data_for_manage.get('month_name', 'Unknown Month')
                year_disp_mng = data_for_manage.get('year', 'Unknown Year')
                st.markdown(f"<h4>{month_name_disp_mng} {year_disp_mng}</h4>", unsafe_allow_html=True)
                
                col1_manage, col2_manage, col3_manage, col4_manage = st.columns([2, 2, 1, 2])
                with col1_manage:
                    st.markdown(f"<a href='{data_for_manage.get('drive_folder_url', '#')}' target='_blank'>Drive Folder</a>", unsafe_allow_html=True)
                with col2_manage:
                    st.markdown(f"<a href='{data_for_manage.get('spreadsheet_url', '#')}' target='_blank'>Spreadsheet</a>", unsafe_allow_html=True)
                with col3_manage:
                    is_active_current = data_for_manage.get("active", False)
                    new_status_current = st.checkbox("Active", value=is_active_current, key=f"active_manage_tab_{period_key_for_manage}")
                    if new_status_current != is_active_current:
                        mcm_periods_manage_local_copy[period_key_for_manage]["active"] = new_status_current
                        if save_mcm_periods(drive_service, mcm_periods_manage_local_copy):
                            st.success(f"Status for {month_name_disp_mng} {year_disp_mng} updated.")
                            st.rerun()
                        else:
                            st.error("Failed to save updated status to Drive.")
                            mcm_periods_manage_local_copy[period_key_for_manage]["active"] = is_active_current  # Revert local copy
                with col4_manage:
                    if st.button("Delete Period Record", key=f"delete_mcm_btn_mng_tab_{period_key_for_manage}", type="secondary"):
                        st.session_state.period_to_delete = period_key_for_manage
                        st.session_state.show_delete_confirm = True
                        st.rerun()
                st.markdown("---")

            if st.session_state.get('show_delete_confirm') and st.session_state.get('period_to_delete'):
                period_key_to_delete_confirm = st.session_state.period_to_delete
                period_data_to_delete_confirm = mcm_periods_manage_local_copy.get(period_key_to_delete_confirm, {})
                with st.form(key=f"delete_confirm_form_final_submit_v2_{period_key_to_delete_confirm}"):  # Unique form key
                    st.warning(f"Are you sure you want to delete the MCM period record for **{period_data_to_delete_confirm.get('month_name')} {period_data_to_delete_confirm.get('year')}**?")
                    st.error("**Warning:** Delete period will delete the backend historic DAR data in the spreadsheet and drive. So use cautiously.")
                    st.caption(f"Currently, this action only removes the period's entry from the app's configuration file (`{MCM_PERIODS_FILENAME_ON_DRIVE}`). Backend logic for deleting Google Drive/Sheets resources needs to be implemented for the warning to be fully accurate.")
                    pco_password_confirm_del = st.text_input("Enter your PCO password:", type="password", key=f"pco_pass_del_confirm_final_{period_key_to_delete_confirm}")
                    form_c1, form_c2 = st.columns(2)
                    with form_c1:
                        submitted_delete_final = st.form_submit_button("Yes, Delete Record from Tracking", use_container_width=True)
                    with form_c2:
                        if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
                            st.session_state.show_delete_confirm = False
                            st.session_state.period_to_delete = None
                            st.rerun()
                    if submitted_delete_final:
                        if pco_password_confirm_del == USER_CREDENTIALS.get("planning_officer"):
                            del mcm_periods_manage_local_copy[period_key_to_delete_confirm]
                            if save_mcm_periods(drive_service, mcm_periods_manage_local_copy):
                                st.success(f"MCM record for {period_data_to_delete_confirm.get('month_name')} {period_data_to_delete_confirm.get('year')} deleted from tracking.")
                            else:
                                st.error("Failed to save changes to Drive after deleting record locally.")
                            st.session_state.show_delete_confirm = False
                            st.session_state.period_to_delete = None
                            st.rerun()
                        else:
                            st.error("Incorrect password.")
    # ========================== VIEW UPLOADED REPORTS TAB ==========================
    elif selected_tab == "View Uploaded Reports":
        st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
        all_periods_for_view = mcm_periods.copy()
        if not all_periods_for_view:
            st.info("No MCM periods to view reports for.")
        else:
            period_options_list_view = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_periods_for_view.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
            if not period_options_list_view and all_periods_for_view:
                st.warning("No valid MCM periods with complete month/year info found.")
            elif not period_options_list_view:
                st.info("No MCM periods available.")
            else:
                selected_period_str_view = st.selectbox("Select MCM Period", options=period_options_list_view, key="pco_view_reports_sel_final_v2")
                if selected_period_str_view:
                    selected_period_k_for_view = next((k for k, p in all_periods_for_view.items() if f"{p.get('month_name')} {p.get('year')}" == selected_period_str_view), None)
                    if selected_period_k_for_view and sheets_service:
                        sheet_id_for_report_view = all_periods_for_view[selected_period_k_for_view]['spreadsheet_id']
                        with st.spinner("Loading data from Google Sheet..."):
                            df_report_data = read_from_spreadsheet(sheets_service, sheet_id_for_report_view)
                        if df_report_data is not None and not df_report_data.empty:
                            # --- SECTION 1: DISPLAY ALL EXISTING SUMMARY REPORTS ---
                            st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
                            if 'Audit Group Number' in df_report_data.columns:
                                try:
                                    df_report_data['Audit Group Number Numeric'] = pd.to_numeric(df_report_data['Audit Group Number'], errors='coerce')
                                    df_summary_reports = df_report_data.dropna(subset=['Audit Group Number Numeric'])
                                    
                                    # Report 1: DARs per Group
                                    dars_per_group_rep = df_summary_reports.groupby('Audit Group Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
                                    st.write("**DARs Uploaded per Audit Group:**")
                                    st.dataframe(dars_per_group_rep, use_container_width=True)
                                    
                                    # Report 2: Paras per Group
                                    paras_per_group_rep = df_summary_reports.groupby('Audit Group Number Numeric').size().reset_index(name='Total Para Entries')
                                    st.write("**Total Para Entries per Audit Group:**")
                                    st.dataframe(paras_per_group_rep, use_container_width=True)
                                    
                                    # Report 3: DARs per Circle
                                    if 'Audit Circle Number' in df_report_data.columns:
                                        df_summary_reports['Audit Circle Number Numeric'] = pd.to_numeric(df_summary_reports['Audit Circle Number'], errors='coerce')
                                        dars_per_circle_rep = df_summary_reports.dropna(subset=['Audit Circle Number Numeric']).groupby('Audit Circle Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
                                        st.write("**DARs Uploaded per Audit Circle:**")
                                        st.dataframe(dars_per_circle_rep, use_container_width=True)
                                        
                                    # Report 4: Para Status
                                    if 'Status of para' in df_report_data.columns:
                                        status_summary_rep = df_summary_reports['Status of para'].value_counts().reset_index(name='Count')
                                        status_summary_rep.columns = ['Status of para', 'Count']
                                        st.write("**Para Status Summary:**")
                                        st.dataframe(status_summary_rep, use_container_width=True)
                                    
                                    st.markdown("<hr>", unsafe_allow_html=True)
                                    
                                    # --- SECTION 2: EDIT AND SAVE DETAILED DATA ---
                                    st.markdown("<h4>Edit Detailed Data</h4>", unsafe_allow_html=True)
                                    st.info("You can edit data in the table below. Click 'Save Changes' to update the source spreadsheet.", icon="✍️")
    
                                    edited_df = st.data_editor(
                                        df_report_data,
                                        use_container_width=True,
                                        hide_index=True,
                                        num_rows="dynamic",
                                        key=f"editor_{selected_period_k_for_view}"
                                    )
    
                                    if st.button("Save Changes to Spreadsheet", type="primary"):
                                        with st.spinner("Saving changes to Google Sheet..."):
                                            success = update_spreadsheet_from_df(sheets_service, sheet_id_for_report_view, edited_df)
                                            if success:
                                                st.success("Changes saved successfully!")
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error("Failed to save changes. Please check the error message above.")
    
                                except Exception as e_rep_sum:
                                    st.error(f"Error processing summary: {e_rep_sum}")
                            else:
                                st.warning("Missing 'Audit Group Number' column for summary.")
                                st.dataframe(df_report_data, use_container_width=True)
                        elif df_report_data is None:
                            st.error("Could not load data from the spreadsheet.")
                        else:
                            st.info(f"No data in spreadsheet for {selected_period_str_view}.")
                    elif not sheets_service:
                        st.error("Google Sheets service not available.")
    # # ========================== VIEW UPLOADED REPORTS TAB ==========================
    # elif selected_tab == "View Uploaded Reports":
    #     st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
    #     all_periods_for_view = mcm_periods.copy()  # Use copy of loaded periods
    #     if not all_periods_for_view:
    #         st.info("No MCM periods to view reports for.")
    #     else:
    #         period_options_list_view = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_periods_for_view.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
    #         if not period_options_list_view and all_periods_for_view:
    #             st.warning("No valid MCM periods with complete month/year info found.")
    #         elif not period_options_list_view:
    #             st.info("No MCM periods available.")
    #         else:
    #             selected_period_str_view = st.selectbox("Select MCM Period", options=period_options_list_view, key="pco_view_reports_sel_final_v2")
    #             if selected_period_str_view:
    #                 selected_period_k_for_view = next((k for k, p in all_periods_for_view.items() if f"{p.get('month_name')} {p.get('year')}" == selected_period_str_view), None)
    #                 if selected_period_k_for_view and sheets_service:
    #                     sheet_id_for_report_view = all_periods_for_view[selected_period_k_for_view]['spreadsheet_id']
    #                     with st.spinner("Loading data from Google Sheet..."):
    #                         df_report_data = read_from_spreadsheet(sheets_service, sheet_id_for_report_view)
    #                     if df_report_data is not None and not df_report_data.empty:
    #                         st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
    #                         if 'Audit Group Number' in df_report_data.columns:
    #                             try:
    #                                 df_report_data['Audit Group Number Numeric'] = pd.to_numeric(df_report_data['Audit Group Number'], errors='coerce')
    #                                 df_summary_reports = df_report_data.dropna(subset=['Audit Group Number Numeric'])
    #                                 dars_per_group_rep = df_summary_reports.groupby('Audit Group Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
    #                                 st.write("**DARs Uploaded per Audit Group:**")
    #                                 st.dataframe(dars_per_group_rep, use_container_width=True)
    #                                 paras_per_group_rep = df_summary_reports.groupby('Audit Group Number Numeric').size().reset_index(name='Total Para Entries')
    #                                 st.write("**Total Para Entries per Audit Group:**")
    #                                 st.dataframe(paras_per_group_rep, use_container_width=True)
    #                                 if 'Audit Circle Number' in df_report_data.columns:
    #                                     df_summary_reports['Audit Circle Number Numeric'] = pd.to_numeric(df_summary_reports['Audit Circle Number'], errors='coerce')
    #                                     dars_per_circle_rep = df_summary_reports.dropna(subset=['Audit Circle Number Numeric']).groupby('Audit Circle Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
    #                                     st.write("**DARs Uploaded per Audit Circle:**")
    #                                     st.dataframe(dars_per_circle_rep, use_container_width=True)
    #                                 if 'Status of para' in df_report_data.columns:
    #                                     status_summary_rep = df_summary_reports['Status of para'].value_counts().reset_index(name='Count')
    #                                     status_summary_rep.columns = ['Status of para', 'Count']
    #                                     st.write("**Para Status Summary:**")
    #                                     st.dataframe(status_summary_rep, use_container_width=True)
    #                                 st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True)
    #                                 st.dataframe(df_report_data, use_container_width=True)
    #                             except Exception as e_rep_sum:
    #                                 st.error(f"Error processing summary: {e_rep_sum}")
    #                                 st.dataframe(df_report_data, use_container_width=True)
    #                         else:
    #                             st.warning("Missing 'Audit Group Number' column for summary.")
    #                             st.dataframe(df_report_data, use_container_width=True)
    #                     elif df_report_data is None:
    #                         st.error("Could not load data from the spreadsheet.")
    #                     else:
    #                         st.info(f"No data in spreadsheet for {selected_period_str_view}.")
    #                 elif not sheets_service and selected_period_k_for_view:
    #                     st.error("Google Sheets service not available.")
    elif selected_tab == "MCM Agenda":
        mcm_agenda_tab(drive_service, sheets_service, mcm_periods) # Call the imported function
    # ========================== VISUALIZATIONS TAB ==========================
    # ========================== VISUALIZATIONS TAB ==========================
    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        all_mcm_periods_for_viz_tab = mcm_periods  # Use directly loaded mcm_periods
        if not all_mcm_periods_for_viz_tab:
            st.info("No MCM periods to visualize data from.")
        else:
            viz_options_list = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_mcm_periods_for_viz_tab.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
            if not viz_options_list and all_mcm_periods_for_viz_tab:
                st.warning("No valid MCM periods with complete month/year information for visualization options.")
            elif not viz_options_list:
                st.info("No MCM periods available to visualize.")
            else:
                selected_viz_period_str_tab = st.selectbox("Select MCM Period for Visualization", options=viz_options_list, key="pco_viz_selectbox_final_v4")
                if selected_viz_period_str_tab and sheets_service:
                    selected_viz_period_k_tab = next((k for k, p in all_mcm_periods_for_viz_tab.items() if f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_str_tab), None)
                    if selected_viz_period_k_tab:
                        sheet_id_for_viz_tab = all_mcm_periods_for_viz_tab[selected_viz_period_k_tab]['spreadsheet_id']
                        with st.spinner("Loading data for visualizations..."):
                            df_viz_data = read_from_spreadsheet(sheets_service, sheet_id_for_viz_tab)  # Main DataFrame for this tab
                        if df_viz_data is not None and not df_viz_data.empty:
                            # --- Data Cleaning and Preparation ---
                            viz_amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)', 'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
                            for v_col in viz_amount_cols:
                                if v_col in df_viz_data.columns:
                                    df_viz_data[v_col] = pd.to_numeric(df_viz_data[v_col], errors='coerce').fillna(0)
                            
                            if 'Audit Group Number' in df_viz_data.columns:
                                df_viz_data['Audit Group Number'] = pd.to_numeric(df_viz_data['Audit Group Number'], errors='coerce').fillna(0).astype(int)
    
                            # --- De-duplicate data for aggregated charts to prevent inflated sums ---
                            if 'DAR PDF URL' in df_viz_data.columns and df_viz_data['DAR PDF URL'].notna().any():
                                df_unique_reports = df_viz_data.drop_duplicates(subset=['DAR PDF URL']).copy()
                            else:
                                st.warning("⚠️ 'DAR PDF URL' column not found. Chart sums might be inflated due to repeated values.", icon=" ")
                                df_unique_reports = df_viz_data.copy()
    
                            # --- NEW: Summary Table ---
                            st.markdown("#### Monthly Performance Summary")
                            
                            # --- Calculations for Summary ---
                            num_dars = df_unique_reports['DAR PDF URL'].nunique()
                            total_detected = df_unique_reports['Total Amount Detected (Overall Rs)'].sum()
                            total_recovered = df_unique_reports['Total Amount Recovered (Overall Rs)'].sum()
    
                            dars_per_group = df_unique_reports[df_unique_reports['Audit Group Number'] > 0].groupby('Audit Group Number')['DAR PDF URL'].nunique()
                            
                            if not dars_per_group.empty:
                                max_dars_count = dars_per_group.max()
                                max_dars_group = dars_per_group.idxmax()
                                max_group_str = f"AG {max_dars_group} ({max_dars_count} DARs)"
                            else:
                                max_group_str = "N/A"
    
                            # Assuming total audit groups are from 1 to 30. This should ideally come from a config file.
                            all_audit_groups = set(range(1, 31)) 
                            submitted_groups = set(dars_per_group.index)
                            zero_dar_groups = sorted(list(all_audit_groups - submitted_groups))
                            zero_dar_groups_str = ", ".join(map(str, zero_dar_groups)) if zero_dar_groups else "None"
    
                            # --- Display Summary ---
                            col1, col2, col3 = st.columns(3)
                            col1.metric(label="✅ No. of DARs Submitted", value=f"{num_dars}")
                            col2.metric(label="💰 Total Revenue Involved", value=f"₹{total_detected/100000:.2f} Lakhs")
                            col3.metric(label="🏆 Total Revenue Recovered", value=f"₹{total_recovered/100000:.2f} Lakhs")
    
                            st.markdown(f"**Maximum DARs by:** `{max_group_str}`")
                            st.markdown(f"**Audit Groups with Zero DARs:** `{zero_dar_groups_str}`")
    
                            # --- End of Summary Table ---
    
                            # --- NEW: Convert amounts to Lakhs on the de-duplicated data for clear visualization ---
                            if 'Total Amount Detected (Overall Rs)' in df_unique_reports.columns:
                                df_unique_reports['Detection in Lakhs'] = df_unique_reports['Total Amount Detected (Overall Rs)'] / 100000.0
                            if 'Total Amount Recovered (Overall Rs)' in df_unique_reports.columns:
                                df_unique_reports['Recovery in Lakhs'] = df_unique_reports['Total Amount Recovered (Overall Rs)'] / 100000.0
    
    
                            # Prepare other columns for categorization and grouping
                            for df in [df_viz_data, df_unique_reports]:
                                if 'Audit Group Number' in df.columns:
                                    df['Audit Group Number'] = pd.to_numeric(df['Audit Group Number'], errors='coerce').fillna(0).astype(int)
                                else:
                                    df['Audit Group Number'] = 0
                                df['Audit Group Number Str'] = df['Audit Group Number'].astype(str)
                                
                                if 'Audit Circle Number' in df.columns and df['Audit Circle Number'].notna().any() and pd.to_numeric(df['Audit Circle Number'], errors='coerce').notna().any():
                                    df['Circle Number For Plot'] = pd.to_numeric(df['Audit Circle Number'], errors='coerce').fillna(0).astype(int)
                                elif 'Audit Group Number' in df.columns and not df['Audit Group Number'].eq(0).all():
                                    df['Circle Number For Plot'] = ((df['Audit Group Number'] - 1) // 3 + 1).astype(int)
                                else:
                                    df['Circle Number For Plot'] = 0
                                df['Circle Number Str Plot'] = df['Circle Number For Plot'].astype(str)
                                
                                df['Category'] = df.get('Category', pd.Series(dtype='str')).fillna('Unknown')
                                df['Trade Name'] = df.get('Trade Name', pd.Series(dtype='str')).fillna('Unknown Trade Name')
                                df['Status of para'] = df.get('Status of para', pd.Series(dtype='str')).fillna('Unknown')
    
                            # --- Para Status Distribution (uses original full data) ---
                            st.markdown("---")
                            st.markdown("<h4>Para Status Distribution</h4>", unsafe_allow_html=True)
                            if 'Status of para' in df_viz_data.columns and df_viz_data['Status of para'].nunique() > 1:
                                viz_status_counts = df_viz_data['Status of para'].value_counts().reset_index()
                                viz_status_counts.columns = ['Status of para', 'Count']
                                viz_fig_status_dist = px.bar(viz_status_counts, x='Status of para', y='Count', text_auto=True, title="Distribution of Para Statuses", labels={'Status of para': '<b>Status</b>', 'Count': 'Number of Paras'})
                                viz_fig_status_dist.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
                                viz_fig_status_dist.update_traces(textposition='outside', marker_color='teal')
                                st.plotly_chart(viz_fig_status_dist, use_container_width=True)
                            else:
                                st.info("Not enough data for 'Status of para' distribution chart.")
    
                            # --- Group-wise Performance (uses de-duplicated data and shows in Lakhs) ---
                            st.markdown("---")
                            st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
                            if 'Detection in Lakhs' in df_unique_reports.columns and (df_unique_reports['Audit Group Number'].nunique() > 1 or (df_unique_reports['Audit Group Number'].nunique() == 1 and df_unique_reports['Audit Group Number'].iloc[0] != 0)):
                                viz_detection_data = df_unique_reports.groupby('Audit Group Number Str')['Detection in Lakhs'].sum().reset_index().sort_values(by='Detection in Lakhs', ascending=False).nlargest(5, 'Detection in Lakhs')
                                if not viz_detection_data.empty:
                                    st.write("**Top 5 Groups by Total Detection Amount (Lakhs Rs):**")
                                    fig_det_grp = px.bar(viz_detection_data, x='Audit Group Number Str', y='Detection in Lakhs', text_auto='.2f', labels={'Detection in Lakhs': 'Total Detection (Lakhs Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
                                    fig_det_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
                                    fig_det_grp.update_traces(textposition='outside', marker_color='indianred')
                                    st.plotly_chart(fig_det_grp, use_container_width=True)
                            
                            if 'Recovery in Lakhs' in df_unique_reports.columns and (df_unique_reports['Audit Group Number'].nunique() > 1 or (df_unique_reports['Audit Group Number'].nunique() == 1 and df_unique_reports['Audit Group Number'].iloc[0] != 0)):
                                viz_recovery_data = df_unique_reports.groupby('Audit Group Number Str')['Recovery in Lakhs'].sum().reset_index().sort_values(by='Recovery in Lakhs', ascending=False).nlargest(5, 'Recovery in Lakhs')
                                if not viz_recovery_data.empty:
                                    st.write("**Top 5 Groups by Total Realisation Amount (Lakhs Rs):**")
                                    fig_rec_grp = px.bar(viz_recovery_data, x='Audit Group Number Str', y='Recovery in Lakhs', text_auto='.2f', labels={'Recovery in Lakhs': 'Total Realisation (Lakhs Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
                                    fig_rec_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
                                    fig_rec_grp.update_traces(textposition='outside', marker_color='lightseagreen')
                                    st.plotly_chart(fig_rec_grp, use_container_width=True)
    
                            # --- Circle-wise Performance (uses de-duplicated data and shows in Lakhs) ---
                            st.markdown("---")
                            st.markdown("<h4>Circle-wise Performance Metrics</h4>", unsafe_allow_html=True)
                            if 'Circle Number Str Plot' in df_unique_reports and (df_unique_reports['Circle Number For Plot'].nunique() > 1 or (df_unique_reports['Circle Number For Plot'].nunique() == 1 and df_unique_reports['Circle Number For Plot'].iloc[0] != 0)):
                                if 'Recovery in Lakhs' in df_unique_reports.columns:
                                    recovery_per_circle_plot = df_unique_reports.groupby('Circle Number Str Plot')['Recovery in Lakhs'].sum().reset_index().sort_values(by='Recovery in Lakhs', ascending=False)
                                    if not recovery_per_circle_plot.empty:
                                        st.write("**Total Recovery Amount (Lakhs Rs) per Circle (Descending):**")
                                        fig_rec_circle_plot = px.bar(recovery_per_circle_plot, x='Circle Number Str Plot', y='Recovery in Lakhs', text_auto='.2f', labels={'Recovery in Lakhs': 'Total Recovery (Lakhs Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Recovery")
                                        fig_rec_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
                                        fig_rec_circle_plot.update_traces(textposition='outside', marker_color='goldenrod')
                                        st.plotly_chart(fig_rec_circle_plot, use_container_width=True)
                            
                                if 'Detection in Lakhs' in df_unique_reports.columns:
                                    detection_per_circle_plot = df_unique_reports.groupby('Circle Number Str Plot')['Detection in Lakhs'].sum().reset_index().sort_values(by='Detection in Lakhs', ascending=False)
                                    if not detection_per_circle_plot.empty:
                                        st.write("**Total Detection Amount (Lakhs Rs) per Circle (Descending):**")
                                        fig_det_circle_plot = px.bar(detection_per_circle_plot, x='Circle Number Str Plot', y='Detection in Lakhs', text_auto='.2f', labels={'Detection in Lakhs': 'Total Detection (Lakhs Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Detection")
                                        fig_det_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
                                        fig_det_circle_plot.update_traces(textposition='outside', marker_color='mediumseagreen')
                                        st.plotly_chart(fig_det_circle_plot, use_container_width=True)
    
                            # --- Treemap Visualizations (uses de-duplicated data and shows in Lakhs) ---
                            st.markdown("---")
                            st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
                            if 'Detection in Lakhs' in df_unique_reports.columns:
                                viz_df_detection_treemap = df_unique_reports[df_unique_reports['Detection in Lakhs'] > 0]
                                if not viz_df_detection_treemap.empty:
                                    st.write("**Detection Amounts (Lakhs Rs) by Trade Name (Size: Amount, Color: Category)**")
                                    viz_fig_treemap_detection = px.treemap(viz_df_detection_treemap, path=[px.Constant("All Detections"), 'Category', 'Trade Name'], values='Detection in Lakhs', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
                                    viz_fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
                                    viz_fig_treemap_detection.data[0].textinfo = 'label+value'
                                    viz_fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Lakhs Rs<extra></extra>")
                                    st.plotly_chart(viz_fig_treemap_detection, use_container_width=True)
                            
                            if 'Recovery in Lakhs' in df_unique_reports.columns:
                                viz_df_recovery_treemap = df_unique_reports[df_unique_reports['Recovery in Lakhs'] > 0]
                                if not viz_df_recovery_treemap.empty:
                                    st.write("**Recovery Amounts (Lakhs Rs) by Trade Name (Size: Amount, Color: Category)**")
                                    viz_fig_treemap_recovery = px.treemap(viz_df_recovery_treemap, path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'], values='Recovery in Lakhs', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
                                    viz_fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
                                    viz_fig_treemap_recovery.data[0].textinfo = 'label+value'
                                    viz_fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Lakhs Rs<extra></extra>")
                                    st.plotly_chart(viz_fig_treemap_recovery, use_container_width=True)
    
                            # --- Para-wise Performance (uses original full data) ---
                            st.markdown("---")
                            st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
                            if 'num_paras_to_show_pco' not in st.session_state:
                                st.session_state.num_paras_to_show_pco = 5
                            viz_n_paras_input = st.text_input("Enter N for Top N Paras (e.g., 5):", value=str(st.session_state.num_paras_to_show_pco), key="pco_n_paras_input_final_v2")
                            viz_num_paras_show = st.session_state.num_paras_to_show_pco
                            try:
                                viz_parsed_n = int(viz_n_paras_input)
                                if viz_parsed_n < 1:
                                    viz_num_paras_show = 5
                                    st.warning("N must be positive. Showing Top 5.", icon="⚠️")
                                elif viz_parsed_n > 50:
                                    viz_num_paras_show = 50
                                    st.warning("N capped at 50. Showing Top 50.", icon="⚠️")
                                else:
                                    viz_num_paras_show = viz_parsed_n
                                st.session_state.num_paras_to_show_pco = viz_num_paras_show
                            except ValueError:
                                if viz_n_paras_input != str(st.session_state.num_paras_to_show_pco):
                                    st.warning(f"Invalid N ('{viz_n_paras_input}'). Using: {viz_num_paras_show}", icon="⚠️")
                            
                            viz_df_paras_only = df_viz_data[df_viz_data['Audit Para Number'].notna() & (~df_viz_data['Audit Para Heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
                            if 'Revenue Involved (Lakhs Rs)' in viz_df_paras_only.columns:
                                viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Involved (Lakhs Rs)')
                                if not viz_top_det_paras.empty:
                                    st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**")
                                    viz_disp_cols_det = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)', 'Status of para']
                                    viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]
                                    st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
                            if 'Revenue Recovered (Lakhs Rs)' in viz_df_paras_only.columns:
                                viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Recovered (Lakhs Rs)')
                                if not viz_top_rec_paras.empty:
                                    st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**")
                                    viz_disp_cols_rec = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)', 'Status of para']
                                    viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]
                                    st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
    
                        elif df_viz_data is None:
                            st.error("Error reading data from spreadsheet for visualization.")
                        else:
                            st.info(f"No data in spreadsheet for {selected_viz_period_str_tab} to visualize.")
                    elif not sheets_service and selected_viz_period_k_tab:
                        st.error("Google Sheets service unavailable when trying to load visualization data.")
                    elif not sheets_service and selected_viz_period_str_tab:
                        st.error("Google Sheets service is not available.")
    # ADD THIS ELIF BLOCK for the new "Reports" tab
    elif selected_tab == "Reports":
        pco_reports_dashboard(drive_service, sheets_service)

    # elif selected_tab == "Visualizations":
    #     st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
    #     all_mcm_periods_for_viz_tab = mcm_periods  # Use directly loaded mcm_periods
    #     if not all_mcm_periods_for_viz_tab:
    #         st.info("No MCM periods to visualize data from.")
    #     else:
    #         viz_options_list = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_mcm_periods_for_viz_tab.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
    #         if not viz_options_list and all_mcm_periods_for_viz_tab:
    #             st.warning("No valid MCM periods with complete month/year information for visualization options.")
    #         elif not viz_options_list:
    #             st.info("No MCM periods available to visualize.")
    #         else:
    #             selected_viz_period_str_tab = st.selectbox("Select MCM Period for Visualization", options=viz_options_list, key="pco_viz_selectbox_final_v4")
    #             if selected_viz_period_str_tab and sheets_service:
    #                 selected_viz_period_k_tab = next((k for k, p in all_mcm_periods_for_viz_tab.items() if f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_str_tab), None)
    #                 if selected_viz_period_k_tab:
    #                     sheet_id_for_viz_tab = all_mcm_periods_for_viz_tab[selected_viz_period_k_tab]['spreadsheet_id']
    #                     with st.spinner("Loading data for visualizations..."):
    #                         df_viz_data = read_from_spreadsheet(sheets_service, sheet_id_for_viz_tab)  # Main DataFrame for this tab
    #                     if df_viz_data is not None and not df_viz_data.empty:
    #                         # --- Data Cleaning and Preparation ---
    #                         viz_amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)', 'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
    #                         for v_col in viz_amount_cols:
    #                             if v_col in df_viz_data.columns:
    #                                 df_viz_data[v_col] = pd.to_numeric(df_viz_data[v_col], errors='coerce').fillna(0)
                            
    #                         # --- De-duplicate data for aggregated charts to prevent inflated sums ---
    #                         if 'DAR PDF URL' in df_viz_data.columns and df_viz_data['DAR PDF URL'].notna().any():
    #                             df_unique_reports = df_viz_data.drop_duplicates(subset=['DAR PDF URL']).copy()
    #                         else:
    #                             st.warning("⚠️ 'DAR PDF URL' column not found. Chart sums might be inflated due to repeated values.", icon=" ")
    #                             df_unique_reports = df_viz_data.copy()
    
    #                         # --- NEW: Convert amounts to Lakhs on the de-duplicated data for clear visualization ---
    #                         if 'Total Amount Detected (Overall Rs)' in df_unique_reports.columns:
    #                             df_unique_reports['Detection in Lakhs'] = df_unique_reports['Total Amount Detected (Overall Rs)'] / 100000.0
    #                         if 'Total Amount Recovered (Overall Rs)' in df_unique_reports.columns:
    #                             df_unique_reports['Recovery in Lakhs'] = df_unique_reports['Total Amount Recovered (Overall Rs)'] / 100000.0
    
    
    #                         # Prepare other columns for categorization and grouping
    #                         for df in [df_viz_data, df_unique_reports]:
    #                             if 'Audit Group Number' in df.columns:
    #                                 df['Audit Group Number'] = pd.to_numeric(df['Audit Group Number'], errors='coerce').fillna(0).astype(int)
    #                             else:
    #                                 df['Audit Group Number'] = 0
    #                             df['Audit Group Number Str'] = df['Audit Group Number'].astype(str)
                                
    #                             if 'Audit Circle Number' in df.columns and df['Audit Circle Number'].notna().any() and pd.to_numeric(df['Audit Circle Number'], errors='coerce').notna().any():
    #                                 df['Circle Number For Plot'] = pd.to_numeric(df['Audit Circle Number'], errors='coerce').fillna(0).astype(int)
    #                             elif 'Audit Group Number' in df.columns and not df['Audit Group Number'].eq(0).all():
    #                                 df['Circle Number For Plot'] = ((df['Audit Group Number'] - 1) // 3 + 1).astype(int)
    #                             else:
    #                                 df['Circle Number For Plot'] = 0
    #                             df['Circle Number Str Plot'] = df['Circle Number For Plot'].astype(str)
                                
    #                             df['Category'] = df.get('Category', pd.Series(dtype='str')).fillna('Unknown')
    #                             df['Trade Name'] = df.get('Trade Name', pd.Series(dtype='str')).fillna('Unknown Trade Name')
    #                             df['Status of para'] = df.get('Status of para', pd.Series(dtype='str')).fillna('Unknown')
    
    #                         # --- Para Status Distribution (uses original full data) ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Para Status Distribution</h4>", unsafe_allow_html=True)
    #                         if 'Status of para' in df_viz_data.columns and df_viz_data['Status of para'].nunique() > 1:
    #                             viz_status_counts = df_viz_data['Status of para'].value_counts().reset_index()
    #                             viz_status_counts.columns = ['Status of para', 'Count']
    #                             viz_fig_status_dist = px.bar(viz_status_counts, x='Status of para', y='Count', text_auto=True, title="Distribution of Para Statuses", labels={'Status of para': '<b>Status</b>', 'Count': 'Number of Paras'})
    #                             viz_fig_status_dist.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                             viz_fig_status_dist.update_traces(textposition='outside', marker_color='teal')
    #                             st.plotly_chart(viz_fig_status_dist, use_container_width=True)
    #                         else:
    #                             st.info("Not enough data for 'Status of para' distribution chart.")
    
    #                         # --- Group-wise Performance (uses de-duplicated data and shows in Lakhs) ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
    #                         if 'Detection in Lakhs' in df_unique_reports.columns and (df_unique_reports['Audit Group Number'].nunique() > 1 or (df_unique_reports['Audit Group Number'].nunique() == 1 and df_unique_reports['Audit Group Number'].iloc[0] != 0)):
    #                             viz_detection_data = df_unique_reports.groupby('Audit Group Number Str')['Detection in Lakhs'].sum().reset_index().sort_values(by='Detection in Lakhs', ascending=False).nlargest(5, 'Detection in Lakhs')
    #                             if not viz_detection_data.empty:
    #                                 st.write("**Top 5 Groups by Total Detection Amount (Lakhs Rs):**")
    #                                 fig_det_grp = px.bar(viz_detection_data, x='Audit Group Number Str', y='Detection in Lakhs', text_auto='.2f', labels={'Detection in Lakhs': 'Total Detection (Lakhs Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
    #                                 fig_det_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                 fig_det_grp.update_traces(textposition='outside', marker_color='indianred')
    #                                 st.plotly_chart(fig_det_grp, use_container_width=True)
                            
    #                         if 'Recovery in Lakhs' in df_unique_reports.columns and (df_unique_reports['Audit Group Number'].nunique() > 1 or (df_unique_reports['Audit Group Number'].nunique() == 1 and df_unique_reports['Audit Group Number'].iloc[0] != 0)):
    #                             viz_recovery_data = df_unique_reports.groupby('Audit Group Number Str')['Recovery in Lakhs'].sum().reset_index().sort_values(by='Recovery in Lakhs', ascending=False).nlargest(5, 'Recovery in Lakhs')
    #                             if not viz_recovery_data.empty:
    #                                 st.write("**Top 5 Groups by Total Realisation Amount (Lakhs Rs):**")
    #                                 fig_rec_grp = px.bar(viz_recovery_data, x='Audit Group Number Str', y='Recovery in Lakhs', text_auto='.2f', labels={'Recovery in Lakhs': 'Total Realisation (Lakhs Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
    #                                 fig_rec_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                 fig_rec_grp.update_traces(textposition='outside', marker_color='lightseagreen')
    #                                 st.plotly_chart(fig_rec_grp, use_container_width=True)
    
    #                         # --- Circle-wise Performance (uses de-duplicated data and shows in Lakhs) ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Circle-wise Performance Metrics</h4>", unsafe_allow_html=True)
    #                         if 'Circle Number Str Plot' in df_unique_reports and (df_unique_reports['Circle Number For Plot'].nunique() > 1 or (df_unique_reports['Circle Number For Plot'].nunique() == 1 and df_unique_reports['Circle Number For Plot'].iloc[0] != 0)):
    #                             if 'Recovery in Lakhs' in df_unique_reports.columns:
    #                                 recovery_per_circle_plot = df_unique_reports.groupby('Circle Number Str Plot')['Recovery in Lakhs'].sum().reset_index().sort_values(by='Recovery in Lakhs', ascending=False)
    #                                 if not recovery_per_circle_plot.empty:
    #                                     st.write("**Total Recovery Amount (Lakhs Rs) per Circle (Descending):**")
    #                                     fig_rec_circle_plot = px.bar(recovery_per_circle_plot, x='Circle Number Str Plot', y='Recovery in Lakhs', text_auto='.2f', labels={'Recovery in Lakhs': 'Total Recovery (Lakhs Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Recovery")
    #                                     fig_rec_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_rec_circle_plot.update_traces(textposition='outside', marker_color='goldenrod')
    #                                     st.plotly_chart(fig_rec_circle_plot, use_container_width=True)
    
    #                             if 'Detection in Lakhs' in df_unique_reports.columns:
    #                                 detection_per_circle_plot = df_unique_reports.groupby('Circle Number Str Plot')['Detection in Lakhs'].sum().reset_index().sort_values(by='Detection in Lakhs', ascending=False)
    #                                 if not detection_per_circle_plot.empty:
    #                                     st.write("**Total Detection Amount (Lakhs Rs) per Circle (Descending):**")
    #                                     fig_det_circle_plot = px.bar(detection_per_circle_plot, x='Circle Number Str Plot', y='Detection in Lakhs', text_auto='.2f', labels={'Detection in Lakhs': 'Total Detection (Lakhs Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Detection")
    #                                     fig_det_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_det_circle_plot.update_traces(textposition='outside', marker_color='mediumseagreen')
    #                                     st.plotly_chart(fig_det_circle_plot, use_container_width=True)
    
    #                         # --- Treemap Visualizations (uses de-duplicated data and shows in Lakhs) ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
    #                         if 'Detection in Lakhs' in df_unique_reports.columns:
    #                             viz_df_detection_treemap = df_unique_reports[df_unique_reports['Detection in Lakhs'] > 0]
    #                             if not viz_df_detection_treemap.empty:
    #                                 st.write("**Detection Amounts (Lakhs Rs) by Trade Name (Size: Amount, Color: Category)**")
    #                                 viz_fig_treemap_detection = px.treemap(viz_df_detection_treemap, path=[px.Constant("All Detections"), 'Category', 'Trade Name'], values='Detection in Lakhs', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
    #                                 viz_fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
    #                                 viz_fig_treemap_detection.data[0].textinfo = 'label+value'
    #                                 viz_fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Lakhs Rs<extra></extra>")
    #                                 st.plotly_chart(viz_fig_treemap_detection, use_container_width=True)
    
    #                         if 'Recovery in Lakhs' in df_unique_reports.columns:
    #                             viz_df_recovery_treemap = df_unique_reports[df_unique_reports['Recovery in Lakhs'] > 0]
    #                             if not viz_df_recovery_treemap.empty:
    #                                 st.write("**Recovery Amounts (Lakhs Rs) by Trade Name (Size: Amount, Color: Category)**")
    #                                 viz_fig_treemap_recovery = px.treemap(viz_df_recovery_treemap, path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'], values='Recovery in Lakhs', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
    #                                 viz_fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
    #                                 viz_fig_treemap_recovery.data[0].textinfo = 'label+value'
    #                                 viz_fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Lakhs Rs<extra></extra>")
    #                                 st.plotly_chart(viz_fig_treemap_recovery, use_container_width=True)
    
    #                         # --- Para-wise Performance (uses original full data) ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
    #                         if 'num_paras_to_show_pco' not in st.session_state:
    #                             st.session_state.num_paras_to_show_pco = 5
    #                         viz_n_paras_input = st.text_input("Enter N for Top N Paras (e.g., 5):", value=str(st.session_state.num_paras_to_show_pco), key="pco_n_paras_input_final_v2")
    #                         viz_num_paras_show = st.session_state.num_paras_to_show_pco
    #                         try:
    #                             viz_parsed_n = int(viz_n_paras_input)
    #                             if viz_parsed_n < 1:
    #                                 viz_num_paras_show = 5
    #                                 st.warning("N must be positive. Showing Top 5.", icon="⚠️")
    #                             elif viz_parsed_n > 50:
    #                                 viz_num_paras_show = 50
    #                                 st.warning("N capped at 50. Showing Top 50.", icon="⚠️")
    #                             else:
    #                                 viz_num_paras_show = viz_parsed_n
    #                             st.session_state.num_paras_to_show_pco = viz_num_paras_show
    #                         except ValueError:
    #                             if viz_n_paras_input != str(st.session_state.num_paras_to_show_pco):
    #                                 st.warning(f"Invalid N ('{viz_n_paras_input}'). Using: {viz_num_paras_show}", icon="⚠️")
                            
    #                         viz_df_paras_only = df_viz_data[df_viz_data['Audit Para Number'].notna() & (~df_viz_data['Audit Para Heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
    #                         if 'Revenue Involved (Lakhs Rs)' in viz_df_paras_only.columns:
    #                             viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Involved (Lakhs Rs)')
    #                             if not viz_top_det_paras.empty:
    #                                 st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**")
    #                                 viz_disp_cols_det = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)', 'Status of para']
    #                                 viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]
    #                                 st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
    #                         if 'Revenue Recovered (Lakhs Rs)' in viz_df_paras_only.columns:
    #                             viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Recovered (Lakhs Rs)')
    #                             if not viz_top_rec_paras.empty:
    #                                 st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**")
    #                                 viz_disp_cols_rec = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)', 'Status of para']
    #                                 viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]
    #                                 st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
    
    #                     elif df_viz_data is None:
    #                         st.error("Error reading data from spreadsheet for visualization.")
    #                     else:
    #                         st.info(f"No data in spreadsheet for {selected_viz_period_str_tab} to visualize.")
    #                 elif not sheets_service and selected_viz_period_k_tab:
    #                     st.error("Google Sheets service unavailable when trying to load visualization data.")
    #                 elif not sheets_service and selected_viz_period_str_tab:
    #                     st.error("Google Sheets service is not available.")
    
        #st.markdown("</div>", unsafe_allow_html=True)
    # # ========================== VISUALIZATIONS TAB ==========================
    # elif selected_tab == "Visualizations":
    #     st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
    #     all_mcm_periods_for_viz_tab = mcm_periods  # Use directly loaded mcm_periods
    #     if not all_mcm_periods_for_viz_tab:
    #         st.info("No MCM periods to visualize data from.")
    #     else:
    #         viz_options_list = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_mcm_periods_for_viz_tab.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
    #         if not viz_options_list and all_mcm_periods_for_viz_tab:
    #             st.warning("No valid MCM periods with complete month/year information for visualization options.")
    #         elif not viz_options_list:
    #             st.info("No MCM periods available to visualize.")
    #         else:
    #             selected_viz_period_str_tab = st.selectbox("Select MCM Period for Visualization", options=viz_options_list, key="pco_viz_selectbox_final_v4")
    #             if selected_viz_period_str_tab and sheets_service:
    #                 selected_viz_period_k_tab = next((k for k, p in all_mcm_periods_for_viz_tab.items() if f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_str_tab), None)
    #                 if selected_viz_period_k_tab:
    #                     sheet_id_for_viz_tab = all_mcm_periods_for_viz_tab[selected_viz_period_k_tab]['spreadsheet_id']
    #                     with st.spinner("Loading data for visualizations..."):
    #                         df_viz_data = read_from_spreadsheet(sheets_service, sheet_id_for_viz_tab)  # Main DataFrame for this tab
    #                     if df_viz_data is not None and not df_viz_data.empty:
    #                         # --- Data Cleaning and Preparation ---
    #                         viz_amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)', 'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
    #                         for v_col in viz_amount_cols:
    #                             if v_col in df_viz_data.columns:
    #                                 df_viz_data[v_col] = pd.to_numeric(df_viz_data[v_col], errors='coerce').fillna(0)
                            
    #                         # Group Number for Group charts
    #                         if 'Audit Group Number' in df_viz_data.columns:
    #                             df_viz_data['Audit Group Number'] = pd.to_numeric(df_viz_data['Audit Group Number'], errors='coerce').fillna(0).astype(int)
    #                         else:
    #                             df_viz_data['Audit Group Number'] = 0 
    #                         df_viz_data['Audit Group Number Str'] = df_viz_data['Audit Group Number'].astype(str)
                            
    #                         # Circle Number: Prioritize from sheet, then derive
    #                         if 'Audit Circle Number' in df_viz_data.columns and df_viz_data['Audit Circle Number'].notna().any() and pd.to_numeric(df_viz_data['Audit Circle Number'], errors='coerce').notna().any():
    #                             df_viz_data['Circle Number For Plot'] = pd.to_numeric(df_viz_data['Audit Circle Number'], errors='coerce').fillna(0).astype(int)
    #                             # st.caption("Using 'Audit Circle Number' from sheet for circle-wise charts.")
    #                         elif 'Audit Group Number' in df_viz_data.columns and df_viz_data['Audit Group Number'].iloc[0] != 0:  # Check if group number is valid before deriving
    #                             df_viz_data['Circle Number For Plot'] = ((df_viz_data['Audit Group Number'] - 1) // 3 + 1).astype(int)
    #                             # st.caption("Deriving 'Circle Number' from 'Audit Group Number' for charts as sheet column was missing/invalid.")
    #                         else:
    #                             # st.warning("'Audit Circle Number' (from sheet) and 'Audit Group Number' (for derivation) are missing or invalid. Circle charts may be affected.")
    #                             df_viz_data['Circle Number For Plot'] = 0  # Placeholder
    #                         df_viz_data['Circle Number Str Plot'] = df_viz_data['Circle Number For Plot'].astype(str)
                            
    #                         df_viz_data['Category'] = df_viz_data.get('Category', pd.Series(dtype='str')).fillna('Unknown')
    #                         df_viz_data['Trade Name'] = df_viz_data.get('Trade Name', pd.Series(dtype='str')).fillna('Unknown Trade Name')
    #                         df_viz_data['Status of para'] = df_viz_data.get('Status of para', pd.Series(dtype='str')).fillna('Unknown')

    #                         # --- Para Status Distribution ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Para Status Distribution</h4>", unsafe_allow_html=True)
    #                         if 'Status of para' in df_viz_data.columns and df_viz_data['Status of para'].nunique() > 0 and not (df_viz_data['Status of para'].nunique() == 1 and df_viz_data['Status of para'].iloc[0] == 'Unknown'):
    #                             viz_status_counts = df_viz_data['Status of para'].value_counts().reset_index()
    #                             viz_status_counts.columns = ['Status of para', 'Count']
    #                             viz_fig_status_dist = px.bar(viz_status_counts, x='Status of para', y='Count', text_auto=True, title="Distribution of Para Statuses", labels={'Status of para': '<b>Status</b>', 'Count': 'Number of Paras'})
    #                             viz_fig_status_dist.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                             viz_fig_status_dist.update_traces(textposition='outside', marker_color='teal')
    #                             st.plotly_chart(viz_fig_status_dist, use_container_width=True)
    #                         else:
    #                             st.info("Not enough data for 'Status of para' distribution chart.")

    #                         # --- Group-wise Performance ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
    #                         if df_viz_data['Audit Group Number'].nunique() > 1 or (df_viz_data['Audit Group Number'].nunique() == 1 and df_viz_data['Audit Group Number'].iloc[0] != 0):
    #                             if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns:
    #                                 viz_detection_data = df_viz_data.groupby('Audit Group Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
    #                                 if not viz_detection_data.empty:
    #                                     st.write("**Top 5 Groups by Total Detection Amount (Rs):**")
    #                                     fig_det_grp = px.bar(viz_detection_data, x='Audit Group Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
    #                                     fig_det_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_det_grp.update_traces(textposition='outside', marker_color='indianred')
    #                                     st.plotly_chart(fig_det_grp, use_container_width=True)
    #                             if 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns:
    #                                 viz_recovery_data = df_viz_data.groupby('Audit Group Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
    #                                 if not viz_recovery_data.empty:
    #                                     st.write("**Top 5 Groups by Total Realisation Amount (Rs):**")
    #                                     fig_rec_grp = px.bar(viz_recovery_data, x='Audit Group Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
    #                                     fig_rec_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_rec_grp.update_traces(textposition='outside', marker_color='lightseagreen')
    #                                     st.plotly_chart(fig_rec_grp, use_container_width=True)
    #                             if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns and 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns:
    #                                 viz_grp_summary = df_viz_data.groupby('Audit Group Number Str').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index()
    #                                 viz_grp_summary['Recovery_Ratio'] = viz_grp_summary.apply(lambda r: (r['Total_Recovered'] / r['Total_Detected']) * 100 if pd.notna(r['Total_Detected']) and r['Total_Detected'] > 0 and pd.notna(r['Total_Recovered']) else 0, axis=1)
    #                                 viz_ratio_data = viz_grp_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
    #                                 if not viz_ratio_data.empty:
    #                                     st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**")
    #                                     fig_ratio_grp = px.bar(viz_ratio_data, x='Audit Group Number Str', y='Recovery_Ratio', text_auto=True, labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number Str': '<b>Audit Group</b>'})
    #                                     fig_ratio_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_ratio_grp.update_traces(textposition='outside', marker_color='mediumpurple')
    #                                     st.plotly_chart(fig_ratio_grp, use_container_width=True)
    #                         else:
    #                             st.info("Group-wise charts require valid 'Audit Group Number' data with more than one group or a non-zero group.")

    #                         # --- Circle-wise Performance ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Circle-wise Performance Metrics</h4>", unsafe_allow_html=True)
    #                         if 'Circle Number Str Plot' in df_viz_data and (df_viz_data['Circle Number For Plot'].nunique() > 1 or (df_viz_data['Circle Number For Plot'].nunique() == 1 and df_viz_data['Circle Number For Plot'].iloc[0] != 0)):
    #                             if 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns:
    #                                 recovery_per_circle_plot = df_viz_data.groupby('Circle Number Str Plot')['Total Amount Recovered (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False)
    #                                 if not recovery_per_circle_plot.empty:
    #                                     st.write("**Total Recovery Amount (Rs) per Circle (Descending):**")
    #                                     fig_rec_circle_plot = px.bar(recovery_per_circle_plot, x='Circle Number Str Plot', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Recovery (Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Recovery")
    #                                     fig_rec_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_rec_circle_plot.update_traces(textposition='outside', marker_color='goldenrod')
    #                                     st.plotly_chart(fig_rec_circle_plot, use_container_width=True)
    #                             if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns:
    #                                 detection_per_circle_plot = df_viz_data.groupby('Circle Number Str Plot')['Total Amount Detected (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Detected (Overall Rs)', ascending=False)
    #                                 if not detection_per_circle_plot.empty:
    #                                     st.write("**Total Detection Amount (Rs) per Circle (Descending):**")
    #                                     fig_det_circle_plot = px.bar(detection_per_circle_plot, x='Circle Number Str Plot', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Detection")
    #                                     fig_det_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_det_circle_plot.update_traces(textposition='outside', marker_color='mediumseagreen')
    #                                     st.plotly_chart(fig_det_circle_plot, use_container_width=True)
    #                             if 'DAR PDF URL' in df_viz_data.columns:
    #                                 dars_per_circle_plot = df_viz_data.groupby('Circle Number Str Plot')['DAR PDF URL'].nunique().reset_index(name='DARs Sponsored').sort_values(by='DARs Sponsored', ascending=False)
    #                                 if not dars_per_circle_plot.empty:
    #                                     st.write("**DARs Sponsored per Circle (Descending):**")
    #                                     fig_dars_circle_plot = px.bar(dars_per_circle_plot, x='Circle Number Str Plot', y='DARs Sponsored', text_auto=True, labels={'DARs Sponsored': 'Number of DARs Sponsored', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise DARs Sponsored")
    #                                     fig_dars_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                                     fig_dars_circle_plot.update_traces(textposition='outside', marker_color='skyblue')
    #                                     st.plotly_chart(fig_dars_circle_plot, use_container_width=True)
    #                         else:
    #                             st.info("Not enough distinct and valid circle data to plot circle-wise charts.")
                            
    #                         # --- Treemap Visualizations ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
    #                         if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns and 'Trade Name' in df_viz_data.columns and 'Category' in df_viz_data.columns:
    #                             viz_df_detection_treemap_source = df_viz_data[df_viz_data['Total Amount Detected (Overall Rs)'] > 0].copy()
    #                             viz_df_detection_treemap_unique_dars = viz_df_detection_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in viz_df_detection_treemap_source.columns and viz_df_detection_treemap_source['DAR PDF URL'].notna().any() else viz_df_detection_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Detected (Overall Rs)'])
    #                             if not viz_df_detection_treemap_unique_dars.empty:
    #                                 st.write("**Detection Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
    #                                 try:
    #                                     viz_fig_treemap_detection = px.treemap(viz_df_detection_treemap_unique_dars, path=[px.Constant("All Detections"), 'Category', 'Trade Name'], values='Total Amount Detected (Overall Rs)', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
    #                                     viz_fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
    #                                     viz_fig_treemap_detection.data[0].textinfo = 'label+value'
    #                                     viz_fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Rs<extra></extra>")
    #                                     st.plotly_chart(viz_fig_treemap_detection, use_container_width=True)
    #                                 except Exception as e_viz_treemap_det:
    #                                     st.error(f"Could not generate detection treemap: {e_viz_treemap_det}")
    #                             else:
    #                                 st.info("No positive detection data (Overall Rs) for treemap.")
    #                         else:
    #                             st.info("Required columns for Detection Treemap missing.")
    #                         if 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns and 'Trade Name' in df_viz_data.columns and 'Category' in df_viz_data.columns:
    #                             viz_df_recovery_treemap_source = df_viz_data[df_viz_data['Total Amount Recovered (Overall Rs)'] > 0].copy()
    #                             viz_df_recovery_treemap_unique_dars = viz_df_recovery_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in viz_df_recovery_treemap_source.columns and viz_df_recovery_treemap_source['DAR PDF URL'].notna().any() else viz_df_recovery_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Recovered (Overall Rs)'])
    #                             if not viz_df_recovery_treemap_unique_dars.empty:
    #                                 st.write("**Recovery Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
    #                                 try:
    #                                     viz_fig_treemap_recovery = px.treemap(viz_df_recovery_treemap_unique_dars, path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'], values='Total Amount Recovered (Overall Rs)', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
    #                                     viz_fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
    #                                     viz_fig_treemap_recovery.data[0].textinfo = 'label+value'
    #                                     viz_fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Rs<extra></extra>")
    #                                     st.plotly_chart(viz_fig_treemap_recovery, use_container_width=True)
    #                                 except Exception as e_viz_treemap_rec:
    #                                     st.error(f"Could not generate recovery treemap: {e_viz_treemap_rec}")
    #                             else:
    #                                 st.info("No positive recovery data (Overall Rs) for treemap.")
    #                         else:
    #                             st.info("Required columns for Recovery Treemap missing.")

    #                         # --- Para-wise Performance ---
    #                         st.markdown("---")
    #                         st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
    #                         if 'num_paras_to_show_pco' not in st.session_state:
    #                             st.session_state.num_paras_to_show_pco = 5
    #                         viz_n_paras_input = st.text_input("Enter N for Top N Paras (e.g., 5):", value=str(st.session_state.num_paras_to_show_pco), key="pco_n_paras_input_final_v2")
    #                         viz_num_paras_show = st.session_state.num_paras_to_show_pco
    #                         try:
    #                             viz_parsed_n = int(viz_n_paras_input)
    #                             if viz_parsed_n < 1:
    #                                 viz_num_paras_show = 5
    #                                 st.warning("N must be positive. Showing Top 5.", icon="⚠️")
    #                             elif viz_parsed_n > 50:
    #                                 viz_num_paras_show = 50
    #                                 st.warning("N capped at 50. Showing Top 50.", icon="⚠️")
    #                             else:
    #                                 viz_num_paras_show = viz_parsed_n
    #                             st.session_state.num_paras_to_show_pco = viz_num_paras_show
    #                         except ValueError:
    #                             if viz_n_paras_input != str(st.session_state.num_paras_to_show_pco):
    #                                 st.warning(f"Invalid N ('{viz_n_paras_input}'). Using: {viz_num_paras_show}", icon="⚠️")
                            
    #                         viz_df_paras_only = df_viz_data[df_viz_data['Audit Para Number'].notna() & (~df_viz_data['Audit Para Heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
    #                         if 'Revenue Involved (Lakhs Rs)' in viz_df_paras_only.columns:
    #                             viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Involved (Lakhs Rs)')
    #                             if not viz_top_det_paras.empty:
    #                                 st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**")
    #                                 viz_disp_cols_det = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)', 'Status of para']
    #                                 viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]
    #                                 st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
    #                             else:
    #                                 st.info("No data for 'Top Detection Paras' list.")
    #                         if 'Revenue Recovered (Lakhs Rs)' in viz_df_paras_only.columns:
    #                             viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Recovered (Lakhs Rs)')
    #                             if not viz_top_rec_paras.empty:
    #                                 st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**")
    #                                 viz_disp_cols_rec = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)', 'Status of para']
    #                                 viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]
    #                                 st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
    #                             else:
    #                                 st.info("No data for 'Top Realisation Paras' list.")
    #                     elif df_viz_data is None:
    #                         st.error("Error reading data from spreadsheet for visualization.")
    #                     else:
    #                         st.info(f"No data in spreadsheet for {selected_viz_period_str_tab} to visualize.")
    #                 elif not sheets_service and selected_viz_period_k_tab:
    #                     st.error("Google Sheets service unavailable when trying to load visualization data.")
    #             elif not sheets_service and selected_viz_period_str_tab:
    #                 st.error("Google Sheets service is not available.")

    # st.markdown("</div>", unsafe_allow_html=True)  # Close the card div, aligned with function level# #ui_pco.py

