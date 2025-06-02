# Modified report_service.py

import logging
import json
import re
from datetime import datetime
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, llm, district_analyzer, pdf_generator, search_tool=None):
        self.llm = llm
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator
        self.search_tool = search_tool

    def _clean_search_content(self, content: str) -> str:
        if not content:
            return ""
        # ... (cleaning logic remains the same)
        content = re.sub(r'!\[.*?\]\([^)]+\)', '', content)
        content = re.sub(r'<img[^>]*>', '', content)
        content = re.sub(r'https?://[^\s<>"\']*\.(jpg|jpeg|png|gif|webp|svg)(\?[^\s]*)?', '', content,
                         flags=re.IGNORECASE)
        content = re.sub(r'data:image/[^;]+;base64,[^\s]+', '', content)
        content = re.sub(r'\[image[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\[photo[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\[picture[^\]]*\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = re.sub(r' +', ' ', content)
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        content = '\n'.join(lines)
        return content.strip()

    async def generate_property_report(self, analysis_data: dict) -> dict:
        logger.info("Generating property report")
        try:
            # ... (timestamp check and data extraction logic remains the same)
            if 'timestamp' in analysis_data:
                analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                time_diff = datetime.now() - analysis_time
                if time_diff.total_seconds() > 600:  # 10 minutes
                    logger.warning("Property analysis data for report is older than 10 minutes.")

            property_data_dict = analysis_data.get("property_data", {})
            district_analysis_text = analysis_data.get("district_analysis_string",
                                                       "Дүүргийн шинжилгээний мэдээлэл олдсонгүй.")
            search_results_text = await self._search_property_info(property_data_dict)
            detailed_llm_analysis = await self._analyze_property(
                property_data_dict,
                district_analysis_text
            )
            # ... (pdf generation and response remains the same)
            pdf_path = self.pdf_generator.generate_property_analysis_report(
                property_data=property_data_dict,
                district_analysis=district_analysis_text,
                comparison_result=detailed_llm_analysis,
                search_results=search_results_text
            )
            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"
            return {
                "message": f"Үл хөдлөх хөрөнгийн PDF тайлан ({filename}) бэлэн боллоо!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.exception("Error generating property report")
            return {
                "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
                "success": False
            }

    async def generate_district_report(self, analysis_data: dict) -> dict:
        logger.info("Generating district report")
        try:
            # ... (timestamp check and data extraction logic remains the same)
            query = analysis_data.get("query", "ерөнхий дүүргүүд")
            analysis_type = analysis_data.get("type", "district")
            base_analysis_content = analysis_data.get("analysis_content", "Дүүргийн мэдээлэл олдсонгүй.")

            if 'timestamp' in analysis_data:
                analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                time_diff = datetime.now() - analysis_time
                if time_diff.total_seconds() > 1800:  # 30 minutes
                    logger.warning("District/Market analysis data for report is older than 30 minutes.")

            districts_data_for_pdf = []
            market_analysis_for_pdf = ""
            search_results_text = ""

            if analysis_type == "district_comparison":
                districts_data_for_pdf = self._extract_districts_data()
                search_results_text = await self._search_market_info(
                    query="Улаанбаатар дүүргүүдийн үл хөдлөх хөрөнгийн зах зээл")
                if districts_data_for_pdf:
                    market_analysis_for_pdf = await self._analyze_market_for_report(districts_data_for_pdf)
                else:
                    market_analysis_for_pdf = base_analysis_content

            elif analysis_type == "district":
                single_district_name = query
                districts_data_for_pdf = self._extract_districts_data()
                search_results_text = await self._search_market_info(
                    query=f"{single_district_name} дүүргийн үл хөдлөх хөрөнгийн зах зээл")

                llm_analysis_of_all_districts_context = ""
                if districts_data_for_pdf:
                    llm_analysis_of_all_districts_context = await self._analyze_market_for_report(
                        districts_data_for_pdf)

                market_analysis_for_pdf = f"**{single_district_name.capitalize()} дүүргийн шинжилгээ:**\n{base_analysis_content}\n\n**Ерөнхий зах зээлийн чиг хандлага (бусад дүүргүүдийн мэдээлэлд үндэслэв):**\n{llm_analysis_of_all_districts_context}"
            else:
                return {"message": "Тайлангийн төрөл тодорхойгүй байна.", "success": False}

            # ... (pdf generation and response remains the same)
            pdf_path = self.pdf_generator.generate_district_summary_report(
                districts_data=districts_data_for_pdf,
                market_trends=market_analysis_for_pdf,
                search_results=search_results_text
            )
            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"
            return {
                "message": f"Дүүргийн PDF тайлан ({filename}) бэлэн боллоо!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }
        except Exception as e:
            logger.exception("Error generating district report")
            return {
                "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
                "success": False
            }

    async def generate_market_report(self, analysis_data: dict) -> dict:
        logger.info("Generating market report")
        try:
            # ... (timestamp check and data extraction logic remains the same)
            user_query = analysis_data.get("query", "ерөнхий зах зээл")
            search_content_from_chat = analysis_data.get("search_content", "")

            if 'timestamp' in analysis_data:
                analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                time_diff = datetime.now() - analysis_time
                if time_diff.total_seconds() > 1800:  # 30 minutes
                    logger.warning("Market analysis data for report is older than 30 minutes.")

            report_focused_search_summary = await self._summarize_search_results(
                search_content_from_chat,
                prompt_guideline="Focus on detailed trends, statistics, and future outlook for a comprehensive report."
            )
            current_districts_structured_data = self._extract_districts_data()
            llm_analysis_of_districts = ""
            if current_districts_structured_data:
                llm_analysis_of_districts = await self._analyze_market_for_report(current_districts_structured_data)
            # ... (pdf generation and response remains the same)

            pdf_path = self.pdf_generator.generate_market_analysis_report(
                market_summary_from_search=report_focused_search_summary,
                current_district_data_analysis=llm_analysis_of_districts,
                user_query=user_query,
                raw_search_content_preview=search_content_from_chat[:1000]
            )
            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"
            return {
                "message": f"Зах зээлийн PDF тайлан ({filename}) бэлэн боллоо!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.exception("Error generating market report")
            return {
                "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
                "success": False
            }

    def _extract_districts_data(self) -> list:
        # ... (logic remains the same)
        if not self.district_analyzer or not self.district_analyzer.vectorstore:
            logger.warning("DistrictAnalyzer or its vectorstore not available for data extraction. Using fallback.")
            return self._get_fallback_data()

        available_docs = []
        try:
            # Ensure docstore and _dict exist and are not None
            if hasattr(self.district_analyzer.vectorstore, 'docstore') and \
                    self.district_analyzer.vectorstore.docstore is not None and \
                    hasattr(self.district_analyzer.vectorstore.docstore, '_dict') and \
                    self.district_analyzer.vectorstore.docstore._dict is not None:
                available_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
            else:
                logger.warning("Vectorstore docstore or _dict is not available or None. Using fallback.")
                return self._get_fallback_data()
        except Exception as e:
            logger.error(f"Failed to access vectorstore.docstore._dict: {e}. Using fallback.")
            return self._get_fallback_data()

        if not available_docs:
            logger.warning("Vectorstore is empty. Using fallback district data.")
            return self._get_fallback_data()

        districts_data = []
        for doc in available_docs:
            content = doc.page_content.strip()
            district_info = {}
            name_match = re.search(r"Дүүрэг:\s*(.+)", content)
            if name_match:
                district_info['name'] = name_match.group(1).strip()

            overall_match = re.search(r"(?:Нийт байрны|Нийт ерөнхий) 1м2? дундаж үнэ:\s*([\d\s,]+)\s*(?:₮|төгрөг)",
                                      content)
            if overall_match:
                district_info['overall_avg'] = self._parse_price_value(overall_match.group(1))

            rooms_2_match = re.search(r"2 өрөө байрны 1м2? дундаж үнэ:\s*([\d\s,]+)\s*(?:₮|төгрөг)", content)
            if rooms_2_match:
                district_info['two_room_avg'] = self._parse_price_value(rooms_2_match.group(1))

            rooms_3_match = re.search(r"3 өрөө байрны 1м2? дундаж үнэ:\s*([\d\s,]+)\s*(?:₮|төгрөг)", content)
            if rooms_3_match:
                district_info['three_room_avg'] = self._parse_price_value(rooms_3_match.group(1))

            one_room_match = re.search(r"1 өрөө байрны 1м2? дундаж үнэ:\s*([\d\s,]+)\s*(?:₮|төгрөг)", content)
            if one_room_match:
                district_info['one_room_avg'] = self._parse_price_value(one_room_match.group(1))

            four_room_match = re.search(r"4 өрөө байрны 1м2? дундаж үнэ:\s*([\d\s,]+)\s*(?:₮|төгрөг)", content)
            if four_room_match:
                district_info['four_room_avg'] = self._parse_price_value(four_room_match.group(1))

            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)

        if not districts_data:
            logger.warning("No valid district data extracted from vectorstore documents. Using fallback.")
            return self._get_fallback_data()

        return districts_data

    def _parse_price_value(self, price_str: str) -> float:
        # ... (logic remains the same)
        try:
            return float(price_str.replace(',', '').replace(' ', ''))
        except ValueError:
            return 0.0

    def _get_fallback_data(self) -> list:
        # ... (logic remains the same)
        logger.info("Using fallback static district data for report.")
        return [
            {'name': 'Сүхбаатар', 'overall_avg': 4500000, 'two_room_avg': 4600000, 'three_room_avg': 4400000},
            {'name': 'Хан-Уул', 'overall_avg': 4000000, 'two_room_avg': 4100000, 'three_room_avg': 3900000},
            {'name': 'Чингэлтэй', 'overall_avg': 3800000, 'two_room_avg': 3900000, 'three_room_avg': 3700000},
            {'name': 'Баянгол', 'overall_avg': 3500000, 'two_room_avg': 3600000, 'three_room_avg': 3400000},
            {'name': 'Баянзүрх', 'overall_avg': 3200000, 'two_room_avg': 3300000, 'three_room_avg': 3100000},
            {'name': 'Сонгинохайрхан', 'overall_avg': 2800000, 'two_room_avg': 2900000, 'three_room_avg': 2700000},
        ]

    async def _search_property_info(self, property_data_dict: dict) -> str:
        # ... (logic remains the same)
        if not self.search_tool:
            logger.info("Search tool not available for property info.")
            return "Нэмэлт мэдээллийн хайлт хийгдсэнгүй (хайлт тохируулагдаагүй)."

        try:
            district = property_data_dict.get("district", "")
            title = property_data_dict.get("title", "")
            query_parts = ["Улаанбаатар"]
            if district:
                query_parts.append(district + " дүүрэг")

            if title:
                clean_title = re.sub(r'\d+\s*өрөө|\bбайр\b|\bзарна\b', '', title, flags=re.IGNORECASE).strip()
                specific_location_parts = clean_title.split()[:3]
                if specific_location_parts:
                    query_parts.append(" ".join(specific_location_parts))

            query_parts.append("орчны мэдээлэл үнэ ханш")
            query = " ".join(query_parts)

            logger.info(f"Searching for property context with query: {query}")
            search_response = self.search_tool.invoke({"query": query})
            return await self._summarize_search_results(search_response)
        except Exception as e:
            logger.exception("Error during property information search")
            return "Үл хөдлөх хөрөнгийн талаарх нэмэлт мэдээлэл хайхад алдаа гарлаа."

    async def _search_market_info(self,
                                  query: str = "Улаанбаатар орон сууцны зах зээлийн ерөнхий мэдээлэл 2024 2025") -> str:
        # ... (logic remains the same)
        if not self.search_tool:
            logger.info("Search tool not available for market info.")
            return "Зах зээлийн нэмэлт мэдээллийн хайлт хийгдсэнгүй (хайлт тохируулагдаагүй)."
        try:
            logger.info(f"Searching for market context with query: {query}")
            search_response = self.search_tool.invoke({"query": query})
            return await self._summarize_search_results(search_response)
        except Exception as e:
            logger.exception("Error during market information search")
            return "Зах зээлийн талаарх нэмэлт мэдээлэл хайхад алдаа гарлаа."

    async def _summarize_search_results(self, search_response_data: any,
                                        prompt_guideline: str = "Extract key market trends, pricing information, and actionable insights.") -> str:
        try:
            # ... (search text extraction and cleaning remains the same)
            search_text = ""
            if isinstance(search_response_data, str):
                search_text = search_response_data
            elif isinstance(search_response_data, list):
                for result in search_response_data:
                    if isinstance(result, dict):
                        content = result.get('content', '') or result.get('snippet', '')
                        if content:
                            search_text += content + "\n\n"
            else:
                logger.warning(f"Unexpected search_response_data format: {type(search_response_data)}")
                search_text = str(search_response_data)

            if not search_text.strip():
                logger.warning("No valid search text found from search_response_data.")
                return "Хайлтын илэрцээс боловсруулах мэдээлэл олдсонгүй."

            cleaned_search_text = self._clean_search_content(search_text)

            if not cleaned_search_text.strip():
                logger.warning("Search text is empty after cleaning.")
                return "Хайлтын илэрц цэвэрлэгээний дараа хоосон боллоо."

            max_llm_context_length = 3000
            if len(cleaned_search_text) > max_llm_context_length:
                cleaned_search_text = cleaned_search_text[:max_llm_context_length]
                logger.info(f"Truncated cleaned search text to {max_llm_context_length} characters for LLM summary.")

            logger.info(f"Cleaned search text length for LLM summary: {len(cleaned_search_text)} chars.")
            logger.debug(f"Cleaned search text preview for LLM: {cleaned_search_text[:200]}...")

            # System prompt body in English, output instruction remains critical for Mongolian.
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a professional real estate market analyst. Analyze the provided search results text and provide a clear, concise summary.
{prompt_guideline}
Focus on:
- Key market trends and pricing information.
- Important factors affecting the market.
- Specific developments or changes if mentioned.
- Actionable insights for buyers and investors.
- Use specific numbers and data when available.
- The summary should be well-structured and informative for a report.

CRITICAL: Your final response must be written entirely in Mongolian language. Start your response directly in Mongolian."""),
                ("human",
                 "Search results text: {content}\n\nBased on the text above, provide a clear and concise summary in Mongolian.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            summary = await chain.ainvoke({"content": cleaned_search_text})
            return summary.strip() if summary else "Хайлтын илэрцийг хураангуйлахад мэдээлэл гарсангүй."

        except Exception as e:
            logger.exception("Error summarizing search results")
            return f"Хайлтын илэрцийг хураангуйлахад алдаа гарлаа: {str(e)}"

    async def _analyze_property(self, property_data_dict: dict, district_analysis_text: str) -> str:
        try:
            # System prompt body in English, output instruction remains critical for Mongolian.
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a professional real estate analyst. Based on the provided 'Property details' and 'District analysis text', generate a comprehensive analysis for a PDF report. The section titles in your response must be exactly as listed below (e.g., 1. **Үл Хөдлөх Хөрөнгийн Тойм (Property Overview)**).

Report Analysis Structure:
1.  **Үл Хөдлөх Хөрөнгийн Тойм (Property Overview)**: Summarize key features of the property, such as building specifics, advantages, room layout, and total area.
2.  **Үнийн Үнэлгээ (Price Assessment)**: Evaluate the property's price (using price/m² from 'Property details') by comparing it to the average district price for similar properties found in the 'District analysis text'. State clearly with justification whether the price is fair, high, or low. Express the difference numerically.
3.  **Байршлын Шинжилгээ (Location Analysis)**: Analyze the property's location, discussing advantages, disadvantages, nearby services, infrastructure, and future development prospects (using 'District analysis text').
4.  **Хөрөнгө Оруулалтын Боломж (Investment Potential)**: Assess the investment potential of this property. Evaluate potential for value appreciation, rental income, and short-term/long-term outlook.
5.  **Дүгнэлт ба Зөвлөмж (Conclusion and Recommendations)**: Based on the analyses above, provide specific, actionable recommendations for potential buyers or investors.

Instructions:
-   Each section should be clear, concise, and professionally written.
-   Cite specific information and figures from 'Property details' and 'District analysis text'.
-   Provide clear reasoning for all conclusions.
-   Offer realistic and actionable advice.

CRITICAL: Your final response must be written entirely in Mongolian language. Start your response directly in Mongolian, for example: "1. Үл Хөдлөх Хөрөнгийн Тойм: ..." """),
                ("human",
                 "Property details: {property_json_str}\nDistrict analysis text: {district_text}\n\nBased on the information above, write a detailed analysis for a PDF report in Mongolian.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            analysis = await chain.ainvoke({
                "property_json_str": json.dumps(property_data_dict, ensure_ascii=False, indent=2),
                "district_text": district_analysis_text
            })
            return analysis.strip() if analysis else "Үл хөдлөх хөрөнгийн дэлгэрэнгүй шинжилгээ хийхэд алдаа гарлаа."
        except Exception as e:
            logger.exception("Error in _analyze_property for report")
            return f"Үл хөдлөх хөрөнгийн дэлгэрэнгүй шинжилгээг боловсруулахад алдаа: {str(e)}"

    async def _analyze_market_for_report(self, districts_data_list: list) -> str:
        try:
            # System prompt body in English, output instruction remains critical for Mongolian.
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a real estate market analyst. Based on the provided structured 'List of district data', generate a comprehensive market analysis summary for a PDF report. The section titles in your response must be exactly as listed below.

Report Market Analysis Structure:
1.  **Зах Зээлийн Ерөнхий Тойм (Market Overview)**: Summarize the current state of Ulaanbaatar's district apartment market based on the 'List of district data'. Mention general price levels and key trends.
2.  **Үнийн Харьцуулалт ба Ялгаа (Price Comparison and Differentials)**: Identify the districts with the highest and lowest average prices and explain the price differences using data from the 'List of district data'. If possible, speculate on factors contributing to these price differences.
3.  **Хөрөнгө Оруулалтын Боломжит Бүсүүд (Potential Investment Zones)**: Based on the 'List of district data', categorize districts that might be more attractive for investors with different budgets (high-end, mid-range, affordable).
4.  **Худалдан Авагчдад Өгөх Стратеги (Buyer Strategies)**: Advise on which districts might offer advantages for various types of buyers (first-time buyers, families looking to upgrade, investors) according to their needs.
5.  **Зах Зээлийн Ирээдүйн Төлөв (Market Outlook - if inferable)**: Based on the current data, offer a cautious outlook on the near-term future of the market (if possible).

Instructions:
-   Use specific figures and average prices from the 'List of district data'.
-   Conclusions and recommendations should be realistic and data-driven.
-   Maintain a professional tone suitable for a report.

CRITICAL: Your final response must be written entirely in Mongolian language. Start your response directly in Mongolian, for example: "1. Зах Зээлийн Ерөнхий Тойм: ..." """),
                ("human",
                 "List of district data: {districts_json_str}\n\nBased on the district data above, write a detailed market analysis for a PDF report in Mongolian.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            analysis = await chain.ainvoke({
                "districts_json_str": json.dumps(districts_data_list, ensure_ascii=False, indent=2)
            })
            return analysis.strip() if analysis else "Дүүргүүдийн мэдээллийг нэгтгэн дүгнэхэд алдаа гарлаа."
        except Exception as e:
            logger.exception("Error in _analyze_market_for_report")
            return f"Зах зээлийн шинжилгээг боловсруулахад алдаа: {str(e)}"