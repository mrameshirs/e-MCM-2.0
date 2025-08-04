#mcm_report_generator.py
import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Frame, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from svglib.svglib import svg2rlg
import os
import re
import xml.etree.ElementTree as ET
import pandas as pd
from reportlab.platypus import NextPageTemplate, PageTemplate, Frame
class PDFReportGenerator:
    """
    A structured PDF report generator with controlled chart placement and descriptions.
    """

    def __init__(self, selected_period, vital_stats, chart_images, chart_metadata=None):
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer, 
            pagesize=letter, 
            leftMargin=0.25*inch, 
            rightMargin=0.25*inch,
            topMargin=0.25*inch,
            bottomMargin=0.25*inch
        )
        self.story = []
        self.styles = getSampleStyleSheet()
        self.width, self.height = letter

        self.selected_period = selected_period
        self.vital_stats = vital_stats or {}  # Ensure it's a dict
        self.chart_images = chart_images
        
        # Chart metadata structure: [{"title": "Chart Title", "description": "Chart description", "page_break_after": True}, ...]
        self.chart_metadata = chart_metadata or self._generate_default_metadata()
        # Create chart registry for easy access
        self.chart_registry = self._create_chart_registry()
        # Register fonts with proper error handling
        self._register_fonts()
        self._setup_custom_styles()

    def _generate_default_metadata(self):
        """Generate enhanced default metadata with proper IDs from visualization charts"""
        chart_configs = [
            # Chart 1: Performance Summary by Category (fig1)
            {
                "id": "category_detection_performance",
                "title": "Detection Amount by Taxpayer Category", 
                "description": "Bar chart showing detection amounts across Large, Medium, and Small taxpayer categories.",
                "section": "performance_summary",
                "position": "after_metrics",
                "size": "medium"
            },
            # Chart 2: Status Count Chart (fig2)
            {
                "id": "status_para_count",
                "title": "Number of Audit Paras by Status",
                "description": "Distribution of audit paras by their current status (Agreed, Disputed, etc.).",
                "section": "status_analysis", 
                "position": "after_header",
                "size": "medium"
            },
            # Chart 3: Status Detection Chart (fig3)  
            {
                "id": "status_analysis",
                "title": "Detection Amount by Status",
                "description": "Analysis of detection amounts categorized by para status showing recovery potential.",
                "section": "status_analysis",
                "position": "after_table", 
                "size": "medium"
            },
            # Chart 4: Group Detection Performance (fig4)
            {
                "id": "group_detection_performance", 
                "title": "Top 10 Groups by Detection",
                "description": "Performance ranking of audit groups based on detection amounts.",
                "section": "performance_analysis",
                "position": "standalone",
                "size": "medium"
            },
            # Chart 5: Circle Detection Performance (fig5)
            {
                "id": "circle_detection_performance",
                "title": "Circle-wise Detection Performance", 
                "description": "Detection amounts across different audit circles showing regional performance.",
                "section": "performance_analysis",
                "position": "standalone",
                "size": "medium"
            },
            # Chart 6: Group Recovery Performance (fig6)
            {
                "id": "group_recovery_performance",
                "title": "Top 10 Groups by Recovery",
                "description": "Recovery performance ranking of audit groups.",
                "section": "performance_analysis", 
                "position": "standalone",
                "size": "medium"
            },
            # Chart 7: Circle Recovery Performance (fig7)
            {
                "id": "recovery_trends", 
                "title": "Circle-wise Recovery Performance",
                "description": "Recovery amounts across different audit circles showing collection efficiency.",
                "section": "status_analysis",
                "position": "after_table",
                "size": "medium"
            },
            # Chart 8: Taxpayer Classification Distribution (fig8)
            {
                "id": "taxpayer_classification_distribution",
                "title": "Distribution of DARs by Taxpayer Classification", 
                "description": "Pie chart showing distribution of Draft Audit Reports across taxpayer types.",
                "section": "sectoral_analysis",
                "position": "after_header",
                "size": "medium"
            },
            # Chart 9: Detection by Classification (fig9)
            {
                "id": "taxpayer_classification_detection",
                "title": "Detection Amount by Taxpayer Classification",
                "description": "Pie chart showing detection amounts distributed across different taxpayer classifications.",
                "section": "sectoral_analysis", 
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 9b: Recovery by Classification (fig9b - NEW)
            {
                "id": "taxpayer_classification_recovery",
                "title": "Recovery Amount by Taxpayer Classification",
                "description": "Pie chart showing recovery amounts distributed across different taxpayer classifications.",
                "section": "sectoral_analysis", 
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 10: Paras by Classification (fig10 -> now fig11)
            {
                "id": "classification_para_count",
                "title": "Number of Audit Paras by Categorisation", 
                "description": "Bar chart showing audit para counts across different non-compliance categories.",
                "section": "compliance_analysis",
                "position": "after_header",
                "size": "medium"
            },
            # Chart 11: Detection by Classification (fig11 -> now fig12)
            {
                "id": "classification_detection",
                "title": "Detection Amount by Categorisation",
                "description": "Detection amounts across different compliance violation categories.",
                "section": "compliance_analysis",
                "position": "after_chart", 
                "size": "medium"
            },
            # Chart 12: Recovery by Classification (fig12 -> now fig13)
            {
                "id": "classification_recovery",
                "title": "Recovery Amount by Categorisation", 
                "description": "Recovery amounts across different compliance violation categories.",
                "section": "compliance_analysis",
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 13: Detection Treemap (fig13 -> now fig14)
            {
                "id": "detection_treemap",
                "title": "Detection by Trade Name Treemap",
                "description": "Hierarchical view of detection amounts by taxpayer category and trade name.",
                "section": "detailed_analysis",
                "position": "standalone", 
                "size": "large"
            },
            # Chart 14: Recovery Treemap (fig14 -> now fig15)
            {
                "id": "recovery_treemap", 
                "title": "Recovery by Trade Name Treemap",
                "description": "Hierarchical view of recovery amounts by taxpayer category and trade name.",
                "section": "detailed_analysis",
                "position": "standalone",
                "size": "large"
            },
            # Chart 15: Risk Paras Chart (fig15 -> now fig16)
            {
                "id": "risk_para_distribution",
                "title": "Top 15 Risk Flags by Number of Audit Paras", 
                "description": "Distribution of audit paras across different GST risk parameters.",
                "section": "risk_analysis",
                "position": "after_header",
                "size": "medium"
            },
            # Chart 16: Risk Detection Chart (fig16 -> now fig17) 
            {
                "id": "risk_detection_analysis",
                "title": "Top 10 Detection Amount by Risk Flag",
                "description": "Detection amounts associated with different risk parameters.",
                "section": "risk_analysis",
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 17: Risk Recovery Chart (fig17 -> now fig18)
            {
                "id": "risk_recovery_analysis",
                "title": "Top 10 Recovery Amount by Risk Flag", 
                "description": "Recovery amounts associated with different risk parameters.",
                "section": "risk_analysis",
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 18: Risk Recovery Percentage (fig18 -> now fig19)
            {
                "id": "risk_distribution",
                "title": "Top 10 Percentage Recovery by Risk Flag",
                "description": "Recovery efficiency percentages across different risk parameters.",
                "section": "risk_analysis",
                "position": "after_chart", 
                "size": "medium"
            }
        ]
        #ADD DETAILED CLASSIFICATION CHARTS (Charts 19+)
        # These correspond to the nc_tab2 and nc_tab3 detailed breakdown charts
        CLASSIFICATION_CODES_DESC = {
            'TP': 'TAX PAYMENT DEFAULTS', 'RC': 'REVERSE CHARGE MECHANISM',
            'IT': 'INPUT TAX CREDIT VIOLATIONS', 'IN': 'INTEREST LIABILITY DEFAULTS',
            'RF': 'RETURN FILING NON-COMPLIANCE', 'PD': 'PROCEDURAL & DOCUMENTATION',
            'CV': 'CLASSIFICATION & VALUATION', 'SS': 'SPECIAL SITUATIONS',
            'PG': 'PENALTY & GENERAL COMPLIANCE'
        }
        
        # Add detailed DETECTION charts for each classification code
        for code in ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']:
            chart_configs.append({
                "id": f"detailed_detection_{code}",
                "title": f"Detection for {code} - {CLASSIFICATION_CODES_DESC[code]}",
                "description": f"Detailed breakdown of detection amounts for {CLASSIFICATION_CODES_DESC[code]} subcategories.",
                "section": "detailed_compliance_analysis",
                "size": "medium"
            })
        
        # Add detailed RECOVERY charts for each classification code  
        for code in ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']:
            chart_configs.append({
                "id": f"detailed_recovery_{code}",
                "title": f"Recovery for {code} - {CLASSIFICATION_CODES_DESC[code]}",
                "description": f"Detailed breakdown of recovery amounts for {CLASSIFICATION_CODES_DESC[code]} subcategories.",
                "section": "detailed_compliance_analysis", 
                "size": "medium"
            })
        
        # Return only the number of charts that actually exist
        return chart_configs[:len(self.chart_images)]
      
        
    def add_section_highlight_bar(self, section_title,text_color, bar_color="#FAD6a5"):
        """Add a highlight bar for section separation"""
        try:
            # Create a table with colored background to act as highlight bar
            highlight_data = [[section_title]]
            highlight_table = Table(highlight_data, colWidths=[7*inch])
            
            # Style the highlight bar
            highlight_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bar_color)),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(text_color)),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 16),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            self.story.append(highlight_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
        except Exception as e:
            print(f"Error adding section highlight bar: {e}")
            # Fallback to regular header if highlight bar fails
            fallback_style = ParagraphStyle(
                name='FallbackHeader',
                parent=self.styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor(bar_color),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=16,
                spaceBefore=16
            )
            self.story.append(Paragraph(section_title, fallback_style))
        
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for different content types"""
        self.chart_title_style = ParagraphStyle(
            name='ChartTitle',
            parent=self.styles['Heading2'],
            fontSize=14,  # CHANGED from 16
            textColor=colors.HexColor("#1F3A4D"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=6,   # CHANGED from 8
            spaceBefore=10  # CHANGED from 12
        )
        
        self.chart_description_style = ParagraphStyle(
            name='ChartDescription',
            parent=self.styles['Normal'],
            fontSize=10,    # CHANGED from 11
            textColor=colors.HexColor("#2C2C2C"),
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            spaceAfter=8,   # CHANGED from 16
            spaceBefore=4,  # CHANGED from 8
            leftIndent=0.25*inch,
            rightIndent=0.25*inch,
            leading=12,     # CHANGED from 13
            wordWrap='LTR'
        )
        """Setup custom paragraph styles for different content types"""
        self.chart_title_style = ParagraphStyle(
            name='ChartTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor("#1F3A4D"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=8,  # Reduced from 12
            spaceBefore=12  # Reduced from 16
        )
        
        self.chart_description_style = ParagraphStyle(
            name='ChartDescription',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor("#2C2C2C"),
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            spaceAfter=8,  # Reduced from 16
            spaceBefore=4,  # Reduced from 8
            leftIndent=0.25*inch,
            rightIndent=0.25*inch,
            leading=13,  # Reduced from 14
            wordWrap='LTR'  # Enable proper word wrapping
        )
        
        self.section_header_style = ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor("#1F3A4D"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=16,
            spaceBefore=24
         )
        
 
    
    def _create_chart_registry(self):
        """Create a registry of charts with IDs for easy access - ENHANCED for all chart types"""
        registry = {}
        print(f"Creating chart registry with {len(self.chart_images)} images and {len(self.chart_metadata)} metadata entries")
        
        for i, chart_data in enumerate(self.chart_metadata):
            if i >= len(self.chart_images):
                print(f"Warning: Metadata entry {i} has no corresponding chart image")
                break
                
            chart_id = chart_data.get('id', f'chart_{i+1}')
            registry[chart_id] = {
                'index': i,
                'image': self.chart_images[i],
                'metadata': chart_data
            }
            print(f"Registered chart {i}: {chart_id} -> {chart_data.get('title', 'No title')}")
        
        print(f"Final registry keys: {list(registry.keys())}")
        return registry
    
   
    def insert_chart_by_id(self, chart_id, size="medium", add_title=False, add_description=False):
        """Insert chart with proper scaling - ENHANCED for all chart types including detailed classification"""
        try:
            print(f'Processing Chart ID: {chart_id}')
            if chart_id not in self.chart_registry:
                print(f"Chart ID '{chart_id}' not found in registry")
                print(f"Available IDs: {list(self.chart_registry.keys())[:10]}...")  # Show first 10
                return False
    
            chart_info = self.chart_registry[chart_id]
            chart_data = chart_info['metadata']
            img_bytes = chart_info['image']
    
            if img_bytes is None:
                print(f"No image data for chart '{chart_id}'")
                return False
    
            # Add title and description with reduced spacing for detailed charts
            if add_title:
                # Use smaller title style for detailed charts
                title_style = self.chart_title_style
                if 'detailed_' in chart_id:
                    title_style = ParagraphStyle(
                        name='DetailedChartTitle',
                        parent=self.chart_title_style,
                        fontSize=12,  # Smaller font for detailed charts
                        spaceAfter=4,  # Less space after
                        spaceBefore=6  # Less space before
                    )
                self.story.append(Paragraph(chart_data.get('title', ''), title_style))
                
            if add_description:
                self.story.append(Paragraph(chart_data.get('description', ''), self.chart_description_style))
    
            # Create drawing
            drawing, error = self._create_safe_svg_drawing(img_bytes)
            
            if error or drawing is None:
                print(f"Failed to create drawing for '{chart_id}': {error}")
                return False
    
            # Enhanced size configurations with more options
            size_configs = {
                "tiny": 3.0 * inch,
                "small": 4.0 * inch,
                "compact": 4.5 * inch,     # Perfect for detailed classification charts
                "medium": 5.0 * inch,
                "large": 6.5 * inch,
                "extra_large": 7.5 * inch
            }
    
            # Special handling for different chart types
            is_pie_row = any(keyword in chart_id for keyword in ['combined', 'three_pie', 'taxpayer_classification_distribution'])
            is_treemap = 'treemap' in chart_id
            is_detailed = 'detailed_' in chart_id
            
            if is_pie_row:
                # Wide format for three pies in row  
                target_width = 7.5 * inch
                target_height = 4.0 * inch
            elif is_treemap:
                # Larger format for treemaps
                target_width = 7.0 * inch
                target_height = 3.0 * inch
            elif is_detailed:
                # Compact format for detailed breakdown charts
                target_width = 5.0 * inch
                target_height = 3.5 * inch
            else:
                # Regular sizing for other charts
                target_width = size_configs.get(size, 5.5 * inch)
                target_height = target_width * 0.6  # Standard aspect ratio
    
            # Calculate scale factors
            original_width = getattr(drawing, 'width', 400)
            original_height = getattr(drawing, 'height', 400)
            
            if original_width <= 0 or original_height <= 0:
                print(f"Invalid original dimensions for '{chart_id}': {original_width}x{original_height}")
                return False
                
            scale_x = target_width / original_width
            scale_y = target_height / original_height
    
            # Create properly scaled drawing
            from reportlab.graphics.shapes import Drawing, Group
            
            scaled_drawing = Drawing(target_width, target_height)
            content_group = Group()
            content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
            
            # Add original contents safely
            if hasattr(drawing, 'contents'):
                for item in drawing.contents:
                    content_group.add(item)
            
            scaled_drawing.add(content_group)
            scaled_drawing.hAlign = 'CENTER'
            
            # Add minimal spacing for detailed charts, regular spacing for others
            if is_detailed:
                self.story.append(Spacer(1, 0.005 * inch))  # Minimal spacing
            else:
                self.story.append(Spacer(1, 0.01 * inch))
                
            self.story.append(scaled_drawing)
            
            if is_detailed:
                self.story.append(Spacer(1, 0.005 * inch))  # Minimal spacing
            else:
                self.story.append(Spacer(1, 0.01 * inch))
            
            print(f"SUCCESS: Chart '{chart_id}' added with size {size} ({target_width:.1f}x{target_height:.1f})")
            return True
            
        except Exception as e:
            print(f"ERROR inserting chart '{chart_id}': {e}")
            import traceback
            traceback.print_exc()
            return False
    def _register_fonts(self):
        """Register fonts with proper error handling"""
        try:
            font_path = 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'
            #font_path='Mangal Regular.ttf'
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('HindiFont', font_path))
                print("Hindi font registered successfully")
            else:
                print("Hindi font file not found, using fallback")
                self._use_fallback_font()
        except Exception as e:
            print(f"Font registration failed: {e}")
            self._use_fallback_font()

    def _use_fallback_font(self):
        """Use built-in fonts as fallback"""
        try:
            pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica'))
        except Exception as e:
            print(f"Fallback font registration failed: {e}")

   
    def run(self, detailed=False):
        """Generate the full report with comprehensive error handling"""
        try:
            print("=== STARTING PDF GENERATION ===")
            try:
   

                # 1. Create cover page
                self.create_cover_page_story()
                self.story.append(PageBreak())
                
                # 2. Create summary header
                self.create_summary_header()
            except Exception as e:
                print(f"ERROR in Coverpage and summary header: {e}")
            
         
            # 3. Add comprehensive monthly performance summary with charts Section I and II
            try:
                self.add_monthly_performance_summary()
            except Exception as e:
                print(f"Error in monthly performance summary: {e}")
            
            # 4. Add Section III Sectoral analysis
            try:
                self.add_sectoral_analysis()
            except Exception as e:
                print(f"Error in sectoral analysis: {e}")
            
            # 5. Add Section IV Nature of Non Compliance Analysis
            try:
                self.add_nature_of_non_compliance_analysis()
            except Exception as e:
                print(f"Error in nature of non compliance analysis: {e}")
            
            # 6. Add Risk Parameter Analysis if available
            try:
                if self.vital_stats.get('risk_analysis_available', False):
                    self.add_risk_parameter_analysis()
            except Exception as e:
                print(f"Error in risk parameter analysis: {e}")
          
                         
            # 7. Add Section V - Top Audit Group and Circle Performance
            try:
                self.add_top_performance_analysis()
            except Exception as e:
                print(f"Error in top performance analysis: {e}")
            
            # 8. Add Section VI - Top Taxpayers of Detection and Recovery
            try:
                self.add_top_taxpayers_analysis()
            except Exception as e:
                print(f"Error in top taxpayer analysis: {e}")
                
            # 8a. Add Section VII - Performance Summary of Audit Group  
            self.add_audit_group_performance_summary()

             # 8b. Add Section VIII - Analysis of MCM Decisions (NEW!)
            self.add_mcm_decision_analysis()
            
            # 8c. Add Section IX - Summary of Audit Paras (renamed from VIII)
            self.add_summary_of_audit_paras()
                   
            # 9. Build the document
            print(f"Story has {len(self.story)} elements")
            
            try:
                print("Building final PDF document with page elements...")
                self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
                print("✓ PDF document built successfully with page elements")
                
            except IndexError as e:
                print(f"IndexError during build (likely table styling issue): {e}")
                print("Retrying without page callbacks...")
                try:
                    self.doc.build(self.story)
                    print("✓ PDF built successfully without page callbacks")
                except Exception as e2:
                    print(f"Build failed completely: {e2}")
                    raise e2
                    
            except Exception as e:
                print(f"Other error during build: {e}")
                print("Retrying without page callbacks...")
                try:
                    self.doc.build(self.story)
                    print("✓ PDF built successfully without page callbacks")
                except Exception as e2:
                    print(f"Build failed completely: {e2}")
                    raise e2
    
            # 10. Finalize and validate buffer
            self.buffer.seek(0)
            pdf_content = self.buffer.read()
            pdf_size = len(pdf_content)
            print(f"Generated PDF size: {pdf_size} bytes")
            
            if pdf_size < 1000:
                print("WARNING: PDF is suspiciously small - likely corrupted")
                return self._generate_error_pdf("Generated PDF too small")
            
            # Create final buffer
            final_buffer = BytesIO()
            final_buffer.write(pdf_content)
            final_buffer.seek(0)
            
            print("=== PDF GENERATION COMPLETED SUCCESSFULLY ===")
            return final_buffer
            
        except Exception as e:
            print(f"FATAL ERROR generating PDF: {e}")
            import traceback
            traceback.print_exc()
            return self._generate_error_pdf(str(e))
    def create_summary_header(self):
        """Create the summary page header"""
        try:
            title_style = ParagraphStyle(
                name='MainTitle', 
                fontSize=28, 
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )
            
            # Check if Hindi font is available
            try:
                pdfmetrics.getFont('HindiFont')
                hindi_font = 'HindiFont'
            except:
                hindi_font = 'Helvetica-Bold'
                
            hindi_style = ParagraphStyle(
                name='HindiTitle', 
                parent=title_style, 
                fontName=hindi_font, 
                fontSize=24
            )
            
            # self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
            # self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            # self.story.append(Spacer(1, 0.5 * inch))

            # Summary styles
            summary_style_caps = ParagraphStyle(
                name='SummaryCaps', 
                fontSize=18, 
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )
            summary_italic_style = ParagraphStyle(
                name='SummaryItalic', 
                fontSize=10, 
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Oblique'
            )
            summary_footer_style = ParagraphStyle(
                name='SummaryFooter', 
                fontSize=14, 
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )

            self.story.append(Paragraph("EXECUTIVE SUMMARY", summary_style_caps))
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph("(Auto generated through e-MCM App)", summary_italic_style))
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", summary_footer_style))
            self.story.append(Spacer(1, 0.4 * inch))

            # Add introduction paragraph - first part
            intro_text_part1 = f"""
            This executive summary presents the Infographical analysis of Audit Performance submitted during Monitoring Committee meeting for the {self.selected_period} period. 
            The report contains comprehensive charts and visualizations that highlight:
            """
            
            # Create bullet points as separate paragraphs for better alignment
            bullet_points = [
                "(i) <b>Overall Audit Performance</b> for the month, across Small, Medium, Large Categories",
                "(ii) <b>Status of Para Analysis</b>, based on Tax Recovery Status and pending recovery potential", 
                "(iii) <b>Sectoral Analysis</b>, based on Trader, Manufacturer and Service sectors",
                "(iv) <b>Nature of Non Compliance Analysis</b>, using Audit Para Categorisation Coding System of Audit-1 commissionerate",
                "(v) <b>Risk Parameter Analysis</b>",
                "(vi) <b>Top Audit Group and Circle Performance</b>",
                "(vii) <b>Top Taxpayers of Detection and Recovery</b>",
                "(viii) <b>MCM Decision Analysis</b>"
            ]
            
            # Final part
            conclusion_text = """
            The report covers the <b>Summary of Taxpayer wise Audit paras raised and the decision taken during MCM</b>, encompassing all the Draft Audit Reports submitted before Monitoring Committee.
            """
            
         
            
            intro_style = ParagraphStyle(
                name='IntroStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.5*inch,
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=12
            )
            
            # Create bullet point style with proper indentation
            bullet_style = ParagraphStyle(
                name='BulletStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_LEFT,
                fontName='Helvetica',
                leftIndent=0.75*inch,  # Fixed left indent for alignment
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=4,
                spaceBefore=2
            )
            
            # Add the introduction parts
            self.story.append(Paragraph(intro_text_part1, intro_style))
            
            # Add each bullet point as a separate paragraph
            for bullet in bullet_points:
                self.story.append(Paragraph(bullet, bullet_style))
            
            # Add conclusion
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph(conclusion_text, intro_style))
            
            # # Add Monthly Performance Summary section
            # self.story.append(Spacer(1, 0.3 * inch))
            # self.add_monthly_performance_summary()
            # self.story.append(Spacer(1, 0.3 * inch))
                
        except Exception as e:
            print(f"Error creating summary header: {e}")

    def create_structured_chart_sections(self):
        """Create structured sections with headings and descriptions for each chart"""
        if not self.chart_images or len(self.chart_images) == 0:
            placeholder_style = ParagraphStyle(
                name='Placeholder', 
                parent=self.styles['Normal'],
                fontSize=12, 
                alignment=TA_CENTER
            )
            self.story.append(Paragraph("No charts available for this report.", placeholder_style))
            return

        successful_charts = 0
        
        for i, img_bytes in enumerate(self.chart_images):
            try:
                if img_bytes is None:
                    self._add_chart_error_section(i, "No image data provided")
                    continue

                print(f"Processing chart section {i+1}/{len(self.chart_images)}")
                
                # Get metadata for this chart
                metadata = self.chart_metadata[i] if i < len(self.chart_metadata) else {
                    "title": f"Chart {i+1}",
                    "description": "Analysis and insights from the data visualization.",
                    "page_break_after": False
                }
                
                # Add chart title
                self.story.append(Paragraph(metadata["title"], self.chart_title_style))
                
                # Add chart description
                self.story.append(Paragraph(metadata["description"], self.chart_description_style))
                
                # Create and add the chart
                drawing, error = self._create_safe_svg_drawing(img_bytes)
                # Add this after: drawing, error = self._create_safe_svg_drawing(img_bytes)
                print(f"=== DEBUG CHART {chart_id} ===")
                print(f"Requested size: {size}")
                print(f"Drawing object: {drawing}")
                if drawing:
                    print(f"Drawing width: {getattr(drawing, 'width', 'No width')}")
                    print(f"Drawing height: {getattr(drawing, 'height', 'No height')}")
                print(f"Target width should be: {size_configs.get(size, 'Unknown')}")
                print("=" * 30)
                if error:
                    print(f"Chart {i+1} error: {error}")
                    self._add_chart_error_inline(i, error)
                    continue

                if drawing is None:
                    self._add_chart_error_inline(i, "Could not create drawing")
                    continue

                # Scale and add the drawing
                try:
                    render_width = 6.5 * inch
                    scale_factor = render_width / drawing.width
                    drawing.width = render_width
                    drawing.height = drawing.height * scale_factor
                    drawing.hAlign = 'CENTER'
                    
                    # Add the chart with reduced spacing
                    self.story.append(Spacer(1, 0.1 * inch))  # Reduced from 0.3
                    self.story.append(drawing)
                    self.story.append(Spacer(1, 0.2 * inch))  # Reduced from 0.3
                    successful_charts += 1
                    
                    print(f"Successfully processed chart {i+1}")
                    
                    # Add page break if specified in metadata
                    if metadata.get("page_break_after", False):
                        self.story.append(PageBreak())
                        
                except Exception as scale_error:
                    print(f"Chart {i+1} scaling error: {scale_error}")
                    self._add_chart_error_inline(i, f"Scaling failed: {scale_error}")
                    
            except Exception as e:
                print(f"Unexpected error processing chart section {i+1}: {e}")
                self._add_chart_error_section(i, f"Unexpected error: {e}")

        print(f"Successfully processed {successful_charts}/{len(self.chart_images)} chart sections")

    def _add_chart_error_section(self, chart_index, error_message):
        """Add error section for failed chart with title"""
        try:
            metadata = self.chart_metadata[chart_index] if chart_index < len(self.chart_metadata) else {
                "title": f"Chart {chart_index+1}",
                "description": "Chart could not be generated due to technical issues."
            }
            
            # Add title even for error
            self.story.append(Paragraph(metadata["title"], self.chart_title_style))
            
            # Add error message
            error_style = ParagraphStyle(
                name='ChartError', 
                parent=self.styles['Normal'],
                fontSize=11, 
                textColor=colors.red,
                alignment=TA_CENTER,
                fontName='Helvetica-Oblique'
            )
            self.story.append(Paragraph(f"Unable to load chart: {error_message}", error_style))
            self.story.append(Spacer(1, 0.3 * inch))
        except Exception as e:
            print(f"Error adding chart error section: {e}")

    def _add_chart_error_inline(self, chart_index, error_message):
        """Add inline error message for failed chart"""
        try:
            error_style = ParagraphStyle(
                name='ChartErrorInline', 
                parent=self.styles['Normal'],
                fontSize=10, 
                textColor=colors.red,
                alignment=TA_CENTER,
                fontName='Helvetica-Oblique'
            )
            self.story.append(Paragraph(f"Chart error: {error_message}", error_style))
            self.story.append(Spacer(1, 0.3 * inch))
        except Exception as e:
            print(f"Error adding inline chart error: {e}")

    # Include all the other methods from your original class...
    # (I'll include the key ones for SVG processing)

    def _validate_svg_content(self, svg_content):
        """Validate SVG content and fix common issues that cause transformation errors"""
        try:
            if isinstance(svg_content, bytes):
                svg_string = svg_content.decode('utf-8')
            else:
                svg_string = str(svg_content)

            if len(svg_string.strip()) < 10:
                return None, "SVG content too short"

            try:
                root = ET.fromstring(svg_string)
            except ET.ParseError as e:
                return None, f"Invalid XML structure: {e}"

            if not (root.tag.endswith('svg') or 'svg' in root.tag.lower()):
                return None, "Not a valid SVG element"

            svg_string = self._fix_svg_transforms(svg_string)
            svg_string = self._ensure_svg_dimensions(svg_string)

            return svg_string.encode('utf-8'), None

        except Exception as e:
            return None, f"SVG validation error: {e}"

    def _fix_svg_transforms(self, svg_string):
        """Fix problematic transformation matrices in SVG"""
        svg_string = re.sub(r'scale\(0(?:\.0*)?\)', 'scale(0.001)', svg_string)
        svg_string = re.sub(r'scale\(0(?:\.0*)?[,\s]+0(?:\.0*)?\)', 'scale(0.001,0.001)', svg_string)
        
        def fix_matrix(match):
            values = [float(x.strip()) for x in match.group(1).split(',')]
            if len(values) == 6:
                a, b, c, d, e, f = values
                det = a * d - b * c
                if abs(det) < 1e-10:
                    return 'matrix(1,0,0,1,0,0)'
            return match.group(0)
        
        svg_string = re.sub(r'matrix\(([^)]+)\)', fix_matrix, svg_string)
        return svg_string

    def _ensure_svg_dimensions(self, svg_string):
        """Ensure SVG has proper width and height attributes"""
        if 'width=' not in svg_string and 'height=' not in svg_string:
            svg_string = re.sub(
                r'<svg([^>]*?)>', 
                r'<svg\1 width="400" height="300">', 
                svg_string, 
                count=1
            )
        
        svg_string = re.sub(r'width=["\']0["\']', 'width="400"', svg_string)
        svg_string = re.sub(r'height=["\']0["\']', 'height="300"', svg_string)
        
        return svg_string

    def _create_safe_svg_drawing(self, img_bytes):
        """Create an SVG drawing with comprehensive error handling and validation"""
        try:
            img_bytes.seek(0)
            original_content = img_bytes.read()
            
            if not original_content:
                return None, "Empty image data"

            fixed_content, error = self._validate_svg_content(original_content)
            if error:
                return None, error

            fixed_buffer = BytesIO(fixed_content)
            
            try:
                drawing = svg2rlg(fixed_buffer)
            except Exception as svg_error:
                return None, f"SVG parsing failed: {svg_error}"

            if drawing is None:
                return None, "svg2rlg returned None"

            if not hasattr(drawing, 'width') or not hasattr(drawing, 'height'):
                return None, "Drawing missing width/height attributes"

            if drawing.width <= 0 or drawing.height <= 0:
                return None, f"Invalid dimensions: {drawing.width}x{drawing.height}"

            if not (0 < drawing.width < 10000 and 0 < drawing.height < 10000):
                return None, f"Unreasonable dimensions: {drawing.width}x{drawing.height}"

            return drawing, None

        except Exception as e:
            return None, f"Unexpected error creating SVG drawing: {e}"

    def _generate_error_pdf(self, error_message):
        """Generate a simple PDF with error message if main generation fails"""
        try:
            error_buffer = BytesIO()
            error_doc = SimpleDocTemplate(error_buffer, pagesize=letter)
            error_story = []
            
            error_style = ParagraphStyle(
                name='Error', 
                parent=self.styles['Normal'],
                fontSize=12, 
                textColor=colors.red,
                alignment=TA_CENTER
            )
            
            error_story.append(Spacer(1, 2*inch))
            error_story.append(Paragraph("PDF Generation Error", error_style))
            error_story.append(Spacer(1, 0.5*inch))
            error_story.append(Paragraph(f"Error: {error_message}", self.styles['Normal']))
            error_story.append(Spacer(1, 0.5*inch))
            error_story.append(Paragraph("Please check your chart data and try again.", self.styles['Normal']))
            
            error_doc.build(error_story)
            error_buffer.seek(0)
            return error_buffer
        except Exception as fallback_error:
            print(f"Even fallback PDF generation failed: {fallback_error}")
            empty_buffer = BytesIO()
            empty_buffer.write(b"PDF generation failed")
            empty_buffer.seek(0)
            return empty_buffer

    def add_page_elements(self, canvas, doc):
        """Unified method to draw static elements on ALL pages"""
        try:
            canvas.saveState()
            if doc.page == 1:
                # Cover Page Background
                canvas.setFillColor(colors.HexColor("#193041"))  # Dark Blue
                canvas.rect(0, self.height * 0.20, self.width, self.height, stroke=0, fill=1)
                canvas.setFillColor(colors.HexColor("#C8B59E"))  # Gold
                canvas.rect(0, 0, self.width, self.height * 0.20, stroke=0, fill=1)
                canvas.setStrokeColor(colors.HexColor("#C8B59E"))
                canvas.setLineWidth(3)
                canvas.line(0, self.height * 0.20, self.width, self.height * 0.20)

                # Draw static lines for the cover page
                canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
                canvas.setLineWidth(1)
                logo_y_pos = self.height - 1.6 * inch
                canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos)  # Left line
                canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos)  # Right line
            else:
                # Background for all other pages
                canvas.setFillColor(colors.HexColor("#FAEBD7"))  # Light beige
                canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
            
            canvas.restoreState()
        except Exception as e:
            print(f"Error drawing page elements: {e}")
            canvas.restoreState()

    def create_cover_page_story(self):
        """Method to create the cover page CONTENT with logos"""
        try:
            # CBIC Logo at the Top
            try:
                cbic_logo = Image('cbic_logo.png', width=1.6*inch, height=1.6*inch)
                cbic_logo.hAlign = 'CENTER'
                self.story.append(cbic_logo)
            except Exception as e:
                print(f"Warning: cbic_logo.png not found. Using text placeholder. Error: {e}")
                logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
                self.story.append(Paragraph("CBIC LOGO", logo_style))
            
            self.story.append(Spacer(1, 0.8 * inch))

            # Title and Subtitles
            title_style = ParagraphStyle(name='Title', fontSize=38, textColor=colors.HexColor("#f5ddc1"),
                                       alignment=TA_CENTER, fontName='Helvetica-Bold', leading=46)
            title2_style = ParagraphStyle(name='Title2', parent=title_style, fontSize=34)
            title3_style = ParagraphStyle(name='Title3', parent=title_style, fontSize=26, textColor=colors.HexColor("#FCC200"),fontName='Helvetica')
            title4_style = ParagraphStyle(name='Title4', parent=title_style, fontSize=20,textColor=colors.HexColor("#FC200") ,fontName='Helvetica-Oblique')
            # NEW: MCM Date Style
            mcm_date_style = ParagraphStyle(name='MCMDate', parent=title_style, fontSize=18, 
                                           textColor=colors.HexColor("#FFE5B4"), fontName='Helvetica-Bold')
        
            try:
                pdfmetrics.getFont('HindiFont')
                hindi_font = 'HindiFont'
            except:
                hindi_font = 'Helvetica-Bold'
            hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName=hindi_font, fontSize=24)
            
            self.story.append(Paragraph("MONITORING COMMITTEE MEETING", title_style))
            #self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            self.story.append(Paragraph(" िनगरानी सिमित की बैठक", hindi_style))
           
            self.story.append(Paragraph(f"{self.selected_period.upper()}", title2_style))
            ##self.story.append(Spacer(1, 0.1 * inch))
            # NEW: Add MCM Date if available
            mcm_date = self.vital_stats.get('mcm_date')
            if mcm_date:
                self.story.append(Spacer(1, 0.2 * inch))
                self.story.append(Paragraph(f"Meeting Date: {mcm_date}", mcm_date_style))
            
            self.story.append(Spacer(1, 0.2 * inch))
            self.story.append(Paragraph("EXECUTIVE SUMMARY REPORT", title3_style))
            #self.story.append(Paragraph(" कार्यकारी सारांश प्रतिवेदन", hindi_style))
            self.story.append(Paragraph("[Auto-generated by e-MCM App]", title4_style))
            
            self.story.append(Spacer(1, 1.4 * inch))

            # Emblem and Address at the Bottom using a Table
            contact_style = ParagraphStyle(name='Contact', fontSize=12, textColor=colors.HexColor("#193041"), alignment=TA_LEFT)
            org_style = ParagraphStyle(name='Org', fontSize=18, textColor=colors.HexColor("#193041"), alignment=TA_LEFT, fontName='Helvetica-Bold', leading=18)
            disclaimer_style = ParagraphStyle(name='Org', fontSize=10, textColor=colors.HexColor("#193041"), alignment=TA_LEFT, fontName='Helvetica-Oblique', leading=18)
            right_col_text = [
                Paragraph("Office of the Commissioner of CGST & Central Excise", org_style),
                Paragraph("Audit-I Commissionerate, Mumbai", org_style),
                Spacer(1, 0.2 * inch),
                Paragraph("Ph: 022-22617504 | Email: audit1mum@gov.in", contact_style),
                Spacer(1, 0.3 * inch),
                Paragraph("Note:For more details on MCM decisions ,refer to Detailed Minutes of the Meeting document", disclaimer_style)
            ]

            try:
                emblem_logo = Image('emblem.png', width=0.8*inch, height=1.2*inch)
            except Exception as e:
                print(f"Warning: emblem.png not found. Using a text placeholder. Error: {e}")
                emblem_logo = Paragraph("EMBLEM", contact_style)

            table_data = [[emblem_logo, right_col_text]]
            bottom_table = Table(table_data, colWidths=[1.0*inch, 6.5*inch])

            bottom_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            self.story.append(bottom_table)
            self.story.append(Spacer(1, 0.2 * inch))
        except Exception as e:
            print(f"Error creating cover page: {e}")

    def add_monthly_performance_summary(self):
        """Add I and II sections-  Monthly Performance Summary section and status of para with metrics and table"""
        try:
            # Section header
            perf_header_style = ParagraphStyle(
                name='PerfHeader',
                parent=self.styles['Heading2'],
                fontSize=18,
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=16,
                spaceBefore=16
            )
            para_style = ParagraphStyle(
                name='IntroStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.5*inch,
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=12
            )
            self.add_section_highlight_bar("I. Monthly Performance Summary",text_color="#0E4C92")
            #self.story.append(Paragraph("I. Monthly Performance Summary", perf_header_style))
            
            # Extract metrics from vital_stats - using the correct keys from visualisation_utils.py
            dars_submitted = self.vital_stats.get('num_dars', 0)
            revenue_involved = self.vital_stats.get('total_detected', 0)
            revenue_recovered = self.vital_stats.get('total_recovered', 0)
            
            # Create metrics section using a table for better layout
            metrics_data = [
                ['✅ DARs Submitted', '💰 Revenue Involved', '💎 Revenue Recovered'],
                [f'{dars_submitted}', f'Rs.{revenue_involved:.2f} L', f'Rs.{revenue_recovered:.2f} L']
            ]
            metrics_table = Table(metrics_data, colWidths=[3*inch, 3*inch, 3*inch])
            #metrics_table = Table(metrics_data, colWidths=[2.33*inch, 2.33*inch, 2.33*inch])
            metrics_table.setStyle(TableStyle([
                # Header row styling
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#666666")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Data row styling
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 24),
                #('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#1134A6")),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#0f52ba")),
                
                # Spacing
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            
            self.story.append(metrics_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Performance Summary Table Header
            table_header_style = ParagraphStyle(
                name='TableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("🎯 Performance Summary Table", table_header_style))
            
            # Get the categories summary from vital_stats (populated by visualisation_utils.py)
            categories_summary = self.vital_stats.get('categories_summary', [])
            
            # Create the performance data table
            if categories_summary:
                # Build table from actual data
                performance_data = [['CATEGORY', 'NO. OF DARS', 'TOTAL DETECTED', 'TOTAL RECOVERED', 'NO. OF AUDIT PARAS']]
                
                total_dars = 0
                total_detected = 0
                total_recovered = 0
                total_paras = 0
                
                for category_data in categories_summary:
                    category = category_data.get('category', 'Unknown')
                    dars = int(category_data.get('dars_submitted', 0))
                    detected = float(category_data.get('total_detected', 0))
                    recovered = float(category_data.get('total_recovered', 0))
                    paras = int(category_data.get('num_audit_paras', 0))
                    
                    total_dars += dars
                    total_detected += detected
                    total_recovered += recovered
                    total_paras += paras
                    
                    performance_data.append([
                        category,
                        str(dars),
                        f'Rs.{detected:,.2f} L',
                        f'Rs.{recovered:,.2f} L',
                        str(paras)
                    ])
                
                # Add total row
                performance_data.append([
                    '📊 Total (All)',
                    str(total_dars),
                    f'Rs.{total_detected:,.2f} L',
                    f'Rs.{total_recovered:,.2f} L',
                    str(total_paras)
                ])
            else:
                # Fallback to default data if categories_summary is not available
                performance_data = [
                    ['CATEGORY', 'NO. OF DARS', 'TOTAL DETECTED', 'TOTAL RECOVERED', 'NO. OF AUDIT PARAS'],
                    ['Large', '0', '0 L', 'Rs.0.00 L', '0'],
                    ['Medium', '0', '0 L', 'Rs.15.20 L', '0'],
                    ['Small', '0', '0 L', 'Rs.0.00 L', '0'],
                    ['📊 Total (All)', '10', 'Rs.0 L', '0 ', '0']
                ]
            
            # Create table with custom column widths
            #col_widths = [1.4*inch, 0.9*inch, 1.2*inch, 1.2*inch, 1.3*inch]
            col_widths = [1*inch, 1.2*inch, 1.8*inch, 1.8*inch, 1.8*inch]
            performance_table = Table(performance_data, colWidths=col_widths)
            
            # SAFE table styling with bounds checking
            total_rows = len(performance_data)
            print(f"Performance table has {total_rows} rows")
            
            # Base styles that are always safe
            performance_styles = [
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows styling
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, -2), 10),
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('TEXTCOLOR', (0, 1), (-1, -2), colors.HexColor("#333333")),
                
                # Total row styling (last row)
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 10),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
                # Vertical alignment
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # SAFE alternating row colors - only for rows that exist
            # SAFE - proper bounds checking
            if total_rows > 2:  # Only if we have data rows beyond header
                for row_idx in range(2, min(total_rows - 1, 10)):  # Limit to reasonable range and exclude totals
                    if row_idx % 2 == 0:  # Every other row
                        performance_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8F8F8")))
            
            # Apply styles safely
            try:
                performance_table.setStyle(TableStyle(performance_styles))
                print(f"✓ Applied {len(performance_styles)} performance table styles successfully")
            except Exception as style_error:
                print(f"ERROR applying performance table styles: {style_error}")
                # Fallback with minimal styling
                performance_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ]))
                        
            self.story.append(performance_table)
            self.story.append(Spacer(1, 0.3 * inch))
            print("=== TRYING TO INSERT CHARTS ===")
        
            # Add Status Summary Table if available
            self.add_section_highlight_bar("II. Status of Audit Para Analysis",text_color="#0E4C92")
            section2_description='This section provides analysis of Audit paras based on the Recovery status of the amount involved and shows potential recovery paras , actionable by the audit groups'
            self.story.append(Paragraph(section2_description, para_style))
            if self.vital_stats.get('status_analysis_available', False):
                self.add_status_summary_table()
            # INSERT STATUS ANALYSIS CHART
           
            print(f"Chart registry keys: {list(self.chart_registry.keys())}")
            print(f"Chart registry: {self.chart_registry}")
            
            # result1 = self.insert_chart_by_id("status_analysis", size="medium", add_title=False)
            # print(f"Status analysis result: {result1}")
            
            # result2 = self.insert_chart_by_id("recovery_trends", size="small") 
            # print(f"Recovery trends result: {result2}")
            # print("=== FINISHED CHART INSERTION ===")
            # if self.vital_stats.get('status_analysis_available', False):
            #     self.add_status_summary_table()
                
            # # INSERT RECOVERY TRENDS CHART
            # self.insert_chart_by_id("recovery_trends", size="small",add_title=False)
            
            # # Add Risk Parameter Analysis if available
            # if self.vital_stats.get('risk_analysis_available', False):
            #     self.add_risk_parameter_analysis()
            
        except Exception as e:
            print(f"Error adding monthly performance summary: {e}")
            # Add error message if table creation fails
            error_style = ParagraphStyle(
                name='TableError',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.red,
                alignment=TA_CENTER
            )
            self.story.append(Paragraph("Error loading performance summary table", error_style))

    # def add_status_summary_table(self):
    #     """Add Status Summary Table section"""
    #     try:
    #         # Section header
    #         status_header_style = ParagraphStyle(
    #             name='StatusHeader',
    #             parent=self.styles['Heading3'],
    #             fontSize=14,
    #             textColor=colors.HexColor("#1134A6"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=12,
    #             spaceBefore=16
    #         )
            
    #         self.story.append(Paragraph("📊 Status Summary Table", status_header_style))
            
    #         # Get status summary data from vital_stats (if available from visualization processing)
    #         status_summary_data = self.vital_stats.get('status_summary', [])
            
    #         if status_summary_data:
    #             # Build table from actual data
    #             status_data = [['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION (Rs.L)', 'TOTAL RECOVERY (Rs.L)', 'RECOVERY %']]
                
    #             for status_item in status_summary_data:
    #                 status = status_item.get('status_of_para', 'Unknown')
    #                 paras = int(status_item.get('Para_Count', 0))
    #                 detection = float(status_item.get('Total_Detection', 0))
    #                 recovery = float(status_item.get('Total_Recovery', 0))
    #                 recovery_pct = float(status_item.get('Recovery_Percentage', 0))
                    
    #                 status_data.append([
    #                     status,
    #                     str(paras),
    #                     f'Rs.{detection:,.2f} L',
    #                     f'Rs.{recovery:,.2f} L',
    #                     f'{recovery_pct:.1f}%'
    #                 ])
    #         else:
    #             # Fallback data based on the image you shared
    #             status_data = [
    #                 ['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION ( L)', 'TOTAL RECOVERY (L)', 'RECOVERY %'],
    #                 ['Agreed yet to pay', '51', '₹13.74 L', '₹0.00 L', '0.0%'],
    #                 ['Agreed and Paid', '26', '₹19.96 L', '₹9.20 L', '46.1%'],
    #                 ['Not agreed', '16', '₹1.07 L', '₹0.00 L', '0.0%'],
    #                 ['Partially agreed, yet to paid', '1', '₹0.00 L', '₹0.00 L', '0.0%']
    #             ]
            
    #         # Create the status table
    #         #status_col_widths = [2.2*inch, 0.8*inch, 1.3*inch, 1.3*inch, 1.0*inch]
    #         status_col_widths = [1.8*inch, 1*inch, 1.8*inch, 1.8*inch, 1.8*inch]
    #         status_table = Table(status_data, colWidths=status_col_widths)
    #         # SAFE TABLE STYLING - check table size first
    #         total_rows = len(status_data)
    #         print(f"Status table has {total_rows} rows")
            
    #         # Base styles that are always safe
    #         base_styles = [
    #             # Header styling with gradient effect
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),  # Purple header
    #             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 0), (-1, 0), 9),
    #             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
    #             # Data rows with alternating colors
    #             ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #             ('FONTSIZE', (0, 1), (-1, -1), 9),
    #             ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Numbers centered
    #             ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Status left-aligned
                
    #             # Grid and borders
    #             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #             ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                
    #             # Padding
    #             ('TOPPADDING', (0, 0), (-1, -1), 6),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 8),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                
    #             # Vertical alignment
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #         ]
            
    #         # SAFE row coloring - only for rows that actually exist
    #         row_colors = ["#E8F5E8", "#FFF3CD", "#F8D7DA", "#E2E3E5"]
            
    #         for i in range(1, total_rows):  # Start from row 1 (skip header at row 0)
    #             if i <= len(row_colors):  # Don't exceed available colors
    #                 color_index = (i - 1) % len(row_colors)  # Cycle through colors
    #                 base_styles.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(row_colors[color_index])))
            
    #         # Apply all styles safely
    #         status_table.setStyle(TableStyle(base_styles))
            
            
    #         self.story.append(status_table)
    #         self.story.append(Spacer(1, 0.05 * inch))
    #         self.story.append(Paragraph("📊 Total Recovery Potential", status_header_style))
    #         self.insert_chart_by_id("status_analysis", size="small")
    #         self.story.append(Spacer(1, 0.05 * inch))
    #         # Add "Top 5 Paras with Largest Detection" section if data is available
    #         # if self.vital_stats.get('agreed_yet_to_pay_analysis'):
    #         #     self.add_top_agreed_paras_section()
          
    #         try:
    #             # Get the analysis data
    #             agreed_analysis = self.vital_stats.get('agreed_yet_to_pay_analysis', {})
                
    #             if agreed_analysis and agreed_analysis.get('top_5_paras') is not None:
    #                 # Add summary metrics
    #                 total_paras = agreed_analysis.get('total_paras', 0)
    #                 total_detection = agreed_analysis.get('total_detection', 0)
    #                 total_recovery = agreed_analysis.get('total_recovery', 0)
                    
    #                 # Create metrics row
    #                 metrics_data = [
    #                     [f"Total 'Agreed yet to pay' Paras", f"Total Detection Amount", f"Total Recovery Potential"],
    #                     [f"{total_paras}", f"Rs.{total_detection:,.2f} L", f"Rs.{total_detection:,.2f} L"]
    #                 ]
    #                    # Section header
    #                 top_paras_header_style = ParagraphStyle(
    #                     name='TopParasHeader',
    #                     parent=self.styles['Heading3'],
    #                     fontSize=14,
    #                     textColor=colors.HexColor("#1134A6"),
    #                     alignment=TA_LEFT,
    #                     fontName='Helvetica-Bold',
    #                     spaceAfter=12,
    #                     spaceBefore=16
    #                 )
                    
                    
    #                 metrics_table = Table(metrics_data, colWidths=[2.33*inch, 2.33*inch, 2.33*inch])
    #                 metrics_table.setStyle(TableStyle([
    #                     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                     ('FONTSIZE', (0, 0), (-1, 0), 10),
    #                     ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
    #                     ('FONTSIZE', (0, 1), (-1, 1), 12),
    #                     ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #                     ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #                     ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8F4F8")),
    #                     ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F8FF")),
    #                     ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #                     ('TOPPADDING', (0, 0), (-1, -1), 6),
    #                     ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    #                 ]))
                    
    #                 self.story.append(metrics_table)
    #                 top_5_paras = agreed_analysis['top_5_paras']
                    
    #                 # Create table data
    #                 #para_data = [['Audit Group', 'Trade Name', 'Para No.', 'Para Heading', 'Detection (Rs.L)', 'Recovery (Rs.L)', 'Status']]
    #                 para_data = [['Audit Group', 'Trade Name', 'Para Heading', 'Detection (Rs.L)']]
    #                 for _, row in top_5_paras.iterrows():
    #                     audit_group = str(row.get('audit_group_number_str', 'N/A'))
    #                     trade_name = str(row.get('trade_name', 'N/A'))[:50] + '...' if len(str(row.get('trade_name', 'N/A'))) > 30 else str(row.get('trade_name', 'N/A'))
    #                     #para_no = str(row.get('audit_para_number', 'N/A'))
    #                     para_heading = str(row.get('audit_para_heading', 'N/A'))[:100] + '...' if len(str(row.get('audit_para_heading', 'N/A'))) > 100 else str(row.get('audit_para_heading', 'N/A'))
    #                     detection = f"Rs.{row.get('Para Detection in Lakhs', 0):.2f} L"
    #                     #recovery = f"₹{row.get('Para Recovery in Lakhs', 0):.2f} L"
    #                     #status = str(row.get('status_of_para', 'N/A'))
                        
    #                     #para_data.append([audit_group, trade_name, para_no, para_heading, detection, recovery, status])
    #                     para_data.append([audit_group, trade_name,  para_heading, detection])
                    
    #                 # Create table
    #                 para_col_widths = [0.7*inch, 1.6*inch, 4.8*inch, 1.1*inch]
    #                 para_table = Table(para_data, colWidths=para_col_widths)
                    
    #                 # FIX 3: Correct table styling for 4 columns (indices 0,1,2,3)
    #                 para_table.setStyle(TableStyle([
    #                     # Header styling
    #                     ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
    #                     ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #                     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                     ('FONTSIZE', (0, 0), (-1, 0), 8),
    #                     ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        
    #                     # Data rows
    #                     ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #                     ('FONTSIZE', (0, 1), (-1, -1), 8),
                        
    #                     # FIXED ALIGNMENTS for 4 columns (0=Group, 1=Trade, 2=Heading, 3=Detection)
    #                     ('ALIGN', (3, 1), (3, -1), 'RIGHT'),   # Detection column (index 3) right-aligned
    #                     ('ALIGN', (0, 1), (2, -1), 'LEFT'),    # Other columns (0,1,2) left-aligned
    #                     # REMOVED: Status center alignment (no Status column anymore)
                        
    #                     # Alternating row colors
    #                     ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F8F8")),
    #                     ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F8F8")),
    #                     ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F8F8")),
                        
    #                     # Grid and borders
    #                     ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #                     ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
                        
    #                     # Padding
    #                     ('TOPPADDING', (0, 0), (-1, -1), 4),
    #                     ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    #                     ('LEFTPADDING', (0, 0), (-1, -1), 4),
    #                     ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                        
    #                     # Vertical alignment - ADD TOP alignment for better text wrapping
    #                     ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Changed from MIDDLE to TOP
    #                 ]))
    #                 self.story.append(Paragraph("🎯 Top 5 Paras with Largest Detection - Status: 'Agreed yet to pay'", top_paras_header_style))
    #                 self.story.append(para_table)
    #                 self.story.append(Spacer(1, 0.2 * inch))
                    
                    
                    
    #             else:
    #                 # Fallback message
    #                 info_style = ParagraphStyle(
    #                     name='InfoStyle',
    #                     parent=self.styles['Normal'],
    #                     fontSize=10,
    #                     textColor=colors.HexColor("#666666"),
    #                     alignment=TA_CENTER
    #                 )
    #                 self.story.append(Paragraph("No 'Agreed yet to pay' paras found for this period.", info_style))
                    
    #         except Exception as e:
    #             print(f"Error adding top agreed paras section: {e}")    
    #     except Exception as e:
    #         print(f"Error adding status summary table: {e}") 
    def add_status_summary_table(self):
        """Add Status Summary Table section - FIXED IndexError Safe Version"""
        try:
            # Section header
            status_header_style = ParagraphStyle(
                name='StatusHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("📊 Status Summary Table", status_header_style))
            
            # Get status summary data from vital_stats
            status_summary_data = self.vital_stats.get('status_summary', [])
            
            if status_summary_data:
                # Build table from actual data
                status_data = [['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION (Rs.L)', 'TOTAL RECOVERY (Rs.L)', 'RECOVERY %']]
                
                for status_item in status_summary_data:
                    status = status_item.get('status_of_para', 'Unknown')
                    paras = int(status_item.get('Para_Count', 0))
                    detection = float(status_item.get('Total_Detection', 0))
                    recovery = float(status_item.get('Total_Recovery', 0))
                    recovery_pct = float(status_item.get('Recovery_Percentage', 0))
                    
                    status_data.append([
                        status,
                        str(paras),
                        f'Rs.{detection:,.2f} L',
                        f'Rs.{recovery:,.2f} L',
                        f'{recovery_pct:.1f}%'
                    ])
            else:
                # Fallback data
                status_data = [
                    ['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION ( L)', 'TOTAL RECOVERY (L)', 'RECOVERY %'],
                    ['Agreed yet to pay', '51', '₹13.74 L', '₹0.00 L', '0.0%'],
                    ['Agreed and Paid', '26', '₹19.96 L', '₹9.20 L', '46.1%'],
                    ['Not agreed', '16', '₹1.07 L', '₹0.00 L', '0.0%'],
                    ['Partially agreed, yet to paid', '1', '₹0.00 L', '₹0.00 L', '0.0%']
                ]
            
            # SAFE TABLE CREATION - check dimensions first
            total_rows = len(status_data)
            total_cols = len(status_data[0]) if status_data else 0
            print(f"Status table: {total_rows} rows x {total_cols} cols")
            
            if total_rows < 2:  # Need at least header + 1 data row
                print("Warning: Insufficient data for status table")
                return
            
            # Create table
            status_col_widths = [1.8*inch, 1*inch, 1.8*inch, 1.8*inch, 1.8*inch]
            status_table = Table(status_data, colWidths=status_col_widths)
            
            # SAFE BASE STYLES - no hardcoded row references
            base_styles = [
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows - SAFE ranges
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Numbers centered
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Status left-aligned only
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # SAFE ALTERNATING ROW COLORS - dynamic based on actual table size
            alternating_colors = ["#E8F5E8", "#FFF3CD", "#F8D7DA", "#E2E3E5"]
            
            for row_idx in range(1, total_rows):  # Start from row 1 (skip header)
                try:
                    color_index = (row_idx - 1) % len(alternating_colors)
                    base_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), 
                                     colors.HexColor(alternating_colors[color_index])))
                except Exception as color_error:
                    print(f"Error applying color to row {row_idx}: {color_error}")
                    break
            
            # SAFE TABLE STYLING APPLICATION
            try:
                status_table.setStyle(TableStyle(base_styles))
                print(f"✓ Applied {len(base_styles)} styles successfully to status table")
            except IndexError as e:
                print(f"IndexError in status table styling: {e}")
                # FALLBACK - minimal styling
                safe_styles = [
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]
                status_table.setStyle(TableStyle(safe_styles))
            except Exception as e:
                print(f"Critical error in status table styling: {e}")
                # Absolute fallback
                status_table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, colors.black)]))
            
            self.story.append(status_table)
            self.story.append(Spacer(1, 0.05 * inch))
            
            # Charts and additional content...
            self.story.append(Paragraph("📊 Total Recovery Potential", status_header_style))
            self.insert_chart_by_id("status_analysis", size="small")
            self.story.append(Spacer(1, 0.05 * inch))
            
            # SAFE TOP 5 PARAS SECTION
            try:
                agreed_analysis = self.vital_stats.get('agreed_yet_to_pay_analysis', {})
                
                if agreed_analysis and agreed_analysis.get('top_5_paras') is not None:
                    self._add_safe_top_paras_table(agreed_analysis)
                else:
                    info_style = ParagraphStyle(name='InfoStyle', parent=self.styles['Normal'],
                                              fontSize=10, textColor=colors.HexColor("#666666"), alignment=TA_CENTER)
                    self.story.append(Paragraph("No 'Agreed yet to pay' paras found for this period.", info_style))
                    
            except Exception as e:
                print(f"Error adding top agreed paras section: {e}")
                
        except Exception as e:
            print(f"Error adding status summary table: {e}")
    
    def _add_safe_top_paras_table(self, agreed_analysis):
        """SAFE version of top paras table creation"""
        try:
            total_paras = agreed_analysis.get('total_paras', 0)
            total_detection = agreed_analysis.get('total_detection', 0)
            total_recovery = agreed_analysis.get('total_recovery', 0)
            
            # Metrics table - SAFE creation
            metrics_data = [
                [f"Total 'Agreed yet to pay' Paras", f"Total Detection Amount", f"Total Recovery Potential"],
                [f"{total_paras}", f"Rs.{total_detection:,.2f} L", f"Rs.{total_detection:,.2f} L"]
            ]
            
            metrics_table = Table(metrics_data, colWidths=[2.33*inch, 2.33*inch, 2.33*inch])
            
            # SAFE metrics table styling
            safe_metrics_styles = [
                ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),  # SAFE: specific range
                ('FONTSIZE', (0, 0), (2, 0), 10),
                ('FONTNAME', (0, 1), (2, 1), 'Helvetica-Bold'),  # SAFE: specific range
                ('FONTSIZE', (0, 1), (2, 1), 12),
                ('ALIGN', (0, 0), (2, 1), 'CENTER'),             # SAFE: specific range
                ('VALIGN', (0, 0), (2, 1), 'MIDDLE'),            # SAFE: specific range
                ('BACKGROUND', (0, 0), (2, 0), colors.HexColor("#E8F4F8")),
                ('BACKGROUND', (0, 1), (2, 1), colors.HexColor("#F0F8FF")),
                ('GRID', (0, 0), (2, 1), 1, colors.HexColor("#CCCCCC")),  # SAFE: exact range
                ('TOPPADDING', (0, 0), (2, 1), 6),
                ('BOTTOMPADDING', (0, 0), (2, 1), 6),
            ]
            
            try:
                metrics_table.setStyle(TableStyle(safe_metrics_styles))
                self.story.append(metrics_table)
            except Exception as metrics_error:
                print(f"Error styling metrics table: {metrics_error}")
                # Add without styling if needed
                self.story.append(metrics_table)
            
            # Main paras table - SAFE creation
            top_5_paras = agreed_analysis['top_5_paras']
            para_data = [['Audit Group', 'Trade Name', 'Para Heading', 'Detection (Rs.L)']]
            
            # SAFE row processing
            rows_added = 0
            for _, row in top_5_paras.iterrows():
                if rows_added >= 5:  # Limit to 5 rows max
                    break
                    
                try:
                    audit_group = str(row.get('audit_group_number_str', 'N/A'))
                    trade_name = str(row.get('trade_name', 'N/A'))
                    if len(trade_name) > 30:
                        trade_name = trade_name[:30] + '...'
                    
                    para_heading = str(row.get('audit_para_heading', 'N/A'))
                    if len(para_heading) > 100:
                        para_heading = para_heading[:100] + '...'
                    
                    detection = f"Rs.{row.get('Para Detection in Lakhs', 0):.2f} L"
                    
                    para_data.append([audit_group, trade_name, para_heading, detection])
                    rows_added += 1
                    
                except Exception as row_error:
                    print(f"Error processing para row: {row_error}")
                    continue
            
            # SAFE TABLE CREATION
            if len(para_data) > 1:  # More than just header
                para_table = Table(para_data, colWidths=[0.7*inch, 1.6*inch, 4.8*inch, 1.1*inch])
                
                # SAFE STYLING - calculate valid ranges
                actual_rows = len(para_data)
                actual_cols = 4  # We know we have 4 columns
                
                para_styles = [
                    # Header styling - SAFE
                    ('BACKGROUND', (0, 0), (3, 0), colors.HexColor("#6F2E2E")),  # Exact range
                    ('TEXTCOLOR', (0, 0), (3, 0), colors.white),
                    ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (3, 0), 8),
                    ('ALIGN', (0, 0), (3, 0), 'CENTER'),
                    
                    # Grid and borders - SAFE
                    ('GRID', (0, 0), (3, actual_rows-1), 1, colors.HexColor("#CCCCCC")),
                    ('LINEBELOW', (0, 0), (3, 0), 2, colors.HexColor("#6F2E2E")),
                    
                    # Padding - SAFE
                    ('TOPPADDING', (0, 0), (3, actual_rows-1), 4),
                    ('BOTTOMPADDING', (0, 0), (3, actual_rows-1), 4),
                    ('LEFTPADDING', (0, 0), (3, actual_rows-1), 4),
                    ('RIGHTPADDING', (0, 0), (3, actual_rows-1), 4),
                    ('VALIGN', (0, 0), (3, actual_rows-1), 'TOP'),
                ]
                
                # SAFE DATA ROW STYLING - only if we have data rows
                if actual_rows > 1:
                    para_styles.extend([
                        ('FONTNAME', (0, 1), (3, actual_rows-1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (3, actual_rows-1), 8),
                        ('ALIGN', (3, 1), (3, actual_rows-1), 'RIGHT'),   # Detection column right-aligned
                        ('ALIGN', (0, 1), (2, actual_rows-1), 'LEFT'),    # Other columns left-aligned
                    ])
                
                # SAFE ALTERNATING COLORS - dynamic based on actual rows
                for row_idx in range(1, actual_rows):  # Skip header
                    if row_idx % 2 == 0:  # Every other row
                        para_styles.append(('BACKGROUND', (0, row_idx), (3, row_idx), colors.HexColor("#F8F8F8")))
                
                # APPLY STYLES SAFELY
                try:
                    para_table.setStyle(TableStyle(para_styles))
                    
                    # Add to story
                    top_paras_header_style = ParagraphStyle(
                        name='TopParasHeader', parent=self.styles['Heading3'],
                        fontSize=14, textColor=colors.HexColor("#1134A6"),
                        alignment=TA_LEFT, fontName='Helvetica-Bold',
                        spaceAfter=12, spaceBefore=16
                    )
                    
                    self.story.append(Paragraph("🎯 Top 5 Paras with Largest Detection - Status: 'Agreed yet to pay'", top_paras_header_style))
                    self.story.append(para_table)
                    self.story.append(Spacer(1, 0.2 * inch))
                    
                    print("✓ Successfully added safe top paras table")
                    
                except IndexError as style_error:
                    print(f"IndexError in para table styling: {style_error}")
                    # MINIMAL FALLBACK
                    para_table.setStyle(TableStyle([
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ]))
                    self.story.append(para_table)
                    
            else:
                print("No para data to display")
                
        except Exception as e:
            print(f"Error in _add_safe_top_paras_table: {e}")
    
    def add_sectoral_analysis(self):
        """Add Section III - Sectoral Analysis with pie charts and summary table"""
        try:
            # Section III Header
            self.story.append(Spacer(1, 0.2 * inch))
            self.add_section_highlight_bar("III. Sectoral Analysis", text_color="#0E4C92")
            
            # Description (same as before)
            desc_style = ParagraphStyle(
                name='SectoralDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides sectoral analysis of audit performance across different taxpayer classifications and business categories. 
            The analysis helps identify sector-wise compliance patterns and focus areas for targeted audit interventions .
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Chart heading style
            chart_header_style = ParagraphStyle(
                name='ChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            # First Chart
            self.story.append(Paragraph("🎯 Taxpayer Classification Analysis- Total DARs, Detection and Recovery", chart_header_style))
            self.insert_chart_by_id("taxpayer_classification_distribution", 
                                   size="small", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # # Second Chart
            # self.story.append(Paragraph("🎯 Detection Amount by Taxpayer Classification", chart_header_style))
            # self.insert_chart_by_id("taxpayer_classification_detection", 
            #                        size="medium", 
            #                        add_title=False, 
            #                        add_description=False)
            # self.story.append(Spacer(1, 0.2 * inch))
            # # Third Chart
            # self.story.append(Paragraph("🎯 Recovery Amount by Taxpayer Classification", chart_header_style))
            # self.insert_chart_by_id("taxpayer_classification_recovery", 
            #                        size="medium", 
            #                        add_title=False, 
            #                        add_description=False)
            # self.story.append(Spacer(1, 0.2 * inch))
            # ADD SECTORAL SUMMARY TABLE if data available
        
            if self.vital_stats.get('sectoral_analysis_available', False):
                self.add_sectoral_summary_table()
            
            self.story.append(Spacer(1, 0.3 * inch))
                
        except Exception as e:
            print(f"Error adding sectoral analysis: {e}")
    
    def add_sectoral_summary_table(self):
        """Add sectoral summary table - FIXED VERSION with bounds checking"""
        try:
            sectoral_summary = self.vital_stats.get('sectoral_summary', [])
            print('Sectoral summary',sectoral_summary)
            
            if sectoral_summary:
                table_header_style = ParagraphStyle(
                    name='SectoralTableHeader',
                    parent=self.styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor("#1134A6"),
                    alignment=TA_LEFT,
                    fontName='Helvetica-Bold',
                    spaceAfter=12,
                    spaceBefore=16
                )
                
                self.story.append(Paragraph("📊 Sectoral Performance Summary", table_header_style))
                
                # Create sectoral table data
                sectoral_data = [['Classification', 'No. of DARs', 'Detection (Rs.L)', 'Recovery (Rs.L)']]
                
                for item in sectoral_summary[:6]:  # Top 6 classifications
                    classification = item.get('classification', 'Unknown')
                    dar_count = item.get('dar_count', 0)
                    detection = item.get('total_detection', 0)
                    recovery = item.get('total_recovery', 0)
                    
                    sectoral_data.append([
                        classification,
                        str(dar_count),
                        f'Rs.{detection:.2f} L',
                        f'Rs.{recovery:.2f} L'
                    ])
                
                # SAFE table creation - check if we have data
                total_rows = len(sectoral_data)
                print(f"Sectoral table will have {total_rows} rows")
                
                if total_rows > 1:  # More than just header
                    sectoral_table = Table(sectoral_data, colWidths=[2.5*inch, 1.2*inch, 1.4*inch, 1.4*inch])
                    
                    # SAFE styling with bounds checking
                    sectoral_styles = [
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]
                    
                    # SAFE - proper bounds checking
                    if total_rows > 2:  # Only if we have data rows beyond header
                        for row_idx in range(2, min(total_rows - 1, 10)):  # Limit to reasonable range and exclude totals
                            if row_idx % 2 == 0:  # Every other row
                                performance_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8F8F8")))
                    # Apply styles safely
                    try:
                        sectoral_table.setStyle(TableStyle(sectoral_styles))
                        self.story.append(sectoral_table)
                        self.story.append(Spacer(1, 0.2 * inch))
                        print(f"✓ Successfully added sectoral table with {total_rows} rows")
                        
                    except Exception as style_error:
                        print(f"ERROR applying sectoral table styles: {style_error}")
                        # Fallback with minimal styling
                        sectoral_table.setStyle(TableStyle([
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ]))
                        self.story.append(sectoral_table)
                        self.story.append(Spacer(1, 0.2 * inch))
                else:
                    print("No sectoral data to display")
            else:
                print("No sectoral summary data available")
                    
        except Exception as e:
            print(f"Error adding sectoral summary table: {e}")
            import traceback
            traceback.print_exc()
            
    
    def add_comprehensive_classification_page(self):
        """Add an ultra-compact classification page that fits on one page"""
        try:
            # Get pre-processed classification data from vital_stats
            classification_data = self.vital_stats.get('classification_page_data', {})
            
            if classification_data:
                total_observations = classification_data.get('total_observations', 0)
                main_categories_count = classification_data.get('main_categories_count', 0)  
                sub_categories_count = classification_data.get('sub_categories_count', 0)
                
                # Convert category stats back to DataFrame for compatibility
                category_stats_records = classification_data.get('category_stats', [])
                category_stats = pd.DataFrame(category_stats_records)
                
                print(f"SUCCESS: Loaded classification data - {total_observations} observations")
            else:
                # Fallback values if no data
                total_observations = main_categories_count = sub_categories_count = 0
                category_stats = pd.DataFrame()
                print("WARNING: No classification data found in vital_stats")
    
            # ULTRA COMPACT HEADER - Reduced height by 50%
            header_style = ParagraphStyle(
                name='ClassificationHeader',
                parent=self.styles['Heading1'],
                fontSize=16,  # Reduced from 20
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=0,
                spaceBefore=0
            )
            
            subtitle_style = ParagraphStyle(
                name='ClassificationSubtitle',
                parent=self.styles['Normal'],
                fontSize=10,  # Reduced from 12
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica',
                spaceAfter=0
            )
    
            # Create compact header with reduced padding
            header_data = [
                [Paragraph("GST Audit Para Codification and Classification ", header_style)],
                [Paragraph("Comprehensive categorization by Nature of Non-Compliance using AI Agent", subtitle_style)],
                [Paragraph(f"📅 Period: {self.selected_period} | 🔍 Real-time Analysis Data", subtitle_style)]
            ]
            
            header_table = Table(header_data, colWidths=[7.5*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#2a5298")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),     # Reduced from 15
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Reduced from 15
                ('LEFTPADDING', (0, 0), (-1, -1), 10),   # Reduced from 20
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),  # Reduced from 20
            ]))
            
            self.story.append(header_table)
            
            # ULTRA COMPACT STATISTICS SECTION - Reduced height by 60%
            stats_header_style = ParagraphStyle(
                name='StatsHeader',
                parent=self.styles['Heading2'],
                fontSize=12,  # Reduced from 16
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            stats_data = [
                [Paragraph("Classification Overview", stats_header_style)],
                [self._create_compact_stats_grid(main_categories_count, sub_categories_count, total_observations)]
            ]
            
            stats_table = Table(stats_data, colWidths=[7.5*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#764ba2")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),     # Reduced from 15
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Reduced from 15
            ]))
            
            self.story.append(stats_table)
            self.story.append(Spacer(1, 0.1*inch))  # Reduced from 0.2*inch
    
            # ULTRA COMPACT CLASSIFICATION CATEGORIES GRID
            self._add_compact_classification_categories_grid(category_stats)
            
            # ULTRA COMPACT LEGEND SECTION
            self._add_compact_classification_legend()
            
        except Exception as e:
            print(f"Error adding comprehensive classification page: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_compact_stats_grid(self, main_categories, sub_categories, total_observations):
        """Create ultra-compact statistics grid with minimal spacing"""
        
        stat_style = ParagraphStyle(
            name='StatNumber',
            fontSize=16,  # Reduced from 20
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=1,  # Reduced from 3
            spaceBefore=0
        )
        
        label_style = ParagraphStyle(
            name='StatLabel',
            fontSize=8,   # Reduced from 10
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=0
        )
        
        # Create mini tables for each stat with minimal padding
        stats_data = [
            [
                Table([
                    [Paragraph(str(main_categories), stat_style)],
                    [Paragraph("Main Categories", label_style)]
                ], colWidths=[1.3*inch]),  # Reduced width
                
                Table([
                    [Paragraph(str(sub_categories), stat_style)],
                    [Paragraph("Sub-Categories", label_style)]
                ], colWidths=[1.3*inch]),  # Reduced width
                
                Table([
                    [Paragraph(str(total_observations), stat_style)],
                    [Paragraph("Audit Observations", label_style)]
                ], colWidths=[1.3*inch]),  # Reduced width
                
                Table([
                    [Paragraph("100%" if total_observations > 0 else "0%", stat_style)],
                    [Paragraph("Coverage", label_style)]
                ], colWidths=[1.3*inch])  # Reduced width
            ]
        ]
        
        grid_table = Table(stats_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        grid_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),     # Minimal padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # Minimal padding
        ]))
        
        return grid_table
    
    def _add_compact_classification_categories_grid(self, category_stats):
        """Add ultra-compact 3x3 grid with minimal spacing"""
        
        categories_info = [
            ("TP", "Tax Payment Defaults", "#e74c3c", [
                "Output Tax Short Payment", "Output Tax on Other Income", "Export & SEZ Related Issues"
            ]),
            ("RC", "Reverse Charge Mechanism", "#f39c12", [
                "Transportation & Logistics", "Professional & Legal Services", "Import of Services"
            ]),
            ("IT", "Input Tax Credit Violations", "#3498db", [
                "Blocked Credit Claims (Sec 17(5))", "Ineligible ITC Claims (Sec 16)", "Excess ITC Reconciliation"
            ]),
            ("IN", "Interest Liability Defaults", "#9b59b6", [
                "Tax Payment Related Interest", "ITC Related Interest (Sec 50)", "Time of Supply Interest"
            ]),
            ("RF", "Return Filing Non-Compliance", "#2ecc71", [
                "Late Filing Penalties", "Non-Filing Issues (ITC-04)", "Filing Quality Issues"
            ]),
            ("PD", "Procedural & Documentation", "#34495e", [
                "Return Reconciliation", "Documentation Deficiencies", "Cash Payment Violations"
            ]),
            ("CV", "Classification & Valuation", "#e67e22", [
                "Service Classification Errors", "Wrong Chapter Heading", "Incorrect Notification Claims"
            ]),
            ("SS", "Special Situations", "#1abc9c", [
                "Construction/Real Estate", "Job Work Related Compliance", "Inter-Company Transactions"
            ]),
            ("PG", "Penalty & General Compliance", "#c0392b", [
                "Statutory Penalties (Sec 123)", "Stock & Physical Verification", "General Non-Compliance"
            ])
        ]
        
        # Create ultra-compact 3x3 grid
        rows_data = []
        for i in range(0, 9, 3):
            row_cards = []
            for j in range(3):
                if i + j < len(categories_info):
                    card = self._create_ultra_compact_category_card(categories_info[i + j], category_stats)
                    row_cards.append(card)
                else:
                    row_cards.append("")
            rows_data.append(row_cards)
        
        # Create the grid table with minimal spacing
        grid_table = Table(rows_data, colWidths=[2.4*inch, 2.4*inch, 2.4*inch])  # Slightly reduced
        grid_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),    # Minimal padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),   # Minimal padding
            ('TOPPADDING', (0, 0), (-1, -1), 2),     # Minimal padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # Minimal padding
        ]))
        
        self.story.append(grid_table)
    
    def _create_ultra_compact_category_card(self, category_info, category_stats):
        """Create ultra-compact visual card with minimal spacing"""
        code, title, color, subcategories = category_info
        
        # Get real statistics for this category
        stats_text = self._get_category_stats_text(category_stats, code)
        
        # Ultra-compact card title style
        title_style = ParagraphStyle(
            name=f'CardTitle_{code}',
            fontSize=9,    # Reduced from 11
            textColor=colors.HexColor("#2c3e50"),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            spaceAfter=3,  # Reduced from 6
            spaceBefore=0
        )
        
        # Ultra-compact subcategory style
        sub_style = ParagraphStyle(
            name=f'CardSub_{code}',
            fontSize=7,    # Reduced from 8
            textColor=colors.HexColor("#5a6c7d"),
            alignment=TA_LEFT,
            fontName='Helvetica',
            spaceAfter=1,  # Reduced from 2
            leftIndent=8,  # Reduced from 10
            leading=8      # Tight line spacing
        )
        
        # Ultra-compact stats style
        stats_style = ParagraphStyle(
            name=f'CardStats_{code}',
            fontSize=7,    # Reduced from 8
            textColor=colors.HexColor("#34495e"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=0,
            spaceBefore=2  # Minimal space above
        )
        
        # Create ultra-compact card content
        card_content = [
            [Paragraph(f"<font color='{color}'>{code}</font> • {title}", title_style)]
        ]
        
        # Add only 2 subcategories for space saving
        for sub in subcategories[:2]:  # Reduced from 3 to 2
            card_content.append([Paragraph(f"▶ {sub}", sub_style)])
        
        # Add statistics
        card_content.append([Paragraph(stats_text, stats_style)])
        
        # Create the ultra-compact card table
        card_table = Table(card_content, colWidths=[2.2*inch])  # Slightly reduced
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e0e0e0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),    # Reduced from 8
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),   # Reduced from 8
            ('TOPPADDING', (0, 0), (-1, -1), 4),     # Reduced from 8
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),  # Reduced from 8
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Add colored left border
            ('LINEABOVE', (0, 0), (0, 0), 3, colors.HexColor(color)),  # Reduced from 4
        ]))
        
        return card_table
    
    def _get_category_stats_text(self, category_stats, category_code):
        """Get formatted statistics text for a category"""
        if category_stats.empty:
            return "📊 No data | 💰 Rs.0 L | 💎 Rs.0 L"
        
        category_data = category_stats[category_stats['major_code'] == category_code]
        if category_data.empty:
            return "📊 No data | 💰 Rs.0 L | 💎 Rs.0 L"
        
        paras = int(category_data['para_count'].iloc[0])
        detection = float(category_data['total_detection'].iloc[0])
        recovery = float(category_data['total_recovery'].iloc[0])
        
        return f"📊 {paras} paras | 💰 Rs.{detection:.1f}L | 💎 Rs.{recovery:.1f}L"
    
    def _add_compact_classification_legend(self):
        """Add ultra-compact single line legend"""
        legend_style = ParagraphStyle(
            name='LegendText',
            fontSize=11,
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=11
        )
        
        # Single line legend text
        legend_text = "Audit 1 Commissionerate Mumbai GST Zone codified Nature of compliances into total 58 Sub codes under 9 main classification codes for analysis using AI Agent"
        
        # Create simple legend table
        legend_data = [
            [Paragraph(legend_text, legend_style)]
        ]
        
        legend_table = Table(legend_data, colWidths=[7.5*inch])
        legend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#34495e")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        
        self.story.append(Spacer(1, 0.05*inch))  # Minimal spacer
        self.story.append(legend_table)
    # def add_classification_summary_table(self):
    #         """Add classification summary table"""  
    #         try:
    #             classification_summary = self.vital_stats.get('classification_summary', [])
                
    #             if classification_summary:
    #                 table_header_style = ParagraphStyle(
    #                     name='ClassificationTableHeader',
    #                     parent=self.styles['Heading3'],
    #                     fontSize=14,
    #                     textColor=colors.HexColor("#1134A6"),
    #                     alignment=TA_LEFT,
    #                     fontName='Helvetica-Bold',
    #                     spaceAfter=12,
    #                     spaceBefore=16
    #                 )
                    
    #                 self.story.append(Paragraph("📊 Non-Compliance Categories Summary", table_header_style))
                    
    #                 # Classification codes mapping
    #                 CLASSIFICATION_CODES_DESC = {
    #                     'TP': 'TAX PAYMENT DEFAULTS', 
    #                     'RC': 'REVERSE CHARGE MECHANISM',
    #                     'IT': 'INPUT TAX CREDIT VIOLATIONS', 
    #                     'IN': 'INTEREST LIABILITY DEFAULTS',
    #                     'RF': 'RETURN FILING NON-COMPLIANCE', 
    #                     'PD': 'PROCEDURAL & DOCUMENTATION',
    #                     'CV': 'CLASSIFICATION & VALUATION', 
    #                     'SS': 'SPECIAL SITUATIONS',
    #                     'PG': 'PENALTY & GENERAL COMPLIANCE'
    #                 }
                    
    #                 # Create classification table
    #                 classification_data = [['Code', 'Description', 'Paras', 'Detection (Rs. L)', 'Recovery (Rs. L)']]
                    
    #                 for item in classification_summary[:7]:  # Top 7 categories
    #                     code = item.get('major_code', 'Unknown')
    #                     description = CLASSIFICATION_CODES_DESC.get(code, 'Unknown Category')
    #                     para_count = item.get('Para_Count', 0)
    #                     detection = item.get('Total_Detection', 0)
    #                     recovery = item.get('Total_Recovery', 0)
                        
    #                     classification_data.append([
    #                         code,
    #                         description[:35] + '...' if len(description) > 35 else description,
    #                         str(para_count),
    #                         f'Rs.{detection:.2f} L',
    #                         f'Rs.{recovery:.2f} L'
    #                     ])
                    
    #                 classification_table = Table(classification_data, 
    #                                            colWidths=[0.6*inch, 2.4*inch, 0.8*inch, 1.3*inch, 1.3*inch])
                    
    #                 classification_table.setStyle(TableStyle([
    #                     ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
    #                     ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #                     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                     ('FONTSIZE', (0, 0), (-1, 0), 8),
    #                     ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    #                     ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #                     ('FONTSIZE', (0, 1), (-1, -1), 8),
    #                     ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
    #                     ('ALIGN', (0, 1), (1, -1), 'LEFT'),
    #                     ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #                     ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
    #                     ('TOPPADDING', (0, 0), (-1, -1), 6),
    #                     ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    #                     ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #                 ]))
                    
    #                 self.story.append(classification_table)
    #                 self.story.append(Spacer(1, 0.01 * inch))
                    
    #         except Exception as e:
    #             print(f"Error adding classification summary table: {e}")
    # def add_classification_summary_table(self):
    #     """Add classification summary table - FIXED VERSION with bounds checking"""  
    #     try:
    #         classification_summary = self.vital_stats.get('classification_summary', [])
            
    #         if classification_summary:
    #             table_header_style = ParagraphStyle(
    #                 name='ClassificationTableHeader',
    #                 parent=self.styles['Heading3'],
    #                 fontSize=14,
    #                 textColor=colors.HexColor("#1134A6"),
    #                 alignment=TA_LEFT,
    #                 fontName='Helvetica-Bold',
    #                 spaceAfter=12,
    #                 spaceBefore=16
    #             )
                
    #             self.story.append(Paragraph("📊 Non-Compliance Categories Summary", table_header_style))
                
    #             # Classification codes mapping
    #             CLASSIFICATION_CODES_DESC = {
    #                 'TP': 'TAX PAYMENT DEFAULTS', 
    #                 'RC': 'REVERSE CHARGE MECHANISM',
    #                 'IT': 'INPUT TAX CREDIT VIOLATIONS', 
    #                 'IN': 'INTEREST LIABILITY DEFAULTS',
    #                 'RF': 'RETURN FILING NON-COMPLIANCE', 
    #                 'PD': 'PROCEDURAL & DOCUMENTATION',
    #                 'CV': 'CLASSIFICATION & VALUATION', 
    #                 'SS': 'SPECIAL SITUATIONS',
    #                 'PG': 'PENALTY & GENERAL COMPLIANCE'
    #             }
                
    #             # Create classification table data
    #             classification_data = [['Code', 'Description', 'Paras', 'Detection (Rs. L)', 'Recovery (Rs. L)']]
                
    #             for item in classification_summary[:7]:  # Top 7 categories
    #                 code = item.get('major_code', 'Unknown')
    #                 description = CLASSIFICATION_CODES_DESC.get(code, 'Unknown Category')
    #                 para_count = item.get('Para_Count', 0)
    #                 detection = item.get('Total_Detection', 0)
    #                 recovery = item.get('Total_Recovery', 0)
                    
    #                 classification_data.append([
    #                     code,
    #                     description[:35] + '...' if len(description) > 35 else description,
    #                     str(para_count),
    #                     f'Rs.{detection:.2f} L',
    #                     f'Rs.{recovery:.2f} L'
    #                 ])
                
    #             # SAFE table creation - check if we have data
    #             total_rows = len(classification_data)
    #             print(f"Classification table will have {total_rows} rows")
                
    #             if total_rows > 1:  # More than just header
    #                 classification_table = Table(classification_data, 
    #                                            colWidths=[0.6*inch, 2.4*inch, 0.8*inch, 1.3*inch, 1.3*inch])
                    
    #                 # SAFE styling with bounds checking
    #                 classification_styles = [
    #                     ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
    #                     ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #                     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                     ('FONTSIZE', (0, 0), (-1, 0), 8),
    #                     ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    #                     ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #                     ('FONTSIZE', (0, 1), (-1, -1), 8),
    #                     ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
    #                     ('ALIGN', (0, 1), (1, -1), 'LEFT'),
    #                     ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #                     ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
    #                     ('TOPPADDING', (0, 0), (-1, -1), 6),
    #                     ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    #                     ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #                 ]
                    
    #                 # SAFE alternating row colors - only for rows that exist
    #                 # SAFE - proper bounds checking
    #                 if total_rows > 2:  # Only if we have data rows beyond header
    #                     for row_idx in range(2, min(total_rows - 1, 10)):  # Limit to reasonable range and exclude totals
    #                         if row_idx % 2 == 0:  # Every other row
    #                             performance_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8F8F8")))
    #                 # Apply styles safely
    #                 try:
    #                     classification_table.setStyle(TableStyle(classification_styles))
    #                     self.story.append(classification_table)
    #                     self.story.append(Spacer(1, 0.01 * inch))
    #                     print(f"✓ Successfully added classification table with {total_rows} rows")
                        
    #                 except Exception as style_error:
    #                     print(f"ERROR applying classification table styles: {style_error}")
    #                     # Fallback with minimal styling
    #                     classification_table.setStyle(TableStyle([
    #                         ('GRID', (0, 0), (-1, -1), 1, colors.black),
    #                         ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    #                         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #                     ]))
    #                     self.story.append(classification_table)
    #                     self.story.append(Spacer(1, 0.01 * inch))
    #             else:
    #                 print("No classification data to display")
    #         else:
    #             print("No classification summary data available")
                
    #     except Exception as e:
    #         print(f"Error adding classification summary table: {e}")
    #         import traceback
    #         traceback.print_exc()            
    def add_classification_summary_table(self):
        """Add classification summary table - FIXED IndexError Safe Version"""  
        try:
            classification_summary = self.vital_stats.get('classification_summary', [])
            
            if classification_summary:
                table_header_style = ParagraphStyle(
                    name='ClassificationTableHeader',
                    parent=self.styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor("#1134A6"),
                    alignment=TA_LEFT,
                    fontName='Helvetica-Bold',
                    spaceAfter=12,
                    spaceBefore=16
                )
                
                self.story.append(Paragraph("📊 Non-Compliance Categories Summary", table_header_style))
                
                # Classification codes mapping
                CLASSIFICATION_CODES_DESC = {
                    'TP': 'TAX PAYMENT DEFAULTS', 
                    'RC': 'REVERSE CHARGE MECHANISM',
                    'IT': 'INPUT TAX CREDIT VIOLATIONS', 
                    'IN': 'INTEREST LIABILITY DEFAULTS',
                    'RF': 'RETURN FILING NON-COMPLIANCE', 
                    'PD': 'PROCEDURAL & DOCUMENTATION',
                    'CV': 'CLASSIFICATION & VALUATION', 
                    'SS': 'SPECIAL SITUATIONS',
                    'PG': 'PENALTY & GENERAL COMPLIANCE'
                }
                
                # Create classification table data
                classification_data = [['Code', 'Description', 'Paras', 'Detection (Rs. L)', 'Recovery (Rs. L)']]
                
                for item in classification_summary[:7]:  # Top 7 categories
                    code = item.get('major_code', 'Unknown')
                    description = CLASSIFICATION_CODES_DESC.get(code, 'Unknown Category')
                    para_count = item.get('Para_Count', 0)
                    detection = item.get('Total_Detection', 0)
                    recovery = item.get('Total_Recovery', 0)
                    
                    classification_data.append([
                        code,
                        description[:35] + '...' if len(description) > 35 else description,
                        str(para_count),
                        f'Rs.{detection:.2f} L',
                        f'Rs.{recovery:.2f} L'
                    ])
                
                # SAFE table creation - check if we have data
                total_rows = len(classification_data)
                total_cols = len(classification_data[0]) if classification_data else 0
                print(f"Classification table will have {total_rows} rows x {total_cols} cols")
                
                if total_rows > 1 and total_cols == 5:  # More than header + correct columns
                    classification_table = Table(classification_data, 
                                               colWidths=[0.6*inch, 2.4*inch, 0.8*inch, 1.3*inch, 1.3*inch])
                    
                    # CORRECT VARIABLE NAME - classification_styles NOT performance_styles
                    classification_styles = [
                        # Header styling
                        ('BACKGROUND', (0, 0), (4, 0), colors.HexColor("#6F2E2E")),  # Exact range
                        ('TEXTCOLOR', (0, 0), (4, 0), colors.white),
                        ('FONTNAME', (0, 0), (4, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (4, 0), 8),
                        ('ALIGN', (0, 0), (4, 0), 'CENTER'),
                        
                        # Grid and borders
                        ('GRID', (0, 0), (4, total_rows-1), 1, colors.HexColor("#CCCCCC")),
                        ('LINEBELOW', (0, 0), (4, 0), 2, colors.HexColor("#6F2E2E")),
                        
                        # Padding
                        ('TOPPADDING', (0, 0), (4, total_rows-1), 6),
                        ('BOTTOMPADDING', (0, 0), (4, total_rows-1), 6),
                        ('VALIGN', (0, 0), (4, total_rows-1), 'MIDDLE'),
                    ]
                    
                    # SAFE data row styling - only if we have data rows
                    if total_rows > 1:
                        data_end = total_rows - 1
                        classification_styles.extend([
                            ('FONTNAME', (0, 1), (4, data_end), 'Helvetica'),
                            ('FONTSIZE', (0, 1), (4, data_end), 8),
                            ('ALIGN', (2, 1), (4, data_end), 'CENTER'),  # Numbers centered (cols 2-4)
                            ('ALIGN', (0, 1), (1, data_end), 'LEFT'),    # Code and description left (cols 0-1)
                        ])
                    
                    # SAFE alternating row colors - only for rows that exist
                    for row_idx in range(1, total_rows):  # Skip header
                        if row_idx % 2 == 0:  # Every other row
                            classification_styles.append(('BACKGROUND', (0, row_idx), (4, row_idx), colors.HexColor("#F8F9FA")))
                    
                    # Apply styles safely
                    try:
                        classification_table.setStyle(TableStyle(classification_styles))  # CORRECT VARIABLE NAME
                        self.story.append(classification_table)
                        self.story.append(Spacer(1, 0.2 * inch))
                        print(f"✓ Successfully added classification table with {total_rows} rows")
                        
                    except IndexError as style_error:
                        print(f"IndexError applying classification table styles: {style_error}")
                        # Fallback with minimal styling
                        classification_table.setStyle(TableStyle([
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ]))
                        self.story.append(classification_table)
                        self.story.append(Spacer(1, 0.2 * inch))
                        
                    except Exception as other_error:
                        print(f"Other error in classification table styling: {other_error}")
                        # Basic table without styling
                        basic_table = Table(classification_data, colWidths=[0.6*inch, 2.4*inch, 0.8*inch, 1.3*inch, 1.3*inch])
                        basic_table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                        self.story.append(basic_table)
                        self.story.append(Spacer(1, 0.2 * inch))
                else:
                    print("Invalid classification table dimensions - skipping")
            else:
                print("No classification summary data available")
                    
        except Exception as e:
            print(f"Error adding classification summary table: {e}")
            import traceback
            traceback.print_exc()
    def _add_detailed_charts_2x3_layout_simple(self, chart_type):
        """Simple approach: Add detailed charts in 2x3 layout using direct insertion"""
        try:
            # Classification codes in logical order (first 6 for first page, next 6 for second page)
            classification_codes = ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']
            
            # Filter available charts for this type
            available_charts = []
            for code in classification_codes:
                chart_id = f"detailed_{chart_type}_{code}"
                if chart_id in self.chart_registry:
                    available_charts.append(chart_id)
            
            print(f"Found {len(available_charts)} available {chart_type} charts")
            
            if not available_charts:
                print(f"No {chart_type} charts available")
                return
            
            # Process charts in groups of 6 (2x3 layout per page)
            charts_per_page = 6
            
            for page_start in range(0, len(available_charts), charts_per_page):
                page_charts = available_charts[page_start:page_start + charts_per_page]
                
                # Add charts in pairs (2 per row)
                for i in range(0, len(page_charts), 2):
                    # Create a table for this row (2 charts side by side)
                    row_charts = []
                    
                    # First chart in the row
                    if i < len(page_charts):
                        chart1_content = self._create_compact_chart_for_row(page_charts[i])
                        row_charts.append(chart1_content)
                    
                    # Second chart in the row (if available)
                    if i + 1 < len(page_charts):
                        chart2_content = self._create_compact_chart_for_row(page_charts[i + 1])
                        row_charts.append(chart2_content)
                    else:
                        # Empty cell if odd number of charts
                        row_charts.append("")
                    
                    # Create table for this row
                    if len(row_charts) >= 2:
                        row_table = Table([row_charts], colWidths=[3.75*inch, 3.75*inch])
                        row_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 2),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ]))
                        
                        self.story.append(row_table)
                        self.story.append(Spacer(1, 0.1 * inch))
                    else:
                        # Single chart - center it
                        single_table = Table([row_charts], colWidths=[7.5*inch])
                        single_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ]))
                        self.story.append(single_table)
                        self.story.append(Spacer(1, 0.1 * inch))
                
                # Add page break if there are more charts
                if page_start + charts_per_page < len(available_charts):
                    self.story.append(PageBreak())
                    
        except Exception as e:
            print(f"Error adding {chart_type} charts in simple 2x3 layout: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_compact_chart_for_row(self, chart_id):
        """Create a compact chart with title for row layout"""
        try:
            if chart_id not in self.chart_registry:
                return ""
                
            chart_info = self.chart_registry[chart_id]
            chart_data = chart_info['metadata']
            img_bytes = chart_info['image']
            
            if img_bytes is None:
                return ""
            
            # Create title
            title_style = ParagraphStyle(
                name='CompactChartTitle',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=3,
                spaceBefore=0
            )
            
            chart_title = Paragraph(chart_data.get('title', ''), title_style)
            
            # Create drawing
            drawing, error = self._create_safe_svg_drawing(img_bytes)
            
            if error or drawing is None:
                print(f"Failed to create compact drawing for '{chart_id}': {error}")
                return chart_title  # Return at least the title
            
            # Compact size for side-by-side layout
            target_width = 4 * inch
            target_height = 2.5 * inch
            
            # Calculate scale factors
            original_width = getattr(drawing, 'width', 400)
            original_height = getattr(drawing, 'height', 400)
            
            if original_width <= 0 or original_height <= 0:
                return chart_title
                
            scale_x = target_width / original_width
            scale_y = target_height / original_height
            
            # Create properly scaled drawing
            from reportlab.graphics.shapes import Drawing, Group
            
            scaled_drawing = Drawing(target_width, target_height)
            content_group = Group()
            content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
            
            # Add original contents safely
            if hasattr(drawing, 'contents'):
                for item in drawing.contents:
                    content_group.add(item)
            
            scaled_drawing.add(content_group)
            scaled_drawing.hAlign = 'CENTER'
            
            # Create container with title and chart
            #container_data = [[chart_title], [scaled_drawing]]
            container_data = [[scaled_drawing]]
            container_table = Table(container_data, colWidths=[3.5*inch])
            container_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            
            return container_table
            
        except Exception as e:
            print(f"Error creating compact chart for row: {e}")
            return ""
    
    # UPDATED VERSION - Replace the _add_detailed_charts_2x3_layout method with the simple version
    def _add_detailed_charts_2x3_layout(self, chart_type):
        """Add detailed charts in 2 charts per row, 3 rows per page (6 charts per page) - SIMPLE VERSION"""
        return self._add_detailed_charts_2x3_layout_simple(chart_type)
        
    def add_nature_of_non_compliance_analysis(self):
            
            """Add Section IV - Nature of Non Compliance Analysis"""
            try:
              
                self.story.append(PageBreak())
                             
                # Switch back to normal template after this section
                
                self.add_section_highlight_bar("IV. Nature of Non Compliance Analysis ", text_color="#0E4C92")
                
                # Description
                desc_style = ParagraphStyle(
                    name='ComplianceDesc',
                    parent=self.styles['Normal'],
                    fontSize=11,
                    textColor=colors.HexColor("#2C2C2C"),
                    alignment=TA_JUSTIFY,
                    fontName='Helvetica',
                    leftIndent=0.25*inch,
                    rightIndent=0.25*inch,
                    leading=14,
                    spaceAfter=16
                )
                
                # description_text = """
                # This section analyzes the nature of non-compliance using the Audit Para Categorisation Coding System of Audit-1 Commissionerate. 
                # The analysis categorizes violations into major areas like Tax Payment Defaults, ITC Violations, Return Filing issues, and Procedural Non-compliance.
                # """
                
                # self.story.append(Paragraph(description_text, desc_style))
                # ADD PAGE BREAK AND COMPREHENSIVE CLASSIFICATION PAGE
                
                self.add_comprehensive_classification_page()
              
                # Add classification summary table (only if you want it later)
                if self.vital_stats.get('compliance_analysis_available', False):
                    self.story.append(Spacer(1, 0.05 * inch))
                    self.add_classification_summary_table()
                # Chart heading style
                chart_header_style = ParagraphStyle(
                    name='ComplianceChartHeader',
                    parent=self.styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor("#1134A6"),
                    alignment=TA_LEFT,
                    fontName='Helvetica-Bold',
                    spaceAfter=6,
                    spaceBefore=6
                )
                
                # First Chart: Number of Paras by Classification
                self.story.append(Paragraph("🎯 Number of Audit Paras by Categorisation", chart_header_style))
                self.insert_chart_by_id("classification_para_count", 
                                       size="medium", 
                                       add_title=False, 
                                       add_description=False)
                self.story.append(Spacer(1, 0.01 * inch))
                
                # Second Chart: Detection Amount by Classification
                self.story.append(Paragraph("🎯 Detection Amount by Categorisation", chart_header_style))
                self.insert_chart_by_id("classification_detection", 
                                       size="medium", 
                                       add_title=False, 
                                       add_description=False)
                self.story.append(Spacer(1, 0.01 * inch))
                
                # Third Chart: Recovery Amount by Classification
                self.story.append(Paragraph("🎯 Recovery Amount by Categorisation", chart_header_style))
                self.insert_chart_by_id("classification_recovery", 
                                       size="medium", 
                                       add_title=False, 
                                       add_description=False)
                self.story.append(Spacer(1, 0.01 * inch))
                
                # PART B: DETAILED SUBCATEGORY ANALYSIS WITH 2x3 LAYOUT
                # Add subsection header for detailed analysis
                # detailed_header_style = ParagraphStyle(
                #     name='DetailedComplianceHeader',
                #     parent=self.styles['Heading3'],
                #     fontSize=13,
                #     textColor=colors.HexColor("#8B4A9C"),
                #     alignment=TA_LEFT,
                #     fontName='Helvetica-Bold',
                #     spaceAfter=8,
                #     spaceBefore=12
                # )
                
                # self.story.append(Paragraph("🔍 Detailed Subcategory Analysis", detailed_header_style))
                
                # Add description for detailed section
                detailed_desc_style = ParagraphStyle(
                    name='DetailedDesc',
                    parent=self.styles['Normal'],
                    fontSize=10,
                    textColor=colors.HexColor("#2C2C2C"),
                    alignment=TA_JUSTIFY,
                    fontName='Helvetica',
                    leftIndent=0.25*inch,
                    rightIndent=0.25*inch,
                    leading=12,
                    spaceAfter=12
                )
                
                detailed_description = """
                The following charts provide detailed breakdown of each major compliance category into codified specific subcategories using AI Agent, 
                showing exact types of non-compliance .
                """
                
                
                
                # PART B1: DETAILED DETECTION ANALYSIS (2x3 Layout)
                
                self.story.append(Paragraph("💰 Detection Analysis by Detailed Subcategorization", chart_header_style))
                self.story.append(Paragraph(detailed_description, detailed_desc_style))
                # Add detailed detection charts in 2x3 layout
                self._add_detailed_charts_2x3_layout("detection")
                
                #TEMPORARILY NOT SHOWING RECOVERY GRAPHS # PART B2: DETAILED RECOVERY ANALYSIS (2x3 Layout)
                # #self.story.append(PageBreak())  # Start recovery analysis on new page
                # self.story.append(Paragraph("💎 Recovery Analysis by Detailed Subcategorization", chart_header_style))
                
                # # Add detailed recovery charts in 2x3 layout
                # self._add_detailed_charts_2x3_layout("recovery")
                
                print("Added detailed classification analysis with 2x3 layout")
                    
            except Exception as e:
                print(f"Error adding nature of non compliance analysis: {e}")
    def _add_risk_charts_2x2_layout(self):
            """Add risk parameter charts in 2x2 layout"""
            try:
                # Define the 4 risk charts in order
                risk_chart_configs = [
                    ('risk_para_distribution', "Risk Flags by Audit Paras"),
                    ('risk_detection_analysis', "Detection by Risk Flag"), 
                    ('risk_recovery_analysis', "Recovery by Risk Flag"),
                    ('risk_distribution', "Recovery Percentage by Risk")
                ]
                
                # Check which charts are available
                available_charts = []
                for chart_id, title in risk_chart_configs:
                    if chart_id in self.chart_registry:
                        available_charts.append((chart_id, title))
                        print(f"Risk chart available: {chart_id}")
                    else:
                        print(f"Risk chart NOT available: {chart_id}")
                
                if len(available_charts) < 4:
                    print(f"Warning: Only {len(available_charts)} risk charts available out of 4")
                
                # Create 2x2 layout using tables
                # Row 1: First two charts
                if len(available_charts) >= 2:
                    row1_charts = []
                    
                    # First chart
                    chart1_content = self._create_compact_chart_for_risk(available_charts[0][0], available_charts[0][1])
                    row1_charts.append(chart1_content)
                    
                    # Second chart
                    chart2_content = self._create_compact_chart_for_risk(available_charts[1][0], available_charts[1][1])
                    row1_charts.append(chart2_content)
                    
                    # Create table for row 1
                    row1_table = Table([row1_charts], colWidths=[3.75*inch, 3.75*inch])
                    row1_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ]))
                    
                    self.story.append(row1_table)
                    self.story.append(Spacer(1, 0.15 * inch))
                
                # Row 2: Next two charts
                if len(available_charts) >= 4:
                    row2_charts = []
                    
                    # Third chart
                    chart3_content = self._create_compact_chart_for_risk(available_charts[2][0], available_charts[2][1])
                    row2_charts.append(chart3_content)
                    
                    # Fourth chart
                    chart4_content = self._create_compact_chart_for_risk(available_charts[3][0], available_charts[3][1])
                    row2_charts.append(chart4_content)
                    
                    # Create table for row 2
                    row2_table = Table([row2_charts], colWidths=[3.75*inch, 3.75*inch])
                    row2_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ]))
                    
                    self.story.append(row2_table)
                    self.story.append(Spacer(1, 0.2 * inch))
                elif len(available_charts) == 3:
                    # Handle case where only 3 charts available - put third chart centered
                    chart3_content = self._create_compact_chart_for_risk(available_charts[2][0], available_charts[2][1])
                    row2_table = Table([[chart3_content]], colWidths=[7.5*inch])
                    row2_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    self.story.append(row2_table)
                    self.story.append(Spacer(1, 0.2 * inch))
                
                print(f"Successfully added {len(available_charts)} risk charts in 2x2 layout")
                
            except Exception as e:
                print(f"Error adding risk charts in 2x2 layout: {e}")
                import traceback
                traceback.print_exc()
        
    def _create_compact_chart_for_risk(self, chart_id, title):
            """Create a compact chart for risk analysis layout"""
            try:
                if chart_id not in self.chart_registry:
                    print(f"Chart ID '{chart_id}' not found in registry")
                    return ""
                    
                chart_info = self.chart_registry[chart_id]
                img_bytes = chart_info['image']
                
                if img_bytes is None:
                    print(f"No image data for chart '{chart_id}'")
                    return ""
                
                # # Create title
                # title_style = ParagraphStyle(
                #     name='RiskChartTitle',
                #     parent=self.styles['Normal'],
                #     fontSize=12,
                #     textColor=colors.HexColor("#1F3A4D"),
                #     alignment=TA_CENTER,
                #     fontName='Helvetica-Bold',
                #     spaceAfter=5,
                #     spaceBefore=0
                # )
                
                # chart_title = Paragraph(title, title_style)
                
                # Create drawing
                drawing, error = self._create_safe_svg_drawing(img_bytes)
                
                if error or drawing is None:
                    print(f"Failed to create drawing for '{chart_id}': {error}")
                    return chart_title  # Return at least the title
                
                # Compact size for 2x2 layout
                target_width = 3.5 * inch
                target_height = 2.8 * inch
                
                # Calculate scale factors
                original_width = getattr(drawing, 'width', 400)
                original_height = getattr(drawing, 'height', 400)
                
                if original_width <= 0 or original_height <= 0:
                    print(f"Invalid dimensions for '{chart_id}': {original_width}x{original_height}")
                    return chart_title
                    
                scale_x = target_width / original_width
                scale_y = target_height / original_height
                
                # Create properly scaled drawing
                from reportlab.graphics.shapes import Drawing, Group
                
                scaled_drawing = Drawing(target_width, target_height)
                content_group = Group()
                content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
                
                # Add original contents safely
                if hasattr(drawing, 'contents'):
                    for item in drawing.contents:
                        content_group.add(item)
                
                scaled_drawing.add(content_group)
                scaled_drawing.hAlign = 'CENTER'
                
                # Create container with title and chart
                #container_data = [[chart_title], [scaled_drawing]]
                container_data = [[scaled_drawing]]
                container_table = Table(container_data, colWidths=[3.5*inch])
                container_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ]))
                
                print(f"Successfully created compact chart for '{chart_id}'")
                return container_table
                
            except Exception as e:
                print(f"Error creating compact chart for '{chart_id}': {e}")
                import traceback
                traceback.print_exc()
                return ""

   
 
           

    # def add_risk_parameter_analysis(self):
    #     """Add Risk Parameter Analysis section"""
    #     try:
    #         # Section header with description
    #         risk_header_style = ParagraphStyle(
    #             name='RiskHeader',
    #             parent=self.styles['Heading2'],
    #             fontSize=18,
    #             textColor=colors.HexColor("#1134A6"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=12,
    #             spaceBefore=20
    #         )
    #         self.add_section_highlight_bar("V. Risk Parameter Analysis", text_color="#0E4C92")
    #         #self.story.append(Paragraph("Risk Parameter Analysis", risk_header_style))
            
    #         # Add description
    #         desc_style = ParagraphStyle(
    #             name='RiskDesc',
    #             parent=self.styles['Normal'],
    #             fontSize=11,
    #             textColor=colors.HexColor("#2C2C2C"),
    #             alignment=TA_JUSTIFY,
    #             fontName='Helvetica',
    #             leftIndent=0.25*inch,
    #             rightIndent=0.25*inch,
    #             leading=14,
    #             spaceAfter=16
    #         )
            
    #         description_text = """
    #         This section analyzes audit performance based on pre-defined GST risk parameters of DGARM . 
    #         It helps identify which risks are most frequently associated with audit observations and which ones 
    #         contribute most to revenue detection and recovery. The charts are sorted to highlight the most significant parameters.
    #         """
            
    #         self.story.append(Paragraph(description_text, desc_style))
            
    #         # Get risk analysis data from vital_stats
    #         risk_summary_data = self.vital_stats.get('risk_summary', [])
    #         gstins_with_risk = self.vital_stats.get('gstins_with_risk_data', 4)
    #         paras_linked_to_risks = self.vital_stats.get('paras_linked_to_risks', 10)
            
    #         # Add metrics
    #         col1, col2 = st.columns(2) if 'st' in globals() else (None, None)
            
    #         # Create metrics table
    #         risk_metrics_data = [
    #             ['GSTINs with Risk Data', 'Paras Linked to Risks'],
    #             [f'{gstins_with_risk}', f'{paras_linked_to_risks}']
    #         ]
            
    #         risk_metrics_table = Table(risk_metrics_data, colWidths=[3.5*inch, 3.5*inch])
    #         risk_metrics_table.setStyle(TableStyle([
    #             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 0), (-1, 0), 12),
    #             ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 1), (-1, 1), 18),
    #             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8F4F8")),
    #             ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F8FF")),
    #             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #             ('TOPPADDING', (0, 0), (-1, -1), 8),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    #         ]))
            
    #         self.story.append(risk_metrics_table)
    #         self.story.append(Spacer(1, 0.2 * inch))
            
    #         # Risk Parameter Summary Table Header
    #         risk_table_header_style = ParagraphStyle(
    #             name='RiskTableHeader',
    #             parent=self.styles['Heading3'],
    #             fontSize=14,
    #             textColor=colors.HexColor("#1F3A4D"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=12,
    #             spaceBefore=16
    #         )
    #           # Risk Parameter Charts in 2x2 Layout
    #         chart_header_style = ParagraphStyle(
    #             name='RiskChartHeader',
    #             parent=self.styles['Heading3'],
    #             fontSize=14,
    #             textColor=colors.HexColor("#1134A6"),
    #             alignment=TA_CENTER,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=8,
    #             spaceBefore=12
    #         )
            
    #         self.story.append(Paragraph("📊 Risk Parameter Analysis Charts", chart_header_style))
    #         self.story.append(Spacer(1, 0.1 * inch))
            
    #         # Create 2x2 layout for risk charts
    #         self._add_risk_charts_2x2_layout()
            
      
    #         self.story.append(Paragraph("📊 Risk Parameter Summary", risk_table_header_style))
            
    #         if risk_summary_data:
    #             # Build table from actual data
    #             risk_data = [['RISK FLAG', 'RISK DESCRIPTION', 'NO.OF PARAS', 'TOTAL DETECTION ', 'TOTAL RECOVERY', 'RECOVERY %']]
                
    #             for risk_item in risk_summary_data:
    #                 risk_flag = risk_item.get('risk_flag', 'Unknown')
    #                 description = risk_item.get('description', 'Unknown Risk Code')[:60] + '...' if len(risk_item.get('description', '')) > 60 else risk_item.get('description', 'Unknown Risk Code')
    #                 paras = int(risk_item.get('Para_Count', 0))
    #                 detection = float(risk_item.get('Total_Detection', 0))
    #                 recovery = float(risk_item.get('Total_Recovery', 0))
    #                 recovery_pct = float(risk_item.get('Percentage_Recovery', 0))
                    
    #                 risk_data.append([
    #                     risk_flag,
    #                     description,
    #                     str(paras),
    #                     f'Rs.{detection:.2f} L',
    #                     f'Rs.{recovery:.2f} L',
    #                     f'{recovery_pct:.1f}%'
    #                 ])
    #         else:
    #             # Fallback data based on the image you shared
    #             risk_data = [
    #                 ['RISK FLAG', 'RISK DESCRIPTION', 'NO. OF PARAS', 'TOTAL DETECTION (Rs. L)', 'TOTAL RECOVERY (Rs. L)', 'RECOVERY %'],
    #                 ['P07', 'High ratio of tax paid through ITC to total tax payable', 'NA', 'NA', 'NA', 'NA'],
    #                 ['P10', 'High ratio of non-GST supplies to total turnover', 'NA', 'NA', 'NA', 'NA']
                  
    #             ]
            
    #         # Create the risk table with dynamic column widths
    #         risk_col_widths = [0.8*inch, 3.2*inch, 0.8*inch, 1.3*inch, 1.3*inch, 0.9*inch]
    #         risk_table = Table(risk_data, colWidths=risk_col_widths)
            
    #         # Apply colorful styling matching the image
    #         risk_table.setStyle(TableStyle([
    #             # Header styling with gradient colors
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),  # Purple header
    #             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 0), (-1, 0), 9),
    #             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
    #             # Data rows
    #             ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #             ('FONTSIZE', (0, 1), (-1, -1), 8),
    #             ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Numbers centered
    #             ('ALIGN', (0, 1), (1, -1), 'LEFT'),     # Flag and description left-aligned
                
    #             # Row background colors - creating the colorful effect from the image
    #             ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#E8F5E8")),    # Light green
    #             ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#FFF3CD")),    # Light yellow  
    #             ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#E2E3E5")),    # Light gray
    #             ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor("#FFF3CD")),    # Light yellow
    #             ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#D4EDDA")),    # Light green
    #             ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor("#D4EDDA")),    # Light green
                
    #             # Grid and borders
    #             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    #             ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                
    #             # Padding
    #             ('TOPPADDING', (0, 0), (-1, -1), 6),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 6),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
    #             # Vertical alignment
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #         ]))
            
    #         self.story.append(risk_table)
    #         self.story.append(Spacer(1, 0.3 * inch))
                
    #     except Exception as e:
    #           print(f"Error adding risk parameter analysis: {e}")#0, 0), (-1, -1), 'MIDDLE'),
        
    def add_risk_parameter_analysis(self):
        """Add Risk Parameter Analysis section"""
        try:
            # Section header with description
            risk_header_style = ParagraphStyle(
                name='RiskHeader',
                parent=self.styles['Heading2'],
                fontSize=18,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=20
            )
            self.add_section_highlight_bar("V. Risk Parameter Analysis", text_color="#0E4C92")
            
            # Add description
            desc_style = ParagraphStyle(
                name='RiskDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section analyzes audit performance based on pre-defined GST risk parameters of DGARM . 
            It helps identify which risks are most frequently associated with audit observations and which ones 
            contribute most to revenue detection and recovery. The charts are sorted to highlight the most significant parameters.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Get risk analysis data from vital_stats
            risk_summary_data = self.vital_stats.get('risk_summary', [])
            gstins_with_risk = self.vital_stats.get('gstins_with_risk_data', 4)
            paras_linked_to_risks = self.vital_stats.get('paras_linked_to_risks', 10)
            
            # Create metrics table
            risk_metrics_data = [
                ['GSTINs with Risk Data', 'Paras Linked to Risks'],
                [f'{gstins_with_risk}', f'{paras_linked_to_risks}']
            ]
            
            risk_metrics_table = Table(risk_metrics_data, colWidths=[3.5*inch, 3.5*inch])
            risk_metrics_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 18),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8F4F8")),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F8FF")),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            self.story.append(risk_metrics_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Risk Parameter Summary Table Header
            risk_table_header_style = ParagraphStyle(
                name='RiskTableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            # Risk Parameter Charts in 2x2 Layout
            chart_header_style = ParagraphStyle(
                name='RiskChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            self.story.append(Paragraph("📊 Risk Parameter Analysis Charts", chart_header_style))
            self.story.append(Spacer(1, 0.1 * inch))
            self._add_risk_charts_2x2_layout()
            
            self.story.append(Paragraph("📊 Risk Parameter Summary", risk_table_header_style))
            
            # Build risk table data
            risk_data = [['RISK FLAG', 'RISK DESCRIPTION', 'NO.OF PARAS', 'TOTAL DETECTION ', 'TOTAL RECOVERY', 'RECOVERY %']]
            
            if risk_summary_data:
                for risk_item in risk_summary_data:
                    risk_flag = risk_item.get('risk_flag', 'Unknown')
                    description = risk_item.get('description', 'Unknown Risk Code')
                    description = (description[:60] + '...') if len(description) > 60 else description
                    paras = int(risk_item.get('Para_Count', 0))
                    detection = float(risk_item.get('Total_Detection', 0))
                    recovery = float(risk_item.get('Total_Recovery', 0))
                    recovery_pct = float(risk_item.get('Percentage_Recovery', 0))
                    
                    risk_data.append([
                        risk_flag,
                        description,
                        str(paras),
                        f'Rs.{detection:.2f} L',
                        f'Rs.{recovery:.2f} L',
                        f'{recovery_pct:.1f}%'
                    ])
            else:
                # Fallback data
                risk_data.append([
                    'P07',
                    'High ratio of tax paid through ITC to total tax payable',
                    'NA', 'NA', 'NA', 'NA'
                ])
                risk_data.append([
                    'P10',
                    'High ratio of non-GST supplies to total turnover',
                    'NA', 'NA', 'NA', 'NA'
                ])
            
            # Define column widths
            risk_col_widths = [0.8*inch, 3.2*inch, 0.8*inch, 1.3*inch, 1.3*inch, 0.9*inch]
            risk_table = Table(risk_data, colWidths=risk_col_widths)
            
            # Build dynamic TableStyle to avoid IndexError
            num_rows = len(risk_data)
            style_commands = [
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),  # Purple
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data row fonts
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Numeric columns
                ('ALIGN', (0, 1), (1, -1), 'LEFT'),     # Risk flag & description
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # Alternating or color-coded row backgrounds (safe for any number of rows)
            # Use a color cycle to avoid hardcoded indices
            row_colors = [
                "#E8F5E8", "#FFF3CD", "#E2E3E5", 
                "#FFF3CD", "#D4EDDA", "#D4EDDA"
            ]
            
            for i in range(1, num_rows):  # Skip header (row 0)
                color = row_colors[i % len(row_colors)]
                style_commands.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(color)))
            
            # Apply the dynamic style
            risk_table.setStyle(TableStyle(style_commands))
            
            self.story.append(risk_table)
            self.story.append(Spacer(1, 0.3 * inch))
            
        except Exception as e:
            print(f"Error adding risk parameter analysis: {e}")
            import traceback
            traceback.print_exc()
    def add_top_performance_analysis(self):
        """Add Section V - Top Audit Group and Circle Performance"""
        try:
            # Section header
            self.add_section_highlight_bar("VI. Top Audit Group and Circle Performance", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='PerformanceDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section highlights the top-performing audit groups and circles based on detection and recovery amounts. 
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Chart heading style
            chart_header_style = ParagraphStyle(
                name='PerformanceChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            # Group Performance Charts
            self.story.append(Paragraph("🏆 Top 10 Audit Groups by Detection Amount", chart_header_style))
            self.insert_chart_by_id("group_detection_performance", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.15 * inch))
            
            self.story.append(Paragraph("🏆 Top 10 Audit Groups by Recovery Amount", chart_header_style))
            self.insert_chart_by_id("group_recovery_performance", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.15 * inch))
            
            # Circle Performance Charts
            self.story.append(Paragraph("🎯 Circle-wise Detection Performance", chart_header_style))
            self.insert_chart_by_id("circle_detection_performance", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.15 * inch))
            
            self.story.append(Paragraph("🎯 Circle-wise Recovery Performance", chart_header_style))
            self.insert_chart_by_id("recovery_trends", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
                       
        except Exception as e:
            print(f"Error adding top performance analysis: {e}")
    
    
    
    def add_top_taxpayers_analysis(self):
        """Add Section VI - Top Taxpayers of Detection and Recovery"""
        try:
            # Section header
            self.add_section_highlight_bar("VI. Top Taxpayers of Detection and Recovery", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='TaxpayerDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides hierarchical analysis of taxpayers with highest detection and recovery amounts. 
            The treemap visualizations show proportional representation of taxpayer categories and individual entities, 
            helping identify key contributors to audit performance and recovery potential.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            
            
            # Add top taxpayers summary table if data is available
            if self.vital_stats.get('top_taxpayers_data'):
                self.add_top_taxpayers_summary_table()
                
        except Exception as e:
            print(f"Error adding top taxpayers analysis: {e}")
            
    # STEP 1: IMMEDIATE FIX - Replace add_top_taxpayers_summary_table method
    def add_top_taxpayers_summary_table(self):
        """FIXED VERSION - Add top taxpayers summary table with bulletproof error handling"""
        try:
            print("=== STARTING TOP TAXPAYERS SUMMARY TABLE ===")
            
            # Get the data
            top_taxpayers_data = self.vital_stats.get('top_taxpayers_data', {})
            
            if not top_taxpayers_data:
                self._add_info_message("No top taxpayers data available for this period.")
                return
            # Chart heading style
            chart_header_style = ParagraphStyle(
                name='TaxpayerChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
          
            # Table header style
            table_header_style = ParagraphStyle(
                name='TopTaxpayersTableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
           
            # Detection Treemap
            self.story.append(Paragraph("🌳 Top Taxpayers by Detection Amount (Treemap)", chart_header_style))
            self.insert_chart_by_id("detection_treemap", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Process Top Detection
            self._process_top_taxpayers_table(
                data_key='top_detection',
                title="🏆 Top 5 Taxpayers by Detection Amount",
                header_style=table_header_style,
                table_color="#6F2E2E"
            )
            #Recovery Treemap
            self.story.append(Paragraph("🌳 Top Taxpayers by Recovery Amount (Treemap)", chart_header_style))
            self.insert_chart_by_id("recovery_treemap", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
            
            # Process Top Recovery
            self._process_top_taxpayers_table(
                data_key='top_recovery', 
                title="💎 Top 5 Taxpayers by Recovery Amount",
                header_style=table_header_style,
                table_color="#2E8B57"
            )
            
            print("=== TOP TAXPAYERS SUMMARY TABLE COMPLETED ===")
            
        except Exception as e:
            print(f"ERROR in add_top_taxpayers_summary_table: {e}")
            self._add_error_message("Top Taxpayers Summary", str(e))
    
    def _process_top_taxpayers_table(self, data_key, title, header_style, table_color):
        """Process a single top taxpayers table safely"""
        try:
            top_taxpayers_data = self.vital_stats.get('top_taxpayers_data', {})
            raw_data = top_taxpayers_data.get(data_key, [])
            
            print(f"Processing {data_key}: type={type(raw_data)}, length={len(raw_data) if hasattr(raw_data, '__len__') else 'no length'}")
            
            # Convert DataFrame to list if necessary
            if hasattr(raw_data, 'to_dict'):
                print(f"Converting {data_key} DataFrame to list...")
                data_list = raw_data.to_dict('records')
            elif isinstance(raw_data, list):
                data_list = raw_data
            else:
                print(f"WARNING: {data_key} is neither DataFrame nor list: {type(raw_data)}")
                data_list = []
            
            if not data_list:
                print(f"No data available for {data_key}")
                return
            
            print(f"Processing {len(data_list)} records for {data_key}")
            
            # Add title
            self.story.append(Paragraph(title, header_style))
            
            # Create table data
            table_data = [['Trade Name', 'Category', 'Detection (Rs.L)', 'Recovery (Rs.L)', 'Recovery %']]
            
            # Process up to 5 records safely
            for i in range(min(5, len(data_list))):
                try:
                    record = data_list[i]
                    if not isinstance(record, dict):
                        print(f"Skipping non-dict record {i}: {type(record)}")
                        continue
                    
                    # Extract data with multiple fallback key names
                    trade_name = self._safe_get_value(record, ['trade_name', 'Trade Name'], f'Taxpayer {i+1}')
                    category = self._safe_get_value(record, ['category', 'Category'], 'Unknown')
                    detection = self._safe_get_float(record, ['total_detection', 'Detection in Lakhs', 'detection'], 0)
                    recovery = self._safe_get_float(record, ['total_recovery', 'Recovery in Lakhs', 'recovery'], 0)
                    recovery_pct = self._safe_get_float(record, ['recovery_percentage', 'Recovery %'], 0)
                    
                    # Calculate recovery percentage if not present
                    if recovery_pct == 0 and detection > 0:
                        recovery_pct = (recovery / detection) * 100
                    
                    # Truncate long trade names
                    if len(str(trade_name)) > 40:
                        trade_name = str(trade_name)[:37] + '...'
                    
                    table_data.append([
                        str(trade_name),
                        str(category),
                        f'Rs.{detection:.2f} L',
                        f'Rs.{recovery:.2f} L',
                        f'{recovery_pct:.1f}%'
                    ])
                    
                except Exception as record_error:
                    print(f"Error processing record {i}: {record_error}")
                    table_data.append([f'Error in record {i+1}', 'N/A', 'Rs.0.00 L', 'Rs.0.00 L', '0.0%'])
            
            # Create and style table
            if len(table_data) > 1:  # More than just header
                table = Table(table_data, colWidths=[2.5*inch, 1*inch, 1.3*inch, 1.3*inch, 1*inch])
                # Replace the table styling section with:
                # table.setStyle(TableStyle([
                #     ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(table_color)),
                #     ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                #     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                #     ('FONTSIZE', (0, 0), (-1, 0), 8),
                #     ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                #     ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                #     ('FONTSIZE', (0, 1), (-1, -1), 8),
                #     ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                #     ('ALIGN', (0, 1), (1, -1), 'LEFT'),
                #     ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                #     ('TOPPADDING', (0, 0), (-1, -1), 6),
                #     ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                #     ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # ]))
                
                # # Add alternating row colors ONLY for rows that exist
                # num_data_rows = len(table_data) - 1  # Subtract header row
                # for row_idx in range(1, num_data_rows + 1, 2):  # Every other row starting from 1
                #     if row_idx < len(table_data):  # Safety check
                #         table.setStyle(TableStyle([
                #             ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8F8F8")),
                #         ]))
                # SAFE alternating row colors - only add for rows that exist
                # Create base styles first
                base_styles = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(table_color)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                    ('ALIGN', (0, 1), (1, -1), 'LEFT'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
                total_rows = len(table_data)
                # SAFE - proper bounds checking
                if total_rows > 2:  # Only if we have data rows beyond header
                    for row_idx in range(2, min(total_rows - 1, 10)):  # Limit to reasonable range and exclude totals
                        if row_idx % 2 == 0:  # Every other row
                            performance_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8F8F8")))
                
                # Apply all styles at once
                table.setStyle(TableStyle(base_styles))
                self.story.append(table)
                self.story.append(Spacer(1, 0.15 * inch))
                print(f"✓ Successfully added {data_key} table")
            
        except Exception as e:
            print(f"Error processing {data_key} table: {e}")
            import traceback
            traceback.print_exc()
    
    def _safe_get_value(self, record, keys, default):
        """Safely get value from record with multiple possible keys"""
        for key in keys:
            if key in record and record[key] is not None:
                return record[key]
        return default
    
    def _safe_get_float(self, record, keys, default):
        """Safely get float value from record"""
        for key in keys:
            if key in record and record[key] is not None:
                try:
                    return float(record[key])
                except (ValueError, TypeError):
                    continue
        return default
    
    def _add_info_message(self, message):
        """Add an info message to the PDF"""
        info_style = ParagraphStyle(
            name='InfoStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor("#666666"),
            alignment=TA_CENTER
        )
        self.story.append(Paragraph(message, info_style))
        self.story.append(Spacer(1, 0.2 * inch))
    
    def _add_error_message(self, section_name, error_message):
        """Add an error message to the PDF"""
        error_style = ParagraphStyle(
            name='ErrorStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.red,
            alignment=TA_CENTER
        )
        self.story.append(Paragraph(f"Error in {section_name}: {error_message}", error_style))
        self.story.append(Spacer(1, 0.2 * inch))
        
    def add_audit_group_performance_summary(self):
        
        """Add Section VII - Performance Summary of Audit Group - ENHANCED with merged circle cells"""
        try:
            print("=== STARTING AUDIT GROUP PERFORMANCE SUMMARY ===")
            
            # Section header
            self.add_section_highlight_bar("VII. Performance Summary of Audit Group", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='GroupPerformanceDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides a comprehensive performance analysis of each audit group, showing their contribution 
            to overall audit performance in terms of DARs submitted, audit paras raised, detection amounts, and recovery efficiency.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Table header style
            table_header_style = ParagraphStyle(
                name='GroupPerformanceTableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("📊 Audit Group Performance Summary", table_header_style))
            
            # Get data from vital_stats
            group_performance_data = self.vital_stats.get('group_performance_data', [])
            print(f"Group performance data length: {len(group_performance_data)}")
            
            if group_performance_data and len(group_performance_data) > 0:
                print("Creating table from actual group performance data...")
                # Create the performance table with circle calculation
                raw_data = []
                
                for group_item in group_performance_data:
                    try:
                        audit_group = str(group_item.get('audit_group', 'N/A'))
                        try:
                            group_num = int(audit_group)
                            circle_num = ((group_num - 1) // 3) + 1 if group_num > 0 else 0
                        except (ValueError, TypeError):
                            circle_num = 0
                        
                        dar_count = int(group_item.get('dar_count', 0))
                        paras_count = int(group_item.get('paras_count', 0))
                        detection = float(group_item.get('total_detection', 0))
                        recovery = float(group_item.get('total_recovery', 0))
                        recovery_pct = float(group_item.get('recovery_percentage', 0))
                        
                        raw_data.append({
                            'circle': circle_num,
                            'audit_group': audit_group,
                            'dar_count': dar_count,
                            'paras_count': paras_count,
                            'detection': detection,
                            'recovery': recovery,
                            'recovery_pct': recovery_pct
                        })
                        
                    except Exception as row_error:
                        print(f"Error processing group performance row: {row_error}")
                        continue
                
                # Sort by circle then by audit group
                raw_data.sort(key=lambda x: (x['circle'], int(x['audit_group']) if x['audit_group'].isdigit() else 999))
                
            else:
                print("Using fallback group performance data...")
                # Fallback data
                raw_data = [
                    {'circle': 1, 'audit_group': '1', 'dar_count': 2, 'paras_count': 8, 'detection': 5.25, 'recovery': 2.10, 'recovery_pct': 40.0},
                    {'circle': 1, 'audit_group': '2', 'dar_count': 3, 'paras_count': 12, 'detection': 8.75, 'recovery': 3.50, 'recovery_pct': 40.0},
                    {'circle': 1, 'audit_group': '3', 'dar_count': 1, 'paras_count': 4, 'detection': 2.15, 'recovery': 0.85, 'recovery_pct': 39.5},
                    {'circle': 2, 'audit_group': '4', 'dar_count': 2, 'paras_count': 7, 'detection': 6.80, 'recovery': 2.95, 'recovery_pct': 43.4},
                    {'circle': 2, 'audit_group': '5', 'dar_count': 1, 'paras_count': 3, 'detection': 1.95, 'recovery': 0.75, 'recovery_pct': 38.5},
                    {'circle': 2, 'audit_group': '6', 'dar_count': 1, 'paras_count': 5, 'detection': 3.45, 'recovery': 1.25, 'recovery_pct': 36.2}
                ]
            
            # CREATE TABLE DATA with circle merging logic
            performance_data = [['Circle No.', 'Audit Group', 'Total DARs', 'Total Audit Paras', 'Total Detection (Rs.L)', 'Total Recovery (Rs.L)', 'Recovery %']]
            
            # Group by circle to calculate spans
            circle_groups = {}
            for item in raw_data:
                circle = item['circle']
                if circle not in circle_groups:
                    circle_groups[circle] = []
                circle_groups[circle].append(item)
            
            # Build table data and track spans
            circle_spans = {}  # {circle_num: (start_row, end_row)}
            current_row = 1  # Start after header
            
            for circle_num in sorted(circle_groups.keys()):
                circle_items = circle_groups[circle_num]
                start_row = current_row
                
                for i, item in enumerate(circle_items):
                    # First row of each circle shows circle number, others show empty string
                    circle_display = str(circle_num) if i == 0 else ""
                    
                    performance_data.append([
                        circle_display,
                        item['audit_group'],
                        str(item['dar_count']),
                        str(item['paras_count']),
                        f"Rs.{item['detection']:.2f} L",
                        f"Rs.{item['recovery']:.2f} L",
                        f"{item['recovery_pct']:.1f}%"
                    ])
                    current_row += 1
                
                end_row = current_row - 1
                circle_spans[circle_num] = (start_row, end_row)
                print(f"Circle {circle_num}: rows {start_row} to {end_row}")
            
            # CRITICAL FIX: Calculate actual table dimensions
            total_rows = len(performance_data)
            data_rows = total_rows - 1
            print(f"Table will have {total_rows} total rows ({data_rows} data rows)")
            
            # Create table with optimized column widths
            col_widths = [0.8*inch, 1.0*inch, 0.9*inch, 1.2*inch, 1.5*inch, 1.5*inch, 1.0*inch]
            performance_table = Table(performance_data, colWidths=col_widths)
            
            # ENHANCED STYLING with circle merging and colors
            base_styles = [
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows styling
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (1, -1), 'CENTER'),   # Circle and Group columns centered
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # All other columns centered
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#1F4E79")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
                # Vertical alignment
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # # CIRCLE-SPECIFIC STYLING with different colors
            # circle_colors = {
            #     1: "#E8F5E8",  # Light green
            #     2: "#FFF3CD",  # Light yellow
            #     3: "#F8D7DA",  # Light red/pink
            #     4: "#E2E3E5",  # Light gray
            #     5: "#D4EDDA",  # Another green shade
            #     6: "#CCE5FF",  # Light blue
            #     7: "#FFE6CC",  # Light orange
            #     8: "#F0E6FF",  # Light purple
            #     9: "#FFE6F0",  # Light pink
            #     10: "#E6F7FF"  # Light cyan
            # }
            
            # # Apply spans and colors for each circle
            # try:
            #     for circle_num, (start_row, end_row) in circle_spans.items():
            #         if end_row > start_row:  # Multiple rows - need to span
            #             # SPAN the circle column
            #             base_styles.append(('SPAN', (0, start_row), (0, end_row)))
            #             print(f"Added SPAN for circle {circle_num}: (0, {start_row}) to (0, {end_row})")
                    
            #         # Apply circle-specific background color to the entire circle section
            #         circle_color = circle_colors.get(circle_num, "#F8F9FA")  # Default light color
            #         base_styles.append(('BACKGROUND', (0, start_row), (-1, end_row), colors.HexColor(circle_color)))
                    
            #         # Make circle numbers bold and centered
            #         base_styles.append(('FONTNAME', (0, start_row), (0, end_row), 'Helvetica-Bold'))
            #         base_styles.append(('FONTSIZE', (0, start_row), (0, end_row), 11))
            #         base_styles.append(('VALIGN', (0, start_row), (0, end_row), 'MIDDLE'))
                    
            #         print(f"Applied color {circle_color} to circle {circle_num}")
                
            # except Exception as span_error:
            #     print(f"Warning: Could not apply circle spans: {span_error}")
            # SAFE alternating row colors - only for rows that exist
            # SAFE - proper bounds checking
            if total_rows > 2:  # Only if we have data rows beyond header
                for row_idx in range(2, min(total_rows - 1, 10)):  # Limit to reasonable range and exclude totals
                    if row_idx % 2 == 0:  # Every other row
                        performance_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8F8F8")))
            # Apply all styles safely
            try:
                performance_table.setStyle(TableStyle(base_styles))
                print(f"✓ Applied {len(base_styles)} table styles successfully")
                
            except Exception as style_error:
                print(f"ERROR applying table styles: {style_error}")
                # Create a minimal table as fallback
                simple_table = Table(performance_data, colWidths=col_widths)
                simple_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ]))
                performance_table = simple_table
            
            self.story.append(performance_table)
            self.story.append(Spacer(1, 0.3 * inch))
            
            print("✓ Enhanced audit group performance summary completed successfully")
            
        except Exception as e:
            print(f"ERROR in add_audit_group_performance_summary: {e}")
            import traceback
            traceback.print_exc()
            
            # Add error message to PDF instead of crashing
            try:
                error_style = ParagraphStyle(
                    name='ErrorStyle',
                    parent=self.styles['Normal'],
                    fontSize=10,
                    textColor=colors.red,
                    alignment=TA_CENTER
                )
                self.story.append(Paragraph(f"[Error loading Audit Group Performance Summary: {str(e)}]", error_style))
                self.story.append(Spacer(1, 0.2 * inch))
            except:
                pass  # Don't let error handling crash the whole PDF
    

    def add_summary_of_audit_paras(self):
        """Add Section VIII - Summary of Audit Paras (Comprehensive MCM Summary)"""
        try:
            # Page break for new section
            self.story.append(PageBreak())
            
            # Section header
            self.add_section_highlight_bar("IX. Summary of Audit Paras ", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='ParaSummaryDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides a comprehensive summary of all audit paras discussed during the MCM, organized by audit circles and groups. 
            Each entry includes taxpayer details, para summaries, MCM decisions, and chair remarks.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Overall Remarks Section
            self._add_overall_remarks_section()
            
            # MCM Data - Get from vital_stats or fallback
            mcm_data = self.vital_stats.get('mcm_detailed_data', self._get_fallback_mcm_data())
            
            # Organize data by circles and groups
            organized_data = self._organize_mcm_data_by_circles(mcm_data)
            
            # Add circle-wise sections
            for circle_num in sorted(organized_data.keys()):
                self._add_circle_section(circle_num, organized_data[circle_num])
                
        except Exception as e:
            print(f"Error adding summary of audit paras: {e}")

    def _add_overall_remarks_section(self):
        """Add overall remarks for the meeting"""
        try:
            # Overall Remarks Header
            remarks_header_style = ParagraphStyle(
                name='RemarksHeader',
                parent=self.styles['Heading3'],
                fontSize=16,
                textColor=colors.HexColor("#8B4A9C"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=20
            )
            
            self.story.append(Paragraph("📝 Overall Remarks of the Chair for the Meeting", remarks_header_style))
            
            # Get overall remarks from vital_stats
            overall_remarks = self.vital_stats.get('overall_remarks', '')
            
            if not overall_remarks or overall_remarks.strip() == '':
                overall_remarks = "NIL"
            
            # Remarks content style
            remarks_style = ParagraphStyle(
                name='RemarksContent',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.5*inch,
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=20,
                spaceBefore=10
            )
            
            # Create a table for better formatting of remarks
            remarks_data = [[Paragraph(overall_remarks, remarks_style)]]
            remarks_table = Table(remarks_data, colWidths=[7*inch])
            remarks_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor("#E0E0E0")),
                ('TOPPADDING', (0, 0), (-1, -1), 15),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
                ('LEFTPADDING', (0, 0), (-1, -1), 20),
                ('RIGHTPADDING', (0, 0), (-1, -1), 20),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            self.story.append(remarks_table)
            self.story.append(Spacer(1, 0.3 * inch))
            
        except Exception as e:
            print(f"Error adding overall remarks: {e}")

    def _organize_mcm_data_by_circles(self, mcm_data):
        """Organize MCM data by circles and groups"""
        try:
            organized = {}
            
            for record in mcm_data:
                # Calculate circle from audit group
                audit_group = record.get('audit_group_number', 0)
                try:
                    group_num = int(audit_group)
                    circle_num = ((group_num - 1) // 3) + 1 if group_num > 0 else 0
                except (ValueError, TypeError):
                    circle_num = 0
                
                if circle_num == 0:
                    continue
                    
                if circle_num not in organized:
                    organized[circle_num] = {}
                
                if audit_group not in organized[circle_num]:
                    organized[circle_num][audit_group] = []
                
                organized[circle_num][audit_group].append(record)
            
            return organized
            
        except Exception as e:
            print(f"Error organizing MCM data: {e}")
            return {}

    def _add_circle_section(self, circle_num, circle_data):
        """Add a complete circle section with all its audit groups"""
        try:
            # Circle Header
            circle_header_style = ParagraphStyle(
                name='CircleHeader',
                parent=self.styles['Heading2'],
                fontSize=18,
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=0,
                spaceBefore=20
            )
            
            # Create circle header with colored background
            circle_header_data = [[Paragraph(f"🔵 AUDIT CIRCLE {circle_num}", circle_header_style)]]
            circle_header_table = Table(circle_header_data, colWidths=[7.5*inch])
            
            # Circle-specific colors
            circle_colors = {
                1: "#2E8B57",  # Sea Green
                2: "#4682B4",  # Steel Blue  
                3: "#B8860B",  # Dark Goldenrod
                4: "#8B4513",  # Saddle Brown
                5: "#4B0082",  # Indigo
            }
            
            circle_color = circle_colors.get(circle_num, "#2C3E50")
            
            circle_header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(circle_color)),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 20),
                ('RIGHTPADDING', (0, 0), (-1, -1), 20),
            ]))
            
            self.story.append(circle_header_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Add each audit group in this circle
            for audit_group in sorted(circle_data.keys()):
                self._add_audit_group_section(circle_num, audit_group, circle_data[audit_group])
                
        except Exception as e:
            print(f"Error adding circle {circle_num} section: {e}")

    def _add_audit_group_section(self, circle_num, audit_group, group_data):
        """Add audit group section with all GSTINs and their paras"""
        try:
            # Group Header
            group_header_style = ParagraphStyle(
                name='GroupHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=10,
                spaceBefore=15
            )
            
            self.story.append(Paragraph(f"📋 Audit Group {audit_group}", group_header_style))
            
            # Organize by GSTIN/Trade Name
            gstin_data = {}
            for record in group_data:
                gstin = record.get('gstin', 'Unknown')
                trade_name = record.get('trade_name', 'Unknown')
                key = f"{gstin}_{trade_name}"
                
                if key not in gstin_data:
                    gstin_data[key] = {
                        'gstin': gstin,
                        'trade_name': trade_name,
                        'category': record.get('category', 'Unknown'),
                        'chair_remarks': record.get('chair_remarks', ''),
                        'paras': []
                    }
                
                gstin_data[key]['paras'].append(record)
            
            # Add each GSTIN section
            for gstin_key, gstin_info in gstin_data.items():
                self._add_gstin_section(gstin_info)
                
        except Exception as e:
            print(f"Error adding audit group {audit_group} section: {e}")

    def _add_gstin_section(self, gstin_info):
        """Add individual GSTIN section with paras table and remarks - Enhanced to match UI"""
        try:
            # GSTIN Header Box (matching UI style)
            trade_name = gstin_info['trade_name']
            category = gstin_info['category']
            gstin = gstin_info['gstin']
            
            # Create header similar to UI
            header_style = ParagraphStyle(
                name='GSTINHeaderStyle',
                parent=self.styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor("#2C3E50"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=0,
                spaceBefore=12
            )
            
            # Company name in button-like style
            company_header_data = [[Paragraph(trade_name.upper(), header_style)]]
            company_header_table = Table(company_header_data, colWidths=[7.5*inch])
            company_header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#E8E8E8")),
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            self.story.append(company_header_table)
            
            # Category and GSTIN info boxes (side by side like UI)
            info_style = ParagraphStyle(
                name='InfoStyle',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C3E50"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            # Determine category color
            category_colors = {
                'Large': ("#f8d7da", "#721c24"),
                'Medium': ("#ffeeba", "#856404"), 
                'Small': ("#d4edda", "#155724"),
                'Unknown': ("#e2e3e5", "#383d41")
            }
            cat_bg, cat_text = category_colors.get(category, ("#e2e3e5", "#383d41"))
            
            category_text = f"Category: {category}"
            gstin_text = f"GSTIN: {gstin}"
            
            info_data = [[
                Paragraph(category_text, info_style),
                Paragraph(gstin_text, info_style)
            ]]
            
            info_table = Table(info_data, colWidths=[3.75*inch, 3.75*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor(cat_bg)),
                ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor(cat_text)),
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#e9ecef")),
                ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor("#495057")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
            ]))
            
            self.story.append(info_table)
            self.story.append(Spacer(1, 0.1 * inch))
            
            # Section title (matching UI)
            section_title_style = ParagraphStyle(
                name='SectionTitleStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#154360"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=10,
                spaceBefore=5
            )
            
            section_title = f"Gist of Audit Paras & MCM Decisions for: {trade_name}"
            self.story.append(Paragraph(section_title, section_title_style))
            
            # Create paras table with enhanced formatting
            self._create_paras_table(gstin_info['paras'])
            
            # Add chair remarks
            self._add_chair_remarks(gstin_info['chair_remarks'])
            
            self.story.append(Spacer(1, 0.2 * inch))
            
        except Exception as e:
            print(f"Error adding GSTIN section: {e}")

    # def _create_paras_table(self, paras_data):
    #     """Create professional table for audit paras with totals summary"""
    #     try:
    #         # Table header
    #         table_data = [['Para No.', 'Para Title', 'Detection (₹)', 'Recovery (₹)', 'Status', 'MCM Decision']]
            
    #         # Initialize totals
    #         total_detection = 0
    #         total_recovery = 0
            
    #         # Add para data
    #         for i, para in enumerate(paras_data):
    #             para_num = str(int(para.get('audit_para_number', 0))) if para.get('audit_para_number') else 'N/A'
                
    #             # Text-wrapped para title
    #             para_title = para.get('audit_para_heading', 'N/A')
    #             if len(para_title) > 80:
    #                 para_title = para_title[:77] + '...'
                
    #             # Get amounts in actual rupees (not lakhs)
    #             detection_lakhs = para.get('revenue_involved_lakhs_rs', 0) or 0
    #             recovery_lakhs = para.get('revenue_recovered_lakhs_rs', 0) or 0
                
    #             detection_rs = detection_lakhs * 100000  # Convert lakhs to rupees
    #             recovery_rs = recovery_lakhs * 100000
                
    #             total_detection += detection_rs
    #             total_recovery += recovery_rs
                
    #             status = para.get('status_of_para', 'N/A')
    #             mcm_decision = para.get('mcm_decision', 'N/A')
                
    #             # Format amounts using Indian numbering system
    #             detection_formatted = self.format_indian_currency(detection_rs)
    #             recovery_formatted = self.format_indian_currency(recovery_rs)
                
    #             table_data.append([
    #                 para_num,
    #                 para_title,
    #                 detection_formatted,
    #                 recovery_formatted,
    #                 status,
    #                 mcm_decision
    #             ])
            
    #         # Add totals row
    #         total_detection_formatted = self.format_indian_currency(total_detection)
    #         total_recovery_formatted = self.format_indian_currency(total_recovery)
            
    #         table_data.append([
    #             '',
    #             'Total of Paras',
    #             total_detection_formatted,
    #             total_recovery_formatted,
    #             '',
    #             ''
    #         ])
            
    #         # Create table
    #         col_widths = [0.7*inch, 2.8*inch, 1.0*inch, 1.0*inch, 1.2*inch, 1.8*inch]
    #         paras_table = Table(table_data, colWidths=col_widths)
            
    #         # Apply colorful styling
    #         paras_table.setStyle(TableStyle([
    #             # Header styling
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495E")),
    #             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 0), (-1, 0), 9),
    #             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
    #             # Data rows
    #             ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),  # Exclude totals row
    #             ('FONTSIZE', (0, 1), (-1, -2), 8),
    #             ('ALIGN', (0, 1), (0, -2), 'CENTER'),     # Para No. centered
    #             ('ALIGN', (1, 1), (1, -2), 'LEFT'),      # Para Title left-aligned
    #             ('ALIGN', (2, 1), (-1, -2), 'CENTER'),   # Other columns centered
                
    #             # Totals row styling
    #             ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
    #             ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, -1), (-1, -1), 9),
    #             ('ALIGN', (1, -1), (1, -1), 'RIGHT'),    # "Total of Paras" right-aligned
    #             ('ALIGN', (2, -1), (-1, -1), 'CENTER'),  # Amount columns centered
    #             ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                
    #             # Alternating row colors (excluding header and totals)
    #             ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor("#F8F9FA")),
                
    #             # Grid and borders
    #             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7")),
    #             ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#34495E")),
    #             ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),  # Line above totals
                
    #             # Padding for text wrapping
    #             ('TOPPADDING', (0, 0), (-1, -1), 6),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 4),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                
    #             # Vertical alignment
    #             ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Top alignment for text wrapping
    #         ]))
            
    #         self.story.append(paras_table)
            
    #         # Add company totals summary (like in the UI)
    #         self._add_company_totals_summary(paras_data, total_detection, total_recovery)
            
    #     except Exception as e:
    #         print(f"Error creating paras table: {e}")
    # def _create_paras_table(self, paras_data):
    #     """Create professional table for audit paras with totals summary - FIXED TEXT WRAPPING"""
    #     try:
    #         # Define styles for table content
    #         para_title_style = ParagraphStyle(
    #             name='ParaTitleStyle',
    #             parent=self.styles['Normal'],
    #             fontSize=8,
    #             textColor=colors.HexColor("#2C2C2C"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica',
    #             leading=10,
    #             wordWrap='LTR'  # Enable word wrapping
    #         )
            
    #         cell_style = ParagraphStyle(
    #             name='CellStyle',
    #             parent=self.styles['Normal'],
    #             fontSize=8,
    #             textColor=colors.HexColor("#2C2C2C"),
    #             alignment=TA_CENTER,
    #             fontName='Helvetica',
    #             leading=10
    #         )
    #         header_style = ParagraphStyle(
    #         name='HeaderStyle',
    #         parent=self.styles['Normal'],
    #         fontSize=9,
    #         textColor=colors.white,  # WHITE TEXT for header
    #         alignment=TA_CENTER,
    #         fontName='Helvetica-Bold',
    #         leading=11
    #         )
    #         # Table header - using Paragraph objects for proper formatting
    #         table_data = [[
    #             Paragraph('Para No.', header_style),
    #             Paragraph('Para Title', header_style), 
    #             Paragraph('Detection(Rs)', header_style),
    #             Paragraph('Recovery(Rs)', header_style),
    #             Paragraph('Status', header_style),
    #             Paragraph('MCM Decision', header_style)
    #         ]]
            
    #         # Initialize totals
    #         total_detection = 0
    #         total_recovery = 0
            
    #         # Add para data
    #         for i, para in enumerate(paras_data):
    #             para_num = str(int(para.get('audit_para_number', 0))) if para.get('audit_para_number') else 'N/A'
                
    #             # Para title with proper text wrapping - DON'T truncate, let it wrap
    #             para_title_text = para.get('audit_para_heading', 'N/A')
    #             # Remove truncation - let the paragraph handle wrapping
    #             para_title = Paragraph(para_title_text, para_title_style)
                
    #             # Get amounts in actual rupees (not lakhs)
    #             detection_lakhs = para.get('revenue_involved_lakhs_rs', 0) or 0
    #             recovery_lakhs = para.get('revenue_recovered_lakhs_rs', 0) or 0
                
    #             detection_rs = detection_lakhs * 100000  # Convert lakhs to rupees
    #             recovery_rs = recovery_lakhs * 100000
                
    #             total_detection += detection_rs
    #             total_recovery += recovery_rs
                
    #             status = para.get('status_of_para', 'N/A')
    #             mcm_decision = para.get('mcm_decision', 'N/A')
                
    #             # Format amounts using Indian numbering system
    #             detection_formatted = self.format_indian_currency(detection_rs)
    #             recovery_formatted = self.format_indian_currency(recovery_rs)
                
    #             # Create table row with Paragraph objects for wrapping
    #             table_data.append([
    #                 Paragraph(para_num, cell_style),
    #                 para_title,  # This is already a Paragraph object
    #                 Paragraph(detection_formatted, cell_style),
    #                 Paragraph(recovery_formatted, cell_style),
    #                 Paragraph(status, cell_style),
    #                 Paragraph(mcm_decision, cell_style)
    #             ])
            
    #         # Add totals row
    #         total_detection_formatted = self.format_indian_currency(total_detection)
    #         total_recovery_formatted = self.format_indian_currency(total_recovery)
            
    #         total_style = ParagraphStyle(
    #             name='TotalStyle',
    #             parent=cell_style,
    #             fontName='Helvetica-Bold',
    #             fontSize=9
    #         )
            
    #         table_data.append([
    #             Paragraph('', total_style),
    #             Paragraph('Total of Paras', total_style),
    #             Paragraph(total_detection_formatted, total_style),
    #             Paragraph(total_recovery_formatted, total_style),
    #             Paragraph('', total_style),
    #             Paragraph('', total_style)
    #         ])
            
    #         # FIXED COLUMN WIDTHS - Make Para Title column wider
    #         col_widths = [0.6*inch, 3.5*inch, 1.0*inch, 1.0*inch, 1.1*inch, 1.3*inch]
    #         # Total width = 8.5 inches (fits in page width)
            
    #         paras_table = Table(table_data, colWidths=col_widths)
            
    #         # Apply enhanced styling with text wrapping
    #         paras_table.setStyle(TableStyle([
    #             # Header styling
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495E")),
    #             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 0), (-1, 0), 9),
    #             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
    #             # Data rows - REMOVED specific font settings since we're using Paragraph objects
    #             ('ALIGN', (0, 1), (0, -2), 'CENTER'),     # Para No. centered
    #             ('ALIGN', (1, 1), (1, -2), 'LEFT'),      # Para Title left-aligned
    #             ('ALIGN', (2, 1), (-1, -2), 'CENTER'),   # Other columns centered
                
    #             # Totals row styling
    #             ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
    #             ('ALIGN', (1, -1), (1, -1), 'RIGHT'),    # "Total of Paras" right-aligned
    #             ('ALIGN', (2, -1), (-1, -1), 'CENTER'),  # Amount columns centered
    #             ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                
    #             # Alternating row colors (excluding header and totals)
    #             ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor("#F8F9FA")),
                
    #             # Grid and borders
    #             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7")),
    #             ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#34495E")),
    #             ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),
                
    #             # CRITICAL: Padding for text wrapping - increase vertical padding
    #             ('TOPPADDING', (0, 0), (-1, -1), 8),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 4),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                
    #             # CRITICAL: TOP alignment for proper text wrapping
    #             ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                
    #             # CRITICAL: Allow row height to expand for wrapped text
    #             ('ROWBACKGROUNDS', (0, 0), (-1, -1), [None]),  # Ensures row height adapts
    #         ]))
            
    #         self.story.append(paras_table)
            
    #         # Add company totals summary (like in the UI)
    #         self._add_company_totals_summary(paras_data, total_detection, total_recovery)
            
    #         print("✓ Created paras table with proper text wrapping")
            
    #     except Exception as e:
    #         print(f"Error creating paras table: {e}")
    #         import traceback
    #         traceback.print_exc()
    # def _create_paras_table(self, paras_data):
    #     """Create professional table for audit paras with totals summary - FIXED TEXT WRAPPING"""
    #     try:
    #         # Define styles for table content
    #         para_title_style = ParagraphStyle(
    #             name='ParaTitleStyle',
    #             parent=self.styles['Normal'],
    #             fontSize=8,
    #             textColor=colors.HexColor("#2C2C2C"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica',
    #             leading=10,
    #             wordWrap='LTR'  # Enable word wrapping
    #         )
            
    #         cell_style = ParagraphStyle(
    #             name='CellStyle',
    #             parent=self.styles['Normal'],
    #             fontSize=8,
    #             textColor=colors.HexColor("#2C2C2C"),
    #             alignment=TA_CENTER,
    #             fontName='Helvetica',
    #             leading=10
    #         )
    #         header_style = ParagraphStyle(
    #         name='HeaderStyle',
    #         parent=self.styles['Normal'],
    #         fontSize=9,
    #         textColor=colors.white,  # WHITE TEXT for header
    #         alignment=TA_CENTER,
    #         fontName='Helvetica-Bold',
    #         leading=11
    #         )
    #         # Table header - using Paragraph objects for proper formatting
    #         table_data = [[
    #             Paragraph('Para No.', header_style),
    #             Paragraph('Para Title', header_style), 
    #             Paragraph('Detection(Rs)', header_style),
    #             Paragraph('Recovery(Rs)', header_style),
    #             Paragraph('Status', header_style),
    #             Paragraph('MCM Decision', header_style)
    #         ]]
            
    #         # Initialize totals
    #         total_detection = 0
    #         total_recovery = 0
            
    #         # Add para data
    #         for i, para in enumerate(paras_data):
    #             para_num = str(int(para.get('audit_para_number', 0))) if para.get('audit_para_number') else 'N/A'
                
    #             # Para title with proper text wrapping - DON'T truncate, let it wrap
    #             para_title_text = para.get('audit_para_heading', 'N/A')
    #             # Remove truncation - let the paragraph handle wrapping
    #             para_title = Paragraph(para_title_text, para_title_style)

    #             # FIXED: Use correct field names from your data model
    #             # Get amounts in rupees (already in rupees according to your model)
    #             detection_rs = para.get('revenue_involved_rs', 0) or 0
    #             recovery_rs = para.get('revenue_recovered_rs', 0) or 0
                
    #             # NO CONVERSION NEEDED - amounts are already in rupees
    #             total_detection += detection_rs
    #             total_recovery += recovery_rs
    #             # # Get amounts in actual rupees (not lakhs)
    #             # detection_lakhs = para.get('revenue_involved_lakhs_rs', 0) or 0
    #             # recovery_lakhs = para.get('revenue_recovered_lakhs_rs', 0) or 0
                
    #             # detection_rs = detection_lakhs * 100000  # Convert lakhs to rupees
    #             # recovery_rs = recovery_lakhs * 100000
                
    #             # total_detection += detection_rs
    #             # total_recovery += recovery_rs
                
    #             status = para.get('status_of_para', 'N/A')
    #             mcm_decision = para.get('mcm_decision', 'N/A')
                
    #             # Format amounts using Indian numbering system
    #             detection_formatted = self.format_indian_currency(detection_rs)
    #             recovery_formatted = self.format_indian_currency(recovery_rs)
                
    #             # Create table row with Paragraph objects for wrapping
    #             table_data.append([
    #                 Paragraph(para_num, cell_style),
    #                 para_title,  # This is already a Paragraph object
    #                 Paragraph(detection_formatted, cell_style),
    #                 Paragraph(recovery_formatted, cell_style),
    #                 Paragraph(status, cell_style),
    #                 Paragraph(mcm_decision, cell_style)
    #             ])
            
    #         # Add totals row
    #         total_detection_formatted = self.format_indian_currency(total_detection)
    #         total_recovery_formatted = self.format_indian_currency(total_recovery)
            
    #         total_style = ParagraphStyle(
    #             name='TotalStyle',
    #             parent=cell_style,
    #             fontName='Helvetica-Bold',
    #             fontSize=9
    #         )
            
    #         table_data.append([
    #             Paragraph('', total_style),
    #             Paragraph('Total of Paras', total_style),
    #             Paragraph(total_detection_formatted, total_style),
    #             Paragraph(total_recovery_formatted, total_style),
    #             Paragraph('', total_style),
    #             Paragraph('', total_style)
    #         ])
            
    #         # FIXED COLUMN WIDTHS - Make Para Title column wider
    #         col_widths = [0.6*inch, 3.5*inch, 1.0*inch, 1.0*inch, 1.1*inch, 1.3*inch]
    #         # Total width = 8.5 inches (fits in page width)
            
    #         paras_table = Table(table_data, colWidths=col_widths)
            
    #         # Apply enhanced styling with text wrapping
    #         paras_table.setStyle(TableStyle([
    #             # Header styling
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495E")),
    #             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #             ('FONTSIZE', (0, 0), (-1, 0), 9),
    #             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
    #             # Data rows - REMOVED specific font settings since we're using Paragraph objects
    #             ('ALIGN', (0, 1), (0, -2), 'CENTER'),     # Para No. centered
    #             ('ALIGN', (1, 1), (1, -2), 'LEFT'),      # Para Title left-aligned
    #             ('ALIGN', (2, 1), (-1, -2), 'CENTER'),    # Other columns centered
                
    #             # Totals row styling
    #             ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
    #             ('ALIGN', (1, -1), (1, -1), 'RIGHT'),     # "Total of Paras" right-aligned
    #             ('ALIGN', (2, -1), (-1, -1), 'CENTER'),    # Amount columns centered
    #             ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                
    #             # Alternating row colors (excluding header and totals)
    #             ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F9FA")),
    #             ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor("#F8F9FA")),
                
    #             # Grid and borders
    #             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7")),
    #             ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#34495E")),
    #             ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),
                
    #             # CRITICAL: Padding for text wrapping - increase vertical padding
    #             ('TOPPADDING', (0, 0), (-1, -1), 8),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 4),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                
    #             # CRITICAL: TOP alignment for proper text wrapping
    #             ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                
    #             # CRITICAL: Allow row height to expand for wrapped text
    #             ('ROWBACKGROUNDS', (0, 0), (-1, -1), [None]),  # Ensures row height adapts
    #         ]))
            
    #         self.story.append(paras_table)
            
    #         # Add company totals summary (like in the UI)
    #         self._add_company_totals_summary(paras_data, total_detection, total_recovery)
            
    #         print("✓ Created paras table with proper text wrapping")
            
    #     except Exception as e:
    #         print(f"Error creating paras table: {e}")
    #         import traceback
    #         traceback.print_exc()
    def _create_paras_table(self, paras_data):
        """Create professional table for audit paras with totals summary - DEBUG VERSION"""
        try:
            print("=== DEBUGGING PARAS TABLE ===")
            print(f"Number of paras: {len(paras_data)}")
            
            # Debug: Print the first para to see the exact structure
            if paras_data:
                print("First para structure:")
                first_para = paras_data[0]
                print(f"Type: {type(first_para)}")
                print(f"Keys: {list(first_para.keys()) if isinstance(first_para, dict) else 'Not a dict'}")
                print(f"First para data: {first_para}")
                
                # Check all possible field names for amounts
                possible_amount_fields = [
                    'revenue_involved_rs', 'revenue_recovered_rs',
                    'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs', 
                    'Para Detection in Lakhs', 'Para Recovery in Lakhs',
                    'detection_amount', 'recovery_amount',
                    'amount_detected', 'amount_recovered',
                    'detected', 'recovered',
                    'detection', 'recovery'
                ]
                
                print("\nChecking for amount fields:")
                for field in possible_amount_fields:
                    if field in first_para:
                        print(f"✓ Found field '{field}': {first_para[field]} (type: {type(first_para[field])})")
                    else:
                        print(f"✗ Field '{field}' not found")
            
            # Define styles for table content
            para_title_style = ParagraphStyle(
                name='ParaTitleStyle',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_LEFT,
                fontName='Helvetica',
                leading=10,
                wordWrap='LTR'
            )
            
            cell_style = ParagraphStyle(
                name='CellStyle',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_CENTER,
                fontName='Helvetica',
                leading=10
            )
            
            header_style = ParagraphStyle(
                name='HeaderStyle',
                parent=self.styles['Normal'],
                fontSize=9,
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                leading=11
            )
            
            # Table header
            table_data = [[
                Paragraph('Para No.', header_style),
                Paragraph('Para Title', header_style), 
                Paragraph('Detection(Rs)', header_style),
                Paragraph('Recovery(Rs)', header_style),
                Paragraph('Status', header_style),
                Paragraph('MCM Decision', header_style)
            ]]
            
            # Initialize totals
            total_detection = 0
            total_recovery = 0
            
            # Add para data with enhanced debugging
            for i, para in enumerate(paras_data):
                print(f"\n--- Processing Para {i+1} ---")
                print(f"Para data: {para}")
                
                para_num = str(int(para.get('audit_para_number', 0))) if para.get('audit_para_number') else 'N/A'
                para_title_text = para.get('audit_para_heading', 'N/A')
                para_title = Paragraph(para_title_text, para_title_style)
                
                # ENHANCED: Try multiple possible field names for amounts
                detection_rs = 0
                recovery_rs = 0
                
                # Try different possible field names for detection
                detection_fields = [
                    'revenue_involved_rs',
                    'revenue_involved_lakhs_rs', 
                    'Para Detection in Lakhs',
                    'detection_amount',
                    'amount_detected',
                    'detected',
                    'detection'
                ]
                
                for field in detection_fields:
                    if field in para and para[field] is not None:
                        try:
                            value = float(para[field])
                            # If field contains 'lakhs', convert to rupees
                            if 'lakhs' in field.lower():
                                detection_rs = value * 100000
                            else:
                                detection_rs = value
                            print(f"✓ Detection from field '{field}': {value} -> {detection_rs}")
                            break
                        except (ValueError, TypeError) as e:
                            print(f"✗ Could not convert detection field '{field}': {para[field]} - {e}")
                            continue
                
                # Try different possible field names for recovery
                recovery_fields = [
                    'revenue_recovered_rs',
                    'revenue_recovered_lakhs_rs',
                    'Para Recovery in Lakhs', 
                    'recovery_amount',
                    'amount_recovered',
                    'recovered',
                    'recovery'
                ]
                
                for field in recovery_fields:
                    if field in para and para[field] is not None:
                        try:
                            value = float(para[field])
                            # If field contains 'lakhs', convert to rupees
                            if 'lakhs' in field.lower():
                                recovery_rs = value * 100000
                            else:
                                recovery_rs = value
                            print(f"✓ Recovery from field '{field}': {value} -> {recovery_rs}")
                            break
                        except (ValueError, TypeError) as e:
                            print(f"✗ Could not convert recovery field '{field}': {para[field]} - {e}")
                            continue
                
                print(f"Final amounts - Detection: {detection_rs}, Recovery: {recovery_rs}")
                
                total_detection += detection_rs
                total_recovery += recovery_rs
                
                status = para.get('status_of_para', 'N/A')
                mcm_decision = para.get('mcm_decision', 'N/A')
                
                # Format amounts
                detection_formatted = self.format_indian_currency(detection_rs)
                recovery_formatted = self.format_indian_currency(recovery_rs)
                
                print(f"Formatted amounts - Detection: {detection_formatted}, Recovery: {recovery_formatted}")
                
                # Create table row
                table_data.append([
                    Paragraph(para_num, cell_style),
                    para_title,
                    Paragraph(detection_formatted, cell_style),
                    Paragraph(recovery_formatted, cell_style),
                    Paragraph(status, cell_style),
                    Paragraph(mcm_decision, cell_style)
                ])
            
            print(f"\n=== FINAL TOTALS ===")
            print(f"Total Detection: {total_detection}")
            print(f"Total Recovery: {total_recovery}")
            
            # Add totals row
            total_detection_formatted = self.format_indian_currency(total_detection)
            total_recovery_formatted = self.format_indian_currency(total_recovery)
            
            print(f"Formatted Totals - Detection: {total_detection_formatted}, Recovery: {total_recovery_formatted}")
            
            total_style = ParagraphStyle(
                name='TotalStyle',
                parent=cell_style,
                fontName='Helvetica-Bold',
                fontSize=9
            )
            
            table_data.append([
                Paragraph('', total_style),
                Paragraph('Total of Paras', total_style),
                Paragraph(total_detection_formatted, total_style),
                Paragraph(total_recovery_formatted, total_style),
                Paragraph('', total_style),
                Paragraph('', total_style)
            ])
            
            # Create table
            col_widths = [0.6*inch, 3.5*inch, 1.0*inch, 1.0*inch, 1.1*inch, 1.3*inch]
            paras_table = Table(table_data, colWidths=col_widths)
            
            # Apply styling (same as before)
            paras_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495E")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (0, -2), 'CENTER'),
                ('ALIGN', (1, 1), (1, -2), 'LEFT'),
                ('ALIGN', (2, 1), (-1, -2), 'CENTER'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
                ('ALIGN', (1, -1), (1, -1), 'RIGHT'),
                ('ALIGN', (2, -1), (-1, -1), 'CENTER'),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F9FA")),
                ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F9FA")),
                ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor("#F8F9FA")),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#34495E")),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [None]),
            ]))
            
            self.story.append(paras_table)
            
            # Add company totals summary
            self._add_company_totals_summary(paras_data, total_detection, total_recovery)
            
            print("✓ Created paras table with debugging")
            
        except Exception as e:
            print(f"Error creating paras table: {e}")
            import traceback
            traceback.print_exc()
    def format_indian_currency(self, amount):
        """Format currency in Indian numbering system"""
        try:
            if amount == 0:
                return "Rs. 0"
            
            # Convert to integer for formatting
            amount = int(amount)
            
            # Handle negative numbers
            if amount < 0:
                return f"Rs.-{self.format_indian_currency(-amount)[2:]}"
            
            # Convert to string and format
            amount_str = str(amount)
            
            if len(amount_str) <= 3:
                return f"Rs,{amount_str}"
            
            # Split into groups
            last_three = amount_str[-3:]
            remaining = amount_str[:-3]
            
            # Add commas every 2 digits for remaining part
            formatted_parts = []
            while len(remaining) > 2:
                formatted_parts.append(remaining[-2:])
                remaining = remaining[:-2]
            
            if remaining:
                formatted_parts.append(remaining)
            
            formatted_parts.reverse()
            formatted_remaining = ','.join(formatted_parts)
            
            return f"₹ {formatted_remaining},{last_three}"
            
        except Exception as e:
            print(f"Error formatting currency: {e}")
            return f"₹ {amount}"

    def _add_company_totals_summary(self, paras_data, total_detection, total_recovery):
        """Add company totals summary boxes like in the UI"""
        try:
            if not paras_data:
                return
                
            # Get company name from first para
            company_name = paras_data[0].get('trade_name', 'Unknown Company')
            if len(company_name) > 40:
                company_name = company_name[:37] + '...'
            
            # Format amounts
            detection_formatted = self.format_indian_currency(total_detection)
            recovery_formatted = self.format_indian_currency(total_recovery)
            
            # Detection summary box (red background like UI)
            detection_style = ParagraphStyle(
                name='DetectionSummary',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#721c24"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=15
            )
            
            detection_text = f"Total Detection for {company_name}: {detection_formatted}"
            detection_data = [[Paragraph(detection_text, detection_style)]]
            detection_table = Table(detection_data, colWidths=[7.5*inch])
            detection_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8d7da")),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ]))
            
            self.story.append(detection_table)
            
            # Recovery summary box (green background like UI)
            recovery_style = ParagraphStyle(
                name='RecoverySummary',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#155724"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=15,
                spaceBefore=5
            )
            
            recovery_text = f"Total Recovery for {company_name}: {recovery_formatted}"
            recovery_data = [[Paragraph(recovery_text, recovery_style)]]
            recovery_table = Table(recovery_data, colWidths=[7.5*inch])
            recovery_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#d4edda")),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ]))
            
            self.story.append(recovery_table)
            
        except Exception as e:
            print(f"Error adding company totals summary: {e}")

    def _add_chair_remarks(self, chair_remarks):
        """Add chair remarks section below the table"""
        try:
            # Chair remarks header
            remarks_style = ParagraphStyle(
                name='ChairRemarksStyle',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor("#2C3E50"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=5,
                spaceBefore=8
            )
            
            self.story.append(Paragraph("💬 Chair's Remarks:", remarks_style))
            
            # Remarks content
            if not chair_remarks or chair_remarks.strip() == '':
                remarks_content = "NIL"
            else:
                remarks_content = chair_remarks
            
            remarks_content_style = ParagraphStyle(
                name='ChairRemarksContent',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor("#34495E"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.3*inch,
                rightIndent=0.1*inch,
                leading=12,
                spaceAfter=10
            )
            
            # Create remarks box
            remarks_data = [[Paragraph(remarks_content, remarks_content_style)]]
            remarks_table = Table(remarks_data, colWidths=[7.5*inch])
            remarks_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ECF0F1")),
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            self.story.append(remarks_table)
            
        except Exception as e:
            print(f"Error adding chair remarks: {e}")

    def _get_fallback_mcm_data(self):
        """Get fallback MCM data if none available"""
        return [
            {
                'audit_group_number': 1,
                'gstin': '27AADCS5283M1ZT',
                'trade_name': 'SRP ENTERPRISES PVT LTD',
                'category': 'Large',
                'audit_para_number': 1,
                'audit_para_heading': 'Non-payment of late fee for late filing of monthly return GSTR-1',
                'revenue_involved_lakhs_rs': 0.06850,
                'revenue_recovered_lakhs_rs': 0,
                'status_of_para': 'Agreed yet to pay',
                'mcm_decision': 'Para to be pursued else issue SCN',
                'chair_remarks': 'Follow up required for payment compliance'
            },
            {
                'audit_group_number': 1,
                'gstin': '27AADCS5283M1ZT',
                'trade_name': 'SRP ENTERPRISES PVT LTD',
                'category': 'Large',
                'audit_para_number': 2,
                'audit_para_heading': 'Non-payment of late fee for late filing of GSTR-3B',
                'revenue_involved_lakhs_rs': 0.03850,
                'revenue_recovered_lakhs_rs': 0,
                'status_of_para': 'Agreed yet to pay',
                'mcm_decision': 'Para to be pursued else issue SCN',
                'chair_remarks': 'Follow up required for payment compliance'
            }
        ]
    def add_mcm_decision_analysis(self):
        """Add Section VIII - Analysis of MCM Decisions with bar chart and summary table"""
        try:
            print("=== STARTING MCM DECISION ANALYSIS ===")
            
            # Section header
            self.add_section_highlight_bar("VIII. Analysis of MCM Decisions", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='MCMDecisionDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides an analysis of MCM decisions taken for all audit paras during the meeting. 
            It shows the distribution of paras across different decision categories and helps track the action items 
            and follow-up requirements for the audit teams.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Get MCM detailed data
            mcm_detailed_data = self.vital_stats.get('mcm_detailed_data', [])
            
            if not mcm_detailed_data:
                self.story.append(Paragraph("No MCM decision data available for analysis.", desc_style))
                return
            
            # Analyze MCM decisions
            decision_analysis = self._analyze_mcm_decisions(mcm_detailed_data)
            
            if not decision_analysis:
                self.story.append(Paragraph("No valid MCM decisions found for analysis.", desc_style))
                return
            
            # Add summary table
            self._add_mcm_decision_summary_table(decision_analysis)
            
            # Add bar chart
            self._add_mcm_decision_chart(decision_analysis)
            
            # Add insights
            self._add_mcm_decision_insights(decision_analysis)
            
            print("✓ MCM Decision Analysis completed successfully")
            
        except Exception as e:
            print(f"ERROR in add_mcm_decision_analysis: {e}")
            import traceback
            traceback.print_exc()
            
            # Add error message instead of crashing
            try:
                error_style = ParagraphStyle(name='ErrorStyle', parent=self.styles['Normal'], 
                                            fontSize=10, textColor=colors.red, alignment=TA_CENTER)
                self.story.append(Paragraph(f"[Error loading MCM Decision Analysis: {str(e)}]", error_style))
                self.story.append(Spacer(1, 0.2 * inch))
            except:
                pass
    
    def _analyze_mcm_decisions(self, mcm_data):
        """Analyze MCM decisions and return summary statistics"""
        try:
            decision_counts = {}
            decision_detection = {}
            decision_recovery = {}
            
            # Standard MCM decision categories
            standard_decisions = [
                'Para closed since recovered',
                'Para deferred', 
                'Para to be pursued else issue SCN',
                'Decision pending(not saved)'
            ]
            
            # Initialize counters
            for decision in standard_decisions:
                decision_counts[decision] = 0
                decision_detection[decision] = 0.0
                decision_recovery[decision] = 0.0
            
            # Count other decisions
            other_decisions = {}
            
            for record in mcm_data:
                try:
                    decision = record.get('mcm_decision', 'Decision pending')
                    if not decision or decision.strip() == '':
                        decision = 'Decision pending'
                    
                    # Get financial amounts (convert from lakhs to lakhs for consistency)
                    detection_lakhs = float(record.get('revenue_involved_lakhs_rs', 0))
                    recovery_lakhs = float(record.get('revenue_recovered_lakhs_rs', 0))
                    
                    if decision in standard_decisions:
                        decision_counts[decision] += 1
                        decision_detection[decision] += detection_lakhs
                        decision_recovery[decision] += recovery_lakhs
                    else:
                        # Handle other/custom decisions
                        if decision not in other_decisions:
                            other_decisions[decision] = {'count': 0, 'detection': 0.0, 'recovery': 0.0}
                        other_decisions[decision]['count'] += 1
                        other_decisions[decision]['detection'] += detection_lakhs
                        other_decisions[decision]['recovery'] += recovery_lakhs
                    
                except Exception as record_error:
                    print(f"Error processing MCM record: {record_error}")
                    continue
            
            # Combine results
            analysis_results = []
            
            # Add standard decisions
            for decision in standard_decisions:
                if decision_counts[decision] > 0:  # Only include decisions that have paras
                    analysis_results.append({
                        'decision': decision,
                        'para_count': decision_counts[decision],
                        'total_detection': decision_detection[decision],
                        'total_recovery': decision_recovery[decision],
                        'recovery_percentage': (decision_recovery[decision] / decision_detection[decision] * 100) 
                                             if decision_detection[decision] > 0 else 0
                    })
            
            # Add other decisions
            for decision, data in other_decisions.items():
                analysis_results.append({
                    'decision': decision,
                    'para_count': data['count'],
                    'total_detection': data['detection'],
                    'total_recovery': data['recovery'],
                    'recovery_percentage': (data['recovery'] / data['detection'] * 100) 
                                         if data['detection'] > 0 else 0
                })
            
            # Sort by para count (descending)
            analysis_results.sort(key=lambda x: x['para_count'], reverse=True)
            
            print(f"Analyzed {len(analysis_results)} different MCM decisions")
            return analysis_results
            
        except Exception as e:
            print(f"Error analyzing MCM decisions: {e}")
            return []
    
    def _add_mcm_decision_summary_table(self, decision_analysis):
        """Add MCM decision summary table"""
        try:
            # Table header style
            table_header_style = ParagraphStyle(
                name='MCMDecisionTableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("📊 MCM Decision Summary", table_header_style))
            
            # Create table data
            table_data = [['MCM Decision', 'No. of Paras', 'Total Detection (Rs.L)', 'Total Recovery (Rs.L)', 'Recovery %']]
            
            total_paras = 0
            total_detection = 0.0
            total_recovery = 0.0
            
            for item in decision_analysis:
                para_count = item['para_count']
                detection = item['total_detection']
                recovery = item['total_recovery']
                recovery_pct = item['recovery_percentage']
                
                total_paras += para_count
                total_detection += detection
                total_recovery += recovery
                
                # Truncate long decision names for better table formatting
                decision_text = item['decision']
                if len(decision_text) > 35:
                    decision_text = decision_text[:32] + '...'
                
                table_data.append([
                    decision_text,
                    str(para_count),
                    f'Rs.{detection:.2f} L',
                    f'Rs.{recovery:.2f} L',
                    f'{recovery_pct:.1f}%'
                ])
            
            # Add totals row
            total_recovery_pct = (total_recovery / total_detection * 100) if total_detection > 0 else 0
            table_data.append([
                '📊 Total (All Decisions)',
                str(total_paras),
                f'Rs.{total_detection:.2f} L',
                f'Rs.{total_recovery:.2f} L',
                f'{total_recovery_pct:.1f}%'
            ])
            
            # Create and style table
            col_widths = [2.8*inch, 1.0*inch, 1.4*inch, 1.4*inch, 1.0*inch]
            decision_table = Table(table_data, colWidths=col_widths)
            
            decision_table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -2), 9),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Numbers centered
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Decision text left-aligned
                
                # Totals row styling
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 9),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            self.story.append(decision_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
        except Exception as e:
            print(f"Error adding MCM decision summary table: {e}")
    
    def _add_mcm_decision_chart(self, decision_analysis):
        """Add MCM decision distribution bar chart"""
        try:
            chart_header_style = ParagraphStyle(
                name='MCMDecisionChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            self.story.append(Paragraph("📊 Distribution of Audit Paras by MCM Decision", chart_header_style))
            
            # Create simple text-based chart for now (can be enhanced with actual chart generation later)
            chart_style = ParagraphStyle(
                name='ChartText',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_LEFT,
                fontName='Helvetica',
                leftIndent=0.5*inch,
                leading=14,
                spaceAfter=8
            )
            
            # Create a simple text representation of the chart
            max_count = max([item['para_count'] for item in decision_analysis]) if decision_analysis else 1
            
            for item in decision_analysis:
                decision = item['decision']
                count = item['para_count']
                
                # Create a simple bar using characters
                bar_length = int((count / max_count) * 30)  # Scale to max 30 characters
                bar = '█' * bar_length
                
                chart_text = f"{decision[:25]:<25} │{bar:<30}│ {count} paras"
                self.story.append(Paragraph(chart_text, chart_style))
            
            self.story.append(Spacer(1, 0.2 * inch))
            
        except Exception as e:
            print(f"Error adding MCM decision chart: {e}")
    
    def _add_mcm_decision_insights(self, decision_analysis):
        """Add insights and key findings from MCM decision analysis"""
        try:
            insights_header_style = ParagraphStyle(
                name='InsightsHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            insights_style = ParagraphStyle(
                name='InsightsText',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=8
            )
            
            self.story.append(Paragraph("💡 Key Insights from MCM Decisions", insights_header_style))
            
            if decision_analysis:
                # Calculate insights
                total_paras = sum([item['para_count'] for item in decision_analysis])
                most_common_decision = decision_analysis[0]  # Already sorted by count
                
                # Find decisions needing action
                action_needed = []
                for item in decision_analysis:
                    if 'pursue' in item['decision'].lower() or 'deferred' in item['decision'].lower():
                        action_needed.append(item)
                
                total_action_paras = sum([item['para_count'] for item in action_needed])
                
                insights_text = f"""
                <b>Summary of MCM Decisions:</b><br/>
                • Total audit paras reviewed: <b>{total_paras}</b><br/>
                • Most common decision: <b>"{most_common_decision['decision']}"</b> ({most_common_decision['para_count']} paras)<br/>
                • Decisions have been recorded for all paras to ensure proper tracking and compliance monitoring.


                                              (SUMMARY OF AUDIT PARAS - FROM NEXT PAGE)
                """
                
                self.story.append(Paragraph(insights_text, insights_style))
            
            self.story.append(Spacer(1, 0.3 * inch))
            
        except Exception as e:
            print(f"Error adding MCM decision insights: {e}")    
    
