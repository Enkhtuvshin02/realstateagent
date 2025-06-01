# real_estate_assistant/data_processors/property_aggregator.py - Үл хөдлөх хөрөнгийн өгөгдлийн нэгтгэгч
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
        """Үл хөдлөх хөрөнгө нь нэгтгэхэд хүчинтэй орон сууцны жагсаалт мөн эсэхийг шалгах"""
        title = prop_data.get("title", "").lower()

        price_per_sqm = prop_data.get("price_per_sqm")
        area_sqm = prop_data.get("area_sqm")
        room_count = prop_data.get("room_count")

        if not isinstance(room_count, int) or room_count < 1 or room_count > 10:
            logger.debug(f"Буутай тоо биш эсвэл 1-10 тооны хооронд биш: {room_count} өрөөний тоо {title}-д")
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
            logger.debug(f"Тодорхой хасах жагсаалтад орсон учир хасав: {title}")
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
                logger.debug(f"Хасав: {title}-д өрөө байр биш")
                return False

            commercial_indicators = [
                "оффис",
                "үйлчилгээ",
                "барилга",
                "дэлгүүр",
                "объект",
            ]
            if any(indicator in title for indicator in commercial_indicators):
                logger.debug(f"Хасав: {title}-д үйлчилгээний газар байна")
                return False

        if area_sqm is None or not (15 <= area_sqm <= 500):
            logger.debug(f"Талбайн хэмжээ буруу: {area_sqm} м² {title}-д")
            return False

        if (
            price_per_sqm is None
            or not isinstance(price_per_sqm, (int, float))
            or price_per_sqm <= 0
        ):
            logger.debug(
                f"Ханш м²-д буруу эсвэл алга: {price_per_sqm} {title}-д"
            )
            return False

        if not (500_000 <= price_per_sqm <= 20_000_000):
            logger.debug(
                f"Ханш м²-д хэтэрхий өндөр эсвэл бага: {price_per_sqm:,.0f} ₮/м² {title}-д"
            )
            return False

        logger.debug(f"✅ Хүчинтэй орон сууц: {title}")
        return True

    def _classify_property_type(self, prop_data: Dict[str, Any]) -> str:
        """Логгингийн зорилгоор үл хөдлөх хөрөнгийн төрлийг ангилах"""
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
        """Үл хөдлөх хөрөнгийн өгөгдлийг нэгтгэх бүтэцд нэмэх."""
        district = prop_data.get("scraped_district") or prop_data.get(
            "district", "Unknown"
        )
        room_count = prop_data.get("room_count")
        price_per_sqm = prop_data.get("price_per_sqm")

        if not all([district, room_count is not None, price_per_sqm is not None]):
            logger.debug(
                f"Нэмэхээс татгалзав: дүүрэг={district}, өрөөний тоо={room_count}, ханш м²-д={price_per_sqm} мэдээлэл алга"
            )
            return

        aggregated_data[district]["overall"]["total_price_per_sqm"] += price_per_sqm
        aggregated_data[district]["overall"]["count"] += 1

        room_key = f"{room_count}_rooms"
        aggregated_data[district][room_key]["total_price_per_sqm"] += price_per_sqm
        aggregated_data[district][room_key]["count"] += 1

        logger.debug(
            f"✅ Нэмэв: {district} - {room_count} өрөө - {price_per_sqm:,.0f} ₮/м²"
        )

    def generate_district_documents(self, aggregated_data: Dict) -> List[Document]:
        """Вектор хадгалагчид зориулж нэгтгэсэн өгөгдлөөс Document объектуудыг үүсгэх."""
        district_documents = []

        if not aggregated_data:
            logger.warning("Аль ч дүүрэгт мэдээлэл цуглуулаагүй байна")
            return []

        for district, room_types in aggregated_data.items():
            overall_info = room_types.get(
                "overall", {"total_price_per_sqm": 0, "count": 0}
            )
            two_room_info = room_types.get(
                "2_rooms", {"total_price_per_sqm": 0, "count": 0}
            )
            three_room_info = room_types.get(
                "3_rooms", {"total_price_per_sqm": 0, "count": 0}
            )

            overall_avg = (
                overall_info["total_price_per_sqm"] / overall_info["count"]
                if overall_info["count"] > 0
                else 0
            )
            two_room_avg = (
                two_room_info["total_price_per_sqm"] / two_room_info["count"]
                if two_room_info["count"] > 0
                else 0
            )
            three_room_avg = (
                three_room_info["total_price_per_sqm"] / three_room_info["count"]
                if three_room_info["count"] > 0
                else 0
            )

            overall_avg_formatted = (
                f"{int(overall_avg):,} төгрөг".replace(",", " ")
                if overall_avg > 0
                else "мэдээлэл байхгүй"
            )
            two_room_avg_formatted = (
                f"{int(two_room_avg):,} төгрөг".replace(",", " ")
                if two_room_avg > 0
                else "мэдээлэл байхгүй"
            )
            three_room_avg_formatted = (
                f"{int(three_room_avg):,} төгрөг".replace(",", " ")
                if three_room_avg > 0
                else "мэдээлэл байхгүй"
            )

            description = DISTRICT_DESCRIPTIONS.get(
                district, f"{district} дүүргийн тухай нэмэлт мэдээлэл байхгүй."
            )

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
            logger.debug(
                f"Generated document for {district} with {overall_info['count']} properties"
            )

        return district_documents
