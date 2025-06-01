# real_estate_assistant/agents/property_retriever.py - Үл хөдлөх хөрөнгийн мэдээлэл авагч
import logging
import asyncio
from collections import defaultdict
import json
from typing import Dict, Any, List

import httpx
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from utils.unegui_scraper import UneguiScraper
from data_processors.property_aggregator import PropertyAggregator
from config.constants import DISTRICT_URL_PATHS, BASE_LISTING_URL, MAX_PAGES_TO_SCRAPE_PER_DISTRICT

logger = logging.getLogger(__name__)

class PropertyRetriever:
    def __init__(self, llm=None): # LLM нь энэ шинэчилсэн классд шууд ашиглагдахгүй, гэхдээ нийцтэй байлгахын тулд үлдээсэн
        self.llm = llm # Хэрэв LLM энд ашиглагдахгүй бол устгаж болно
        self.scraper = UneguiScraper()
        self.aggregator = PropertyAggregator()
        self.district_url_paths = DISTRICT_URL_PATHS

    async def retrieve_property_details(self, url: str) -> Dict[str, Any]:
        """
        Unegui.mn-ийн үл хөдлөх хөрөнгийн дэлгэрэнгүй мэдээллийг UneguiScraper ашиглан авч задлана.
        """
        return await self.scraper.retrieve_property_details(url)

    async def retrieve_vector_data(self) -> List[Document]:
        """
        Unegui.mn жагсаалтын хуудаснуудаас бодит цагийн мэдээлэл цуглуулж,
        дүүрэг болон өрөөний төрлөөр дундаж үнийг нэгтгэн,
        DistrictAnalyzer-ийн вектор санд зориулсан Баримтуудыг буцаана.
        """
        aggregated_data = defaultdict(lambda: defaultdict(lambda: {'total_price_per_sqm': 0.0, 'count': 0}))

        logger.info("Starting real-time data collection from Unegui.mn...")

        for district_name, path_segment in self.district_url_paths.items():
            logger.info(f"Collecting data for district: {district_name}")

            district_url = BASE_LISTING_URL + path_segment
            max_pages = MAX_PAGES_TO_SCRAPE_PER_DISTRICT

            for page_num in range(1, max_pages + 1):
                page_url = district_url
                if page_num > 1:
                    page_url += f"&page={page_num}"

                logger.info(f"  {page_num} дахь хуудсыг {district_name} дүүргийн хувьд скрапинг хийж байна: {page_url}")

                try:
                    response = await self.scraper.async_client.get(page_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")

                    listings = soup.find_all("div", class_="advert js-item-listing")
                    logger.info(f"  {page_num} дахь хуудсанд {len(listings)} мэдээлэл олдсон")

                    for listing in listings:
                        try:
                            prop_data = self.scraper.extract_listing_data(listing)
                            prop_data['scraped_district'] = district_name

                            logger.debug(f"  Raw extracted data: {json.dumps(prop_data, ensure_ascii=False, indent=2)}")

                            if self.aggregator._is_valid_residential_property(prop_data):
                                self.aggregator.aggregate_property_data(prop_data, aggregated_data)
                                logger.info(f"  ✅ Added residential apartment: {prop_data.get('title', 'N/A')[:50]}...")
                            else:
                                property_type = self.aggregator._classify_property_type(prop_data)
                                logger.info(f"  ❌ Excluded {property_type}: {prop_data.get('title', 'N/A')[:50]}...")

                        except Exception as e:
                            logger.error(f"  Error processing listing: {e}")
                            continue

                    await asyncio.sleep(1) # Delay between page requests

                except httpx.RequestError as e:
                    logger.error(f"  Network error fetching {page_url}: {e}")
                    break
                except Exception as e:
                    logger.error(f"  Error processing page {page_url}: {e}")
                    continue

            logger.info(f"Finished collecting data for {district_name}")

        district_documents = self.aggregator.generate_district_documents(aggregated_data)

        logger.info("\n" + "=" * 80)
        logger.info("📊 REAL-TIME DATA COLLECTION SUMMARY")
        logger.info("=" * 80)

        if not district_documents:
            logger.warning("❌ No valid residential apartment data was collected!")
            logger.info("This could be due to:")
            logger.info("- Network connectivity issues")
            logger.info("- Website structure changes")
            logger.info("- All properties being filtered out")
            return []

        total_properties = sum(
            room_types.get('overall', {}).get('count', 0)
            for room_types in aggregated_data.values()
        )

        logger.info(f"✅ Successfully collected data from {len(district_documents)} districts")
        logger.info(f"📈 Total residential apartments analyzed: {total_properties}")

        for district, room_types in aggregated_data.items():
            overall_info = room_types.get('overall', {'total_price_per_sqm': 0, 'count': 0})
            two_room_info = room_types.get('2_rooms', {'total_price_per_sqm': 0, 'count': 0})
            three_room_info = room_types.get('3_rooms', {'total_price_per_sqm': 0, 'count': 0})

            overall_avg = overall_info['total_price_per_sqm'] / overall_info['count'] if overall_info['count'] > 0 else 0

            logger.info(f"\n🏢 {district}:")
            logger.info(f"   📊 Total apartments: {overall_info['count']}")
            logger.info(f"   💰 Average price/m²: {overall_avg:,.0f} ₮")
            logger.info(f"   🏠 2-room apartments: {two_room_info['count']}")
            logger.info(f"   🏠 3-room apartments: {three_room_info['count']}")

        logger.info("\n" + "=" * 80)
        logger.info("📋 GENERATED VECTOR STORE DOCUMENTS")
        logger.info("=" * 80)

        for i, doc in enumerate(district_documents, 1):
            logger.info(f"\n📄 Document {i}:")
            logger.info("-" * 40)
            logger.info(doc.page_content)
            logger.info("-" * 40)

        logger.info(f"\n✅ Vector data collection completed successfully!")
        logger.info(f"📦 Generated {len(district_documents)} documents for DistrictAnalyzer")
        logger.info("=" * 80)

        return district_documents

    async def close(self):
        """Скрапер дахь async клиентийг хаана."""
        await self.scraper.close()