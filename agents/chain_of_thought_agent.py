# agents/chain_of_thought_agent.py - ENHANCED VERSION WITH ENGLISH PROMPTS
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChainOfThoughtAgent:
    """
    Enhanced Chain of Thought Agent that provides clear, valuable analysis
    with concise steps and actionable insights using English prompts for better reasoning.
    """

    def __init__(self, llm):
        self.llm = llm

    async def enhance_response_with_reasoning(self,
                                              original_response: str,
                                              analysis_type: str,
                                              data: Dict[str, Any],
                                              user_query: str) -> str:
        """
        Enhance response with clear, valuable chain of thought reasoning
        """
        try:
            # Get available analysis types
            if analysis_type == "property_analysis":
                enhanced_response = await self._property_cot_analysis(original_response, data, user_query)
            elif analysis_type == "district_comparison":
                enhanced_response = await self._district_cot_analysis(original_response, data, user_query)
            elif analysis_type == "market_research":
                enhanced_response = await self._market_cot_analysis(original_response, data, user_query)
            else:
                # Fallback for other types
                return f"**💡 Шинжилгээ:**\n{original_response}"

            return enhanced_response

        except Exception as e:
            logger.error(f"Error in CoT enhancement: {e}")
            return original_response

    async def _property_cot_analysis(self, original_response: str, data: Dict[str, Any], user_query: str) -> str:
        """Generate property analysis with clear reasoning steps"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate analyst. Your task is to provide clear, valuable analysis with specific reasoning steps.

Analyze the property data and provide insights in the following structure:
1. **Price Analysis** - What does the pricing indicate?
2. **Location Advantages** - Strengths and weaknesses of the location
3. **Investment Evaluation** - Investment potential assessment
4. **Risk Assessment** - What could go wrong?
5. **Practical Recommendations** - Specific actionable advice

For each section:
- Use specific numbers and facts from the data
- Show clear reasoning steps (because X, therefore Y)
- Provide valuable insights that help decision-making
- Keep each section to 2-3 sentences maximum
- Be specific and actionable, avoid vague statements

CRITICAL: Your final response must be written entirely in Mongolian language. Think through the analysis in English, but write your final answer in Mongolian."""),
            ("human", """Property data: {property_data}

User question: {user_query}

Provide detailed property analysis with clear reasoning steps. Write your final response in Mongolian.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        cot_analysis = await chain.ainvoke({
            "property_data": json.dumps(data, ensure_ascii=False, indent=2),
            "user_query": user_query
        })

        # Format the response
        enhanced_response = f"""**🧠 Дэлгэрэнгүй шинжилгээ:**

{cot_analysis}

---
**💡 Хураангуй хариулт:**
{original_response}"""

        return enhanced_response

    async def _district_cot_analysis(self, original_response: str, data: Dict[str, Any], user_query: str) -> str:
        """Generate district analysis with clear reasoning steps"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate market analyst specializing in district comparisons. Your task is to provide clear, valuable analysis with specific reasoning steps.

Analyze the district data and provide insights in the following structure:
1. **Price Situation** - What do the prices indicate?
2. **Comparative Analysis** - How does it compare to other districts?
3. **Investment Opportunities** - Investment potential assessment
4. **Buyer Recommendations** - Advice for different types of buyers
5. **Future Outlook** - What to expect in the coming months

For each section:
- Use specific numbers and facts from the data
- Show clear reasoning steps (because X, therefore Y)
- Provide valuable insights that help decision-making
- Keep each section to 2-3 sentences maximum
- Be specific and actionable, avoid vague statements
- Compare with other districts when relevant

CRITICAL: Your final response must be written entirely in Mongolian language. Think through the analysis in English, but write your final answer in Mongolian."""),
            ("human", """District data: {district_data}

User question: {user_query}

Provide detailed district analysis with clear reasoning steps. Write your final response in Mongolian.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        cot_analysis = await chain.ainvoke({
            "district_data": json.dumps(data, ensure_ascii=False, indent=2),
            "user_query": user_query
        })

        enhanced_response = f"""**🧠 Дэлгэрэнгүй шинжилгээ:**

{cot_analysis}

---
**💡 Хураангуй хариулт:**
{original_response}"""

        return enhanced_response

    async def _market_cot_analysis(self, original_response: str, data: Dict[str, Any], user_query: str) -> str:
        """Generate clear market research analysis"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional real estate market research analyst. Your task is to provide clear, valuable market analysis with specific reasoning steps.

Analyze the market data and provide insights in the following structure:
1. **Current Market Conditions** - What is the current state of the market?
2. **Price Trends** - Where are prices heading and why?
3. **Investment Opportunities** - Best investment potential assessment
4. **Risk Factors** - What risks should investors be aware of?
5. **Strategic Recommendations** - What should be done in the next 6 months?

For each section:
- Use specific data from search results and market indicators
- Show clear reasoning steps (because X, therefore Y)
- Give timeline-based advice with specific timeframes
- Provide clear action items that can be implemented
- Keep each section to 2-3 sentences maximum
- Be specific and actionable, no vague statements
- Focus on what the user should actually do

CRITICAL: Your final response must be written entirely in Mongolian language. Think through the analysis in English, but write your final answer in Mongolian."""),
            ("human", """Market data: {market_data}

User question: {user_query}

Provide clear, valuable market analysis with reasoning steps. Write your final response in Mongolian.""")
        ])

        chain = prompt | self.llm | StrOutputParser()
        cot_analysis = await chain.ainvoke({
            "market_data": json.dumps(data, ensure_ascii=False, indent=2),
            "user_query": user_query
        })

        enhanced_response = f"""**🧠 Зах зээлийн дэлгэрэнгүй шинжилгээ:**

{cot_analysis}

---
**💡 Хураангуй хариулт:**
{original_response}"""

        return enhanced_response

    def get_analysis_types(self) -> List[str]:
        """Get available analysis types"""
        return ["property_analysis", "district_comparison", "market_research"]

    def get_reasoning_stats(self) -> Dict[str, Any]:
        """Get reasoning performance statistics"""
        return {
            "available_templates": 3,
            "analysis_types": self.get_analysis_types(),
            "last_updated": datetime.now().isoformat(),
            "approach": "english_prompts_mongolian_output",
            "reasoning_method": "step_by_step_with_because_therefore_logic"
        }