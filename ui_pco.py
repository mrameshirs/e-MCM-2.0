# ui_pco.py
import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
import math # For math.ceil if needed

# Assuming google_utils.py and config.py are in the same directory and correctly set up
from google_utils import (
    load_mcm_periods, save_mcm_periods, create_drive_folder,
    create_spreadsheet, read_from_spreadsheet
)
from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE

def pco_dashboard(drive_service, sheets_service):
    st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
    mcm_periods = load_mcm_periods(drive_service) # Direct load, no caching

    with st.sidebar:
        try:
            st.image("logo.png", width=80) # Use local logo
        except Exception as e:
            st.sidebar.warning(f"Could not load logo.png: {e}")
            st.sidebar.markdown("*(Logo)*")

        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        if st.button("Logout", key="pco_logout_full_final_v2", use_container_width=True): # Unique key
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

    selected_tab = option_menu(
        menu_title=None,
        options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "Visualizations"],
        icons=["calendar-plus-fill", "sliders", "eye-fill", "bar-chart-fill"],
        menu_icon="gear-wide-connected", default_index=0, orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#e9ecef"},
            "icon": {"color": "#007bff", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
            "nav-link-selected": {"background-color": "#007bff", "color": "white"},
        })

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
                            if save_mcm_periods(drive_service, mcm_periods_local_copy_create): # Save the updated dict
                                st.success(f"Successfully created MCM period for {selected_month_name} {selected_year}!")
                                st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>", unsafe_allow_html=True)
                                st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>", unsafe_allow_html=True)
                                st.balloons(); time.sleep(0.5); st.rerun() # Rerun to reflect new period
                            else: st.error("Failed to save MCM period configuration to Drive.")
                        else: st.error("Failed to create Drive folder or Spreadsheet.")

    # ========================== MANAGE MCM PERIODS TAB ==========================
    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: red;'>Pls Note ,Deleting the records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: green;'>Only the Months which are marked as 'Active' by Planning officer, will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
        
        mcm_periods_manage_local_copy = mcm_periods.copy() # Work with a copy

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
                with col1_manage: st.markdown(f"<a href='{data_for_manage.get('drive_folder_url', '#')}' target='_blank'>Drive Folder</a>", unsafe_allow_html=True)
                with col2_manage: st.markdown(f"<a href='{data_for_manage.get('spreadsheet_url', '#')}' target='_blank'>Spreadsheet</a>", unsafe_allow_html=True)
                with col3_manage:
                    is_active_current = data_for_manage.get("active", False)
                    new_status_current = st.checkbox("Active", value=is_active_current, key=f"active_manage_tab_{period_key_for_manage}")
                    if new_status_current != is_active_current:
                        mcm_periods_manage_local_copy[period_key_for_manage]["active"] = new_status_current
                        if save_mcm_periods(drive_service, mcm_periods_manage_local_copy):
                            st.success(f"Status for {month_name_disp_mng} {year_disp_mng} updated."); st.rerun()
                        else:
                            st.error("Failed to save updated status to Drive.")
                            mcm_periods_manage_local_copy[period_key_for_manage]["active"] = is_active_current # Revert local copy
                with col4_manage:
                    if st.button("Delete Period Record", key=f"delete_mcm_btn_mng_tab_{period_key_for_manage}", type="secondary"):
                        st.session_state.period_to_delete = period_key_for_manage; st.session_state.show_delete_confirm = True; st.rerun()
                st.markdown("---")

            if st.session_state.get('show_delete_confirm') and st.session_state.get('period_to_delete'):
                period_key_to_delete_confirm = st.session_state.period_to_delete
                period_data_to_delete_confirm = mcm_periods_manage_local_copy.get(period_key_to_delete_confirm, {})
                with st.form(key=f"delete_confirm_form_final_submit_v2_{period_key_to_delete_confirm}"): # Unique form key
                    st.warning(f"Are you sure you want to delete the MCM period record for **{period_data_to_delete_confirm.get('month_name')} {period_data_to_delete_confirm.get('year')}**?")
                    st.error("**Warning:** Delete period will delete the backend historic DAR data in the spreadsheet and drive. So use cautiously.")
                    st.caption(f"Currently, this action only removes the period's entry from the app's configuration file (`{MCM_PERIODS_FILENAME_ON_DRIVE}`). Backend logic for deleting Google Drive/Sheets resources needs to be implemented for the warning to be fully accurate.")
                    pco_password_confirm_del = st.text_input("Enter your PCO password:", type="password", key=f"pco_pass_del_confirm_final_{period_key_to_delete_confirm}")
                    form_c1, form_c2 = st.columns(2)
                    with form_c1: submitted_delete_final = st.form_submit_button("Yes, Delete Record from Tracking", use_container_width=True)
                    with form_c2:
                        if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
                            st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
                    if submitted_delete_final:
                        if pco_password_confirm_del == USER_CREDENTIALS.get("planning_officer"):
                            del mcm_periods_manage_local_copy[period_key_to_delete_confirm]
                            if save_mcm_periods(drive_service, mcm_periods_manage_local_copy):
                                st.success(f"MCM record for {period_data_to_delete_confirm.get('month_name')} {period_data_to_delete_confirm.get('year')} deleted from tracking.");
                            else: st.error("Failed to save changes to Drive after deleting record locally.")
                            st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
                        else: st.error("Incorrect password.")

    # ========================== VIEW UPLOADED REPORTS TAB ==========================
    elif selected_tab == "View Uploaded Reports":
        st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
        all_periods_for_view = mcm_periods.copy() # Use copy of loaded periods
        if not all_periods_for_view:
            st.info("No MCM periods to view reports for.")
        else:
            period_options_list_view = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_periods_for_view.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
            if not period_options_list_view and all_periods_for_view: st.warning("No valid MCM periods with complete month/year info found.")
            elif not period_options_list_view: st.info("No MCM periods available.")
            else:
                selected_period_str_view = st.selectbox("Select MCM Period", options=period_options_list_view, key="pco_view_reports_sel_final_v2")
                if selected_period_str_view:
                    selected_period_k_for_view = next((k for k, p in all_periods_for_view.items() if f"{p.get('month_name')} {p.get('year')}" == selected_period_str_view), None)
                    if selected_period_k_for_view and sheets_service:
                        sheet_id_for_report_view = all_periods_for_view[selected_period_k_for_view]['spreadsheet_id']
                        with st.spinner("Loading data from Google Sheet..."):
                            df_report_data = read_from_spreadsheet(sheets_service, sheet_id_for_report_view)
                        if df_report_data is not None and not df_report_data.empty:
                            st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
                            if 'Audit Group Number' in df_report_data.columns:
                                try:
                                    df_report_data['Audit Group Number Numeric'] = pd.to_numeric(df_report_data['Audit Group Number'], errors='coerce')
                                    df_summary_reports = df_report_data.dropna(subset=['Audit Group Number Numeric'])
                                    dars_per_group_rep = df_summary_reports.groupby('Audit Group Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded'); st.write("**DARs Uploaded per Audit Group:**"); st.dataframe(dars_per_group_rep, use_container_width=True)
                                    paras_per_group_rep = df_summary_reports.groupby('Audit Group Number Numeric').size().reset_index(name='Total Para Entries'); st.write("**Total Para Entries per Audit Group:**"); st.dataframe(paras_per_group_rep, use_container_width=True)
                                    if 'Audit Circle Number' in df_report_data.columns:
                                         df_summary_reports['Audit Circle Number Numeric'] = pd.to_numeric(df_summary_reports['Audit Circle Number'], errors='coerce')
                                         dars_per_circle_rep = df_summary_reports.dropna(subset=['Audit Circle Number Numeric']).groupby('Audit Circle Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded'); st.write("**DARs Uploaded per Audit Circle:**"); st.dataframe(dars_per_circle_rep, use_container_width=True)
                                    if 'Status of para' in df_report_data.columns:
                                        status_summary_rep = df_summary_reports['Status of para'].value_counts().reset_index(name='Count'); status_summary_rep.columns = ['Status of para', 'Count']; st.write("**Para Status Summary:**"); st.dataframe(status_summary_rep, use_container_width=True)
                                    st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True); st.dataframe(df_report_data, use_container_width=True)
                                except Exception as e_rep_sum: st.error(f"Error processing summary: {e_rep_sum}"); st.dataframe(df_report_data, use_container_width=True)
                            else: st.warning("Missing 'Audit Group Number' column for summary."); st.dataframe(df_report_data, use_container_width=True)
                        elif df_report_data is None: st.error("Could not load data from the spreadsheet.")
                        else: st.info(f"No data in spreadsheet for {selected_period_str_view}.")
                    elif not sheets_service and selected_period_k_for_view: st.error("Google Sheets service not available.")

    # ========================== VISUALIZATIONS TAB ==========================
    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        all_mcm_periods_for_viz_tab = mcm_periods # Use directly loaded mcm_periods
        if not all_mcm_periods_for_viz_tab:
            st.info("No MCM periods to visualize data from.")
        else:
            viz_options_list = [f"{p.get('month_name')} {p.get('year')}" for k, p in sorted(all_mcm_periods_for_viz_tab.items(), key=lambda x: x[0], reverse=True) if p.get('month_name') and p.get('year')]
            if not viz_options_list and all_mcm_periods_for_viz_tab: st.warning("No valid MCM periods with complete month/year information for visualization options.")
            elif not viz_options_list: st.info("No MCM periods available to visualize.")
            else:
                selected_viz_period_str_tab = st.selectbox("Select MCM Period for Visualization", options=viz_options_list, key="pco_viz_selectbox_final_v4")
                if selected_viz_period_str_tab and sheets_service:
                    selected_viz_period_k_tab = next((k for k, p in all_mcm_periods_for_viz_tab.items() if f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_str_tab), None)
                    if selected_viz_period_k_tab:
                        sheet_id_for_viz_tab = all_mcm_periods_for_viz_tab[selected_viz_period_k_tab]['spreadsheet_id']
                        with st.spinner("Loading data for visualizations..."):
                            df_viz_data = read_from_spreadsheet(sheets_service, sheet_id_for_viz_tab) # Main DataFrame for this tab

                        if df_viz_data is not None and not df_viz_data.empty:
                            # --- Data Cleaning and Preparation ---
                            viz_amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)', 'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
                            for v_col in viz_amount_cols:
                                if v_col in df_viz_data.columns: df_viz_data[v_col] = pd.to_numeric(df_viz_data[v_col], errors='coerce').fillna(0)
                            
                            # Group Number for Group charts
                            if 'Audit Group Number' in df_viz_data.columns:
                                df_viz_data['Audit Group Number'] = pd.to_numeric(df_viz_data['Audit Group Number'], errors='coerce').fillna(0).astype(int)
                            else: df_viz_data['Audit Group Number'] = 0 
                            df_viz_data['Audit Group Number Str'] = df_viz_data['Audit Group Number'].astype(str)
                            
                            # Circle Number: Prioritize from sheet, then derive
                            if 'Audit Circle Number' in df_viz_data.columns and df_viz_data['Audit Circle Number'].notna().any() and pd.to_numeric(df_viz_data['Audit Circle Number'], errors='coerce').notna().any() :
                                df_viz_data['Circle Number For Plot'] = pd.to_numeric(df_viz_data['Audit Circle Number'], errors='coerce').fillna(0).astype(int)
                                # st.caption("Using 'Audit Circle Number' from sheet for circle-wise charts.")
                            elif 'Audit Group Number' in df_viz_data.columns and df_viz_data['Audit Group Number'].iloc[0] != 0 : # Check if group number is valid before deriving
                                df_viz_data['Circle Number For Plot'] = ((df_viz_data['Audit Group Number'] - 1) // 3 + 1).astype(int)
                                # st.caption("Deriving 'Circle Number' from 'Audit Group Number' for charts as sheet column was missing/invalid.")
                            else:
                                # st.warning("'Audit Circle Number' (from sheet) and 'Audit Group Number' (for derivation) are missing or invalid. Circle charts may be affected.")
                                df_viz_data['Circle Number For Plot'] = 0 # Placeholder
                            df_viz_data['Circle Number Str Plot'] = df_viz_data['Circle Number For Plot'].astype(str)
                            
                            df_viz_data['Category'] = df_viz_data.get('Category', pd.Series(dtype='str')).fillna('Unknown')
                            df_viz_data['Trade Name'] = df_viz_data.get('Trade Name', pd.Series(dtype='str')).fillna('Unknown Trade Name')
                            df_viz_data['Status of para'] = df_viz_data.get('Status of para', pd.Series(dtype='str')).fillna('Unknown')

                            # --- Para Status Distribution ---
                            st.markdown("---"); st.markdown("<h4>Para Status Distribution</h4>", unsafe_allow_html=True)
                            if 'Status of para' in df_viz_data.columns and df_viz_data['Status of para'].nunique() > 0 and not (df_viz_data['Status of para'].nunique() == 1 and df_viz_data['Status of para'].iloc[0] == 'Unknown'):
                                viz_status_counts = df_viz_data['Status of para'].value_counts().reset_index(); viz_status_counts.columns = ['Status of para', 'Count']
                                viz_fig_status_dist = px.bar(viz_status_counts, x='Status of para', y='Count', text_auto=True, title="Distribution of Para Statuses", labels={'Status of para': '<b>Status</b>', 'Count': 'Number of Paras'})
                                viz_fig_status_dist.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); viz_fig_status_dist.update_traces(textposition='outside', marker_color='teal'); st.plotly_chart(viz_fig_status_dist, use_container_width=True)
                            else: st.info("Not enough data for 'Status of para' distribution chart.")

                            # --- Group-wise Performance ---
                            st.markdown("---"); st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
                            if df_viz_data['Audit Group Number'].nunique() > 1 or (df_viz_data['Audit Group Number'].nunique() == 1 and df_viz_data['Audit Group Number'].iloc[0] != 0):
                                if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns:
                                    viz_detection_data = df_viz_data.groupby('Audit Group Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
                                    if not viz_detection_data.empty: st.write("**Top 5 Groups by Total Detection Amount (Rs):**"); fig_det_grp = px.bar(viz_detection_data, x='Audit Group Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'}); fig_det_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); fig_det_grp.update_traces(textposition='outside', marker_color='indianred'); st.plotly_chart(fig_det_grp, use_container_width=True)
                                if 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns:
                                    viz_recovery_data = df_viz_data.groupby('Audit Group Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
                                    if not viz_recovery_data.empty: st.write("**Top 5 Groups by Total Realisation Amount (Rs):**"); fig_rec_grp = px.bar(viz_recovery_data, x='Audit Group Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'}); fig_rec_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); fig_rec_grp.update_traces(textposition='outside', marker_color='lightseagreen'); st.plotly_chart(fig_rec_grp, use_container_width=True)
                                if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns and 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns:
                                    viz_grp_summary = df_viz_data.groupby('Audit Group Number Str').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index(); viz_grp_summary['Recovery_Ratio'] = viz_grp_summary.apply(lambda r: (r['Total_Recovered'] / r['Total_Detected']) * 100 if pd.notna(r['Total_Detected']) and r['Total_Detected'] > 0 and pd.notna(r['Total_Recovered']) else 0, axis=1); viz_ratio_data = viz_grp_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
                                    if not viz_ratio_data.empty: st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**"); fig_ratio_grp = px.bar(viz_ratio_data, x='Audit Group Number Str', y='Recovery_Ratio', text_auto=True, labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number Str': '<b>Audit Group</b>'}); fig_ratio_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); fig_ratio_grp.update_traces(textposition='outside', marker_color='mediumpurple'); st.plotly_chart(fig_ratio_grp, use_container_width=True)
                            else: st.info("Group-wise charts require valid 'Audit Group Number' data with more than one group or a non-zero group.")

                            # --- Circle-wise Performance ---
                            st.markdown("---"); st.markdown("<h4>Circle-wise Performance Metrics</h4>", unsafe_allow_html=True)
                            if 'Circle Number Str Plot' in df_viz_data and (df_viz_data['Circle Number For Plot'].nunique() > 1 or (df_viz_data['Circle Number For Plot'].nunique() == 1 and df_viz_data['Circle Number For Plot'].iloc[0] != 0)):
                                if 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns:
                                    recovery_per_circle_plot = df_viz_data.groupby('Circle Number Str Plot')['Total Amount Recovered (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False)
                                    if not recovery_per_circle_plot.empty: st.write("**Total Recovery Amount (Rs) per Circle (Descending):**"); fig_rec_circle_plot = px.bar(recovery_per_circle_plot, x='Circle Number Str Plot', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Recovery (Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Recovery"); fig_rec_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); fig_rec_circle_plot.update_traces(textposition='outside', marker_color='goldenrod'); st.plotly_chart(fig_rec_circle_plot, use_container_width=True)
                                if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns:
                                    detection_per_circle_plot = df_viz_data.groupby('Circle Number Str Plot')['Total Amount Detected (Overall Rs)'].sum().reset_index().sort_values(by='Total Amount Detected (Overall Rs)', ascending=False)
                                    if not detection_per_circle_plot.empty: st.write("**Total Detection Amount (Rs) per Circle (Descending):**"); fig_det_circle_plot = px.bar(detection_per_circle_plot, x='Circle Number Str Plot', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise Total Detection"); fig_det_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); fig_det_circle_plot.update_traces(textposition='outside', marker_color='mediumseagreen'); st.plotly_chart(fig_det_circle_plot, use_container_width=True)
                                if 'DAR PDF URL' in df_viz_data.columns:
                                    dars_per_circle_plot = df_viz_data.groupby('Circle Number Str Plot')['DAR PDF URL'].nunique().reset_index(name='DARs Sponsored').sort_values(by='DARs Sponsored', ascending=False)
                                    if not dars_per_circle_plot.empty: st.write("**DARs Sponsored per Circle (Descending):**"); fig_dars_circle_plot = px.bar(dars_per_circle_plot, x='Circle Number Str Plot', y='DARs Sponsored', text_auto=True, labels={'DARs Sponsored': 'Number of DARs Sponsored', 'Circle Number Str Plot': '<b>Circle Number</b>'}, title="Circle-wise DARs Sponsored"); fig_dars_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category'); fig_dars_circle_plot.update_traces(textposition='outside', marker_color='skyblue'); st.plotly_chart(fig_dars_circle_plot, use_container_width=True)
                            else: st.info("Not enough distinct and valid circle data to plot circle-wise charts.")
                            
                            # --- Treemap Visualizations ---
                            st.markdown("---"); st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
                            if 'Total Amount Detected (Overall Rs)' in df_viz_data.columns and 'Trade Name' in df_viz_data.columns and 'Category' in df_viz_data.columns :
                                viz_df_detection_treemap_source = df_viz_data[df_viz_data['Total Amount Detected (Overall Rs)'] > 0].copy(); viz_df_detection_treemap_unique_dars = viz_df_detection_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in viz_df_detection_treemap_source.columns and viz_df_detection_treemap_source['DAR PDF URL'].notna().any() else viz_df_detection_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Detected (Overall Rs)'])
                                if not viz_df_detection_treemap_unique_dars.empty:
                                    st.write("**Detection Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
                                    try: viz_fig_treemap_detection = px.treemap(viz_df_detection_treemap_unique_dars, path=[px.Constant("All Detections"), 'Category', 'Trade Name'], values='Total Amount Detected (Overall Rs)', color='Category', hover_name='Trade Name', custom_data=['Audit Group Number Str', 'Trade Name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'}); viz_fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10)); viz_fig_treemap_detection.data[0].textinfo = 'label+value'; viz_fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Rs<extra></extra>"); st.plotly_chart(viz_fig_treemap_detection, use_container_width=True)
                                    except Exception as e_viz_treemap_det: st.error(f"Could not generate detection treemap: {e_viz_treemap_det}")
                                else: st.info("No positive detection data (Overall Rs) for treemap.")
                            else: st.info("Required columns for Detection Treemap missing.")
                            if 'Total Amount Recovered (Overall Rs)' in df_viz_data.columns and 'Trade Name' in df_viz_data.columns and 'Category' in df_viz_data.columns:
                                viz_df_recovery_treemap_source = df_viz_data[df_viz_data['Total Amount Recovered (Overall Rs)'] > 0].copy(); viz_df_recovery_treemap_unique_dars = viz_df_recovery_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in viz_df_recovery_treemap_source.columns and viz_df_recovery_treemap_source['DAR PDF URL'].notna().any() else viz_df_recovery_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Recovered (Overall Rs)'])
                                if not viz_df_recovery_treemap_unique_dars.empty:
                                    st.write("**Recovery Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
                                    try: viz_fig_treemap_recovery = px.treemap(viz_df_recovery_treemap_unique_dars,path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'],values='Total Amount Recovered (Overall Rs)',color='Category',hover_name='Trade Name',custom_data=['Audit Group Number Str', 'Trade Name'],color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'}); viz_fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10)); viz_fig_treemap_recovery.data[0].textinfo = 'label+value'; viz_fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Rs<extra></extra>"); st.plotly_chart(viz_fig_treemap_recovery, use_container_width=True)
                                    except Exception as e_viz_treemap_rec: st.error(f"Could not generate recovery treemap: {e_viz_treemap_rec}")
                                else: st.info("No positive recovery data (Overall Rs) for treemap.")
                            else: st.info("Required columns for Recovery Treemap missing.")

                            # --- Para-wise Performance ---
                            st.markdown("---"); st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
                            if 'num_paras_to_show_pco' not in st.session_state: st.session_state.num_paras_to_show_pco = 5
                            viz_n_paras_input = st.text_input("Enter N for Top N Paras (e.g., 5):", value=str(st.session_state.num_paras_to_show_pco), key="pco_n_paras_input_final_v2")
                            viz_num_paras_show = st.session_state.num_paras_to_show_pco
                            try:
                                viz_parsed_n = int(viz_n_paras_input);
                                if viz_parsed_n < 1: viz_num_paras_show = 5; st.warning("N must be positive. Showing Top 5.", icon="⚠️")
                                elif viz_parsed_n > 50: viz_num_paras_show = 50; st.warning("N capped at 50. Showing Top 50.", icon="⚠️")
                                else: viz_num_paras_show = viz_parsed_n
                                st.session_state.num_paras_to_show_pco = viz_num_paras_show
                            except ValueError:
                                if viz_n_paras_input != str(st.session_state.num_paras_to_show_pco): st.warning(f"Invalid N ('{viz_n_paras_input}'). Using: {viz_num_paras_show}", icon="⚠️")
                            
                            viz_df_paras_only = df_viz_data[df_viz_data['Audit Para Number'].notna() & (~df_viz_data['Audit Para Heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
                            if 'Revenue Involved (Lakhs Rs)' in viz_df_paras_only.columns:
                                viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Involved (Lakhs Rs)')
                                if not viz_top_det_paras.empty: st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**"); viz_disp_cols_det = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)', 'Status of para']; viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]; st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
                                else: st.info("No data for 'Top Detection Paras' list.")
                            if 'Revenue Recovered (Lakhs Rs)' in viz_df_paras_only.columns:
                                viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'Revenue Recovered (Lakhs Rs)')
                                if not viz_top_rec_paras.empty: st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**"); viz_disp_cols_rec = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)', 'Status of para']; viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]; st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
                                else: st.info("No data for 'Top Realisation Paras' list.")
                        elif df_viz_data is None: st.error("Error reading data from spreadsheet for visualization.")
                        else: st.info(f"No data in spreadsheet for {selected_viz_period_display_str} to visualize.")
                    elif not sheets_service and selected_viz_period_key_str: st.error("Google Sheets service unavailable when trying to load visualization data.")
                elif not sheets_service and selected_viz_period_display_str: st.error("Google Sheets service is not available.")
            elif not viz_options_list and all_mcm_periods_for_viz_tab: st.warning("No MCM periods with complete month/year found for viz options.")

    st.markdown("</div>", unsafe_allow_html=True)# # ui_pco.py
# import streamlit as st
# import datetime
# import time
# import pandas as pd
# import plotly.express as px
# from streamlit_option_menu import option_menu
# import math # For math.ceil if needed, though derivation is usually integer division

# # Assuming google_utils.py and config.py are in the same directory and correctly set up
# from google_utils import (
#     load_mcm_periods, save_mcm_periods, create_drive_folder,
#     create_spreadsheet, read_from_spreadsheet
# )
# from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE

# def pco_dashboard(drive_service, sheets_service):
#     st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
#     mcm_periods = load_mcm_periods(drive_service)

#     with st.sidebar:
#         try:
#             st.image("logo.png", width=80) # Use local logo
#         except Exception as e:
#             st.sidebar.warning(f"Could not load logo.png: {e}")
#             st.sidebar.markdown("*(Logo)*")

#         st.markdown(f"**User:** {st.session_state.username}")
#         st.markdown(f"**Role:** {st.session_state.role}")
#         if st.button("Logout", key="pco_logout_styled", use_container_width=True):
#             st.session_state.logged_in = False
#             st.session_state.username = ""
#             st.session_state.role = ""
#             st.session_state.drive_structure_initialized = False
#             keys_to_clear = ['period_to_delete', 'show_delete_confirm', 'num_paras_to_show_pco']
#             for key in keys_to_clear:
#                 if key in st.session_state:
#                     del st.session_state[key]
#             st.rerun()
#         st.markdown("---")

#     selected_tab = option_menu(
#         menu_title=None,
#         options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "Visualizations"],
#         icons=["calendar-plus-fill", "sliders", "eye-fill", "bar-chart-fill"],
#         menu_icon="gear-wide-connected", default_index=0, orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
#             "icon": {"color": "#007bff", "font-size": "20px"},
#             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
#             "nav-link-selected": {"background-color": "#007bff", "color": "white"},
#         })

#     st.markdown("<div class='card'>", unsafe_allow_html=True)
#     if selected_tab == "Create MCM Period":
#         st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
#         current_year = datetime.datetime.now().year
#         years = list(range(current_year - 1, current_year + 3))
#         months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
#                   "November", "December"]
#         col1, col2 = st.columns(2)
#         with col1:
#             selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year), key="pco_year")
#         with col2:
#             selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1,
#                                                key="pco_month")
#         selected_month_num = months.index(selected_month_name) + 1
#         period_key = f"{selected_year}-{selected_month_num:02d}"

#         if period_key in mcm_periods:
#             st.warning(f"MCM Period for {selected_month_name} {selected_year} already exists.")
#         else:
#             if st.button(f"Create MCM for {selected_month_name} {selected_year}", key="pco_create_mcm",
#                          use_container_width=True):
#                 if not drive_service or not sheets_service or not st.session_state.get('master_drive_folder_id'):
#                     st.error("Google Services or Master Drive Folder not available. Cannot create MCM period.")
#                 else:
#                     with st.spinner("Creating Google Drive folder and Spreadsheet..."):
#                         master_folder_id = st.session_state.master_drive_folder_id
#                         folder_name = f"MCM_DARs_{selected_month_name}_{selected_year}"
#                         spreadsheet_title = f"MCM_Audit_Paras_{selected_month_name}_{selected_year}"

#                         folder_id, folder_url = create_drive_folder(drive_service, folder_name,
#                                                                     parent_id=master_folder_id)
#                         sheet_id, sheet_url = create_spreadsheet(sheets_service, drive_service, spreadsheet_title,
#                                                                  parent_folder_id=master_folder_id)

#                         if folder_id and sheet_id:
#                             mcm_periods[period_key] = {
#                                 "year": selected_year, "month_num": selected_month_num,
#                                 "month_name": selected_month_name,
#                                 "drive_folder_id": folder_id, "drive_folder_url": folder_url,
#                                 "spreadsheet_id": sheet_id, "spreadsheet_url": sheet_url, "active": True
#                             }
#                             if save_mcm_periods(drive_service, mcm_periods):
#                                 st.success(
#                                     f"Successfully created MCM period for {selected_month_name} {selected_year}!")
#                                 st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>",
#                                             unsafe_allow_html=True)
#                                 st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>",
#                                             unsafe_allow_html=True)
#                                 st.balloons(); time.sleep(0.5); st.rerun()
#                             else:
#                                 st.error("Failed to save MCM period configuration to Drive.")
#                         else:
#                             st.error("Failed to create Drive folder or Spreadsheet.")

#     elif selected_tab == "Manage MCM Periods":
#         st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
#         st.markdown("<h4 style='color: red;'>Pls Note ,Deleting the records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
#         st.markdown("<h5 style='color: green;'>Only the Months which are marked as 'Active' by Planning officer, will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
#         if not mcm_periods:
#             st.info("No MCM periods created yet.")
#         else:
#             sorted_periods_keys = sorted(mcm_periods.keys(), reverse=True)
#             for period_key in sorted_periods_keys:
#                 data = mcm_periods[period_key]
#                 month_name_display = data.get('month_name', 'Unknown Month')
#                 year_display = data.get('year', 'Unknown Year')
#                 st.markdown(f"<h4>{month_name_display} {year_display}</h4>", unsafe_allow_html=True)
#                 col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
#                 with col1:
#                     st.markdown(f"<a href='{data.get('drive_folder_url', '#')}' target='_blank'>Open Drive Folder</a>",
#                                 unsafe_allow_html=True)
#                 with col2:
#                     st.markdown(f"<a href='{data.get('spreadsheet_url', '#')}' target='_blank'>Open Spreadsheet</a>",
#                                 unsafe_allow_html=True)
#                 with col3:
#                     is_active = data.get("active", False)
#                     new_status = st.checkbox("Active", value=is_active, key=f"active_{period_key}_styled_manage") # ensure key is unique
#                     if new_status != is_active:
#                         mcm_periods[period_key]["active"] = new_status
#                         if save_mcm_periods(drive_service, mcm_periods):
#                             month_name_succ = data.get('month_name', 'Unknown Period')
#                             year_succ = data.get('year', '')
#                             st.success(f"Status for {month_name_succ} {year_succ} updated."); st.rerun()
#                         else:
#                             st.error("Failed to save updated MCM period status to Drive.")
#                 with col4:
#                     if st.button("Delete Period Record", key=f"delete_mcm_{period_key}", type="secondary"):
#                         st.session_state.period_to_delete = period_key
#                         st.session_state.show_delete_confirm = True; st.rerun()
#                 st.markdown("---")

#             if st.session_state.get('show_delete_confirm', False) and st.session_state.get('period_to_delete'):
#                 period_key_to_delete = st.session_state.period_to_delete
#                 period_data_to_delete = mcm_periods.get(period_key_to_delete, {})
#                 with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
#                     st.warning(
#                         f"Are you sure you want to delete the MCM period record for **{period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')}**?")

#                     st.error( # User requested warning message
#                         "**Warning:** Delete period will delete the backend historic DAR data in the spreadsheet and drive. So use cautiously."
#                     )
#                     st.caption( # Clarification of current functionality
#                         f"Currently, this action only removes the period's entry from the app's configuration file (`{MCM_PERIODS_FILENAME_ON_DRIVE}`). "
#                         "To make the above warning accurate, backend logic for deleting Google Drive/Sheets resources needs to be implemented."
#                     )

#                     pco_password_confirm = st.text_input("Enter your PCO password:", type="password",
#                                                          key=f"pco_pass_conf_{period_key_to_delete}")
#                     c1, c2 = st.columns(2)
#                     with c1:
#                         submitted_delete = st.form_submit_button("Yes, Delete Record from Tracking", use_container_width=True)
#                     with c2:
#                         if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
#                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
#                     if submitted_delete:
#                         if pco_password_confirm == USER_CREDENTIALS.get("planning_officer"):
#                             del mcm_periods[period_key_to_delete]
#                             if save_mcm_periods(drive_service, mcm_periods):
#                                 st.success(
#                                     f"MCM record for {period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')} deleted from tracking.");
#                             else:
#                                 st.error("Failed to save changes to Drive after deleting record locally.")
#                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
#                         else:
#                             st.error("Incorrect password.")

#     elif selected_tab == "View Uploaded Reports":
#         st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
#         active_periods = {k: v for k, v in mcm_periods.items()} # Show all periods for viewing reports
#         if not active_periods:
#             st.info("No MCM periods to view reports for.")
#         else:
#             period_options = [
#                  f"{p.get('month_name')} {p.get('year')}"
#                  for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
#                  if p.get('month_name') and p.get('year')
#              ]
#             if not period_options and active_periods:
#                  st.warning("No valid MCM periods with complete month and year information found to display options.")
#             elif not period_options:
#                  st.info("No MCM periods available.")

#             selected_period_display = st.selectbox("Select MCM Period", options=period_options,
#                                                    key="pco_view_reports_period_select")
#             if selected_period_display:
#                 selected_period_key = next((k for k, p in active_periods.items() if
#                             p.get('month_name') and p.get('year') and
#                             f"{p.get('month_name')} {p.get('year')}" == selected_period_display), None)
#                 if selected_period_key and sheets_service:
#                     sheet_id = mcm_periods[selected_period_key]['spreadsheet_id']
#                     with st.spinner("Loading data from Google Sheet..."):
#                         df = read_from_spreadsheet(sheets_service, sheet_id) #
#                     if not df.empty:
#                         st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
#                         # Ensure "Audit Circle Number" and "Status of para" are available for display if needed
#                         # The df returned by read_from_spreadsheet should now contain these columns
#                         if 'Audit Group Number' in df.columns:
#                             try:
#                                 df['Audit Group Number Numeric'] = pd.to_numeric(df['Audit Group Number'], errors='coerce')
#                                 df_summary = df.dropna(subset=['Audit Group Number Numeric'])
#                                 dars_per_group = df_summary.groupby('Audit Group Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
#                                 st.write("**DARs Uploaded per Audit Group:**"); st.dataframe(dars_per_group, use_container_width=True)

#                                 paras_per_group = df_summary.groupby('Audit Group Number Numeric').size().reset_index(name='Total Para Entries')
#                                 st.write("**Total Para Entries per Audit Group:**"); st.dataframe(paras_per_group, use_container_width=True)

#                                 if 'Audit Circle Number' in df.columns:
#                                      df_summary['Audit Circle Number Numeric'] = pd.to_numeric(df_summary['Audit Circle Number'], errors='coerce')
#                                      dars_per_circle = df_summary.dropna(subset=['Audit Circle Number Numeric']).groupby('Audit Circle Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
#                                      st.write("**DARs Uploaded per Audit Circle:**"); st.dataframe(dars_per_circle, use_container_width=True)

#                                 if 'Status of para' in df.columns:
#                                     status_summary = df_summary['Status of para'].value_counts().reset_index(name='Count')
#                                     status_summary.columns = ['Status of para', 'Count']
#                                     st.write("**Para Status Summary:**"); st.dataframe(status_summary, use_container_width=True)


#                                 st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True); st.dataframe(df, use_container_width=True)
#                             except Exception as e:
#                                 st.error(f"Error processing summary: {e}"); st.dataframe(df, use_container_width=True)
#                         else:
#                             st.warning("Missing 'Audit Group Number' column for summary."); st.dataframe(df, use_container_width=True)
#                     else:
#                         st.info(f"No data in spreadsheet for {selected_period_display}.")
#                 elif not sheets_service and selected_period_key:
#                     st.error("Google Sheets service not available.")

#     elif selected_tab == "Visualizations":
#         st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
#         all_mcm_periods = mcm_periods
#         if not all_mcm_periods:
#             st.info("No MCM periods to visualize data from.")
#         else:
#             viz_period_options = [
#                 f"{p.get('month_name')} {p.get('year')}"
#                 for k, p in sorted(all_mcm_periods.items(), key=lambda item: item[0], reverse=True)
#                 if p.get('month_name') and p.get('year')
#             ]
#             if not viz_period_options and all_mcm_periods:
#                 st.warning("No valid MCM periods with complete month/year information for visualization options.")
#             elif not viz_period_options:
#                  st.info("No MCM periods available to visualize.")

#             selected_viz_period_display = st.selectbox("Select MCM Period for Visualization",
#                                                        options=viz_period_options, key="pco_viz_selectbox")

#             if selected_viz_period_display and sheets_service:
#                 selected_viz_period_key = next((k for k, p in all_mcm_periods.items() if
#                                 p.get('month_name') and p.get('year') and
#                                 f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_display), None)

#                 if selected_viz_period_key:
#                     sheet_id_viz = all_mcm_periods[selected_viz_period_key]['spreadsheet_id']
#                     with st.spinner("Loading data for visualizations..."):
#                         df_viz = read_from_spreadsheet(sheets_service, sheet_id_viz) #

#                     if not df_viz.empty:
#                         # --- Data Cleaning and Preparation ---
#                         amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)',
#                                        'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
#                         for col in amount_cols:
#                             if col in df_viz.columns:
#                                 df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)

#                         if 'Audit Group Number' in df_viz.columns and pd.api.types.is_numeric_dtype(df_viz['Audit Group Number'].dropna()):
#                             df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)
#                             # Derive Circle Number for internal consistency in this PCO view,
#                             # even if "Audit Circle Number" is in the sheet.
#                             df_viz['Circle Number Derived'] = ((df_viz['Audit Group Number'] - 1) // 3 + 1).astype(int)
#                         else:
#                             if 'Audit Group Number' in df_viz.columns:
#                                 st.warning("Audit Group Number column contains non-numeric data or many NaNs. Group and Circle charts might be inaccurate.")
#                                 df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)
#                             else:
#                                 st.warning("Audit Group Number column is missing. Group and Circle charts cannot be generated accurately.")
#                                 df_viz['Audit Group Number'] = 0
#                             df_viz['Circle Number Derived'] = 0

#                         df_viz['Audit Group Number Str'] = df_viz['Audit Group Number'].astype(str)
#                         df_viz['Category'] = df_viz['Category'].fillna('Unknown') if 'Category' in df_viz.columns else 'Unknown'
#                         df_viz['Trade Name'] = df_viz['Trade Name'].fillna('Unknown Trade Name') if 'Trade Name' in df_viz.columns else 'Unknown Trade Name'
#                         df_viz['Status of para'] = df_viz['Status of para'].fillna('Unknown') if 'Status of para' in df_viz.columns else 'Unknown' #

#                         # --- Para Status Visualization ---
#                         st.markdown("---")
#                         st.markdown("<h4>Para Status Distribution</h4>", unsafe_allow_html=True)
#                         if 'Status of para' in df_viz.columns and df_viz['Status of para'].nunique() > 0 and not (df_viz['Status of para'].nunique() == 1 and df_viz['Status of para'].iloc[0] == 'Unknown'):
#                             status_counts = df_viz['Status of para'].value_counts().reset_index()
#                             status_counts.columns = ['Status of para', 'Count']
#                             fig_status_dist = px.bar(status_counts, x='Status of para', y='Count',
#                                                      text_auto=True, title="Distribution of Para Statuses",
#                                                      labels={'Status of para': '<b>Status</b>', 'Count': 'Number of Paras'})
#                             fig_status_dist.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                             fig_status_dist.update_traces(textposition='outside', marker_color='teal')
#                             st.plotly_chart(fig_status_dist, use_container_width=True)
#                         else:
#                             st.info("Not enough data or no 'Status of para' column available for status distribution chart.")


#                         # --- Group-wise Performance ---
#                         st.markdown("---")
#                         st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
#                         if df_viz['Audit Group Number'].nunique() > 1 or (df_viz['Audit Group Number'].nunique() == 1 and df_viz['Audit Group Number'].iloc[0] != 0):
#                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns:
#                                 detection_data = df_viz.groupby('Audit Group Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index()
#                                 detection_data = detection_data.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
#                                 if not detection_data.empty:
#                                     st.write("**Top 5 Groups by Total Detection Amount (Rs):**")
#                                     fig_det_group = px.bar(detection_data, x='Audit Group Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
#                                     fig_det_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                     fig_det_group.update_traces(textposition='outside', marker_color='indianred')
#                                     st.plotly_chart(fig_det_group, use_container_width=True)
#                                 else: st.info("Not enough data for 'Top Detection Groups' chart.")

#                             if 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
#                                 recovery_data = df_viz.groupby('Audit Group Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
#                                 recovery_data = recovery_data.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
#                                 if not recovery_data.empty:
#                                     st.write("**Top 5 Groups by Total Realisation Amount (Rs):**")
#                                     fig_rec_group = px.bar(recovery_data, x='Audit Group Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
#                                     fig_rec_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                     fig_rec_group.update_traces(textposition='outside', marker_color='lightseagreen')
#                                     st.plotly_chart(fig_rec_group, use_container_width=True)
#                                 else: st.info("Not enough data for 'Top Realisation Groups' chart.")

#                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
#                                 group_summary = df_viz.groupby('Audit Group Number Str').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index()
#                                 group_summary['Recovery_Ratio'] = group_summary.apply(lambda row: (row['Total_Recovered'] / row['Total_Detected']) * 100 if pd.notna(row['Total_Detected']) and row['Total_Detected'] > 0 and pd.notna(row['Total_Recovered']) else 0, axis=1)
#                                 ratio_data = group_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
#                                 if not ratio_data.empty:
#                                     st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**")
#                                     fig_ratio_group = px.bar(ratio_data, x='Audit Group Number Str', y='Recovery_Ratio', text_auto=True, labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number Str': '<b>Audit Group</b>'})
#                                     fig_ratio_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                     fig_ratio_group.update_traces(textposition='outside', marker_color='mediumpurple')
#                                     st.plotly_chart(fig_ratio_group, use_container_width=True)
#                                 else: st.info("Not enough data for 'Top Recovery Ratio Groups' chart.")
#                         else:
#                              st.info("Group-wise charts require valid 'Audit Group Number' data.")


#                         # --- Circle-wise Performance (using Circle Number Derived) ---
#                         st.markdown("---")
#                         st.markdown("<h4>Circle-wise Performance</h4>", unsafe_allow_html=True)
#                         if df_viz['Circle Number Derived'].nunique() > 1 or (df_viz['Circle Number Derived'].nunique() == 1 and df_viz['Circle Number Derived'].iloc[0] != 0):
#                             df_viz['Circle Number Str'] = df_viz['Circle Number Derived'].astype(str) # Use the derived one
#                             if 'DAR PDF URL' in df_viz.columns:
#                                 dars_per_circle = df_viz.groupby('Circle Number Str')['DAR PDF URL'].nunique().reset_index(name='DARs Sponsored')
#                                 dars_per_circle = dars_per_circle.sort_values(by='DARs Sponsored', ascending=False)
#                                 if not dars_per_circle.empty:
#                                     st.write("**DARs Sponsored per Circle:**")
#                                     fig_dars_circle = px.bar(dars_per_circle, x='Circle Number Str', y='DARs Sponsored', text_auto=True, labels={'DARs Sponsored': 'Number of DARs Sponsored', 'Circle Number Str': '<b>Circle Number</b>'})
#                                     fig_dars_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                     fig_dars_circle.update_traces(textposition='outside', marker_color='skyblue')
#                                     st.plotly_chart(fig_dars_circle, use_container_width=True)
#                                 else: st.info("Not enough data for 'DARs Sponsored per Circle' chart.")

#                             paras_per_circle = df_viz.groupby('Circle Number Str').size().reset_index(name='Total Para Entries')
#                             paras_per_circle = paras_per_circle.sort_values(by='Total Para Entries', ascending=False)
#                             if not paras_per_circle.empty:
#                                 st.write("**Total Para Entries per Circle:**")
#                                 fig_paras_circle = px.bar(paras_per_circle, x='Circle Number Str', y='Total Para Entries', text_auto=True, labels={'Total Para Entries': 'Total Para Entries', 'Circle Number Str': '<b>Circle Number</b>'})
#                                 fig_paras_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                 fig_paras_circle.update_traces(textposition='outside', marker_color='lightcoral')
#                                 st.plotly_chart(fig_paras_circle, use_container_width=True)
#                             else: st.info("Not enough data for 'Total Para Entries per Circle' chart.")

#                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns:
#                                 detection_per_circle = df_viz.groupby('Circle Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index()
#                                 detection_per_circle = detection_per_circle.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False)
#                                 if not detection_per_circle.empty:
#                                     st.write("**Total Detection Amount (Rs) per Circle:**")
#                                     fig_det_circle = px.bar(detection_per_circle, x='Circle Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Circle Number Str': '<b>Circle Number</b>'})
#                                     fig_det_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                     fig_det_circle.update_traces(textposition='outside', marker_color='mediumseagreen')
#                                     st.plotly_chart(fig_det_circle, use_container_width=True)
#                                 else: st.info("Not enough data for 'Total Detection per Circle' chart.")

#                             if 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
#                                 recovery_per_circle = df_viz.groupby('Circle Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
#                                 recovery_per_circle = recovery_per_circle.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False)
#                                 if not recovery_per_circle.empty:
#                                     st.write("**Total Recovery Amount (Rs) per Circle:**")
#                                     fig_rec_circle = px.bar(recovery_per_circle, x='Circle Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Recovery (Rs)', 'Circle Number Str': '<b>Circle Number</b>'})
#                                     fig_rec_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
#                                     fig_rec_circle.update_traces(textposition='outside', marker_color='goldenrod')
#                                     st.plotly_chart(fig_rec_circle, use_container_width=True)
#                                 else: st.info("Not enough data for 'Total Recovery per Circle' chart.")
#                         else:
#                              st.info("Circle-wise charts require valid 'Circle Number Derived' data, from 'Audit Group Number'.")


#                         # --- Treemap Visualizations ---
#                         st.markdown("---")
#                         st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)

#                         if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Trade Name' in df_viz.columns and 'Category' in df_viz.columns :
#                             df_detection_treemap_source = df_viz[df_viz['Total Amount Detected (Overall Rs)'] > 0].copy()
#                             df_detection_treemap_unique_dars = df_detection_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in df_detection_treemap_source.columns and df_detection_treemap_source['DAR PDF URL'].notna().any() else df_detection_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Detected (Overall Rs)'])

#                             if not df_detection_treemap_unique_dars.empty:
#                                 st.write("**Detection Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
#                                 try:
#                                     fig_treemap_detection = px.treemap(
#                                         df_detection_treemap_unique_dars,
#                                         path=[px.Constant("All Detections"), 'Category', 'Trade Name'],
#                                         values='Total Amount Detected (Overall Rs)',
#                                         color='Category',
#                                         hover_name='Trade Name',
#                                         custom_data=['Audit Group Number Str', 'Trade Name'],
#                                         color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'}
#                                     )
#                                     fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
#                                     fig_treemap_detection.data[0].textinfo = 'label+value'
#                                     fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Rs<extra></extra>")
#                                     st.plotly_chart(fig_treemap_detection, use_container_width=True)
#                                 except Exception as e_treemap_det: st.error(f"Could not generate detection treemap: {e_treemap_det}")
#                             else: st.info("No positive detection data (Overall Rs) available for the treemap.")
#                         else: st.info("Required columns for Detection Treemap (Total Amount Detected, Category, Trade Name) are missing.")

#                         if 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Trade Name' in df_viz.columns and 'Category' in df_viz.columns:
#                             df_recovery_treemap_source = df_viz[df_viz['Total Amount Recovered (Overall Rs)'] > 0].copy()
#                             df_recovery_treemap_unique_dars = df_recovery_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in df_recovery_treemap_source.columns and df_recovery_treemap_source['DAR PDF URL'].notna().any() else df_recovery_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Recovered (Overall Rs)'])

#                             if not df_recovery_treemap_unique_dars.empty:
#                                 st.write("**Recovery Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
#                                 try:
#                                     fig_treemap_recovery = px.treemap(
#                                         df_recovery_treemap_unique_dars,
#                                         path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'],
#                                         values='Total Amount Recovered (Overall Rs)',
#                                         color='Category',
#                                         hover_name='Trade Name',
#                                         custom_data=['Audit Group Number Str', 'Trade Name'],
#                                         color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'}
#                                     )
#                                     fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
#                                     fig_treemap_recovery.data[0].textinfo = 'label+value'
#                                     fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Rs<extra></extra>")
#                                     st.plotly_chart(fig_treemap_recovery, use_container_width=True)
#                                 except Exception as e_treemap_rec: st.error(f"Could not generate recovery treemap: {e_treemap_rec}")
#                             else: st.info("No positive recovery data (Overall Rs) available for the treemap.")
#                         else: st.info("Required columns for Recovery Treemap (Total Amount Recovered, Category, Trade Name) are missing.")


#                         # --- Para-wise Performance (Input type changed) ---
#                         st.markdown("---")
#                         st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)

#                         if 'num_paras_to_show_pco' not in st.session_state:
#                             st.session_state.num_paras_to_show_pco = 5

#                         n_paras_input_val = st.text_input(
#                             "Enter N for Top N Paras (e.g., 5) and press Enter:",
#                             value=str(st.session_state.num_paras_to_show_pco),
#                             key="pco_n_paras_text_input_final"
#                         )

#                         num_paras_to_show_val = st.session_state.num_paras_to_show_pco
#                         try:
#                             parsed_n = int(n_paras_input_val)
#                             if parsed_n < 1:
#                                 num_paras_to_show_val = 5
#                                 if str(parsed_n) != n_paras_input_val or parsed_n != 5 :
#                                      st.warning("N must be a positive integer. Displaying Top 5.", icon="⚠️")
#                             elif parsed_n > 50:
#                                 num_paras_to_show_val = 50
#                                 st.warning("N capped at 50. Displaying Top 50.", icon="⚠️")
#                             else:
#                                 num_paras_to_show_val = parsed_n
#                             st.session_state.num_paras_to_show_pco = num_paras_to_show_val
#                         except ValueError:
#                             if n_paras_input_val != str(st.session_state.num_paras_to_show_pco):
#                                 st.warning(f"Invalid input for N ('{n_paras_input_val}'). Please enter a number. Using: {num_paras_to_show_val}", icon="⚠️")

#                         df_paras_only = df_viz[df_viz['Audit Para Number'].notna() &
#                                                (~df_viz['Audit Para Heading'].astype(str).isin([
#                                                    "N/A - Header Info Only (Add Paras Manually)",
#                                                    "Manual Entry Required",
#                                                    "Manual Entry - PDF Error",
#                                                    "Manual Entry - PDF Upload Failed"
#                                                    ]))]

#                         if 'Revenue Involved (Lakhs Rs)' in df_paras_only.columns:
#                             top_detection_paras = df_paras_only.nlargest(num_paras_to_show_val, 'Revenue Involved (Lakhs Rs)')
#                             if not top_detection_paras.empty:
#                                 st.write(f"**Top {num_paras_to_show_val} Detection Paras (by Revenue Involved):**")
#                                 display_cols_det_para = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)', 'Status of para'] # Added Status
#                                 existing_cols_det = [col for col in display_cols_det_para if col in top_detection_paras.columns]
#                                 st.dataframe(top_detection_paras[existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
#                             else: st.info("Not enough data for 'Top Detection Paras' list.")

#                         if 'Revenue Recovered (Lakhs Rs)' in df_paras_only.columns:
#                             top_recovery_paras = df_paras_only.nlargest(num_paras_to_show_val, 'Revenue Recovered (Lakhs Rs)')
#                             if not top_recovery_paras.empty:
#                                 st.write(f"**Top {num_paras_to_show_val} Realisation Paras (by Revenue Recovered):**")
#                                 display_cols_rec_para = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)', 'Status of para'] # Added Status
#                                 existing_cols_rec = [col for col in display_cols_rec_para if col in top_recovery_paras.columns]
#                                 st.dataframe(top_recovery_paras[existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
#                             else: st.info("Not enough data for 'Top Realisation Paras' list.")
#                     else:
#                         st.info(f"No data in spreadsheet for {selected_viz_period_display} to visualize.")
#                 elif not sheets_service and selected_viz_period_key:
#                     st.error("Google Sheets service not available.")
#             elif not sheets_service and selected_viz_period_display :
#                 st.error("Google Sheets service not available.")

#     st.markdown("</div>", unsafe_allow_html=True)# # ui_pco.py
# # import streamlit as st
# # import datetime
# # import time
# # import pandas as pd
# # import plotly.express as px
# # from streamlit_option_menu import option_menu

# # # Assuming google_utils.py and config.py are in the same directory and correctly set up
# # from google_utils import (
# #     load_mcm_periods, save_mcm_periods, create_drive_folder,
# #     create_spreadsheet, read_from_spreadsheet
# # )
# # from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE

# # def pco_dashboard(drive_service, sheets_service):
# #     st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
# #     mcm_periods = load_mcm_periods(drive_service)

# #     with st.sidebar:
# #         try:
# #             st.image("logo.png", width=80) # Use local logo
# #         except Exception as e:
# #             st.sidebar.warning(f"Could not load logo.png: {e}")
# #             st.sidebar.markdown("*(Logo)*") 

# #         st.markdown(f"**User:** {st.session_state.username}")
# #         st.markdown(f"**Role:** {st.session_state.role}")
# #         if st.button("Logout", key="pco_logout_styled", use_container_width=True):
# #             st.session_state.logged_in = False
# #             st.session_state.username = ""
# #             st.session_state.role = ""
# #             st.session_state.drive_structure_initialized = False
# #             keys_to_clear = ['period_to_delete', 'show_delete_confirm', 'num_paras_to_show_pco']
# #             for key in keys_to_clear:
# #                 if key in st.session_state:
# #                     del st.session_state[key]
# #             st.rerun()
# #         st.markdown("---")

# #     selected_tab = option_menu(
# #         menu_title=None,
# #         options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "Visualizations"],
# #         icons=["calendar-plus-fill", "sliders", "eye-fill", "bar-chart-fill"],
# #         menu_icon="gear-wide-connected", default_index=0, orientation="horizontal",
# #         styles={
# #             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
# #             "icon": {"color": "#007bff", "font-size": "20px"},
# #             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
# #             "nav-link-selected": {"background-color": "#007bff", "color": "white"},
# #         })

# #     st.markdown("<div class='card'>", unsafe_allow_html=True)
# #     if selected_tab == "Create MCM Period":
# #         st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
# #         current_year = datetime.datetime.now().year
# #         years = list(range(current_year - 1, current_year + 3))
# #         months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
# #                   "November", "December"]
# #         col1, col2 = st.columns(2)
# #         with col1:
# #             selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year), key="pco_year")
# #         with col2:
# #             selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1,
# #                                                key="pco_month")
# #         selected_month_num = months.index(selected_month_name) + 1
# #         period_key = f"{selected_year}-{selected_month_num:02d}"

# #         if period_key in mcm_periods:
# #             st.warning(f"MCM Period for {selected_month_name} {selected_year} already exists.")
# #         else:
# #             if st.button(f"Create MCM for {selected_month_name} {selected_year}", key="pco_create_mcm",
# #                          use_container_width=True):
# #                 if not drive_service or not sheets_service or not st.session_state.get('master_drive_folder_id'):
# #                     st.error("Google Services or Master Drive Folder not available. Cannot create MCM period.")
# #                 else:
# #                     with st.spinner("Creating Google Drive folder and Spreadsheet..."):
# #                         master_folder_id = st.session_state.master_drive_folder_id
# #                         folder_name = f"MCM_DARs_{selected_month_name}_{selected_year}"
# #                         spreadsheet_title = f"MCM_Audit_Paras_{selected_month_name}_{selected_year}"

# #                         folder_id, folder_url = create_drive_folder(drive_service, folder_name,
# #                                                                     parent_id=master_folder_id)
# #                         sheet_id, sheet_url = create_spreadsheet(sheets_service, drive_service, spreadsheet_title,
# #                                                                  parent_folder_id=master_folder_id)

# #                         if folder_id and sheet_id:
# #                             mcm_periods[period_key] = {
# #                                 "year": selected_year, "month_num": selected_month_num,
# #                                 "month_name": selected_month_name,
# #                                 "drive_folder_id": folder_id, "drive_folder_url": folder_url,
# #                                 "spreadsheet_id": sheet_id, "spreadsheet_url": sheet_url, "active": True
# #                             }
# #                             if save_mcm_periods(drive_service, mcm_periods):
# #                                 st.success(
# #                                     f"Successfully created MCM period for {selected_month_name} {selected_year}!")
# #                                 st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>",
# #                                             unsafe_allow_html=True)
# #                                 st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>",
# #                                             unsafe_allow_html=True)
# #                                 st.balloons(); time.sleep(0.5); st.rerun()
# #                             else:
# #                                 st.error("Failed to save MCM period configuration to Drive.")
# #                         else:
# #                             st.error("Failed to create Drive folder or Spreadsheet.")

# #     elif selected_tab == "Manage MCM Periods":
# #         st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
# #         st.markdown("<h4 style='color: red;'>Pls Note ,Deleting the records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
# #         st.markdown("<h5 style='color: green;'>Only the Months which are marked as 'Active' by Planning officer, will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
# #         if not mcm_periods:
# #             st.info("No MCM periods created yet.")
# #         else:
# #             sorted_periods_keys = sorted(mcm_periods.keys(), reverse=True)
# #             for period_key in sorted_periods_keys:
# #                 data = mcm_periods[period_key]
# #                 month_name_display = data.get('month_name', 'Unknown Month')
# #                 year_display = data.get('year', 'Unknown Year')
# #                 st.markdown(f"<h4>{month_name_display} {year_display}</h4>", unsafe_allow_html=True)
# #                 col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
# #                 with col1:
# #                     st.markdown(f"<a href='{data.get('drive_folder_url', '#')}' target='_blank'>Open Drive Folder</a>",
# #                                 unsafe_allow_html=True)
# #                 with col2:
# #                     st.markdown(f"<a href='{data.get('spreadsheet_url', '#')}' target='_blank'>Open Spreadsheet</a>",
# #                                 unsafe_allow_html=True)
# #                 with col3:
# #                     is_active = data.get("active", False)
# #                     new_status = st.checkbox("Active", value=is_active, key=f"active_{period_key}_styled_manage") # ensure key is unique
# #                     if new_status != is_active:
# #                         mcm_periods[period_key]["active"] = new_status
# #                         if save_mcm_periods(drive_service, mcm_periods):
# #                             month_name_succ = data.get('month_name', 'Unknown Period')
# #                             year_succ = data.get('year', '')
# #                             st.success(f"Status for {month_name_succ} {year_succ} updated."); st.rerun()
# #                         else:
# #                             st.error("Failed to save updated MCM period status to Drive.")
# #                 with col4:
# #                     if st.button("Delete Period Record", key=f"delete_mcm_{period_key}", type="secondary"):
# #                         st.session_state.period_to_delete = period_key
# #                         st.session_state.show_delete_confirm = True; st.rerun()
# #                 st.markdown("---")

# #             if st.session_state.get('show_delete_confirm', False) and st.session_state.get('period_to_delete'):
# #                 period_key_to_delete = st.session_state.period_to_delete
# #                 period_data_to_delete = mcm_periods.get(period_key_to_delete, {})
# #                 with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
# #                     st.warning(
# #                         f"Are you sure you want to delete the MCM period record for **{period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')}**?")
                    
# #                     st.error( # User requested warning message
# #                         "**Warning:** Delete period will delete the backend historic DAR data in the spreadsheet and drive. So use cautiously."
# #                     )
# #                     st.caption( # Clarification of current functionality
# #                         f"Currently, this action only removes the period's entry from the app's configuration file (`{MCM_PERIODS_FILENAME_ON_DRIVE}`). "
# #                         "To make the above warning accurate, backend logic for deleting Google Drive/Sheets resources needs to be implemented."
# #                     )
                                        
# #                     pco_password_confirm = st.text_input("Enter your PCO password:", type="password",
# #                                                          key=f"pco_pass_conf_{period_key_to_delete}")
# #                     c1, c2 = st.columns(2)
# #                     with c1:
# #                         submitted_delete = st.form_submit_button("Yes, Delete Record from Tracking", use_container_width=True)
# #                     with c2:
# #                         if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
# #                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
# #                     if submitted_delete:
# #                         if pco_password_confirm == USER_CREDENTIALS.get("planning_officer"):
# #                             del mcm_periods[period_key_to_delete]
# #                             if save_mcm_periods(drive_service, mcm_periods):
# #                                 st.success(
# #                                     f"MCM record for {period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')} deleted from tracking.");
# #                             else:
# #                                 st.error("Failed to save changes to Drive after deleting record locally.")
# #                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
# #                         else:
# #                             st.error("Incorrect password.")

# #     elif selected_tab == "View Uploaded Reports":
# #         st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
# #         active_periods = {k: v for k, v in mcm_periods.items()} # Show all periods for viewing reports, not just active
# #         if not active_periods: # Changed from mcm_periods to active_periods for consistency with text
# #             st.info("No MCM periods to view reports for.")
# #         else:
# #             period_options = [
# #                  f"{p.get('month_name')} {p.get('year')}"
# #                  for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
# #                  if p.get('month_name') and p.get('year')
# #              ]
# #             if not period_options and active_periods: 
# #                  st.warning("No valid MCM periods with complete month and year information found to display options.")
# #             elif not period_options: 
# #                  st.info("No MCM periods available.")

# #             selected_period_display = st.selectbox("Select MCM Period", options=period_options,
# #                                                    key="pco_view_reports_period_select") # Unique key
# #             if selected_period_display:
# #                 selected_period_key = next((k for k, p in active_periods.items() if
# #                             p.get('month_name') and p.get('year') and
# #                             f"{p.get('month_name')} {p.get('year')}" == selected_period_display), None)
# #                 if selected_period_key and sheets_service:
# #                     sheet_id = mcm_periods[selected_period_key]['spreadsheet_id']
# #                     with st.spinner("Loading data from Google Sheet..."):
# #                         df = read_from_spreadsheet(sheets_service, sheet_id)
# #                     if not df.empty:
# #                         st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
# #                         if 'Audit Group Number' in df.columns:
# #                             try:
# #                                 df['Audit Group Number Numeric'] = pd.to_numeric(df['Audit Group Number'], errors='coerce')
# #                                 df_summary = df.dropna(subset=['Audit Group Number Numeric']) 
# #                                 dars_per_group = df_summary.groupby('Audit Group Number Numeric')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
# #                                 st.write("**DARs Uploaded per Audit Group:**"); st.dataframe(dars_per_group, use_container_width=True)
# #                                 paras_per_group = df_summary.groupby('Audit Group Number Numeric').size().reset_index(name='Total Para Entries')
# #                                 st.write("**Total Para Entries per Audit Group:**"); st.dataframe(paras_per_group, use_container_width=True)
# #                                 st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True); st.dataframe(df, use_container_width=True)
# #                             except Exception as e:
# #                                 st.error(f"Error processing summary: {e}"); st.dataframe(df, use_container_width=True)
# #                         else:
# #                             st.warning("Missing 'Audit Group Number' column for summary."); st.dataframe(df, use_container_width=True)
# #                     else:
# #                         st.info(f"No data in spreadsheet for {selected_period_display}.")
# #                 elif not sheets_service and selected_period_key: 
# #                     st.error("Google Sheets service not available.")
    
# #     elif selected_tab == "Visualizations":
# #         st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
# #         all_mcm_periods = mcm_periods
# #         if not all_mcm_periods:
# #             st.info("No MCM periods to visualize data from.")
# #         else:
# #             viz_period_options = [
# #                 f"{p.get('month_name')} {p.get('year')}"
# #                 for k, p in sorted(all_mcm_periods.items(), key=lambda item: item[0], reverse=True)
# #                 if p.get('month_name') and p.get('year')
# #             ]
# #             if not viz_period_options and all_mcm_periods:
# #                 st.warning("No valid MCM periods with complete month/year information for visualization options.")
# #             elif not viz_period_options:
# #                  st.info("No MCM periods available to visualize.")
            
# #             selected_viz_period_display = st.selectbox("Select MCM Period for Visualization",
# #                                                        options=viz_period_options, key="pco_viz_selectbox") # Unique key
            
# #             if selected_viz_period_display and sheets_service:
# #                 selected_viz_period_key = next((k for k, p in all_mcm_periods.items() if
# #                                 p.get('month_name') and p.get('year') and
# #                                 f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_display), None)
                
# #                 if selected_viz_period_key:
# #                     sheet_id_viz = all_mcm_periods[selected_viz_period_key]['spreadsheet_id']
# #                     with st.spinner("Loading data for visualizations..."):
# #                         df_viz = read_from_spreadsheet(sheets_service, sheet_id_viz)

# #                     if not df_viz.empty:
# #                         # --- Data Cleaning and Preparation ---
# #                         amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)',
# #                                        'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
# #                         for col in amount_cols:
# #                             if col in df_viz.columns: 
# #                                 df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)
                        
# #                         if 'Audit Group Number' in df_viz.columns and pd.api.types.is_numeric_dtype(df_viz['Audit Group Number'].dropna()):
# #                             df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)
# #                             df_viz['Circle Number'] = ((df_viz['Audit Group Number'] - 1) // 3 + 1)
# #                         else:
# #                             if 'Audit Group Number' in df_viz.columns:
# #                                 st.warning("Audit Group Number column contains non-numeric data or many NaNs. Group and Circle charts might be inaccurate.")
# #                                 df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)
# #                             else:
# #                                 st.warning("Audit Group Number column is missing. Group and Circle charts cannot be generated accurately.")
# #                                 df_viz['Audit Group Number'] = 0 
# #                             df_viz['Circle Number'] = 0 
                        
# #                         df_viz['Audit Group Number Str'] = df_viz['Audit Group Number'].astype(str)
# #                         df_viz['Category'] = df_viz['Category'].fillna('Unknown') if 'Category' in df_viz.columns else 'Unknown'
# #                         df_viz['Trade Name'] = df_viz['Trade Name'].fillna('Unknown Trade Name') if 'Trade Name' in df_viz.columns else 'Unknown Trade Name'


# #                         # --- Group-wise Performance ---
# #                         st.markdown("---")
# #                         st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
# #                         if df_viz['Audit Group Number'].nunique() > 1 or (df_viz['Audit Group Number'].nunique() == 1 and df_viz['Audit Group Number'].iloc[0] != 0):
# #                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns:
# #                                 detection_data = df_viz.groupby('Audit Group Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index()
# #                                 detection_data = detection_data.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
# #                                 if not detection_data.empty:
# #                                     st.write("**Top 5 Groups by Total Detection Amount (Rs):**")
# #                                     fig_det_group = px.bar(detection_data, x='Audit Group Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
# #                                     fig_det_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category') 
# #                                     fig_det_group.update_traces(textposition='outside', marker_color='indianred')
# #                                     st.plotly_chart(fig_det_group, use_container_width=True)
# #                                 else: st.info("Not enough data for 'Top Detection Groups' chart.")

# #                             if 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
# #                                 recovery_data = df_viz.groupby('Audit Group Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
# #                                 recovery_data = recovery_data.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
# #                                 if not recovery_data.empty:
# #                                     st.write("**Top 5 Groups by Total Realisation Amount (Rs):**")
# #                                     fig_rec_group = px.bar(recovery_data, x='Audit Group Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
# #                                     fig_rec_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category') 
# #                                     fig_rec_group.update_traces(textposition='outside', marker_color='lightseagreen')
# #                                     st.plotly_chart(fig_rec_group, use_container_width=True)
# #                                 else: st.info("Not enough data for 'Top Realisation Groups' chart.")

# #                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
# #                                 group_summary = df_viz.groupby('Audit Group Number Str').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index()
# #                                 group_summary['Recovery_Ratio'] = group_summary.apply(lambda row: (row['Total_Recovered'] / row['Total_Detected']) * 100 if pd.notna(row['Total_Detected']) and row['Total_Detected'] > 0 and pd.notna(row['Total_Recovered']) else 0, axis=1)
# #                                 ratio_data = group_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
# #                                 if not ratio_data.empty:
# #                                     st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**")
# #                                     fig_ratio_group = px.bar(ratio_data, x='Audit Group Number Str', y='Recovery_Ratio', text_auto=True, labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number Str': '<b>Audit Group</b>'})
# #                                     fig_ratio_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category') 
# #                                     fig_ratio_group.update_traces(textposition='outside', marker_color='mediumpurple')
# #                                     st.plotly_chart(fig_ratio_group, use_container_width=True)
# #                                 else: st.info("Not enough data for 'Top Recovery Ratio Groups' chart.")
# #                         else:
# #                              st.info("Group-wise charts require valid 'Audit Group Number' data.")


# #                         # --- Circle-wise Performance ---
# #                         st.markdown("---")
# #                         st.markdown("<h4>Circle-wise Performance</h4>", unsafe_allow_html=True)
# #                         if df_viz['Circle Number'].nunique() > 1 or (df_viz['Circle Number'].nunique() == 1 and df_viz['Circle Number'].iloc[0] != 0):
# #                             df_viz['Circle Number Str'] = df_viz['Circle Number'].astype(str)
# #                             if 'DAR PDF URL' in df_viz.columns:
# #                                 dars_per_circle = df_viz.groupby('Circle Number Str')['DAR PDF URL'].nunique().reset_index(name='DARs Sponsored')
# #                                 dars_per_circle = dars_per_circle.sort_values(by='DARs Sponsored', ascending=False)
# #                                 if not dars_per_circle.empty:
# #                                     st.write("**DARs Sponsored per Circle:**")
# #                                     fig_dars_circle = px.bar(dars_per_circle, x='Circle Number Str', y='DARs Sponsored', text_auto=True, labels={'DARs Sponsored': 'Number of DARs Sponsored', 'Circle Number Str': '<b>Circle Number</b>'})
# #                                     fig_dars_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
# #                                     fig_dars_circle.update_traces(textposition='outside', marker_color='skyblue')
# #                                     st.plotly_chart(fig_dars_circle, use_container_width=True)
# #                                 else: st.info("Not enough data for 'DARs Sponsored per Circle' chart.")

# #                             paras_per_circle = df_viz.groupby('Circle Number Str').size().reset_index(name='Total Para Entries')
# #                             paras_per_circle = paras_per_circle.sort_values(by='Total Para Entries', ascending=False)
# #                             if not paras_per_circle.empty:
# #                                 st.write("**Total Para Entries per Circle:**")
# #                                 fig_paras_circle = px.bar(paras_per_circle, x='Circle Number Str', y='Total Para Entries', text_auto=True, labels={'Total Para Entries': 'Total Para Entries', 'Circle Number Str': '<b>Circle Number</b>'})
# #                                 fig_paras_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
# #                                 fig_paras_circle.update_traces(textposition='outside', marker_color='lightcoral')
# #                                 st.plotly_chart(fig_paras_circle, use_container_width=True)
# #                             else: st.info("Not enough data for 'Total Para Entries per Circle' chart.")

# #                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns:
# #                                 detection_per_circle = df_viz.groupby('Circle Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index()
# #                                 detection_per_circle = detection_per_circle.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False)
# #                                 if not detection_per_circle.empty:
# #                                     st.write("**Total Detection Amount (Rs) per Circle:**")
# #                                     fig_det_circle = px.bar(detection_per_circle, x='Circle Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Circle Number Str': '<b>Circle Number</b>'})
# #                                     fig_det_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
# #                                     fig_det_circle.update_traces(textposition='outside', marker_color='mediumseagreen')
# #                                     st.plotly_chart(fig_det_circle, use_container_width=True)
# #                                 else: st.info("Not enough data for 'Total Detection per Circle' chart.")
                            
# #                             if 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
# #                                 recovery_per_circle = df_viz.groupby('Circle Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
# #                                 recovery_per_circle = recovery_per_circle.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False)
# #                                 if not recovery_per_circle.empty:
# #                                     st.write("**Total Recovery Amount (Rs) per Circle:**")
# #                                     fig_rec_circle = px.bar(recovery_per_circle, x='Circle Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Recovery (Rs)', 'Circle Number Str': '<b>Circle Number</b>'})
# #                                     fig_rec_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
# #                                     fig_rec_circle.update_traces(textposition='outside', marker_color='goldenrod')
# #                                     st.plotly_chart(fig_rec_circle, use_container_width=True)
# #                                 else: st.info("Not enough data for 'Total Recovery per Circle' chart.")
# #                         else:
# #                              st.info("Circle-wise charts require valid 'Circle Number' data, derived from 'Audit Group Number'.")


# #                         # --- Treemap Visualizations ---
# #                         st.markdown("---")
# #                         st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
                        
# #                         if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Trade Name' in df_viz.columns and 'Category' in df_viz.columns :
# #                             df_detection_treemap_source = df_viz[df_viz['Total Amount Detected (Overall Rs)'] > 0].copy()
# #                             df_detection_treemap_unique_dars = df_detection_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in df_detection_treemap_source.columns and df_detection_treemap_source['DAR PDF URL'].notna().any() else df_detection_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Detected (Overall Rs)'])

# #                             if not df_detection_treemap_unique_dars.empty:
# #                                 st.write("**Detection Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
# #                                 try:
# #                                     fig_treemap_detection = px.treemap(
# #                                         df_detection_treemap_unique_dars,
# #                                         path=[px.Constant("All Detections"), 'Category', 'Trade Name'],
# #                                         values='Total Amount Detected (Overall Rs)',
# #                                         color='Category',
# #                                         hover_name='Trade Name',
# #                                         custom_data=['Audit Group Number Str', 'Trade Name'], # Ensure 'Trade Name' is explicitly in custom_data for hovertemplate
# #                                         color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'}
# #                                     )
# #                                     fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
# #                                     fig_treemap_detection.data[0].textinfo = 'label+value'
# #                                     fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Rs<extra></extra>")
# #                                     st.plotly_chart(fig_treemap_detection, use_container_width=True)
# #                                 except Exception as e_treemap_det: st.error(f"Could not generate detection treemap: {e_treemap_det}")
# #                             else: st.info("No positive detection data (Overall Rs) available for the treemap.")
# #                         else: st.info("Required columns for Detection Treemap (Total Amount Detected, Category, Trade Name) are missing.")

# #                         if 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Trade Name' in df_viz.columns and 'Category' in df_viz.columns:
# #                             df_recovery_treemap_source = df_viz[df_viz['Total Amount Recovered (Overall Rs)'] > 0].copy()
# #                             df_recovery_treemap_unique_dars = df_recovery_treemap_source.drop_duplicates(subset=['DAR PDF URL']) if 'DAR PDF URL' in df_recovery_treemap_source.columns and df_recovery_treemap_source['DAR PDF URL'].notna().any() else df_recovery_treemap_source.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Recovered (Overall Rs)'])
                            
# #                             if not df_recovery_treemap_unique_dars.empty:
# #                                 st.write("**Recovery Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
# #                                 try:
# #                                     fig_treemap_recovery = px.treemap(
# #                                         df_recovery_treemap_unique_dars,
# #                                         path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'],
# #                                         values='Total Amount Recovered (Overall Rs)',
# #                                         color='Category',
# #                                         hover_name='Trade Name',
# #                                         custom_data=['Audit Group Number Str', 'Trade Name'],
# #                                         color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'}
# #                                     )
# #                                     fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
# #                                     fig_treemap_recovery.data[0].textinfo = 'label+value'
# #                                     fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Rs<extra></extra>")
# #                                     st.plotly_chart(fig_treemap_recovery, use_container_width=True)
# #                                 except Exception as e_treemap_rec: st.error(f"Could not generate recovery treemap: {e_treemap_rec}")
# #                             else: st.info("No positive recovery data (Overall Rs) available for the treemap.")
# #                         else: st.info("Required columns for Recovery Treemap (Total Amount Recovered, Category, Trade Name) are missing.")


# #                         # --- Para-wise Performance (Input type changed) ---
# #                         st.markdown("---")
# #                         st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
                        
# #                         if 'num_paras_to_show_pco' not in st.session_state:
# #                             st.session_state.num_paras_to_show_pco = 5 

# #                         n_paras_input_val = st.text_input( # Changed input method
# #                             "Enter N for Top N Paras (e.g., 5) and press Enter:",
# #                             value=str(st.session_state.num_paras_to_show_pco),
# #                             key="pco_n_paras_text_input_final" 
# #                         )
                        
# #                         num_paras_to_show_val = st.session_state.num_paras_to_show_pco # Default to session state
# #                         try:
# #                             parsed_n = int(n_paras_input_val)
# #                             if parsed_n < 1:
# #                                 num_paras_to_show_val = 5 
# #                                 if str(parsed_n) != n_paras_input_val or parsed_n != 5 : # Avoid warning if input was benignly '5'
# #                                      st.warning("N must be a positive integer. Displaying Top 5.", icon="⚠️")
# #                             elif parsed_n > 50: 
# #                                 num_paras_to_show_val = 50
# #                                 st.warning("N capped at 50. Displaying Top 50.", icon="⚠️")
# #                             else:
# #                                 num_paras_to_show_val = parsed_n
# #                             st.session_state.num_paras_to_show_pco = num_paras_to_show_val 
# #                         except ValueError:
# #                             if n_paras_input_val != str(st.session_state.num_paras_to_show_pco):
# #                                 st.warning(f"Invalid input for N ('{n_paras_input_val}'). Please enter a number. Using: {num_paras_to_show_val}", icon="⚠️")
                        
# #                         df_paras_only = df_viz[df_viz['Audit Para Number'].notna() & 
# #                                                (~df_viz['Audit Para Heading'].astype(str).isin([
# #                                                    "N/A - Header Info Only (Add Paras Manually)", 
# #                                                    "Manual Entry Required", 
# #                                                    "Manual Entry - PDF Error", 
# #                                                    "Manual Entry - PDF Upload Failed"
# #                                                    ]))]

# #                         if 'Revenue Involved (Lakhs Rs)' in df_paras_only.columns:
# #                             top_detection_paras = df_paras_only.nlargest(num_paras_to_show_val, 'Revenue Involved (Lakhs Rs)')
# #                             if not top_detection_paras.empty:
# #                                 st.write(f"**Top {num_paras_to_show_val} Detection Paras (by Revenue Involved):**")
# #                                 display_cols_det_para = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)']
# #                                 existing_cols_det = [col for col in display_cols_det_para if col in top_detection_paras.columns]
# #                                 st.dataframe(top_detection_paras[existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
# #                             else: st.info("Not enough data for 'Top Detection Paras' list.")
                        
# #                         if 'Revenue Recovered (Lakhs Rs)' in df_paras_only.columns:
# #                             top_recovery_paras = df_paras_only.nlargest(num_paras_to_show_val, 'Revenue Recovered (Lakhs Rs)')
# #                             if not top_recovery_paras.empty:
# #                                 st.write(f"**Top {num_paras_to_show_val} Realisation Paras (by Revenue Recovered):**")
# #                                 display_cols_rec_para = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)']
# #                                 existing_cols_rec = [col for col in display_cols_rec_para if col in top_recovery_paras.columns]
# #                                 st.dataframe(top_recovery_paras[existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True)
# #                             else: st.info("Not enough data for 'Top Realisation Paras' list.")
# #                     else:
# #                         st.info(f"No data in spreadsheet for {selected_viz_period_display} to visualize.")
# #                 elif not sheets_service and selected_viz_period_key:
# #                     st.error("Google Sheets service not available.")
# #             elif not sheets_service and selected_viz_period_display : 
# #                 st.error("Google Sheets service not available.")
            
# #     st.markdown("</div>", unsafe_allow_html=True)
# #     # # ui_pco.py
# # # import streamlit as st
# # # import datetime
# # # import time
# # # import pandas as pd
# # # import plotly.express as px
# # # from streamlit_option_menu import option_menu

# # # from google_utils import (
# # #     load_mcm_periods, save_mcm_periods, create_drive_folder,
# # #     create_spreadsheet, read_from_spreadsheet
# # # )
# # # from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE
# # # # import math # Not strictly needed as integer division is used

# # # def pco_dashboard(drive_service, sheets_service):
# # #     st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
# # #     mcm_periods = load_mcm_periods(drive_service)

# # #     with st.sidebar:
# # #         st.image(
# # #             "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Indian_Ministry_of_Finance_logo.svg/1200px-Indian_Ministry_of_Finance_logo.svg.png",
# # #             width=80)
# # #         st.markdown(f"**User:** {st.session_state.username}")
# # #         st.markdown(f"**Role:** {st.session_state.role}")
# # #         if st.button("Logout", key="pco_logout_styled", use_container_width=True):
# # #             st.session_state.logged_in = False
# # #             st.session_state.username = ""
# # #             st.session_state.role = ""
# # #             st.session_state.drive_structure_initialized = False
# # #             # Clear any other PCO specific session state if necessary
# # #             keys_to_clear = ['period_to_delete', 'show_delete_confirm']
# # #             for key in keys_to_clear:
# # #                 if key in st.session_state:
# # #                     del st.session_state[key]
# # #             st.rerun()
# # #         st.markdown("---")

# # #     selected_tab = option_menu(
# # #         menu_title=None,
# # #         options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "Visualizations"],
# # #         icons=["calendar-plus-fill", "sliders", "eye-fill", "bar-chart-fill"],
# # #         menu_icon="gear-wide-connected", default_index=0, orientation="horizontal",
# # #         styles={
# # #             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
# # #             "icon": {"color": "#007bff", "font-size": "20px"},
# # #             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
# # #             "nav-link-selected": {"background-color": "#007bff", "color": "white"},
# # #         })

# # #     st.markdown("<div class='card'>", unsafe_allow_html=True)
# # #     if selected_tab == "Create MCM Period":
# # #         st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
# # #         current_year = datetime.datetime.now().year
# # #         years = list(range(current_year - 1, current_year + 3))
# # #         months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
# # #                   "November", "December"]
# # #         col1, col2 = st.columns(2)
# # #         with col1:
# # #             selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year), key="pco_year")
# # #         with col2:
# # #             selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1,
# # #                                                key="pco_month")
# # #         selected_month_num = months.index(selected_month_name) + 1
# # #         period_key = f"{selected_year}-{selected_month_num:02d}"

# # #         if period_key in mcm_periods:
# # #             st.warning(f"MCM Period for {selected_month_name} {selected_year} already exists.")
# # #         else:
# # #             if st.button(f"Create MCM for {selected_month_name} {selected_year}", key="pco_create_mcm",
# # #                          use_container_width=True):
# # #                 if not drive_service or not sheets_service or not st.session_state.get('master_drive_folder_id'):
# # #                     st.error("Google Services or Master Drive Folder not available. Cannot create MCM period.")
# # #                 else:
# # #                     with st.spinner("Creating Google Drive folder and Spreadsheet..."):
# # #                         master_folder_id = st.session_state.master_drive_folder_id
# # #                         folder_name = f"MCM_DARs_{selected_month_name}_{selected_year}"
# # #                         spreadsheet_title = f"MCM_Audit_Paras_{selected_month_name}_{selected_year}"

# # #                         folder_id, folder_url = create_drive_folder(drive_service, folder_name,
# # #                                                                     parent_id=master_folder_id)
# # #                         sheet_id, sheet_url = create_spreadsheet(sheets_service, drive_service, spreadsheet_title,
# # #                                                                  parent_folder_id=master_folder_id)

# # #                         if folder_id and sheet_id:
# # #                             mcm_periods[period_key] = {
# # #                                 "year": selected_year, "month_num": selected_month_num,
# # #                                 "month_name": selected_month_name,
# # #                                 "drive_folder_id": folder_id, "drive_folder_url": folder_url,
# # #                                 "spreadsheet_id": sheet_id, "spreadsheet_url": sheet_url, "active": True
# # #                             }
# # #                             if save_mcm_periods(drive_service, mcm_periods):
# # #                                 st.success(
# # #                                     f"Successfully created MCM period for {selected_month_name} {selected_year}!")
# # #                                 st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>",
# # #                                             unsafe_allow_html=True)
# # #                                 st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>",
# # #                                             unsafe_allow_html=True)
# # #                                 st.balloons(); time.sleep(0.5); st.rerun()
# # #                             else:
# # #                                 st.error("Failed to save MCM period configuration to Drive.")
# # #                         else:
# # #                             st.error("Failed to create Drive folder or Spreadsheet.")

# # #     elif selected_tab == "Manage MCM Periods":
# # #         st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
# # #         if not mcm_periods:
# # #             st.info("No MCM periods created yet.")
# # #         else:
# # #             sorted_periods_keys = sorted(mcm_periods.keys(), reverse=True)
# # #             for period_key in sorted_periods_keys:
# # #                 data = mcm_periods[period_key]
# # #                 month_name_display = data.get('month_name', 'Unknown Month')
# # #                 year_display = data.get('year', 'Unknown Year')
# # #                 st.markdown(f"<h4>{month_name_display} {year_display}</h4>", unsafe_allow_html=True)
# # #                 col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
# # #                 with col1:
# # #                     st.markdown(f"<a href='{data.get('drive_folder_url', '#')}' target='_blank'>Open Drive Folder</a>",
# # #                                 unsafe_allow_html=True)
# # #                 with col2:
# # #                     st.markdown(f"<a href='{data.get('spreadsheet_url', '#')}' target='_blank'>Open Spreadsheet</a>",
# # #                                 unsafe_allow_html=True)
# # #                 with col3:
# # #                     is_active = data.get("active", False)
# # #                     new_status = st.checkbox("Active", value=is_active, key=f"active_{period_key}_styled")
# # #                     if new_status != is_active:
# # #                         mcm_periods[period_key]["active"] = new_status
# # #                         if save_mcm_periods(drive_service, mcm_periods):
# # #                             month_name_succ = data.get('month_name', 'Unknown Period')
# # #                             year_succ = data.get('year', '')
# # #                             st.success(f"Status for {month_name_succ} {year_succ} updated."); st.rerun()
# # #                         else:
# # #                             st.error("Failed to save updated MCM period status to Drive.")
# # #                 with col4:
# # #                     if st.button("Delete Period Record", key=f"delete_mcm_{period_key}", type="secondary"):
# # #                         st.session_state.period_to_delete = period_key
# # #                         st.session_state.show_delete_confirm = True; st.rerun()
# # #                 st.markdown("---")

# # #             if st.session_state.get('show_delete_confirm', False) and st.session_state.get('period_to_delete'):
# # #                 period_key_to_delete = st.session_state.period_to_delete
# # #                 period_data_to_delete = mcm_periods.get(period_key_to_delete, {})
# # #                 with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
# # #                     st.warning(
# # #                         f"Are you sure you want to delete the MCM period record for **{period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')}** from this application?")
# # #                     st.caption(
# # #                         f"This action only removes the period from the app's tracking (from the `{MCM_PERIODS_FILENAME_ON_DRIVE}` file on Google Drive). It **does NOT delete** the actual Google Drive folder or the Google Spreadsheet.")
# # #                     pco_password_confirm = st.text_input("Enter your PCO password:", type="password",
# # #                                                          key=f"pco_pass_conf_{period_key_to_delete}")
# # #                     c1, c2 = st.columns(2)
# # #                     with c1:
# # #                         submitted_delete = st.form_submit_button("Yes, Delete Record", use_container_width=True)
# # #                     with c2:
# # #                         if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
# # #                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
# # #                     if submitted_delete:
# # #                         if pco_password_confirm == USER_CREDENTIALS.get("planning_officer"):
# # #                             del mcm_periods[period_key_to_delete]
# # #                             if save_mcm_periods(drive_service, mcm_periods):
# # #                                 st.success(
# # #                                     f"MCM record for {period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')} deleted.");
# # #                             else:
# # #                                 st.error("Failed to save changes to Drive after deleting record locally.")
# # #                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
# # #                         else:
# # #                             st.error("Incorrect password.")

# # #     elif selected_tab == "View Uploaded Reports":
# # #         st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
# # #         active_periods = {k: v for k, v in mcm_periods.items()}
# # #         if not active_periods:
# # #             st.info("No MCM periods to view reports for.")
# # #         else:
# # #             period_options = [
# # #                  f"{p.get('month_name')} {p.get('year')}"
# # #                  for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
# # #                  if p.get('month_name') and p.get('year')
# # #              ]
# # #             if not period_options and active_periods: # Check if active_periods was not empty
# # #                  st.warning("No valid MCM periods with complete month and year information found to display options.")
# # #             elif not period_options: # Only if active_periods was also empty
# # #                  st.info("No MCM periods available.")

# # #             selected_period_display = st.selectbox("Select MCM Period", options=period_options,
# # #                                                    key="pco_view_reports_period")
# # #             if selected_period_display:
# # #                 selected_period_key = next((k for k, p in active_periods.items() if
# # #                             p.get('month_name') and p.get('year') and
# # #                             f"{p.get('month_name')} {p.get('year')}" == selected_period_display), None)
# # #                 if selected_period_key and sheets_service:
# # #                     sheet_id = mcm_periods[selected_period_key]['spreadsheet_id']
# # #                     with st.spinner("Loading data from Google Sheet..."):
# # #                         df = read_from_spreadsheet(sheets_service, sheet_id)
# # #                     if not df.empty:
# # #                         st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
# # #                         if 'Audit Group Number' in df.columns:
# # #                             try:
# # #                                 df['Audit Group Number'] = pd.to_numeric(df['Audit Group Number'], errors='coerce')
# # #                                 df.dropna(subset=['Audit Group Number'], inplace=True) # Crucial for numeric grouping
# # #                                 dars_per_group = df.groupby('Audit Group Number')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
# # #                                 st.write("**DARs Uploaded per Audit Group:**"); st.dataframe(dars_per_group, use_container_width=True)
# # #                                 paras_per_group = df.groupby('Audit Group Number').size().reset_index(name='Total Para Entries')
# # #                                 st.write("**Total Para Entries per Audit Group:**"); st.dataframe(paras_per_group, use_container_width=True)
# # #                                 st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True); st.dataframe(df, use_container_width=True)
# # #                             except Exception as e:
# # #                                 st.error(f"Error processing summary: {e}"); st.dataframe(df, use_container_width=True)
# # #                         else:
# # #                             st.warning("Missing 'Audit Group Number' column."); st.dataframe(df, use_container_width=True)
# # #                     else:
# # #                         st.info(f"No data in spreadsheet for {selected_period_display}.")
# # #                 elif not sheets_service and selected_period_key: # Added selected_period_key check
# # #                     st.error("Google Sheets service not available.")

# # #     elif selected_tab == "Visualizations":
# # #         st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
# # #         all_mcm_periods = mcm_periods
# # #         if not all_mcm_periods:
# # #             st.info("No MCM periods to visualize data from.")
# # #         else:
# # #             viz_period_options = [
# # #                 f"{p.get('month_name')} {p.get('year')}"
# # #                 for k, p in sorted(all_mcm_periods.items(), key=lambda item: item[0], reverse=True)
# # #                 if p.get('month_name') and p.get('year')
# # #             ]
# # #             if not viz_period_options and all_mcm_periods:
# # #                 st.warning("No valid MCM periods with complete month and year information found for visualization options.")
# # #             elif not viz_period_options:
# # #                  st.info("No MCM periods available to visualize.")
            
# # #             selected_viz_period_display = st.selectbox("Select MCM Period for Visualization",
# # #                                                        options=viz_period_options, key="pco_viz_period")
# # #             if selected_viz_period_display and sheets_service:
# # #                 selected_viz_period_key = next((k for k, p in all_mcm_periods.items() if
# # #                                 p.get('month_name') and p.get('year') and
# # #                                 f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_display), None)
                
# # #                 if selected_viz_period_key:
# # #                     sheet_id_viz = all_mcm_periods[selected_viz_period_key]['spreadsheet_id']
# # #                     with st.spinner("Loading data for visualizations..."):
# # #                         df_viz = read_from_spreadsheet(sheets_service, sheet_id_viz)

# # #                     if not df_viz.empty:
# # #                         # --- Data Cleaning and Preparation ---
# # #                         amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)',
# # #                                        'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
# # #                         for col in amount_cols:
# # #                             if col in df_viz.columns: 
# # #                                 df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)
                        
# # #                         if 'Audit Group Number' in df_viz.columns and df_viz['Audit Group Number'].notna().all():
# # #                             df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)
# # #                             # Calculate Circle Number: (Group Number - 1) // 3 + 1
# # #                             df_viz['Circle Number'] = ((df_viz['Audit Group Number'] - 1) // 3 + 1)
# # #                         else:
# # #                             st.warning("Audit Group Number column is missing or contains non-numeric/NaN values. Group and Circle wise charts might be affected or unavailable.")
# # #                             # Ensure columns exist even if they can't be fully populated
# # #                             if 'Audit Group Number' not in df_viz.columns: df_viz['Audit Group Number'] = 0 
# # #                             df_viz['Circle Number'] = 0 # Placeholder if Audit Group Number is problematic
                        
# # #                         df_viz['Audit Group Number Str'] = df_viz['Audit Group Number'].astype(str)
# # #                         if 'Category' in df_viz.columns:
# # #                              df_viz['Category'] = df_viz['Category'].fillna('Unknown')
# # #                         else:
# # #                              df_viz['Category'] = 'Unknown'
# # #                         if 'Trade Name' in df_viz.columns:
# # #                              df_viz['Trade Name'] = df_viz['Trade Name'].fillna('Unknown Trade Name')
# # #                         else:
# # #                              df_viz['Trade Name'] = 'Unknown Trade Name'


# # #                         # --- Group-wise Performance ---
# # #                         st.markdown("---")
# # #                         st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
# # #                         if df_viz['Audit Group Number'].nunique() > 1 or (df_viz['Audit Group Number'].nunique() == 1 and df_viz['Audit Group Number'].iloc[0] != 0): # Check if there's valid group data
# # #                             # Top 5 Groups by Total Detection
# # #                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns:
# # #                                 detection_data = df_viz.groupby('Audit Group Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index()
# # #                                 detection_data = detection_data.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
# # #                                 if not detection_data.empty:
# # #                                     st.write("**Top 5 Groups by Total Detection Amount (Rs):**")
# # #                                     fig_det_group = px.bar(detection_data, x='Audit Group Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True,
# # #                                                  labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
# # #                                     fig_det_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, 
# # #                                                           xaxis_type='category') 
# # #                                     fig_det_group.update_traces(textposition='outside', marker_color='indianred')
# # #                                     st.plotly_chart(fig_det_group, use_container_width=True)
# # #                                 else: st.info("Not enough data for 'Top Detection Groups' chart.")

# # #                             # Top 5 Groups by Total Realisation
# # #                             if 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
# # #                                 recovery_data = df_viz.groupby('Audit Group Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
# # #                                 recovery_data = recovery_data.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
# # #                                 if not recovery_data.empty:
# # #                                     st.write("**Top 5 Groups by Total Realisation Amount (Rs):**")
# # #                                     fig_rec_group = px.bar(recovery_data, x='Audit Group Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True,
# # #                                                  labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number Str': '<b>Audit Group</b>'})
# # #                                     fig_rec_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, 
# # #                                                           xaxis_type='category') 
# # #                                     fig_rec_group.update_traces(textposition='outside', marker_color='lightseagreen')
# # #                                     st.plotly_chart(fig_rec_group, use_container_width=True)
# # #                                 else: st.info("Not enough data for 'Top Realisation Groups' chart.")

# # #                             # Top 5 Groups by Recovery/Detection Ratio
# # #                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
# # #                                 group_summary = df_viz.groupby('Audit Group Number Str').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index()
# # #                                 group_summary['Recovery_Ratio'] = group_summary.apply(lambda row: (row['Total_Recovered'] / row['Total_Detected']) * 100 if pd.notna(row['Total_Detected']) and row['Total_Detected'] > 0 and pd.notna(row['Total_Recovered']) else 0, axis=1)
# # #                                 ratio_data = group_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
# # #                                 if not ratio_data.empty:
# # #                                     st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**")
# # #                                     fig_ratio_group = px.bar(ratio_data, x='Audit Group Number Str', y='Recovery_Ratio', text_auto=True,
# # #                                                  labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number Str': '<b>Audit Group</b>'})
# # #                                     fig_ratio_group.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, 
# # #                                                             xaxis_type='category') 
# # #                                     fig_ratio_group.update_traces(textposition='outside', marker_color='mediumpurple')
# # #                                     st.plotly_chart(fig_ratio_group, use_container_width=True)
# # #                                 else: st.info("Not enough data for 'Top Recovery Ratio Groups' chart.")
# # #                         else:
# # #                              st.info("Group-wise charts require valid 'Audit Group Number' data.")


# # #                         # --- Circle-wise Performance ---
# # #                         st.markdown("---")
# # #                         st.markdown("<h4>Circle-wise Performance</h4>", unsafe_allow_html=True)
# # #                         if df_viz['Circle Number'].nunique() > 1 or (df_viz['Circle Number'].nunique() == 1 and df_viz['Circle Number'].iloc[0] != 0): # Check if there's valid circle data
# # #                             df_viz['Circle Number Str'] = df_viz['Circle Number'].astype(str)
# # #                             # 1. Circle wise number of DARs
# # #                             if 'DAR PDF URL' in df_viz.columns:
# # #                                 dars_per_circle = df_viz.groupby('Circle Number Str')['DAR PDF URL'].nunique().reset_index(name='DARs Sponsored')
# # #                                 dars_per_circle = dars_per_circle.sort_values(by='DARs Sponsored', ascending=False)
# # #                                 if not dars_per_circle.empty:
# # #                                     st.write("**DARs Sponsored per Circle:**")
# # #                                     fig_dars_circle = px.bar(dars_per_circle, x='Circle Number Str', y='DARs Sponsored', text_auto=True,
# # #                                                              labels={'DARs Sponsored': 'Number of DARs Sponsored', 'Circle Number Str': '<b>Circle Number</b>'})
# # #                                     fig_dars_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14,
# # #                                                                  xaxis_tickfont_size=12, yaxis_tickfont_size=12,
# # #                                                                  xaxis_type='category')
# # #                                     fig_dars_circle.update_traces(textposition='outside', marker_color='skyblue')
# # #                                     st.plotly_chart(fig_dars_circle, use_container_width=True)
# # #                                 else: st.info("Not enough data for 'DARs Sponsored per Circle' chart.")

# # #                             # 2. Circle wise total paras
# # #                             paras_per_circle = df_viz.groupby('Circle Number Str').size().reset_index(name='Total Para Entries')
# # #                             paras_per_circle = paras_per_circle.sort_values(by='Total Para Entries', ascending=False)
# # #                             if not paras_per_circle.empty:
# # #                                 st.write("**Total Para Entries per Circle:**")
# # #                                 fig_paras_circle = px.bar(paras_per_circle, x='Circle Number Str', y='Total Para Entries', text_auto=True,
# # #                                                          labels={'Total Para Entries': 'Total Para Entries', 'Circle Number Str': '<b>Circle Number</b>'})
# # #                                 fig_paras_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14,
# # #                                                              xaxis_tickfont_size=12, yaxis_tickfont_size=12,
# # #                                                              xaxis_type='category')
# # #                                 fig_paras_circle.update_traces(textposition='outside', marker_color='lightcoral')
# # #                                 st.plotly_chart(fig_paras_circle, use_container_width=True)
# # #                             else: st.info("Not enough data for 'Total Para Entries per Circle' chart.")

# # #                             # 3. Circle wise Total detection amount
# # #                             if 'Total Amount Detected (Overall Rs)' in df_viz.columns:
# # #                                 detection_per_circle = df_viz.groupby('Circle Number Str')['Total Amount Detected (Overall Rs)'].sum().reset_index()
# # #                                 detection_per_circle = detection_per_circle.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False)
# # #                                 if not detection_per_circle.empty:
# # #                                     st.write("**Total Detection Amount (Rs) per Circle:**")
# # #                                     fig_det_circle = px.bar(detection_per_circle, x='Circle Number Str', y='Total Amount Detected (Overall Rs)', text_auto=True,
# # #                                                              labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Circle Number Str': '<b>Circle Number</b>'})
# # #                                     fig_det_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14,
# # #                                                                  xaxis_tickfont_size=12, yaxis_tickfont_size=12,
# # #                                                                  xaxis_type='category')
# # #                                     fig_det_circle.update_traces(textposition='outside', marker_color='mediumseagreen')
# # #                                     st.plotly_chart(fig_det_circle, use_container_width=True)
# # #                                 else: st.info("Not enough data for 'Total Detection per Circle' chart.")
                            
# # #                             # 4. Circle wise total recovery amount
# # #                             if 'Total Amount Recovered (Overall Rs)' in df_viz.columns:
# # #                                 recovery_per_circle = df_viz.groupby('Circle Number Str')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
# # #                                 recovery_per_circle = recovery_per_circle.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False)
# # #                                 if not recovery_per_circle.empty:
# # #                                     st.write("**Total Recovery Amount (Rs) per Circle:**")
# # #                                     fig_rec_circle = px.bar(recovery_per_circle, x='Circle Number Str', y='Total Amount Recovered (Overall Rs)', text_auto=True,
# # #                                                              labels={'Total Amount Recovered (Overall Rs)': 'Total Recovery (Rs)', 'Circle Number Str': '<b>Circle Number</b>'})
# # #                                     fig_rec_circle.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14,
# # #                                                                  xaxis_tickfont_size=12, yaxis_tickfont_size=12,
# # #                                                                  xaxis_type='category')
# # #                                     fig_rec_circle.update_traces(textposition='outside', marker_color='goldenrod')
# # #                                     st.plotly_chart(fig_rec_circle, use_container_width=True)
# # #                                 else: st.info("Not enough data for 'Total Recovery per Circle' chart.")
# # #                         else:
# # #                              st.info("Circle-wise charts require valid 'Circle Number' data, derived from 'Audit Group Number'.")


# # #                         # --- Treemap Visualizations ---
# # #                         st.markdown("---")
# # #                         st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
                        
# # #                         # Treemap for Detection
# # #                         if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Trade Name' in df_viz.columns and 'Category' in df_viz.columns :
# # #                             df_detection_treemap = df_viz[df_viz['Total Amount Detected (Overall Rs)'] > 0].copy()
# # #                             # To avoid issues with many small, identical entries if overall amounts are repeated per para for the same DAR:
# # #                             # We only want one entry per DAR for this specific visualization of *Overall* amounts.
# # #                             # A DAR is likely unique by 'DAR PDF URL' or a combination of 'Trade Name' and 'GSTIN' (if GSTIN is present)
# # #                             # For simplicity, if 'DAR PDF URL' is available and reliable:
# # #                             if 'DAR PDF URL' in df_detection_treemap.columns:
# # #                                 df_detection_treemap_unique_dars = df_detection_treemap.drop_duplicates(subset=['DAR PDF URL'])
# # #                             else: # Fallback: might still show multiple entries if overall amounts are repeated per Trade Name for different reasons
# # #                                 df_detection_treemap_unique_dars = df_detection_treemap.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Detected (Overall Rs)'])


# # #                             if not df_detection_treemap_unique_dars.empty:
# # #                                 st.write("**Detection Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
# # #                                 try:
# # #                                     fig_treemap_detection = px.treemap(
# # #                                         df_detection_treemap_unique_dars,
# # #                                         path=[px.Constant("All Detections"), 'Category', 'Trade Name'],
# # #                                         values='Total Amount Detected (Overall Rs)',
# # #                                         color='Category',
# # #                                         hover_name='Trade Name',
# # #                                         custom_data=['Audit Group Number Str', 'Trade Name'],
# # #                                         color_discrete_map={
# # #                                             'Large': 'rgba(230, 57, 70, 0.8)', 
# # #                                             'Medium': 'rgba(241, 196, 15, 0.8)',
# # #                                             'Small': 'rgba(26, 188, 156, 0.8)',
# # #                                             'Unknown': 'rgba(149, 165, 166, 0.7)'
# # #                                         }
# # #                                     )
# # #                                     fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
# # #                                     fig_treemap_detection.data[0].textinfo = 'label+value'
# # #                                     fig_treemap_detection.update_traces(
# # #                                         hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Rs<extra></extra>"
# # #                                     )
# # #                                     st.plotly_chart(fig_treemap_detection, use_container_width=True)
# # #                                 except Exception as e_treemap_det:
# # #                                     st.error(f"Could not generate detection treemap: {e_treemap_det}")
# # #                             else:
# # #                                 st.info("No positive detection data (Overall Rs) available for the treemap.")
# # #                         else:
# # #                             st.info("Required columns for Detection Treemap (Total Amount Detected, Category, Trade Name) are missing.")

# # #                         # Treemap for Recovery
# # #                         if 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Trade Name' in df_viz.columns and 'Category' in df_viz.columns:
# # #                             df_recovery_treemap = df_viz[df_viz['Total Amount Recovered (Overall Rs)'] > 0].copy()
# # #                             if 'DAR PDF URL' in df_recovery_treemap.columns:
# # #                                 df_recovery_treemap_unique_dars = df_recovery_treemap.drop_duplicates(subset=['DAR PDF URL'])
# # #                             else:
# # #                                 df_recovery_treemap_unique_dars = df_recovery_treemap.drop_duplicates(subset=['Trade Name', 'Category', 'Total Amount Recovered (Overall Rs)'])

# # #                             if not df_recovery_treemap_unique_dars.empty:
# # #                                 st.write("**Recovery Amounts (Overall Rs) by Trade Name (Size: Amount, Color: Category)**")
# # #                                 try:
# # #                                     fig_treemap_recovery = px.treemap(
# # #                                         df_recovery_treemap_unique_dars,
# # #                                         path=[px.Constant("All Recoveries"), 'Category', 'Trade Name'],
# # #                                         values='Total Amount Recovered (Overall Rs)',
# # #                                         color='Category',
# # #                                         hover_name='Trade Name',
# # #                                         custom_data=['Audit Group Number Str', 'Trade Name'],
# # #                                         color_discrete_map={
# # #                                             'Large': 'rgba(230, 57, 70, 0.8)',
# # #                                             'Medium': 'rgba(241, 196, 15, 0.8)',
# # #                                             'Small': 'rgba(26, 188, 156, 0.8)',
# # #                                             'Unknown': 'rgba(149, 165, 166, 0.7)'
# # #                                         }
# # #                                     )
# # #                                     fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
# # #                                     fig_treemap_recovery.data[0].textinfo = 'label+value'
# # #                                     fig_treemap_recovery.update_traces(
# # #                                         hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Rs<extra></extra>"
# # #                                     )
# # #                                     st.plotly_chart(fig_treemap_recovery, use_container_width=True)
# # #                                 except Exception as e_treemap_rec:
# # #                                      st.error(f"Could not generate recovery treemap: {e_treemap_rec}")
# # #                             else:
# # #                                 st.info("No positive recovery data (Overall Rs) available for the treemap.")
# # #                         else:
# # #                             st.info("Required columns for Recovery Treemap (Total Amount Recovered, Category, Trade Name) are missing.")


# # #                         # --- Para-wise Performance (existing) ---
# # #                         st.markdown("---")
# # #                         st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
# # #                         num_paras_to_show = st.number_input("Select N for Top N Paras:", min_value=1, max_value=20, value=5, step=1, key="top_n_paras_viz")
                        
# # #                         df_paras_only = df_viz[df_viz['Audit Para Number'].notna() & 
# # #                                                (~df_viz['Audit Para Heading'].astype(str).isin([
# # #                                                    "N/A - Header Info Only (Add Paras Manually)", 
# # #                                                    "Manual Entry Required", 
# # #                                                    "Manual Entry - PDF Error", 
# # #                                                    "Manual Entry - PDF Upload Failed"
# # #                                                    ]))]

# # #                         if 'Revenue Involved (Lakhs Rs)' in df_paras_only.columns:
# # #                             top_detection_paras = df_paras_only.nlargest(num_paras_to_show, 'Revenue Involved (Lakhs Rs)')
# # #                             if not top_detection_paras.empty:
# # #                                 st.write(f"**Top {num_paras_to_show} Detection Paras (by Revenue Involved):**")
# # #                                 display_cols_det_para = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)']
# # #                                 existing_cols_det = [col for col in display_cols_det_para if col in top_detection_paras.columns]
# # #                                 st.dataframe(top_detection_paras[existing_cols_det].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True) # Renamed for display
# # #                             else: st.info("Not enough data for 'Top Detection Paras' list.")
                        
# # #                         if 'Revenue Recovered (Lakhs Rs)' in df_paras_only.columns:
# # #                             top_recovery_paras = df_paras_only.nlargest(num_paras_to_show, 'Revenue Recovered (Lakhs Rs)')
# # #                             if not top_recovery_paras.empty:
# # #                                 st.write(f"**Top {num_paras_to_show} Realisation Paras (by Revenue Recovered):**")
# # #                                 display_cols_rec_para = ['Audit Group Number Str', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)']
# # #                                 existing_cols_rec = [col for col in display_cols_rec_para if col in top_recovery_paras.columns]
# # #                                 st.dataframe(top_recovery_paras[existing_cols_rec].rename(columns={'Audit Group Number Str': 'Audit Group'}), use_container_width=True) # Renamed for display
# # #                             else: st.info("Not enough data for 'Top Realisation Paras' list.")
# # #                     else:
# # #                         st.info(f"No data in spreadsheet for {selected_viz_period_display} to visualize.")
# # #                 elif not sheets_service and selected_viz_period_key:
# # #                     st.error("Google Sheets service not available.")
# # #             elif not sheets_service and selected_viz_period_display : # Case where period selected but sheets_service is None
# # #                 st.error("Google Sheets service not available.")
# # #             # elif not viz_period_options: # If no valid periods were found to select from, this is handled above.
# # #             #    pass 


# # #     st.markdown("</div>", unsafe_allow_html=True)# # ui_pco.py
# # # # import streamlit as st
# # # # import datetime
# # # # import time
# # # # import pandas as pd
# # # # import plotly.express as px
# # # # from streamlit_option_menu import option_menu

# # # # from google_utils import (
# # # #     load_mcm_periods, save_mcm_periods, create_drive_folder,
# # # #     create_spreadsheet, read_from_spreadsheet
# # # # )
# # # # from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE

# # # # def pco_dashboard(drive_service, sheets_service):
# # # #     st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
# # # #     mcm_periods = load_mcm_periods(drive_service)

# # # #     with st.sidebar:
# # # #         st.image(
# # # #             "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Indian_Ministry_of_Finance_logo.svg/1200px-Indian_Ministry_of_Finance_logo.svg.png",
# # # #             width=80)
# # # #         st.markdown(f"**User:** {st.session_state.username}")
# # # #         st.markdown(f"**Role:** {st.session_state.role}")
# # # #         if st.button("Logout", key="pco_logout_styled", use_container_width=True):
# # # #             st.session_state.logged_in = False
# # # #             st.session_state.username = ""
# # # #             st.session_state.role = ""
# # # #             st.session_state.drive_structure_initialized = False
# # # #             st.rerun()
# # # #         st.markdown("---")

# # # #     selected_tab = option_menu(
# # # #         menu_title=None,
# # # #         options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "Visualizations"],
# # # #         icons=["calendar-plus-fill", "sliders", "eye-fill", "bar-chart-fill"],
# # # #         menu_icon="gear-wide-connected", default_index=0, orientation="horizontal",
# # # #         styles={
# # # #             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
# # # #             "icon": {"color": "#007bff", "font-size": "20px"},
# # # #             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
# # # #             "nav-link-selected": {"background-color": "#007bff", "color": "white"},
# # # #         })

# # # #     st.markdown("<div class='card'>", unsafe_allow_html=True)
# # # #     if selected_tab == "Create MCM Period":
# # # #         st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
# # # #         current_year = datetime.datetime.now().year
# # # #         years = list(range(current_year - 1, current_year + 3))
# # # #         months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
# # # #                   "November", "December"]
# # # #         col1, col2 = st.columns(2)
# # # #         with col1:
# # # #             selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year), key="pco_year")
# # # #         with col2:
# # # #             selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1,
# # # #                                                key="pco_month")
# # # #         selected_month_num = months.index(selected_month_name) + 1
# # # #         period_key = f"{selected_year}-{selected_month_num:02d}"

# # # #         if period_key in mcm_periods:
# # # #             st.warning(f"MCM Period for {selected_month_name} {selected_year} already exists.")
# # # #         else:
# # # #             if st.button(f"Create MCM for {selected_month_name} {selected_year}", key="pco_create_mcm",
# # # #                          use_container_width=True):
# # # #                 if not drive_service or not sheets_service or not st.session_state.get('master_drive_folder_id'):
# # # #                     st.error("Google Services or Master Drive Folder not available. Cannot create MCM period.")
# # # #                 else:
# # # #                     with st.spinner("Creating Google Drive folder and Spreadsheet..."):
# # # #                         master_folder_id = st.session_state.master_drive_folder_id
# # # #                         folder_name = f"MCM_DARs_{selected_month_name}_{selected_year}"
# # # #                         spreadsheet_title = f"MCM_Audit_Paras_{selected_month_name}_{selected_year}"

# # # #                         folder_id, folder_url = create_drive_folder(drive_service, folder_name,
# # # #                                                                     parent_id=master_folder_id)
# # # #                         sheet_id, sheet_url = create_spreadsheet(sheets_service, drive_service, spreadsheet_title,
# # # #                                                                  parent_folder_id=master_folder_id)

# # # #                         if folder_id and sheet_id:
# # # #                             mcm_periods[period_key] = {
# # # #                                 "year": selected_year, "month_num": selected_month_num,
# # # #                                 "month_name": selected_month_name,
# # # #                                 "drive_folder_id": folder_id, "drive_folder_url": folder_url,
# # # #                                 "spreadsheet_id": sheet_id, "spreadsheet_url": sheet_url, "active": True
# # # #                             }
# # # #                             if save_mcm_periods(drive_service, mcm_periods):
# # # #                                 st.success(
# # # #                                     f"Successfully created MCM period for {selected_month_name} {selected_year}!")
# # # #                                 st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>",
# # # #                                             unsafe_allow_html=True)
# # # #                                 st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>",
# # # #                                             unsafe_allow_html=True)
# # # #                                 st.balloons(); time.sleep(0.5); st.rerun()
# # # #                             else:
# # # #                                 st.error("Failed to save MCM period configuration to Drive.")
# # # #                         else:
# # # #                             st.error("Failed to create Drive folder or Spreadsheet.")

# # # #     elif selected_tab == "Manage MCM Periods":
# # # #         st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
# # # #         if not mcm_periods:
# # # #             st.info("No MCM periods created yet.")
# # # #         else:
# # # #             sorted_periods_keys = sorted(mcm_periods.keys(), reverse=True)
# # # #             for period_key in sorted_periods_keys:
# # # #                 data = mcm_periods[period_key]
# # # #                 month_name_display = data.get('month_name', 'Unknown Month')
# # # #                 year_display = data.get('year', 'Unknown Year')
# # # #                 st.markdown(f"<h4>{month_name_display} {year_display}</h4>", unsafe_allow_html=True)
# # # #                 col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
# # # #                 with col1:
# # # #                     st.markdown(f"<a href='{data.get('drive_folder_url', '#')}' target='_blank'>Open Drive Folder</a>",
# # # #                                 unsafe_allow_html=True)
# # # #                 with col2:
# # # #                     st.markdown(f"<a href='{data.get('spreadsheet_url', '#')}' target='_blank'>Open Spreadsheet</a>",
# # # #                                 unsafe_allow_html=True)
# # # #                 with col3:
# # # #                     is_active = data.get("active", False)
# # # #                     new_status = st.checkbox("Active", value=is_active, key=f"active_{period_key}_styled")
# # # #                     if new_status != is_active:
# # # #                         mcm_periods[period_key]["active"] = new_status
# # # #                         if save_mcm_periods(drive_service, mcm_periods):
# # # #                             month_name_succ = data.get('month_name', 'Unknown Period')
# # # #                             year_succ = data.get('year', '')
# # # #                             st.success(f"Status for {month_name_succ} {year_succ} updated."); st.rerun()
# # # #                         else:
# # # #                             st.error("Failed to save updated MCM period status to Drive.")
# # # #                 with col4:
# # # #                     if st.button("Delete Period Record", key=f"delete_mcm_{period_key}", type="secondary"):
# # # #                         st.session_state.period_to_delete = period_key
# # # #                         st.session_state.show_delete_confirm = True; st.rerun()
# # # #                 st.markdown("---")

# # # #             if st.session_state.get('show_delete_confirm', False) and st.session_state.get('period_to_delete'):
# # # #                 period_key_to_delete = st.session_state.period_to_delete
# # # #                 period_data_to_delete = mcm_periods.get(period_key_to_delete, {})
# # # #                 with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
# # # #                     st.warning(
# # # #                         f"Are you sure you want to delete the MCM period record for **{period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')}** from this application?")
# # # #                     st.caption(
# # # #                         f"This action only removes the period from the app's tracking (from the `{MCM_PERIODS_FILENAME_ON_DRIVE}` file on Google Drive). It **does NOT delete** the actual Google Drive folder or the Google Spreadsheet.")
# # # #                     pco_password_confirm = st.text_input("Enter your PCO password:", type="password",
# # # #                                                          key=f"pco_pass_conf_{period_key_to_delete}")
# # # #                     c1, c2 = st.columns(2)
# # # #                     with c1:
# # # #                         submitted_delete = st.form_submit_button("Yes, Delete Record", use_container_width=True)
# # # #                     with c2:
# # # #                         if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
# # # #                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
# # # #                     if submitted_delete:
# # # #                         if pco_password_confirm == USER_CREDENTIALS.get("planning_officer"):
# # # #                             del mcm_periods[period_key_to_delete]
# # # #                             if save_mcm_periods(drive_service, mcm_periods):
# # # #                                 st.success(
# # # #                                     f"MCM record for {period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')} deleted.");
# # # #                             else:
# # # #                                 st.error("Failed to save changes to Drive after deleting record locally.")
# # # #                             st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
# # # #                         else:
# # # #                             st.error("Incorrect password.")

# # # #     elif selected_tab == "View Uploaded Reports":
# # # #         st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
# # # #         active_periods = {k: v for k, v in mcm_periods.items()}
# # # #         if not active_periods:
# # # #             st.info("No MCM periods to view reports for.")
# # # #         else:
# # # #             period_options = [
# # # #                  f"{p.get('month_name')} {p.get('year')}"
# # # #                  for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
# # # #                  if p.get('month_name') and p.get('year')
# # # #              ]
# # # #             if not period_options:
# # # #                  st.warning("No valid MCM periods with complete month and year information found to display options.")
# # # #             selected_period_display = st.selectbox("Select MCM Period", options=period_options,
# # # #                                                    key="pco_view_reports_period")
# # # #             if selected_period_display:
# # # #                 selected_period_key = next((k for k, p in active_periods.items() if
# # # #                             p.get('month_name') and p.get('year') and
# # # #                             f"{p.get('month_name')} {p.get('year')}" == selected_period_display), None)
# # # #                 if selected_period_key and sheets_service:
# # # #                     sheet_id = mcm_periods[selected_period_key]['spreadsheet_id']
# # # #                     with st.spinner("Loading data from Google Sheet..."):
# # # #                         df = read_from_spreadsheet(sheets_service, sheet_id)
# # # #                     if not df.empty:
# # # #                         st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
# # # #                         if 'Audit Group Number' in df.columns:
# # # #                             try:
# # # #                                 df['Audit Group Number'] = pd.to_numeric(df['Audit Group Number'], errors='coerce')
# # # #                                 df.dropna(subset=['Audit Group Number'], inplace=True)
# # # #                                 dars_per_group = df.groupby('Audit Group Number')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
# # # #                                 st.write("**DARs Uploaded per Audit Group:**"); st.dataframe(dars_per_group, use_container_width=True)
# # # #                                 paras_per_group = df.groupby('Audit Group Number').size().reset_index(name='Total Para Entries')
# # # #                                 st.write("**Total Para Entries per Audit Group:**"); st.dataframe(paras_per_group, use_container_width=True)
# # # #                                 st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True); st.dataframe(df, use_container_width=True)
# # # #                             except Exception as e:
# # # #                                 st.error(f"Error processing summary: {e}"); st.dataframe(df, use_container_width=True)
# # # #                         else:
# # # #                             st.warning("Missing 'Audit Group Number' column."); st.dataframe(df, use_container_width=True)
# # # #                     else:
# # # #                         st.info(f"No data in spreadsheet for {selected_period_display}.")
# # # #                 elif not sheets_service:
# # # #                     st.error("Google Sheets service not available.")

# # # #     elif selected_tab == "Visualizations":
# # # #         st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
# # # #         all_mcm_periods = mcm_periods
# # # #         if not all_mcm_periods:
# # # #             st.info("No MCM periods to visualize data from.")
# # # #         else:
# # # #             viz_period_options = [
# # # #                 f"{p.get('month_name')} {p.get('year')}"
# # # #                 for k, p in sorted(all_mcm_periods.items(), key=lambda item: item[0], reverse=True)
# # # #                 if p.get('month_name') and p.get('year')
# # # #             ]
# # # #             if not viz_period_options:
# # # #                 st.warning("No valid MCM periods with complete month and year information found for visualization options.")
# # # #             selected_viz_period_display = st.selectbox("Select MCM Period for Visualization",
# # # #                                                        options=viz_period_options, key="pco_viz_period")
# # # #             if selected_viz_period_display and sheets_service:
# # # #                 selected_viz_period_key = next((k for k, p in all_mcm_periods.items() if
# # # #                                 p.get('month_name') and p.get('year') and
# # # #                                 f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_display), None)
# # # #                 if selected_viz_period_key:
# # # #                     sheet_id_viz = all_mcm_periods[selected_viz_period_key]['spreadsheet_id']
# # # #                     with st.spinner("Loading data for visualizations..."):
# # # #                         df_viz = read_from_spreadsheet(sheets_service, sheet_id_viz)

# # # #                     if not df_viz.empty:
# # # #                         amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)',
# # # #                                        'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
# # # #                         for col in amount_cols:
# # # #                             if col in df_viz.columns: df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)
# # # #                         if 'Audit Group Number' in df_viz.columns:
# # # #                             df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)

# # # #                         st.markdown("---")
# # # #                         st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)

# # # #                         if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Audit Group Number' in df_viz.columns:
# # # #                             detection_data = df_viz.groupby('Audit Group Number')['Total Amount Detected (Overall Rs)'].sum().reset_index()
# # # #                             detection_data = detection_data.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
# # # #                             if not detection_data.empty:
# # # #                                 st.write("**Top 5 Groups by Total Detection Amount (Rs):**")
# # # #                                 fig = px.bar(detection_data, x='Audit Group Number', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number': '<b>Audit Group</b>'})
# # # #                                 fig.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis={'categoryorder':'total descending'})
# # # #                                 fig.update_traces(textposition='outside', marker_color='indianred')
# # # #                                 st.plotly_chart(fig, use_container_width=True)
# # # #                             else: st.info("Not enough data for 'Top Detection Groups' chart.")

# # # #                         if 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Audit Group Number' in df_viz.columns:
# # # #                             recovery_data = df_viz.groupby('Audit Group Number')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
# # # #                             recovery_data = recovery_data.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
# # # #                             if not recovery_data.empty:
# # # #                                 st.write("**Top 5 Groups by Total Realisation Amount (Rs):**")
# # # #                                 fig = px.bar(recovery_data, x='Audit Group Number', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number': '<b>Audit Group</b>'})
# # # #                                 fig.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis={'categoryorder':'total descending'})
# # # #                                 fig.update_traces(textposition='outside', marker_color='lightseagreen')
# # # #                                 st.plotly_chart(fig, use_container_width=True)
# # # #                             else: st.info("Not enough data for 'Top Realisation Groups' chart.")

# # # #                         if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Audit Group Number' in df_viz.columns:
# # # #                             group_summary = df_viz.groupby('Audit Group Number').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index()
# # # #                             group_summary['Recovery_Ratio'] = group_summary.apply(lambda row: (row['Total_Recovered'] / row['Total_Detected']) * 100 if pd.notna(row['Total_Detected']) and row['Total_Detected'] > 0 and pd.notna(row['Total_Recovered']) else 0, axis=1)
# # # #                             ratio_data = group_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
# # # #                             if not ratio_data.empty:
# # # #                                 st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**")
# # # #                                 fig = px.bar(ratio_data, x='Audit Group Number', y='Recovery_Ratio', text_auto=True, labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number': '<b>Audit Group</b>'})
# # # #                                 fig.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis={'categoryorder':'total descending'})
# # # #                                 fig.update_traces(textposition='outside', marker_color='mediumpurple')
# # # #                                 st.plotly_chart(fig, use_container_width=True)
# # # #                             else: st.info("Not enough data for 'Top Recovery Ratio Groups' chart.")

# # # #                         st.markdown("---")
# # # #                         st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
# # # #                         num_paras_to_show = st.number_input("Select N for Top N Paras:", min_value=1, max_value=20, value=5, step=1, key="top_n_paras_viz")
# # # #                         df_paras_only = df_viz[df_viz['Audit Para Number'].notna() & (~df_viz['Audit Para Heading'].isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]

# # # #                         if 'Revenue Involved (Lakhs Rs)' in df_paras_only.columns:
# # # #                             top_detection_paras = df_paras_only.nlargest(num_paras_to_show, 'Revenue Involved (Lakhs Rs)')
# # # #                             if not top_detection_paras.empty:
# # # #                                 st.write(f"**Top {num_paras_to_show} Detection Paras (by Revenue Involved):**")
# # # #                                 st.dataframe(top_detection_paras[['Audit Group Number', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)']], use_container_width=True)
# # # #                             else: st.info("Not enough data for 'Top Detection Paras' list.")
# # # #                         if 'Revenue Recovered (Lakhs Rs)' in df_paras_only.columns:
# # # #                             top_recovery_paras = df_paras_only.nlargest(num_paras_to_show, 'Revenue Recovered (Lakhs Rs)')
# # # #                             if not top_recovery_paras.empty:
# # # #                                 st.write(f"**Top {num_paras_to_show} Realisation Paras (by Revenue Recovered):**")
# # # #                                 st.dataframe(top_recovery_paras[['Audit Group Number', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)']], use_container_width=True)
# # # #                             else: st.info("Not enough data for 'Top Realisation Paras' list.")
# # # #                     else:
# # # #                         st.info(f"No data in spreadsheet for {selected_viz_period_display} to visualize.")
# # # #                 elif not sheets_service:
# # # #                     st.error("Google Sheets service not available.")
# # # #     st.markdown("</div>", unsafe_allow_html=True)
