# real_estate_assistant/scrapers/unegui_scraper.py
import logging
import re
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
import asyncio

from utils.property_parsers import find_feature_in_list, parse_area_string, parse_room_string, parse_price_from_text, extract_area_from_title, extract_room_count_from_title
from config.constants import FEATURE_TRANSLATIONS

logger = logging.getLogger(__name__)

class UneguiScraper:
    def __init__(self):
        self.async_client = httpx.AsyncClient(timeout=30.0)
        self.feature_translations = FEATURE_TRANSLATIONS

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
            property_details = {"url": url, "price_numeric": None, "price_raw": "N/A"}

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
            price_text_found = "N/A"

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
                        property_details['price_numeric'] = parse_price_from_text(price_text_found)
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
                        property_details['price_numeric'] = parse_price_from_text(price_text_found)
                        logger.debug(f"Found price in page text: {price_text_found} -> {property_details['price_numeric']}")
                        if property_details['price_numeric']:
                            break
            property_details['price_raw'] = price_text_found
            logger.debug(f"Extracted price: {property_details['price_raw']} -> {property_details['price_numeric']}")

            # Extract all characteristics from chars-column
            characteristics_list = soup.find("ul", class_="chars-column")
            if characteristics_list:
                li_elements = characteristics_list.find_all("li")

                # Extract each characteristic
                for mongolian_header, english_key in self.feature_translations.items():
                    value = find_feature_in_list(li_elements, mongolian_header)
                    property_details[english_key.lower().replace(' ', '_')] = value
                    logger.debug(f"Extracted {mongolian_header}: {value}")
            else:
                logger.warning(f"Could not find 'chars-column' on {url}")
                for english_key in self.feature_translations.values():
                    property_details[english_key.lower().replace(' ', '_')] = "N/A"

            # Extract area from characteristics or title
            area_from_chars = property_details.get('area', 'N/A')
            area_sqm = parse_area_string(area_from_chars)

            if area_sqm is None: # If no area in characteristics, try title
                area_sqm = extract_area_from_title(property_details['title'].lower())

            property_details['area_sqm'] = area_sqm
            logger.debug(f"Final area: {area_sqm}")

            # Extract room count from characteristics or title
            room_from_chars = property_details.get('rooms', 'N/A')
            room_count = parse_room_string(room_from_chars)

            if room_count is None: # If no room count in characteristics, extract from title
                room_count = extract_room_count_from_title(property_details['title'].lower())

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
            date_meta = soup.find("span", class_="date-meta")
            property_details['published_date'] = date_meta.text.strip() if date_meta else "N/A"

            ad_number = soup.find("span", {"itemprop": "sku"})
            property_details['ad_number'] = ad_number.text.strip() if ad_number else "N/A"

            logger.info(f"✅ Successfully extracted detailed property data for: {property_details.get('title', 'N/A')}")
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

    def extract_listing_data(self, listing_soup: Any) -> Dict[str, Any]:
        """Extract data from a single listing element (from a search results page)"""
        prop_data = {}

        # Extract title
        title_tag = listing_soup.find("a", class_="advert__content-title")
        prop_data['title'] = title_tag.text.strip() if title_tag else "N/A"

        # Extract price
        price_tag = listing_soup.find("span", class_="advert__content-price") or \
                    listing_soup.find("a", class_="advert__content-price")
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            prop_data['price_numeric'] = parse_price_from_text(price_text)
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

        # Extract area and room count from title using helper functions
        title_lower = prop_data['title'].lower()
        prop_data['area_sqm'] = extract_area_from_title(title_lower)
        prop_data['room_count'] = extract_room_count_from_title(title_lower)

        # Calculate price per sqm
        if prop_data['price_numeric'] and prop_data['area_sqm'] and prop_data['area_sqm'] > 0:
            prop_data['price_per_sqm'] = prop_data['price_numeric'] / prop_data['area_sqm']
        else:
            prop_data['price_per_sqm'] = None

        return prop_data

    async def close(self):
        """Close the async client"""
        await self.async_client.aclose()