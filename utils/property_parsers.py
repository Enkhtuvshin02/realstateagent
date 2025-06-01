# real_estate_assistant/utils/property_parsers.py - Үл хөдлөх хөрөнгийн парсерүүд
import re
import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

def find_feature_in_list(li_list: List[Any], header: str) -> str:
    """Элементүүдийн жагсаалтаас тодорхой шинж чанарын утгыг олох."""
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
    """Талбайн текстийг задлаж метр квадратыг илэрхийлсэн float утга буцаана."""
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
    """Өрөөний тооны текстийг задлаж бүхэл тоо буцаана."""
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
    """Үнийн текстийг задлаж, 'сая' ба 'тэрбум' зэрэг янз бүрийн форматуудыг боловсруулах."""
    if not price_text:
        return None

    price_cleaned = price_text.replace('₮', '').replace(',', '').replace(' ', '').strip()

    # Саяар илэрхийлсэн форматыг боловсруулах
    if 'сая' in price_cleaned.lower():
        match_million = re.search(r'(\d+\.?\d*)', price_cleaned)
        if match_million:
            try:
                return float(match_million.group(1)) * 1_000_000
            except ValueError:
                pass

    # Тэрбумаар илэрхийлсэн форматыг боловсруулах
    if 'тэрбум' in price_cleaned.lower():
        match_billion = re.search(r'(\d+\.?\d*)', price_cleaned)
        if match_billion:
            try:
                return float(match_billion.group(1)) * 1_000_000_000
            except ValueError:
                pass

    # Шууд тоон форматыг боловсруулах
    match_direct = re.search(r'(\d+)', price_cleaned)
    if match_direct:
        try:
            return float(match_direct.group(0))
        except ValueError:
            pass

    return None

def extract_area_from_title(title_lower: str) -> Optional[float]:
    """Талбайг гарчгийн текстээс янз бүрийн хэв загваруудыг ашиглан авах."""
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
                area_str = area_match.group(1).replace(',', '.') # Таслалыг цэгээр хөрвүүлэх
                extracted_area = float(area_str)
                if 10 <= extracted_area <= 1000: # Орон сууцны өргөн хүрээ
                    return extracted_area
            except ValueError:
                continue
    return None

def extract_room_count_from_title(title_lower: str) -> Optional[int]:
    """Өрөөний тоог гарчгийн текстээс янз бүрийн хэв загваруудыг ашиглан авах."""
    room_patterns = [
        r'(\d+)\s*өрөө', r'(\d+)\s*room', r'(\d+)\s*oroo',
    ]

    for pattern in room_patterns:
        room_match = re.search(pattern, title_lower)
        if room_match:
            try:
                extracted_rooms = int(room_match.group(1))
                if 1 <= extracted_rooms <= 10: # Өрөөний бодитой тоо
                    return extracted_rooms
            except ValueError:
                continue
    return None