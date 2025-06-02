"""
Enhanced PDF Report Configuration with 5+ Sections
Refactored to meet project requirements of at least 5 different sections per report type.
"""

from pathlib import Path

# Constants for PDF generation
FONTS_DIR = Path("static/fonts")
FONTS_DIR.mkdir(parents=True, exist_ok=True)

# Font configurations with fallbacks
CYRILLIC_FONTS = {
    "regular": "NotoSans-Regular.ttf",
    "bold": "NotoSans-Bold.ttf",
    "fallback": "DejaVuSans.ttf",
    "system_fallback": "Arial Unicode MS"
}

FONT_FAMILY_NAMES = {
    "primary": "NotoSans",
    "secondary": "Arial, Helvetica, sans-serif",
    "fallback": "DejaVuSans, Arial Unicode MS, sans-serif"
}

# PDF page configuration
PDF_PAGE_CONFIG = {
    "size": "A4",
    "margin": "2cm 2cm 2.5cm 2cm",
    "footer_left": "2cm",
    "footer_width": "17cm",
    "footer_top": "26.5cm",
    "footer_height": "1cm"
}

# Font sizes
FONT_SIZES = {
    "h1": "20pt",
    "h2": "16pt",
    "h3": "14pt",
    "body": "12pt",
    "small": "10pt",
    "price_highlight": "14pt"
}

# Colors
COLORS = {
    "text_primary": "#333333",
    "text_secondary": "#666666",
    "text_header": "#1a1a1a",
    "border": "#cccccc",
    "border_light": "#e0e0e0",
    "background_light": "#f5f5f5",
    "background_highlight": "#f0f7ff"
}

# Spacing
SPACING = {
    "margin_body": "0",
    "margin_h2_top": "1.5em",
    "margin_h3_top": "1.2em",
    "margin_p_bottom": "0.8em",
    "margin_section": "1.8em",
    "padding_cell": "8px",
    "padding_highlight": "12px",
    "line_height": "1.5"
}

# Table configuration
TABLE_CONFIG = {
    "district_comparison": {
        "headers": ["Дүүрэг", "Дундаж үнэ (м²)", "2 өрөө (м²)", "3 өрөө (м²)"],
        "sort_key": "overall_avg"
    }
}

# Price formatting
PRICE_FORMAT = {
    "currency": "₮",
    "million_threshold": 1000000,
    "million_suffix": "сая ₮",
    "decimal_places": 1
}

# Investment thresholds
INVESTMENT_THRESHOLDS = {
    "expensive": 4000000,
    "affordable": 3000000,
    "messages": {
        "expensive": "Энэ үл хөдлөх хөрөнгө нь Улаанбаатар хотын дундаж үнээс дээгүүр үнэтэй. Урт хугацааны өсөлтийн боломжтой боловч эхний хөрөнгө оруулалт өндөр байна.",
        "moderate": "Энэ үл хөдлөх хөрөнгө нь Улаанбаатар хотын дундаж үнэтэй. Хөрөнгө оруулалтын сайн тэнцвэрт боломжтой бөгөөд түрээсийн орлого олох боломжтой.",
        "affordable": "Энэ үл хөдлөх хөрөнгө нь харьцангуй хямд үнэтэй. Хөрөнгө оруулалтын сайн боломжтой, түрээсийн өгөөж өндөр байх магадлалтай."
    }
}

# Date formats
DATE_FORMATS = {
    "filename": "%Y%m%d_%H%M%S",
    "mongolian": "%Y оны %m-р сарын %d"
}

# File configuration
FILE_CONFIG = {
    "reports_dir": "reports",
    "property_prefix": "property_analysis_xhtml2pdf_",
    "district_prefix": "district_summary_xhtml2pdf_",
    "market_prefix": "market_analysis_xhtml2pdf_",
    "extension": ".pdf"
}

# Error messages
ERROR_MESSAGES = {
    "no_data": "Мэдээлэл байхгүй",
    "font_missing": "Анхааруулга: {} фонт олдсонгүй ({} хавтсанд). Системийн фонт ашиглах болно.",
    "pdf_generation_failed": "{} тайлан үүсгэхэд алдаа гарлаа. Шалтгаан: {} фонт олдсонгүй эсвэл PDF боловсруулахад алдаа гарлаа.",
    "search_failed": ["хайлт хийгдсэнгүй", "мэдээлэл хайхад алдаа гарлаа", "хайлт тохируулагдаагүй"]
}

# Enhanced Report Templates with 5+ Sections Each
REPORT_TEMPLATES = {
    "property": {
        "title": "Үл хөдлөх хөрөнгийн дэлгэрэнгүй шинжилгээ",
        "sections": [
            "1. Үндсэн мэдээлэл ба техникийн үзүүлэлт",          # Section 1: Basic Info & Technical Specs
            "2. Үнийн шинжилгээ ба зах зээлийн байршил",         # Section 2: Price Analysis & Market Position
            "3. Дүүргийн зах зээлийн шинжилгээ",                 # Section 3: District Market Analysis
            "4. Хөрөнгийн үнэлгээ ба харьцуулалт",              # Section 4: Property Valuation & Comparison
            "5. Хөрөнгө оруулалтын боломж ба эрсдэл",           # Section 5: Investment Opportunities & Risks
            "6. Зөвлөмж ба дүгнэлт",                           # Section 6: Recommendations & Conclusions
            "7. Нэмэлт зах зээлийн мэдээлэл"                   # Section 7: Additional Market Information
        ]
    },
    "district": {
        "title": "Дүүргийн үл хөдлөх хөрөнгийн зах зээлийн шинжилгээ",
        "sections": [
            "1. Дүүргүүдийн үнийн харьцуулалт ба зэрэглэл",      # Section 1: Price Comparison & Rankings
            "2. Зах зээлийн чиг хандлага ба статистик",          # Section 2: Market Trends & Statistics
            "3. Хөрөнгө оруулалтын боломжит бүсүүд",            # Section 3: Investment Opportunity Zones
            "4. Дүүргүүдийн давуу болон сул талууд",            # Section 4: District Advantages & Disadvantages
            "5. Худалдан авагчдад зориулсан стратеги",          # Section 5: Buyer Strategies
            "6. Ирээдүйн хөгжлийн төлөв байдал",               # Section 6: Future Development Outlook
            "7. Интернэт судалгааны нэмэлт мэдээлэл"           # Section 7: Additional Research Information
        ]
    },
    "market": {
        "title": "Үл хөдлөх хөрөнгийн зах зээлийн дэлгэрэнгүй шинжилгээ",
        "sections": [
            "1. Зах зээлийн ерөнхий байдал ба тойм",            # Section 1: Market Overview & Summary
            "2. Үнийн өөрчлөлт ба чиг хандлага",               # Section 2: Price Changes & Trends
            "3. Эрэлт хэрэгцээ ба нийлүүлэлтийн шинжилгээ",     # Section 3: Supply & Demand Analysis
            "4. Дүүргүүдийн зах зээлийн харьцуулалт",          # Section 4: District Market Comparison
            "5. Хөрөнгө оруулалтын стратеги ба боломж",        # Section 5: Investment Strategy & Opportunities
            "6. Эрсдэлийн үнэлгээ ба анхааруулга",             # Section 6: Risk Assessment & Warnings
            "7. Зах зээлийн таамаглал ба зөвлөмж"              # Section 7: Market Forecast & Recommendations
        ]
    }
}