# services/initialization_service.py - Хялбаршуулсан эхлүүлэлтийн үйлчилгээ
import os
import logging
from langchain_together import ChatTogether
from langchain_community.tools.tavily_search import TavilySearchResults

from agents.property_retriever import PropertyRetriever
from agents.district_analyzer import DistrictAnalyzer
from utils.xhtml2pdf_generator import PDFReportGenerator

logger = logging.getLogger(__name__)


class InitializationService:
    def __init__(self):
        self.llm = None
        self.search_tool = None
        self.property_retriever_agent = None
        self.district_analyzer_agent = None
        self.pdf_generator = None

    async def initialize(self):
        """Бүх компонентыг эхлүүлэх"""
        logger.info("🔧 Үйлчилгээнүүдийг эхлүүлж байна...")

        # API түлхүүрүүдийг шалгах
        together_api_key = os.getenv("TOGETHER_API_KEY")
        tavily_api_key = os.getenv("TAVILY_API_KEY")

        if not together_api_key:
            raise ValueError("TOGETHER_API_KEY орчны хувьсагч тохируулаагүй байна")
        if not tavily_api_key:
            raise ValueError("TAVILY_API_KEY орчны хувьсагч тохируулаагүй байна")

        # LLM эхлүүлэх
        logger.info("🤖 LLM эхлүүлж байна...")
        self.llm = ChatTogether(
            together_api_key=together_api_key,
            model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
            temperature=0.7
        )
        logger.info("✅ LLM эхэлсэн")

        # Хайлтын хэрэгсэл эхлүүлэх
        logger.info("🔍 Хайлтын хэрэгсэл эхлүүлж байна...")
        self.search_tool = TavilySearchResults(
            max_results=5,
            search_depth="advanced",
            include_answer=True,
            tavily_api_key=tavily_api_key
        )
        logger.info("✅ Хайлтын хэрэгсэл эхэлсэн")

        # Property retriever эхлүүлэх
        logger.info("🏠 Property retriever эхлүүлж байна...")
        self.property_retriever_agent = PropertyRetriever(llm=self.llm)
        logger.info("✅ Property retriever эхэлсэн")

        # District analyzer эхлүүлэх
        logger.info("📊 District analyzer эхлүүлж байна...")
        self.district_analyzer_agent = DistrictAnalyzer(
            llm=self.llm,
            property_retriever=self.property_retriever_agent
        )
        logger.info("✅ District analyzer эхэлсэн")

        # PDF generator эхлүүлэх
        logger.info("📄 PDF generator эхлүүлж байна...")
        self.pdf_generator = PDFReportGenerator()
        logger.info("✅ PDF generator эхэлсэн")

        # Анхны өгөгдөл ачаалах
        await self._load_initial_data()

    async def _load_initial_data(self):
        """Анхны өгөгдөл ачаалах"""
        logger.info("📚 Анхны өгөгдөл ачаалж байна...")

        try:
            cache_status = self.district_analyzer_agent.get_cache_status()
            logger.info(f"📊 Кэшийн статус: {cache_status}")

            # Хэрэв кэш хуучирсан бол шинэчлэх
            if not cache_status["is_fresh"]:
                logger.info("🔄 Кэш хуучирсан, шинэ өгөгдөл ачаалж байна...")
                await self.district_analyzer_agent._update_with_realtime_data()
                logger.info("✅ Шинэ өгөгдөл ачаалагдсан")
            else:
                logger.info("📅 Кэшийн өгөгдөл шинэ байна")

        except Exception as e:
            logger.error(f"❌ Анхны өгөгдөл ачаалахад алдаа: {e}")
            logger.info("📚 Статик өгөгдлөөр үргэлжлүүлж байна")

    async def cleanup(self):
        """Нөөцүүдийг цэвэрлэх"""
        if self.property_retriever_agent:
            await self.property_retriever_agent.close()
            logger.info("🧹 Property retriever хаагдсан")