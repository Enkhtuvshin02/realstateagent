import logging
import re
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
import asyncio
import json

from utils.property_parsers import find_feature_in_list, parse_area_string, parse_room_string, parse_price_from_text, \
    extract_area_from_title, extract_room_count_from_title
from config.constants import FEATURE_TRANSLATIONS

logger = logging.getLogger(__name__)


class UneguiScraper:
    def __init__(self):
        self.async_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        self.feature_translations = FEATURE_TRANSLATIONS

    async def retrieve_property_details(self, url: str) -> Dict[str, Any]:
        if "unegui.mn" not in url:
            return {"url": url, "error": "Not a Unegui.mn URL"}
        try:
            response = await self.async_client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            property_details = {"url": url, "price_numeric": None, "price_raw": "N/A"}
            title_tag = soup.find("h1", {"class": "title-announcement"}) or soup.find("h1", {"id": "ad-title"})
            property_details['title'] = title_tag.text.strip() if title_tag else "N/A"
            location_tag = soup.find("span", {"itemprop": "address"})
            if location_tag:
                full_location_text = location_tag.text.strip()
                property_details['full_location'] = full_location_text
                district_name = "N/A"
                if "—" in full_location_text:
                    parts = full_location_text.split("—")
                    if len(parts) > 1:
                        district_part = parts[1].strip()
                        district_name = district_part.split(',')[0].strip()
                property_details['district'] = district_name
            else:
                property_details['full_location'] = "N/A"
                property_details['district'] = "N/A"
            price_text_found = "N/A"
            price_section = soup.find("section", {"data-price": True})
            if price_section:
                try:
                    property_details['price_numeric'] = float(price_section.get("data-price"))
                    price_text_found = f"{property_details['price_numeric']:,.0f} ₮"
                except (ValueError, TypeError):
                    pass
            if property_details['price_numeric'] is None:
                price_container = soup.find("div", class_="announcement-price__cost")
                if price_container:
                    price_text_found = price_container.get_text(strip=True)
                    property_details['price_numeric'] = parse_price_from_text(price_text_found)
            if property_details['price_numeric'] is None:
                price_meta = soup.find("meta", {"itemprop": "price"})
                if price_meta:
                    try:
                        property_details['price_numeric'] = float(price_meta.get("content"))
                        price_text_found = f"{property_details['price_numeric']:,.0f} ₮"
                    except (ValueError, TypeError):
                        pass
            if property_details['price_numeric'] is None:
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
                        if property_details['price_numeric']:
                            break
            property_details['price_raw'] = price_text_found
            characteristics_list = soup.find("ul", class_="chars-column")
            if characteristics_list:
                li_elements = characteristics_list.find_all("li")
                for mongolian_header, english_key in self.feature_translations.items():
                    value = find_feature_in_list(li_elements, mongolian_header + ":") 
                    if value == 'N/A': 
                        value = find_feature_in_list(li_elements, mongolian_header)
                    property_details[english_key.lower().replace(' ', '_')] = value
            else:
                for english_key in self.feature_translations.values():
                    property_details[english_key.lower().replace(' ', '_')] = "N/A"
            area_from_chars = property_details.get('area', 'N/A')
            area_sqm = parse_area_string(area_from_chars)
            if area_sqm is None: 
                area_sqm = extract_area_from_title(property_details['title'])
            property_details['area_sqm'] = area_sqm
            room_from_chars = property_details.get('rooms', 'N/A')
            room_count = parse_room_string(room_from_chars)
            if room_count is None: 
                room_count = extract_room_count_from_title(property_details['title'])
            property_details['room_count'] = room_count
            if property_details['price_numeric'] and property_details['area_sqm'] and property_details['area_sqm'] > 0:
                property_details['price_per_sqm'] = property_details['price_numeric'] / property_details['area_sqm']
            else:
                property_details['price_per_sqm'] = None
            date_meta = soup.find("span", class_="date-meta")
            property_details['published_date'] = date_meta.text.strip() if date_meta else "N/A"
            ad_number = soup.find("span", {"itemprop": "sku"})
            property_details['ad_number'] = ad_number.text.strip() if ad_number else "N/A"
            description_div = soup.find("div", class_="announcement-description")
            if description_div:
                desc_content = description_div.find("div", class_="js-description")
                if desc_content:
                    paragraphs = desc_content.find_all("p")
                    description_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                    property_details['description'] = description_text
                else:
                    property_details['description'] = description_div.get_text(strip=True)
            else:
                property_details['description'] = "N/A"
            view_counter = soup.find("span", class_="counter-views")
            if view_counter:
                view_text = view_counter.text.strip()
                view_match = re.search(r'(\d+)', view_text)
                property_details['view_count'] = int(view_match.group(1)) if view_match else 0
            else:
                property_details['view_count'] = 0
            logger.info("=" * 80)
            logger.info("EXTRACTED PROPERTY DATA")
            logger.info("=" * 80)
            logger.info(f"Title: {property_details.get('title', 'N/A')}")
            logger.info(f"Location: {property_details.get('full_location', 'N/A')}")
            logger.info(f"District: {property_details.get('district', 'N/A')}")
            logger.info(f"Price Raw: {property_details.get('price_raw', 'N/A')}")
            logger.info(f"Price Numeric: {property_details.get('price_numeric', 'N/A')}")
            logger.info(f"Area: {property_details.get('area_sqm', 'N/A')} m²")
            logger.info(f"Rooms: {property_details.get('room_count', 'N/A')}")
            if property_details.get('price_per_sqm'):
                logger.info(f"Price per m²: {property_details['price_per_sqm']:,.0f} ₮")
            else:
                logger.info(f"Price per m²: N/A")
            logger.info(f"Published: {property_details.get('published_date', 'N/A')}")
            logger.info(f"Ad Number: {property_details.get('ad_number', 'N/A')}")
            logger.info(f"Views: {property_details.get('view_count', 'N/A')}")
            logger.info("PROPERTY CHARACTERISTICS:")
            logger.info("-" * 40)
            for mongolian_header, english_key in self.feature_translations.items():
                value = property_details.get(english_key.lower().replace(' ', '_'), 'N/A')
            logger.info("=" * 80)
            return property_details
        except httpx.RequestError as e:
            return {"url": url, "error": f"Failed to fetch page: {e}"}
        except Exception as e:
            return {"url": url, "error": f"Error parsing: {e}"}

    def extract_listing_data(self, listing_soup: Any) -> Dict[str, Any]:
        prop_data = {}
        title_selectors = [
            "a.advert-grid__content-title",
            "a.advert__content-title",
            ".advert-grid__content-title",
            ".advert__content-title"
        ]
        title_tag = None
        for selector in title_selectors:
            title_tag = listing_soup.select_one(selector)
            if title_tag:
                break
        prop_data['title'] = title_tag.text.strip() if title_tag else "N/A"
        price_selectors = [
            "a.advert-grid__content-price._not-title span",
            "a.advert-grid__content-price span",
            ".advert-grid__content-price span",
            "span.advert__content-price",
            "a.advert__content-price"
        ]
        price_tag = None
        for selector in price_selectors:
            price_tag = listing_soup.select_one(selector)
            if price_tag:
                break
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            prop_data['price_numeric'] = parse_price_from_text(price_text)
            prop_data['price_raw'] = price_text
        else:
            prop_data['price_numeric'] = None
            prop_data['price_raw'] = "N/A"
        location_selectors = [
            ".advert-grid__content-hint .advert-grid__content-place",
            ".advert__content-place",
            "div.advert__content-place"
        ]
        location_tag = None
        for selector in location_selectors:
            location_tag = listing_soup.select_one(selector)
            if location_tag:
                break
        if location_tag:
            location_text = location_tag.text.strip()
            prop_data['full_location'] = location_text
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
        if prop_data['title'] != "N/A":
            title_lower = prop_data['title'].lower()
            prop_data['area_sqm'] = extract_area_from_title(title_lower)
            prop_data['room_count'] = extract_room_count_from_title(title_lower)
        if prop_data['price_numeric'] and prop_data['area_sqm'] and prop_data['area_sqm'] > 0:
            prop_data['price_per_sqm'] = prop_data['price_numeric'] / prop_data['area_sqm']
        else:
            prop_data['price_per_sqm'] = None
        return prop_data

    async def close(self):
        await self.async_client.aclose()