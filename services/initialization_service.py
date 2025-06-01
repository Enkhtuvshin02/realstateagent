# services/initialization_service.py
import os
import logging
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

    async def initialize(self):
        """Initialize all components"""
        logger.info("🔧 Initializing services...")

        # Check API keys
        together_api_key = os.getenv("TOGETHER_API_KEY")
        tavily_api_key = os.getenv("TAVILY_API_KEY")

        if not together_api_key:
            raise ValueError("TOGETHER_API_KEY is not set in environment variables")
        if not tavily_api_key:
            raise ValueError("TAVILY_API_KEY is not set in environment variables")

        # Initialize LLM
        logger.info("🤖 Initializing LLM...")
        self.llm = ChatTogether(
            together_api_key=together_api_key,
            model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
            temperature=0.7
        )
        logger.info("✅ LLM initialized")

        # Initialize search tool
        logger.info("🔍 Initializing search tool...")
        self.search_tool = TavilySearchResults(
            max_results=5,
            search_depth="advanced",
            include_answer=True,
            tavily_api_key=tavily_api_key
        )
        logger.info("✅ Search tool initialized")

        # Initialize agents
        logger.info("🏠 Initializing property retriever...")
        self.property_retriever_agent = PropertyRetriever(llm=self.llm)
        logger.info("✅ Property retriever initialized")

        logger.info("📊 Initializing district analyzer...")
        self.district_analyzer_agent = DistrictAnalyzer(
            llm=self.llm,
            property_retriever=self.property_retriever_agent
        )
        logger.info("✅ District analyzer initialized")

        # Initialize PDF generator
        logger.info("📄 Initializing PDF generator...")
        self.pdf_generator = PDFReportGenerator()
        logger.info("✅ PDF generator initialized")

        # Load initial data
        await self._load_initial_data()

    async def _load_initial_data(self):
        """Load initial data for district analyzer"""
        logger.info("📚 Loading initial data...")

        try:
            cache_status = self.district_analyzer_agent.get_cache_status()
            logger.info(f"📊 Cache status: {cache_status}")

            if not cache_status["is_fresh"]:
                logger.info("🔄 Cache is stale, loading fresh data...")
                await self.district_analyzer_agent.update_with_realtime_data(force_update=True)
                logger.info("✅ Fresh data loaded")
            else:
                logger.info("📅 Using cached data (fresh)")

        except Exception as e:
            logger.error(f"❌ Failed to load initial data: {e}")
            logger.info("📚 Continuing with static fallback data")

    async def cleanup(self):
        """Cleanup resources"""
        if self.property_retriever_agent:
            await self.property_retriever_agent.close()
            logger.info("🧹 Property retriever closed")