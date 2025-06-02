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
    """Handles HTML formatting and text processing for PDF generation"""

    def clean_text_for_html(self, text: Any) -> str:
        """Clean and escape text for HTML output, and handle newlines."""
        if text is None:
            return ERROR_MESSAGES.get("no_data", "Мэдээлэл байхгүй")
        text_str = str(text)

        # 1. Convert any explicit <br> tags from LLM (or other sources) into newlines first.
        # This helps standardize newline representation before HTML conversion.
        text_str = re.sub(r'<br\s*/?>', '\n', text_str, flags=re.IGNORECASE)

        # 2. Standard HTML escaping for security to prevent XSS if text comes from unsafe sources.
        # This will convert characters like <, >, & into their HTML entities.
        text_str = text_str.replace('&', '&amp;')
        text_str = text_str.replace('<', '&lt;')
        text_str = text_str.replace('>', '&gt;')
        # text_str = text_str.replace('"', '&quot;') # Optional: if quotes in attributes are an issue
        # text_str = text_str.replace("'", '&#39;')  # Optional: if single quotes are an issue

        # 3. Now, convert newlines (both original and from replaced <br> tags)
        # into <br> HTML tags for PDF rendering.
        # This must happen AFTER HTML escaping of < and > to prevent <br> from becoming &lt;br&gt;.
        text_str = text_str.replace('\n\n', '<br><br>')
        text_str = text_str.replace('\n', '<br>')

        # 4. Consolidate multiple spaces and strip leading/trailing whitespace.
        text_str = re.sub(r' +', ' ', text_str).strip()
        return text_str

    def format_price_html(self, price: Any) -> str:
        """Format price for HTML display"""
        if price is None or price == "" or str(price).lower() == ERROR_MESSAGES.get("no_data", "мэдээлэл байхгүй").lower():
            return ERROR_MESSAGES.get("no_data", "Мэдээлэл байхгүй")
        try:
            price_num = float(price)
            if price_num == 0: # Explicitly handle 0 if it should be "Мэдээлэл байхгүй" or "0 ₮"
                 return "0 " + PRICE_FORMAT.get('currency', '₮') # Or ERROR_MESSAGES["no_data"] if 0 means no data

            # Use .get for dictionary access with fallbacks
            million_threshold = PRICE_FORMAT.get("million_threshold", 1000000)
            decimal_places = PRICE_FORMAT.get("decimal_places", 1)
            million_suffix = PRICE_FORMAT.get("million_suffix", "сая ₮")
            currency_symbol = PRICE_FORMAT.get("currency", "₮")

            if price_num >= million_threshold:
                return f"{price_num / million_threshold:.{decimal_places}f} {million_suffix}"
            return f"{int(price_num):,} {currency_symbol}".replace(',', ' ')
        except (ValueError, TypeError):
            # If conversion fails, clean the original string representation and return it.
            return self.clean_text_for_html(str(price))


    def should_include_search_results(self, search_results: str) -> bool:
        """Check if search results should be included in the report"""
        # This was set to always False. If you want to include search results based on content:
        # return bool(search_results and search_results.strip() and \
        #             "олдсонгүй" not in search_results and \
        #             "хайлт хийгдсэнгүй" not in search_results)
        return False # Keeping original logic unless specified otherwise

    def get_base_css(self) -> str:
        """Generate CSS with font fallback mechanisms"""
        font_primary = FONT_FAMILY_NAMES.get("primary", "NotoSans")
        font_secondary = FONT_FAMILY_NAMES.get("secondary", "Arial, Helvetica, sans-serif")
        font_fallback = FONT_FAMILY_NAMES.get("fallback", "DejaVuSans, Arial Unicode MS, sans-serif")

        regular_font_path = get_font_path("regular")
        bold_font_path = get_font_path("bold")

        # Ensure paths are correctly formatted for CSS URL, especially if they might contain spaces
        # or special characters (though pathlib should handle this well for local files)
        css_regular_font_path = regular_font_path.replace("\\", "/") # Ensure forward slashes for CSS
        css_bold_font_path = bold_font_path.replace("\\", "/")     # Ensure forward slashes for CSS


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