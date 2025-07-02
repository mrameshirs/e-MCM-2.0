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
# from reportlab.pdfgen import canvas

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


# def create_page_number_stamp_pdf(buffer, page_num, total_pages):
#     """
#     Creates a PDF in memory with 'Page X of Y' at the bottom center.
#     This will be used as a "stamp" to overlay on existing pages.
#     """
#     c = canvas.Canvas(buffer, pagesize=A4)
#     c.setFont('Helvetica', 9)
#     c.setFillColor(colors.darkgrey)
#     # Draws the string 'Page X of Y' centered at the bottom of the page
#     c.drawCentredString(A4[0] / 2.0, 0.5 * inch, f"Page {page_num} of {total_pages}")
#     c.save()
#     buffer.seek(0)
#     return buffer


# # --- PDF Generation Functions ---
# def create_cover_page_pdf(buffer, title_text, subtitle_text):
#     doc = SimpleDocTemplate(
#         buffer,
#         pagesize=A4,
#         topMargin=1.5 * inch,
#         bottomMargin=1.5 * inch,
#         leftMargin=1 * inch,
#         rightMargin=1 * inch
#     )
#     styles = getSampleStyleSheet()
#     story = []
#     title_style = ParagraphStyle(
#         'AgendaCoverTitle',
#         parent=styles['h1'],
#         fontName='Helvetica-Bold',
#         fontSize=28,
#         alignment=TA_CENTER,
#         textColor=colors.HexColor("#dc3545"),
#         spaceBefore=1 * inch,
#         spaceAfter=0.3 * inch
#     )
#     story.append(Paragraph(title_text, title_style))
#     story.append(Spacer(1, 0.3 * inch))
#     subtitle_style = ParagraphStyle(
#         'AgendaCoverSubtitle',
#         parent=styles['h2'],
#         fontName='Helvetica',
#         fontSize=16,
#         alignment=TA_CENTER,
#         textColor=colors.darkslategray,
#         spaceAfter=2 * inch
#     )
#     story.append(Paragraph(subtitle_text, subtitle_style))
#     doc.build(story)
#     buffer.seek(0)
#     return buffer


# def create_index_page_pdf(buffer, index_data_list, start_page_offset_for_index_table):
#     doc = SimpleDocTemplate(
#         buffer,
#         pagesize=A4,
#         leftMargin=0.75 * inch,
#         rightMargin=0.75 * inch,
#         topMargin=0.75 * inch,
#         bottomMargin=0.75 * inch
#     )
#     styles = getSampleStyleSheet()
#     story = []
#     story.append(Paragraph("<b>Index of DARs</b>", styles['h1']))
#     story.append(Spacer(1, 0.2 * inch))
#     table_data = [[
#         Paragraph("<b>Audit Circle</b>", styles['Normal']),
#         Paragraph("<b>Trade Name of DAR</b>", styles['Normal']),
#         Paragraph("<b>Start Page</b>", styles['Normal'])
#     ]]

#     for item in index_data_list:
#         table_data.append([
#             Paragraph(str(item['circle']), styles['Normal']),
#             Paragraph(html.escape(item['trade_name']), styles['Normal']),
#             Paragraph(str(item['start_page_in_final_pdf']), styles['Normal'])
#         ])
#     col_widths = [1.5 * inch, 4 * inch, 1.5 * inch]
#     index_table = Table(table_data, colWidths=col_widths)
#     index_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, -1), 10),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
#         ('TOPPADDING', (0, 0), (-1, -1), 5),
#         ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)
#     ]))
#     story.append(index_table)
#     doc.build(story)
#     buffer.seek(0)
#     return buffer


# def create_high_value_paras_pdf(buffer, df_high_value_paras_data):
#     doc = SimpleDocTemplate(
#         buffer,
#         pagesize=A4,
#         leftMargin=0.75 * inch,
#         rightMargin=0.75 * inch,
#         topMargin=0.75 * inch,
#         bottomMargin=0.75 * inch
#     )
#     styles = getSampleStyleSheet()
#     story = []
#     story.append(Paragraph("<b>High-Value Audit Paras (> 5 Lakhs Detection)</b>", styles['h1']))
#     story.append(Spacer(1, 0.2 * inch))
#     table_data_hv = [[
#         Paragraph("<b>Audit Group</b>", styles['Normal']),
#         Paragraph("<b>Para No.</b>", styles['Normal']),
#         Paragraph("<b>Para Title</b>", styles['Normal']),
#         Paragraph("<b>Detected (Rs)</b>", styles['Normal']),
#         Paragraph("<b>Recovered (Rs)</b>", styles['Normal'])
#     ]]
#     for _, row_hv in df_high_value_paras_data.iterrows():
#         table_data_hv.append([
#             Paragraph(html.escape(str(row_hv.get("Audit Group Number", "N/A"))), styles['Normal']),
#             Paragraph(html.escape(str(row_hv.get("Audit Para Number", "N/A"))), styles['Normal']),
#             Paragraph(html.escape(str(row_hv.get("Audit Para Heading", "N/A"))[:100]), styles['Normal']),
#             Paragraph(f"{row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal']),
#             Paragraph(f"{row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000:,.0f}", styles['Normal'])
#         ])

#     col_widths_hv = [1 * inch, 0.7 * inch, 3 * inch, 1.4 * inch, 1.4 * inch]
#     hv_table = Table(table_data_hv, colWidths=col_widths_hv)
#     hv_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
#         ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, -1), 9),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
#         ('TOPPADDING', (0, 0), (-1, -1), 4),
#         ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)
#     ]))
#     story.append(hv_table)
#     doc.build(story)
#     buffer.seek(0)
#     return buffer


# def create_placeholder_pdf(buffer, trade_name, dar_url, error_msg="Failed to load"):
#     """Create a proper placeholder PDF when DAR fails to load"""
#     doc = SimpleDocTemplate(
#         buffer,
#         pagesize=A4,
#         leftMargin=1 * inch,
#         rightMargin=1 * inch,
#         topMargin=1 * inch,
#         bottomMargin=1 * inch
#     )
#     styles = getSampleStyleSheet()
#     story = []

#     story.append(Paragraph(f"<b>DAR for: {html.escape(trade_name)}</b>", styles['h1']))
#     story.append(Spacer(1, 0.3 * inch))
#     story.append(Paragraph(f"Status: {html.escape(error_msg)}", styles['Normal']))
#     story.append(Spacer(1, 0.2 * inch))
#     story.append(Paragraph(f"URL: {html.escape(dar_url)}", styles['Normal']))
#     story.append(Spacer(1, 0.3 * inch))
#     story.append(Paragraph("Please check the source document manually.", styles['Normal']))

#     doc.build(story)
#     buffer.seek(0)
#     return buffer


# def safe_pdf_download(drive_service, file_id, max_retries=3):
#     """Safely download and read PDF with retries"""
#     for attempt in range(max_retries):
#         try:
#             request = drive_service.files().get_media(fileId=file_id)
#             file_buffer = BytesIO()
#             downloader = MediaIoBaseDownload(file_buffer, request)
#             done = False
#             while not done:
#                 status, done = downloader.next_chunk(num_retries=2)
#             file_buffer.seek(0)

#             # Try to read the PDF
#             pdf_reader = PdfReader(file_buffer)
#             # Validate that the PDF has readable pages
#             if pdf_reader.pages and len(pdf_reader.pages) > 0:
#                 # Test read the first page to ensure it's not corrupted
#                 try:
#                     _ = pdf_reader.pages[0]
#                     return pdf_reader, len(pdf_reader.pages)
#                 except Exception as page_error:
#                     if attempt == max_retries - 1:
#                         raise Exception(f"PDF pages unreadable: {page_error}")
#                     continue
#             else:
#                 if attempt == max_retries - 1:
#                     raise Exception("PDF has no readable pages")
#                 continue

#         except Exception as e:
#             if attempt == max_retries - 1:
#                 raise e
#             continue

#     return None, 0


# # --- End PDF Generation Functions ---

# def calculate_audit_circle_agenda(audit_group_number_val):
#     try:
#         agn = int(audit_group_number_val)
#         if 1 <= agn <= 30:
#             return math.ceil(agn / 3.0)
#         return 0
#     except (ValueError, TypeError, AttributeError):
#         return 0

# def create_page_number_stamp_pdf_fixed(buffer, page_num, total_pages):
#     """
#     Fixed version - Creates a PDF with page numbers that will actually show up
#     """
#     # Create canvas with proper settings
#     c = canvas.Canvas(buffer, pagesize=A4)
    
#     # Set font and color with higher visibility
#     c.setFont('Helvetica-Bold', 10)  # Slightly larger and bold
#     c.setFillColor(colors.black)     # Use black instead of grey
#     c.setStrokeColor(colors.black)
    
#     # Get page dimensions
#     width, height = A4
    
#     # Position at bottom center with more margin from bottom
#     x_position = width / 2.0
#     y_position = 0.75 * inch  # Higher from bottom edge
    
#     # Draw the page number
#     page_text = f"Page {page_num} of {total_pages}"
#     c.drawCentredString(x_position, y_position, page_text)
    
#     # Optional: Add a small line or border to make it more visible
#     # c.line(x_position - 50, y_position - 5, x_position + 50, y_position - 5)
    
#     # Finalize the PDF
#     c.save()
#     buffer.seek(0)
#     return buffer

# def create_page_number_overlay_alternative(page_num, total_pages):
#     """
#     Alternative approach - create overlay PDF with better positioning
#     """
#     buffer = BytesIO()
#     c = canvas.Canvas(buffer, pagesize=A4)
    
#     # Set font and styling
#     c.setFont('Helvetica', 9)
#     c.setFillColor(colors.darkgrey)
    
#     # Calculate position (bottom center)
#     width, height = A4
#     x = width / 2.0
#     y = 30  # 30 points from bottom (about 0.4 inches)
    
#     # Draw page number
#     text = f"Page {page_num} of {total_pages}"
#     c.drawCentredString(x, y, text)
    
#     # Save and return
#     c.save()
#     buffer.seek(0)
#     return buffer

# def add_page_numbers_to_pdf_improved(input_pdf_buffer, output_buffer):
#     """
#     Improved method to add page numbers to existing PDF
#     """
#     # Read the input PDF
#     reader = PdfReader(input_pdf_buffer)
#     writer = PdfWriter()
#     total_pages = len(reader.pages)
    
#     for page_num, page in enumerate(reader.pages, 1):
#         # Create page number overlay
#         overlay_buffer = create_page_number_overlay_alternative(page_num, total_pages)
#         overlay_reader = PdfReader(overlay_buffer)
#         overlay_page = overlay_reader.pages[0]
        
#         # Create a new page by merging
#         new_page = page
        
#         # Try different merge methods
#         try:
#             # Method 1: Standard merge
#             new_page.merge_page(overlay_page)
#         except Exception as e1:
#             try:
#                 # Method 2: Merge with transformation
#                 new_page.merge_transformed_page(overlay_page, [1, 0, 0, 1, 0, 0])
#             except Exception as e2:
#                 # Method 3: Add as separate layer (fallback)
#                 print(f"Warning: Could not merge page number on page {page_num}: {e1}, {e2}")
#                 # Just add the original page without numbers
#                 pass
        
#         writer.add_page(new_page)
    
#     # Write to output buffer
#     writer.write(output_buffer)
#     output_buffer.seek(0)
#     return output_buffer

# # Updated main PDF compilation section
# def compile_mcm_pdf_with_working_page_numbers(final_pdf_merger, month_year_str):
#     """
#     Fixed version of the PDF compilation with working page numbers
#     """
#     try:
#         # First, create the merged PDF without page numbers
#         temp_buffer = BytesIO()
#         final_pdf_merger.write(temp_buffer)
#         temp_buffer.seek(0)
        
#         # Now add page numbers using the improved method
#         final_output_buffer = BytesIO()
#         add_page_numbers_to_pdf_improved(temp_buffer, final_output_buffer)
        
#         return final_output_buffer
        
#     except Exception as e:
#         print(f"Error in PDF compilation: {e}")
#         # Fallback: return PDF without page numbers
#         fallback_buffer = BytesIO()
#         final_pdf_merger.write(fallback_buffer)
#         fallback_buffer.seek(0)
#         return fallback_buffer

# # Alternative approach using reportlab's built-in page numbering
# def create_pdf_with_built_in_page_numbers(story_elements, output_buffer):
#     """
#     Alternative: Use reportlab's built-in page numbering
#     """
#     from reportlab.platypus import SimpleDocTemplate, PageBreak
#     from reportlab.lib.styles import getSampleStyleSheet
#     from reportlab.platypus.tableofcontents import TableOfContents
    
#     class NumberedCanvas(canvas.Canvas):
#         def __init__(self, *args, **kwargs):
#             canvas.Canvas.__init__(self, *args, **kwargs)
#             self._saved_page_states = []
    
#         def showPage(self):
#             self._saved_page_states.append(dict(self.__dict__))
#             self._startPage()
    
#         def save(self):
#             num_pages = len(self._saved_page_states)
#             for (page_num, page_state) in enumerate(self._saved_page_states):
#                 self.__dict__.update(page_state)
#                 self.draw_page_number(page_num + 1, num_pages)
#                 canvas.Canvas.showPage(self)
#             canvas.Canvas.save(self)
    
#         def draw_page_number(self, page_num, total_pages):
#             self.setFont("Helvetica", 9)
#             self.setFillColor(colors.black)
#             self.drawCentredString(A4[0]/2.0, 0.75*inch, f"Page {page_num} of {total_pages}")
    
#     # Create document with numbered canvas
#     doc = SimpleDocTemplate(output_buffer, pagesize=A4, 
#                           leftMargin=0.75*inch, rightMargin=0.75*inch,
#                           topMargin=0.75*inch, bottomMargin=1*inch)
    
#     # Build with custom canvas
#     doc.build(story_elements, canvasmaker=NumberedCanvas)
#     output_buffer.seek(0)
#     return output_buffer

# # Debug function to check if page numbers are actually being added
# def debug_page_number_addition():
#     """
#     Simple test to verify page numbering works
#     """
#     # Create a simple test PDF
#     test_buffer = BytesIO()
#     c = canvas.Canvas(test_buffer, pagesize=A4)
    
#     # Add a few test pages
#     for i in range(3):
#         c.drawString(100, 750, f"This is test page {i+1}")
#         c.showPage()
    
#     c.save()
#     test_buffer.seek(0)
    
#     # Now add page numbers
#     output_buffer = BytesIO()
#     add_page_numbers_to_pdf_improved(test_buffer, output_buffer)
    
#     return output_buffer
# def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
#     st.markdown("### MCM Agenda Preparation")

#     if not mcm_periods:
#         st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
#         return

#     period_options = {
#         k: f"{v.get('month_name')} {v.get('year')}"
#         for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True)
#         if v.get('month_name') and v.get('year')
#     }
#     if not period_options:
#         st.warning("No valid MCM periods with complete month and year information available.")
#         return

#     selected_period_key = st.selectbox(
#         "Select MCM Period for Agenda",
#         options=list(period_options.keys()),
#         format_func=lambda k: period_options[k],
#         key="mcm_agenda_period_select_v3_full"
#     )

#     if not selected_period_key:
#         st.info("Please select an MCM period.")
#         return

#     selected_period_info = mcm_periods[selected_period_key]
#     month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
#     st.markdown(
#         f"<h2 style='text-align: center; color: #007bff; font-size: 22pt; margin-bottom:10px;'>"
#         f"MCM Audit Paras for {month_year_str}</h2>",
#         unsafe_allow_html=True
#     )
#     st.markdown("---")

#     df_period_data_full = pd.DataFrame()
#     if sheets_service and selected_period_info.get('spreadsheet_id'):
#         with st.spinner(f"Loading data for {month_year_str}..."):
#             df_period_data_full = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])

#     if df_period_data_full is None or df_period_data_full.empty:
#         st.info(f"No data found in the spreadsheet for {month_year_str}.")
#     else:
#         # Ensure correct data types for key columns
#         cols_to_convert_numeric = [
#             'Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)',
#             'Total Amount Recovered (Overall Rs)', 'Audit Para Number',
#             'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)'
#         ]
#         for col_name in cols_to_convert_numeric:
#             if col_name in df_period_data_full.columns:
#                 df_period_data_full[col_name] = pd.to_numeric(df_period_data_full[col_name], errors='coerce')
#             else:
#                 df_period_data_full[col_name] = 0 if "Amount" in col_name or "Revenue" in col_name else pd.NA

#         # Derive/Validate Audit Circle Number
#         circle_col_to_use = 'Audit Circle Number'  # Default to using sheet column
#         if (
#             'Audit Circle Number' not in df_period_data_full.columns or
#             not df_period_data_full['Audit Circle Number'].notna().any() or
#             not pd.to_numeric(df_period_data_full['Audit Circle Number'], errors='coerce').fillna(0).astype(int).gt(0).any()
#         ):
#             if 'Audit Group Number' in df_period_data_full.columns and df_period_data_full['Audit Group Number'].notna().any():
#                 df_period_data_full['Derived Audit Circle Number'] = (
#                     df_period_data_full['Audit Group Number'].apply(calculate_audit_circle_agenda).fillna(0).astype(int)
#                 )
#                 circle_col_to_use = 'Derived Audit Circle Number'
#                 st.caption("Using derived 'Audit Circle Number' as sheet column was missing/invalid.")
#             else:
#                 # If derived also cannot be made, create a placeholder to avoid errors
#                 if 'Derived Audit Circle Number' not in df_period_data_full.columns:
#                     df_period_data_full['Derived Audit Circle Number'] = 0
#                 circle_col_to_use = 'Derived Audit Circle Number'  # Fallback to potentially zeroed derived col
#                 st.warning("'Audit Circle Number' could not be determined reliably from sheet or derived.")
#         else:  # Sheet column exists and seems valid
#             df_period_data_full['Audit Circle Number'] = (
#                 df_period_data_full['Audit Circle Number'].fillna(0).astype(int)
#             )
#             # circle_col_to_use is already 'Audit Circle Number'

#         # Vertical collapsible tabs for Audit Circles
#         for circle_num_iter in range(1, 11):
#             circle_label_iter = f"Audit Circle {circle_num_iter}"
#             # Ensure using the correctly determined or derived circle column name
#             df_circle_iter_data = df_period_data_full[df_period_data_full[circle_col_to_use] == circle_num_iter]

#             expander_header_html = (
#                 f"<div style='background-color:#007bff; color:white; padding:10px 15px; "
#                 f"border-radius:5px; margin-top:12px; margin-bottom:3px; font-weight:bold; font-size:16pt;'>"
#                 f"{html.escape(circle_label_iter)}</div>"
#             )
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
#                         unique_trade_names_list = (
#                             df_current_grp_item.get('Trade Name', pd.Series(dtype='str')).dropna().unique()
#                         )

#                         if not unique_trade_names_list.any():
#                             st.write("No trade names with DARs found for this group.")
#                             continue

#                         st.markdown(f"**DARs for {group_labels_list[i]}:**", unsafe_allow_html=True)
#                         session_key_selected_trade = (
#                             f"selected_trade_{circle_num_iter}_{group_labels_list[i].replace(' ', '_')}"
#                         )

#                         for tn_idx_iter, trade_name_item in enumerate(unique_trade_names_list):
#                             trade_name_data_for_pdf_url = df_current_grp_item[
#                                 df_current_grp_item['Trade Name'] == trade_name_item
#                             ]
#                             dar_pdf_url_item = None
#                             if not trade_name_data_for_pdf_url.empty and 'DAR PDF URL' in trade_name_data_for_pdf_url.columns:
#                                 dar_pdf_url_item = trade_name_data_for_pdf_url['DAR PDF URL'].iloc[0]

#                             cols_trade_display = st.columns([0.7, 0.3])
#                             with cols_trade_display[0]:
#                                 if st.button(
#                                     f"{trade_name_item}",
#                                     key=f"tradebtn_agenda_v3_{circle_num_iter}_{i}_{tn_idx_iter}",
#                                     help=f"Show paras for {trade_name_item}",
#                                     use_container_width=True
#                                 ):
#                                     st.session_state[session_key_selected_trade] = trade_name_item
#                             with cols_trade_display[1]:
#                                 if (
#                                     pd.notna(dar_pdf_url_item) and
#                                     isinstance(dar_pdf_url_item, str) and
#                                     dar_pdf_url_item.startswith("http")
#                                 ):
#                                     st.link_button(
#                                         "View DAR PDF",
#                                         dar_pdf_url_item,
#                                         use_container_width=True,
#                                         type="secondary"
#                                     )
#                                 else:
#                                     st.caption("No PDF Link")

#                             if st.session_state.get(session_key_selected_trade) == trade_name_item:
#                                 st.markdown(
#                                     f"<h5 style='font-size:13pt; margin-top:10px; color:#154360;'>"
#                                     f"Gist of Audit Paras for: {html.escape(trade_name_item)}</h5>",
#                                     unsafe_allow_html=True
#                                 )
#                                 df_trade_paras_item = df_current_grp_item[
#                                     df_current_grp_item['Trade Name'] == trade_name_item
#                                 ]

#                                 html_rows = ""
#                                 total_det_tn_item = 0
#                                 total_rec_tn_item = 0
#                                 for _, para_item_row in df_trade_paras_item.iterrows():
#                                     para_num = para_item_row.get("Audit Para Number", "N/A")
#                                     p_num_str = str(int(para_num)) if pd.notna(para_num) and para_num != 0 else "N/A"
#                                     p_title = html.escape(str(para_item_row.get("Audit Para Heading", "N/A")))
#                                     p_status = html.escape(str(para_item_row.get("Status of para", "N/A")))

#                                     det_lakhs = para_item_row.get('Revenue Involved (Lakhs Rs)', 0)
#                                     det_rs = (det_lakhs * 100000) if pd.notna(det_lakhs) else 0
#                                     rec_lakhs = para_item_row.get('Revenue Recovered (Lakhs Rs)', 0)
#                                     rec_rs = (rec_lakhs * 100000) if pd.notna(rec_lakhs) else 0
#                                     total_det_tn_item += det_rs
#                                     total_rec_tn_item += rec_rs

#                                     html_rows += (
#                                         f"<tr>"
#                                         f"<td>{p_num_str}</td>"
#                                         f"<td>{p_title}</td>"
#                                         f"<td class='amount-col'>{det_rs:,.0f}</td>"
#                                         f"<td class='amount-col'>{rec_rs:,.0f}</td>"
#                                         f"<td>{p_status}</td>"
#                                         f"</tr>"
#                                     )

#                                 table_full_html = (
#                                     f"<style>"
#                                     f".paras-table {{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:10pt;}}"
#                                     f".paras-table th, .paras-table td {{border:1px solid #bbb;padding:5px;text-align:left;word-wrap:break-word;}}"
#                                     f".paras-table th {{background-color:#343a40;color:white;font-size:11pt;}}"
#                                     f".paras-table tr:nth-child(even) {{background-color:#f4f6f6;}}"
#                                     f".amount-col {{text-align:right!important;}}"
#                                     f"</style>"
#                                     f"<table class='paras-table'>"
#                                     f"<tr><th>Para No.</th><th>Para Title</th><th>Detection (Rs)</th>"
#                                     f"<th>Recovery (Rs)</th><th>Status</th></tr>"
#                                     f"{html_rows}"
#                                     f"</table>"
#                                 )
#                                 st.markdown(table_full_html, unsafe_allow_html=True)
#                                 st.markdown(
#                                     f"<b>Total Detection for {html.escape(trade_name_item)}: Rs. {total_det_tn_item:,.0f}</b>",
#                                     unsafe_allow_html=True
#                                 )
#                                 st.markdown(
#                                     f"<b>Total Recovery for {html.escape(trade_name_item)}: Rs. {total_rec_tn_item:,.0f}</b>",
#                                     unsafe_allow_html=True
#                                 )
#                                 st.markdown(
#                                     "<hr style='border-top: 1px solid #ccc; margin-top:10px; margin-bottom:10px;'>",
#                                     unsafe_allow_html=True
#                                 )

#         st.markdown("---")

#         # --- Compile PDF Button ---
#         if st.button(
#             "Compile Full MCM Agenda PDF",
#             key="compile_mcm_agenda_pdf_final_v4_progress",
#             type="primary",
#             help="Generates a comprehensive PDF.",
#             use_container_width=True
#         ):
#             if df_period_data_full.empty:
#                 st.error("No data available for the selected MCM period to compile into PDF.")
#             else:
#                 status_message_area = st.empty()
#                 progress_bar = st.progress(0)

#                 try:
#                     final_pdf_merger = PdfWriter()
#                     compiled_pdf_pages_count = 0

#                     # Filter and sort data for PDF
#                     df_for_pdf = df_period_data_full.dropna(subset=['DAR PDF URL', 'Trade Name', circle_col_to_use]).copy()
#                     df_for_pdf[circle_col_to_use] = (
#                         pd.to_numeric(df_for_pdf[circle_col_to_use], errors='coerce').fillna(0).astype(int)
#                     )

#                     # Get unique DARs, sorted for consistent processing order
#                     unique_dars_to_process = df_for_pdf.sort_values(
#                         by=[circle_col_to_use, 'Trade Name', 'DAR PDF URL']
#                     ).drop_duplicates(subset=['DAR PDF URL'])

#                     total_dars = len(unique_dars_to_process)

#                     if total_dars == 0:
#                         status_message_area.warning("No valid DARs with PDF URLs found to compile.")
#                         progress_bar.empty()
#                         st.stop()

#                     total_steps_for_pdf = 4 + (2 * total_dars)
#                     current_pdf_step = 0

#                     dar_objects_for_merge_and_index = []

#                     # Step 1: Pre-fetch DAR PDFs to count pages
#                     if drive_service:
#                         status_message_area.info(f"Pre-fetching {total_dars} DAR PDFs to count pages and prepare content...")
#                         for idx, (_, dar_row) in enumerate(unique_dars_to_process.iterrows()):
#                             current_pdf_step += 1
#                             dar_url_val = dar_row.get('DAR PDF URL')
#                             file_id_val = get_file_id_from_drive_url(dar_url_val)
#                             num_pages_val = 1  # Default in case of fetch failure
#                             reader_obj_val = None
#                             trade_name_val = dar_row.get('Trade Name', 'Unknown DAR')
#                             circle_val = f"Circle {int(dar_row.get(circle_col_to_use, 0))}"

#                             status_message_area.info(
#                                 f"Step {current_pdf_step}/{total_steps_for_pdf}: "
#                                 f"Fetching DAR {idx + 1}/{total_dars} for {trade_name_val}..."
#                             )

#                             if file_id_val:
#                                 try:
#                                     reader_obj_val, num_pages_val = safe_pdf_download(drive_service, file_id_val)
#                                     if reader_obj_val is None:
#                                         st.warning(f"Failed to download PDF for {trade_name_val}. Using placeholder.")
#                                         num_pages_val = 1
#                                 except Exception as e_fetch_val:
#                                     st.warning(
#                                         f"PDF Read Error for {trade_name_val} ({dar_url_val}): {e_fetch_val}. "
#                                         f"Using placeholder."
#                                     )
#                                     reader_obj_val = None
#                                     num_pages_val = 1
#                             else:
#                                 st.warning(f"Could not extract file ID from URL for {trade_name_val}. Using placeholder.")

#                             dar_objects_for_merge_and_index.append({
#                                 'circle': circle_val,
#                                 'trade_name': trade_name_val,
#                                 'num_pages_in_dar': num_pages_val,
#                                 'pdf_reader': reader_obj_val,
#                                 'dar_url': dar_url_val
#                             })
#                             progress_bar.progress(current_pdf_step / total_steps_for_pdf)
#                     else:
#                         status_message_area.error("Google Drive service not available.")
#                         progress_bar.empty()
#                         st.stop()

#                     # Step 2: Cover Page
#                     current_pdf_step += 1
#                     status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Cover Page...")
#                     cover_buffer = BytesIO()
#                     create_cover_page_pdf(cover_buffer, f"Audit Paras for MCM {month_year_str}", "Audit 1 Commissionerate Mumbai")
#                     cover_reader = PdfReader(cover_buffer)
#                     final_pdf_merger.append(cover_reader)
#                     compiled_pdf_pages_count += len(cover_reader.pages)
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)

#                     # Step 3: High-Value Paras Table
#                     current_pdf_step += 1
#                     status_message_area.info(
#                         f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating High-Value Paras Table..."
#                     )
#                     df_hv_data = df_period_data_full[
#                         (df_period_data_full['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000
#                     ].copy()
#                     df_hv_data.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
#                     hv_pages_count = 0
#                     if not df_hv_data.empty:
#                         hv_buffer = BytesIO()
#                         create_high_value_paras_pdf(hv_buffer, df_hv_data)
#                         hv_reader = PdfReader(hv_buffer)
#                         final_pdf_merger.append(hv_reader)
#                         hv_pages_count = len(hv_reader.pages)
#                     compiled_pdf_pages_count += hv_pages_count
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)

#                     # Step 4: Calculate start pages for index and prepare index data
#                     current_pdf_step += 1
#                     status_message_area.info(
#                         f"Step {current_pdf_step}/{total_steps_for_pdf}: Calculating page numbers for index..."
#                     )

#                     index_data_for_final = []
#                     current_start_page = compiled_pdf_pages_count + 2  # +1 for index page itself, +1 for 1-based indexing

#                     for dar_item in dar_objects_for_merge_and_index:
#                         index_data_for_final.append({
#                             'circle': dar_item['circle'],
#                             'trade_name': dar_item['trade_name'],
#                             'start_page_in_final_pdf': current_start_page
#                         })
#                         current_start_page += dar_item['num_pages_in_dar']

#                     # Generate Index Page
#                     index_buffer = BytesIO()
#                     create_index_page_pdf(index_buffer, index_data_for_final, compiled_pdf_pages_count + 1)
#                     index_reader = PdfReader(index_buffer)
#                     final_pdf_merger.append(index_reader)
#                     compiled_pdf_pages_count += len(index_reader.pages)
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)

#                     # Step 5: Add all DAR PDFs
#                     for idx, dar_item in enumerate(dar_objects_for_merge_and_index):
#                         current_pdf_step += 1
#                         status_message_area.info(
#                             f"Step {current_pdf_step}/{total_steps_for_pdf}: "
#                             f"Adding DAR {idx + 1}/{total_dars} - {dar_item['trade_name']}..."
#                         )

#                         if dar_item['pdf_reader'] is not None:
#                             try:
#                                 # Add the actual DAR PDF
#                                 final_pdf_merger.append(dar_item['pdf_reader'])
#                                 compiled_pdf_pages_count += dar_item['num_pages_in_dar']
#                             except Exception as merge_error:
#                                 st.warning(f"Error merging DAR for {dar_item['trade_name']}: {merge_error}. Adding placeholder.")
#                                 # Create placeholder PDF
#                                 placeholder_buffer = BytesIO()
#                                 create_placeholder_pdf(
#                                     placeholder_buffer,
#                                     dar_item['trade_name'],
#                                     dar_item['dar_url'],
#                                     f"Merge Error: {merge_error}"
#                                 )
#                                 placeholder_reader = PdfReader(placeholder_buffer)
#                                 final_pdf_merger.append(placeholder_reader)
#                                 compiled_pdf_pages_count += len(placeholder_reader.pages)
#                         else:
#                             # Add placeholder PDF for failed downloads
#                             placeholder_buffer = BytesIO()
#                             create_placeholder_pdf(
#                                 placeholder_buffer,
#                                 dar_item['trade_name'],
#                                 dar_item['dar_url'],
#                                 "Failed to download PDF"
#                             )
#                             placeholder_reader = PdfReader(placeholder_buffer)
#                             final_pdf_merger.append(placeholder_reader)
#                             compiled_pdf_pages_count += len(placeholder_reader.pages)

#                         progress_bar.progress(current_pdf_step / total_steps_for_pdf)

#                     # Final step: Add page numbers to all pages
#                     current_pdf_step += 1
#                     status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Adding page numbers...")

#                     # Create final PDF with page numbers
#                     final_output_buffer = BytesIO()
#                     final_pdf_with_pages = PdfWriter()

#                     # Get the merged PDF as bytes to re-read it
#                     temp_buffer = BytesIO()
#                     final_pdf_merger.write(temp_buffer)
#                     temp_buffer.seek(0)
#                     temp_reader = PdfReader(temp_buffer)

#                     total_final_pages = len(temp_reader.pages)
#                     final_output_buffer = compile_mcm_pdf_with_working_page_numbers(final_pdf_merger, month_year_str)

#                     # for page_num, page in enumerate(temp_reader.pages, 1):
#                     #     # Create page number overlay
#                     #     stamp_buffer = BytesIO()
#                     #     create_page_number_stamp_pdf(stamp_buffer, page_num, total_final_pages)
#                     #     stamp_reader = PdfReader(stamp_buffer)
#                     #     stamp_page = stamp_reader.pages[0]

#                     #     # Merge the page number onto the original page
#                     #     page.merge_page(stamp_page)
#                     #     final_pdf_with_pages.add_page(page)

#                     # Write final PDF
#                     final_pdf_with_pages.write(final_output_buffer)
#                     final_output_buffer.seek(0)

#                     progress_bar.progress(1.0)
#                     status_message_area.success(f"PDF compilation completed! Total pages: {total_final_pages}")

#                     # Provide download button
#                     st.download_button(
#                         label=f"📥 Download MCM Agenda PDF - {month_year_str}",
#                         data=final_output_buffer.getvalue(),
#                         file_name=f"MCM_Agenda_{month_year_str.replace(' ', '_')}.pdf",
#                         mime="application/pdf",
#                         type="primary",
#                         use_container_width=True
#                     )

#                     # Clear progress indicators
#                     progress_bar.empty()
#                     status_message_area.empty()

#                 except Exception as compilation_error:
#                     progress_bar.empty()
#                     status_message_area.error(f"PDF compilation failed: {compilation_error}")
#                     st.error(f"Detailed error: {str(compilation_error)}")

#                     # Provide fallback option
#                     st.info("You can try downloading individual DARs from the trade name buttons above.")


# # Additional helper function to fix blank pages issue
# def validate_pdf_reader(pdf_reader):
#     """Validate that PDF reader has readable content"""
#     if not pdf_reader or not pdf_reader.pages:
#         return False

#     try:
#         # Try to access the first page to ensure it's readable
#         first_page = pdf_reader.pages[0]
#         # Try to extract some basic info to verify the page is valid
#         _ = first_page.mediabox
#         return True
#     except Exception:
#         return False


# # Updated safe_pdf_download function to better handle corrupted PDFs
# def safe_pdf_download_improved(drive_service, file_id, max_retries=3):
#     """Improved PDF download with better corruption detection"""
#     for attempt in range(max_retries):
#         try:
#             request = drive_service.files().get_media(fileId=file_id)
#             file_buffer = BytesIO()
#             downloader = MediaIoBaseDownload(file_buffer, request)
#             done = False

#             while not done:
#                 status, done = downloader.next_chunk(num_retries=2)

#             file_buffer.seek(0)

#             # Validate the downloaded content
#             if file_buffer.tell() == 0 or len(file_buffer.getvalue()) < 100:
#                 raise Exception("Downloaded file is too small or empty")

#             file_buffer.seek(0)

#             # Try to read the PDF
#             pdf_reader = PdfReader(file_buffer)

#             # Validate PDF content
#             if not validate_pdf_reader(pdf_reader):
#                 raise Exception("PDF validation failed - corrupted or unreadable")

#             return pdf_reader, len(pdf_reader.pages)

#         except Exception as e:
#             if attempt == max_retries - 1:
#                 raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
#             # Wait a bit before retrying
#             import time
#             time.sleep(1)
#             continue

#     return None, 0
######################################################################
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
# from reportlab.pdfgen import canvas

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
    
# def create_page_number_stamp_pdf(buffer, page_num, total_pages):
#     """
#     Creates a PDF in memory with 'Page X of Y' at the bottom center.
#     This will be used as a "stamp" to overlay on existing pages.
#     """
#     c = canvas.Canvas(buffer, pagesize=A4)
#     c.setFont('Helvetica', 9)
#     c.setFillColor(colors.darkgrey)
#     # Draws the string 'Page X of Y' centered at the bottom of the page
#     c.drawCentredString(A4[0] / 2.0, 0.5 * inch, f"Page {page_num} of {total_pages}")
#     c.save()
#     buffer.seek(0)
#     return buffer
    
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
#         # # --- Compile PDF Button ---
#         # Inside mcm_agenda_tab function, replace the PDF compilation block (after the button) with this:
#         if st.button("Compile Full MCM Agenda PDF", key="compile_mcm_agenda_pdf_final_v4_progress", type="primary", help="Generates a comprehensive PDF.", use_container_width=True):
#             if df_period_data_full.empty:
#                 st.error("No data available for the selected MCM period to compile into PDF.")
#             else:
#                 status_message_area = st.empty() 
#                 progress_bar = st.progress(0)
                
#                 with st.spinner("Preparing for PDF compilation..."):
#                     final_pdf_merger = PdfWriter()
#                     compiled_pdf_pages_count = 0 
        
#                     # Filter and sort data for PDF
#                     df_for_pdf = df_period_data_full.dropna(subset=['DAR PDF URL', 'Trade Name', circle_col_to_use]).copy()
#                     df_for_pdf[circle_col_to_use] = pd.to_numeric(df_for_pdf[circle_col_to_use], errors='coerce').fillna(0).astype(int)
                    
#                     # Get unique DARs, sorted for consistent processing order
#                     unique_dars_to_process = df_for_pdf.sort_values(by=[circle_col_to_use, 'Trade Name', 'DAR PDF URL']).drop_duplicates(subset=['DAR PDF URL'])
#                     # # ===================================================================
#                     # # --- TEST CODE: Limit to 3 DARs for faster testing ---
#                     # st.info("ℹ️ TEST MODE: Compiling only the first 3 DARs found.")
#                     # unique_dars_to_process = unique_dars_to_process.head(3)
#                     # # --- END TEST CODE ---
#                     # # ===================================================================
                    
#                     total_dars = len(unique_dars_to_process)
                    
#                     dar_objects_for_merge_and_index = [] 
                    
#                     if total_dars == 0:
#                         status_message_area.warning("No valid DARs with PDF URLs found to compile.")
#                         progress_bar.empty()
#                         st.stop()
        
#                     #total_steps_for_pdf = 4 + total_dars  # Cover, High-Value, Index, each DAR, Finalize
#                     total_steps_for_pdf = 4 + (2 * total_dars)
#                     current_pdf_step = 0
        
#                     # Step 1: Pre-fetch DAR PDFs to count pages
#                     if drive_service:
#                         status_message_area.info(f"Pre-fetching {total_dars} DAR PDFs to count pages and prepare content...")
#                         for idx, dar_row in unique_dars_to_process.iterrows():
#                             current_pdf_step += 1
#                             dar_url_val = dar_row.get('DAR PDF URL')
#                             file_id_val = get_file_id_from_drive_url(dar_url_val)
#                             num_pages_val = 1  # Default in case of fetch failure
#                             reader_obj_val = None
#                             trade_name_val = dar_row.get('Trade Name', 'Unknown DAR')
#                             circle_val = f"Circle {int(dar_row.get(circle_col_to_use, 0))}"
        
#                             status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Fetching DAR {idx+1}/{total_dars} for {trade_name_val}...")
#                             if file_id_val:
#                                 try:
#                                     req_val = drive_service.files().get_media(fileId=file_id_val)
#                                     fh_val = BytesIO()
#                                     downloader = MediaIoBaseDownload(fh_val, req_val)
#                                     done = False
#                                     while not done:
#                                         status, done = downloader.next_chunk(num_retries=2)
#                                     fh_val.seek(0)
#                                     reader_obj_val = PdfReader(fh_val)
#                                     num_pages_val = len(reader_obj_val.pages) if reader_obj_val.pages else 1
#                                 except HttpError as he:
#                                     st.warning(f"PDF HTTP Error for {trade_name_val} ({dar_url_val}): {he}. Using placeholder.")
#                                 except Exception as e_fetch_val:
#                                     st.warning(f"PDF Read Error for {trade_name_val} ({dar_url_val}): {e_fetch_val}. Using placeholder.")
                            
#                             dar_objects_for_merge_and_index.append({
#                                 'circle': circle_val, 
#                                 'trade_name': trade_name_val,
#                                 'num_pages_in_dar': num_pages_val, 
#                                 'pdf_reader': reader_obj_val, 
#                                 'dar_url': dar_url_val
#                             })
#                             progress_bar.progress(current_pdf_step / total_steps_for_pdf)
#                     else:
#                         status_message_area.error("Google Drive service not available.")
#                         progress_bar.empty()
#                         st.stop()
        
#                 # Now compile with progress
#                 try:
#                     # Step 2: Cover Page
#                     current_pdf_step += 1
#                     status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Cover Page...")
#                     cover_buffer = BytesIO()
#                     create_cover_page_pdf(cover_buffer, f"Audit Paras for MCM {month_year_str}", "Audit 1 Commissionerate Mumbai")
#                     cover_reader = PdfReader(cover_buffer)
#                     final_pdf_merger.append(cover_reader)
#                     compiled_pdf_pages_count += len(cover_reader.pages)
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)
        
#                     # Step 3: High-Value Paras Table
#                     current_pdf_step += 1
#                     status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating High-Value Paras Table...")
#                     df_hv_data = df_period_data_full[(df_period_data_full['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000].copy()
#                     df_hv_data.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
#                     hv_pages_count = 0
#                     if not df_hv_data.empty:
#                         hv_buffer = BytesIO()
#                         create_high_value_paras_pdf(hv_buffer, df_hv_data)
#                         hv_reader = PdfReader(hv_buffer)
#                         final_pdf_merger.append(hv_reader)
#                         hv_pages_count = len(hv_reader.pages)
#                     compiled_pdf_pages_count += hv_pages_count
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)
        
#                     # Step 4: Index Page
#                     current_pdf_step += 1
#                     status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Generating Index Page...")
#                     index_page_actual_start = compiled_pdf_pages_count + 1
#                     dar_start_page_counter_val = index_page_actual_start + 1  # After index page(s)
                    
#                     index_items_list_final = []
#                     for item_info in dar_objects_for_merge_and_index:
#                         index_items_list_final.append({
#                             'circle': item_info['circle'], 
#                             'trade_name': item_info['trade_name'],
#                             'start_page_in_final_pdf': dar_start_page_counter_val, 
#                             'num_pages_in_dar': item_info['num_pages_in_dar']
#                         })
#                         dar_start_page_counter_val += item_info['num_pages_in_dar']
                    
#                     index_buffer = BytesIO()
#                     create_index_page_pdf(index_buffer, index_items_list_final, index_page_actual_start)
#                     index_reader = PdfReader(index_buffer)
#                     final_pdf_merger.append(index_reader)
#                     compiled_pdf_pages_count += len(index_reader.pages)
#                     progress_bar.progress(current_pdf_step / total_steps_for_pdf)
        
#                     # Step 5: Merge actual DAR PDFs
#                     for i, dar_detail_info in enumerate(dar_objects_for_merge_and_index):
#                         current_pdf_step += 1
#                         status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Merging DAR {i+1}/{total_dars} ({html.escape(dar_detail_info['trade_name'])})...")
#                         if dar_detail_info['pdf_reader']:
#                             final_pdf_merger.append(dar_detail_info['pdf_reader'])
#                         else:  # Placeholder
#                             ph_b = BytesIO()
#                             ph_d = SimpleDocTemplate(ph_b, pagesize=A4)
#                             ph_s = [Paragraph(f"Content for {html.escape(dar_detail_info['trade_name'])} (URL: {html.escape(dar_detail_info['dar_url'])}) failed to load.", getSampleStyleSheet()['Normal'])]
#                             ph_d.build(ph_s)
#                             ph_b.seek(0)
#                             final_pdf_merger.append(PdfReader(ph_b))
#                         progress_bar.progress(current_pdf_step / total_steps_for_pdf)
                        
#                     # # --- NEW: Add Page Numbers before Finalizing ---
#                     # status_message_area.info("Adding page numbers to the document...")
                    
#                     # # Get the total number of pages in the merged document
#                     # total_pages_final = len(final_pdf_merger.pages)

#                     # # Loop through each page of the merged PDF
#                     # for i in range(total_pages_final):
#                     #     # Get a specific page
#                     #     page_to_stamp = final_pdf_merger.pages[i]
                        
#                     #     # Create a new "stamp" PDF for the current page number
#                     #     stamp_buffer = BytesIO()
#                     #     create_page_number_stamp_pdf(stamp_buffer, i + 1, total_pages_final) # Use i + 1 for human-readable page numbers (1, 2, 3...)
                        
#                     #     # Read the stamp PDF
#                     #     stamp_reader = PdfReader(stamp_buffer)
#                     #     stamp_page = stamp_reader.pages[0]
                        
#                     #     # Merge the stamp onto the original page
#                     #     page_to_stamp.merge_page(stamp_page)
#                     #     #page_to_stamp.merge_layered_page(stamp_page, expand=False)

#                     # # --- End of New Page Numbering Logic ---
#                     # Step 6: Finalize PDF
#                     current_pdf_step += 1
#                     status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Finalizing PDF...")
#                     output_pdf_final = BytesIO()
#                     final_pdf_merger.write(output_pdf_final)
#                     output_pdf_final.seek(0)
#                     progress_bar.progress(1.0)
#                     status_message_area.success("PDF Compilation Complete!")
                    
#                     dl_filename = f"MCM_Agenda_{month_year_str.replace(' ', '_')}_Compiled.pdf"
#                     st.download_button(label="Download Compiled PDF Agenda", data=output_pdf_final, file_name=dl_filename, mime="application/pdf")
        
#                 except Exception as e_compile_outer:
#                     status_message_area.error(f"An error occurred during PDF compilation: {e_compile_outer}")
#                     import traceback
#                     st.error(traceback.format_exc())
#                 finally:
#                     import time
#                     time.sleep(0.5)  # Brief pause to ensure user sees final status
#                     status_message_area.empty()
#                     progress_bar.empty()
               
import streamlit as st
import pandas as pd
import datetime
import math
from io import BytesIO
import requests
from urllib.parse import urlparse, parse_qs
import html
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# PDF manipulation libraries
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import inch
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas

from google_utils import read_from_spreadsheet
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google_utils import update_spreadsheet_from_df
# --- NEW HELPER FUNCTION FOR INDIAN NUMBERING ---
def format_inr(n):
    """
    Formats a number into the Indian numbering system (lakhs, crores).
    """
    if not isinstance(n, (int, float)):
        return "0"
    
    n = int(n)
    if n < 0:
        return '-' + format_inr(-n)
    
    if n == 0:
        return "0"
    
    s = str(n)
    
    # Handle numbers with 3 digits or less
    if len(s) <= 3:
        return s
    
    # Get the last 3 digits
    s_last_three = s[-3:]
    s_remaining = s[:-3]
    
    # Split remaining digits into groups of 2 from right to left
    groups = []
    while len(s_remaining) > 2:
        groups.append(s_remaining[-2:])
        s_remaining = s_remaining[:-2]
    
    # Add any remaining digits (1 or 2 digits)
    if s_remaining:
        groups.append(s_remaining)
    
    # Reverse the groups to get correct order
    groups.reverse()
    
    # Join all groups with commas
    result = ','.join(groups) + ',' + s_last_three
    
    return result

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
        # --- MODIFIED: Use format_inr for PDF values ---
        detected_val = row_hv.get('Revenue Involved (Lakhs Rs)', 0) * 100000
        recovered_val = row_hv.get('Revenue Recovered (Lakhs Rs)', 0) * 100000
        table_data_hv.append([
            Paragraph(html.escape(str(row_hv.get("Audit Group Number", "N/A"))), styles['Normal']),
            Paragraph(html.escape(str(row_hv.get("Audit Para Number", "N/A"))), styles['Normal']),
            Paragraph(html.escape(str(row_hv.get("Audit Para Heading", "N/A"))[:100]), styles['Normal']),
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
#                 if 'Derived Audit Circle Number' not in df_period_data_full.columns:
#                          df_period_data_full['Derived Audit Circle Number'] = 0
#                 circle_col_to_use = 'Derived Audit Circle Number'
#                 st.warning("'Audit Circle Number' could not be determined reliably from sheet or derived.")
#         else:
#              df_period_data_full['Audit Circle Number'] = df_period_data_full['Audit Circle Number'].fillna(0).astype(int)

#         for circle_num_iter in range(1, 11):
#             circle_label_iter = f"Audit Circle {circle_num_iter}"
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
#                             trade_name_data = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
#                             dar_pdf_url_item = None

#                             if not trade_name_data.empty:
#                                 dar_pdf_url_item = trade_name_data.iloc[0].get('DAR PDF URL')

#                             cols_trade_display = st.columns([0.7, 0.3])
#                             with cols_trade_display[0]:
#                                 # --- CHANGE 2: BUTTON TOGGLE LOGIC ---
#                                 if st.button(f"{trade_name_item}", key=f"tradebtn_agenda_v3_{circle_num_iter}_{i}_{tn_idx_iter}", help=f"Toggle paras for {trade_name_item}", use_container_width=True):
#                                     # If the button of the already selected item is clicked, deselect it (toggle off)
#                                     if st.session_state.get(session_key_selected_trade) == trade_name_item:
#                                         st.session_state[session_key_selected_trade] = None
#                                     # Otherwise, select the new item (toggle on)
#                                     else:
#                                         st.session_state[session_key_selected_trade] = trade_name_item

#                             with cols_trade_display[1]:
#                                 if pd.notna(dar_pdf_url_item) and isinstance(dar_pdf_url_item, str) and dar_pdf_url_item.startswith("http"):
#                                     st.link_button("View DAR PDF", dar_pdf_url_item, use_container_width=True, type="secondary")
#                                 else:
#                                     st.caption("No PDF Link")

#                             if st.session_state.get(session_key_selected_trade) == trade_name_item:
#                                 df_trade_paras_item = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]

#                                 taxpayer_category = "N/A"
#                                 taxpayer_gstin = "N/A"
#                                 if not df_trade_paras_item.empty:
#                                     first_row = df_trade_paras_item.iloc[0]
#                                     taxpayer_category = first_row.get('Category', 'N/A')
#                                     taxpayer_gstin = first_row.get('GSTIN', 'N/A')
                                
#                                 # --- CHANGE 1: LIGHTER CATEGORY COLORS ---
#                                 # Each entry is a tuple of (background_color, text_color)
#                                 category_color_map = {
#                                     "Large": ("#f8d7da", "#721c24"),   # Light Red
#                                     "Medium": ("#ffeeba", "#856404"), # Light Yellow/Orange
#                                     "Small": ("#d4edda", "#155724"),   # Light Green
#                                     "N/A": ("#e2e3e5", "#383d41")      # Light Grey
#                                 }
#                                 cat_bg_color, cat_text_color = category_color_map.get(taxpayer_category, ("#e2e3e5", "#383d41"))

#                                 info_cols = st.columns(2)
#                                 with info_cols[0]:
#                                     st.markdown(f"""
#                                     <div style="background-color: {cat_bg_color}; color: {cat_text_color}; padding: 4px 8px; border-radius: 5px; text-align: center; font-size: 0.8rem; margin-top: 2px;">
#                                         <b>Category:</b> {html.escape(str(taxpayer_category))}
#                                     </div>
#                                     """, unsafe_allow_html=True)
#                                 with info_cols[1]:
#                                     st.markdown(f"""
#                                     <div style="background-color: #e9ecef; color: #495057; padding: 4px 8px; border-radius: 5px; text-align: center; font-size: 0.8rem; margin-top: 2px;">
#                                         <b>GSTIN:</b> {html.escape(str(taxpayer_gstin))}
#                                     </div>
#                                     """, unsafe_allow_html=True)

#                                 st.markdown(f"<h5 style='font-size:13pt; margin-top:15px; color:#154360;'>Gist of Audit Paras for: {html.escape(trade_name_item)}</h5>", unsafe_allow_html=True)

#                                 html_rows = ""
#                                 total_para_det_rs = 0
#                                 total_para_rec_rs = 0
#                                 for _, para_item_row in df_trade_paras_item.iterrows():
#                                     para_num = para_item_row.get("Audit Para Number", "N/A"); p_num_str = str(int(para_num)) if pd.notna(para_num) and para_num !=0 else "N/A"
#                                     p_title = html.escape(str(para_item_row.get("Audit Para Heading", "N/A")))
#                                     p_status = html.escape(str(para_item_row.get("Status of para", "N/A")))
#                                     det_lakhs = para_item_row.get('Revenue Involved (Lakhs Rs)', 0); det_rs = (det_lakhs * 100000) if pd.notna(det_lakhs) else 0
#                                     rec_lakhs = para_item_row.get('Revenue Recovered (Lakhs Rs)', 0); rec_rs = (rec_lakhs * 100000) if pd.notna(rec_lakhs) else 0
#                                     total_para_det_rs += det_rs
#                                     total_para_rec_rs += rec_rs
#                                     html_rows += f"""
#                                     <tr>
#                                         <td>{p_num_str}</td>
#                                         <td>{p_title}</td>
#                                         <td class='amount-col'>{format_inr(det_rs)}</td>
#                                         <td class='amount-col'>{format_inr(rec_rs)}</td>
#                                         <td>{p_status}</td>
#                                     </tr>"""

#                                 total_row_html = f"""
#                                 <tfoot>
#                                     <tr style='font-weight:bold; background-color:#e9ecef;'>
#                                         <td colspan="2" style="text-align:right;">Total of Paras</td>
#                                         <td class='amount-col'>{format_inr(total_para_det_rs)}</td>
#                                         <td class='amount-col'>{format_inr(total_para_rec_rs)}</td>
#                                         <td></td>
#                                     </tr>
#                                 </tfoot>"""

#                                 table_full_html = f"""
#                                 <style>
#                                 .paras-table {{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:10pt;}}
#                                 .paras-table th, .paras-table td {{border:1px solid #bbb;padding:5px;text-align:left;word-wrap:break-word;}}
#                                 .paras-table th {{background-color:#343a40;color:white;font-size:11pt;}}
#                                 .paras-table tr:nth-child(even) {{background-color:#f4f6f6;}}
#                                 .amount-col {{text-align:right!important;}}
#                                 </style>
#                                 <table class='paras-table'>
#                                     <thead>
#                                         <tr><th>Para No.</th><th>Para Title</th><th>Detection (₹)</th><th>Recovery (₹)</th><th>Status</th></tr>
#                                     </thead>
#                                     <tbody>{html_rows}</tbody>
#                                     {total_row_html}
#                                 </table>"""
#                                 st.markdown(table_full_html, unsafe_allow_html=True)
#                                 total_overall_detection = 0
#                                 total_overall_recovery = 0
                                
#                                 if not df_trade_paras_item.empty:
#                                     detection_val = df_trade_paras_item['Total Amount Detected (Overall Rs)'].iloc[0]
#                                     recovery_val = df_trade_paras_item['Total Amount Recovered (Overall Rs)'].iloc[0]
                                    
#                                     total_overall_detection = 0 if pd.isna(detection_val) else int(detection_val)
#                                     total_overall_recovery = 0 if pd.isna(recovery_val) else int(recovery_val)
                                
#                                 # Display the final totals
#                                 st.markdown(f"<b>Total Detection for {html.escape(trade_name_item)}: ₹ {format_inr(total_overall_detection)}</b>", unsafe_allow_html=True)
#                                 st.markdown(f"<b>Total Recovery for {html.escape(trade_name_item)}: ₹ {format_inr(total_overall_recovery)}</b>", unsafe_allow_html=True)
#                                 st.markdown("<hr style='border-top: 1px solid #ccc; margin-top:10px; margin-bottom:10px;'>", unsafe_allow_html=True)
        
#         st.markdown("---")
# Add this import at the top of your main Python file if you haven't already
from google_utils import update_spreadsheet_from_df

# Replace your existing mcm_agenda_tab function with this entire block
def mcm_agenda_tab(drive_service, sheets_service, mcm_periods):
    st.markdown("### MCM Agenda Preparation")

    if not mcm_periods:
        st.warning("No MCM periods found. Please create them first via 'Create MCM Period' tab.")
        return

    period_options = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(mcm_periods.items(), key=lambda item: item[0], reverse=True) if v.get('month_name') and v.get('year')}
    if not period_options:
        st.warning("No valid MCM periods with complete month and year information available.")
        return

    selected_period_key = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()), format_func=lambda k: period_options[k], key="mcm_agenda_period_select_v3_full")

    if not selected_period_key:
        st.info("Please select an MCM period."); return

    selected_period_info = mcm_periods[selected_period_key]
    month_year_str = f"{selected_period_info.get('month_name')} {selected_period_info.get('year')}"
    st.markdown(f"<h2 style='text-align: center; color: #007bff; font-size: 22pt; margin-bottom:10px;'>MCM Audit Paras for {month_year_str}</h2>", unsafe_allow_html=True)
    st.markdown("---")

    # --- Data Loading using Session State ---
    if 'df_period_data' not in st.session_state or st.session_state.get('current_period_key') != selected_period_key:
        with st.spinner(f"Loading data for {month_year_str}..."):
            df = read_from_spreadsheet(sheets_service, selected_period_info['spreadsheet_id'])
            if df is None or df.empty:
                st.info(f"No data found in the spreadsheet for {month_year_str}.")
                st.session_state.df_period_data = pd.DataFrame()
                return
            
            cols_to_convert_numeric = ['Audit Group Number', 'Audit Circle Number', 'Total Amount Detected (Overall Rs)',
                                       'Total Amount Recovered (Overall Rs)', 'Audit Para Number',
                                       'Revenue Involved (Lakhs Rs)', 'Revenue Recovered (Lakhs Rs)']
            for col_name in cols_to_convert_numeric:
                if col_name in df.columns:
                    df[col_name] = df[col_name].astype(str).str.replace(r'[^\d.]', '', regex=True)
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                else:
                    df[col_name] = 0 if "Amount" in col_name or "Revenue" in col_name else pd.NA
            
            st.session_state.df_period_data = df
            st.session_state.current_period_key = selected_period_key
    
    df_period_data_full = st.session_state.df_period_data
    if df_period_data_full.empty:
        st.info(f"No data available for {month_year_str}.")
        return

    # --- Code to derive Audit Circle and set up UI loops ---
    # This logic remains the same.
    circle_col_to_use = 'Audit Circle Number'
    if 'Audit Circle Number' not in df_period_data_full.columns or not df_period_data_full['Audit Circle Number'].notna().any() or not pd.to_numeric(df_period_data_full['Audit Circle Number'], errors='coerce').fillna(0).astype(int).gt(0).any():
        if 'Audit Group Number' in df_period_data_full.columns and df_period_data_full['Audit Group Number'].notna().any():
            df_period_data_full['Derived Audit Circle Number'] = df_period_data_full['Audit Group Number'].apply(calculate_audit_circle_agenda).fillna(0).astype(int)
            circle_col_to_use = 'Derived Audit Circle Number'
        else:
            df_period_data_full['Derived Audit Circle Number'] = 0
            circle_col_to_use = 'Derived Audit Circle Number'
    else:
        df_period_data_full['Audit Circle Number'] = df_period_data_full['Audit Circle Number'].fillna(0).astype(int)

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
                df_grp_iter_data = df_circle_iter_data[df_circle_iter_data['Audit Group Number'] == grp_iter_num]
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
                    unique_trade_names_list = df_current_grp_item.get('Trade Name', pd.Series(dtype='str')).dropna().unique()

                    if not unique_trade_names_list.any():
                        st.write("No trade names with DARs found for this group.")
                        continue

                    st.markdown(f"**DARs for {group_labels_list[i]}:**")
                    session_key_selected_trade = f"selected_trade_{circle_num_iter}_{group_labels_list[i].replace(' ','_')}"

                    for tn_idx_iter, trade_name_item in enumerate(unique_trade_names_list):
                        trade_name_data = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item]
                        dar_pdf_url_item = None
                        if not trade_name_data.empty:
                            dar_pdf_url_item = trade_name_data.iloc[0].get('DAR PDF URL')

                        cols_trade_display = st.columns([0.7, 0.3])
                        with cols_trade_display[0]:
                            if st.button(f"{trade_name_item}", key=f"tradebtn_agenda_v3_{circle_num_iter}_{i}_{tn_idx_iter}", help=f"Toggle paras for {trade_name_item}", use_container_width=True):
                                st.session_state[session_key_selected_trade] = None if st.session_state.get(session_key_selected_trade) == trade_name_item else trade_name_item
                        
                        with cols_trade_display[1]:
                            if pd.notna(dar_pdf_url_item) and dar_pdf_url_item.startswith("http"):
                                st.link_button("View DAR PDF", dar_pdf_url_item, use_container_width=True, type="secondary")
                            else:
                                st.caption("No PDF Link")

                        if st.session_state.get(session_key_selected_trade) == trade_name_item:
                            df_trade_paras_item = df_current_grp_item[df_current_grp_item['Trade Name'] == trade_name_item].copy()
                            
                            st.markdown(f"<h5 style='font-size:13pt; margin-top:15px; color:#154360;'>Gist of Audit Paras & MCM Decisions for: {html.escape(trade_name_item)}</h5>", unsafe_allow_html=True)
                            
                            # --- INTERACTIVE TABLE WITH BORDERS ---
                            st.markdown("""
                                <style>
                                    .grid-header {
                                        font-weight: bold;
                                        background-color: #343a40;
                                        color: white;
                                        padding: 10px 5px;
                                        border-radius: 5px;
                                        text-align: center;
                                    }
                                    .revenue-number {
                                        font-weight: bold;
                                    }
                                </style>
                            """, unsafe_allow_html=True)

                            # Define headers in a styled row
                            header_cols = st.columns((1, 4, 2, 2, 2, 3))
                            headers = ['Para No.', 'Para Title', 'Detection (₹)', 'Recovery (₹)', 'Status', 'MCM Decision']
                            for col, header in zip(header_cols, headers):
                                col.markdown(f"<div class='grid-header'>{header}</div>", unsafe_allow_html=True)
                            
                            decision_options = ['Para closed since recovered', 'Para deferred', 'Para to be pursued else issue SCN']
                            
                            # Create a bordered container for each para row
                            for index, row in df_trade_paras_item.iterrows():
                                with st.container(border=True): # This creates the row border
                                    para_num_str = str(int(row["Audit Para Number"])) if pd.notna(row["Audit Para Number"]) and row["Audit Para Number"] != 0 else "N/A"
                                    det_rs = (row.get('Revenue Involved (Lakhs Rs)', 0) * 100000) if pd.notna(row.get('Revenue Involved (Lakhs Rs)')) else 0
                                    rec_rs = (row.get('Revenue Recovered (Lakhs Rs)', 0) * 100000) if pd.notna(row.get('Revenue Recovered (Lakhs Rs)')) else 0
                                    
                                    default_index = 0
                                    if 'MCM Decision' in df_trade_paras_item.columns and pd.notna(row['MCM Decision']) and row['MCM Decision'] in decision_options:
                                        default_index = decision_options.index(row['MCM Decision'])
                                    
                                    row_cols = st.columns((1, 4, 2, 2, 2, 3))
                                    row_cols[0].write(para_num_str)
                                    row_cols[1].write(row.get("Audit Para Heading", "N/A"))
                                    row_cols[2].markdown(f"<span class='revenue-number'>{format_inr(det_rs)}</span>", unsafe_allow_html=True)
                                    row_cols[3].markdown(f"<span class='revenue-number'>{format_inr(rec_rs)}</span>", unsafe_allow_html=True)
                                    row_cols[4].write(row.get("Status of para", "N/A"))
                                    
                                    decision_key = f"mcm_decision_{trade_name_item}_{para_num_str}_{index}"
                                    row_cols[5].selectbox("Decision", options=decision_options, index=default_index, key=decision_key, label_visibility="collapsed")
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            
                            # Save button logic
                            if st.button("Save Decisions", key=f"save_decisions_{trade_name_item}", use_container_width=True, type="primary"):
                                with st.spinner("Saving decisions..."):
                                    if 'MCM Decision' not in st.session_state.df_period_data.columns:
                                        st.session_state.df_period_data['MCM Decision'] = ""
                                    
                                    for index, row in df_trade_paras_item.iterrows():
                                        para_num_str = str(int(row["Audit Para Number"])) if pd.notna(row["Audit Para Number"]) and row["Audit Para Number"] != 0 else "N/A"
                                        decision_key = f"mcm_decision_{trade_name_item}_{para_num_str}_{index}"
                                        selected_decision = st.session_state.get(decision_key, decision_options[0])
                                        st.session_state.df_period_data.loc[index, 'MCM Decision'] = selected_decision
                                    
                                    success = update_spreadsheet_from_df(
                                        sheets_service=sheets_service,
                                        spreadsheet_id=selected_period_info['spreadsheet_id'],
                                        df_to_write=st.session_state.df_period_data
                                    )
                                    
                                    if success:
                                        st.success("✅ Decisions saved successfully!")
                                    else:
                                        st.error("❌ Failed to save decisions. Check app logs for details.")

                            st.markdown("<hr>", unsafe_allow_html=True)
        # --- Compile PDF Button ---
        if st.button("Compile Full MCM Agenda PDF", key=f"compile_mcm_agenda_pdf_{selected_period_key}", type="primary", help="Generates a comprehensive PDF.", use_container_width=True):
        #if st.button("Compile Full MCM Agenda PDF", key="compile_mcm_agenda_pdf_final_v4_progress", type="primary", help="Generates a comprehensive PDF.", use_container_width=True):
            if df_period_data_full.empty:
                st.error("No data available for the selected MCM period to compile into PDF.")
            else:
                status_message_area = st.empty()
                progress_bar = st.progress(0)

                with st.spinner("Preparing for PDF compilation..."):
                    final_pdf_merger = PdfWriter()
                    compiled_pdf_pages_count = 0

                    # Filter and sort data for PDF
                    df_for_pdf = df_period_data_full.dropna(subset=['DAR PDF URL', 'Trade Name', circle_col_to_use]).copy()
                    df_for_pdf[circle_col_to_use] = pd.to_numeric(df_for_pdf[circle_col_to_use], errors='coerce').fillna(0).astype(int)

                    # Get unique DARs, sorted for consistent processing order
                    unique_dars_to_process = df_for_pdf.sort_values(by=[circle_col_to_use, 'Trade Name', 'DAR PDF URL']).drop_duplicates(subset=['DAR PDF URL'])

                    total_dars = len(unique_dars_to_process)

                    dar_objects_for_merge_and_index = []

                    if total_dars == 0:
                        status_message_area.warning("No valid DARs with PDF URLs found to compile.")
                        progress_bar.empty()
                        st.stop()

                    total_steps_for_pdf = 4 + (2 * total_dars)
                    current_pdf_step = 0

                    # Step 1: Pre-fetch DAR PDFs to count pages
                    if drive_service:
                        status_message_area.info(f"Pre-fetching {total_dars} DAR PDFs to count pages and prepare content...")
                        for idx, dar_row in unique_dars_to_process.iterrows():
                            current_pdf_step += 1
                            dar_url_val = dar_row.get('DAR PDF URL')
                            file_id_val = get_file_id_from_drive_url(dar_url_val)
                            num_pages_val = 1  # Default in case of fetch failure
                            reader_obj_val = None
                            trade_name_val = dar_row.get('Trade Name', 'Unknown DAR')
                            circle_val = f"Circle {int(dar_row.get(circle_col_to_use, 0))}"

                            status_message_area.info(f"Step {current_pdf_step}/{total_steps_for_pdf}: Fetching DAR for {trade_name_val}...")
                            if file_id_val:
                                try:
                                    req_val = drive_service.files().get_media(fileId=file_id_val)
                                    fh_val = BytesIO()
                                    downloader = MediaIoBaseDownload(fh_val, req_val)
                                    done = False
                                    while not done:
                                        status, done = downloader.next_chunk(num_retries=2)
                                    fh_val.seek(0)
                                    reader_obj_val = PdfReader(fh_val)
                                    num_pages_val = len(reader_obj_val.pages) if reader_obj_val.pages else 1
                                except HttpError as he:
                                    st.warning(f"PDF HTTP Error for {trade_name_val} ({dar_url_val}): {he}. Using placeholder.")
                                except Exception as e_fetch_val:
                                    st.warning(f"PDF Read Error for {trade_name_val} ({dar_url_val}): {e_fetch_val}. Using placeholder.")

                            dar_objects_for_merge_and_index.append({
                                'circle': circle_val,
                                'trade_name': trade_name_val,
                                'num_pages_in_dar': num_pages_val,
                                'pdf_reader': reader_obj_val,
                                'dar_url': dar_url_val
                            })
                            progress_bar.progress(current_pdf_step / total_steps_for_pdf)
                    else:
                        status_message_area.error("Google Drive service not available.")
                        progress_bar.empty()
                        st.stop()

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
                    df_hv_data = df_period_data_full[(df_period_data_full['Revenue Involved (Lakhs Rs)'].fillna(0) * 100000) > 500000].copy()
                    df_hv_data.sort_values(by='Revenue Involved (Lakhs Rs)', ascending=False, inplace=True)
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
                            ph_s = [Paragraph(f"Content for {html.escape(dar_detail_info['trade_name'])} (URL: {html.escape(dar_detail_info['dar_url'])}) failed to load.", getSampleStyleSheet()['Normal'])]
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
                    import time
                    time.sleep(0.5)  # Brief pause to ensure user sees final status
                    status_message_area.empty()
                    progress_bar.empty()
