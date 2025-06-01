# utils/pdf_generator.py
import logging
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)

# Register CID fonts for Asian languages
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))


class MongolianPDFGenerator:
    def __init__(self):
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

    def generate_property_report(self, property_data: Dict[str, Any],
                                 district_analysis: str,
                                 comparison_result: str,
                                 search_results: str = "") -> str:
        """Generate property analysis PDF report in Mongolian"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"property_analysis_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        # Create PDF with custom canvas
        c = canvas.Canvas(str(filepath), pagesize=A4)
        width, height = A4

        # Set font for Mongolian text
        c.setFont('HeiseiKakuGo-W5', 14)

        # Title
        y = height - 50
        c.drawCentredString(width / 2, y, "Үл хөдлөх хөрөнгийн шинжилгээний тайлан")

        # Date
        y -= 30
        c.setFont('HeiseiMin-W3', 10)
        c.drawString(50, y, f"Огноо: {datetime.now().strftime('%Y-%m-%d')}")

        # Section 1: Basic Information
        y -= 40
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "1. Орон сууцны үндсэн мэдээлэл")

        y -= 20
        c.setFont('HeiseiMin-W3', 10)

        # Property details
        details = [
            ("Гарчиг:", property_data.get('title', 'Мэдээлэл байхгүй')),
            ("Байршил:", property_data.get('full_location', 'Мэдээлэл байхгүй')),
            ("Дүүрэг:", property_data.get('district', 'Мэдээлэл байхгүй')),
            ("Талбай:", f"{property_data.get('area_sqm', 'N/A')} м²"),
            ("Өрөөний тоо:", str(property_data.get('room_count', 'Мэдээлэл байхгүй'))),
            ("Нийт үнэ:", self._format_price(property_data.get('price_numeric'))),
            ("м² үнэ:", self._format_price(property_data.get('price_per_sqm')))
        ]

        for label, value in details:
            c.drawString(70, y, label)
            c.drawString(200, y, value)
            y -= 20

        # Section 2: Technical Details
        y -= 20
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "2. Техникийн мэдээлэл")

        y -= 20
        c.setFont('HeiseiMin-W3', 10)

        tech_details = [
            ("Шал:", property_data.get('floor', 'Мэдээлэл байхгүй')),
            ("Тагт:", property_data.get('balcony', 'Мэдээлэл байхгүй')),
            ("Ашиглалтад орсон он:", property_data.get('year_built', 'Мэдээлэл байхгүй')),
            ("Гараж:", property_data.get('garage', 'Мэдээлэл байхгүй')),
            ("Давхар:", property_data.get('floor_number', 'Мэдээлэл байхгүй'))
        ]

        for label, value in tech_details:
            if value != 'N/A' and value != 'Мэдээлэл байхгүй':
                c.drawString(70, y, label)
                c.drawString(200, y, value)
                y -= 20

        # Section 3: District Analysis
        y -= 20
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "3. Дүүргийн зах зээлийн шинжилгээ")

        y -= 20
        c.setFont('HeiseiMin-W3', 10)

        # Wrap text for district analysis
        district_lines = self._wrap_text(district_analysis, 80)
        for line in district_lines[:10]:  # Limit lines
            c.drawString(50, y, line)
            y -= 15
            if y < 100:
                c.showPage()
                y = height - 50
                c.setFont('HeiseiMin-W3', 10)

        # Section 4: Price Comparison
        y -= 20
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "4. Үнийн харьцуулалт")

        y -= 20
        c.setFont('HeiseiMin-W3', 10)

        comparison_lines = self._wrap_text(comparison_result, 80)
        for line in comparison_lines[:10]:
            c.drawString(50, y, line)
            y -= 15
            if y < 100:
                c.showPage()
                y = height - 50
                c.setFont('HeiseiMin-W3', 10)

        # Section 5: Market Research
        if search_results:
            y -= 20
            c.setFont('HeiseiKakuGo-W5', 12)
            c.drawString(50, y, "5. Зах зээлийн судалгаа")

            y -= 20
            c.setFont('HeiseiMin-W3', 10)

            search_lines = self._wrap_text(search_results, 80)
            for line in search_lines[:10]:
                c.drawString(50, y, line)
                y -= 15
                if y < 100:
                    c.showPage()
                    y = height - 50
                    c.setFont('HeiseiMin-W3', 10)

        # Footer
        c.setFont('HeiseiMin-W3', 8)
        c.drawString(50, 50, f"Тайлан үүсгэсэн: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        c.drawString(50, 35, "Үл хөдлөх хөрөнгийн туслах системээр үүсгэсэн")

        # Save PDF
        c.save()
        logger.info(f"Property PDF report generated: {filepath}")
        return str(filepath)

    def generate_district_summary_report(self, districts_data: List[Dict],
                                         market_trends: str = "",
                                         search_results: str = "") -> str:
        """Generate district comparison PDF report in Mongolian"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"district_summary_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        # Create PDF with custom canvas
        c = canvas.Canvas(str(filepath), pagesize=A4)
        width, height = A4

        # Set font
        c.setFont('HeiseiKakuGo-W5', 14)

        # Title
        y = height - 50
        c.drawCentredString(width / 2, y, "Улаанбаатар хотын дүүргийн харьцуулалтын тайлан")

        # Date
        y -= 30
        c.setFont('HeiseiMin-W3', 10)
        c.drawString(50, y, f"Огноо: {datetime.now().strftime('%Y-%m-%d')}")

        # Section 1: District Comparison Table
        y -= 40
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "1. Дүүргүүдийн үнийн харьцуулалт")

        y -= 30
        c.setFont('HeiseiMin-W3', 10)

        # Table header
        c.drawString(50, y, "Дүүрэг")
        c.drawString(150, y, "Дундаж үнэ (₮/м²)")
        c.drawString(280, y, "2 өрөө (₮/м²)")
        c.drawString(400, y, "3 өрөө (₮/м²)")

        y -= 20
        c.line(50, y, 500, y)
        y -= 10

        # Table data
        for district in districts_data:
            c.drawString(50, y, district.get('name', 'Тодорхойгүй'))
            c.drawString(150, y, self._format_price(district.get('overall_avg', 0)))
            c.drawString(280, y, self._format_price(district.get('two_room_avg', 0)))
            c.drawString(400, y, self._format_price(district.get('three_room_avg', 0)))
            y -= 20

            if y < 100:
                c.showPage()
                y = height - 50
                c.setFont('HeiseiMin-W3', 10)

        # Section 2: Market Analysis
        y -= 30
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "2. Зах зээлийн шинжилгээ")

        y -= 20
        c.setFont('HeiseiMin-W3', 10)

        if market_trends:
            trends_lines = self._wrap_text(market_trends, 80)
            for line in trends_lines[:15]:
                c.drawString(50, y, line)
                y -= 15
                if y < 100:
                    c.showPage()
                    y = height - 50
                    c.setFont('HeiseiMin-W3', 10)

        # Section 3: Investment Opportunities
        y -= 30
        c.setFont('HeiseiKakuGo-W5', 12)
        c.drawString(50, y, "3. Хөрөнгө оруулалтын боломжууд")

        y -= 20
        c.setFont('HeiseiMin-W3', 10)

        opportunities = [
            "• Хамгийн хямд дүүрэг: Налайх, Багануур",
            "• Хамгийн үнэтэй дүүрэг: Сүхбаатар, Хан-Уул",
            "• Хөрөнгө оруулалтад тохиромжтой: Баянзүрх, Сонгинохайрхан",
            "• Түрээсийн өгөөж өндөр: Төвийн дүүргүүд",
            "• Ирээдүйн хөгжлийн боломжтой: Хан-Уул, Баянзүрх"
        ]

        for opportunity in opportunities:
            c.drawString(50, y, opportunity)
            y -= 20

        # Footer
        c.setFont('HeiseiMin-W3', 8)
        c.drawString(50, 50, f"Тайлан үүсгэсэн: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        c.drawString(50, 35, "Үл хөдлөх хөрөнгийн туслах системээр үүсгэсэн")

        # Save PDF
        c.save()
        logger.info(f"District summary PDF generated: {filepath}")
        return str(filepath)

    def _format_price(self, price) -> str:
        """Format price with proper formatting"""
        if not price or price == 0:
            return "Мэдээлэл байхгүй"
        try:
            return f"{int(price):,} ₮".replace(",", " ")
        except (ValueError, TypeError):
            return "Мэдээлэл байхгүй"

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        """Wrap text to fit within character limit"""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars:
                current_line += word + " "
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word + " "

        if current_line:
            lines.append(current_line.strip())

        return lines


# Update the PDFReportGenerator class to use the new Mongolian generator
class PDFReportGenerator:
    def __init__(self):
        self.mongolian_generator = MongolianPDFGenerator()

    def generate_property_analysis_report(self, property_data, district_analysis,
                                          comparison_result, search_results=""):
        return self.mongolian_generator.generate_property_report(
            property_data, district_analysis, comparison_result, search_results
        )

    def generate_district_summary_report(self, districts_data, market_trends="",
                                         search_results=""):
        return self.mongolian_generator.generate_district_summary_report(
            districts_data, market_trends, search_results
        )