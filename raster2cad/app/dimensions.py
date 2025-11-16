"""
Dimension extraction and reconstruction for architectural plans.

Converts dimension_line features into usable architectural dimension data
with validation and quality metrics.
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .scale_inference import parse_dimension_text_to_mm, get_dimension_line_length_px

logger = logging.getLogger(__name__)


@dataclass
class Dimension:
    """Represents a single architectural dimension."""
    id: str
    from_mm: Tuple[float, float]  # [x, y] in mm
    to_mm: Tuple[float, float]    # [x, y] in mm
    value_mm: float               # Measured value in mm
    raw_text: str                 # Original text from drawing
    confidence: float             # Feature confidence from LLM
    orientation: str              # "horizontal", "vertical", or "diagonal"
    deviation_percent: Optional[float] = None  # Deviation from expected


def extract_dimensions(
    plan: Dict[str, Any],
    px_to_mm: float,
    min_confidence: float = 0.5,
) -> List[Dimension]:
    """
    Extract dimensions from a plan with all validation.

    Args:
        plan: Plan JSON dict
        px_to_mm: Scale factor (mm per pixel)
        min_confidence: Minimum feature confidence to include

    Returns:
        List of Dimension objects
    """
    dimensions = []

    if "features" not in plan:
        return dimensions

    for feature in plan.get("features", []):
        if feature.get("label") != "dimension_line":
            continue

        if feature.get("conf", 0.0) < min_confidence:
            continue

        dim = _feature_to_dimension(feature, px_to_mm)
        if dim is not None:
            dimensions.append(dim)

    logger.info(f"Extracted {len(dimensions)} dimensions from plan")
    return dimensions


def _feature_to_dimension(feature: Dict[str, Any], px_to_mm: float) -> Optional[Dimension]:
    """Convert a dimension_line feature to Dimension object."""
    try:
        feature_id = feature.get("id", "unknown")
        box = feature.get("box")
        conf = feature.get("conf", 0.0)
        metadata = feature.get("metadata", {})

        if not box or len(box) != 4:
            logger.debug(f"Invalid box for dimension {feature_id}")
            return None

        x1, y1, x2, y2 = box
        dimension_text = metadata.get("dimension")

        if not dimension_text:
            logger.debug(f"No dimension text for {feature_id}")
            return None

        value_mm = parse_dimension_text_to_mm(dimension_text)
        if value_mm is None or value_mm <= 0:
            logger.debug(f"Invalid dimension value: {dimension_text}")
            return None

        # Convert pixel coords to mm
        from_mm = (x1 * px_to_mm, y1 * px_to_mm)
        to_mm = (x2 * px_to_mm, y2 * px_to_mm)

        # Determine orientation
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx > dy * 2:
            orientation = "horizontal"
        elif dy > dx * 2:
            orientation = "vertical"
        else:
            orientation = "diagonal"

        # Calculate expected length based on coordinates
        expected_px = get_dimension_line_length_px(box)
        expected_mm = expected_px * px_to_mm

        # Calculate deviation
        if expected_mm > 0:
            deviation = abs(expected_mm - value_mm) / value_mm * 100
        else:
            deviation = None

        return Dimension(
            id=feature_id,
            from_mm=from_mm,
            to_mm=to_mm,
            value_mm=value_mm,
            raw_text=dimension_text,
            confidence=conf,
            orientation=orientation,
            deviation_percent=deviation,
        )

    except Exception as e:
        logger.warning(f"Error converting dimension feature: {e}")
        return None


def validate_dimensions(
    dimensions: List[Dimension],
    max_deviation_percent: float = 20.0,
) -> Tuple[List[Dimension], List[Dimension]]:
    """
    Separate valid from suspicious dimensions.

    Args:
        dimensions: List of extracted dimensions
        max_deviation_percent: Max allowed deviation (%)

    Returns:
        (valid_dimensions, suspicious_dimensions)
    """
    valid = []
    suspicious = []

    for dim in dimensions:
        if dim.deviation_percent is None:
            valid.append(dim)
        elif dim.deviation_percent <= max_deviation_percent:
            valid.append(dim)
        else:
            suspicious.append(dim)
            logger.warning(
                f"Suspicious dimension {dim.id}: {dim.deviation_percent:.1f}% "
                f"deviation (expected {dim.value_mm:.0f}mm)"
            )

    logger.info(f"Dimension validation: {len(valid)} valid, {len(suspicious)} suspicious")
    return valid, suspicious


def dimensions_to_dict(dimensions: List[Dimension]) -> List[Dict[str, Any]]:
    """Convert Dimension objects to serializable dicts."""
    return [
        {
            "id": d.id,
            "from_mm": d.from_mm,
            "to_mm": d.to_mm,
            "value_mm": d.value_mm,
            "raw_text": d.raw_text,
            "confidence": d.confidence,
            "orientation": d.orientation,
            "deviation_percent": d.deviation_percent,
        }
        for d in dimensions
    ]


def create_dxf_dimensions(
    doc,
    msp,
    dimensions: List[Dimension],
    layer_name: str = "DIMENSIONS",
) -> int:
    """
    Add dimensions to DXF document.

    Creates DIMENSION entities or simple LINE+TEXT representations.

    Args:
        doc: ezdxf document
        msp: Model space
        dimensions: List of Dimension objects
        layer_name: DXF layer name

    Returns:
        Number of dimensions added
    """
    try:
        # Ensure layer exists
        if layer_name not in doc.layers:
            doc.layers.new(name=layer_name, dxfattribs={"color": 2})

        count = 0
        for dim in dimensions:
            x1, y1 = dim.from_mm
            x2, y2 = dim.to_mm

            # Add dimension line
            msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer_name, "color": 2})

            # Add dimension text
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text = f"{dim.value_mm:.0f}"

            msp.add_text(
                text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 2,
                    "height": 50,  # 50mm text height
                    "halign": 1,   # Center horizontal
                    "valign": 0,   # Bottom vertical
                },
            ).set_pos((mid_x, mid_y))

            count += 1

        logger.info(f"Added {count} dimensions to DXF")
        return count

    except Exception as e:
        logger.error(f"Error creating DXF dimensions: {e}")
        return 0


def summarize_dimensions(dimensions: List[Dimension]) -> Dict[str, Any]:
    """Create a summary of dimension statistics."""
    if not dimensions:
        return {
            "total": 0,
            "horizontal": 0,
            "vertical": 0,
            "diagonal": 0,
            "avg_confidence": 0.0,
        }

    horizontal = [d for d in dimensions if d.orientation == "horizontal"]
    vertical = [d for d in dimensions if d.orientation == "vertical"]
    diagonal = [d for d in dimensions if d.orientation == "diagonal"]

    avg_conf = sum(d.confidence for d in dimensions) / len(dimensions) if dimensions else 0.0

    return {
        "total": len(dimensions),
        "horizontal": len(horizontal),
        "vertical": len(vertical),
        "diagonal": len(diagonal),
        "avg_confidence": avg_conf,
        "avg_value_mm": sum(d.value_mm for d in dimensions) / len(dimensions),
    }
