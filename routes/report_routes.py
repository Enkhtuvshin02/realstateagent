# routes/routes.py
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/download/{filename}")
async def download_report(filename: str):
    """Download a generated PDF report"""
    try:
        file_path = Path("reports") / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Report file not found")

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/list")
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
                "download_url": f"/reports/download/{report_path.name}"
            })

        return {
            "status": "success",
            "reports": report_info,
            "total_reports": len(report_info)
        }
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")