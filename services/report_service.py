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
        content = re.sub(r"https?://[^\s<>\"]*\.(jpg|jpeg|png|gif|webp|svg)(\?[^\s<>\"']*)?", '', content,
                         flags=re.IGNORECASE)
        content = re.sub(r'data:image/[^;]+;base64,[^\s<>"]+', '', content)
        content = re.sub(r'\[image[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\[photo[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\[picture[^\]]*\]', '', content, flags=re.IGNORECASE)

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
                property_data_dict = {"title": "No Information", "price_per_sqm": 0}

            district_analysis_text = analysis_data.get("district_analysis_string",
                                                       "District analysis information not found.")
            search_results_text = await self._search_property_info(property_data_dict)

            try:
                detailed_llm_analysis = await self._analyze_property(property_data_dict, district_analysis_text)
            except Exception as e:
                logger.error(f"Error in property analysis: {e}", exc_info=True)
                detailed_llm_analysis = "An error occurred while performing detailed property analysis."

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
            query = analysis_data.get("query", "general districts")
            analysis_type = analysis_data.get("type", "district")
            base_analysis_content = analysis_data.get("analysis_content", "District information not found.")

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
                search_results_text = await self._search_market_info(
                    query="Ulaanbaatar districts real estate market overview")
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
                search_results_text = await self._search_market_info(
                    query=f"{single_district_name} district real estate market information")
                focused_district_data = [d for d in districts_data_for_pdf if d.get('name') == single_district_name]
                if focused_district_data:
                    try:
                        market_analysis_for_pdf = await self._analyze_market_for_report(focused_district_data)
                    except Exception as e:
                        logger.error(f"Error analyzing market for single district '{single_district_name}': {e}",
                                     exc_info=True)
                        market_analysis_for_pdf = f"{single_district_name} дүүргийн зах зээлийн чиг хандлагыг тодорхойлоход алдаа гарлаа."
                else:
                    market_analysis_for_pdf = f"{single_district_name} дүүргийн талаарх дэлгэрэнгүй мэдээлэл олдсонгүй. {base_analysis_content}"
            else:
                return {"message": "Тайлангийн төрөл тодорхойгүй байна.", "success": False}

            generated_future_outlook_text = ""
            current_context_for_outlook = f"Current district information: {json.dumps(districts_data_for_pdf, ensure_ascii=False, indent=2)}\n\nGeneral market analysis: {market_analysis_for_pdf}"
            try:
                future_outlook_prompt_template = ChatPromptTemplate.from_messages([
                    ("system", """You are a real estate market analyst in Mongolia.
                     Based on the given district information and general market trends, develop a "Future Development Outlook" section for the PDF report.
                     This section should discuss infrastructure projects, development of educational and commercial facilities, price trends, or risks related to future development that might affect these districts.
                     Your answer MUST BE ONLY IN MONGOLIAN, detailed, suitable for an official report, with 3-5 paragraphs. DO NOT USE ENGLISH WORDS OR HTML TAGS. Use \\n for new lines."""),
                    ("human",
                     "Context:\n{context_for_outlook}\n\nBased on the above information, write the content for the 'Future Development Outlook' section in Mongolian.")
                ])
                future_outlook_chain = future_outlook_prompt_template | self.llm | StrOutputParser()
                generated_future_outlook_text = await future_outlook_chain.ainvoke(
                    {"context_for_outlook": current_context_for_outlook})
                generated_future_outlook_text = self._clean_search_content(generated_future_outlook_text.strip())
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
            user_query = analysis_data.get("query", "general market")
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
                    prompt_guideline="Provide detailed trends, statistics, and future outlook for the Ulaanbaatar real estate market. Highlight key figures and changes, and generate a comprehensive summary for a report including an overview, price trends, and market predictions.",
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

            market_context_for_llm = f"General market summary (to be used for Overview, Price Trends, and Forecasts): {report_focused_search_summary}\n\nComparative District Analysis: {llm_analysis_of_districts}\n\nDetailed initial search information (use if needed): {search_content_from_chat[:1000]}"

            generated_supply_demand_text = ""
            try:
                supply_demand_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a Mongolian real estate analyst. Based on the given market information, write a "Supply-Demand Analysis" section ONLY IN MONGOLIAN, suitable for an official report, in detail.
                    Identify key demand drivers (e.g., demographics, credit availability) and current supply conditions (new construction, existing housing stock), and how they affect market balance. If possible, mention quantitative indicators and trends, providing in-depth analysis with 3-5 paragraphs. DO NOT USE ENGLISH WORDS OR HTML TAGS. Use \\n for new lines."""),
                    ("human",
                     "Market context:\n{market_context}\n\nBased on the above information, write the 'Supply-Demand Analysis' section.")
                ])
                supply_demand_chain = supply_demand_prompt | self.llm | StrOutputParser()
                generated_supply_demand_text = await supply_demand_chain.ainvoke(
                    {"market_context": market_context_for_llm})
                generated_supply_demand_text = self._clean_search_content(generated_supply_demand_text.strip())
                if not generated_supply_demand_text or len(generated_supply_demand_text) < 50:
                    generated_supply_demand_text = "Зах зээлийн эрэлт нийлүүлэлтийн талаарх дэлгэрэнгүй мэдээллийг боловсруулах боломжгүй. Ерөнхийдөө барилгын салбарын идэвхжил, зээлийн хүртээмж, хүн амын өсөлт зэрэг нь эрэлт нийлүүлэлтэд голлон нөлөөлдөг."
            except Exception as e:
                logger.error(f"Error generating supply_demand text: {e}", exc_info=True)
                generated_supply_demand_text = "Эрэлт нийлүүлэлтийн шинжилгээг хийхэд алдаа гарлаа. Зах зээлийн судалгааны байгууллагуудын тайланг үзнэ үү."

            generated_investment_strategy_text = ""
            try:
                investment_strategy_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a real estate investment advisor in Mongolia. Based on the given market information, write an "Investment Strategy and Opportunities" section ONLY IN MONGOLIAN, suitable for an official report, in detail.
                    Mention short-term and long-term strategies, risk mitigation methods, and highlighted opportunities (e.g., specific districts, property types), providing in-depth analysis with 3-5 paragraphs. DO NOT USE ENGLISH WORDS OR HTML TAGS. Use \\n for new lines."""),
                    ("human",
                     "Market context:\n{market_context}\n\nBased on the above information, write the 'Investment Strategy and Opportunities' section.")
                ])
                investment_strategy_chain = investment_strategy_prompt | self.llm | StrOutputParser()
                generated_investment_strategy_text = await investment_strategy_chain.ainvoke(
                    {"market_context": market_context_for_llm})
                generated_investment_strategy_text = self._clean_search_content(
                    generated_investment_strategy_text.strip())
                if not generated_investment_strategy_text or len(generated_investment_strategy_text) < 50:
                    generated_investment_strategy_text = "Хөрөнгө оруулалтын стратегийн талаарх дэлгэрэнгүй зөвлөмжийг боловсруулах боломжгүй. Ерөнхийдөө байршил, ирээдүйн хөгжлийн төлөв, түрээсийн өгөөж, хувийн санхүүгийн зорилго зэргийг харгалзан үзэх нь чухал."
            except Exception as e:
                logger.error(f"Error generating investment_strategy text: {e}", exc_info=True)
                generated_investment_strategy_text = "Хөрөнгө оруулалтын стратеги боловсруулахад алдаа гарлаа. Мэргэжлийн санхүүгийн зөвлөхтэй зөвлөлдөнө үү."

            generated_risk_assessment_text = ""
            try:
                risk_assessment_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a real estate risk analyst in Mongolia. Based on the given market information, write the CONTENT for the "Risk Assessment and Warnings" section ONLY IN MONGOLIAN, suitable for an official report, in detail. DO NOT REPEAT THE SECTION TITLE.
                    Mention potential macroeconomic, market-specific, policy, and other risks, and methods to prevent them or mitigate risks, providing in-depth analysis with 3-5 paragraphs. DO NOT USE ENGLISH WORDS OR HTML TAGS. Use \\n for new lines."""),
                    ("human",
                     "Market context:\n{market_context}\n\nBased on the above information, write the CONTENT for the 'Risk Assessment and Warnings' section.")
                ])
                risk_assessment_chain = risk_assessment_prompt | self.llm | StrOutputParser()
                generated_risk_assessment_text = await risk_assessment_chain.ainvoke(
                    {"market_context": market_context_for_llm})
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
        if not self.district_analyzer or not hasattr(self.district_analyzer,
                                                     'vectorstore') or not self.district_analyzer.vectorstore:
            logger.warning("DistrictAnalyzer or its vectorstore not available. Using fallback data.")
            return self._get_fallback_data()

        all_docs = []
        try:
            if hasattr(self.district_analyzer.vectorstore, 'docstore') and \
                    hasattr(self.district_analyzer.vectorstore.docstore, '_dict'):
                all_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
                logger.info(f"Retrieved {len(all_docs)} documents directly from docstore.")
            else:
                logger.warning(
                    "Cannot directly access vectorstore's full document list. Fallback needed or vectorstore inspection.")
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
                    (r"(?:Нийт байрны|Нийт ерөнхий|Ерөнхий дундаж)\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)",
                     'overall_avg'),
                    (r"2 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)",
                     'two_room_avg'),
                    (r"3 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)",
                     'three_room_avg'),
                    (r"1 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)",
                     'one_room_avg'),
                    (r"4 өрөө(?:ний)?\s*(?:байрны)?\s*1м2?\s*дундаж үнэ:\s*([\d\s,.]+)\s*(?:₮|төгрөг|MNT)",
                     'four_room_avg'),
                ]
                for pattern, key in price_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        price_val = self._parse_price_value(match.group(1))
                        if price_val > 0:
                            district_info[key] = price_val

                if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
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
            {'name': 'Sukhbaatar', 'overall_avg': 4500000, 'two_room_avg': 4600000, 'three_room_avg': 4400000},
            {'name': 'Khan-Uul', 'overall_avg': 4000000, 'two_room_avg': 4100000, 'three_room_avg': 3900000},
            {'name': 'Chingeltei', 'overall_avg': 3800000, 'two_room_avg': 3900000, 'three_room_avg': 3700000},
            {'name': 'Bayangol', 'overall_avg': 3500000, 'two_room_avg': 3600000, 'three_room_avg': 3400000},
            {'name': 'Bayanzurkh', 'overall_avg': 3200000, 'two_room_avg': 3300000, 'three_room_avg': 3100000},
            {'name': 'Songinokhairkhan', 'overall_avg': 2800000, 'two_room_avg': 2900000, 'three_room_avg': 2700000},
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
                clean_title = re.sub(r'\d+\s*өрөө|\bбайр\b|\bорон сууц\b|\bзарна\b', '', title,
                                     flags=re.IGNORECASE).strip()
                specific_location_parts = clean_title.split()[:3]
                if specific_location_parts:
                    query_parts.append(" ".join(specific_location_parts))
            query_parts.append("орчны мэдээлэл үнэ ханш түрээс")
            query = " ".join(query_parts)
            logger.info(f"Searching for property context with query: {query}")
            search_response = await self.search_tool.ainvoke({"query": query})

            return await self._summarize_search_results(
                search_response,
                prompt_guideline="Тухайн үл хөдлөх хөрөнгийн байршил, орчин тойрны мэдээлэл, ойролцоох үнэ ханш, зах зээлийн идэвхжилийн талаарх гол мэдээллийг гарга. Тайлангийн хэсэгт тохиромжтой, товч байдлаар нэгтгэ.",
                max_summary_length=600
            )
        except Exception as e:
            logger.exception(f"Error during property information search: {e}")
            return "Үл хөдлөх хөрөнгийн талаарх нэмэлт мэдээлэл хайхад алдаа гарлаа."

    async def _search_market_info(self,
                                  query: str = "Улаанбаатар орон сууцны зах зээлийн ерөнхий мэдээлэл 2024 2025") -> str:
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

    async def _summarize_search_results(self, search_response_data: any,
                                        prompt_guideline: str = "Extract key market trends, pricing information, and actionable insights.",
                                        max_summary_length: int = 1000) -> str:
        try:
            search_text = ""
            if isinstance(search_response_data, str):
                search_text = search_response_data
            elif isinstance(search_response_data, list):
                texts = []
                for item in search_response_data:
                    if isinstance(item, dict):
                        content = item.get('content', '') or item.get('snippet', '')
                        if content: texts.append(str(content))
                    elif hasattr(item, 'page_content'):
                        texts.append(str(item.page_content))
                    elif isinstance(item, str):
                        texts.append(item)
                search_text = "\n\n".join(texts)
            elif isinstance(search_response_data, dict):
                if 'answer' in search_response_data:
                    search_text = str(search_response_data['answer'])
                elif 'content' in search_response_data:
                    search_text = str(search_response_data['content'])
                elif 'results' in search_response_data and isinstance(search_response_data['results'], list):
                    texts = [str(r.get('snippet', r.get('content', ''))) for r in search_response_data['results'] if
                             isinstance(r, dict) and (r.get('snippet') or r.get('content'))]
                    search_text = "\n\n".join(texts)
                else:
                    search_text = str(search_response_data)
            else:
                logger.warning(f"Unexpected search_response_data format: {type(search_response_data)}")
                search_text = str(search_response_data)

            cleaned_search_text = self._clean_search_content(search_text)
            filtered_cleaned_text = self._filter_search_text(cleaned_search_text)

            if not filtered_cleaned_text.strip():
                logger.warning(
                    "Search text is empty or fully filtered out after cleaning. Cannot summarize meaningfully.")
                if not cleaned_search_text.strip() and search_text.strip():
                    return "Хайлтын илэрц боловсруулахад тохиромжгүй тэмдэгтүүд агуулж байсан тул мэдээлэл гаргасангүй."
                return "Хайлтын системээс одоогоор мэдээлэл авах боломжгүй эсвэл олдсон мэдээлэл нь ашиглах боломжгүй байна."

            llm_max_input_chars = 3500
            if len(filtered_cleaned_text) > llm_max_input_chars:
                final_text_for_llm = filtered_cleaned_text[:llm_max_input_chars] + "\n... (мэдээлэл хэт урт тул таслав)"
                logger.info(f"Truncated filtered search text to ~{llm_max_input_chars} characters for LLM summary.")
            else:
                final_text_for_llm = filtered_cleaned_text

            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a professional real estate market analyst in Mongolia. Analyze the given search results and provide a concise and understandable summary.
                {prompt_guideline}
                **IMPORTANT INSTRUCTIONS:**
                - THE ANSWER MUST BE **ONLY IN MONGOLIAN**.
                - **DO NOT USE ENGLISH WORDS OR HTML TAGS (like <br>).** If new lines are needed, use only the \\n character.
                - If the provided {{{{content}}}} text contains phrases indicating search system failures like "not working" or "cannot find information", include a brief, polite statement in your final summary such as "Хайлтын системээс одоогоор мэдээлэл авах боломжгүй байна." Do not verbatim repeat table phrases.
                - Key focus areas: Major market trends, pricing information; Important factors affecting the market; Specific developments and changes if mentioned; Practical advice for buyers and investors (if in context); Use specific numbers and facts if possible.
                - The summary should be suitable for inclusion in a report, well-structured, and informative. Start the summary directly in Mongolian."""),
                ("human",
                 "Search result text: {content}\n\nBased on the above text, generate a clear and concise summary in Mongolian, without including HTML tags.")
            ])
            chain = prompt | self.llm | StrOutputParser()
            try:
                summary = await chain.ainvoke({"content": final_text_for_llm})
                summary = self._clean_search_content(summary.strip())

                if not self._filter_search_text(summary):
                    logger.warning("LLM summary contained a filtered phrase. Returning a generic message.")
                    return "Хайлтын системээс одоогоор мэдээлэл авах боломжгүй байна."

                if len(summary) > max_summary_length:
                    summary = summary[:max_summary_length] + "... (дэлгэрэнгүй мэдээллийг харна уу)"
                    logger.info(f"Truncated LLM summary to ~{max_summary_length} characters.")
                return summary if summary else "Хайлтын илэрцийг хураангуйлахад мэдээлэл гарсангүй."
            except Exception as e:
                logger.error(f"Error invoking LLM for search summary: {e}", exc_info=True)
                fallback_summary = final_text_for_llm[:max_summary_length] + (
                    "... (LLM хураангуй үүсгэхэд алдаа гарлаа)" if len(
                        final_text_for_llm) > max_summary_length else " (LLM хураангуй үүсгэхэд алдаа гарлаа)")
                return fallback_summary
        except Exception as e:
            logger.exception(f"General error in _summarize_search_results: {e}")
            return f"Хайлтын илэрцийг хураангуйлахад системийн алдаа гарлаа: {str(e)}"

    async def _analyze_property(self, property_data_dict: dict, district_analysis_text: str) -> str:
        try:
            prompt_template = """You are a professional real estate analyst. Based on the property information and district analysis below, write a detailed assessment, comparison, and recommendations for a PDF report.

            Key focus areas:
            1.  **Price Valuation:** How does the property's price (total and per sqm) compare to the market average? Price advantages and disadvantages. Is this price reasonable?
            2.  **Location Analysis:** Property location, district specifics, infrastructure (roads, schools, kindergartens, services), advantages and disadvantages of the surroundings.
            3.  **Investment Potential:** What investment opportunities does this property offer? Potential for value appreciation, rental income opportunities, and risks.
            4.  **Conclusion and Recommendation:** Based on the above analysis, provide specific, practical recommendations for buyers/investors. What type of person might this property be more suitable for?

            THE ANSWER MUST BE **ONLY IN MONGOLIAN**, detailed with 3-5 paragraphs, structured, and suitable for inclusion in a report. **DO NOT USE ENGLISH WORDS OR HTML TAGS.** Use \\n for new lines. Example: "1. Үнийн Үнэлгээ: Энэхүү орон сууцны м.кв үнэ нь..."
            """
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                ("human",
                 "Detailed property information: {property_json_str}\n\nDistrict analysis text (use as context): {district_text}\n\nBased on the above information, write an analysis including assessment, comparison, and recommendations in Mongolian.")
            ])

            if not property_data_dict:
                property_data_dict = {"title": "No Information", "price_per_sqm": 0,
                                      "error": "No property data provided"}

            if len(district_analysis_text) > 800:
                district_analysis_text = district_analysis_text[:800] + "... (text truncated)"

            chain = prompt | self.llm | StrOutputParser()
            try:
                analysis = await chain.ainvoke({
                    "property_json_str": json.dumps(property_data_dict, ensure_ascii=False, indent=2),
                    "district_text": district_analysis_text
                })
                analysis = self._clean_search_content(analysis.strip())
                if not analysis or len(analysis) < 100:
                    logger.warning(
                        f"LLM analysis for property returned too short or empty. Property: {property_data_dict.get('title', 'N/A')}")
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
            prompt_template = """You are a real estate market analyst. Based on the structured district information ('List of district data') below, generate a comprehensive market analysis summary for a PDF report.
            Your answer must follow the structure below, using the exact section titles:

            1.  **Market Overview**: Based on the 'List of district data', summarize the current state of the Ulaanbaatar real estate market across its districts. Mention general price levels and key trends.
            2.  **Price Comparison and Differentials**: Identify the districts with the highest and lowest average prices, and explain the price differentials using the 'List of district data'. If possible, hypothesize factors influencing these price differences.
            3.  **Potential Investment Zones**: Based on the 'List of district data', categorize districts that might be more attractive to investors with different budgets (premium, mid-range, affordable).
            4.  **Buyer Strategies**: Advise various types of buyers (first-time homebuyers, families looking to upgrade, investors) on which districts might offer advantages suited to their needs.
            5.  **Market Outlook (if inferable)**: Based on the current information, make a cautious prediction about the near future of the market (if possible).

            Instructions:
            -   Use specific facts and average prices from the 'List of district data'.
            -   Conclusions and recommendations must be realistic and data-driven.
            -   Maintain a formal tone suitable for a report. The ANSWER MUST BE 300-500 words.

            IMPORTANT: Your final answer must be ENTIRELY **ONLY IN MONGOLIAN**. **DO NOT USE ENGLISH WORDS OR HTML TAGS.** Use \\n for new lines. Example: "1. Зах Зээлийн Ерөнхий Тойм: ..."
            """
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                ("human",
                 "List of district information: {districts_json_str}\n\nBased on the above district information, write a detailed market analysis for a PDF report in Mongolian.")
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
            ("system", "You are a real estate expert. Provide a concise summary ONLY IN MONGOLIAN, within 150 words."),
            ("human", "Apartment: {property}\nDistrict: {district}\n\nConcise summary:")
        ])
        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "property": json.dumps(property_data, ensure_ascii=False)[:500], "district": district_analysis[:300]})
        return self._clean_search_content(response.strip())

    async def _generate_market_analysis_with_validation(self, query: str, search_content: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a real estate market researcher. Provide an analysis ONLY IN MONGOLIAN, within 120 words."),
            ("human", "Question: {query}\nInformation: {content}\n\nMarket analysis:")
        ])
        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({"query": query, "content": search_content[:2000]})
        return self._clean_search_content(response.strip())

    async def _generate_general_response_with_validation(self, query: str, search_content: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant robot. Provide an answer ONLY IN MONGOLIAN, within 100 words."),
            ("human", "Question: {query}\nInformation: {content}\n\nAnswer:")
        ])
        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({"query": query, "content": search_content[:1500]})
        return self._clean_search_content(response.strip())