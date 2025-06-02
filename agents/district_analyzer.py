# agents/district_analyzer.py - Хялбаршуулсан дүүргийн шинжээч
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_together import ChatTogether
from langchain_community.vectorstores import FAISS
from langchain_together.embeddings import TogetherEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class DistrictAnalyzer:
    def __init__(self, llm: ChatTogether, property_retriever=None):
        self.llm = llm
        self.property_retriever = property_retriever
        self.embeddings_model = TogetherEmbeddings(
            together_api_key=os.getenv("TOGETHER_API_KEY"),
            model="togethercomputer/m2-bert-80M-8k-retrieval"
        )
        self.vectorstore = None
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)

        # Анхны өгөгдлөөр эхлүүлэх
        self._initialize_with_static_data()

    def _initialize_with_static_data(self):
        """Статик өгөгдлөөр векторын санг эхлүүлэх"""
        logger.info("Статик өгөгдлөөр эхлүүлж байна...")

        static_data = [
            Document(page_content="""
            Дүүрэг: Хан-Уул
            Нийт байрны 1м2 дундаж үнэ: 4 000 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 100 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 900 000 төгрөг
            Хан-Уул дүүрэг нь баруун урд байрладаг, үнэ өндөр дүүрэг.
            """),
            Document(page_content="""
            Дүүрэг: Баянгол
            Нийт байрны 1м2 дундаж үнэ: 3 500 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 600 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 400 000 төгрөг
            Баянгол дүүрэг нь төвтэй ойр, дундаж үнэтэй дүүрэг.
            """),
            Document(page_content="""
            Дүүрэг: Сүхбаатар
            Нийт байрны 1м2 дундаж үнэ: 4 500 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 600 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 4 400 000 төгрөг
            Сүхбаатар дүүрэг нь хамгийн үнэтэй, төвийн дүүрэг.
            """),
            Document(page_content="""
            Дүүрэг: Чингэлтэй
            Нийт байрны 1м2 дундаж үнэ: 3 800 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 900 000 төгрөг
            3 өрөө байрны 1m2 дундаж үнэ: 3 700 000 төгрөг
            Чингэлтэй дүүрэг нь төв хэсэгтэй ойр байрладаг.
            """),
            Document(page_content="""
            Дүүрэг: Баянзүрх
            Нийт байрны 1м2 дундаж үнэ: 3 200 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 300 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 100 000 төгрөг
            Баянзүрх дүүрэг нь хамгийн том, дундаж үнэтэй дүүрэг.
            """),
            Document(page_content="""
            Дүүрэг: Сонгинохайрхан
            Нийт байрны 1м2 дундаж үнэ: 2 800 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 2 900 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 2 700 000 төгрөг
            Сонгинохайрхан дүүрэг нь баруун хэсэгт байрладаг том дүүрэг.
            """)
        ]

        self.vectorstore = FAISS.from_documents(static_data, self.embeddings_model)
        logger.info("Векторын сан статик өгөгдлөөр бэлэн болсон")

    async def analyze_district(self, location: str) -> str:
        """Дүүргийн шинжилгээ хийх - хялбаршуулсан"""
        logger.info(f"Дүүргийн шинжилгээ: '{location}'")

        # Шинэ өгөгдөл шалгах (1 долоо хоног тутам)
        await self._ensure_fresh_data()

        # Барилга жагсаалт харьцуулах эсэхийг шалгах
        comparison_keywords = ['бүх дүүрэг', 'дүүрэг харьцуулах', 'дүүргүүд', 'compare']
        is_comparison = any(keyword in location.lower() for keyword in comparison_keywords)

        if is_comparison:
            return await self._compare_all_districts(location)
        else:
            return await self._analyze_specific_district(location)

    async def _analyze_specific_district(self, location: str) -> str:
        """Тодорхой дүүргийн шинжилгээ"""
        # Векторын санаас хайх
        results = self.vectorstore.similarity_search_with_score(location, k=3)

        # Хамгийн сайн тохирохыг олох
        best_match = None
        for doc, score in results:
            if location.lower() in doc.page_content.lower():
                best_match = doc
                break

        if best_match:
            content = best_match.page_content
            logger.info(f"Олдсон: {content.splitlines()[0]}")
        else:
            content = "Тодорхой дүүргийн мэдээлэл олдсонгүй."

        # LLM-ээр шинжилгээ хийх
        prompt_template = """
        You are a real estate market analyst specializing in Ulaanbaatar districts. 
        Analyze the district information and provide insights.

        If specific district data is available, provide:
        1. District name and location
        2. Average prices for different property types
        3. Comparison with other districts
        4. Investment potential and recommendations
        5. Market characteristics and trends

        Location query: {location}
        Available data: {context}

        IMPORTANT: Respond ONLY in Mongolian language.
        """

        ANALYZE_PROMPT = PromptTemplate.from_template(prompt_template)
        analysis_chain = ANALYZE_PROMPT | self.llm | StrOutputParser()

        response = await analysis_chain.ainvoke({
            "location": location,
            "context": content
        })

        return response

    async def _compare_all_districts(self, location: str) -> str:
        """Бүх дүүргийн харьцуулалт"""
        all_docs = list(self.vectorstore.docstore._dict.values())
        all_content = "\n\n".join([doc.page_content for doc in all_docs])

        prompt_template = """
        You are a real estate market analyst. Provide a comprehensive comparison of ALL districts.

        Create analysis that includes:
        1. Overview of all districts with their average prices
        2. Price ranking from most expensive to least expensive
        3. District categories (premium, mid-range, affordable)
        4. Investment recommendations for different buyer types
        5. Best value districts and reasons why

        Location query: {location}
        All districts data: {context}

        IMPORTANT: Respond ONLY in Mongolian language with comprehensive district comparison.
        """

        ANALYZE_PROMPT = PromptTemplate.from_template(prompt_template)
        analysis_chain = ANALYZE_PROMPT | self.llm | StrOutputParser()

        response = await analysis_chain.ainvoke({
            "location": location,
            "context": all_content
        })

        return response

    async def _ensure_fresh_data(self):
        """Шинэ өгөгдөл байгаа эсэхийг шалгах"""
        if not self.property_retriever:
            return

        cache_file = self.cache_dir / "last_update.txt"
        should_update = True

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    last_update_str = f.read().strip()
                last_update = datetime.fromisoformat(last_update_str)
                age = datetime.now() - last_update
                should_update = age > timedelta(days=7)
            except:
                should_update = True

        if should_update:
            logger.info("Шинэ өгөгдөл татаж байна...")
            await self._update_with_realtime_data()

    async def _update_with_realtime_data(self):
        """Бодит цагийн өгөгдлөөр шинэчлэх"""
        try:
            real_time_documents = await self.property_retriever.retrieve_vector_data()

            if real_time_documents:
                # Шинэ векторын сан үүсгэх
                self.vectorstore = FAISS.from_documents(real_time_documents, self.embeddings_model)

                # Сүүлийн шинэчлэлийн огноог хадгалах
                cache_file = self.cache_dir / "last_update.txt"
                with open(cache_file, 'w') as f:
                    f.write(datetime.now().isoformat())

                logger.info(f"Векторын сан {len(real_time_documents)} баримттайгаар шинэчлэгдсэн")
            else:
                logger.warning("Шинэ өгөгдөл татаж чадсангүй")

        except Exception as e:
            logger.error(f"Шинэ өгөгдөл татахад алдаа: {e}")

    def get_cache_status(self) -> dict:
        """Кэшийн статусыг авах"""
        cache_file = self.cache_dir / "last_update.txt"

        if not cache_file.exists():
            return {"is_fresh": False, "age_days": None}

        try:
            with open(cache_file, 'r') as f:
                last_update_str = f.read().strip()
            last_update = datetime.fromisoformat(last_update_str)
            age = datetime.now() - last_update

            return {
                "is_fresh": age <= timedelta(days=7),
                "age_days": age.days,
                "last_update": last_update_str
            }
        except:
            return {"is_fresh": False, "age_days": None}