# pdf_generator.py

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from xhtml2pdf import pisa

from config.pdf_config import FILE_CONFIG, DATE_FORMATS, ERROR_MESSAGES
from utils.font_manager import FontManager
from utils.html_formatter import HTMLFormatter
from utils.html_builders import PropertyHTMLBuilder, DistrictHTMLBuilder, MarketHTMLBuilder

logger = logging.getLogger(__name__)


class XHTML2PDFGenerator:
    """Core PDF generation functionality using xhtml2pdf"""

    def __init__(self):
        self.reports_dir = Path(FILE_CONFIG["reports_dir"])
        self.reports_dir.mkdir(exist_ok=True)

        # Initialize components
        self.font_manager = FontManager()
        self.formatter = HTMLFormatter()
        self.property_builder = PropertyHTMLBuilder(self.formatter)
        self.district_builder = DistrictHTMLBuilder(self.formatter)
        self.market_builder = MarketHTMLBuilder(self.formatter)

        logger.info(f"XHTML2PDFGenerator initialized. Reports directory: {self.reports_dir}")

    def _generate_pdf_from_html(self, html_content: str, output_filepath: str) -> bool:
        """Generate PDF with enhanced error handling and reporting"""
        try:
            output_path = Path(output_filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.exists() and not os.access(str(output_path), os.W_OK):
                logger.error(f"Output file exists but is not writable: {output_filepath}")
                try:
                    output_path.unlink()
                    logger.info(f"Removed existing unwritable file: {output_filepath}")
                except Exception as e:
                    logger.error(f"Failed to remove existing file: {e}")
                    return False

            with open(output_filepath, "w+b") as result_file:
                pisa_status = pisa.CreatePDF(
                    html_content,
                    dest=result_file,
                    encoding='UTF-8',
                    link_callback=self.font_manager.create_link_callback()
                )

            if pisa_status.err:
                logger.error(f"Error generating PDF with xhtml2pdf: {pisa_status.err}")
                if hasattr(pisa_status, 'log') and pisa_status.log:
                    logger.error(f"PISA log: {pisa_status.log}")
                logger.error(f"HTML content that failed (first 500 chars): {html_content[:500]}")
                return False

            if not os.path.exists(output_filepath) or os.path.getsize(output_filepath) == 0:
                logger.error(f"PDF file was not created or is empty: {output_filepath}")
                return False

            logger.info(f"xhtml2pdf report generated successfully: {output_filepath}")
            return True

        except Exception as e:
            logger.error(f"Exception during PDF generation with xhtml2pdf: {e}", exc_info=True)
            logger.error(f"HTML content that failed (first 500 chars): {html_content[:500]}")
            return False

    def generate_property_report(self, property_data: Dict[str, Any], district_analysis: str,
                                 comparison_result: str, search_results: str = "") -> str:
        """Generate property report with enhanced error handling"""
        try:
            timestamp = datetime.now().strftime(DATE_FORMATS["filename"])
            filename = f"{FILE_CONFIG['property_prefix']}{timestamp}{FILE_CONFIG['extension']}"
            filepath = self.reports_dir / filename

            prop_title = self.formatter.clean_text_for_html(property_data.get('title', 'Орон сууцны шинжилгээ'))
            location = self.formatter.clean_text_for_html(property_data.get('full_location', 'Тодорхойгүй'))
            district = self.formatter.clean_text_for_html(property_data.get('district', 'Тодорхойгүй'))
            area = property_data.get('area_sqm', 0.0)
            rooms = property_data.get('room_count', 0)
            price = self.formatter.format_price_html(property_data.get('price_numeric', 0))
            price_per_sqm_val = property_data.get('price_per_sqm', 0.0)
            price_per_sqm_display = self.formatter.format_price_html(price_per_sqm_val)


            cleaned_district_analysis = self.formatter.clean_text_for_html(
                district_analysis or "Дүүргийн шинжилгээний мэдээлэл байхгүй.")
            cleaned_comparison_result = self.formatter.clean_text_for_html(
                comparison_result or "Хөрөнгийн үнэлгээний мэдээлэл байхгүй.")
            cleaned_search_results = self.formatter.clean_text_for_html(search_results or "")

            html = self.property_builder.build_html(
                prop_title, location, district, float(area), int(rooms), price, price_per_sqm_display,
                cleaned_district_analysis, cleaned_comparison_result, cleaned_search_results,
                float(price_per_sqm_val)
            )

            if self._generate_pdf_from_html(html, str(filepath)):
                return str(filepath)
            else:
                logger.error(f"Failed to generate property report PDF: {filepath}")
                # Return path if file was partially created, otherwise error message.
                return str(filepath) if filepath.exists() else ERROR_MESSAGES["pdf_generation_failed"].format(
                    "property", "PDF generation process failed")

        except Exception as e:
            logger.exception(f"Error in generate_property_report: {e}")
            return ERROR_MESSAGES["pdf_generation_failed"].format("property", str(e))

    def generate_district_summary_report(self, districts_data: List[Dict], market_trends: str = "",
                                         search_results: str = "", future_development_content: str = "") -> str:
        """Generate district summary report with enhanced error handling"""
        try:
            timestamp = datetime.now().strftime(DATE_FORMATS["filename"])
            filename = f"{FILE_CONFIG['district_prefix']}{timestamp}{FILE_CONFIG['extension']}"
            filepath = self.reports_dir / filename

            cleaned_market_trends = self.formatter.clean_text_for_html(
                market_trends or "Зах зээлийн чиг хандлагын мэдээлэл байхгүй.")
            cleaned_search_results = self.formatter.clean_text_for_html(search_results or "")
            cleaned_future_development_content = self.formatter.clean_text_for_html(
                future_development_content or "Ирээдүйн хөгжлийн төлөвийн талаарх мэдээлэл боловсруулагдаагүй."
            )

            html = self.district_builder.build_html(
                districts_data,
                cleaned_market_trends,
                cleaned_search_results,
                cleaned_future_development_content
            )

            if self._generate_pdf_from_html(html, str(filepath)):
                return str(filepath)
            else:
                logger.error(f"Failed to generate district report PDF: {filepath}")
                return str(filepath) if filepath.exists() else ERROR_MESSAGES["pdf_generation_failed"].format(
                    "district summary", "PDF generation process failed")

        except Exception as e:
            logger.exception(f"Error in generate_district_summary_report: {e}")
            return ERROR_MESSAGES["pdf_generation_failed"].format("district summary", str(e))

    def generate_market_analysis_report(self, market_summary_from_search: str, current_district_data_analysis: str,
                                        user_query: str = "", raw_search_content_preview: str = "",
                                        supply_demand_content: str = "",
                                        investment_strategy_content: str = "",
                                        risk_assessment_content: str = ""
                                        ) -> str:
        """Generate market analysis report with enhanced error handling"""
        try:
            timestamp = datetime.now().strftime(DATE_FORMATS["filename"])
            filename = f"{FILE_CONFIG['market_prefix']}{timestamp}{FILE_CONFIG['extension']}"
            filepath = self.reports_dir / filename

            cleaned_market_summary = self.formatter.clean_text_for_html(
                market_summary_from_search or "Зах зээлийн мэдээлэл олдсонгүй.")
            cleaned_district_analysis = self.formatter.clean_text_for_html(
                current_district_data_analysis or "Дүүргүүдийн дэлгэрэнгүй мэдээлэл байхгүй.")
            cleaned_query = self.formatter.clean_text_for_html(user_query or "Зах зээлийн ерөнхий мэдээлэл")

            cleaned_supply_demand_content = self.formatter.clean_text_for_html(
                supply_demand_content or "Эрэлт нийлүүлэлтийн шинжилгээний мэдээлэл боловсруулагдаагүй."
            )
            cleaned_investment_strategy_content = self.formatter.clean_text_for_html(
                investment_strategy_content or "Хөрөнгө оруулалтын стратегийн мэдээлэл боловсруулагдаагүй."
            )
            cleaned_risk_assessment_content = self.formatter.clean_text_for_html(
                risk_assessment_content or "Эрсдэлийн үнэлгээний мэдээлэл боловсруулагдаагүй."
            )

            html = self.market_builder.build_html(
                cleaned_market_summary,
                cleaned_district_analysis,
                cleaned_query,
                cleaned_supply_demand_content,
                cleaned_investment_strategy_content,
                cleaned_risk_assessment_content
            )

            if self._generate_pdf_from_html(html, str(filepath)):
                return str(filepath)
            else:
                logger.error(f"Failed to generate market report PDF: {filepath}")
                return str(filepath) if filepath.exists() else ERROR_MESSAGES["pdf_generation_failed"].format(
                    "market analysis", "PDF generation process failed")

        except Exception as e:
            logger.exception(f"Error in generate_market_analysis_report: {e}")
            return ERROR_MESSAGES["pdf_generation_failed"].format("market analysis", str(e))

    def _generate_emergency_pdf(self, report_type: str) -> str:
        """Generate a minimal emergency PDF when all else fails"""
        try:
            timestamp = datetime.now().strftime(DATE_FORMATS["filename"])
            filename = f"emergency_{report_type}_{timestamp}.pdf"
            filepath = self.reports_dir / filename

            minimal_html = f"""
            <html><head><meta charset="UTF-8"><style>body {{ font-family: Arial, sans-serif; }}</style></head>
            <body><h1>Тайлан үүсгэхэд алдаа гарлаа</h1><p>Тайлан: {report_type}</p>
            <p>Огноо: {datetime.now().strftime(DATE_FORMATS['mongolian'])}</p>
            <p>Системд алдаа гарсан тул энэхүү түр хугацааны тайланг үүсгэв.</p></body></html>"""

            try:
                with open(filepath, "w+b") as result_file:
                    pisa.CreatePDF(minimal_html, dest=result_file, encoding='UTF-8')
                if filepath.exists() and filepath.stat().st_size > 0:
                    logger.info(f"Emergency PDF created: {filepath}")
                    return str(filepath)
            except Exception as e_pdf:
                logger.error(f"Even emergency PDF creation failed: {e_pdf}")

            text_filepath = filepath.with_suffix(".txt")
            with open(text_filepath, "w", encoding="utf-8") as f:
                f.write(f"ТАЙЛАН ҮҮСГЭХЭД АЛДАА ГАРЛАА\nТайлан: {report_type}\nОгноо: {datetime.now()}\n")
            logger.info(f"Last resort - created text file: {text_filepath}")
            return str(text_filepath)
        except Exception as e:
            logger.critical(f"Complete failure in emergency PDF generation: {e}")
            # Return a predictable error path
            return str(self.reports_dir / f"ABSOLUTE_FAILURE_emergency_{report_type}_report.txt")


class PDFReportGenerator:
    """Main PDF generator class with enhanced error recovery"""

    def __init__(self):
        try:
            self.generator = XHTML2PDFGenerator()
            logger.info("PDFReportGenerator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PDFReportGenerator: {e}", exc_info=True)
            self.generator = None # Ensure generator is None if init fails

    def generate_property_analysis_report(self, property_data: Dict[str, Any], district_analysis: str,
                                          comparison_result: str, search_results: str = "") -> str:
        """Generate property report with fallback mechanisms"""
        if not self.generator:
            logger.error("PDF generator (XHTML2PDFGenerator) is not available for property report.")
            # Attempt to create a very basic emergency text file if generator is None from the start
            emergency_path = Path(FILE_CONFIG["reports_dir"]) / f"emergency_property_{datetime.now().strftime(DATE_FORMATS['filename'])}.txt"
            emergency_path.parent.mkdir(parents=True, exist_ok=True)
            with open(emergency_path, "w", encoding="utf-8") as f:
                f.write("Property Report Generation Failed - Core PDF Generator Missing.")
            return str(emergency_path)

        try:
            if not property_data: # Basic validation
                property_data = {"title": "Unknown Property (No Data)", "price_per_sqm": 0.0} #
                logger.warning("Empty property data provided to PDFReportGenerator, using placeholder")

            result = self.generator.generate_property_report(
                property_data, district_analysis, comparison_result, search_results
            )

            if result and Path(result).exists() and Path(result).stat().st_size > 0:
                return result
            else:
                logger.error(f"Generated property file does not exist or is empty: {result}. Triggering emergency PDF.")
                return self.generator._generate_emergency_pdf("property")

        except Exception as e:
            logger.exception(f"Critical error in generate_property_analysis_report: {e}")
            # Ensure _generate_emergency_pdf is called even if self.generator exists but a method failed
            return self.generator._generate_emergency_pdf("property") if self.generator else str(Path(FILE_CONFIG["reports_dir"]) / "EMERGENCY_PROPERTY_REPORT_FAILED.txt")


    def generate_district_summary_report(self, districts_data: List[Dict], market_trends: str = "",
                                         search_results: str = "", future_development_content: str = "") -> str:
        """Generate district report with fallback mechanisms"""
        if not self.generator:
            logger.error("PDF generator (XHTML2PDFGenerator) is not available for district report.")
            emergency_path = Path(FILE_CONFIG["reports_dir"]) / f"emergency_district_{datetime.now().strftime(DATE_FORMATS['filename'])}.txt"
            emergency_path.parent.mkdir(parents=True, exist_ok=True)
            with open(emergency_path, "w", encoding="utf-8") as f:
                f.write("District Report Generation Failed - Core PDF Generator Missing.")
            return str(emergency_path)
        try:
            if not districts_data: # Basic validation
                logger.warning("Empty districts data provided to PDFReportGenerator, using empty list for builder.")
                districts_data = []


            result = self.generator.generate_district_summary_report(
                districts_data, market_trends, search_results, future_development_content
            )

            if result and Path(result).exists() and Path(result).stat().st_size > 0:
                return result
            else:
                logger.error(f"Generated district file does not exist or is empty: {result}. Triggering emergency PDF.")
                return self.generator._generate_emergency_pdf("district")

        except Exception as e:
            logger.exception(f"Critical error in generate_district_summary_report: {e}")
            return self.generator._generate_emergency_pdf("district") if self.generator else str(Path(FILE_CONFIG["reports_dir"]) / "EMERGENCY_DISTRICT_REPORT_FAILED.txt")

    def generate_market_analysis_report(self, market_summary_from_search: str, current_district_data_analysis: str,
                                        user_query: str = "", raw_search_content_preview: str = "",
                                        supply_demand_content: str = "",
                                        investment_strategy_content: str = "",
                                        risk_assessment_content: str = ""
                                        ) -> str:
        """Generate market report with fallback mechanisms"""
        if not self.generator:
            logger.error("PDF generator (XHTML2PDFGenerator) is not available for market report.")
            emergency_path = Path(FILE_CONFIG["reports_dir"]) / f"emergency_market_{datetime.now().strftime(DATE_FORMATS['filename'])}.txt"
            emergency_path.parent.mkdir(parents=True, exist_ok=True)
            with open(emergency_path, "w", encoding="utf-8") as f:
                f.write("Market Report Generation Failed - Core PDF Generator Missing.")
            return str(emergency_path)
        try:
            result = self.generator.generate_market_analysis_report(
                market_summary_from_search, current_district_data_analysis, user_query, raw_search_content_preview,
                supply_demand_content, investment_strategy_content, risk_assessment_content
            )

            if result and Path(result).exists() and Path(result).stat().st_size > 0:
                return result
            else:
                logger.error(f"Generated market file does not exist or is empty: {result}. Triggering emergency PDF.")
                return self.generator._generate_emergency_pdf("market")

        except Exception as e:
            logger.exception(f"Critical error in generate_market_analysis_report: {e}")
            return self.generator._generate_emergency_pdf("market") if self.generator else str(Path(FILE_CONFIG["reports_dir"]) / "EMERGENCY_MARKET_REPORT_FAILED.txt")