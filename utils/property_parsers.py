import re
from typing import Any, List, Optional

def find_feature_in_list(li_elements: List[Any], feature_name: str) -> str:
    for li in li_elements:
        text = li.get_text(strip=True)
        if feature_name in text:
            value = text.replace(feature_name, "").strip()
            return value if value else "N/A"
    return "N/A"

def parse_area_string(area_str: str) -> Optional[float]:
    if not area_str or area_str == "N/A":
        return None
    match = re.search(r"(\d+[\.,]?\d*)\s*м²", area_str)
    if match:
        return float(match.group(1).replace(",", "."))
    match = re.search(r"(\d+[\.,]?\d*)", area_str)
    if match:
        return float(match.group(1).replace(",", "."))
    return None

def parse_room_string(room_str: str) -> Optional[int]:
    if not room_str or room_str == "N/A":
        return None
    match = re.search(r"(\d+)", room_str)
    if match:
        return int(match.group(1))
    return None

def parse_price_from_text(price_text: str) -> Optional[float]:
    if not price_text or price_text == "N/A":
        return None
    price_text = price_text.replace(",", "").replace(" ", "")
    match = re.search(r"(\d+\.?\d*)", price_text)
    if match:
        return float(match.group(1))
    return None

def extract_area_from_title(title: str) -> Optional[float]:
    if not title:
        return None
    match = re.search(r"(\d{2,3})\s*м²", title)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d{2,3})\s*sqm", title, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None

def extract_room_count_from_title(title: str) -> Optional[int]:
    if not title:
        return None
    match = re.search(r"(\d+)\s*өрөө", title)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*-?room", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None