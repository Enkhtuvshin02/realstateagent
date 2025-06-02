# services/chat_service.py - Хялбаршуулсан чат үйлчилгээ
import logging
import re
import json
from datetime import datetime
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.report_service import ReportService
from agents.chain_of_thought_agent import ChainOfThoughtAgent

logger = logging.getLogger(__name__)

# Тогтмол утгууд - хялбаршуулсан
REPORT_KEYWORDS = ['тиймээ', 'тийм', 'yes', 'тайлан']
DISTRICT_NAMES = ["хан-уул", "баянгол", "сүхбаатар", "чингэлтэй", "баянзүрх", "сонгинохайрхан"]


class ChatService:
    """Үл хөдлөх хөрөнгийн чат үйлчилгээ - хялбаршуулсан хувилбар"""

    def __init__(self, llm, search_tool, property_retriever, district_analyzer, pdf_generator):
        self.llm = llm
        self.search_tool = search_tool
        self.property_retriever = property_retriever
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator

        # Дэд үйлчилгээнүүд
        self.report_service = ReportService(llm, district_analyzer, pdf_generator, search_tool)
        self.cot_agent = ChainOfThoughtAgent(llm)

        # Сүүлийн шинжилгээнүүд хадгалах
        self.last_property = None
        self.last_district = None

    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """Мессеж боловсруулах - гол функц"""
        logger.info(f"Мессеж боловсруулж байна: {user_message[:50]}...")

        try:
            # Тайлан хүсэх эсэхийг шалгах
            if self._wants_report(user_message):
                return await self._generate_report()

            # Мессежийн төрлийг тодорхойлох
            message_type = self._classify_message(user_message)

            # CoT хэрэглэх эсэхийг шийдэх
            use_cot = len(user_message) > 30 or message_type in ['property', 'district']

            # Мессежийн төрлөөр боловсруулах
            if message_type == 'property':
                return await self._handle_property(user_message, use_cot)
            elif message_type == 'district':
                return await self._handle_district(user_message, use_cot)
            elif message_type == 'market':
                return await self._handle_market(user_message, use_cot)
            else:
                return await self._handle_general(user_message)

        except Exception as e:
            logger.error(f"Мессеж боловсруулахад алдаа: {e}")
            return {"response": "Алдаа гарлаа. Дахин оролдоно уу.", "offer_report": False}

    def _classify_message(self, message: str) -> str:
        """Мессежийн төрлийг ангилах"""
        message_lower = message.lower()

        # URL шалгах
        if re.search(r'https?://\S+', message):
            return 'property'

        # Дүүргийн нэр шалгах
        if any(district in message_lower for district in DISTRICT_NAMES):
            return 'district'

        # Зах зээлийн түлхүүр үг шалгах
        market_keywords = ['зах зээл', 'үнийн чиглэл', 'market', 'тренд', 'статистик']
        if any(keyword in message_lower for keyword in market_keywords):
            return 'market'

        return 'general'

    def _wants_report(self, message: str) -> bool:
        """Тайлан хүсэж байгаа эсэхийг шалгах"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in REPORT_KEYWORDS) and len(message) < 50

    async def _handle_property(self, message: str, use_cot: bool) -> Dict[str, Any]:
        """Орон сууцны URL боловсруулах"""
        url_match = re.search(r'https?://\S+', message)
        if not url_match:
            return {"response": "URL олдсонгүй.", "offer_report": False}

        url = url_match.group(0)
        logger.info(f"Орон сууцны URL боловсруулж байна: {url}")

        try:
            # Орон сууцны мэдээлэл татах
            property_data = await self.property_retriever.retrieve_property_details(url)
            if property_data.get("error"):
                return {"response": f"Мэдээлэл татахад алдаа: {property_data['error']}", "offer_report": False}

            # Дүүргийн шинжилгээ
            district_analysis = await self._get_district_analysis(property_data.get("district"))

            # Хариу үүсгэх
            response = await self._generate_property_response(message, property_data, district_analysis)

            # CoT сайжруулалт
            if use_cot:
                response = await self.cot_agent.enhance_response_with_reasoning(
                    response, "property_analysis",
                    {"property": property_data, "district": district_analysis}, message
                )

            # Мэдээлэл хадгалах
            self.last_property = {"property_data": property_data, "district_analysis": district_analysis, "url": url}

            return {
                "response": response + "\n\n🏠 **Тайлан авах уу?**\nПDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot
            }

        except Exception as e:
            logger.error(f"Орон сууц боловсруулахад алдаа: {e}")
            return {"response": "Орон сууцны мэдээлэл боловсруулахад алдаа гарлаа.", "offer_report": False}

    async def _handle_district(self, message: str, use_cot: bool) -> Dict[str, Any]:
        """Дүүргийн асуулт боловсруулах"""
        logger.info("Дүүргийн асуулт боловсруулж байна")

        try:
            district_analysis = await self.district_analyzer.analyze_district(message)
            response = await self._generate_district_response(message, district_analysis)

            if use_cot:
                response = await self.cot_agent.enhance_response_with_reasoning(
                    response, "district_comparison",
                    {"analysis": district_analysis, "query": message}, message
                )

            self.last_district = {"analysis": district_analysis, "query": message}

            return {
                "response": response + "\n\n📊 **Тайлан авах уу?**\nДүүргийн PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot
            }

        except Exception as e:
            logger.error(f"Дүүрэг боловсруулахад алдаа: {e}")
            return {"response": "Дүүргийн мэдээлэл боловсруулахад алдаа гарлаа.", "offer_report": False}

    async def _handle_market(self, message: str, use_cot: bool) -> Dict[str, Any]:
        """Зах зээлийн асуулт боловсруулах"""
        logger.info("Зах зээлийн асуулт боловсруулж байна")

        try:
            search_results = self.search_tool.invoke({"query": message})
            response = await self._generate_market_response(message, search_results)

            if use_cot:
                response = await self.cot_agent.enhance_response_with_reasoning(
                    response, "market_research",
                    {"search": search_results, "query": message}, message
                )

            return {
                "response": response + "\n\n📈 **Тайлан авах уу?**\nЗах зээлийн PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot
            }

        except Exception as e:
            logger.error(f"Зах зээл боловсруулахад алдаа: {e}")
            return {"response": "Зах зээлийн мэдээлэл боловсруулахад алдаа гарлаа.", "offer_report": False}

    async def _handle_general(self, message: str) -> Dict[str, Any]:
        """Ерөнхий асуулт боловсруулах"""
        try:
            search_results = self.search_tool.invoke({"query": message})
            response = await self._generate_general_response(message, search_results)
            return {"response": response, "offer_report": False}

        except Exception as e:
            logger.error(f"Ерөнхий асуулт боловсруулахад алдаа: {e}")
            return {"response": "Хайлт хийхэд алдаа гарлаа.", "offer_report": False}

    async def _generate_report(self) -> Dict[str, Any]:
        """Тайлан үүсгэх"""
        try:
            if self.last_property:
                result = await self.report_service.generate_property_report(self.last_property)
            elif self.last_district:
                result = await self.report_service.generate_district_report()
            else:
                result = await self.report_service.generate_comprehensive_market_report()

            if isinstance(result, dict) and result.get("success"):
                return {
                    "response": result["message"],
                    "download_url": result["download_url"],
                    "filename": result["filename"],
                    "offer_report": False
                }
            else:
                return {"response": str(result), "offer_report": False}

        except Exception as e:
            logger.error(f"Тайлан үүсгэхэд алдаа: {e}")
            return {"response": "Тайлан үүсгэхэд алдаа гарлаа.", "offer_report": False}

    async def _get_district_analysis(self, district: str) -> str:
        """Дүүргийн шинжилгээ авах"""
        if district and district != "N/A":
            return await self.district_analyzer.analyze_district(district)
        return "Дүүргийн мэдээлэл тодорхойгүй."

    async def _generate_property_response(self, query: str, property_data: Dict, district_analysis: str) -> str:
        """Орон сууцны хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate expert. Analyze this property and provide valuable insights.

Focus on:
1. Price evaluation - is it fair value?
2. Location benefits and drawbacks  
3. Investment potential with numbers
4. Key recommendations

Be specific, use numbers, and provide actionable advice.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human",
             "User query: {query}\nProperty details: {property}\nDistrict analysis: {district}\n\nProvide property analysis in Mongolian.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({
            "query": query,
            "property": json.dumps(property_data, ensure_ascii=False),
            "district": district_analysis
        })

    async def _generate_district_response(self, query: str, district_analysis: str) -> str:
        """Дүүргийн хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate market analyst. Provide clear district analysis with specific insights.

Focus on:
1. Current price levels with numbers
2. Comparison to other districts
3. Investment opportunities 
4. Who should buy here
5. Future outlook

Be specific and provide actionable recommendations.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human", "User query: {query}\nDistrict analysis: {analysis}\n\nProvide district analysis in Mongolian.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"query": query, "analysis": district_analysis})

    async def _generate_market_response(self, query: str, search_results: Any) -> str:
        """Зах зээлийн хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate market researcher. Analyze search results and provide valuable market insights.

Focus on:
1. Current market conditions
2. Price trends with specifics
3. Investment opportunities
4. Risks to watch
5. Actionable recommendations

Be specific with data and provide clear guidance.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human", "User query: {query}\nSearch results: {results}\n\nProvide market analysis in Mongolian.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"query": query, "results": search_results})

    async def _generate_general_response(self, query: str, search_results: Any) -> str:
        """Ерөнхий хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate assistant specializing in Mongolia's property market. 
Provide clear, helpful answers based on search results.

Provide:
- Direct answer to the user's question
- Relevant facts and data
- Practical advice if applicable
- Clear, actionable information

IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human", "User question: {query}\nSearch results: {results}\n\nProvide answer in Mongolian.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"query": query, "results": search_results})