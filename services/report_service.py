# services/report_service.py - Хялбаршуулсан тайлангийн үйлчилгээ
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

    async def generate_property_report(self, analysis_data: dict) -> dict:
        """Орон сууцны тайлан үүсгэх"""
        logger.info("Орон сууцны тайлан үүсгэж байна")

        try:
            # Шинэлэг эсэхийг шалгах (10 минут)
            if 'timestamp' in analysis_data:
                analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                time_diff = datetime.now() - analysis_time
                if time_diff.total_seconds() > 600:
                    return {
                        "message": "Шинжилгээ хуучирсан байна. Дахин шинжилгээ хийнэ үү.",
                        "success": False
                    }

            # Интернэт хайлт хийх
            search_results = await self._search_property_info(analysis_data)

            # Дэлгэрэнгүй шинжилгээ үүсгэх
            detailed_analysis = await self._analyze_property(analysis_data)

            # PDF үүсгэх
            pdf_path = self.pdf_generator.generate_property_analysis_report(
                property_data=analysis_data["property_data"],
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
            logger.error(f"Орон сууцны тайлан үүсгэхэд алдаа: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа: {str(e)}",
                "success": False
            }

    async def generate_district_report(self) -> dict:
        """Дүүргийн тайлан үүсгэх"""
        logger.info("Дүүргийн тайлан үүсгэж байна")

        try:
            # Дүүргийн өгөгдөл авах
            districts_data = self._extract_districts_data()

            if not districts_data:
                return {
                    "message": "Дүүргийн мэдээлэл олдсонгүй.",
                    "success": False
                }

            # Зах зээлийн хайлт
            search_results = await self._search_market_info()

            # Зах зээлийн шинжилгээ
            market_analysis = await self._analyze_market(districts_data)

            # PDF үүсгэх
            pdf_path = self.pdf_generator.generate_district_summary_report(
                districts_data=districts_data,
                market_trends=market_analysis,
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
            logger.error(f"Дүүргийн тайлан үүсгэхэд алдаа: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа: {str(e)}",
                "success": False
            }

    async def generate_comprehensive_market_report(self) -> dict:
        """Иж бүрэн зах зээлийн тайлан - дүүргийн тайлантай ижил"""
        return await self.generate_district_report()

    def _extract_districts_data(self) -> list:
        """Дүүргийн өгөгдлийг авах"""
        if not self.district_analyzer.vectorstore:
            return self._get_fallback_data()

        available_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
        districts_data = []

        for doc in available_docs:
            content = doc.page_content.strip()
            district_info = {}

            # Дүүргийн нэр олох
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if 'Дүүрэг:' in line:
                    district_info['name'] = line.replace('Дүүрэг:', '').strip()
                elif 'Нийт байрны 1м' in line and 'дундаж үнэ:' in line:
                    price = self._extract_price(line)
                    if price > 0:
                        district_info['overall_avg'] = price
                elif '2 өрөө байрны 1м' in line and 'дундаж үнэ:' in line:
                    price = self._extract_price(line)
                    if price > 0:
                        district_info['two_room_avg'] = price
                elif '3 өрөө байрны 1м' in line and 'дундаж үнэ:' in line:
                    price = self._extract_price(line)
                    if price > 0:
                        district_info['three_room_avg'] = price

            # Бүрэн мэдээлэлтэй бол нэмэх
            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)

        return districts_data if districts_data else self._get_fallback_data()

    def _extract_price(self, line: str) -> float:
        """Мөрөөс үнэ олох"""
        try:
            if ':' in line:
                price_part = line.split(':', 1)[1].strip()
            else:
                price_part = line

            # "мэдээлэл байхгүй" шалгах
            if any(word in price_part.lower() for word in ['мэдээлэл байхгүй', 'байхгүй']):
                return 0

            # Валют болон үг арилгах
            clean_text = price_part.replace('төгрөг', '').replace('₮', '').strip()

            # Сая форматыг боловсруулах
            if 'сая' in clean_text.lower():
                numbers = re.findall(r'(\d+(?:\.\d+)?)', clean_text)
                if numbers:
                    return float(numbers[0]) * 1_000_000

            # Зайг арилгаж тоо олох
            number_only = re.sub(r'[^\d]', '', clean_text)
            if number_only:
                return float(number_only)

            return 0

        except Exception as e:
            logger.error(f"Үнэ олохад алдаа '{line}': {e}")
            return 0

    def _get_fallback_data(self) -> list:
        """Нөөц өгөгдөл"""
        return [
            {'name': 'Сүхбаатар', 'overall_avg': 4500000, 'two_room_avg': 4600000, 'three_room_avg': 4400000},
            {'name': 'Хан-Уул', 'overall_avg': 4000000, 'two_room_avg': 4100000, 'three_room_avg': 3900000},
            {'name': 'Чингэлтэй', 'overall_avg': 3800000, 'two_room_avg': 3900000, 'three_room_avg': 3700000},
            {'name': 'Баянгол', 'overall_avg': 3500000, 'two_room_avg': 3600000, 'three_room_avg': 3400000},
            {'name': 'Баянзүрх', 'overall_avg': 3200000, 'two_room_avg': 3300000, 'three_room_avg': 3100000},
            {'name': 'Сонгинохайрхан', 'overall_avg': 2800000, 'two_room_avg': 2900000, 'three_room_avg': 2700000},
        ]

    async def _search_property_info(self, analysis_data: dict) -> str:
        """Орон сууцны мэдээлэл хайх"""
        if not self.search_tool:
            return ""

        try:
            district = analysis_data["property_data"].get("district", "")
            query = f"Улаанбаатар {district} орон сууцны үнэ 2024"
            search_response = self.search_tool.invoke({"query": query})
            return await self._summarize_search_results(search_response)
        except Exception as e:
            logger.error(f"Орон сууцны хайлт алдаа: {e}")
            return ""

    async def _search_market_info(self) -> str:
        """Зах зээлийн мэдээлэл хайх"""
        if not self.search_tool:
            return ""

        try:
            query = "Улаанбаатар орон сууцны зах зээл 2024"
            search_response = self.search_tool.invoke({"query": query})
            return await self._summarize_search_results(search_response)
        except Exception as e:
            logger.error(f"Зах зээлийн хайлт алдаа: {e}")
            return ""

    async def _summarize_search_results(self, search_response) -> str:
        """Хайлтын үр дүнг нэгтгэх"""
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

            # Хайлтын үр дүнг нэгтгэх
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a professional real estate market analyst. Analyze search results and provide a clear, concise summary.

Guidelines:
- Extract key market trends and pricing information
- Identify important factors affecting the market
- Note any specific developments or changes
- Focus on actionable insights for buyers and investors
- Keep the summary concise but valuable
- Use specific numbers and data when available

IMPORTANT: Write your final response entirely in Mongolian language."""),
                ("human", "Search results: {content}\n\nProvide a clear summary in Mongolian.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            summary = await chain.ainvoke({"content": search_text[:2000]})
            return summary or ""

        except Exception as e:
            logger.error(f"Хайлтын үр дүн нэгтгэхэд алдаа: {e}")
            return ""

    async def _analyze_property(self, analysis_data: dict) -> str:
        """Орон сууцны дэлгэрэнгүй шинжилгээ"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate analyst. Provide comprehensive property analysis.

Analysis structure:
1. **Property Overview** - Key characteristics and features
2. **Price Assessment** - Is the price reasonable compared to market?
3. **Location Analysis** - Strengths and weaknesses of the location
4. **Investment Potential** - Short-term and long-term outlook
5. **Recommendations** - Clear advice for potential buyers

For each section:
- Use specific information from the property details
- Reference district market data when relevant
- Provide clear reasoning for conclusions
- Be specific and actionable
- Keep each section concise (2-3 sentences maximum)

IMPORTANT: Write your final response entirely in Mongolian language."""),
            ("human", "Property details: {property}\nDistrict analysis: {district}\n\nProvide comprehensive analysis in Mongolian.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "property": json.dumps(analysis_data["property_data"], ensure_ascii=False),
            "district": analysis_data["district_analysis"]
        })
        return analysis

    async def _analyze_market(self, districts_data: list) -> str:
        """Зах зээлийн шинжилгээ"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate market analyst. Analyze district-level data and provide market insights.

Analysis structure:
1. **Market Overview** - Current state across districts
2. **Price Ranges** - Highest to lowest priced districts with numbers
3. **Value Opportunities** - Which districts offer the best value?
4. **Investment Zones** - Best areas for different types of investors
5. **Market Trends** - What patterns do you see?
6. **Strategic Recommendations** - Actionable advice for buyers

Use specific data and numbers from the district information.
IMPORTANT: Write your final response entirely in Mongolian language."""),
            ("human", "District data: {data}\n\nProvide comprehensive market analysis in Mongolian.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "data": json.dumps(districts_data, ensure_ascii=False)
        })
        return analysis