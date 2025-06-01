# main.py - ReportLab PDF үүсгэх шинэчлэлтэй
import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Сервис болон агентуудыг импортлох
from services.chat_service import ChatService
from services.initialization_service import InitializationService # ReportLab генераторыг эхлүүлнэ

# Орчны хувьсагчдыг ачаалах
load_dotenv()

# Логийг илүү сайн форматтай тохируулах
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('real_estate_assistant.log')
    ]
)
logger = logging.getLogger(__name__)

# --- FastAPI Апп Тохиргоо ---
app = FastAPI(
    title="Professional Real Estate Assistant",
    description="Enhanced Real Estate Assistant with PDF Reports (using ReportLab) and Chain-of-Thought Analysis",
    version="2.1.0" # Хувилбарын шинэчлэл
)
templates = Jinja2Templates(directory="templates")

# Глобаль хувьсагчид
initialization_service = None
chat_service = None


@app.on_event("startup")
async def startup_event():
    """# Эхлэхэд бүх зүйлийг илүү сайн алдааны мэдээлэлтэй эхлүүлэх"""
    global initialization_service, chat_service

    logger.info("🚀 Starting Professional Real Estate Assistant v2.1 (with ReportLab)...")
    logger.info("📄 PDF generation will use ReportLab.")
    logger.info("💡 Ensure a Mongolian-supporting TTF font is in static/fonts/ and configured in xhtml2pdf_generator.py for proper text rendering.")

    try:
        # Initialize all services
        initialization_service = InitializationService()
        await initialization_service.initialize() # This will initialize ReportLabPDFGenerator

        # Create chat service with all components
        chat_service = ChatService(
            llm=initialization_service.llm,
            search_tool=initialization_service.search_tool,
            property_retriever=initialization_service.property_retriever_agent,
            district_analyzer=initialization_service.district_analyzer_agent,
            pdf_generator=initialization_service.pdf_generator # This is now the ReportLab one
        )

        logger.info("✅ All components initialized successfully!")
        logger.info("🧠 Chain-of-Thought reasoning is active!")
        logger.info("📋 PDF reports using ReportLab are enabled!")

        # Log system capabilities
        logger.info("🔍 Available features:")
        logger.info("  • Property URL analysis with unegui.mn integration")
        logger.info("  • District comparison across 9 Ulaanbaatar districts")
        logger.info("  • Real-time market research with internet search")
        logger.info("  • Chain-of-Thought enhanced reasoning")
        logger.info("  • PDF report generation (ReportLab)")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}", exc_info=True) # Added exc_info for more details
        logger.error("🔧 Please check your environment variables and dependencies (including ReportLab and required fonts)")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """# Унтраахад цэвэрлэх"""
    if initialization_service:
        await initialization_service.cleanup()
        logger.info("🧹 Services cleaned up successfully")


@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    """# Сайжруулсан интерфэйстэй үндсэн чат хуудас"""
    # Removed WeasyPrint specific variables from template context
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "pdf_engine_name": "ReportLab", # Indicate ReportLab is used
        "version": "2.1.0"
    })


@app.post("/chat")
async def chat_endpoint(request: Request, user_message: str = Form(...)):
    """# PDF үүсгэх боломжтой сайжруулсан чат цэг"""
    logger.info(f"📝 Chat message received: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")

    if not chat_service:
        return {
            "response": "🔧 Системийг эхлүүлж байна. Түр хүлээнэ үү...",
            "offer_report": False,
            "status": "initializing"
        }

    try:
        start_time = datetime.now()
        result = await chat_service.process_message(user_message)
        processing_time = (datetime.now() - start_time).total_seconds()

        enhancements = []
        if result.get("cot_enhanced"):
            enhancements.append("Chain-of-Thought reasoning")
        if result.get("report_generated"):
            enhancements.append("ReportLab PDF report") # Updated
        if result.get("search_performed"):
            enhancements.append("Internet search")

        logger.info(f"✅ Response generated in {processing_time:.2f}s")
        if enhancements:
            logger.info(f"🚀 Applied enhancements: {', '.join(enhancements)}")

        result.update({
            "processing_time": round(processing_time, 2),
            "enhancements_applied": enhancements,
            "pdf_engine_name": "ReportLab", # Updated
            "timestamp": datetime.now().isoformat()
        })

        return result

    except Exception as e:
        logger.error(f"❌ Chat processing error: {e}", exc_info=True)
        return {
            "response": "🔧 Уучлаарай, техникийн алдаа гарлаа. Дахин оролдоно уу.",
            "offer_report": False,
            "error": str(e),
            "status": "error"
        }


@app.get("/download-report/{filename}")
async def download_report(filename: str):
    """# Сайжруулсан алдааны мэдээлэлтэй PDF тайлан татах"""
    try:
        file_path = Path("reports") / filename
        if not file_path.exists():
            logger.warning(f"📄 Report file not found: {filename}")
            return JSONResponse(
                status_code=404,
                content={"error": "Файл олдсонгүй", "filename": filename}
            )

        file_size = file_path.stat().st_size
        logger.info(f"📥 Downloading report: {filename} ({file_size} bytes)")

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"📄 Download error for {filename}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Файл татахад алдаа: {str(e)}"}
        )


@app.get("/health")
async def health():
    """# Сайжруулсан эрүүл байдлыг шалгах цэг"""
    health_status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
        "services": {},
        "pdf_capabilities": {
            "engine": "ReportLab", # Updated
            "status": "Active. Ensure fonts are correctly configured for full language support."
        }
    }

    if initialization_service:
        health_status["services"] = {
            "llm": initialization_service.llm is not None,
            "search_tool": initialization_service.search_tool is not None,
            "property_retriever": initialization_service.property_retriever_agent is not None,
            "district_analyzer": initialization_service.district_analyzer_agent is not None,
            "pdf_generator": initialization_service.pdf_generator is not None, # Checks ReportLab generator
            "chat_service": chat_service is not None,
            "chain_of_thought": chat_service.cot_agent is not None if chat_service else False,
        }
    else:
        health_status["services"] = {
            "initialization_service": False
        }

    all_services_ready = all(health_status["services"].values())
    health_status["all_ready"] = all_services_ready

    if not all_services_ready:
        health_status["status"] = "degraded"

    return health_status

# WeasyPrint-д зориулсан статус цэгүүдийг хассан (/weasyprint/status, /pdf/status)
# учир нь тэд WeasyPrint-д маш их төвлөрсөн байсан. Шаардлагатай бол ReportLab-д зориулсан шинэ /pdf/status үүсгэж болно.

@app.middleware("http")
async def enhanced_logging_middleware(request: Request, call_next):
    start_time = datetime.now()
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        response.headers["X-PDF-Engine"] = "ReportLab" # Updated
        return response
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ {request.method} {request.url.path} - Error: {e} - {process_time:.3f}s", exc_info=True)
        raise


if __name__ == "__main__":
    import uvicorn

    directories = ["reports", "cache", "templates", "static/fonts", "logs"] # static/fonts нэмсэн
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True) # parents=True нэмсэн

    logger.info("🚀 Starting Professional Real Estate Assistant Server v2.1 (ReportLab)...")
    logger.info("🧠 Enhanced Chain-of-Thought reasoning active!")
    logger.info("📋 PDF generation with ReportLab enabled!")
    logger.info("💡 Ensure a Mongolian TTF font is in static/fonts/ and correctly configured in xhtml2pdf_generator.py.")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
