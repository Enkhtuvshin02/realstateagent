import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import re
import json

from langchain_together import ChatTogether
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Import our services and agents
from services.report_service import ReportService
from agents.property_retriever import PropertyRetriever
from agents.district_analyzer import DistrictAnalyzer
from utils.pdf_generator import PDFReportGenerator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App Setup ---
app = FastAPI(title="Real Estate Assistant Chatbot")
templates = Jinja2Templates(directory="templates")

# Global variables
llm = None
search_tool = None
property_retriever_agent = None
district_analyzer_agent = None
pdf_generator = None
report_service = None

# Store last analyses
last_property_analysis = None
last_district_analysis = None


@app.on_event("startup")
async def startup_event():
    """Initialize everything on startup"""
    global llm, search_tool, property_retriever_agent, district_analyzer_agent, pdf_generator, report_service

    logger.info("🚀 Starting Enhanced Real Estate Assistant...")

    # Check API keys
    together_api_key = os.getenv("TOGETHER_API_KEY")
    tavily_api_key = os.getenv("TAVILY_API_KEY")

    if not together_api_key or not tavily_api_key:
        logger.error("Missing API keys in environment variables")
        raise ValueError("API keys not found")

    # Initialize LLM
    logger.info("🤖 Initializing LLM...")
    llm = ChatTogether(
        together_api_key=together_api_key,
        model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
        temperature=0.7
    )

    # Initialize search tool
    logger.info("🔍 Initializing search tool...")
    search_tool = TavilySearchResults(
        max_results=5,
        search_depth="advanced",
        include_answer=True,
        tavily_api_key=tavily_api_key
    )

    # Initialize agents
    logger.info("🏠 Initializing property retriever...")
    property_retriever_agent = PropertyRetriever(llm=llm)

    logger.info("📊 Initializing district analyzer...")
    district_analyzer_agent = DistrictAnalyzer(llm=llm, property_retriever=property_retriever_agent)

    logger.info("📄 Initializing PDF generator...")
    pdf_generator = PDFReportGenerator()

    # Initialize report service with search integration
    logger.info("📋 Initializing report service...")
    report_service = ReportService(
        llm=llm,
        district_analyzer=district_analyzer_agent,
        pdf_generator=pdf_generator,
        search_tool=search_tool
    )

    logger.info("✅ All components initialized successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if property_retriever_agent:
        await property_retriever_agent.close()


def is_report_request(message: str) -> bool:
    """Check if user wants a report"""
    keywords = [
        'тайлан', 'report', 'pdf', 'татаж авах', 'тиймээ', 'yes', 'тиим',
        'дэлгэрэнгүй тайлан', 'иж бүрэн тайлан', 'зах зээлийн тайлан'
    ]
    return any(keyword in message.lower() for keyword in keywords)


def get_report_type(message: str) -> str:
    """Determine what type of report is being requested"""
    message_lower = message.lower()

    if any(keyword in message_lower for keyword in ['дүүргийн тайлан', 'дүүрэг харьцуулах', 'бүх дүүрэг']):
        return "district"
    elif any(keyword in message_lower for keyword in ['иж бүрэн', 'дэлгэрэнгүй зах зээл', 'зах зээлийн тайлан']):
        return "comprehensive"
    elif last_property_analysis:
        return "property"
    else:
        return "district"  # Default to district report


def is_district_query(message: str) -> bool:
    """Check if message is about districts"""
    districts = ["хан-уул", "баянгол", "сүхбаатар", "чингэлтэй", "баянзүрх", "сонгинохайрхан"]
    location_keywords = ["дүүрэг", "байршил", "хот", "газар"]
    comparison_keywords = ["харьцуулалт", "харьцуулах", "бүх дүүрэг", "дүүргүүд"]

    message_lower = message.lower()
    return (any(d in message_lower for d in districts) or
            any(k in message_lower for k in location_keywords) or
            any(c in message_lower for c in comparison_keywords))


async def process_property_url(url: str, user_message: str) -> dict:
    """Process property URL"""
    global last_property_analysis

    try:
        logger.info(f"🏠 Processing property URL: {url}")

        # Get property details
        property_details = await property_retriever_agent.retrieve_property_details(url)

        if property_details.get("error"):
            return {
                "response": f"Мэдээлэл татаж авахад алдаа гарлаа: {property_details['error']}",
                "offer_report": False
            }

        # Get district analysis
        location = property_details.get("district", "Улаанбаатар")
        if location and location != "N/A":
            district_analysis = await district_analyzer_agent.analyze_district(location)
        else:
            district_analysis = "Дүүргийн мэдээлэл тодорхойгүй байна."

        # Store for reports
        last_property_analysis = {
            "property_details": property_details,
            "district_analysis": district_analysis,
            "url": url,
            "timestamp": datetime.now().isoformat()
        }

        # Check if user explicitly asked for report in the message
        if any(keyword in user_message.lower() for keyword in ['тайлан', 'report', 'pdf']):
            # Generate report immediately
            report_result = await report_service.generate_property_report(last_property_analysis)
            if isinstance(report_result, dict) and report_result.get("success"):
                return {
                    "response": report_result["message"],
                    "download_url": report_result["download_url"],
                    "filename": report_result["filename"],
                    "offer_report": False,
                    "report_generated": True
                }
            else:
                return {
                    "response": str(report_result),
                    "offer_report": False
                }

        # Generate response with search integration
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн мэргэжилтэн. Орон сууцны мэдээллийг Монгол хэлээр дэлгэрэнгүй тайлбарлана уу. 

Дараах зүйлсийг тусгана уу:
- Орон сууцны үндсэн мэдээлэл
- Үнийн шинжилгээ
- Дүүргийн харьцуулалт
- Практик зөвлөмж

Зөвхөн Монгол хэлээр хариулна уу."""),
            ("human", """Хэрэглэгчийн асуулт: {query}
Орон сууц: {property_details}  
Дүүргийн шинжилгээ: {district_analysis}

Хэрэглэгчийн асуултад Монгол хэлээр дэлгэрэнгүй хариулна уу.""")
        ])

        chain = prompt | llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": user_message,
            "property_details": json.dumps(property_details, ensure_ascii=False),
            "district_analysis": district_analysis
        })

        return {
            "response": response,
            "offer_report": True,
            "report_type": "property",
            "ask_for_report": True
        }

    except Exception as e:
        logger.error(f"❌ Error processing URL: {e}")
        return {
            "response": f"URL боловсруулахад алдаа гарлаа: {str(e)}",
            "offer_report": False
        }


async def process_district_query(user_message: str) -> dict:
    """Process district query"""
    global last_district_analysis

    try:
        logger.info("📍 Processing district query")

        # Extract specific district name if present
        district_name = extract_district_name(user_message)
        logger.info(f"📍 Extracted district name: {district_name}")

        # Use the specific district name or the full query for analysis
        query_for_analysis = district_name if district_name else user_message

        # Get district analysis
        district_analysis = await district_analyzer_agent.analyze_district(query_for_analysis)

        # Store for reports
        last_district_analysis = {
            "district_analysis": district_analysis,
            "query": user_message,
            "timestamp": datetime.now().isoformat()
        }

        # Check if user explicitly asked for report in the message
        if any(keyword in user_message.lower() for keyword in ['тайлан', 'report', 'pdf']):
            # Generate report immediately
            report_result = await report_service.generate_district_report()
            if isinstance(report_result, dict) and report_result.get("success"):
                return {
                    "response": report_result["message"],
                    "download_url": report_result["download_url"],
                    "filename": report_result["filename"],
                    "offer_report": False,
                    "report_generated": True
                }
            else:
                return {
                    "response": str(report_result),
                    "offer_report": False
                }

        # Generate response
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Та бол үл хөдлөх хөрөнгийн туслах. Дүүргийн шинжилгээг Монгол хэлээр тайлбарлана уу."),
            ("human",
             "Дүүргийн шинжилгээ: {district_analysis}\nХэрэглэгчийн асуулт: {query}\n\nМонгол хэлээр хариулна уу.")
        ])

        chain = prompt | llm | StrOutputParser()
        response = await chain.ainvoke({
            "district_analysis": district_analysis,
            "query": user_message
        })

        # Check if comprehensive query that might need report
        message_lower = user_message.lower()
        if any(keyword in message_lower for keyword in ["бүх дүүрэг", "харьцуулах", "дэлгэрэнгүй"]):
            return {
                "response": response,
                "offer_report": True,
                "report_type": "district",
                "ask_for_report": True
            }
        else:
            return {
                "response": response,
                "offer_report": False
            }

    except Exception as e:
        logger.error(f"❌ Error processing district query: {e}")
        return {
            "response": "Дүүргийн мэдээлэл боловсруулахад алдаа гарлаа.",
            "offer_report": False
        }


def extract_district_name(message: str) -> str:
    """Extract district name from message"""
    districts_mapping = {
        "хан-уул": "Хан-Уул",
        "баянгол": "Баянгол",
        "сүхбаатар": "Сүхбаатар",
        "чингэлтэй": "Чингэлтэй",
        "баянзүрх": "Баянзүрх",
        "сонгинохайрхан": "Сонгинохайрхан",
        "багануур": "Багануур",
        "налайх": "Налайх",
        "багахангай": "Багахангай"
    }

    message_lower = message.lower()
    for district_key, district_name in districts_mapping.items():
        if district_key in message_lower:
            return district_name
    return None


async def process_general_query(user_message: str) -> dict:
    """Process general query with search"""
    try:
        logger.info("🔍 Processing general query with search")

        # Search for relevant information
        search_results = search_tool.invoke({"query": user_message})

        # Clean search results to remove problematic content
        cleaned_results = clean_search_results(search_results)

        # Generate response
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Та бол үл хөдлөх хөрөнгийн туслах. Интернэт хайлтын үр дүнд үндэслэн хэрэглэгчийн асуултад Монгол хэлээр хариулна уу. 

Монгол улсын үл хөдлөх хөрөнгийн зах зээлд анхаарлаа хандуулна уу. Зөвхөн Монгол хэлээр хариулна уу."""),
            ("human", "Асуулт: {query}\nХайлтын үр дүн: {search_results}\n\nМонгол хэлээр хариулна уу.")
        ])

        chain = prompt | llm | StrOutputParser()
        response = await chain.ainvoke({
            "query": user_message,
            "search_results": cleaned_results
        })

        return {
            "response": response,
            "offer_report": False
        }

    except Exception as e:
        logger.error(f"❌ Error processing general query: {e}")
        return {
            "response": "Хайлт хийхэд алдаа гарлаа.",
            "offer_report": False
        }


def clean_search_results(search_results) -> str:
    """Clean search results to remove problematic content"""
    try:
        if isinstance(search_results, list):
            cleaned_content = []
            for result in search_results:
                if isinstance(result, dict):
                    # Extract text content and clean it
                    content = result.get('content', '') or result.get('snippet', '') or result.get('title', '')
                    if content:
                        # Remove image markdown syntax and other problematic patterns
                        content = re.sub(r'!\[.*?\]\(.*?\)', '', content)  # Remove ![](url) patterns
                        content = re.sub(r'\[.*?\]\(.*?\)', '', content)  # Remove [text](url) patterns
                        content = re.sub(r'<[^>]*>', '', content)  # Remove HTML tags
                        content = re.sub(r'\s+', ' ', content).strip()  # Normalize whitespace
                        if content and len(content) > 10:  # Only include meaningful content
                            cleaned_content.append(content)

            return ' '.join(cleaned_content[:5])  # Limit to first 5 results
        else:
            # Handle string results
            content = str(search_results)
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'<[^>]*>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content[:1000]  # Limit length

    except Exception as e:
        logger.error(f"Error cleaning search results: {e}")
        return "Хайлтын үр дүнг боловсруулахад алдаа гарлаа."


async def generate_report(report_type: str) -> dict:
    """Generate report based on type"""
    try:
        logger.info(f"📋 Generating {report_type} report")

        if report_type == "property":
            if not last_property_analysis:
                return {
                    "response": "Орон сууцны мэдээлэл байхгүй. Эхлээд орон сууцны холбоос илгээнэ үү.",
                    "offer_report": False
                }
            result = await report_service.generate_property_report(last_property_analysis)

        elif report_type == "district":
            result = await report_service.generate_district_report()

        elif report_type == "comprehensive":
            result = await report_service.generate_comprehensive_market_report()

        else:
            return {
                "response": "Тайлангийн төрөл тодорхойгүй байна.",
                "offer_report": False
            }

        # Handle both old string format and new dict format
        if isinstance(result, dict) and result.get("success"):
            return {
                "response": result["message"],
                "download_url": result["download_url"],
                "filename": result["filename"],
                "offer_report": False,
                "report_generated": True
            }
        else:
            return {
                "response": str(result),
                "offer_report": False
            }

    except Exception as e:
        logger.error(f"❌ Error generating {report_type} report: {e}")
        return {
            "response": f"Тайлан үүсгэхэд алдаа гарлаа: {str(e)}",
            "offer_report": False
        }


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    """Main chat page"""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/chat")
async def chat_endpoint(request: Request, user_message: str = Form(...)):
    """Main chat endpoint with enhanced features"""
    logger.info(f"📝 Chat message: {user_message}")

    # Check if services are ready
    if not llm or not property_retriever_agent or not report_service:
        return {"response": "Системийг эхлүүлж байна. Түр хүлээнэ үү.", "offer_report": False}

    try:
        # Process message based on type
        if is_report_request(user_message):
            # Determine report type and generate
            report_type = get_report_type(user_message)
            result = await generate_report(report_type)

        elif re.search(r'https?://\S+', user_message):
            # Property URL analysis
            url = re.search(r'https?://\S+', user_message).group(0)
            result = await process_property_url(url, user_message)

        elif is_district_query(user_message):
            # District analysis
            result = await process_district_query(user_message)

        else:
            # General query with search
            result = await process_general_query(user_message)

        logger.info("✅ Response generated successfully")
        return result

    except Exception as e:
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        return {"response": "Уучлаарай, алдаа гарлаа. Дахин оролдоно уу.", "offer_report": False}


@app.get("/download-report/{filename}")
async def download_report(filename: str):
    """Download PDF report"""
    try:
        file_path = Path("reports") / filename
        if not file_path.exists():
            return {"error": "File not found"}

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/pdf'
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        return {"error": str(e)}


@app.get("/reports/list")
async def list_reports():
    """List all available PDF reports"""
    try:
        reports_dir = Path("reports")
        if not reports_dir.exists():
            return {"status": "success", "reports": [], "total_reports": 0}

        pdf_files = list(reports_dir.glob("*.pdf"))
        report_info = []

        for report_path in sorted(pdf_files, key=lambda x: x.stat().st_mtime, reverse=True):
            stat = report_path.stat()
            report_info.append({
                "filename": report_path.name,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "download_url": f"/download-report/{report_path.name}"
            })

        return {
            "status": "success",
            "reports": report_info,
            "total_reports": len(report_info)
        }
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/cache/status")
async def get_cache_status():
    """Get district analyzer cache status"""
    try:
        if not district_analyzer_agent:
            return {"status": "error", "message": "District analyzer not initialized"}

        cache_status = district_analyzer_agent.get_cache_status()
        return {"status": "success", "cache": cache_status}
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/cache/refresh")
async def refresh_cache():
    """Force refresh district analyzer cache"""
    try:
        if not district_analyzer_agent:
            return {"status": "error", "message": "District analyzer not initialized"}

        logger.info("🔄 Force refreshing cache...")
        success = await district_analyzer_agent.force_update()

        if success:
            return {"status": "success", "message": "Cache refreshed successfully"}
        else:
            return {"status": "error", "message": "Failed to refresh cache"}
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint"""
    health_status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "llm": llm is not None,
            "search_tool": search_tool is not None,
            "property_retriever": property_retriever_agent is not None,
            "district_analyzer": district_analyzer_agent is not None,
            "pdf_generator": pdf_generator is not None,
            "report_service": report_service is not None
        }
    }

    all_services_ready = all(health_status["services"].values())
    health_status["all_ready"] = all_services_ready

    return health_status


@app.get("/features")
async def get_features():
    """Get available features and capabilities"""
    return {
        "features": {
            "property_analysis": {
                "description": "Analyze individual properties from unegui.mn URLs",
                "supported_sites": ["unegui.mn"],
                "capabilities": ["price analysis", "district comparison", "investment recommendations"]
            },
            "district_analysis": {
                "description": "Analyze and compare different districts in Ulaanbaatar",
                "capabilities": ["price comparison", "market trends", "investment opportunities"]
            },
            "market_research": {
                "description": "Internet search integration for current market data",
                "search_engine": "Tavily",
                "capabilities": ["real-time market data", "trend analysis", "news integration"]
            },
            "pdf_reports": {
                "description": "Generate comprehensive PDF reports",
                "types": ["property analysis", "district comparison", "comprehensive market analysis"],
                "languages": ["Mongolian"],
                "sections": ["basic info", "technical specs", "market analysis", "price comparison",
                             "internet research", "investment recommendations", "source information"]
            },
            "data_sources": {
                "real_estate_sites": ["unegui.mn"],
                "vectorstore": "FAISS",
                "search_integration": "Tavily",
                "caching": "7-day cache system"
            }
        },
        "supported_queries": {
            "property_urls": "Paste any unegui.mn property URL for detailed analysis",
            "district_queries": "Ask about specific districts or compare multiple districts",
            "general_questions": "General real estate questions with internet search",
            "report_requests": "Request PDF reports with 'тайлан үүсгэх' or similar phrases"
        }
    }


# Custom middleware for logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()

    logger.info(f"📊 {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    return response


if __name__ == "__main__":
    import uvicorn

    # Create necessary directories
    Path("reports").mkdir(exist_ok=True)
    Path("cache").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)

    logger.info("🚀 Starting Enhanced Real Estate Assistant Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)