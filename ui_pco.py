# ui_pco.py
import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu

from google_utils import (
    load_mcm_periods, save_mcm_periods, create_drive_folder,
    create_spreadsheet, read_from_spreadsheet
)
from config import USER_CREDENTIALS, MCM_PERIODS_FILENAME_ON_DRIVE

def pco_dashboard(drive_service, sheets_service):
    st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
    mcm_periods = load_mcm_periods(drive_service)

    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Indian_Ministry_of_Finance_logo.svg/1200px-Indian_Ministry_of_Finance_logo.svg.png",
            width=80)
        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        if st.button("Logout", key="pco_logout_styled", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.drive_structure_initialized = False
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
    if selected_tab == "Create MCM Period":
        st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
        current_year = datetime.datetime.now().year
        years = list(range(current_year - 1, current_year + 3))
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                  "November", "December"]
        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year), key="pco_year")
        with col2:
            selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1,
                                               key="pco_month")
        selected_month_num = months.index(selected_month_name) + 1
        period_key = f"{selected_year}-{selected_month_num:02d}"

        if period_key in mcm_periods:
            st.warning(f"MCM Period for {selected_month_name} {selected_year} already exists.")
        else:
            if st.button(f"Create MCM for {selected_month_name} {selected_year}", key="pco_create_mcm",
                         use_container_width=True):
                if not drive_service or not sheets_service or not st.session_state.get('master_drive_folder_id'):
                    st.error("Google Services or Master Drive Folder not available. Cannot create MCM period.")
                else:
                    with st.spinner("Creating Google Drive folder and Spreadsheet..."):
                        master_folder_id = st.session_state.master_drive_folder_id
                        folder_name = f"MCM_DARs_{selected_month_name}_{selected_year}"
                        spreadsheet_title = f"MCM_Audit_Paras_{selected_month_name}_{selected_year}"

                        folder_id, folder_url = create_drive_folder(drive_service, folder_name,
                                                                    parent_id=master_folder_id)
                        sheet_id, sheet_url = create_spreadsheet(sheets_service, drive_service, spreadsheet_title,
                                                                 parent_folder_id=master_folder_id)

                        if folder_id and sheet_id:
                            mcm_periods[period_key] = {
                                "year": selected_year, "month_num": selected_month_num,
                                "month_name": selected_month_name,
                                "drive_folder_id": folder_id, "drive_folder_url": folder_url,
                                "spreadsheet_id": sheet_id, "spreadsheet_url": sheet_url, "active": True
                            }
                            if save_mcm_periods(drive_service, mcm_periods):
                                st.success(
                                    f"Successfully created MCM period for {selected_month_name} {selected_year}!")
                                st.markdown(f"**Drive Folder:** <a href='{folder_url}' target='_blank'>Open Folder</a>",
                                            unsafe_allow_html=True)
                                st.markdown(f"**Spreadsheet:** <a href='{sheet_url}' target='_blank'>Open Sheet</a>",
                                            unsafe_allow_html=True)
                                st.balloons(); time.sleep(0.5); st.rerun()
                            else:
                                st.error("Failed to save MCM period configuration to Drive.")
                        else:
                            st.error("Failed to create Drive folder or Spreadsheet.")

    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        if not mcm_periods:
            st.info("No MCM periods created yet.")
        else:
            sorted_periods_keys = sorted(mcm_periods.keys(), reverse=True)
            for period_key in sorted_periods_keys:
                data = mcm_periods[period_key]
                month_name_display = data.get('month_name', 'Unknown Month')
                year_display = data.get('year', 'Unknown Year')
                st.markdown(f"<h4>{month_name_display} {year_display}</h4>", unsafe_allow_html=True)
                col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
                with col1:
                    st.markdown(f"<a href='{data.get('drive_folder_url', '#')}' target='_blank'>Open Drive Folder</a>",
                                unsafe_allow_html=True)
                with col2:
                    st.markdown(f"<a href='{data.get('spreadsheet_url', '#')}' target='_blank'>Open Spreadsheet</a>",
                                unsafe_allow_html=True)
                with col3:
                    is_active = data.get("active", False)
                    new_status = st.checkbox("Active", value=is_active, key=f"active_{period_key}_styled")
                    if new_status != is_active:
                        mcm_periods[period_key]["active"] = new_status
                        if save_mcm_periods(drive_service, mcm_periods):
                            month_name_succ = data.get('month_name', 'Unknown Period')
                            year_succ = data.get('year', '')
                            st.success(f"Status for {month_name_succ} {year_succ} updated."); st.rerun()
                        else:
                            st.error("Failed to save updated MCM period status to Drive.")
                with col4:
                    if st.button("Delete Period Record", key=f"delete_mcm_{period_key}", type="secondary"):
                        st.session_state.period_to_delete = period_key
                        st.session_state.show_delete_confirm = True; st.rerun()
                st.markdown("---")

            if st.session_state.get('show_delete_confirm', False) and st.session_state.get('period_to_delete'):
                period_key_to_delete = st.session_state.period_to_delete
                period_data_to_delete = mcm_periods.get(period_key_to_delete, {})
                with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
                    st.warning(
                        f"Are you sure you want to delete the MCM period record for **{period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')}** from this application?")
                    st.caption(
                        f"This action only removes the period from the app's tracking (from the `{MCM_PERIODS_FILENAME_ON_DRIVE}` file on Google Drive). It **does NOT delete** the actual Google Drive folder or the Google Spreadsheet.")
                    pco_password_confirm = st.text_input("Enter your PCO password:", type="password",
                                                         key=f"pco_pass_conf_{period_key_to_delete}")
                    c1, c2 = st.columns(2)
                    with c1:
                        submitted_delete = st.form_submit_button("Yes, Delete Record", use_container_width=True)
                    with c2:
                        if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
                            st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
                    if submitted_delete:
                        if pco_password_confirm == USER_CREDENTIALS.get("planning_officer"):
                            del mcm_periods[period_key_to_delete]
                            if save_mcm_periods(drive_service, mcm_periods):
                                st.success(
                                    f"MCM record for {period_data_to_delete.get('month_name')} {period_data_to_delete.get('year')} deleted.");
                            else:
                                st.error("Failed to save changes to Drive after deleting record locally.")
                            st.session_state.show_delete_confirm = False; st.session_state.period_to_delete = None; st.rerun()
                        else:
                            st.error("Incorrect password.")

    elif selected_tab == "View Uploaded Reports":
        st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
        active_periods = {k: v for k, v in mcm_periods.items()}
        if not active_periods:
            st.info("No MCM periods to view reports for.")
        else:
            period_options = [
                 f"{p.get('month_name')} {p.get('year')}"
                 for k, p in sorted(active_periods.items(), key=lambda item: item[0], reverse=True)
                 if p.get('month_name') and p.get('year')
             ]
            if not period_options:
                 st.warning("No valid MCM periods with complete month and year information found to display options.")
            selected_period_display = st.selectbox("Select MCM Period", options=period_options,
                                                   key="pco_view_reports_period")
            if selected_period_display:
                selected_period_key = next((k for k, p in active_periods.items() if
                            p.get('month_name') and p.get('year') and
                            f"{p.get('month_name')} {p.get('year')}" == selected_period_display), None)
                if selected_period_key and sheets_service:
                    sheet_id = mcm_periods[selected_period_key]['spreadsheet_id']
                    with st.spinner("Loading data from Google Sheet..."):
                        df = read_from_spreadsheet(sheets_service, sheet_id)
                    if not df.empty:
                        st.markdown("<h4>Summary of Uploads:</h4>", unsafe_allow_html=True)
                        if 'Audit Group Number' in df.columns:
                            try:
                                df['Audit Group Number'] = pd.to_numeric(df['Audit Group Number'], errors='coerce')
                                df.dropna(subset=['Audit Group Number'], inplace=True)
                                dars_per_group = df.groupby('Audit Group Number')['DAR PDF URL'].nunique().reset_index(name='DARs Uploaded')
                                st.write("**DARs Uploaded per Audit Group:**"); st.dataframe(dars_per_group, use_container_width=True)
                                paras_per_group = df.groupby('Audit Group Number').size().reset_index(name='Total Para Entries')
                                st.write("**Total Para Entries per Audit Group:**"); st.dataframe(paras_per_group, use_container_width=True)
                                st.markdown("<h4>Detailed Data:</h4>", unsafe_allow_html=True); st.dataframe(df, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error processing summary: {e}"); st.dataframe(df, use_container_width=True)
                        else:
                            st.warning("Missing 'Audit Group Number' column."); st.dataframe(df, use_container_width=True)
                    else:
                        st.info(f"No data in spreadsheet for {selected_period_display}.")
                elif not sheets_service:
                    st.error("Google Sheets service not available.")

    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        all_mcm_periods = mcm_periods
        if not all_mcm_periods:
            st.info("No MCM periods to visualize data from.")
        else:
            viz_period_options = [
                f"{p.get('month_name')} {p.get('year')}"
                for k, p in sorted(all_mcm_periods.items(), key=lambda item: item[0], reverse=True)
                if p.get('month_name') and p.get('year')
            ]
            if not viz_period_options:
                st.warning("No valid MCM periods with complete month and year information found for visualization options.")
            selected_viz_period_display = st.selectbox("Select MCM Period for Visualization",
                                                       options=viz_period_options, key="pco_viz_period")
            if selected_viz_period_display and sheets_service:
                selected_viz_period_key = next((k for k, p in all_mcm_periods.items() if
                                p.get('month_name') and p.get('year') and
                                f"{p.get('month_name')} {p.get('year')}" == selected_viz_period_display), None)
                if selected_viz_period_key:
                    sheet_id_viz = all_mcm_periods[selected_viz_period_key]['spreadsheet_id']
                    with st.spinner("Loading data for visualizations..."):
                        df_viz = read_from_spreadsheet(sheets_service, sheet_id_viz)

                    if not df_viz.empty:
                        amount_cols = ['Total Amount Detected (Overall Rs)', 'Total Amount Recovered (Overall Rs)',
                                       'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
                        for col in amount_cols:
                            if col in df_viz.columns: df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)
                        if 'Audit Group Number' in df_viz.columns:
                            df_viz['Audit Group Number'] = pd.to_numeric(df_viz['Audit Group Number'], errors='coerce').fillna(0).astype(int)

                        st.markdown("---")
                        st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)

                        if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Audit Group Number' in df_viz.columns:
                            detection_data = df_viz.groupby('Audit Group Number')['Total Amount Detected (Overall Rs)'].sum().reset_index()
                            detection_data = detection_data.sort_values(by='Total Amount Detected (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Detected (Overall Rs)')
                            if not detection_data.empty:
                                st.write("**Top 5 Groups by Total Detection Amount (Rs):**")
                                fig = px.bar(detection_data, x='Audit Group Number', y='Total Amount Detected (Overall Rs)', text_auto=True, labels={'Total Amount Detected (Overall Rs)': 'Total Detection (Rs)', 'Audit Group Number': '<b>Audit Group</b>'})
                                fig.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis={'categoryorder':'total descending'})
                                fig.update_traces(textposition='outside', marker_color='indianred')
                                st.plotly_chart(fig, use_container_width=True)
                            else: st.info("Not enough data for 'Top Detection Groups' chart.")

                        if 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Audit Group Number' in df_viz.columns:
                            recovery_data = df_viz.groupby('Audit Group Number')['Total Amount Recovered (Overall Rs)'].sum().reset_index()
                            recovery_data = recovery_data.sort_values(by='Total Amount Recovered (Overall Rs)', ascending=False).nlargest(5, 'Total Amount Recovered (Overall Rs)')
                            if not recovery_data.empty:
                                st.write("**Top 5 Groups by Total Realisation Amount (Rs):**")
                                fig = px.bar(recovery_data, x='Audit Group Number', y='Total Amount Recovered (Overall Rs)', text_auto=True, labels={'Total Amount Recovered (Overall Rs)': 'Total Realisation (Rs)', 'Audit Group Number': '<b>Audit Group</b>'})
                                fig.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis={'categoryorder':'total descending'})
                                fig.update_traces(textposition='outside', marker_color='lightseagreen')
                                st.plotly_chart(fig, use_container_width=True)
                            else: st.info("Not enough data for 'Top Realisation Groups' chart.")

                        if 'Total Amount Detected (Overall Rs)' in df_viz.columns and 'Total Amount Recovered (Overall Rs)' in df_viz.columns and 'Audit Group Number' in df_viz.columns:
                            group_summary = df_viz.groupby('Audit Group Number').agg(Total_Detected=('Total Amount Detected (Overall Rs)', 'sum'), Total_Recovered=('Total Amount Recovered (Overall Rs)', 'sum')).reset_index()
                            group_summary['Recovery_Ratio'] = group_summary.apply(lambda row: (row['Total_Recovered'] / row['Total_Detected']) * 100 if pd.notna(row['Total_Detected']) and row['Total_Detected'] > 0 and pd.notna(row['Total_Recovered']) else 0, axis=1)
                            ratio_data = group_summary.sort_values(by='Recovery_Ratio', ascending=False).nlargest(5, 'Recovery_Ratio')
                            if not ratio_data.empty:
                                st.write("**Top 5 Groups by Recovery/Detection Ratio (%):**")
                                fig = px.bar(ratio_data, x='Audit Group Number', y='Recovery_Ratio', text_auto=True, labels={'Recovery_Ratio': 'Recovery Ratio (%)', 'Audit Group Number': '<b>Audit Group</b>'})
                                fig.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis={'categoryorder':'total descending'})
                                fig.update_traces(textposition='outside', marker_color='mediumpurple')
                                st.plotly_chart(fig, use_container_width=True)
                            else: st.info("Not enough data for 'Top Recovery Ratio Groups' chart.")

                        st.markdown("---")
                        st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
                        num_paras_to_show = st.number_input("Select N for Top N Paras:", min_value=1, max_value=20, value=5, step=1, key="top_n_paras_viz")
                        df_paras_only = df_viz[df_viz['Audit Para Number'].notna() & (~df_viz['Audit Para Heading'].isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]

                        if 'Revenue Involved (Lakhs Rs)' in df_paras_only.columns:
                            top_detection_paras = df_paras_only.nlargest(num_paras_to_show, 'Revenue Involved (Lakhs Rs)')
                            if not top_detection_paras.empty:
                                st.write(f"**Top {num_paras_to_show} Detection Paras (by Revenue Involved):**")
                                st.dataframe(top_detection_paras[['Audit Group Number', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Involved (Lakhs Rs)']], use_container_width=True)
                            else: st.info("Not enough data for 'Top Detection Paras' list.")
                        if 'Revenue Recovered (Lakhs Rs)' in df_paras_only.columns:
                            top_recovery_paras = df_paras_only.nlargest(num_paras_to_show, 'Revenue Recovered (Lakhs Rs)')
                            if not top_recovery_paras.empty:
                                st.write(f"**Top {num_paras_to_show} Realisation Paras (by Revenue Recovered):**")
                                st.dataframe(top_recovery_paras[['Audit Group Number', 'Trade Name', 'Audit Para Number', 'Audit Para Heading', 'Revenue Recovered (Lakhs Rs)']], use_container_width=True)
                            else: st.info("Not enough data for 'Top Realisation Paras' list.")
                    else:
                        st.info(f"No data in spreadsheet for {selected_viz_period_display} to visualize.")
                elif not sheets_service:
                    st.error("Google Sheets service not available.")
    st.markdown("</div>", unsafe_allow_html=True)