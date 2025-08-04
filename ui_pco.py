import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
import json
import numpy as np
# Dropbox-based imports
from dropbox_utils import read_from_spreadsheet, update_spreadsheet_from_df
from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH,USER_CREDENTIALS

# Import tab modules
from ui_mcm_agenda import mcm_agenda_tab
from ui_pco_reports import pco_reports_dashboard

def pco_dashboard(dbx):
    st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)

    with st.sidebar:
        try:
            st.image("logo.png", width=80)
        except Exception:
            st.sidebar.markdown("*(Logo)*")
        
        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        
        if st.button("Logout", key="pco_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            # Clear session state keys
            keys_to_clear = ['period_to_delete', 'show_delete_confirm', 'num_paras_to_show_pco']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        # Smart Audit Tracker Button with styling
        st.markdown("""
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
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Smart Audit Tracker", key="launch_sat_pco"):
            st.session_state.app_mode = "smart_audit_tracker"
            st.rerun()
        st.markdown("---")
    
    # Navigation menu
    selected_tab = option_menu(
        menu_title=None,
        options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "MCM Agenda", "Visualizations", "Reports"],
        icons=["calendar-plus-fill", "sliders", "eye-fill", "journal-richtext", "bar-chart-fill", "file-earmark-text-fill"],
        menu_icon="gear-wide-connected",
        default_index=0,
        orientation="horizontal",
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
        
        with st.form("create_period_form"):
            current_year = datetime.datetime.now().year
            years = list(range(current_year - 1, current_year + 3))
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            
            col1, col2 = st.columns(2)
            selected_year = col1.selectbox("Select Year", options=years, index=years.index(current_year))
            selected_month = col2.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1)
            
            submitted = st.form_submit_button(f"Create MCM for {selected_month} {selected_year}", use_container_width=True)
            
            if submitted:
                df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
                if df_periods is None:
                    df_periods = pd.DataFrame()
                
                period_key = f"{selected_month}_{selected_year}"
                
                # --- FIX: Check if 'key' column exists before accessing it ---
                if not df_periods.empty and 'key' in df_periods.columns and period_key in df_periods['key'].values:
                    st.warning(f"MCM Period for {selected_month} {selected_year} already exists.")
                else:
                    new_period = pd.DataFrame([{
                        "month_name": selected_month, 
                        "year": selected_year, 
                        "active": True, 
                        "key": period_key,
                        "overall_remarks": "" 
                    }])

                    if 'overall_remarks' not in df_periods.columns and not df_periods.empty:
                        df_periods['overall_remarks'] = ""
                    
                    # Ensure all columns from the new period are in the old one before concat
                    for col in new_period.columns:
                        if col not in df_periods.columns:
                            df_periods[col] = pd.NA

                    updated_df = pd.concat([df_periods, new_period], ignore_index=True)
                    
                    if update_spreadsheet_from_df(dbx, updated_df, MCM_PERIODS_INFO_PATH):
                        st.success(f"Successfully created and activated MCM period for {selected_month} {selected_year}!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to save the new MCM period to Dropbox.")
   

    # # ========================== MANAGE MCM PERIODS TAB ==========================
    # elif selected_tab == "Manage MCM Periods":
    #     st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
    #     st.markdown("<h4 style='color: red;'>Please Note: Deleting records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
    #     st.markdown("<h5 style='color: green;'>Only the months marked as 'Active' by Planning officer will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
    #     st.info("You can activate/deactivate periods or delete them using the editor. Changes are saved automatically.", icon="ℹ️")
        
    #     df_periods_manage = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        
    #     if df_periods_manage is None or df_periods_manage.empty:
    #         st.info("No MCM periods have been created yet.")
    #     else:
    #         edited_df = st.data_editor(
    #             df_periods_manage,
    #             column_config={
    #                 "month_name": st.column_config.TextColumn("Month", disabled=True),
    #                 "year": st.column_config.NumberColumn("Year", disabled=True),
    #                 "active": st.column_config.CheckboxColumn("Active?", default=False),
    #                 "key": None  # Hide the key column
    #             },
    #             use_container_width=True,
    #             hide_index=True,
    #             num_rows="dynamic",
    #             key="manage_periods_editor"
    #         )
            
    #         if not df_periods_manage.equals(edited_df):
    #             if update_spreadsheet_from_df(dbx, edited_df, MCM_PERIODS_INFO_PATH):
    #                 st.toast("Changes saved successfully!")
    #                 time.sleep(1)
    #                 st.rerun()
    #             else:
    #                 st.error("Failed to save changes to Dropbox.")

    #     # Handle deletion with confirmation (similar to original Google version)
    #     if st.session_state.get('show_delete_confirm') and st.session_state.get('period_to_delete'):
    #         period_key_to_delete = st.session_state.period_to_delete
    #         with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
    #             st.warning(f"Are you sure you want to delete the MCM period: **{period_key_to_delete}**?")
    #             st.error("**Warning:** This will remove the period from tracking. Use cautiously.")
                
    #             pco_password_confirm = st.text_input("Enter your PCO password:", type="password")
    #             form_c1, form_c2 = st.columns(2)
                
    #             with form_c1:
    #                 submitted_delete = st.form_submit_button("Yes, Delete Record", use_container_width=True)
    #             with form_c2:
    #                 if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
    #                     st.session_state.show_delete_confirm = False
    #                     st.session_state.period_to_delete = None
    #                     st.rerun()
                
    #             if submitted_delete:
    #                 # Here you would validate the password against your user credentials
    #                 # For now, we'll skip password validation as it depends on your config
    #                 if pco_password_confirm:  # Replace with actual password validation
    #                     # Remove the period from the dataframe
    #                     df_updated = df_periods_manage[df_periods_manage['key'] != period_key_to_delete]
    #                     if update_spreadsheet_from_df(dbx, df_updated, MCM_PERIODS_INFO_PATH):
    #                         st.success(f"MCM period {period_key_to_delete} deleted successfully.")
    #                     else:
    #                         st.error("Failed to delete the period.")
    #                     st.session_state.show_delete_confirm = False
    #                     st.session_state.period_to_delete = None
    #                     st.rerun()
    #                 else:
    #                     st.error("Please enter your password to confirm deletion.")
    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: red;'>Please Note: Deleting records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: green;'>Only the months marked as 'Active' by Planning officer will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
        st.info("You can activate/deactivate periods or delete them using the editor. Changes are saved automatically.", icon="ℹ️")
        
        df_periods_manage = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        
        if df_periods_manage is None or df_periods_manage.empty:
            st.info("No MCM periods have been created yet.")
        else:
            edited_df = st.data_editor(
                df_periods_manage,
                column_config={
                    "month_name": st.column_config.TextColumn("Month", disabled=True),
                    "year": st.column_config.NumberColumn("Year", disabled=True),
                    "active": st.column_config.CheckboxColumn("Active?", default=False),
                    "key": None  # Hide the key column
                },
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="manage_periods_editor"
            )
            
            if not df_periods_manage.equals(edited_df):
                if update_spreadsheet_from_df(dbx, edited_df, MCM_PERIODS_INFO_PATH):
                    st.toast("Changes saved successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to save changes to Dropbox.")
    
            # ========================== DELETE MCM PERIODS SECTION ==========================
            st.markdown("---")
            st.markdown("<h3>Delete MCM Periods</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: #d32f2f; font-weight: bold;'>⚠️ Warning: Deleting a period will permanently remove all associated data including DARs and audit reports.</p>", unsafe_allow_html=True)
            
            # Custom CSS for the delete section
            st.markdown("""
            <style>
            .delete-period-card {
                background: linear-gradient(135deg, #fff 0%, #f8f9fa 100%);
                border: 1px solid #e9ecef;
                border-radius: 12px;
                padding: 20px;
                margin: 10px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
            }
            .delete-period-card:hover {
                box-shadow: 0 4px 16px rgba(0,0,0,0.15);
                transform: translateY(-2px);
            }
            .period-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            .period-title {
                font-size: 1.2em;
                font-weight: bold;
                color: #2c3e50;
                margin: 0;
            }
            .period-status {
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: bold;
                text-transform: uppercase;
            }
            .status-active {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .status-inactive {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .period-details {
                color: #6c757d;
                font-size: 0.9em;
                margin-bottom: 15px;
            }
            .delete-btn-container {
                text-align: right;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Display all periods with delete buttons
            for index, row in df_periods_manage.iterrows():
                period_key = row['key']
                month_name = row['month_name']
                year = row['year']
                is_active = row.get('active', False)
                
                # Create the period card
                status_class = "status-active" if is_active else "status-inactive"
                status_text = "Active" if is_active else "Inactive"
                
                st.markdown(f"""
                <div class="delete-period-card">
                    <div class="period-info">
                        <h4 class="period-title">📅 {month_name} {year}</h4>
                        <span class="period-status {status_class}">{status_text}</span>
                    </div>
                    <div class="period-details">
                        <strong>Period Key:</strong> {period_key}<br>
                        <strong>Status:</strong> {"Available for DAR uploads" if is_active else "Not available for uploads"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add delete button for each period
                col1, col2, col3 = st.columns([1, 1, 1])
                with col3:
                    if st.button(f"🗑️ Delete {month_name} {year}", 
                                key=f"delete_period_{period_key}",
                                type="secondary",
                                use_container_width=True):
                        st.session_state.period_to_delete = period_key
                        st.session_state.show_delete_confirm = True
                        st.rerun()
    
            # Handle deletion confirmation
            if st.session_state.get('show_delete_confirm') and st.session_state.get('period_to_delete'):
                period_key_to_delete = st.session_state.period_to_delete
                
                # Find the period details for display
                period_row = df_periods_manage[df_periods_manage['key'] == period_key_to_delete]
                if not period_row.empty:
                    period_display = f"{period_row.iloc[0]['month_name']} {period_row.iloc[0]['year']}"
                else:
                    period_display = period_key_to_delete
                
                # Confirmation dialog styling
                st.markdown("""
                <style>
                .delete-confirmation {
                    background: linear-gradient(135deg, #ffe6e6 0%, #ffcccc 100%);
                    border: 2px solid #ff4444;
                    border-radius: 15px;
                    padding: 25px;
                    margin: 20px 0;
                    box-shadow: 0 4px 12px rgba(255, 68, 68, 0.3);
                }
                .confirmation-title {
                    color: #d32f2f;
                    font-size: 1.3em;
                    font-weight: bold;
                    margin-bottom: 15px;
                    text-align: center;
                }
                .confirmation-warning {
                    background-color: #fff;
                    border-left: 4px solid #ff4444;
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 5px;
                }
                </style>
                """, unsafe_allow_html=True)
                
                st.markdown('<div class="delete-confirmation">', unsafe_allow_html=True)
                st.markdown(f'<div class="confirmation-title">🚨 Confirm Deletion</div>', unsafe_allow_html=True)
                
                with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
                    st.markdown(f"""
                    <div class="confirmation-warning">
                        <strong>⚠️ You are about to delete the MCM period: "{period_display}"</strong><br><br>
                        This action will permanently remove:
                        <ul>
                            <li>✗ All DAR PDF files uploaded for this period</li>
                            <li>✗ All audit para data and spreadsheet entries</li>
                            <li>✗ All associated reports and analytics</li>
                            <li>✗ The period tracking record</li>
                        </ul>
                        <strong style="color: #d32f2f;">This action cannot be undone!</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    pco_password_confirm = st.text_input(
                        "🔐 Enter your PCO password to confirm deletion:", 
                        type="password",
                        help="This is required for security verification"
                    )
                    
                    form_c1, form_c2 = st.columns(2)
                    
                    with form_c1:
                        submitted_delete = st.form_submit_button(
                            "🗑️ Yes, Delete Permanently", 
                            type="primary",
                            use_container_width=True
                        )
                    with form_c2:
                        cancel_delete = st.form_submit_button(
                            "❌ Cancel", 
                            type="secondary", 
                            use_container_width=True
                        )
                    
                    if cancel_delete:
                        st.session_state.show_delete_confirm = False
                        st.session_state.period_to_delete = None
                        st.rerun()
                    
                    if submitted_delete:
                        # Validate password (replace with actual password validation)
                        if pco_password_confirm == USER_CREDENTIALS.get("planning_officer", ""):
                            # Remove the period from the dataframe
                            df_updated = df_periods_manage[df_periods_manage['key'] != period_key_to_delete]
                            
                            if update_spreadsheet_from_df(dbx, df_updated, MCM_PERIODS_INFO_PATH):
                                st.success(f"✅ MCM period '{period_display}' deleted successfully!")
                                st.balloons()
                                
                                # Clear session state
                                st.session_state.show_delete_confirm = False
                                st.session_state.period_to_delete = None
                                
                                # Wait and reload
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete the period from Dropbox.")
                        else:
                            st.error("🔒 Incorrect password. Please try again.")
                
                st.markdown('</div>', unsafe_allow_html=True)

    # ========================== VIEW UPLOADED REPORTS TAB ==========================
    elif selected_tab == "View Uploaded Reports":
        st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
        
        df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        if df_periods is None or df_periods.empty:
            st.info("No MCM periods exist. Please create one first.")
            return

        period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
        selected_period = st.selectbox("Select MCM Period to View", options=period_options)

        if not selected_period:
            return

        with st.spinner("Loading all report data..."):
            df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)

        if df_all_data is None or df_all_data.empty:
            st.info("No DARs have been submitted by any group yet.")
            return

        df_filtered = df_all_data[df_all_data['mcm_period'] == selected_period].copy()

        if df_filtered.empty:
            st.info(f"No data found for the period: {selected_period}")
            return

        # Summary section
        st.markdown("#### Summary of Uploads")
        df_filtered['audit_group_number'] = pd.to_numeric(df_filtered['audit_group_number'], errors='coerce')
        df_filtered['audit_circle_number'] = pd.to_numeric(df_filtered['audit_circle_number'], errors='coerce')
        
        # Table 1: DARs & Audit Paras per Group (FULL WIDTH)
        st.markdown("**DARs & Audit Paras Uploaded per Group:**")
        dars_per_group = df_filtered.groupby('audit_group_number')['dar_pdf_path'].nunique().reset_index(name='DARs Uploaded')
        paras_per_group = df_filtered.groupby('audit_group_number').size().reset_index(name='Audit Paras')
        
        # Merge the two dataframes
        group_summary = pd.merge(dars_per_group, paras_per_group, on='audit_group_number', how='outer').fillna(0)
        group_summary['DARs Uploaded'] = group_summary['DARs Uploaded'].astype(int)
        group_summary['Audit Paras'] = group_summary['Audit Paras'].astype(int)
        group_summary['audit_group_number'] = group_summary['audit_group_number'].astype(int)
        group_summary = group_summary.rename(columns={'audit_group_number': 'Audit Group Number'})
        
        st.dataframe(group_summary, use_container_width=True, hide_index=True)
        
        # Add spacing
        st.markdown("---")
        
        # Table 2: DARs & Audit Paras per Circle (FULL WIDTH)
        st.markdown("**DARs & Audit Paras Uploaded per Circle:**")
        if 'audit_circle_number' in df_filtered.columns:
            df_circle_data = df_filtered.dropna(subset=['audit_circle_number'])
            if not df_circle_data.empty:
                dars_per_circle = df_circle_data.groupby('audit_circle_number')['dar_pdf_path'].nunique().reset_index(name='DARs Uploaded')
                paras_per_circle = df_circle_data.groupby('audit_circle_number').size().reset_index(name='Audit Paras')
                
                # Merge the two dataframes
                circle_summary = pd.merge(dars_per_circle, paras_per_circle, on='audit_circle_number', how='outer').fillna(0)
                circle_summary['DARs Uploaded'] = circle_summary['DARs Uploaded'].astype(int)
                circle_summary['Audit Paras'] = circle_summary['Audit Paras'].astype(int)
                circle_summary['audit_circle_number'] = circle_summary['audit_circle_number'].astype(int)
                circle_summary = circle_summary.rename(columns={'audit_circle_number': 'Audit Circle Number'})
                
                st.dataframe(circle_summary, use_container_width=True, hide_index=True)
            else:
                st.info("No circle data available for this period")
        else:
            st.info("Circle information not available in the data")
        
        # Add spacing
        st.markdown("---")
        
        # Table 3: Para Status Summary (FULL WIDTH)
        st.markdown("**Para Status Summary:**")
        if 'status_of_para' in df_filtered.columns:
            status_summary = df_filtered['status_of_para'].value_counts().reset_index(name='Count')
            status_summary.columns = ['Status of Para', 'Count']
            st.dataframe(status_summary, use_container_width=True, hide_index=True)
        else:
            st.info("Para status information not available in the data")

        st.markdown("<hr>")
        st.markdown(f"#### Edit Detailed Data for {selected_period}")
        st.info("You can edit data below. Click 'Save Changes' to update the master file.", icon="✍️")

        edited_df = st.data_editor(
            df_filtered, 
            use_container_width=True, 
            hide_index=True, 
            num_rows="dynamic", 
            key=f"pco_editor_{selected_period}"
        )

        if st.button("Save Changes to Master File", type="primary"):
            with st.spinner("Saving changes to Dropbox..."):
                # Update the master dataframe with edited rows
                df_all_data.update(edited_df)
                if update_spreadsheet_from_df(dbx, df_all_data, MCM_DATA_PATH):
                    st.success("Changes saved successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to save changes.")

    # ========================== MCM AGENDA TAB ==========================
    elif selected_tab == "MCM Agenda":
        mcm_agenda_tab(dbx)
  
    # ========================== VISUALIZATIONS TAB ==========================
    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        
        # --- 1. Load Prerequisite Data ---
        df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        if df_periods is None or df_periods.empty:
            st.info("No MCM periods exist to visualize.")
            return
            
        period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
        selected_period = st.selectbox("Select MCM Period for Visualization", options=period_options, key="pco_viz_selectbox_final_v4")
    
        if not selected_period:
            return
    
        # --- 2. Load and Filter Core Visualization Data ---
        with st.spinner("Loading data for visualizations..."):
            df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            if df_viz_data is None or df_viz_data.empty:
                st.info("No data available to visualize.")
                return
            df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
    
        if df_viz_data.empty:
            st.info(f"No data to visualize for {selected_period}.")
            return
    
        # --- Data Cleaning and Preparation (Consolidated) ---
        amount_cols = [
            'total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs',
            'revenue_involved_rs', 'revenue_recovered_rs'
        ]
        for col in amount_cols:
            if col in df_viz_data.columns:
                df_viz_data[col] = pd.to_numeric(df_viz_data[col], errors='coerce').fillna(0)
    
        df_viz_data['Detection in Lakhs'] = df_viz_data.get('total_amount_detected_overall_rs', 0) / 100000.0
        df_viz_data['Recovery in Lakhs'] = df_viz_data.get('total_amount_recovered_overall_rs', 0) / 100000.0
        df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
        df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        
        df_viz_data['audit_group_number'] = pd.to_numeric(df_viz_data.get('audit_group_number'), errors='coerce').fillna(0).astype(int)
        df_viz_data['audit_circle_number'] = pd.to_numeric(df_viz_data.get('audit_circle_number'), errors='coerce').fillna(0).astype(int)
        df_viz_data['audit_group_number_str'] = df_viz_data['audit_group_number'].astype(str)
        df_viz_data['circle_number_str'] = df_viz_data['audit_circle_number'].astype(str)
        
        df_viz_data['category'] = df_viz_data.get('category', 'Unknown').fillna('Unknown')
        df_viz_data['trade_name'] = df_viz_data.get('trade_name', 'Unknown Trade Name').fillna('Unknown Trade Name')
        df_viz_data['taxpayer_classification'] = df_viz_data.get('taxpayer_classification', 'Unknown').fillna('Unknown')
        df_viz_data['para_classification_code'] = df_viz_data.get('para_classification_code', 'UNCLASSIFIED').fillna('UNCLASSIFIED')

        # Unique reports for DAR-level analysis
        if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
            df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
        else:
            df_unique_reports = df_viz_data.drop_duplicates(subset=['gstin']).copy()
    
    
        # --- 4. Monthly Performance Summary Metrics ---
        st.markdown("#### Monthly Performance Summary")
        num_dars = df_unique_reports['dar_pdf_path'].nunique()
        total_detected = df_unique_reports.get('Detection in Lakhs', 0).sum()
        total_recovered = df_unique_reports.get('Recovery in Lakhs', 0).sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric(label="✅ DARs Submitted", value=f"{num_dars}")
        col2.metric(label="💰 Revenue Involved", value=f"₹{total_detected:.2f} L")
        col3.metric(label="🏆 Revenue Recovered", value=f"₹{total_recovered:.2f} L")

        # --- This block prepares the data for the table ---
        categories_order = ['Large', 'Medium', 'Small']
        dar_summary = df_unique_reports.groupby('category').agg(
            dars_submitted=('dar_pdf_path', 'nunique'),
            total_detected=('Detection in Lakhs', 'sum'),
            total_recovered=('Recovery in Lakhs', 'sum')
        )
        df_actual_paras = df_viz_data[df_viz_data['audit_para_number'].notna() & (~df_viz_data['audit_para_heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
        para_summary = df_actual_paras.groupby('category').size().reset_index(name='num_audit_paras').set_index('category')
        summary_df = pd.concat([dar_summary, para_summary], axis=1).reindex(categories_order).fillna(0)
        summary_df.reset_index(inplace=True)
        total_row = {
            'category': '🏆 Total (All)',
            'dars_submitted': summary_df['dars_submitted'].sum(),
            'num_audit_paras': summary_df['num_audit_paras'].sum(),
            'total_detected': summary_df['total_detected'].sum(),
            'total_recovered': summary_df['total_recovered'].sum()
        }
        summary_df = pd.concat([summary_df, pd.DataFrame([total_row])], ignore_index=True)
        
        # Format the dataframe for display
        display_df = summary_df.copy()
        display_df.rename(columns={
            'category': 'CATEGORY',
            'dars_submitted': 'NO. OF DARS',
            'num_audit_paras': 'NO. OF AUDIT PARAS',
            'total_detected': 'TOTAL DETECTED',
            'total_recovered': 'TOTAL RECOVERED'
        }, inplace=True)
        
        # Convert to integers and format currency
        display_df['NO. OF DARS'] = display_df['NO. OF DARS'].astype(int)
        display_df['NO. OF AUDIT PARAS'] = display_df['NO. OF AUDIT PARAS'].astype(int)
        display_df['TOTAL DETECTED'] = display_df['TOTAL DETECTED'].apply(lambda x: f"₹{x:,.2f} L")
        display_df['TOTAL RECOVERED'] = display_df['TOTAL RECOVERED'].apply(lambda x: f"₹{x:,.2f} L")
        
        # Add colorful styling for st.table
        st.markdown("""
        <style>
        /* Style for st.table */
        .stTable {
            border: 4px solid;
            border-image: linear-gradient(45deg, #FF6B6B, #4ECDC4, #45B7D1, #96CEB4, #FFEAA7, #DDA0DD) 1;
            border-radius: 15px !important;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            margin: 20px 0;
        }
        
        .stTable > div {
            border-radius: 15px;
            overflow: hidden;
        }
        
        /* Header styling */
        .stTable table thead th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%) !important;
            color: white !important;
            font-weight: 900 !important;
            font-size: 14px !important;
            text-align: center !important;
            padding: 15px 10px !important;
            border: none !important;
            text-transform: uppercase !important;
            letter-spacing: 1px !important;
            text-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
        }
        
        /* Body cell styling */
        .stTable table tbody td {
            font-weight: 700 !important;
            font-size: 13px !important;
            padding: 12px 10px !important;
            text-align: center !important;
            border-bottom: 2px solid #f0f2f6 !important;
        }
        
        /* Alternating row colors */
        .stTable table tbody tr:nth-child(odd) {
            background: linear-gradient(135deg, #f8f9ff 0%, #fff5f5 100%) !important;
        }
        
        .stTable table tbody tr:nth-child(even) {
            background: linear-gradient(135deg, #fff8e1 0%, #f0f8ff 100%) !important;
        }
        
        /* Special styling for Total row */
        .stTable table tbody tr:last-child {
            background: linear-gradient(135deg, #e8f5e8 0%, #fff3cd 50%, #f8d7da 100%) !important;
            border-top: 3px solid #667eea !important;
            font-weight: 900 !important;
        }
        
        .stTable table tbody tr:last-child td {
            font-weight: 900 !important;
            font-size: 14px !important;
            color: #1a237e !important;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
        }
        
        /* Hover effect */
        .stTable table tbody tr:hover {
            background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 50%, #fff3e0 100%) !important;
            transform: scale(1.02);
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        /* Number cells - right align and bold */
        .stTable table tbody td:nth-child(2),
        .stTable table tbody td:nth-child(3),
        .stTable table tbody td:nth-child(4),
        .stTable table tbody td:nth-child(5) {
            text-align: right !important;
            font-family: 'Courier New', monospace !important;
            font-weight: 800 !important;
            color: #2c3e50 !important;
        }
        
        /* Category column - left align */
        .stTable table tbody td:nth-child(1) {
            text-align: left !important;
            font-weight: 800 !important;
            color: #34495e !important;
        }
        
        /* Add some animation */
        .stTable table {
            animation: slideIn 0.5s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display the beautiful Streamlit table
        st.markdown("#### 🎯 **Performance Summary Table**")
        st.table(display_df)
        
        # --- Status of Para Analysis ---
        st.markdown("---")
        st.markdown("<h4>📊 Status of Para Analysis</h4>", unsafe_allow_html=True)
        
        # Check if status_of_para column exists
        if 'status_of_para' not in df_viz_data.columns:
            st.warning("Column 'status_of_para' not found in the dataset. Skipping Status of Para Analysis.")
        else:
            # Filter out records without para status
            df_status_analysis = df_viz_data[
                df_viz_data['status_of_para'].notna() & 
                (df_viz_data['status_of_para'] != '') &
                df_viz_data['audit_para_number'].notna()
            ].copy()
            
            if df_status_analysis.empty:
                st.info("No audit paras with status information found for this period.")
            else:
                # Aggregate data by status
                status_agg = df_status_analysis.groupby('status_of_para').agg(
                    Para_Count=('status_of_para', 'count'),
                    Total_Detection=('Para Detection in Lakhs', 'sum'),
                    Total_Recovery=('Para Recovery in Lakhs', 'sum')
                ).reset_index()
                
                # Sort by para count for better visualization
                status_agg_sorted_count = status_agg.sort_values('Para_Count', ascending=False)
                status_agg_sorted_detection = status_agg.sort_values('Total_Detection', ascending=False)
                
                # Create two columns for side-by-side charts
                col1, col2 = st.columns(2)
                
                with col1:
                    # Chart 1: Number of Audit Paras vs Status
                    fig_status_count = px.bar(
                        status_agg_sorted_count,
                        x='status_of_para',
                        y='Para_Count',
                        title="Number of Audit Paras by Status",
                        text_auto=True,
                        color_discrete_sequence=px.colors.qualitative.Set3,
                        labels={
                            'status_of_para': 'Status of Para',
                            'Para_Count': 'Number of Paras'
                        }
                    )
                    fig_status_count.update_layout(
                        title_x=0.5,
                        height=450,
                        xaxis_title="Status of Para",
                        yaxis_title="Number of Paras",
                        xaxis={'tickangle': 45}
                    )
                    fig_status_count.update_traces(textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig_status_count, use_container_width=True)
                
                with col2:
                    # Chart 2: Detection Amount vs Status
                    fig_status_detection = px.bar(
                        status_agg_sorted_detection,
                        x='status_of_para',
                        y='Total_Detection',
                        title="Detection Amount by Status",
                        text_auto='.2f',
                        color_discrete_sequence=px.colors.qualitative.Pastel1,
                        labels={
                            'status_of_para': 'Status of Para',
                            'Total_Detection': 'Detection Amount (₹ Lakhs)'
                        }
                    )
                    fig_status_detection.update_layout(
                        title_x=0.5,
                        height=450,
                        xaxis_title="Status of Para",
                        yaxis_title="Detection Amount (₹ Lakhs)",
                        xaxis={'tickangle': 45}
                    )
                    fig_status_detection.update_traces(textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig_status_detection, use_container_width=True)
                
                # Summary table for status analysis
                st.markdown("#### 📋 Status Summary Table")
                
                # Format the status summary table
                display_status_agg = status_agg.copy()
                display_status_agg = display_status_agg.rename(columns={
                    'status_of_para': 'STATUS OF PARA',
                    'Para_Count': 'NO. OF PARAS',
                    'Total_Detection': 'TOTAL DETECTION (₹ L)',
                    'Total_Recovery': 'TOTAL RECOVERY (₹ L)'
                })
                
                # Calculate recovery percentage
                display_status_agg['RECOVERY %'] = (
                    display_status_agg['TOTAL RECOVERY (₹ L)'] / 
                    display_status_agg['TOTAL DETECTION (₹ L)'].replace(0, np.nan)
                ).fillna(0) * 100
                
                # Format currency and percentage columns
                display_status_agg['TOTAL DETECTION (₹ L)'] = display_status_agg['TOTAL DETECTION (₹ L)'].apply(lambda x: f"₹{x:,.2f} L")
                display_status_agg['TOTAL RECOVERY (₹ L)'] = display_status_agg['TOTAL RECOVERY (₹ L)'].apply(lambda x: f"₹{x:,.2f} L")
                display_status_agg['RECOVERY %'] = display_status_agg['RECOVERY %'].apply(lambda x: f"{x:.1f}%")
                
                # Sort by number of paras descending
                display_status_agg = display_status_agg.sort_values('NO. OF PARAS', ascending=False)
                
                st.table(display_status_agg)
                
                # Top 5 Paras with largest detection amount under "Agreed yet to pay" status
                st.markdown("---")
                st.markdown("#### 🎯 Top 5 Paras with Largest Detection - Status: 'Agreed yet to pay'")
                
                # Filter for "Agreed yet to pay" status (case insensitive search)
                agreed_yet_to_pay_paras = df_status_analysis[
                    df_status_analysis['status_of_para'].str.contains('Agreed yet to pay', case=False, na=False)
                ].copy()
                
                if agreed_yet_to_pay_paras.empty:
                    # Try alternative search terms
                    agreed_yet_to_pay_paras = df_status_analysis[
                        df_status_analysis['status_of_para'].str.contains('agreed.*pay|yet.*pay|pending.*payment', case=False, na=False)
                    ].copy()
                
                if agreed_yet_to_pay_paras.empty:
                    st.info("No audit paras found with status 'Agreed yet to pay' or similar.")
                    st.write("**Available status values:**")
                    unique_statuses = df_status_analysis['status_of_para'].unique()
                    for status in sorted(unique_statuses):
                        st.write(f"- {status}")
                else:
                    # Get top 5 by detection amount
                    top_5_agreed = agreed_yet_to_pay_paras.nlargest(5, 'Para Detection in Lakhs')
                    
                    # Prepare display columns
                    display_columns = [
                        'audit_group_number_str', 'trade_name', 'gstin', 
                        'audit_para_number', 'audit_para_heading', 
                        'Para Detection in Lakhs', 'Para Recovery in Lakhs', 'status_of_para'
                    ]
                    
                    # Filter columns that exist in the dataframe
                    available_columns = [col for col in display_columns if col in top_5_agreed.columns]
                    
                    # Create a clean display dataframe
                    display_top_5 = top_5_agreed[available_columns].copy()
                    
                    # Rename columns for better display
                    column_rename_map = {
                        'audit_group_number_str': 'Audit Group',
                        'trade_name': 'Trade Name',
                        'gstin': 'GSTIN',
                        'audit_para_number': 'Para No.',
                        'audit_para_heading': 'Para Heading',
                        'Para Detection in Lakhs': 'Detection (₹ L)',
                        'Para Recovery in Lakhs': 'Recovery (₹ L)',
                        'status_of_para': 'Status'
                    }
                    
                    for old_col, new_col in column_rename_map.items():
                        if old_col in display_top_5.columns:
                            display_top_5 = display_top_5.rename(columns={old_col: new_col})
                    
                    # Format currency columns
                    if 'Detection (₹ L)' in display_top_5.columns:
                        display_top_5['Detection (₹ L)'] = display_top_5['Detection (₹ L)'].apply(lambda x: f"₹{x:,.2f} L")
                    if 'Recovery (₹ L)' in display_top_5.columns:
                        display_top_5['Recovery (₹ L)'] = display_top_5['Recovery (₹ L)'].apply(lambda x: f"₹{x:,.2f} L")
                    
                    # Display the table
                    st.dataframe(display_top_5, use_container_width=True, hide_index=True)
                    
                    # Summary metrics for "Agreed yet to pay"
                    total_agreed_paras = len(agreed_yet_to_pay_paras)
                    total_agreed_detection = agreed_yet_to_pay_paras['Para Detection in Lakhs'].sum()
                    total_agreed_recovery = agreed_yet_to_pay_paras['Para Recovery in Lakhs'].sum()
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total 'Agreed yet to pay' Paras", f"{total_agreed_paras}")
                    col2.metric("Total Detection Amount", f"₹{total_agreed_detection:,.2f} L")
                    col3.metric("Total Recovery Amount", f"₹{total_agreed_recovery:,.2f}L")
        # --- 5. Group & Circle Performance Bar Charts ---
        st.markdown("---")
        st.markdown("<h4>Group & Circle Performance</h4>", unsafe_allow_html=True)
        
        def style_chart(fig, title_text, y_title, x_title):
            fig.update_layout(
                title_text=f"<b>{title_text}</b>", title_x=0.5,
                yaxis_title=f"<b>{y_title}</b>", xaxis_title=f"<b>{x_title}</b>",
                font=dict(family="sans-serif", color="#333"),
                paper_bgcolor='#F0F2F6', plot_bgcolor='#FFFFFF',
                xaxis_type='category',
                yaxis=dict(showgrid=True, gridcolor='#e5e5e5'),
                xaxis=dict(showgrid=False), height=400
            )
            fig.update_traces(marker_line=dict(width=1.5, color='#333'), textposition="outside", cliponaxis=False)
            return fig
    
        tab1, tab2 = st.tabs(["Detection Performance", "Recovery Performance"])
    
        with tab1:
            group_detection = df_unique_reports.groupby('audit_group_number_str')['Detection in Lakhs'].sum().nlargest(10).reset_index()
            if not group_detection.empty:
                fig_det_grp = px.bar(group_detection, x='audit_group_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Vivid)
                fig_det_grp = style_chart(fig_det_grp, "Top 10 Groups by Detection", "Amount (₹ Lakhs)", "Audit Group")
                st.plotly_chart(fig_det_grp, use_container_width=True)
    
            circle_detection = df_unique_reports.groupby('circle_number_str')['Detection in Lakhs'].sum().sort_values(ascending=False).reset_index()
            circle_detection = circle_detection[circle_detection['circle_number_str'] != '0']
            if not circle_detection.empty:
                fig_det_circle = px.bar(circle_detection, x='circle_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Pastel1)
                fig_det_circle = style_chart(fig_det_circle, "Circle-wise Detection", "Amount (₹ Lakhs)", "Audit Circle")
                st.plotly_chart(fig_det_circle, use_container_width=True)
    
        with tab2:
            group_recovery = df_unique_reports.groupby('audit_group_number_str')['Recovery in Lakhs'].sum().nlargest(10).reset_index()
            if not group_recovery.empty:
                fig_rec_grp = px.bar(group_recovery, x='audit_group_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Set2)
                fig_rec_grp = style_chart(fig_rec_grp, "Top 10 Groups by Recovery", "Amount (₹ Lakhs)", "Audit Group")
                st.plotly_chart(fig_rec_grp, use_container_width=True)
    
            circle_recovery = df_unique_reports.groupby('circle_number_str')['Recovery in Lakhs'].sum().sort_values(ascending=False).reset_index()
            circle_recovery = circle_recovery[circle_recovery['circle_number_str'] != '0']
            if not circle_recovery.empty:
                fig_rec_circle = px.bar(circle_recovery, x='circle_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.G10)
                fig_rec_circle = style_chart(fig_rec_circle, "Circle-wise Recovery", "Amount (₹ Lakhs)", "Audit Circle")
                st.plotly_chart(fig_rec_circle, use_container_width=True)
              # --- Section 3: Taxpayer Classification Analysis (New) ---
        st.markdown("---")
        st.markdown("<h4>Taxpayer Classification Analysis</h4>", unsafe_allow_html=True)

        tc_tab1, tc_tab2 = st.tabs(["DARs by Classification", "Detection & Recovery by Classification"])

        with tc_tab1:
            if 'taxpayer_classification' in df_unique_reports.columns:
                class_counts = df_unique_reports['taxpayer_classification'].value_counts().reset_index()
                class_counts.columns = ['classification', 'count']
                
                fig_pie_dars = px.pie(class_counts, names='classification', values='count',
                                      title="Distribution of DARs by Taxpayer Classification",
                                      color_discrete_sequence=px.colors.sequential.Blues_r,
                                      labels={'classification': 'Taxpayer Classification', 'count': 'Number of DARs'})
                fig_pie_dars.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05]*len(class_counts))
                fig_pie_dars.update_layout(legend_title="Classification", title_x=0.5)
                st.plotly_chart(fig_pie_dars, use_container_width=True)
            else:
                st.info("Taxpayer classification data not available for this period.")

        with tc_tab2:
            if 'taxpayer_classification' in df_unique_reports.columns:
                class_agg = df_unique_reports.groupby('taxpayer_classification').agg(
                    Total_Detection=('Detection in Lakhs', 'sum'),
                    Total_Recovery=('Recovery in Lakhs', 'sum')
                ).reset_index()

                col_det, col_rec = st.columns(2)
                with col_det:
                    fig_pie_det = px.pie(class_agg, names='taxpayer_classification', values='Total_Detection',
                                         title="Detection Amount by Taxpayer Classification",
                                         color_discrete_sequence=px.colors.sequential.Reds_r,
                                         labels={'taxpayer_classification': 'Classification', 'Total_Detection': 'Detection (₹ Lakhs)'})
                    fig_pie_det.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie_det.update_layout(legend_title="Classification", title_x=0.5)
                    st.plotly_chart(fig_pie_det, use_container_width=True)
                
                with col_rec:
                    fig_pie_rec = px.pie(class_agg, names='taxpayer_classification', values='Total_Recovery',
                                         title="Recovery Amount by Taxpayer Classification",
                                         color_discrete_sequence=px.colors.sequential.Purples_r,
                                         labels={'taxpayer_classification': 'Classification', 'Total_Recovery': 'Recovery (₹ Lakhs)'})
                    fig_pie_rec.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie_rec.update_layout(legend_title="Classification", title_x=0.5)
                    st.plotly_chart(fig_pie_rec, use_container_width=True)
            else:
                st.info("Taxpayer classification data not available for this period.")

        st.markdown("---")
        st.markdown("<h4>Nature of Compliance Analysis for Audit Paras</h4>", unsafe_allow_html=True)
        
        CLASSIFICATION_CODES_DESC = {
            'TP': 'TAX PAYMENT DEFAULTS', 'RC': 'REVERSE CHARGE MECHANISM',
            'IT': 'INPUT TAX CREDIT VIOLATIONS', 'IN': 'INTEREST LIABILITY DEFAULTS',
            'RF': 'RETURN FILING NON-COMPLIANCE', 'PD': 'PROCEDURAL & DOCUMENTATION',
            'CV': 'CLASSIFICATION & VALUATION', 'SS': 'SPECIAL SITUATIONS',
            'PG': 'PENALTY & GENERAL COMPLIANCE'
        }
        
        DETAILED_CLASSIFICATION_DESC = {
            'TP01': 'Output Tax Short Payment - GSTR Discrepancies', 'TP02': 'Output Tax on Other Income',
            'TP03': 'Output Tax on Asset Sales', 'TP04': 'Export & SEZ Related Issues',
            'TP05': 'Credit Note Adjustment Errors', 'TP06': 'Turnover Reconciliation Issues',
            'TP07': 'Scheme Migration Issues', 'TP08': 'Other Tax Payment Issues',
            'RC01': 'RCM on Transportation Services', 'RC02': 'RCM on Professional Services',
            'RC03': 'RCM on Administrative Services', 'RC04': 'RCM on Import of Services',
            'RC05': 'RCM Reconciliation Issues', 'RC06': 'RCM on Other Services', 'RC07': 'Other RCM Issues',
            'IT01': 'Blocked Credit Claims (Sec 17(5))', 'IT02': 'Ineligible ITC Claims (Sec 16)',
            'IT03': 'Excess ITC - GSTR Reconciliation', 'IT04': 'Supplier Registration Issues',
            'IT05': 'ITC Reversal - 180 Day Rule', 'IT06': 'ITC Reversal - Other Reasons',
            'IT07': 'Proportionate ITC Issues (Rule 42)', 'IT08': 'RCM ITC Mismatches',
            'IT09': 'Import IGST ITC Issues', 'IT10': 'Migration Related ITC Issues', 'IT11': 'Other ITC Issues',
            'IN01': 'Interest on Delayed Tax Payment', 'IN02': 'Interest on Delayed Filing',
            'IN03': 'Interest on ITC - 180 Day Rule', 'IN04': 'Interest on ITC Reversals',
            'IN05': 'Interest on Time of Supply Issues', 'IN06': 'Interest on Self-Assessment (DRC-03)',
            'IN07': 'Other Interest Issues', 'RF01': 'GSTR-1 Late Filing Fees', 'RF02': 'GSTR-3B Late Filing Fees',
            'RF03': 'GSTR-9 Late Filing Fees', 'RF04': 'GSTR-9C Late Filing Fees',
            'RF05': 'ITC-04 Non-Filing', 'RF06': 'General Return Filing Issues', 'RF07': 'Other Return Filing Issues',
            'PD01': 'Return Reconciliation Mismatches', 'PD02': 'Documentation Deficiencies',
            'PD03': 'Cash Payment Violations (Rule 86B)', 'PD04': 'Record Maintenance Issues', 'PD05': 'Other Procedural Issues',
            'CV01': 'Service Classification Errors', 'CV02': 'Rate Classification Errors',
            'CV03': 'Place of Supply Issues', 'CV04': 'Other Classification Issues',
            'SS01': 'Construction/Real Estate Issues', 'SS02': 'Job Work Related Issues',
            'SS03': 'Inter-Company Transaction Issues', 'SS04': 'Composition Scheme Issues', 'SS05': 'Other Special Situations',
            'PG01': 'Statutory Penalties (Sec 123)', 'PG02': 'Stock & Physical Verification Issues',
            'PG03': 'Compliance Monitoring Issues', 'PG04': 'Other Penalty Issues'
        }

        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        if not df_paras.empty:
            df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
        
            nc_tab1, nc_tab2, nc_tab3 = st.tabs(["Classification Code Summary", "Detection by Detailed Code", "Recovery by Detailed Code"])

            with nc_tab1:
                major_code_agg = df_paras.groupby('major_code').agg(
                    Para_Count=('major_code', 'count'),
                    Total_Detection=('Para Detection in Lakhs', 'sum'),
                    Total_Recovery=('Para Recovery in Lakhs', 'sum')
                ).reset_index()
                major_code_agg['description'] = major_code_agg['major_code'].map(CLASSIFICATION_CODES_DESC)

                fig_bar_paras = px.bar(major_code_agg, x='description', y='Para_Count', text_auto=True,
                                       title="Number of Audit Paras by Classification",
                                       labels={'description': 'Classification Code', 'Para_Count': 'Number of Paras'},
                                       color_discrete_sequence=['#1f77b4'])
                st.plotly_chart(fig_bar_paras, use_container_width=True)

                fig_bar_det = px.bar(major_code_agg, x='description', y='Total_Detection', text_auto='.2f',
                                     title="Detection Amount by Classification",
                                     labels={'description': 'Classification Code', 'Total_Detection': 'Detection (₹ Lakhs)'},
                                     color_discrete_sequence=['#ff7f0e'])
                st.plotly_chart(fig_bar_det, use_container_width=True)

                fig_bar_rec = px.bar(major_code_agg, x='description', y='Total_Recovery', text_auto='.2f',
                                     title="Recovery Amount by Classification",
                                     labels={'description': 'Classification Code', 'Total_Recovery': 'Recovery (₹ Lakhs)'},
                                     color_discrete_sequence=['#2ca02c'])
                st.plotly_chart(fig_bar_rec, use_container_width=True)

            with nc_tab2:
                st.markdown("<h5>Detection Analysis by Detailed Classification</h5>", unsafe_allow_html=True)
                unique_major_codes_det = df_paras[df_paras['Para Detection in Lakhs'] > 0]['major_code'].unique()
                for code in sorted(unique_major_codes_det):
                    df_filtered = df_paras[df_paras['major_code'] == code].copy()
                    df_agg = df_filtered.groupby('para_classification_code')['Para Detection in Lakhs'].sum().reset_index()
                    df_agg['description'] = df_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
                    
                    fig = px.bar(df_agg, 
                                 x='para_classification_code', 
                                 y='Para Detection in Lakhs',
                                 color='description',
                                 title=f"Detection for {code} - {CLASSIFICATION_CODES_DESC.get(code, '')}",
                                 labels={
                                     'para_classification_code': 'Detailed Code', 
                                     'Para Detection in Lakhs': 'Detection (₹ Lakhs)',
                                     'description': 'Classification Description'
                                 },
                                 text_auto='.2f')
                    fig.update_layout(legend_title_text='Classification Description', legend_traceorder="normal")
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)

            with nc_tab3:
                st.markdown("<h5>Recovery Analysis by Detailed Classification</h5>", unsafe_allow_html=True)
                unique_major_codes_rec = df_paras[df_paras['Para Recovery in Lakhs'] > 0]['major_code'].unique()
                for code in sorted(unique_major_codes_rec):
                    df_filtered = df_paras[df_paras['major_code'] == code].copy()
                    df_agg = df_filtered.groupby('para_classification_code')['Para Recovery in Lakhs'].sum().reset_index()
                    df_agg['description'] = df_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)

                    fig = px.bar(df_agg, 
                                 x='para_classification_code', 
                                 y='Para Recovery in Lakhs',
                                 color='description',
                                 title=f"Recovery for {code} - {CLASSIFICATION_CODES_DESC.get(code, '')}",
                                 labels={
                                     'para_classification_code': 'Detailed Code', 
                                     'Para Recovery in Lakhs': 'Recovery (₹ Lakhs)',
                                     'description': 'Classification Description'
                                 },
                                 text_auto='.2f')
                    fig.update_layout(legend_title_text='Classification Description', legend_traceorder="normal")
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No classified audit para data available for this period.")


        # --- 6. Treemaps by Trade Name ---
        st.markdown("---")
        st.markdown("<h4>Analysis by Trade Name</h4>", unsafe_allow_html=True)
        
        df_treemap = df_unique_reports.dropna(subset=['category', 'trade_name']).copy()
        
        # MODIFICATION: New light and modern color palette, avoiding red
        color_map = {
            'Large': '#3A86FF',    # Bright Blue
            'Medium': '#3DCCC7',   # Turquoise
            'Small': '#90E0EF',    # Light Blue/Cyan
            'Unknown': '#CED4DA'   # Light Grey
        }
    
        # Detection Treemap
        df_det_treemap = df_treemap[df_treemap['Detection in Lakhs'] > 0]
        if not df_det_treemap.empty:
            try:
                fig_tree_det = px.treemap(
                    df_det_treemap, path=[px.Constant("All Detections"), 'category', 'trade_name'],
                    values='Detection in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                fig_tree_det.update_layout(
                    title_text="<b>Detection by Trade Name</b>", title_x=0.5, 
                    margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif")
                )
                # MODIFICATION: Add white borders for better separation and update hover text
                fig_tree_det.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Detection: %{value:,.2f} L<extra></extra>"
                )
                st.plotly_chart(fig_tree_det, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate detection treemap: {e}")
    
        # Recovery Treemap
        df_rec_treemap = df_treemap[df_treemap['Recovery in Lakhs'] > 0]
        if not df_rec_treemap.empty:
            try:
                fig_tree_rec = px.treemap(
                    df_rec_treemap, path=[px.Constant("All Recoveries"), 'category', 'trade_name'],
                    values='Recovery in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                # MODIFICATION: Applied consistent styling to the recovery treemap
                fig_tree_rec.update_layout(
                    title_text="<b>Recovery by Trade Name</b>", title_x=0.5,
                    margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif")
                )
                fig_tree_rec.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Recovery: %{value:,.2f} L<extra></extra>"
                )
                st.plotly_chart(fig_tree_rec, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate recovery treemap: {e}")


      
        st.markdown("---")
        st.markdown("<h4>Risk Parameter Analysis</h4>", unsafe_allow_html=True)
        
        st.markdown("""
        This section analyzes audit performance based on pre-defined GST risk parameters. 
        It helps identify which risks are most frequently associated with audit observations and which ones 
        contribute most to revenue detection and recovery. The charts are sorted to highlight the most significant parameters.
        """)

        GST_RISK_PARAMETERS = {
            "P01": "Sale turnover (GSTR-3B) is less than the purchase turnover", 
            "P03": "High ratio of nil-rated/exempt supplies to total turnover",
            "P04": "High ratio of zero-rated supplies to total turnover", 
            "P09": "Decline in average monthly taxable turnover in GSTR-3B",
            "P10": "High ratio of non-GST supplies to total turnover", 
            "P21": "High ratio of zero-rated supply to SEZ to total GST turnover",
            "P22": "High ratio of deemed exports to total GST turnover", 
            "P23": "High ratio of zero-rated supply (other than exports) to total supplies",
            "P29": "High ratio of taxable turnover as per ITC-04 vs. total turnover in GSTR-3B", 
            "P31": "High ratio of Credit Notes to total taxable turnover value",
            "P32": "High ratio of Debit Notes to total taxable turnover value", 
            "P02": "IGST paid on import is more than the ITC availed in GSTR-3B",
            "P05": "High ratio of inward supplies liable to reverse charge to total turnover", 
            "P06": "Mismatch between RCM liability declared and ITC claimed on RCM",
            "P07": "High ratio of tax paid through ITC to total tax payable", 
            "P14": "Positive difference between ITC availed in GSTR-3B and ITC available in GSTR-2A",
            "P15": "Positive difference between ITC on import of goods (GSTR-3B) and IGST paid at Customs", 
            "P16": "Low ratio of tax paid under RCM compared to ITC claimed on RCM",
            "P17": "High ratio of ISD credit to total ITC availed", 
            "P18": "Low ratio of ITC reversed to total ITC availed",
            "P19": "Mismatch between the proportion of exempt supplies and the proportion of ITC reversed", 
            "P08": "Low ratio of tax payment in cash to total tax liability",
            "P11": "Taxpayer has filed more than six GST returns late", 
            "P12": "Taxpayer has not filed three consecutive GSTR-3B returns",
            "P30": "Taxpayer was selected for audit on risk criteria last year but was not audited", 
            "P13": "Taxpayer has both SEZ and non-SEZ registrations with the same PAN in the same state",
            "P20": "Mismatch between the taxable value of exports in GSTR-1 and the IGST value in shipping bills (Customs data)", 
            "P24": "Risk associated with other linked GSTINs of the same PAN",
            "P28": "Taxpayer is flagged in Red Flag Reports of DGARM", 
            "P33": "Substantial difference between turnover in GSTR-3B and turnover in Income Tax Return (ITR)",
            "P34": "Negligible income tax payment despite substantial turnover in GSTR-3B", 
            "P25": "High amount of IGST Refund claimed (for Risky Exporters)",
            "P26": "High amount of LUT Export Refund claimed (for Risky Exporters)", 
            "P27": "High amount of Refund claimed due to inverted duty structure (for Risky Exporters)"
        }


        if 'risk_flags_data' not in df_viz_data.columns:
            st.warning("Column 'risk_flags_data' not found. Skipping Risk Parameter Analysis.")
        else:
            risk_para_records = []
            valid_risk_data = df_viz_data[
                df_viz_data['risk_flags_data'].notna() & 
                (df_viz_data['risk_flags_data'] != '') & 
                (df_viz_data['risk_flags_data'] != '[]') &
                (df_viz_data['risk_flags_data'].astype(str) != 'nan')
            ]
            
            gstins_with_risk_data = valid_risk_data['gstin'].nunique()

            # Process risk data
            for idx, row in valid_risk_data.iterrows():
                try:
                    risk_data_str = str(row['risk_flags_data']).strip()
                    
                    # Try to parse as JSON
                    if risk_data_str.startswith('[') or risk_data_str.startswith('{'):
                        risk_list = json.loads(risk_data_str)
                    else:
                        # If not JSON, try to split by comma or other delimiter
                        risk_list = [{"risk_flag": risk_data_str, "paras": [row.get('audit_para_number', 1)]}]
                    
                    # Handle different data structures
                    if isinstance(risk_list, list):
                        for risk_item in risk_list:
                            if isinstance(risk_item, dict):
                                risk_flag = risk_item.get("risk_flag", risk_item.get("risk_parameter", "Unknown"))
                                paras = risk_item.get("paras", [row.get('audit_para_number', 1)])
                            else:
                                risk_flag = str(risk_item)
                                paras = [row.get('audit_para_number', 1)]
                            
                            if risk_flag and paras:
                                for para_num in paras:
                                    risk_para_records.append({
                                        "gstin": row['gstin'], 
                                        "audit_para_number": para_num, 
                                        "risk_flag": risk_flag
                                    })
                    else:
                        # Single risk item
                        risk_flag = str(risk_list)
                        risk_para_records.append({
                            "gstin": row['gstin'], 
                            "audit_para_number": row.get('audit_para_number', 1), 
                            "risk_flag": risk_flag
                        })
                        
                except Exception:
                    continue
            
            if not risk_para_records:
                st.info("No valid risk parameter data could be processed for this period.")
            else:
                df_risk_long = pd.DataFrame(risk_para_records)
                
                # Convert audit_para_number to numeric
                df_risk_long['audit_para_number'] = pd.to_numeric(df_risk_long['audit_para_number'], errors='coerce')

                # Merge with main data
                df_risk_analysis = pd.merge(
                    df_viz_data.dropna(subset=['audit_para_number']), 
                    df_risk_long, 
                    on=['gstin', 'audit_para_number'], 
                    how='inner'
                )
                
                if df_risk_analysis.empty:
                    st.info("No matching records found after merging risk data with audit data.")
                else:
                    paras_with_risk_flags = df_risk_analysis[['gstin', 'audit_para_number']].drop_duplicates().shape[0]

                    # Display summary metrics
                    col1, col2 = st.columns(2)
                    col1.metric("GSTINs with Risk Data", f"{gstins_with_risk_data}")
                    col2.metric("Paras Linked to Risks", f"{paras_with_risk_flags}")
                    
                    # Aggregate risk data
                    risk_agg = df_risk_analysis.groupby('risk_flag').agg(
                        Para_Count=('risk_flag', 'count'),
                        Total_Detection=('Para Detection in Lakhs', 'sum'),
                        Total_Recovery=('Para Recovery in Lakhs', 'sum')
                    ).reset_index()

                    risk_agg['description'] = risk_agg['risk_flag'].map(GST_RISK_PARAMETERS).fillna("Unknown Risk Code")
                    risk_agg['Percentage_Recovery'] = (risk_agg['Total_Recovery'] / risk_agg['Total_Detection'].replace(0, np.nan)).fillna(0) * 100

                    # Display Risk Aggregation Table
                    st.markdown("#### 📊 Risk Parameter Summary")
                    
                    # Format the risk aggregation table for better display
                    display_risk_agg = risk_agg.copy()
                    display_risk_agg = display_risk_agg.rename(columns={
                        'risk_flag': 'RISK FLAG',
                        'Para_Count': 'NO. OF PARAS',
                        'Total_Detection': 'TOTAL DETECTION (₹ L)',
                        'Total_Recovery': 'TOTAL RECOVERY (₹ L)',
                        'Percentage_Recovery': 'RECOVERY %',
                        'description': 'RISK DESCRIPTION'
                    })
                    
                    # Format currency columns
                    display_risk_agg['TOTAL DETECTION (₹ L)'] = display_risk_agg['TOTAL DETECTION (₹ L)'].apply(lambda x: f"₹{x:,.2f} L")
                    display_risk_agg['TOTAL RECOVERY (₹ L)'] = display_risk_agg['TOTAL RECOVERY (₹ L)'].apply(lambda x: f"₹{x:,.2f} L")
                    display_risk_agg['RECOVERY %'] = display_risk_agg['RECOVERY %'].apply(lambda x: f"{x:.1f}%")
                    
                    # Sort by Para Count descending
                    display_risk_agg = display_risk_agg.sort_values('NO. OF PARAS', ascending=False)
                    
                    st.table(display_risk_agg[['RISK FLAG', 'RISK DESCRIPTION', 'NO. OF PARAS', 'TOTAL DETECTION (₹ L)', 'TOTAL RECOVERY (₹ L)', 'RECOVERY %']])

                    # Chart 1: Audit Paras by Risk Flag
                    if not risk_agg.empty:
                        st.markdown("#### 📈 Risk Parameter Analysis Charts")
                        
                        risk_agg_sorted_count = risk_agg.sort_values('Para_Count', ascending=False).head(15)
                        fig_risk_paras = px.bar(
                            risk_agg_sorted_count, 
                            x='risk_flag', 
                            y='Para_Count', 
                            text_auto=True, 
                            hover_name='description', 
                            hover_data={'risk_flag': False, 'description': True, 'Para_Count': True}, 
                            color_discrete_sequence=px.colors.qualitative.Bold,
                            title="Top 15 Risk Flags by Number of Audit Paras"
                        )
                        fig_risk_paras.update_layout(
                            title_x=0.5,
                            xaxis_title="Risk Flag",
                            yaxis_title="Number of Paras",
                            height=500
                        )
                        fig_risk_paras.update_traces(textposition="outside", cliponaxis=False)
                        st.plotly_chart(fig_risk_paras, use_container_width=True)

                        # Chart 2 & 3: Detection and Recovery
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            risk_agg_sorted_det = risk_agg.sort_values('Total_Detection', ascending=False).head(10)
                            if not risk_agg_sorted_det.empty and risk_agg_sorted_det['Total_Detection'].sum() > 0:
                                fig_risk_detection = px.bar(
                                    risk_agg_sorted_det, 
                                    x='risk_flag', 
                                    y='Total_Detection', 
                                    text_auto='.2f', 
                                    hover_name='description', 
                                    hover_data={'risk_flag': False}, 
                                    color_discrete_sequence=px.colors.qualitative.Prism,
                                    title="Top 10 Detection Amount by Risk Flag"
                                )
                                fig_risk_detection.update_layout(
                                    title_x=0.5,
                                    xaxis_title="Risk Flag",
                                    yaxis_title="Amount (₹ Lakhs)",
                                    height=400
                                )
                                fig_risk_detection.update_traces(textposition="outside", cliponaxis=False)
                                st.plotly_chart(fig_risk_detection, use_container_width=True)
                            else:
                                st.info("No detection data available for risk analysis")
                        
                        with col2:
                            risk_agg_sorted_rec = risk_agg.sort_values('Total_Recovery', ascending=False).head(10)
                            if not risk_agg_sorted_rec.empty and risk_agg_sorted_rec['Total_Recovery'].sum() > 0:
                                fig_risk_recovery = px.bar(
                                    risk_agg_sorted_rec, 
                                    x='risk_flag', 
                                    y='Total_Recovery', 
                                    text_auto='.2f', 
                                    hover_name='description', 
                                    hover_data={'risk_flag': False}, 
                                    color_discrete_sequence=px.colors.qualitative.Safe,
                                    title="Top 10 Recovery Amount by Risk Flag"
                                )
                                fig_risk_recovery.update_layout(
                                    title_x=0.5,
                                    xaxis_title="Risk Flag",
                                    yaxis_title="Amount (₹ Lakhs)",
                                    height=400
                                )
                                fig_risk_recovery.update_traces(textposition="outside", cliponaxis=False)
                                st.plotly_chart(fig_risk_recovery, use_container_width=True)
                            else:
                                st.info("No recovery data available for risk analysis")

                        # Chart 4: Percentage Recovery
                        risk_with_recovery = risk_agg[risk_agg['Total_Detection'] > 0]
                        if not risk_with_recovery.empty:
                            risk_agg_sorted_perc = risk_with_recovery.sort_values('Percentage_Recovery', ascending=False).head(10)
                            fig_risk_percentage = px.bar(
                                risk_agg_sorted_perc, 
                                x='risk_flag', 
                                y='Percentage_Recovery', 
                                hover_name='description', 
                                hover_data={'risk_flag': False}, 
                                color='Percentage_Recovery', 
                                color_continuous_scale=px.colors.sequential.Greens,
                                title="Top 10 Percentage Recovery by Risk Flag"
                            )
                            fig_risk_percentage.update_traces(texttemplate='%{y:.1f}%', textposition='outside', cliponaxis=False)
                            fig_risk_percentage.update_layout(
                                title_x=0.5,
                                xaxis_title="Risk Flag",
                                yaxis_title="Recovery (%)",
                                height=400,
                                coloraxis_showscale=False
                            )
                            st.plotly_chart(fig_risk_percentage, use_container_width=True)
                        else:
                            st.info("No percentage recovery data available for risk analysis")


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
        
        viz_df_paras_only = df_viz_data[df_viz_data['audit_para_number'].notna() & (~df_viz_data['audit_para_heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
        if 'revenue_involved_lakhs_rs' in viz_df_paras_only.columns:
            viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'revenue_involved_lakhs_rs')
            if not viz_top_det_paras.empty:
                st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**")
                viz_disp_cols_det = ['audit_group_number_str', 'trade_name', 'audit_para_number', 'audit_para_heading', 'revenue_involved_lakhs_rs', 'status_of_para']
                viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]
                st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'audit_group_number_str': 'Audit Group'}), use_container_width=True)
        if 'revenue_recovered_lakhs_rs' in viz_df_paras_only.columns:
            viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'revenue_recovered_lakhs_rs')
            if not viz_top_rec_paras.empty:
                st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**")
                viz_disp_cols_rec = ['audit_group_number_str', 'trade_name', 'audit_para_number', 'audit_para_heading', 'revenue_recovered_lakhs_rs', 'status_of_para']
                viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]
                st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'audit_group_number_str': 'Audit Group'}), use_container_width=True)

    elif selected_tab == "Reports":
        pco_reports_dashboard(dbx)

    st.markdown("</div>", unsafe_allow_html=True)
  


