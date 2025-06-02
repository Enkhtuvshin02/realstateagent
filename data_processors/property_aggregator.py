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
        title = prop_data.get("title", "").lower()

        price_per_sqm = prop_data.get("price_per_sqm")
        area_sqm = prop_data.get("area_sqm")
        room_count = prop_data.get("room_count")

        if not isinstance(room_count,
                          int) or room_count < 0:
            logger.debug(f"Invalid room count: {room_count} rooms in {title}")
            return False

        definite_exclusions = [
            "зогсоол",
            "газар",
            "агуулах",
            "үйлдвэр",
            "гараж",
            "хүлэмж",
            "зуслан",
            "night club",
            "автозасвар",
            "эмнэлэг",
            "салон",
            "тоот",
            "амралт",
        ]
        if any(keyword in title for keyword in definite_exclusions):
            logger.debug(f"Excluded due to definite exclusion list: {title}")
            return False

        apartment_indicators = [
            "өрөө байр",
            "орон сууц",
            "апартмент",
            "мкв",
            "м²",
            "дуплекс",
            "студи",
            "пентхаус",
        ]
        has_apartment_indicator = any(
            indicator in title for indicator in apartment_indicators
        )

        if not has_apartment_indicator:
            house_indicators = ["хашаа байшин", "байшин", "аос", "хаус"]
            if any(indicator in title for indicator in house_indicators):
                logger.debug(f"Excluded: {title} is not an apartment")
                return False

            commercial_indicators = [
                "оффис",
                "үйлчилгээ",
                "барилга",
                "дэлгүүр",
                "объект",
            ]
            if any(keyword in title for keyword in commercial_indicators):
                logger.debug(f"Excluded: {title} is a commercial property")
                return False

        if area_sqm is None or not (15 <= area_sqm <= 500):
            logger.debug(f"Invalid area size: {area_sqm} m² in {title}")
            return False

        if (
                price_per_sqm is None
                or not isinstance(price_per_sqm, (int, float))
                or price_per_sqm <= 0
        ):
            logger.debug(f"Price per sqm invalid or missing: {price_per_sqm} in {title}")
            return False

        if not (500_000 <= price_per_sqm <= 20_000_000):
            logger.debug(f"Price per sqm too high or too low: {price_per_sqm:,.0f} ₮/m² in {title}")
            return False

        logger.debug(f" Valid residential property: {title}")
        return True

    def _classify_property_type(self, prop_data: Dict[str, Any]) -> str:
        title = prop_data.get("title", "").lower()

        if any(keyword in title for keyword in ["зогсоол", "гараж"]):
            return "зогсоол/гараж"
        elif any(keyword in title for keyword in ["газар", "зуслан"]):
            return "газар"
        elif (
                any(keyword in title for keyword in ["хашаа байшин", "байшин", "хаус"])
                and "өрөө" not in title
        ):
            return "байшин/хаус"
        elif any(keyword in title for keyword in ["агуулах", "үйлдвэр"]):
            return "агуулах/үйлдвэр"
        elif (
                any(keyword in title for keyword in ["оффис", "барилга"])
                and "өрөө" not in title
        ):
            return "оффис/барилга"
        elif any(keyword in title for keyword in ["дэлгүүр", "салон", "эмнэлэг"]):
            return "дэлгүүр/салон/эмнэлэг"
        elif (
                any(keyword in title for keyword in ["night club", "объект"])
                and "өрөө" not in title
        ):
            return "үйлчилгээний газар"
        elif prop_data.get("room_count") is None:
            return "өрөөний тоо алга"
        elif prop_data.get("area_sqm") is None:
            return "талбайн хэмжээ алга"
        elif prop_data.get("price_per_sqm") is None:
            return "ханш м²-д алга"
        else:
            price_per_sqm = prop_data.get("price_per_sqm", 0)
            area_sqm = prop_data.get("area_sqm", 0)
            room_count = prop_data.get("room_count", 0)

            if price_per_sqm < 500_000:
                return f"ханш м²-д хэтэрхий бага ({price_per_sqm:,.0f} ₮/м²)"
            elif price_per_sqm > 20_000_000:
                return f"ханш м²-д хэтэрхий өндөр ({price_per_sqm:,.0f} ₮/м²)"
            elif area_sqm < 15:
                return f"талбайн хэмжээ хэтэрхий бага ({area_sqm} м²)"
            elif area_sqm > 500:
                return f"талбайн хэмжээ хэтэрхий их ({area_sqm} м²)"
            elif room_count > 10:
                return f"өрөөний тоо хэтэрхий их ({room_count})"
            else:
                return "бусад шалгуурууд"

    def aggregate_property_data(
            self, prop_data: Dict[str, Any], aggregated_data: Dict
    ) -> None:
        district = prop_data.get("scraped_district") or prop_data.get(
            "district", "Unknown"
        )
        room_count = prop_data.get("room_count")
        price_per_sqm = prop_data.get("price_per_sqm")

        if not all([district, room_count is not None, price_per_sqm is not None]):
            logger.debug(
                f"Rejected addition: district={district}, room_count={room_count}, price_per_sqm={price_per_sqm} information missing")
            return

        aggregated_data[district]["overall"]["total_price_per_sqm"] += price_per_sqm
        aggregated_data[district]["overall"]["count"] += 1

        room_key = f"{room_count}_rooms"
        aggregated_data[district][room_key]["total_price_per_sqm"] += price_per_sqm
        aggregated_data[district][room_key]["count"] += 1

        logger.debug(f" Added: {district} - {room_count} rooms - {price_per_sqm:,.0f} ₮/m²")

    def generate_district_documents(self, aggregated_data: Dict) -> List[Document]:
        district_documents = []

        if not aggregated_data:
            logger.warning("No data collected for any district")
            return []

        for district, room_types_data in aggregated_data.items():
            overall_info = room_types_data.get(
                "overall", {"total_price_per_sqm": 0, "count": 0}
            )

            overall_avg = (
                overall_info["total_price_per_sqm"] / overall_info["count"]
                if overall_info["count"] > 0
                else 0
            )

            overall_avg_formatted = (
                f"{int(overall_avg):,} төгрөг".replace(",", " ")
                if overall_avg > 0
                else "no data"
            )

            room_type_summaries = []
            room_counts_info = defaultdict(int)

            for key, value in room_types_data.items():
                if key != "overall" and key.endswith("_rooms"):
                    room_count_str = key.split("_")[0]
                    try:
                        room_count_num = int(room_count_str)
                        room_avg = (
                            value["total_price_per_sqm"] / value["count"]
                            if value["count"] > 0
                            else 0
                        )
                        room_avg_formatted = (
                            f"{int(room_avg):,} төгрөг".replace(",", " ")
                            if room_avg > 0
                            else "no data"
                        )
                        room_type_summaries.append(f"{room_count_num} өрөө байрны 1м2 дундаж үнэ: {room_avg_formatted}")
                        room_counts_info[room_count_num] = value['count']
                    except ValueError:
                        logger.warning(f"Could not parse room count from key: {key}")
                        continue

            room_type_summaries.sort(key=lambda x: int(x.split(' ')[0]))
            room_type_summaries_str = "\n".join(room_type_summaries)

            room_counts_display = ", ".join(
                [f"{count} өрөө: {num_properties}" for count, num_properties in sorted(room_counts_info.items())])
            if not room_counts_display:
                room_counts_display = "No specific room type data collected"

            description = DISTRICT_DESCRIPTIONS.get(
                district, f"{district} district has no additional information."
            )

            content = f"""
Дүүрэг: {district}
Нийт байрны 1м2 дундаж үнэ: {overall_avg_formatted}
{room_type_summaries_str}
{description}
Цуглуулсан өгөгдөл: {overall_info['count']} орон сууц ({room_counts_display})
Дата цуглуулсан огноо: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
            """.strip()

            district_documents.append(Document(page_content=content))
            logger.debug(f"Generated document for {district} with {overall_info['count']} properties")

        return district_documents