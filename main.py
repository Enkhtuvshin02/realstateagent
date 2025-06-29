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
        
        # Log the request for debugging purposes
        logger.info(f"Processing chat request with message: {user_message[:100]}...")
        
        # Check if the message is about a district
        district_request = False
        for district in ["хан-уул", "баянгол", "сүхбаатар", "чингэлтэй", "баянзүрх", "сонгинохайрхан"]:
            if district.lower() in user_message.lower():
                district_request = True
                logger.info(f"Detected district request for: {district}")
                break
        
        # Process the message
        result = await chat_service.process_message(user_message)
        processing_time = (datetime.now() - start_time).total_seconds()

        # Log the processing details
        enhancements = []
        if result.get("cot_enhanced"):
            enhancements.append("Chain-of-Thought шинжилгээ")
        if result.get("report_generated"):
            enhancements.append("PDF тайлан")
        if result.get("search_performed"):
            enhancements.append("Интернэт хайлт")
            
        # Check for error indicators in the response
        error_indicators = ["мэдээлэл олдсонгүй", "алдаа гарлаа", "бүртгэгдээгүй байна"]
        contains_error = any(indicator in result.get("response", "") for indicator in error_indicators)
        
        if contains_error and district_request:
            logger.warning(f"Response contains error indicators for district request: {user_message[:100]}")
            if not result.get("search_performed"):
                logger.warning("Vector retrieval likely failed but search fallback wasn't performed")
        
        # Log the result status
        status = result.get("status", "unknown")
        logger.info(f"Chat processing completed with status: {status} in {processing_time:.2f}s")
        if status == "error" or status == "partial_success":
            error_info = result.get("error_info", "No detailed error information")
            logger.error(f"Chat processing error details: {error_info}")
        
        if enhancements:
            logger.info(f"Хэрэглэсэн сайжруулалт: {', '.join(enhancements)}")

        # Update the result with additional metadata
        result.update({
            "processing_time": round(processing_time, 2),
            "enhancements_applied": enhancements,
            "timestamp": datetime.now().isoformat(),
            "vector_retrieval_attempted": district_request,
            "contains_error_indicators": contains_error
        })

        return result

    except Exception as e:
        logger.error(f"Чат боловсруулахад алдаа: {e}", exc_info=True)
        # Try to determine if this was a vector retrieval or search issue
        error_type = "unknown"
        if "vector" in str(e).lower() or "district" in str(e).lower():
            error_type = "vector_retrieval"
        elif "search" in str(e).lower() or "tavily" in str(e).lower():
            error_type = "search"
            
        return {
            "response": "Уучлаарай, техникийн алдаа гарлаа. Дахин оролдоно уу.",
            "offer_report": False,
            "error": str(e),
            "error_type": error_type,
            "status": "error"
        }


@app.get("/download-report/{filename}")
async def download_report(filename: str):
    try:
        # Validate filename to prevent path traversal attacks
        if ".." in filename or "/" in filename:
            logger.warning(f"Attempted path traversal in download: {filename}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid filename format", "filename": filename}
            )

        file_path = Path("reports") / filename
        if not file_path.exists():
            logger.warning(f"Report file not found: {filename}")
            return JSONResponse(
                status_code=404,
                content={"error": "File not found", "filename": filename}
            )

        file_size = file_path.stat().st_size
        logger.info(f"Downloading report: {filename} ({file_size} bytes)")

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
        logger.error(f"Error serving download {filename}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download file: {str(e)}"}
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
        port=8009,
        log_level="info"
    )
