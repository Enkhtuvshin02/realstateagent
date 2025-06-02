import os
import logging
from langchain_together import ChatTogether
from langchain_community.tools.tavily_search import TavilySearchResults

from agents.property_retriever import PropertyRetriever
# Make sure the import path for DistrictAnalyzer is correct if file names changed
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
        logger.info("Initializing services...")

        together_api_key = os.getenv("TOGETHER_API_KEY")
        tavily_api_key = os.getenv("TAVILY_API_KEY")

        if not together_api_key:
            raise ValueError("TOGETHER_API_KEY environment variable is not set")
        if not tavily_api_key:
            raise ValueError("TAVILY_API_KEY environment variable is not set")

        self.llm = ChatTogether(
            together_api_key=together_api_key,
            model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
            temperature=0.7
        )
        logger.info("LLM initialized")

        self.search_tool = TavilySearchResults(
            max_results=5,
            search_depth="advanced",
            include_answer=True,
            tavily_api_key=tavily_api_key
        )
        logger.info("Search tool initialized")

        self.property_retriever_agent = PropertyRetriever(llm=self.llm)
        logger.info("Property retriever initialized")

        # Create DistrictAnalyzer instance; its vectorstore will be initialized in _load_initial_data
        self.district_analyzer_agent = DistrictAnalyzer(
            llm=self.llm,
            property_retriever=self.property_retriever_agent
        )
        logger.info("District analyzer instance created (vectorstore pending initialization).")

        self.pdf_generator = PDFReportGenerator()
        logger.info("PDF generator initialized")

        await self._load_initial_data()

    async def _load_initial_data(self):
        logger.info("InitializationService: Starting initial data loading procedures...")

        try:
            # DistrictAnalyzer now handles its own vectorstore initialization logic including cache
            logger.info("InitializationService: Triggering DistrictAnalyzer vectorstore initialization.")
            await self.district_analyzer_agent._initialize_vectorstore_at_startup()

            # Log the final status of the DistrictAnalyzer's data
            da_status = self.district_analyzer_agent.get_current_vectorstore_status()
            logger.info(f"InitializationService: DistrictAnalyzer post-initialization status: {da_status}")
            if not da_status.get("vectorstore_initialized") or da_status.get("document_count", 0) == 0:
                logger.warning(
                    "InitializationService: DistrictAnalyzer vectorstore might not be properly initialized or is empty.")

        except Exception as e:
            logger.error(f"InitializationService: Critical error during _load_initial_data: {e}", exc_info=True)
            logger.info(
                "InitializationService: System might be running with limited data capabilities for DistrictAnalyzer.")

    async def cleanup(self):
        if self.property_retriever_agent:
            await self.property_retriever_agent.close()
            logger.info("Property retriever closed")

    # Removed get_cache_status as DistrictAnalyzer now manages its own cache status internally.
    # If other services need a generic cache status, it could be redesigned or kept if it served other purposes.