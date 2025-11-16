"""
Plan overlay visualization for debugging and verification.

Creates visual overlays of detected features on the original drawing
for manual inspection and quality assurance.
"""

import logging
import cv2
import numpy as np
from typing import Dict, Any, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Color map for different feature labels (BGR format for OpenCV)
FEATURE_COLORS = {
    "wall_structure": (255, 0, 0),  # Blue
    "text": (0, 255, 0),  # Green
    "symbol": (0, 0, 255),  # Red
    "dimension_line": (255, 255, 0),  # Cyan
    "floorplan": (200, 100, 0),  # Dark cyan
    "noise": (128, 128, 128),  # Gray
    "elevation": (255, 165, 0),  # Orange
    "section": (255, 0, 255),  # Magenta
    "north_arrow": (255, 200, 0),  # Light blue
    "default": (200, 200, 200),  # Light gray
}


def draw_overlay(
    image_path: str,
    plan: Dict[str, Any],
    out_path: str,
    feature_filter: Optional[list] = None,
    alpha: float = 0.3,
    line_thickness: int = 2,
    text_size: float = 0.4,
    show_ids: bool = True,
    show_confidence: bool = True,
) -> bool:
    """
    Draw bounding boxes and labels on the original image.

    Creates a visual overlay showing all detected features for debugging
    and verification purposes.

    Args:
        image_path: Path to original image file
        plan: Plan JSON dict with features
        out_path: Output path for overlay image
        feature_filter: List of labels to include (None = all)
        alpha: Transparency of boxes (0.0-1.0)
        line_thickness: Thickness of bounding box lines
        text_size: Font size for labels
        show_ids: Include feature IDs in labels
        show_confidence: Include confidence scores

    Returns:
        True if successful, False otherwise
    """
    try:
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            return False

        img_overlay = img.copy()
        h, w = img.shape[:2]

        if "features" not in plan:
            logger.warning("No features in plan, saving blank overlay")
            cv2.imwrite(out_path, img)
            return True

        features = plan.get("features", [])
        logger.info(f"Drawing {len(features)} features on overlay")

        for feature in features:
            label = feature.get("label", "unknown")

            # Apply filter if specified
            if feature_filter and label not in feature_filter:
                continue

            box = feature.get("box")
            if not box or len(box) != 4:
                continue

            x1, y1, x2, y2 = [int(v) for v in box]

            # Clamp to image bounds
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w - 1))
            y2 = max(0, min(y2, h - 1))

            if x2 <= x1 or y2 <= y1:
                continue

            # Get color for this label
            color = FEATURE_COLORS.get(label, FEATURE_COLORS["default"])

            # Draw semi-transparent rectangle
            overlay = img_overlay.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            img_overlay = cv2.addWeighted(overlay, alpha, img_overlay, 1 - alpha, 0)

            # Draw rectangle outline
            cv2.rectangle(img_overlay, (x1, y1), (x2, y2), color, line_thickness)

            # Build label text
            label_parts = [label]
            if show_ids:
                feature_id = feature.get("id", "?")
                label_parts.append(f"#{feature_id}")
            if show_confidence:
                conf = feature.get("conf", 0.0)
                label_parts.append(f"{conf:.2f}")

            label_text = " ".join(label_parts)

            # Add content for text/dimension features
            if label == "text":
                content = feature.get("metadata", {}).get("content", "")
                if content:
                    label_text += f"\n'{content}'"

            # Draw text background
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = text_size
            thickness = 1
            text_size_px = cv2.getTextSize(label_text, font, font_scale, thickness)[0]

            # Use first line only for placement
            first_line = label_text.split("\n")[0]
            text_size_px = cv2.getTextSize(first_line, font, font_scale, thickness)[0]

            text_x = x1 + 3
            text_y = y1 - 5
            if text_y < 10:
                text_y = y2 + text_size_px[1] + 5

            # Draw text background
            cv2.rectangle(
                img_overlay,
                (text_x - 2, text_y - text_size_px[1] - 2),
                (text_x + text_size_px[0] + 2, text_y + 2),
                color,
                -1,
            )

            # Draw text
            cv2.putText(
                img_overlay,
                label_text,
                (text_x, text_y),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
            )

        # Save overlay
        success = cv2.imwrite(out_path, img_overlay)
        if success:
            logger.info(f"Overlay saved to {out_path}")
        else:
            logger.error(f"Failed to save overlay to {out_path}")

        return success

    except Exception as e:
        logger.error(f"Error drawing overlay: {e}")
        return False


def draw_overlay_with_categories(
    image_path: str,
    plan: Dict[str, Any],
    out_path: str,
) -> bool:
    """
    Draw overlay with features organized by category on sides.

    Creates a composite image with the original drawing in the center
    and feature categories listed on the right.

    Args:
        image_path: Path to original image
        plan: Plan JSON
        out_path: Output path

    Returns:
        True if successful
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return False

        # Draw basic overlay
        temp_path = "/tmp/overlay_temp.png"
        if not draw_overlay(image_path, plan, temp_path):
            return False

        img_overlay = cv2.imread(temp_path)

        # Create category summary
        categories = _categorize_features(plan)
        summary_text = _format_category_summary(categories)

        # Add text panel on the right
        h, w = img.shape[:2]
        panel_width = 300
        panel = np.ones((h, panel_width, 3), dtype=np.uint8) * 240

        # Draw text on panel
        y_offset = 20
        font = cv2.FONT_HERSHEY_SIMPLEX
        for line in summary_text.split("\n"):
            cv2.putText(panel, line, (10, y_offset), font, 0.4, (0, 0, 0), 1)
            y_offset += 20

        # Combine image + panel
        result = np.hstack([img_overlay, panel])

        cv2.imwrite(out_path, result)
        logger.info(f"Overlay with categories saved to {out_path}")
        return True

    except Exception as e:
        logger.error(f"Error drawing categorized overlay: {e}")
        return False


def _categorize_features(plan: Dict[str, Any]) -> Dict[str, list]:
    """Group features by label."""
    categories = {}
    for feature in plan.get("features", []):
        label = feature.get("label", "unknown")
        if label not in categories:
            categories[label] = []
        categories[label].append(feature)
    return categories


def _format_category_summary(categories: Dict[str, list]) -> str:
    """Format category summary for display."""
    lines = ["Feature Summary:"]
    total = 0
    for label in sorted(categories.keys()):
        count = len(categories[label])
        total += count
        lines.append(f"{label}: {count}")
    lines.append(f"Total: {total}")
    return "\n".join(lines)


def compare_overlays(
    image_path: str,
    plan1: Dict[str, Any],
    plan2: Dict[str, Any],
    out_path: str,
) -> bool:
    """
    Create a side-by-side comparison of two plan overlays.

    Useful for comparing LLM outputs or algorithm variations.

    Args:
        image_path: Original image
        plan1: First plan
        plan2: Second plan
        out_path: Output path

    Returns:
        True if successful
    """
    try:
        temp1 = "/tmp/overlay1.png"
        temp2 = "/tmp/overlay2.png"

        if not draw_overlay(image_path, plan1, temp1):
            return False
        if not draw_overlay(image_path, plan2, temp2):
            return False

        img1 = cv2.imread(temp1)
        img2 = cv2.imread(temp2)

        # Ensure same height
        h = max(img1.shape[0], img2.shape[0])
        img1 = cv2.resize(img1, (int(img1.shape[1] * h / img1.shape[0]), h))
        img2 = cv2.resize(img2, (int(img2.shape[1] * h / img2.shape[0]), h))

        # Combine
        result = np.hstack([img1, img2])
        cv2.imwrite(out_path, result)

        logger.info(f"Comparison overlay saved to {out_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating comparison overlay: {e}")
        return False
