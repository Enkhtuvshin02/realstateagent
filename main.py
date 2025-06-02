import os
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from services.chat_service import ChatService
from services.initialization_service import InitializationService

# Орчны хувьсагчдыг ачаалах
load_dotenv()

# Лог тохиргоо
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('real_estate_assistant.log')
    ]
)
logger = logging.getLogger(__name__)

# FastAPI тохиргоо
app = FastAPI(title="Үл хөдлөх хөрөнгийн туслах", version="2.1.0")
templates = Jinja2Templates(directory="templates")

# Глобаль хувьсагчид
initialization_service = None
chat_service = None


@app.on_event("startup")
async def startup_event():
    """Системийг эхлүүлэх"""
    global initialization_service, chat_service

    logger.info("🚀 Үл хөдлөх хөрөнгийн туслах серверийг эхлүүлж байна...")
    logger.info("🧠 Chain-of-Thought шинжилгээ идэвхтэй!")
    logger.info("📋 PDF тайлан үүсгэх боломжтой!")



    try:
        # Бүх үйлчилгээг эхлүүлэх
        initialization_service = InitializationService()
        await initialization_service.initialize()

        # Чат үйлчилгээг үүсгэх
        chat_service = ChatService(
            llm=initialization_service.llm,
            search_tool=initialization_service.search_tool,
            property_retriever=initialization_service.property_retriever_agent,
            district_analyzer=initialization_service.district_analyzer_agent,
            pdf_generator=initialization_service.pdf_generator
        )

        logger.info("✅ Бүх бүрэлдэхүүн амжилттай эхэлсэн!")
        logger.info("🧠 Chain-of-Thought үйл ажиллагаатай!")
        logger.info("📋 PDF тайлан үүсгэх боломжтой!")

        # Онцлогуудыг лог хийх
        logger.info("🔍 Боломжтой функцууд:")
        logger.info("  • Unegui.mn орон сууцны шинжилгээ")
        logger.info("  • 9 дүүргийн харьцуулалт")
        logger.info("  • Интернэт хайлт")
        logger.info("  • CoT сэтгэлгээний шинжилгээ")
        logger.info("  • PDF тайлан үүсгэх")

    except Exception as e:
        logger.error(f"❌ Эхлүүлэхэд алдаа гарлаа: {e}", exc_info=True)
        logger.error("🔧 Орчны хувьсагч болон хамаарлыг шалгана уу")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Системийг хаах"""
    if initialization_service:
        await initialization_service.cleanup()
        logger.info("🧹 Үйлчилгээнүүд амжилттай хаагдсан")


@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    """Үндсэн чат хуудас"""
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "version": "2.1.0"
    })


@app.post("/chat")
async def chat_endpoint(request: Request, user_message: str = Form(...)):
    """Чат эндпойнт"""
    logger.info(f"📝 Мессеж хүлээн авсан: {user_message[:100]}...")

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

        # Хэрэглэсэн сайжруулалтуудыг тэмдэглэх
        enhancements = []
        if result.get("cot_enhanced"):
            enhancements.append("Chain-of-Thought шинжилгээ")
        if result.get("report_generated"):
            enhancements.append("PDF тайлан")
        if result.get("search_performed"):
            enhancements.append("Интернэт хайлт")

        logger.info(f"✅ Хариу үүсгэгдсэн: {processing_time:.2f}с")
        if enhancements:
            logger.info(f"🚀 Хэрэглэсэн сайжруулалт: {', '.join(enhancements)}")

        result.update({
            "processing_time": round(processing_time, 2),
            "enhancements_applied": enhancements,
            "timestamp": datetime.now().isoformat()
        })

        return result

    except Exception as e:
        logger.error(f"❌ Чат боловсруулахад алдаа: {e}", exc_info=True)
        return {
            "response": "🔧 Уучлаарай, техникийн алдаа гарлаа. Дахин оролдоно уу.",
            "offer_report": False,
            "error": str(e),
            "status": "error"
        }


@app.get("/download-report/{filename}")
async def download_report(filename: str):
    """PDF тайлан татах"""
    try:
        file_path = Path("reports") / filename
        if not file_path.exists():
            logger.warning(f"📄 Тайлан файл олдсонгүй: {filename}")
            return JSONResponse(
                status_code=404,
                content={"error": "Файл олдсонгүй", "filename": filename}
            )

        file_size = file_path.stat().st_size
        logger.info(f"📥 Тайлан татаж байна: {filename} ({file_size} bytes)")

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
        logger.error(f"📄 Татахад алдаа {filename}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Файл татахад алдаа: {str(e)}"}
        )


@app.get("/health")
async def health():
    """Эрүүл мэндийн статус"""
    health_status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
        "services": {},
        "pdf_engine": "ReportLab"
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
        }
    else:
        health_status["services"] = {"initialization_service": False}

    all_ready = all(health_status["services"].values())
    health_status["all_ready"] = all_ready

    if not all_ready:
        health_status["status"] = "degraded"

    return health_status


@app.get("/cache/status")
async def cache_status():
    """Кэшийн статус"""
    try:
        if not initialization_service or not initialization_service.district_analyzer_agent:
            return {"status": "error", "message": "District analyzer олдсонгүй"}

        cache_info = initialization_service.district_analyzer_agent.get_cache_status()
        return {"status": "success", "cache": cache_info}

    except Exception as e:
        logger.error(f"Кэш статус шалгахад алдаа: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/cache/refresh")
async def refresh_cache():
    """Кэш шинэчлэх"""
    try:
        if not initialization_service or not initialization_service.district_analyzer_agent:
            return {"status": "error", "message": "District analyzer олдсонгүй"}

        await initialization_service.district_analyzer_agent._update_with_realtime_data()
        return {"status": "success", "message": "Кэш амжилттай шинэчлэгдсэн"}

    except Exception as e:
        logger.error(f"Кэш шинэчлэхэд алдаа: {e}")
        return {"status": "error", "message": str(e)}


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Лог хийх middleware"""
    start_time = datetime.now()
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        return response
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ {request.method} {request.url.path} - Алдаа: {e} - {process_time:.3f}с")
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
