# Improved initialization_service.py
import os
import time
import logging
import traceback
from langchain_together import ChatTogether
from langchain_community.tools.tavily_search import TavilySearchResults

from agents.property_retriever import PropertyRetriever
from agents.district_analyzer import DistrictAnalyzer
from utils.pdf_generator import PDFReportGenerator

logger = logging.getLogger(__name__)


class InitializationService:
    def __init__(self):
        self.llm = None
        self.search_tool = None
        self.property_retriever_agent = None
        self.district_analyzer_agent = None
        self.pdf_generator = None

    async def initialize(self) -> bool:
        """Initialize all services with improved error handling"""
        logger.info("Starting service initialization...")

        try:
            # Validate API keys
            if not self._validate_api_keys():
                raise ValueError("Required API keys not found")

            # Initialize core components
            await self._initialize_llm()
            await self._initialize_search_tool()
            await self._initialize_property_retriever()
            await self._initialize_district_analyzer()
            await self._initialize_pdf_generator()

            # Initialize vectorstore
            await self._initialize_vectorstore()

            logger.info("All services initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            logger.error(traceback.format_exc())
            return False

    def _validate_api_keys(self) -> bool:
        """Validate required API keys"""
        required_keys = ["TOGETHER_API_KEY", "TAVILY_API_KEY"]
        missing_keys = [key for key in required_keys if not os.getenv(key)]

        if missing_keys:
            logger.error(f"Missing API keys: {missing_keys}")
            return False

        return True

    async def _initialize_llm(self):
        """Initialize LLM with error handling"""
        try:
            self.llm = ChatTogether(
                together_api_key=os.getenv("TOGETHER_API_KEY"),
                model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
                temperature=0.7
            )
            logger.info("LLM initialized successfully")
        except Exception as e:
            logger.error(f"LLM initialization failed: {e}")
            raise

    async def _initialize_search_tool(self):
        """Initialize search tool with monitoring and fallback"""
        try:
            # Create base search tool
            self.search_tool = TavilySearchResults(
                max_results=5,
                search_depth="advanced",
                include_answer=True,
                tavily_api_key=os.getenv("TAVILY_API_KEY")
            )

            # Wrap with monitoring

            # Test the search tool
            await self._test_search_tool()
            logger.info("Search tool initialized and tested successfully")

        except Exception as e:
            logger.error(f"Search tool initialization failed: {e}")
            # Create fallback search tool
            self.search_tool = self._create_fallback_search_tool()
            logger.warning("Using fallback search tool")

    async def _test_search_tool(self):
        """Test search tool functionality"""
        try:
            test_results = await self.search_tool.ainvoke("test query")
            if not test_results:
                raise Exception("Search tool returned no results")
        except Exception as e:
            logger.warning(f"Search tool test failed: {e}")
            raise

    def _create_fallback_search_tool(self):
        """Create a fallback search tool that returns error messages"""

        class FallbackSearchTool:
            async def ainvoke(self, query, *args, **kwargs):
                logger.warning(f"Fallback search called for: {query}")
                return [{
                    "content": "Хайлтын үйлчилгээ одоогоор ажиллахгүй байна.",
                    "title": "Хайлтын алдаа"
                }]

        return FallbackSearchTool()

    async def _initialize_property_retriever(self):
        """Initialize property retriever"""
        try:
            self.property_retriever_agent = PropertyRetriever(llm=self.llm)
            logger.info("Property retriever initialized successfully")
        except Exception as e:
            logger.error(f"Property retriever initialization failed: {e}")
            raise

    async def _initialize_district_analyzer(self):
        """Initialize district analyzer"""
        try:
            self.district_analyzer_agent = DistrictAnalyzer(
                llm=self.llm,
                property_retriever=self.property_retriever_agent,
                search_tool=self.search_tool
            )
            logger.info("District analyzer initialized successfully")
        except Exception as e:
            logger.error(f"District analyzer initialization failed: {e}")
            raise

    async def _initialize_pdf_generator(self):
        """Initialize PDF generator"""
        try:
            self.pdf_generator = PDFReportGenerator()
            logger.info("PDF generator initialized successfully")
        except Exception as e:
            logger.error(f"PDF generator initialization failed: {e}")
            raise

    async def _initialize_vectorstore(self):
        """Initialize vectorstore with proper error handling"""
        try:
            logger.info("Initializing district analyzer vectorstore...")
            start_time = time.time()

            # Initialize vectorstore
            success = await self.district_analyzer_agent.initialize_vectorstore()

            duration = time.time() - start_time
            if success:
                logger.info(f"Vectorstore initialized successfully in {duration:.2f}s")

                # Log vectorstore status
                status = self.district_analyzer_agent.get_vectorstore_status()
                logger.info(f"Vectorstore status: {status}")

                if status.get("document_count", 0) == 0:
                    logger.warning("Vectorstore is empty - search fallback will be used")
                else:
                    logger.info(f"Vectorstore contains {status['document_count']} documents")
            else:
                logger.warning(f"Vectorstore initialization partially failed in {duration:.2f}s")
                logger.warning("System will rely more heavily on search fallback")

        except Exception as e:
            logger.error(f"Vectorstore initialization error: {e}")
            logger.error(traceback.format_exc())
            logger.warning("Continuing without vectorstore - search fallback will be used")

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.property_retriever_agent:
                await self.property_retriever_agent.close()
                logger.info("Property retriever closed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def get_initialization_status(self) -> dict:
        """Get status of all initialized components"""
        return {
            "llm": self.llm is not None,
            "search_tool": self.search_tool is not None,
            "property_retriever": self.property_retriever_agent is not None,
            "district_analyzer": self.district_analyzer_agent is not None,
            "pdf_generator": self.pdf_generator is not None,
            "vectorstore": (
                    self.district_analyzer_agent is not None and
                    hasattr(self.district_analyzer_agent, "vectorstore") and
                    self.district_analyzer_agent.vectorstore is not None
            )
        }