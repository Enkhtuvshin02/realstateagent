# html_builders.py

import logging
import re
from datetime import datetime
from typing import Dict, List, Any
from config.pdf_config import (
    REPORT_TEMPLATES, DATE_FORMATS, TABLE_CONFIG, INVESTMENT_THRESHOLDS, #
    FONTS_DIR, CYRILLIC_FONTS, PDF_PAGE_CONFIG, FONT_SIZES, COLORS, SPACING #
)
from utils.html_formatter import HTMLFormatter

logger = logging.getLogger(__name__)


class PropertyHTMLBuilder:
    """Builds HTML content for property reports with 7 sections"""

    def __init__(self, formatter: HTMLFormatter): #
        self.formatter = formatter #

    def build_html(self, title: str, location: str, district: str, area: float,
                   rooms: int, price: str, price_per_sqm: str, district_analysis: str,
                   comparison_result: str, search_results: str, price_per_sqm_numeric: float) -> str: #
        """Build HTML content for property report with 7 sections"""
        now = datetime.now() #

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self.formatter.get_base_css()}</style>
            <title>{REPORT_TEMPLATES['property']['title']}</title> 
        </head>
        <body>
            <h1>{REPORT_TEMPLATES['property']['title']}</h1>
            <p class="report-date">Тайлангийн огноо: {now.strftime(DATE_FORMATS['mongolian'])}</p>

            <div class="section property-details">
                <h2>{REPORT_TEMPLATES['property']['sections'][0]}</h2>
                {self._build_basic_info_section(title, location, district, area, rooms)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][1]}</h2>
                {self._build_price_analysis_section(price, price_per_sqm, price_per_sqm_numeric, area)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][2]}</h2>
                {self._build_district_analysis_section(district_analysis, district)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][3]}</h2>
                {self._build_valuation_comparison_section(comparison_result, price_per_sqm_numeric)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][4]}</h2>
                {self._build_investment_analysis_section(price_per_sqm_numeric, district, area)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][5]}</h2>
                {self._build_recommendations_section(price_per_sqm_numeric, district, rooms)}
            </div>
        """ #

        # Note: The logic for should_include_search_results in HTMLFormatter always returns False,
        # so this section might not be added based on current HTMLFormatter.
        # If it should be included, HTMLFormatter.should_include_search_results needs to be updated.
        if self.formatter.should_include_search_results(search_results): #
            html += f"""
            <div class="section">
                <h2>{REPORT_TEMPLATES['property']['sections'][6]}</h2> 
                {self._build_additional_market_info_section(search_results)}
            </div>
            """ #

        html += f"""
            <div id="footer_content" class="footer-text">
                Улаанбаатар хотын үл хөдлөх хөрөнгийн туслах систем © {now.year}
            </div>
        </body>
        </html>
        """ #

        return html

    def _build_basic_info_section(self, title: str, location: str, district: str, area: float, rooms: int) -> str: #
        """Section 1: Basic Information & Technical Specifications"""
        # Ensure rooms is not zero to prevent DivisionByZeroError
        avg_area_per_room_text = f"{area/rooms:.1f} м² (дундажаар)" if rooms > 0 else "Тодорхойгүй (өрөөний тоо 0)"
        return f"""
            <h3>Үндсэн мэдээлэл:</h3>
            <div><strong>Гарчиг:</strong> {self.formatter.clean_text_for_html(title)}</div>
            <div><strong>Байршил:</strong> {self.formatter.clean_text_for_html(location)}</div>
            <div><strong>Дүүрэг:</strong> {self.formatter.clean_text_for_html(district)}</div>
            
            <h3>Техникийн үзүүлэлт:</h3>
            <div><strong>Талбай:</strong> {area:.2f} м²</div>
            <div><strong>Өрөөний тоо:</strong> {rooms} өрөө</div>
            <div><strong>1 өрөөнд ногдох талбай:</strong> {avg_area_per_room_text}</div>
        """ #

    def _build_price_analysis_section(self, price: str, price_per_sqm: str, price_per_sqm_numeric: float, area: float) -> str: #
        """Section 2: Price Analysis & Market Position"""
        # Ensure price_per_sqm_numeric is a float for comparison
        price_per_sqm_numeric = float(price_per_sqm_numeric) if price_per_sqm_numeric is not None else 0.0
        area = float(area) if area is not None else 0.0

        price_category = "дундаж"
        if price_per_sqm_numeric > 0: # Add check to avoid issues if price_per_sqm_numeric is 0 or None
            if 3000000 <= price_per_sqm_numeric <= 4000000: #
                price_category = "дундаж" #
            elif price_per_sqm_numeric > 4000000: #
                price_category = "өндөр" #
            else: # price_per_sqm_numeric < 3000000
                price_category = "доогуур" #
        else:
            price_category = "тодорхойгүй"


        price_class = "Тодорхойгүй"
        if price_per_sqm_numeric > 0:
            if price_per_sqm_numeric > 4000000: price_class = "Үнэтэй" #
            elif price_per_sqm_numeric > 3000000: price_class = "Дундаж" #
            else: price_class = "Хямд" #
        
        calculated_total_price = "Тодорхойгүй"
        if price_per_sqm_numeric > 0 and area > 0:
            calculated_total_price = f"{int(price_per_sqm_numeric * area):,}₮".replace(',', ' ')


        return f"""
            <div class="price-highlight">
                <div class="price-main">Нийт үнэ: {price}</div>
                <div class="price-main">м² үнэ: {price_per_sqm}</div>
            </div>
            
            <h3>Үнийн шинжилгээ:</h3>
            <div><strong>Зах зээлийн байршил:</strong> {price_category} үнийн түвшин</div>
            <div><strong>Нийт дүн (тооцоолсон):</strong> {calculated_total_price}</div>
            <div><strong>Үнийн ангилал:</strong> {price_class}</div>
        """ #

    def _build_district_analysis_section(self, district_analysis: str, district: str) -> str: #
        """Section 3: District Market Analysis"""
        return f"""
            <h3>{self.formatter.clean_text_for_html(district)} дүүргийн зах зээлийн үнэлгээ:</h3>
            <p>{self.formatter.clean_text_for_html(district_analysis)}</p>
            
            <h3>Дүүргийн онцлог:</h3>
            <p>Энэ дүүрэг нь Улаанбаатар хотын нэгэн чухал хэсэг бөгөөд өөрийн гэсэн онцлог, давуу талтай. Дэлгэрэнгүй мэдээллийг дээрх үнэлгээнээс харна уу.</p>
        """ #

    def _build_valuation_comparison_section(self, comparison_result: str, price_per_sqm_numeric: float) -> str: #
        """Section 4: Property Valuation & Comparison"""
        price_per_sqm_numeric = float(price_per_sqm_numeric) if price_per_sqm_numeric is not None else 0.0
        market_comparison_text = "Тодорхойгүй"
        if price_per_sqm_numeric > 0:
            if price_per_sqm_numeric > 3500000: market_comparison_text = "Дээгүүр" #
            elif price_per_sqm_numeric < 3000000: market_comparison_text = "Доогуур" #
            else: market_comparison_text = "Ойролцоо" #

        return f"""
            <h3>Хөрөнгийн үнэлгээ (LLM шинжилгээ):</h3>
            <p>{self.formatter.clean_text_for_html(comparison_result)}</p>
            
            <h3>Зах зээлийн харьцуулалт (м.кв үнээр):</h3>
            <div><strong>Дундаж зах зээлийн үнэтэй харьцуулбал:</strong> {market_comparison_text}</div>
        """ #

    def _build_investment_analysis_section(self, price_per_sqm_numeric: float, district: str, area: float) -> str: #
        """Section 5: Investment Opportunities & Risks"""
        price_per_sqm_numeric = float(price_per_sqm_numeric) if price_per_sqm_numeric is not None else 0.0
        area = float(area) if area is not None else 0.0

        investment_potential = "Тодорхойгүй"
        if price_per_sqm_numeric > 0:
            if price_per_sqm_numeric < 3500000: investment_potential = "Өндөр" #
            elif price_per_sqm_numeric < 4500000: investment_potential = "Дундаж" #
            else: investment_potential = "Бага" #
        
        rental_income_probability = "Тодорхойгүй"
        if area > 0:
            if area > 50: rental_income_probability = "Сайн" #
            else: rental_income_probability = "Дундаж" #

        price_risk = "Тодорхойгүй"
        if price_per_sqm_numeric > 0:
            if price_per_sqm_numeric > 5000000: price_risk = "Өндөр" #
            elif price_per_sqm_numeric > 0: price_risk = "Дундаж" #


        return f"""
            <h3>Хөрөнгө оруулалтын боломж:</h3>
            <div><strong>Хөрөнгө оруулалтын потенциал:</strong> {investment_potential}</div>
            <div><strong>Түрээсийн орлогын магадлал:</strong> {rental_income_probability} (талбайн хэмжээнээс хамаарч)</div>
            
            <h3>Эрсдэлийн үнэлгээ:</h3>
            <div><strong>Үнийн эрсдэл (өндөр үнэтэй бол):</strong> {price_risk}</div>
            <div><strong>Зах зээлийн тогтвортой байдал:</strong> {self.formatter.clean_text_for_html(district)} дүүрэг харьцангуй тогтвортой (ерөнхий төлөв).</div>
        """ #

    def _build_recommendations_section(self, price_per_sqm_numeric: float, district: str, rooms: int) -> str: #
        """Section 6: Recommendations & Conclusions"""
        price_per_sqm_numeric = float(price_per_sqm_numeric) if price_per_sqm_numeric is not None else 0.0
        investment_advice = self._generate_investment_recommendation(price_per_sqm_numeric) #
        
        room_advice = "Хувь хүний амьдралд болон жижиг гэр бүлд тохиромжтой хэмжээтэй."
        if rooms >= 3: room_advice = "Гэр бүлийн хэрэгцээнд нийцэхүйц, олон өрөөтэй." #
        elif rooms == 0: room_advice = "Өрөөний тоо тодорхойгүй."


        return f"""
            <h3>Хөрөнгө оруулалтын ерөнхий зөвлөмж (м.кв үнээр):</h3>
            <p>{self.formatter.clean_text_for_html(investment_advice)}</p>
            
            <h3>Худалдан авахын өмнөх анхаарах зүйлс:</h3>
            <ul>
                <li>Орон сууцыг биечлэн үзэж, техникийн байдал, засварын түвшинг шалгана уу.</li>
                <li>{self.formatter.clean_text_for_html(district)} дүүргийн бусад ижил төстэй байрнуудын үнэтэй харьцуулж судлаарай.</li>
                <li>Худалдан авах гэрээ, бичиг баримтын бүрдэл, хууль зүйн асуудлыг сайтар нягтална уу.</li>
                <li>{room_advice}</li>
            </ul>
        """ #

    def _build_additional_market_info_section(self, search_results: str) -> str: #
        """Section 7: Additional Market Information (from search)"""
        return f"""
            <h3>Нэмэлт судалгааны үр дүн (интернет хайлтаас):</h3>
            <p>{self.formatter.clean_text_for_html(search_results) if search_results else "Нэмэлт онлайн судалгааны мэдээлэл олдсонгүй."}</p>
            
            <h3>Зах зээлийн нэмэлт мэдээлэл:</h3>
            <p>Энэхүү мэдээлэл нь автоматжуулсан интернет хайлтаас цуглуулсан бөгөөд зах зээлийн одоогийн байдлыг тодорхой хэмжээнд тусгасан болно. Нарийвчилсан шийдвэр гаргахын өмнө мэргэжлийн байгууллагуудаас зөвлөгөө авна уу.</p>
        """ #

    def _generate_investment_recommendation(self, price_per_sqm: float) -> str: #
        """Generate investment recommendation based on price per square meter"""
        price_per_sqm = float(price_per_sqm) if price_per_sqm is not None else 0.0
        if price_per_sqm <= 0:
            return "Үнийн мэдээлэл байхгүй тул хөрөнгө оруулалтын зөвлөмж өгөх боломжгүй."

        if price_per_sqm > INVESTMENT_THRESHOLDS["expensive"]: #
            return INVESTMENT_THRESHOLDS["messages"]["expensive"] #
        elif price_per_sqm < INVESTMENT_THRESHOLDS["affordable"]: #
            return INVESTMENT_THRESHOLDS["messages"]["affordable"] #
        else:
            return INVESTMENT_THRESHOLDS["messages"]["moderate"] #


class DistrictHTMLBuilder:
    """Builds HTML content for district reports with 7 sections"""

    def __init__(self, formatter: HTMLFormatter): #
        self.formatter = formatter #

    # MODIFIED: Added future_development_content parameter
    def build_html(self, districts_data: List[Dict], market_trends: str,
                   search_results: str, future_development_content: str) -> str: #
        """Build HTML content for district report with 7 sections"""
        now = datetime.now() #

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self.formatter.get_base_css()}</style>
            <title>{REPORT_TEMPLATES['district']['title']}</title>
        </head>
        <body>
            <h1>{REPORT_TEMPLATES['district']['title']}</h1>
            <p class="report-date">Тайлангийн огноо: {now.strftime(DATE_FORMATS['mongolian'])}</p>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][0]}</h2>
                {self._build_price_comparison_section(districts_data)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][1]}</h2>
                {self._build_market_trends_section(market_trends, districts_data)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][2]}</h2>
                {self._build_investment_zones_section(districts_data)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][3]}</h2>
                {self._build_district_advantages_section(districts_data)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][4]}</h2>
                {self._build_buyer_strategies_section(districts_data)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][5]}</h2>
                {self._build_future_development_section(future_development_content)} 
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['district']['sections'][6]}</h2>
                {self._build_additional_research_section(search_results)}
            </div>

            <div id="footer_content" class="footer-text">
                Улаанбаатар хотын үл хөдлөх хөрөнгийн туслах систем © {now.year}
            </div>
        </body>
        </html>
        """ #

        return html

    def _build_price_comparison_section(self, districts_data: List[Dict]) -> str: #
        """Section 1: Price Comparison & Rankings"""
        if not districts_data: #
            return "<p>Дүүргийн үнийн харьцуулалт хийх мэдээлэл байхгүй.</p>" #

        # Sort districts by price for ranking, ensuring 'overall_avg' exists and is numeric
        valid_districts_for_ranking = [d for d in districts_data if isinstance(d.get('overall_avg'), (int, float)) and d['overall_avg'] > 0]
        if not valid_districts_for_ranking:
            return "<p>Дүүргүүдийн үнийн зэрэглэл гаргахад хангалттай мэдээлэл алга.</p>" + self._build_districts_table(districts_data)


        sorted_districts = sorted(valid_districts_for_ranking, key=lambda x: x.get('overall_avg', 0), reverse=True) #

        html = "<h3>Үнийн зэрэглэл (өндрөөс доошоо, м.кв дундаж үнээр):</h3><ol>" #
        for district in sorted_districts:
            name = self.formatter.clean_text_for_html(district.get('name', 'Тодорхойгүй')) #
            price = self.formatter.format_price_html(district.get('overall_avg', 0)) #
            html += f"<li><strong>{name}</strong>: {price}</li>" #
        html += "</ol>" #

        html += self._build_districts_table(districts_data) #
        return html

    def _build_market_trends_section(self, market_trends: str, districts_data: List[Dict]) -> str: #
        """Section 2: Market Trends & Statistics (LLM Generated for trends, basic stats from data)"""
        stats_html = "<p>Зах зээлийн статистик тооцоолох дүүргийн дэлгэрэнгүй мэдээлэл байхгүй.</p>" #
        
        valid_districts_for_stats = [d for d in districts_data if isinstance(d.get('overall_avg'), (int, float)) and d['overall_avg'] > 0]

        if valid_districts_for_stats:
            try:
                avg_price = sum(d.get('overall_avg', 0) for d in valid_districts_for_stats) / len(valid_districts_for_stats) #
                max_price = max(d.get('overall_avg', 0) for d in valid_districts_for_stats) #
                min_price = min(d.get('overall_avg', 0) for d in valid_districts_for_stats) #

                stats_html = f"""
                <h3>Зах зээлийн статистик (өгөгдсөн дүүргүүдэд тулгуурлав):</h3>
                <ul>
                    <li><strong>Дундаж үнэ (м.кв):</strong> {self.formatter.format_price_html(avg_price)}</li>
                    <li><strong>Хамгийн өндөр дундаж үнэ (м.кв):</strong> {self.formatter.format_price_html(max_price)}</li>
                    <li><strong>Хамгийн доод дундаж үнэ (м.кв):</strong> {self.formatter.format_price_html(min_price)}</li>
                    <li><strong>Үнийн зөрүү (дээд ба доод):</strong> {self.formatter.format_price_html(max_price - min_price)}</li>
                </ul>
                """ #
            except Exception as e:
                logger.error(f"Error calculating district stats: {e}")
                stats_html = "<p>Зах зээлийн статистик тооцоолоход алдаа гарлаа.</p>"


        # market_trends is now expected to be LLM generated summary
        return f"""
            {stats_html}
            <h3>Зах зээлийн чиг хандлага (LLM шинжилгээ):</h3>
            <p>{self.formatter.clean_text_for_html(market_trends) if market_trends else "Зах зээлийн ерөнхий чиг хандлагын талаарх мэдээлэл боловсруулагдаагүй."}</p>
        """ #

    def _build_investment_zones_section(self, districts_data: List[Dict]) -> str: #
        """Section 3: Investment Opportunity Zones (Logic based on data)"""
        if not districts_data: #
            return "<p>Хөрөнгө оруулалтын бүсийн мэдээлэл тодорхойлох өгөгдөл байхгүй.</p>" #

        expensive_districts = [d for d in districts_data if isinstance(d.get('overall_avg'), (int,float)) and d.get('overall_avg', 0) > 4000000] #
        moderate_districts = [d for d in districts_data if isinstance(d.get('overall_avg'), (int,float)) and 3000000 <= d.get('overall_avg', 0) <= 4000000] #
        affordable_districts = [d for d in districts_data if isinstance(d.get('overall_avg'), (int,float)) and d.get('overall_avg', 0) > 0 and d.get('overall_avg', 0) < 3000000] #

        html = """
        <h3>Хөрөнгө оруулалтын боломжит бүсүүд (м.кв дундаж үнээр ангилсан):</h3>
        """ #

        if expensive_districts:
            html += "<h4>💰 Өндөр зэрэглэлийн бүс (&gt;4,000,000₮/м²):</h4><ul>" #
            for district in expensive_districts:
                html += f"<li><strong>{self.formatter.clean_text_for_html(district.get('name'))}</strong> - Урт хугацааны үнэ цэнийн өсөлт, нэр хүндтэй байршил.</li>" #
            html += "</ul>" #
        
        if moderate_districts:
            html += "<h4>🏠 Дундаж үнийн бүс (3,000,000-4,000,000₮/м²):</h4><ul>" #
            for district in moderate_districts:
                html += f"<li><strong>{self.formatter.clean_text_for_html(district.get('name'))}</strong> - Тэнцвэртэй хөрөнгө оруулалт, тогтвортой өгөөж.</li>" #
            html += "</ul>" #

        if affordable_districts:
            html += "<h4>🌟 Боломжийн үнэтэй бүс (&lt;3,000,000₮/м²):</h4><ul>" #
            for district in affordable_districts:
                html += f"<li><strong>{self.formatter.clean_text_for_html(district.get('name'))}</strong> - Эхний хөрөнгө оруулагчдад болон түрээсийн өндөр өгөөж хүсэгчдэд.</li>" #
            html += "</ul>" #
        
        if not expensive_districts and not moderate_districts and not affordable_districts:
            html += "<p>Өгөгдсөн дүүргүүдээс хөрөнгө оруулалтын бүсчлэлийг ангилахад хангалттай мэдээлэл алга.</p>"

        return html

    def _build_district_advantages_section(self, districts_data: List[Dict]) -> str: #
        """Section 4: District Advantages & Disadvantages (Logic based on data)"""
        html = "<h3>Дүүргүүдийн онцлог ба давуу сул тал (ерөнхий үнэлгээ):</h3>" #

        if not districts_data: #
            return html + "<p>Дүүргүүдийн онцлогийг тодорхойлох мэдээлэл байхгүй.</p>" #

        # Analyze top 3 distinct districts by price if available, or all if less than 3
        valid_districts_for_adv = [d for d in districts_data if isinstance(d.get('overall_avg'), (int, float)) and d['overall_avg'] > 0 and d.get('name')]
        
        if not valid_districts_for_adv:
             return html + "<p>Дүүргүүдийн онцлогийг тодорхойлох мэдээлэл хангалтгүй байна.</p>"

        sorted_districts = sorted(valid_districts_for_adv, key=lambda x: x.get('overall_avg', 0), reverse=True)[:3] #

        for i, district in enumerate(sorted_districts):
            name = self.formatter.clean_text_for_html(district.get('name', 'Тодорхойгүй')) #
            price = district.get('overall_avg', 0) #

            advantages = [] #
            disadvantages = [] #

            if price > 4000000: #
                advantages.extend(["Нэр хүндтэй байршил", "Дэд бүтэц сайн хөгжсөн", "Үйлчилгээний хүртээмж өндөр"]) #
                disadvantages.extend(["Үл хөдлөх хөрөнгийн үнэ өндөр", "Хөрөнгө оруулалтын эхлэлтийн зардал их"]) #
            elif price > 3000000: #
                advantages.extend(["Үнэ болон байршлын тэнцвэртэй харьцаа", "Олон нийтийн тээврийн хүртээмж сайн", "Тогтвортой зах зээл"]) #
                disadvantages.extend(["Дундаж өсөлттэй байж болзошгүй", "Зарим хэсэгт хэт төвлөрөл үүссэн байж болно"]) #
            else: # price <= 3000000 and price > 0
                advantages.extend(["Боломжийн үнэ", "Ирээдүйд үнэ цэнэ өсөх потенциал", "Анхны худалдан авагчдад тохиромжтой"]) #
                disadvantages.extend(["Зарим дэд бүтэц хөгжиж буй шатанд", "Хотын төвөөс зайтай байж болзошгүй"]) #

            html += f"""
            <h4>{i+1}. {name} дүүрэг:</h4>
            <p><strong>Давуу тал (ерөнхийлсөн):</strong> {', '.join(advantages) if advantages else "Тодорхойгүй"}</p>
            <p><strong>Сул тал (ерөнхийлсөн):</strong> {', '.join(disadvantages) if disadvantages else "Тодорхойгүй"}</p>
            """ #
        if not sorted_districts:
             html += "<p>Онцлох дүүргийн мэдээлэл алга байна.</p>"
        return html

    def _build_buyer_strategies_section(self, districts_data: List[Dict]) -> str: #
        """Section 5: Buyer Strategies (Semi-static with dynamic district hints)"""
        html = "<h3>Худалдан авагчдад зориулсан стратеги:</h3>" #
        
        family_district_suggestion = "Тохиромжтой дүүргийн мэдээлэл дутмаг."
        if districts_data: #
            # Suggest districts with available 3-room average price, preferably lower for families
            family_districts = [d for d in districts_data if isinstance(d.get('three_room_avg'), (int, float)) and d.get('three_room_avg', 0) > 0 and d.get('name')]
            if family_districts: #
                best_family_district = min(family_districts, key=lambda x: x.get('three_room_avg', float('inf'))) #
                family_district_suggestion = f"{self.formatter.clean_text_for_html(best_family_district.get('name'))} дүүрэг (3 өрөөний дундаж үнэ харьцангуй боломжийн)." #
        
        starter_district_suggestion = "Тохиромжтой дүүргийн мэдээлэл дутмаг."
        if districts_data: #
            # Suggest affordable districts for first-time buyers
            affordable_districts = [d for d in districts_data if isinstance(d.get('overall_avg'), (int,float)) and d.get('overall_avg', 0) > 0 and d.get('overall_avg', 0) < 3500000 and d.get('name')] #
            if affordable_districts: #
                best_starter_district = min(affordable_districts, key=lambda x: x.get('overall_avg', float('inf'))) #
                starter_district_suggestion = f"{self.formatter.clean_text_for_html(best_starter_district.get('name'))} дүүрэг (ерөнхий дундаж үнэ харьцангуй боломжийн)." #


        html += f"""
        <h4>👨‍👩‍👧‍👦 Гэр бүлээрээ амьдрах гэж буй худалдан авагчид:</h4>
        <ul>
            <li>Сургууль, цэцэрлэг, эмнэлэг, ногоон байгууламж зэрэг гэр бүлд ээлтэй дэд бүтцийн ойр орчмыг сонгох.</li>
            <li>3 ба түүнээс дээш өрөөтэй, талбай томтой орон сууцыг судлах.</li>
            <li>Санал болгож болох дүүрэг (жишээ): {family_district_suggestion}</li>
        </ul>
        
        <h4>🏠 Анх удаа орон сууц худалдан авагчид:</h4>
        <ul>
            <li>Санхүүгийн боломждоо тохирсон 1-2 өрөө байрнаас эхлэх.</li>
            <li>Ажлын газар болон нийтийн тээврийн хүртээмж сайтай байршлыг сонгох.</li>
            <li>Ипотекийн зээлийн нөхцөлүүдийг сайтар судлах.</li>
            <li>Санал болгож болох дүүрэг (жишээ): {starter_district_suggestion}</li>
        </ul>
        
        <h4>💼 Хөрөнгө оруулагчид:</h4>
        <ul>
            <li>Түрээсийн эрэлт өндөртэй, өгөөж сайтай байршлуудыг судлах.</li>
            <li>Ирээдүйд үнэ цэнэ нь өсөх боломжтой, хөгжиж буй бүс нутгуудад анхаарах.</li>
            <li>Зах зээлийн чиг хандлага, үнийн өөрчлөлтийг тогтмол хянах.</li>
            <li>Олон төрлийн үл хөдлөх хөрөнгийн багц бүрдүүлэхийг зорих.</li>
        </ul>
        """ #
        return html

    # MODIFIED: Accepts dynamic content
    def _build_future_development_section(self, future_development_content: str) -> str: #
        """Section 6: Future Development Outlook - Now Dynamic"""
        # The H3 title is part of the main HTML structure using REPORT_TEMPLATES
        # This method now just returns the formatted LLM-generated content.
        return f"""
        <p>{self.formatter.clean_text_for_html(future_development_content)}</p>
        """

    def _build_additional_research_section(self, search_results: str) -> str: #
        """Section 7: Additional Research Information (from search)"""
        search_content = "Интернэт судалгааны нэмэлт мэдээлэл байхгүй." #
        if search_results and search_results.strip(): #
            search_content = self.formatter.clean_text_for_html(search_results) #

        return f"""
        <h3>Нэмэлт интернэт судалгааны үр дүн:</h3>
        <p>{search_content}</p>
        
        <h3>Мэдээллийн нэмэлт эх сурвалжууд:</h3>
        <ul>
            <li>Албан ёсны статистикийн газрууд (Үндэсний Статистикийн Хороо г.м)</li>
            <li>Үл хөдлөх хөрөнгийн мэргэшсэн агентлагуудын тайлан, судалгаа</li>
            <li>Банк, санхүүгийн байгууллагуудын ипотекийн зээлийн мэдээлэл</li>
            <li>Барилга, хот байгуулалтын яамны мэдээ, төлөвлөгөө</li>
            <li>Үл хөдлөх хөрөнгийн онлайн зар сурталчилгааны платформууд</li>
        </ul>
        """ #

    def _build_districts_table(self, districts_data: List[Dict]) -> str: #
        """Build HTML table for district comparison"""
        if not districts_data: #
            return "<p>Дүүргүүдийн дэлгэрэнгүй харьцуулалт хийх мэдээлэл байхгүй.</p>" #

        table_config = TABLE_CONFIG["district_comparison"] #
        
        # Ensure districts_data for sorting is valid
        valid_districts_for_table = [
            d for d in districts_data 
            if d.get('name') and isinstance(d.get(table_config["sort_key"], 0), (int, float)) #
        ]
        
        if not valid_districts_for_table:
            return "<p>Дүүргүүдийн дэлгэрэнгүй харьцуулалт хийхэд хангалттай мэдээлэл алга.</p>"


        try:
            districts_sorted = sorted(
                valid_districts_for_table,
                key=lambda x: float(x.get(table_config["sort_key"], 0.0)), #
                reverse=True
            )
        except Exception as e:
            logger.error(f"Error sorting districts for table: {e}") #
            districts_sorted = valid_districts_for_table # Use unsorted if error

        html = f"""
            <h3>Дүүргүүдийн дэлгэрэнгүй харьцуулалт (м.кв дундаж үнээр):</h3>
            <table>
                <thead>
                    <tr>
        """ #

        for header in table_config["headers"]: #
            html += f"<th>{header}</th>" #

        html += """
                    </tr>
                </thead>
                <tbody>
        """ #

        for district in districts_sorted:
            name = self.formatter.clean_text_for_html(district.get('name', 'Тодорхойгүй')) #
            overall = self.formatter.format_price_html(district.get('overall_avg', 0)) #
            two_room = self.formatter.format_price_html(district.get('two_room_avg', 0)) #
            three_room = self.formatter.format_price_html(district.get('three_room_avg', 0)) #

            html += f"""
                    <tr>
                        <td>{name}</td>
                        <td>{overall}</td>
                        <td>{two_room}</td>
                        <td>{three_room}</td>
                    </tr>
            """ #

        html += """
                </tbody>
            </table>
        """ #
        return html


class MarketHTMLBuilder:
    """Builds HTML content for market analysis reports with 7 sections"""

    def __init__(self, formatter: HTMLFormatter): #
        self.formatter = formatter #

    # MODIFIED: Added new dynamic content parameters
    def build_html(self, market_summary: str, district_analysis: str, user_query: str,
                   supply_demand_content: str,
                   investment_strategy_content: str,
                   risk_assessment_content: str) -> str: #
        """Build HTML content for market analysis report with 7 sections"""
        now = datetime.now() #

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self.formatter.get_base_css()}</style>
            <title>{REPORT_TEMPLATES['market']['title']}</title>
        </head>
        <body>
            <h1>{REPORT_TEMPLATES['market']['title']}</h1>
            <p class="report-date">Тайлангийн огноо: {now.strftime(DATE_FORMATS['mongolian'])}</p>
            <p><strong>Хайлтын утга (Хэрэглэгчийн асуулга):</strong> {self.formatter.clean_text_for_html(user_query)}</p>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][0]}</h2>
                {self._build_market_overview_section(market_summary)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][1]}</h2>
                {self._build_price_trends_section(market_summary)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][2]}</h2>
                {self._build_supply_demand_section(supply_demand_content)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][3]}</h2>
                {self._build_district_comparison_section(district_analysis)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][4]}</h2>
                {self._build_investment_strategy_section(investment_strategy_content)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][5]}</h2>
                {self._build_risk_assessment_section(risk_assessment_content)}
            </div>

            <div class="section">
                <h2>{REPORT_TEMPLATES['market']['sections'][6]}</h2>
                {self._build_market_forecast_section(market_summary)}
            </div>

            <div id="footer_content" class="footer-text">
                Улаанбаатар хотын үл хөдлөх хөрөнгийн туслах систем © {now.year}
            </div>
        </body>
        </html>
        """ #

        return html

    def _build_market_overview_section(self, market_summary: str) -> str: #
        """Section 1: Market Overview & Summary (Uses part of LLM summary)"""
        # market_summary is expected to be a comprehensive LLM summary.
        # We can take a portion for the overview.
        overview_text = market_summary
        if len(market_summary) > 800: # Adjust length as needed
            match = re.search(r'(Зах Зээлийн Ерөнхий Тойм|Market Overview):?\s*(.*?)(?=\n\n(?:2\.|II\.|[A-ZӨҮ]))', market_summary, re.DOTALL | re.IGNORECASE)
            if match and match.group(2).strip():
                overview_text = match.group(2).strip()
            else: # Fallback if specific section not found in summary
                overview_text = (market_summary.split("\n\n")[0] if "\n\n" in market_summary else market_summary[:800]) + "..."


        return f"""
        <h3>Зах зээлийн ерөнхий байдал (LLM хураангуй):</h3>
        <p>{self.formatter.clean_text_for_html(overview_text)}</p>
        
        <h3>Гол үзүүлэлтүүд (ерөнхий төлөв):</h3>
        <ul>
            <li><strong>Зах зээлийн идэвхжил:</strong> Ихэвчлэн улирлын чанартай, эдийн засгийн нөхцөл байдлаас хамаарна.</li>
            <li><strong>Худалдан авагчдын эрэлт:</strong> Зээлийн хүртээмж, хүн амын өсөлт, орлогын түвшин зэргээс шалтгаална.</li>
            <li><strong>Нийлүүлэлтийн байдал:</strong> Шинэ барилгын төслүүд, хуучин орон сууцны зах зээлийн идэвхээс хамаарна.</li>
        </ul>
        """ #

    def _build_price_trends_section(self, market_summary: str) -> str: #
        """Section 2: Price Changes & Trends (Uses part of LLM summary)"""
        trends_text = market_summary
        if len(market_summary) > 800: # Adjust length as needed
            match = re.search(r'(Үнийн Харьцуулалт ба Ялгаа|Price Comparison and Differentials|Үнийн чиг хандлага|Price Trends):?\s*(.*?)(?=\n\n(?:3\.|III\.|[A-ZӨҮ]))', market_summary, re.DOTALL | re.IGNORECASE)
            if match and match.group(2).strip():
                trends_text = match.group(2).strip()
            else: # Fallback if specific section not found in summary
                 # Try to find a second paragraph or a good chunk
                paragraphs = market_summary.split("\n\n")
                if len(paragraphs) > 1:
                    trends_text = paragraphs[1][:800] + "..." if len(paragraphs[1]) > 800 else paragraphs[1]
                else:
                    trends_text = market_summary[:800] + ("..." if len(market_summary) > 800 else "")


        return f"""
        <h3>Үнийн чиг хандлага (LLM хураангуй):</h3>
        <p>{self.formatter.clean_text_for_html(trends_text)}</p>
        
        <h3>Үнэд нөлөөлөх гол хүчин зүйлүүд:</h3>
        <ul>
            <li>Инфляци ба валютын ханшны өөрчлөлт</li>
            <li>Ипотекийн зээлийн хүү, зээлийн нөхцөл</li>
            <li>Барилгын материалын үнэ, нийлүүлэлт</li>
            <li>Засгийн газрын бодлого, хот төлөвлөлт</li>
            <li>Хүн амын өсөлт, шилжилт хөдөлгөөн</li>
        </ul>
        """ #

    # MODIFIED: Accepts dynamic content
    def _build_supply_demand_section(self, supply_demand_content: str) -> str: #
        """Section 3: Supply & Demand Analysis - Now Dynamic"""
        return f"""
        <h3>Эрэлт ба нийлүүлэлтийн шинжилгээ (LLM шинжилгээ):</h3>
        <p>{self.formatter.clean_text_for_html(supply_demand_content)}</p>
        """

    def _build_district_comparison_section(self, district_analysis: str) -> str: #
        """Section 4: District Market Comparison (Uses LLM analysis of district data)"""
        # district_analysis is expected to be the output of _analyze_market_for_report from ReportService
        return f"""
        <h3>Дүүргүүдийн зах зээлийн харьцуулсан шинжилгээ (LLM шинжилгээ):</h3>
        <p>{self.formatter.clean_text_for_html(district_analysis)}</p>
        
        <h3>Зах зээлийн сегментчилэл (ерөнхий ангилал):</h3>
        <ul>
            <li><strong>Премиум сегмент:</strong> Ихэвчлэн хотын төвийн болон шинээр хөгжиж буй тансаг зэрэглэлийн бүсүүд.</li>
            <li><strong>Дундаж сегмент:</strong> Дэд бүтэц сайтай, олон нийтэд хүртээмжтэй, тогтсон суурьшлын бүсүүд.</li>
            <li><strong>Боломжийн үнэтэй сегмент:</strong> Хотын захын болон хөгжиж буй шинэ суурьшлын бүсүүд.</li>
        </ul>
        """ #

    # MODIFIED: Accepts dynamic content
    def _build_investment_strategy_section(self, investment_strategy_content: str) -> str: #
        """Section 5: Investment Strategy & Opportunities - Now Dynamic"""
        return f"""
        <h3>Хөрөнгө оруулалтын стратеги ба боломжууд (LLM зөвлөмж):</h3>
        <p>{self.formatter.clean_text_for_html(investment_strategy_content)}</p>
        """

    # MODIFIED: Accepts dynamic content
    def _build_risk_assessment_section(self, risk_assessment_content: str) -> str: #
        """Section 6: Risk Assessment & Warnings - Now Dynamic"""
        return f"""
        <h3>Эрсдэлийн үнэлгээ ба анхааруулга (LLM шинжилгээ):</h3>
        <p>{self.formatter.clean_text_for_html(risk_assessment_content)}</p>
        """

    def _build_market_forecast_section(self, market_summary: str) -> str: #
        """Section 7: Market Forecast & Recommendations (Uses part of LLM summary)"""
        forecast_text = market_summary
        if len(market_summary) > 800: # Adjust length as needed
             match = re.search(r'(Зах Зээлийн Ирээдүйн Төлөв|Market Outlook|Таамаглал|Forecast):?\s*(.*?)(?:\Z|\n\n(?:[A-ZӨҮ]))', market_summary, re.DOTALL | re.IGNORECASE)
             if match and match.group(2).strip():
                 forecast_text = match.group(2).strip()
             else: # Fallback if specific section not found
                paragraphs = market_summary.split("\n\n")
                if len(paragraphs) > 2: # Try to get a later part of the summary
                    forecast_text = ("\n\n".join(paragraphs[2:]))[:800] + "..." if len("\n\n".join(paragraphs[2:])) > 800 else "\n\n".join(paragraphs[2:])
                elif paragraphs: # Get the last part if only one or two paragraphs
                    forecast_text = paragraphs[-1][:800] + "..." if len(paragraphs[-1]) > 800 else paragraphs[-1]
                else: # Fallback to a generic statement or a smaller part of the summary
                    forecast_text = market_summary[:500] + "..." if len(market_summary) > 500 else market_summary


        return f"""
        <h3>Зах зээлийн таамаглал ба зөвлөмж (LLM хураангуй):</h3>
        <p>{self.formatter.clean_text_for_html(forecast_text)}</p>
        
        <h3>Ерөнхий зөвлөмж:</h3>
        <ul>
            <li>Зах зээлийн судалгааг тогтмол хийж, мэдээлэлтэй байх.</li>
            <li>Хувийн санхүүгийн байдал, зорилгодоо нийцүүлэн шийдвэр гаргах.</li>
            <li>Шаардлагатай бол мэргэжлийн үл хөдлөх хөрөнгийн болон санхүүгийн зөвлөхөөс зөвлөгөө авах.</li>
            <li>Гэрээ, бичиг баримтыг сайтар нягталж, хууль эрх зүйн орчныг ойлгох.</li>
        </ul>
        """ #