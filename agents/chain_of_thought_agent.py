# agents/chain_of_thought_agent.py - COMPLETELY IMPROVED VERSION
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
    Improved Chain-of-Thought reasoning agent that provides clear, valuable analysis
    with concise steps and actionable insights.
    """

    def __init__(self, llm):
        self.llm = llm

    async def enhance_response_with_reasoning(self,
                                              original_response: str,
                                              analysis_type: str,
                                              data: Dict[str, Any],
                                              user_query: str) -> str:
        """
        Enhance response with clear, valuable chain-of-thought reasoning
        """
        try:
            # Get the appropriate reasoning template based on analysis type
            if analysis_type == "property_analysis":
                enhanced_response = await self._property_cot_analysis(original_response, data, user_query)
            elif analysis_type == "district_comparison":
                enhanced_response = await self._district_cot_analysis(original_response, data, user_query)
            elif analysis_type == "market_research":
                enhanced_response = await self._market_cot_analysis(original_response, data, user_query)
            else:
                # For other types, just return original with minimal enhancement
                return f"**💡 Шинжилгээ:**\n{original_response}"

            return enhanced_response

        except Exception as e:
            logger.error(f"Error in CoT enhancement: {e}")
            return original_response

    async def _property_cot_analysis(self, original_response: str, data: Dict[str, Any], user_query: str) -> str:
        """Generate clear property analysis with reasoning steps"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate expert. Provide clear, step-by-step analysis of a property with ACTIONABLE insights.

Create a structured analysis with these sections:
1. **Үнийн шинжилгээ** - Is the price fair? Compare to market averages
2. **Байршлын давуу тал** - Location advantages and disadvantages  
3. **Хөрөнгө оруулалтын үнэлгээ** - Investment potential with specific numbers
4. **Эрсдлийн үнэлгээ** - What could go wrong?
5. **Практик зөвлөмж** - Specific actionable advice

For each section:
- Be specific with numbers and facts
- Provide clear reasoning 
- Give actionable insights
- Keep each section 2-3 sentences maximum

IMPORTANT: 
- Write ONLY in Mongolian
- Be concise and valuable
- Focus on insights the user can act on
- No repetition or filler content"""),
            ("human", """Property data: {property_data}

User question: {user_query}

Provide clear, valuable property analysis with step-by-step reasoning in Mongolian.""")
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
        """Generate clear district analysis with reasoning steps"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a real estate market analyst. Provide clear district analysis with SPECIFIC insights.

Create structured analysis with these sections:
1. **Үнийн байдал** - Current price levels with specific numbers
2. **Харьцуулалт** - How it compares to other districts (be specific)
3. **Хөрөнгө оруулалтын боломж** - Investment opportunities with ROI estimates
4. **Худалдан авагчдад зөвлөмж** - Who should buy here and why
5. **Ирээдүйн төлөв** - What to expect in 1-2 years

For each section:
- Use specific numbers and percentages
- Give clear comparisons
- Provide actionable advice
- Maximum 2-3 sentences per section

IMPORTANT:
- Write ONLY in Mongolian  
- Be specific and valuable
- No repetitive content
- Focus on actionable insights"""),
            ("human", """District data: {district_data}

User question: {user_query}

Provide clear, valuable district analysis with reasoning in Mongolian.""")
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
            ("system", """You are a market research expert. Provide clear market analysis with SPECIFIC insights.

Create analysis with these sections:
1. **Одоогийн зах зээлийн нөхцөл** - Current market state with facts
2. **Үнийн чиглэл** - Price trends with specific predictions  
3. **Хөрөнгө оруулалтын боломж** - Best investment opportunities now
4. **Эрсдэл** - What risks to watch for
5. **Стратеги зөвлөмж** - What to do in next 6 months

For each section:
- Use specific data from search results
- Give timeline-based advice
- Provide clear action items
- Maximum 2-3 sentences per section

IMPORTANT:
- Write ONLY in Mongolian
- Be specific and actionable  
- No vague statements
- Focus on what user should do"""),
            ("human", """Market data: {market_data}

User question: {user_query}

Provide clear, valuable market analysis with reasoning in Mongolian.""")
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
        """Get statistics about reasoning performance"""
        return {
            "available_templates": 3,
            "analysis_types": self.get_analysis_types(),
            "last_updated": datetime.now().isoformat(),
            "approach": "concise_valuable_insights"
        }