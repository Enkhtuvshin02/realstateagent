
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

        content = re.sub(r'!\[.*?\]\([^)]+\)', '', content)
        content = re.sub(r'<img[^>]*>', '', content)
        content = re.sub(r'https?://[^\s<>"\']*\.(jpg|jpeg|png|gif|webp|svg)(\?[^\s]*)?', '', content, flags=re.IGNORECASE)
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
            if 'timestamp' in analysis_data:
                analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
                time_diff = datetime.now() - analysis_time
                if time_diff.total_seconds() > 600:
                    return {
                        "message": "Analysis is outdated. Please perform a new analysis.",
                        "success": False
                    }

            search_results = await self._search_property_info(analysis_data)
            detailed_analysis = await self._analyze_property(analysis_data)
            pdf_path = self.pdf_generator.generate_property_analysis_report(
                property_data=analysis_data["property_data"],
                district_analysis=analysis_data["district_analysis"],
                comparison_result=detailed_analysis,
                search_results=search_results
            )
            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"
            return {
                "message": f"✅ Property PDF report is ready!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error generating property report: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа: {str(e)}",
                "success": False
            }

    async def generate_district_report(self) -> dict:
        logger.info("Generating district report")

        try:
            districts_data = self._extract_districts_data()
            if not districts_data:
                return {
                    "message": "District information not found.",
                    "success": False
                }

            search_results = await self._search_market_info()
            market_analysis = await self._analyze_market(districts_data)
            pdf_path = self.pdf_generator.generate_district_summary_report(
                districts_data=districts_data,
                market_trends=market_analysis,
                search_results=search_results
            )
            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"
            return {
                "message": f"✅ District comparison PDF report is ready!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error generating district report: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа: {str(e)}",
                "success": False
            }

    async def generate_comprehensive_market_report(self) -> dict:
        return await self.generate_district_report()

    def _extract_districts_data(self) -> list:
        if not self.district_analyzer.vectorstore:
            return self._get_fallback_data()

        available_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
        districts_data = []

        for doc in available_docs:
            content = doc.page_content.strip()
            district_info = {}

            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if 'Дүүрэг:' in line:
                    district_info['name'] = line.replace('Дүүрэг:', '').strip()
                elif 'Нийт байрны 1мк' in line and 'дундаж үнэ:' in line:
                    price = self._extract_price(line)
                    if price > 0:
                        district_info['overall_avg'] = price
                elif '2 өрөө байрны 1мк' in line and 'дундаж үнэ:' in line:
                    price = self._extract_price(line)
                    if price > 0:
                        district_info['two_room_avg'] = price
                elif '3 өрөө байрны 1мк' in line and 'дундаж үнэ:' in line:
                    price = self._extract_price(line)
                    if price > 0:
                        district_info['three_room_avg'] = price

            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)

        return districts_data if districts_data else self._get_fallback_data()

    def _extract_price(self, line: str) -> float:
        try:
            if ':' in line:
                price_part = line.split(':', 1)[1].strip()
            else:
                price_part = line

            if any(word in price_part.lower() for word in ['мэдээлэл байхгүй', 'байхгүй']):
                return 0

            clean_text = price_part.replace('төгрөг', '').replace('₮', '').strip()

            if 'сая' in clean_text.lower():
                numbers = re.findall(r'(\d+(?:\.\d+)?)', clean_text)
                if numbers:
                    return float(numbers[0]) * 1_000_000

            number_only = re.sub(r'[^\d]', '', clean_text)
            if number_only:
                return float(number_only)

            return 0

        except Exception as e:
            logger.error(f"Үнэ олоход алдаа '{line}': {e}")
            return 0

    def _get_fallback_data(self) -> list:
        return [
            {'name': 'Сүхбаатар', 'overall_avg': 4500000, 'two_room_avg': 4600000, 'three_room_avg': 4400000},
            {'name': 'Хан-Уул', 'overall_avg': 4000000, 'two_room_avg': 4100000, 'three_room_avg': 3900000},
            {'name': 'Чингэлтэй', 'overall_avg': 3800000, 'two_room_avg': 3900000, 'three_room_avg': 3700000},
            {'name': 'Баянгол', 'overall_avg': 3500000, 'two_room_avg': 3600000, 'three_room_avg': 3400000},
            {'name': 'Баянзүрх', 'overall_avg': 3200000, 'two_room_avg': 3300000, 'three_room_avg': 3100000},
            {'name': 'Сонгинохайрхан', 'overall_avg': 2800000, 'two_room_avg': 2900000, 'three_room_avg': 2700000},
        ]

    async def _search_property_info(self, analysis_data: dict) -> str:
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
        try:
            search_text = ""
            if isinstance(search_response, list):
                for result in search_response:
                    if isinstance(result, dict):
                        content = result.get('content', '') or result.get('snippet', '')
                        if content:
                            cleaned_content = self._clean_search_content(content)
                            if cleaned_content:
                                search_text += cleaned_content + " "

            if not search_text:
                logger.warning("No valid search text found after cleaning")
                return ""

            search_text = self._clean_search_content(search_text)

            if not search_text.strip():
                logger.warning("Search text is empty after cleaning")
                return ""

            max_length = 1500
            if len(search_text) > max_length:
                search_text = search_text[:max_length] + "..."
                logger.info(f"Truncated search text to {max_length} characters")

            logger.info(f"Cleaned search text length: {len(search_text)} characters")
            logger.debug(f"Cleaned search text preview: {search_text[:200]}...")

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
            summary = await chain.ainvoke({"content": search_text})
            return summary or ""

        except Exception as e:
            logger.error(f"Error summarizing search results: {e}")
            logger.error(f"Error details: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response content: {e.response}")
            return ""

    async def _analyze_property(self, analysis_data: dict) -> str:
        try:
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
                ("human",
                 "Property details: {property}\nDistrict analysis: {district}\n\nProvide comprehensive analysis in Mongolian.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            analysis = await chain.ainvoke({
                "property": json.dumps(analysis_data["property_data"], ensure_ascii=False),
                "district": analysis_data["district_analysis"]
            })
            return analysis
        except Exception as e:
            logger.error(f"Property analysis error: {e}")
            return "Error performing detailed property analysis."

    async def _analyze_market(self, districts_data: list) -> str:
        try:
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
        except Exception as e:
            logger.error(f"Market analysis error: {e}")
            return "Error performing market analysis."