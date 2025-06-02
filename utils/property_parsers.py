
import re
import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)


def find_feature_in_list(li_list: List[Any], header: str) -> str:
    for li in li_list:
        key_chars_tag = li.find("span", class_="key-chars")
        value_chars_tag = li.find("span", class_="value-chars") or li.find("a", class_="value-chars")

        if key_chars_tag and value_chars_tag:
            key_text = key_chars_tag.text.strip()
            value_text = value_chars_tag.text.strip()


            if key_text == header:
                logger.debug(f"Found exact match for '{header}': {value_text}")
                return value_text


            if key_text.rstrip(':') == header.rstrip(':'):
                logger.debug(f"Found match without colon for '{header}': {value_text}")
                return value_text


            if key_text == header + ':' or key_text + ':' == header:
                logger.debug(f"Found match with colon for '{header}': {value_text}")
                return value_text

    logger.debug(f"No match found for '{header}'")
    return 'N/A'


def parse_area_string(area_str: str) -> Optional[float]:
    if not area_str or area_str == 'N/A':
        return None


    area_cleaned = area_str.lower().replace('м²', '').replace('мк', '').replace('мкв', '').replace('мк2', '').replace(
        'm²', '').replace('sqm', '').strip()


    match = re.search(r'(\d+[,.]?\d*)', area_cleaned)
    if match:
        try:
            area_str_clean = match.group(1).replace(',', '.')
            area_value = float(area_str_clean)

            if 10 <= area_value <= 1000:
                logger.debug(f"Parsed area: '{area_str}' -> {area_value}")
                return area_value
            else:
                logger.debug(f"Area value {area_value} outside reasonable range (10-1000)")
        except ValueError:
            logger.debug(f"Could not convert area to float: {area_str}")

    logger.debug(f"Could not parse area from: '{area_str}'")
    return None


def parse_room_string(room_str: str) -> Optional[int]:
    if not room_str or room_str == 'N/A':
        return None


    match = re.search(r'(\d+)', room_str)
    if match:
        try:
            room_count = int(match.group(1))

            if 1 <= room_count <= 10:
                logger.debug(f"Parsed room count: '{room_str}' -> {room_count}")
                return room_count
            else:
                logger.debug(f"Room count {room_count} outside reasonable range (1-10)")
        except ValueError:
            logger.debug(f"Could not convert room count to int: {room_str}")

    logger.debug(f"Could not parse room count from: '{room_str}'")
    return None


def parse_price_from_text(price_text: str) -> Optional[float]:
    if not price_text:
        return None

    price_cleaned = price_text.replace('₮', '').replace(',', '').replace(' ', '').strip().lower()
    logger.debug(f"Parsing price: '{price_text}' -> cleaned: '{price_cleaned}'")


    if 'сая' in price_cleaned:
        match_million = re.search(r'(\d+\.?\d*)', price_cleaned)
        if match_million:
            try:
                result = float(match_million.group(1)) * 1_000_000
                logger.debug(f"Parsed million format: {result}")
                return result
            except ValueError:
                pass


    if 'тэрбум' in price_cleaned:
        match_billion = re.search(r'(\d+\.?\d*)', price_cleaned)
        if match_billion:
            try:
                result = float(match_billion.group(1)) * 1_000_000_000
                logger.debug(f"Parsed billion format: {result}")
                return result
            except ValueError:
                pass


    match_direct = re.search(r'(\d+)', price_cleaned)
    if match_direct:
        try:
            result = float(match_direct.group(0))
            logger.debug(f"Parsed direct format: {result}")
            return result
        except ValueError:
            pass

    logger.debug(f"Could not parse price from: '{price_text}'")
    return None


def extract_area_from_title(title_lower: str) -> Optional[float]:
    if not title_lower:
        return None


    area_patterns = [
        r'(\d+[,.]?\d*)\s*мкв\b',
        r'(\d+[,.]?\d*)\s*м²\b',
        r'(\d+[,.]?\d*)\s*мк\b',
        r'(\d+[,.]?\d*)\s*квм\b',
        r'(\d+[,.]?\d*)\s*м2\b',
        r'(\d+[,.]?\d*)\s*mkv\b',
        r'(\d+[,.]?\d*)\s*m²\b',
        r'(\d+[,.]?\d*)\s*sqm\b',
        r'(\d+[,.]?\d*)\s*м\.кв\b',
        r'(\d+[,.]?\d*)\s*кв\.?м\b',

        r'(\d+[,.]?\d*)\s*м\d?\b',
    ]

    for pattern in area_patterns:
        area_match = re.search(pattern, title_lower)
        if area_match:
            try:
                area_str = area_match.group(1).replace(',', '.')  # Convert comma to dot
                extracted_area = float(area_str)

                if 10 <= extracted_area <= 1000:
                    logger.debug(f"Extracted area from title: '{title_lower}' -> {extracted_area}")
                    return extracted_area
                else:
                    logger.debug(f"Area {extracted_area} outside reasonable range")
            except ValueError:
                continue

    logger.debug(f"Could not extract area from title: '{title_lower}'")
    return None


def extract_room_count_from_title(title_lower: str) -> Optional[int]:
    if not title_lower:
        return None


    room_patterns = [
        r'(\d+)\s*өрөө\b',
        r'(\d+)\s*room\b',
        r'(\d+)\s*oroo\b',
        r'(\d+)\s*р\b',
        r'(\d+)\+?\s*өрөө',
    ]

    for pattern in room_patterns:
        room_match = re.search(pattern, title_lower)
        if room_match:
            try:
                extracted_rooms = int(room_match.group(1))

                if 1 <= extracted_rooms <= 10:
                    logger.debug(f"Extracted room count from title: '{title_lower}' -> {extracted_rooms}")
                    return extracted_rooms
                else:
                    logger.debug(f"Room count {extracted_rooms} outside reasonable range")
            except ValueError:
                continue

    logger.debug(f"Could not extract room count from title: '{title_lower}'")
    return None