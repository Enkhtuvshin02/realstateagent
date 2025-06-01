# services/chat_service.py - Improved with selective CoT application
import logging
import re
import json
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.report_service import ReportService
from agents.chain_of_thought_agent import ChainOfThoughtAgent

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

        # Initialize improved Chain-of-Thought agent
        self.cot_agent = ChainOfThoughtAgent(llm=llm)

        # Store last analysis for report generation
        self.last_property_analysis = None
        self.last_district_analysis = None
        self.last_response_type = None

    async def process_message(self, user_message: str) -> dict:
        """Process user message and return structured response with selective CoT"""
        logger.info(f"🔄 Processing message: {user_message}")

        try:
            # Check if this is a report acceptance response
            if self._is_report_acceptance(user_message):
                return await self._generate_report_based_on_context()

            # Determine message type and route accordingly
            message_type = self._classify_message(user_message)
            logger.info(f"📋 Message classified as: {message_type}")

            # Check if CoT should be applied based on query complexity
            should_apply_cot = self._should_apply_cot(user_message, message_type)
            logger.info(f"🧠 CoT application decision: {should_apply_cot}")

            if message_type == "report_request":
                return await self._handle_report_request(user_message)
            elif message_type == "property_url":
                return await self._handle_property_url(user_message, apply_cot=should_apply_cot)
            elif message_type == "district_query":
                return await self._handle_district_query(user_message, apply_cot=should_apply_cot)
            elif message_type == "market_research":
                return await self._handle_market_research(user_message, apply_cot=should_apply_cot)
            else:
                return await self._handle_general_query(user_message, apply_cot=should_apply_cot)

        except Exception as e:
            logger.error(f"❌ Error in process_message: {e}", exc_info=True)
            return {
                "response": "Уучлаарай, алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False,
                "error": str(e)
            }

    def _should_apply_cot(self, user_message: str, message_type: str) -> bool:
        """Determine if Chain-of-Thought should be applied based on query complexity"""

        # Always apply CoT for these indicators
        complex_indicators = [
            'дэлгэрэнгүй', 'шинжилгээ', 'хөрөнгө оруулалт', 'харьцуулах',
            'зөвлөмж', 'investment', 'analysis', 'compare', 'detailed'
        ]

        # Apply CoT for property and district analysis
        if message_type in ['property_url', 'district_query']:
            return True

        # Apply CoT for complex market research
        if message_type == 'market_research':
            return True

        # Check for complexity indicators in the message
        message_lower = user_message.lower()
        if any(indicator in message_lower for indicator in complex_indicators):
            return True

        # For long queries (likely complex)
        if len(user_message) > 50:
            return True

        # Don't apply CoT for simple questions
        return False

    async def _handle_property_url(self, user_message: str, apply_cot: bool = True) -> dict:
        """Handle property URL analysis with optional CoT"""
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

            # Generate enhanced response
            response = await self._generate_enhanced_property_response(
                user_message, property_details, district_analysis, url
            )

            # Apply CoT enhancement if requested
            if apply_cot:
                cot_data = {
                    "property_details": property_details,
                    "district_analysis": district_analysis,
                    "url": url
                }

                logger.info("🧠 Applying CoT enhancement to property analysis...")
                response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=response,
                    analysis_type="property_analysis",
                    data=cot_data,
                    user_query=user_message
                )

            # Store for potential report generation
            self.last_property_analysis = {
                "property_details": property_details,
                "district_analysis": district_analysis,
                "url": url,
                "timestamp": datetime.now().isoformat()
            }
            self.last_response_type = "property"

            return {
                "response": response + "\n\n🏠 **Тайлан авах уу?**\nЭнэ орон сууцны дэлгэрэнгүй PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "report_type": "property",
                "property_analyzed": True,
                "cot_enhanced": apply_cot
            }

        except Exception as e:
            logger.error(f"❌ Error processing property URL: {e}")
            return {
                "response": f"URL боловсруулахад алдаа гарлаа: {str(e)}",
                "offer_report": False
            }

    async def _handle_district_query(self, user_message: str, apply_cot: bool = True) -> dict:
        """Handle district queries with optional CoT"""
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

            # Apply CoT enhancement if requested
            if apply_cot:
                cot_data = {
                    "district_analysis": district_analysis,
                    "query": user_message,
                    "district_name": district_name
                }

                logger.info("🧠 Applying CoT enhancement to district analysis...")
                response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=response,
                    analysis_type="district_comparison",
                    data=cot_data,
                    user_query=user_message
                )

            # Store for potential report
            self.last_district_analysis = {
                "district_analysis": district_analysis,
                "query": user_message,
                "district_name": district_name,
                "timestamp": datetime.now().isoformat()
            }
            self.last_response_type = "district"

            return {
                "response": response + "\n\n📊 **Тайлан авах уу?**\nДүүргийн харьцуулалтын PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "report_type": "district",
                "district_analyzed": True,
                "cot_enhanced": apply_cot
            }

        except Exception as e:
            logger.error(f"❌ Error processing district query: {e}")
            return {
                "response": "Дүүргийн мэдээлэл боловсруулахад алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False
            }

    async def _handle_market_research(self, user_message: str, apply_cot: bool = True) -> dict:
        """Handle market research with optional CoT"""
        logger.info("🔍 Processing market research query")

        try:
            # Perform targeted search
            search_results = self.search_tool.invoke({"query": user_message})

            # Generate response
            response = await self._generate_market_research_response(
                user_message, search_results
            )

            # Apply CoT enhancement if requested
            if apply_cot:
                cot_data = {
                    "search_results": search_results,
                    "query": user_message
                }

                logger.info("🧠 Applying CoT enhancement to market research...")
                response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=response,
                    analysis_type="market_research",
                    data=cot_data,
                    user_query=user_message
                )

            self.last_response_type = "market"

            return {
                "response": response + "\n\n📈 **Тайлан авах уу?**\nЗах зээлийн дэлгэрэнгүй PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                "offer_report": True,
                "report_type": "comprehensive",
                "search_performed": True,
                "cot_enhanced": apply_cot
            }

        except Exception as e:
            logger.error(f"❌ Error processing market research: {e}")
            return {
                "response": "Зах зээлийн судалгаа хийхэд алдаа гарлаа.",
                "offer_report": False
            }

    async def _handle_general_query(self, user_message: str, apply_cot: bool = False) -> dict:
        """Handle general queries with selective CoT"""
        logger.info("🔍 Processing general query")

        try:
            # Use search for general queries
            search_results = self.search_tool.invoke({"query": user_message})

            # Generate response using improved prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a professional real estate assistant specializing in Mongolia's property market. Provide clear, helpful answers based on search results.

Provide:
- Direct answer to the user's question
- Relevant facts and data
- Practical advice if applicable
- Clear, actionable information

IMPORTANT: Respond ONLY in Mongolian language with clear, valuable information."""),
                ("human",
                 "User question: {query}\nSearch results: {search_results}\n\nProvide a clear, helpful answer in Mongolian language.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({
                "query": user_message,
                "search_results": search_results
            })

            # Apply CoT only for complex general queries
            if apply_cot and len(response) > 150:
                cot_data = {
                    "search_results": search_results,
                    "query": user_message
                }

                logger.info("🧠 Applying CoT enhancement to complex general query...")
                response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=response,
                    analysis_type="market_research",
                    data=cot_data,
                    user_query=user_message
                )

            self.last_response_type = "general"

            if len(response) > 200:
                return {
                    "response": response + "\n\n📄 **Тайлан авах уу?**\nЭнэ мэдээллийн PDF тайлан авахыг хүсвэл **'Тиймээ'** гэж бичнэ үү.",
                    "offer_report": True,
                    "search_performed": True,
                    "cot_enhanced": apply_cot
                }
            else:
                return {
                    "response": response,
                    "offer_report": False,
                    "search_performed": True,
                    "cot_enhanced": apply_cot
                }

        except Exception as e:
            logger.error(f"❌ Error processing general query: {e}")
            return {
                "response": "Хайлт хийхэд алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False
            }

    async def _generate_enhanced_property_response(self, query: str, property_details: dict,
                                                   district_analysis: str, url: str) -> str:
        """Generate enhanced property analysis response"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate expert. Analyze this property and provide valuable insights.

Focus on:
1. Price evaluation - is it fair value?
2. Location benefits and drawbacks  
3. Investment potential with numbers
4. Key recommendations

Be specific, use numbers, and provide actionable advice.

IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human", """User query: {query}

Property details: {property_details}

District analysis: {district_analysis}

Provide clear property analysis in Mongolian language.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": query,
            "property_details": json.dumps(property_details, ensure_ascii=False, indent=2),
            "district_analysis": district_analysis
        })

        return response

    async def _generate_enhanced_district_response(self, query: str, district_analysis: str,
                                                   district_name: str) -> str:
        """Generate enhanced district response"""

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
            ("human", """User query: {query}

District analysis: {district_analysis}

Provide clear district analysis in Mongolian language.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": query,
            "district_analysis": district_analysis
        })

        return response

    async def _generate_market_research_response(self, query: str, search_results) -> str:
        """Generate market research response"""

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
            ("human", """User query: {query}

Search results: {search_results}

Provide clear market analysis in Mongolian language.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": query,
            "search_results": search_results
        })

        return response

    # ... (rest of the methods remain the same as before)

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

        if re.search(r'https?://\S+', message):
            return "property_url"

        report_keywords = [
            'тайлан', 'report', 'pdf', 'татаж авах', 'download',
            'тайлан үүсгэх', 'generate report'
        ]
        if any(keyword in message_lower for keyword in report_keywords):
            return "report_request"

        districts = [
            "хан-уул", "баянгол", "сүхбаатар", "чингэлтэй",
            "баянзүрх", "сонгинохайрхан", "багануур", "налайх", "багахангай"
        ]

        location_keywords = ["дүүрэг", "байршил", "хот", "газар", "орон сууц", "байр"]
        comparison_keywords = [
            "бүх дүүрэг", "дүүрэг харьцуулах", "дүүргүүд", "харьцуулалт",
            "compare", "all districts", "дүүргийн үнэ", "үнэ харьцуулах"
        ]

        has_district = any(district in message_lower for district in districts)
        has_location_context = any(keyword in message_lower for keyword in location_keywords)
        has_comparison_request = any(keyword in message_lower for keyword in comparison_keywords)

        if has_district or has_location_context or has_comparison_request:
            return "district_query"

        market_keywords = [
            "зах зээл", "үнийн чиглэл", "market", "тренд", "статистик",
            "хөрөнгө оруулалт", "investment", "зээл", "ипотек"
        ]
        if any(keyword in message_lower for keyword in market_keywords):
            return "market_research"

        return "general"

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

        # Check for comparison queries first
        comparison_keywords = [
            "бүх дүүрэг", "дүүрэг харьцуулах", "дүүргүүд", "харьцуулалт",
            "compare", "all districts", "дүүргийн үнэ", "үнэ харьцуулах"
        ]

        if any(keyword in message_lower for keyword in comparison_keywords):
            return "ALL_DISTRICTS_COMPARISON"  # Special flag for comparison queries

        # Look for specific district names
        for district in districts:
            if district in message_lower:
                return district

        return None

    def get_analytics(self) -> dict:
        """Get usage analytics including CoT statistics"""
        return {
            "last_property_analysis": self.last_property_analysis is not None,
            "last_district_analysis": self.last_district_analysis is not None,
            "last_response_type": self.last_response_type,
            "property_timestamp": self.last_property_analysis.get("timestamp") if self.last_property_analysis else None,
            "district_timestamp": self.last_district_analysis.get("timestamp") if self.last_district_analysis else None,
            "cot_agent_available": self.cot_agent is not None,
            "cot_analysis_types": self.cot_agent.get_analysis_types() if self.cot_agent else [],
            "cot_approach": "selective_application"
        }