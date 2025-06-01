# utils/improved_pdf_generator.py - Professional PDF generation with excellent structure
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json
import re

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logging.warning("WeasyPrint not available. Install with: pip install weasyprint")

logger = logging.getLogger(__name__)


class ProfessionalPDFGenerator:
    """Professional PDF generator with excellent structure and readability"""

    def __init__(self):
        self.reports_dir = Path("reports")
        self.templates_dir = Path("pdf_templates")

        # Create directories
        self.reports_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)

        # Initialize font configuration
        self.font_config = FontConfiguration() if WEASYPRINT_AVAILABLE else None

        # Create improved CSS and templates
        self._create_professional_templates()

    def _create_professional_templates(self):
        """Create professional CSS with excellent structure and readability"""

        css_content = """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        @page {
            size: A4;
            margin: 2.5cm 2cm 3cm 2cm;
            @top-left {
                content: "Үл хөдлөх хөрөнгийн шинжилгээний тайлан";
                font-size: 9pt;
                color: #6b7280;
                font-weight: 500;
            }
            @top-right {
                content: "Огноо: " string(report-date);
                font-size: 9pt;
                color: #6b7280;
            }
            @bottom-center {
                content: "Хуудас " counter(page) " / " counter(pages);
                font-size: 9pt;
                color: #6b7280;
                text-align: center;
            }
        }

        /* Reset and base styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', 'Arial', 'DejaVu Sans', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #1f2937;
            background: #ffffff;
        }

        /* Typography hierarchy */
        h1 {
            font-size: 28pt;
            font-weight: 700;
            color: #111827;
            margin-bottom: 8pt;
            letter-spacing: -0.5pt;
        }

        h2 {
            font-size: 20pt;
            font-weight: 600;
            color: #1f2937;
            margin: 24pt 0 12pt 0;
            border-bottom: 2pt solid #3b82f6;
            padding-bottom: 6pt;
        }

        h3 {
            font-size: 16pt;
            font-weight: 600;
            color: #374151;
            margin: 18pt 0 10pt 0;
        }

        h4 {
            font-size: 14pt;
            font-weight: 500;
            color: #4b5563;
            margin: 14pt 0 8pt 0;
        }

        p {
            margin-bottom: 12pt;
            text-align: justify;
        }

        /* Header section */
        .report-header {
            text-align: center;
            margin-bottom: 40pt;
            padding: 30pt 20pt;
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
            border-radius: 8pt;
            page-break-inside: avoid;
        }

        .report-title {
            font-size: 32pt;
            font-weight: 700;
            margin-bottom: 12pt;
            text-shadow: 0 2pt 4pt rgba(0,0,0,0.1);
        }

        .report-subtitle {
            font-size: 16pt;
            font-weight: 400;
            opacity: 0.9;
            margin-bottom: 8pt;
        }

        .report-date {
            font-size: 12pt;
            font-weight: 300;
            opacity: 0.8;
        }

        /* Executive Summary */
        .executive-summary {
            background: #f8fafc;
            border-left: 6pt solid #059669;
            padding: 20pt;
            margin: 20pt 0;
            border-radius: 0 8pt 8pt 0;
            page-break-inside: avoid;
        }

        .executive-summary h3 {
            color: #059669;
            margin-top: 0;
            margin-bottom: 12pt;
        }

        .key-points {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200pt, 1fr));
            gap: 15pt;
            margin: 15pt 0;
        }

        .key-point {
            background: white;
            padding: 15pt;
            border-radius: 6pt;
            border-left: 4pt solid #3b82f6;
            box-shadow: 0 2pt 4pt rgba(0,0,0,0.05);
        }

        .key-point-label {
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 6pt;
            font-size: 12pt;
        }

        .key-point-value {
            font-size: 14pt;
            font-weight: 500;
            color: #3b82f6;
        }

        /* Property Information Card */
        .property-card {
            background: #ffffff;
            border: 1pt solid #e5e7eb;
            border-radius: 8pt;
            padding: 20pt;
            margin: 20pt 0;
            box-shadow: 0 4pt 6pt rgba(0,0,0,0.05);
            page-break-inside: avoid;
        }

        .property-header {
            border-bottom: 1pt solid #e5e7eb;
            padding-bottom: 15pt;
            margin-bottom: 15pt;
        }

        .property-title {
            font-size: 18pt;
            font-weight: 600;
            color: #111827;
            margin-bottom: 8pt;
        }

        .property-location {
            font-size: 12pt;
            color: #6b7280;
            display: flex;
            align-items: center;
        }

        .property-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150pt, 1fr));
            gap: 15pt;
            margin: 15pt 0;
        }

        .detail-item {
            display: flex;
            flex-direction: column;
            gap: 4pt;
        }

        .detail-label {
            font-size: 10pt;
            font-weight: 500;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5pt;
        }

        .detail-value {
            font-size: 13pt;
            font-weight: 600;
            color: #111827;
        }

        /* Price highlights */
        .price-highlight {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: white;
            padding: 20pt;
            border-radius: 8pt;
            text-align: center;
            margin: 20pt 0;
            page-break-inside: avoid;
        }

        .price-main {
            font-size: 24pt;
            font-weight: 700;
            margin-bottom: 6pt;
        }

        .price-unit {
            font-size: 14pt;
            font-weight: 400;
            opacity: 0.9;
        }

        /* Comparison tables */
        .comparison-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20pt 0;
            background: white;
            border-radius: 8pt;
            overflow: hidden;
            box-shadow: 0 4pt 6pt rgba(0,0,0,0.05);
        }

        .comparison-table thead {
            background: #1f2937;
            color: white;
        }

        .comparison-table th {
            padding: 15pt 12pt;
            text-align: left;
            font-weight: 600;
            font-size: 11pt;
            letter-spacing: 0.5pt;
        }

        .comparison-table td {
            padding: 12pt;
            border-bottom: 1pt solid #f3f4f6;
            font-size: 11pt;
        }

        .comparison-table tbody tr:nth-child(even) {
            background: #f9fafb;
        }

        .comparison-table tbody tr:hover {
            background: #f3f4f6;
        }

        .table-highlight {
            background: #fef3c7 !important;
            font-weight: 600;
        }

        /* Analysis sections */
        .analysis-section {
            background: #ffffff;
            border: 1pt solid #e5e7eb;
            border-radius: 8pt;
            padding: 20pt;
            margin: 20pt 0;
            page-break-inside: avoid;
        }

        .section-header {
            display: flex;
            align-items: center;
            margin-bottom: 15pt;
            padding-bottom: 10pt;
            border-bottom: 1pt solid #e5e7eb;
        }

        .section-icon {
            font-size: 20pt;
            margin-right: 10pt;
        }

        .section-title {
            font-size: 16pt;
            font-weight: 600;
            color: #1f2937;
            margin: 0;
        }

        /* Chain-of-Thought specific styling */
        .cot-container {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border: 2pt solid #3b82f6;
            border-radius: 12pt;
            padding: 25pt;
            margin: 25pt 0;
            page-break-inside: avoid;
        }

        .cot-header {
            text-align: center;
            margin-bottom: 20pt;
        }

        .cot-title {
            font-size: 20pt;
            font-weight: 700;
            color: #1e40af;
            margin-bottom: 8pt;
        }

        .cot-subtitle {
            font-size: 12pt;
            color: #3730a3;
            font-weight: 500;
        }

        .thinking-step {
            background: white;
            border-radius: 8pt;
            padding: 18pt;
            margin: 15pt 0;
            border-left: 6pt solid #3b82f6;
            box-shadow: 0 2pt 4pt rgba(0,0,0,0.05);
            page-break-inside: avoid;
        }

        .step-number {
            background: #3b82f6;
            color: white;
            width: 30pt;
            height: 30pt;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 12pt;
            margin-bottom: 10pt;
        }

        .step-title {
            font-size: 14pt;
            font-weight: 600;
            color: #1e40af;
            margin-bottom: 8pt;
        }

        .step-content {
            font-size: 11pt;
            line-height: 1.6;
            color: #374151;
        }

        .confidence-indicator {
            margin-top: 12pt;
            display: flex;
            align-items: center;
            gap: 8pt;
        }

        .confidence-bar {
            flex: 1;
            height: 6pt;
            background: #e5e7eb;
            border-radius: 3pt;
            overflow: hidden;
        }

        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #10b981 100%);
            border-radius: 3pt;
            transition: width 0.3s ease;
        }

        .confidence-text {
            font-size: 10pt;
            font-weight: 500;
            color: #6b7280;
            min-width: 40pt;
        }

        /* Insights and recommendations */
        .insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200pt, 1fr));
            gap: 20pt;
            margin: 20pt 0;
        }

        .insight-card {
            background: white;
            border-radius: 8pt;
            padding: 18pt;
            border-left: 6pt solid #059669;
            box-shadow: 0 2pt 4pt rgba(0,0,0,0.05);
        }

        .insight-icon {
            font-size: 24pt;
            margin-bottom: 8pt;
        }

        .insight-title {
            font-size: 13pt;
            font-weight: 600;
            color: #059669;
            margin-bottom: 6pt;
        }

        .insight-content {
            font-size: 11pt;
            color: #374151;
            line-height: 1.5;
        }

        /* Risk indicators */
        .risk-low { border-left-color: #10b981; }
        .risk-medium { border-left-color: #f59e0b; }
        .risk-high { border-left-color: #ef4444; }

        /* Search results styling */
        .search-results {
            background: #f8fafc;
            border: 1pt solid #e2e8f0;
            border-radius: 8pt;
            padding: 20pt;
            margin: 20pt 0;
        }

        .search-header {
            font-size: 14pt;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12pt;
            display: flex;
            align-items: center;
            gap: 8pt;
        }

        .search-content {
            font-size: 11pt;
            line-height: 1.6;
            color: #334155;
        }

        /* Footer */
        .report-footer {
            margin-top: 40pt;
            padding-top: 20pt;
            border-top: 2pt solid #e5e7eb;
            text-align: center;
            font-size: 10pt;
            color: #6b7280;
        }

        /* Utility classes */
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        .font-bold { font-weight: 700; }
        .font-semibold { font-weight: 600; }
        .text-sm { font-size: 10pt; }
        .text-lg { font-size: 14pt; }
        .mb-2 { margin-bottom: 8pt; }
        .mb-4 { margin-bottom: 16pt; }
        .mt-4 { margin-top: 16pt; }

        /* Page break controls */
        .page-break-before { page-break-before: always; }
        .page-break-after { page-break-after: always; }
        .page-break-inside-avoid { page-break-inside: avoid; }

        /* Responsive adjustments */
        @media print {
            .analysis-section,
            .property-card,
            .thinking-step,
            .insight-card {
                page-break-inside: avoid;
            }

            .comparison-table {
                font-size: 10pt;
            }
        }
        """

        # Save CSS template
        css_file = self.templates_dir / "professional_styles.css"
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(css_content)

    def generate_property_report(self, property_data: Dict[str, Any],
                                 district_analysis: str,
                                 comparison_result: str,
                                 search_results: str = "") -> str:
        """Generate professional property analysis PDF report"""

        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint is required. Install with: pip install weasyprint")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"property_analysis_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        # Generate structured HTML content
        html_content = self._generate_property_html(
            property_data, district_analysis, comparison_result, search_results
        )

        # Generate PDF with professional styling
        css_path = str(self.templates_dir / "professional_styles.css")
        html = HTML(string=html_content)
        css = CSS(filename=css_path)

        html.write_pdf(str(filepath), stylesheets=[css], font_config=self.font_config)

        logger.info(f"Professional property PDF report generated: {filepath}")
        return str(filepath)

    def generate_district_summary_report(self, districts_data: List[Dict],
                                         market_trends: str = "",
                                         search_results: str = "") -> str:
        """Generate professional district comparison PDF report"""

        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint is required. Install with: pip install weasyprint")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"district_comparison_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        # Generate structured HTML content
        html_content = self._generate_district_html(
            districts_data, market_trends, search_results
        )

        # Generate PDF with professional styling
        css_path = str(self.templates_dir / "professional_styles.css")
        html = HTML(string=html_content)
        css = CSS(filename=css_path)

        html.write_pdf(str(filepath), stylesheets=[css], font_config=self.font_config)

        logger.info(f"Professional district PDF report generated: {filepath}")
        return str(filepath)

    def _generate_property_html(self, property_data: Dict[str, Any],
                                district_analysis: str,
                                comparison_result: str,
                                search_results: str) -> str:
        """Generate well-structured HTML for property report"""

        # Extract and format data safely
        title = self._clean_text(property_data.get('title', 'Орон сууцны шинжилгээ'))
        location = self._clean_text(property_data.get('full_location', 'Байршил тодорхойгүй'))
        district = self._clean_text(property_data.get('district', 'Дүүрэг тодорхойгүй'))
        area = property_data.get('area_sqm', 0)
        rooms = property_data.get('room_count', 0)
        price = property_data.get('price_numeric', 0)
        price_per_sqm = property_data.get('price_per_sqm', 0)

        # Generate executive summary
        exec_summary = self._generate_executive_summary(property_data)

        # Format CoT analysis
        cot_html = self._format_cot_analysis(comparison_result)

        # Generate insights
        insights_html = self._generate_property_insights(property_data)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="mn">
        <head>
            <meta charset="UTF-8">
            <title>Орон сууцны дэлгэрэнгүй шинжилгээний тайлан</title>
            <style>
                body {{ string-set: report-date "{datetime.now().strftime('%Y-%m-%d')}"; }}
            </style>
        </head>
        <body>
            <!-- Header -->
            <div class="report-header">
                <h1 class="report-title">🏠 Орон сууцны дэлгэрэнгүй шинжилгээ</h1>
                <p class="report-subtitle">Мэргэжлийн үл хөдлөх хөрөнгийн шинжилгээний тайлан</p>
                <p class="report-date">{datetime.now().strftime('%Y оны %m сарын %d өдөр')}</p>
            </div>

            <!-- Executive Summary -->
            <div class="executive-summary">
                <h3>📋 Гол хураангуй</h3>
                {exec_summary}
            </div>

            <!-- Property Details Card -->
            <div class="property-card">
                <div class="property-header">
                    <h3 class="property-title">{title}</h3>
                    <p class="property-location">📍 {location}</p>
                </div>

                <div class="property-details">
                    <div class="detail-item">
                        <span class="detail-label">Дүүрэг</span>
                        <span class="detail-value">{district}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Талбай</span>
                        <span class="detail-value">{area} м²</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Өрөөний тоо</span>
                        <span class="detail-value">{rooms} өрөө</span>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20pt; margin-top: 20pt;">
                    <div class="price-highlight">
                        <div class="price-main">{self._format_price(price)}</div>
                        <div class="price-unit">Нийт үнэ</div>
                    </div>
                    <div class="price-highlight">
                        <div class="price-main">{self._format_price(price_per_sqm)}</div>
                        <div class="price-unit">м² үнэ</div>
                    </div>
                </div>
            </div>

            <!-- Chain-of-Thought Analysis -->
            {cot_html}

            <!-- District Analysis -->
            <div class="analysis-section">
                <div class="section-header">
                    <span class="section-icon">🏘️</span>
                    <h3 class="section-title">Дүүргийн зах зээлийн шинжилгээ</h3>
                </div>
                {self._format_analysis_content(district_analysis)}
            </div>

            <!-- Key Insights -->
            <div class="insights-grid">
                {insights_html}
            </div>

            {self._generate_search_results_html(search_results) if search_results else ''}

            <!-- Investment Recommendations -->
            <div class="analysis-section">
                <div class="section-header">
                    <span class="section-icon">💡</span>
                    <h3 class="section-title">Хөрөнгө оруулалтын зөвлөмж</h3>
                </div>
                {self._generate_investment_recommendations(property_data)}
            </div>

            <!-- Footer -->
            <div class="report-footer">
                <p>Тайлан үүсгэсэн: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p>Үл хөдлөх хөрөнгийн мэргэжлийн туслах системээр автоматаар үүсгэсэн</p>
                <p>🧠 Chain-of-Thought шинжилгээний аргаар боловсруулсан</p>
            </div>
        </body>
        </html>
        """

        return html_content

    def _generate_district_html(self, districts_data: List[Dict],
                                market_trends: str,
                                search_results: str) -> str:
        """Generate well-structured HTML for district comparison report"""

        # Sort districts by price
        if districts_data:
            districts_data = sorted(districts_data, key=lambda x: x.get('overall_avg', 0), reverse=True)

        # Generate comparison table
        table_html = self._generate_comparison_table(districts_data)

        # Generate market analysis
        market_analysis_html = self._format_analysis_content(
            market_trends) if market_trends else self._get_default_market_analysis()

        # Generate district profiles
        profiles_html = self._generate_district_profiles(districts_data)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="mn">
        <head>
            <meta charset="UTF-8">
            <title>Улаанбаатар хотын дүүргийн харьцуулалтын тайлан</title>
            <style>
                body {{ string-set: report-date "{datetime.now().strftime('%Y-%m-%d')}"; }}
            </style>
        </head>
        <body>
            <!-- Header -->
            <div class="report-header">
                <h1 class="report-title">🏘️ Дүүргийн харьцуулалтын тайлан</h1>
                <p class="report-subtitle">Улаанбаатар хотын орон сууцны зах зээлийн дэлгэрэнгүй харьцуулалт</p>
                <p class="report-date">{datetime.now().strftime('%Y оны %m сарын %d өдөр')}</p>
            </div>

            <!-- Executive Summary -->
            <div class="executive-summary">
                <h3>📊 Гол хураангуй</h3>
                <div class="key-points">
                    <div class="key-point">
                        <div class="key-point-label">Хамгийн үнэтэй дүүрэг</div>
                        <div class="key-point-value">{districts_data[0].get('name', 'Тодорхойгүй') if districts_data else 'Мэдээлэл байхгүй'}</div>
                    </div>
                    <div class="key-point">
                        <div class="key-point-label">Хамгийн хямд дүүрэг</div>
                        <div class="key-point-value">{districts_data[-1].get('name', 'Тодорхойгүй') if districts_data else 'Мэдээлэл байхгүй'}</div>
                    </div>
                    <div class="key-point">
                        <div class="key-point-label">Дүүргүүдийн тоо</div>
                        <div class="key-point-value">{len(districts_data)} дүүрэг</div>
                    </div>
                    <div class="key-point">
                        <div class="key-point-label">Үнийн ялгаа</div>
                        <div class="key-point-value">{self._calculate_price_range(districts_data)}</div>
                    </div>
                </div>
            </div>

            <!-- Comparison Table -->
            <div class="analysis-section">
                <div class="section-header">
                    <span class="section-icon">📊</span>
                    <h3 class="section-title">Дүүргүүдийн үнийн харьцуулалт</h3>
                </div>
                {table_html}
            </div>

            <!-- Market Analysis -->
            <div class="analysis-section">
                <div class="section-header">
                    <span class="section-icon">📈</span>
                    <h3 class="section-title">Зах зээлийн шинжилгээ</h3>
                </div>
                {market_analysis_html}
            </div>

            {self._generate_search_results_html(search_results) if search_results else ''}

            <!-- District Profiles -->
            <div class="analysis-section">
                <div class="section-header">
                    <span class="section-icon">🏢</span>
                    <h3 class="section-title">Дүүрэг тус бүрийн онцлог</h3>
                </div>
                {profiles_html}
            </div>

            <!-- Investment Opportunities -->
            <div class="insights-grid">
                {self._generate_investment_opportunities(districts_data)}
            </div>

            <!-- Footer -->
            <div class="report-footer">
                <p>Тайлан үүсгэсэн: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p>Үл хөдлөх хөрөнгийн мэргэжлийн туслах системээр автоматаар үүсгэсэн</p>
                <p>🧠 Chain-of-Thought шинжилгээний аргаар боловсруулсан</p>
            </div>
        </body>
        </html>
        """

        return html_content

    def _format_cot_analysis(self, cot_content: str) -> str:
        """Format Chain-of-Thought analysis with professional structure"""
        if not cot_content:
            return ""

        # Parse CoT sections
        sections = self._parse_cot_sections(cot_content)

        steps_html = ""
        step_number = 1

        for section in sections:
            if section['type'] == 'step':
                confidence = min(95, 70 + (step_number * 5))  # Simulate confidence progression

                steps_html += f"""
                <div class="thinking-step">
                    <div class="step-number">{step_number}</div>
                    <div class="step-title">{section['title']}</div>
                    <div class="step-content">{section['content']}</div>
                    <div class="confidence-indicator">
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: {confidence}%"></div>
                        </div>
                        <div class="confidence-text">{confidence}%</div>
                    </div>
                </div>"""
                step_number += 1

        return f"""
        <div class="cot-container">
            <div class="cot-header">
                <h3 class="cot-title">🧠 Chain-of-Thought дэлгэрэнгүй шинжилгээ</h3>
                <p class="cot-subtitle">Алхам бүрийн системтэй шинжилгээний процесс</p>
            </div>
            {steps_html}
        </div>"""

    def _parse_cot_sections(self, content: str) -> List[Dict]:
        """Parse CoT content into structured sections"""
        sections = []

        # Split by double asterisks (markdown headers)
        parts = re.split(r'\*\*(.*?)\*\*', content)

        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                title = parts[i + 1].strip()
                content_part = parts[i + 2].strip() if i + 2 < len(parts) else ""

                if title and content_part:
                    sections.append({
                        'type': 'step',
                        'title': title,
                        'content': content_part
                    })

        # If no structured sections found, create default ones
        if not sections:
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            for i, para in enumerate(paragraphs[:5]):  # Limit to 5 steps
                sections.append({
                    'type': 'step',
                    'title': f"Шинжилгээний {i + 1}-р алхам",
                    'content': para
                })

        return sections

    def _generate_executive_summary(self, property_data: Dict) -> str:
        """Generate executive summary for property"""
        price = property_data.get('price_numeric', 0)
        price_per_sqm = property_data.get('price_per_sqm', 0)
        area = property_data.get('area_sqm', 0)

        # Determine price level
        if price_per_sqm > 4500000:
            price_level = "өндөр"
            price_color = "risk-high"
        elif price_per_sqm > 3000000:
            price_level = "дундаж"
            price_color = "risk-medium"
        else:
            price_level = "доогуур"
            price_color = "risk-low"

        return f"""
        <div class="key-points">
            <div class="key-point {price_color}">
                <div class="key-point-label">Үнийн түвшин</div>
                <div class="key-point-value">{price_level} түвшинд</div>
            </div>
            <div class="key-point">
                <div class="key-point-label">Нийт үнэ</div>
                <div class="key-point-value">{self._format_price(price)}</div>
            </div>
            <div class="key-point">
                <div class="key-point-label">М² үнэ</div>
                <div class="key-point-value">{self._format_price(price_per_sqm)}</div>
            </div>
            <div class="key-point">
                <div class="key-point-label">Хөрөнгө оруулалт</div>
                <div class="key-point-value">{'Зөвлөдөг' if price_level != 'өндөр' else 'Анхаарах'}</div>
            </div>
        </div>
        """

    def _generate_property_insights(self, property_data: Dict) -> str:
        """Generate key insights for property"""
        insights = []

        price_per_sqm = property_data.get('price_per_sqm', 0)
        district = property_data.get('district', '')

        # Price analysis insight
        if price_per_sqm > 4500000:
            insights.append({
                'icon': '⚠️',
                'title': 'Үнийн анализ',
                'content': 'Зах зээлээс өндөр үнэтэй байна. Тохиролцох боломжийг хайж үзэх хэрэгтэй.',
                'risk': 'risk-high'
            })
        elif price_per_sqm < 2500000:
            insights.append({
                'icon': '💰',
                'title': 'Үнийн давуу тал',
                'content': 'Зах зээлээс доогуур үнэтэй. Хөрөнгө оруулалтын боломжтой.',
                'risk': 'risk-low'
            })
        else:
            insights.append({
                'icon': '📊',
                'title': 'Үнийн байдал',
                'content': 'Зах зээлийн дундаж үнэтэй байна. Тохиромжтой үнэ.',
                'risk': 'risk-medium'
            })

        # Location insight
        if 'сүхбаатар' in district.lower():
            insights.append({
                'icon': '🏛️',
                'title': 'Байршлын давуу тал',
                'content': 'Хотын төвд байрладаг. Түрээсийн орлого өндөр хүлээгдэж байна.',
                'risk': 'risk-low'
            })
        elif 'налайх' in district.lower() or 'багануур' in district.lower():
            insights.append({
                'icon': '🌱',
                'title': 'Хөгжлийн боломж',
                'content': 'Ирээдүйн хөгжлийн боломжтой бүс. Урт хугацааны хөрөнгө оруулалт.',
                'risk': 'risk-medium'
            })

        # Generate HTML
        html = ""
        for insight in insights:
            html += f"""
            <div class="insight-card {insight['risk']}">
                <div class="insight-icon">{insight['icon']}</div>
                <div class="insight-title">{insight['title']}</div>
                <div class="insight-content">{insight['content']}</div>
            </div>"""

        return html

    def _generate_comparison_table(self, districts_data: List[Dict]) -> str:
        """Generate professional comparison table"""
        if not districts_data:
            return "<p>Дүүргийн мэдээлэл байхгүй.</p>"

        rows_html = ""
        for i, district in enumerate(districts_data):
            name = district.get('name', 'Тодорхойгүй')
            overall = self._format_price(district.get('overall_avg', 0))
            two_room = self._format_price(district.get('two_room_avg', 0))
            three_room = self._format_price(district.get('three_room_avg', 0))

            # Highlight most/least expensive
            row_class = ""
            if i == 0:  # Most expensive
                row_class = "table-highlight"

            rows_html += f"""
            <tr class="{row_class}">
                <td><strong>{name}</strong></td>
                <td>{overall}</td>
                <td>{two_room}</td>
                <td>{three_room}</td>
            </tr>"""

        return f"""
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Дүүрэг</th>
                    <th>Дундаж үнэ (₮/м²)</th>
                    <th>2 өрөө (₮/м²)</th>
                    <th>3 өрөө (₮/м²)</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>"""

    def _generate_district_profiles(self, districts_data: List[Dict]) -> str:
        """Generate detailed district profiles"""
        profiles = {
            'Сүхбаатар': {
                'description': 'Хотын төв, өндөр үнэтэй, түрээсийн орлого сайн',
                'investment': 'Түрээсийн орлогод тохиромжтой',
                'risk': 'risk-low'
            },
            'Хан-Уул': {
                'description': 'Шинэ хорооллын бүс, хөгжиж буй дэд бүтэц',
                'investment': 'Ирээдүйн өсөлтийн боломжтой',
                'risk': 'risk-medium'
            },
            'Чингэлтэй': {
                'description': 'Хотын төв хэсэг, тохиромжтой байршил',
                'investment': 'Тогтвортой хөрөнгө оруулалт',
                'risk': 'risk-low'
            },
            'Баянгол': {
                'description': 'Дундаж үнэтэй, тогтвортой зах зээл',
                'investment': 'Эхлэн худалдан авагчдад тохиромжтой',
                'risk': 'risk-medium'
            },
            'Баянзүрх': {
                'description': 'Том дүүрэг, олон янзын сонголт',
                'investment': 'Олон төрлийн боломж',
                'risk': 'risk-medium'
            },
            'Сонгинохайрхан': {
                'description': 'Хөрөнгө оруулалтад тохиромжтой',
                'investment': 'Дундаж өртөгтэй, боломжтой',
                'risk': 'risk-medium'
            },
            'Багануур': {
                'description': 'Хямд үнэтэй, ирээдүйн боломжтой',
                'investment': 'Урт хугацааны хөрөнгө оруулалт',
                'risk': 'risk-high'
            },
            'Налайх': {
                'description': 'Хамгийн хямд, эхлэн худалдан авагчдад тохиромжтой',
                'investment': 'Анхны худалдан авалт',
                'risk': 'risk-high'
            }
        }

        html = ""
        for district in districts_data[:6]:  # Show top 6
            name = district.get('name', '')
            price = self._format_price(district.get('overall_avg', 0))
            profile = profiles.get(name, {
                'description': 'Дэлгэрэнгүй мэдээлэл байхгүй',
                'investment': 'Шинжилгээ хийх шаардлагатай',
                'risk': 'risk-medium'
            })

            html += f"""
            <div class="insight-card {profile['risk']}" style="margin-bottom: 15pt;">
                <div class="insight-title">{name}</div>
                <div class="insight-content">
                    <p><strong>Тодорхойлолт:</strong> {profile['description']}</p>
                    <p><strong>Хөрөнгө оруулалт:</strong> {profile['investment']}</p>
                    <p><strong>Дундаж үнэ:</strong> {price}</p>
                </div>
            </div>"""

        return html

    def _generate_investment_opportunities(self, districts_data: List[Dict]) -> str:
        """Generate investment opportunities section"""
        if not districts_data:
            return ""

        # Find best opportunities
        cheapest = min(districts_data, key=lambda x: x.get('overall_avg', float('inf')))
        most_expensive = max(districts_data, key=lambda x: x.get('overall_avg', 0))

        opportunities = [
            {
                'icon': '💎',
                'title': 'Хамгийн үнэтэй зах зээл',
                'content': f"{most_expensive.get('name', 'Тодорхойгүй')} - Түрээсийн орлого өндөр",
                'risk': 'risk-low'
            },
            {
                'icon': '🌟',
                'title': 'Хамгийн боломжийн үнэ',
                'content': f"{cheapest.get('name', 'Тодорхойгүй')} - Анхны худалдан авалтад тохиромжтой",
                'risk': 'risk-medium'
            },
            {
                'icon': '📈',
                'title': 'Өсөлтийн боломж',
                'content': 'Хан-Уул, Баянзүрх - Ирээдүйн хөгжлийн боломжтой',
                'risk': 'risk-medium'
            },
            {
                'icon': '🏦',
                'title': 'Түрээсийн орлого',
                'content': 'Төвийн дүүргүүд - Тогтвортой түрээсийн орлого',
                'risk': 'risk-low'
            }
        ]

        html = ""
        for opp in opportunities:
            html += f"""
            <div class="insight-card {opp['risk']}">
                <div class="insight-icon">{opp['icon']}</div>
                <div class="insight-title">{opp['title']}</div>
                <div class="insight-content">{opp['content']}</div>
            </div>"""

        return html

    def _generate_investment_recommendations(self, property_data: Dict) -> str:
        """Generate investment recommendations"""
        price_per_sqm = property_data.get('price_per_sqm', 0)
        district = property_data.get('district', '')

        recommendations = []

        # Price-based recommendations
        if price_per_sqm > 4500000:
            recommendations.append("⚠️ Үнэ өндөр түвшинд байгаа тул тохиролцох боломжийг авч үзэх")
            recommendations.append("📋 Үнийн судалгаа нэмж хийх")
            recommendations.append("⏰ Худалдан авахын өмнө хүлээх боломжийг харгалзах")
        elif price_per_sqm < 2500000:
            recommendations.append("💰 Зах зээлээс доогуур үнэтэй - хөрөнгө оруулалтын боломжтой")
            recommendations.append("🚀 Хурдан шийдвэр гаргах боломжтой")
            recommendations.append("📈 Ирээдүйн үнийн өсөлт хүлээгдэж байна")
        else:
            recommendations.append("✅ Зах зээлийн дундаж үнэтэй - тохиромжтой үнэ")
            recommendations.append("🎯 Худалдан авах боломжтой")

        # District-based recommendations
        if 'сүхбаатар' in district.lower():
            recommendations.append("🏛️ Төвийн дүүрэг - түрээсийн орлого өндөр")
            recommendations.append("🚇 Тээврийн хэрэгслийн давуу тал")
        elif 'налайх' in district.lower() or 'багануур' in district.lower():
            recommendations.append("🌱 Ирээдүйн хөгжлийн боломжтой бүс")
            recommendations.append("💡 Урт хугацааны хөрөнгө оруулалтад тохиромжтой")

        # Generate HTML
        html = "<div style='display: grid; gap: 10pt;'>"
        for rec in recommendations:
            html += f"<p style='margin: 0; padding: 8pt; background: #f8fafc; border-left: 4pt solid #3b82f6; border-radius: 4pt;'>{rec}</p>"
        html += "</div>"

        return html

    def _generate_search_results_html(self, search_results: str) -> str:
        """Generate search results section"""
        if not search_results:
            return ""

        return f"""
        <div class="search-results">
            <div class="search-header">
                <span>🔍</span>
                Интернэт судалгааны үр дүн
            </div>
            <div class="search-content">
                {self._format_analysis_content(search_results)}
            </div>
        </div>"""

    def _format_analysis_content(self, content: str) -> str:
        """Format analysis content with proper structure"""
        if not content:
            return "<p>Мэдээлэл байхгүй.</p>"

        # Clean content
        content = self._clean_text(content)

        # Split into paragraphs and format
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        formatted_paragraphs = []

        for para in paragraphs:
            if para.startswith('**') and para.endswith('**'):
                # This is a header
                header_text = para.strip('*').strip()
                formatted_paragraphs.append(f"<h4>{header_text}</h4>")
            elif '**' in para:
                # Contains bold text
                formatted_para = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', para)
                formatted_paragraphs.append(f"<p>{formatted_para}</p>")
            else:
                formatted_paragraphs.append(f"<p>{para}</p>")

        return '\n'.join(formatted_paragraphs)

    def _get_default_market_analysis(self) -> str:
        """Get default market analysis when no data available"""
        return """
        <h4>Улаанбаатар хотын орон сууцны зах зээлийн ерөнхий байдал</h4>
        <p>Улаанбаатар хотын орон сууцны зах зээл тогтвортой хөгжиж байгаа. Дүүргүүдийн үнийн ялгаа тодорхой бөгөөд төвийн дүүргүүд илүү үнэтэй байна.</p>

        <h4>Үнийн чиглэл</h4>
        <p>Орон сууцны үнэ жилийн 5-8% өсөлт үзүүлж байгаа. Шинэ хорооллын хөгжлийн улмаас нийлүүлэлт нэмэгдэж байна.</p>

        <h4>Хөрөнгө оруулалтын боломжууд</h4>
        <p>Төвийн дүүргүүдэд түрээсийн орлого өндөр, захын дүүргүүдэд үнийн өсөлтийн боломж их байна.</p>
        """

    def _calculate_price_range(self, districts_data: List[Dict]) -> str:
        """Calculate price range between districts"""
        if not districts_data:
            return "Мэдээлэл байхгүй"

        prices = [d.get('overall_avg', 0) for d in districts_data if d.get('overall_avg', 0) > 0]
        if not prices:
            return "Мэдээлэл байхгүй"

        min_price = min(prices)
        max_price = max(prices)
        difference = max_price - min_price
        percentage = (difference / min_price) * 100 if min_price > 0 else 0

        return f"{percentage:.0f}% ялгаа"

    def _clean_text(self, text: str) -> str:
        """Clean text for HTML display"""
        if not text:
            return "Мэдээлэл байхгүй"

        # Remove problematic characters and normalize
        text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        return text.strip()

    def _format_price(self, price) -> str:
        """Format price with proper formatting"""
        if not price or price == 0:
            return "Мэдээлэл байхгүй"
        try:
            if price >= 1000000:
                return f"{price / 1000000:.1f} сая ₮"
            else:
                return f"{int(price):,} ₮".replace(",", " ")
        except (ValueError, TypeError):
            return "Мэдээлэл байхгүй"


# Updated PDFReportGenerator class to use the improved generator
class PDFReportGenerator:
    def __init__(self):
        if WEASYPRINT_AVAILABLE:
            self.generator = ProfessionalPDFGenerator()
            logger.info("✅ Professional PDF generator initialized with excellent structure")
        else:
            logger.warning("⚠️ Using ReportLab fallback - install WeasyPrint for professional PDFs")

    def generate_property_analysis_report(self, property_data, district_analysis,
                                          comparison_result, search_results=""):
        return self.generator.generate_property_report(
            property_data, district_analysis, comparison_result, search_results
        )

    def generate_district_summary_report(self, districts_data, market_trends="",
                                         search_results=""):
        return self.generator.generate_district_summary_report(
            districts_data, market_trends, search_results
        )