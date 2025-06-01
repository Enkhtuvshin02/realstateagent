# main.py - Fixed WeasyPrint import error handling
import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Import our services and agents
from services.chat_service import ChatService
from services.initialization_service import InitializationService

# Load environment variables
load_dotenv()

# Configure logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('real_estate_assistant.log')
    ]
)
logger = logging.getLogger(__name__)

# Check WeasyPrint availability with proper error handling
WEASYPRINT_AVAILABLE = False
WEASYPRINT_ERROR = None

try:
    import weasyprint

    WEASYPRINT_AVAILABLE = True
    logger.info("✅ WeasyPrint available - Professional PDF generation enabled")
except ImportError as e:
    WEASYPRINT_ERROR = "WeasyPrint not installed"
    logger.warning("⚠️ WeasyPrint not available - Install with: pip install weasyprint")
    logger.warning(f"Import error: {e}")
except OSError as e:
    WEASYPRINT_ERROR = f"WeasyPrint system dependencies missing: {e}"
    logger.error("❌ WeasyPrint system dependencies missing!")
    logger.error(f"Error: {e}")
    logger.info("🔧 Fix on macOS:")
    logger.info(
        "  1. Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
    logger.info("  2. Install dependencies: brew install pango gdk-pixbuf libffi")
    logger.info("  3. Reinstall WeasyPrint: pip uninstall weasyprint && pip install weasyprint")
except Exception as e:
    WEASYPRINT_ERROR = f"Unexpected WeasyPrint error: {e}"
    logger.error(f"❌ Unexpected WeasyPrint error: {e}")

# --- FastAPI App Setup ---
app = FastAPI(
    title="Professional Real Estate Assistant",
    description="Enhanced Real Estate Assistant with PDF Reports and Chain-of-Thought Analysis",
    version="2.0.0"
)
templates = Jinja2Templates(directory="templates")

# Global variables
initialization_service = None
chat_service = None


@app.on_event("startup")
async def startup_event():
    """Initialize everything on startup with better error handling"""
    global initialization_service, chat_service

    logger.info("🚀 Starting Professional Real Estate Assistant v2.0...")

    if WEASYPRINT_AVAILABLE:
        logger.info("📄 Professional PDF generation with WeasyPrint enabled")
        logger.info("✨ Features: HTML/CSS styling, professional layout, excellent structure")
    else:
        logger.info("📄 Using fallback PDF generation (ReportLab)")
        if WEASYPRINT_ERROR:
            logger.warning(f"WeasyPrint issue: {WEASYPRINT_ERROR}")
        logger.info("💡 For professional PDFs, install WeasyPrint dependencies:")
        logger.info("  brew install pango gdk-pixbuf libffi")
        logger.info("  pip install weasyprint")

    try:
        # Initialize all services
        initialization_service = InitializationService()
        await initialization_service.initialize()

        # Create chat service with all components
        chat_service = ChatService(
            llm=initialization_service.llm,
            search_tool=initialization_service.search_tool,
            property_retriever=initialization_service.property_retriever_agent,
            district_analyzer=initialization_service.district_analyzer_agent,
            pdf_generator=initialization_service.pdf_generator
        )

        logger.info("✅ All components initialized successfully!")
        logger.info("🧠 Chain-of-Thought reasoning is active!")

        if WEASYPRINT_AVAILABLE:
            logger.info("📋 Professional PDF reports with excellent structure enabled!")
        else:
            logger.info("📋 Basic PDF reports enabled (upgrade to WeasyPrint for professional quality)")

        # Log system capabilities
        logger.info("🔍 Available features:")
        logger.info("  • Property URL analysis with unegui.mn integration")
        logger.info("  • District comparison across 9 Ulaanbaatar districts")
        logger.info("  • Real-time market research with internet search")
        logger.info("  • Chain-of-Thought enhanced reasoning")
        logger.info(f"  • {'Professional' if WEASYPRINT_AVAILABLE else 'Basic'} PDF report generation")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        logger.error("🔧 Please check your environment variables and dependencies")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if initialization_service:
        await initialization_service.cleanup()
        logger.info("🧹 Services cleaned up successfully")


@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    """Main chat page with improved UI"""
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "weasyprint_available": WEASYPRINT_AVAILABLE,
        "weasyprint_error": WEASYPRINT_ERROR,
        "version": "2.0.0"
    })


@app.post("/chat")
async def chat_endpoint(request: Request, user_message: str = Form(...)):
    """Enhanced chat endpoint with PDF generation"""
    logger.info(f"📝 Chat message received: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")

    # Check if services are ready
    if not chat_service:
        return {
            "response": "🔧 Системийг эхлүүлж байна. Түр хүлээнэ үү...",
            "offer_report": False,
            "status": "initializing"
        }

    try:
        # Process message with all enhancements
        start_time = datetime.now()
        result = await chat_service.process_message(user_message)
        processing_time = (datetime.now() - start_time).total_seconds()

        # Log enhancements and performance
        enhancements = []
        if result.get("cot_enhanced"):
            enhancements.append("Chain-of-Thought reasoning")
        if result.get("report_generated"):
            enhancements.append(f"{'Professional' if WEASYPRINT_AVAILABLE else 'Basic'} PDF report")
        if result.get("search_performed"):
            enhancements.append("Internet search")

        logger.info(f"✅ Response generated in {processing_time:.2f}s")
        if enhancements:
            logger.info(f"🚀 Applied enhancements: {', '.join(enhancements)}")

        # Add metadata to response
        result.update({
            "processing_time": round(processing_time, 2),
            "enhancements_applied": enhancements,
            "weasyprint_available": WEASYPRINT_AVAILABLE,
            "weasyprint_error": WEASYPRINT_ERROR,
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
    """Download PDF report with improved error handling"""
    try:
        file_path = Path("reports") / filename
        if not file_path.exists():
            logger.warning(f"📄 Report file not found: {filename}")
            return JSONResponse(
                status_code=404,
                content={"error": "Файл олдсонгүй", "filename": filename}
            )

        # Log download
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
        logger.error(f"📄 Download error for {filename}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Файл татахад алдаа: {str(e)}"}
        )


@app.get("/health")
async def health():
    """Enhanced health check endpoint with WeasyPrint status"""
    health_status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "services": {},
        "pdf_capabilities": {
            "engine": "WeasyPrint" if WEASYPRINT_AVAILABLE else "ReportLab",
            "professional_styling": WEASYPRINT_AVAILABLE,
            "weasyprint_available": WEASYPRINT_AVAILABLE,
            "weasyprint_error": WEASYPRINT_ERROR
        }
    }

    if initialization_service:
        health_status["services"] = {
            "llm": initialization_service.llm is not None,
            "search_tool": initialization_service.search_tool is not None,
            "property_retriever": initialization_service.property_retriever_agent is not None,
            "district_analyzer": initialization_service.district_analyzer_agent is not None,
            "pdf_generator": initialization_service.pdf_generator is not None,
            "chat_service": chat_service is not None,
            "chain_of_thought": chat_service.cot_agent is not None if chat_service else False,
            "weasyprint_available": WEASYPRINT_AVAILABLE
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


@app.get("/weasyprint/status")
async def get_weasyprint_status():
    """Detailed WeasyPrint status and installation help"""
    return {
        "available": WEASYPRINT_AVAILABLE,
        "error": WEASYPRINT_ERROR,
        "status": "success" if WEASYPRINT_AVAILABLE else "error",
        "installation_guide": {
            "macos": [
                "Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"",
                "Install dependencies: brew install pango gdk-pixbuf libffi",
                "Reinstall WeasyPrint: pip uninstall weasyprint && pip install weasyprint"
            ],
            "ubuntu": [
                "sudo apt-get install build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info",
                "pip install weasyprint"
            ],
            "windows": [
                "Download GTK3 runtime from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases",
                "Install GTK3 runtime",
                "pip install weasyprint"
            ]
        },
        "benefits_when_available": [
            "Professional HTML/CSS styling",
            "Excellent typography and readability",
            "Structured layout with visual hierarchy",
            "Print-optimized formatting",
            "Custom branding support"
        ],
        "current_capabilities": [
            "Basic PDF generation with ReportLab" if not WEASYPRINT_AVAILABLE else "Professional PDF generation with WeasyPrint",
            "Chain-of-Thought analysis",
            "Property and district analysis",
            "Market research integration"
        ]
    }


@app.get("/pdf/status")
async def get_pdf_status():
    """PDF generation status and capabilities"""
    try:
        # Count existing reports
        reports_dir = Path("reports")
        report_count = len(list(reports_dir.glob("*.pdf"))) if reports_dir.exists() else 0

        return {
            "status": "success",
            "pdf_engine": "WeasyPrint" if WEASYPRINT_AVAILABLE else "ReportLab",
            "professional_quality": WEASYPRINT_AVAILABLE,
            "weasyprint_available": WEASYPRINT_AVAILABLE,
            "weasyprint_error": WEASYPRINT_ERROR,
            "capabilities": {
                "basic_pdf_generation": True,
                "html_css_support": WEASYPRINT_AVAILABLE,
                "professional_typography": WEASYPRINT_AVAILABLE,
                "structured_layout": WEASYPRINT_AVAILABLE,
                "visual_hierarchy": WEASYPRINT_AVAILABLE,
                "unicode_support": True,
                "mongolian_fonts": True
            },
            "report_statistics": {
                "total_reports_generated": report_count,
                "reports_directory": str(reports_dir)
            },
            "upgrade_instructions": {
                "for_professional_pdfs": "Install WeasyPrint dependencies",
                "macos_command": "brew install pango gdk-pixbuf libffi",
                "install_command": "pip install weasyprint"
            } if not WEASYPRINT_AVAILABLE else {
                "status": "Professional PDF generation active"
            }
        }
    except Exception as e:
        logger.error(f"📄 Error getting PDF status: {e}")
        return {"status": "error", "message": str(e)}


# Custom middleware for enhanced logging
@app.middleware("http")
async def enhanced_logging_middleware(request: Request, call_next):
    start_time = datetime.now()

    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()

        # Add performance headers
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        response.headers["X-PDF-Engine"] = "WeasyPrint" if WEASYPRINT_AVAILABLE else "ReportLab"
        response.headers["X-WeasyPrint-Available"] = str(WEASYPRINT_AVAILABLE)

        return response

    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ {request.method} {request.url.path} - Error: {e} - {process_time:.3f}s")
        raise


if __name__ == "__main__":
    import uvicorn

    # Create necessary directories
    directories = ["reports", "cache", "templates", "pdf_templates", "logs"]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

    logger.info("🚀 Starting Professional Real Estate Assistant Server v2.0...")
    logger.info("🧠 Enhanced Chain-of-Thought reasoning active!")

    if WEASYPRINT_AVAILABLE:
        logger.info("📋 Professional PDF generation with WeasyPrint enabled!")
        logger.info("✨ Features: Excellent structure, professional typography, visual hierarchy")
    else:
        logger.info("📋 Basic PDF generation active (ReportLab fallback)")
        if WEASYPRINT_ERROR:
            logger.warning(f"💡 WeasyPrint issue: {WEASYPRINT_ERROR}")
        logger.info("🔧 To enable professional PDFs:")
        logger.info("  1. brew install pango gdk-pixbuf libffi")
        logger.info("  2. pip install weasyprint")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )