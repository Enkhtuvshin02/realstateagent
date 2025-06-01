# services/chat_service.py
import logging
import re
import json
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.report_service import ReportService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, llm, search_tool, property_retriever, district_analyzer, pdf_generator):
        self.llm = llm
        self.search_tool = search_tool
        self.property_retriever = property_retriever
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator

        # Initialize enhanced report service with search integration
        self.report_service = ReportService(
            llm=llm,
            district_analyzer=district_analyzer,
            pdf_generator=pdf_generator,
            search_tool=search_tool
        )

        # Store last analysis for report generation
        self.last_property_analysis = None
        self.last_district_analysis = None
        self.last_response_type = None

    async def process_message(self, user_message: str) -> dict:
        """Process user message and return structured response"""
        logger.info(f"🔄 Processing message: {user_message}")

        try:
            # Check if this is a report acceptance response
            if self._is_report_acceptance(user_message):
                return await self._generate_report_based_on_context()

            # Determine message type and route accordingly
            message_type = self._classify_message(user_message)
            logger.info(f"📋 Message classified as: {message_type}")

            if message_type == "report_request":
                return await self._handle_report_request(user_message)
            elif message_type == "property_url":
                return await self._handle_property_url(user_message)
            elif message_type == "district_query":
                return await self._handle_district_query(user_message)
            elif message_type == "market_research":
                return await self._handle_market_research(user_message)
            else:
                return await self._handle_general_query(user_message)

        except Exception as e:
            logger.error(f"❌ Error in process_message: {e}", exc_info=True)
            return {
                "response": "Уучлаарай, алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False,
                "error": str(e)
            }

    def _is_report_acceptance(self, message: str) -> bool:
        """Check if user is accepting a report offer"""
        acceptance_keywords = [
            'тиймээ', 'тийм', 'yes', 'тайлан хүсэж байна',
            'хүсэж байна', 'гаргана уу', 'үүсгэнэ үү'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in acceptance_keywords) and len(message) < 50

    async def _generate_report_based_on_context(self) -> dict:
        """Generate report based on last response type"""
        if self.last_response_type == "property" and self.last_property_analysis:
            result = await self.report_service.generate_property_report(self.last_property_analysis)
        elif self.last_response_type == "district" and self.last_district_analysis:
            result = await self.report_service.generate_district_report()
        else:
            result = await self.report_service.generate_comprehensive_market_report()

        if isinstance(result, dict) and result.get("success"):
            return {
                "response": result["message"],
                "download_url": result["download_url"],
                "filename": result["filename"],
                "offer_report": False,
                "report_generated": True
            }
        else:
            return {
                "response": str(result),
                "offer_report": False
            }

    def _classify_message(self, message: str) -> str:
        """Classify the type of user message"""
        message_lower = message.lower()

        # Check for URL
        if re.search(r'https?://\S+', message):
            return "property_url"

        # Check for explicit report requests
        report_keywords = [
            'тайлан', 'report', 'pdf', 'татаж авах', 'download',
            'тайлан үүсгэх', 'generate report'
        ]
        if any(keyword in message_lower for keyword in report_keywords):
            return "report_request"

        # Check for district queries
        districts = [
            "хан-уул", "баянгол", "сүхбаатар", "чингэлтэй",
            "баянзүрх", "сонгинохайрхан", "багануур", "налайх", "багахангай"
        ]
        location_keywords = ["дүүрэг", "байршил", "хот", "газар", "орон сууц", "байр"]

        has_district = any(district in message_lower for district in districts)
        has_location_context = any(keyword in message_lower for keyword in location_keywords)

        if has_district or has_location_context:
            return "district_query"

        # Check for market research queries
        market_keywords = [
            "зах зээл", "үнийн чиглэл", "market", "тренд", "статистик",
            "хөрөнгө оруулалт", "investment", "зээл", "ипотек"
        ]
        if any(keyword in message_lower for keyword in market_keywords):
            return "market_research"

        return "general"

    async def _handle_property_url(self, user_message: str) -> dict:
        """Handle property URL analysis"""
        url_match = re.search(r'https?://\S+', user_message)
        if not url_match:
            return {
                "response": "URL олдсонгүй.",
                "offer_report": False
            }

        url = url_match.group(0)
        logger.info(f"🏠 Processing property URL: {url}")

        try:
            # Extract property details
            property_details = await self.property_retriever.retrieve_property_details(url)

            if property_details.get("error"):
                return {
                    "response": f"Мэдээлэл татаж авахад алдаа гарлаа: {property_details['error']}",
                    "offer_report": False
                }

            # Get district analysis
            location = property_details.get("district", "Улаанбаатар")
            if location and location != "N/A":
                district_analysis = await self.district_analyzer.analyze_district(location)
            else:
                district_analysis = "Дүүргийн мэдээлэл тодорхойгүй байна."

            # Generate comprehensive response
            response = await self._generate_enhanced_property_response(
                user_message, property_details, district_analysis, url
            )

            # Store for potential report generation
            self.last_property_analysis = {
                "property_details": property_details,
                "district_analysis": district_analysis,
                "url": url,
                "timestamp": datetime.now().isoformat()
            }
            self.last_response_type = "property"

            # Always offer report after property analysis
            return {
                "response": response + "\n\n🏠 **Тайлан авах уу?**\nЭнэ орон сууцны дэлгэрэнгүй PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "report_type": "property",
                "property_analyzed": True
            }

        except Exception as e:
            logger.error(f"❌ Error processing property URL: {e}")
            return {
                "response": f"URL боловсруулахад алдаа гарлаа: {str(e)}",
                "offer_report": False
            }

    async def _handle_district_query(self, user_message: str) -> dict:
        """Handle district-related queries"""
        logger.info("📍 Processing district query")

        try:
            # Find district name in message
            district_name = self._extract_district_name(user_message)

            # Get district analysis
            district_analysis = await self.district_analyzer.analyze_district(
                district_name if district_name else user_message
            )

            # Generate enhanced response
            response = await self._generate_enhanced_district_response(
                user_message, district_analysis, district_name
            )

            # Store for potential report
            self.last_district_analysis = {
                "district_analysis": district_analysis,
                "query": user_message,
                "district_name": district_name,
                "timestamp": datetime.now().isoformat()
            }
            self.last_response_type = "district"

            # Always offer report after district analysis
            return {
                "response": response + "\n\n📊 **Тайлан авах уу?**\nДүүргийн харьцуулалтын PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "report_type": "district",
                "district_analyzed": True
            }

        except Exception as e:
            logger.error(f"❌ Error processing district query: {e}")
            return {
                "response": "Дүүргийн мэдээлэл боловсруулахад алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False
            }

    async def _handle_market_research(self, user_message: str) -> dict:
        """Handle market research queries"""
        logger.info("🔍 Processing market research query")

        try:
            # Perform targeted search
            search_results = self.search_tool.invoke({"query": user_message})

            # Generate comprehensive response
            response = await self._generate_market_research_response(
                user_message, search_results
            )

            self.last_response_type = "market"

            # Always offer report after market research
            return {
                "response": response + "\n\n📈 **Тайлан авах уу?**\nЗах зээлийн дэлгэрэнгүй PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "report_type": "comprehensive",
                "search_performed": True
            }

        except Exception as e:
            logger.error(f"❌ Error processing market research: {e}")
            return {
                "response": "Зах зээлийн судалгаа хийхэд алдаа гарлаа.",
                "offer_report": False
            }

    async def _handle_general_query(self, user_message: str) -> dict:
        """Handle general real estate queries"""
        logger.info("🔍 Processing general query")

        try:
            # Use search for general queries
            search_results = self.search_tool.invoke({"query": user_message})

            # Generate response using LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Та бол үл хөдлөх хөрөнгийн туслах. Хэрэглэгчийн асуултад интернэтээс хайсан мэдээлэлд үндэслэн хариулна уу. 

Монгол улсын үл хөдлөх хөрөнгийн зах зээлд анхаарлаа хандуулна уу. Зөвхөн Монгол хэлээр хариулна уу."""),
                ("human", "Асуулт: {query}\nХайлтын үр дүн: {search_results}")
            ])

            chain = prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({
                "query": user_message,
                "search_results": search_results
            })

            self.last_response_type = "general"

            # For general queries, offer report if it seems substantial
            if len(response) > 200:
                return {
                    "response": response + "\n\n📄 **Тайлан авах уу?**\nЭнэ мэдээллийн PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                    "offer_report": True,
                    "search_performed": True
                }
            else:
                return {
                    "response": response,
                    "offer_report": False,
                    "search_performed": True
                }

        except Exception as e:
            logger.error(f"❌ Error processing general query: {e}")
            return {
                "response": "Хайлт хийхэд алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False
            }

    async def _handle_report_request(self, user_message: str) -> dict:
        """Handle explicit report generation requests"""
        logger.info("📋 Handling report request")

        try:
            report_type = self._determine_report_type(user_message)
            logger.info(f"📊 Generating {report_type} report")

            if report_type == "property":
                if not self.last_property_analysis:
                    return {
                        "response": "Орон сууцны мэдээлэл байхгүй. Эхлээд орон сууцны холбоос илгээнэ үү.",
                        "offer_report": False
                    }
                response = await self.report_service.generate_property_report(self.last_property_analysis)

            elif report_type == "district":
                response = await self.report_service.generate_district_report()

            elif report_type == "comprehensive":
                response = await self.report_service.generate_comprehensive_market_report()

            else:
                response = "Тайлангийн төрөл тодорхойгүй байна."

            if isinstance(response, dict) and response.get("success"):
                return {
                    "response": response["message"],
                    "download_url": response["download_url"],
                    "filename": response["filename"],
                    "offer_report": False,
                    "report_generated": True
                }
            else:
                return {
                    "response": str(response),
                    "offer_report": False
                }

        except Exception as e:
            logger.error(f"❌ Error generating report: {e}")
            return {
                "response": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
                "offer_report": False
            }

    def _determine_report_type(self, message: str) -> str:
        """Determine what type of report is being requested"""
        message_lower = message.lower()

        if any(keyword in message_lower for keyword in ['дүүргийн тайлан', 'дүүрэг харьцуулах', 'бүх дүүрэг']):
            return "district"
        elif any(keyword in message_lower for keyword in ['иж бүрэн', 'дэлгэрэнгүй зах зээл', 'зах зээлийн тайлан']):
            return "comprehensive"
        elif self.last_property_analysis:
            return "property"
        else:
            return "district"  # Default

    def _extract_district_name(self, message: str) -> str:
        """Extract district name from message"""
        districts = [
            "хан-уул", "баянгол", "сүхбаатар", "чингэлтэй",
            "баянзүрх", "сонгинохайрхан", "багануур", "налайх", "багахангай"
        ]

        message_lower = message.lower()
        for district in districts:
            if district in message_lower:
                return district
        return None

    async def _generate_enhanced_property_response(self, query: str, property_details: dict,
                                                   district_analysis: str, url: str) -> str:
        """Generate enhanced property analysis response"""

        # Get property-specific search data
        search_context = ""
        try:
            district_name = property_details.get("district", "")
            if district_name and district_name != "N/A":
                search_query = f"Улаанбаатар {district_name} дүүрэг орон сууцны зах зээл үнэ"
                search_results = self.search_tool.invoke({"query": search_query})
                if search_results:
                    search_context = f"Нэмэлт зах зээлийн мэдээлэл: {str(search_results)[:500]}"
        except Exception as e:
            logger.error(f"Search failed for property context: {e}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн мэргэжилтэн. Орон сууцны дэлгэрэнгүй шинжилгээг Монгол хэлээр хийнэ үү.

Дараах зүйлсийг тусгана уу:
1. Орон сууцны үндсэн мэдээлэл
2. Үнийн шинжилгээ ба тооцоолол
3. Дүүргийн зах зээлтэй харьцуулалт
4. Хөрөнгө оруулалтын боломж
5. Практик зөвлөмж

Зөвхөн Монгол хэлээр, дэлгэрэнгүй хариулна уу."""),
            ("human", """Хэрэглэгчийн асуулт: {query}

Орон сууцны мэдээлэл: {property_details}

Дүүргийн шинжилгээ: {district_analysis}

Нэмэлт контекст: {search_context}

Орон сууцны дэлгэрэнгүй шинжилгээг Монгол хэлээр хийнэ үү.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": query,
            "property_details": json.dumps(property_details, ensure_ascii=False, indent=2),
            "district_analysis": district_analysis,
            "search_context": search_context
        })

        return response

    async def _generate_enhanced_district_response(self, query: str, district_analysis: str,
                                                   district_name: str) -> str:
        """Generate enhanced district response"""

        # Get district-specific market data
        search_context = ""
        try:
            if district_name:
                search_query = f"{district_name} дүүрэг орон сууц зах зээл хөгжил"
                search_results = self.search_tool.invoke({"query": search_query})
                if search_results:
                    search_context = f"Нэмэлт мэдээлэл: {str(search_results)[:500]}"
        except Exception as e:
            logger.error(f"Search failed for district context: {e}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн туслах. Дүүргийн шинжилгээг дэлгэрэнгүй тайлбарлана уу.

Дараах зүйлсийг тусгана уу:
1. Дүүргийн үнийн түвшин
2. Харьцуулалт бусад дүүргүүдтэй
3. Байршлын давуу тал
4. Хөрөнгө оруулалтын боломж
5. Ирээдүйн төлөв

Зөвхөн Монгол хэлээр хариулна уу."""),
            ("human", """Хэрэглэгчийн асуулт: {query}

Дүүргийн шинжилгээ: {district_analysis}

Нэмэлт контекст: {search_context}

Дүүргийн мэдээллийг дэлгэрэнгүй тайлбарлана уу.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": query,
            "district_analysis": district_analysis,
            "search_context": search_context
        })

        return response

    async def _generate_market_research_response(self, query: str, search_results) -> str:
        """Generate market research response"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн зах зээлийн шинжээч. Интернэт хайлтын үр дүнд үндэслэн зах зээлийн шинжилгээ хийнэ үү.

Дараах зүйлсийг тусгана уу:
1. Одоогийн зах зээлийн нөхцөл
2. Үнийн чиглэл
3. Хөрөнгө оруулалтын боломж
4. Эрсдэл ба сорилт
5. Ирээдүйн төлөв

Зөвхөн Монгол хэлээр, мэргэжлийн шинжилгээ хийнэ үү."""),
            ("human", """Хэрэглэгчийн асуулт: {query}

Хайлтын үр дүн: {search_results}

Зах зээлийн шинжилгээг Монгол хэлээр хийнэ үү.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": query,
            "search_results": search_results
        })

        return response

    def get_analytics(self) -> dict:
        """Get usage analytics"""
        return {
            "last_property_analysis": self.last_property_analysis is not None,
            "last_district_analysis": self.last_district_analysis is not None,
            "last_response_type": self.last_response_type,
            "property_timestamp": self.last_property_analysis.get("timestamp") if self.last_property_analysis else None,
            "district_timestamp": self.last_district_analysis.get("timestamp") if self.last_district_analysis else None
        }