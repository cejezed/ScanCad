"""
Post-processing cleanup for LLM-generated floor plans.

Corrects bounding box issues where the LLM's floorplan/wall detection
is too small or positioned incorrectly by inferring the true floorplan
extent from the union of all semantic features (text, symbols, walls).
"""

import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

Box = Tuple[float, float, float, float]

# Feature types to ignore when calculating floorplan bounds
IGNORED_FOR_FLOORPLAN = {"dimension_line", "north_arrow", "noise"}


def union_box(boxes: List[Box]) -> Optional[Box]:
    """
    Calculate the bounding box that encloses all given boxes.

    Args:
        boxes: List of [x1, y1, x2, y2] tuples

    Returns:
        Union box as (x1, y1, x2, y2) or None if list is empty
    """
    if not boxes:
        return None

    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes)
    y2 = max(b[3] for b in boxes)
    return (x1, y1, x2, y2)


def infer_floorplan_box(plan: Dict[str, Any], padding: int = 20) -> Optional[Box]:
    """
    Determine a robust floorplan bounding box as the union of:
    - all wall_structure features
    - all text features
    - all symbol features

    Ignores dimension_line, north_arrow, noise as they are outside the main plan.

    Args:
        plan: Plan dictionary with features list
        padding: Padding around the union box in pixels (default 20)

    Returns:
        Computed bounding box as (x1, y1, x2, y2) or None if no candidates found
    """
    features = plan.get("features", [])
    if not isinstance(features, list):
        return None

    candidate_boxes: List[Box] = []

    for feature in features:
        label = feature.get("label")

        # Skip ignored feature types
        if label in IGNORED_FOR_FLOORPLAN:
            continue

        box = feature.get("box")
        if not box or not isinstance(box, (list, tuple)) or len(box) != 4:
            continue

        # Ensure all coordinates are numeric
        try:
            box_tuple = tuple(float(x) for x in box)
            candidate_boxes.append(box_tuple)
        except (TypeError, ValueError):
            continue

    if not candidate_boxes:
        logger.debug("No candidate boxes found for floorplan inference")
        return None

    union = union_box(candidate_boxes)
    if union is None:
        return None

    x1, y1, x2, y2 = union
    # Apply padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = x2 + padding
    y2 = y2 + padding

    return (x1, y1, x2, y2)


def normalize_floorplan_and_walls(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize floorplan and main wall_structure features using inferred bounds.

    This function:
    1. Computes the true floorplan extent from all semantic features
    2. Updates or creates the main floorplan feature with this extent
    3. Updates the largest wall_structure feature to match the floorplan extent

    This ensures that the floorplan and main wall boxes properly enclose all rooms,
    doors, windows, and text labels.

    Args:
        plan: Plan dictionary with features list

    Returns:
        Modified plan dictionary with normalized boxes
    """
    inferred_bbox = infer_floorplan_box(plan)

    if inferred_bbox is None:
        logger.debug("Could not infer floorplan box; returning plan unchanged")
        return plan

    features = plan.get("features", [])
    if not isinstance(features, list):
        return plan

    logger.info(f"Inferred floorplan box: {inferred_bbox}")

    # 1. Update or create main floorplan feature
    floorplan_features = [f for f in features if f.get("label") == "floorplan"]

    if floorplan_features:
        # Update existing floorplan feature
        main_floorplan = floorplan_features[0]
        main_floorplan["box"] = list(inferred_bbox)
        logger.info(f"Updated existing floorplan feature to {inferred_bbox}")
    else:
        # Create new floorplan feature
        new_floorplan = {
            "id": "auto_floorplan",
            "label": "floorplan",
            "box": list(inferred_bbox),
            "conf": 0.99,
            "metadata": {}
        }
        features.insert(0, new_floorplan)
        logger.info(f"Created new floorplan feature: {inferred_bbox}")

    # 2. Update largest wall_structure feature to match floorplan
    wall_features = [
        f for f in features
        if f.get("label") == "wall_structure"
        and isinstance(f.get("box"), (list, tuple))
        and len(f.get("box")) == 4
    ]

    if wall_features:
        # Calculate area for each wall feature
        def box_area(feature):
            try:
                x1, y1, x2, y2 = feature["box"]
                return (x2 - x1) * (y2 - y1)
            except (TypeError, ValueError):
                return 0

        # Select largest wall feature
        main_wall = max(wall_features, key=box_area)
        main_wall["box"] = list(inferred_bbox)
        logger.info(f"Updated largest wall_structure feature to {inferred_bbox}")

    plan["features"] = features
    return plan
