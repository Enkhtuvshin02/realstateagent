import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from services.chat_service import ChatService
from services.initialization_service import InitializationService


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('real_estate_assistant.log')
    ]
)
logger = logging.getLogger(__name__)


app = FastAPI(title="Үл хөдлөх хөрөнгийн туслах", version="1.0.0")
templates = Jinja2Templates(directory="templates")


initialization_service = None
chat_service = None


@app.on_event("startup")
async def startup_event():
    global initialization_service, chat_service
    try:
        initialization_service = InitializationService()
        await initialization_service.initialize()

        chat_service = ChatService(
            llm=initialization_service.llm,
            search_tool=initialization_service.search_tool,
            property_retriever=initialization_service.property_retriever_agent,
            district_analyzer=initialization_service.district_analyzer_agent,
            pdf_generator=initialization_service.pdf_generator
        )


    except Exception as e:
        logger.error(f"Эхлүүлэхэд алдаа гарлаа: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    if initialization_service:
        await initialization_service.cleanup()


@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "version": "2.1.0"
    })


@app.post("/chat")
async def chat_endpoint(request: Request, user_message: str = Form(...)):
    logger.info(f"Мессеж хүлээн авсан: {user_message[:100]}...")

    if not chat_service:
        return {
            "response": "Системийг эхлүүлж байна. Түр хүлээнэ үү...",
            "offer_report": False,
            "status": "initializing"
        }

    try:
        start_time = datetime.now()
        result = await chat_service.process_message(user_message)
        processing_time = (datetime.now() - start_time).total_seconds()

        enhancements = []
        if result.get("cot_enhanced"):
            enhancements.append("Chain-of-Thought шинжилгээ")
        if result.get("report_generated"):
            enhancements.append("PDF тайлан")
        if result.get("search_performed"):
            enhancements.append("Интернэт хайлт")

        logger.info(f"Хариу үүсгэгдсэн: {processing_time:.2f}с")
        if enhancements:
            logger.info(f"Хэрэглэсэн сайжруулалт: {', '.join(enhancements)}")

        result.update({
            "processing_time": round(processing_time, 2),
            "enhancements_applied": enhancements,
            "timestamp": datetime.now().isoformat()
        })

        return result

    except Exception as e:
        logger.error(f"Чат боловсруулахад алдаа: {e}", exc_info=True)
        return {
            "response": "Уучлаарай, техникийн алдаа гарлаа. Дахин оролдоно уу.",
            "offer_report": False,
            "error": str(e),
            "status": "error"
        }


@app.get("/download-report/{filename}")
async def download_report(filename: str):
    try:
        file_path = Path("reports") / filename
        if not file_path.exists():
            logger.warning(f"Тайлангийн файл олдсонгүй: {filename}")
            return JSONResponse(
                status_code=404,
                content={"error": "Файл олдсонгүй", "filename": filename}
            )

        file_size = file_path.stat().st_size
        logger.info(f"Тайлан татаж байна: {filename} ({file_size} bytes)")

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
        logger.error(f"Татахад алдаа {filename}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Файл татахад алдаа: {str(e)}"}
        )


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = datetime.now()
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        return response
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"{request.method} {request.url.path} - Алдаа: {e} - {process_time:.3f}с")
        raise


if __name__ == "__main__":
    import uvicorn

    directories = ["reports", "cache", "templates", "static/fonts", "logs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
