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
from .vectorize import process_plan, vectorize_walls_from_plan
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
    Debug endpoint: Analyze and return detailed feature info with provider used.
    """
    import os
    import logging

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        if is_pdf(file_bytes):
            images = pdf_to_images(file_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(status_code=400, detail="Failed to convert PDF")
            file_bytes, _ = images[0]

        # Set logging to DEBUG to see what provider is used
        logging.getLogger("raster2cad.app.llm_analyzer").setLevel(logging.DEBUG)

        plan_dict = analyze_image(file_bytes, dpi=dpi)

        # Return with feature count summary and provider info
        features = plan_dict.get("features", [])
        summary = {
            "total_features": len(features),
            "by_label": {},
            "features": features,
            "debug_info": {
                "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
                "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
            },
        }

        for feature in features:
            label = feature.get("label", "unknown")
            summary["by_label"][label] = summary["by_label"].get(label, 0) + 1

        return JSONResponse(content=summary)

    except Exception as e:
        logger.error(f"Debug analysis failed: {e}", exc_info=True)
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


# Advanced Analysis Endpoints
@app.post("/overlay")
async def create_overlay(
    file: UploadFile = File(...),
    plan: UploadFile = File(...),
) -> FileResponse:
    """
    Create debug overlay visualization of detected features on image.

    Args:
        file: Original image file
        plan: Plan JSON file

    Returns:
        PNG overlay image
    """
    import shutil

    temp_dir = tempfile.mkdtemp()

    try:
        # Read image and plan
        image_bytes = await file.read()
        plan_bytes = await plan.read()

        if not image_bytes or not plan_bytes:
            raise HTTPException(status_code=400, detail="Empty files")

        # Save image
        image_path = Path(temp_dir) / "input.jpg"
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Parse plan
        plan_dict = json.loads(plan_bytes)

        # Create overlay
        from .overlay import draw_overlay_with_categories

        overlay_path = Path(temp_dir) / "overlay.png"
        success = draw_overlay_with_categories(str(image_path), plan_dict, str(overlay_path))

        if not success:
            raise HTTPException(status_code=500, detail="Failed to create overlay")

        return FileResponse(
            path=overlay_path,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=overlay.png"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Overlay creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Overlay failed: {str(e)}")
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@app.post("/analyze-rooms")
async def analyze_rooms(
    file: UploadFile = File(...),
    plan: UploadFile = File(...),
    dpi: int = Form(default=300),
) -> JSONResponse:
    """
    Analyze room configuration from plan.

    Args:
        file: Original image file
        plan: Plan JSON file
        dpi: Resolution in DPI

    Returns:
        Room analysis JSON with topology
    """
    import shutil
    import cv2

    temp_dir = tempfile.mkdtemp()

    try:
        # Read image and plan
        image_bytes = await file.read()
        plan_bytes = await plan.read()

        if not image_bytes or not plan_bytes:
            raise HTTPException(status_code=400, detail="Empty files")

        # Save image
        image_path = Path(temp_dir) / "input.jpg"
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Parse plan
        plan_dict = json.loads(plan_bytes)

        # Extract wall segments from plan
        wall_features = [f for f in plan_dict.get("features", []) if f.get("label") == "wall_structure"]
        wall_segments = []
        for feat in wall_features:
            box = feat.get("box", [])
            if len(box) == 4:
                x1, y1, x2, y2 = box
                wall_segments.append((x1, y1, x2, y2))

        if not wall_segments:
            return JSONResponse({
                "rooms": [],
                "statistics": {
                    "total_rooms": 0,
                    "message": "No wall segments found"
                }
            })

        # Detect rooms
        from .rooms import detect_rooms_from_segments, summarize_rooms
        px_to_mm = (1.0 / dpi) * 25.4  # DPI-based scaling

        rooms = detect_rooms_from_segments(wall_segments, px_to_mm=px_to_mm, plan=plan_dict)
        summary = summarize_rooms(rooms)

        # Build spatial graph
        from .plan_graph import build_room_graph, analyze_connectivity

        rooms_dict = [
            {
                "id": r.id,
                "name": r.name,
                "area_m2": r.area_m2,
                "centroid": r.centroid,
            }
            for r in rooms
        ]

        graph = build_room_graph(rooms_dict, plan_dict)
        connectivity = analyze_connectivity(graph)

        return JSONResponse({
            "rooms": rooms_dict,
            "statistics": summary,
            "connectivity": connectivity,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Room analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Room analysis failed: {str(e)}")
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@app.post("/export-graph")
async def export_graph(
    plan: UploadFile = File(...),
) -> JSONResponse:
    """
    Export spatial topology graph as JSON.

    Args:
        plan: Plan JSON file

    Returns:
        Graph structure with nodes, edges, and analysis
    """
    try:
        plan_bytes = await plan.read()

        if not plan_bytes:
            raise HTTPException(status_code=400, detail="Empty plan file")

        # Parse plan
        plan_dict = json.loads(plan_bytes)

        # Extract room data
        rooms_data = []
        text_features = [f for f in plan_dict.get("features", []) if f.get("label") == "text"]

        # Simple room creation from text labels
        for i, text_feat in enumerate(text_features):
            rooms_data.append({
                "id": f"room_{i:03d}",
                "name": text_feat.get("metadata", {}).get("content"),
                "area_m2": None,
            })

        if not rooms_data:
            rooms_data = [{"id": "room_000", "name": "Main Space", "area_m2": None}]

        # Build graph
        from .plan_graph import build_room_graph, analyze_connectivity

        graph = build_room_graph(rooms_data, plan_dict)
        connectivity = analyze_connectivity(graph)

        return JSONResponse({
            "graph": graph.to_dict(),
            "analysis": connectivity,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph export failed: {str(e)}")


# Human-in-the-loop editing endpoint
@app.post("/vectorize-with-plan")
async def vectorize_with_plan(
    file: UploadFile = File(...),
    plan_json: str = Form(...),
    dpi: int = Form(default=300),
):
    """
    Vectorize using a client-provided (edited) plan.json instead of LLM analysis.

    This endpoint enables human-in-the-loop workflows:
    1. User uploads image → /analyze → gets plan.json + viewer overlay
    2. User edits features in viewer (add, delete, change labels)
    3. User submits corrected plan → /vectorize-with-plan → gets DXF

    Args:
        file: Raster image (jpg, png) or PDF
        plan_json: Edited plan.json as form string (must be valid JSON)
        dpi: Resolution in DPI

    Returns:
        DXF file (MIME type: application/dxf)

    Raises:
        HTTPException: 400 if plan_json is invalid JSON
        HTTPException: 500 if vectorization fails
    """
    import shutil
    from .pdf_utils import is_pdf, pdf_to_images

    temp_dir = tempfile.mkdtemp()

    try:
        # Read image
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file")

        # Parse provided plan
        try:
            plan_dict = json.loads(plan_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON in plan_json: {str(e)}"
            )

        # Handle PDF
        if is_pdf(image_bytes):
            logger.info("PDF detected, converting first page to image")
            images = pdf_to_images(image_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(status_code=400, detail="Failed to convert PDF")
            image_bytes, _ = images[0]

        # Save image temporarily
        image_path = Path(temp_dir) / "input.jpg"
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Vectorize with provided plan (skip LLM analysis)
        output_path = Path(temp_dir) / "output.dxf"
        logger.info(f"Vectorizing with client-provided plan ({len(plan_dict.get('features', []))} features)")

        from .vectorize import Vectorizer

        vectorizer = Vectorizer(dpi=dpi)
        vectorizer.process_plan(plan_dict, str(image_path), str(output_path))

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
        logger.error(f"Vectorization with plan failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Vectorization failed: {str(e)}"
        )
    finally:
        # Cleanup temp files
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")


@app.post("/vectorize-walls")
async def vectorize_walls(
    file: UploadFile = File(...),
    dpi: int = Form(default=300),
    api_key: Optional[str] = Form(default=None),
):
    """
    Vectorize architectural drawing for walls only (hybrid LLM+CV mode).

    Uses LLM to identify wall region boundaries (coarse ROIs),
    then runs CV-based line detection within those ROIs to extract wall geometry.

    Args:
        file: Image file (jpg, png) or PDF
        dpi: Resolution in DPI
        api_key: Optional Anthropic API key

    Returns:
        DXF file containing only detected walls in layer "WALLS"
    """
    import shutil

    temp_dir = tempfile.mkdtemp()

    try:
        # Read image
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file")

        # Handle PDF
        if is_pdf(image_bytes):
            logger.info("PDF detected, converting first page to image")
            images = pdf_to_images(image_bytes, page_num=1, dpi=dpi)
            if not images:
                raise HTTPException(status_code=400, detail="Failed to convert PDF")
            image_bytes, _ = images[0]

        # Analyze in walls_only mode to get wall ROIs
        logger.info("Analyzing image in walls_only mode to identify wall regions")
        plan_dict = analyze_image(image_bytes, dpi=dpi, api_key=api_key, mode="walls_only")

        # Vectorize walls
        output_path = Path(temp_dir) / "walls.dxf"
        logger.info(f"Vectorizing walls to {output_path}")
        vectorize_walls_from_plan(image_bytes, plan_dict, str(output_path), dpi=dpi)

        # Load DXF file into memory before cleanup
        with open(output_path, "rb") as f:
            dxf_content = f.read()

        # Return DXF file as streaming response
        return StreamingResponse(
            iter([dxf_content]),
            media_type="application/dxf",
            headers={"Content-Disposition": "attachment; filename=walls.dxf"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Walls vectorization failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Walls vectorization failed: {str(e)}"
        )
    finally:
        # Cleanup temp files
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
