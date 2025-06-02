
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from xhtml2pdf import pisa


from config.pdf_constants import (
    CYRILLIC_FONTS, FONT_FAMILY_NAMES, FONTS_DIR, get_font_path,
    PDF_PAGE_CONFIG, FONT_SIZES, COLORS, SPACING, REPORT_TEMPLATES,
    TABLE_CONFIG, ERROR_MESSAGES, PRICE_FORMAT, INVESTMENT_THRESHOLDS,
    DATE_FORMATS, FILE_CONFIG
)

logger = logging.getLogger(__name__)


class XHTML2PDFGenerator:

    def __init__(self):
        self.reports_dir = Path(FILE_CONFIG["reports_dir"])
        self.reports_dir.mkdir(exist_ok=True)


        self._validate_fonts()

        logger.info(f"XHTML2PDFGenerator initialized. Font path: {get_font_path()}")

    def _validate_fonts(self) -> None:
        primary_font = FONTS_DIR / CYRILLIC_FONTS["regular"]
        if not primary_font.exists():
            logger.error(
                ERROR_MESSAGES["font_missing"].format(
                    CYRILLIC_FONTS["regular"],
                    FONTS_DIR
                )
            )

    def _clean_text_for_html(self, text: Any) -> str:
        if text is None:
            return ERROR_MESSAGES["no_data"]

        text_str = str(text)

        text_str = text_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        text_str = text_str.replace('\n\n', '<br><br>').replace('\n', '<br>')

        text_str = re.sub(r' +', ' ', text_str).strip()
        return text_str

    def _format_price_html(self, price: Any) -> str:
        if price is None or price == 0 or str(price).lower() == ERROR_MESSAGES["no_data"]:
            return ERROR_MESSAGES["no_data"]

        try:
            price_num = float(price)
            if price_num >= PRICE_FORMAT["million_threshold"]:
                return f"{price_num / PRICE_FORMAT['million_threshold']:.{PRICE_FORMAT['decimal_places']}f} {PRICE_FORMAT['million_suffix']}"
            return f"{int(price_num):,} {PRICE_FORMAT['currency']}"
        except (ValueError, TypeError):
            return self._clean_text_for_html(str(price))

    def _generate_pdf_from_html(self, html_content: str, output_filepath: str) -> bool:
        try:
            with open(output_filepath, "w+b") as result_file:
                pisa_status = pisa.CreatePDF(
                    html_content,
                    dest=result_file,
                    encoding='UTF-8',
                    link_callback=self._link_callback
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

    def _link_callback(self, uri: str, rel: str) -> str:
        from pathlib import Path
        import os
        return os.path.join(str(FONTS_DIR.parent), uri.replace(f"file://{FONTS_DIR.parent}/", ""))

    def _get_base_css(self) -> str:
        return f"""
        @font-face {{
            font-family: '{FONT_FAMILY_NAMES["primary"]}';
            src: url('{get_font_path("regular")}');
        }}

        body {{
            font-family: '{FONT_FAMILY_NAMES["primary"]}', {FONT_FAMILY_NAMES["secondary"]};
            font-size: {FONT_SIZES["body"]};
            line-height: {SPACING["line_height"]};
            margin: {SPACING["margin_body"]};
            color: {COLORS["text_primary"]};
        }}

        h1, h2, h3, h4 {{
            font-family: '{FONT_FAMILY_NAMES["primary"]}', {FONT_FAMILY_NAMES["secondary"]};
            color: {COLORS["text_header"]};
            margin-bottom: 0.5em;
        }}

        h1 {{ 
            font-size: {FONT_SIZES["h1"]}; 
            text-align: center; 
            margin-bottom: 1em; 
        }}

        h2 {{ 
            font-size: {FONT_SIZES["h2"]}; 
            border-bottom: 1px solid {COLORS["border_light"]}; 
            padding-bottom: 0.2em; 
            margin-top: {SPACING["margin_h2_top"]};
        }}

        h3 {{ 
            font-size: {FONT_SIZES["h3"]}; 
            margin-top: {SPACING["margin_h3_top"]}; 
        }}

        p {{ 
            margin-bottom: {SPACING["margin_p_bottom"]}; 
        }}

        .report-date, .footer-text {{
            text-align: right;
            font-size: {FONT_SIZES["small"]};
            color: {COLORS["text_secondary"]};
        }}

        .footer-text {{ 
            text-align: center; 
            margin-top: 2em; 
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1em;
            margin-bottom: 1em;
        }}

        th, td {{
            border: 1px solid {COLORS["border"]};
            padding: {SPACING["padding_cell"]};
            text-align: left;
            word-wrap: break-word;
        }}

        th {{
            background-color: {COLORS["background_light"]};
            font-weight: bold;
        }}

        .property-details div, .price-highlight div {{ 
            margin-bottom: 5px; 
        }}

        .price-highlight {{
            border: 1px solid {COLORS["border_light"]};
            padding: {SPACING["padding_highlight"]};
            margin-top: 10px;
            background-color: {COLORS["background_highlight"]};
        }}

        .price-main {{ 
            font-size: {FONT_SIZES["price_highlight"]}; 
            font-weight: bold; 
        }}

        .section {{ 
            margin-bottom: {SPACING["margin_section"]}; 
            page-break-inside: avoid; 
        }}

        @page {{
            size: {PDF_PAGE_CONFIG["size"]};
            margin: {PDF_PAGE_CONFIG["margin"]};
            @frame footer_frame {{
                -pdf-frame-content: footer_content;
                left: {PDF_PAGE_CONFIG["footer_left"]}; 
                width: {PDF_PAGE_CONFIG["footer_width"]}; 
                top: {PDF_PAGE_CONFIG["footer_top"]}; 
                height: {PDF_PAGE_CONFIG["footer_height"]};
            }}
        }}
        """

    def _generate_investment_recommendation(self, price_per_sqm: float) -> str:
        if price_per_sqm > INVESTMENT_THRESHOLDS["expensive"]:
            return INVESTMENT_THRESHOLDS["messages"]["expensive"]
        elif price_per_sqm < INVESTMENT_THRESHOLDS["affordable"]:
            return INVESTMENT_THRESHOLDS["messages"]["affordable"]
        else:
            return INVESTMENT_THRESHOLDS["messages"]["moderate"]

    def _should_include_search_results(self, search_results: str) -> bool:
        if not search_results:
            return False
        cleaned_results = search_results.lower().strip()
        return cleaned_results not in ERROR_MESSAGES["search_failed"]

    def generate_property_report(self, property_data: Dict[str, Any], district_analysis: str, comparison_result: str, search_results: str = "") -> str:
        timestamp = datetime.now().strftime(DATE_FORMATS["filename"])
        filename = f"{FILE_CONFIG['property_prefix']}{timestamp}{FILE_CONFIG['extension']}"
        filepath = self.reports_dir / filename

        prop_title = self._clean_text_for_html(property_data.get('title', 'Орон сууцны шинжилгээ'))
        location = self._clean_text_for_html(property_data.get('full_location', 'Тодорхойгүй'))
        district = self._clean_text_for_html(property_data.get('district', 'Тодорхойгүй'))
        area = property_data.get('area_sqm', 0)
        rooms = property_data.get('room_count', 0)
        price = self._format_price_html(property_data.get('price_numeric', 0))
        price_per_sqm = self._format_price_html(property_data.get('price_per_sqm', 0))

        cleaned_district_analysis = self._clean_text_for_html(district_analysis)
        cleaned_comparison_result = self._clean_text_for_html(comparison_result)
        cleaned_search_results = self._clean_text_for_html(search_results)

        html = self._build_property_html(
            prop_title, location, district, area, rooms, price, price_per_sqm,
            cleaned_district_analysis, cleaned_comparison_result, cleaned_search_results,
            property_data.get('price_per_sqm', 0)
        )

        if self._generate_pdf_from_html(html, str(filepath)):
            return str(filepath)
        else:
            return ERROR_MESSAGES["pdf_generation_failed"].format("property", CYRILLIC_FONTS["regular"])

    def _build_property_html(self, title: str, location: str, district: str, area: float, rooms: int, price: str, price_per_sqm: str, district_analysis: str, comparison_result: str, search_results: str, price_per_sqm_numeric: float) -> str:
        now = datetime.now()

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self._get_base_css()}</style>
            <title>{REPORT_TEMPLATES['property']['title']}</title>
        </head>
        <body>
            <h1>{REPORT_TEMPLATES['property']['title']}</h1>
            <p class="report-date">Тайлангийн огноо: {now.strftime(DATE_FORMATS['mongolian'])}</p>

            <div class="section property-details">
                <h2>{REPORT_TEMPLATES['property']['sections'][0]}</h2>
                <div><strong>Гарчиг:</strong> {title}</div>
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
                <h2>{REPORT_TEMPLATES['property']['sections'][1]}</h2>
                <p>{district_analysis}</p>
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][2]}</h2>
                <p>{comparison_result}</p>
            </div>
        """

        if self._should_include_search_results(search_results):
            html += f"""
            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][3]}</h2>
                <p>{search_results}</p>
            </div>
            """

        investment_advice = self._generate_investment_recommendation(price_per_sqm_numeric)
        html += f"""
            <div class="section">
                <h2> {REPORT_TEMPLATES['property']['sections'][4]} (Жишээ)</h2>
                <p>{investment_advice}</p>
            </div>
        </body>
        </html>
        """

        return html

    def generate_district_summary_report(self, districts_data: List[Dict], market_trends: str = "", search_results: str = "") -> str:
        timestamp = datetime.now().strftime(DATE_FORMATS["filename"])
        filename = f"{FILE_CONFIG['district_prefix']}{timestamp}{FILE_CONFIG['extension']}"
        filepath = self.reports_dir / filename

        cleaned_market_trends = self._clean_text_for_html(market_trends)
        cleaned_search_results = self._clean_text_for_html(search_results)

        html = self._build_district_html(districts_data, cleaned_market_trends, cleaned_search_results)

        if self._generate_pdf_from_html(html, str(filepath)):
            return str(filepath)
        else:
            return ERROR_MESSAGES["pdf_generation_failed"].format("district summary", CYRILLIC_FONTS["regular"])

    def _build_district_html(self, districts_data: List[Dict], market_trends: str, search_results: str) -> str:
        now = datetime.now()

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self._get_base_css()}</style>
            <title>{REPORT_TEMPLATES['district']['title']}</title>
        </head>
        <body>
            <div id="footer_content" class="footer-text">
                Тайлан үүсгэсэн: {now.strftime(DATE_FORMATS['display'])} | Хуудас <pdf:pagenumber />
            </div>

            <h1>{REPORT_TEMPLATES['district']['title']}</h1>
            <p class="report-date">Тайлангийн огноо: {now.strftime(DATE_FORMATS['mongolian'])}</p>

            <div class="section">
                <h2{REPORT_TEMPLATES['district']['sections'][0]}</h2>
        """

        html += self._build_districts_table(districts_data)
        html += "</div>"

        html += f"""
            <div class="section">
                <h2{REPORT_TEMPLATES['district']['sections'][1]}</h2>
                <p>{market_trends if market_trends else 'Зах зээлийн ерөнхий чиг хандлагын мэдээлэл олдсонгүй.'}</p>
            </div>
        """

        if self._should_include_search_results(search_results):
            html += f"""
            <div class="section">
                <h2{REPORT_TEMPLATES['district']['sections'][2]}</h2>
                <p>{search_results}</p>
            </div>
            """

        html += """
            <p class="footer-text">Үл хөдлөх хөрөнгийн мэргэжлийн туслах системээр автоматаар үүсгэсэн.</p>
        </body>
        </html>
        """

        return html

    def _build_districts_table(self, districts_data: List[Dict]) -> str:
        if not districts_data:
            return "<p>Дүүргийн мэдээлэл байхгүй.</p>"

        table_config = TABLE_CONFIG["district_comparison"]
        districts_sorted = sorted(
            districts_data,
            key=lambda x: x.get(table_config["sort_key"], 0),
            reverse=True
        )

        html = f"""
            <table>
                <thead>
                    <tr>
        """

        for header in table_config["headers"]:
            html += f"<th>{header}</th>"

        html += """
                    </tr>
                </thead>
                <tbody>
        """

        for district in districts_sorted:
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

        return html


class PDFReportGenerator:
    def __init__(self):
        self.generator = XHTML2PDFGenerator()

    def generate_property_analysis_report(self, property_data: Dict[str, Any], district_analysis: str, comparison_result: str, search_results: str = "") -> str:
        if not self.generator:
            logger.error("xhtml2pdf PDF generator is not available.")
            raise RuntimeError("xhtml2pdf PDF generator is not available for property report.")

        return self.generator.generate_property_report(
            property_data, district_analysis, comparison_result, search_results
        )

    def generate_district_summary_report(self, districts_data: List[Dict], market_trends: str = "", search_results: str = "") -> str:
        if not self.generator:
            logger.error("xhtml2pdf PDF generator is not available.")
            raise RuntimeError("xhtml2pdf PDF generator is not available for district report.")

        return self.generator.generate_district_summary_report(
            districts_data, market_trends, search_results
        )