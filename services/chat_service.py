# services/chat_service.py - Рефакторлогдсон чат үйлчилгээ Chain of Thought агенттай
import logging
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.report_service import ReportService
from agents.chain_of_thought_agent import ChainOfThoughtAgent
from config.chat_constants import (
    MESSAGE_TYPES, REPORT_ACCEPTANCE_KEYWORDS, DISTRICT_NAMES,
    CLASSIFICATION_KEYWORDS, COT_INDICATORS, REPORT_TYPES,
    REPORT_TYPE_KEYWORDS, RESPONSE_TEMPLATES, ERROR_MESSAGES,
    SYSTEM_PROMPTS, CONFIG, SPECIAL_FLAGS
)

logger = logging.getLogger(__name__)


class ChatService:
    """Үл хөдлөх хөрөнгийн чат үйлчилгээ Chain of Thought агенттай"""

    def __init__(self, llm, search_tool, property_retriever, district_analyzer, pdf_generator):
        self.llm = llm
        self.search_tool = search_tool
        self.property_retriever = property_retriever
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator

        # Үйлчилгээнүүдийг эхлүүлэх
        self.report_service = ReportService(
            llm=llm,
            district_analyzer=district_analyzer,
            pdf_generator=pdf_generator,
            search_tool=search_tool
        )
        self.cot_agent = ChainOfThoughtAgent(llm=llm)

        # Төлөв хадгалах
        self.last_property_analysis = None
        self.last_district_analysis = None
        self.last_response_type = None

    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """Хэрэглэгчийн мессежийг боловсруулах"""
        logger.info(f"🔄 Processing message: {user_message}")

        try:
            # Тайлан хүлээн авах эсэхийг шалгах
            if self._is_report_acceptance(user_message):
                return await self._generate_report_based_on_context()

            # Мессежийн төрлийг тодорхойлох
            message_type = self._classify_message(user_message)
            logger.info(f"📋 Message type: {message_type}")

            # CoT хэрэглэх эсэхийг шийдэх
            should_apply_cot = self._should_apply_cot(user_message, message_type)
            logger.info(f"🧠 CoT decision: {should_apply_cot}")

            # Мессежийн төрлөөр чиглүүлэх
            handlers = {
                MESSAGE_TYPES["REPORT_REQUEST"]: self._handle_report_request,
                MESSAGE_TYPES["PROPERTY_URL"]: lambda msg: self._handle_property_url(msg, should_apply_cot),
                MESSAGE_TYPES["DISTRICT_QUERY"]: lambda msg: self._handle_district_query(msg, should_apply_cot),
                MESSAGE_TYPES["MARKET_RESEARCH"]: lambda msg: self._handle_market_research(msg, should_apply_cot),
                MESSAGE_TYPES["GENERAL"]: lambda msg: self._handle_general_query(msg, should_apply_cot)
            }

            handler = handlers.get(message_type, handlers[MESSAGE_TYPES["GENERAL"]])
            return await handler(user_message)

        except Exception as e:
            logger.error(f"❌ Error in process_message: {e}", exc_info=True)
            return self._create_error_response(ERROR_MESSAGES["general_error"], str(e))

    def _should_apply_cot(self, user_message: str, message_type: str) -> bool:
        """CoT хэрэглэх эсэхийг шийдэх"""
        # Үргэлж CoT хэрэглэх төрлүүд
        if message_type in COT_INDICATORS["always_apply_types"]:
            return True

        message_lower = user_message.lower()

        # Төвөгтэй шалгуур үгүүд
        if any(indicator in message_lower for indicator in COT_INDICATORS["complex_terms"]):
            return True

        # Урт мессеж (төвөгтэй байх магадлалтай)
        if len(user_message) > COT_INDICATORS["min_message_length"]:
            return True

        return False

    async def _handle_property_url(self, user_message: str, apply_cot: bool = True) -> Dict[str, Any]:
        """Үл хөдлөх хөрөнгийн URL боловсруулах"""
        url_match = re.search(r'https?://\S+', user_message)
        if not url_match:
            return self._create_error_response(ERROR_MESSAGES["url_not_found"])

        url = url_match.group(0)
        logger.info(f"🏠 Processing property URL: {url}")

        try:
            # Үл хөдлөх хөрөнгийн мэдээлэл татах
            property_details = await self.property_retriever.retrieve_property_details(url)

            if property_details.get("error"):
                return self._create_error_response(
                    ERROR_MESSAGES["property_extraction_failed"].format(property_details['error'])
                )

            # Дүүргийн шинжилгээ хийх
            district_analysis = await self._get_district_analysis(property_details.get("district"))

            # Хариу үүсгэх
            response = await self._generate_property_response(
                user_message, property_details, district_analysis, url
            )

            # CoT сайжруулалт хэрэглэх
            if apply_cot:
                response = await self._apply_cot_enhancement(
                    response, "property_analysis",
                    {"property_details": property_details, "district_analysis": district_analysis, "url": url},
                    user_message
                )

            # Мэдээллийг хадгалах
            self._store_property_analysis(property_details, district_analysis, url)

            return self._create_property_response(response, apply_cot)

        except Exception as e:
            logger.error(f"❌ Error processing property URL: {e}")
            return self._create_error_response(ERROR_MESSAGES["property_url_error"].format(str(e)))

    async def _handle_district_query(self, user_message: str, apply_cot: bool = True) -> Dict[str, Any]:
        """Дүүргийн хайлт боловсруулах"""
        logger.info("📍 Processing district query")

        try:
            district_name = self._extract_district_name(user_message)
            district_analysis = await self.district_analyzer.analyze_district(
                district_name if district_name else user_message
            )

            response = await self._generate_district_response(
                user_message, district_analysis, district_name
            )

            if apply_cot:
                response = await self._apply_cot_enhancement(
                    response, "district_comparison",
                    {"district_analysis": district_analysis, "query": user_message, "district_name": district_name},
                    user_message
                )

            self._store_district_analysis(district_analysis, user_message, district_name)

            return self._create_district_response(response, apply_cot)

        except Exception as e:
            logger.error(f"❌ Error processing district query: {e}")
            return self._create_error_response(ERROR_MESSAGES["district_processing_error"])

    async def _handle_market_research(self, user_message: str, apply_cot: bool = True) -> Dict[str, Any]:
        """Зах зээлийн судалгаа боловсруулах"""
        logger.info("🔍 Processing market research query")

        try:
            search_results = self.search_tool.invoke({"query": user_message})

            response = await self._generate_market_response(user_message, search_results)

            if apply_cot:
                response = await self._apply_cot_enhancement(
                    response, "market_research",
                    {"search_results": search_results, "query": user_message},
                    user_message
                )

            self.last_response_type = "market"

            return self._create_market_response(response, apply_cot)

        except Exception as e:
            logger.error(f"❌ Error processing market research: {e}")
            return self._create_error_response(ERROR_MESSAGES["market_research_error"])

    async def _handle_general_query(self, user_message: str, apply_cot: bool = False) -> Dict[str, Any]:
        """Ерөнхий хайлт боловсруулах"""
        logger.info("🔍 Processing general query")

        try:
            search_results = self.search_tool.invoke({"query": user_message})

            response = await self._generate_general_response(user_message, search_results)

            # Төвөгтэй ерөнхий хайлтад CoT хэрэглэх
            if apply_cot and len(response) > COT_INDICATORS["complex_response_length"]:
                response = await self._apply_cot_enhancement(
                    response, "market_research",
                    {"search_results": search_results, "query": user_message},
                    user_message
                )

            self.last_response_type = "general"

            return self._create_general_response(response, apply_cot)

        except Exception as e:
            logger.error(f"❌ Error processing general query: {e}")
            return self._create_error_response(ERROR_MESSAGES["search_error"])

    async def _handle_report_request(self, user_message: str) -> Dict[str, Any]:
        """Тайлан үүсгэх хүсэлт боловсруулах"""
        logger.info("📋 Processing report request")

        try:
            report_type = self._determine_report_type(user_message)
            logger.info(f"📊 Generating {report_type} report")

            if report_type == REPORT_TYPES["PROPERTY"]:
                if not self.last_property_analysis:
                    return self._create_error_response(ERROR_MESSAGES["no_property_data"])
                response = await self.report_service.generate_property_report(self.last_property_analysis)
            elif report_type == REPORT_TYPES["DISTRICT"]:
                response = await self.report_service.generate_district_report()
            elif report_type == REPORT_TYPES["COMPREHENSIVE"]:
                response = await self.report_service.generate_comprehensive_market_report()
            else:
                return self._create_error_response(ERROR_MESSAGES["unknown_report_type"])

            return self._process_report_response(response)

        except Exception as e:
            logger.error(f"❌ Error generating report: {e}")
            return self._create_error_response(ERROR_MESSAGES["report_generation_error"].format(str(e)))

    # === HELPER METHODS ===

    async def _get_district_analysis(self, district: str) -> str:
        """Дүүргийн шинжилгээ авах"""
        if district and district != "N/A":
            return await self.district_analyzer.analyze_district(district)
        return "Дүүргийн мэдээлэл тодорхойгүй байна."

    async def _apply_cot_enhancement(self, response: str, analysis_type: str,
                                     data: Dict[str, Any], user_query: str) -> str:
        """Chain of Thought сайжруулалт хэрэглэх"""
        logger.info("🧠 Applying CoT enhancement...")
        return await self.cot_agent.enhance_response_with_reasoning(
            original_response=response,
            analysis_type=analysis_type,
            data=data,
            user_query=user_query
        )

    def _store_property_analysis(self, property_details: Dict, district_analysis: str, url: str) -> None:
        """Үл хөдлөх хөрөнгийн шинжилгээг хадгалах"""
        self.last_property_analysis = {
            "property_details": property_details,
            "district_analysis": district_analysis,
            "url": url,
            "timestamp": datetime.now().isoformat()
        }
        self.last_response_type = "property"

    def _store_district_analysis(self, district_analysis: str, query: str, district_name: str) -> None:
        """Дүүргийн шинжилгээг хадгалах"""
        self.last_district_analysis = {
            "district_analysis": district_analysis,
            "query": query,
            "district_name": district_name,
            "timestamp": datetime.now().isoformat()
        }
        self.last_response_type = "district"

    # === RESPONSE GENERATORS ===

    async def _generate_property_response(self, query: str, property_details: Dict,
                                          district_analysis: str, url: str) -> str:
        """Үл хөдлөх хөрөнгийн хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPTS["property_analysis"]),
            ("human",
             "User query: {query}\n\nProperty details: {property_details}\n\nDistrict analysis: {district_analysis}\n\nProvide clear property analysis in Mongolian language.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({
            "query": query,
            "property_details": json.dumps(property_details, ensure_ascii=False, indent=2),
            "district_analysis": district_analysis
        })

    async def _generate_district_response(self, query: str, district_analysis: str, district_name: str) -> str:
        """Дүүргийн хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPTS["district_analysis"]),
            ("human",
             "User query: {query}\n\nDistrict analysis: {district_analysis}\n\nProvide clear district analysis in Mongolian language.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({
            "query": query,
            "district_analysis": district_analysis
        })

    async def _generate_market_response(self, query: str, search_results: Any) -> str:
        """Зах зээлийн хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPTS["market_research"]),
            ("human",
             "User query: {query}\n\nSearch results: {search_results}\n\nProvide clear market analysis in Mongolian language.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({
            "query": query,
            "search_results": search_results
        })

    async def _generate_general_response(self, query: str, search_results: Any) -> str:
        """Ерөнхий хариу үүсгэх"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPTS["general_query"]),
            ("human",
             "User question: {query}\nSearch results: {search_results}\n\nProvide a clear, helpful answer in Mongolian language.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({
            "query": query,
            "search_results": search_results
        })

    # === RESPONSE CREATORS ===

    def _create_property_response(self, response: str, cot_enhanced: bool) -> Dict[str, Any]:
        """Үл хөдлөх хөрөнгийн хариу үүсгэх"""
        return {
            "response": response + RESPONSE_TEMPLATES["property_offer"],
            "offer_report": True,
            "report_type": REPORT_TYPES["PROPERTY"],
            "property_analyzed": True,
            "cot_enhanced": cot_enhanced
        }

    def _create_district_response(self, response: str, cot_enhanced: bool) -> Dict[str, Any]:
        """Дүүргийн хариу үүсгэх"""
        return {
            "response": response + RESPONSE_TEMPLATES["district_offer"],
            "offer_report": True,
            "report_type": REPORT_TYPES["DISTRICT"],
            "district_analyzed": True,
            "cot_enhanced": cot_enhanced
        }

    def _create_market_response(self, response: str, cot_enhanced: bool) -> Dict[str, Any]:
        """Зах зээлийн хариу үүсгэх"""
        return {
            "response": response + RESPONSE_TEMPLATES["market_offer"],
            "offer_report": True,
            "report_type": REPORT_TYPES["COMPREHENSIVE"],
            "search_performed": True,
            "cot_enhanced": cot_enhanced
        }

    def _create_general_response(self, response: str, cot_enhanced: bool) -> Dict[str, Any]:
        """Ерөнхий хариу үүсгэх"""
        if len(response) > CONFIG["min_complex_response_length"]:
            return {
                "response": response + RESPONSE_TEMPLATES["general_offer"],
                "offer_report": True,
                "search_performed": True,
                "cot_enhanced": cot_enhanced
            }
        else:
            return {
                "response": response,
                "offer_report": False,
                "search_performed": True,
                "cot_enhanced": cot_enhanced
            }

    def _create_error_response(self, message: str, error: str = None) -> Dict[str, Any]:
        """Алдааны хариу үүсгэх"""
        response = {"response": message, "offer_report": False}
        if error:
            response["error"] = error
        return response

    # === CLASSIFICATION METHODS ===

    def _classify_message(self, message: str) -> str:
        """Мессежийн төрлийг ангилах"""
        message_lower = message.lower()

        if re.search(r'https?://\S+', message):
            return MESSAGE_TYPES["PROPERTY_URL"]

        if any(keyword in message_lower for keyword in CLASSIFICATION_KEYWORDS["report"]):
            return MESSAGE_TYPES["REPORT_REQUEST"]

        has_district = any(district in message_lower for district in DISTRICT_NAMES)
        has_location = any(keyword in message_lower for keyword in CLASSIFICATION_KEYWORDS["location"])
        has_comparison = any(keyword in message_lower for keyword in CLASSIFICATION_KEYWORDS["comparison"])

        if has_district or has_location or has_comparison:
            return MESSAGE_TYPES["DISTRICT_QUERY"]

        if any(keyword in message_lower for keyword in CLASSIFICATION_KEYWORDS["market"]):
            return MESSAGE_TYPES["MARKET_RESEARCH"]

        return MESSAGE_TYPES["GENERAL"]

    def _is_report_acceptance(self, message: str) -> bool:
        """Тайлан хүлээн авах эсэхийг шалгах"""
        message_lower = message.lower()
        return (any(keyword in message_lower for keyword in REPORT_ACCEPTANCE_KEYWORDS)
                and len(message) < CONFIG["max_acceptance_message_length"])

    def _determine_report_type(self, message: str) -> str:
        """Тайлангийн төрлийг тодорхойлох"""
        message_lower = message.lower()

        if any(keyword in message_lower for keyword in REPORT_TYPE_KEYWORDS["district"]):
            return REPORT_TYPES["DISTRICT"]
        elif any(keyword in message_lower for keyword in REPORT_TYPE_KEYWORDS["comprehensive"]):
            return REPORT_TYPES["COMPREHENSIVE"]
        elif self.last_property_analysis:
            return REPORT_TYPES["PROPERTY"]
        else:
            return REPORT_TYPES["DISTRICT"]

    def _extract_district_name(self, message: str) -> Optional[str]:
        """Мессежээс дүүргийн нэр ялгах"""
        message_lower = message.lower()

        # Харьцуулах хайлт эсэхийг шалгах
        if any(keyword in message_lower for keyword in CLASSIFICATION_KEYWORDS["comparison"]):
            return SPECIAL_FLAGS["all_districts_comparison"]

        # Тодорхой дүүргийн нэр хайх
        for district in DISTRICT_NAMES:
            if district in message_lower:
                return district

        return None

    # === UTILITY METHODS ===

    async def _generate_report_based_on_context(self) -> Dict[str, Any]:
        """Сүүлийн хариултын төрөлд үндэслэн тайлан үүсгэх"""
        if self.last_response_type == "property" and self.last_property_analysis:
            result = await self.report_service.generate_property_report(self.last_property_analysis)
        elif self.last_response_type == "district" and self.last_district_analysis:
            result = await self.report_service.generate_district_report()
        else:
            result = await self.report_service.generate_comprehensive_market_report()

        return self._process_report_response(result)

    def _process_report_response(self, result: Any) -> Dict[str, Any]:
        """Тайлангийн хариуг боловсруулах"""
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

    def get_analytics(self) -> Dict[str, Any]:
        """Хэрэглээний аналитик болон CoT статистик авах"""
        return {
            "last_property_analysis": self.last_property_analysis is not None,
            "last_district_analysis": self.last_district_analysis is not None,
            "last_response_type": self.last_response_type,
            "property_timestamp": self.last_property_analysis.get("timestamp") if self.last_property_analysis else None,
            "district_timestamp": self.last_district_analysis.get("timestamp") if self.last_district_analysis else None,
            "cot_agent_available": self.cot_agent is not None,
            "cot_analysis_types": self.cot_agent.get_analysis_types() if self.cot_agent else [],
            "cot_approach": CONFIG["cot_approach"]
        }