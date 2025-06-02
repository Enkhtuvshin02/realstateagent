# Enhanced district_analyzer.py with garbage response handling
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

# Enhanced district mappings
DISTRICT_NAMES = [
    "Баянгол", "Баянзүрх", "Сонгинохайрхан", "Сүхбаатар",
    "Чингэлтэй", "Хан-Уул", "Налайх", "Багануур", "Багахангай"
]

DISTRICT_VARIATIONS = {
    "баянгол": "Баянгол",
    "баянзүрх": "Баянзүрх",
    "баянзурх": "Баянзүрх",
    "сонгинохайрхан": "Сонгинохайрхан",
    "сүхбаатар": "Сүхбаатар",
    "сухбаатар": "Сүхбаатар",
    "чингэлтэй": "Чингэлтэй",
    "чингэлтэи": "Чингэлтэй",
    "хан-уул": "Хан-Уул",
    "хануул": "Хан-Уул",
    "хан уул": "Хан-Уул",
    "khan-uul": "Хан-Уул",
    "khanuul": "Хан-Уул",
    "khan uul": "Хан-Уул",
    "налайх": "Налайх",
    "багануур": "Багануур",
    "багахангай": "Багахангай"
}


class ResponseValidator:
    """Enhanced response validator to handle garbage outputs"""

    @staticmethod
    def is_garbage_response(text: str) -> bool:
        """Detect if response contains garbage/repeated content"""
        if not text or len(text.strip()) < 20:
            return True

        # Check for excessive repetition of characters
        if re.search(r'(.)\1{20,}', text):
            logger.warning("Detected excessive character repetition")
            return True

        # Check for repeated words/phrases
        words = text.split()
        if len(words) > 10:
            # Count repeated consecutive words
            repeated_count = 0
            for i in range(len(words) - 1):
                if words[i] == words[i + 1]:
                    repeated_count += 1

            # If more than 30% of words are repeated consecutively
            if repeated_count / len(words) > 0.3:
                logger.warning("Detected excessive word repetition")
                return True

        # Check for repeated Mongolian syllables/patterns
        mongolian_patterns = [
            r'(өөрөө){10,}',
            r'(рөөрөө){10,}',
            r'(хөхөхө){10,}',
            r'(\w{2,4})\1{15,}'  # Any 2-4 character pattern repeated 15+ times
        ]

        for pattern in mongolian_patterns:
            if re.search(pattern, text):
                logger.warning(f"Detected Mongolian pattern repetition: {pattern}")
                return True

        return False

    @staticmethod
    def clean_garbage_response(text: str) -> str:
        """Clean up response with repeated content"""
        if not text:
            return ""

        # Remove excessive character repetition (keep max 2)
        text = re.sub(r'(.)\1{3,}', r'\1\1', text)

        # Remove repeated word patterns
        text = re.sub(r'\b(\w+)(\s+\1){3,}', r'\1', text)

        # Remove repeated Mongolian patterns
        text = re.sub(r'(өөрөө){3,}', 'өөрөө', text)
        text = re.sub(r'(рөөрөө){3,}', '', text)

        # Remove excessively long words (probably garbage)
        words = text.split()
        cleaned_words = []
        for word in words:
            if len(word) < 100:  # Keep words under 100 chars
                cleaned_words.append(word)
            else:
                logger.warning(f"Removed excessively long word: {word[:50]}...")

        text = ' '.join(cleaned_words)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    @staticmethod
    def validate_mongolian_response(text: str) -> Dict[str, Any]:
        """Validate if response is proper Mongolian"""
        if not text:
            return {"is_valid": False, "reason": "empty"}

        # Check for garbage
        if ResponseValidator.is_garbage_response(text):
            return {"is_valid": False, "reason": "garbage_detected"}

        # Check minimum length
        if len(text.strip()) < 50:
            return {"is_valid": False, "reason": "too_short"}

        # Check for excessive English
        english_words = ['the', 'and', 'or', 'in', 'of', 'to', 'for', 'with', 'by',
                         'analysis', 'price', 'district', 'property', 'market']
        english_count = sum(1 for word in english_words if word.lower() in text.lower())

        if english_count > 5:
            return {"is_valid": False, "reason": "too_much_english"}

        # Check for error indicators
        error_patterns = [
            "мэдээлэл олдсонгүй",
            "алдаа гарлаа",
            "error",
            "failed"
        ]

        has_errors = any(pattern in text.lower() for pattern in error_patterns)
        if has_errors:
            return {"is_valid": False, "reason": "contains_errors"}

        return {"is_valid": True, "reason": "valid"}


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

        # Cache settings
        self.cache_validity_days = 7
        self.faiss_index_path = self.cache_dir / "district_index"
        self.timestamp_file = self.cache_dir / "last_update.txt"

        # Response validator
        self.validator = ResponseValidator()

        logger.info("DistrictAnalyzer initialized with enhanced validation")

    async def initialize_vectorstore(self):
        """Initialize vectorstore with simplified logic"""
        try:
            # Try to load from cache first
            if self._is_cache_valid() and self._load_from_cache():
                logger.info("Vectorstore loaded from cache")
                return True

            # If cache invalid or loading failed, try to update with real data
            if await self._update_with_real_data():
                logger.info("Vectorstore updated with real-time data")
                return True

            # Fallback to static data
            self._load_static_data()
            logger.warning("Using static fallback data for vectorstore")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize vectorstore: {e}")
            self._load_static_data()
            return False

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
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
        """Load vectorstore from cache"""
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
        """Save vectorstore to cache"""
        try:
            if self.vectorstore:
                self.vectorstore.save_local(
                    folder_path=str(self.cache_dir),
                    index_name="district_index"
                )
                # Update timestamp
                with open(self.timestamp_file, 'w') as f:
                    f.write(datetime.now().isoformat())
                logger.info("Vectorstore saved to cache")
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")

    async def _update_with_real_data(self) -> bool:
        """Update vectorstore with real-time data"""
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
        """Load static fallback data"""
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
        """Enhanced district name extraction"""
        query_lower = query.lower().strip()
        logger.debug(f"Extracting district from: '{query}'")

        # Direct variation match
        for variation, canonical in DISTRICT_VARIATIONS.items():
            if re.search(r'\b' + re.escape(variation) + r'\b', query_lower):
                logger.info(f"Found district: {canonical} (exact match: {variation})")
                return canonical

        # Partial matches for compound words
        for variation, canonical in DISTRICT_VARIATIONS.items():
            if variation in query_lower:
                logger.info(f"Found district: {canonical} (partial match: {variation})")
                return canonical

        # Pattern match for "X дүүрэг"
        district_match = re.search(r'(\S+)\s*дүүр', query_lower)
        if district_match:
            district_part = district_match.group(1).strip()
            for variation, canonical in DISTRICT_VARIATIONS.items():
                if district_part == variation or district_part in variation:
                    logger.info(f"Found district from pattern: {canonical}")
                    return canonical

        return None

    async def analyze_district(self, query: str) -> str:
        """Main analysis method with enhanced error handling"""
        logger.info(f"Analyzing district query: {query[:100]}...")

        # Check for comparison request
        if self._is_comparison_query(query):
            return await self._compare_all_districts()

        # Extract district name
        district_name = self._extract_district_name(query)
        if not district_name:
            logger.warning("No district name found in query, using search fallback")
            return await self._search_fallback(query, "No district name found")

        logger.info(f"Processing analysis for district: {district_name}")

        # Try vectorstore first with enhanced retrieval
        try:
            result = await self._analyze_from_vectorstore_enhanced(district_name, query)
            validation = self.validator.validate_mongolian_response(result)

            if validation["is_valid"]:
                logger.info(f"Successfully analyzed {district_name} using vectorstore")
                return result
            else:
                logger.warning(f"Vectorstore result invalid for {district_name}: {validation['reason']}")

        except Exception as e:
            logger.warning(f"Vectorstore analysis failed for {district_name}: {e}")

        # Fallback to search
        logger.info(f"Using search fallback for {district_name}")
        return await self._search_fallback(query, f"Vectorstore failed for {district_name}")

    def _is_comparison_query(self, query: str) -> bool:
        """Check if query is asking for district comparison"""
        comparison_keywords = ['харьцуул', 'зэрэгцүүл', 'бүх', 'бүгд', 'compare']
        return any(keyword in query.lower() for keyword in comparison_keywords)

    async def _analyze_from_vectorstore_enhanced(self, district_name: str, query: str) -> str:
        """Enhanced vectorstore analysis with validation"""
        if not self.vectorstore:
            raise Exception("Vectorstore not available")

        logger.info(f"Searching vectorstore for district: {district_name}")

        # Multiple search strategies
        search_queries = [
            f"{district_name}",
            f"Дүүрэг: {district_name}",
            f"{district_name} дүүрэг",
        ]

        # Add variations if available
        for variation, canonical in DISTRICT_VARIATIONS.items():
            if canonical == district_name:
                search_queries.extend([
                    f"{variation}",
                    f"Дүүрэг: {variation}"
                ])

        relevant_docs = []

        # Try different search strategies
        for search_query in search_queries:
            try:
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

                if relevant_docs:
                    break

            except Exception as e:
                continue

        if not relevant_docs:
            # Manual search fallback
            try:
                if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                    all_docs = list(self.vectorstore.docstore._dict.values())

                    for doc in all_docs:
                        content = doc.page_content
                        district_match = re.search(r'Дүүрэг:\s*(.+)', content)
                        if district_match:
                            doc_district = district_match.group(1).strip()
                            if doc_district == district_name:
                                relevant_docs.append(doc)
                                break
            except Exception as e:
                pass

        if not relevant_docs:
            raise Exception(f"No relevant documents found for {district_name}")

        # Combine document content
        combined_content = "\n\n".join([doc.page_content for doc in relevant_docs])
        logger.info(f"Found {len(relevant_docs)} relevant documents for {district_name}")

        # Generate analysis with robust validation
        return await self._generate_analysis_with_validation(district_name, query, combined_content)

    async def _generate_analysis_with_validation(self, district_name: str, query: str, vector_content: str) -> str:
        """Generate analysis with multiple validation attempts"""

        # Enhanced prompt with garbage prevention
        prompt = PromptTemplate.from_template(
            """Та үл хөдлөх хөрөнгийн мэргэжлийн зөвлөх. 

ВЕКТОРЫН САНГИЙН МЭДЭЭЛЭЛ:
{vector_content}

{district} дүүргийн талаар дээрх мэдээллийг ашиглан ТОВЧ шинжилгээ хийнэ үү.

ЗААВАР:
1. Үнийн түвшин (векторын сангийн тоонуудыг ашиглана уу)
2. Дүүргийн онцлог
3. Хөрөнгө оруулалтын боломж
4. Зөвлөмж

ШААРДЛАГА:
- Зөвхөн МОНГОЛ хэлээр бичнэ үү
- 200 үгээс хэтрэхгүй байх
- Давтан бичихгүй байх
- Англи үг хэрэглэхгүй байх
- Тодорхой, товч мэдээлэл өгнө үү""")

        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                chain = prompt | self.llm | StrOutputParser()
                analysis = await chain.ainvoke({
                    "district": district_name,
                    "vector_content": vector_content
                })

                # Validate the response
                validation = self.validator.validate_mongolian_response(analysis)

                if validation["is_valid"]:
                    # Clean up any minor issues
                    cleaned_analysis = self.validator.clean_garbage_response(analysis)
                    logger.info(f"Generated valid analysis for {district_name} on attempt {attempt + 1}")
                    return cleaned_analysis
                else:
                    logger.warning(f"Attempt {attempt + 1} failed validation: {validation['reason']}")
                    if attempt < max_attempts - 1:
                        # Try again with stricter prompt
                        continue

            except Exception as e:
                logger.error(f"Analysis generation attempt {attempt + 1} failed: {e}")

        # All attempts failed, return fallback
        return await self._generate_fallback_analysis(district_name, vector_content)

    async def _generate_fallback_analysis(self, district_name: str, vector_content: str) -> str:
        """Generate a simple, safe fallback analysis"""
        try:
            # Extract basic info manually
            price_match = re.search(r'Нийт байрны 1м2 дундаж үнэ:\s*([\d\s,]+)\s*төгрөг', vector_content)
            avg_price = price_match.group(1).strip() if price_match else "тодорхойгүй"

            two_room_match = re.search(r'2 өрөө байрны 1м2 дундаж үнэ:\s*([\d\s,]+)\s*төгрөг', vector_content)
            two_room_price = two_room_match.group(1).strip() if two_room_match else "тодорхойгүй"

            return f"""**{district_name} дүүргийн шинжилгээ**

**Үнийн түвшин:**
- Нийт дундаж үнэ: {avg_price} төгрөг/м²
- 2 өрөө байрны дундаж: {two_room_price} төгрөг/м²

**Дүүргийн онцлог:**
{district_name} дүүрэг нь Улаанбаатар хотын нэгэн дүүрэг.

**Хөрөнгө оруулалтын боломж:**
Одоогийн үнийн түвшинг харгалзан хөрөнгө оруулалтын боломжийг судлах хэрэгтэй.

**Зөвлөмж:**
Дэлгэрэнгүй мэдээлэл авахын тулд зах зээлийн судалгаа хийхийг зөвлөж байна."""

        except Exception as e:
            logger.error(f"Fallback analysis generation failed: {e}")
            return f"{district_name} дүүргийн шинжилгээ боловсруулахад алдаа гарлаа."

    async def _search_fallback(self, query: str, reason: str) -> str:
        """Enhanced search fallback with validation"""
        logger.info(f"Using search fallback: {reason}")

        if not self.search_tool:
            return f"Уучлаарай, {query} талаар мэдээлэл олдсонгүй. Хайлтын хэрэгсэл байхгүй."

        try:
            district_name = self._extract_district_name(query) or "дүүрэг"
            search_query = f"{district_name} дүүрэг үл хөдлөх хөрөнгийн үнэ Улаанбаатар"

            results = await self.search_tool.ainvoke(search_query)

            if not results:
                return f"Уучлаарай, {query} талаар интернетээс мэдээлэл олдсонгүй."

            content = self._process_search_results(results)
            if not content:
                return f"Уучлаарай, {query} талаар боловсруулах мэдээлэл олдсонгүй."

            # Generate analysis with validation
            analysis = await self._generate_search_analysis_with_validation(district_name, query, content)

            return f"{analysis}\n\n(Энэ мэдээлэл интернет хайлтаас авсан болно.)"

        except Exception as e:
            logger.error(f"Search fallback failed: {e}")
            return f"Уучлаарай, {query} талаар мэдээлэл хайхад алдаа гарлаа."

    async def _generate_search_analysis_with_validation(self, district_name: str, query: str,
                                                        search_content: str) -> str:
        """Generate search analysis with validation"""

        prompt = PromptTemplate.from_template(
            """Та Монгол үл хөдлөх хөрөнгийн зөвлөх. 

ХАЙЛТЫН МЭДЭЭЛЭЛ:
{search_content}

{district} дүүргийн талаар дээрх мэдээллийг ашиглан ТОВЧ шинжилгээ хийнэ үү.

ШААРДЛАГА:
- Зөвхөн МОНГОЛ хэлээр бичнэ үү
- 150 үгээс хэтрэхгүй байх
- Давтан бичихгүй байх
- Англи үг хэрэглэхгүй байх
- Тодорхой мэдээлэл өгнө үү""")

        try:
            chain = prompt | self.llm | StrOutputParser()
            analysis = await chain.ainvoke({
                "district": district_name,
                "search_content": search_content[:1500]  # Limit content
            })

            # Validate and clean
            validation = self.validator.validate_mongolian_response(analysis)
            if validation["is_valid"]:
                return self.validator.clean_garbage_response(analysis)
            else:
                return f"{district_name} дүүргийн талаар хайлтын мэдээллээс тодорхой шинжилгээ хийх боломжгүй."

        except Exception as e:
            logger.error(f"Search analysis generation failed: {e}")
            return f"{district_name} дүүргийн хайлтын шинжилгээ боловсруулахад алдаа гарлаа."

    def _process_search_results(self, results: List[Dict]) -> str:
        """Process and clean search results"""
        content_parts = []
        seen_content = set()

        for result in results[:3]:  # Limit to top 3 results
            if isinstance(result, dict):
                content = result.get('content', '') or result.get('snippet', '')
                title = result.get('title', '')

                if len(content) < 50 or content in seen_content:
                    continue

                # Clean content
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()

                # Limit content length
                if len(content) > 300:
                    content = content[:300] + "..."

                if title:
                    content_parts.append(f"{title}: {content}")
                else:
                    content_parts.append(content)

                seen_content.add(content)

        return "\n\n".join(content_parts)

    async def _compare_all_districts(self) -> str:
        """Compare all districts with validation"""
        if not self.vectorstore:
            return "Дүүргүүдийн харьцуулалт хийхэд мэдээллийн сан байхгүй байна."

        try:
            # Get all documents
            all_docs = []
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = list(self.vectorstore.docstore._dict.values())

            if not all_docs:
                return "Дүүргүүдийн мэдээлэл байхгүй байна."

            # Extract district data
            districts_data = []
            for doc in all_docs:
                district_info = self._parse_district_data_enhanced(doc.page_content)
                if district_info:
                    districts_data.append(district_info)

            if not districts_data:
                return "Дүүргүүдийн мэдээлэл боловсруулахад алдаа гарлаа."

            # Sort by price
            districts_data.sort(key=lambda x: x.get('overall_avg', 0), reverse=True)

            # Format response safely
            response = "**Улаанбаатар хотын дүүргүүдийн орон сууцны үнийн харьцуулалт:**\n\n"

            for i, district in enumerate(districts_data, 1):
                if i > 8:  # Limit to prevent long responses
                    break

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
        """Enhanced district data parsing"""
        try:
            district_info = {}

            # Extract district name
            name_match = re.search(r'Дүүрэг:\s*(.+)', content)
            if name_match:
                district_info['name'] = name_match.group(1).strip()
            else:
                return None

            # Extract prices with multiple patterns
            price_patterns = [
                (r'Нийт байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'overall_avg'),
                (r'2 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'two_room_avg'),
                (r'3 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'three_room_avg'),
                (r'1 өрөө байрны 1м2?\s*дундаж үнэ:\s*([\d\s,]+)', 'one_room_avg'),
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
        """Enhanced price parsing"""
        try:
            cleaned = price_str.replace(' ', '').replace(',', '').replace('төгрөг', '').strip()
            return float(cleaned)
        except:
            return 0.0

    def get_vectorstore_status(self) -> Dict[str, Any]:
        """Get current vectorstore status"""
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

                # Extract available districts
                for doc in docs:
                    match = re.search(r'Дүүрэг:\s*(.+)', doc.page_content)
                    if match:
                        district = match.group(1).strip()
                        if district not in status["available_districts"]:
                            status["available_districts"].append(district)
            except:
                pass

        return status