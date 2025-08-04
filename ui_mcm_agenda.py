# ui_mcm_agenda.py
import streamlit as st
import pandas as pd
import datetime
import math
from io import BytesIO
import html
import time as time_module

# PDF manipulation libraries
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import inch
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas

# Dropbox-based imports
from dropbox_utils import read_from_spreadsheet, download_file, update_spreadsheet_from_df
from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH

# --- NEW IMPORTS for Report Generation ---
from mcm_report_generator import PDFReportGenerator
from visualisation_utils import get_visualization_data # Import the helper function

# # --- HELPER FUNCTION FOR INDIAN NUMBERING ---
# def format_inr(n):
#     """
#     Formats a number (including numpy types) into the Indian numbering system.
#     """
#     try:
#         # First, try to convert the input to a standard integer. This handles numpy types.
#         n = int(n)
#     except (ValueError, TypeError):
#         return "0" # If it can't be converted, return "0"
    
#     if n < 0:
#         return '-' + format_inr(-n)
#     if n == 0:
#         return "0"
    
#     s = str(n)
#     if len(s) <= 3:
#         return s
    
#     s_last_three = s[-3:]
#     s_remaining = s[:-3]
    
#     groups = []
#     while len(s_remaining) > 2:
#         groups.append(s_remaining[-2:])
#         s_remaining = s_remaining[:-2]
    
#     if s_remaining:
#         groups.append(s_remaining)
    
#     groups.reverse()
#     result = ','.join(groups) + ',' + s_last_three
#     return result
def format_inr(n):
    """
    FIXED: Formats a number into the Indian numbering system with proper error handling.
    """
    try:
        # Handle None, NaN, and empty values
        if n is None or n == '' or pd.isna(n):
            return "0"
        
        # Convert to float first to handle any string numbers or scientific notation
        n = float(n)
        
        # Convert to integer for formatting (remove decimals)
        n = int(n)
        
        # Handle negative numbers
        if n < 0:
            return '-' + format_inr(-n)
        
        if n == 0:
            return "0"
        
        # Convert to string for processing
        s = str(n)
        
        # Handle numbers with 3 digits or less
        if len(s) <= 3:
            return s
        
        # Split into last 3 digits and remaining
        s_last_three = s[-3:]
        s_remaining = s[:-3]
        
        # Process remaining digits in groups of 2
        groups = []
        while len(s_remaining) > 2:
            groups.append(s_remaining[-2:])
            s_remaining = s_remaining[:-2]
        
        # Add any remaining digits
        if s_remaining:
            groups.append(s_remaining)
        
        # Reverse and join
        groups.reverse()
        result = ','.join(groups) + ',' + s_last_three
        return result
        
    except (ValueError, TypeError, AttributeError) as e:
        print(f"Error formatting currency {n}: {e}")
        return "0"

def create_page_number_stamp_pdf(buffer, page_num, total_pages):
    """
    Creates a PDF in memory with 'Page X of Y' at the bottom center.
    This will be used as a "stamp" to overlay on existing pages.
    """
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont('Helvetica', 9)
    c.setFillColor(colors.darkgrey)
    # Draws the string 'Page X of Y' centered at the bottom of the page
    c.drawCentredString(A4[0] / 2.0, 0.5 * inch, f"Page {page_num} of {total_pages}")
    c.save()
    buffer.seek(0)
    return buffer

# --- PDF Generation Functions ---
def create_cover_page_pdf(buffer, title_text, subtitle_text):
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch, bottomMargin=1.5*inch, leftMargin=1*inch, rightMargin=1*inch)
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle('AgendaCoverTitle', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=28, alignment=TA_CENTER, textColor=colors.HexColor("#dc3545"), spaceBefore=1*inch, spaceAfter=0.3*inch)
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 0.3*inch))
    subtitle_style = ParagraphStyle('AgendaCoverSubtitle', parent=styles['h2'], fontName='Helvetica', fontSize=16, alignment=TA_CENTER, textColor=colors.darkslategray, spaceAfter=2*inch)
    story.append(Paragraph(subtitle_text, subtitle_style))
    doc.build(story)
    buffer.seek(0)
    return buffer

def create_index_page_pdf(buffer, index_data_list, start_page_offset_for_index_table):
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("<b>Index of DARs</b>", styles['h1']))
    story.append(Spacer(1, 0.2*inch))
    table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Start Page</b>", styles['Normal'])]]

    for item in index_data_list:
        table_data.append([
            Paragraph(str(item['circle']), styles['Normal']),
            Paragraph(html.escape(item['trade_name']), styles['Normal']),
            Paragraph(str(item['start_page_in_final_pdf']), styles['Normal'])
        ])
    col_widths = [1.5*inch, 4*inch, 1.5*inch]; index_table = Table(table_data, colWidths=col_widths)
    index_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)])); story.append(index_table)
    doc.build(story); buffer.seek(0); return buffer

def create_high_value_paras_pdf(buffer, df_high_value_paras_data):
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet(); story = []
    story.append(Paragraph("<b>High-Value Audit Paras (&gt; ₹5 Lakhs Detection)</b>", styles['h1'])); story.append(Spacer(1, 0.2*inch))
    table_data_hv = [[Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
                      Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (₹)</b>", styles['Normal']),
                      Paragraph("<b>Recovered (₹)</b>", styles['Normal'])]]
    for _, row_hv in df_high_value_paras_data.iterrows():
        # Use format_inr for PDF values
        detected_val = row_hv.get('revenue_involved_lakhs_rs', 0) * 100000
        recovered_val = row_hv.get('revenue_recovered_lakhs_rs', 0) * 100000
        table_data_hv.append([
            Paragraph(html.escape(str(row_hv.get("audit_group_number", "N/A"))), styles['Normal']),
            Paragraph(html.escape(str(row_hv.get("audit_para_number", "N/A"))), styles['Normal']),
            Paragraph(html.escape(str(row_hv.get("audit_para_heading", "N/A"))[:100]), styles['Normal']),
            Paragraph(format_inr(detected_val), styles['Normal']),
            Paragraph(format_inr(recovered_val), styles['Normal'])])

    col_widths_hv = [1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch]; hv_table = Table(table_data_hv, colWidths=col_widths_hv)
    hv_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,1), (-1,-1), 4),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)])); story.append(hv_table)
    doc.build(story); buffer.seek(0); return buffer
# --- End PDF Generation Functions ---

def calculate_audit_circle_agenda(audit_group_number_val):
    try:
        agn = int(audit_group_number_val)
        if 1 <= agn <= 30: return math.ceil(agn / 3.0)
        return 0
    except (ValueError, TypeError, AttributeError): return 0


def mcm_agenda_tab(dbx):
    st.markdown("### MCM Agenda Preparation")
    # --- CSS for Tab Styling ---
    st.markdown("""
        <style>
            /* Make tab text bolder and larger */
            button[data-testid="stTab"] {
                font-size: 16px;
                font-weight: 600;
            }
            /* Highlight the selected tab with a blue background and border */
            button[data-testid="stTab"][aria-selected="true"] {
                background-color: #e3f2fd;
                border-bottom: 3px solid #007bff;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Load MCM periods
    df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    if df_periods is None or df_periods.empty:
        st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
        return

    # Create period options
    period_options = {}
    for _, period_row in df_periods.iterrows():
        if pd.notna(period_row.get('month_name')) and pd.notna(period_row.get('year')):
            key = f"{period_row.get('month_name')} {period_row.get('year')}"
            period_options[key] = key
    
    if not period_options:
        st.warning("No valid MCM periods with complete month and year information available.")
        return

    selected_period = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), key="mcm_agenda_period_select_v3_full")

    if not selected_period:
        st.info("Please select an MCM period."); return
    # --- NEW: Overall Remarks Section ---
    st.markdown("---")
    with st.container(border=True):
        st.markdown("<h5>Overall Remarks for the Meeting</h5>", unsafe_allow_html=True)

        df_periods_for_remarks = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        if df_periods_for_remarks is None:
            df_periods_for_remarks = pd.DataFrame(columns=['key', 'overall_remarks'])
        if 'overall_remarks' not in df_periods_for_remarks.columns:
            df_periods_for_remarks['overall_remarks'] = ''
        df_periods_for_remarks['overall_remarks'] = df_periods_for_remarks['overall_remarks'].fillna('').astype(object)
        # if 'overall_remarks' not in df_periods_for_remarks.columns:
        #     df_periods_for_remarks['overall_remarks'] = ""

        current_remark = ""
        period_key_str = selected_period.replace(" ", "_")
        
        # Match period using month and year from the selected string
        month_name, year_val = selected_period.split(" ")
        year_val = int(year_val)
        
        period_row = df_periods_for_remarks[(df_periods_for_remarks['month_name'] == month_name) & (df_periods_for_remarks['year'] == year_val)]

        if not period_row.empty:
            current_remark = period_row.iloc[0].get('overall_remarks', '')
            if pd.isna(current_remark):
                current_remark = ""

        overall_remark_text = st.text_area(
            "Record any overall remarks or instructions from the chair for this MCM period.",
            value=current_remark,
            key=f"overall_remarks_{period_key_str}",
            height=100
        )

        if st.button("Save Overall Remarks", key=f"save_overall_remarks_{period_key_str}"):
            with st.spinner("Saving overall remarks..."):
                period_indices = df_periods_for_remarks.index[(df_periods_for_remarks['month_name'] == month_name) & (df_periods_for_remarks['year'] == year_val)].tolist()
                if period_indices:
                    idx_to_update = period_indices[0]
                    df_periods_for_remarks.loc[idx_to_update, 'overall_remarks'] = overall_remark_text
                    
                    if update_spreadsheet_from_df(dbx, df_periods_for_remarks, MCM_PERIODS_INFO_PATH):
                        st.success("Overall remarks saved successfully!")
                        time_module.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to save overall remarks.")
                else:
                    st.error("Could not find the current period in the periods file to save remarks.")
    # --- END: Overall Remarks Section ---
    month_year_str = selected_period
    st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 22pt; margin-bottom:10px;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
    st.markdown("---")

    # --- Data Loading using Session State ---
    if 'df_period_data' not in st.session_state or st.session_state.get('current_period_key') != selected_period:
        with st.spinner(f"Loading data for {month_year_str}..."):
            df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            if df is None or df.empty:
                st.info(f"No data found in the spreadsheet for {month_year_str}.")
                st.session_state.df_period_data = pd.DataFrame()
                return
            
            # Filter data for selected period
            df = df[df['mcm_period'] == selected_period].copy()
            
            # Convert numeric columns
            cols_to_convert_numeric = ['audit_group_number', 'audit_circle_number', 'total_amount_detected_overall_rs',
                                       'total_amount_recovered_overall_rs', 'audit_para_number',
                                       'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs']
            for col_name in cols_to_convert_numeric:
                if col_name in df.columns:
                    df[col_name] = df[col_name].astype(str).str.replace(r'[^\d.]', '', regex=True)
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                else:
                    df[col_name] = 0 if "amount" in col_name.lower() or "revenue" in col_name.lower() else pd.NA
            
            st.session_state.df_period_data = df
            st.session_state.current_period_key = selected_period
    
    df_period_data_full = st.session_state.df_period_data
    if df_period_data_full.empty:
        st.info(f"No data available for {month_year_str}.")
        return

    # --- Code to derive Audit Circle and set up UI loops ---
    circle_col_to_use = 'audit_circle_number'
    if 'audit_circle_number' not in df_period_data_full.columns or not df_period_data_full['audit_circle_number'].notna().any() or not pd.to_numeric(df_period_data_full['audit_circle_number'], errors='coerce').fillna(0).astype(int).gt(0).any():
        if 'audit_group_number' in df_period_data_full.columns and df_period_data_full['audit_group_number'].notna().any():
            df_period_data_full['derived_audit_circle_number'] = df_period_data_full['audit_group_number'].apply(calculate_audit_circle_agenda).fillna(0).astype(int)
            circle_col_to_use = 'derived_audit_circle_number'
        else:
            df_period_data_full['derived_audit_circle_number'] = 0
            circle_col_to_use = 'derived_audit_circle_number'
    else:
        df_period_data_full['audit_circle_number'] = df_period_data_full['audit_circle_number'].fillna(0).astype(int)

    for circle_num_iter in range(1, 11):
        circle_label_iter = f"Audit Circle {circle_num_iter}"
        df_circle_iter_data = df_period_data_full[df_period_data_full[circle_col_to_use] == circle_num_iter]

        expander_header_html = f"<div style='background-color:#007bff; color:white; padding:10px 15px; border-radius:5px; margin-top:12px; margin-bottom:3px; font-weight:bold; font-size:16pt;'>{html.escape(circle_label_iter)}</div>"
        st.markdown(expander_header_html, unsafe_allow_html=True)
        with st.expander(f"View Details for {html.escape(circle_label_iter)}", expanded=False):
            if df_circle_iter_data.empty:
                st.write(f"No data for {circle_label_iter} in this MCM period.")
                continue

            group_labels_list = []
            group_dfs_list = []
            min_grp = (circle_num_iter - 1) * 3 + 1
            max_grp = circle_num_iter * 3
            for grp_iter_num in range(min_grp, max_grp + 1):
                df_grp_iter_data = df_circle_iter_data[df_circle_iter_data['audit_group_number'] == grp_iter_num]
                if not df_grp_iter_data.empty:
                    group_labels_list.append(f"Audit Group {grp_iter_num}")
                    group_dfs_list.append(df_grp_iter_data)
            
            if not group_labels_list:
                st.write(f"No specific audit group data found within {circle_label_iter}.")
                continue

            group_st_tabs_widgets = st.tabs(group_labels_list)
            for i, group_tab_widget_item in enumerate(group_st_tabs_widgets):
                with group_tab_widget_item:
                    df_current_grp_item = group_dfs_list[i]
                    unique_trade_names_list = df_current_grp_item.get('trade_name', pd.Series(dtype='str')).dropna().unique()

                    if not unique_trade_names_list.any():
                        st.write("No trade names with DARs found for this group.")
                        continue

                    st.markdown(f"**DARs for {group_labels_list[i]}:**")
                    session_key_selected_trade = f"selected_trade_{circle_num_iter}_{group_labels_list[i].replace(' ','_')}"

                    for tn_idx_iter, trade_name_item in enumerate(unique_trade_names_list):
                        trade_name_data = df_current_grp_item[df_current_grp_item['trade_name'] == trade_name_item]
                        dar_pdf_path_item = None
                        if not trade_name_data.empty:
                            dar_pdf_path_item = trade_name_data.iloc[0].get('dar_pdf_path')

                        cols_trade_display = st.columns([0.7, 0.3])
                        with cols_trade_display[0]:
                            if st.button(f"{trade_name_item}", key=f"tradebtn_agenda_v3_{circle_num_iter}_{i}_{tn_idx_iter}", help=f"Toggle paras for {trade_name_item}", use_container_width=True):
                                st.session_state[session_key_selected_trade] = None if st.session_state.get(session_key_selected_trade) == trade_name_item else trade_name_item
                        
                        with cols_trade_display[1]:
                            if pd.notna(dar_pdf_path_item) and dar_pdf_path_item:
                                # Create Dropbox share link (simplified)
                                dropbox_link = f"https://www.dropbox.com/home{dar_pdf_path_item.replace(' ', '%20')}"
                                st.link_button("View DAR PDF", dropbox_link, use_container_width=True, type="secondary")
                            else:
                                st.caption("No PDF Link")

                        if st.session_state.get(session_key_selected_trade) == trade_name_item:
                            df_trade_paras_item = df_current_grp_item[df_current_grp_item['trade_name'] == trade_name_item].copy()
                            # --- RESTORED: Category and GSTIN boxes ---
                            taxpayer_category = "N/A"
                            taxpayer_gstin = "N/A"
                            if not df_trade_paras_item.empty:
                                first_row = df_trade_paras_item.iloc[0]
                                taxpayer_category = first_row.get('category', 'N/A')
                                taxpayer_gstin = first_row.get('gstin', 'N/A')
                            
                            category_color_map = {
                                "Large": ("#f8d7da", "#721c24"),
                                "Medium": ("#ffeeba", "#856404"),
                                "Small": ("#d4edda", "#155724"),
                                "N/A": ("#e2e3e5", "#383d41")
                            }
                            cat_bg_color, cat_text_color = category_color_map.get(taxpayer_category, ("#e2e3e5", "#383d41"))

                            info_cols = st.columns(2)
                            with info_cols[0]:
                                st.markdown(f"""
                                <div style="background-color: {cat_bg_color}; color: {cat_text_color}; padding: 4px 8px; border-radius: 5px; text-align: center; font-size: 0.9rem; margin-top: 5px;">
                                    <b>Category:</b> {html.escape(str(taxpayer_category))}
                                </div>
                                """, unsafe_allow_html=True)
                            with info_cols[1]:
                                st.markdown(f"""
                                <div style="background-color: #e9ecef; color: #495057; padding: 4px 8px; border-radius: 5px; text-align: center; font-size: 0.9rem; margin-top: 5px;">
                                    <b>GSTIN:</b> {html.escape(str(taxpayer_gstin))}
                                </div>
                                """, unsafe_allow_html=True)
                            
                            st.markdown(f"<h5 style='font-size:13pt; margin-top:20px; color:#154360;'>Gist of Audit Paras & MCM Decisions for: {html.escape(trade_name_item)}</h5>", unsafe_allow_html=True)
                            
                             
                            # # --- CSS FOR ALL STYLING ---
                            # st.markdown("""
                            #     <style>
                            #         .grid-header { font-weight: bold; background-color: #343a40; color: white; padding: 10px 5px; border-radius: 5px; text-align: center; }
                            #         .cell-style { padding: 8px 5px; margin: 1px; border-radius: 5px; text-align: center; }
                            #         .title-cell { background-color: #f0f2f6; text-align: left; padding-left: 10px;}
                            #         .revenue-cell { background-color: #e8f5e9; font-weight: bold; }
                            #         .status-cell { background-color: #e3f2fd; font-weight: bold; color: #800000; } /* Maroon text on light blue */
                            #         .total-row { font-weight: bold; padding-top: 10px; }
                            #     </style>
                            # """, unsafe_allow_html=True)
                            st.markdown("""
                                <style>
                                    .grid-header { font-weight: bold; background-color: #343a40; color: white; padding: 10px 5px; border-radius: 5px; text-align: center; }
                                    .cell-style { padding: 8px 5px; margin: 1px; border-radius: 5px; text-align: center; }
                                    .title-cell { 
                                        background-color: #f0f2f6; 
                                        text-align: left; 
                                        padding: 8px 10px;
                                        word-wrap: break-word;
                                        overflow-wrap: break-word;
                                        white-space: normal;
                                        max-width: 100%;
                                        line-height: 1.4;
                                        font-size: 11px;
                                        height: auto;
                                        min-height: 60px;
                                        display: flex;
                                        align-items: flex-start;
                                    }
                                    .revenue-cell { background-color: #e8f5e9; font-weight: bold; }
                                    .status-cell { background-color: #e3f2fd; font-weight: bold; color: #800000; }
                                    .total-row { font-weight: bold; padding-top: 10px; }
                                </style>
                            """, unsafe_allow_html=True)

                            #col_proportions = (0.9, 5, 1.5, 1.5, 1.8, 2.5)
                            col_proportions = (0.7, 3.5, 1.3, 1.3, 1.4, 2.0)
                            header_cols = st.columns(col_proportions)
                            headers = ['Para No.', 'Para Title', 'Detection (₹)', 'Recovery (₹)', 'Status', 'MCM Decision']
                            for col, header in zip(header_cols, headers):
                                col.markdown(f"<div class='grid-header'>{header}</div>", unsafe_allow_html=True)
                            
                            decision_options = ['Para closed since recovered', 'Para deferred', 'Para to be pursued else issue SCN']
                            total_para_det_rs, total_para_rec_rs = 0, 0
                            
                            for index, row in df_trade_paras_item.iterrows():
                                with st.container(border=True):
                                    para_num_str = str(int(row["audit_para_number"])) if pd.notna(row["audit_para_number"]) and row["audit_para_number"] != 0 else "N/A"
                                    # det_rs = (row.get('revenue_involved_lakhs_rs', 0) * 100000) if pd.notna(row.get('revenue_involved_lakhs_rs')) else 0
                                    # rec_rs = (row.get('revenue_recovered_lakhs_rs', 0) * 100000) if pd.notna(row.get('revenue_recovered_lakhs_rs')) else 0

                                    # Get the lakhs values safely
                                    det_lakhs = row.get('revenue_involved_lakhs_rs', 0)
                                    rec_lakhs = row.get('revenue_recovered_lakhs_rs', 0)
                                    
                                    # Clean and convert to numeric (handles string values with commas, etc.)
                                    det_lakhs = pd.to_numeric(str(det_lakhs).replace(',', '').replace('₹', ''), errors='coerce')
                                    rec_lakhs = pd.to_numeric(str(rec_lakhs).replace(',', '').replace('₹', ''), errors='coerce')
                                    
                                    # Handle NaN values
                                    det_lakhs = det_lakhs if pd.notna(det_lakhs) else 0
                                    rec_lakhs = rec_lakhs if pd.notna(rec_lakhs) else 0
                                    
                                    # Convert lakhs to rupees (multiply by 1,00,000)
                                    det_rs = int(det_lakhs * 100000) if det_lakhs > 0 else 0
                                    rec_rs = int(rec_lakhs * 100000) if rec_lakhs > 0 else 0

                                    total_para_det_rs += det_rs
                                    total_para_rec_rs += rec_rs
                                    status_text = html.escape(str(row.get("status_of_para", "N/A")))
                                    #para_title_text = f"<b>{html.escape(str(row.get('audit_para_heading', 'N/A')))}</b>"
                                    # AFTER (multi-line with proper wrapping):
                                    def wrap_para_title_for_display(title, max_length=100):
                                        """Wrap para title for better display in table"""
                                        try:
                                            if pd.isna(title) or title == '' or title == 'N/A':
                                                return 'N/A'
                                            
                                            title_str = str(title).strip()
                                            
                                            # If title is short enough, return as is
                                            if len(title_str) <= max_length:
                                                return title_str
                                            
                                            # Split into words for intelligent wrapping
                                            words = title_str.split()
                                            lines = []
                                            current_line = []
                                            current_length = 0
                                            
                                            for word in words:
                                                # Check if adding this word would exceed line length
                                                if current_length + len(word) + 1 <= 50:  # ~50 chars per line
                                                    current_line.append(word)
                                                    current_length += len(word) + 1
                                                else:
                                                    # Start new line
                                                    if current_line:
                                                        lines.append(' '.join(current_line))
                                                    current_line = [word]
                                                    current_length = len(word)
                                                    
                                                    # Limit to 2 lines max
                                                    if len(lines) >= 2:
                                                        break
                                            
                                            # Add remaining words to last line
                                            if current_line:
                                                lines.append(' '.join(current_line))
                                            
                                            # Join lines with <br> for HTML display
                                            wrapped_title = '<br>'.join(lines)
                                            
                                            # Add ellipsis if we had to truncate
                                            if len(' '.join(title_str.split()[:len(' '.join(lines).split())])) < len(title_str):
                                                wrapped_title += '...'
                                            
                                            return wrapped_title
                                            
                                        except Exception as e:
                                            print(f"Error wrapping para title: {e}")
                                            return str(title)[:80] + '...' if len(str(title)) > 80 else str(title)
                                    
                                    # Use the wrapped title in display:
                                    clean_title = wrap_para_title_for_display(row.get('audit_para_heading', 'N/A'))
                                    para_title_text = f"<b>{clean_title}</b>"
                                    default_index = 0
                                    if 'mcm_decision' in df_trade_paras_item.columns and pd.notna(row['mcm_decision']) and row['mcm_decision'] in decision_options:
                                        default_index = decision_options.index(row['mcm_decision'])
                                    
                                    row_cols = st.columns(col_proportions)
                                    row_cols[0].write(para_num_str)
                                    #row_cols[1].markdown(f"<div class='cell-style title-cell'>{para_title_text}</div>", unsafe_allow_html=True)
                                    row_cols[1].markdown(f"<div class='cell-style title-cell'>{para_title_text}</div>", unsafe_allow_html=True)
                                    # row_cols[2].markdown(f"<div class='cell-style revenue-cell'>{format_inr(det_rs)}</div>", unsafe_allow_html=True)
                                    # row_cols[3].markdown(f"<div class='cell-style revenue-cell'>{format_inr(rec_rs)}</div>", unsafe_allow_html=True)
                                    row_cols[2].markdown(f"<div class='cell-style revenue-cell'>{format_inr(det_rs)}</div>", unsafe_allow_html=True)
                                    row_cols[3].markdown(f"<div class='cell-style revenue-cell'>{format_inr(rec_rs)}</div>", unsafe_allow_html=True)
                                    row_cols[4].markdown(f"<div class='cell-style status-cell'>{status_text}</div>", unsafe_allow_html=True)
                                    
                                    decision_key = f"mcm_decision_{trade_name_item}_{para_num_str}_{index}"
                                    row_cols[5].selectbox("Decision", options=decision_options, index=default_index, key=decision_key, label_visibility="collapsed")
                            
                            st.markdown("---")
                            with st.container():
                                total_cols = st.columns(col_proportions)
                                total_cols[1].markdown("<div class='total-row' style='text-align:right;'>Total of Paras</div>", unsafe_allow_html=True)
                                total_cols[2].markdown(f"<div class='total-row revenue-cell cell-style'>{format_inr(total_para_det_rs)}</div>", unsafe_allow_html=True)
                                total_cols[3].markdown(f"<div class='total-row revenue-cell cell-style'>{format_inr(total_para_rec_rs)}</div>", unsafe_allow_html=True)

                            st.markdown("<br>", unsafe_allow_html=True)
                            
                            total_overall_detection, total_overall_recovery = 0, 0
                            if not df_trade_paras_item.empty:
                                detection_val = df_trade_paras_item['total_amount_detected_overall_rs'].iloc[0]
                                recovery_val = df_trade_paras_item['total_amount_recovered_overall_rs'].iloc[0]
                                total_overall_detection = 0 if pd.isna(detection_val) else detection_val
                                total_overall_recovery = 0 if pd.isna(recovery_val) else recovery_val
                            # --- STYLED SUMMARY LINES ---
                            detection_style = "background-color: #f8d7da; color: #721c24; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 1.2em;"
                            recovery_style = "background-color: #d4edda; color: #155724; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 1.2em;"
                            
                            st.markdown(f"<p style='{detection_style}'>Total Detection for {html.escape(trade_name_item)}: ₹ {format_inr(total_overall_detection)}</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='{recovery_style}'>Total Recovery for {html.escape(trade_name_item)}: ₹ {format_inr(total_overall_recovery)}</p>", unsafe_allow_html=True)
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            # --- NEW: Chair's Remarks Section per Trade Name ---
                            st.markdown(f"<h6 style='font-size:12pt; color:#154360;'>Remarks of Chair for {html.escape(trade_name_item)}</h6>", unsafe_allow_html=True)

                            if 'chair_remarks' not in df_trade_paras_item.columns:
                                df_trade_paras_item['chair_remarks'] = ""

                            existing_chair_remark = ""
                            if not df_trade_paras_item.empty:
                                remark_val = df_trade_paras_item.iloc[0].get('chair_remarks')
                                if pd.notna(remark_val):
                                    existing_chair_remark = str(remark_val)
                            
                            chair_remark_key = f"chair_remark_input_{trade_name_item}_{session_key_selected_trade}"
                            st.text_area(
                                "Enter remarks for this assessee:",
                                value=existing_chair_remark,
                                key=chair_remark_key,
                                label_visibility="collapsed",
                                height=80
                            )
                            # --- END: Chair's Remarks Section ---
                            
                            if st.button("Save Decisions & Remarks", key=f"save_decisions_{trade_name_item}", use_container_width=True, type="primary"):
                                with st.spinner("Saving decisions and remarks..."):
                                    # Ensure columns exist in the main dataframe
                                    if 'mcm_decision' not in st.session_state.df_period_data.columns:
                                        st.session_state.df_period_data['mcm_decision'] = ""
                                    if 'chair_remarks' not in st.session_state.df_period_data.columns:
                                        st.session_state.df_period_data['chair_remarks'] = ""
                                    
                                    new_chair_remark = st.session_state.get(chair_remark_key, "")

                                    for index, row in df_trade_paras_item.iterrows():
                                        para_num_str = str(int(row["audit_para_number"])) if pd.notna(row["audit_para_number"]) and row["audit_para_number"] != 0 else "N/A"
                                        decision_key = f"mcm_decision_{trade_name_item}_{para_num_str}_{index}"
                                        selected_decision = st.session_state.get(decision_key, decision_options[0])
                                        
                                        # Update both decision and remark in the main session state dataframe
                                        st.session_state.df_period_data.loc[index, 'mcm_decision'] = selected_decision
                                        st.session_state.df_period_data.loc[index, 'chair_remarks'] = new_chair_remark
                                    
                                    success = update_spreadsheet_from_df(
                                        dbx=dbx,
                                        df_to_write=st.session_state.df_period_data,
                                        dropbox_path=MCM_DATA_PATH
                                    )
                                    
                                    if success:
                                        st.success("✅ Decisions and remarks saved successfully!")
                                        time_module.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to save. Check app logs for details.")
                            
                            st.markdown("<hr>", unsafe_allow_html=True)

                            # if st.button("Save Decisions", key=f"save_decisions_{trade_name_item}", use_container_width=True, type="primary"):
                            #     with st.spinner("Saving decisions..."):
                            #         if 'mcm_decision' not in st.session_state.df_period_data.columns:
                            #             st.session_state.df_period_data['mcm_decision'] = ""
                                    
                            #         for index, row in df_trade_paras_item.iterrows():
                            #             para_num_str = str(int(row["audit_para_number"])) if pd.notna(row["audit_para_number"]) and row["audit_para_number"] != 0 else "N/A"
                            #             decision_key = f"mcm_decision_{trade_name_item}_{para_num_str}_{index}"
                            #             selected_decision = st.session_state.get(decision_key, decision_options[0])
                            #             st.session_state.df_period_data.loc[index, 'mcm_decision'] = selected_decision
                                    
                            #         success = update_spreadsheet_from_df(
                            #             dbx=dbx,
                            #             df_to_write=st.session_state.df_period_data,
                            #             dropbox_path=MCM_DATA_PATH
                            #         )
                                    
                            #         if success:
                            #             st.success("✅ Decisions saved successfully!")
                            #         else:
                            #             st.error("❌ Failed to save decisions. Check app logs for details.")
                            
                            # st.markdown("<hr>", unsafe_allow_html=True)

    # --- Compile PDF Button ---
    if st.button("Compile Full MCM Agenda PDF", key="compile_mcm_agenda_pdf_final_v4_progress", type="primary", help="Generates a comprehensive PDF.", use_container_width=True):
        if df_period_data_full.empty:
            st.error("No data available for the selected MCM period to compile into PDF.")
        else:
            status_message_area = st.empty()
            progress_bar = st.progress(0)

            with st.spinner("Preparing for PDF compilation..."):
                final_pdf_merger = PdfWriter()
                compiled_pdf_pages_count = 0

                # Filter and sort data for PDF
                df_for_pdf = df_period_data_full.dropna(subset=['dar_pdf_path', 'trade_name', circle_col_to_use]).copy()
                df_for_pdf[circle_col_to_use] = pd.to_numeric(df_for_pdf[circle_col_to_use], errors='coerce').fillna(0).astype(int)

                # Get unique DARs, sorted for consistent processing order
                unique_dars_to_process = df_for_pdf.sort_values(by=[circle_col_to_use, 'trade_name', 'dar_pdf_path']).drop_duplicates(subset=['dar_pdf_path'])

                total_dars = len(unique_dars_to_process)

                dar_objects_for_merge_and_index = []

                if total_dars == 0:
                    status_message_area.warning("No valid DARs with PDF paths found to compile.")
                    progress_bar.empty()
                    st.stop()

                total_steps_for_pdf = 4 + (2 * total_dars)
                current_pdf_step = 0

                # Step 1: Pre-fetch DAR PDFs to count pages
                status_message_area.info(f"Pre-fetching {total_dars} DAR PDFs to count pages and prepare content...")
                for idx, dar_row in unique_dars_to_process.iterrows():
                    current_pdf_step += 1
                    dar_path_val = dar_row.get('dar_pdf_path')
                    num_pages_val = 1  # Default in case of fetch failure
                    reader_obj_val = None
                    trade_name_val = dar_row.get('trade_name', 'Unknown DAR')
                    circle_val = f"Circle {int(dar_row.get(circle_col_to_use, 0))}"

                    status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Fetching DAR for {trade_name_val}...")
                    if dar_path_val:
                        try:
                            pdf_content = download_file(dbx, dar_path_val)
                            if pdf_content:
                                fh_val = BytesIO(pdf_content)
                                reader_obj_val = PdfReader(fh_val)
                                num_pages_val = len(reader_obj_val.pages) if reader_obj_val.pages else 1
                            else:
                                st.warning(f"Failed to download PDF for {trade_name_val} at path: {dar_path_val}")
                        except Exception as e_fetch_val:
                            st.warning(f"PDF Read Error for {trade_name_val} ({dar_path_val}): {e_fetch_val}. Using placeholder.")

                    dar_objects_for_merge_and_index.append({
                        'circle': circle_val,
                        'trade_name': trade_name_val,
                        'num_pages_in_dar': num_pages_val,
                        'pdf_reader': reader_obj_val,
                        'dar_path': dar_path_val
                    })
                    progress_bar.progress(current_pdf_step / total_steps_for_pdf)

            # Now compile with progress
            try:
                # Step 2: Cover Page
                current_pdf_step += 1
                status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Cover Page...")
                cover_buffer = BytesIO()
                create_cover_page_pdf(cover_buffer, f"Audit Paras for MCM {month_year_str}", "Audit 1 Commissionerate Mumbai")
                cover_reader = PdfReader(cover_buffer)
                final_pdf_merger.append(cover_reader)
                compiled_pdf_pages_count += len(cover_reader.pages)
                progress_bar.progress(current_pdf_step / total_steps_for_pdf)

                # Step 3: High-Value Paras Table
                current_pdf_step += 1
                status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating High-Value Paras Table...")
                df_hv_data = df_period_data_full[(df_period_data_full['revenue_involved_lakhs_rs'].fillna(0) * 100000) > 500000].copy()
                df_hv_data.sort_values(by='revenue_involved_lakhs_rs', ascending=False, inplace=True)
                hv_pages_count = 0
                if not df_hv_data.empty:
                    hv_buffer = BytesIO()
                    create_high_value_paras_pdf(hv_buffer, df_hv_data)
                    hv_reader = PdfReader(hv_buffer)
                    final_pdf_merger.append(hv_reader)
                    hv_pages_count = len(hv_reader.pages)
                compiled_pdf_pages_count += hv_pages_count
                progress_bar.progress(current_pdf_step / total_steps_for_pdf)

                # Step 4: Index Page
                current_pdf_step += 1
                status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Index Page...")
                index_page_actual_start = compiled_pdf_pages_count + 1
                dar_start_page_counter_val = index_page_actual_start + 1  # After index page(s)

                index_items_list_final = []
                for item_info in dar_objects_for_merge_and_index:
                    index_items_list_final.append({
                        'circle': item_info['circle'],
                        'trade_name': item_info['trade_name'],
                        'start_page_in_final_pdf': dar_start_page_counter_val,
                        'num_pages_in_dar': item_info['num_pages_in_dar']
                    })
                    dar_start_page_counter_val += item_info['num_pages_in_dar']

                index_buffer = BytesIO()
                create_index_page_pdf(index_buffer, index_items_list_final, index_page_actual_start)
                index_reader = PdfReader(index_buffer)
                final_pdf_merger.append(index_reader)
                compiled_pdf_pages_count += len(index_reader.pages)
                progress_bar.progress(current_pdf_step / total_steps_for_pdf)

                # Step 5: Merge actual DAR PDFs
                for i, dar_detail_info in enumerate(dar_objects_for_merge_and_index):
                    current_pdf_step += 1
                    status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Merging DAR {i+1}/{total_dars} ({html.escape(dar_detail_info['trade_name'])})...")
                    if dar_detail_info['pdf_reader']:
                        final_pdf_merger.append(dar_detail_info['pdf_reader'])
                    else:  # Placeholder
                        ph_b = BytesIO()
                        ph_d = SimpleDocTemplate(ph_b, pagesize=A4)
                        ph_s = [Paragraph(f"Content for {html.escape(dar_detail_info['trade_name'])} (Path: {html.escape(dar_detail_info['dar_path'])}) failed to load.", getSampleStyleSheet()['Normal'])]
                        ph_d.build(ph_s)
                        ph_b.seek(0)
                        final_pdf_merger.append(PdfReader(ph_b))
                    progress_bar.progress(current_pdf_step / total_steps_for_pdf)

                # Step 6: Finalize PDF
                current_pdf_step += 1
                status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Finalizing PDF...")
                output_pdf_final = BytesIO()
                final_pdf_merger.write(output_pdf_final)
                output_pdf_final.seek(0)
                progress_bar.progress(1.0)
                status_message_area.success("PDF Compilation Complete!")

                dl_filename = f"MCM_Agenda_{month_year_str.replace(' ', '_')}_Compiled.pdf"
                st.download_button(label="⬇️ Download Compiled PDF Agenda", data=output_pdf_final, file_name=dl_filename, mime="application/pdf")

            except Exception as e_compile_outer:
                status_message_area.error(f"An error occurred during PDF compilation: {e_compile_outer}")
                import traceback
                st.error(traceback.format_exc())
            finally:
                
                time_module.sleep(0.5)  # Brief pause to ensure user sees final status
                status_message_area.empty()
                progress_bar.empty()
                
    # --- MCM Date Selection Section ---
    st.markdown("---")
    st.markdown("### MCM Meeting Date Selection")
    st.markdown("📅 **Please select the date when the MCM meeting was conducted for this period.**")
    
    # Create date picker with reasonable date range
    import datetime
    current_date = datetime.datetime.now()
    min_date = current_date - datetime.timedelta(days=365)  # 1 year ago
    max_date = current_date + datetime.timedelta(days=30)   # 1 month ahead
    
    # Initialize session state for MCM date if not exists
    mcm_date_key = f"mcm_date_{selected_period.replace(' ', '_')}"
    if mcm_date_key not in st.session_state:
        st.session_state[mcm_date_key] = None
    
    # Date picker with validation
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_mcm_date = st.date_input(
            "Select MCM Meeting Date:",
            value=st.session_state[mcm_date_key],
            min_value=min_date.date(),
            max_value=max_date.date(),
            key=f"mcm_date_picker_{selected_period.replace(' ', '_')}",
            help="Choose the actual date when the MCM meeting was conducted"
        )
        
        # Update session state
        if selected_mcm_date:
            st.session_state[mcm_date_key] = selected_mcm_date
    
    with col2:
        # Show formatted date
        if selected_mcm_date:
            formatted_date = selected_mcm_date.strftime("%d %B, %Y")
            st.markdown(f"""
            <div style="background-color: #d4edda; color: #155724; padding: 10px; 
                        border-radius: 5px; margin-top: 25px; text-align: center; 
                        font-weight: bold;">
                📅 {formatted_date}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #f8d7da; color: #721c24; padding: 10px; 
                        border-radius: 5px; margin-top: 25px; text-align: center; 
                        font-weight: bold;">
                ⚠️ Date Required
            </div>
            """, unsafe_allow_html=True)
    # Function to validate MCM date
    def validate_mcm_date_selection():
        """Validate if MCM date is selected before PDF generation"""
        mcm_date = st.session_state.get(mcm_date_key)
        if not mcm_date:
            st.error("⚠️ **MCM Date Required**: Please select the MCM meeting date before generating the executive summary.")
            st.info("💡 The MCM date will be displayed on the cover page of the PDF report.")
            return False
        return True


    # --- NEW: Executive Summary PDF Generation Section ---
    st.markdown("---")
    st.markdown("### Generate Executive Summary PDF")
    st.markdown("Generate a PDF summary of the minutes, enriched with infographics from the PCO dashboard.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Generate Executive Summary (Short)", use_container_width=True):
             # Validate MCM date first
            if not validate_mcm_date_selection():
                st.stop()
                
            mcm_date = st.session_state.get(mcm_date_key)
            with st.spinner("Generating Short PDF Summary... Please wait."):
                # 1. Fetch data and charts
                vital_stats, charts = get_visualization_data(dbx, selected_period)
                if not vital_stats or not charts:
                    st.error("Could not fetch visualization data to generate the report.")
                    return
                # 2. ADD MCM DATE TO VITAL STATS
                vital_stats['mcm_date'] = mcm_date.strftime("%d %B, %Y") if mcm_date else None
            
                # 2. ENHANCE with MCM detailed data for new sections
                df_mcm_current = read_from_spreadsheet(dbx, MCM_DATA_PATH)
                if df_mcm_current is not None and not df_mcm_current.empty:
                    df_mcm_filtered = df_mcm_current[df_mcm_current['mcm_period'] == selected_period].copy()
                    
                    # Prepare MCM detailed data for Section VIII
                    mcm_columns = [
                        'audit_group_number', 'gstin', 'trade_name', 'category', 
                        'audit_para_number', 'audit_para_heading', 'revenue_involved_lakhs_rs', 
                        'revenue_recovered_lakhs_rs', 'status_of_para', 'mcm_decision', 'chair_remarks'
                    ]
                    
                    # Filter for actual paras only
                    df_mcm_paras = df_mcm_filtered[
                        df_mcm_filtered['audit_para_number'].notna() & 
                        (~df_mcm_filtered['audit_para_heading'].astype(str).isin([
                            "N/A - Header Info Only (Add Paras Manually)", 
                            "Manual Entry Required", 
                            "Manual Entry - PDF Error", 
                            "Manual Entry - PDF Upload Failed"
                        ]))
                    ].copy()
                    
                    if not df_mcm_paras.empty:
                        # Ensure all required columns exist and clean data
                        for col in mcm_columns:
                            if col not in df_mcm_paras.columns:
                                df_mcm_paras[col] = ''
                        
                        # Clean and format data
                        df_mcm_paras['revenue_involved_lakhs_rs'] = pd.to_numeric(df_mcm_paras['revenue_involved_lakhs_rs'], errors='coerce').fillna(0)
                        df_mcm_paras['revenue_recovered_lakhs_rs'] = pd.to_numeric(df_mcm_paras['revenue_recovered_lakhs_rs'], errors='coerce').fillna(0)
                        df_mcm_paras['chair_remarks'] = df_mcm_paras['chair_remarks'].fillna('')
                        df_mcm_paras['mcm_decision'] = df_mcm_paras['mcm_decision'].fillna('Decision pending')
                        df_mcm_paras['status_of_para'] = df_mcm_paras['status_of_para'].fillna('Status not updated')
                        
                        # Update vital_stats with MCM data
                        vital_stats['mcm_detailed_data'] = df_mcm_paras[mcm_columns].to_dict('records')
                        
                        # Get overall remarks from periods data
                        df_periods_remarks = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
                        if df_periods_remarks is not None and 'overall_remarks' in df_periods_remarks.columns:
                            try:
                                month_name, year_str = selected_period.split(" ")
                                year_val = int(year_str)
                                period_row = df_periods_remarks[
                                    (df_periods_remarks['month_name'] == month_name) & 
                                    (df_periods_remarks['year'] == year_val)
                                ]
                                if not period_row.empty:
                                    overall_remarks = period_row.iloc[0].get('overall_remarks', '')
                                    if pd.notna(overall_remarks):
                                        vital_stats['overall_remarks'] = overall_remarks
                            except:
                                pass
                
                # 3. Convert Plotly charts to images in memory
                chart_images = [BytesIO(chart.to_image(format="svg", width=520, height=300)) for chart in charts]
    
                # 4. Generate PDF (THIS WILL NOW INCLUDE THE NEW SECTIONS AUTOMATICALLY)
                report_generator = PDFReportGenerator(
                    selected_period=selected_period,
                    vital_stats=vital_stats,
                    chart_images=chart_images
                )
                pdf_bytes = report_generator.run(detailed=False)  # Short version
    
                # 5. Provide Download Link
                st.download_button(
                    label="⬇️ Download Short Summary PDF",
                    data=pdf_bytes,
                    file_name=f"MCM_Executive_Summary_Short_{selected_period.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("Enhanced short summary PDF is ready for download!")
    
    # SIMILARLY UPDATE THE DETAILED BUTTON:
    
    with col2:
        if st.button("📑 Generate Executive Summary (Detailed)", use_container_width=True, type="primary"):
             # Validate MCM date first
            if not validate_mcm_date_selection():
                st.stop()
                
            mcm_date = st.session_state.get(mcm_date_key)
            with st.spinner("Generating Detailed PDF Summary... This may take a moment."):
                # 1. Fetch data and charts  
                vital_stats, charts = get_visualization_data(dbx, selected_period)
                if not vital_stats or not charts:
                    st.error("Could not fetch visualization data to generate the report.")
                    return
                 # 2. ADD MCM DATE TO VITAL STATS
                vital_stats['mcm_date'] = mcm_date.strftime("%d %B, %Y") if mcm_date else None
            
                # 2. ENHANCE with MCM detailed data (same as above)
                df_mcm_current = read_from_spreadsheet(dbx, MCM_DATA_PATH)
                if df_mcm_current is not None and not df_mcm_current.empty:
                    df_mcm_filtered = df_mcm_current[df_mcm_current['mcm_period'] == selected_period].copy()
                    
                    mcm_columns = [
                        'audit_group_number', 'gstin', 'trade_name', 'category', 
                        'audit_para_number', 'audit_para_heading', 'revenue_involved_lakhs_rs', 
                        'revenue_recovered_lakhs_rs', 'status_of_para', 'mcm_decision', 'chair_remarks'
                    ]
                    
                    df_mcm_paras = df_mcm_filtered[
                        df_mcm_filtered['audit_para_number'].notna() & 
                        (~df_mcm_filtered['audit_para_heading'].astype(str).isin([
                            "N/A - Header Info Only (Add Paras Manually)", 
                            "Manual Entry Required", 
                            "Manual Entry - PDF Error", 
                            "Manual Entry - PDF Upload Failed"
                        ]))
                    ].copy()
                    
                    if not df_mcm_paras.empty:
                        for col in mcm_columns:
                            if col not in df_mcm_paras.columns:
                                df_mcm_paras[col] = ''
                        
                        df_mcm_paras['revenue_involved_lakhs_rs'] = pd.to_numeric(df_mcm_paras['revenue_involved_lakhs_rs'], errors='coerce').fillna(0)
                        df_mcm_paras['revenue_recovered_lakhs_rs'] = pd.to_numeric(df_mcm_paras['revenue_recovered_lakhs_rs'], errors='coerce').fillna(0)
                        df_mcm_paras['chair_remarks'] = df_mcm_paras['chair_remarks'].fillna('')
                        df_mcm_paras['mcm_decision'] = df_mcm_paras['mcm_decision'].fillna('Decision pending')
                        df_mcm_paras['status_of_para'] = df_mcm_paras['status_of_para'].fillna('Status not updated')
                        
                        vital_stats['mcm_detailed_data'] = df_mcm_paras[mcm_columns].to_dict('records')
                        
                        df_periods_remarks = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
                        if df_periods_remarks is not None and 'overall_remarks' in df_periods_remarks.columns:
                            try:
                                month_name, year_str = selected_period.split(" ")
                                year_val = int(year_str)
                                period_row = df_periods_remarks[
                                    (df_periods_remarks['month_name'] == month_name) & 
                                    (df_periods_remarks['year'] == year_val)
                                ]
                                if not period_row.empty:
                                    overall_remarks = period_row.iloc[0].get('overall_remarks', '')
                                    if pd.notna(overall_remarks):
                                        vital_stats['overall_remarks'] = overall_remarks
                            except:
                                pass
    
                # 3. Convert Plotly charts to images in memory
                chart_images = [BytesIO(chart.to_image(format="png", scale=2)) for chart in charts]
    
                # 4. Generate PDF (THIS WILL NOW INCLUDE THE NEW SECTIONS AUTOMATICALLY)
                report_generator = PDFReportGenerator(
                    selected_period=selected_period,
                    vital_stats=vital_stats,
                    chart_images=chart_images
                )
                pdf_bytes = report_generator.run(detailed=True)  # Detailed version
    
                # 5. Provide Download Link
                st.download_button(
                    label="⬇️ Download Detailed Summary PDF",
                    data=pdf_bytes,
                    file_name=f"MCM_Executive_Summary_Detailed_{selected_period.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("Enhanced detailed summary PDF is ready for download!")
    # with col1:
    #     if st.button("📄 Generate Executive Summary (Short)", use_container_width=True):
    #         with st.spinner("Generating Short PDF Summary... Please wait."):
    #             # 1. Fetch data and charts
    #             vital_stats, charts = get_visualization_data(dbx, selected_period)
    #             if not vital_stats or not charts:
    #                 st.error("Could not fetch visualization data to generate the report.")
    #                 return
    #             ############  Debug the data structure Added may be reomoved 
    #             ttd = vital_stats.get('top_taxpayers_data', {})
    #             print(f"Top taxpayers data type: {type(ttd)}")
    #             for key in ['top_detection', 'top_recovery']:
    #                 data = ttd.get(key, [])
    #                 print(f"{key}: type={type(data)}, length={len(data) if hasattr(data, '__len__') else 'no length'}")
    #                 if hasattr(data, 'to_dict'):
    #                     print(f"  WARNING: {key} is still a DataFrame!")
    #             ####################
    #             # 2. Convert Plotly charts to images in memory
    #             # AFTER
    #             #chart_images = [BytesIO(chart.to_image(format="svg")) for chart in charts]
    #             #chart_images = [BytesIO(chart.to_image(format="svg", width=720, height=450)) for chart in charts]
    #             chart_images = [BytesIO(chart.to_image(format="svg", width=520, height=300)) for chart in charts]
    #             #chart_images = [BytesIO(chart.to_image(format="png", scale=2)) for chart in charts]
    
    #             # 3. Generate PDF
    #             report_generator = PDFReportGenerator(
    #                 selected_period=selected_period,
    #                 vital_stats=vital_stats,
    #                 chart_images=chart_images
    #             )
    #             pdf_bytes = report_generator.run(detailed=False)
    
    #             # 4. Provide Download Link
    #             st.download_button(
    #                 label="⬇️ Download Short Summary PDF",
    #                 data=pdf_bytes,
    #                 file_name=f"MCM_Executive_Summary_Short_{selected_period.replace(' ', '_')}.pdf",
    #                 mime="application/pdf",
    #                 use_container_width=True
    #             )
    #             st.success("Short summary PDF is ready for download!")
    
    # with col2:
    #     if st.button("📑 Generate Executive Summary (Detailed)", use_container_width=True, type="primary"):
    #         with st.spinner("Generating Detailed PDF Summary... This may take a moment."):
    #             # 1. Fetch data and charts
    #             vital_stats, charts = get_visualization_data(dbx, selected_period)
    #             if not vital_stats or not charts:
    #                 st.error("Could not fetch visualization data to generate the report.")
    #                 return
    
    #             # 2. Convert Plotly charts to images in memory
    #             chart_images = [BytesIO(chart.to_image(format="png", scale=2)) for chart in charts]
    
    #             # 3. Generate PDF
    #             report_generator = PDFReportGenerator(
    #                 selected_period=selected_period,
    #                 vital_stats=vital_stats,
    #                 chart_images=chart_images
    #             )
    #             pdf_bytes = report_generator.run(detailed=True)
    
    #             # 4. Provide Download Link
    #             st.download_button(
    #                 label="⬇️ Download Detailed Summary PDF",
    #                 data=pdf_bytes,
    #                 file_name=f"MCM_Executive_Summary_Detailed_{selected_period.replace(' ', '_')}.pdf",
    #                 mime="application/pdf",
    #                 use_container_width=True
    #             )
    #             st.success("Detailed summary PDF is ready for download!")
# # ui_mcm_agenda.py
# import streamlit as st
# import pandas as pd
# import html
# from io import BytesIO
# import time

# # PDF manipulation libraries
# from reportlab.lib.pagesizes import A4
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.enums import TA_CENTER
# from reportlab.lib import colors
# from reportlab.lib.units import inch
# from PyPDF2 import PdfWriter, PdfReader

# # Dropbox-based imports
# from dropbox_utils import read_from_spreadsheet, download_file, update_spreadsheet_from_df
# from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH

# # --- Helper Functions (Identical to your original file) ---

# def format_inr(n):
#     """Formats a number into the Indian numbering system."""
#     try:
#         n = float(n)
#         if pd.isna(n): return "0"
#         n = int(n)
#     except (ValueError, TypeError):
#         return "0"
    
#     s = str(n)
#     if n < 0: return '-' + format_inr(-n)
#     if len(s) <= 3: return s
    
#     last_three = s[-3:]
#     other_digits = s[:-3]
#     groups = []
#     while len(other_digits) > 2:
#         groups.append(other_digits[-2:])
#         other_digits = other_digits[:-2]
#     if other_digits:
#         groups.append(other_digits)
    
#     return ','.join(reversed(groups)) + ',' + last_three

# def create_cover_page_pdf(buffer, title_text, subtitle_text):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch)
#     styles = getSampleStyleSheet()
#     story = []
#     title_style = ParagraphStyle('Title', parent=styles['h1'], fontSize=28, alignment=TA_CENTER, spaceAfter=0.3*inch, textColor=colors.HexColor("#dc3545"))
#     story.append(Paragraph(title_text, title_style))
#     story.append(Spacer(1, 0.3*inch))
#     subtitle_style = ParagraphStyle('Subtitle', parent=styles['h2'], fontSize=16, alignment=TA_CENTER)
#     story.append(Paragraph(subtitle_text, subtitle_style))
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# def create_index_page_pdf(buffer, index_data_list):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
#     styles = getSampleStyleSheet()
#     story = [Paragraph("<b>Index of DARs</b>", styles['h1']), Spacer(1, 0.2*inch)]
#     table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Start Page</b>", styles['Normal'])]]
    
#     for item in index_data_list:
#         table_data.append([
#             Paragraph(str(item['circle']), styles['Normal']),
#             Paragraph(html.escape(item['trade_name']), styles['Normal']),
#             Paragraph(str(item['start_page']), styles['Normal'])
#         ])
    
#     index_table = Table(table_data, colWidths=[1.5*inch, 4*inch, 1.5*inch])
#     index_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)
#     ]))
#     story.append(index_table)
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# def create_high_value_paras_pdf(buffer, df_high_value_paras):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
#     styles = getSampleStyleSheet()
#     story = [Paragraph("<b>High-Value Audit Paras (> ₹5 Lakhs Detection)</b>", styles['h1']), Spacer(1, 0.2*inch)]
    
#     table_data = [[Paragraph(f"<b>{col}</b>", styles['Normal']) for col in ["Audit Group", "Para No.", "Para Title", "Detected (₹)", "Recovered (₹)"]]]
    
#     for _, row in df_high_value_paras.iterrows():
#         detected_val = row.get('revenue_involved_lakhs_rs', 0) * 100000
#         recovered_val = row.get('revenue_recovered_lakhs_rs', 0) * 100000
#         table_data.append([
#             Paragraph(str(row.get("audit_group_number", "N/A")), styles['Normal']),
#             Paragraph(str(row.get("audit_para_number", "N/A")), styles['Normal']),
#             Paragraph(html.escape(str(row.get("audit_para_heading", "N/A"))[:100]), styles['Normal']),
#             Paragraph(format_inr(detected_val), styles['Normal']),
#             Paragraph(format_inr(recovered_val), styles['Normal'])
#         ])
        
#     hv_table = Table(table_data, colWidths=[1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch])
#     hv_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)
#     ]))
#     story.append(hv_table)
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# # --- Main Tab Function ---
# def mcm_agenda_tab(dbx):
#     st.markdown("### MCM Agenda Preparation")
    
#     df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if df_periods.empty:
#         st.warning("No MCM periods found."); return
        
#     period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
#     selected_period = st.selectbox("Select MCM Period for Agenda", options=period_options)

#     if not selected_period: return

#     month_year_str = selected_period
#     st.markdown(f"#### MCM Audit Paras for {month_year_str}")
#     st.markdown("---")
    
#     if 'mcm_agenda_df' not in st.session_state or st.session_state.get('mcm_agenda_period') != selected_period:
#         with st.spinner(f"Loading data for {month_year_str}..."):
#             df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#             df_all_data.reset_index(inplace=True) 
#             df_period = df_all_data[df_all_data['mcm_period'] == selected_period].copy()
#             st.session_state.mcm_agenda_df = df_period
#             st.session_state.mcm_agenda_period = selected_period

#     df_period_data = st.session_state.mcm_agenda_df

#     if df_period_data.empty:
#         st.info(f"No data found for {month_year_str}."); return

#     for circle_num in sorted(df_period_data['audit_circle_number'].dropna().unique()):
#         with st.expander(f"Audit Circle {int(circle_num)}"):
#             df_circle = df_period_data[df_period_data['audit_circle_number'] == circle_num]
#             group_tabs = st.tabs([f"Audit Group {int(g)}" for g in sorted(df_circle['audit_group_number'].unique())])

#             for i, group_num in enumerate(sorted(df_circle['audit_group_number'].unique())):
#                 with group_tabs[i]:
#                     df_group = df_circle[df_circle['audit_group_number'] == group_num]
#                     for trade_name in sorted(df_group['trade_name'].unique()):
#                         df_trade = df_group[df_group['trade_name'] == trade_name]
                        
#                         c1, c2 = st.columns([0.7, 0.3])
#                         pdf_path = df_trade['dar_pdf_path'].iloc[0]
#                         if c1.button(trade_name, key=f"btn_{trade_name}_{group_num}", use_container_width=True):
#                             st.session_state[f"show_{trade_name}_{group_num}"] = not st.session_state.get(f"show_{trade_name}_{group_num}", False)
                        
#                         if pd.notna(pdf_path):
#                             c2.link_button("View DAR PDF", f"https://www.dropbox.com/home{pdf_path.replace(' ', '%20')}", use_container_width=True)

#                         if st.session_state.get(f"show_{trade_name}_{group_num}", False):
#                             with st.container(border=True):
#                                 gstin = df_trade['gstin'].iloc[0]; category = df_trade['category'].iloc[0]
#                                 cat_color_map = {"Large": ("#f8d7da", "#721c24"), "Medium": ("#ffeeba", "#856404"), "Small": ("#d4edda", "#155724")}
#                                 cat_bg, cat_text = cat_color_map.get(category, ("#e2e3e5", "#383d41"))

#                                 info_cols = st.columns(2)
#                                 info_cols[0].markdown(f"""<div style="background-color:{cat_bg};color:{cat_text};padding:4px 8px;border-radius:5px;text-align:center;"><b>Category:</b> {html.escape(str(category))}</div>""", unsafe_allow_html=True)
#                                 info_cols[1].markdown(f"""<div style="background-color:#e9ecef;color:#495057;padding:4px 8px;border-radius:5px;text-align:center;"><b>GSTIN:</b> {html.escape(str(gstin))}</div>""", unsafe_allow_html=True)

#                                 st.markdown(f"<h5 style='margin-top:20px;'>Gist of Audit Paras & MCM Decisions</h5>", unsafe_allow_html=True)
                                
#                                 # --- RESTORED: Custom CSS grid layout ---
#                                 st.markdown("""<style>.grid-header{font-weight:bold;background-color:#343a40;color:white;padding:10px 5px;border-radius:5px;text-align:center;}.cell-style{padding:8px 5px;margin:1px;border-radius:5px;}.title-cell{text-align:left;padding-left:10px;background-color:#f0f2f6;}.revenue-cell{font-weight:bold;text-align:right!important;background-color:#e8f5e9;}.status-cell{font-weight:bold;text-align:center;background-color:#e3f2fd;}.total-row{font-weight:bold;padding-top:10px;}</style>""", unsafe_allow_html=True)
#                                 col_props = (0.9, 5, 1.5, 1.5, 1.8, 2.5)
#                                 headers = ['Para No.', 'Para Title', 'Detection (₹)', 'Recovery (₹)', 'Status', 'MCM Decision']
#                                 header_cols = st.columns(col_props)
#                                 for col, h in zip(header_cols, headers):
#                                     col.markdown(f"<div class='grid-header'>{h}</div>", unsafe_allow_html=True)

#                                 total_det, total_rec = 0, 0
#                                 for original_index, row in df_trade.iterrows():
#                                     with st.container():
#                                         para_num = int(row["audit_para_number"]) if pd.notna(row["audit_para_number"]) else "N/A"
#                                         det_rs = row.get('revenue_involved_lakhs_rs', 0) * 100000; total_det += det_rs
#                                         rec_rs = row.get('revenue_recovered_lakhs_rs', 0) * 100000; total_rec += rec_rs
                                        
#                                         row_cols = st.columns(col_props)
#                                         row_cols[0].markdown(f"<div class='cell-style'>{para_num}</div>", unsafe_allow_html=True)
#                                         row_cols[1].markdown(f"<div class='cell-style title-cell'>{html.escape(str(row.get('audit_para_heading')))}</div>", unsafe_allow_html=True)
#                                         row_cols[2].markdown(f"<div class='cell-style revenue-cell'>{format_inr(det_rs)}</div>", unsafe_allow_html=True)
#                                         row_cols[3].markdown(f"<div class='cell-style revenue-cell'>{format_inr(rec_rs)}</div>", unsafe_allow_html=True)
#                                         row_cols[4].markdown(f"<div class='cell-style status-cell'>{html.escape(str(row.get('status_of_para')))}</div>", unsafe_allow_html=True)

#                                         options = ['Select a decision', 'Para closed since recovered', 'Para deferred', 'Para to be pursued else issue SCN']
#                                         current = row.get('mcm_decision'); current = current if pd.notna(current) and current in options else options[0]
#                                         sel_decision = row_cols[5].selectbox("Decision", options=options, index=options.index(current), key=f"dec_{row['index']}", label_visibility="collapsed")
                                        
#                                         if sel_decision != current:
#                                             st.session_state.mcm_agenda_df.loc[st.session_state.mcm_agenda_df['index'] == row['index'], 'mcm_decision'] = sel_decision
#                                             st.rerun()
                                
#                                 st.markdown("---")
#                                 total_cols = st.columns(col_props)
#                                 total_cols[1].markdown("<div class='total-row' style='text-align:right;'>Total of Paras</div>", unsafe_allow_html=True)
#                                 total_cols[2].markdown(f"<div class='total-row revenue-cell cell-style'>{format_inr(total_det)}</div>", unsafe_allow_html=True)
#                                 total_cols[3].markdown(f"<div class='total-row revenue-cell cell-style'>{format_inr(total_rec)}</div>", unsafe_allow_html=True)
#                                 st.markdown("<br>", unsafe_allow_html=True)
                                
#                                 detection_style = "background-color: #f8d7da; color: #721c24; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 1.1em;"
#                                 recovery_style = "background-color: #d4edda; color: #155724; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 1.1em;"
#                                 st.markdown(f"<p style='{detection_style}'>Total Overall Detection for {html.escape(trade_name)}: ₹ {format_inr(df_trade['total_amount_detected_overall_rs'].iloc[0])}</p>", unsafe_allow_html=True)
#                                 st.markdown(f"<p style='{recovery_style}'>Total Overall Recovery for {html.escape(trade_name)}: ₹ {format_inr(df_trade['total_amount_recovered_overall_rs'].iloc[0])}</p>", unsafe_allow_html=True)

#     if st.button("Save All Decisions", type="primary"):
#         with st.spinner("Saving decisions..."):
#             df_master = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#             if 'mcm_decision' not in df_master.columns: df_master['mcm_decision'] = ""
#             update_data = st.session_state.mcm_agenda_df.set_index('index')[['mcm_decision']]
#             df_master.update(update_data)
#             if update_spreadsheet_from_df(dbx, df_master, MCM_DATA_PATH):
#                 st.success("Decisions saved!")
#             else:
#                 st.error("Failed to save decisions.")

#     st.markdown("---")
#     if st.button("Compile Full MCM Agenda PDF", use_container_width=True):
#         with st.spinner("Compiling PDF Agenda..."):
#             final_merger = PdfWriter()
            
#             cover_buf = BytesIO(); create_cover_page_pdf(cover_buf, f"MCM Agenda: {month_year_str}", "Audit-I Commissionerate"); final_merger.append(PdfReader(cover_buf))
            
#             df_hv = df_period_data[df_period_data['revenue_involved_lakhs_rs'] * 100000 > 500000]
#             if not df_hv.empty:
#                 hv_buf = BytesIO(); create_high_value_paras_pdf(hv_buf, df_hv); final_merger.append(PdfReader(hv_buf))

#             df_pdf = df_period_data.dropna(subset=['dar_pdf_path', 'trade_name', 'audit_circle_number']).drop_duplicates(subset=['dar_pdf_path']).sort_values(by=['audit_circle_number', 'trade_name'])
#             index_data, readers, current_page = [], {}, len(final_merger.pages) + 2
            
#             prog_bar = st.progress(0, text="Downloading DAR PDFs...")
#             for i, (_, row) in enumerate(df_pdf.iterrows()):
#                 content = download_file(dbx, row['dar_pdf_path'])
#                 if content: readers[row['dar_pdf_path']] = PdfReader(BytesIO(content))
#                 prog_bar.progress((i + 1) / len(df_pdf), text=f"Downloading... ({i+1}/{len(df_pdf)})")

#             for _, row in df_pdf.iterrows():
#                 reader = readers.get(row['dar_pdf_path'])
#                 pages = len(reader.pages) if reader else 0
#                 index_data.append({'circle': f"Circle {int(row['audit_circle_number'])}", 'trade_name': row['trade_name'], 'start_page': current_page})
#                 current_page += pages
            
#             index_buf = BytesIO(); create_index_page_pdf(index_buf, index_data); final_merger.append(PdfReader(index_buf))
            
#             prog_bar.progress(0, text="Merging PDFs...")
#             for i, (_, row) in enumerate(df_pdf.iterrows()):
#                 if readers.get(row['dar_pdf_path']): final_merger.append(readers[row['dar_pdf_path']])
#                 prog_bar.progress((i + 1) / len(df_pdf), text=f"Merging... ({i+1}/{len(df_pdf)})")

#             output_pdf_bytes = BytesIO()
#             final_merger.write(output_pdf_bytes)
#             output_pdf_bytes.seek(0)
#             prog_bar.empty()
#             st.success("PDF Compilation Complete!")
#             st.download_button("⬇️ Download Compiled PDF Agenda", data=output_pdf_bytes, file_name=f"MCM_Agenda_{month_year_str.replace(' ', '_')}.pdf", mime="application/pdf")
