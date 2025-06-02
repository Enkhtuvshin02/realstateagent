
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
        logger.info("🔧 Initializing services...")


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


        self.district_analyzer_agent = DistrictAnalyzer(
            llm=self.llm,
            property_retriever=self.property_retriever_agent
        )
        logger.info("District analyzer initialized")


        self.pdf_generator = PDFReportGenerator()
        logger.info("PDF generator initialized")


        await self._load_initial_data()

    async def _load_initial_data(self):
        logger.info("Loading initial data...")

        try:
            cache_status = self.district_analyzer_agent.get_cache_status()
            logger.info(f"Cache status: {cache_status}")


            if not cache_status["is_fresh"]:
                await self.district_analyzer_agent._update_with_realtime_data()
                logger.info(" New data loaded")
            else:
                logger.info("Cache data is fresh")

        except Exception as e:
            logger.error(f"Error loading initial data: {e}")
            logger.info("Continuing with static data")

    async def cleanup(self):
        if self.property_retriever_agent:
            await self.property_retriever_agent.close()
            logger.info("Property retriever closed")