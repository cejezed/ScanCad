"""
FastAPI backend for raster2cad vectorization service.
Provides REST endpoints for image analysis and DXF conversion.
"""

import io
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .llm_analyzer import analyze_image, mock_analyze
from .vectorize import process_plan
from .plan_contract import Plan
from .pdf_utils import pdf_to_images, is_pdf

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Raster2CAD",
    description="LLM-first architectural drawing vectorization engine",
    version="0.1.0",
)

# Enable CORS for web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (web UI)
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/")
async def root():
    """Serve web UI."""
    web_file = Path(__file__).parent.parent / "web" / "index.html"
    if web_file.exists():
        return FileResponse(web_file, media_type="text/html")
    return {"message": "Web UI not available"}


@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "raster2cad"}


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    dpi: int = Form(default=300),
    api_key: Optional[str] = Form(default=None),
) -> JSONResponse:
    """
    Analyze an architectural drawing image.

    Args:
        file: Image file (jpg, png) or PDF
        dpi: Resolution in DPI
        api_key: Optional Anthropic API key

    Returns:
        Plan JSON conforming to plan.schema.json
    """
    try:
        # Read file
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # Handle PDF
        if is_pdf(file_bytes):
            logger.info("PDF detected, converting first page to image")
            images = pdf_to_images(file_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(
                    status_code=400, detail="Failed to convert PDF"
                )
            file_bytes, _ = images[0]

        # Analyze
        logger.info(f"Analyzing image ({len(file_bytes)} bytes)")
        plan_dict = analyze_image(file_bytes, dpi=dpi, api_key=api_key)

        return JSONResponse(content=plan_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/vectorize")
async def vectorize(
    file: UploadFile = File(...),
    plan: Optional[UploadFile] = File(default=None),
    dpi: int = Form(default=300),
    api_key: Optional[str] = Form(default=None),
):
    """
    Vectorize an architectural drawing to DXF.

    If plan is not provided, analyzes the image first.

    Args:
        file: Image file (jpg, png) or PDF
        plan: Optional pre-generated plan.json
        dpi: Resolution in DPI
        api_key: Optional Anthropic API key

    Returns:
        DXF file
    """
    import shutil

    temp_dir = tempfile.mkdtemp()

    try:
        # Read image
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file")

        # Save image temporarily
        image_path = Path(temp_dir) / "input.jpg"
        if is_pdf(image_bytes):
            # Convert PDF to image
            logger.info("PDF detected, converting first page")
            images = pdf_to_images(image_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(
                    status_code=400, detail="Failed to convert PDF"
                )
            image_bytes, _ = images[0]

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Get or generate plan
        if plan:
            plan_bytes = await plan.read()
            plan_dict = json.loads(plan_bytes)
            logger.info("Using provided plan")
        else:
            logger.info("Analyzing image to generate plan")
            plan_dict = analyze_image(image_bytes, dpi=dpi, api_key=api_key)

        # Vectorize
        output_path = Path(temp_dir) / "output.dxf"
        logger.info(f"Vectorizing to {output_path}")
        process_plan(plan_dict, str(image_path), str(output_path), dpi=dpi)

        # Load DXF file into memory before cleanup
        with open(output_path, "rb") as f:
            dxf_content = f.read()

        # Return DXF file as streaming response
        return StreamingResponse(
            iter([dxf_content]),
            media_type="application/dxf",
            headers={"Content-Disposition": "attachment; filename=output.dxf"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vectorization failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Vectorization failed: {str(e)}"
        )
    finally:
        # Cleanup temp files
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")


@app.post("/plan")
async def get_plan(
    file: UploadFile = File(...),
    dpi: int = Form(default=300),
) -> JSONResponse:
    """
    Analyze image and return plan without vectorization.

    Args:
        file: Image file (jpg, png) or PDF
        dpi: Resolution in DPI

    Returns:
        Plan JSON
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        if is_pdf(file_bytes):
            images = pdf_to_images(file_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(
                    status_code=400, detail="Failed to convert PDF"
                )
            file_bytes, _ = images[0]

        plan_dict = analyze_image(file_bytes, dpi=dpi)
        return JSONResponse(content=plan_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Plan generation failed: {str(e)}"
        )


@app.get("/debug/config")
async def debug_config() -> JSONResponse:
    """Debug endpoint: Show loaded configuration."""
    import os

    return JSONResponse(
        content={
            "anthropic_key_loaded": bool(os.getenv("ANTHROPIC_API_KEY")),
            "openai_key_loaded": bool(os.getenv("OPENAI_API_KEY")),
            "dpi": os.getenv("DPI", "300"),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "env_file_path": str(Path(__file__).parent.parent / ".env"),
        }
    )


@app.post("/debug/analyze")
async def debug_analyze(
    file: UploadFile = File(...),
    dpi: int = Form(default=300),
) -> JSONResponse:
    """
    Debug endpoint: Analyze and return detailed feature info.
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        if is_pdf(file_bytes):
            images = pdf_to_images(file_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(status_code=400, detail="Failed to convert PDF")
            file_bytes, _ = images[0]

        plan_dict = analyze_image(file_bytes, dpi=dpi)

        # Return with feature count summary
        features = plan_dict.get("features", [])
        summary = {
            "total_features": len(features),
            "by_label": {},
            "features": features,
        }

        for feature in features:
            label = feature.get("label", "unknown")
            summary["by_label"][label] = summary["by_label"].get(label, 0) + 1

        return JSONResponse(content=summary)

    except Exception as e:
        logger.error(f"Debug analysis failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Debug analysis failed: {str(e)}"
        )


@app.get("/schema")
async def get_schema() -> JSONResponse:
    """Return the plan schema."""
    schema_path = Path(__file__).parent.parent / "plan.schema.json"
    if schema_path.exists():
        with open(schema_path, "r") as f:
            return JSONResponse(content=json.load(f))
    else:
        return JSONResponse(
            content={"error": "Schema not found"}, status_code=404
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
