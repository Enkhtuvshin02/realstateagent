import logging
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.report_service import ReportService
from agents.chain_of_thought_agent import ChainOfThoughtAgent

logger = logging.getLogger(__name__)

REPORT_KEYWORDS = ['тийм', 'yes', 'тайлан', 'report']
DISTRICT_NAMES = [
    "хан-уул", "хануул", "khan-uul", "khanuul", "хан уул",
    "баянгол", "bayngol",
    "сүхбаатар", "сухбаатар", "sukhbaatar", "suhbaatar",
    "чингэлтэй", "чингэлтэи", "chingeltei",
    "баянзүрх", "баянзурх", "bayanzurkh", "bayanzurh",
    "сонгинохайрхан", "сонгино", "songinokhairkhan",
    "багануур", "baganuur",
    "налайх", "nalaikh",
    "багахангай", "bagakhangai"
]
COMPARISON_KEYWORDS = ['бүх дүүрэг', 'дүүрэг харьцуулах', 'дүүргүүд', 'харьцуулах', 'compare']
MARKET_KEYWORDS = ['зах зээл', 'үнийн чиглэл', 'market', 'тренд', 'статистик']

class ResponseValidator:
    @staticmethod
    def is_garbage_response(text: str) -> bool:
        if not text or len(text.strip()) < 20:
            return True
        if re.search(r'(.)\1{15,}', text):
            return True
        if re.search(r'(\w+)(\s+\1){5,}', text):
            return True
        mongolian_patterns = [
            r'(өөрөө){8,}',
            r'(рөөрөө){8,}',
            r'(\w{3,5})\1{10,}'
        ]
        for pattern in mongolian_patterns:
            if re.search(pattern, text):
                return True
        return False
    @staticmethod
    def clean_response(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'(.)\1{5,}', r'\1', text)
        text = re.sub(r'\b(\w+)(\s+\1){3,}', r'\1', text)
        text = re.sub(r'(өөрөө){3,}', 'өөрөө', text)
        text = re.sub(r'(рөөрөө){3,}', '', text)
        words = text.split()
        cleaned_words = [word for word in words if len(word) < 80]
        text = ' '.join(cleaned_words)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    @staticmethod
    def validate_response(text: str) -> Dict[str, Any]:
        if not text:
            return {"is_valid": False, "reason": "empty", "can_clean": False}
        if ResponseValidator.is_garbage_response(text):
            cleaned = ResponseValidator.clean_response(text)
            if len(cleaned) > 50 and not ResponseValidator.is_garbage_response(cleaned):
                return {
                    "is_valid": True,
                    "reason": "cleaned_garbage",
                    "can_clean": True,
                    "cleaned_text": cleaned
                }
            else:
                return {"is_valid": False, "reason": "garbage_detected", "can_clean": False}
        if len(text.strip()) < 50:
            return {"is_valid": False, "reason": "too_short", "can_clean": False}
        english_words = ['the', 'and', 'or', 'in', 'of', 'to', 'for', 'with', 'by',
                         'analysis', 'price', 'district', 'property', 'market', 'investment']
        english_count = sum(1 for word in english_words if word.lower() in text.lower())
        if english_count > 8:
            return {"is_valid": False, "reason": "too_much_english", "can_clean": False}
        error_patterns = [
            "мэдээлэл олдсонгүй",
            "алдаа гарлаа",
            "боловсруулахад алдаа",
            "error occurred"
        ]
        has_errors = any(pattern in text.lower() for pattern in error_patterns)
        if has_errors:
            return {"is_valid": False, "reason": "contains_errors", "can_clean": False}
        return {"is_valid": True, "reason": "valid", "can_clean": False}

class ChatService:
    def __init__(self, llm, search_tool, property_retriever, district_analyzer, pdf_generator):
        self.llm = llm
        self.search_tool = search_tool
        self.property_retriever = property_retriever
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator
        self.report_service = ReportService(llm, district_analyzer, pdf_generator, search_tool)
        self.cot_agent = ChainOfThoughtAgent(llm)
        self.validator = ResponseValidator()
        self.last_property_context = None
        self.last_district_context = None
        self.last_market_context = None
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        logger.info(f"Processing: {user_message[:50]}...")
        try:
            if self._wants_report(user_message):
                return await self._generate_report()
            message_type = self._classify_message(user_message)
            use_cot = len(user_message) > 20 or message_type in ['property', 'district', 'market']
            if message_type == 'property':
                return await self._handle_property(user_message, use_cot)
            elif message_type == 'district':
                return await self._handle_district(user_message, use_cot)
            elif message_type == 'market':
                return await self._handle_market(user_message, use_cot)
            else:
                return await self._handle_general(user_message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "response": "Уучлаарай, хүсэлтийг боловсруулахад алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False,
                "status": "error"
            }
    def _classify_message(self, message: str) -> str:
        message_lower = message.lower()
        if re.search(r'https?://\S+', message):
            return 'property'
        if any(keyword in message_lower for keyword in COMPARISON_KEYWORDS):
            return 'district'
        if any(district in message_lower for district in DISTRICT_NAMES):
            return 'district'
        if 'дүүрэг' in message_lower:
            return 'district'
        if any(keyword in message_lower for keyword in MARKET_KEYWORDS):
            return 'market'
        return 'general'
    def _wants_report(self, message: str) -> bool:
        message_lower = message.lower().strip()
        is_report_request = (
                any(keyword == message_lower for keyword in REPORT_KEYWORDS) or
                (message_lower.startswith("тийм") and len(message_lower) < 10) or
                (message_lower.startswith("yes") and len(message_lower) < 10)
        )
        has_context = any([
            self.last_property_context,
            self.last_district_context,
            self.last_market_context
        ])
        return is_report_request and has_context
    async def _handle_district(self, message: str, use_cot: bool) -> Dict[str, Any]:
        logger.info(f"Processing district query: {message[:50]}...")
        try:
            if hasattr(self.district_analyzer, 'get_vectorstore_status'):
                status = self.district_analyzer.get_vectorstore_status()
                logger.info(f"Vectorstore status: {status}")
            analysis = await self.district_analyzer.analyze_district(message)
            validation = self.validator.validate_response(analysis)
            logger.info(f"Analysis validation: {validation}")
            if not validation["is_valid"]:
                if validation["reason"] == "garbage_detected":
                    logger.warning("Detected garbage response, generating fallback")
                    analysis = await self._generate_fallback_district_response(message)
                elif validation["reason"] == "too_much_english":
                    logger.warning("Response contains too much English, regenerating")
                    analysis = await self._regenerate_mongolian_response(message, "district")
                elif validation["can_clean"]:
                    logger.info("Cleaning response with minor issues")
                    analysis = validation["cleaned_text"]
                else:
                    logger.warning(f"Invalid response: {validation['reason']}")
                    analysis = await self._generate_fallback_district_response(message)
            analysis_quality = self._assess_analysis_quality(analysis)
            logger.info(f"Analysis quality: {analysis_quality}")
            if analysis_quality['is_valid']:
                final_response = analysis
                if use_cot and analysis_quality['is_high_quality']:
                    try:
                        analysis_type = "district_comparison" if "харьцуулалт" in analysis else "district_analysis"
                        cot_data = {"district_analysis_text": analysis, "user_query": message}
                        cot_response = await self.cot_agent.enhance_response_with_reasoning(
                            original_response=analysis,
                            analysis_type=analysis_type,
                            data=cot_data,
                            user_query=message
                        )
                        cot_validation = self.validator.validate_response(cot_response)
                        if cot_validation["is_valid"]:
                            final_response = cot_response
                        else:
                            logger.warning("CoT response invalid, using original")
                    except Exception as e:
                        logger.warning(f"CoT enhancement failed: {e}")
                self.last_district_context = {
                    "query": message,
                    "analysis_content": analysis,
                    "quality": analysis_quality,
                    "timestamp": datetime.now().isoformat()
                }
                self._clear_other_contexts("district")
                return {
                    "response": final_response + "\n\nТайлан үүсгэх үү?\nДүүргийн PDF тайлан үүсгэхийг хүсвэл Тийм гэж бичнэ үү.",
                    "offer_report": True,
                    "cot_enhanced": use_cot and analysis_quality['is_high_quality'],
                    "status": "success",
                    "vectorstore_used": analysis_quality.get('used_vectorstore', False)
                }
            else:
                return {
                    "response": analysis,
                    "offer_report": False,
                    "status": "partial_success",
                    "vectorstore_used": False
                }
        except Exception as e:
            logger.error(f"District handling error: {e}")
            return {
                "response": "Дүүргийн мэдээлэл боловсруулахад алдаа гарлаа. Дахин оролдоно уу.",
                "offer_report": False,
                "status": "error"
            }
    async def _generate_fallback_district_response(self, message: str) -> str:
        district_match = re.search(r'(хан-уул|баянгол|сүхбаатар|чингэлтэй|баянзүрх|сонгинохайрхан)', message.lower())
        district_name = district_match.group(1).title() if district_match else "тодорхойгүй дүүрэг"
        return f"""**{district_name} дүүргийн ерөнхий мэдээлэл**

Уучлаарай, {district_name} дүүргийн дэлгэрэнгүй шинжилгээг одоогоор боловсруулж чадахгүй байна.

**Ерөнхий зөвлөмж:**
- Дүүргийн үнийн түвшинг судлахын тулд олон эх сурвалжийг харьцуулаарай
- Орон нутгийн үл хөдлөх хөрөнгийн агентуудтай зөвлөлдөөрэй  
- Дүүргийн инфраструктур, боловсролын байгууллага, тээврийн хүртээмжийг анхаарна уу

Дэлгэрэнгүй мэдээллийг авахын тулд дахин асууна уу."""
    async def _regenerate_mongolian_response(self, message: str, response_type: str) -> str:
        district_match = re.search(r'(хан-уул|баянгол|сүхбаатар|чингэлтэй|баянзүрх|сонгинохайрхан)', message.lower())
        district_name = district_match.group(1).title() if district_match else "дүүрэг"
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та ЗӨВХӨН монгол хэлээр хариулдаг үл хөдлөх хөрөнгийн зөвлөх. \n\nХАТУУ ШААРДЛАГА:\n- Зөвхөн МОНГОЛ хэлээр бичнэ үү \n- Англи үг огт хэрэглэхгүй байх\n- 100 үгээс хэтрэхгүй байх\n- Давтан бичихгүй байх\n- Тодорхой, товч мэдээлэл өгнө үү"""),
            ("human", "{district} дүүргийн талаар товч мэдээлэл өгнө үү.")
        ])
        try:
            chain = prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({"district": district_name})
            validation = self.validator.validate_response(response)
            if validation["is_valid"]:
                return response
            else:
                return await self._generate_fallback_district_response(message)
        except Exception as e:
            logger.error(f"Response regeneration failed: {e}")
            return await self._generate_fallback_district_response(message)
    def _assess_analysis_quality(self, analysis: str) -> Dict[str, Any]:
        if not analysis or len(analysis.strip()) < 100:
            return {
                "is_valid": False,
                "is_high_quality": False,
                "reason": "too_short"
            }
        analysis_lower = analysis.lower()
        error_indicators = [
            "мэдээлэл олдсонгүй",
            "алдаа гарлаа",
            "хайлтаас мэдээлэл олдсонгүй",
            "интернетээс мэдээлэл олдсонгүй",
            "боловсруулж чадахгүй"
        ]
        has_errors = any(indicator in analysis_lower for indicator in error_indicators)
        quality_indicators = [
            "төгрөг",
            "дундаж үнэ",
            "дүүрэг",
            "хөрөнгө оруулалт",
            "зөвлөмж"
        ]
        quality_score = sum(1 for indicator in quality_indicators if indicator in analysis_lower)
        has_specific_numbers = bool(re.search(r'\d{1,3}[, ]\d{3}[, ]\d{3}', analysis))
        used_vectorstore = "(Энэ мэдээлэл интернет хайлтаас авсан болно.)" not in analysis
        garbage_validation = self.validator.validate_response(analysis)
        is_clean = garbage_validation["is_valid"]
        is_valid = not has_errors and is_clean and quality_score >= 2
        is_high_quality = is_valid and quality_score >= 4 and has_specific_numbers
        return {
            "is_valid": is_valid,
            "is_high_quality": is_high_quality,
            "quality_score": quality_score,
            "has_specific_numbers": has_specific_numbers,
            "used_vectorstore": used_vectorstore,
            "has_errors": has_errors,
            "is_clean": is_clean,
            "reason": "quality_assessed"
        }
    async def _handle_property(self, message: str, use_cot: bool) -> Dict[str, Any]:
        url_match = re.search(r'https?://\S+', message)
        if not url_match:
            return {
                "response": "Орон сууцны мэдээлэл авахын тулд URL хаягийг оруулна уу.",
                "offer_report": False
            }
        url = url_match.group(0)
        logger.info(f"Processing property URL: {url}")
        try:
            property_data = await self.property_retriever.retrieve_property_details(url)
            if not property_data or property_data.get("error"):
                error_msg = property_data.get("error", "Үл хөдлөх хөрөнгийн мэдээлэл авахад алдаа гарлаа.")
                return {"response": f"Алдаа: {error_msg}", "offer_report": False}
            district_name = property_data.get("district", "")
            district_analysis = "Дүүргийн мэдээлэл олдсонгүй."
            if district_name and district_name.lower() != 'n/a':
                try:
                    district_analysis = await self.district_analyzer.analyze_district(district_name)
                    validation = self.validator.validate_response(district_analysis)
                    if not validation["is_valid"]:
                        district_analysis = f"{district_name} дүүргийн мэдээлэл одоогоор боловсруулах боломжгүй."
                except Exception as e:
                    logger.warning(f"District analysis failed: {e}")
                    district_analysis = f"{district_name} дүүргийн мэдээлэл авахад алдаа гарлаа."
            summary = await self._generate_property_summary_with_validation(message, property_data, district_analysis)
            final_response = summary
            if use_cot:
                try:
                    cot_data = {
                        "property_details": property_data,
                        "district_analysis_text": district_analysis
                    }
                    cot_response = await self.cot_agent.enhance_response_with_reasoning(
                        original_response=summary,
                        analysis_type="property_analysis",
                        data=cot_data,
                        user_query=message
                    )
                    cot_validation = self.validator.validate_response(cot_response)
                    if cot_validation["is_valid"]:
                        final_response = cot_response
                    else:
                        logger.warning("CoT response validation failed, using summary")
                except Exception as e:
                    logger.warning(f"CoT enhancement failed: {e}")
            self.last_property_context = {
                "property_data": property_data,
                "district_analysis_string": district_analysis,
                "user_query": message,
                "url": url,
                "timestamp": datetime.now().isoformat()
            }
            self._clear_other_contexts("property")
            return {
                "response": final_response + "\n\nТайлан үүсгэх үү?\nПDF тайлан үүсгэхийг хүсвэл Тийм гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Property handling error: {e}")
            return {
                "response": "Үл хөдлөх хөрөнгийн мэдээлэл боловсруулахад алдаа гарлаа.",
                "offer_report": False,
                "status": "error"
            }
    async def _generate_property_summary_with_validation(self, query: str, property_data: Dict,
                                                         district_analysis: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та үл хөдлөх хөрөнгийн мэргэжилтэн. 

            ШААРДЛАГА:
            - ЗӨВХӨН монгол хэлээр бичнэ үү
            - Англи үг хэрэглэхгүй байх
            - 150 үгээс хэтрэхгүй байх
            - Давтан бичихгүй байх
            - Тодорхой мэдээлэл өгнө үү"""),
            ("human", "Орон сууц: {property}\nДүүрэг: {district}\n\nТовч дүгнэлт өгнө үү.")
        ])
        try:
            chain = prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({
                "property": json.dumps(property_data, ensure_ascii=False, indent=2)[:500],
                "district": district_analysis[:300]
            })
            validation = self.validator.validate_response(response)
            if validation["is_valid"]:
                return validation.get("cleaned_text", response)
            else:
                return self._generate_safe_property_fallback(property_data)
        except Exception as e:
            logger.error(f"Property summary generation failed: {e}")
            return self._generate_safe_property_fallback(property_data)
    def _generate_safe_property_fallback(self, property_data: Dict) -> str:
        title = property_data.get('title', 'Орон сууц')[:50]
        price = property_data.get('price_raw', 'Тодорхойгүй')
        area = property_data.get('area_sqm', 'Тодорхойгүй')
        return f"""**Орон сууцны мэдээлэл**

**Гарчиг:** {title}
**Үнэ:** {price}
**Талбай:** {area} м²

Дэлгэрэнгүй шинжилгээний тулд дахин асууна уу."""
    async def _handle_market(self, message: str, use_cot: bool) -> Dict[str, Any]:
        logger.info(f"Processing market query: {message[:50]}...")
        try:
            search_query = f"Mongolia real estate market trends {message}"
            search_results = await self.search_tool.ainvoke(search_query)
            if not search_results:
                return {
                    "response": "Зах зээлийн мэдээлэл хайлтаас олдсонгүй.",
                    "offer_report": False,
                    "status": "no_data"
                }
            search_content = self._process_search_results(search_results)
            if not search_content:
                return {
                    "response": "Зах зээлийн боловсруулах мэдээлэл олдсонгүй.",
                    "offer_report": False,
                    "status": "no_data"
                }
            analysis = await self._generate_market_analysis_with_validation(message, search_content)
            final_response = analysis
            if use_cot:
                try:
                    cot_data = {"search_results_text": search_content, "user_query": message}
                    cot_response = await self.cot_agent.enhance_response_with_reasoning(
                        original_response=analysis,
                        analysis_type="market_analysis",
                        data=cot_data,
                        user_query=message
                    )
                    cot_validation = self.validator.validate_response(cot_response)
                    if cot_validation["is_valid"]:
                        final_response = cot_response
                except Exception as e:
                    logger.warning(f"CoT enhancement failed: {e}")
            self.last_market_context = {
                "query": message,
                "search_content": search_content,
                "generated_analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }
            self._clear_other_contexts("market")
            return {
                "response": final_response + "\n\n Тайлан үүсгэх үү?\nЗах зээлийн PDF тайлан үүсгэхийг хүсвэл Тийм гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Market handling error: {e}")
            return {
                "response": "Зах зээлийн мэдээлэл боловсруулахад алдаа гарлаа.",
                "offer_report": False,
                "status": "error"
            }
    async def _generate_market_analysis_with_validation(self, query: str, search_content: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та үл хөдлөх хөрөнгийн зах зээлийн судлаач. 

            ШААРДЛАГА:
            - ЗӨВХӨН монгол хэлээр бичнэ үү
            - Англи үг хэрэглэхгүй байх
            - 120 үгээс хэтрэхгүй байх
            - Давтан бичихгүй байх"""),
            ("human", "Асуулт: {query}\nМэдээлэл: {content}\n\nЗах зээлийн шинжилгээ өгнө үү.")
        ])
        try:
            chain = prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({
                "query": query,
                "content": search_content[:2000]
            })
            validation = self.validator.validate_response(response)
            if validation["is_valid"]:
                return validation.get("cleaned_text", response)
            else:
                return "Зах зээлийн одоогийн мэдээллээр дэлгэрэнгүй шинжилгээ хийх боломжгүй байна. Дахин асууна уу."
        except Exception as e:
            logger.error(f"Market analysis generation failed: {e}")
            return "Зах зээлийн шинжилгээ үүсгэхэд алдаа гарлаа."
    async def _handle_general(self, message: str) -> Dict[str, Any]:
        logger.info(f"Processing general query: {message[:50]}...")
        try:
            search_results = await self.search_tool.ainvoke(message)
            if not search_results:
                return {
                    "response": "Уучлаарай, таны асуултын хариу олдсонгүй.",
                    "offer_report": False,
                    "status": "no_data"
                }
            search_content = self._process_search_results(search_results)
            if search_content:
                response = await self._generate_general_response_with_validation(message, search_content)
            else:
                response = "Хайлтын үр дүнг боловсруулахад алдаа гарлаа."
            return {
                "response": response,
                "offer_report": False,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"General handling error: {e}")
            return {
                "response": "Ерөнхий асуултад хариулахад алдаа гарлаа.",
                "offer_report": False,
                "status": "error"
            }
    async def _generate_general_response_with_validation(self, query: str, search_content: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та туслах робот. 

            ШААРДЛАГА:
            - ЗӨВХӨН монгол хэлээр бичнэ үү
            - Англи үг хэрэглэхгүй байх
            - 100 үгээс хэтрэхгүй байх
            - Тодорхой хариулт өгнө үү"""),
            ("human", "Асуулт: {query}\nМэдээлэл: {content}\n\nХариулт өгнө үү.")
        ])
        try:
            chain = prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({
                "query": query,
                "content": search_content[:1500]
            })
            validation = self.validator.validate_response(response)
            if validation["is_valid"]:
                return validation.get("cleaned_text", response)
            else:
                return "Таны асуултын хариуг одоогоор өгөх боломжгүй байна. Өөрөөр асууж үзнэ үү."
        except Exception as e:
            logger.error(f"General response generation failed: {e}")
            return "Хариулт үүсгэхэд алдаа гарлаа."
    async def _generate_report(self) -> Dict[str, Any]:
        try:
            contexts = [
                ("property", self.last_property_context),
                ("district", self.last_district_context),
                ("market", self.last_market_context)
            ]
            recent_context = None
            recent_type = None
            recent_time = datetime.min
            for context_type, context in contexts:
                if context and "timestamp" in context:
                    try:
                        context_time = datetime.fromisoformat(context["timestamp"])
                        if context_time > recent_time:
                            recent_time = context_time
                            recent_context = context
                            recent_type = context_type
                    except ValueError:
                        continue
            if not recent_context:
                return {
                    "response": "Тайлан үүсгэх контекст олдсонгүй. Эхлээд шинжилгээ хийлгэнэ үү.",
                    "offer_report": False
                }
            if recent_type == "property":
                result = await self.report_service.generate_property_report(recent_context)
            elif recent_type == "district":
                result = await self.report_service.generate_district_report(recent_context)
            elif recent_type == "market":
                result = await self.report_service.generate_market_report(recent_context)
            else:
                return {
                    "response": "Тодорхойгүй тайлангийн төрөл.",
                    "offer_report": False
                }
            if recent_type == "property":
                self.last_property_context = None
            elif recent_type == "district":
                self.last_district_context = None
            elif recent_type == "market":
                self.last_market_context = None
            return result if isinstance(result, dict) else {
                "response": "Тайлан үүсгэхэд алдаа гарлаа.",
                "offer_report": False
            }
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            return {
                "response": "Тайлан үүсгэхэд алдаа гарлаа.",
                "offer_report": False
            }
    def _process_search_results(self, results) -> str:
        if not results:
            return ""
        content_parts = []
        seen_content = set()
        if isinstance(results, list):
            for result in results[:3]:
                if isinstance(result, dict):
                    content = result.get('content', '') or result.get('snippet', '')
                    if content and len(content) > 30 and content not in seen_content:
                        content = re.sub(r'<[^>]+>', '', content)
                        content = re.sub(r'\s+', ' ', content).strip()
                        if len(content) > 300:
                            content = content[:300] + "..."
                        content_parts.append(content)
                        seen_content.add(content)
        elif isinstance(results, dict):
            if "answer" in results:
                content_parts.append(str(results["answer"])[:500])
            elif "content" in results:
                content_parts.append(str(results["content"])[:500])
        return "\n\n".join(content_parts)
    def _clear_other_contexts(self, keep_type: str):
        if keep_type != "property":
            self.last_property_context = None
        if keep_type != "district":
            self.last_district_context = None
        if keep_type != "market":
            self.last_market_context = None