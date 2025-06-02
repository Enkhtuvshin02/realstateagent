import re
import logging
from typing import Any
from config.pdf_config import (
    ERROR_MESSAGES, PRICE_FORMAT, FONT_FAMILY_NAMES, FONT_SIZES,
    COLORS, SPACING, PDF_PAGE_CONFIG
)
from utils.font_manager import get_font_path

logger = logging.getLogger(__name__)


class HTMLFormatter:

    def clean_text_for_html(self, text: Any) -> str:
        if text is None:
            return ERROR_MESSAGES.get("no_data", "Мэдээлэл байхгүй")
        text_str = str(text)

        text_str = re.sub(r'<br\s*/?>', '\n', text_str, flags=re.IGNORECASE)

        text_str = text_str.replace('&', '&amp;')
        text_str = text_str.replace('<', '&lt;')
        text_str = text_str.replace('>', '&gt;')
        text_str = text_str.replace('\n\n', '<br><br>')
        text_str = text_str.replace('\n', '<br>')

        text_str = re.sub(r' +', ' ', text_str).strip()
        return text_str

    def format_price_html(self, price: Any) -> str:
        if price is None or price == "" or str(price).lower() == ERROR_MESSAGES.get("no_data", "мэдээлэл байхгүй").lower():
            return ERROR_MESSAGES.get("no_data", "Мэдээлэл байхгүй")
        try:
            price_num = float(price)
            if price_num == 0:
                 return "0 " + PRICE_FORMAT.get('currency', '₮')

            million_threshold = PRICE_FORMAT.get("million_threshold", 1000000)
            decimal_places = PRICE_FORMAT.get("decimal_places", 1)
            million_suffix = PRICE_FORMAT.get("million_suffix", "сая ₮")
            currency_symbol = PRICE_FORMAT.get("currency", "₮")

            if price_num >= million_threshold:
                return f"{price_num / million_threshold:.{decimal_places}f} {million_suffix}"
            return f"{int(price_num):,} {currency_symbol}".replace(',', ' ')
        except (ValueError, TypeError):
            return self.clean_text_for_html(str(price))


    def should_include_search_results(self, search_results: str) -> bool:
        return False

    def get_base_css(self) -> str:
        font_primary = FONT_FAMILY_NAMES.get("primary", "NotoSans")
        font_secondary = FONT_FAMILY_NAMES.get("secondary", "Arial, Helvetica, sans-serif")
        font_fallback = FONT_FAMILY_NAMES.get("fallback", "DejaVuSans, Arial Unicode MS, sans-serif")

        regular_font_path = get_font_path("regular")
        bold_font_path = get_font_path("bold")

        css_regular_font_path = regular_font_path.replace("\\", "/")
        css_bold_font_path = bold_font_path.replace("\\", "/")


        return f"""
        @font-face {{
            font-family: '{font_primary}';
            src: url('{css_regular_font_path}');
            font-weight: normal;
            font-style: normal;
        }}

        @font-face {{
            font-family: '{font_primary}';
            src: url('{css_bold_font_path}');
            font-weight: bold;
            font-style: normal;
        }}

        body {{
            font-family: "{font_primary}", {font_secondary}, {font_fallback};
            font-size: {FONT_SIZES.get("body", "12pt")}; 
            line-height: {SPACING.get("line_height", "1.5")};
            margin: {SPACING.get("margin_body", "0")};
            color: {COLORS.get("text_primary", "#333333")};
        }}

        h1, h2, h3, h4 {{
            font-family: "{font_primary}", {font_secondary}, {font_fallback};
            color: {COLORS.get("text_header", "#1a1a1a")};
            margin-bottom: 0.5em;
        }}

        h1 {{
            font-size: {FONT_SIZES.get("h1", "20pt")};
            text-align: center;
            margin-bottom: 1em;
        }}

        h2 {{
            font-size: {FONT_SIZES.get("h2", "16pt")};
            border-bottom: 1px solid {COLORS.get("border_light", "#e0e0e0")};
            padding-bottom: 0.2em;
            margin-top: {SPACING.get("margin_h2_top", "1.5em")};
            font-weight: bold;
        }}

        h3 {{
            font-size: {FONT_SIZES.get("h3", "14pt")};
            margin-top: {SPACING.get("margin_h3_top", "1.2em")};
            font-weight: bold;
        }}

        p {{
            margin-bottom: {SPACING.get("margin_p_bottom", "0.8em")};
        }}

        .report-date, .footer-text {{
            text-align: right;
            font-size: {FONT_SIZES.get("small", "10pt")};
            color: {COLORS.get("text_secondary", "#666666")};
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
            border: 1px solid {COLORS.get("border", "#cccccc")};
            padding: {SPACING.get("padding_cell", "8px")};
            text-align: left;
            word-wrap: break-word;
        }}

        th {{
            background-color: {COLORS.get("background_light", "#f5f5f5")};
            font-weight: bold;
        }}

        .property-details div, .price-highlight div {{
            margin-bottom: 5px;
        }}

        .price-highlight {{
            border: 1px solid {COLORS.get("border_light", "#e0e0e0")};
            padding: {SPACING.get("padding_highlight", "12px")};
            margin-top: 10px;
            background-color: {COLORS.get("background_highlight", "#f0f7ff")};
        }}

        .price-main {{
            font-size: {FONT_SIZES.get("price_highlight", "14pt")};
            font-weight: bold;
        }}

        .section {{
            margin-bottom: {SPACING.get("margin_section", "1.8em")};
            page-break-inside: avoid;
            padding-top: 1em; /* Add padding to create space for the border */
            border-top: 1px solid {COLORS.get("border_light", "#e0e0e0")}; /* Add a light border */
        }}
        
        .section:first-of-type {{ /* Remove top border and padding for the very first section */
            border-top: none;
            padding-top: 0;
        }}


        @page {{
            size: {PDF_PAGE_CONFIG.get("size", "A4")};
            margin: {PDF_PAGE_CONFIG.get("margin", "2cm 2cm 2.5cm 2cm")};
            @frame footer_frame {{
                -pdf-frame-content: footer_content;
                left: {PDF_PAGE_CONFIG.get("footer_left", "2cm")};
                width: {PDF_PAGE_CONFIG.get("footer_width", "17cm")};
                top: {PDF_PAGE_CONFIG.get("footer_top", "26.5cm")}; /* Adjusted for A4 default, might need fine-tuning */
                height: {PDF_PAGE_CONFIG.get("footer_height", "1cm")};
            }}
        }}
        """