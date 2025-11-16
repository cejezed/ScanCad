"""
Wall detection and filtering for hybrid LLM+CV vectorization.

Estimates line thickness and filters segments that match wall characteristics
(thick, straight lines of significant length).
"""

import logging
import numpy as np
import cv2
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

Segment = Tuple[float, float, float, float]


def estimate_line_thickness(
    binary_image: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    samples: int = 5,
) -> float:
    """
    Estimate the thickness of a line segment by sampling perpendicular widths.

    Args:
        binary_image: Binary image where white (>127) is foreground
        x1, y1, x2, y2: Line endpoints in pixels
        samples: Number of perpendicular samples to take

    Returns:
        Estimated line thickness in pixels
    """
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    h, w = binary_image.shape[:2]

    # Clamp to image bounds
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(0, min(w - 1, x2))
    y2 = max(0, min(h - 1, y2))

    if x1 == x2 and y1 == y2:
        return 0

    thicknesses = []

    # Sample perpendicular distance at multiple points along the line
    for i in range(samples):
        t = i / (samples - 1) if samples > 1 else 0.5
        # Point along the line
        px = int(x1 + t * (x2 - x1))
        py = int(y1 + t * (y2 - y1))

        # Perpendicular direction
        dx = x2 - x1
        dy = y2 - y1
        length = np.sqrt(dx**2 + dy**2)

        if length < 1:
            continue

        # Unit perpendicular vector
        perp_x = -dy / length
        perp_y = dx / length

        # Measure thickness by walking perpendicular to line
        thickness = 0
        for dist in range(1, 30):
            # Check both directions from line
            for sign in [-1, 1]:
                sx = int(px + sign * dist * perp_x)
                sy = int(py + sign * dist * perp_y)

                if 0 <= sx < w and 0 <= sy < h:
                    if binary_image[sy, sx] > 127:
                        thickness = max(thickness, dist)

        if thickness > 0:
            thicknesses.append(thickness * 2)  # Both sides

    if not thicknesses:
        return 0

    return float(np.median(thicknesses))


def filter_wall_segments(
    binary_image: np.ndarray,
    segments: List[Segment],
    min_thickness_px: float = 4.0,
    max_thickness_px: float = 50.0,
    min_length_px: float = 30.0,
) -> List[Segment]:
    """
    Filter line segments to keep only those that match wall characteristics.

    Args:
        binary_image: Binary image of the region (white foreground)
        segments: List of [x1, y1, x2, y2] line segments
        min_thickness_px: Minimum wall thickness in pixels
        max_thickness_px: Maximum wall thickness in pixels
        min_length_px: Minimum wall segment length in pixels

    Returns:
        Filtered list of segments that are likely walls
    """
    if not segments:
        return []

    wall_segments = []

    for seg in segments:
        if not isinstance(seg, (list, tuple)) or len(seg) != 4:
            continue

        x1, y1, x2, y2 = seg

        # Calculate segment length
        length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

        # Filter by length
        if length < min_length_px:
            continue

        # Estimate thickness
        thickness = estimate_line_thickness(binary_image, x1, y1, x2, y2)

        # Filter by thickness
        if thickness < min_thickness_px or thickness > max_thickness_px:
            continue

        wall_segments.append(seg)

    logger.debug(
        f"Wall filter: kept {len(wall_segments)}/{len(segments)} segments "
        f"(length>{min_length_px}px, thickness {min_thickness_px}-{max_thickness_px}px)"
    )

    return wall_segments


def detect_line_segments(
    binary_image: np.ndarray,
    min_line_length: float = 30,
    max_line_gap: float = 10,
) -> List[Segment]:
    """
    Detect line segments in a binary image using probabilistic Hough transform.

    Args:
        binary_image: Binary image (white foreground, black background)
        min_line_length: Minimum line segment length
        max_line_gap: Maximum gap to link line segments

    Returns:
        List of [x1, y1, x2, y2] segments
    """
    try:
        # Ensure image is 8-bit
        if binary_image.dtype != np.uint8:
            binary_image = (binary_image * 255).astype(np.uint8)

        # Apply Canny edge detection
        edges = cv2.Canny(binary_image, 50, 150)

        # Use Hough Line Transform (probabilistic)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=int(min_line_length),
            maxLineGap=int(max_line_gap),
        )

        if lines is None:
            return []

        # Convert to list of tuples
        segments = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            segments.append((float(x1), float(y1), float(x2), float(y2)))

        logger.debug(f"Detected {len(segments)} line segments via Hough")
        return segments

    except Exception as e:
        logger.error(f"Line detection failed: {e}")
        return []
