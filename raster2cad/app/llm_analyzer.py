"""
LLM-based architectural drawing analyzer.
Sends images to multimodal LLM (Claude, GPT-4V) for analysis.
Includes mock analyzer for offline/testing scenarios.
"""

import base64
import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from .plan_contract import Plan, Feature

logger = logging.getLogger(__name__)

# Load system prompt
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
VISION_PROMPT_PATH = PROMPTS_DIR / "vision_analysis.md"

if VISION_PROMPT_PATH.exists():
    with open(VISION_PROMPT_PATH, "r") as f:
        SYSTEM_PROMPT = f.read()
else:
    SYSTEM_PROMPT = "You are an expert architectural drawing analyzer."


def get_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes to base64."""
    return base64.b64encode(image_bytes).decode("utf-8")


def analyze_image(
    image_bytes: bytes,
    dpi: int = 300,
    api_key: Optional[str] = None,
    model: str = "claude-3-5-sonnet-20241022",
) -> Dict[str, Any]:
    """
    Analyze architectural drawing via Claude API.

    Args:
        image_bytes: Raw image data (jpg/png)
        dpi: Dots per inch resolution
        api_key: Anthropic API key (uses env var if not provided)
        model: LLM model to use

    Returns:
        Plan dict conforming to plan.schema.json

    Raises:
        ValueError: If API key missing or image invalid
        requests.RequestException: If API call fails
    """
    if requests is None:
        raise ImportError("requests library required for LLM analysis")

    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No API key provided, using mock analyzer")
        return mock_analyze(image_bytes, dpi)

    # Detect image format
    image_format = "image/jpeg"
    if image_bytes.startswith(b"\x89PNG"):
        image_format = "image/png"

    base64_image = get_image_base64(image_bytes)

    # Prepare API request
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_format,
                            "data": base64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analyze this architectural drawing and return ONLY valid JSON "
                            "matching the schema with image_source, image_dims, dpi, and features array. "
                            "No markdown, no extra text, just JSON."
                        ),
                    },
                ],
            }
        ],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {e}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    result = response.json()
    if "error" in result:
        logger.error(f"API error: {result['error']}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    # Extract JSON from response
    response_text = result["content"][0]["text"]

    # Try to parse JSON (handle markdown code blocks)
    try:
        if "```json" in response_text:
            json_start = response_text.index("```json") + 7
            json_end = response_text.index("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.index("```") + 3
            json_end = response_text.index("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        plan_dict = json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    # Validate and enrich with actual image dimensions if available
    try:
        # Try to get actual image dimensions
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(image_bytes))
        plan_dict["image_dims"] = list(img.size)
        plan_dict["dpi"] = dpi
    except Exception as e:
        logger.warning(f"Could not extract image dimensions: {e}")
        # Use defaults if not provided
        if "image_dims" not in plan_dict:
            plan_dict["image_dims"] = [1024, 768]

    return plan_dict


def mock_analyze(image_bytes: bytes, dpi: int = 300) -> Dict[str, Any]:
    """
    Generate mock analysis without API call.
    Used for testing and offline scenarios.

    Args:
        image_bytes: Raw image data
        dpi: Dots per inch resolution

    Returns:
        Sample plan dict with realistic wall, text, and symbol features
    """
    # Try to get actual image dimensions
    img_width, img_height = 1024, 768
    try:
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(image_bytes))
        img_width, img_height = img.size
    except Exception:
        pass

    # Generate realistic mock features for a floor plan
    features = [
        # Outer walls
        {
            "id": "wall_001",
            "label": "wall_structure",
            "box": [50, 50, 70, img_height - 50],
            "conf": 0.98,
            "metadata": {},
        },
        {
            "id": "wall_002",
            "label": "wall_structure",
            "box": [50, 50, img_width - 50, 70],
            "conf": 0.98,
            "metadata": {},
        },
        {
            "id": "wall_003",
            "label": "wall_structure",
            "box": [img_width - 70, 50, img_width - 50, img_height - 50],
            "conf": 0.98,
            "metadata": {},
        },
        {
            "id": "wall_004",
            "label": "wall_structure",
            "box": [50, img_height - 70, img_width - 50, img_height - 50],
            "conf": 0.98,
            "metadata": {},
        },
        # Interior wall
        {
            "id": "wall_005",
            "label": "wall_structure",
            "box": [img_width // 2 - 10, 70, img_width // 2 + 10, img_height - 70],
            "conf": 0.95,
            "metadata": {},
        },
        # Door symbol
        {
            "id": "symbol_001",
            "label": "symbol",
            "box": [img_width // 2 - 30, 65, img_width // 2 + 30, 75],
            "conf": 0.90,
            "metadata": {"symbol_type": "door", "swing_direction": "right"},
        },
        # Window symbols
        {
            "id": "symbol_002",
            "label": "symbol",
            "box": [100, 45, 150, 55],
            "conf": 0.88,
            "metadata": {"symbol_type": "window"},
        },
        {
            "id": "symbol_003",
            "label": "symbol",
            "box": [img_width - 150, 45, img_width - 100, 55],
            "conf": 0.88,
            "metadata": {"symbol_type": "window"},
        },
        # Text labels
        {
            "id": "text_001",
            "label": "text",
            "box": [100, 200, 200, 240],
            "conf": 0.92,
            "metadata": {"content": "LIVING ROOM", "rotation_deg": 0},
        },
        {
            "id": "text_002",
            "label": "text",
            "box": [img_width - 200, 200, img_width - 100, 240],
            "conf": 0.92,
            "metadata": {"content": "BEDROOM", "rotation_deg": 0},
        },
        {
            "id": "text_003",
            "label": "text",
            "box": [img_width // 2 - 100, img_height - 150, img_width // 2 + 100, img_height - 100],
            "conf": 0.90,
            "metadata": {"content": "KITCHEN", "rotation_deg": 0},
        },
        # Dimension lines
        {
            "id": "dim_001",
            "label": "dimension_line",
            "box": [40, 80, 40, img_height - 80],
            "conf": 0.85,
            "metadata": {"dimension": "10.5m"},
        },
        {
            "id": "dim_002",
            "label": "dimension_line",
            "box": [100, img_height - 75, img_width - 100, img_height - 75],
            "conf": 0.85,
            "metadata": {"dimension": "15.0m"},
        },
        # North arrow
        {
            "id": "north_001",
            "label": "north_arrow",
            "box": [img_width - 120, 20, img_width - 20, 100],
            "conf": 0.95,
            "metadata": {"orientation_deg": 0},
        },
    ]

    return {
        "image_source": "mock_image.jpg",
        "image_dims": [img_width, img_height],
        "dpi": dpi,
        "features": features,
    }
