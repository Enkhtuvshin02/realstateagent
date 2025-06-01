
import logging
import json
import re
from datetime import datetime
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, llm, district_analyzer, pdf_generator, search_tool=None):
        self.llm = llm
        self.district_analyzer = district_analyzer
        self.pdf_generator = pdf_generator
        self.search_tool = search_tool

    async def generate_property_report(self, analysis_data: dict) -> str:
        """Generate property analysis PDF report with search integration"""
        logger.info("📄 Generating property report with search integration")

        try:
            # Check if analysis is recent (within last 10 minutes)
            analysis_time = datetime.fromisoformat(analysis_data["timestamp"])
            time_diff = datetime.now() - analysis_time

            if time_diff.total_seconds() > 600:  # 10 minutes
                return {
                    "message": "Орон сууцны шинжилгээ хуучирсан байна. Эхлээд орон сууцны холбоосыг илгээгээд дараа нь тайлан хүсэх боломжтой.",
                    "success": False
                }

            # Perform internet search for market research
            search_results = ""
            if self.search_tool:
                try:
                    district_name = analysis_data["property_details"].get("district", "")
                    search_query = f"Улаанбаатар {district_name} дүүрэг орон сууцны зах зээл үнэ 2024 2025"
                    logger.info(f"🔍 Searching for: {search_query}")

                    search_response = self.search_tool.invoke({"query": search_query})
                    if search_response:
                        search_results = await self._process_search_results(search_response, "property")
                        logger.info("✅ Search results processed for property report")
                except Exception as e:
                    logger.error(f"❌ Search failed: {e}")
                    search_results = "Интернэт хайлт хийхэд алдаа гарлаа."

            # Generate detailed analysis for PDF in Mongolian
            detailed_analysis = await self._generate_detailed_property_analysis_mn(
                analysis_data["property_details"],
                analysis_data["district_analysis"]
            )

            # Generate PDF with search results
            pdf_path = self.pdf_generator.generate_property_analysis_report(
                property_data=analysis_data["property_details"],
                district_analysis=analysis_data["district_analysis"],
                comparison_result=detailed_analysis,
                search_results=search_results
            )

            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"

            return {
                "message": f"✅ Орон сууцны дэлгэрэнгүй PDF тайлан амжилттай үүсгэгдлээ!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"❌ Error generating property report: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}. Дахин оролдоно уу.",
                "success": False
            }

    async def generate_district_report(self) -> str:
        """Generate district comparison PDF report with search integration"""
        logger.info("📊 Generating district report with search integration")

        try:
            # Ensure fresh data
            await self.district_analyzer.ensure_fresh_data()

            # Extract district data
            districts_data = self._extract_districts_data()

            if not districts_data:
                return "Дүүргийн мэдээлэл олдсонгүй. Дахин оролдоно уу."

            # Perform internet search for market trends
            search_results = ""
            if self.search_tool:
                try:
                    search_query = "Улаанбаатар орон сууцны зах зээл үнэ чиглэл 2024 2025 дүүрэг харьцуулалт"
                    logger.info(f"🔍 Searching for market trends: {search_query}")

                    search_response = self.search_tool.invoke({"query": search_query})
                    if search_response:
                        search_results = await self._process_search_results(search_response, "market")
                        logger.info("✅ Search results processed for district report")
                except Exception as e:
                    logger.error(f"❌ Search failed: {e}")
                    search_results = "Интернэт хайлт хийхэд алдаа гарлаа."

            # Generate market trends analysis in Mongolian
            market_trends = await self._generate_market_trends_analysis_mn(districts_data)

            # Generate PDF with search results
            pdf_path = self.pdf_generator.generate_district_summary_report(
                districts_data=districts_data,
                market_trends=market_trends,
                search_results=search_results
            )

            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"

            return {
                "message": f"✅ Улаанбаатар хотын дүүргийн харьцуулалтын PDF тайлан амжилттай үүсгэгдлээ!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"❌ Error generating district report: {e}")
            return {
                "message": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}. Дахин оролдоно уу.",
                "success": False
            }

    async def _process_search_results(self, search_response, report_type: str) -> str:
        """Process search results and generate relevant summary in Mongolian"""
        try:
            # Extract useful information from search results
            search_text = ""
            if isinstance(search_response, list):
                for result in search_response:
                    if isinstance(result, dict):
                        content = result.get('content', '') or result.get('snippet', '')
                        title = result.get('title', '')
                        if content:
                            search_text += f"{title}: {content}\n"
                    else:
                        search_text += str(result) + "\n"
            else:
                search_text = str(search_response)

            if not search_text.strip():
                return "Интернэт хайлтаас мэдээлэл олдсонгүй."

            # Generate summary based on report type
            if report_type == "property":
                prompt = ChatPromptTemplate.from_messages([
                    ("system",
                     "Та бол үл хөдлөх хөрөнгийн шинжээч. Интернэт хайлтын үр дүнгээс орон сууцны зах зээлийн чухал мэдээллийг Монгол хэлээр нэгтгэн харуулна уу. Зөвхөн хамгийн чухал мэдээллийг товч тодорхой байдлаар бичнэ үү."),
                    ("human",
                     "Интернэт хайлтын үр дүн: {search_results}\n\nОрон сууцны зах зээлийн талаарх чухал мэдээллийг Монгол хэлээр нэгтгэн харуулна уу.")
                ])
            else:  # market trends
                prompt = ChatPromptTemplate.from_messages([
                    ("system",
                     "Та бол үл хөдлөх хөрөнгийн зах зээлийн шинжээч. Интернэт хайлтын үр дүнгээс Улаанбаатар хотын орон сууцны зах зээлийн ерөнхий чиг хандлагыг Монгол хэлээр нэгтгэн харуулна уу."),
                    ("human",
                     "Интернэт хайлтын үр дүн: {search_results}\n\nУлаанбаатар хотын орон сууцны зах зээлийн чиг хандлагын талаарх мэдээллийг Монгол хэлээр нэгтгэн харуулна уу.")
                ])

            chain = prompt | self.llm | StrOutputParser()
            summary = await chain.ainvoke({"search_results": search_text[:3000]})  # Limit text length

            return summary if summary else "Хайлтын үр дүнгээс мэдээлэл боловсруулж чадсангүй."

        except Exception as e:
            logger.error(f"❌ Error processing search results: {e}")
            return "Хайлтын үр дүнг боловсруулахад алдаа гарлаа."

    async def _generate_detailed_property_analysis_mn(self, property_details: dict, district_analysis: str) -> str:
        """Generate detailed property analysis in Mongolian"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн мэргэжилтэн. Орон сууцны дэлгэрэнгүй шинжилгээг Монгол хэлээр хийнэ үү. 

Дараах зүйлсийг агуулна уу:
1. Зах зээл дэх байр суурь
2. Хөрөнгө оруулалтын боломж
3. Дүүргийн дундажтай харьцуулалт  
4. Эрсдлийн үнэлгээ
5. Зөвлөмжүүд

Зөвхөн Монгол хэлээр, тодорхой, практик зөвлөмж өгнө үү."""),
            ("human", """Орон сууц: {property_details}
Дүүргийн шинжилгээ: {district_analysis}

Энэ орон сууцны дэлгэрэнгүй зах зээлийн шинжилгээг Монгол хэлээр хийнэ үү.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "property_details": json.dumps(property_details, ensure_ascii=False, indent=2),
            "district_analysis": district_analysis
        })

        return analysis

    async def _generate_market_trends_analysis_mn(self, districts_data: list) -> str:
        """Generate market trends analysis in Mongolian"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн зах зээлийн шинжээч. Улаанбаатар хотын дүүргүүдийн орон сууцны зах зээлийн шинжилгээг Монгол хэлээр хийнэ үү.

Дараах зүйлсийг агуулна уу:
1. Ерөнхий зах зээлийн нөхцөл байдал
2. Дүүрэг хоорондын үнийн ялгаа
3. Хөрөнгө оруулалтын боломжууд
4. Зах зээлийн өсөлтийн чиглэл
5. Өөр өөр худалдан авагчдад зориулсан зөвлөмж

Зөвхөн Монгол хэлээр, мэргэжлийн шинжилгээ хийнэ үү."""),
            ("human", """Дүүргүүдийн мэдээлэл: {districts_data}

Улаанбаатар хотын орон сууцны зах зээлийн чиг хандлагыг энэ мэдээлэлд үндэслэн Монгол хэлээр шинжилнэ үү.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "districts_data": json.dumps(districts_data, ensure_ascii=False, indent=2)
        })

        return analysis

    def _extract_districts_data(self) -> list:
        """Extract district data from vectorstore with improved parsing"""
        if not self.district_analyzer.vectorstore:
            logger.warning("No vectorstore available")
            return []

        available_docs = list(self.district_analyzer.vectorstore.docstore._dict.values())
        districts_data = []

        logger.info(f"Extracting data from {len(available_docs)} documents...")

        for doc in available_docs:
            lines = doc.page_content.strip().split('\n')
            district_info = {}

            logger.debug(f"Processing document with content: {doc.page_content[:100]}...")

            for line in lines:
                line = line.strip()

                # Extract district name
                if 'Дүүрэг:' in line:
                    district_info['name'] = line.replace('Дүүрэг:', '').strip()
                    logger.debug(f"Found district: {district_info['name']}")

                # Extract overall average price
                elif 'Нийт байрны 1м2 дундаж үнэ:' in line:
                    price_match = re.search(r'(\d[\d\s,]*)', line)
                    if price_match:
                        price_str = price_match.group(1).replace(' ', '').replace(',', '')
                        try:
                            district_info['overall_avg'] = float(price_str)
                            logger.debug(f"Extracted overall avg: {district_info['overall_avg']}")
                        except ValueError as e:
                            logger.warning(f"Could not parse overall price '{price_str}': {e}")
                            district_info['overall_avg'] = 0

                # Extract 2-room price
                elif '2 өрөө байрны 1м2 дундаж үнэ:' in line:
                    price_match = re.search(r'(\d[\d\s,]*)', line)
                    if price_match:
                        price_str = price_match.group(1).replace(' ', '').replace(',', '')
                        try:
                            district_info['two_room_avg'] = float(price_str)
                            logger.debug(f"Extracted 2-room avg: {district_info['two_room_avg']}")
                        except ValueError as e:
                            logger.warning(f"Could not parse 2-room price '{price_str}': {e}")
                            district_info['two_room_avg'] = 0

                # Extract 3-room price
                elif '3 өрөө байрны 1м2 дундаж үнэ:' in line:
                    price_match = re.search(r'(\d[\d\s,]*)', line)
                    if price_match:
                        price_str = price_match.group(1).replace(' ', '').replace(',', '')
                        try:
                            district_info['three_room_avg'] = float(price_str)
                            logger.debug(f"Extracted 3-room avg: {district_info['three_room_avg']}")
                        except ValueError as e:
                            logger.warning(f"Could not parse 3-room price '{price_str}': {e}")
                            district_info['three_room_avg'] = 0

            # Only add district if we have a name and at least one price
            if district_info.get('name') and district_info.get('overall_avg', 0) > 0:
                districts_data.append(district_info)
                logger.info(f"Added district: {district_info['name']} with price {district_info['overall_avg']:,.0f}")
            else:
                logger.warning(f"Skipping incomplete district data: {district_info}")

        logger.info(f"Successfully extracted {len(districts_data)} districts with valid data")

        # If no valid data extracted, return fallback data
        if not districts_data:
            logger.warning("No valid district data found, using fallback data")
            districts_data = [
                {
                    'name': 'Сүхбаатар',
                    'overall_avg': 4500000,
                    'two_room_avg': 4600000,
                    'three_room_avg': 4400000
                },
                {
                    'name': 'Хан-Уул',
                    'overall_avg': 4000323,
                    'two_room_avg': 4100323,
                    'three_room_avg': 3900323
                },
                {
                    'name': 'Чингэлтэй',
                    'overall_avg': 3800000,
                    'two_room_avg': 3900000,
                    'three_room_avg': 3700000
                },
                {
                    'name': 'Баянгол',
                    'overall_avg': 3510645,
                    'two_room_avg': 3610645,
                    'three_room_avg': 3410645
                },
                {
                    'name': 'Баянзүрх',
                    'overall_avg': 3200000,
                    'two_room_avg': 3300000,
                    'three_room_avg': 3100000
                },
                {
                    'name': 'Сонгинохайрхан',
                    'overall_avg': 2800000,
                    'two_room_avg': 2900000,
                    'three_room_avg': 2700000
                },
                {
                    'name': 'Багануур',
                    'overall_avg': 2200000,
                    'two_room_avg': 2300000,
                    'three_room_avg': 2100000
                },
                {
                    'name': 'Налайх',
                    'overall_avg': 2000000,
                    'two_room_avg': 2100000,
                    'three_room_avg': 1900000
                }
            ]

        return districts_data
    async def generate_comprehensive_market_report(self) -> str:
        """Generate a comprehensive market analysis report"""
        logger.info("📈 Generating comprehensive market report")

        try:
            # Ensure fresh data
            await self.district_analyzer.ensure_fresh_data()

            # Extract district data
            districts_data = self._extract_districts_data()

            if not districts_data:
                return "Дүүргийн мэдээлэл олдсонгүй. Дахин оролдоно уу."

            # Perform multiple searches for comprehensive analysis
            search_results = ""
            if self.search_tool:
                try:
                    search_queries = [
                        "Улаанбаатар орон сууцны зах зээл 2024 2025 статистик",
                        "Монгол орон сууцны үнэ өсөлт чиглэл",
                        "Улаанбаатар шинэ хорооллын орон сууц",
                        "Монгол үл хөдлөх хөрөнгийн зээл ипотек"
                    ]

                    combined_results = []
                    for query in search_queries:
                        logger.info(f"🔍 Searching: {query}")
                        try:
                            result = self.search_tool.invoke({"query": query})
                            if result:
                                combined_results.append(result)
                        except Exception as e:
                            logger.error(f"Search failed for '{query}': {e}")
                            continue

                    if combined_results:
                        search_results = await self._process_comprehensive_search_results(combined_results)
                        logger.info("✅ Comprehensive search results processed")
                except Exception as e:
                    logger.error(f"❌ Comprehensive search failed: {e}")
                    search_results = "Интернэт хайлт хийхэд алдаа гарлаа."

            # Generate comprehensive market analysis
            market_analysis = await self._generate_comprehensive_market_analysis(districts_data, search_results)

            # Generate enhanced PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_market_report_{timestamp}.pdf"

            # Use existing district report generator but with enhanced data
            pdf_path = self.pdf_generator.generate_district_summary_report(
                districts_data=districts_data,
                market_trends=market_analysis,
                search_results=search_results
            )

            filename = Path(pdf_path).name
            download_url = f"/download-report/{filename}"

            return {
                "message": f"✅ Улаанбаатар хотын дэлгэрэнгүй зах зээлийн тайлан амжилттай үүсгэгдлээ!",
                "filename": filename,
                "download_url": download_url,
                "success": True
            }

        except Exception as e:
            logger.error(f"❌ Error generating comprehensive market report: {e}")
            return {
                "message": f"Дэлгэрэнгүй тайлан үүсгэхэд алдаа гарлаа: {str(e)}. Дахин оролдоно уу.",
                "success": False
            }

    async def _process_comprehensive_search_results(self, search_results_list) -> str:
        """Process multiple search results for comprehensive analysis"""
        try:
            all_content = ""
            for results in search_results_list:
                if isinstance(results, list):
                    for result in results:
                        if isinstance(result, dict):
                            content = result.get('content', '') or result.get('snippet', '')
                            title = result.get('title', '')
                            if content:
                                all_content += f"{title}: {content}\n"

            if not all_content.strip():
                return "Интернэт хайлтаас мэдээлэл олдсонгүй."

            prompt = ChatPromptTemplate.from_messages([
                ("system", """Та бол үл хөдлөх хөрөнгийн зах зээлийн мэргэжилтэн. Олон хайлтын үр дүнгээс Улаанбаатар хотын орон сууцны зах зээлийн дэлгэрэнгүй шинжилгээг Монгол хэлээр хийнэ үү.

Дараах зүйлсийг тусгана уу:
- Одоогийн зах зээлийн нөхцөл байдал
- Үнийн динамик ба чиглэл  
- Шинэ хөгжлийн төслүүд
- Санхүүжилтийн нөхцөл
- Ирээдүйн таамаглал

Зөвхөн Монгол хэлээр, мэргэжлийн дүн шинжилгээ хийнэ үү."""),
                ("human",
                 "Интернэт хайлтын үр дүнгүүд: {search_content}\n\nЭдгээр мэдээллээс Улаанбаатар хотын орон сууцны зах зээлийн дэлгэрэнгүй шинжилгээг Монгол хэлээр хийнэ үү.")
            ])

            chain = prompt | self.llm | StrOutputParser()
            summary = await chain.ainvoke({"search_content": all_content[:4000]})  # Limit length

            return summary if summary else "Хайлтын үр дүнгээс мэдээлэл боловсруулж чадсангүй."

        except Exception as e:
            logger.error(f"❌ Error processing comprehensive search results: {e}")
            return "Хайлтын үр дүнг боловсруулахад алдаа гарлаа."

    async def _generate_comprehensive_market_analysis(self, districts_data: list, search_results: str) -> str:
        """Generate comprehensive market analysis combining district data and search results"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн зах зээлийн тэргүүний шинжээч. Дүүргүүдийн мэдээлэл болон интернэт судалгааны үр дүнг хослуулан Улаанбаатар хотын орон сууцны зах зээлийн иж бүрэн шинжилгээг Монгол хэлээр хийнэ үү.

Дараах бүлгүүдийг тусгана уу:
1. Зах зээлийн ерөнхий үнэлгээ
2. Дүүрэг хоорондын харьцуулалт  
3. Үнийн чиглэл ба шалтгаан
4. Хөрөнгө оруулалтын боломжууд
5. Эрсдэл ба сорилт
6. Ирээдүйн төлөв

Мэргэжлийн, дэлгэрэнгүй шинжилгээ хийнэ үү."""),
            ("human", """Дүүргүүдийн мэдээлэл: {districts_data}

Интернэт судалгааны үр дүн: {search_results}

Эдгээр мэдээллийг нэгтгэн Улаанбаатар хотын орон сууцны зах зээлийн иж бүрэн шинжилгээг Монгол хэлээр хийнэ үү.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        analysis = await chain.ainvoke({
            "districts_data": json.dumps(districts_data, ensure_ascii=False, indent=2),
            "search_results": search_results
        })

        return analysis


def _parse_price_from_text(self, text: str) -> float:
    """Parse price from Mongolian text with various formats"""
    if not text:
        return 0

    # Remove common Mongolian price indicators
    text = text.replace('төгрөг', '').replace('₮', '').strip()

    # Handle million format
    if 'сая' in text.lower():
        match = re.search(r'(\d+(?:[,.]\d+)?)', text)
        if match:
            try:
                number = float(match.group(1).replace(',', '.'))
                return number * 1_000_000
            except ValueError:
                pass

    # Handle billion format
    if 'тэрбум' in text.lower():
        match = re.search(r'(\d+(?:[,.]\d+)?)', text)
        if match:
            try:
                number = float(match.group(1).replace(',', '.'))
                return number * 1_000_000_000
            except ValueError:
                pass

    # Handle direct number format (with spaces as thousands separators)
    text = text.replace(' ', '').replace(',', '')
    match = re.search(r'(\d+)', text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    return 0