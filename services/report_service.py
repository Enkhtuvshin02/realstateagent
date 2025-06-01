# services/simple_report_service.py - Хялбаршуулсан тайлангийн үйлчилгээ уншихад хялбар PDF-тэй
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
        """Үнийн задлалтыг сайжруулсан дүүргийн өгөгдлийг авах - уншихад хялбар байхыг чухалчилж байна"""
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

                # Дүүргийн нэр олох
                if 'Дүүрэг:' in line:
                    district_name = line.replace('Дүүрэг:', '').strip()
                    district_info['name'] = district_name
                    logger.debug(f"Found district: {district_name}")

                # Энгийн задлалтаар үнэ олох
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

            # Нэр болон үнэ байвал дүүргийг нэмэх
            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)
                logger.info(f"✅ Added: {district_info['name']} - {district_info['overall_avg']:,.0f} ₮/m²")
            else:
                logger.warning(f"❌ Incomplete data for: {district_info.get('name', 'Unknown')}")

        logger.info(f"Extracted {len(districts_data)} valid districts")

        # Задлал амжилтгүй бол нөөц өгөгдөл ашиглах
        if not districts_data:
            logger.warning("No valid data extracted, using fallback")
            return self._get_simple_fallback_data()

        return districts_data

    def _extract_price_simple(self, line: str) -> float:
        """Түгээмэл форматуудыг боловсруулдаг энгийн үнийн задлалт"""
        try:
            # Хоёр цэгийн дараахыг авах
            if ':' in line:
                price_part = line.split(':', 1)[1].strip()
            else:
                price_part = line

            logger.debug(f"Extracting price from: '{price_part}'")

            # "мэдээлэл байхгүй" тохиолдлуудыг шийдэх
            if any(word in price_part.lower() for word in ['мэдээлэл байхгүй', 'байхгүй', 'n/a']):
                return 0

            # Валютын үг болон тэмдэгтүүдийг арилгах
            clean_text = price_part.replace('төгрөг', '').replace('₮', '').strip()

            # Сая форматыг боловсруулах
            if 'сая' in clean_text.lower():
                numbers = re.findall(r'(\d+(?:\.\d+)?)', clean_text)
                if numbers:
                    return float(numbers[0]) * 1_000_000

            # Зайгаар тусгаарлагдсан тоонуудыг боловсруулах (жишээ нь: "4 000 323")
            # Зайг арилгаж тоо задлах
            number_only = re.sub(r'[^\d]', '', clean_text)
            if number_only:
                return float(number_only)

            # Шууд тоо задлах
            numbers = re.findall(r'(\d+)', clean_text)
            if numbers:
                return float(numbers[0])

            logger.warning(f"Could not parse price from: '{line}'")
            return 0

        except Exception as e:
            logger.error(f"Error parsing price from '{line}': {e}")
            return 0

    def _get_simple_fallback_data(self) -> list:
        """Бодит үнэтэй энгийн нөөц өгөгдөл"""
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
        """Энгийн, уншихад хялбар үл хөдлөх хөрөнгийн тайлан үүсгэх"""
        logger.info("📄 Тайлан үүсгэж байна")

        try:
            # Шинэлэг эсэхийг шалгах
            analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
            time_diff = datetime.now() - analysis_time

            if time_diff.total_seconds() > 600:  # 10 минут
                return {
                    "message": "Орон сууцны шинжилгээ хуучирсан байна. Дахин шинжилгээ хийнэ үү.",
                    "success": False
                }

            # Энгийн хайлт
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

            # Энгийн шинжилгээ үүсгэх
            detailed_analysis = await self._simple_property_analysis(
                analysis_data["property_details"],
                analysis_data["district_analysis"]
            )

            # PDF үүсгэх
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
        """Энгийн, уншихад хялбар дүүргийн тайлан үүсгэх"""
        logger.info("📊 Дүүргийн тайлан үүсгэж байна")

        try:
            # Шинэ өгөгдөл авах
            await self.district_analyzer.ensure_fresh_data()

            # Энгийн задлалтаар өгөгдөл авах
            districts_data = self._extract_districts_data_simple()

            if not districts_data:
                return {
                    "message": "Дүүргийн мэдээлэл олдсонгүй.",
                    "success": False
                }

            # Энгийн хайлт
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

            # Энгийн зах зээлийн шинжилгээ үүсгэх
            market_trends = await self._simple_market_analysis(districts_data)

            # PDF үүсгэх
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
        """Дүүргийн тайланг ашиглан иж бүрэн тайлан үүсгэх"""
        logger.info("📈 Иж бүрэн тайлан үүсгэж байна")
        # Иж бүрэн шинжилгээнд дүүргийн тайланг ашиглах
        return await self.generate_district_report()

    async def _simple_search_summary(self, search_response) -> str:
        """Энгийн хайлтын үр дүнгийн боловсруулалт"""
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

            # Хайлтын үр дүнг нэгтгэх энгийн prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a professional real estate market analyst. Your task is to analyze search results about real estate markets and provide a clear, concise summary.

Guidelines for analysis:
- Extract key market trends and pricing information
- Identify important factors affecting the market
- Note any specific developments or changes
- Focus on actionable insights for buyers and investors
- Keep the summary concise but valuable
- Use specific numbers and data when available
- Avoid speculation, stick to facts from the search results

IMPORTANT: Write your final response entirely in Mongolian language. Analyze the information thoroughly but present it in clear, readable Mongolian."""),
                ("human", """Search results about real estate market: {content}

Provide a clear, concise summary of the key market information in Mongolian.""")
            ])

            chain = prompt | self.llm | StrOutputParser()
            summary = await chain.ainvoke({"content": search_text[:2000]})
            return summary or ""

        except Exception as e:
            logger.error(f"Search summary error: {e}")
            return ""

    async def _simple_property_analysis(self, property_details: dict, district_analysis: str) -> str:
        """Энгийн үл хөдлөх хөрөнгийн шинжилгээ"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate analyst specializing in property evaluation. Your task is to provide a clear, valuable analysis of a specific property.

Analysis structure:
1. **Property Overview** - Key characteristics and features
2. **Price Assessment** - Is the price reasonable compared to market?
3. **Location Analysis** - Strengths and weaknesses of the location
4. **Investment Potential** - Short-term and long-term outlook
5. **Recommendations** - Clear advice for potential buyers

For each section:
- Use specific information from the property details
- Reference district market data when relevant
- Provide clear reasoning for your conclusions
- Be specific and actionable
- Keep each section concise (2-3 sentences maximum)
- Include relevant numbers and comparisons

IMPORTANT: Write your final response entirely in Mongolian language. Think through the analysis thoroughly but present it in clear, readable Mongolian."""),
            ("human", """Property details: {property}
District analysis: {district}

Provide a comprehensive property analysis with clear recommendations in Mongolian.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "property": json.dumps(property_details, ensure_ascii=False),
            "district": district_analysis
        })
        return analysis

    async def _simple_market_analysis(self, districts_data: list) -> str:
        """Энгийн зах зээлийн шинжилгээ"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate market analyst. Your task is to analyze district-level real estate data and provide valuable market insights.

Analysis structure:
1. **Market Overview** - Current state of the market across districts
2. **Price Ranges** - Highest to lowest priced districts with specific numbers
3. **Value Opportunities** - Which districts offer the best value?
4. **Investment Zones** - Best areas for different types of investors
5. **Market Trends** - What patterns do you see in the data?
6. **Strategic Recommendations** - Actionable advice for buyers and investors

For each section:
- Use specific data and numbers from the district information
- Calculate price differences and percentages
- Identify clear patterns and trends
- Provide actionable insights
- Keep each section concise but valuable
- Include specific district names and prices

IMPORTANT: Write your final response entirely in Mongolian language. Analyze the data thoroughly but present insights in clear, readable Mongolian."""),
            ("human", """District data: {data}

Provide comprehensive market analysis with specific insights and recommendations in Mongolian.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "data": json.dumps(districts_data, ensure_ascii=False)
        })
        return analysis