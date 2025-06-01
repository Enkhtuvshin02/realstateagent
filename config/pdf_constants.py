# real_estate_assistant/config/pdf_constants.py - PDF үүсгэгчийн тогтмол үтгүүд

from pathlib import Path
import os

# === ФОНТ ТОХИРГОО ===
# Монгол кирилл бичгийн фонт файлууд
CYRILLIC_FONTS = {
    "regular": "NotoSans-Regular.ttf",
    "bold": "NotoSans-Bold.ttf",
    "italic": "NotoSans-Italic.ttf"
}

# CSS-д ашиглах фонтын нэрс
FONT_FAMILY_NAMES = {
    "primary": "NotoSansCustom",
    "secondary": "Arial, sans-serif"
}

# Фонт файлуудын зам тохиргоо
BASE_DIR = Path(os.getcwd())
STATIC_DIR = BASE_DIR / "static"
FONTS_DIR = STATIC_DIR / "fonts"

def get_font_path(font_type: str = "regular") -> str:
    """Фонт файлын бүрэн зам авах"""
    font_filename = CYRILLIC_FONTS.get(font_type, CYRILLIC_FONTS["regular"])
    return f"file://{FONTS_DIR / font_filename}"

# === PDF ХУУДАС ТОХИРГОО ===
PDF_PAGE_CONFIG = {
    "size": "a4 portrait",
    "margin": "1cm",
    "footer_height": "20pt",
    "footer_top": "770pt",
    "footer_left": "50pt",
    "footer_width": "500pt"
}

# === CSS STYLE ТОГТМОЛУУД ===
FONT_SIZES = {
    "body": "10pt",
    "h1": "20pt",
    "h2": "16pt",
    "h3": "13pt",
    "small": "8pt",
    "price_highlight": "1.2em"
}

COLORS = {
    "text_primary": "#333",
    "text_secondary": "#777",
    "text_header": "#111",
    "border": "#ccc",
    "border_light": "#eee",
    "background_light": "#f0f0f0",
    "background_highlight": "#f9f9f9"
}

SPACING = {
    "line_height": "1.4",
    "margin_body": "0.5in",
    "margin_h2_top": "1.5em",
    "margin_h3_top": "1.2em",
    "margin_p_bottom": "0.8em",
    "margin_section": "20px",
    "padding_cell": "6px",
    "padding_highlight": "10px"
}

# === PDF ТАЙЛАНГИЙН ЗАГВАР ===
REPORT_TEMPLATES = {
    "property": {
        "title": "🏠 Орон сууцны дэлгэрэнгүй шинжилгээ",
        "sections": [
            "Үндсэн мэдээлэл",
            "Дүүргийн зах зээлийн шинжилгээ",
            "Chain-of-Thought дэлгэрэнгүй шинжилгээ",
            "Интернэт судалгааны үр дүн",
            "Хөрөнгө оруулалтын зөвлөмж"
        ]
    },
    "district": {
        "title": "🏘️ Дүүргийн харьцуулалтын тайлан",
        "sections": [
            "Дүүргүүдийн үнийн харьцуулалт",
            "Зах зээлийн шинжилгээ",
            "Интернэт судалгааны үр дүн"
        ]
    }
}

# === ХҮСНЭГТИЙН ТОХИРГОО ===
TABLE_CONFIG = {
    "district_comparison": {
        "headers": ["Дүүрэг", "Дундаж үнэ (₮/м²)", "2 өрөө (₮/м²)", "3 өрөө (₮/м²)"],
        "sort_key": "overall_avg"
    }
}

# === АЛДАА МЭДЭЭЛЛИЙН ЗАГВАР ===
ERROR_MESSAGES = {
    "font_missing": "CRITICAL FONT MISSING: {} not found in {}. Mongolian Cyrillic text will NOT render correctly.",
    "pdf_generation_failed": "ERROR: Could not generate PDF for {} report. Check logs. Missing font '{}' could be an issue.",
    "no_data": "Мэдээлэл байхгүй",
    "search_failed": ["мэдээлэл байхгүй", "интернэт хайлт хийхэд алдаа гарлаа.", "интернэт хайлтаас мэдээлэл олдсонгүй."]
}

# === ҮНИЙН ФОРМАТЫН ТОХИРГОО ===
PRICE_FORMAT = {
    "million_threshold": 1_000_000,
    "million_suffix": "сая ₮",
    "currency": "₮",
    "decimal_places": 1
}

# === ХӨРӨНГӨ ОРУУЛАЛТЫН ЗӨВЛӨМЖИЙН БОСГО ===
INVESTMENT_THRESHOLDS = {
    "expensive": 4_500_000,  # ₮/м² - үнэ өндөр гэж үзэх босго
    "affordable": 2_500_000,  # ₮/м² - хямд гэж үзэх босго
    "messages": {
        "expensive": "⚠️ Үнэ өндөр түвшинд байгаа тул тохиролцох боломжийг авч үзэх.",
        "affordable": "💰 Зах зээлээс доогуур үнэтэй - хөрөнгө оруулалтын боломжтой.",
        "moderate": "✅ Зах зээлийн дундаж үнэтэй - тохиромжтой үнэ."
    }
}

# === ХУГАЦААНЫ ФОРМАТ ===
DATE_FORMATS = {
    "filename": "%Y%m%d_%H%M%S",
    "display": "%Y-%m-%d %H:%M",
    "mongolian": "%Y оны %m сарын %d өдөр"
}

# === ФАЙЛЫН ТОХИРГОО ===
FILE_CONFIG = {
    "reports_dir": "reports",
    "property_prefix": "property_analysis_xhtml2pdf_",
    "district_prefix": "district_summary_xhtml2pdf_",
    "extension": ".pdf"
}