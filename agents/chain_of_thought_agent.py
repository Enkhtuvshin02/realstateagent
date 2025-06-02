# Modified chain_of_thought_agent.py

import logging
from typing import Dict, Any, Union
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class ChainOfThoughtAgent:
    def __init__(self, llm):
        self.llm = llm

    async def enhance_with_cot(self, user_query: str, original_response: str, analysis_type: str = "district_analysis") -> str:
       
        logger.info(f"CoT Agent: Enhancing response with CoT for {analysis_type}")
        
        data = {
            "query": user_query,
            "response": original_response,
            "analysis_type": analysis_type
        }
        
        return await self.enhance_response_with_reasoning(original_response, analysis_type, data, user_query)
        
    async def enhance_response_with_reasoning(self,
                                              original_response: str,
                                              analysis_type: str,
                                              data: Dict[str, Any],
                                              user_query: str) -> str:
        logger.info(
            f"CoT Agent: Enhancing response for analysis_type '{analysis_type}'. User query: {user_query[:50]}...")

        try:
            system_prompt = ""
            if analysis_type == "property_analysis":
                system_prompt = self._get_property_prompt()
            elif analysis_type == "district_analysis":
                system_prompt = self._get_district_prompt()
            elif analysis_type == "district_comparison":
                system_prompt = self._get_district_comparison_prompt()
            elif analysis_type == "market_analysis":
                system_prompt = self._get_market_prompt()
            else:
                logger.warning(f"CoT Agent: Unknown analysis_type '{analysis_type}'. Returning original response.")
                return original_response

            prompt_data_str = json.dumps(data, ensure_ascii=False, indent=2)
            logger.debug(f"CoT Agent: Data for prompt ({analysis_type}):\n{prompt_data_str}")

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", """Original User Query: {user_query}
Provided Data for Analysis:
{prompt_data_str}

Original Summary (if available, for context only, do not repeat):
{original_response_summary}

---
Based on the 'Provided Data for Analysis' and the system prompt's structure, provide your detailed step-by-step reasoning and analysis.
Write your entire response in Mongolian language.""")
            ])

            chain = prompt | self.llm | StrOutputParser()

            cot_detailed_analysis = await chain.ainvoke({
                "user_query": user_query,
                "prompt_data_str": prompt_data_str,
                "original_response_summary": original_response
            })

            logger.info(
                f"CoT Agent: Detailed analysis generated for '{analysis_type}'. Length: {len(cot_detailed_analysis)}")

            return f"""{cot_detailed_analysis}

---
**Хураангуй:**
{original_response}"""

        except Exception as e:
            logger.exception(f"CoT Agent: Error during enhancement for {analysis_type}")
            return f"""**Дэлгэрэнгүй шинжилгээ:**
Уучлаарай, дэлгэрэнгүй шинжилгээг боловсруулахад алдаа гарлаа.

---
**Хураангуй:**
{original_response}"""

    def _get_property_prompt(self) -> str:
        return """You are a professional real estate analyst. From the 'Provided Data for Analysis', extract property details and relevant district analysis text. Then, provide a detailed property analysis with the following structure. The section titles in your response must be exactly as listed below (e.g., 1. **Үнийн Шинжилгээ (Price Analysis)**).

1.  **Үнийн Шинжилгээ (Price Analysis)**
    * From the 'Provided Data for Analysis', determine the price per square meter (price/m²) of the subject property.
    * Also from the 'Provided Data for Analysis', find the average price/m² for similar properties (e.g., same number of rooms) in its district from the district analysis text.
    * Compare these two price/m² values. Is the subject property's price/m² higher, lower, or similar to the district average?
    * Express the difference numerically (e.g., by X₮/m² more/less, or by Y% more/less).
    * Based on this price/m² comparison, conclude whether the property's price is reasonable, high, or low, and clearly explain why. Avoid vague statements.

2.  **Байршлын Давуу ба Сул Тал (Location Benefits and Drawbacks)** - Based on the property and district information, list the benefits and drawbacks of the location.

3.  **Хөрөнгө Оруулалтын Боломж (Investment Potential)** - Evaluate future opportunities and risks, citing specific data points. Consider short-term and long-term prospects.

4.  **Зөвлөмж (Recommendations)** - Provide specific, actionable advice for the user regarding this property.

Instructions:
-   For each section, use specific numbers and facts from the 'Provided Data for Analysis'.
-   Show clear reasoning (e.g., because of X, therefore Y).
-   Try to keep each section to 2-3 sentences.
-   Be specific and actionable.

CRITICAL: Таны эцсийн хариулт БҮХЭЛДЭЭ МОНГОЛ хэлээр бичигдсэн байх ёстой. Хариултаа шууд Монгол хэлээр эхлүүлнэ үү, жишээ нь: "1. Үнийн Шинжилгээ: ..."
CRITICAL: For the price analysis, you must compare the property's price per square meter with the average price per square meter of similarly sized (number of rooms) properties in the district, as mentioned above, and state the numerical difference."""

    def _get_district_prompt(self) -> str:
        return """You are a real estate market analyst. From the 'Provided Data for Analysis' (which contains 'district_analysis_text'), provide a detailed district analysis. The section titles in your response must be exactly as listed below.

Follow this structure:
1.  **Үнийн Түвшин ба Тренд (Price Levels and Trends)**: Detail current price levels, average prices by number of rooms (if available), and price trends mentioned in 'district_analysis_text'.
2.  **Бусад Дүүрэгтэй Харьцуулалт (Comparative Analysis)**: If 'district_analysis_text' contains comparisons with other districts, elaborate on them.
3.  **Хөрөнгө Оруулалтын Боломж ба Эрсдэл (Investment Opportunities and Risks)**: Identify investment opportunities, advantages, and potential risks mentioned in 'district_analysis_text'.
4.  **Зорилтот Худалдан Авагчид (Target Buyers)**: Based on 'district_analysis_text', advise what type of buyers (e.g., families, young couples, investors) might find this district most suitable.
5.  **Зах Зээлийн Онцлог ба Ирээдүйн Төлөв (Market Characteristics and Future Outlook)**: Detail market characteristics, development plans, or future outlook mentioned in 'district_analysis_text'.

Instructions:
-   Analysis MUST be based STRICTLY on the 'district_analysis_text' within 'Provided Data for Analysis'. Do not use external knowledge.
-   Use specific data and numbers if present in the text.
-   Provide clear reasoning.
-   Keep concise but valuable.

CRITICAL: Таны эцсийн хариулт БҮХЭЛДЭЭ МОНГОЛ хэлээр бичигдсэн байх ёстой. Хариултаа шууд Монгол хэлээр эхлүүлнэ үү, жишээ нь: "1. Үнийн Түвшин ба Тренд: ..." """

    def _get_district_comparison_prompt(self) -> str:
        return "You are a real estate market analyst. The 'Provided Data for Analysis' contains a 'district_comparison_summary' which lists average prices for various districts."

    def _get_market_prompt(self) -> str:
        return """You are a real estate market researcher. From the 'Provided Data for Analysis' (which contains 'search_results_text' from a web search), provide a detailed market analysis. The section titles in your response must be exactly as listed below.

Follow this structure:
1.  **Зах Зээлийн Одоогийн Нөхцөл Байдал (Current Market Conditions)**: Summarize the general market situation, supply-demand balance, and key players mentioned in 'search_results_text'.
2.  **Үнийн Чиг Хандлага ба Шалтгаан (Price Trends and Drivers)**: Identify price trends (growth, decline, stability) from 'search_results_text'. Mention factors influencing these trends (if any).
3.  **Хөрөнгө Оруулалтын Шилдэг Боломжууд (Best Investment Opportunities)**: Based on 'search_results_text', highlight what types of real estate (location, number of rooms, new/old, etc.) or which regions might offer better investment returns currently.
4.  **Болзошгүй Эрсдэл ба Анхааруулга (Potential Risks and Caveats)**: Identify potential market risks and points for investors and buyers to consider, as mentioned in 'search_results_text'.
5.  **Стратегийн Зөвлөмж (Strategic Recommendations)**: Based on 'search_results_text', offer strategic advice for buyers, sellers, or investors for the next 6-12 months.

Instructions:
-   Analysis MUST be based STRICTLY on the 'search_results_text' within 'Provided Data for Analysis'. Do not use external knowledge beyond interpreting this text.
-   Use specific market data and indicators if present in the text.
-   Provide timeline-based advice if possible.
-   Give clear action items.
-   Focus on practical insights.

CRITICAL: Таны эцсийн хариулт БҮХЭЛДЭЭ МОНГОЛ хэлээр бичигдсэн байх ёстой. Хариултаа шууд Монгол хэлээр эхлүүлнэ үү, жишээ нь: "1. Зах Зээлийн Одоогийн Нөхцөл Байдал: ..." """