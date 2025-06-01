# utils/xhtml2pdf_generator.py - PDF generation using xhtml2pdf (for Mongolian Cyrillic)
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import re

from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

# --- IMPORTANT FONT CONFIGURATION ---
# This should be the name of the font file you placed in static/fonts/
# Noto Sans (Regular) is a good choice for Mongolian Cyrillic.
CYRILLIC_FONT_FILENAME = "NotoSans-Regular.ttf"
FONT_FAMILY_NAME_CSS = "NotoSansCustom" # Name to use in CSS

# Base path for resolving static files like fonts
# Assumes this script is in 'utils' and 'static' is a sibling of 'utils' or at project root.
# Adjust if your project structure is different.
# For simplicity, assuming 'static' is at the project root from where main.py runs.
BASE_DIR = Path(os.getcwd()) # Current working directory, should be project root
STATIC_DIR = BASE_DIR / "static"
FONT_PATH_CSS = f"file://{STATIC_DIR / 'fonts' / CYRILLIC_FONT_FILENAME}"

class XHTML2PDFGenerator:
    """PDF generator using xhtml2pdf, configured for Mongolian Cyrillic."""

    def __init__(self):
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
        logger.info(f"XHTML2PDFGenerator initialized. Font expected at: {FONT_PATH_CSS}")
        if not (STATIC_DIR / "fonts" / CYRILLIC_FONT_FILENAME).exists():
            logger.error(
                f"CRITICAL FONT MISSING: {CYRILLIC_FONT_FILENAME} not found in {STATIC_DIR / 'fonts'}. "
                "Mongolian Cyrillic text will NOT render correctly. "
                "Please download NotoSans-Regular.ttf (or your chosen Cyrillic font) "
                f"and place it in {STATIC_DIR / 'fonts'}."
            )

    def _clean_text_for_html(self, text: Any) -> str:
        if text is None:
            return "Мэдээлэл байхгүй"
        text_str = str(text)
        # Basic HTML escaping
        text_str = text_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Preserve newlines for <pre> or CSS white-space: pre-wrap, or convert to <br>
        text_str = text_str.replace('\n\n', '<br><br>').replace('\n', '<br>')
        # Remove excessive spaces that might remain from other processing
        text_str = re.sub(r' +', ' ', text_str).strip()
        return text_str

    def _format_price_html(self, price: Any) -> str:
        if price is None or price == 0 or str(price).lower() == "мэдээлэл байхгүй":
            return "Мэдээлэл байхгүй"
        try:
            price_num = float(price)
            if price_num >= 1_000_000:
                return f"{price_num / 1_000_000:.1f} сая ₮"
            return f"{int(price_num):,} ₮" # Commas will be rendered as is by browsers/pdf
        except (ValueError, TypeError):
            return self._clean_text_for_html(str(price))

    def _generate_pdf_from_html(self, html_content: str, output_filepath: str) -> bool:
        """Converts HTML content to PDF and saves it."""
        try:
            with open(output_filepath, "w+b") as result_file:
                # link_callback is important for xhtml2pdf to find local resources like fonts
                # Pass the base path for static files
                pisa_status = pisa.CreatePDF(
                    html_content,
                    dest=result_file,
                    encoding='UTF-8',
                    link_callback=lambda uri, rel: os.path.join(STATIC_DIR, uri.replace(f"file://{STATIC_DIR}/", ""))
                )

            if pisa_status.err:
                logger.error(f"Error generating PDF with xhtml2pdf: {pisa_status.err}")
                logger.error(f"HTML content that failed (first 500 chars): {html_content[:500]}")
                return False
            logger.info(f"xhtml2pdf report generated successfully: {output_filepath}")
            return True
        except Exception as e:
            logger.error(f"Exception during PDF generation with xhtml2pdf: {e}", exc_info=True)
            logger.error(f"HTML content that failed (first 500 chars): {html_content[:500]}")
            return False

    def _get_base_css(self) -> str:
        # Ensure the @font-face src path is correct and accessible by xhtml2pdf
        # The FONT_PATH_CSS should be an absolute file:// URL
        return f"""
        @font-face {{
            font-family: '{FONT_FAMILY_NAME_CSS}';
            src: url('{FONT_PATH_CSS}');
            /* Include bold/italic versions if you have them and need them */
            /* src: url('file://{STATIC_DIR / 'fonts' / 'NotoSans-Bold.ttf'}') format('truetype'); */
        }}
        body {{
            font-family: '{FONT_FAMILY_NAME_CSS}', sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            margin: 0.5in;
            color: #333;
        }}
        h1, h2, h3, h4 {{
            font-family: '{FONT_FAMILY_NAME_CSS}', sans-serif;
            color: #111;
            margin-bottom: 0.5em;
        }}
        h1 {{ font-size: 20pt; text-align: center; margin-bottom: 1em; }}
        h2 {{ font-size: 16pt; border-bottom: 1px solid #eee; padding-bottom: 0.2em; margin-top: 1.5em;}}
        h3 {{ font-size: 13pt; margin-top: 1.2em; }}
        p {{ margin-bottom: 0.8em; }}
        .report-date, .footer-text {{
            text-align: right;
            font-size: 8pt;
            color: #777;
        }}
        .footer-text {{ text-align: center; margin-top: 2em; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1em;
            margin-bottom: 1em;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 6px;
            text-align: left;
            word-wrap: break-word; /* Help with long words in table cells */
        }}
        th {{
            background-color: #f0f0f0;
            font-weight: bold;
        }}
        .property-details div, .price-highlight div {{ margin-bottom: 5px; }}
        .price-highlight {{
            border: 1px solid #ddd;
            padding: 10px;
            margin-top:10px;
            background-color: #f9f9f9;
        }}
        .price-main {{ font-size: 1.2em; font-weight: bold; }}
        .section {{ margin-bottom: 20px; page-break-inside: avoid; }}
        /* Add other styles as needed */
        @page {{
            size: a4 portrait;
            margin: 1cm; /* Default margin */
            @frame footer_frame {{
                -pdf-frame-content: footer_content;
                left: 50pt; width: 500pt; top: 770pt; height: 20pt;
            }}
        }}
        """

    def generate_property_report(self, property_data: Dict[str, Any],
                                 district_analysis: str,
                                 comparison_result: str, # This was detailed_analysis_mn from ReportService
                                 search_results: str = "") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"property_analysis_xhtml2pdf_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        # Clean data for HTML
        prop_title = self._clean_text_for_html(property_data.get('title', 'Орон сууцны шинжилгээ'))
        location = self._clean_text_for_html(property_data.get('full_location', 'Тодорхойгүй'))
        district = self._clean_text_for_html(property_data.get('district', 'Тодорхойгүй'))
        area = property_data.get('area_sqm', 0)
        rooms = property_data.get('room_count', 0)
        price = self._format_price_html(property_data.get('price_numeric', 0))
        price_per_sqm = self._format_price_html(property_data.get('price_per_sqm', 0))

        cleaned_district_analysis = self._clean_text_for_html(district_analysis)
        cleaned_comparison_result = self._clean_text_for_html(comparison_result) # was detailed_analysis
        cleaned_search_results = self._clean_text_for_html(search_results)

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self._get_base_css()}</style>
            <title>Орон сууцны дэлгэрэнгүй шинжилгээ</title>
        </head>
        <body>
            <div id="footer_content" class="footer-text">
                Тайлан үүсгэсэн: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Хуудас <pdf:pagenumber />
            </div>

            <h1>🏠 Орон сууцны дэлгэрэнгүй шинжилгээ</h1>
            <p class="report-date">Тайлангийн огноо: {datetime.now().strftime('%Y оны %m сарын %d өдөр')}</p>

            <div class="section property-details">
                <h2>Үндсэн мэдээлэл</h2>
                <div><strong>Гарчиг:</strong> {prop_title}</div>
                <div><strong>Байршил:</strong> {location}</div>
                <div><strong>Дүүрэг:</strong> {district}</div>
                <div><strong>Талбай:</strong> {area} м²</div>
                <div><strong>Өрөөний тоо:</strong> {rooms} өрөө</div>
                <div class="price-highlight">
                    <div class="price-main">Нийт үнэ: {price}</div>
                    <div class="price-main">м² үнэ: {price_per_sqm}</div>
                </div>
            </div>

            <div class="section">
                <h2>🏘️ Дүүргийн зах зээлийн шинжилгээ</h2>
                <p>{cleaned_district_analysis}</p>
            </div>

            <div class="section">
                <h2>🧠 Chain-of-Thought дэлгэрэнгүй шинжилгээ</h2>
                <p>{cleaned_comparison_result}</p>
            </div>

            """
        if search_results and cleaned_search_results and cleaned_search_results.lower() not in ["мэдээлэл байхгүй", "интернэт хайлт хийхэд алдаа гарлаа.", "интернэт хайлтаас мэдээлэл олдсонгүй."]:
            html += f"""
            <div class="section">
                <h2>🔍 Интернэт судалгааны үр дүн</h2>
                <p>{cleaned_search_results}</p>
            </div>
            """
        html += """
            <div class="section">
                <h2>💡 Хөрөнгө оруулалтын зөвлөмж (Жишээ)</h2>
        """
        # Simplified recommendations based on your previous logic
        price_per_sqm_numeric = property_data.get('price_per_sqm', 0)
        if price_per_sqm_numeric > 4500000:
            html += "<p>⚠️ Үнэ өндөр түвшинд байгаа тул тохиролцох боломжийг авч үзэх.</p>"
        elif price_per_sqm_numeric < 2500000:
            html += "<p>💰 Зах зээлээс доогуур үнэтэй - хөрөнгө оруулалтын боломжтой.</p>"
        else:
            html += "<p>✅ Зах зээлийн дундаж үнэтэй - тохиромжтой үнэ.</p>"
        html += """
            </div>
             <p class="footer-text">Үл хөдлөх хөрөнгийн мэргэжлийн туслах системээр автоматаар үүсгэсэн.</p>
        </body>
        </html>
        """

        if self._generate_pdf_from_html(html, str(filepath)):
            return str(filepath)
        else:
            # Fallback or error indication
            return f"ERROR: Could not generate PDF for property report. Check logs. Missing font '{CYRILLIC_FONT_FILENAME}' could be an issue."

    def generate_district_summary_report(self, districts_data: List[Dict],
                                         market_trends: str = "",
                                         search_results: str = "") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"district_summary_xhtml2pdf_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        cleaned_market_trends = self._clean_text_for_html(market_trends)
        cleaned_search_results = self._clean_text_for_html(search_results)

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self._get_base_css()}</style>
            <title>Дүүргийн харьцуулалтын тайлан</title>
        </head>
        <body>
            <div id="footer_content" class="footer-text">
                 Тайлан үүсгэсэн: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Хуудас <pdf:pagenumber />
            </div>

            <h1>🏘️ Дүүргийн харьцуулалтын тайлан</h1>
            <p class="report-date">Тайлангийн огноо: {datetime.now().strftime('%Y оны %m сарын %d өдөр')}</p>

            <div class="section">
                <h2>📊 Дүүргүүдийн үнийн харьцуулалт</h2>
        """
        if districts_data:
            districts_data_sorted = sorted(districts_data, key=lambda x: x.get('overall_avg', 0), reverse=True)
            html += """
                <table>
                    <thead>
                        <tr>
                            <th>Дүүрэг</th>
                            <th>Дундаж үнэ (₮/м²)</th>
                            <th>2 өрөө (₮/м²)</th>
                            <th>3 өрөө (₮/м²)</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for district in districts_data_sorted:
                name = self._clean_text_for_html(district.get('name', 'N/A'))
                overall = self._format_price_html(district.get('overall_avg', 0))
                two_room = self._format_price_html(district.get('two_room_avg', 0))
                three_room = self._format_price_html(district.get('three_room_avg', 0))
                html += f"""
                        <tr>
                            <td>{name}</td>
                            <td>{overall}</td>
                            <td>{two_room}</td>
                            <td>{three_room}</td>
                        </tr>
                """
            html += """
                    </tbody>
                </table>
            """
        else:
            html += "<p>Дүүргийн мэдээлэл байхгүй.</p>"
        html += "</div>" # End section for table

        html += f"""
            <div class="section">
                <h2>📈 Зах зээлийн шинжилгээ</h2>
                <p>{cleaned_market_trends if cleaned_market_trends else 'Зах зээлийн ерөнхий чиг хандлагын мэдээлэл олдсонгүй.'}</p>
            </div>
        """

        if search_results and cleaned_search_results and cleaned_search_results.lower() not in ["мэдээлэл байхгүй", "интернэт хайлт хийхэд алдаа гарлаа.", "интернэт хайлтаас мэдээлэл олдсонгүй."]:
            html += f"""
            <div class="section">
                <h2>🔍 Интернэт судалгааны үр дүн</h2>
                <p>{cleaned_search_results}</p>
            </div>
            """
        html += """
             <p class="footer-text">Үл хөдлөх хөрөнгийн мэргэжлийн туслах системээр автоматаар үүсгэсэн.</p>
        </body>
        </html>
        """

        if self._generate_pdf_from_html(html, str(filepath)):
            return str(filepath)
        else:
            return f"ERROR: Could not generate PDF for district summary. Check logs. Missing font '{CYRILLIC_FONT_FILENAME}' could be an issue."


# Wrapper class to maintain consistency with how PDFReportGenerator was used
class PDFReportGenerator:
    def __init__(self):
        self.generator = XHTML2PDFGenerator()
        logger.info("✅ PDF generator (xhtml2pdf) initialized for Mongolian Cyrillic.")

    def generate_property_analysis_report(self, property_data, district_analysis,
                                          comparison_result, search_results=""):
        if not self.generator:
            logger.error("xhtml2pdf PDF generator is not available.")
            raise RuntimeError("xhtml2pdf PDF generator is not available for property report.")
        return self.generator.generate_property_report(
            property_data, district_analysis, comparison_result, search_results
        )

    def generate_district_summary_report(self, districts_data, market_trends="",
                                         search_results=""):
        if not self.generator:
            logger.error("xhtml2pdf PDF generator is not available.")
            raise RuntimeError("xhtml2pdf PDF generator is not available for district report.")
        return self.generator.generate_district_summary_report(
            districts_data, market_trends, search_results
        )

