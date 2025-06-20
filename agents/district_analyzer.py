import json
import logging
import os
import re
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_together import ChatTogether
from langchain_community.vectorstores import FAISS
from langchain_together.embeddings import TogetherEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

DISTRICT_NAMES = [
    "Баянгол", "Баянзүрх", "Сонгинохайрхан", "Сүхбаатар",
    "Чингэлтэй", "Хан-Уул", "Налайх", "Багануур", "Багахангай"
]

DISTRICT_VARIATIONS = {
    "баянгол": "Баянгол",
    "bayngol": "Баянгол",
    "баянзүрх": "Баянзүрх",
    "баянзурх": "Баянзүрх",
    "bayanzurkh": "Баянзүрх",
    "bayanzurh": "Баянзүрх",
    "сонгинохайрхан": "Сонгинохайрхан",
    "сонгино": "Сонгинохайрхан",
    "songinokhairkhan": "Сонгинохайрхан",
    "сүхбаатар": "Сүхбаатар",
    "сухбаатар": "Сүхбаатар",
    "sukhbaatar": "Сүхбаатар",
    "suhbaatar": "Сүхбаатар",
    "чингэлтэй": "Чингэлтэй",
    "чингэлтэи": "Чингэлтэй",
    "chingeltei": "Чингэлтэй",
    "хан-уул": "Хан-Уул",
    "хануул": "Хан-Уул",
    "хан уул": "Хан-Уул",
    "khan-uul": "Хан-Уул",
    "khanuul": "Хан-Уул",
    "khan uul": "Хан-Уул",
    "налайх": "Налайх",
    "nalaikh": "Налайх",
    "багануур": "Багануур",
    "baganuur": "Багануур",
    "багахангай": "Багахангай",
    "bagakhangai": "Багахангай"
}

class DistrictAnalyzer:
    def __init__(self, llm: ChatTogether, property_retriever=None, search_tool=None):
        self.llm = llm
        self.property_retriever = property_retriever
        self.search_tool = search_tool
        self.embeddings_model = TogetherEmbeddings(
            together_api_key=os.getenv("TOGETHER_API_KEY"),
            model="togethercomputer/m2-bert-80M-8k-retrieval"
        )
        self.vectorstore = None
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_validity_days = 7
        self.faiss_index_path = self.cache_dir / "district_index"
        self.timestamp_file = self.cache_dir / "last_update.txt"
        logger.info("DistrictAnalyzer initialized")

    async def initialize_vectorstore(self):
        try:
            if self._is_cache_valid() and self._load_from_cache():
                logger.info("Vectorstore loaded from cache")
                self._debug_vectorstore_content()
                return True
            if await self._update_with_real_data():
                logger.info("Vectorstore updated with real-time data")
                self._debug_vectorstore_content()
                return True
            self._load_static_data()
            logger.warning("Using static fallback data for vectorstore")
            self._debug_vectorstore_content()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize vectorstore: {e}")
            self._load_static_data()
            return False

    def _debug_vectorstore_content(self):
        if not self.vectorstore:
            logger.warning("DEBUG: Vectorstore is None")
            return
        try:
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                docs = list(self.vectorstore.docstore._dict.values())
                logger.info(f"DEBUG: Vectorstore contains {len(docs)} documents")
                available_districts = []
                for doc in docs:
                    content = doc.page_content
                    match = re.search(r'Дүүрэг:\s*(.+)', content)
                    if match:
                        district = match.group(1).strip()
                        available_districts.append(district)
                        logger.debug(f"DEBUG: Found district '{district}' in vectorstore")
                logger.info(f"DEBUG: Available districts: {available_districts}")
            else:
                logger.warning("DEBUG: Vectorstore doesn't have expected docstore structure")
        except Exception as e:
            logger.error(f"DEBUG: Error examining vectorstore: {e}")

    def _is_cache_valid(self) -> bool:
        if not self.timestamp_file.exists():
            return False
        try:
            with open(self.timestamp_file, 'r') as f:
                timestamp_str = f.read().strip()
            last_update = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - last_update
            return age.days < self.cache_validity_days
        except Exception:
            return False

    def _load_from_cache(self) -> bool:
        try:
            if self.faiss_index_path.with_suffix('.faiss').exists():
                self.vectorstore = FAISS.load_local(
                    folder_path=str(self.cache_dir),
                    index_name="district_index",
                    embeddings=self.embeddings_model,
                    allow_dangerous_deserialization=True
                )
                return True
        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
        return False

    def _save_to_cache(self):
        try:
            if self.vectorstore:
                self.vectorstore.save_local(
                    folder_path=str(self.cache_dir),
                    index_name="district_index"
                )
                with open(self.timestamp_file, 'w') as f:
                    f.write(datetime.now().isoformat())
                logger.info("Vectorstore saved to cache")
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")

    async def _update_with_real_data(self) -> bool:
        try:
            if not self.property_retriever:
                return False
            documents = await self.property_retriever.retrieve_vector_data()
            if documents:
                self.vectorstore = FAISS.from_documents(documents, self.embeddings_model)
                self._save_to_cache()
                logger.info(f"Vectorstore updated with {len(documents)} documents")
                return True
        except Exception as e:
            logger.error(f"Failed to update with real data: {e}")
        return False

    def _load_static_data(self):
        static_docs = [
            Document(page_content=f"""Дүүрэг: Баянгол
Нийт байрны 1м2 дундаж үнэ: 3500000 төгрөг
2 өрөө байрны 1м2 дундаж үнэ: 3600000 төгрөг  
3 өрөө байрны 1м2 дундаж үнэ: 3400000 төгрөг
Баянгол дүүрэг нь хотын төв хэсэгт байрладаг дундаж үнэтэй дүүрэг."""),
            Document(page_content=f"""Дүүрэг: Хан-Уул
Нийт байрны 1м2 дундаж үнэ: 4000000 төгрөг
2 өрөө байрны 1м2 дундаж үнэ: 4100000 төгрөг
3 өрөө байрны 1м2 дундаж үнэ: 3900000 төгрөг
Хан-Уул дүүрэг нь баруун урд байрладаг үнэ өндөр дүүрэг."""),
            Document(page_content=f"""Дүүрэг: Сонгинохайрхан  
Нийт байрны 1м2 дундаж үнэ: 2800000 төгрөг
2 өрөө байрны 1м2 дундаж үнэ: 2900000 төгрөг
3 өрөө байрны 1м2 дундаж үнэ: 2700000 төгрөг
Сонгинохайрхан дүүрэг нь хотын баруун хэсэгт байрладаг том дүүрэг."""),
            Document(page_content=f"""Дүүрэг: Сүхбаатар
Нийт байрны 1м2 дундаж үнэ: 4500000 төгрөг  
2 өрөө байрны 1м2 дундаж үнэ: 4600000 төгрөг
3 өрөө байрны 1м2 дундаж үнэ: 4400000 төгрөг
Сүхбаатар дүүрэг нь хотын хамгийн үнэтэй бүсүүдийн нэг."""),
            Document(page_content=f"""Дүүрэг: Чингэлтэй
Нийт байрны 1м2 дундаж үнэ: 3800000 төгрөг
2 өрөө байрны 1м2 дундаж үнэ: 3900000 төгрөг  
3 өрөө байрны 1м2 дундаж үнэ: 3700000 төгрөг
Чингэлтэй дүүрэг нь хотын төв хэсэгт оршдог."""),
            Document(page_content=f"""Дүүрэг: Баянзүрх
Нийт байрны 1м2 дундаж үнэ: 3200000 төгрөг
2 өрөө байрны 1м2 дундаж үнэ: 3300000 төгрөг
3 өрөө байрны 1м2 дундаж үнэ: 3100000 төгрөг  
Баянзүрх дүүрэг нь Улаанбаатар хотын хамгийн том дүүрэг.""")
        ]
        try:
            self.vectorstore = FAISS.from_documents(static_docs, self.embeddings_model)
            logger.info("Static fallback data loaded")
        except Exception as e:
            logger.error(f"Failed to load static data: {e}")

    def _extract_district_name(self, query: str) -> Optional[str]:
        query_lower = query.lower().strip()
        logger.debug(f"Extracting district from: '{query}'")
        for variation, canonical in DISTRICT_VARIATIONS.items():
            if re.search(r'\b' + re.escape(variation) + r'\b', query_lower):
                logger.info(f"Found district: {canonical} (exact match: {variation})")
                return canonical
        for variation, canonical in DISTRICT_VARIATIONS.items():
            if variation in query_lower:
                logger.info(f"Found district: {canonical} (partial match: {variation})")
                return canonical
        district_match = re.search(r'(\S+)\s*дүүр', query_lower)
        if district_match:
            district_part = district_match.group(1).strip()
            logger.debug(f"Extracted district part from pattern: '{district_part}'")
            for variation, canonical in DISTRICT_VARIATIONS.items():
                if district_part == variation or district_part in variation:
                    logger.info(f"Found district from pattern: {canonical}")
                    return canonical
        logger.warning(f"No district name found in query: '{query}'")
        return None

    async def analyze_district(self, query: str) -> str:
        logger.info(f"Analyzing district query: {query[:100]}...")
        if self._is_comparison_query(query):
            return await self._compare_all_districts()
        district_name = self._extract_district_name(query)
        if not district_name:
            logger.warning("No district name found in query, using search fallback")
            return await self._search_fallback(query, "No district name found")
        logger.info(f"Processing analysis for district: {district_name}")
        try:
            result = await self._analyze_from_vectorstore_enhanced(district_name, query)
            if self._is_valid_result(result):
                logger.info(f"Successfully analyzed {district_name} using vectorstore")
                return result
            else:
                logger.warning(f"Vectorstore result invalid for {district_name}")
        except Exception as e:
            logger.warning(f"Vectorstore analysis failed for {district_name}: {e}")
        logger.info(f"Using search fallback for {district_name}")
        return await self._search_fallback(query, f"Vectorstore failed for {district_name}")

    def _is_comparison_query(self, query: str) -> bool:
        comparison_keywords = ['харьцуул', 'зэрэгцүүл', 'бүх', 'бүгд', 'compare']
        return any(keyword in query.lower() for keyword in comparison_keywords)

    async def _analyze_from_vectorstore_enhanced(self, district_name: str, query: str) -> str:
        if not self.vectorstore:
            raise Exception("Vectorstore not available")
        logger.info(f"Searching vectorstore for district: {district_name}")
        search_queries = [
            f"{district_name}",
            f"Дүүрэг: {district_name}",
            f"{district_name} дүүрэг",
        ]
        for variation, canonical in DISTRICT_VARIATIONS.items():
            if canonical == district_name:
                search_queries.extend([
                    f"{variation}",
                    f"Дүүрэг: {variation}",
                    f"{variation} дүүрэг"
                ])
        relevant_docs = []
        for search_query in search_queries:
            try:
                logger.debug(f"Trying search query: '{search_query}'")
                docs = self.vectorstore.similarity_search(search_query, k=3)
                for doc in docs:
                    content_lower = doc.page_content.lower()
                    district_lower = district_name.lower()
                    if (district_lower in content_lower or
                            f"дүүрэг: {district_lower}" in content_lower or
                            any(var in content_lower for var, canon in DISTRICT_VARIATIONS.items() if
                                canon == district_name)):
                        if doc not in relevant_docs:
                            relevant_docs.append(doc)
                            logger.debug(f"Found relevant document for {district_name}")
                if relevant_docs:
                    break
            except Exception as e:
                logger.warning(f"Search query failed: '{search_query}' - {e}")
                continue
        if not relevant_docs:
            logger.warning(f"No documents found via similarity search for {district_name}, trying manual search")
            try:
                if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                    all_docs = list(self.vectorstore.docstore._dict.values())
                    logger.debug(f"Manually searching through {len(all_docs)} documents")
                    for doc in all_docs:
                        content = doc.page_content
                        district_match = re.search(r'Дүүрэг:\s*(.+)', content)
                        if district_match:
                            doc_district = district_match.group(1).strip()
                            if doc_district == district_name:
                                relevant_docs.append(doc)
                                logger.info(f"Found {district_name} via manual search")
                                break
            except Exception as e:
                logger.error(f"Manual search failed: {e}")
        if not relevant_docs:
            raise Exception(f"No relevant documents found for {district_name}")
        content_parts = []
        for doc in relevant_docs:
            content_parts.append(doc.page_content)
        combined_content = "\n\n".join(content_parts)
        logger.info(f"Found {len(relevant_docs)} relevant documents for {district_name}")
        logger.debug(f"Combined content length: {len(combined_content)} chars")
        return await self._generate_analysis_with_context(district_name, query, combined_content)

    async def _generate_analysis_with_context(self, district_name: str, query: str, vector_content: str) -> str:
        prompt = PromptTemplate.from_template(
            "You are a professional real estate consultant.\n\nVECTORSTORE DATA:\n{vector_content}\n\nUsing the above information from the vectorstore, provide a detailed analysis about the {district} district.\n\nYour answer MUST follow this structure:\n1. Price level and trends\n2. Advantages and disadvantages of the district\n3. Investment opportunities\n4. Recommendations\n\nIMPORTANT REQUIREMENTS:\n- Use the exact numbers from the vectorstore data (for example: 4,813,578 төгрөг)\n- Your answer MUST be written ONLY in MONGOLIAN language\n- Do NOT use any English words\n- Base your answer strictly on the facts and numbers from the vectorstore data")
        try:
            chain = prompt | self.llm | StrOutputParser()
            analysis = await chain.ainvoke({
                "district": district_name,
                "vector_content": vector_content
            })
            analysis = re.sub(r'\n{3,}', '\n\n', analysis)
            analysis = analysis.strip()
            if not analysis or len(analysis) < 100:
                logger.warning(f"Generated analysis too short for {district_name}")
                return await self._generate_fallback_analysis(district_name, vector_content)
            english_indicators = ['the', 'and', 'or', 'in', 'of', 'to', 'for', 'with', 'by']
            english_count = sum(1 for word in english_indicators if word in analysis.lower())
            if english_count > 5:
                logger.warning(f"Analysis appears to be in English for {district_name}, regenerating...")
                return await self._generate_fallback_analysis(district_name, vector_content)
            return analysis
        except Exception as e:
            logger.error(f"LLM analysis failed for {district_name}: {e}")
            return await self._generate_fallback_analysis(district_name, vector_content)

    async def _generate_fallback_analysis(self, district_name: str, vector_content: str) -> str:
        try:
            price_match = re.search(r'Нийт байрны 1м2 дундаж үнэ:\s*([\d\s,]+)\s*төгрөг', vector_content)
            avg_price = price_match.group(1).strip() if price_match else "тодорхойгүй"
            return f"""**{district_name} дүүргийн шинжилгээ**

1. **Үнийн түвшин ба чиг хандлага**
{district_name} дүүргийн нийт байрны 1м² дундаж үнэ: {avg_price} төгрөг байна.

2. **Дүүргийн давуу болон сул талууд**
Дүүргийн байршил болон инфраструктурын талаар нэмэлт мэдээлэл шаардлагатай.

3. **Хөрөнгө оруулалтын боломж**
Одоогийн үнийн түвшинг үндэслэн хөрөнгө оруулалтын боломжийг судлах хэрэгтэй.

4. **Зөвлөмж**
{district_name} дүүрэгт хөрөнгө оруулахын өмнө зах зээлийн судалгаа хийхийг зөвлөж байна."""
        except Exception as e:
            logger.error(f"Fallback analysis generation failed: {e}")
            return f"{district_name} дүүргийн шинжилгээ боловсруулахад алдаа гарлаа."

    async def _search_fallback(self, query: str, reason: str) -> str:
        logger.info(f"Using search fallback: {reason}")
        if not self.search_tool:
            return f"Уучлаарай, {query} талаар мэдээлэл олдсонгүй. Хайлтын хэрэгсэл байхгүй."
        try:
            district_name = self._extract_district_name(query) or "дүүрэг"
            search_query = f"{district_name} дүүрэг үл хөдлөх хөрөнгийн үнэ Улаанбаатар Mongolia real estate"
            results = await self.search_tool.ainvoke(search_query)
            if not results:
                return f"Уучлаарай, {query} талаар интернетээс мэдээлэл олдсонгүй."
            content = self._process_search_results(results)
            if not content:
                return f"Уучлаарай, {query} талаар боловсруулах мэдээлэл олдсонгүй."
            analysis = await self._generate_search_analysis(district_name, query, content)
            return f"{analysis}\n\n(Энэ мэдээлэл интернет хайлтаас авсан болно.)"
        except Exception as e:
            logger.error(f"Search fallback failed: {e}")
            return f"Уучлаарай, {query} талаар мэдээлэл хайхад алдаа гарлаа."

    async def _generate_search_analysis(self, district_name: str, query: str, search_content: str) -> str:
        prompt = PromptTemplate.from_template(
            "You are a real estate consultant in Mongolia.\n\nSEARCH RESULTS:\n{search_content}\n\nUsing the above information, provide an analysis about the {district} district.\n\nYour answer MUST follow this structure:\n1. Price level and trends\n2. Advantages and disadvantages of the district\n3. Investment opportunities\n4. Recommendations\n\nSPECIAL REQUIREMENTS:\n- Your answer MUST be written ONLY in MONGOLIAN language\n- Do NOT use any English words at all\n- If the information is insufficient, write 'мэдээлэл дутмаг' (information is insufficient)")
        try:
            chain = prompt | self.llm | StrOutputParser()
            analysis = await chain.ainvoke({
                "district": district_name,
                "search_content": search_content[:2000]
            })
            analysis = analysis.strip()
            if not analysis or 'english' in analysis.lower():
                return f"{district_name} дүүргийн талаар хайлтын мэдээллээс шинжилгээ хийхэд алдаа гарлаа."
            return analysis
        except Exception as e:
            logger.error(f"Search analysis generation failed: {e}")
            return f"{district_name} дүүргийн хайлтын шинжилгээ боловсруулахад алдаа гарлаа."

    def _process_search_results(self, results: List[Dict]) -> str:
        content_parts = []
        seen_content = set()
        for result in results[:5]:
            if isinstance(result, dict):
                content = result.get('content', '') or result.get('snippet', '')
                title = result.get('title', '')
                if len(content) < 50 or content in seen_content:
                    continue
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()
                if title:
                    content_parts.append(f"Гарчиг: {title}\n{content}")
                else:
                    content_parts.append(content)
                seen_content.add(content)
        return "\n\n".join(content_parts)

    async def _compare_all_districts(self) -> str:
        if not self.vectorstore:
            return "Дүүргүүдийн харьцуулалт хийхэд мэдээллийн сан байхгүй байна."
        try:
            all_docs = []
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = list(self.vectorstore.docstore._dict.values())
            if not all_docs:
                return "Дүүргүүдийн мэдээлэл байхгүй байна."
            districts_data = []
            for doc in all_docs:
                district_info = self._parse_district_data_enhanced(doc.page_content)
                if district_info:
                    districts_data.append(district_info)
            if not districts_data:
                return "Дүүргүүдийн мэдээлэл боловсруулахад алдаа гарлаа."
            districts_data.sort(key=lambda x: x.get('overall_avg', 0), reverse=True)
            response = "**Улаанбаатар хотын дүүргүүдийн орон сууцны үнийн харьцуулалт:**\n\n"
            for i, district in enumerate(districts_data, 1):
                name = district.get('name', 'Тодорхойгүй')
                overall = district.get('overall_avg', 0)
                two_room = district.get('two_room_avg', 0)
                three_room = district.get('three_room_avg', 0)
                response += f"**{i}. {name} дүүрэг:**\n"
                if overall > 0:
                    response += f"   • Ерөнхий дундаж: {int(overall):,}₮/м²\n".replace(',', ' ')
                if two_room > 0:
                    response += f"   • 2 өрөө: {int(two_room):,}₮/м²\n".replace(',', ' ')
                if three_room > 0:
                    response += f"   • 3 өрөө: {int(three_room):,}₮/м²\n".replace(',', ' ')
                response += "\n"
            return response
        except Exception as e:
            logger.error(f"District comparison failed: {e}")
            return "Дүүргүүдийн харьцуулалт хийхэд алдаа гарлаа."

    def _parse_district_data_enhanced(self, content: str) -> Optional[Dict]:
        try:
            district_info = {}
            name_match = re.search(r'Дүүрэг:\s*(.+)', content)
            if name_match:
                district_info['name'] = name_match.group(1).strip()
            else:
                return None
            price_patterns = [
                (r'Нийт байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'overall_avg'),
                (r'2 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'two_room_avg'),
                (r'3 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'three_room_avg'),
                (r'1 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'one_room_avg'),
                (r'4 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'four_room_avg'),
            ]
            for pattern, key in price_patterns:
                match = re.search(pattern, content)
                if match:
                    price_value = self._parse_price_enhanced(match.group(1))
                    if price_value > 0:
                        district_info[key] = price_value
            return district_info if district_info.get('overall_avg', 0) > 0 else None
        except Exception as e:
            logger.debug(f"Error parsing district data: {e}")
            return None

    def _parse_price_enhanced(self, price_str: str) -> float:
        try:
            cleaned = price_str.replace(' ', '').replace(',', '').replace('төгрөг', '').strip()
            return float(cleaned)
        except:
            return 0.0

    def _is_valid_result(self, result: str) -> bool:
        if not result or len(result.strip()) < 50:
            return False
        error_indicators = [
            "мэдээлэл олдсонгүй",
            "алдаа гарлаа",
            "хайлтаас мэдээлэл олдсонгүй",
            "интернетээс мэдээлэл олдсонгүй",
            "error",
            "failed"
        ]
        result_lower = result.lower()
        return not any(indicator in result_lower for indicator in error_indicators)

    def get_vectorstore_status(self) -> Dict[str, Any]:
        status = {
            "initialized": self.vectorstore is not None,
            "cache_valid": self._is_cache_valid(),
            "document_count": 0,
            "available_districts": []
        }
        if self.vectorstore and hasattr(self.vectorstore, 'docstore'):
            try:
                docs = list(self.vectorstore.docstore._dict.values())
                status["document_count"] = len(docs)
                for doc in docs:
                    match = re.search(r'Дүүрэг:\s*(.+)', doc.page_content)
                    if match:
                        district = match.group(1).strip()
                        if district not in status["available_districts"]:
                            status["available_districts"].append(district)
            except:
                pass
        return status