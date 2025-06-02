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

        self._initialize_with_static_data()

    def _initialize_with_static_data(self):
        logger.info("Initializing with static data...")

        static_data = [
            Document(page_content="""Дүүрэг: Хан-Уул
            Нийт байрны 1м2 дундаж үнэ: 4 000 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 100 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 900 000 төгрөг
            Хан-Уул дүүрэг нь баруун урд байрладаг, үнэ өндөр дүүрэг.
            """),
            Document(page_content="""Дүүрэг: Баянгол
            Нийт байрны 1м2 дундаж үнэ: 3 500 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 600 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 400 000 төгрөг
            Баянгол дүүрэг нь төвтэй ойр, дундаж үнэтэй дүүрэг.
            """),
            Document(page_content="""Дүүрэг: Сүхбаатар
            Нийт байрны 1м2 дундаж үнэ: 4 500 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 600 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 4 400 000 төгрөг
            Сүхбаатар дүүрэг нь хамгийн үнэтэй, төвийн дүүрэг.
            """),
            Document(page_content="""Дүүрэг: Чингэлтэй
            Нийт байрны 1м2 дундаж үнэ: 3 800 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 900 000 төгрөг
            3 өрөө байрны 1m2 дундаж үнэ: 3 700 000 төгрөг
            Чингэлтэй дүүрэг нь төв хэсэгтэй ойр байрладаг.
            """),
            Document(page_content="""Дүүрэг: Баянзүрх
            Нийт байрны 1м2 дундаж үнэ: 3 200 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 3 300 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 100 000 төгрөг
            Баянзүрх дүүрэг нь хамгийн том, дундаж үнэтэй дүүрэг.
            """),
            Document(page_content="""Дүүрэг: Сонгинохайрхан
            Нийт байрны 1м2 дундаж үнэ: 2 800 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 2 900 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 2 700 000 төгрөг
            Сонгинохайрхан дүүрэг нь хотын баруун хэсэгт байрладаг том дүүрэг.
            """)
        ]

        self.vectorstore = FAISS.from_documents(static_data, self.embeddings_model)
        logger.info("Vector store initialized with static data")

    async def analyze_district(self, location: str) -> str:
        logger.info(f"Specific district analysis for: '{location}'")

        await self._ensure_fresh_data()

        comparison_keywords = ['бүх дүүрэг', 'дүүрэг харьцуулах', 'дүүргүүд', 'compare']
        is_comparison = any(keyword in location.lower() for keyword in comparison_keywords)

        if is_comparison:
            return await self._compare_all_districts(location)
        else:
            return await self._analyze_specific_district(location)

    async def _analyze_specific_district(self, location: str) -> str:
        results = self.vectorstore.similarity_search_with_score(location, k=3)

        best_match = None
        for doc, score in results:
            if location.lower() in doc.page_content.lower():
                best_match = doc
                break

        if best_match:
            content = best_match.page_content
            logger.info(f"Found: {content.splitlines()[0]}")
        else:
            content = "No specific district information found."

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
        all_docs = list(self.vectorstore.docstore._dict.values())

        # Extract structured data from documents for direct processing
        districts_data = []
        for doc in all_docs:
            content = doc.page_content.strip()
            district_info = {}
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if 'Дүүрэг:' in line:
                    district_info['name'] = line.replace('Дүүрэг:', '').strip()
                elif 'Нийт байрны 1м2 дундаж үнэ:' in line:
                    price_str = line.split(':', 1)[1].strip().replace('төгрөг', '').replace(' ', '').replace(',', '')
                    district_info['overall_avg'] = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0
                elif '1 өрөө байрны 1м2 дундаж үнэ:' in line:
                    price_str = line.split(':', 1)[1].strip().replace('төгрөг', '').replace(' ', '').replace(',', '')
                    district_info['one_room_avg'] = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0
                elif '2 өрөө байрны 1м2 дундаж үнэ:' in line:
                    price_str = line.split(':', 1)[1].strip().replace('төгрөг', '').replace(' ', '').replace(',', '')
                    district_info['two_room_avg'] = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0
                elif '3 өрөө байрны 1м2 дундаж үнэ:' in line:
                    price_str = line.split(':', 1)[1].strip().replace('төгрөг', '').replace(' ', '').replace(',', '')
                    district_info['three_room_avg'] = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0
                # Add more room types if necessary, mirroring how PropertyAggregator generates them

            if district_info.get('name'):
                districts_data.append(district_info)

        # Sort by overall average price for better presentation
        districts_data_sorted = sorted(districts_data, key=lambda x: x.get('overall_avg', 0), reverse=True)

        # Format the data for direct output
        formatted_response = "Улаанбаатар хотын дүүргүүдийн 1м² дундаж үнэ:\n\n"
        for d in districts_data_sorted:
            formatted_response += f"**Дүүрэг: {d.get('name', 'N/A')}**\n"
            if d.get('overall_avg', 0) > 0:
                formatted_response += f"  Нийт дундаж: {int(d['overall_avg']):,}₮/м²\n".replace(',', ' ')
            if d.get('one_room_avg', 0) > 0:
                formatted_response += f"  1 өрөө: {int(d['one_room_avg']):,}₮/м²\n".replace(',', ' ')
            if d.get('two_room_avg', 0) > 0:
                formatted_response += f"  2 өрөө: {int(d['two_room_avg']):,}₮/м²\n".replace(',', ' ')
            if d.get('three_room_avg', 0) > 0:
                formatted_response += f"  3 өрөө: {int(d['three_room_avg']):,}₮/м²\n".replace(',', ' ')
            # Add more room types here if they are extracted
            formatted_response += "\n"

        # Now, if we want an LLM summary, pass the formatted data to a *very constrained* LLM call
        # For simplicity, we can return the formatted string directly first.
        # If the user still asks for more general insights, that's where a more complex LLM call comes in.

        # Removed the direct LLM call here, as it was leading to hallucinations.
        # The primary goal for "show all districts" is direct data presentation.
        return formatted_response

    async def _ensure_fresh_data(self):
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
            logger.info("Fetching new data...")
            await self._update_with_realtime_data()

    async def _update_with_realtime_data(self):
        try:
            real_time_documents = await self.property_retriever.retrieve_vector_data()

            if real_time_documents:
                self.vectorstore = FAISS.from_documents(real_time_documents, self.embeddings_model)

                cache_file = self.cache_dir / "last_update.txt"
                with open(cache_file, 'w') as f:
                    f.write(datetime.now().isoformat())

                logger.info(f"Vector store updated with {len(real_time_documents)} documents")
            else:
                logger.warning("Failed to fetch new data")

        except Exception as e:
            logger.error(f"Error fetching new data: {e}")

    def get_cache_status(self) -> dict:
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