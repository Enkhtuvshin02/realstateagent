import logging
import re
import json
from typing import Dict, Any
from datetime import datetime  # Ensure this is imported
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.report_service import ReportService
from agents.chain_of_thought_agent import ChainOfThoughtAgent

# from agents.district_analyzer import DistrictAnalyzer # For type hinting if needed

logger = logging.getLogger(__name__)

REPORT_KEYWORDS = ['тийм', 'yes', 'тайлан', 'report']
DISTRICT_NAMES = ["хан-уул", "баянгол", "сүхбаатар", "чингэлтэй", "баянзүрх", "сонгинохайрхан"]
COMPARISON_KEYWORDS = ['бүх дүүрэг', 'дүүрэг харьцуулах', 'дүүргүүд', 'харьцуулах', 'compare all districts',
                       'compare districts']


class ChatService:

    def __init__(self, llm, search_tool, property_retriever, district_analyzer, pdf_generator):
        self.llm = llm
        self.search_tool = search_tool
        self.property_retriever = property_retriever
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator

        self.report_service = ReportService(llm, district_analyzer, pdf_generator, search_tool)
        self.cot_agent = ChainOfThoughtAgent(llm)
        self.last_property_analysis_context = None
        self.last_district_analysis_context = None
        self.last_market_analysis_context = None


    async def process_message(self, user_message: str) -> Dict[str, Any]:
        logger.info(f"Processing message: {user_message[:100]}...")
        try:
            if self._wants_report(user_message):
                return await self._generate_report(user_message)

            message_type = self._classify_message(user_message)
            use_cot = len(user_message) > 20 or message_type in ['property', 'district', 'district_comparison',
                                                                 'market']

            if message_type == 'property':
                return await self._handle_property(user_message, use_cot)
            elif message_type == 'district' or message_type == 'district_comparison':
                return await self._handle_district(user_message, use_cot, message_type)
            elif message_type == 'market':
                return await self._handle_market(user_message, use_cot)
            else:  # general
                return await self._handle_general(user_message)

        except Exception as e:
            logger.exception(f"Error processing message: {user_message[:100]}")
            return {"response": "Уучлаарай, таны хүсэлтийг боловсруулахад алдаа гарлаа. Дахин оролдоно уу.",
                    "offer_report": False}

    def _classify_message(self, message: str) -> str:
        message_lower = message.lower()
        if re.search(r'https?://\S+', message):
            logger.debug("Classified message as 'property' due to URL.")
            return 'property'

        if any(keyword in message_lower for keyword in COMPARISON_KEYWORDS):
            logger.debug("Classified message as 'district_comparison'.")
            return 'district_comparison'

        if any(district in message_lower for district in DISTRICT_NAMES):
            logger.debug(f"Classified message as 'district' due to district name: {message_lower}.")
            return 'district'

        market_keywords = ['зах зээл', 'үнийн чиглэл', 'market', 'тренд', 'статистик', 'хэтийн төлөв', 'төлөв байдал']
        if any(keyword in message_lower for keyword in market_keywords):
            logger.debug("Classified message as 'market'.")
            return 'market'

        logger.debug("Classified message as 'general'.")
        return 'general'

    def _wants_report(self, message: str) -> bool:
        message_lower = message.lower().strip()
        is_report_request = any(keyword == message_lower for keyword in REPORT_KEYWORDS) or \
                            (message_lower.startswith("тийм") and len(message_lower) < 10) or \
                            (message_lower.startswith("yes") and len(message_lower) < 10)

        if is_report_request and (
                self.last_property_analysis_context or self.last_district_analysis_context or self.last_market_analysis_context):
            logger.info("User wants a report based on previous context.")
            return True
        logger.debug(
            f"Message '{message_lower}' not identified as a direct report request or no prior context for report.")
        return False

    async def _handle_property(self, message: str, use_cot: bool) -> Dict[str, Any]:
        url_match = re.search(r'https?://\S+', message)
        if not url_match:
            return {"response": "Орон сууцны мэдээлэл авахын тулд URL хаягийг оруулна уу.", "offer_report": False}

        url = url_match.group(0)
        logger.info(f"Handling property URL: {url}")

        logger.info("Before fetching district analysis for property, current vectorstore state:")
        self._log_district_analyzer_vectorstore_content()

        try:
            property_data = await self.property_retriever.retrieve_property_details(url)
            if not property_data or property_data.get("error"):
                error_msg = property_data.get("error", "Үл хөдлөх хөрөнгийн мэдээллийг авахад алдаа гарлаа.")
                logger.error(f"Error retrieving property data from {url}: {error_msg}")
                return {"response": f"Алдаа: {error_msg}", "offer_report": False}

            district_name = property_data.get("district")
            district_analysis_str = "Дүүргийн мэдээлэл олдсонгүй."
            if district_name and isinstance(district_name, str) and district_name.lower() != 'n/a':
                logger.info(f"Fetching district analysis for: {district_name}")
                district_analysis_str = await self.district_analyzer.analyze_district(district_name)
            else:
                logger.warning(
                    f"No valid district found for property at {url}. Property data district: {district_name}")

            summary_response = await self._generate_property_response(message, property_data, district_analysis_str)

            final_response = summary_response
            if use_cot:
                logger.info(f"Enhancing property response with CoT for query: {message[:50]}...")
                cot_input_data = {
                    "property_details": property_data,
                    "district_analysis_text": district_analysis_str  # This is the string passed to CoT
                }
                final_response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=summary_response,
                    analysis_type="property_analysis",
                    data=cot_input_data,
                    user_query=message
                )

            self.last_property_analysis_context = {
                "property_data": property_data,
                "district_analysis_string": district_analysis_str,  # Stored with this key
                "user_query": message,
                "url": url,
                "timestamp": datetime.now().isoformat()
            }
            self.last_district_analysis_context = None
            self.last_market_analysis_context = None

            return {
                "response": final_response + "\n\nТайлан үүсгэх үү?\nДээрх үл хөдлөх хөрөнгийн талаар PDF тайлан үүсгэхийг хүсвэл Тийм эсвэл Тайлан гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot
            }

        except Exception as e:
            logger.exception(f"Error handling property message for URL {url}")
            return {"response": "Уучлаарай, үл хөдлөх хөрөнгийн мэдээллийг боловсруулахад алдаа гарлаа.",
                    "offer_report": False}

    async def _handle_district(self, message: str, use_cot: bool, message_type: str) -> Dict[str, Any]:
        logger.info(f"Handling district query ({message_type}): {message[:50]}...")

        logger.info("Before analyzing district(s), current vectorstore state:")
        self._log_district_analyzer_vectorstore_content()

        try:
            analysis_type_for_cot = "district_analysis"  # Default
            base_response = ""
            cot_input_data = {}

            if message_type == "district_comparison":
                district_data_summary = await self.district_analyzer.analyze_district(message)
                analysis_type_for_cot = "district_comparison"
                base_response = district_data_summary
                cot_input_data = {"district_comparison_summary": district_data_summary, "user_query": message}
            else:  # specific district
                district_analysis_str = await self.district_analyzer.analyze_district(message)
                base_response = await self._generate_district_response(message, district_analysis_str)
                cot_input_data = {"district_analysis_text": district_analysis_str, "user_query": message}

            final_response = base_response
            if use_cot:
                logger.info(f"Enhancing district response with CoT for query: {message[:50]}...")
                final_response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=base_response,
                    analysis_type=analysis_type_for_cot,
                    data=cot_input_data,
                    user_query=message
                )

            self.last_district_analysis_context = {
                "type": message_type,
                "query": message,
                "analysis_content": base_response,
                "timestamp": datetime.now().isoformat()
            }
            if message_type == "district_comparison" and "district_comparison_summary" in cot_input_data:
                self.last_district_analysis_context["comparison_data_for_report"] = cot_input_data[
                    "district_comparison_summary"]
            elif message_type == "district" and "district_analysis_text" in cot_input_data:
                self.last_district_analysis_context["single_district_text_for_report"] = cot_input_data[
                    "district_analysis_text"]

            self.last_property_analysis_context = None
            self.last_market_analysis_context = None

            return {
                "response": final_response + "\n\n Тайлан үүсгэх үү?\nДүүргийн мэдээллийн талаар PDF тайлан үүсгэхийг хүсвэл Тийм эсвэл Тайлан гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot
            }
        except Exception as e:
            logger.exception(f"Error handling district message: {message[:50]}")
            return {"response": "Уучлаарай, дүүргийн мэдээллийг боловсруулахад алдаа гарлаа.", "offer_report": False}

    async def _handle_market(self, message: str, use_cot: bool) -> Dict[str, Any]:
        logger.info(f"Handling market query: {message[:50]}...")
        try:
            logger.debug(f"Performing Tavily search for market query: {message}")
            search_results_raw = self.search_tool.invoke({"query": f"Mongolia real estate market trends {message}"})

            search_content = ""
            if isinstance(search_results_raw, list):
                for res in search_results_raw:
                    if isinstance(res, dict) and "content" in res:
                        search_content += res["content"] + "\n\n"
            elif isinstance(search_results_raw,
                            dict) and "answer" in search_results_raw:  # Tavily can return a direct answer
                search_content = search_results_raw["answer"]
            else:
                search_content = str(search_results_raw)

            if not search_content.strip():
                logger.warning(f"No content found from Tavily search for market query: {message}")
                no_data_response = "Зах зээлийн талаарх одоогийн хайлтын илэрц хоосон байна. Та асуулгаа өөрөөр лавлана уу."
                return {"response": no_data_response, "offer_report": False}

            logger.debug(f"Tavily search content length: {len(search_content)}")
            base_response = await self._generate_market_response(message, search_content)

            final_response = base_response
            if use_cot:
                logger.info(f"Enhancing market response with CoT for query: {message[:50]}...")
                cot_input_data = {"search_results_text": search_content, "user_query": message}
                final_response = await self.cot_agent.enhance_response_with_reasoning(
                    original_response=base_response,
                    analysis_type="market_analysis",
                    data=cot_input_data,
                    user_query=message
                )

            self.last_market_analysis_context = {
                "query": message,
                "search_content": search_content,  # Store the raw search content
                "generated_analysis": base_response,  # Store the initial LLM summary of search_content
                "timestamp": datetime.now().isoformat()
            }
            self.last_property_analysis_context = None
            self.last_district_analysis_context = None

            return {
                "response": final_response + "\n\n📈 Тайлан үүсгэх үү?\nЗах зээлийн мэдээллийн талаар PDF тайлан үүсгэхийг хүсвэл Тийм эсвэл Тайлан гэж бичнэ үү.",
                "offer_report": True,
                "cot_enhanced": use_cot
            }
        except Exception as e:
            logger.exception(f"Error handling market message: {message[:50]}")
            return {"response": "Уучлаарай, зах зээлийн мэдээллийг боловсруулахад алдаа гарлаа.", "offer_report": False}

    async def _handle_general(self, message: str) -> Dict[str, Any]:
        logger.info(f"Handling general query: {message[:50]}...")
        try:
            logger.debug(f"Performing Tavily search for general query: {message}")
            search_results_raw = self.search_tool.invoke({"query": message})

            search_content = ""
            if isinstance(search_results_raw, list):
                for res in search_results_raw:
                    if isinstance(res, dict) and "content" in res:
                        search_content += res["content"] + "\n\n"
            elif isinstance(search_results_raw, dict) and "answer" in search_results_raw:
                search_content = search_results_raw["answer"]
            else:
                search_content = str(search_results_raw)

            if not search_content.strip():
                logger.warning(f"No content found from Tavily search for general query: {message}")
                return {"response": "Уучлаарай, таны асуултын дагуу мэдээлэл олдсонгүй. Та өөрөөр лавлаж үзнэ үү.",
                        "offer_report": False}

            logger.debug(
                f"Tavily search content for general query (length {len(search_content)}): {search_content[:200]}...")
            response = await self._generate_general_response(message, search_content)
            return {"response": response, "offer_report": False}

        except Exception as e:
            logger.exception(f"Error handling general message: {message[:50]}")
            return {"response": "Уучлаарай, ерөнхий асуултад хариулахад алдаа гарлаа.", "offer_report": False}

    async def _generate_report(self, user_message: str) -> Dict[
        str, Any]:  # Added user_message to potentially guide report type
        logger.info("Report generation requested.")
        report_type_determined = None
        try:
            # Determine which context is most recent and relevant
            last_prop_time = datetime.min
            last_dist_time = datetime.min
            last_mark_time = datetime.min

            if self.last_property_analysis_context and "timestamp" in self.last_property_analysis_context:
                try:
                    last_prop_time = datetime.fromisoformat(self.last_property_analysis_context["timestamp"])
                except ValueError:
                    logger.error(
                        f"Invalid timestamp in prop context: {self.last_property_analysis_context['timestamp']}")

            if self.last_district_analysis_context and "timestamp" in self.last_district_analysis_context:
                try:
                    last_dist_time = datetime.fromisoformat(self.last_district_analysis_context["timestamp"])
                except ValueError:
                    logger.error(
                        f"Invalid timestamp in dist context: {self.last_district_analysis_context['timestamp']}")

            if self.last_market_analysis_context and "timestamp" in self.last_market_analysis_context:
                try:
                    last_mark_time = datetime.fromisoformat(self.last_market_analysis_context["timestamp"])
                except ValueError:
                    logger.error(
                        f"Invalid timestamp in market context: {self.last_market_analysis_context['timestamp']}")

            # Choose the most recent context if user just says "yes"
            if self.last_property_analysis_context and last_prop_time >= last_dist_time and last_prop_time >= last_mark_time:
                report_type_determined = "property"
                logger.info(
                    f"Generating property report based on last context: {self.last_property_analysis_context.get('url', 'N/A')}")
                result = await self.report_service.generate_property_report(self.last_property_analysis_context)
            elif self.last_district_analysis_context and last_dist_time >= last_mark_time:
                report_type_determined = "district"
                logger.info(
                    f"Generating district report based on last context: {self.last_district_analysis_context.get('query', 'N/A')}")
                result = await self.report_service.generate_district_report(
                    self.last_district_analysis_context)  # Pass context
            elif self.last_market_analysis_context:
                report_type_determined = "market"
                logger.info(
                    f"Generating market report based on last context: {self.last_market_analysis_context.get('query', 'N/A')}")
                result = await self.report_service.generate_market_report(
                    self.last_market_analysis_context)  # Pass context
            else:
                logger.warning("Report requested, but no relevant context found.")
                return {
                    "response": "Уучлаарай, ямар тайлан үүсгэх нь тодорхойгүй байна. Та эхлээд дүн шинжилгээ хийлгэнэ үү.",
                    "offer_report": False}

            # Clear the context used for the report
            if report_type_determined == "property":
                self.last_property_analysis_context = None
            elif report_type_determined == "district":
                self.last_district_analysis_context = None
            elif report_type_determined == "market":
                self.last_market_analysis_context = None

            if isinstance(result, dict) and result.get("success"):
                logger.info(f"Report generated successfully: {result.get('filename')}")
                return {
                    "response": result["message"],
                    "download_url": result.get("download_url"),
                    "filename": result.get("filename"),
                    "offer_report": False
                }
            else:
                error_message = result.get("message", "Тайлан үүсгэхэд тодорхойгүй алдаа гарлаа.")
                logger.error(f"Report generation failed: {error_message}")
                return {"response": error_message, "offer_report": False}

        except Exception as e:
            logger.exception("Critical error during report generation dispatcher")
            return {"response": "Уучлаарай, тайлан үүсгэх явцад ноцтой алдаа гарлаа.", "offer_report": False}

    async def _get_district_analysis(self, district: str) -> str:  # Keep this for potential direct use
        if district and isinstance(district, str) and district.lower() != "n/a":
            logger.info(f"Getting district analysis for: {district} (via _get_district_analysis helper)")
            return await self.district_analyzer.analyze_district(district)
        logger.warning(f"District name invalid or N/A in _get_district_analysis: '{district}'")
        return "Дүүргийн мэдээлэл тодорхойгүй байна."

    async def _generate_property_response(self, query: str, property_data: Dict, district_analysis_str: str) -> str:
        logger.debug(f"Generating initial property response. Property title: {property_data.get('title', 'N/A')[:50]}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate expert. Analyze this property and provide valuable insights for a property summary.

Focus on:
1. Price evaluation (Summary):
   - From the 'Property details', identify the property's specific price per square meter (price/m²).
   - From the 'District analysis', identify the average price/m² for similar properties (e.g., same number of rooms) in its district.
   - Briefly state if the property's price/m² is higher, lower, or similar to the district average for its type.
   - Conclude if the asking price seems fair, high, or low based on this comparison.
2. Key location benefits and potential drawbacks (from 'Property details' and 'District analysis').
3. Brief investment potential note (e.g., "good for investment due to location", "price suggests quick sale").
4. One or two key recommendations for the user.

Keep the summary concise, using key numbers. This is not the full detailed analysis yet.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human",
             "User query: {query}\nProperty details: {property_json}\nDistrict analysis: {district_analysis_text}\n\nProvide a concise property summary analysis in Mongolian.")
        ])
        chain = prompt | self.llm | StrOutputParser()
        property_json_str = json.dumps(property_data, ensure_ascii=False, indent=2)

        return await chain.ainvoke({
            "query": query,
            "property_json": property_json_str,
            "district_analysis_text": district_analysis_str
        })

    async def _generate_district_response(self, query: str, district_analysis_str: str) -> str:
        logger.debug(f"Generating initial district response for query: {query[:50]}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate market analyst. Provide a clear summary of the district analysis.
Respond strictly based on the provided 'District analysis text'. Do NOT include any external or generalized information.

Focus on summarizing:
1. Current price levels with numbers if available in the text.
2. Comparison to other districts if mentioned.
3. Investment opportunities or characteristics noted.
4. Who might be interested in this district (e.g., families, investors) if suggested by the text.
5. Any future outlook or trends mentioned.

Keep the summary concise.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human",
             "User query: {query}\nDistrict analysis text: {analysis_text}\n\nProvide a district analysis summary in Mongolian.")
        ])
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"query": query, "analysis_text": district_analysis_str})

    async def _generate_market_response(self, query: str, search_results_text: str) -> str:
        logger.debug(f"Generating initial market response for query: {query[:50]}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate market researcher. Summarize the provided search results to give market insights.
Respond strictly based on the 'Search results text'. Do NOT include external or generalized information.

Focus on summarizing:
1. Current market conditions mentioned.
2. Price trends with specifics if detailed in the text.
3. Investment opportunities or risks highlighted.
4. Actionable recommendations if any are present in the text.

Keep the summary concise and directly tied to the provided text.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human",
             "User query: {query}\nSearch results text: {results_text}\n\nProvide a market analysis summary in Mongolian based on the text.")
        ])
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"query": query, "results_text": search_results_text})

    async def _generate_general_response(self, query: str, search_results_text: Any) -> str:
        logger.debug(f"Generating general response for query: {query[:50]}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant specializing in providing information based on search results, with a focus on real estate topics when relevant.
Provide a clear, helpful answer to the user's question based strictly on the provided 'Search results text'.
Do NOT include any external or generalized information, or unrelated examples.

If the question is about real estate in Mongolia, use that context.
Provide:
- A direct answer to the user's question.
- Relevant facts and data from the text.
- Practical advice if applicable and supported by the text.

Keep the answer concise and informative.
IMPORTANT: Respond ONLY in Mongolian language."""),
            ("human",
             "User question: {query}\nSearch results text: {results_text}\n\nProvide an answer in Mongolian based on the text.")
        ])

        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"query": query, "results_text": str(search_results_text)})

    def _log_district_analyzer_vectorstore_content(self):
        """Helper function to log the current content of DistrictAnalyzer's vectorstore."""
        if not self.district_analyzer or not self.district_analyzer.vectorstore:
            logger.info("VECTORSTORE_DEBUG: DistrictAnalyzer or its vectorstore is not initialized or available.")
            return

        try:
            if hasattr(self.district_analyzer.vectorstore, 'docstore') and \
                    hasattr(self.district_analyzer.vectorstore.docstore, '_dict') and \
                    self.district_analyzer.vectorstore.docstore._dict is not None:  # Added check for _dict not None
                all_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
                logger.info(f"VECTORSTORE_DEBUG: Current DistrictAnalyzer.vectorstore ({len(all_docs)} documents):")
                if not all_docs:
                    logger.info("VECTORSTORE_DEBUG: Vectorstore is empty.")
                for i, doc in enumerate(all_docs):
                    logger.info(f"VECTORSTORE_DEBUG: Document {i + 1}:\n{doc.page_content}\n---")
            else:
                logger.info(
                    "VECTORSTORE_DEBUG: Vectorstore docstore not in expected format for direct listing or is empty.")
        except Exception as e:
            logger.error(f"VECTORSTORE_DEBUG: Error logging vectorstore content: {e}", exc_info=True)
