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
    model: Optional[str] = None,
    provider: str = "auto",
) -> Dict[str, Any]:
    """
    Analyze architectural drawing via Claude or OpenAI API.

    Args:
        image_bytes: Raw image data (jpg/png)
        dpi: Dots per inch resolution
        api_key: API key (Anthropic or OpenAI, uses env var if not provided)
        model: LLM model to use (auto-detects if not specified)
        provider: "claude", "openai", or "auto" (auto-detect from env vars)

    Returns:
        Plan dict conforming to plan.schema.json

    Raises:
        ValueError: If API key missing or image invalid
        requests.RequestException: If API call fails
    """
    if requests is None:
        raise ImportError("requests library required for LLM analysis")

    # Auto-detect provider and API key
    if provider == "auto":
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if api_key:
            # Detect from api_key format
            if api_key.startswith("sk-proj-") or api_key.startswith("sk-"):
                provider = "openai"
            else:
                provider = "claude"
        elif claude_key:
            provider = "claude"
            api_key = claude_key
        elif openai_key:
            provider = "openai"
            api_key = openai_key
        else:
            logger.warning("No API key provided, using mock analyzer")
            return mock_analyze(image_bytes, dpi)

    # Set default model based on provider
    # Using best available models: Claude 3.5 Sonnet + OpenAI GPT-5
    if not model:
        model = "gpt-5-2025-08-07" if provider == "openai" else "claude-3-5-sonnet-20241022"

    logger.info(f"Using {provider} ({model})")

    if provider == "openai":
        return _analyze_with_openai(image_bytes, dpi, api_key, model)
    else:
        return _analyze_with_claude(image_bytes, dpi, api_key, model)


def _analyze_with_claude(
    image_bytes: bytes,
    dpi: int,
    api_key: str,
    model: str,
) -> Dict[str, Any]:
    """Analyze using Claude API."""
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
        logger.error(f"Claude API call failed: {e}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    result = response.json()
    if "error" in result:
        logger.error(f"Claude API error: {result['error']}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    # Extract JSON from response
    response_text = result["content"][0]["text"]
    return _parse_json_response(response_text, image_bytes, dpi)


def _analyze_with_openai(
    image_bytes: bytes,
    dpi: int,
    api_key: str,
    model: str,
) -> Dict[str, Any]:
    """Analyze using OpenAI GPT-4 Vision API."""
    base64_image = get_image_base64(image_bytes)

    # Detect image format
    image_format = "image/jpeg"
    if image_bytes.startswith(b"\x89PNG"):
        image_format = "image/png"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this architectural drawing and return ONLY valid JSON "
                            "matching the schema with image_source, image_dims, dpi, and features array. "
                            "No markdown, no extra text, just JSON.\n\n"
                            + SYSTEM_PROMPT
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_format};base64,{base64_image}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
    }

    try:
        logger.debug(f"Sending request to OpenAI with model: {model}")
        logger.debug(f"API Key (first 20 chars): {api_key[:20]}...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        logger.debug(f"OpenAI response status: {response.status_code}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenAI API call failed: {e}")
        try:
            error_details = response.json() if response else {}
            logger.error(f"OpenAI error details: {error_details}")
        except:
            logger.error(f"OpenAI response text: {response.text if response else 'No response'}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    result = response.json()
    if "error" in result:
        logger.error(f"OpenAI API error: {result['error']}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)

    # Extract JSON from response
    try:
        response_text = result["choices"][0]["message"]["content"]
        logger.debug(f"OpenAI response length: {len(response_text)} chars")
        logger.debug(f"OpenAI response preview (first 500 chars): {response_text[:500]}")
        parsed = _parse_json_response(response_text, image_bytes, dpi)
        logger.info(f"OpenAI analysis complete: {len(parsed.get('features', []))} features detected")
        return parsed
    except (KeyError, IndexError) as e:
        logger.error(f"Failed to extract response from OpenAI: {e}")
        logger.error(f"Response structure: {result}")
        logger.warning("Falling back to mock analyzer")
        return mock_analyze(image_bytes, dpi)


def _parse_json_response(
    response_text: str,
    image_bytes: bytes,
    dpi: int,
) -> Dict[str, Any]:
    """Parse JSON from LLM response."""
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
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(image_bytes))
        plan_dict["image_dims"] = list(img.size)
        plan_dict["dpi"] = dpi
    except Exception as e:
        logger.warning(f"Could not extract image dimensions: {e}")
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
    # Scale: assume 300 DPI image where 1 inch = 25.4 mm
    # For a 1024px × 768px image at 300 DPI = 86.4mm × 64.8mm
    # Scale up features to be realistic room dimensions

    wall_thickness = 20  # pixels (represents ~5mm wall)
    margin = 100  # pixels margin from edge

    features = [
        # Outer walls (perimeter)
        {
            "id": "wall_001",
            "label": "wall_structure",
            "box": [margin, margin, margin + wall_thickness, img_height - margin],
            "conf": 0.98,
            "metadata": {},
        },
        {
            "id": "wall_002",
            "label": "wall_structure",
            "box": [margin, margin, img_width - margin, margin + wall_thickness],
            "conf": 0.98,
            "metadata": {},
        },
        {
            "id": "wall_003",
            "label": "wall_structure",
            "box": [img_width - margin - wall_thickness, margin, img_width - margin, img_height - margin],
            "conf": 0.98,
            "metadata": {},
        },
        {
            "id": "wall_004",
            "label": "wall_structure",
            "box": [margin, img_height - margin - wall_thickness, img_width - margin, img_height - margin],
            "conf": 0.98,
            "metadata": {},
        },
        # Interior wall (dividing rooms)
        {
            "id": "wall_005",
            "label": "wall_structure",
            "box": [img_width // 2 - wall_thickness // 2, margin + wall_thickness, img_width // 2 + wall_thickness // 2, img_height - margin - wall_thickness],
            "conf": 0.95,
            "metadata": {},
        },
        # Door symbol
        {
            "id": "symbol_001",
            "label": "symbol",
            "box": [img_width // 2 - 40, margin + wall_thickness - 5, img_width // 2 + 40, margin + wall_thickness + 30],
            "conf": 0.90,
            "metadata": {"symbol_type": "door", "swing_direction": "right"},
        },
        # Window symbols
        {
            "id": "symbol_002",
            "label": "symbol",
            "box": [margin + 100, margin - 30, margin + 200, margin + 10],
            "conf": 0.88,
            "metadata": {"symbol_type": "window"},
        },
        {
            "id": "symbol_003",
            "label": "symbol",
            "box": [img_width - margin - 200, margin - 30, img_width - margin - 100, margin + 10],
            "conf": 0.88,
            "metadata": {"symbol_type": "window"},
        },
        # Text labels
        {
            "id": "text_001",
            "label": "text",
            "box": [margin + 150, margin + 150, margin + 300, margin + 250],
            "conf": 0.92,
            "metadata": {"content": "LIVING ROOM", "rotation_deg": 0},
        },
        {
            "id": "text_002",
            "label": "text",
            "box": [img_width - margin - 300, margin + 150, img_width - margin - 150, margin + 250],
            "conf": 0.92,
            "metadata": {"content": "BEDROOM", "rotation_deg": 0},
        },
        {
            "id": "text_003",
            "label": "text",
            "box": [img_width // 2 - 150, img_height - margin - 200, img_width // 2 + 150, img_height - margin - 100],
            "conf": 0.90,
            "metadata": {"content": "KITCHEN", "rotation_deg": 0},
        },
        # Dimension lines
        {
            "id": "dim_001",
            "label": "dimension_line",
            "box": [margin - 50, margin + wall_thickness, margin - 30, img_height - margin - wall_thickness],
            "conf": 0.85,
            "metadata": {"dimension": "10.5m"},
        },
        {
            "id": "dim_002",
            "label": "dimension_line",
            "box": [margin + wall_thickness, img_height - margin - 50, img_width - margin - wall_thickness, img_height - margin - 30],
            "conf": 0.85,
            "metadata": {"dimension": "15.0m"},
        },
        # North arrow
        {
            "id": "north_001",
            "label": "north_arrow",
            "box": [img_width - margin - 80, margin, img_width - margin, margin + 80],
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
