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

        # Define paths for FAISS index and timestamp
        self.faiss_index_folder = self.cache_dir
        self.faiss_index_name = "district_analyzer_index"  # Base name for FAISS files
        self.last_update_timestamp_file = self.cache_dir / "district_data_last_update.txt"

        # Removed: self._initialize_with_static_data() - This will be handled by _initialize_vectorstore_at_startup

    async def _initialize_vectorstore_at_startup(self):
        """
        Initializes the vectorstore at application startup.
        Tries to load from disk cache if fresh, otherwise updates from real-time data,
        and falls back to static data if necessary.
        This method is intended to be called by InitializationService.
        """
        logger.info("DistrictAnalyzer: Attempting to initialize vectorstore at startup.")
        cache_status = self._get_cache_file_status()

        if cache_status["is_fresh"]:
            logger.info(
                f"DistrictAnalyzer: Cache timestamp is fresh (Last update: {cache_status['last_update']}). Trying to load vectorstore from disk.")
            if self._load_vectorstore_from_disk():
                logger.info("DistrictAnalyzer: Successfully loaded vectorstore from disk cache.")
                return
            else:
                logger.warning(
                    "DistrictAnalyzer: Failed to load vectorstore from disk cache despite fresh timestamp. Will attempt to update from real-time data.")
        else:
            if cache_status['last_update'] == "N/A (No timestamp file)":
                logger.info(
                    "DistrictAnalyzer: No cache timestamp file found. Will attempt to update from real-time data.")
            else:
                logger.info(
                    f"DistrictAnalyzer: Cache is stale (Last update: {cache_status['last_update']}). Will attempt to update from real-time data.")

        # If cache not fresh, or loading from disk failed:
        updated_successfully = await self._update_with_realtime_data()
        if not updated_successfully:
            logger.warning("DistrictAnalyzer: Real-time data update failed. Initializing with static fallback data.")
            self._initialize_with_static_data_fallback()  # Fallback to static

    def _get_cache_file_status(self) -> dict:
        """Checks the status of the cache timestamp file."""
        default_status = {"is_fresh": False, "age_days": None, "last_update": "N/A (No timestamp file)"}
        if not self.last_update_timestamp_file.exists():
            return default_status
        try:
            with open(self.last_update_timestamp_file, 'r') as f:
                last_update_str = f.read().strip()
            last_update = datetime.fromisoformat(last_update_str)
            age = datetime.now() - last_update
            is_fresh = age <= timedelta(days=7)  # Cache valid for 7 days
            logger.info(f"Cache timestamp file read. Last update: {last_update_str}, Age: {age}, Is fresh: {is_fresh}")
            return {
                "is_fresh": is_fresh,
                "age_days": age.days,
                "last_update": last_update_str
            }
        except Exception as e:
            logger.warning(f"Could not parse cache timestamp file {self.last_update_timestamp_file}: {e}",
                           exc_info=True)
            return {"is_fresh": False, "age_days": None, "last_update": f"Error reading timestamp: {str(e)}"}

    def _load_vectorstore_from_disk(self) -> bool:
        """Loads the FAISS vectorstore from disk."""
        faiss_file = self.faiss_index_folder / f"{self.faiss_index_name}.faiss"
        pkl_file = self.faiss_index_folder / f"{self.faiss_index_name}.pkl"

        if faiss_file.exists() and pkl_file.exists():
            try:
                self.vectorstore = FAISS.load_local(
                    folder_path=str(self.faiss_index_folder),
                    index_name=self.faiss_index_name,
                    embeddings=self.embeddings_model,
                    allow_dangerous_deserialization=True  # Required for FAISS loading with pickle
                )
                logger.info(f"Successfully loaded FAISS index from {self.faiss_index_folder / self.faiss_index_name}")
                return True
            except Exception as e:
                logger.error(f"Error loading FAISS index from {self.faiss_index_folder / self.faiss_index_name}: {e}",
                             exc_info=True)
                # Clean up potentially corrupted cache files if loading fails
                # This is optional and depends on how strictly you want to handle errors.
                # if faiss_file.exists(): faiss_file.unlink(missing_ok=True)
                # if pkl_file.exists(): pkl_file.unlink(missing_ok=True)
                return False
        else:
            logger.info(
                f"FAISS index files ({faiss_file.name}, {pkl_file.name}) not found in {self.faiss_index_folder}. Cannot load from disk cache.")
            return False

    def _save_vectorstore_to_disk(self):
        """Saves the current FAISS vectorstore to disk."""
        if self.vectorstore:
            try:
                self.vectorstore.save_local(
                    folder_path=str(self.faiss_index_folder),
                    index_name=self.faiss_index_name
                )
                logger.info(f"Successfully saved FAISS index to {self.faiss_index_folder / self.faiss_index_name}")
            except Exception as e:
                logger.error(f"Error saving FAISS index to {self.faiss_index_folder / self.faiss_index_name}: {e}",
                             exc_info=True)
        else:
            logger.warning("Attempted to save vectorstore, but it's None or not a FAISS index.")

    def _initialize_with_static_data_fallback(self):
        """Initializes the vectorstore with static data as a last resort."""
        logger.info("DistrictAnalyzer: Initializing with static fallback data...")
        static_data = [
            Document(page_content="""Дүүрэг: Хан-Уул
            Нийт байрны 1м2 дундаж үнэ: 4 000 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 4 100 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 3 900 000 төгрөг
            Хан-Уул дүүрэг нь баруун урд байрладаг, үнэ өндөр дүүрэг.
            """),
            # ... (other static data entries as before) ...
            Document(page_content="""Дүүрэг: Сонгинохайрхан
            Нийт байрны 1м2 дундаж үнэ: 2 800 000 төгрөг
            2 өрөө байрны 1м2 дундаж үнэ: 2 900 000 төгрөг
            3 өрөө байрны 1м2 дундаж үнэ: 2 700 000 төгрөг
            Сонгинохайрхан дүүрэг нь хотын баруун хэсэгт байрладаг том дүүрэг.
            """)
        ]
        try:
            self.vectorstore = FAISS.from_documents(static_data, self.embeddings_model)
            logger.info("DistrictAnalyzer: Vector store initialized with static fallback data.")
        except Exception as e:
            logger.error(f"DistrictAnalyzer: Failed to initialize vectorstore with static data: {e}", exc_info=True)
            self.vectorstore = None  # Ensure it's None if static init fails

    async def _update_with_realtime_data(self) -> bool:
        """Fetches real-time data, updates the vectorstore, saves it, and updates the timestamp."""
        try:
            logger.info("DistrictAnalyzer: Attempting to fetch and update with real-time vector data.")
            if not self.property_retriever:
                logger.error("DistrictAnalyzer: PropertyRetriever is not configured. Cannot update real-time data.")
                return False

            real_time_documents = await self.property_retriever.retrieve_vector_data()

            if real_time_documents and len(real_time_documents) > 0:
                logger.info(f"DistrictAnalyzer: Successfully fetched {len(real_time_documents)} real-time documents.")
                self.vectorstore = FAISS.from_documents(real_time_documents, self.embeddings_model)
                logger.info("DistrictAnalyzer: Vectorstore has been UPDATED with real-time documents.")
                self._save_vectorstore_to_disk()

                with open(self.last_update_timestamp_file, 'w') as f:
                    f.write(datetime.now().isoformat())
                logger.info(f"DistrictAnalyzer: Cache timestamp file '{self.last_update_timestamp_file.name}' updated.")
                return True
            else:
                logger.warning(
                    "DistrictAnalyzer: Failed to fetch new data or no documents returned. Vectorstore not updated from real-time source.")
                return False
        except Exception as e:
            logger.error(f"DistrictAnalyzer: Error updating with real-time data: {e}", exc_info=True)
            return False

    async def analyze_district(self, location: str) -> str:
        logger.info(f"Specific district analysis requested for: '{location}'")
        # _ensure_fresh_data is removed from here as startup handles initial freshness.
        # For very long-running apps, a periodic refresh mechanism might be added back if needed.

        if not self.vectorstore:
            logger.error("DistrictAnalyzer.vectorstore is not initialized. Cannot perform analysis.")
            self._initialize_with_static_data_fallback()  # Attempt one last fallback
            if not self.vectorstore:
                return "Дүүргийн мэдээллийн сан бэлэн бус байна. Системийн админтай холбогдоно уу."

        comparison_keywords = ['бүх дүүрэг', 'дүүрэг харьцуулах', 'дүүргүүд', 'compare all districts']
        is_comparison = any(keyword in location.lower() for keyword in comparison_keywords)

        if is_comparison:
            return await self._compare_all_districts(location)
        else:
            return await self._analyze_specific_district(location)

    async def _analyze_specific_district(self, location: str) -> str:
        logger.info(f"Analyzing specific district: {location}")
        if not self.vectorstore:  # Double check, though analyze_district should handle this
            logger.error("Vectorstore not initialized in _analyze_specific_district. Returning empty.")
            return "Дүүргийн мэдээллийн сан олдсонгүй."
        # ... (rest of the method remains the same)
        results = self.vectorstore.similarity_search_with_score(location, k=3)

        best_match = None
        # Ensure the location name is part of the retrieved document for higher relevance
        for doc, score in results:
            if location.lower() in doc.page_content.lower():  # Simple check if district name is in content
                best_match = doc
                logger.info(f"Best match found for '{location}' with score {score}.")
                break

        if not best_match and results:  # Fallback to highest score if no exact name match
            best_match = results[0][0]
            logger.info(f"No exact name match for '{location}', using best available match with score {results[0][1]}.")

        if best_match:
            content = best_match.page_content
            logger.info(
                f"Found best match for '{location}'. Content that will be used for district analysis:\n-----\n{content}\n-----")
        else:
            content = "No specific district information found."
            logger.warning(f"No specific district information found in vectorstore for '{location}'.")
            return f"{location} дүүргийн талаарх дэлгэрэнгүй мэдээлэл одоогоор системд бүртгэгдээгүй байна."

        prompt_template = """
        You are a real estate market analyst specializing in Ulaanbaatar districts.
        Analyze the provided district information ('Available data') for the queried 'Location query'.

        If specific district data is available in 'Available data', provide:
        1. District name and general location characteristics.
        2. Average prices for different property types (overall, 2-room, 3-room, etc., if available).
        3. Brief comparison highlights if the data allows (e.g., "relatively expensive", "mid-range price").
        4. Investment potential and recommendations based SOLELY on the provided 'Available data'.
        5. Market characteristics and trends mentioned in the 'Available data'.

        Location query: {location}
        Available data: {context}

        IMPORTANT: Respond ONLY in Mongolian language.
        IMPORTANT: Base your analysis STRICTLY on the text provided in 'Available data'. Do not invent or use external knowledge.
        If 'Available data' is minimal or says 'No specific district information found', state that detailed analysis for {location} cannot be provided due to lack of data.
        """

        ANALYZE_PROMPT = PromptTemplate.from_template(prompt_template)
        analysis_chain = ANALYZE_PROMPT | self.llm | StrOutputParser()

        response = await analysis_chain.ainvoke({
            "location": location,
            "context": content
        })
        logger.info(f"LLM analysis generated for {location}: {response[:200]}...")
        return response

    async def _compare_all_districts(self, location: str) -> str:
        if not self.vectorstore:
            logger.warning("Vectorstore not available for _compare_all_districts.")
            return "Дүүргийн мэдээлэл одоогоор байхгүй байна."
        # ... (rest of the method remains the same)
        all_docs = []
        if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
            all_docs = list(self.vectorstore.docstore._dict.values())
        else:
            logger.warning(
                "Cannot retrieve all documents from vectorstore for comparison as docstore._dict is not available.")
            return "Дүүргүүдийг харьцуулах боломжгүй байна: Мэдээллийн сангийн бүтэц тохирохгүй."

        logger.info(f"Comparing all districts. Found {len(all_docs)} documents in vectorstore.")

        districts_data = []
        for doc_idx, doc in enumerate(all_docs):
            content = doc.page_content.strip()
            logger.debug(f"Processing document {doc_idx} for comparison: {content[:100]}...")
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

            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)
            else:
                logger.debug(f"Skipping document {doc_idx} due to missing name or overall_avg: {district_info}")

        if not districts_data:
            logger.warning("No valid district data extracted for comparison from vectorstore documents.")
            return "Дүүргүүдийн харьцуулсан мэдээлэл боловсруулахад хангалттай өгөгдөл олдсонгүй."

        districts_data_sorted = sorted(districts_data, key=lambda x: x.get('overall_avg', 0), reverse=True)

        formatted_response = "Улаанбаатар хотын дүүргүүдийн орон сууцны 1м² дундаж үнийн харьцуулалт (системийн одоогийн мэдээллээр):\n\n"
        for d in districts_data_sorted:
            formatted_response += f"**Дүүрэг: {d.get('name', 'N/A')}**\n"
            if d.get('overall_avg', 0) > 0:
                formatted_response += f"  Нийт дундаж: {int(d['overall_avg']):,}₮/м²\n".replace(',', ' ')
            if d.get('one_room_avg', 0) > 0:
                formatted_response += f"  1 өрөө дундаж: {int(d['one_room_avg']):,}₮/м²\n".replace(',', ' ')
            if d.get('two_room_avg', 0) > 0:
                formatted_response += f"  2 өрөө дундаж: {int(d['two_room_avg']):,}₮/м²\n".replace(',', ' ')
            if d.get('three_room_avg', 0) > 0:
                formatted_response += f"  3 өрөө дундаж: {int(d['three_room_avg']):,}₮/м²\n".replace(',', ' ')
            formatted_response += "\n"

        logger.info("Successfully formatted comparison for all districts.")
        return formatted_response

    # Removed _ensure_fresh_data method, its logic is now part of _initialize_vectorstore_at_startup

    # Renamed original get_cache_status to _get_cache_file_status and made it internal.
    # If InitializationService or other external modules need status, they can call a new public method
    # or DistrictAnalyzer can expose its status more directly after initialization.
    def get_current_vectorstore_status(self) -> dict:
        """Returns information about the current state of the vectorstore and its data freshness."""
        status = self._get_cache_file_status()
        status["vectorstore_initialized"] = self.vectorstore is not None
        if self.vectorstore and hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
            status["document_count"] = len(self.vectorstore.docstore._dict)
        else:
            status["document_count"] = 0
        return status