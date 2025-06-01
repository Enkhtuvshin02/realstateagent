# real_estate_assistant/agents/property_retriever.py
import logging
import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from typing import Dict, Any, List, Optional
import re
import httpx
import asyncio
from collections import defaultdict
import json
import datetime

logger = logging.getLogger(__name__)


class PropertyRetriever:
    def __init__(self, llm):
        self.llm = llm
        self.feature_translations = {
            'Шал': 'Floor', 'Тагт': 'Balcony', 'Ашиглалтанд орсон он': 'Year Built',
            'Гараж': 'Garage', 'Цонх': 'Window Type', 'Барилгын давхар': 'Building Floors',
            'Хаалга': 'Door Type', 'Талбай': 'Area', 'Хэдэн давхарт': 'Floor Number',
            'Төлбөрийн нөхцөл': 'Payment Terms', 'Цонхны тоо': 'Number of Windows',
            'Барилгын явц': 'Construction Status', 'Цахилгаан шаттай эсэх': 'Has Elevator',
            'Өрөөний тоо': 'Rooms'
        }
        self.district_url_paths = {
            "Баянзүрх": "ub-bayanzrh/?type_view=line",
            "Сүхбаатар": "ulan-bator/?type_view=line",
            "Баянгол": "ub-bayangol/?type_view=line",
            "Чингэлтэй": "ub-chingeltej/?type_view=line",
            "Хан-Уул": "ub-hanuul/?type_view=line",
            "Сонгинохайрхан": "ub-songinohajrhan/?type_view=line",
            "Багануур": "ub-baganuur/?type_view=line",
            "Багахангай": "ub-bagahangaj/?type_view=line",
            "Налайх": "ub-nalajh/?type_view=line"
        }
        self.async_client = httpx.AsyncClient(timeout=30.0)

    def _find_feature(self, li_list, header):
        ret_value = 'N/A'
        for li in li_list:
            key_chars_tag = li.find("span", class_="key-chars")
            value_chars_tag = li.find("span", class_="value-chars") or li.find("a", class_="value-chars")
            if key_chars_tag and value_chars_tag:
                key_text = key_chars_tag.text.strip()
                value_text = value_chars_tag.text.strip()
                if key_text == header:
                    return value_text
        return ret_value

    def _parse_area_string(self, area_str: str) -> Optional[float]:
        if not area_str or area_str == 'N/A':
            return None
        area_str = area_str.lower().replace('м²', '').replace('мк', '').replace('мкв', '').replace('мк2', '').strip()
        match = re.search(r'(\d+\.?\d*)', area_str)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
        return None

    def _parse_room_string(self, room_str: str) -> Optional[int]:
        if not room_str or room_str == 'N/A':
            return None
        match = re.search(r'(\d+)', room_str)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return None
        return None

    def _parse_price_from_listing(self, price_text: str) -> Optional[float]:
        """Parse price from listing page with better handling of different formats"""
        if not price_text:
            return None

        logger.debug(f"[Price Debug] Raw price text: '{price_text}'")

        # Clean the price text
        price_cleaned = price_text.replace('₮', '').replace(',', '').replace(' ', '').strip()
        logger.debug(f"[Price Debug] Cleaned price text: '{price_cleaned}'")

        # Handle million format (сая)
        if 'сая' in price_cleaned.lower():
            match_million = re.search(r'(\d+\.?\d*)', price_cleaned)
            if match_million:
                try:
                    price_numeric = float(match_million.group(1)) * 1_000_000
                    logger.debug(f"[Price Debug] Million format parsed: {price_numeric}")
                    return price_numeric
                except ValueError:
                    pass

        # Handle billion format (тэрбум)
        if 'тэрбум' in price_cleaned.lower():
            match_billion = re.search(r'(\d+\.?\d*)', price_cleaned)
            if match_billion:
                try:
                    price_numeric = float(match_billion.group(1)) * 1_000_000_000
                    logger.debug(f"[Price Debug] Billion format parsed: {price_numeric}")
                    return price_numeric
                except ValueError:
                    pass

        # Handle direct number format
        match_direct = re.search(r'(\d+)', price_cleaned)
        if match_direct:
            try:
                price_numeric = float(match_direct.group(0))
                logger.debug(f"[Price Debug] Direct number parsed: {price_numeric}")
                return price_numeric
            except ValueError:
                pass

        logger.debug("[Price Debug] Could not parse price")
        return None

    def _extract_listing_data(self, listing_soup) -> Dict[str, Any]:
        """Extract data from a single listing element"""
        prop_data = {}

        # Extract title
        title_tag = listing_soup.find("a", class_="advert__content-title")
        prop_data['title'] = title_tag.text.strip() if title_tag else "N/A"

        # Extract price
        price_tag = listing_soup.find("span", class_="advert__content-price") or \
                    listing_soup.find("a", class_="advert__content-price")
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            prop_data['price_numeric'] = self._parse_price_from_listing(price_text)
            prop_data['price_raw'] = price_text
        else:
            prop_data['price_numeric'] = None
            prop_data['price_raw'] = "N/A"

        # Extract location
        location_tag = listing_soup.find("div", class_="advert__content-place")
        if location_tag:
            location_text = location_tag.text.strip()
            prop_data['full_location'] = location_text

            # Parse district from location
            if "—" in location_text:
                parts = location_text.split("—")
                if len(parts) > 1:
                    district_part = parts[1].strip()
                    prop_data['district'] = district_part.split(',')[0].strip()
                else:
                    prop_data['district'] = "N/A"
            else:
                prop_data['district'] = "N/A"
        else:
            prop_data['full_location'] = "N/A"
            prop_data['district'] = "N/A"

        # Extract area and room count from title with improved parsing
        title_lower = prop_data['title'].lower()

        # Extract area with more comprehensive patterns
        area_patterns = [
            r'(\d+\.?\d*)\s*мкв',  # 107мкв, 107 мкв
            r'(\d+\.?\d*)\s*м²',  # 85м², 85 м²
            r'(\d+\.?\d*)\s*мк\b',  # 69.7мк, 69.7 мк (word boundary to avoid matching мкв)
            r'(\d+\.?\d*)\s*квм',  # квм format
            r'(\d+\.?\d*)\s*м2',  # м2 format
            r'(\d+\.?\d*)\s*mkv',  # mkv format
            r'(\d+\.?\d*)\s*m²',  # m² format
            r'(\d+\.?\d*)\s*sqm',  # sqm format
        ]

        area_sqm = None
        for pattern in area_patterns:
            area_match = re.search(pattern, title_lower)
            if area_match:
                try:
                    extracted_area = float(area_match.group(1))
                    # Accept a broader range initially, will filter later in validation
                    if 10 <= extracted_area <= 1000:
                        area_sqm = extracted_area
                        logger.debug(f"Extracted area: {area_sqm} from '{area_match.group(0)}'")
                        break
                    else:
                        logger.debug(f"Area {extracted_area} out of range, skipping")
                except ValueError:
                    continue

        # If no area found in title, try alternative extraction from location or description
        if area_sqm is None:
            # Sometimes area is mentioned differently, e.g., "223,62мкв" with comma
            area_alt_patterns = [
                r'(\d+[,\.]\d+)\s*мкв',  # 223,62мкв or 223.62мкв
                r'(\d+[,\.]\d+)\s*м²',  # with comma/dot
                r'(\d+[,\.]\d+)\s*мк\b',  # with comma/dot
            ]

            for pattern in area_alt_patterns:
                area_match = re.search(pattern, title_lower)
                if area_match:
                    try:
                        area_str = area_match.group(1).replace(',', '.')  # Convert comma to dot
                        extracted_area = float(area_str)
                        if 10 <= extracted_area <= 1000:
                            area_sqm = extracted_area
                            logger.debug(f"Extracted area (alt): {area_sqm} from '{area_match.group(0)}'")
                            break
                    except ValueError:
                        continue

        prop_data['area_sqm'] = area_sqm

        # Extract room count with improved patterns
        room_patterns = [
            r'(\d+)\s*өрөө',  # 3 өрөө, 3өрөө
            r'(\d+)\s*room',  # 3 room (English)
            r'(\d+)\s*oroo',  # 3 oroo (transliterated)
        ]

        room_count = None
        for pattern in room_patterns:
            room_match = re.search(pattern, title_lower)
            if room_match:
                try:
                    extracted_rooms = int(room_match.group(1))
                    # Only accept reasonable room counts (1-10)
                    if 1 <= extracted_rooms <= 10:
                        room_count = extracted_rooms
                        logger.debug(f"Extracted rooms: {room_count} from '{room_match.group(0)}'")
                        break
                    else:
                        logger.debug(f"Room count {extracted_rooms} out of reasonable range, skipping")
                except ValueError:
                    continue

        prop_data['room_count'] = room_count

        # Calculate price per sqm
        if prop_data['price_numeric'] and prop_data['area_sqm'] and prop_data['area_sqm'] > 0:
            prop_data['price_per_sqm'] = prop_data['price_numeric'] / prop_data['area_sqm']
        else:
            prop_data['price_per_sqm'] = None

        return prop_data

    async def retrieve_property_details(self, url: str) -> Dict[str, Any]:
        """
        Retrieves and parses detailed property information from a Unegui.mn individual property page.
        This extracts comprehensive data from the property detail page structure.
        """
        logger.debug(f"Fetching detailed property data from: {url}")
        if "unegui.mn" not in url:
            logger.warning(f"URL is not from unegui.mn: {url}")
            return {"url": url, "error": "Not a Unegui.mn URL"}

        try:
            response = await self.async_client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            property_details = {"url": url, "price_numeric": None, "price_raw": "N/A"} # Initialize here

            # Extract title from h1.title-announcement
            title_tag = soup.find("h1", {"class": "title-announcement"})
            property_details['title'] = title_tag.text.strip() if title_tag else "N/A"
            logger.debug(f"Extracted title: {property_details['title']}")

            # Extract location from span with itemprop="address"
            location_tag = soup.find("span", {"itemprop": "address"})
            if location_tag:
                full_location_text = location_tag.text.strip()
                property_details['full_location'] = full_location_text

                # Parse district from location (format: "УБ — Сүхбаатар, 100 айл")
                district_name = "N/A"
                if "—" in full_location_text:
                    parts = full_location_text.split("—")
                    if len(parts) > 1:
                        district_part = parts[1].strip()
                        district_name = district_part.split(',')[0].strip()
                property_details['district'] = district_name
                logger.debug(f"Extracted location: {full_location_text}, District: {district_name}")
            else:
                property_details['full_location'] = "N/A"
                property_details['district'] = "N/A"

            # Extract price from multiple sources
            price_text_found = "N/A" # Use a temporary variable for price text initially

            # First, try to get price from data attribute (most reliable)
            price_data_attr = soup.find("section", {"data-price": True})
            if price_data_attr:
                try:
                    property_details['price_numeric'] = float(price_data_attr.get("data-price"))
                    price_text_found = f"{property_details['price_numeric']:,.0f} ₮"
                    logger.debug(f"Found price from data-price attribute: {property_details['price_numeric']}")
                except (ValueError, TypeError):
                    pass

            # If no data-price, try price containers
            if property_details['price_numeric'] is None:
                price_containers = [
                    soup.find("div", {"class": "announcement-price__cost"}),
                    soup.find("span", {"class": "announcement-price"}),
                    soup.find("div", {"class": "price-container"}),
                    soup.find("div", {"class": "announcement__content-price"}),
                    soup.find("span", {"class": "advert__content-price"}),
                ]

                for container in price_containers:
                    if container:
                        price_text_found = container.text.strip()
                        logger.debug(f"Found price container: {container.get('class')} with text: {price_text_found}")
                        property_details['price_numeric'] = self._parse_price_from_listing(price_text_found)
                        if property_details['price_numeric']:
                            break

            # Last resort: search page text for price patterns
            if property_details['price_numeric'] is None:
                logger.debug("No price container found, searching page text...")
                price_patterns = [
                    r'(\d+\.?\d*)\s*сая\s*₮',
                    r'(\d+\.?\d*)\s*тэрбум\s*₮',
                    r'(\d+[\s,\d]*)\s*₮'
                ]
                page_text = soup.get_text()
                for pattern in price_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        price_text_found = match.group(0)
                        property_details['price_numeric'] = self._parse_price_from_listing(price_text_found)
                        logger.debug(f"Found price in page text: {price_text_found} -> {property_details['price_numeric']}")
                        if property_details['price_numeric']:
                            break
            property_details['price_raw'] = price_text_found # Assign the found price text to price_raw
            logger.debug(f"Extracted price: {property_details['price_raw']} -> {property_details['price_numeric']}")


            # Extract all characteristics from chars-column
            characteristics_list = soup.find("ul", class_="chars-column")
            if characteristics_list:
                li_elements = characteristics_list.find_all("li")

                # Extract each characteristic
                for mongolian_header, english_key in self.feature_translations.items():
                    value = self._find_feature(li_elements, mongolian_header)
                    property_details[english_key.lower().replace(' ', '_')] = value
                    logger.debug(f"Extracted {mongolian_header}: {value}")
            else:
                logger.warning(f"Could not find 'chars-column' on {url}")
                for english_key in self.feature_translations.values():
                    property_details[english_key.lower().replace(' ', '_')] = "N/A"

            # Extract area from characteristics or title
            area_from_chars = property_details.get('area', 'N/A')
            area_sqm = self._parse_area_string(area_from_chars)

            # If no area in characteristics, try to extract from title
            if area_sqm is None:
                title_lower = property_details['title'].lower()
                area_patterns = [
                    r'(\d+\.?\d*)\s*м²',
                    r'(\d+\.?\d*)\s*мк\b',
                    r'(\d+\.?\d*)\s*мкв',
                ]
                for pattern in area_patterns:
                    area_match = re.search(pattern, title_lower)
                    if area_match:
                        try:
                            area_sqm = float(area_match.group(1))
                            break
                        except ValueError:
                            continue

            property_details['area_sqm'] = area_sqm
            logger.debug(f"Final area: {area_sqm}")

            # Extract room count from characteristics or title
            room_from_chars = property_details.get('rooms', 'N/A')
            room_count = self._parse_room_string(room_from_chars)

            # If no room count in characteristics, extract from title
            if room_count is None:
                title_lower = property_details['title'].lower()
                room_match = re.search(r'(\d+)\s*өрөө', title_lower)
                if room_match:
                    try:
                        room_count = int(room_match.group(1))
                    except ValueError:
                        pass

            property_details['room_count'] = room_count
            logger.debug(f"Final room count: {room_count}")

            # Calculate price per sqm
            if property_details['price_numeric'] and property_details['area_sqm'] and property_details['area_sqm'] > 0:
                property_details['price_per_sqm'] = property_details['price_numeric'] / property_details['area_sqm']
                logger.info(
                    f"💰 Price calculation: {property_details['price_numeric']:,} ÷ {property_details['area_sqm']} = {property_details['price_per_sqm']:,.0f} ₮/m²")
            else:
                property_details['price_per_sqm'] = None
                logger.warning(
                    f"❌ Cannot calculate price per sqm: price={property_details['price_numeric']}, area={property_details['area_sqm']}")

            # Extract additional useful information
            # Publication date
            date_meta = soup.find("span", class_="date-meta")
            property_details['published_date'] = date_meta.text.strip() if date_meta else "N/A"

            # Ad number
            ad_number = soup.find("span", {"itemprop": "sku"})
            property_details['ad_number'] = ad_number.text.strip() if ad_number else "N/A"

            logger.info(f"✅ Successfully extracted detailed property data for: {property_details.get('title', 'N/A')}")

            # Format price per sqm for logging
            price_per_sqm_str = f"{property_details.get('price_per_sqm'):,.0f}" if property_details.get(
                'price_per_sqm') else "N/A"
            logger.info(
                f"📋 Key details: Price: {property_details.get('price_raw')}, Area: {property_details.get('area_sqm')}m², Rooms: {property_details.get('room_count')}, Price/m²: {price_per_sqm_str} ₮")

            return property_details

        except httpx.RequestError as e:
            logger.error(f"Network error fetching {url}: {e}")
            return {"url": url, "error": f"Failed to fetch page: {e}"}
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}", exc_info=True)
            return {"url": url, "error": f"Error parsing: {e}"}

    async def retrieve_vector_data(self) -> List[Document]:
        """
        Scrapes Unegui.mn listing pages to collect real-time data,
        aggregates average prices by district and room type,
        and returns Documents for the DistrictAnalyzer's vector store.
        """
        base_listing_url = "https://www.unegui.mn/l-hdlh/l-hdlh-zarna/"

        # Structure for aggregation: {district: {room_type: {'total_price_per_sqm': 0, 'count': 0}}}
        aggregated_data = defaultdict(lambda: defaultdict(lambda: {'total_price_per_sqm': 0.0, 'count': 0}))

        logger.info("Starting real-time data collection from Unegui.mn...")

        for district_name, path_segment in self.district_url_paths.items():
            logger.info(f"Collecting data for district: {district_name}")

            district_url = base_listing_url + path_segment
            max_pages_to_scrape = 3  # Limit to first 3 pages for each district

            for page_num in range(1, max_pages_to_scrape + 1):
                page_url = district_url
                if page_num > 1:
                    page_url += f"&page={page_num}"

                logger.info(f"  Scraping page {page_num} for {district_name}: {page_url}")

                try:
                    response = await self.async_client.get(page_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Find all listing elements
                    listings = soup.find_all("div", class_="advert js-item-listing")
                    logger.info(f"  Found {len(listings)} listings on page {page_num}")

                    for listing in listings:
                        try:
                            prop_data = self._extract_listing_data(listing)
                            prop_data['scraped_district'] = district_name  # Ensure district is set

                            logger.debug(f"  Raw extracted data: {json.dumps(prop_data, ensure_ascii=False, indent=2)}")

                            # Filter and categorize properties
                            if self._is_valid_residential_property(prop_data):
                                self._aggregate_property_data(prop_data, aggregated_data)
                                logger.info(f"  ✅ Added residential apartment: {prop_data.get('title', 'N/A')[:50]}...")
                            else:
                                # Log what type of property was excluded
                                property_type = self._classify_property_type(prop_data)
                                logger.info(f"  ❌ Excluded {property_type}: {prop_data.get('title', 'N/A')[:50]}...")

                        except Exception as e:
                            logger.error(f"  Error processing listing: {e}")
                            continue

                    # Add delay between requests to be respectful
                    await asyncio.sleep(1)

                except httpx.RequestError as e:
                    logger.error(f"  Network error fetching {page_url}: {e}")
                    break
                except Exception as e:
                    logger.error(f"  Error processing page {page_url}: {e}")
                    continue

            logger.info(f"Finished collecting data for {district_name}")

        # Generate Documents from aggregated data
        district_documents = self._generate_district_documents(aggregated_data)

        # Comprehensive logging of all collected data
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

        total_properties = 0
        for district, room_types in aggregated_data.items():
            overall_count = room_types.get('overall', {}).get('count', 0)
            total_properties += overall_count

        logger.info(f"✅ Successfully collected data from {len(district_documents)} districts")
        logger.info(f"📈 Total residential apartments analyzed: {total_properties}")

        # Detailed breakdown by district
        for district, room_types in aggregated_data.items():
            overall_info = room_types.get('overall', {'total_price_per_sqm': 0, 'count': 0})
            two_room_info = room_types.get('2_rooms', {'total_price_per_sqm': 0, 'count': 0})
            three_room_info = room_types.get('3_rooms', {'total_price_per_sqm': 0, 'count': 0})

            overall_avg = overall_info['total_price_per_sqm'] / overall_info['count'] if overall_info[
                                                                                             'count'] > 0 else 0

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

    def _is_valid_residential_property(self, prop_data: Dict[str, Any]) -> bool:
        """Check if property is a valid residential apartment listing for aggregation"""
        title = prop_data.get('title', '').lower()

        # Get the essential data
        price_per_sqm = prop_data.get('price_per_sqm')
        area_sqm = prop_data.get('area_sqm')
        room_count = prop_data.get('room_count')

        # Must have room count (indicates residential)
        if not isinstance(room_count, int) or room_count < 1 or room_count > 10:
            logger.debug(f"Invalid room count: {room_count}")
            return False

        # First check for definite exclusions (non-residential)
        definite_exclusions = [
            'зогсоол', 'газар', 'агуулах', 'үйлдвэр', 'гараж',
            'хүлэмж', 'зуслан', 'night club', 'автозасвар',
            'эмнэлэг', 'салон', 'тоот', 'амралт'
        ]

        for keyword in definite_exclusions:
            if keyword in title:
                logger.debug(f"Excluded by definite exclusion '{keyword}': {title}")
                return False

        # Check for apartment indicators (positive signals)
        apartment_indicators = [
            'өрөө байр',  # "room apartment"
            'орон сууц',  # "residential apartment"
            'апартмент',  # "apartment"
            'мкв',  # square meters (usually apartments)
            'м²',  # square meters
            'дуплекс',  # duplex apartment
            'студи',  # studio apartment
            'пентхаус'  # penthouse
        ]

        has_apartment_indicator = any(indicator in title for indicator in apartment_indicators)

        # If it has rooms but no clear apartment indicators, check more carefully
        if not has_apartment_indicator:
            # Check if it's likely a house/compound
            house_indicators = [
                'хашаа байшин',  # compound house
                'байшин',  # house (standalone)
                'аос',  # ger/traditional house
                'хаус'  # house
            ]

            # If it clearly mentions house but also has rooms, it might be a house with room count
            has_house_indicator = any(indicator in title for indicator in house_indicators)

            if has_house_indicator:
                logger.debug(f"Excluded house (not apartment): {title}")
                return False

            # If no clear indicators but has rooms, check for commercial use
            commercial_indicators = [
                'оффис', 'үйлчилгээ', 'барилга', 'дэлгүүр', 'объект'
            ]

            has_commercial_indicator = any(indicator in title for indicator in commercial_indicators)
            if has_commercial_indicator:
                logger.debug(f"Excluded commercial property: {title}")
                return False

        # Handle missing area data - try to validate other ways
        if area_sqm is None:
            # If no area but has room count and price, might still be valid
            # Check if we can extract area from detailed description or if it's clearly an apartment
            if has_apartment_indicator:
                logger.debug(f"Missing area data but has apartment indicators: {title}")
                # For properties with room count but no area, we'll skip price per sqm calculation
                # but might still want to include them if they're clearly apartments
                # However, for aggregation purposes, we need area to calculate price per sqm
                return False  # For now, require area for price analysis
            else:
                logger.debug(f"Missing area and no apartment indicators: {title}")
                return False
        else:
            # Has area - validate it's reasonable for apartments
            if not (15 <= area_sqm <= 500):  # Relaxed range for apartments
                logger.debug(f"Invalid area: {area_sqm} sqm")
                return False

        # Must have price per sqm for aggregation (calculated from price and area)
        if price_per_sqm is None or not isinstance(price_per_sqm, (int, float)) or price_per_sqm <= 0:
            logger.debug(f"Missing or invalid price per sqm: {price_per_sqm}")
            return False

        # Price per sqm sanity check (relaxed range)
        if not (500_000 <= price_per_sqm <= 20_000_000):  # Broader range
            logger.debug(f"Price per sqm out of range: {price_per_sqm:,.0f} ₮/m²")
            return False

        logger.debug(f"✅ Valid residential apartment: {title}")
        return True

    def _classify_property_type(self, prop_data: Dict[str, Any]) -> str:
        """Classify what type of property this is for logging purposes"""
        title = prop_data.get('title', '').lower()

        # Check for different property types
        if any(keyword in title for keyword in ['зогсоол', 'гараж']):
            return "parking/garage"
        elif any(keyword in title for keyword in ['газар', 'зуслан']):
            return "land"
        elif any(keyword in title for keyword in ['хашаа байшин', 'байшин', 'хаус']) and 'өрөө' not in title:
            return "house/compound"
        elif any(keyword in title for keyword in ['агуулах', 'үйлдвэр']):
            return "warehouse/factory"
        elif any(keyword in title for keyword in ['оффис', 'барилга']) and 'өрөө' not in title:
            return "office/commercial building"
        elif any(keyword in title for keyword in ['дэлгүүр', 'салон', 'эмнэлэг']):
            return "shop/service"
        elif any(keyword in title for keyword in ['night club', 'объект']) and 'өрөө' not in title:
            return "commercial property"
        elif prop_data.get('room_count') is None:
            return "no room count"
        elif prop_data.get('area_sqm') is None:
            return "no area data"
        elif prop_data.get('price_per_sqm') is None:
            return "no price per sqm"
        else:
            price_per_sqm = prop_data.get('price_per_sqm', 0)
            area_sqm = prop_data.get('area_sqm', 0)
            room_count = prop_data.get('room_count', 0)

            if price_per_sqm < 500_000:
                return f"price too low ({price_per_sqm:,.0f} ₮/m²)"
            elif price_per_sqm > 20_000_000:
                return f"price too high ({price_per_sqm:,.0f} ₮/m²)"
            elif area_sqm < 15:
                return f"area too small ({area_sqm} m²)"
            elif area_sqm > 500:
                return f"area too large ({area_sqm} m²)"
            elif room_count > 10:
                return f"too many rooms ({room_count})"
            elif 'дуплекс' in title:
                return "duplex apartment (should be included)"
            elif 'хотхон' in title and 'өрөө' in title:
                return "apartment in residential complex (should be included)"
            else:
                return "other validation criteria"

    def _aggregate_property_data(self, prop_data: Dict[str, Any], aggregated_data):
        """Add property data to aggregation structure"""
        district = prop_data.get('scraped_district') or prop_data.get('district', 'Unknown')
        room_count = prop_data.get('room_count')
        price_per_sqm = prop_data.get('price_per_sqm')

        if not all([district, room_count is not None, price_per_sqm is not None]):
            logger.debug(
                f"Skipping aggregation - missing data: district={district}, room_count={room_count}, price_per_sqm={price_per_sqm}")
            return

        # Aggregate overall average
        aggregated_data[district]['overall']['total_price_per_sqm'] += price_per_sqm
        aggregated_data[district]['overall']['count'] += 1

        # Aggregate by specific room counts (focusing on 2 and 3 room apartments)
        if room_count == 2:
            aggregated_data[district]['2_rooms']['total_price_per_sqm'] += price_per_sqm
            aggregated_data[district]['2_rooms']['count'] += 1
        elif room_count == 3:
            aggregated_data[district]['3_rooms']['total_price_per_sqm'] += price_per_sqm
            aggregated_data[district]['3_rooms']['count'] += 1

        # Also track other room counts for reference
        room_key = f"{room_count}_rooms"
        aggregated_data[district][room_key]['total_price_per_sqm'] += price_per_sqm
        aggregated_data[district][room_key]['count'] += 1

        logger.debug(f"✅ Aggregated: {district} - {room_count} rooms - {price_per_sqm:,.0f} ₮/m²")

    def _generate_district_documents(self, aggregated_data) -> List[Document]:
        """Generate Document objects from aggregated data"""
        district_documents = []

        if not aggregated_data:
            logger.warning("No data aggregated for any district")
            return []

        # District descriptions
        district_descriptions = {
            "Хан-Уул": "Хан-Уул дүүрэг нь Улаанбаатар хотын баруун урд байрладаг. Энэ дүүрэг нь орон сууцны үнэ харьцангуй өндөр байдаг.",
            "Баянгол": "Баянгол дүүрэг нь Улаанбаатар хотын төв хэсэгт ойр байрладаг. Энэ дүүрэг нь дундаж үнэтэй орон сууц элбэг.",
            "Сүхбаатар": "Сүхбаатар дүүрэг нь хотын хамгийн үнэтэй бүсүүдийн нэг бөгөөд төвдөө ойрхон.",
            "Чингэлтэй": "Чингэлтэй дүүрэг нь хотын төв хэсэгт оршдог.",
            "Баянзүрх": "Баянзүрх дүүрэг нь Улаанбаатар хотын хамгийн том дүүрэг бөгөөд олон янзын орон сууцтай.",
            "Сонгинохайрхан": "Сонгинохайрхан дүүрэг нь хотын баруун хэсэгт байрладаг том дүүрэг.",
            "Багануур": "Багануур дүүрэг нь хотын зүүн хэсэгт байрладаг.",
            "Налайх": "Налайх дүүрэг нь хотын зүүн урд хэсэгт байрладаг.",
            "Багахангай": "Багахангай дүүрэг нь хотын хойд хэсэгт байрладаг."
        }

        for district, room_types in aggregated_data.items():
            overall_info = room_types.get('overall', {'total_price_per_sqm': 0, 'count': 0})
            two_room_info = room_types.get('2_rooms', {'total_price_per_sqm': 0, 'count': 0})
            three_room_info = room_types.get('3_rooms', {'total_price_per_sqm': 0, 'count': 0})

            # Calculate averages
            overall_avg = overall_info['total_price_per_sqm'] / overall_info['count'] if overall_info[
                                                                                             'count'] > 0 else 0
            two_room_avg = two_room_info['total_price_per_sqm'] / two_room_info['count'] if two_room_info[
                                                                                                'count'] > 0 else 0
            three_room_avg = three_room_info['total_price_per_sqm'] / three_room_info['count'] if three_room_info[
                                                                                                      'count'] > 0 else 0

            # Format prices
            overall_avg_formatted = f"{int(overall_avg):,} төгрөг".replace(",",
                                                                           " ") if overall_avg > 0 else "мэдээлэл байхгүй"
            two_room_avg_formatted = f"{int(two_room_avg):,} төгрөг".replace(",",
                                                                             " ") if two_room_avg > 0 else "мэдээлэл байхгүй"
            three_room_avg_formatted = f"{int(three_room_avg):,} төгрөг".replace(",",
                                                                                 " ") if three_room_avg > 0 else "мэдээлэл байхгүй"

            # Get district description
            description = district_descriptions.get(district, f"{district} дүүргийн тухай нэмэлт мэдээлэл байхгүй.")

            # Create content with more detailed information
            content = f"""
Дүүрэг: {district}
Нийт байрны 1м2 дундаж үнэ: {overall_avg_formatted}
2 өрөө байрны 1м2 дундаж үнэ: {two_room_avg_formatted}
3 өрөө байрны 1м2 дундаж үнэ: {three_room_avg_formatted}
{description}
Цуглуулсан өгөгдөл: {overall_info['count']} орон сууц (2 өрөө: {two_room_info['count']}, 3 өрөө: {three_room_info['count']})
Дата цуглуулсан огноо: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
            """.strip()

            district_documents.append(Document(page_content=content))
            logger.debug(f"Generated document for {district} with {overall_info['count']} properties")

        return district_documents

    async def close(self):
        """Close the async client"""
        await self.async_client.aclose()