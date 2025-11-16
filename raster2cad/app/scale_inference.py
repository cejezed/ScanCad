"""
Scale inference module for automatic DXF unit scaling.

Determines the scale (pixels to millimeters) by analyzing dimension lines
detected in the architectural plan. Uses median of all valid dimension
measurements for robustness.
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


def parse_dimension_text_to_mm(text: str) -> Optional[float]:
    """
    Parse dimension strings and convert to millimeters.

    Supports formats:
    - "1306" → 1306 mm
    - "7,20 m" / "7.20 m" → 7200 mm
    - "7,20" → 7200 mm (assumes meters if > 100)
    - "1306 mm" → 1306 mm
    - "130.6 cm" → 1306 mm

    Args:
        text: Raw dimension text from drawing

    Returns:
        Length in millimeters (float) or None if parse fails
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()

    # Try explicit unit markers first
    if "mm" in text.lower():
        match = re.search(r"([\d,\.]+)\s*mm", text, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", "."))
            return value

    if "cm" in text.lower():
        match = re.search(r"([\d,\.]+)\s*cm", text, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", "."))
            return value * 10  # cm to mm

    if "m" in text.lower():
        match = re.search(r"([\d,\.]+)\s*m(?:\s|$)", text, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", "."))
            return value * 1000  # meters to mm

    # No unit marker: try raw number
    match = re.search(r"([\d,\.]+)", text)
    if match:
        value = float(match.group(1).replace(",", "."))
        # Heuristic: if > 100, probably already in mm; if <= 100, probably meters
        if value > 100:
            return value
        else:
            return value * 1000

    return None


def get_dimension_line_length_px(box: List[float]) -> float:
    """
    Calculate pixel length of a dimension line from bounding box.

    Args:
        box: [x1, y1, x2, y2] in pixels

    Returns:
        Euclidean distance in pixels
    """
    x1, y1, x2, y2 = box
    dx = x2 - x1
    dy = y2 - y1
    return (dx**2 + dy**2) ** 0.5


def infer_scale_from_plan(
    plan: Dict[str, Any],
    default_px_to_mm: float = 0.085,  # ~300 DPI default
    min_dimension_confidence: float = 0.7,
    min_valid_measurements: int = 1,
) -> float:
    """
    Infer pixel-to-millimeter scale from dimension lines in the plan.

    Algorithm:
    1. Collect all dimension_line features with valid metadata.dimension
    2. Parse dimension text to mm value
    3. Measure pixel length from bounding box
    4. Calculate scale (mm_per_px) for each valid measurement
    5. Return median scale, or default if insufficient data

    Args:
        plan: Parsed plan JSON with features list
        default_px_to_mm: Default scale if inference fails (mm per pixel)
        min_dimension_confidence: Only use features with confidence >= this
        min_valid_measurements: Minimum valid measurements needed

    Returns:
        Scale factor (mm per pixel)
    """
    if not plan or "features" not in plan:
        logger.warning("No features in plan, using default scale")
        return default_px_to_mm

    features = plan.get("features", [])
    scales = []

    for feature in features:
        label = feature.get("label")
        if label != "dimension_line":
            continue

        conf = feature.get("conf", 0.0)
        if conf < min_dimension_confidence:
            continue

        metadata = feature.get("metadata", {})
        dimension_text = metadata.get("dimension")
        if not dimension_text:
            continue

        mm_value = parse_dimension_text_to_mm(dimension_text)
        if mm_value is None or mm_value <= 0:
            logger.debug(f"Failed to parse dimension: {dimension_text}")
            continue

        box = feature.get("box")
        if not box or len(box) != 4:
            continue

        px_length = get_dimension_line_length_px(box)
        if px_length <= 1:  # Avoid division by near-zero
            continue

        scale = mm_value / px_length
        if scale > 0:
            scales.append(scale)
            logger.debug(f"Dimension '{dimension_text}': {mm_value}mm / {px_length:.1f}px = {scale:.6f} mm/px")

    if len(scales) < min_valid_measurements:
        logger.warning(f"Only {len(scales)} valid dimension measurements (need >={min_valid_measurements}), using default scale {default_px_to_mm}")
        return default_px_to_mm

    # Use median for robustness against outliers
    scales.sort()
    median_scale = scales[len(scales) // 2]

    logger.info(f"Inferred scale from {len(scales)} dimension lines: {median_scale:.6f} mm/px (default was {default_px_to_mm:.6f})")
    return median_scale


def validate_inferred_scale(
    plan: Dict[str, Any],
    inferred_scale: float,
    tolerance_percent: float = 20.0,
) -> bool:
    """
    Validate inferred scale by checking if all dimension_line measurements
    are reasonably close to the inferred scale.

    Args:
        plan: Plan JSON
        inferred_scale: The inferred scale to validate
        tolerance_percent: Max deviation allowed (%)

    Returns:
        True if valid, False if suspicious
    """
    if not plan or "features" not in plan:
        return True  # Can't validate without features

    features = plan.get("features", [])
    deviations = []

    for feature in features:
        if feature.get("label") != "dimension_line":
            continue

        metadata = feature.get("metadata", {})
        dimension_text = metadata.get("dimension")
        if not dimension_text:
            continue

        mm_value = parse_dimension_text_to_mm(dimension_text)
        if mm_value is None or mm_value <= 0:
            continue

        box = feature.get("box")
        if not box or len(box) != 4:
            continue

        px_length = get_dimension_line_length_px(box)
        if px_length <= 1:
            continue

        expected_mm = px_length * inferred_scale
        deviation = abs(expected_mm - mm_value) / mm_value * 100
        deviations.append(deviation)

        if deviation > tolerance_percent:
            logger.warning(f"Dimension '{dimension_text}': expected {expected_mm:.1f}mm, got {mm_value:.1f}mm (deviation {deviation:.1f}%)")

    if deviations:
        avg_deviation = sum(deviations) / len(deviations)
        logger.info(f"Scale validation: average deviation {avg_deviation:.1f}%, max {max(deviations):.1f}%")
        return avg_deviation <= tolerance_percent

    return True
