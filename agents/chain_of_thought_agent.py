import logging
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class ChainOfThoughtAgent:
    def __init__(self, llm):
        self.llm = llm

    async def enhance_response_with_reasoning(self, original_response: str, analysis_type: str,
                                              data: Dict[str, Any], user_query: str) -> str:
        try:
            if analysis_type == "property_analysis":
                system_prompt = self._get_property_prompt()
            elif analysis_type == "district_comparison":
                system_prompt = self._get_district_prompt()
            else:
                system_prompt = self._get_market_prompt()


            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", """Data: {data}
User query: {query}
Provide detailed analysis following the structure above. Write your response in Mongolian language.""")
            ])

            chain = prompt | self.llm | StrOutputParser()
            cot_analysis = await chain.ainvoke({
                "data": str(data),
                "query": user_query
            })


            return f"""**Дэлгэрэнгүй шинжилгээ:**

{cot_analysis}

---
**Хураангуй:**
{original_response}"""

        except Exception as e:
            logger.error(f"CoT алдаа: {e}")
            return original_response

    def _get_property_prompt(self) -> str:
        return """You are a professional real estate analyst. Provide detailed property analysis with the following structure:

1. **Price Analysis** - Is the price fair and reasonable?
2. **Location Benefits** - Location strengths and weaknesses  
3. **Investment Potential** - Future opportunities and risks
4. **Recommendations** - Specific actionable advice

For each section:
- Use specific numbers and facts from the data
- Show clear reasoning (because X, therefore Y)
- Keep each section to 2-3 sentences maximum
- Be specific and actionable

CRITICAL: Your final response must be written entirely in Mongolian language."""

    def _get_district_prompt(self) -> str:
        return """You are a real estate market analyst. Provide district analysis with the following structure:

1. **Price Situation** - Current price levels and trends
2. **Comparative Analysis** - How it compares to other districts
3. **Investment Opportunities** - Potential and risks
4. **Buyer Recommendations** - Who should buy here and why?

For each section:
- Use specific data and numbers
- Compare with other districts when relevant
- Provide clear reasoning
- Keep concise but valuable

CRITICAL: Your final response must be written entirely in Mongolian language."""

    def _get_market_prompt(self) -> str:
        return """You are a real estate market researcher. Provide market analysis with the following structure:

1. **Market Conditions** - Current state of the market
2. **Price Trends** - Where prices are heading and why
3. **Best Opportunities** - Top investment potential right now
4. **Strategic Recommendations** - What to do in the next 6 months

For each section:
- Use specific market data and indicators
- Provide timeline-based advice
- Give clear action items
- Focus on practical insights

CRITICAL: Your final response must be written entirely in Mongolian language."""