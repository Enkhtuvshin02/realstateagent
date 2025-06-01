# real_estate_assistant/agents/district_analyzer.py
import logging
import os
from datetime import datetime, timedelta
import pickle
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
        self.documents_cache_file = self.cache_dir / "district_documents.pkl"
        self.last_update_file = self.cache_dir / "last_update.txt"

        self._initialize_vectorstore()

    def _initialize_vectorstore(self):
        """Initialize vectorstore with cached data if available and fresh, otherwise use static data"""
        # Check if we have valid cached data
        if self._should_use_cached_data():
            logger.info("📦 Loading cached vectorstore data...")
            if self._load_cached_vectorstore():
                logger.info("✅ Successfully loaded cached vectorstore data")
                return
            else:
                logger.warning("⚠️  Failed to load cached data, falling back to static data")

        # Use static fallback data
        logger.info("📚 Initializing with static fallback data...")
        static_district_data = [
            Document(page_content="""
            Дүүрэг: Хан-Уул
            Нийт байрны 1м2 дундаж үнэ: 4 000 323 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 100 323 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 900 323 төгрөг
            Хан-Уул дүүрэг нь Улаанбаатар хотын баруун урд байрладаг. Энэ дүүрэг нь орон сууцны үнэ харьцангуй өндөр байдаг.
            """),
            Document(page_content="""
            Дүүрэг: Баянгол
            Нийт байрны 1м2 дундаж үнэ: 3 510 645 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 610 645 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 410 645 төгрөг
            Баянгол дүүрэг нь Улаанбаатар хотын төв хэсэгт ойр байрладаг. Энэ дүүрэг нь дундаж үнэтэй орон сууц элбэг.
            """),
            Document(page_content="""
            Дүүрэг: Сүхбаатар
            Нийт байрны 1м2 дундаж үнэ: 4 500 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 600 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 4 400 000 төгрөг
            Сүхбаатар дүүрэг нь хотын хамгийн үнэтэй бүсүүдийн нэг бөгөөд төвдөө ойрхон.
            """),
            Document(page_content="""
            Дүүрэг: Чингэлтэй
            Нийт байрны 1м2 дундаж үнэ: 3 800 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 900 000 төгрөг
            3 өрөө байрны 1m2 дундаж үнэ: 3 700 000 төгрөг
            Чингэлтэй дүүрэг нь хотын төв хэсэгт оршдог.
            """),
        ]

        self.vectorstore = FAISS.from_documents(static_district_data, self.embeddings_model)
        logger.info("FAISS vectorstore initialized with static data.")

    def _should_use_cached_data(self) -> bool:
        """Check if cached data exists and is less than 7 days old"""
        if not self.documents_cache_file.exists() or not self.last_update_file.exists():
            logger.info("📊 No cached data found")
            return False

        try:
            with open(self.last_update_file, 'r') as f:
                last_update_str = f.read().strip()

            last_update = datetime.fromisoformat(last_update_str)
            age = datetime.now() - last_update

            if age > timedelta(days=7):
                logger.info(f"📅 Cached data is {age.days} days old, needs refresh")
                return False
            else:
                logger.info(f"📅 Cached data is {age.days} days old, still fresh")
                return True

        except Exception as e:
            logger.error(f"❌ Error checking cache age: {e}")
            return False

    def _load_cached_vectorstore(self) -> bool:
        """Load vectorstore from cached documents"""
        try:
            with open(self.documents_cache_file, 'rb') as f:
                cached_documents = pickle.load(f)

            # Recreate vectorstore from cached documents
            self.vectorstore = FAISS.from_documents(cached_documents, self.embeddings_model)
            logger.info(f"📦 Loaded {len(cached_documents)} documents from cache")
            return True
        except Exception as e:
            logger.error(f"❌ Error loading cached documents: {e}")
            return False

    def _save_vectorstore_cache(self, documents):
        """Save documents to cache file instead of vectorstore"""
        try:
            with open(self.documents_cache_file, 'wb') as f:
                pickle.dump(documents, f)

            with open(self.last_update_file, 'w') as f:
                f.write(datetime.now().isoformat())

            logger.info("💾 Documents cached successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving documents cache: {e}")
            return False

    async def update_with_realtime_data(self, force_update: bool = False):
        """Update vectorstore with real-time scraped data only if needed"""
        if not self.property_retriever:
            logger.warning("No PropertyRetriever provided. Cannot update with real-time data.")
            return False

        # Check if update is needed
        if not force_update and self._should_use_cached_data():
            logger.info("📅 Cached data is still fresh, skipping update")
            return True

        try:
            logger.info("🔄 Updating vectorstore with real-time data...")
            real_time_documents = await self.property_retriever.retrieve_vector_data()

            if real_time_documents:
                # Create new vectorstore with real-time data
                new_vectorstore = FAISS.from_documents(real_time_documents, self.embeddings_model)

                # Save documents to cache (not the vectorstore object)
                if self._save_vectorstore_cache(real_time_documents):
                    self.vectorstore = new_vectorstore

                logger.info(f"✅ Vectorstore updated with {len(real_time_documents)} real-time documents.")

                # Log what districts we now have data for
                districts = []
                for doc in real_time_documents:
                    lines = doc.page_content.split('\n')
                    district_line = lines[0] if lines else ""
                    if 'Дүүрэг:' in district_line:
                        district_name = district_line.replace('Дүүрэг:', '').strip()
                        districts.append(district_name)

                logger.info(f"📍 Real-time data available for districts: {', '.join(districts)}")
                return True
            else:
                logger.warning("⚠️  No real-time data retrieved. Keeping existing vectorstore.")
                return False

        except Exception as e:
            logger.error(f"❌ Error updating vectorstore with real-time data: {e}")
            logger.info("Continuing with existing vectorstore data.")
            return False

    async def ensure_fresh_data(self):
        """Ensure we have fresh data, but don't update on every request"""
        if not self._should_use_cached_data():
            logger.info("🔄 Data is stale or missing, updating...")
            await self.update_with_realtime_data(force_update=True)
        else:
            logger.info("📊 Using cached data (fresh)")

    async def analyze_district(self, location: str) -> str:
        """
        Analyzes district information based on the provided location,
        leveraging cached or real-time data as appropriate.
        """
        logger.info(f"🔍 Analyzing district for location: '{location}'")

        # Only update data if it's stale (not on every request)
        await self.ensure_fresh_data()

        # Check what districts are available in vectorstore
        available_docs = list(self.vectorstore.docstore._dict.values())
        available_districts = []
        for doc in available_docs:
            lines = doc.page_content.split('\n')
            district_line = lines[0] if lines else ""
            if 'Дүүрэг:' in district_line:
                district_name = district_line.replace('Дүүрэг:', '').strip()
                available_districts.append(district_name)

        logger.info(f"📊 Available districts in vectorstore: {', '.join(available_districts)}")

        # Retrieve relevant district info from vectorstore with scores
        retrieved_results = self.vectorstore.similarity_search_with_score(location, k=len(available_docs))

        logger.debug(f"Retrieved {len(retrieved_results)} documents for '{location}'.")

        # Sort by score (lower score is more similar for FAISS cosine distance)
        retrieved_results.sort(key=lambda x: x[1])

        # Find the best match
        best_match_doc = None
        for doc, score in retrieved_results:
            logger.debug(f"  Doc Score: {score:.4f}, Content (first 50 chars): {doc.page_content.strip()[:50]}...")
            if location.lower() in doc.page_content.lower():
                best_match_doc = doc
                logger.info(f"✅ Found direct match for '{location}' with score {score:.4f}.")
                break

        if best_match_doc:
            retrieved_content = best_match_doc.page_content

            # Check if this is real-time data (has timestamp) or static data
            if 'Дата цуглуулсан огноо:' in retrieved_content:
                logger.info("📊 Using REAL-TIME scraped data for analysis")
            else:
                logger.info("📚 Using STATIC fallback data for analysis")

            logger.info(f"Retrieved district info: {retrieved_content.splitlines()[0]}...")
            logger.debug(f"Full retrieved_content being passed to LLM: \n{retrieved_content}")
        else:
            # Fallback if no exact district name is found
            retrieved_content = "Тус байршилд хамаарах дүүргийн мэдээлэл олдсонгүй."
            logger.warning(
                f"❌ No exact district information found in vectorstore for: '{location}'. Falling back to generic message.")

        prompt_template = """
        Өгөгдсөн байршил болон үнийн мэдээллийг ашиглан дүүргийн дундаж үнийг харуулж, бусад дүүргүүдтэй харьцуулсан мэдээлэл өгнө үү.
        Хэрэв өгөгдсөн "Үнийн мэдээлэл" хэсэгт тухайн "Байршил"-ийн үнийн дэлгэрэнгүй мэдээлэл байхгүй бол "мэдээлэл байхгүй" гэж заана уу.

        Байршил: {location}
        Үнийн мэдээлэл:
        <context>
        {price_context}
        </context>

        Таны хариулт дараах форматыг хатуу мөрдөнө (нэмэлт текстгүйгээр, зөвхөн Монгол хэлээр):
           - Дүүрэг: [Дүүргийн нэр]
               - Нийт байрны 1м2 дундаж үнэ: [Үнэ эсвэл "мэдээлэл байхгүй"]
               - 2 өрөө байрны 1м2 дундаж үнэ: [Үнэ эсвэл "мэдээлэл байхгүй"]
               - 3 өрөө байрны 1м2 дундаж үнэ: [Үнэ эсвэл "мэдээлэл байхгүй"]
           - Харьцуулалт: [Бусад дүүргүүдийн дундаж үнээс дээш эсвэл доош байгаа эсэх мэдээлэл, эсвэл "харьцуулах мэдээлэл байхгүй"]

        Таны хариулт:
        """
        ANALYZE_PROMPT = PromptTemplate.from_template(prompt_template)
        analysis_chain = ANALYZE_PROMPT | self.llm | StrOutputParser()

        logger.debug(
            f"Invoking analysis_chain with location='{location}' and price_context (first 100 chars): '{retrieved_content[:100]}...'")

        response = await analysis_chain.ainvoke({
            "location": location,
            "price_context": retrieved_content
        })
        logger.info(f"District analysis LLM raw response (first 100 chars): {response[:100]}...")
        return response

    def get_all_districts_summary(self) -> str:
        """Get a summary of all districts in the vectorstore"""
        if not self.vectorstore:
            return "Дүүргийн мэдээлэл байхгүй."

        all_docs = list(self.vectorstore.docstore._dict.values())
        summary_parts = []

        for doc in all_docs:
            lines = doc.page_content.strip().split('\n')
            if lines:
                district_line = lines[0].strip()
                summary_parts.append(district_line)

        return "\n".join(summary_parts) if summary_parts else "Дүүргийн мэдээлэл байхгүй."

    def get_cache_status(self) -> dict:
        """Get information about cache status"""
        status = {
            "cache_exists": self.documents_cache_file.exists(),
            "last_update_exists": self.last_update_file.exists(),
            "is_fresh": False,
            "age_days": None,
            "last_update": None
        }

        if status["last_update_exists"]:
            try:
                with open(self.last_update_file, 'r') as f:
                    last_update_str = f.read().strip()

                last_update = datetime.fromisoformat(last_update_str)
                age = datetime.now() - last_update

                status["is_fresh"] = age <= timedelta(days=7)
                status["age_days"] = age.days
                status["last_update"] = last_update_str

            except Exception as e:
                logger.error(f"Error reading cache status: {e}")

        return status

    async def force_update(self):
        """Force an immediate update of the vectorstore data"""
        return await self.update_with_realtime_data(force_update=True)