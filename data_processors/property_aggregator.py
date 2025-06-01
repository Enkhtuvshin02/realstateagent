# real_estate_assistant/data_processors/property_aggregator.py
import logging
import datetime
from collections import defaultdict
from typing import Dict, Any, List
from langchain_core.documents import Document

from config.constants import DISTRICT_DESCRIPTIONS

logger = logging.getLogger(__name__)

class PropertyAggregator:
    def __init__(self):
        pass

    def _is_valid_residential_property(self, prop_data: Dict[str, Any]) -> bool:
        """Check if property is a valid residential apartment listing for aggregation"""
        title = prop_data.get('title', '').lower()

        price_per_sqm = prop_data.get('price_per_sqm')
        area_sqm = prop_data.get('area_sqm')
        room_count = prop_data.get('room_count')

        if not isinstance(room_count, int) or room_count < 1 or room_count > 10:
            logger.debug(f"Invalid room count: {room_count} for {title}")
            return False

        definite_exclusions = [
            'зогсоол', 'газар', 'агуулах', 'үйлдвэр', 'гараж',
            'хүлэмж', 'зуслан', 'night club', 'автозасвар',
            'эмнэлэг', 'салон', 'тоот', 'амралт'
        ]
        if any(keyword in title for keyword in definite_exclusions):
            logger.debug(f"Excluded by definite exclusion '{title}': {title}")
            return False

        apartment_indicators = [
            'өрөө байр', 'орон сууц', 'апартмент', 'мкв', 'м²',
            'дуплекс', 'студи', 'пентхаус'
        ]
        has_apartment_indicator = any(indicator in title for indicator in apartment_indicators)

        if not has_apartment_indicator:
            house_indicators = ['хашаа байшин', 'байшин', 'аос', 'хаус']
            if any(indicator in title for indicator in house_indicators):
                logger.debug(f"Excluded house (not apartment): {title}")
                return False

            commercial_indicators = ['оффис', 'үйлчилгээ', 'барилга', 'дэлгүүр', 'объект']
            if any(indicator in title for indicator in commercial_indicators):
                logger.debug(f"Excluded commercial property: {title}")
                return False

        if area_sqm is None or not (15 <= area_sqm <= 500):
            logger.debug(f"Invalid area: {area_sqm} sqm for {title}")
            return False

        if price_per_sqm is None or not isinstance(price_per_sqm, (int, float)) or price_per_sqm <= 0:
            logger.debug(f"Missing or invalid price per sqm: {price_per_sqm} for {title}")
            return False

        if not (500_000 <= price_per_sqm <= 20_000_000):
            logger.debug(f"Price per sqm out of range: {price_per_sqm:,.0f} ₮/m² for {title}")
            return False

        logger.debug(f"✅ Valid residential apartment: {title}")
        return True

    def _classify_property_type(self, prop_data: Dict[str, Any]) -> str:
        """Classify what type of property this is for logging purposes"""
        title = prop_data.get('title', '').lower()

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
            else:
                return "other validation criteria"


    def aggregate_property_data(self, prop_data: Dict[str, Any], aggregated_data: Dict) -> None:
        """Adds property data to the aggregation structure."""
        district = prop_data.get('scraped_district') or prop_data.get('district', 'Unknown')
        room_count = prop_data.get('room_count')
        price_per_sqm = prop_data.get('price_per_sqm')

        if not all([district, room_count is not None, price_per_sqm is not None]):
            logger.debug(
                f"Skipping aggregation - missing data: district={district}, room_count={room_count}, price_per_sqm={price_per_sqm}")
            return

        aggregated_data[district]['overall']['total_price_per_sqm'] += price_per_sqm
        aggregated_data[district]['overall']['count'] += 1

        room_key = f"{room_count}_rooms"
        aggregated_data[district][room_key]['total_price_per_sqm'] += price_per_sqm
        aggregated_data[district][room_key]['count'] += 1

        logger.debug(f"✅ Aggregated: {district} - {room_count} rooms - {price_per_sqm:,.0f} ₮/m²")

    def generate_district_documents(self, aggregated_data: Dict) -> List[Document]:
        """Generates Document objects from aggregated data for the vector store."""
        district_documents = []

        if not aggregated_data:
            logger.warning("No data aggregated for any district")
            return []

        for district, room_types in aggregated_data.items():
            overall_info = room_types.get('overall', {'total_price_per_sqm': 0, 'count': 0})
            two_room_info = room_types.get('2_rooms', {'total_price_per_sqm': 0, 'count': 0})
            three_room_info = room_types.get('3_rooms', {'total_price_per_sqm': 0, 'count': 0})

            overall_avg = overall_info['total_price_per_sqm'] / overall_info['count'] if overall_info['count'] > 0 else 0
            two_room_avg = two_room_info['total_price_per_sqm'] / two_room_info['count'] if two_room_info['count'] > 0 else 0
            three_room_avg = three_room_info['total_price_per_sqm'] / three_room_info['count'] if three_room_info['count'] > 0 else 0

            overall_avg_formatted = f"{int(overall_avg):,} төгрөг".replace(",", " ") if overall_avg > 0 else "мэдээлэл байхгүй"
            two_room_avg_formatted = f"{int(two_room_avg):,} төгрөг".replace(",", " ") if two_room_avg > 0 else "мэдээлэл байхгүй"
            three_room_avg_formatted = f"{int(three_room_avg):,} төгрөг".replace(",", " ") if three_room_avg > 0 else "мэдээлэл байхгүй"

            description = DISTRICT_DESCRIPTIONS.get(district, f"{district} дүүргийн тухай нэмэлт мэдээлэл байхгүй.")

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