import logging
import asyncio
from collections import defaultdict
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.documents import Document
from utils.unegui_scraper import UneguiScraper
from data_processors.property_aggregator import PropertyAggregator
from config.constants import DISTRICT_URL_PATHS, BASE_LISTING_URL

logger = logging.getLogger(__name__)

MAX_PAGES_PER_DISTRICT = 2
MAX_LISTINGS_PER_PAGE = 20
REQUEST_DELAY = 1.0

class PropertyRetriever:
    def __init__(self, llm=None):
        self.llm = llm
        self.scraper = UneguiScraper()
        self.aggregator = PropertyAggregator()
        self.district_url_paths = DISTRICT_URL_PATHS

    async def retrieve_property_details(self, url: str) -> Dict[str, Any]:
        try:
            return await self.scraper.retrieve_property_details(url)
        except Exception as e:
            logger.error(f"Error retrieving property details: {e}")
            return {"url": url, "error": str(e)}

    async def retrieve_vector_data(self) -> List[Document]:
        logger.info("Starting real-time data collection...")

        aggregated_data = defaultdict(lambda: defaultdict(lambda: {'total_price_per_sqm': 0.0, 'count': 0}))

        total_processed = 0
        total_errors = 0

        for district_name, path_segment in self.district_url_paths.items():
            logger.info(f"Collecting data for {district_name}...")

            try:
                district_stats = await self._collect_district_data(
                    district_name, path_segment, aggregated_data
                )
                total_processed += district_stats['processed']
                total_errors += district_stats['errors']

            except Exception as e:
                logger.error(f"Failed to collect data for {district_name}: {e}")
                total_errors += 1
                continue

        documents = self._generate_documents(aggregated_data)

        logger.info(f"Data collection completed:")
        logger.info(f"  - Districts processed: {len(documents)}")
        logger.info(f"  - Total properties: {total_processed}")
        logger.info(f"  - Errors: {total_errors}")

        return documents

    async def _collect_district_data(self, district_name: str, path_segment: str,
                                     aggregated_data: Dict) -> Dict[str, int]:
        district_url = BASE_LISTING_URL + path_segment
        processed_count = 0
        error_count = 0

        for page_num in range(1, MAX_PAGES_PER_DISTRICT + 1):
            page_url = district_url
            if page_num > 1:
                page_url += f"&page={page_num}"

            logger.debug(f"  Scraping page {page_num} for {district_name}")

            try:
                page_stats = await self._scrape_page(
                    page_url, district_name, aggregated_data
                )
                processed_count += page_stats['processed']
                error_count += page_stats['errors']

                await asyncio.sleep(REQUEST_DELAY)

            except Exception as e:
                logger.warning(f"  Page {page_num} failed for {district_name}: {e}")
                error_count += 1
                continue

        logger.info(f"  {district_name}: {processed_count} properties, {error_count} errors")
        return {'processed': processed_count, 'errors': error_count}

    async def _scrape_page(self, page_url: str, district_name: str,
                           aggregated_data: Dict) -> Dict[str, int]:
        try:
            response = await self.scraper.async_client.get(page_url)
            response.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            listings = soup.find_all("div", class_="advert js-item-listing")

            processed_count = 0
            error_count = 0

            for listing in listings[:MAX_LISTINGS_PER_PAGE]:
                try:
                    prop_data = self.scraper.extract_listing_data(listing)
                    prop_data['scraped_district'] = district_name

                    if self._is_valid_property(prop_data):
                        self.aggregator.aggregate_property_data(prop_data, aggregated_data)
                        processed_count += 1
                    else:
                        logger.debug(f"    Invalid property: {prop_data.get('title', 'N/A')[:30]}...")

                except Exception as e:
                    logger.debug(f"    Error processing listing: {e}")
                    error_count += 1
                    continue

            return {'processed': processed_count, 'errors': error_count}

        except Exception as e:
            logger.error(f"Error scraping page {page_url}: {e}")
            raise

    def _is_valid_property(self, prop_data: Dict[str, Any]) -> bool:
        try:
            if not prop_data.get('title'):
                return False

            price_per_sqm = prop_data.get('price_per_sqm')
            area_sqm = prop_data.get('area_sqm')
            room_count = prop_data.get('room_count')

            if not all([price_per_sqm, area_sqm, room_count]):
                return False

            if not (500_000 <= price_per_sqm <= 20_000_000):
                return False

            if not (15 <= area_sqm <= 500):
                return False

            if not (1 <= room_count <= 10):
                return False

            title_lower = prop_data.get('title', '').lower()
            exclusions = ['зогсоол', 'газар', 'агуулах', 'үйлдвэр', 'гараж', 'оффис']
            if any(exclusion in title_lower for exclusion in exclusions):
                return False

            return True

        except Exception:
            return False

    def _generate_documents(self, aggregated_data: Dict) -> List[Document]:
        if not aggregated_data:
            logger.warning("No aggregated data available")
            return self._get_fallback_documents()

        documents = []

        for district, room_data in aggregated_data.items():
            try:
                overall_info = room_data.get('overall', {'total_price_per_sqm': 0, 'count': 0})

                if overall_info['count'] == 0:
                    continue

                overall_avg = overall_info['total_price_per_sqm'] / overall_info['count']

                content_parts = [
                    f"Дүүрэг: {district}",
                    f"Нийт байрны 1м2 дундаж үнэ: {int(overall_avg):,} төгрөг".replace(',', ' ')
                ]

                for room_key, room_info in room_data.items():
                    if room_key != 'overall' and room_info['count'] > 0:
                        room_count = room_key.split('_')[0]
                        room_avg = room_info['total_price_per_sqm'] / room_info['count']
                        content_parts.append(
                            f"{room_count} өрөө байрны 1м2 дундаж үнэ: {int(room_avg):,} төгрөг".replace(',', ' ')
                        )

                content_parts.extend([
                    f"Цуглуулсан өгөгдөл: {overall_info['count']} орон сууц",
                    f"Дата цуглуулсан огноо: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ])

                content = "\n".join(content_parts)
                documents.append(Document(page_content=content))

                logger.debug(f"Generated document for {district} ({overall_info['count']} properties)")

            except Exception as e:
                logger.error(f"Error generating document for {district}: {e}")
                continue

        if not documents:
            logger.warning("No documents generated, using fallback")
            return self._get_fallback_documents()

        return documents

    def _get_fallback_documents(self) -> List[Document]:
        logger.info("Generating fallback documents")

        fallback_data = [
            ("Баянгол", 3500000, 3600000, 3400000),
            ("Хан-Уул", 4000000, 4100000, 3900000),
            ("Сонгинохайрхан", 2800000, 2900000, 2700000),
            ("Сүхбаатар", 4500000, 4600000, 4400000),
            ("Чингэлтэй", 3800000, 3900000, 3700000),
            ("Баянзүрх", 3200000, 3300000, 3100000)
        ]

        documents = []
        for district, overall, two_room, three_room in fallback_data:
            content = f"""Дүүрэг: {district}
Нийт байрны 1м2 дундаж үнэ: {overall:,} төгрөг
2 өрөө байрны 1м2 дундаж үнэ: {two_room:,} төгрөг
3 өрөө байрны 1м2 дундаж үнэ: {three_room:,} төгрөг
{district} дүүрэг нь Улаанбаатар хотын нэгэн дүүрэг.
Цуглуулсан өгөгдөл: fallback data
Дата цуглуулсан огноо: {datetime.now().strftime('%Y-%m-%d %H:%M')}""".replace(',', ' ')

            documents.append(Document(page_content=content))

        return documents

    async def get_property_data_for_district(self, district_name: str) -> Optional[str]:
        try:
            district_price_factors = {
                "Чингэлтэй": 1.2,
                "Сүхбаатар": 1.3,
                "Баянгол": 0.9,
                "Хан-Уул": 1.1,
                "Баянзүрх": 0.85,
                "Сонгинохайрхан": 0.8
            }

            base_price = 3500000
            factor = district_price_factors.get(district_name, 1.0)
            estimated_price = int(base_price * factor)

            return f"""Дүүрэг: {district_name}
Тооцоолсон дундаж үнэ: {estimated_price:,} төгрөг/м²
Мэдээлэл: property_retriever-ээс тооцоолсон үнэ
Огноо: {datetime.now().strftime('%Y-%m-%d')}""".replace(',', ' ')

        except Exception as e:
            logger.error(f"Error getting district data for {district_name}: {e}")
            return None

    async def close(self):
        try:
            await self.scraper.close()
        except Exception as e:
            logger.error(f"Error closing scraper: {e}")