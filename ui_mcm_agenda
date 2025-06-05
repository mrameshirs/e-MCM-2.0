# ui_mcm_agenda.py
import streamlit as st
import pandas as pd
import datetime
import math
from io import BytesIO
import requests # For fetching PDFs if URLs are direct http/https
from urllib.parse import urlparse, parse_qs

# PDF manipulation libraries
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import inch
from PyPDF2 import PdfWriter, PdfReader # Using PyPDF2

from google_utils import read_from_spreadsheet
from googleapiclient.http import MediaIoBaseDownload

# Helper function to extract File ID from Google Drive webViewLink (from previous response)
def get_file_id_from_drive_url(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    parsed_url = urlparse(url)
    if 'drive.google.com' in parsed_url.netloc:
        if '/file/d/' in parsed_url.path:
            try:
                return parsed_url.path.split('/file/d/')[1].split('/')[0]
            except IndexError:
                return None
        query_params = parse_qs(parsed_url.query)
        if 'id' in query_params:
            return query_params['id'][0]
    return None

# --- PDF Generation Functions (from previous response, ensure they are complete) ---
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

def create_index_page_pdf(buffer, index_data_list, start_page_offset):
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("<b>Index of DARs</b>", styles['h1']))
    story.append(Spacer(1, 0.2*inch))

    table_data = [
        [Paragraph("<b>Audit Circle</b>", styles['Normal']), 
         Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), 
         Paragraph("<b>Page No.</b>", styles['Normal'])]
    ]
    current_page_in_pdf = start_page_offset
    for item in index_data_list:
        table_data.append([
            Paragraph(str(item['circle']), styles['Normal']),
            Paragraph(item['trade_name'], styles['Normal']),
            Paragraph(str(current_page_in_pdf), styles['Normal'])
        ])
        current_page_in_pdf += item.get('num_pages_in_dar', 1) # Add pages of this DAR

    col_widths = [1.5*inch, 4*inch, 1.5*inch]
    index_table = Table(table_data, colWidths=col_widths)
    index_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(index_table)
    doc.build(story)
    buffer.seek(0)
    return buffer

def create_high_value_paras_pdf(buffer, df_high_value_paras_data): # Renamed input variable
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("<b>High-Value Audit Paras (> 5 Lakhs Detection)</b>", styles['h1']))
    story.append(Spacer(1, 0.2*inch))

    table_data_hv = [
        [Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
         Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (Rs)</b>", styles['Normal']),
         Paragraph("<b>Recovered (Rs)</b>", styles['Normal'])]
    ]
    for _, row_hv in df_high_value_paras_data.iterrows():
        table_data_hv.append([
            Paragraph(str(row_hv.get("Audit Group Number", "N/A")), styles['Normal']),
            Paragraph(str(row_hv.get("Audit Para Number", "N/A")), styles['Normal']),
            Paragraph(str(row_hv.get("Audit Para Heading", "N/A"))[:100], styles['Normal']),
            Paragraph(f"{row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal']),
            Paragraph(f"{row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal'])])
    
    col_widths_hv = [1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch]
    hv_table = Table(table_data_hv, colWidths=col_widths_hv)
    hv_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (3,1), (-1,-1), 'RIGHT'), # Align amounts right
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,1), (-1,-1), 4),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(hv_table)
    doc.build(story)
    buffer.seek(0)
    return buffer
# --- End PDF Generation Functions ---

def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
    st.markdown("### MCM Agenda Preparation")

    if not mcm_periods:
        st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
        return

    period_options = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if v.get('month_name') and v.get('year')}
    if not period_options:
        st.warning("No valid MCM periods with complete month and year information available.")
        return

    selected_period_key = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), format_func=lambda k: period_options[k], key="mcm_agenda_period_select_final")

    if not selected_period_key:
        st.info("Please select an MCM period.")
        return

    selected_period_info = mcm_periods[selected_period_key]
    month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
    st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 24pt;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
    st.markdown("---")

    df_period_data = pd.DataFrame()
    if sheets_service and selected_period_info.get('spreadsheet_id'):
        with st.spinner(f"Loading data for {month_year_str}..."):
            df_period_data = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])
    
    if df_period_data is None or df_period_data.empty:
        st.info(f"No data found in the spreadsheet for {month_year_str}.")
    else:
        numeric_cols = ['Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)', 
                        'Total Amount Recovered (Overall Rs)', 'Audit Para Number', 
                        'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
        for col in numeric_cols:
            if col in df_period_data.columns:
                df_period_data[col] = pd.to_numeric(df_period_data[col], errors='coerce')

        if 'Audit Circle Number' not in df_period_data.columns or not df_period_data['Audit Circle Number'].notna().any() or not pd.to_numeric(df_period_data['Audit Circle Number'], errors='coerce').notna().any():
            if 'Audit Group Number' in df_period_data.columns and df_period_data['Audit Group Number'].notna().any():
                df_period_data['Audit Circle Number'] = df_period_data['Audit Group Number'].apply(calculate_audit_circle).fillna(0).astype(int)
                st.caption("Derived 'Audit Circle Number' as it was missing or invalid in the sheet.")
            else:
                df_period_data['Audit Circle Number'] = 0 
                st.warning("'Audit Circle Number' could not be determined.")
        else:
             df_period_data['Audit Circle Number'] = pd.to_numeric(df_period_data['Audit Circle Number'], errors='coerce').fillna(0).astype(int)

        # Vertical collapsible tabs for Audit Circles
        for circle_num in range(1, 11):
            circle_label = f"Audit Circle {circle_num}"
            df_circle_data = df_period_data[df_period_data['Audit Circle Number'] == circle_num]

            # Styled header for the expander
            st.markdown(f"""
            <div style='
                background-color: #007bff; color: white; padding: 10px; 
                border-radius: 5px; margin-top: 10px; margin-bottom: 2px;
                font-weight: bold; font-size: 16pt;
            '>
                {circle_label}
            </div>""", unsafe_allow_html=True)
            
            with st.expander(f"View Details for {circle_label}", expanded=False):
                if df_circle_data.empty:
                    st.write(f"No data for {circle_label} in this MCM period.")
                    continue

                group_labels_in_circle = []
                group_dfs_in_circle = []
                min_group_in_circle = (circle_num - 1) * 3 + 1
                max_group_in_circle = circle_num * 3

                for grp_num in range(min_group_in_circle, max_group_in_circle + 1):
                    df_group_data = df_circle_data[df_circle_data['Audit Group Number'] == grp_num]
                    if not df_group_data.empty:
                        group_labels_in_circle.append(f"Audit Group {grp_num}")
                        group_dfs_in_circle.append(df_group_data)
                
                if not group_labels_in_circle:
                    st.write(f"No specific audit group data found within {circle_label}.")
                    continue

                # Horizontal tabs for Audit Groups
                # Note: Styling st.tabs hover effect needs global CSS targeting .stTabs
                group_st_tabs_widgets = st.tabs(group_labels_in_circle)

                for i, group_tab_content in enumerate(group_st_tabs_widgets):
                    with group_tab_content:
                        df_current_group_agenda = group_dfs_in_circle[i]
                        unique_trade_names_agenda = df_current_group_agenda['Trade Name'].dropna().unique()

                        if not unique_trade_names_agenda.any():
                            st.write("No trade names with DARs found for this group.")
                            continue
                        
                        st.markdown(f"**DARs by Trade Name for {group_labels_in_circle[i]}:**", unsafe_allow_html=True)
                        
                        selected_trade_key = f"selected_trade_{circle_num}_{group_labels_in_circle[i]}"

                        for tn_idx, trade_name_agenda in enumerate(unique_trade_names_agenda):
                            trade_button_key = f"trade_btn_{circle_num}_{group_labels_in_circle[i].replace(' ','_')}_{tn_idx}"
                            if st.button(f"{trade_name_agenda}", key=trade_button_key, help=f"Show paras for {trade_name_agenda}"):
                                st.session_state[selected_trade_key] = trade_name_agenda
                            
                            if st.session_state.get(selected_trade_key) == trade_name_agenda:
                                st.markdown(f"<h5 style='font-size:14pt; margin-top:10px;'>Gist of Audit Paras for: {trade_name_agenda}</h5>", unsafe_allow_html=True)
                                df_trade_paras_agenda = df_current_group_agenda[df_current_group_agenda['Trade Name'] == trade_name_agenda]
                                
                                html_table = """
                                <style>
                                    .paras-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 11pt; }
                                    .paras-table th, .paras-table td { border: 1px solid #ddd; padding: 6px; text-align: left; }
                                    .paras-table th { background-color: #343a40; color: white; font-size: 12pt; }
                                    .paras-table tr:nth-child(even) { background-color: #f2f2f2; }
                                    .amount-col { text-align: right !important; }
                                </style>
                                <table class='paras-table'>
                                    <tr><th>Para No.</th><th>Para Title</th><th>Detection (Rs)</th><th>Recovery (Rs)</th><th>Status</th></tr>
                                """
                                total_detection_tn = 0
                                total_recovery_tn = 0

                                for _, para_row_agenda in df_trade_paras_agenda.iterrows():
                                    detection_rs_val = para_row_agenda.get('Revenue Involved (Lakhs Rs)', 0) * 100000 if pd.notna(para_row_agenda.get('Revenue Involved (Lakhs Rs)')) else 0
                                    recovery_rs_val = para_row_agenda.get('Revenue Recovered (Lakhs Rs)', 0) * 100000 if pd.notna(para_row_agenda.get('Revenue Recovered (Lakhs Rs)')) else 0
                                    total_detection_tn += detection_rs_val
                                    total_recovery_tn += recovery_rs_val
                                    
                                    html_table += f"""
                                    <tr>
                                        <td>{para_row_agenda.get('Audit Para Number', 'N/A')}</td>
                                        <td>{para_row_agenda.get('Audit Para Heading', 'N/A')}</td>
                                        <td class='amount-col'>{detection_rs_val:,.0f}</td>
                                        <td class='amount-col'>{recovery_rs_val:,.0f}</td>
                                        <td>{para_row_agenda.get('Status of para', 'N/A')}</td>
                                    </tr>"""
                                html_table += "</table>"
                                st.markdown(html_table, unsafe_allow_html=True)
                                st.markdown(f"**Total Detection for {trade_name_agenda}: Rs. {total_detection_tn:,.0f}**")
                                st.markdown(f"**Total Recovery for {trade_name_agenda}: Rs. {total_recovery_tn:,.0f}**")
                                st.markdown("<hr style='border-top: 1px solid #ccc;'>", unsafe_allow_html=True)
        
        st.markdown("---")
        # --- Compile PDF Button ---
        if st.button("Compile DARs into PDF", key="compile_mcm_agenda_pdf_btn", type="primary", use_container_width=True):
            if df_period_data.empty:
                st.error("No data loaded for the selected MCM period to compile PDF.")
            else:
                with st.spinner("Compiling PDF... This may take a while for many DARs."):
                    try:
                        final_pdf_buffer = BytesIO()
                        pdf_writer = PdfWriter()

                        # 1. Cover Page
                        cover_buffer_io = BytesIO()
                        title_text_cover = f"Audit Paras for the MCM {month_year_str}"
                        subtitle_text_cover = "Audit 1 Commissionerate Mumbai" # Customize as needed
                        create_cover_page_pdf(cover_buffer_io, title_text_cover, subtitle_text_cover)
                        cover_pdf = PdfReader(cover_buffer_io)
                        pdf_writer.add_page(cover_pdf.pages[0])
                        
                        current_page_offset_for_index = len(pdf_writer.pages) # Page number where index will start

                        # Prepare data for index and high-value table
                        df_for_pdf = df_period_data.dropna(subset=['DAR PDF URL', 'Trade Name', 'Audit Circle Number']).copy()
                        df_for_pdf['Audit Circle Number'] = pd.to_numeric(df_for_pdf['Audit Circle Number'], errors='coerce').fillna(0).astype(int)

                        index_items_list = []
                        dar_pdf_objects_for_merge = [] # Store (trade_name, circle, pdf_reader_object)
                        processed_urls_for_index = set()

                        # Pre-fetch DARs to count pages and prepare for merging
                        dar_page_count_map = {}
                        if drive_service:
                            for idx_dar, dar_row_info in df_for_pdf.iterrows():
                                dar_url = dar_row_info.get('DAR PDF URL')
                                if pd.notna(dar_url) and dar_url not in dar_page_count_map: # Process each URL once
                                    file_id_dar = get_file_id_from_drive_url(dar_url)
                                    if file_id_dar:
                                        try:
                                            req_dar = drive_service.files().get_media(fileId=file_id_dar)
                                            fh_dar_content = BytesIO(); MediaIoBaseDownload(fh_dar_content, req_dar).next_chunk()
                                            fh_dar_content.seek(0)
                                            dar_reader_obj = PdfReader(fh_dar_content)
                                            dar_page_count_map[dar_url] = len(dar_reader_obj.pages)
                                            dar_pdf_objects_for_merge.append({
                                                'circle': dar_row_info.get('Audit Circle Number'),
                                                'trade_name': dar_row_info.get('Trade Name'),
                                                'dar_url': dar_url, # For ordering if needed
                                                'pdf_reader': dar_reader_obj,
                                                'num_pages': len(dar_reader_obj.pages)
                                            })
                                        except Exception as e_fetch:
                                            st.warning(f"Failed to fetch/read PDF {dar_url}: {e_fetch}")
                                            dar_page_count_map[dar_url] = 1 # Default to 1 page on error for index
                                            dar_pdf_objects_for_merge.append({'circle': dar_row_info.get('Audit Circle Number'), 'trade_name': dar_row_info.get('Trade Name'), 'dar_url': dar_url, 'pdf_reader': None, 'num_pages': 1})
                                    else: dar_page_count_map[dar_url] = 1 # Default if no valid ID

                        # Sort dar_pdf_objects_for_merge by circle then trade name for consistent ordering
                        dar_pdf_objects_for_merge.sort(key=lambda x: (x['circle'], x['trade_name']))
                        
                        # Generate index items based on pre-fetched DARs
                        page_counter_for_index = current_page_offset_for_index + 2 # Account for index page itself + HV table page (approx)
                        for dar_info in dar_pdf_objects_for_merge:
                             index_items_list.append({
                                'circle': f"Circle {int(dar_info['circle'])}", 
                                'trade_name': dar_info['trade_name'], 
                                'num_pages_in_dar': dar_info['num_pages'], # This is actual pages in this DAR
                                'page_number_placeholder': page_counter_for_index # This will be its starting page
                            })
                             page_counter_for_index += dar_info['num_pages']
                        
                        # 2. Index Page
                        index_buffer_io = BytesIO()
                        # The start_page_offset for index is after cover page
                        create_index_page_pdf(index_buffer_io, index_items_list, current_page_offset_for_index + 1)
                        index_pdf = PdfReader(index_buffer_io)
                        for page_idx in range(len(index_pdf.pages)): pdf_writer.add_page(index_pdf.pages[page_idx])
                        current_page_offset_for_index += len(index_pdf.pages)

                        # 3. High-Value Paras Table
                        df_hv_paras = df_period_data[ (df_period_data['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000].copy()
                        df_hv_paras.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
                        if not df_hv_paras.empty:
                            hv_buffer_io = BytesIO()
                            create_high_value_paras_pdf(hv_buffer_io, df_hv_paras)
                            hv_pdf = PdfReader(hv_buffer_io)
                            for page_idx in range(len(hv_pdf.pages)): pdf_writer.add_page(hv_pdf.pages[page_idx])
                        
                        # 4. Merge actual DAR PDFs
                        for dar_info_merge in dar_pdf_objects_for_merge:
                            if dar_info_merge['pdf_reader']:
                                for page_content in dar_info_merge['pdf_reader'].pages:
                                    pdf_writer.add_page(page_content)
                            else: # Add placeholder if reader is None (fetch failed)
                                ph_buffer = BytesIO(); ph_doc_temp = SimpleDocTemplate(ph_buffer, pagesize=A4)
                                ph_story_temp = [Paragraph(f"Content for {dar_info_merge['trade_name']} (URL: {dar_info_merge['dar_url']}) could not be loaded due to earlier error.", getSampleStyleSheet()['Normal'])]
                                ph_doc_temp.build(ph_story_temp); ph_buffer.seek(0)
                                ph_reader_temp = PdfReader(ph_buffer)
                                if ph_reader_temp.pages: pdf_writer.add_page(ph_reader_temp.pages[0])


                        pdf_writer.write(final_pdf_buffer)
                        final_pdf_buffer.seek(0)
                        
                        pdf_file_download_name = f"MCM_Agenda_{month_year_str.replace(' ', '_')}.pdf"
                        st.download_button(label="Download Compiled PDF Agenda", data=final_pdf_buffer, file_name=pdf_file_download_name, mime="application/pdf")
                    except Exception as e_compile_pdf:
                        st.error(f"An error occurred during PDF compilation: {e_compile_pdf}")
                        import traceback
                        st.error(traceback.format_exc()) # Full traceback for debugging

    st.markdown("</div>", unsafe_allow_html=True)
