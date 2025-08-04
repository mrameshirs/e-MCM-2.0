# visualization_utils.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
from dropbox_utils import read_from_spreadsheet
from config import MCM_DATA_PATH
from plotly.subplots import make_subplots

def wrap_text(text, max_length=15):
    """
    Helper function to wrap long text into multiple lines
    """
    if len(text) <= max_length:
        return text
    
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= max_length:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                # Word is longer than max_length, split it
                lines.append(word)
                current_line = []
                current_length = 0
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '<br>'.join(lines)
# Add this function to visualization_utils.py - REPLACE the existing detailed charts section

def wrap_text_for_labels(text, max_chars_per_line=20, max_lines=3):# for nature of non compliance analysis function 
    """
    Wrap text into multiple lines for chart labels with character limit per line
    """
    if len(text) <= max_chars_per_line:
        return text
    
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        # Check if adding this word would exceed the character limit
        word_length = len(word)
        if current_length + word_length + len(current_line) <= max_chars_per_line:
            current_line.append(word)
            current_length += word_length
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
                
                # Stop if we've reached max lines
                if len(lines) >= max_lines - 1:
                    break
            else:
                # Single word is too long, truncate it
                lines.append(word[:max_chars_per_line-3] + '...')
                break
    
    # Add remaining words to the last line if within limits
    if current_line and len(lines) < max_lines:
        lines.append(' '.join(current_line))
    
    return '<br>'.join(lines)

def get_visualization_data(dbx, selected_period):
    """
    COMPREHENSIVE helper function that extracts ALL visualization data and charts 
    from the Visualizations tab in ui_pco.py. This function preserves EVERY chart,
    analysis, and feature from the original implementation.
    
    Returns vital_stats dict and list of plotly charts with all analysis features.
    """
    try:
        # --- 1. Load and Filter Core Visualization Data (EXACT REPLICA) ---
        df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz_data is None or df_viz_data.empty:
            return None, None
            
        df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
        if df_viz_data.empty:
            return None, None
        
        # --- 2. Data Cleaning and Preparation (CONSOLIDATED - EXACT REPLICA) ---
        amount_cols = [
            'total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs',
            'revenue_involved_rs', 'revenue_recovered_rs', 'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs'
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

        # Unique reports for DAR-level analysis (EXACT REPLICA)
        if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
            df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
        else:
            df_unique_reports = df_viz_data.drop_duplicates(subset=['gstin']).copy()
        
        # --- 3. Monthly Performance Summary Metrics (EXACT REPLICA) ---
        num_dars = df_unique_reports['dar_pdf_path'].nunique()
        total_detected = df_unique_reports.get('Detection in Lakhs', 0).sum()
        total_recovered = df_unique_reports.get('Recovery in Lakhs', 0).sum()
        
        vital_stats = {
            'num_dars': num_dars,
            'total_detected': total_detected,
            'total_recovered': total_recovered
        }
        
        # --- 4. Prepare Performance Summary Table Data (EXACT REPLICA) ---
        categories_order = ['Large', 'Medium', 'Small']
        dar_summary = df_unique_reports.groupby('category').agg(
            dars_submitted=('dar_pdf_path', 'nunique'),
            total_detected=('Detection in Lakhs', 'sum'),
            total_recovered=('Recovery in Lakhs', 'sum')
        )
        df_actual_paras = df_viz_data[df_viz_data['audit_para_number'].notna() & 
                                     (~df_viz_data['audit_para_heading'].astype(str).isin([
                                         "N/A - Header Info Only (Add Paras Manually)", 
                                         "Manual Entry Required", 
                                         "Manual Entry - PDF Error", 
                                         "Manual Entry - PDF Upload Failed"
                                     ]))]
        para_summary = df_actual_paras.groupby('category').size().reset_index(name='num_audit_paras').set_index('category')
        summary_df = pd.concat([dar_summary, para_summary], axis=1).reindex(categories_order).fillna(0)
        summary_df.reset_index(inplace=True)
        
        # Add Status Analysis Data (around line 200)
        
        status_summary = []
        agreed_yet_to_pay_analysis = None
        
        if 'status_of_para' in df_viz_data.columns:
            df_status_analysis = df_viz_data[
                df_viz_data['status_of_para'].notna() & 
                (df_viz_data['status_of_para'] != '') &
                df_viz_data['audit_para_number'].notna()
            ].copy()
            
            if not df_status_analysis.empty:
                status_agg = df_status_analysis.groupby('status_of_para').agg(
                    Para_Count=('status_of_para', 'count'),
                    Total_Detection=('Para Detection in Lakhs', 'sum'),
                    Total_Recovery=('Para Recovery in Lakhs', 'sum')
                ).reset_index()
                
                status_agg['Recovery_Percentage'] = (status_agg['Total_Recovery'] / status_agg['Total_Detection'].replace(0, np.nan)).fillna(0) * 100
                status_summary = status_agg.to_dict('records')
                
                # Get "Agreed yet to pay" analysis
                agreed_yet_to_pay_paras = df_status_analysis[
                    df_status_analysis['status_of_para'].str.contains('Agreed yet to pay', case=False, na=False)
                ].copy()
                
                if not agreed_yet_to_pay_paras.empty:
                    top_5_agreed = agreed_yet_to_pay_paras.nlargest(5, 'Para Detection in Lakhs')
                    agreed_yet_to_pay_analysis = {
                        'top_5_paras': top_5_agreed,
                        'total_paras': len(agreed_yet_to_pay_paras),
                        'total_detection': agreed_yet_to_pay_paras['Para Detection in Lakhs'].sum(),
                        'total_recovery': agreed_yet_to_pay_paras['Para Recovery in Lakhs'].sum()
                    }
         
        
        # --- 5. Generate ALL Charts (COMPREHENSIVE REPLICA) ---
        charts = []
        def style_chart(fig, title_text, y_title, x_title, wrap_x_labels=False):
            """
            Applies a professional, report-style theme to a Plotly chart with corrected layout.
            """
            header_color = '#6F2E2E'
            plot_bg_color = '#FDFBF5'
            border_color = '#5A4A4A'
            font_color = 'white'
        
            # FIX 1: Increase y-axis padding to 20% to prevent TEXT LABELS from overlapping.
            max_y = 0
            for trace in fig.data:
                if trace.y is not None and len(trace.y) > 0:
                    current_max = max(trace.y)
                    if current_max > max_y:
                        max_y = current_max
            # Use a small minimum range in case all values are zero
            #y_range_top = max_y * 1.50 if max_y > 0 else 1
            y_range_top = max_y * 1.25 if max_y > 0 else 1
            # Wrap x-axis labels if requested
            if wrap_x_labels:
                for trace in fig.data:
                    if hasattr(trace, 'x') and trace.x is not None:
                        wrapped_labels = [wrap_text(str(label)) for label in trace.x]
                        trace.x = wrapped_labels
            fig.update_layout(
                paper_bgcolor=plot_bg_color,
                plot_bgcolor=plot_bg_color,
                font=dict(family="serif", color=border_color, size=12),
                #margin=dict(l=60, r=40, t=80, b=60),
                #margin=dict(l=60, r=20, t=20, b=60),
                margin=dict(l=60, r=20, t=20, b=80 if wrap_x_labels else 60),
                showlegend=True,  # Remove default title area
        
                shapes=[
                    dict(
                        type="rect", xref="paper", yref="paper",
                        x0=0, y0=0.9, x1=1, y1=1,
                        fillcolor=header_color, layer="below", line_width=0,
                    ),
                    dict(
                        type="rect", xref="paper", yref="paper",
                        x0=0, y0=0, x1=1, y1=0.9,
                        layer="below",
                        line=dict(color=border_color, width=2),
                        fillcolor=plot_bg_color
                    )
                ],
                
                # Add title as annotation instead
                annotations=[
                    dict(
                        text=f'<b>{title_text}</b>',
                        x=0.5, y=0.95,
                        xref='paper', yref='paper',
                        xanchor='center', yanchor='middle',
                        font=dict(family="Helvetica" , size=14, color=font_color),
                        showarrow=False
                    )
                ],
                
                xaxis_type='category',
                #yaxis=dict(gridcolor='#D3D3D3', range=[0, y_range_top]),
                yaxis=dict(
                    gridcolor='#D3D3D3', 
                    range=[0, y_range_top],
                    domain=[0, 0.85]  # ← CRITICAL FIX: Limit y-axis to 85% of plot area to avoid overlapping of grid lines on top heading rectangle
                ),
                xaxis=dict(showgrid=False),
                legend=dict(x=0.05, y=0.85, bgcolor='rgba(0,0,0,0)')
            )
            
            # FIX 2: Use a more direct method to set axis titles, preventing raw column names.
            #fig.update_xaxes(title_text=f'<b>{x_title}</b>', title_font_family="serif", title_font_size=14)
            
            #fig.update_yaxes(title_text=f'<b>{y_title}</b>', title_font_family="serif", title_font_size=10, tickfont_size=6)
            fig.update_xaxes(
                title_text=f'<b>{x_title}</b>', 
                title_font_family="serif", 
                title_font_size=14,
                tickangle=0,
                tickfont=dict(size=10, family="serif", color='#5A4A4A')
            )
            
            fig.update_yaxes(
                title_text=f'<b>{y_title}</b>', 
                title_font_family="serif", 
                title_font_size=14,
                tickfont=dict(size=10, family="serif", color='#5A4A4A')
            )
            fig.update_xaxes(tickangle=30)
            fig.update_traces(
                marker_line_color=border_color,
                marker_line_width=1.5,
                textposition="outside",
                cliponaxis=False
            )
            return fig
        # CHART 1: Performance Summary by Category (Bar Chart)
        if not summary_df.empty:
            # FIX: Filter out categories with zero detection to prevent ZeroDivisionError
            summary_df_filtered = summary_df[summary_df['total_detected'] > 0]
            if not summary_df_filtered.empty:
                fig1 = px.bar(summary_df_filtered, x='category', y='total_detected', 
                             title="🎯 Detection Amount by Taxpayer Category",
                             color='category',
                             text_auto='.2f',
                             color_discrete_sequence=['#3A86FF', '#3DCCC7', '#90E0EF'])
                fig1 = style_chart(fig1, "Detection Amount by Taxpayer Category", "Detection (₹ Lakhs)", "Category")
                charts.append(fig1)
                # fig1.update_layout(
                #     title_x=0.5, 
                #     xaxis_title="Category", 
                #     yaxis_title="Detection (₹ Lakhs)",
                #     paper_bgcolor='#F0F2F6', 
                #     plot_bgcolor='#FFFFFF',
                #     font=dict(family="sans-serif", color="#333")
                # )
                # fig1.update_traces(textposition="outside", cliponaxis=False)
                # charts.append(fig1)
        
        # CHART 2 & 3: Status of Para Analysis (EXACT REPLICA)
        if 'status_of_para' in df_viz_data.columns:
            df_status_analysis = df_viz_data[
                df_viz_data['status_of_para'].notna() & 
                (df_viz_data['status_of_para'] != '') &
                df_viz_data['audit_para_number'].notna()
            ].copy()
            
            if not df_status_analysis.empty:
                status_agg = df_status_analysis.groupby('status_of_para').agg(
                    Para_Count=('status_of_para', 'count'),
                    Total_Detection=('Para Detection in Lakhs', 'sum'),
                    Total_Recovery=('Para Recovery in Lakhs', 'sum')
                ).reset_index()
                
                # Status Count Chart
                # FIX: Filter out statuses with zero paras
                status_agg_sorted_count = status_agg.sort_values('Para_Count', ascending=False)
                status_agg_sorted_count = status_agg_sorted_count[status_agg_sorted_count['Para_Count'] > 0]
                if not status_agg_sorted_count.empty:
                    fig2 = px.bar(
                        status_agg_sorted_count, x='status_of_para', y='Para_Count',
                        title="📊 Number of Audit Paras by Status", text_auto=True,
                        color_discrete_sequence=px.colors.qualitative.Set3,
                        labels={'status_of_para': 'Status of Para', 'Para_Count': 'Number of Paras'}
                    )
                    # fig2.update_layout(title_x=0.5, height=450, xaxis_title="Status of Para",
                    #                  yaxis_title="Number of Paras", xaxis={'tickangle': 45})
                    # fig2.update_traces(textposition="outside", cliponaxis=False)
                    fig2 = style_chart(fig2, "Number of Audit Paras by Status", "Number of Paras", "Status of Para")
                    charts.append(fig2)
                
                # Status Detection Chart
                # FIX: Filter out statuses with zero detection
                status_agg_sorted_detection = status_agg.sort_values('Total_Detection', ascending=False)
                status_agg_sorted_detection = status_agg_sorted_detection[status_agg_sorted_detection['Total_Detection'] > 0]
                if not status_agg_sorted_detection.empty:
                    fig3 = px.bar(
                        status_agg_sorted_detection, x='status_of_para', y='Total_Detection',
                        text_auto='.2f',
                        color_discrete_sequence=px.colors.qualitative.Pastel1,
                        labels={'status_of_para': 'Status of Para', 'Total_Detection': 'Detection Amount (₹ Lakhs)'}
                    )
                    # fig3.update_layout(title_x=0.5, height=450, xaxis_title="Status of Para",
                    #                  yaxis_title="Detection Amount (₹ Lakhs)", xaxis={'tickangle': 45})
                    # fig3.update_traces(textposition="outside", cliponaxis=False)
                    fig3 = style_chart(fig3, "Detection Amount by Status", "Detection Amount (₹ Lakhs)", "Status of Para", wrap_x_labels=True)
                    charts.append(fig3)
        
        # CHARTS 4-7: Group & Circle Performance (EXACT REPLICA)
        # Group Detection Performance
        group_detection = df_unique_reports.groupby('audit_group_number_str')['Detection in Lakhs'].sum().nlargest(10).reset_index()
        # FIX: Filter zero values
        group_detection = group_detection[group_detection['Detection in Lakhs'] > 0]
        if not group_detection.empty:
            fig4 = px.bar(group_detection, x='audit_group_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Vivid)
            fig4 = style_chart(fig4, "Top 10 Groups by Detection", "Amount (₹ Lakhs)", "Audit Group")
            fig4.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black'), tickangle=0))

            charts.append(fig4)
        
        # Circle Detection Performance
        circle_detection = df_unique_reports.groupby('circle_number_str')['Detection in Lakhs'].sum().sort_values(ascending=False).reset_index()
        circle_detection = circle_detection[circle_detection['circle_number_str'] != '0']
        # FIX: Filter zero values
        circle_detection = circle_detection[circle_detection['Detection in Lakhs'] > 0]
        if not circle_detection.empty:
            fig5 = px.bar(circle_detection, x='circle_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Pastel1)
            fig5 = style_chart(fig5, "Circle-wise Detection", "Amount (₹ Lakhs)", "Audit Circle")
            fig5.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black'), tickangle=0))

            charts.append(fig5)
        
        # Group Recovery Performance
        group_recovery = df_unique_reports.groupby('audit_group_number_str')['Recovery in Lakhs'].sum().nlargest(10).reset_index()
        # FIX: Filter zero values
        group_recovery = group_recovery[group_recovery['Recovery in Lakhs'] > 0]
        if not group_recovery.empty:
            fig6 = px.bar(group_recovery, x='audit_group_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Set2)
            fig6 = style_chart(fig6, "Top 10 Groups by Recovery", "Amount (₹ Lakhs)", "Audit Group")
            fig6.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black'), tickangle=0))
            charts.append(fig6)
        
        # Circle Recovery Performance
        circle_recovery = df_unique_reports.groupby('circle_number_str')['Recovery in Lakhs'].sum().sort_values(ascending=False).reset_index()
        circle_recovery = circle_recovery[circle_recovery['circle_number_str'] != '0']
        # FIX: Filter zero values
        circle_recovery = circle_recovery[circle_recovery['Recovery in Lakhs'] > 0]
        if not circle_recovery.empty:
            fig7 = px.bar(circle_recovery, x='circle_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.G10)
            fig7 = style_chart(fig7, "Circle-wise Recovery", "Amount (₹ Lakhs)", "Audit Circle")
            fig7.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black'), tickangle=0))
            charts.append(fig7)
        # CHARTS 8-10: Taxpayer Classification Analysis (ULTRA COMPACT - NO TITLE)
      
        if 'taxpayer_classification' in df_unique_reports.columns:
            class_counts = df_unique_reports['taxpayer_classification'].value_counts().reset_index()
            class_counts.columns = ['classification', 'count']
            class_counts = class_counts[class_counts['count'] > 0]
            
            # Detection and Recovery aggregations
            class_agg = df_unique_reports.groupby('taxpayer_classification').agg(
                Total_Detection=('Detection in Lakhs', 'sum'),
                Total_Recovery=('Recovery in Lakhs', 'sum')
            ).reset_index()
            
            class_agg_detection = class_agg[class_agg['Total_Detection'] > 0]
            class_agg_recovery = class_agg[class_agg['Total_Recovery'] > 0]
            
            if not class_counts.empty:
                # Create subplots - 3 pie charts in one row (ULTRA COMPACT)
                fig_combined = make_subplots(
                    rows=1, cols=3,
                    subplot_titles=[
                        "<b>Distribution of DARs</b>",
                        "<b>Detection Amount</b>", 
                        "<b>Recovery Amount</b>"
                    ],
                    specs=[[{"type": "domain"}, {"type": "domain"}, {"type": "domain"}]],
                    horizontal_spacing=0.01,  # Minimal spacing for ultra compact look
                )
                
                # Enhanced color schemes for better contrast against gradient
                colors_distribution = ['#1A365D', '#2C5282', '#3182CE', '#4299E1', '#63B3ED']  # Deeper blues
                colors_detection = ['#742A2A', '#C53030', '#E53E3E', '#F56565', '#FC8181']    # Richer reds
                colors_recovery = ['#22543D', '#2F855A', '#38A169', '#48BB78', '#68D391']     # Deeper greens
                
                # Chart 1: Count Distribution (Left) - MAXIMIZED DOMAIN
                fig_combined.add_trace(
                    go.Pie(
                        labels=class_counts['classification'],
                        values=class_counts['count'],
                        name="DAR Count",
                        marker=dict(colors=colors_distribution, line=dict(color='white', width=2)),
                        textinfo='label+percent',
                        textfont=dict(size=11, color='white', family='Helvetica-Bold'),
                        textposition='inside',
                        pull=[0.02] * len(class_counts),  # Even smaller pull for ultra compact
                        hole=0,
                        domain=dict(x=[0.0, 0.33], y=[0.0, 1.0])  # Full space utilization
                    ),
                    row=1, col=1
                )
                
                # Chart 2: Detection Amount (Center) - MAXIMIZED DOMAIN
                if not class_agg_detection.empty:
                    fig_combined.add_trace(
                        go.Pie(
                            labels=class_agg_detection['taxpayer_classification'],
                            values=class_agg_detection['Total_Detection'],
                            name="Detection",
                            marker=dict(colors=colors_detection, line=dict(color='white', width=2)),
                            textinfo='label+percent',
                            textfont=dict(size=11, color='white', family='Helvetica-Bold'),
                            textposition='inside',
                            pull=[0.02] * len(class_agg_detection),
                            hole=0,
                            domain=dict(x=[0.33, 0.67], y=[0.0, 1.0])  # Full height usage
                        ),
                        row=1, col=2
                    )
                
                # Chart 3: Recovery Amount (Right) - MAXIMIZED DOMAIN
                if not class_agg_recovery.empty:
                    fig_combined.add_trace(
                        go.Pie(
                            labels=class_agg_recovery['taxpayer_classification'],
                            values=class_agg_recovery['Total_Recovery'],
                            name="Recovery",
                            marker=dict(colors=colors_recovery, line=dict(color='white', width=2)),
                            textinfo='label+percent',
                            textfont=dict(size=11, color='white', family='Helvetica-Bold'),
                            textposition='inside',
                            pull=[0.02] * len(class_agg_recovery),
                            hole=0,
                            domain=dict(x=[0.67, 1.0], y=[0.0, 1.0])  # Full space usage
                        ),
                        row=1, col=3
                    )
                
                # ULTRA COMPACT LAYOUT - Gradient background, bold headings
                fig_combined.update_layout(
                    # NO TITLE - Removed completely for maximum compactness
                    paper_bgcolor='#f8f9fa',  # Light gradient base
                    plot_bgcolor='rgba(248, 249, 250, 0.8)',
                    font=dict(family="Helvetica-Bold", color='#2C3E50', size=10),
                    
                    # ULTRA COMPACT DIMENSIONS - Minimal margins
                    width=1000,   # Further reduced width
                    height=320,   # Much smaller height without title
                    margin=dict(l=10, r=10, t=10, b=35),  # Slightly more bottom space for bold labels
                    
                    showlegend=False,  # No legend since labels are inside pies
                    autosize=False,
                    
                    # ENHANCED GRADIENT BACKGROUND using shapes
                    shapes=[
                        dict(
                            type="rect",
                            xref="paper", yref="paper",
                            x0=0, y0=0, x1=1, y1=1,
                            fillcolor="rgba(52, 152, 219, 0.1)",  # Light blue gradient overlay
                            layer="below",
                            line_width=0,
                        ),
                        dict(
                            type="rect",
                            xref="paper", yref="paper", 
                            x0=0, y0=0.7, x1=1, y1=1,
                            fillcolor="rgba(155, 89, 182, 0.05)",  # Purple gradient top
                            layer="below",
                            line_width=0,
                        ),
                        dict(
                            type="rect",
                            xref="paper", yref="paper",
                            x0=0, y0=0, x1=1, y1=0.3,
                            fillcolor="rgba(46, 204, 113, 0.05)",  # Green gradient bottom
                            layer="below", 
                            line_width=0,
                        )
                    ],
                    
                    # BOLD SUBTITLE positioning at bottom with enhanced styling
                    annotations=[
                        dict(text="<b>📊 DISTRIBUTION</b>", x=0.17, y=0.02, 
                             font=dict(size=12, color='#2C3E50', family='Helvetica-Bold'), 
                             showarrow=False,
                             bgcolor="rgba(255, 255, 255, 0.8)",  # Semi-transparent background
                             bordercolor="#3498DB",
                             borderwidth=1,
                             borderpad=4),
                        dict(text="<b>💰 DETECTION</b>", x=0.5, y=0.02,
                             font=dict(size=12, color='#2C3E50', family='Helvetica-Bold'), 
                             showarrow=False,
                             bgcolor="rgba(255, 255, 255, 0.8)",
                             bordercolor="#E74C3C", 
                             borderwidth=1,
                             borderpad=4),
                        dict(text="<b>💎 RECOVERY</b>", x=0.83, y=0.02,
                             font=dict(size=12, color='#2C3E50', family='Helvetica-Bold'), 
                             showarrow=False,
                             bgcolor="rgba(255, 255, 255, 0.8)",
                             bordercolor="#27AE60",
                             borderwidth=1,
                             borderpad=4)
                    ]
                )
                
                # ENHANCED STYLING - Add subtle shadows and better borders
                for i in range(len(fig_combined.data)):
                    fig_combined.data[i].marker.line = dict(color='white', width=2)
                    
                print(f"Ultra compact three pie charts (no title) created successfully!")
                charts.append(fig_combined)
                charts.append(fig_combined)# twice added to maintain the chart count and id matching
                charts.append(fig_combined)
       
        # CHARTS 10-12: Nature of Compliance Analysis (EXACT REPLICA)
        CLASSIFICATION_CODES_DESC = {
            'TP': 'TAX PAYMENT DEFAULTS', 'RC': 'REVERSE CHARGE MECHANISM',
            'IT': 'INPUT TAX CREDIT VIOLATIONS', 'IN': 'INTEREST LIABILITY DEFAULTS',
            'RF': 'RETURN FILING NON-COMPLIANCE', 'PD': 'PROCEDURAL & DOCUMENTATION',
            'CV': 'CLASSIFICATION & VALUATION', 'SS': 'SPECIAL SITUATIONS',
            'PG': 'PENALTY & GENERAL COMPLIANCE'
        }
        
        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        if not df_paras.empty:
            df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
            major_code_agg = df_paras.groupby('major_code').agg(
                Para_Count=('major_code', 'count'),
                Total_Detection=('Para Detection in Lakhs', 'sum'),
                Total_Recovery=('Para Recovery in Lakhs', 'sum')
            ).reset_index()
            major_code_agg['description'] = major_code_agg['major_code'].map(CLASSIFICATION_CODES_DESC)
            
            # Paras by Classification
            fig10 = px.bar(major_code_agg, x='description', y='Para_Count', text_auto=True,
                          # title="Number of Audit Paras by Classification",
                          labels={'description': 'Classification Code', 'Para_Count': 'Number of Paras'},
                          color_discrete_sequence=['#1f77b4'])
            # Add this line to reduce Y-axis tick values font size
            fig10.update_layout(yaxis_tickfont_size=10, xaxis_tickfont_size=10)

            # fig10.update_layout(title_x=0.5, xaxis_title="Categorisation Code", yaxis_title="Number of Paras")
            # fig10.update_traces(textposition="outside", cliponaxis=False)
            fig10 = style_chart(fig10, "Number of Audit Paras by Categorisation", "Number of Paras", "Categorisation Code", wrap_x_labels=True)
            charts.append(fig10)
            
            # Detection by Classification
            fig11 = px.bar(major_code_agg, x='description', y='Total_Detection', text_auto='.2f',
                          # title="Detection Amount by Classification",
                          labels={'description': 'Classification Code', 'Total_Detection': 'Detection (₹ Lakhs)'},
                          color_discrete_sequence=['#ff7f0e'])
            # Add this line to reduce Y-axis tick values font size
            fig11.update_layout(yaxis_tickfont_size=10, xaxis_tickfont_size=10)

            # fig11.update_layout(title_x=0.5, xaxis_title="Categorisation Code", yaxis_title="Detection (₹ Lakhs)")
            # fig11.update_traces(textposition="outside", cliponaxis=False)
            fig11 = style_chart(fig11, "Detection Amount by Categorisation", "Detection (₹ Lakhs)", "Categorisation Code", wrap_x_labels=True)
            charts.append(fig11)
            
            # Recovery by Classification
            fig12 = px.bar(major_code_agg, x='description', y='Total_Recovery', text_auto='.2f',
                          # title="Recovery Amount by Classification",
                          labels={'description': 'Classification Code', 'Total_Recovery': 'Recovery (₹ Lakhs)'},
                          color_discrete_sequence=['#2ca02c'])
            # Add this line to reduce Y-axis tick values font size
            fig12.update_layout(yaxis_tickfont_size=10, xaxis_tickfont_size=10)
 
            # fig12.update_layout(title_x=0.5, xaxis_title="Categorisation  Code", yaxis_title="Recovery (₹ Lakhs)")
            # fig12.update_traces(textposition="outside", cliponaxis=False)
            fig12 = style_chart(fig12, "Recovery Amount by Categorisation", "Recovery (₹ Lakhs)", "Categorisation Code", wrap_x_labels=True)
            charts.append(fig12)
        
        # CHARTS 13-14: Treemap Analysis (EXACT REPLICA)
        df_treemap = df_unique_reports.dropna(subset=['category', 'trade_name']).copy()
        color_map = {
            'Large': '#3A86FF',    # Bright Blue
            'Medium': '#3DCCC7',   # Turquoise
            'Small': '#90E0EF',    # Light Blue/Cyan
            'Unknown': '#CED4DA'   # Light Grey
        }
        
        # Detection Treemap - NOW STYLED
        df_det_treemap = df_treemap[df_treemap['Detection in Lakhs'] > 0]
        if not df_det_treemap.empty:
            try:
                fig13 = px.treemap(
                    df_det_treemap, path=[px.Constant("All Detections"), 'category', 'trade_name'],
                    values='Detection in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                # --- Add this line to change the path bar font color ---
                fig13.update_traces(pathbar=dict(textfont=dict(color='white')))

                # Apply styling for treemap
                fig13.update_layout(
                    #title=dict(text="<b>Detection by Trade Name</b>", x=0.5, font=dict(size=14, color='#5A4A4A')),
                    paper_bgcolor='#FDFBF5',
                    font=dict(family="serif", color='#5A4A4A', size=12),
                    margin=dict(l=5, r=5, t=5, b=5)
                )
                fig13.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Detection: %{value:,.2f} L<extra></extra>"
                )
                charts.append(fig13)
            except Exception:
                pass  # Skip treemap if it fails
        
        # Recovery Treemap - NOW STYLED
        df_rec_treemap = df_treemap[df_treemap['Recovery in Lakhs'] > 0]
        if not df_rec_treemap.empty:
            try:
                fig14 = px.treemap(
                    df_rec_treemap, path=[px.Constant("All Recoveries"), 'category', 'trade_name'],
                    values='Recovery in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                # --- Add this line to change the path bar font color ---
                fig14.update_traces(pathbar=dict(textfont=dict(color='white')))

                # Apply styling for treemap
                fig14.update_layout(
                    #title=dict(text="<b>Recovery by Trade Name</b>", x=0.5, font=dict(size=14, color='#5A4A4A')),
                    paper_bgcolor='#FDFBF5',
                    font=dict(family="serif", color='#5A4A4A', size=12),
                    margin=dict(l=5, r=5, t=5, b=5)
                )
                fig14.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Recovery: %{value:,.2f} L<extra></extra>"
                )
                charts.append(fig14)
            except Exception:
                pass  # Skip treemap if it fails
        
        # CHARTS 15-18: Risk Parameter Analysis (COMPREHENSIVE REPLICA)
        GST_RISK_PARAMETERS = {
            "P01": "Sale turnover (GSTR-3B) is less than the purchase turnover", 
            "P02": "IGST paid on import is more than the ITC availed in GSTR-3B",
            "P03": "High ratio of nil-rated/exempt supplies to total turnover",
            "P04": "High ratio of zero-rated supplies to total turnover", 
            "P05": "High ratio of inward supplies liable to reverse charge to total turnover",
            "P06": "Mismatch between RCM liability declared and ITC claimed on RCM",
            "P07": "High ratio of tax paid through ITC to total tax payable",
            "P08": "Low ratio of tax payment in cash to total tax liability",
            "P09": "Decline in average monthly taxable turnover in GSTR-3B",
            "P10": "High ratio of non-GST supplies to total turnover", 
            "P11": "Taxpayer has filed more than six GST returns late",
            "P12": "Taxpayer has not filed three consecutive GSTR-3B returns",
            "P13": "Taxpayer has both SEZ and non-SEZ registrations with the same PAN in the same state",
            "P14": "Positive difference between ITC availed in GSTR-3B and ITC available in GSTR-2A",
            "P15": "Positive difference between ITC on import of goods (GSTR-3B) and IGST paid at Customs",
            "P16": "Low ratio of tax paid under RCM compared to ITC claimed on RCM",
            "P17": "High ratio of ISD credit to total ITC availed",
            "P18": "Low ratio of ITC reversed to total ITC availed",
            "P19": "Mismatch between the proportion of exempt supplies and the proportion of ITC reversed",
            "P20": "Mismatch between the taxable value of exports in GSTR-1 and the IGST value in shipping bills (Customs data)",
            "P21": "High ratio of zero-rated supply to SEZ to total GST turnover",
            "P22": "High ratio of deemed exports to total GST turnover", 
            "P23": "High ratio of zero-rated supply (other than exports) to total supplies",
            "P24": "Risk associated with other linked GSTINs of the same PAN",
            "P25": "High amount of IGST Refund claimed (for Risky Exporters)",
            "P26": "High amount of LUT Export Refund claimed (for Risky Exporters)",
            "P27": "High amount of Refund claimed due to inverted duty structure (for Risky Exporters)",
            "P28": "Taxpayer is flagged in Red Flag Reports of DGARM",
            "P29": "High ratio of taxable turnover as per ITC-04 vs. total turnover in GSTR-3B", 
            "P30": "Taxpayer was selected for audit on risk criteria last year but was not audited",
            "P31": "High ratio of Credit Notes to total taxable turnover value",
            "P32": "High ratio of Debit Notes to total taxable turnover value",
            "P33": "Substantial difference between turnover in GSTR-3B and turnover in Income Tax Return (ITR)",
            "P34": "Negligible income tax payment despite substantial turnover in GSTR-3B"
        }
        risk_summary = []
        gstins_with_risk_data = 0
        paras_linked_to_risks = 0
        
        if 'risk_flags_data' in df_viz_data.columns:
            risk_para_records = []
            valid_risk_data = df_viz_data[
                df_viz_data['risk_flags_data'].notna() & 
                (df_viz_data['risk_flags_data'] != '') & 
                (df_viz_data['risk_flags_data'] != '[]') &
                (df_viz_data['risk_flags_data'].astype(str) != 'nan')
            ]
            
            # Process risk data (EXACT REPLICA of processing logic)
            for idx, row in valid_risk_data.iterrows():
                try:
                    risk_data_str = str(row['risk_flags_data']).strip()
                    
                    if risk_data_str.startswith('[') or risk_data_str.startswith('{'):
                        risk_list = json.loads(risk_data_str)
                    else:
                        risk_list = [{"risk_flag": risk_data_str, "paras": [row.get('audit_para_number', 1)]}]
                    
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
                        risk_flag = str(risk_list)
                        risk_para_records.append({
                            "gstin": row['gstin'], 
                            "audit_para_number": row.get('audit_para_number', 1), 
                            "risk_flag": risk_flag
                        })
                except Exception:
                    continue
            
            if risk_para_records:
                df_risk_long = pd.DataFrame(risk_para_records)
                df_risk_long['audit_para_number'] = pd.to_numeric(df_risk_long['audit_para_number'], errors='coerce')
                
                df_risk_analysis = pd.merge(
                    df_viz_data.dropna(subset=['audit_para_number']), 
                    df_risk_long, 
                    on=['gstin', 'audit_para_number'], 
                    how='inner'
                )
                
                if not df_risk_analysis.empty:
                    # risk_agg = df_risk_analysis.groupby('risk_flag').agg(
                    #     Para_Count=('risk_flag', 'count'),
                    #     Total_Detection=('Para Detection in Lakhs', 'sum'),
                    #     Total_Recovery=('Para Recovery in Lakhs', 'sum')
                    # ).reset_index()
                    risk_agg = df_risk_analysis.groupby('risk_flag').agg(
                        Para_Count=('audit_para_number', 'nunique'),  # ← FIXED: Unique paras per risk
                        Total_Detection=('Para Detection in Lakhs', 'sum'),
                        Total_Recovery=('Para Recovery in Lakhs', 'sum')
                    ).reset_index()
                    # Risk Paras Chart
                    risk_agg_sorted_count = risk_agg.sort_values('Para_Count', ascending=False).head(5)
                    fig15 = px.bar(
                        risk_agg_sorted_count, 
                        x='risk_flag', 
                        y='Para_Count', 
                        text_auto=True,
                        # title="Top 5 Risk Flags by Number of Audit Paras",
                        color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig15.update_layout(xaxis_tickfont=dict(size=14, family='Helvetica', color='black'))

                    # fig15.update_traces(textposition="outside", cliponaxis=False)
                    fig15 = style_chart(fig15, "Top 5 Risk Flags by Number of Audit Paras", "Number of Paras", "Risk Flag", wrap_x_labels=True)
                    fig15.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black')))


                    charts.append(fig15)
                    
                    # Risk Detection Chart
                    risk_agg_sorted_det = risk_agg.sort_values('Total_Detection', ascending=False).head(10)
                    if not risk_agg_sorted_det.empty and risk_agg_sorted_det['Total_Detection'].sum() > 0:
                        fig16 = px.bar(
                            risk_agg_sorted_det, 
                            x='risk_flag', 
                            y='Total_Detection', 
                            text_auto='.2f',
                            # title="Top 10 Detection Amount by Risk Flag",
                            color_discrete_sequence=px.colors.qualitative.Prism
                        )
                        
                        # fig16.update_traces(textposition="outside", cliponaxis=False)
                        fig16 = style_chart(fig16, "Top 5 Detection Amount by Risk Flag", "Amount (₹ Lakhs)", "Risk Flag", wrap_x_labels=True)
                        fig16.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black')))

                        charts.append(fig16)
                    
                    # Risk Recovery Chart
                    risk_agg_sorted_rec = risk_agg.sort_values('Total_Recovery', ascending=False).head(5)
                    if not risk_agg_sorted_rec.empty and risk_agg_sorted_rec['Total_Recovery'].sum() > 0:
                        fig17 = px.bar(
                            risk_agg_sorted_rec, 
                            x='risk_flag', 
                            y='Total_Recovery', 
                            text_auto='.2f',
                            # title="Top 5 Recovery Amount by Risk Flag",
                            color_discrete_sequence=px.colors.qualitative.Safe
                        )
                     
                        # fig17.update_traces(textposition="outside", cliponaxis=False)
                        fig17 = style_chart(fig17, "Top 5 Recovery Amount by Risk Flag", "Amount (₹ Lakhs)", "Risk Flag", wrap_x_labels=True)
                        fig17.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black')))

                        charts.append(fig17)
                    
                    # Risk Recovery Percentage Chart
                    risk_agg['Percentage_Recovery'] = (risk_agg['Total_Recovery'] / risk_agg['Total_Detection'].replace(0, np.nan)).fillna(0) * 100
                    risk_with_recovery = risk_agg[risk_agg['Total_Detection'] > 0]
                    if not risk_with_recovery.empty:
                        risk_agg_sorted_perc = risk_with_recovery.sort_values('Percentage_Recovery', ascending=False).head(5)
                        fig18 = px.bar(
                            risk_agg_sorted_perc, 
                            x='risk_flag', 
                            y='Percentage_Recovery',
                            # title="Top 5 Percentage Recovery by Risk Flag",
                            color='Percentage_Recovery', 
                            color_continuous_scale=px.colors.sequential.Greens
                        )
                        fig18 = style_chart(fig18, "Top 5 Percentage Recovery by Risk Flag", "Recovery (%)", "Risk Flag", wrap_x_labels=True)
    
                        fig18.update_traces(texttemplate='%{y:.1f}%', textposition='outside', cliponaxis=False)
                        fig18.update_layout(coloraxis_showscale=False)
                        fig18.update_layout(xaxis=dict(tickfont=dict(size=14, family='Helvetica-Bold', color='black')))

                        charts.append(fig18)
         
                    risk_agg = df_risk_analysis.groupby('risk_flag').agg(
                        #Para_Count=('risk_flag', 'count'),#to correct the aggregate no of DARs
                        Para_Count=('audit_para_number', 'nunique'),
                        Total_Detection=('Para Detection in Lakhs', 'sum'),
                        Total_Recovery=('Para Recovery in Lakhs', 'sum')
                    ).reset_index()
                    
                    risk_agg['Percentage_Recovery'] = (risk_agg['Total_Recovery'] / risk_agg['Total_Detection'].replace(0, np.nan)).fillna(0) * 100
                    risk_agg['description'] = risk_agg['risk_flag'].map(GST_RISK_PARAMETERS).fillna("Unknown Risk Code")
                    risk_summary = risk_agg.to_dict('records')
                    
                    gstins_with_risk_data = valid_risk_data['gstin'].nunique()
                    paras_linked_to_risks = df_risk_analysis[['gstin', 'audit_para_number']].drop_duplicates().shape[0]
                    
        # CHARTS 19+: Detailed Classification Analysis (Multiple Charts for nc_tab2 and nc_tab3)
        if not df_paras.empty:
            
            def wrap_text_for_labels(text, max_chars_per_line=18, max_lines=3):
                """Wrap text into multiple lines for chart labels"""
                if len(text) <= max_chars_per_line:
                    return text
                
                words = text.split()
                lines = []
                current_line = []
                current_length = 0
                
                for word in words:
                    word_length = len(word)
                    if current_length + word_length + len(current_line) <= max_chars_per_line:
                        current_line.append(word)
                        current_length += word_length
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                            current_line = [word]
                            current_length = word_length
                            
                            if len(lines) >= max_lines - 1:
                                break
                        else:
                            lines.append(word[:max_chars_per_line-3] + '...')
                            break
                
                if current_line and len(lines) < max_lines:
                    lines.append(' '.join(current_line))
                
                return '<br>'.join(lines)
            
            def create_empty_chart(code, chart_type, classification_desc):
                """Create an empty chart when no data is available"""
                # Create a dummy dataframe with a single bar showing "No Data"
                df_empty = pd.DataFrame({
                    'category': ['No Data Available'],
                    'value': [0],
                    'combined_label': ['No Data<br>Available']
                })
                
                color = '#3498db' if chart_type == 'detection' else '#27AE60'
                y_column = f'Para {chart_type.title()} in Lakhs'
                df_empty[y_column] = [0]
                
                fig_empty = px.bar(
                    df_empty,
                    x='combined_label',
                    y=y_column,
                    color_discrete_sequence=[color]
                )
                
                # Apply professional styling
                fig_empty = style_chart(
                    fig_empty,
                    title_text=f"{chart_type.title()} for {code} - {classification_desc}",
                    y_title=f"{chart_type.title()} (₹ Lakhs)",
                    x_title="Detailed Code",
                    wrap_x_labels=True
                )
                
                # Override for empty chart styling
                fig_empty.update_layout(
                    title="",
                    xaxis_title="",
                    yaxis_title="",
                    xaxis=dict(
                        tickangle=-30,
                        tickfont=dict(size=8, family="serif", color='#5A4A4A'),
                        showgrid=False
                    ),
                    yaxis=dict(
                        range=[0, 1],  # Set a small range so the chart isn't completely flat
                        tickfont=dict(size=10, family="serif", color='#5A4A4A')
                    ),
                    margin=dict(l=60, r=20, t=20, b=120),
                    height=380,
                    # Add annotation for "No Data"
                    annotations=[
                        dict(
                            text="No Data Available",
                            x=0.5, y=0.5,
                            xref='paper', yref='paper',
                            showarrow=False,
                            font=dict(size=14, color='#666666'),
                            bgcolor='rgba(255,255,255,0.8)',
                            bordercolor='#CCCCCC',
                            borderwidth=1
                        )
                    ]
                )
                
                # Remove the bar data values text
                fig_empty.update_traces(texttemplate='')
                
                return fig_empty
            
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
            
            # ALL CLASSIFICATION CODES - ensure we always have 9 charts
            all_classification_codes = ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']
            
            # DETAILED DETECTION CHARTS - ALWAYS 9 CHARTS
            print("Generating detection charts...")
            for code in all_classification_codes:
                df_filtered = df_paras[df_paras['major_code'] == code].copy()
                
                if not df_filtered.empty:
                    df_agg = df_filtered.groupby('para_classification_code')['Para Detection in Lakhs'].sum().reset_index()
                    df_agg = df_agg[df_agg['Para Detection in Lakhs'] > 0]
                else:
                    df_agg = pd.DataFrame()  # Empty dataframe
                
                if not df_agg.empty:
                    # Create normal chart with data
                    df_agg['description'] = df_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
                    df_agg['combined_label'] = df_agg.apply(
                        lambda row: f"{row['para_classification_code']}<br>{wrap_text_for_labels(row['description'] or 'Unknown', max_chars_per_line=18, max_lines=3)}", 
                        axis=1
                    )
                    
                    fig_detailed_det = px.bar(
                        df_agg, 
                        x='combined_label',
                        y='Para Detection in Lakhs',
                        text_auto='.2f',
                        color_discrete_sequence=['#3498db']
                    )
                    
                    # Apply professional styling
                    fig_detailed_det = style_chart(
                        fig_detailed_det, 
                        title_text=f"Detection for {code} - {CLASSIFICATION_CODES_DESC.get(code, '')}",
                        y_title="Detection (₹ Lakhs)", 
                        x_title="Detailed Code",
                        wrap_x_labels=True
                    )
                    
                    # Override for detailed charts
                    fig_detailed_det.update_layout(
                        title="",
                        xaxis_title="",
                        yaxis_title="",
                        xaxis=dict(
                            tickangle=-30,
                            tickfont=dict(size=8, family="serif", color='#5A4A4A'),
                            showgrid=False
                        ),
                        margin=dict(l=60, r=20, t=20, b=120),
                        height=380
                    )
                    
                    charts.append(fig_detailed_det)
                    print(f"Added detection chart for {code} with data")
                    
                else:
                    # Create empty chart
                    fig_empty = create_empty_chart(code, 'detection', CLASSIFICATION_CODES_DESC.get(code, ''))
                    charts.append(fig_empty)
                    print(f"Added EMPTY detection chart for {code}")
            
            # DETAILED RECOVERY CHARTS - ALWAYS 9 CHARTS  
            print("Generating recovery charts...")
            for code in all_classification_codes:
                df_filtered = df_paras[df_paras['major_code'] == code].copy()
                
                if not df_filtered.empty:
                    df_agg = df_filtered.groupby('para_classification_code')['Para Recovery in Lakhs'].sum().reset_index()
                    df_agg = df_agg[df_agg['Para Recovery in Lakhs'] > 0]
                else:
                    df_agg = pd.DataFrame()  # Empty dataframe
                
                if not df_agg.empty:
                    # Create normal chart with data
                    df_agg['description'] = df_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
                    df_agg['combined_label'] = df_agg.apply(
                        lambda row: f"{row['para_classification_code']}<br>{wrap_text_for_labels(row['description'] or 'Unknown', max_chars_per_line=18, max_lines=3)}", 
                        axis=1
                    )
                    
                    fig_detailed_rec = px.bar(
                        df_agg, 
                        x='combined_label',
                        y='Para Recovery in Lakhs',
                        text_auto='.2f',
                        color_discrete_sequence=['#27AE60']
                    )
                    
                    # Apply professional styling
                    fig_detailed_rec = style_chart(
                        fig_detailed_rec, 
                        title_text=f"Recovery for {code} - {CLASSIFICATION_CODES_DESC.get(code, '')}",
                        y_title="Recovery (₹ Lakhs)", 
                        x_title="Detailed Code",
                        wrap_x_labels=True
                    )
                    
                    # Override for detailed charts
                    fig_detailed_rec.update_layout(
                        title="",
                        xaxis_title="",
                        yaxis_title="",
                        xaxis=dict(
                            tickangle=-30,
                            tickfont=dict(size=8, family="serif", color='#5A4A4A'),
                            showgrid=False
                        ),
                        margin=dict(l=60, r=20, t=20, b=120),
                        height=380
                    )
                    
                    charts.append(fig_detailed_rec)
                    print(f"Added recovery chart for {code} with data")
                    
                else:
                    # Create empty chart
                    fig_empty = create_empty_chart(code, 'recovery', CLASSIFICATION_CODES_DESC.get(code, ''))
                    charts.append(fig_empty)
                    print(f"Added EMPTY recovery chart for {code}")
            
            print(f"Total detailed charts generated: 18 (9 detection + 9 recovery)")
            print("This ensures consistent 2x3 layout on each page")
    
        # ADD THIS SECTION - Pre-process classification data for PDF
        classification_page_data = None
        if not df_paras.empty:  # df_paras is already created in your classification analysis
            # Calculate comprehensive stats
            total_observations = len(df_paras)
            main_categories_count = df_paras['major_code'].nunique()
            sub_categories_count = df_paras['para_classification_code'].nunique()
            
            # Category-wise detailed stats  
            category_stats = df_paras.groupby('major_code').agg(
                para_count=('major_code', 'count'),
                total_detection=('Para Detection in Lakhs', 'sum'),
                total_recovery=('Para Recovery in Lakhs', 'sum')
            ).reset_index()
            
            classification_page_data = {
                'total_observations': total_observations,
                'main_categories_count': main_categories_count,
                'sub_categories_count': sub_categories_count,
                'category_stats': category_stats.to_dict('records'),
                'coverage_percentage': 100 if total_observations > 0 else 0
            }
            
            print(f"DEBUG: Classification data processed - {total_observations} observations, {main_categories_count} main categories")
        # ADD SECTORAL SUMMARY DATA (after chart generation)
        sectoral_summary = []
        if 'taxpayer_classification' in df_unique_reports.columns:
            sectoral_agg = df_unique_reports.groupby('taxpayer_classification').agg(
                dar_count=('dar_pdf_path', 'nunique'),
                total_detection=('Detection in Lakhs', 'sum'),
                total_recovery=('Recovery in Lakhs', 'sum')
            ).reset_index()
            sectoral_agg.columns = ['classification', 'dar_count', 'total_detection', 'total_recovery']
            sectoral_summary = sectoral_agg.sort_values('total_detection', ascending=False).to_dict('records')
            print(f"DEBUG: sectoral_summary length: {len(sectoral_summary)}")
            print(f"DEBUG: sectoral_summary content: {sectoral_summary}")
            print(f"DEBUG: taxpayer_classification column exists: {'taxpayer_classification' in df_unique_reports.columns}")
            
            if 'taxpayer_classification' in df_unique_reports.columns:
                print(f"DEBUG: unique classifications: {df_unique_reports['taxpayer_classification'].value_counts()}")
        # ADD CLASSIFICATION SUMMARY DATA (after chart generation)
        classification_summary = []
        if not df_paras.empty:  # df_paras is created in the classification analysis section
            classification_agg = df_paras.groupby('major_code').agg(
                Para_Count=('major_code', 'count'),
                Total_Detection=('Para Detection in Lakhs', 'sum'),
                Total_Recovery=('Para Recovery in Lakhs', 'sum')
            ).reset_index()
            classification_agg['Percentage_Recovery'] = (
                classification_agg['Total_Recovery'] / 
                classification_agg['Total_Detection'].replace(0, np.nan)
            ).fillna(0) * 100
            classification_summary = classification_agg.sort_values('Total_Detection', ascending=False).to_dict('records')        
        # ADD THIS SECTION - Pre-process classification data for PDF
        classification_page_data = None
        if not df_paras.empty:  # df_paras is already created in your classification analysis
            # Calculate comprehensive stats
            total_observations = len(df_paras)
            main_categories_count = df_paras['major_code'].nunique()
            sub_categories_count = df_paras['para_classification_code'].nunique()
            
            # Category-wise detailed stats  
            category_stats = df_paras.groupby('major_code').agg(
                para_count=('major_code', 'count'),
                total_detection=('Para Detection in Lakhs', 'sum'),
                total_recovery=('Para Recovery in Lakhs', 'sum')
            ).reset_index()
            
            classification_page_data = {
                'total_observations': total_observations,
                'main_categories_count': main_categories_count,
                'sub_categories_count': sub_categories_count,
                'category_stats': category_stats.to_dict('records'),
                'coverage_percentage': 100 if total_observations > 0 else 0
            }
            
            print(f"DEBUG: Classification data processed - {total_observations} observations, {main_categories_count} main categories")
        # ADD TOP TAXPAYERS ANALYSIS DATA (before return statement)
        # top_taxpayers_data = {}
        
        # # Get top taxpayers by detection
        # if not df_unique_reports.empty:
        #     # Top Detection Taxpayers
        #     top_detection = df_unique_reports.nlargest(10, 'Detection in Lakhs')[
        #         ['trade_name', 'category', 'Detection in Lakhs', 'Recovery in Lakhs', 'audit_group_number_str']
        #     ].copy()
            
        #     # Add recovery percentage
        #     top_detection['recovery_percentage'] = (
        #         top_detection['Recovery in Lakhs'] / 
        #         top_detection['Detection in Lakhs'].replace(0, np.nan)
        #     ).fillna(0) * 100
            
        #     # Rename columns for consistency
        #     top_detection.columns = ['trade_name', 'category', 'total_detection', 'total_recovery', 'audit_group', 'recovery_percentage']
            
        #     # Top Recovery Taxpayers
        #     top_recovery = df_unique_reports[df_unique_reports['Recovery in Lakhs'] > 0].nlargest(10, 'Recovery in Lakhs')[
        #         ['trade_name', 'category', 'Detection in Lakhs', 'Recovery in Lakhs', 'audit_group_number_str']
        #     ].copy()
            
        #     # Add recovery percentage for top recovery
        #     top_recovery['recovery_percentage'] = (
        #         top_recovery['Recovery in Lakhs'] / 
        #         top_recovery['Detection in Lakhs'].replace(0, np.nan)
        #     ).fillna(0) * 100
            
        #     # Rename columns for consistency
        #     top_recovery.columns = ['trade_name', 'category', 'total_detection', 'total_recovery', 'audit_group', 'recovery_percentage']
            
        #     top_taxpayers_data = {
        #         'top_detection': top_detection.to_dict('records'),
        #         'top_recovery': top_recovery.to_dict('records')
        #     }
        def create_top_taxpayers_data_safe(df_unique_reports):
            """Create top taxpayers data with bulletproof error handling"""
            result = {'top_detection': [], 'top_recovery': []}
            
            try:
                if df_unique_reports is None or df_unique_reports.empty:
                    print("WARNING: df_unique_reports is empty")
                    return result
                
                required_cols = ['trade_name', 'category', 'Detection in Lakhs', 'Recovery in Lakhs']
                if not all(col in df_unique_reports.columns for col in required_cols):
                    print(f"ERROR: Missing required columns. Available: {list(df_unique_reports.columns)}")
                    return result
                
                # Top Detection - Safe processing
                detection_data = df_unique_reports[df_unique_reports['Detection in Lakhs'] > 0]
                if not detection_data.empty:
                    top_detection = detection_data.nlargest(10, 'Detection in Lakhs')[required_cols].copy()
                    top_detection['recovery_percentage'] = np.where(
                        top_detection['Detection in Lakhs'] > 0,
                        (top_detection['Recovery in Lakhs'] / top_detection['Detection in Lakhs']) * 100,
                        0
                    )
                    # Rename for consistency
                    top_detection.columns = ['trade_name', 'category', 'total_detection', 'total_recovery', 'recovery_percentage']
                    
                    # CRITICAL: Convert to list immediately and validate
                    detection_records = top_detection.to_dict('records')
                    print(f"Created {len(detection_records)} detection records")
                    if detection_records:
                        print(f"Sample detection record: {detection_records[0]}")
                    result['top_detection'] = detection_records
                
                # Top Recovery - Safe processing
                recovery_data = df_unique_reports[df_unique_reports['Recovery in Lakhs'] > 0]
                if not recovery_data.empty:
                    top_recovery = recovery_data.nlargest(10, 'Recovery in Lakhs')[required_cols].copy()
                    top_recovery['recovery_percentage'] = np.where(
                        top_recovery['Detection in Lakhs'] > 0,
                        (top_recovery['Recovery in Lakhs'] / top_recovery['Detection in Lakhs']) * 100,
                        0
                    )
                    top_recovery.columns = ['trade_name', 'category', 'total_detection', 'total_recovery', 'recovery_percentage']
                    
                    # CRITICAL: Convert to list immediately and validate
                    recovery_records = top_recovery.to_dict('records')
                    print(f"Created {len(recovery_records)} recovery records")
                    result['top_recovery'] = recovery_records
                
                return result
                
            except Exception as e:
                print(f"ERROR in create_top_taxpayers_data_safe: {e}")
                import traceback
                traceback.print_exc()
                return result
        
        # STEP 3: UPDATE get_visualization_data function
        # Find the top taxpayers section and replace with:
        top_taxpayers_data = create_top_taxpayers_data_safe(df_unique_reports)

        # ADD GROUP PERFORMANCE DATA (for the performance analysis section)
        group_performance_data = []
        if not df_unique_reports.empty:
            # Group performance by detection
            group_performance = df_unique_reports.groupby('audit_group_number_str').agg(
                dar_count=('dar_pdf_path', 'nunique'),
                total_detection=('Detection in Lakhs', 'sum'),
                total_recovery=('Recovery in Lakhs', 'sum')
            ).reset_index()
            
            # Add recovery percentage
            group_performance['recovery_percentage'] = (
                group_performance['total_recovery'] / 
                group_performance['total_detection'].replace(0, np.nan)
            ).fillna(0) * 100
            
            # Rename for consistency
            group_performance.columns = ['audit_group', 'dar_count', 'total_detection', 'total_recovery', 'recovery_percentage']
            
            # Sort by detection and get top performers
            group_performance_data = group_performance.sort_values('total_detection', ascending=False).to_dict('records')
        
        # ENHANCED GROUP PERFORMANCE DATA with Paras Count
        group_performance_data_enhanced = []
        if not df_unique_reports.empty:
            # Get actual paras count from the main data
            df_actual_paras = df_viz_data[
                df_viz_data['audit_para_number'].notna() & 
                (~df_viz_data['audit_para_heading'].astype(str).isin([
                    "N/A - Header Info Only (Add Paras Manually)", 
                    "Manual Entry Required", 
                    "Manual Entry - PDF Error", 
                    "Manual Entry - PDF Upload Failed"
                ]))
            ]
            
            # Group performance with paras count
            group_performance_enhanced = df_unique_reports.groupby('audit_group_number_str').agg(
                dar_count=('dar_pdf_path', 'nunique'),
                total_detection=('Detection in Lakhs', 'sum'),
                total_recovery=('Recovery in Lakhs', 'sum')
            ).reset_index()
            
            # Add paras count for each group
            paras_by_group = df_actual_paras.groupby('audit_group_number_str').size().reset_index(name='paras_count')
            group_performance_enhanced = group_performance_enhanced.merge(
                paras_by_group, 
                on='audit_group_number_str', 
                how='left'
            )
            group_performance_enhanced['paras_count'] = group_performance_enhanced['paras_count'].fillna(0).astype(int)
            
            # Add recovery percentage
            group_performance_enhanced['recovery_percentage'] = (
                group_performance_enhanced['total_recovery'] / 
                group_performance_enhanced['total_detection'].replace(0, np.nan)
            ).fillna(0) * 100
            
            # Rename for consistency
            group_performance_enhanced.columns = [
                'audit_group', 'dar_count', 'total_detection', 'total_recovery', 'paras_count', 'recovery_percentage'
            ]
            
            # Sort by detection and get all groups
            group_performance_data_enhanced = group_performance_enhanced.sort_values('total_detection', ascending=False).to_dict('records')
        
        # MCM DETAILED DATA for Summary of Audit Paras
        mcm_detailed_data = []
        if not df_viz_data.empty:
            # Get detailed MCM data with all required fields
            mcm_columns = [
                'audit_group_number', 'gstin', 'trade_name', 'category', 
                'audit_para_number', 'audit_para_heading', 'revenue_involved_lakhs_rs', 
                'revenue_recovered_lakhs_rs', 'status_of_para', 'mcm_decision', 'chair_remarks'
            ]
            
            # Filter for records with actual para data
            df_mcm_data = df_viz_data[
                df_viz_data['audit_para_number'].notna() & 
                (~df_viz_data['audit_para_heading'].astype(str).isin([
                    "N/A - Header Info Only (Add Paras Manually)", 
                    "Manual Entry Required", 
                    "Manual Entry - PDF Error", 
                    "Manual Entry - PDF Upload Failed"
                ]))
            ].copy()
            
            # Ensure all required columns exist
            for col in mcm_columns:
                if col not in df_mcm_data.columns:
                    df_mcm_data[col] = ''
            
            # Fill missing values appropriately
            df_mcm_data['revenue_involved_lakhs_rs'] = pd.to_numeric(df_mcm_data['revenue_involved_lakhs_rs'], errors='coerce').fillna(0)
            df_mcm_data['revenue_recovered_lakhs_rs'] = pd.to_numeric(df_mcm_data['revenue_recovered_lakhs_rs'], errors='coerce').fillna(0)
            df_mcm_data['chair_remarks'] = df_mcm_data['chair_remarks'].fillna('')
            df_mcm_data['mcm_decision'] = df_mcm_data['mcm_decision'].fillna('Decision pending')
            df_mcm_data['status_of_para'] = df_mcm_data['status_of_para'].fillna('Status not updated')
            
            # Convert to list of dictionaries
            mcm_detailed_data = df_mcm_data[mcm_columns].to_dict('records')
            
            print(f"MCM detailed data prepared: {len(mcm_detailed_data)} records")
        
        # OVERALL REMARKS - Get from periods info
        def get_overall_remarks_for_period(dbx, selected_period):
            """Helper function to get overall remarks for the selected MCM period"""
            try:
                from config import MCM_PERIODS_INFO_PATH
                
                # Load MCM periods data
                df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
                if df_periods is None or df_periods.empty:
                    return ""
                
                # Ensure overall_remarks column exists
                if 'overall_remarks' not in df_periods.columns:
                    return ""
                
                # Parse the selected period to get month and year
                try:
                    month_name, year_str = selected_period.split(" ")
                    year_val = int(year_str)
                except (ValueError, AttributeError):
                    return ""
                
                # Find the matching period
                period_row = df_periods[
                    (df_periods['month_name'] == month_name) & 
                    (df_periods['year'] == year_val)
                ]
                
                if not period_row.empty:
                    remarks = period_row.iloc[0].get('overall_remarks', '')
                    if pd.isna(remarks):
                        remarks = ""
                    return remarks
                
                return ""
                
            except Exception as e:
                print(f"Error loading overall remarks: {e}")
                return ""
        
        # Get overall remarks
        overall_remarks = get_overall_remarks_for_period(dbx, selected_period)

        # Add additional summary data for detailed analysis
        vital_stats.update({
            'status_summary': status_summary,
            'agreed_yet_to_pay_analysis': agreed_yet_to_pay_analysis,
            'risk_summary': risk_summary,
            'gstins_with_risk_data': gstins_with_risk_data,
            'paras_linked_to_risks': paras_linked_to_risks,
            'categories_summary': summary_df.to_dict('records') if not summary_df.empty else [],
            'status_analysis_available': 'status_of_para' in df_viz_data.columns,
            'classification_analysis_available': not df_paras.empty if 'df_paras' in locals() else False,
            'risk_analysis_available': 'risk_flags_data' in df_viz_data.columns,
            'taxpayer_classification_available': 'taxpayer_classification' in df_unique_reports.columns,
            'sectoral_summary': sectoral_summary,           # <-- This was missing!
            'classification_summary': classification_summary , # <-- Add this too
            'sectoral_analysis_available': len(sectoral_summary) > 0,  # NEW
            'compliance_analysis_available': len(classification_summary) > 0,  # NEW
            'classification_page_data': classification_page_data,  
            'top_taxpayers_data': top_taxpayers_data,  
             #'group_performance_data': group_performance_data,
            'group_performance_data': group_performance_data_enhanced,  # Updated with paras count
            'mcm_detailed_data': mcm_detailed_data,                    # New - detailed MCM data
            'overall_remarks': overall_remarks, 
        })
        
        return vital_stats, charts
        
    except Exception as e:
        print(f"Error in get_visualization_data: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def get_agreed_yet_to_pay_analysis(dbx, selected_period):
    """
    Helper function to get the "Agreed yet to pay " analysis data
    This replicates the specific analysis from the original visualization tab
    """
    try:
        df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz_data is None or df_viz_data.empty:
            return None
            
        df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
        if df_viz_data.empty:
            return None
        
        # Data preparation
        df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
        df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        df_viz_data['audit_group_number_str'] = df_viz_data.get('audit_group_number', '').astype(str)
        
        if 'status_of_para' not in df_viz_data.columns:
            return None
            
        # Filter for "Agreed yet to pay" status (EXACT REPLICA)
        df_status_analysis = df_viz_data[
            df_viz_data['status_of_para'].notna() & 
            (df_viz_data['status_of_para'] != '') &
            df_viz_data['audit_para_number'].notna()
        ].copy()
        
        if df_status_analysis.empty:
            return None
            
        agreed_yet_to_pay_paras = df_status_analysis[
            df_status_analysis['status_of_para'].str.contains('Agreed yet to pay', case=False, na=False)
        ].copy()
        
        if agreed_yet_to_pay_paras.empty:
            # Try alternative search terms (EXACT REPLICA)
            agreed_yet_to_pay_paras = df_status_analysis[
                df_status_analysis['status_of_para'].str.contains('agreed.*pay|yet.*pay|pending.*payment', case=False, na=False)
            ].copy()
        
        if agreed_yet_to_pay_paras.empty:
            return None
            
        # Get top 5 by detection amount (EXACT REPLICA)
        top_5_agreed = agreed_yet_to_pay_paras.nlargest(5, 'Para Detection in Lakhs')
        
        # Summary metrics
        total_agreed_paras = len(agreed_yet_to_pay_paras)
        total_agreed_detection = agreed_yet_to_pay_paras['Para Detection in Lakhs'].sum()
        total_agreed_recovery = agreed_yet_to_pay_paras['Para Recovery in Lakhs'].sum()
        
        return {
            'top_5_paras': top_5_agreed,
            'total_paras': total_agreed_paras,
            'total_detection': total_agreed_detection,
            'total_recovery': total_agreed_recovery
        }
        
    except Exception as e:
        print(f"Error in get_agreed_yet_to_pay_analysis: {e}")
        return None

def get_detailed_classification_analysis(dbx, selected_period):
    """
    Helper function to get detailed classification analysis
    This replicates the comprehensive classification breakdown from the original
    """
    try:
        df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz_data is None or df_viz_data.empty:
            return None
            
        df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
        if df_viz_data.empty:
            return None
        
        # DETAILED_CLASSIFICATION_DESC from original code
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
        
        df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
        df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        
        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        if df_paras.empty:
            return None
            
        df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
        
        # Get detailed analysis by major code
        detailed_analysis = {}
        unique_major_codes = df_paras['major_code'].unique()
        
        for code in sorted(unique_major_codes):
            df_filtered = df_paras[df_paras['major_code'] == code].copy()
            
            # Detection analysis
            det_agg = df_filtered.groupby('para_classification_code')['Para Detection in Lakhs'].sum().reset_index()
            det_agg['description'] = det_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
            
            # Recovery analysis  
            rec_agg = df_filtered.groupby('para_classification_code')['Para Recovery in Lakhs'].sum().reset_index()
            rec_agg['description'] = rec_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
            
            detailed_analysis[code] = {
                'detection_data': det_agg,
                'recovery_data': rec_agg
            }
        
        return detailed_analysis
        
    except Exception as e:
        print(f"Error in get_detailed_classification_analysis: {e}")
        return None



# Add this HTML PAGE 
def generate_classification_html_page(df_viz_data, selected_period):
    """
    Generate a comprehensive HTML page for GST Audit Para Classification
    with real data values from the current period
    """
    try:
        # Calculate real statistics from data
        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        
        if df_paras.empty:
            total_observations = 0
            main_categories_count = 0
            sub_categories_count = 0
            coverage_percentage = 0
        else:
            # Real statistics calculation
            total_observations = len(df_paras)
            main_categories_count = df_paras['para_classification_code'].str[:2].nunique()
            sub_categories_count = df_paras['para_classification_code'].nunique()
            coverage_percentage = 100 if total_observations > 0 else 0
            
        # Get category-wise breakdown for real data
        if not df_paras.empty:
            df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
            category_stats = df_paras.groupby('major_code').agg(
                para_count=('major_code', 'count'),
                total_detection=('Para Detection in Lakhs', 'sum'),
                total_recovery=('Para Recovery in Lakhs', 'sum')
            ).reset_index()
        else:
            category_stats = pd.DataFrame()

        # HTML template with real data
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GST Audit Para Classification</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
        
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 15px;
                    transform: scale(0.85);
                    transform-origin: top left;
                }}
        
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 15px 35px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
        
                .header {{
                    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
        
                .header h1 {{
                    font-size: 1.8em;
                    margin-bottom: 8px;
                    font-weight: 300;
                }}
        
                .header p {{
                    font-size: 1em;
                    opacity: 0.9;
                }}
        
                .stats-section {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
        
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 15px;
                    margin-top: 15px;
                }}
        
                .stat-item {{
                    background: rgba(255,255,255,0.1);
                    padding: 15px;
                    border-radius: 8px;
                    backdrop-filter: blur(10px);
                }}
        
                .stat-number {{
                    font-size: 2em;
                    font-weight: bold;
                    margin-bottom: 3px;
                }}
        
                .stat-label {{
                    font-size: 0.9em;
                    opacity: 0.9;
                }}
        
                .diagram-container {{
                    padding: 25px;
                    background: #f8fafc;
                }}
        
                .main-categories {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 18px;
                    margin-bottom: 20px;
                }}
        
                .category-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 18px;
                    box-shadow: 0 6px 20px rgba(0,0,0,0.08);
                    transition: all 0.3s ease;
                    border-left: 4px solid;
                    position: relative;
                    overflow: hidden;
                }}
        
                .category-card:hover {{
                    transform: translateY(-3px);
                    box-shadow: 0 12px 25px rgba(0,0,0,0.12);
                }}
        
                .category-card.tax-payment {{ border-left-color: #e74c3c; }}
                .category-card.rcm {{ border-left-color: #f39c12; }}
                .category-card.itc {{ border-left-color: #3498db; }}
                .category-card.interest {{ border-left-color: #9b59b6; }}
                .category-card.filing {{ border-left-color: #2ecc71; }}
                .category-card.procedural {{ border-left-color: #34495e; }}
                .category-card.classification {{ border-left-color: #e67e22; }}
                .category-card.special {{ border-left-color: #1abc9c; }}
                .category-card.penalty {{ border-left-color: #c0392b; }}
        
                .category-title {{
                    font-size: 1.1em;
                    font-weight: 600;
                    margin-bottom: 12px;
                    color: #2c3e50;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
        
                .category-icon {{
                    width: 25px;
                    height: 25px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 0.8em;
                }}
        
                .tax-payment .category-icon {{ background: #e74c3c; }}
                .rcm .category-icon {{ background: #f39c12; }}
                .itc .category-icon {{ background: #3498db; }}
                .interest .category-icon {{ background: #9b59b6; }}
                .filing .category-icon {{ background: #2ecc71; }}
                .procedural .category-icon {{ background: #34495e; }}
                .classification .category-icon {{ background: #e67e22; }}
                .special .category-icon {{ background: #1abc9c; }}
                .penalty .category-icon {{ background: #c0392b; }}
        
                .subcategories {{
                    list-style: none;
                }}
        
                .subcategories li {{
                    padding: 5px 0;
                    padding-left: 15px;
                    position: relative;
                    color: #5a6c7d;
                    font-size: 0.85em;
                    line-height: 1.3;
                }}
        
                .subcategories li::before {{
                    content: '▶';
                    position: absolute;
                    left: 0;
                    color: #bdc3c7;
                    font-size: 0.7em;
                }}
        
                .category-stats {{
                    background: #ecf0f1;
                    padding: 8px;
                    border-radius: 6px;
                    margin-top: 10px;
                    font-size: 0.8em;
                    text-align: center;
                    color: #34495e;
                }}
        
                .legend {{
                    background: #34495e;
                    color: white;
                    padding: 15px;
                    margin: 15px;
                    border-radius: 8px;
                }}
        
                .legend h3 {{
                    margin-bottom: 12px;
                    text-align: center;
                    font-size: 1.1em;
                }}
        
                .legend-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 10px;
                }}
        
                .legend-item {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 0.85em;
                }}
        
                .legend-color {{
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                }}
        
                .period-info {{
                    background: #3498db;
                    color: white;
                    padding: 10px;
                    text-align: center;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>GST Audit Para Classification</h1>
                    <p>Comprehensive categorization by Nature of Non-Compliance</p>
                </div>
        
                <div class="period-info">
                    📅 Period: {selected_period} | 🔍 Real-time Analysis Data
                </div>
        
                <div class="stats-section">
                    <h2>Classification Overview</h2>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-number">{main_categories_count}</div>
                            <div class="stat-label">Main Categories</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number">{sub_categories_count}</div>
                            <div class="stat-label">Sub-Categories</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number">{total_observations}</div>
                            <div class="stat-label">Audit Observations</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number">{coverage_percentage:.0f}%</div>
                            <div class="stat-label">Coverage</div>
                        </div>
                    </div>
                </div>
        
                <div class="diagram-container">
                    <div class="main-categories">
                        
                        <div class="category-card tax-payment">
                            <div class="category-title">
                                <div class="category-icon">TP</div>
                                Tax Payment Defaults
                            </div>
                            <ul class="subcategories">
                                <li>Output Tax Short Payment</li>
                                <li>Output Tax on Other Income</li>
                                <li>Export & SEZ Related Issues</li>
                                <li>Credit Note Related Errors</li>
                                <li>Scheme Migration Issues</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'TP')}
                            </div>
                        </div>
        
                        <div class="category-card rcm">
                            <div class="category-title">
                                <div class="category-icon">RC</div>
                                Reverse Charge Mechanism
                            </div>
                            <ul class="subcategories">
                                <li>Transportation & Logistics</li>
                                <li>Professional & Legal Services</li>
                                <li>Import of Services</li>
                                <li>RCM Reconciliation Issues</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'RC')}
                            </div>
                        </div>
        
                        <div class="category-card itc">
                            <div class="category-title">
                                <div class="category-icon">IT</div>
                                Input Tax Credit Violations
                            </div>
                            <ul class="subcategories">
                                <li>Blocked Credit Claims (Sec 17(5))</li>
                                <li>Ineligible ITC Claims (Sec 16)</li>
                                <li>Excess ITC Reconciliation</li>
                                <li>ITC Reversal Defaults</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'IT')}
                            </div>
                        </div>
        
                        <div class="category-card interest">
                            <div class="category-title">
                                <div class="category-icon">IN</div>
                                Interest Liability Defaults
                            </div>
                            <ul class="subcategories">
                                <li>Tax Payment Related Interest</li>
                                <li>ITC Related Interest (Sec 50)</li>
                                <li>Time of Supply Interest</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'IN')}
                            </div>
                        </div>
        
                        <div class="category-card filing">
                            <div class="category-title">
                                <div class="category-icon">RF</div>
                                Return Filing Non-Compliance
                            </div>
                            <ul class="subcategories">
                                <li>Late Filing Penalties</li>
                                <li>Non-Filing Issues (ITC-04)</li>
                                <li>Filing Quality Issues</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'RF')}
                            </div>
                        </div>
        
                        <div class="category-card procedural">
                            <div class="category-title">
                                <div class="category-icon">PD</div>
                                Procedural & Documentation
                            </div>
                            <ul class="subcategories">
                                <li>Return Reconciliation</li>
                                <li>Documentation Deficiencies</li>
                                <li>Cash Payment Violations</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'PD')}
                            </div>
                        </div>
        
                        <div class="category-card classification">
                            <div class="category-title">
                                <div class="category-icon">CV</div>
                                Classification & Valuation
                            </div>
                            <ul class="subcategories">
                                <li>Service Classification Errors</li>
                                <li>Wrong Chapter Heading</li>
                                <li>Incorrect Notification Claims</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'CV')}
                            </div>
                        </div>
        
                        <div class="category-card special">
                            <div class="category-title">
                                <div class="category-icon">SS</div>
                                Special Situations
                            </div>
                            <ul class="subcategories">
                                <li>Construction/Real Estate</li>
                                <li>Job Work Related Compliance</li>
                                <li>Inter-Company Transactions</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'SS')}
                            </div>
                        </div>
        
                        <div class="category-card penalty">
                            <div class="category-title">
                                <div class="category-icon">PG</div>
                                Penalty & General Compliance
                            </div>
                            <ul class="subcategories">
                                <li>Statutory Penalties (Sec 123)</li>
                                <li>Stock & Physical Verification</li>
                                <li>General Non-Compliance</li>
                            </ul>
                            <div class="category-stats">
                                {get_category_stats(category_stats, 'PG')}
                            </div>
                        </div>
        
                    </div>
                </div>
        
                <div class="legend">
                    <h3>🎯 Classification Guide & Impact Assessment</h3>
                    <div class="legend-grid">
                        <div class="legend-item">
                            <div class="legend-color" style="background: #e74c3c;"></div>
                            <span>High Risk - Tax Payment Issues</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #f39c12;"></div>
                            <span>Medium Risk - RCM Compliance</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #3498db;"></div>
                            <span>High Volume - ITC Issues</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #9b59b6;"></div>
                            <span>Financial Impact - Interest</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #2ecc71;"></div>
                            <span>Administrative - Filing Issues</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: #34495e;"></div>
                            <span>Process Related - Documentation</span>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        # Helper function to get category statistics
        def get_category_stats(stats_df, category_code):
            if stats_df.empty:
                return "📊 No data | 💰 ₹0 L | 💎 ₹0 L"
            
            category_data = stats_df[stats_df['major_code'] == category_code]
            if category_data.empty:
                return "📊 No data | 💰 ₹0 L | 💎 ₹0 L"
            
            paras = int(category_data['para_count'].iloc[0])
            detection = float(category_data['total_detection'].iloc[0])
            recovery = float(category_data['total_recovery'].iloc[0])
            
            return f"📊 {paras} paras | 💰 ₹{detection:.1f}L | 💎 ₹{recovery:.1f}L"

        # Replace the placeholder function calls with actual data
        formatted_html = html_content
        for category_code in ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']:
            placeholder = f"{{get_category_stats(category_stats, '{category_code}')}}"
            actual_stats = get_category_stats(category_stats, category_code)
            formatted_html = formatted_html.replace(placeholder, actual_stats)

        return formatted_html

    except Exception as e:
        print(f"Error generating classification HTML page: {e}")
        return None
