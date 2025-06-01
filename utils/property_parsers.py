# real_estate_assistant/utils/property_parsers.py
import re
import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

def find_feature_in_list(li_list: List[Any], header: str) -> str:
    """Finds a specific feature value within a list of Beautiful Soup li elements."""
    for li in li_list:
        key_chars_tag = li.find("span", class_="key-chars")
        value_chars_tag = li.find("span", class_="value-chars") or li.find("a", class_="value-chars")
        if key_chars_tag and value_chars_tag:
            key_text = key_chars_tag.text.strip()
            value_text = value_chars_tag.text.strip()
            if key_text == header:
                return value_text
    return 'N/A'

def parse_area_string(area_str: str) -> Optional[float]:
    """Parses an area string and returns a float representing square meters."""
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

def parse_room_string(room_str: str) -> Optional[int]:
    """Parses a room count string and returns an integer."""
    if not room_str or room_str == 'N/A':
        return None
    match = re.search(r'(\d+)', room_str)
    if match:
        try:
            return int(match.group(0))
        except ValueError:
            return None
    return None

def parse_price_from_text(price_text: str) -> Optional[float]:
    """
    Parses a price from text, handling different formats including 'сая' (million) and 'тэрбум' (billion).
    """
    if not price_text:
        return None

    price_cleaned = price_text.replace('₮', '').replace(',', '').replace(' ', '').strip()

    # Handle million format (сая)
    if 'сая' in price_cleaned.lower():
        match_million = re.search(r'(\d+\.?\d*)', price_cleaned)
        if match_million:
            try:
                return float(match_million.group(1)) * 1_000_000
            except ValueError:
                pass

    # Handle billion format (тэрбум)
    if 'тэрбум' in price_cleaned.lower():
        match_billion = re.search(r'(\d+\.?\d*)', price_cleaned)
        if match_billion:
            try:
                return float(match_billion.group(1)) * 1_000_000_000
            except ValueError:
                pass

    # Handle direct number format
    match_direct = re.search(r'(\d+)', price_cleaned)
    if match_direct:
        try:
            return float(match_direct.group(0))
        except ValueError:
            pass

    return None

def extract_area_from_title(title_lower: str) -> Optional[float]:
    """Extracts area from a title string using various patterns."""
    area_patterns = [
        r'(\d+\.?\d*)\s*мкв', r'(\d+\.?\d*)\s*м²', r'(\d+\.?\d*)\s*мк\b',
        r'(\d+\.?\d*)\s*квм', r'(\d+\.?\d*)\s*м2', r'(\d+\.?\d*)\s*mkv',
        r'(\d+\.?\d*)\s*m²', r'(\d+\.?\d*)\s*sqm',
        r'(\d+[,\.]\d+)\s*мкв', r'(\d+[,\.]\d+)\s*м²', r'(\d+[,\.]\d+)\s*мк\b',
    ]

    for pattern in area_patterns:
        area_match = re.search(pattern, title_lower)
        if area_match:
            try:
                area_str = area_match.group(1).replace(',', '.') # Convert comma to dot
                extracted_area = float(area_str)
                if 10 <= extracted_area <= 1000: # Broad range for apartments
                    return extracted_area
            except ValueError:
                continue
    return None

def extract_room_count_from_title(title_lower: str) -> Optional[int]:
    """Extracts room count from a title string using various patterns."""
    room_patterns = [
        r'(\d+)\s*өрөө', r'(\d+)\s*room', r'(\d+)\s*oroo',
    ]

    for pattern in room_patterns:
        room_match = re.search(pattern, title_lower)
        if room_match:
            try:
                extracted_rooms = int(room_match.group(1))
                if 1 <= extracted_rooms <= 10: # Reasonable room counts
                    return extracted_rooms
            except ValueError:
                continue
    return None