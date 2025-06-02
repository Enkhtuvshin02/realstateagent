import logging
import json
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self, llm, district_analyzer, pdf_generator, search_tool=None):
        self.llm = llm
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator
        self.search_tool = search_tool
        logger.info("ReportService initialized with enhanced error handling and dynamic section generation")

    def _clean_search_content(self, content: str) -> str:
        if not content:
            return ""
        content = re.sub(r'!\[.*?\]\([^)]+\)', '', content)
        content = re.sub(r'<img[^>]*>', '', content)
        content = re.sub(r"https?://[^\s<>\"]*\.(jpg|jpeg|png|gif|webp|svg)(\?[^\s<>\"']*)?", '', content, flags=re.IGNORECASE)
        content = re.sub(r'data:image/[^;]+;base64,[^\s<>"]+', '', content)
        content = re.sub(r'\[image[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\[photo[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\[picture[^\]]*\]', '', content, flags=re.IGNORECASE)
        
        # Remove stray <br> tags that LLM might produce, converting them to newlines
        content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)

        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = re.sub(r' +', ' ', content)
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        content = '\n'.join(lines)
        return content.strip()

    def _filter_search_text(self, text: str) -> str:
        if not text:
            return ""
        fallback_phrases = [
            "энэ нь ямар нэгэн өгүүлэлтэй биш боловч",
            "хайлтын үйлчилгээ одоогоор ажиллахгүй байна",
            "энэ мэдээлэл нь хөрөнгө оруулагчдад болон хэрэглэгчдэд ямар нэгэн ач холбогдолтой зүйл болохгүй",
            "мэдээллийг олж мэдэрчээ",
            "i am unable to provide assistance with that as I am only a language model",
            "as an ai language model",
            "i cannot provide",
            "мэдээлэл олж чадахгүй байна"
        ]
        text_lower = text.lower()
        for phrase in fallback_phrases:
            if phrase.lower() in text_lower:
                logger.warning(f"Filtered out search text due to presence of: '{phrase}'")
                return ""
        return text

    async def generate_property_report(self, analysis_data: dict) -> dict:
        logger.info("Generating property report")
        try:
            if 'timestamp' in analysis_data:
                try:
                    analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                    time_diff = datetime.now() - analysis_time
                    if time_diff.total_seconds() > 600:
                        logger.warning("Property analysis data for report is older than 10 minutes.")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp format in analysis_data: {e}")

            property_data_dict = analysis_data.get("property_data", {})
            if not property_data_dict:
                logger.warning("Empty property data received for report generation")
                property_data_dict = {"title": "Мэдээлэл байхгүй", "price_per_sqm": 0}

            district_analysis_text = analysis_data.get("district_analysis_string", "Дүүргийн шинжилгээний мэдээлэл олдсонгүй.")
            search_results_text = await self._search_property_info(property_data_dict)
            # search_results_text is already filtered by _summarize_search_results if it came from there

            try:
                detailed_llm_analysis = await self._analyze_property(property_data_dict, district_analysis_text)
            except Exception as e:
                logger.error(f"Error in property analysis: {e}", exc_info=True)
                detailed_llm_analysis = "Хөрөнгийн дэлгэрэнгүй шинжилгээ хийхэд алдаа гарлаа."

            try:
                pdf_path = self.pdf_generator.generate_property_analysis_report(
                    property_data=property_data_dict,
                    district_analysis=district_analysis_text,
                    comparison_result=detailed_llm_analysis,
                    search_results=search_results_text
                )

                if not pdf_path or not Path(pdf_path).exists():
                    logger.error(f"PDF generation failed or file not found: {pdf_path}")
                    return {
                        "message": "Тайлан үүсгэхэд алдаа гарлаа. Дахин оролдоно уу.",
                        "success": False,
                        "error_details": "PDF file not created"
                    }

                filename = Path(pdf_path).name
                download_url = f"/download-report/{filename}"
                logger.info(f"Property report generated successfully: {filename}")
                return {
                    "message": f"Үл хөдлөх хөрөнгийн PDF тайлан бэлэн боллоо!",
                    "filename": filename,
                    "download_url": download_url,
                    "success": True
                }
            except Exception as e:
                logger.exception(f"Error in PDF generation for property report: {e}")
                return {
                    "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
                    "success": False,
                    "error_details": traceback.format_exc()
                }
        except Exception as e:
            logger.exception("Unexpected error generating property report")
            return {
                "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
                "success": False,
                "error_details": traceback.format_exc()
            }

    async def generate_district_report(self, analysis_data: dict) -> dict:
        logger.info("Generating district report")
        try:
            query = analysis_data.get("query", "ерөнхий дүүргүүд")
            analysis_type = analysis_data.get("type", "district")
            base_analysis_content = analysis_data.get("analysis_content", "Дүүргийн мэдээлэл олдсонгүй.")

            if 'timestamp' in analysis_data:
                try:
                    analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                    time_diff = datetime.now() - analysis_time
                    if time_diff.total_seconds() > 1800:
                        logger.warning("District analysis data for report is older than 30 minutes.")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp format in analysis_data: {e}")

            districts_data_for_pdf = self._extract_districts_data()
            market_analysis_for_pdf = ""
            search_results_text = ""

            if analysis_type == "district_comparison":
                search_results_text = await self._search_market_info(query="Улаанбаатар дүүргүүдийн үл хөдлөх хөрөнгийн зах зээлийн тойм")
                if districts_data_for_pdf:
                    try:
                        market_analysis_for_pdf = await self._analyze_market_for_report(districts_data_for_pdf)
                    except Exception as e:
                        logger.error(f"Error analyzing market for district comparison report: {e}", exc_info=True)
                        market_analysis_for_pdf = base_analysis_content
                else:
                    market_analysis_for_pdf = "Дүүргүүдийн өгөгдөл байхгүй тул зах зээлийн ерөнхий хандлагыг тодорхойлох боломжгүй байна."
            elif analysis_type == "district":
                single_district_name = query
                search_results_text = await self._search_market_info(query=f"{single_district_name} дүүргийн үл хөдлөх хөрөнгийн зах зээлийн мэдээлэл")
                focused_district_data = [d for d in districts_data_for_pdf if d.get('name') == single_district_name]
                if focused_district_data:
                    try:
                        market_analysis_for_pdf = await self._analyze_market_for_report(focused_district_data)
                    except Exception as e:
                        logger.error(f"Error analyzing market for single district '{single_district_name}': {e}", exc_info=True)
                        market_analysis_for_pdf = f"{single_district_name} дүүргийн зах зээлийн чиг хандлагыг тодорхойлоход алдаа гарлаа."
                else:
                     market_analysis_for_pdf = f"{single_district_name} дүүргийн талаарх дэлгэрэнгүй мэдээлэл олдсонгүй. {base_analysis_content}"
            else:
                return {"message": "Тайлангийн төрөл тодорхойгүй байна.", "success": False}

            generated_future_outlook_text = ""
            current_context_for_outlook = f"Одоогийн дүүргүүдийн мэдээлэл: {json.dumps(districts_data_for_pdf, ensure_ascii=False, indent=2)}\n\nЗах зээлийн ерөнхий дүн шинжилгээ: {market_analysis_for_pdf}"
            try:
                future_outlook_prompt_template = ChatPromptTemplate.from_messages([
                    ("system", """Та Монголын үл хөдлөх хөрөнгийн зах зээлийн шинжээч.
                     Өгөгдсөн дүүргүүдийн мэдээлэл болон зах зээлийн ерөнхий чиг хандлагад тулгуурлан PDF тайланд зориулсан "Ирээдүйн Хөгжлийн Төлөв" хэсгийг боловсруулна уу.
                     Энэ хэсэгт эдгээр дүүрэгт нөлөөлж болзошгүй дэд бүтцийн төслүүд, боловсрол, худалдааны байгууламжуудын хөгжил, үнийн чиг хандлага, эсвэл ирээдүйн хөгжилтэй холбоотой эрсдэлүүдийг хэлэлцэх ёстой.
                     Хариулт тань **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР**, албан ёсны тайланд тохиромжтой, 3-5 догол мөр бүхий дэлгэрэнгүй байх ёстой. **АНГЛИ ҮГ, HTML TAG ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэхдээ \\n тэмдэгт ашиглана уу."""),
                    ("human", "Контекст:\n{context_for_outlook}\n\nДээрх мэдээлэлд үндэслэн \"Ирээдүйн Хөгжлийн Төлөв\" хэсгийн агуулгыг Монгол хэлээр бичнэ үү.")
                ])
                future_outlook_chain = future_outlook_prompt_template | self.llm | StrOutputParser()
                generated_future_outlook_text = await future_outlook_chain.ainvoke({"context_for_outlook": current_context_for_outlook})
                generated_future_outlook_text = self._clean_search_content(generated_future_outlook_text.strip()) # Clean LLM output
                if not generated_future_outlook_text or len(generated_future_outlook_text) < 50:
                    logger.warning("LLM generated future outlook text was too short or empty. Using fallback.")
                    generated_future_outlook_text = "Ирээдүйн хөгжлийн төлөвийн талаарх дэлгэрэнгүй мэдээллийг одоогоор боловсруулах боломжгүй байна. Ерөнхийдөө хотын төлөвлөлт, дэд бүтцийн сайжруулалт нь үл хөдлөх хөрөнгийн үнэд нөлөөлөх болно. Тухайн дүүргийн хөгжлийн мастер төлөвлөгөөг судлахыг зөвлөж байна."
            except Exception as e:
                logger.error(f"Error generating LLM-based future development outlook: {e}", exc_info=True)
                generated_future_outlook_text = "Ирээдүйн хөгжлийн төлөвийг тодорхойлоход алдаа гарлаа. Хотын ерөнхий хөгжлийн төлөвлөгөө болон тухайн дүүргийн батлагдсан төлөвлөгөөг судлахыг зөвлөж байна."

            try:
                pdf_path = self.pdf_generator.generate_district_summary_report(
                    districts_data=districts_data_for_pdf,
                    market_trends=market_analysis_for_pdf,
                    search_results=search_results_text,
                    future_development_content=generated_future_outlook_text
                )
                if not pdf_path or not Path(pdf_path).exists():
                    logger.error(f"District PDF generation failed or file not found: {pdf_path}")
                    return {
                        "message": "Дүүргийн тайлан үүсгэхэд алдаа гарлаа. Дахин оролдоно уу.",
                        "success": False,
                        "error_details": "PDF file not created or found post-generation."
                    }
                filename = Path(pdf_path).name
                download_url = f"/download-report/{filename}"
                logger.info(f"District report generated successfully: {filename}")
                return {
                    "message": f"Дүүргийн PDF тайлан бэлэн боллоо!",
                    "filename": filename,
                    "download_url": download_url,
                    "success": True
                }
            except Exception as e:
                logger.exception(f"Error in district PDF generation call: {e}")
                return {
                    "message": f"Дүүргийн тайлан үүсгэхэд PDF үүсгэгчид алдаа гарлаа: {str(e)}",
                    "success": False,
                    "error_details": traceback.format_exc()
                }
        except Exception as e:
            logger.exception("Unexpected error generating district report")
            return {
                "message": f"Дүүргийн тайлан үүсгэхэд урьдчилан таамаглаагүй алдаа гарлаа: {str(e)}",
                "success": False,
                "error_details": traceback.format_exc()
            }

    async def generate_market_report(self, analysis_data: dict) -> dict:
        logger.info("Generating market report")
        try:
            user_query = analysis_data.get("query", "ерөнхий зах зээл")
            search_content_from_chat = analysis_data.get("search_content", "")

            if 'timestamp' in analysis_data:
                try:
                    analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                    time_diff = datetime.now() - analysis_time
                    if time_diff.total_seconds() > 1800:
                        logger.warning("Market analysis data for report is older than 30 minutes.")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp format in analysis_data: {e}")

            try:
                report_focused_search_summary = await self._summarize_search_results(
                    search_content_from_chat,
                    prompt_guideline="Улаанбаатарын үл хөдлөх хөрөнгийн зах зээлийн талаар дэлгэрэнгүй чиг хандлага, статистик, ирээдүйн төлөвийг гарга. Гол тоо баримт, өөрчлөлтүүдийг онцолж, тойм, үнийн хандлага, зах зээлийн таамаглалыг багтаасан иж бүрэн тайланд зориулсан хураангуйг гарга.",
                    max_summary_length=1500
                )
            except Exception as e:
                logger.error(f"Error summarizing search results for market report: {e}", exc_info=True)
                report_focused_search_summary = "Зах зээлийн мэдээллийг хураангуйлахад алдаа гарлаа. Ерөнхий мэдээлэл дутмаг."

            current_districts_structured_data = self._extract_districts_data()
            llm_analysis_of_districts = ""
            if current_districts_structured_data:
                try:
                    llm_analysis_of_districts = await self._analyze_market_for_report(current_districts_structured_data)
                except Exception as e:
                    logger.error(f"Error analyzing districts for market report: {e}", exc_info=True)
                    llm_analysis_of_districts = "Дүүргүүдийн мэдээллийг харьцуулан дүгнэхэд алдаа гарлаа."

            market_context_for_llm = f"Зах зээлийн ерөнхий хураангуй (Тойм, Үнийн Хандлага, Таамаглалд ашиглана): {report_focused_search_summary}\n\nДүүргүүдийн Харьцуулсан Шинжилгээ: {llm_analysis_of_districts}\n\nАнхдагч хайлтын дэлгэрэнгүй мэдээлэл (хэрэв шаардлагатай бол ашиглана): {search_content_from_chat[:1000]}"

            generated_supply_demand_text = ""
            try:
                supply_demand_prompt = ChatPromptTemplate.from_messages([
                    ("system", """Та Монголын үл хөдлөх хөрөнгийн шинжээч. Өгөгдсөн зах зээлийн мэдээлэлд үндэслэн "Эрэлт Нийлүүлэлтийн Шинжилгээ" хэсгийг **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР**, албан тайланд тохирохуйц, дэлгэрэнгүй байдлаар бичнэ үү.
                    Эрэлтийн гол хөдөлгөгч хүчин зүйлс (жишээ нь, хүн ам зүй, зээлийн боломж), нийлүүлэлтийн одоогийн байдал (шинэ барилга, хуучин байрны нөөц), зах зээлийн тэнцвэрт байдалд хэрхэн нөлөөлж буйг тодорхойл. Боломжтой бол тоон үзүүлэлт, чиг хандлагыг дурдаж, 3-5 догол мөр бүхий, гүнзгий анализ бүхий агуулга гаргана уу. **АНГЛИ ҮГ, HTML TAG ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэхдээ \\n тэмдэгт ашиглана уу."""),
                    ("human", "Зах зээлийн контекст:\n{market_context}\n\nДээрх мэдээлэлд тулгуурлан \"Эрэлт Нийлүүлэлтийн Шинжилгээ\" хэсгийг бичнэ үү.")
                ])
                supply_demand_chain = supply_demand_prompt | self.llm | StrOutputParser()
                generated_supply_demand_text = await supply_demand_chain.ainvoke({"market_context": market_context_for_llm})
                generated_supply_demand_text = self._clean_search_content(generated_supply_demand_text.strip())
                if not generated_supply_demand_text or len(generated_supply_demand_text) < 50:
                    generated_supply_demand_text = "Зах зээлийн эрэлт нийлүүлэлтийн талаарх дэлгэрэнгүй мэдээллийг боловсруулах боломжгүй. Ерөнхийдөө барилгын салбарын идэвхжил, зээлийн хүртээмж, хүн амын өсөлт зэрэг нь эрэлт нийлүүлэлтэд голлон нөлөөлдөг."
            except Exception as e:
                logger.error(f"Error generating supply_demand text: {e}", exc_info=True)
                generated_supply_demand_text = "Эрэлт нийлүүлэлтийн шинжилгээг хийхэд алдаа гарлаа. Зах зээлийн судалгааны байгууллагуудын тайланг үзнэ үү."

            generated_investment_strategy_text = ""
            try:
                investment_strategy_prompt = ChatPromptTemplate.from_messages([
                    ("system", """Та Монголын үл хөдлөх хөрөнгийн хөрөнгө оруулалтын зөвлөх. Өгөгдсөн зах зээлийн мэдээлэлд үндэслэн "Хөрөнгө Оруулалтын Стратеги ба Боломжууд" хэсгийг **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР**, албан тайланд тохирохуйц, дэлгэрэнгүй байдлаар бичнэ үү.
                    Богино болон урт хугацааны стратеги, эрсдэлийг бууруулах арга замууд, онцлох боломжуудыг (жишээ нь, тодорхой дүүргүүд, үл хөдлөх хөрөнгийн төрөл) дурдаж, 3-5 догол мөр бүхий, гүнзгий анализ бүхий агуулга гаргана уу. **АНГЛИ ҮГ, HTML TAG ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэхдээ \\n тэмдэгт ашиглана уу."""),
                    ("human", "Зах зээлийн контекст:\n{market_context}\n\nДээрх мэдээлэлд тулгуурлан \"Хөрөнгө Оруулалтын Стратеги ба Боломжууд\" хэсгийг бичнэ үү.")
                ])
                investment_strategy_chain = investment_strategy_prompt | self.llm | StrOutputParser()
                generated_investment_strategy_text = await investment_strategy_chain.ainvoke({"market_context": market_context_for_llm})
                generated_investment_strategy_text = self._clean_search_content(generated_investment_strategy_text.strip())
                if not generated_investment_strategy_text or len(generated_investment_strategy_text) < 50:
                    generated_investment_strategy_text = "Хөрөнгө оруулалтын стратегийн талаарх дэлгэрэнгүй зөвлөмжийг боловсруулах боломжгүй. Ерөнхийдөө байршил, ирээдүйн хөгжлийн төлөв, түрээсийн өгөөж, хувийн санхүүгийн зорилго зэргийг харгалзан үзэх нь чухал."
            except Exception as e:
                logger.error(f"Error generating investment_strategy text: {e}", exc_info=True)
                generated_investment_strategy_text = "Хөрөнгө оруулалтын стратеги боловсруулахад алдаа гарлаа. Мэргэжлийн санхүүгийн зөвлөхтэй зөвлөлдөнө үү."

            generated_risk_assessment_text = ""
            try:
                risk_assessment_prompt = ChatPromptTemplate.from_messages([
                    ("system", """Та Монголын үл хөдлөх хөрөнгийн эрсдэлийн шинжээч. Өгөгдсөн зах зээлийн мэдээлэлд үндэслэн "Эрсдэлийн Үнэлгээ ба Анхааруулга" хэсгийн АГУУЛГЫГ **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР**, албан тайланд тохирохуйц, дэлгэрэнгүй байдлаар бичнэ үү. **ХЭСГИЙН ГАРЧГИЙГ ДАХИН БИЧИХ ХЭРЭГГҮЙ.**
                    Болзошгүй макро эдийн засгийн, зах зээлийн өвөрмөц, бодлогын болон бусад эрсдэлүүд, тэдгээрээс хэрхэн сэргийлэх, эрсдэлийг бууруулах арга замуудын талаар дурдаж, 3-5 догол мөр бүхий, гүнзгий анализ бүхий агуулга гаргана уу. **АНГЛИ ҮГ, HTML TAG ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэхдээ \\n тэмдэгт ашиглана уу."""),
                    ("human", "Зах зээлийн контекст:\n{market_context}\n\nДээрх мэдээлэлд тулгуурлан \"Эрсдэлийн Үнэлгээ ба Анхааруулга\" хэсгийн АГУУЛГЫГ бичнэ үү.")
                ])
                risk_assessment_chain = risk_assessment_prompt | self.llm | StrOutputParser()
                generated_risk_assessment_text = await risk_assessment_chain.ainvoke({"market_context": market_context_for_llm})
                generated_risk_assessment_text = self._clean_search_content(generated_risk_assessment_text.strip())
                if not generated_risk_assessment_text or len(generated_risk_assessment_text) < 50:
                    generated_risk_assessment_text = "Зах зээлийн эрсдэлийн үнэлгээг дэлгэрэнгүй боловсруулах боломжгүй. Ерөнхийдөө зээлийн хүүгийн өөрчлөлт, эдийн засгийн тогтворгүй байдал, барилгын салбарын зохицуулалт, байгалийн гамшиг зэрэг нь анхаарах эрсдэлүүд юм."
            except Exception as e:
                logger.error(f"Error generating risk_assessment text: {e}", exc_info=True)
                generated_risk_assessment_text = "Эрсдэлийн үнэлгээ хийхэд алдаа гарлаа. Хөрөнгө оруулалт хийхээсээ өмнө мэргэжлийн хүмүүстэй зөвлөлдөж, эрсдэлээ сайтар тооцоолно уу."

            try:
                pdf_path = self.pdf_generator.generate_market_analysis_report(
                    market_summary_from_search=report_focused_search_summary,
                    current_district_data_analysis=llm_analysis_of_districts,
                    user_query=user_query,
                    raw_search_content_preview=search_content_from_chat[:1000] if search_content_from_chat else "",
                    supply_demand_content=generated_supply_demand_text,
                    investment_strategy_content=generated_investment_strategy_text,
                    risk_assessment_content=generated_risk_assessment_text
                )
                if not pdf_path or not Path(pdf_path).exists():
                    logger.error(f"Market PDF generation failed or file not found: {pdf_path}")
                    return {
                        "message": "Зах зээлийн тайлан үүсгэхэд алдаа гарлаа. Дахин оролдоно уу.",
                        "success": False,
                        "error_details": "PDF file not created"
                    }
                filename = Path(pdf_path).name
                download_url = f"/download-report/{filename}"
                logger.info(f"Market report generated successfully: {filename}")
                return {
                    "message": f"Зах зээлийн PDF тайлан бэлэн боллоо!",
                    "filename": filename,
                    "download_url": download_url,
                    "success": True
                }
            except Exception as e:
                logger.exception(f"Error in market PDF generation call: {e}")
                return {
                    "message": f"Зах зээлийн тайлан үүсгэхэд PDF үүсгэгчид алдаа гарлаа: {str(e)}",
                    "success": False,
                    "error_details": traceback.format_exc()
                }
        except Exception as e:
            logger.exception("Unexpected error generating market report")
            return {
                "message": f"Зах зээлийн тайлан үүсгэхэд урьдчилан таамаглаагүй алдаа гарлаа: {str(e)}",
                "success": False,
                "error_details": traceback.format_exc()
            }

    def _extract_districts_data(self) -> list:
        logger.info("Extracting districts data for report generation")
        if not self.district_analyzer or not hasattr(self.district_analyzer, 'vectorstore') or not self.district_analyzer.vectorstore:
            logger.warning("DistrictAnalyzer or its vectorstore not available. Using fallback data.")
            return self._get_fallback_data()

        all_docs = []
        try:
            if hasattr(self.district_analyzer.vectorstore, 'docstore') and \
               hasattr(self.district_analyzer.vectorstore.docstore, '_dict'):
                all_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
                logger.info(f"Retrieved {len(all_docs)} documents directly from docstore.")
            else:
                logger.warning("Cannot directly access vectorstore's full document list. Fallback needed or vectorstore inspection.")
                return self._get_fallback_data()

        except Exception as e:
            logger.error(f"Error accessing documents from vectorstore: {e}", exc_info=True)
            return self._get_fallback_data()

        if not all_docs:
            logger.warning("No documents found in vectorstore. Using fallback data.")
            return self._get_fallback_data()

        districts_data = []
        for doc in all_docs:
            try:
                content = doc.page_content
                if not isinstance(content, str): continue

                district_info = {}
                name_match = re.search(r"Дүүрэг:\s*([^\n]+)", content)
                if name_match:
                    district_info['name'] = name_match.group(1).strip()
                else:
                    continue

                price_patterns = [
                    (r"(?:Нийт байрны|Нийт ерөнхий|Ерөнхий дундаж)\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)", 'overall_avg'),
                    (r"2 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)", 'two_room_avg'),
                    (r"3 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)", 'three_room_avg'),
                    (r"1 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)", 'one_room_avg'),
                    (r"4 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)", 'four_room_avg'),
                ]
                for pattern, key in price_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        price_val = self._parse_price_value(match.group(1))
                        if price_val > 0:
                            district_info[key] = price_val

                if district_info.get('name') and district_info.get('overall_avg', 0) > 0 :
                    districts_data.append(district_info)
            except Exception as e:
                logger.error(f"Error parsing district data from doc: {content[:100]}... Error: {e}", exc_info=True)

        if not districts_data:
            logger.warning("No valid district data could be parsed from vectorstore documents. Using fallback.")
            return self._get_fallback_data()

        logger.info(f"Successfully parsed data for {len(districts_data)} districts from vectorstore.")
        return districts_data

    def _parse_price_value(self, price_str: str) -> float:
        try:
            cleaned_price_str = re.sub(r'[^\d.]', '', price_str)
            if cleaned_price_str:
                return float(cleaned_price_str)
            return 0.0
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse price string '{price_str}' to float. Error: {e}")
            return 0.0

    def _get_fallback_data(self) -> list:
        logger.info("Using fallback static district data for report context.")
        return [
            {'name': 'Сүхбаатар', 'overall_avg': 4500000, 'two_room_avg': 4600000, 'three_room_avg': 4400000},
            {'name': 'Хан-Уул', 'overall_avg': 4000000, 'two_room_avg': 4100000, 'three_room_avg': 3900000},
            {'name': 'Чингэлтэй', 'overall_avg': 3800000, 'two_room_avg': 3900000, 'three_room_avg': 3700000},
            {'name': 'Баянгол', 'overall_avg': 3500000, 'two_room_avg': 3600000, 'three_room_avg': 3400000},
            {'name': 'Баянзүрх', 'overall_avg': 3200000, 'two_room_avg': 3300000, 'three_room_avg': 3100000},
            {'name': 'Сонгинохайрхан', 'overall_avg': 2800000, 'two_room_avg': 2900000, 'three_room_avg': 2700000},
        ]

    async def _search_property_info(self, property_data_dict: dict) -> str:
        if not self.search_tool:
            logger.info("Search tool not available for property info.")
            return "Нэмэлт мэдээллийн хайлт хийгдсэнгүй (хайлт тохируулагдаагүй)."
        try:
            district = property_data_dict.get("district", "")
            title = property_data_dict.get("title", "")
            query_parts = ["Улаанбаатар"]
            if district and district != "Тодорхойгүй":
                query_parts.append(district + " дүүрэг")
            if title and title != "Мэдээлэл байхгүй":
                clean_title = re.sub(r'\d+\s*өрөө|\bбайр\b|\bорон сууц\b|\bзарна\b', '', title, flags=re.IGNORECASE).strip()
                specific_location_parts = clean_title.split()[:3]
                if specific_location_parts:
                    query_parts.append(" ".join(specific_location_parts))
            query_parts.append("орчны мэдээлэл үнэ ханш түрээс")
            query = " ".join(query_parts)
            logger.info(f"Searching for property context with query: {query}")
            search_response = await self.search_tool.ainvoke({"query": query})

            # _summarize_search_results will handle empty or problematic search_response
            return await self._summarize_search_results(
                search_response,
                prompt_guideline="Тухайн үл хөдлөх хөрөнгийн байршил, орчин тойрны мэдээлэл, ойролцоох үнэ ханш, зах зээлийн идэвхжилийн талаарх гол мэдээллийг гарга. Тайлангийн хэсэгт тохиромжтой, товч байдлаар нэгтгэ.",
                max_summary_length=600
            )
        except Exception as e:
            logger.exception(f"Error during property information search: {e}")
            return "Үл хөдлөх хөрөнгийн талаарх нэмэлт мэдээлэл хайхад алдаа гарлаа."

    async def _search_market_info(self, query: str = "Улаанбаатар орон сууцны зах зээлийн ерөнхий мэдээлэл 2024 2025") -> str:
        if not self.search_tool:
            logger.info("Search tool not available for market info.")
            return "Зах зээлийн нэмэлт мэдээллийн хайлт хийгдсэнгүй (хайлт тохируулагдаагүй)."
        try:
            logger.info(f"Searching for market context with query: {query}")
            search_response = await self.search_tool.ainvoke({"query": query})

            return await self._summarize_search_results(
                search_response,
                prompt_guideline="Улаанбаатар хотын үл хөдлөх хөрөнгийн зах зээлийн гол чиг хандлага, үнийн статистик, сүүлийн үеийн хөгжүүлэлт, шинжээчдийн дүгнэлтийг гарга. Тайлангийн нэмэлт судалгааны хэсэгт ашиглахад тохиромжтой мэдээллийг нэгтгэ.",
                max_summary_length=1000
            )
        except Exception as e:
            logger.exception(f"Error during market information search: {e}")
            return "Зах зээлийн талаарх нэмэлт мэдээлэл хайхад алдаа гарлаа."

    async def _summarize_search_results(self, search_response_data: any, prompt_guideline: str = "Extract key market trends, pricing information, and actionable insights.", max_summary_length: int = 1000) -> str:
        try:
            search_text = ""
            # ... (logic to extract text from search_response_data as before) ...
            if isinstance(search_response_data, str):
                search_text = search_response_data
            elif isinstance(search_response_data, list):
                texts = []
                for item in search_response_data:
                    if isinstance(item, dict):
                        content = item.get('content', '') or item.get('snippet', '')
                        if content: texts.append(str(content))
                    elif hasattr(item, 'page_content'): # For Document objects
                         texts.append(str(item.page_content))
                    elif isinstance(item, str):
                        texts.append(item)
                search_text = "\n\n".join(texts)
            elif isinstance(search_response_data, dict):
                if 'answer' in search_response_data: search_text = str(search_response_data['answer'])
                elif 'content' in search_response_data: search_text = str(search_response_data['content'])
                elif 'results' in search_response_data and isinstance(search_response_data['results'], list):
                    texts = [str(r.get('snippet', r.get('content', ''))) for r in search_response_data['results'] if isinstance(r, dict) and (r.get('snippet') or r.get('content'))]
                    search_text = "\n\n".join(texts)
                else:
                    search_text = str(search_response_data)
            else:
                logger.warning(f"Unexpected search_response_data format: {type(search_response_data)}")
                search_text = str(search_response_data)


            cleaned_search_text = self._clean_search_content(search_text) # Initial clean (remove images, basic <br>)
            filtered_cleaned_text = self._filter_search_text(cleaned_search_text) # Filter out "no service" type messages

            if not filtered_cleaned_text.strip():
                logger.warning("Search text is empty or fully filtered out after cleaning. Cannot summarize meaningfully.")
                # Return a message indicating search issues, which is more informative than generic "no data"
                if not cleaned_search_text.strip() and search_text.strip(): # Original had content, but cleaning removed it all
                     return "Хайлтын илэрц боловсруулахад тохиромжгүй тэмдэгтүүд агуулж байсан тул мэдээлэл гаргасангүй."
                return "Хайлтын системээс одоогоор мэдээлэл авах боломжгүй эсвэл олдсон мэдээлэл нь ашиглах боломжгүй байна."


            llm_max_input_chars = 3500
            if len(filtered_cleaned_text) > llm_max_input_chars:
                final_text_for_llm = filtered_cleaned_text[:llm_max_input_chars] + "\n... (мэдээлэл хэт урт тул таслав)"
                logger.info(f"Truncated filtered search text to ~{llm_max_input_chars} characters for LLM summary.")
            else:
                final_text_for_llm = filtered_cleaned_text

            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""Та бол Монголын үл хөдлөх хөрөнгийн зах зээлийн мэргэжлийн шинжээч. Өгөгдсөн хайлтын үр дүнг шинжлэн товч бөгөөд ойлгомжтой хураангуйг гаргана уу.
                {prompt_guideline}
                **ЧУХАЛ ЗААВАР:**
                - ХАРИУЛТ **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР** БАЙХ ЁСТОЙ.
                - **АНГЛИ ҮГ, HTML TAG (<br> гэх мэт) ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэх шаардлагатай бол зөвхөн \\n тэмдэгтийг ашиглана уу.
                - Хэрэв өгөгдсөн {{{{content}}}} текстэнд "ажиллахгүй байна", "мэдээлэл олж чадахгүй байна" гэх мэт хайлтын системийн доголдлыг илтгэх үг хэллэг байвал, эцсийн хураангуйдаа "Хайлтын системээс одоогоор мэдээлэл авах боломжгүй байна" гэсэн утгатай товч, эелдэг мэдэгдэл оруулна уу. Хүснэгтийн үг хэллэгийг үгчлэн бүү давтаарай.
                - Гол анхаарах зүйлс: Зах зээлийн гол чиг хандлага, үнийн мэдээлэл; Зах зээлд нөлөөлж буй чухал хүчин зүйлс; Хэрэв дурдсан бол тодорхой хөгжүүлэлт, өөрчлөлтүүд; Худалдан авагчид болон хөрөнгө оруулагчдад өгөх бодит зөвлөмж (хэрэв контекстэд байвал); Боломжтой бол тодорхой тоо, баримтыг ашигла.
                - Хураангуй нь тайланд оруулахад тохиромжтой, сайн бүтэцтэй, мэдээлэл сайтай байх ёстой. Хураангуйг шууд Монгол хэлээр эхлүүлнэ үү."""),
                ("human", "Хайлтын үр дүнгийн текст: {content}\n\nДээрх текстэд үндэслэн тодорхой бөгөөд товч хураангуйг Монгол хэлээр, HTML tag оролцуулалгүйгээр гаргана уу.")
            ])
            chain = prompt | self.llm | StrOutputParser()
            try:
                summary = await chain.ainvoke({"content": final_text_for_llm})
                summary = self._clean_search_content(summary.strip()) # Clean LLM output as well

                if not self._filter_search_text(summary): # Check if LLM itself produced a filtered phrase
                    logger.warning("LLM summary contained a filtered phrase. Returning a generic message.")
                    return "Хайлтын системээс одоогоор мэдээлэл авах боломжгүй байна."

                if len(summary) > max_summary_length:
                    summary = summary[:max_summary_length] + "... (дэлгэрэнгүй мэдээллийг харна уу)"
                    logger.info(f"Truncated LLM summary to ~{max_summary_length} characters.")
                return summary if summary else "Хайлтын илэрцийг хураангуйлахад мэдээлэл гарсангүй."
            except Exception as e:
                logger.error(f"Error invoking LLM for search summary: {e}", exc_info=True)
                fallback_summary = final_text_for_llm[:max_summary_length] + ("... (LLM хураангуй үүсгэхэд алдаа гарлаа)" if len(final_text_for_llm) > max_summary_length else " (LLM хураангуй үүсгэхэд алдаа гарлаа)")
                return fallback_summary
        except Exception as e:
            logger.exception(f"General error in _summarize_search_results: {e}")
            return f"Хайлтын илэрцийг хураангуйлахад системийн алдаа гарлаа: {str(e)}"

    async def _analyze_property(self, property_data_dict: dict, district_analysis_text: str) -> str:
        try:
            prompt_template = """Та бол үл хөдлөх хөрөнгийн мэргэжлийн шинжээч. Доорх үл хөдлөх хөрөнгийн мэдээлэл болон дүүргийн шинжилгээнд үндэслэн PDF тайланд зориулсан дэлгэрэнгүй үнэлгээ, харьцуулалт, зөвлөмжийг бичнэ үү.

            Гол анхаарах зүйлс:
            1.  **Үнийн Үнэлгээ:** Тухайн хөрөнгийн үнэ (нийт болон м.кв-ийн) зах зээлийн дундажтай харьцуулахад ямар байна вэ? Үнийн давуу болон сул тал. Энэ үнэ нь боломжийн эсэх.
            2.  **Байршлын Шинжилгээ:** Хөрөнгийн байршил, дүүргийн онцлог, дэд бүтэц (зам, сургууль, цэцэрлэг, үйлчилгээ), орчны давуу болон сул талууд.
            3.  **Хөрөнгө Оруулалтын Боломж:** Энэхүү хөрөнгө нь хөрөнгө оруулалтын хувьд ямар боломжтой вэ? Үнэ цэнийн өсөлт, түрээсийн орлогын боломж, эрсдэл.
            4.  **Дүгнэлт ба Зөвлөмж:** Дээрх шинжилгээнд үндэслэн худалдан авагч/хөрөнгө оруулагчдад өгөх тодорхой, бодит зөвлөмж. Ямар төрлийн хүнд илүү тохиромжтой байж болох вэ?

            ХАРИУЛТ **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР**, 3-5 догол мөр бүхий дэлгэрэнгүй, бүтэцтэй, тайланд оруулахад тохиромжтой байдлаар бичигдсэн байх ёстой. **АНГЛИ ҮГ, HTML TAG ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэхдээ \\n тэмдэгт ашиглана уу. Жишээ нь: "1. Үнийн Үнэлгээ: Энэхүү орон сууцны м.кв үнэ нь..." гэж эхэлнэ үү.
            """
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                ("human", "Үл хөдлөх хөрөнгийн дэлгэрэнгүй мэдээлэл: {property_json_str}\n\nДүүргийн шинжилгээний текст (контекст болгон ашиглана уу): {district_text}\n\nДээрх мэдээлэлд үндэслэн үнэлгээ, харьцуулалт, зөвлөмж бүхий шинжилгээг Монгол хэлээр бичнэ үү.")
            ])

            if not property_data_dict:
                property_data_dict = {"title": "Мэдээлэл байхгүй", "price_per_sqm": 0, "error": "No property data provided"}

            if len(district_analysis_text) > 800:
                district_analysis_text = district_analysis_text[:800] + "... (текст таслагдав)"

            chain = prompt | self.llm | StrOutputParser()
            try:
                analysis = await chain.ainvoke({
                    "property_json_str": json.dumps(property_data_dict, ensure_ascii=False, indent=2),
                    "district_text": district_analysis_text
                })
                analysis = self._clean_search_content(analysis.strip())
                if not analysis or len(analysis) < 100:
                    logger.warning(f"LLM analysis for property returned too short or empty. Property: {property_data_dict.get('title', 'N/A')}")
                    return "Үл хөдлөх хөрөнгийн дэлгэрэнгүй үнэлгээ, харьцуулалт хийхэд хангалттай мэдээлэл гарсангүй. Зах зээлийн дундаж үнэ, байршлын онцлогийг судалж үзнэ үү. Мэргэжилтнээс зөвлөгөө авахыг зөвлөж байна."
                return analysis
            except Exception as e:
                logger.error(f"Error invoking LLM for property detailed analysis: {e}", exc_info=True)
                return "Үл хөдлөх хөрөнгийн дэлгэрэнгүй үнэлгээ, харьцуулалт хийхэд LLM алдаа гарлаа. Мэдээллийн хүртээмжийг шалгана уу."
        except Exception as e:
            logger.error(f"Error in _analyze_property: {e}", exc_info=True)
            return f"Үл хөдлөх хөрөнгийн дэлгэрэнгүй шинжилгээг боловсруулахад алдаа гарлаа: {str(e)}"

    async def _analyze_market_for_report(self, districts_data_list: list) -> str:
        try:
            prompt_template = """Та бол үл хөдлөх хөрөнгийн зах зээлийн шинжээч. Доорх дүүргүүдийн структурчилсан мэдээлэлд ('List of district data') үндэслэн PDF тайланд зориулсан зах зээлийн цогц шинжилгээний хураангуйг гаргана уу.
            Таны хариулт дараах бүтэцтэй байх ёстой бөгөөд хэсгийн гарчгийг яг доорх байдлаар ашиглана уу:

            1.  **Зах Зээлийн Ерөнхий Тойм (Market Overview)**: 'List of district data'-д үндэслэн Улаанбаатар хотын дүүргүүдийн орон сууцны зах зээлийн одоогийн байдлыг нэгтгэн дүгнэ. Ерөнхий үнийн түвшин, гол чиг хандлагыг дурд.
            2.  **Үнийн Харьцуулалт ба Ялгаа (Price Comparison and Differentials)**: Хамгийн өндөр болон хамгийн бага дундаж үнэтэй дүүргүүдийг тодорхойлж, 'List of district data'-г ашиглан үнийн ялгааг тайлбарла. Боломжтой бол эдгээр үнийн ялгаанд нөлөөлж буй хүчин зүйлсийн талаар таамаглал дэвшүүл.
            3.  **Хөрөнгө Оруулалтын Боломжит Бүсүүд (Potential Investment Zones)**: 'List of district data'-д үндэслэн өөр өөр төсөвтэй (дээд зэрэглэлийн, дунд түвшний, боломжийн үнэтэй) хөрөнгө оруулагчдад илүү сонирхолтой байж болох дүүргүүдийг ангил.
            4.  **Худалдан Авагчдад Өгөх Стратеги (Buyer Strategies)**: Төрөл бүрийн худалдан авагчдад (анх удаа байр авч буй хүмүүс, байраа томсгохыг хүсч буй гэр бүлүүд, хөрөнгө оруулагчид) хэрэгцээнд нь нийцүүлэн аль дүүрэг давуу талтай байж болох талаар зөвлө.
            5.  **Зах Зээлийн Ирээдүйн Төлөв (Market Outlook - if inferable)**: Одоогийн мэдээлэлд үндэслэн зах зээлийн ойрын ирээдүйн талаар болгоомжтой таамаглал дэвшүүл (хэрэв боломжтой бол).

            Зааварчилгаа:
            -   'List of district data'-аас тодорхой тоо баримт, дундаж үнийг ашигла.
            -   Дүгнэлт, зөвлөмж нь бодитой, өгөгдөлд суурилсан байх ёстой.
            -   Тайланд тохиромжтой, албан ёсны өнгө аясыг баримтал. ХАРИУЛТ ЗААВАЛ 300-500 үгтэй байх.

            ЧУХАЛ: Таны эцсийн хариулт БҮХЭЛДЭЭ **ЗӨВХӨН МОНГОЛ ХЭЛЭЭР** бичигдсэн байх ёстой. **АНГЛИ ҮГ, HTML TAG ОГТ ХЭРЭГЛЭЖ БОЛОХГҮЙ.** Шинэ мөр үүсгэхдээ \\n тэмдэгт ашиглана уу. Жишээ нь: "1. Зах Зээлийн Ерөнхий Тойм: ..." гэж эхэлнэ үү.
            """
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                ("human", "Дүүргүүдийн мэдээллийн жагсаалт: {districts_json_str}\n\nДээрх дүүргийн мэдээлэлд үндэслэн PDF тайланд зориулсан зах зээлийн дэлгэрэнгүй шинжилгээг Монгол хэлээр бичнэ үү.")
            ])

            if not districts_data_list or len(districts_data_list) == 0:
                logger.warning("Empty district data list provided for LLM market analysis.")
                return "Дүүргүүдийн мэдээлэл байхгүй тул зах зээлийн дэлгэрэнгүй шинжилгээ хийх боломжгүй. Мэдээллийн санг шалгана уу."

            chain = prompt | self.llm | StrOutputParser()
            try:
                analysis = await chain.ainvoke({
                    "districts_json_str": json.dumps(districts_data_list, ensure_ascii=False, indent=2)
                })
                analysis = self._clean_search_content(analysis.strip())
                if not analysis or len(analysis) < 150:
                    logger.warning("LLM market analysis (from district data) response was too short or empty.")
                    return "Дүүргүүдийн мэдээллийг нэгтгэн дүгнэхэд хангалттай мэдээлэл гарсангүй. Үнийн ерөнхий түвшин болон байршлын онцлогийг харгалзан үзнэ үү. Дэлгэрэнгүй шинжилгээ хийхийн тулд нэмэлт судалгаа шаардлагатай."
                return analysis
            except Exception as e:
                logger.error(f"Error invoking LLM for market analysis from district data: {e}", exc_info=True)
                return "Дүүргүүдийн мэдээллийг нэгтгэн дүгнэхэд LLM алдаа гарлаа. Системийн админтай холбогдоно уу."
        except Exception as e:
            logger.exception(f"Error in _analyze_market_for_report: {e}")
            return f"Зах зээлийн шинжилгээг (дүүргийн мэдээлэлд үндэслэсэн) боловсруулахад системийн алдаа гарлаа: {str(e)}"

    async def _generate_property_summary_with_validation(self, query: str, property_data: Dict,
                                                         district_analysis: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Та үл хөдлөх хөрөнгийн мэргэжилтэн. Зөвхөн монгол хэлээр, 150 үгэнд багтаан товч дүгнэлт өгнө үү."),
            ("human", "Орон сууц: {property}\nДүүрэг: {district}\n\nТовч дүгнэлт:")
        ])
        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "property": json.dumps(property_data, ensure_ascii=False)[:500], "district": district_analysis[:300]})
        return self._clean_search_content(response.strip())

    async def _generate_market_analysis_with_validation(self, query: str, search_content: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Та үл хөдлөх хөрөнгийн зах зээлийн судлаач. Зөвхөн монгол хэлээр, 120 үгэнд багтаан шинжилгээ өгнө үү."),
            ("human", "Асуулт: {query}\nМэдээлэл: {content}\n\nЗах зээлийн шинжилгээ:")
        ])
        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({"query": query, "content": search_content[:2000]})
        return self._clean_search_content(response.strip())

    async def _generate_general_response_with_validation(self, query: str, search_content: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Та туслах робот. Зөвхөн монгол хэлээр, 100 үгэнд багтаан хариулт өгнө үү."),
            ("human", "Асуулт: {query}\nМэдээлэл: {content}\n\nХариулт:")
        ])
        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({"query": query, "content": search_content[:1500]})
        return self._clean_search_content(response.strip())