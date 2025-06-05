# ui_mcm_agenda.py
import streamlit as st
import pandas as pd
import datetime
import math
from io import BytesIO
import requests 
from urllib.parse import urlparse, parse_qs
import html 

# PDF manipulation libraries
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import inch
from PyPDF2 import PdfWriter, PdfReader 

from google_utils import read_from_spreadsheet
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError


# Helper function to extract File ID from Google Drive webViewLink
def get_file_id_from_drive_url(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    parsed_url = urlparse(url)
    if 'drive.google.com' in parsed_url.netloc:
        if '/file/d/' in parsed_url.path:
            try:
                return parsed_url.path.split('/file/d/')[1].split('/')[0]
            except IndexError:
                pass 
        query_params = parse_qs(parsed_url.query)
        if 'id' in query_params:
            return query_params['id'][0]
    return None

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
    story.append(Paragraph("<b>High-Value Audit Paras (&gt; 5 Lakhs Detection)</b>", styles['h1'])); story.append(Spacer(1, 0.2*inch))
    table_data_hv = [[Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
                      Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (Rs)</b>", styles['Normal']),
                      Paragraph("<b>Recovered (Rs)</b>", styles['Normal'])]]
    for _, row_hv in df_high_value_paras_data.iterrows():
        table_data_hv.append([
            Paragraph(html.escape(str(row_hv.get("Audit Group Number", "N/A"))), styles['Normal']), 
            Paragraph(html.escape(str(row_hv.get("Audit Para Number", "N/A"))), styles['Normal']),
            Paragraph(html.escape(str(row_hv.get("Audit Para Heading", "N/A"))[:100]), styles['Normal']), 
            Paragraph(f"{row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal']),
            Paragraph(f"{row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal'])])
    
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

def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
    st.markdown("### MCM Agenda Preparation")

    if not mcm_periods:
        st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
        return

    period_options = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if v.get('month_name') and v.get('year')}
    if not period_options:
        st.warning("No valid MCM periods with complete month and year information available.")
        return

    selected_period_key = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), format_func=lambda k: period_options[k], key="mcm_agenda_period_select_v4_full") # Changed key

    if not selected_period_key:
        st.info("Please select an MCM period."); return

    selected_period_info = mcm_periods[selected_period_key]
    month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
    st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 22pt; margin-bottom:10px;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
    
    df_period_data_full = pd.DataFrame()
    if sheets_service and selected_period_info.get('spreadsheet_id'):
        with st.spinner(f"Loading data for {month_year_str}..."):
            df_period_data_full = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])
    
    if df_period_data_full is None or df_period_data_full.empty:
        st.info(f"No data found in the spreadsheet for {month_year_str}.")
    else:
        # Ensure correct data types for key columns
        cols_to_convert_numeric = ['Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)', 
                                   'Total Amount Recovered (Overall Rs)', 'Audit Para Number', 
                                   'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
        for col_name in cols_to_convert_numeric:
            if col_name in df_period_data_full.columns:
                df_period_data_full[col_name] = pd.to_numeric(df_period_data_full[col_name], errors='coerce')
            else: 
                df_period_data_full[col_name] = 0 if "Amount" in col_name or "Revenue" in col_name else pd.NA
        
        # Derive/Validate Audit Circle Number
        circle_col_to_use = 'Audit Circle Number' 
        if 'Audit Circle Number' not in df_period_data_full.columns or \
           not df_period_data_full['Audit Circle Number'].notna().any() or \
           not pd.to_numeric(df_period_data_full['Audit Circle Number'], errors='coerce').fillna(0).astype(int).gt(0).any():
            if 'Audit Group Number' in df_period_data_full.columns and df_period_data_full['Audit Group Number'].notna().any():
                df_period_data_full['Derived Audit Circle Number'] = df_period_data_full['Audit Group Number'].apply(calculate_audit_circle_agenda).fillna(0).astype(int)
                circle_col_to_use = 'Derived Audit Circle Number'
                st.caption("Using derived 'Audit Circle Number' as sheet column was missing/invalid.")
            else:
                # If 'Derived Audit Circle Number' also wasn't created or is problematic, create a default
                if circle_col_to_use not in df_period_data_full.columns: # Ensure it exists
                    df_period_data_full[circle_col_to_use] = 0 
                st.warning("'Audit Circle Number' could not be determined reliably from sheet or derived.")
        else:
             df_period_data_full['Audit Circle Number'] = df_period_data_full['Audit Circle Number'].fillna(0).astype(int)
             # circle_col_to_use is already 'Audit Circle Number'

        # Vertical collapsible tabs for Audit Circles
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
                    # Ensure 'Audit Group Number' column exists before filtering
                    if 'Audit Group Number' in df_circle_iter_data.columns:
                        df_grp_iter_data = df_circle_iter_data[df_circle_iter_data['Audit Group Number'] == grp_iter_num]
                        if not df_grp_iter_data.empty:
                            group_labels_list.append(f"Audit Group {grp_iter_num}")
                            group_dfs_list.append(df_grp_iter_data)
                    else:
                        st.warning("Audit Group Number column missing in data for circle tabs.")
                        break 
                
                if not group_labels_list:
                    st.write(f"No specific audit group data found within {circle_label_iter}.")
                    continue
                
                group_st_tabs_widgets = st.tabs(group_labels_list)

                for i, group_tab_widget_item in enumerate(group_st_tabs_widgets):
                    with group_tab_widget_item:
                        df_current_grp_item = group_dfs_list[i]
                        # Ensure 'Trade Name' column exists
                        unique_trade_names_list = df_current_grp_item.get('Trade Name', pd.Series(dtype='str')).dropna().unique()

                        if not unique_trade_names_list.any():
                            st.write("No trade names with DARs found for this group.")
                            continue
                        
                        st.markdown(f"**DARs for {group_labels_list[i]}:**", unsafe_allow_html=True)
                        session_key_selected_trade = f"selected_trade_v2_{circle_num_iter}_{group_labels_list[i].replace(' ','_')}" # Ensure unique key

                        for tn_idx_iter, trade_name_item in enumerate(unique_trade_names_list):
                            trade_name_data_for_pdf_url = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
                            dar_pdf_url_item = None
                            if not trade_name_data_for_pdf_url.empty and 'DAR PDF URL' in trade_name_data_for_pdf_url.columns:
                                dar_pdf_url_item = trade_name_data_for_pdf_url['DAR PDF URL'].iloc[0]

                            cols_trade_display = st.columns([0.7, 0.3])
                            with cols_trade_display[0]:
                                if st.button(f"{trade_name_item}", key=f"tradebtn_agenda_v4_{circle_num_iter}_{i}_{tn_idx_iter}", help=f"Show paras for {trade_name_item}", use_container_width=True):
                                    st.session_state[session_key_selected_trade] = trade_name_item
                            with cols_trade_display[1]:
                                if pd.notna(dar_pdf_url_item) and isinstance(dar_pdf_url_item, str) and dar_pdf_url_item.startswith("http"):
                                    st.link_button("View DAR PDF", dar_pdf_url_item, use_container_width=True, type="secondary", key=f"pdf_link_btn_{circle_num_iter}_{i}_{tn_idx_iter}")
                                else:
                                    st.caption("No PDF Link")
                            
                            if st.session_state.get(session_key_selected_trade) == trade_name_item:
                                st.markdown(f"<h5 style='font-size:13pt; margin-top:10px; color:#154360;'>Gist of Audit Paras for: {html.escape(trade_name_item)}</h5>", unsafe_allow_html=True)
                                df_trade_paras_item = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
                                
                                html_rows = ""
                                total_det_tn_item = 0; total_rec_tn_item = 0
                                for _, para_item_row in df_trade_paras_item.iterrows():
                                    para_num = para_item_row.get("Audit Para Number", "N/A"); 
                                    p_num_str = str(int(para_num)) if pd.notna(para_num) and para_num !=0 else "N/A"
                                    p_title = html.escape(str(para_item_row.get("Audit Para Heading", "N/A")))
                                    p_status = html.escape(str(para_item_row.get("Status of para", "N/A")))
                                    
                                    det_lakhs = para_item_row.get('Revenue Involved (Lakhs Rs)'); 
                                    det_rs = (float(det_lakhs) * 100000) if pd.notna(det_lakhs) else 0.0
                                    rec_lakhs = para_item_row.get('Revenue Recovered (Lakhs Rs)'); 
                                    rec_rs = (float(rec_lakhs) * 100000) if pd.notna(rec_lakhs) else 0.0
                                    
                                    total_det_tn_item += det_rs; total_rec_tn_item += rec_rs
                                    
                                    html_rows += f"""
                                    <tr>
                                        <td>{p_num_str}</td>
                                        <td>{p_title}</td>
                                        <td class='amount-col'>{det_rs:,.0f}</td>
                                        <td class='amount-col'>{rec_rs:,.0f}</td>
                                        <td>{p_status}</td>
                                    </tr>"""
                                
                                table_full_html = f"""
                                <style>.paras-table {{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:10pt;}}.paras-table th, .paras-table td {{border:1px solid #bbb;padding:5px;text-align:left;word-wrap:break-word;}}.paras-table th {{background-color:#343a40;color:white;font-size:11pt;}}.paras-table tr:nth-child(even) {{background-color:#f4f6f6;}}.amount-col {{text-align:right!important;}}</style>
                                <table class='paras-table'><tr><th>Para No.</th><th>Para Title</th><th>Detection (Rs)</th><th>Recovery (Rs)</th><th>Status</th></tr>{html_rows}</table>"""
                                st.markdown(table_full_html, unsafe_allow_html=True)
                                st.markdown(f"<b>Total Detection for {html.escape(trade_name_item)}: Rs. {total_det_tn_item:,.0f}</b>", unsafe_allow_html=True)
                                st.markdown(f"<b>Total Recovery for {html.escape(trade_name_item)}: Rs. {total_rec_tn_item:,.0f}</b>", unsafe_allow_html=True)
                                st.markdown("<hr style='border-top: 1px solid #ccc; margin-top:10px; margin-bottom:10px;'>", unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("Compile Full MCM Agenda PDF", key="compile_mcm_agenda_pdf_final_v5_progress", type="primary", help="Generates a comprehensive PDF.", use_container_width=True):
            if df_period_data_full.empty:
                st.error("No data available for the selected MCM period to compile into PDF.")
            else:
                status_message_area = st.empty() 
                progress_bar = st.progress(0)
                
                with st.spinner("Preparing for PDF compilation..."): 
                    final_pdf_merger = PdfWriter()
                    compiled_pdf_pages_count = 0 

                    df_for_pdf = df_period_data_full.dropna(subset=['DAR PDF URL', 'Trade Name', circle_col_to_use]).copy()
                    df_for_pdf[circle_col_to_use] = pd.to_numeric(df_for_pdf[circle_col_to_use], errors='coerce').fillna(0).astype(int)
                    unique_dars_to_process = df_for_pdf.sort_values(by=[circle_col_to_use, 'Trade Name', 'DAR PDF URL']).drop_duplicates(subset=['DAR PDF URL'])
                    total_dars = len(unique_dars_to_process)
                    dar_info_for_processing = [] 
                    
                    if total_dars == 0:
                        status_message_area.warning("No valid DARs with PDF URLs found to compile."); st.stop()

                    total_steps_pdf = 3 + total_dars + 1 
                    current_pdf_step = 0

                    if drive_service:
                        status_message_area.info(f"Pre-fetching {total_dars} DAR PDFs to count pages and prepare content...")
                        for idx_dar_prefetch, dar_row_prefetch in unique_dars_to_process.iterrows():
                            dar_url_fetch = dar_row_prefetch.get('DAR PDF URL')
                            file_id_fetch = get_file_id_from_drive_url(dar_url_fetch)
                            num_pages_fetch = 1; reader_obj_fetch = None
                            trade_name_fetch = dar_row_prefetch.get('Trade Name', 'Unknown DAR')
                            circle_fetch = f"Circle {int(dar_row_prefetch.get(circle_col_to_use,0))}"
                            status_message_area.info(f"Fetching DAR {idx_dar_prefetch - unique_dars_to_process.index[0] + 1}/{total_dars} for {trade_name_fetch}...") # Adjusted index for display
                            if file_id_fetch:
                                try:
                                    req_fetch = drive_service.files().get_media(fileId=file_id_fetch)
                                    fh_fetch = BytesIO(); MediaIoBaseDownload(fh_fetch, req_fetch).next_chunk(num_retries=2); fh_fetch.seek(0)
                                    reader_obj_fetch = PdfReader(fh_fetch)
                                    num_pages_fetch = len(reader_obj_fetch.pages)
                                except HttpError as he_fetch: st.warning(f"PDF HTTP Error for {trade_name_fetch} ({dar_url_fetch}): {he_fetch}. Placeholder will be used.")
                                except Exception as e_fetch_inner: st.warning(f"PDF Read Error for {trade_name_fetch} ({dar_url_fetch}): {e_fetch_inner}. Placeholder will be used.")
                            dar_info_for_processing.append({'circle': circle_fetch, 'trade_name': trade_name_fetch, 'num_pages_in_dar': num_pages_fetch, 'pdf_reader': reader_obj_fetch, 'dar_url': dar_url_fetch})
                    else: st.error("Google Drive service not available."); st.stop()
                
                with st.spinner("Compiling PDF Document..."):
                    try:
                        current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_pdf}: Cover Page...");
                        cover_buffer = BytesIO(); create_cover_page_pdf(cover_buffer, f"Audit Paras for MCM {month_year_str}", "Audit 1 Commissionerate Mumbai")
                        cover_reader = PdfReader(cover_buffer); final_pdf_merger.append_pages_from_reader(cover_reader); progress_bar.progress(current_pdf_step / total_steps_pdf)
                        compiled_pdf_pages_count += len(cover_reader.pages)

                        current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_pdf}: High-Value Paras Table...");
                        df_hv_data = df_period_data_full[(df_period_data_full['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000].copy()
                        df_hv_data.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
                        hv_pages_count = 0
                        if not df_hv_data.empty:
                            hv_buffer = BytesIO(); create_high_value_paras_pdf(hv_buffer, df_hv_data)
                            hv_reader = PdfReader(hv_buffer); final_pdf_merger.append_pages_from_reader(hv_reader); hv_pages_count = len(hv_reader.pages)
                        progress_bar.progress(current_pdf_step / total_steps_pdf); compiled_pdf_pages_count += hv_pages_count
                        
                        current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_pdf}: Index Page...");
                        index_page_actual_start = compiled_pdf_pages_count + 1
                        dar_start_page_counter_val = index_page_actual_start 
                        index_items_list_final = []
                        for item_info in dar_info_for_processing:
                            index_items_list_final.append({'circle': item_info['circle'], 'trade_name': item_info['trade_name'], 'start_page_in_final_pdf': dar_start_page_counter_val, 'num_pages_in_dar': item_info['num_pages_in_dar']})
                            dar_start_page_counter_val += item_info['num_pages_in_dar']
                        index_buffer = BytesIO(); create_index_page_pdf(index_buffer, index_items_list_final, index_page_actual_start) 
                        index_reader = PdfReader(index_buffer); final_pdf_merger.append_pages_from_reader(index_reader); progress_bar.progress(current_pdf_step / total_steps_pdf)
                        
                        for i, dar_detail_info in enumerate(dar_info_for_processing):
                            current_pdf_step += 1
                            status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Merging DAR {i+1}/{total_dars} ({html.escape(dar_detail_info['trade_name'])})...")
                            if dar_detail_info['pdf_reader']: final_pdf_merger.append_pages_from_reader(dar_detail_info['pdf_reader'])
                            else: 
                                ph_b = BytesIO(); ph_d = SimpleDocTemplate(ph_b, pagesize=A4); ph_s = [Paragraph(f"Content for {html.escape(dar_detail_info['trade_name'])} (URL: {html.escape(dar_detail_info['dar_url'])}) failed to load.", getSampleStyleSheet()['Normal'])]; ph_d.build(ph_s); ph_b.seek(0); final_pdf_merger.append_pages_from_reader(PdfReader(ph_b))
                            progress_bar.progress(current_pdf_step / total_steps_for_pdf)

                        current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Finalizing PDF...");
                        output_pdf_final = BytesIO(); final_pdf_merger.write(output_pdf_final); output_pdf_final.seek(0)
                        progress_bar.progress(1.0); status_message_area.success("PDF Compilation Complete!")
                        dl_filename = f"MCM_Agenda_{month_year_str.replace(' ', '_')}_Compiled.pdf"
                        st.download_button(label="Download Compiled PDF Agenda", data=output_pdf_final, file_name=dl_filename, mime="application/pdf")
                    except Exception as e_compile_outer:
                        status_message_area.error(f"An error during PDF compilation: {e_compile_outer}")
                        import traceback; st.error(traceback.format_exc())
                    finally:
                        time.sleep(0.5); status_message_area.empty();
                        if 'progress_bar' in locals() and progress_bar is not None : progress_bar.empty() # Check if progress_bar was defined

    st.markdown("</div>", unsafe_allow_html=True)# # ui_mcm_agenda.py
# import streamlit as st
# import pandas as pd
# import datetime
# import math
# from io import BytesIO
# import requests 
# from urllib.parse import urlparse, parse_qs
# import html 

# # PDF manipulation libraries
# from reportlab.lib.pagesizes import A4
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepInFrame
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
# from reportlab.lib import colors
# from reportlab.lib.units import inch
# from PyPDF2 import PdfWriter, PdfReader 

# from google_utils import read_from_spreadsheet
# from googleapiclient.http import MediaIoBaseDownload
# from googleapiclient.errors import HttpError


# # Helper function to extract File ID from Google Drive webViewLink
# def get_file_id_from_drive_url(url: str) -> str | None:
#     if not url or not isinstance(url, str):
#         return None
#     parsed_url = urlparse(url)
#     if 'drive.google.com' in parsed_url.netloc:
#         if '/file/d/' in parsed_url.path:
#             try:
#                 return parsed_url.path.split('/file/d/')[1].split('/')[0]
#             except IndexError:
#                 pass 
#         query_params = parse_qs(parsed_url.query)
#         if 'id' in query_params:
#             return query_params['id'][0]
#     return None

# # --- PDF Generation Functions ---
# def create_cover_page_pdf(buffer, title_text, subtitle_text):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch, bottomMargin=1.5*inch, leftMargin=1*inch, rightMargin=1*inch)
#     styles = getSampleStyleSheet()
#     story = []
#     title_style = ParagraphStyle('AgendaCoverTitle', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=28, alignment=TA_CENTER, textColor=colors.HexColor("#dc3545"), spaceBefore=1*inch, spaceAfter=0.3*inch)
#     story.append(Paragraph(title_text, title_style))
#     story.append(Spacer(1, 0.3*inch))
#     subtitle_style = ParagraphStyle('AgendaCoverSubtitle', parent=styles['h2'], fontName='Helvetica', fontSize=16, alignment=TA_CENTER, textColor=colors.darkslategray, spaceAfter=2*inch)
#     story.append(Paragraph(subtitle_text, subtitle_style))
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# def create_index_page_pdf(buffer, index_data_list, start_page_offset_for_index_table):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
#     styles = getSampleStyleSheet()
#     story = []
#     story.append(Paragraph("<b>Index of DARs</b>", styles['h1']))
#     story.append(Spacer(1, 0.2*inch))
#     table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Start Page</b>", styles['Normal'])]]
    
#     for item in index_data_list:
#         table_data.append([
#             Paragraph(str(item['circle']), styles['Normal']),
#             Paragraph(html.escape(item['trade_name']), styles['Normal']),
#             Paragraph(str(item['start_page_in_final_pdf']), styles['Normal'])
#         ])
#     col_widths = [1.5*inch, 4*inch, 1.5*inch]; index_table = Table(table_data, colWidths=col_widths)
#     index_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,1), (-1,-1), 5),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)])); story.append(index_table)
#     doc.build(story); buffer.seek(0); return buffer

# def create_high_value_paras_pdf(buffer, df_high_value_paras_data):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
#     styles = getSampleStyleSheet(); story = []
#     story.append(Paragraph("<b>High-Value Audit Paras (&gt; 5 Lakhs Detection)</b>", styles['h1'])); story.append(Spacer(1, 0.2*inch))
#     table_data_hv = [[Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
#                       Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (Rs)</b>", styles['Normal']),
#                       Paragraph("<b>Recovered (Rs)</b>", styles['Normal'])]]
#     for _, row_hv in df_high_value_paras_data.iterrows():
#         table_data_hv.append([
#             Paragraph(html.escape(str(row_hv.get("Audit Group Number", "N/A"))), styles['Normal']), 
#             Paragraph(html.escape(str(row_hv.get("Audit Para Number", "N/A"))), styles['Normal']),
#             Paragraph(html.escape(str(row_hv.get("Audit Para Heading", "N/A"))[:100]), styles['Normal']), 
#             Paragraph(f"{row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal']),
#             Paragraph(f"{row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal'])])
    
#     col_widths_hv = [1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch]; hv_table = Table(table_data_hv, colWidths=col_widths_hv)
#     hv_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,1), (-1,-1), 4),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)])); story.append(hv_table)
#     doc.build(story); buffer.seek(0); return buffer
# # --- End PDF Generation Functions ---

# def calculate_audit_circle_agenda(audit_group_number_val):
#     try:
#         agn = int(audit_group_number_val)
#         if 1 <= agn <= 30: return math.ceil(agn / 3.0)
#         return 0 
#     except (ValueError, TypeError, AttributeError): return 0

# def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
#     st.markdown("### MCM Agenda Preparation")

#     if not mcm_periods:
#         st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
#         return

#     period_options = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if v.get('month_name') and v.get('year')}
#     if not period_options:
#         st.warning("No valid MCM periods with complete month and year information available.")
#         return

#     selected_period_key = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), format_func=lambda k: period_options[k], key="mcm_agenda_period_select_v3_full")

#     if not selected_period_key:
#         st.info("Please select an MCM period."); return

#     selected_period_info = mcm_periods[selected_period_key]
#     month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
#     st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 22pt; margin-bottom:10px;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
#     st.markdown("---")
    
#     df_period_data_full = pd.DataFrame()
#     if sheets_service and selected_period_info.get('spreadsheet_id'):
#         with st.spinner(f"Loading data for {month_year_str}..."):
#             df_period_data_full = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])
    
#     if df_period_data_full is None or df_period_data_full.empty:
#         st.info(f"No data found in the spreadsheet for {month_year_str}.")
#     else:
#         # Ensure correct data types for key columns
#         cols_to_convert_numeric = ['Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)', 
#                                    'Total Amount Recovered (Overall Rs)', 'Audit Para Number', 
#                                    'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
#         for col_name in cols_to_convert_numeric:
#             if col_name in df_period_data_full.columns:
#                 df_period_data_full[col_name] = pd.to_numeric(df_period_data_full[col_name], errors='coerce')
#             else: 
#                 df_period_data_full[col_name] = 0 if "Amount" in col_name or "Revenue" in col_name else pd.NA
        
#         # Derive/Validate Audit Circle Number
#         circle_col_to_use = 'Audit Circle Number' # Default to using sheet column
#         if 'Audit Circle Number' not in df_period_data_full.columns or not df_period_data_full['Audit Circle Number'].notna().any() or not pd.to_numeric(df_period_data_full['Audit Circle Number'], errors='coerce').fillna(0).astype(int).gt(0).any():
#             if 'Audit Group Number' in df_period_data_full.columns and df_period_data_full['Audit Group Number'].notna().any():
#                 df_period_data_full['Derived Audit Circle Number'] = df_period_data_full['Audit Group Number'].apply(calculate_audit_circle_agenda).fillna(0).astype(int)
#                 circle_col_to_use = 'Derived Audit Circle Number'
#                 st.caption("Using derived 'Audit Circle Number' as sheet column was missing/invalid.")
#             else:
#                 # If derived also cannot be made, create a placeholder to avoid errors
#                 if 'Derived Audit Circle Number' not in df_period_data_full.columns:
#                      df_period_data_full['Derived Audit Circle Number'] = 0
#                 circle_col_to_use = 'Derived Audit Circle Number' # Fallback to potentially zeroed derived col
#                 st.warning("'Audit Circle Number' could not be determined reliably from sheet or derived.")
#         else: # Sheet column exists and seems valid
#              df_period_data_full['Audit Circle Number'] = df_period_data_full['Audit Circle Number'].fillna(0).astype(int)
#              # circle_col_to_use is already 'Audit Circle Number'

#         # Vertical collapsible tabs for Audit Circles
#         for circle_num_iter in range(1, 11):
#             circle_label_iter = f"Audit Circle {circle_num_iter}"
#             # Ensure using the correctly determined or derived circle column name
#             df_circle_iter_data = df_period_data_full[df_period_data_full[circle_col_to_use] == circle_num_iter]

#             expander_header_html = f"<div style='background-color:#007bff; color:white; padding:10px 15px; border-radius:5px; margin-top:12px; margin-bottom:3px; font-weight:bold; font-size:16pt;'>{html.escape(circle_label_iter)}</div>"
#             st.markdown(expander_header_html, unsafe_allow_html=True)
            
#             with st.expander(f"View Details for {html.escape(circle_label_iter)}", expanded=False):
#                 if df_circle_iter_data.empty:
#                     st.write(f"No data for {circle_label_iter} in this MCM period.")
#                     continue

#                 group_labels_list = []
#                 group_dfs_list = []
#                 min_grp = (circle_num_iter - 1) * 3 + 1
#                 max_grp = circle_num_iter * 3

#                 for grp_iter_num in range(min_grp, max_grp + 1):
#                     df_grp_iter_data = df_circle_iter_data[df_circle_iter_data['Audit Group Number'] == grp_iter_num]
#                     if not df_grp_iter_data.empty:
#                         group_labels_list.append(f"Audit Group {grp_iter_num}")
#                         group_dfs_list.append(df_grp_iter_data)
                
#                 if not group_labels_list:
#                     st.write(f"No specific audit group data found within {circle_label_iter}.")
#                     continue
                
#                 group_st_tabs_widgets = st.tabs(group_labels_list)

#                 for i, group_tab_widget_item in enumerate(group_st_tabs_widgets):
#                     with group_tab_widget_item:
#                         df_current_grp_item = group_dfs_list[i]
#                         unique_trade_names_list = df_current_grp_item.get('Trade Name', pd.Series(dtype='str')).dropna().unique()

#                         if not unique_trade_names_list.any():
#                             st.write("No trade names with DARs found for this group.")
#                             continue
                        
#                         st.markdown(f"**DARs for {group_labels_list[i]}:**", unsafe_allow_html=True)
#                         session_key_selected_trade = f"selected_trade_{circle_num_iter}_{group_labels_list[i].replace(' ','_')}"

#                         for tn_idx_iter, trade_name_item in enumerate(unique_trade_names_list):
#                             trade_name_data_for_pdf_url = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
#                             dar_pdf_url_item = None
#                             if not trade_name_data_for_pdf_url.empty and 'DAR PDF URL' in trade_name_data_for_pdf_url.columns:
#                                 dar_pdf_url_item = trade_name_data_for_pdf_url['DAR PDF URL'].iloc[0]

#                             cols_trade_display = st.columns([0.7, 0.3])
#                             with cols_trade_display[0]:
#                                 if st.button(f"{trade_name_item}", key=f"tradebtn_agenda_v3_{circle_num_iter}_{i}_{tn_idx_iter}", help=f"Show paras for {trade_name_item}", use_container_width=True):
#                                     st.session_state[session_key_selected_trade] = trade_name_item
#                             with cols_trade_display[1]:
#                                 if pd.notna(dar_pdf_url_item) and isinstance(dar_pdf_url_item, str) and dar_pdf_url_item.startswith("http"):
#                                     st.link_button("View DAR PDF", dar_pdf_url_item, use_container_width=True, type="secondary")
#                                 else:
#                                     st.caption("No PDF Link")
                            
#                             if st.session_state.get(session_key_selected_trade) == trade_name_item:
#                                 st.markdown(f"<h5 style='font-size:13pt; margin-top:10px; color:#154360;'>Gist of Audit Paras for: {html.escape(trade_name_item)}</h5>", unsafe_allow_html=True)
#                                 df_trade_paras_item = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
                                
#                                 html_rows = ""
#                                 total_det_tn_item = 0; total_rec_tn_item = 0
#                                 for _, para_item_row in df_trade_paras_item.iterrows():
#                                     para_num = para_item_row.get("Audit Para Number", "N/A"); p_num_str = str(int(para_num)) if pd.notna(para_num) and para_num !=0 else "N/A"
#                                     p_title = html.escape(str(para_item_row.get("Audit Para Heading", "N/A")))
#                                     p_status = html.escape(str(para_item_row.get("Status of para", "N/A")))
                                    
#                                     det_lakhs = para_item_row.get('Revenue Involved (Lakhs Rs)', 0); det_rs = (det_lakhs * 100000) if pd.notna(det_lakhs) else 0
#                                     rec_lakhs = para_item_row.get('Revenue Recovered (Lakhs Rs)', 0); rec_rs = (rec_lakhs * 100000) if pd.notna(rec_lakhs) else 0
#                                     total_det_tn_item += det_rs; total_rec_tn_item += rec_rs
                                    
#                                     html_rows += f"""
#                                     <tr>
#                                         <td>{p_num_str}</td>
#                                         <td>{p_title}</td>
#                                         <td class='amount-col'>{det_rs:,.0f}</td>
#                                         <td class='amount-col'>{rec_rs:,.0f}</td>
#                                         <td>{p_status}</td>
#                                     </tr>"""
                                
#                                 table_full_html = f"""
#                                 <style>.paras-table {{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:10pt;}}.paras-table th, .paras-table td {{border:1px solid #bbb;padding:5px;text-align:left;word-wrap:break-word;}}.paras-table th {{background-color:#343a40;color:white;font-size:11pt;}}.paras-table tr:nth-child(even) {{background-color:#f4f6f6;}}.amount-col {{text-align:right!important;}}</style>
#                                 <table class='paras-table'><tr><th>Para No.</th><th>Para Title</th><th>Detection (Rs)</th><th>Recovery (Rs)</th><th>Status</th></tr>{html_rows}</table>"""
#                                 st.markdown(table_full_html, unsafe_allow_html=True)
#                                 st.markdown(f"<b>Total Detection for {html.escape(trade_name_item)}: Rs. {total_det_tn_item:,.0f}</b>", unsafe_allow_html=True)
#                                 st.markdown(f"<b>Total Recovery for {html.escape(trade_name_item)}: Rs. {total_rec_tn_item:,.0f}</b>", unsafe_allow_html=True)
#                                 st.markdown("<hr style='border-top: 1px solid #ccc; margin-top:10px; margin-bottom:10px;'>", unsafe_allow_html=True)
        
#         st.markdown("---")
#         # --- Compile PDF Button ---
#         if st.button("Compile Full MCM Agenda PDF", key="compile_mcm_agenda_pdf_final_v4_progress", type="primary", help="Generates a comprehensive PDF.", use_container_width=True):
#             if df_period_data_full.empty:
#                 st.error("No data available for the selected MCM period to compile into PDF.")
#             else:
#                 status_message_area = st.empty() 
#                 progress_bar = st.progress(0)
                
#                 with st.spinner("Preparing for PDF compilation..."): # Initial spinner for setup
#                     final_pdf_merger = PdfWriter()
#                     compiled_pdf_pages_count = 0 

#                     df_for_pdf = df_period_data_full.dropna(subset=['DAR PDF URL', 'Trade Name', circle_col_to_use]).copy()
#                     df_for_pdf[circle_col_to_use] = pd.to_numeric(df_for_pdf[circle_col_to_use], errors='coerce').fillna(0).astype(int)
                    
#                     # Get unique DARs, sorted for consistent processing order
#                     unique_dars_to_process = df_for_pdf.sort_values(by=[circle_col_to_use, 'Trade Name', 'DAR PDF URL']).drop_duplicates(subset=['DAR PDF URL'])
#                     total_dars = len(unique_dars_to_process)
                    
#                     dar_objects_for_merge_and_index = [] 
                    
#                     if total_dars == 0:
#                         status_message_area.warning("No valid DARs with PDF URLs found to compile."); st.stop()

#                     total_steps_for_pdf = 3 + total_dars + 1 # Cover, Index, HV_Table, each DAR, Finalize
#                     current_pdf_step = 0

#                     if drive_service:
#                         status_message_area.info(f"Pre-fetching {total_dars} DAR PDFs to count pages and prepare content...")
#                         for idx, dar_row in unique_dars_to_process.iterrows():
#                             dar_url_val = dar_row.get('DAR PDF URL')
#                             file_id_val = get_file_id_from_drive_url(dar_url_val)
#                             num_pages_val = 1 
#                             reader_obj_val = None
#                             trade_name_val = dar_row.get('Trade Name', 'Unknown DAR')
#                             circle_val = f"Circle {int(dar_row.get(circle_col_to_use,0))}"

#                             status_message_area.info(f"Fetching DAR {idx+1}/{total_dars} for {trade_name_val}...")
#                             if file_id_val:
#                                 try:
#                                     req_val = drive_service.files().get_media(fileId=file_id_val)
#                                     fh_val = BytesIO(); MediaIoBaseDownload(fh_val, req_val).next_chunk(num_retries=2); fh_val.seek(0)
#                                     reader_obj_val = PdfReader(fh_val)
#                                     num_pages_val = len(reader_obj_val.pages)
#                                 except HttpError as he: st.warning(f"PDF HTTP Error for {trade_name_val} ({dar_url_val}): {he}. Using placeholder.")
#                                 except Exception as e_fetch_val: st.warning(f"PDF Read Error for {trade_name_val} ({dar_url_val}): {e_fetch_val}. Using placeholder.")
                            
#                             dar_objects_for_merge_and_index.append({
#                                 'circle': circle_val, 'trade_name': trade_name_val,
#                                 'num_pages_in_dar': num_pages_val, 'pdf_reader': reader_obj_val, 'dar_url': dar_url_val
#                             })
#                     else: st.error("Google Drive service not available."); st.stop()
#                 # --- End of pre-fetching spinner ---
                
#                 # Now compile with progress
#                 try:
#                     # 1. Cover Page
#                     current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Cover Page...");
#                     cover_buffer = BytesIO(); create_cover_page_pdf(cover_buffer, f"Audit Paras for MCM {month_year_str}", "Audit 1 Commissionerate Mumbai")
#                     cover_reader = PdfReader(cover_buffer); final_pdf_merger.append_pages_from_reader(cover_reader); progress_bar.progress(current_pdf_step / total_steps_for_pdf)
#                     compiled_pdf_pages_count += len(cover_reader.pages)

#                     # 2. High-Value Paras Table (Generate before index to know its page count if index is dynamic)
#                     current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating High-Value Paras Table...");
#                     df_hv_data = df_period_data_full[(df_period_data_full['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000].copy()
#                     df_hv_data.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
#                     hv_pages_count = 0
#                     if not df_hv_data.empty:
#                         hv_buffer = BytesIO(); create_high_value_paras_pdf(hv_buffer, df_hv_data)
#                         hv_reader = PdfReader(hv_buffer); final_pdf_merger.append_pages_from_reader(hv_reader)
#                         hv_pages_count = len(hv_reader.pages)
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)
#                     compiled_pdf_pages_count += hv_pages_count
                    
#                     # 3. Index Page (Calculate start pages now)
#                     current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Index Page...");
#                     index_page_actual_start = compiled_pdf_pages_count + 1
#                     dar_start_page_counter_val = index_page_actual_start # This is page number where the first DAR will appear after the index pages
                    
#                     index_items_list_final = []
#                     for item_info in dar_objects_for_merge_and_index: # Use the pre-fetched and sorted list
#                         index_items_list_final.append({
#                             'circle': item_info['circle'], 'trade_name': item_info['trade_name'],
#                             'start_page_in_final_pdf': dar_start_page_counter_val, 
#                             'num_pages_in_dar': item_info['num_pages_in_dar']
#                         })
#                         dar_start_page_counter_val += item_info['num_pages_in_dar']
                    
#                     index_buffer = BytesIO(); create_index_page_pdf(index_buffer, index_items_list_final, index_page_actual_start) # Pass the start page for index content
#                     index_reader = PdfReader(index_buffer); final_pdf_merger.append_pages_from_reader(index_reader)
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)
#                     # compiled_pdf_pages_count += len(index_reader.pages) # Already accounted for by dar_start_page_counter for DARs

#                     # 4. Merge actual DAR PDFs
#                     for i, dar_detail_info in enumerate(dar_objects_for_merge_and_index):
#                         current_pdf_step += 1
#                         status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Merging DAR {i+1}/{total_dars} ({html.escape(dar_detail_info['trade_name'])})...")
#                         if dar_detail_info['pdf_reader']:
#                             final_pdf_merger.append_pages_from_reader(dar_detail_info['pdf_reader'])
#                         else: # Placeholder
#                             ph_b = BytesIO(); ph_d = SimpleDocTemplate(ph_b, pagesize=A4); ph_s = [Paragraph(f"Content for {html.escape(dar_detail_info['trade_name'])} (URL: {html.escape(dar_detail_info['dar_url'])}) failed to load.", getSampleStyleSheet()['Normal'])]; ph_d.build(ph_s); ph_b.seek(0); final_pdf_merger.append_pages_from_reader(PdfReader(ph_b))
#                         progress_bar.progress(current_pdf_step / total_steps_for_pdf)

#                     # 5. Finalize PDF
#                     current_pdf_step += 1; status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Finalizing PDF...");
#                     output_pdf_final = BytesIO(); final_pdf_merger.write(output_pdf_final); output_pdf_final.seek(0)
#                     progress_bar.progress(1.0); status_message_area.success("PDF Compilation Complete!")
                    
#                     dl_filename = f"MCM_Agenda_{month_year_str.replace(' ', '_')}_Compiled.pdf"
#                     st.download_button(label="Download Compiled PDF Agenda", data=output_pdf_final, file_name=dl_filename, mime="application/pdf")

#                 except Exception as e_compile_outer:
#                     status_message_area.error(f"An error occurred during PDF compilation: {e_compile_outer}")
#                     import traceback; st.error(traceback.format_exc())
#                 finally:
#                     time.sleep(0.5) # Give a moment for user to see final status
#                     status_message_area.empty()
#                     progress_bar.empty()

#     st.markdown("</div>", unsafe_allow_html=True)# # ui_mcm_agenda.py
# # import streamlit as st
# # import pandas as pd
# # import datetime
# # import math
# # from io import BytesIO
# # import requests 
# # from urllib.parse import urlparse, parse_qs
# # import html 
# # from reportlab.lib.pagesizes import A4
# # from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
# # from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# # from reportlab.lib.enums import TA_CENTER, TA_LEFT
# # from reportlab.lib import colors
# # from reportlab.lib.units import inch
# # from PyPDF2 import PdfWriter, PdfReader

# # from google_utils import read_from_spreadsheet
# # from googleapiclient.http import MediaIoBaseDownload

# # # Helper function to extract File ID from Google Drive webViewLink
# # def get_file_id_from_drive_url(url: str) -> str | None:
# #     if not url or not isinstance(url, str):
# #         return None
# #     parsed_url = urlparse(url)
# #     if 'drive.google.com' in parsed_url.netloc:
# #         if '/file/d/' in parsed_url.path:
# #             try:
# #                 return parsed_url.path.split('/file/d/')[1].split('/')[0]
# #             except IndexError:
# #                 return None
# #         query_params = parse_qs(parsed_url.query)
# #         if 'id' in query_params:
# #             return query_params['id'][0]
# #     return None

# # # --- PDF Generation Functions (Assumed complete from previous responses) ---
# # def create_cover_page_pdf(buffer, title_text, subtitle_text):
# #     doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch, bottomMargin=1.5*inch, leftMargin=1*inch, rightMargin=1*inch)
# #     styles = getSampleStyleSheet()
# #     story = []
# #     title_style = ParagraphStyle('AgendaCoverTitle', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=28, alignment=TA_CENTER, textColor=colors.HexColor("#dc3545"), spaceBefore=1*inch, spaceAfter=0.3*inch)
# #     story.append(Paragraph(title_text, title_style))
# #     story.append(Spacer(1, 0.3*inch))
# #     subtitle_style = ParagraphStyle('AgendaCoverSubtitle', parent=styles['h2'], fontName='Helvetica', fontSize=16, alignment=TA_CENTER, textColor=colors.darkslategray, spaceAfter=2*inch)
# #     story.append(Paragraph(subtitle_text, subtitle_style))
# #     doc.build(story)
# #     buffer.seek(0)
# #     return buffer

# # def create_index_page_pdf(buffer, index_data_list, start_page_offset):
# #     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
# #     styles = getSampleStyleSheet()
# #     story = []
# #     story.append(Paragraph("<b>Index of DARs</b>", styles['h1']))
# #     story.append(Spacer(1, 0.2*inch))
# #     table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Page No.</b>", styles['Normal'])]]
# #     current_page_in_pdf = start_page_offset
# #     for item in index_data_list:
# #         table_data.append([Paragraph(str(item['circle']), styles['Normal']), Paragraph(item['trade_name'], styles['Normal']), Paragraph(str(current_page_in_pdf), styles['Normal'])])
# #         current_page_in_pdf += item.get('num_pages_in_dar', 1)
# #     col_widths = [1.5*inch, 4*inch, 1.5*inch]; index_table = Table(table_data, colWidths=col_widths)
# #     index_table.setStyle(TableStyle([
# #         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
# #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
# #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10),
# #         ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,1), (-1,-1), 5),
# #         ('GRID', (0, 0), (-1, -1), 1, colors.black)])); story.append(index_table)
# #     doc.build(story); buffer.seek(0); return buffer

# # def create_high_value_paras_pdf(buffer, df_high_value_paras_data):
# #     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
# #     styles = getSampleStyleSheet(); story = []
# #     story.append(Paragraph("<b>High-Value Audit Paras (> 5 Lakhs Detection)</b>", styles['h1'])); story.append(Spacer(1, 0.2*inch))
# #     table_data_hv = [[Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']), Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (Rs)</b>", styles['Normal']), Paragraph("<b>Recovered (Rs)</b>", styles['Normal'])]]
# #     for _, row_hv in df_high_value_paras_data.iterrows():
# #         table_data_hv.append([
# #             Paragraph(str(row_hv.get("Audit Group Number", "N/A")), styles['Normal']), Paragraph(str(row_hv.get("Audit Para Number", "N/A")), styles['Normal']),
# #             Paragraph(str(row_hv.get("Audit Para Heading", "N/A"))[:100], styles['Normal']), Paragraph(f"{row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal']),
# #             Paragraph(f"{row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal'])])
# #     col_widths_hv = [1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch]; hv_table = Table(table_data_hv, colWidths=col_widths_hv)
# #     hv_table.setStyle(TableStyle([
# #         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
# #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
# #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
# #         ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,1), (-1,-1), 4),
# #         ('GRID', (0, 0), (-1, -1), 1, colors.black)])); story.append(hv_table)
# #     doc.build(story); buffer.seek(0); return buffer
# # # --- End PDF Generation Functions ---

# # def calculate_audit_circle_agenda(audit_group_number_val): # Renamed for clarity within this module
# #     try:
# #         agn = int(audit_group_number_val)
# #         if 1 <= agn <= 30: return math.ceil(agn / 3.0)
# #         return 0 # Default to 0 or some indicator of invalid group for circle calculation
# #     except (ValueError, TypeError, AttributeError): return 0


# # def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
# #     st.markdown("### MCM Agenda Preparation")

# #     if not mcm_periods:
# #         st.warning("No MCM periods found. Create them via 'Create MCM Period' tab.")
# #         return

# #     period_options = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if v.get('month_name') and v.get('year')}
# #     if not period_options:
# #         st.warning("No valid MCM periods with complete month/year information.")
# #         return

# #     selected_period_key = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), format_func=lambda k: period_options[k], key="mcm_agenda_period_select_v2")

# #     if not selected_period_key:
# #         st.info("Please select an MCM period."); return

# #     selected_period_info = mcm_periods[selected_period_key]
# #     month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
# #     st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 22pt; margin-bottom:10px;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
    
# #     df_period_data_full = pd.DataFrame()
# #     if sheets_service and selected_period_info.get('spreadsheet_id'):
# #         with st.spinner(f"Loading data for {month_year_str}..."):
# #             df_period_data_full = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])
    
# #     if df_period_data_full is None or df_period_data_full.empty:
# #         st.info(f"No data found in the spreadsheet for {month_year_str}.")
# #     else:
# #         # Ensure correct data types for key columns
# #         cols_to_convert_numeric = ['Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)', 
# #                                    'Total Amount Recovered (Overall Rs)', 'Audit Para Number', 
# #                                    'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
# #         for col_name in cols_to_convert_numeric:
# #             if col_name in df_period_data_full.columns:
# #                 df_period_data_full[col_name] = pd.to_numeric(df_period_data_full[col_name], errors='coerce')
# #             else: # Add column if missing to prevent KeyErrors later, fill with 0 or NaN
# #                 df_period_data_full[col_name] = 0 if "Amount" in col_name or "Revenue" in col_name else pd.NA


# #         # Derive/Validate Audit Circle Number
# #         if 'Audit Circle Number' not in df_period_data_full.columns or not df_period_data_full['Audit Circle Number'].notna().any() or not pd.to_numeric(df_period_data_full['Audit Circle Number'], errors='coerce').fillna(0).astype(int).gt(0).any():
# #             if 'Audit Group Number' in df_period_data_full.columns and df_period_data_full['Audit Group Number'].notna().any():
# #                 df_period_data_full['Derived Audit Circle Number'] = df_period_data_full['Audit Group Number'].apply(calculate_audit_circle_agenda).fillna(0).astype(int)
# #                 circle_col_to_use = 'Derived Audit Circle Number'
# #                 st.caption("Using derived 'Audit Circle Number' as sheet column was missing/invalid.")
# #             else:
# #                 df_period_data_full['Derived Audit Circle Number'] = 0
# #                 circle_col_to_use = 'Derived Audit Circle Number'
# #                 st.warning("'Audit Circle Number' could not be determined reliably.")
# #         else:
# #              df_period_data_full['Audit Circle Number'] = df_period_data_full['Audit Circle Number'].fillna(0).astype(int)
# #              circle_col_to_use = 'Audit Circle Number'

# #         # Vertical collapsible tabs for Audit Circles
# #         for circle_num_iter in range(1, 11):
# #             ##
# #             circle_label_iter = f"Audit Circle {circle_num_iter}"
# #             df_circle_iter_data = df_period_data_full[df_period_data_full[circle_col_to_use] == circle_num_iter]

# #             expander_header_html = f"<div style='background-color:#007bff; color:white; padding:10px 15px; border-radius:5px; margin-top:12px; margin-bottom:3px; font-weight:bold; font-size:16pt;'>{circle_label_iter}</div>"
# #             st.markdown(expander_header_html, unsafe_allow_html=True)
            
# #             with st.expander(f"View Details for {circle_label_iter}", expanded=False):
# #                 if df_circle_iter_data.empty:
# #                     st.write(f"No data for {circle_label_iter} in this MCM period.")
# #                     continue

# #                 group_labels_list = []
# #                 group_dfs_list = []
# #                 min_grp = (circle_num_iter - 1) * 3 + 1
# #                 max_grp = circle_num_iter * 3

# #                 for grp_iter_num in range(min_grp, max_grp + 1):
# #                     df_grp_iter_data = df_circle_iter_data[df_circle_iter_data['Audit Group Number'] == grp_iter_num]
# #                     if not df_grp_iter_data.empty:
# #                         group_labels_list.append(f"Audit Group {grp_iter_num}")
# #                         group_dfs_list.append(df_grp_iter_data)
                
# #                 if not group_labels_list:
# #                     st.write(f"No specific audit group data found within {circle_label_iter}.")
# #                     continue
                
# #                 group_st_tabs_widgets = st.tabs(group_labels_list)

# #                 for i, group_tab_widget_item in enumerate(group_st_tabs_widgets):
# #                     with group_tab_widget_item:
# #                         df_current_grp_item = group_dfs_list[i]
# #                         unique_trade_names_list = df_current_grp_item.get('Trade Name', pd.Series(dtype='str')).dropna().unique()

# #                         if not unique_trade_names_list.any():
# #                             st.write("No trade names with DARs found for this group.")
# #                             continue
                        
# #                         st.markdown(f"**DARs for {group_labels_list[i]}:**", unsafe_allow_html=True)
# #                         session_key_selected_trade = f"selected_trade_{circle_num_iter}_{group_labels_list[i].replace(' ','_')}"

# #                         for tn_idx_iter, trade_name_item in enumerate(unique_trade_names_list):
# #                             trade_name_data_for_pdf_url = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
# #                             dar_pdf_url_item = None
# #                             if not trade_name_data_for_pdf_url.empty and 'DAR PDF URL' in trade_name_data_for_pdf_url.columns:
# #                                 dar_pdf_url_item = trade_name_data_for_pdf_url['DAR PDF URL'].iloc[0]

# #                             cols_trade_display = st.columns([0.7, 0.3])
# #                             with cols_trade_display[0]:
# #                                 if st.button(f"{trade_name_item}", key=f"tradebtn_agenda_{circle_num_iter}_{i}_{tn_idx_iter}", help=f"Show paras for {trade_name_item}", use_container_width=True):
# #                                     st.session_state[session_key_selected_trade] = trade_name_item
# #                             with cols_trade_display[1]:
# #                                 if pd.notna(dar_pdf_url_item) and isinstance(dar_pdf_url_item, str) and dar_pdf_url_item.startswith("http"):
# #                                     st.link_button("View DAR PDF", dar_pdf_url_item, use_container_width=True, type="secondary")
# #                                 else:
# #                                     st.caption("No PDF Link")
                            
# #                             if st.session_state.get(session_key_selected_trade) == trade_name_item:
# #                                 st.markdown(f"<h5 style='font-size:13pt; margin-top:10px; color:#154360;'>Gist of Audit Paras for: {html.escape(trade_name_item)}</h5>", unsafe_allow_html=True)
# #                                 df_trade_paras_item = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
                                
# #                                 html_rows = ""
# #                                 total_det_tn_item = 0; total_rec_tn_item = 0
# #                                 for _, para_item_row in df_trade_paras_item.iterrows():
# #                                     para_num = para_item_row.get("Audit Para Number", "N/A"); p_num_str = str(int(para_num)) if pd.notna(para_num) else "N/A"
# #                                     # Use html.escape() for user-generated content
# #                                     p_title = html.escape(str(para_item_row.get("Audit Para Heading", "N/A")))
# #                                     p_status = html.escape(str(para_item_row.get("Status of para", "N/A")))
                                    
# #                                     det_lakhs = para_item_row.get('Revenue Involved (Lakhs Rs)', 0); det_rs = (det_lakhs * 100000) if pd.notna(det_lakhs) else 0
# #                                     rec_lakhs = para_item_row.get('Revenue Recovered (Lakhs Rs)', 0); rec_rs = (rec_lakhs * 100000) if pd.notna(rec_lakhs) else 0
# #                                     total_det_tn_item += det_rs; total_rec_tn_item += rec_rs
                                    
# #                                     html_rows += f"""
# #                                     <tr>
# #                                         <td>{p_num_str}</td>
# #                                         <td>{p_title}</td>
# #                                         <td class='amount-col'>{det_rs:,.0f}</td>
# #                                         <td class='amount-col'>{rec_rs:,.0f}</td>
# #                                         <td>{p_status}</td>
# #                                     </tr>"""
                                
# #                                 table_full_html = f"""
# #                                 <style>.paras-table {{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:10pt;}}.paras-table th, .paras-table td {{border:1px solid #bbb;padding:5px;text-align:left;word-wrap:break-word;}}.paras-table th {{background-color:#343a40;color:white;font-size:11pt;}}.paras-table tr:nth-child(even) {{background-color:#f4f6f6;}}.amount-col {{text-align:right!important;}}</style>
# #                                 <table class='paras-table'><tr><th>Para No.</th><th>Para Title</th><th>Detection (Rs)</th><th>Recovery (Rs)</th><th>Status</th></tr>{html_rows}</table>"""
# #                                 st.markdown(table_full_html, unsafe_allow_html=True)
# #                                 st.markdown(f"<b>Total Detection for {html.escape(trade_name_item)}: Rs. {total_det_tn_item:,.0f}</b>", unsafe_allow_html=True)
# #                                 st.markdown(f"<b>Total Recovery for {html.escape(trade_name_item)}: Rs. {total_rec_tn_item:,.0f}</b>", unsafe_allow_html=True)
# #                                 st.markdown("<hr style='border-top: 1px solid #ccc; margin-top:10px; margin-bottom:10px;'>", unsafe_allow_html=True)
        
# #         st.markdown("---")
           
# #         if st.button("Compile Full MCM Agenda PDF", key="compile_mcm_agenda_pdf_final_btn", type="primary", help="Generates a comprehensive PDF including cover, index, high-value paras, and all linked DARs.", use_container_width=True):
# #             if df_period_data_full.empty:
# #                 st.error("No data available for the selected MCM period to compile into PDF.")
# #             else:
# #                 with st.spinner("Compiling Full MCM Agenda PDF... This may take several minutes for many DARs."):
# #                     try:
# #                         # (PDF compilation logic from previous response, adapted to use df_period_data_full and circle_col_to_use)
# #                         # This part is extensive and remains largely the same conceptually.
# #                         # Key: It needs to use `df_period_data_full` and `circle_col_to_use`.
# #                         # The helper functions create_cover_page_pdf, create_index_page_pdf, 
# #                         # create_high_value_paras_pdf, and the DAR merging logic will be called here.
# #                         st.success("PDF Compilation feature logic to be fully implemented here.")
# #                         # For now, a placeholder:
# #                         # pdf_buffer = BytesIO() # Example
# #                         # pdf_buffer.write(b"PDF Generation in Progress...")
# #                         # st.download_button("Download Compiled PDF (WIP)", pdf_buffer, f"MCM_Agenda_WIP_{month_year_str}.pdf", "application/pdf")

# #                     except Exception as e_compile_full_pdf:
# #                         st.error(f"Error during PDF compilation: {e_compile_full_pdf}")
# #                         import traceback
# #                         st.error(traceback.format_exc())

# #     st.markdown("</div>", unsafe_allow_html=True)# # ui_mcm_agenda.py
# # # import streamlit as st
# # # import pandas as pd
# # # import datetime
# # # import math
# # # from io import BytesIO
# # # import requests # For fetching PDFs if URLs are direct http/https
# # # from urllib.parse import urlparse, parse_qs

# # # # PDF manipulation libraries
# # # from reportlab.lib.pagesizes import A4
# # # from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
# # # from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# # # from reportlab.lib.enums import TA_CENTER, TA_LEFT
# # # from reportlab.lib import colors
# # # from reportlab.lib.units import inch
# # # from PyPDF2 import PdfWriter, PdfReader # Using PyPDF2

# # # from google_utils import read_from_spreadsheet
# # # from googleapiclient.http import MediaIoBaseDownload

# # # # Helper function to extract File ID from Google Drive webViewLink (from previous response)
# # # def get_file_id_from_drive_url(url: str) -> str | None:
# # #     if not url or not isinstance(url, str):
# # #         return None
# # #     parsed_url = urlparse(url)
# # #     if 'drive.google.com' in parsed_url.netloc:
# # #         if '/file/d/' in parsed_url.path:
# # #             try:
# # #                 return parsed_url.path.split('/file/d/')[1].split('/')[0]
# # #             except IndexError:
# # #                 return None
# # #         query_params = parse_qs(parsed_url.query)
# # #         if 'id' in query_params:
# # #             return query_params['id'][0]
# # #     return None

# # # # --- PDF Generation Functions (from previous response, ensure they are complete) ---
# # # def create_cover_page_pdf(buffer, title_text, subtitle_text):
# # #     doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch, bottomMargin=1.5*inch, leftMargin=1*inch, rightMargin=1*inch)
# # #     styles = getSampleStyleSheet()
# # #     story = []

# # #     title_style = ParagraphStyle('AgendaCoverTitle', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=28, alignment=TA_CENTER, textColor=colors.HexColor("#dc3545"), spaceBefore=1*inch, spaceAfter=0.3*inch)
# # #     story.append(Paragraph(title_text, title_style))
# # #     story.append(Spacer(1, 0.3*inch))
# # #     subtitle_style = ParagraphStyle('AgendaCoverSubtitle', parent=styles['h2'], fontName='Helvetica', fontSize=16, alignment=TA_CENTER, textColor=colors.darkslategray, spaceAfter=2*inch)
# # #     story.append(Paragraph(subtitle_text, subtitle_style))
# # #     doc.build(story)
# # #     buffer.seek(0)
# # #     return buffer

# # # def create_index_page_pdf(buffer, index_data_list, start_page_offset):
# # #     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
# # #     styles = getSampleStyleSheet()
# # #     story = []
# # #     story.append(Paragraph("<b>Index of DARs</b>", styles['h1']))
# # #     story.append(Spacer(1, 0.2*inch))

# # #     table_data = [
# # #         [Paragraph("<b>Audit Circle</b>", styles['Normal']), 
# # #          Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), 
# # #          Paragraph("<b>Page No.</b>", styles['Normal'])]
# # #     ]
# # #     current_page_in_pdf = start_page_offset
# # #     for item in index_data_list:
# # #         table_data.append([
# # #             Paragraph(str(item['circle']), styles['Normal']),
# # #             Paragraph(item['trade_name'], styles['Normal']),
# # #             Paragraph(str(current_page_in_pdf), styles['Normal'])
# # #         ])
# # #         current_page_in_pdf += item.get('num_pages_in_dar', 1) # Add pages of this DAR

# # #     col_widths = [1.5*inch, 4*inch, 1.5*inch]
# # #     index_table = Table(table_data, colWidths=col_widths)
# # #     index_table.setStyle(TableStyle([
# # #         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
# # #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
# # #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10),
# # #         ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,1), (-1,-1), 5),
# # #         ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
# # #     story.append(index_table)
# # #     doc.build(story)
# # #     buffer.seek(0)
# # #     return buffer

# # # def create_high_value_paras_pdf(buffer, df_high_value_paras_data): # Renamed input variable
# # #     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
# # #     styles = getSampleStyleSheet()
# # #     story = []
# # #     story.append(Paragraph("<b>High-Value Audit Paras (> 5 Lakhs Detection)</b>", styles['h1']))
# # #     story.append(Spacer(1, 0.2*inch))

# # #     table_data_hv = [
# # #         [Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
# # #          Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (Rs)</b>", styles['Normal']),
# # #          Paragraph("<b>Recovered (Rs)</b>", styles['Normal'])]
# # #     ]
# # #     for _, row_hv in df_high_value_paras_data.iterrows():
# # #         table_data_hv.append([
# # #             Paragraph(str(row_hv.get("Audit Group Number", "N/A")), styles['Normal']),
# # #             Paragraph(str(row_hv.get("Audit Para Number", "N/A")), styles['Normal']),
# # #             Paragraph(str(row_hv.get("Audit Para Heading", "N/A"))[:100], styles['Normal']),
# # #             Paragraph(f"{row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal']),
# # #             Paragraph(f"{row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal'])])
    
# # #     col_widths_hv = [1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch]
# # #     hv_table = Table(table_data_hv, colWidths=col_widths_hv)
# # #     hv_table.setStyle(TableStyle([
# # #         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
# # #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (3,1), (-1,-1), 'RIGHT'), # Align amounts right
# # #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
# # #         ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,1), (-1,-1), 4),
# # #         ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
# # #     story.append(hv_table)
# # #     doc.build(story)
# # #     buffer.seek(0)
# # #     return buffer
# # # # --- End PDF Generation Functions ---

# # # def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
# # #     st.markdown("### MCM Agenda Preparation")

# # #     if not mcm_periods:
# # #         st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
# # #         return

# # #     period_options = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if v.get('month_name') and v.get('year')}
# # #     if not period_options:
# # #         st.warning("No valid MCM periods with complete month and year information available.")
# # #         return

# # #     selected_period_key = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), format_func=lambda k: period_options[k], key="mcm_agenda_period_select_final")

# # #     if not selected_period_key:
# # #         st.info("Please select an MCM period.")
# # #         return

# # #     selected_period_info = mcm_periods[selected_period_key]
# # #     month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
# # #     st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 24pt;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
# # #     st.markdown("---")

# # #     df_period_data = pd.DataFrame()
# # #     if sheets_service and selected_period_info.get('spreadsheet_id'):
# # #         with st.spinner(f"Loading data for {month_year_str}..."):
# # #             df_period_data = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])
    
# # #     if df_period_data is None or df_period_data.empty:
# # #         st.info(f"No data found in the spreadsheet for {month_year_str}.")
# # #     else:
# # #         numeric_cols = ['Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)', 
# # #                         'Total Amount Recovered (Overall Rs)', 'Audit Para Number', 
# # #                         'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
# # #         for col in numeric_cols:
# # #             if col in df_period_data.columns:
# # #                 df_period_data[col] = pd.to_numeric(df_period_data[col], errors='coerce')

# # #         if 'Audit Circle Number' not in df_period_data.columns or not df_period_data['Audit Circle Number'].notna().any() or not pd.to_numeric(df_period_data['Audit Circle Number'], errors='coerce').notna().any():
# # #             if 'Audit Group Number' in df_period_data.columns and df_period_data['Audit Group Number'].notna().any():
# # #                 df_period_data['Audit Circle Number'] = df_period_data['Audit Group Number'].apply(calculate_audit_circle).fillna(0).astype(int)
# # #                 st.caption("Derived 'Audit Circle Number' as it was missing or invalid in the sheet.")
# # #             else:
# # #                 df_period_data['Audit Circle Number'] = 0 
# # #                 st.warning("'Audit Circle Number' could not be determined.")
# # #         else:
# # #              df_period_data['Audit Circle Number'] = pd.to_numeric(df_period_data['Audit Circle Number'], errors='coerce').fillna(0).astype(int)

# # #         # Vertical collapsible tabs for Audit Circles
# # #         for circle_num in range(1, 11):
# # #             circle_label = f"Audit Circle {circle_num}"
# # #             df_circle_data = df_period_data[df_period_data['Audit Circle Number'] == circle_num]

# # #             # Styled header for the expander
# # #             st.markdown(f"""
# # #             <div style='
# # #                 background-color: #007bff; color: white; padding: 10px; 
# # #                 border-radius: 5px; margin-top: 10px; margin-bottom: 2px;
# # #                 font-weight: bold; font-size: 16pt;
# # #             '>
# # #                 {circle_label}
# # #             </div>""", unsafe_allow_html=True)
            
# # #             with st.expander(f"View Details for {circle_label}", expanded=False):
# # #                 if df_circle_data.empty:
# # #                     st.write(f"No data for {circle_label} in this MCM period.")
# # #                     continue

# # #                 group_labels_in_circle = []
# # #                 group_dfs_in_circle = []
# # #                 min_group_in_circle = (circle_num - 1) * 3 + 1
# # #                 max_group_in_circle = circle_num * 3

# # #                 for grp_num in range(min_group_in_circle, max_group_in_circle + 1):
# # #                     df_group_data = df_circle_data[df_circle_data['Audit Group Number'] == grp_num]
# # #                     if not df_group_data.empty:
# # #                         group_labels_in_circle.append(f"Audit Group {grp_num}")
# # #                         group_dfs_in_circle.append(df_group_data)
                
# # #                 if not group_labels_in_circle:
# # #                     st.write(f"No specific audit group data found within {circle_label}.")
# # #                     continue

# # #                 # Horizontal tabs for Audit Groups
# # #                 # Note: Styling st.tabs hover effect needs global CSS targeting .stTabs
# # #                 group_st_tabs_widgets = st.tabs(group_labels_in_circle)

# # #                 for i, group_tab_content in enumerate(group_st_tabs_widgets):
# # #                     with group_tab_content:
# # #                         df_current_group_agenda = group_dfs_in_circle[i]
# # #                         unique_trade_names_agenda = df_current_group_agenda['Trade Name'].dropna().unique()

# # #                         if not unique_trade_names_agenda.any():
# # #                             st.write("No trade names with DARs found for this group.")
# # #                             continue
                        
# # #                         st.markdown(f"**DARs by Trade Name for {group_labels_in_circle[i]}:**", unsafe_allow_html=True)
                        
# # #                         selected_trade_key = f"selected_trade_{circle_num}_{group_labels_in_circle[i]}"

# # #                         for tn_idx, trade_name_agenda in enumerate(unique_trade_names_agenda):
# # #                             trade_button_key = f"trade_btn_{circle_num}_{group_labels_in_circle[i].replace(' ','_')}_{tn_idx}"
# # #                             if st.button(f"{trade_name_agenda}", key=trade_button_key, help=f"Show paras for {trade_name_agenda}"):
# # #                                 st.session_state[selected_trade_key] = trade_name_agenda
                            
# # #                             if st.session_state.get(selected_trade_key) == trade_name_agenda:
# # #                                 st.markdown(f"<h5 style='font-size:14pt; margin-top:10px;'>Gist of Audit Paras for: {trade_name_agenda}</h5>", unsafe_allow_html=True)
# # #                                 df_trade_paras_agenda = df_current_group_agenda[df_current_group_agenda['Trade Name'] == trade_name_agenda]
                                
# # #                                 html_table = """
# # #                                 <style>
# # #                                     .paras-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 11pt; }
# # #                                     .paras-table th, .paras-table td { border: 1px solid #ddd; padding: 6px; text-align: left; }
# # #                                     .paras-table th { background-color: #343a40; color: white; font-size: 12pt; }
# # #                                     .paras-table tr:nth-child(even) { background-color: #f2f2f2; }
# # #                                     .amount-col { text-align: right !important; }
# # #                                 </style>
# # #                                 <table class='paras-table'>
# # #                                     <tr><th>Para No.</th><th>Para Title</th><th>Detection (Rs)</th><th>Recovery (Rs)</th><th>Status</th></tr>
# # #                                 """
# # #                                 total_detection_tn = 0
# # #                                 total_recovery_tn = 0

# # #                                 for _, para_row_agenda in df_trade_paras_agenda.iterrows():
# # #                                     detection_rs_val = para_row_agenda.get('Revenue Involved (Lakhs Rs)', 0) * 100000 if pd.notna(para_row_agenda.get('Revenue Involved (Lakhs Rs)')) else 0
# # #                                     recovery_rs_val = para_row_agenda.get('Revenue Recovered (Lakhs Rs)', 0) * 100000 if pd.notna(para_row_agenda.get('Revenue Recovered (Lakhs Rs)')) else 0
# # #                                     total_detection_tn += detection_rs_val
# # #                                     total_recovery_tn += recovery_rs_val
                                    
# # #                                     html_table += f"""
# # #                                     <tr>
# # #                                         <td>{para_row_agenda.get('Audit Para Number', 'N/A')}</td>
# # #                                         <td>{para_row_agenda.get('Audit Para Heading', 'N/A')}</td>
# # #                                         <td class='amount-col'>{detection_rs_val:,.0f}</td>
# # #                                         <td class='amount-col'>{recovery_rs_val:,.0f}</td>
# # #                                         <td>{para_row_agenda.get('Status of para', 'N/A')}</td>
# # #                                     </tr>"""
# # #                                 html_table += "</table>"
# # #                                 st.markdown(html_table, unsafe_allow_html=True)
# # #                                 st.markdown(f"**Total Detection for {trade_name_agenda}: Rs. {total_detection_tn:,.0f}**")
# # #                                 st.markdown(f"**Total Recovery for {trade_name_agenda}: Rs. {total_recovery_tn:,.0f}**")
# # #                                 st.markdown("<hr style='border-top: 1px solid #ccc;'>", unsafe_allow_html=True)
        
# # #         st.markdown("---")
# # #         # --- Compile PDF Button ---
# # #         if st.button("Compile DARs into PDF", key="compile_mcm_agenda_pdf_btn", type="primary", use_container_width=True):
# # #             if df_period_data.empty:
# # #                 st.error("No data loaded for the selected MCM period to compile PDF.")
# # #             else:
# # #                 with st.spinner("Compiling PDF... This may take a while for many DARs."):
# # #                     try:
# # #                         final_pdf_buffer = BytesIO()
# # #                         pdf_writer = PdfWriter()

# # #                         # 1. Cover Page
# # #                         cover_buffer_io = BytesIO()
# # #                         title_text_cover = f"Audit Paras for the MCM {month_year_str}"
# # #                         subtitle_text_cover = "Audit 1 Commissionerate Mumbai" # Customize as needed
# # #                         create_cover_page_pdf(cover_buffer_io, title_text_cover, subtitle_text_cover)
# # #                         cover_pdf = PdfReader(cover_buffer_io)
# # #                         pdf_writer.add_page(cover_pdf.pages[0])
                        
# # #                         current_page_offset_for_index = len(pdf_writer.pages) # Page number where index will start

# # #                         # Prepare data for index and high-value table
# # #                         df_for_pdf = df_period_data.dropna(subset=['DAR PDF URL', 'Trade Name', 'Audit Circle Number']).copy()
# # #                         df_for_pdf['Audit Circle Number'] = pd.to_numeric(df_for_pdf['Audit Circle Number'], errors='coerce').fillna(0).astype(int)

# # #                         index_items_list = []
# # #                         dar_pdf_objects_for_merge = [] # Store (trade_name, circle, pdf_reader_object)
# # #                         processed_urls_for_index = set()

# # #                         # Pre-fetch DARs to count pages and prepare for merging
# # #                         dar_page_count_map = {}
# # #                         if drive_service:
# # #                             for idx_dar, dar_row_info in df_for_pdf.iterrows():
# # #                                 dar_url = dar_row_info.get('DAR PDF URL')
# # #                                 if pd.notna(dar_url) and dar_url not in dar_page_count_map: # Process each URL once
# # #                                     file_id_dar = get_file_id_from_drive_url(dar_url)
# # #                                     if file_id_dar:
# # #                                         try:
# # #                                             req_dar = drive_service.files().get_media(fileId=file_id_dar)
# # #                                             fh_dar_content = BytesIO(); MediaIoBaseDownload(fh_dar_content, req_dar).next_chunk()
# # #                                             fh_dar_content.seek(0)
# # #                                             dar_reader_obj = PdfReader(fh_dar_content)
# # #                                             dar_page_count_map[dar_url] = len(dar_reader_obj.pages)
# # #                                             dar_pdf_objects_for_merge.append({
# # #                                                 'circle': dar_row_info.get('Audit Circle Number'),
# # #                                                 'trade_name': dar_row_info.get('Trade Name'),
# # #                                                 'dar_url': dar_url, # For ordering if needed
# # #                                                 'pdf_reader': dar_reader_obj,
# # #                                                 'num_pages': len(dar_reader_obj.pages)
# # #                                             })
# # #                                         except Exception as e_fetch:
# # #                                             st.warning(f"Failed to fetch/read PDF {dar_url}: {e_fetch}")
# # #                                             dar_page_count_map[dar_url] = 1 # Default to 1 page on error for index
# # #                                             dar_pdf_objects_for_merge.append({'circle': dar_row_info.get('Audit Circle Number'), 'trade_name': dar_row_info.get('Trade Name'), 'dar_url': dar_url, 'pdf_reader': None, 'num_pages': 1})
# # #                                     else: dar_page_count_map[dar_url] = 1 # Default if no valid ID

# # #                         # Sort dar_pdf_objects_for_merge by circle then trade name for consistent ordering
# # #                         dar_pdf_objects_for_merge.sort(key=lambda x: (x['circle'], x['trade_name']))
                        
# # #                         # Generate index items based on pre-fetched DARs
# # #                         page_counter_for_index = current_page_offset_for_index + 2 # Account for index page itself + HV table page (approx)
# # #                         for dar_info in dar_pdf_objects_for_merge:
# # #                              index_items_list.append({
# # #                                 'circle': f"Circle {int(dar_info['circle'])}", 
# # #                                 'trade_name': dar_info['trade_name'], 
# # #                                 'num_pages_in_dar': dar_info['num_pages'], # This is actual pages in this DAR
# # #                                 'page_number_placeholder': page_counter_for_index # This will be its starting page
# # #                             })
# # #                              page_counter_for_index += dar_info['num_pages']
                        
# # #                         # 2. Index Page
# # #                         index_buffer_io = BytesIO()
# # #                         # The start_page_offset for index is after cover page
# # #                         create_index_page_pdf(index_buffer_io, index_items_list, current_page_offset_for_index + 1)
# # #                         index_pdf = PdfReader(index_buffer_io)
# # #                         for page_idx in range(len(index_pdf.pages)): pdf_writer.add_page(index_pdf.pages[page_idx])
# # #                         current_page_offset_for_index += len(index_pdf.pages)

# # #                         # 3. High-Value Paras Table
# # #                         df_hv_paras = df_period_data[ (df_period_data['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000].copy()
# # #                         df_hv_paras.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
# # #                         if not df_hv_paras.empty:
# # #                             hv_buffer_io = BytesIO()
# # #                             create_high_value_paras_pdf(hv_buffer_io, df_hv_paras)
# # #                             hv_pdf = PdfReader(hv_buffer_io)
# # #                             for page_idx in range(len(hv_pdf.pages)): pdf_writer.add_page(hv_pdf.pages[page_idx])
                        
# # #                         # 4. Merge actual DAR PDFs
# # #                         for dar_info_merge in dar_pdf_objects_for_merge:
# # #                             if dar_info_merge['pdf_reader']:
# # #                                 for page_content in dar_info_merge['pdf_reader'].pages:
# # #                                     pdf_writer.add_page(page_content)
# # #                             else: # Add placeholder if reader is None (fetch failed)
# # #                                 ph_buffer = BytesIO(); ph_doc_temp = SimpleDocTemplate(ph_buffer, pagesize=A4)
# # #                                 ph_story_temp = [Paragraph(f"Content for {dar_info_merge['trade_name']} (URL: {dar_info_merge['dar_url']}) could not be loaded due to earlier error.", getSampleStyleSheet()['Normal'])]
# # #                                 ph_doc_temp.build(ph_story_temp); ph_buffer.seek(0)
# # #                                 ph_reader_temp = PdfReader(ph_buffer)
# # #                                 if ph_reader_temp.pages: pdf_writer.add_page(ph_reader_temp.pages[0])


# # #                         pdf_writer.write(final_pdf_buffer)
# # #                         final_pdf_buffer.seek(0)
                        
# # #                         pdf_file_download_name = f"MCM_Agenda_{month_year_str.replace(' ', '_')}.pdf"
# # #                         st.download_button(label="Download Compiled PDF Agenda", data=final_pdf_buffer, file_name=pdf_file_download_name, mime="application/pdf")
# # #                     except Exception as e_compile_pdf:
# # #                         st.error(f"An error occurred during PDF compilation: {e_compile_pdf}")
# # #                         import traceback
# # #                         st.error(traceback.format_exc()) # Full traceback for debugging

# # #     st.markdown("</div>", unsafe_allow_html=True)
