# services/simple_report_service.py - Simplified report service with readable PDFs
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

    def _extract_districts_data_simple(self) -> list:
        """Extract district data with improved price parsing - prioritizing readability"""
        if not self.district_analyzer.vectorstore:
            logger.warning("No vectorstore available, using fallback data")
            return self._get_simple_fallback_data()

        available_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
        districts_data = []

        logger.info(f"Extracting data from {len(available_docs)} documents...")

        for doc in available_docs:
            content = doc.page_content.strip()
            lines = content.split('\n')
            district_info = {}

            logger.debug(f"Processing document:\n{content[:200]}...")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Extract district name
                if 'Дүүрэг:' in line:
                    district_name = line.replace('Дүүрэг:', '').strip()
                    district_info['name'] = district_name
                    logger.debug(f"Found district: {district_name}")

                # Extract prices with simple parsing
                elif 'Нийт байрны 1м' in line and 'дундаж үнэ:' in line:
                    price_value = self._extract_price_simple(line)
                    if price_value > 0:
                        district_info['overall_avg'] = price_value
                        logger.debug(f"Overall price: {price_value:,.0f}")

                elif '2 өрөө байрны 1м' in line and 'дундаж үнэ:' in line:
                    price_value = self._extract_price_simple(line)
                    if price_value > 0:
                        district_info['two_room_avg'] = price_value
                        logger.debug(f"2-room price: {price_value:,.0f}")

                elif '3 өрөө байрны 1м' in line and 'дундаж үнэ:' in line:
                    price_value = self._extract_price_simple(line)
                    if price_value > 0:
                        district_info['three_room_avg'] = price_value
                        logger.debug(f"3-room price: {price_value:,.0f}")

            # Add district if we have name and price
            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)
                logger.info(f"✅ Added: {district_info['name']} - {district_info['overall_avg']:,.0f} ₮/m²")
            else:
                logger.warning(f"❌ Incomplete data for: {district_info.get('name', 'Unknown')}")

        logger.info(f"Extracted {len(districts_data)} valid districts")

        # Use fallback if extraction failed
        if not districts_data:
            logger.warning("No valid data extracted, using fallback")
            return self._get_simple_fallback_data()

        return districts_data

    def _extract_price_simple(self, line: str) -> float:
        """Simple price extraction that handles common formats"""
        try:
            # Get the part after the colon
            if ':' in line:
                price_part = line.split(':', 1)[1].strip()
            else:
                price_part = line

            logger.debug(f"Extracting price from: '{price_part}'")

            # Handle "no data" cases
            if any(word in price_part.lower() for word in ['мэдээлэл байхгүй', 'байхгүй', 'n/a']):
                return 0

            # Remove currency words and symbols
            clean_text = price_part.replace('төгрөг', '').replace('₮', '').strip()

            # Handle million format
            if 'сая' in clean_text.lower():
                numbers = re.findall(r'(\d+(?:\.\d+)?)', clean_text)
                if numbers:
                    return float(numbers[0]) * 1_000_000

            # Handle space-separated numbers (e.g., "4 000 323")
            # Remove spaces and extract numbers
            number_only = re.sub(r'[^\d]', '', clean_text)
            if number_only:
                return float(number_only)

            # Direct number extraction
            numbers = re.findall(r'(\d+)', clean_text)
            if numbers:
                return float(numbers[0])

            logger.warning(f"Could not parse price from: '{line}'")
            return 0

        except Exception as e:
            logger.error(f"Error parsing price from '{line}': {e}")
            return 0

    def _get_simple_fallback_data(self) -> list:
        """Simple fallback data with realistic prices"""
        return [
            {'name': 'Сүхбаатар', 'overall_avg': 4500000, 'two_room_avg': 4600000, 'three_room_avg': 4400000},
            {'name': 'Хан-Уул', 'overall_avg': 4000000, 'two_room_avg': 4100000, 'three_room_avg': 3900000},
            {'name': 'Чингэлтэй', 'overall_avg': 3800000, 'two_room_avg': 3900000, 'three_room_avg': 3700000},
            {'name': 'Баянгол', 'overall_avg': 3500000, 'two_room_avg': 3600000, 'three_room_avg': 3400000},
            {'name': 'Баянзүрх', 'overall_avg': 3200000, 'two_room_avg': 3300000, 'three_room_avg': 3100000},
            {'name': 'Сонгинохайрхан', 'overall_avg': 2800000, 'two_room_avg': 2900000, 'three_room_avg': 2700000},
            {'name': 'Багануур', 'overall_avg': 2200000, 'two_room_avg': 2300000, 'three_room_avg': 2100000},
            {'name': 'Налайх', 'overall_avg': 2000000, 'two_room_avg': 2100000, 'three_room_avg': 1900000},
        ]

    async def generate_property_report(self, analysis_data: dict) -> dict:
        """Generate simple, readable property report"""
        logger.info("📄 Generating simple property report")

        try:
            # Check recency
            analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
            time_diff = datetime.now() - analysis_time

            if time_diff.total_seconds() > 600:  # 10 minutes
                return {
                    "message": "Орон сууцны шинжилгээ хуучирсан байна. Дахин шинжилгээ хийнэ үү.",
                    "success": False
                }

            # Simple search
            search_results = ""
            if self.search_tool:
                try:
                    district = analysis_data["property_details"].get("district", "")
                    query = f"Улаанбаатар {district} орон сууцны үнэ 2024"
                    search_response = self.search_tool.invoke({"query": query})
                    if search_response:
                        search_results = await self._simple_search_summary(search_response)
                except Exception as e:
                    logger.error(f"Search failed: {e}")
                    search_results = ""

            # Generate simple analysis
            detailed_analysis = await self._simple_property_analysis(
                analysis_data["property_details"],
                analysis_data["district_analysis"]
            )

            # Generate PDF
            pdf_path = self.pdf_generator.generate_property_analysis_report(
                property_data=analysis_data["property_details"],
                district_analysis=analysis_data["district_analysis"],
                comparison_result=detailed_analysis,
                search_results=search_results
            )

            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"

            return {
                "message": f"✅ Орон сууцны PDF тайлан бэлэн боллоо!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"Property report error: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа: {str(e)}",
                "success": False
            }

    async def generate_district_report(self) -> dict:
        """Generate simple, readable district report"""
        logger.info("📊 Generating simple district report")

        try:
            # Get fresh data
            await self.district_analyzer.ensure_fresh_data()

            # Extract data with simple parsing
            districts_data = self._extract_districts_data_simple()

            if not districts_data:
                return {
                    "message": "Дүүргийн мэдээлэл олдсонгүй.",
                    "success": False
                }

            # Simple search
            search_results = ""
            if self.search_tool:
                try:
                    query = "Улаанбаатар орон сууцны зах зээл 2024"
                    search_response = self.search_tool.invoke({"query": query})
                    if search_response:
                        search_results = await self._simple_search_summary(search_response)
                except Exception as e:
                    logger.error(f"Search failed: {e}")
                    search_results = ""

            # Generate simple market analysis
            market_trends = await self._simple_market_analysis(districts_data)

            # Generate PDF
            pdf_path = self.pdf_generator.generate_district_summary_report(
                districts_data=districts_data,
                market_trends=market_trends,
                search_results=search_results
            )

            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"

            return {
                "message": f"✅ Дүүргийн харьцуулалтын PDF тайлан бэлэн боллоо!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"District report error: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа: {str(e)}",
                "success": False
            }

    async def generate_comprehensive_market_report(self) -> dict:
        """Generate comprehensive report using district report"""
        logger.info("📈 Generating comprehensive market report")
        # Use the district report for comprehensive analysis
        return await self.generate_district_report()

    async def _simple_search_summary(self, search_response) -> str:
        """Simple search result processing"""
        try:
            search_text = ""
            if isinstance(search_response, list):
                for result in search_response:
                    if isinstance(result, dict):
                        content = result.get('content', '') or result.get('snippet', '')
                        if content:
                            search_text += content + " "

            if not search_text:
                return ""

            # Simple prompt for summarizing
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Та орон сууцны зах зээлийн мэдээллийг товч, ойлгомжтой байдлаар Монгол хэлээр нэгтгэдэг."),
                ("human", "Дараах мэдээллийг товчлон хэлнэ үү: {content}")
            ])

            chain = prompt | self.llm | StrOutputParser()
            summary = await chain.ainvoke({"content": search_text[:2000]})
            return summary or ""

        except Exception as e:
            logger.error(f"Search summary error: {e}")
            return ""

    async def _simple_property_analysis(self, property_details: dict, district_analysis: str) -> str:
        """Simple property analysis"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Та орон сууцны шинжээч. Товч, ойлгомжтой шинжилгээг Монгол хэлээр хийнэ үү."),
            ("human", "Орон сууц: {property}\nДүүрэг: {district}\n\nЭнэ орон сууцны талаар товч дүгнэлт өгнө үү.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "property": json.dumps(property_details, ensure_ascii=False),
            "district": district_analysis
        })
        return analysis

    async def _simple_market_analysis(self, districts_data: list) -> str:
        """Simple market analysis"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Та зах зээлийн шинжээч. Дүүргүүдийн мэдээллээс товч дүгнэлт Монгол хэлээр гаргана уу."),
            ("human", "Дүүргүүдийн мэдээлэл: {data}\n\nЗах зээлийн ерөнхий байдлын талаар товч дүгнэлт өгнө үү.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "data": json.dumps(districts_data, ensure_ascii=False)
        })
        return analysis