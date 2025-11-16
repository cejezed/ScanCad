"""
Room detection and analysis for architectural plans.

Detects enclosed room spaces, associates text labels and areas,
and creates room entities for DXF output.
"""

import logging
import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from scipy import ndimage

logger = logging.getLogger(__name__)


@dataclass
class Room:
    """Represents a detected room/space."""
    id: str
    name: Optional[str] = None
    area_m2: Optional[float] = None
    area_px2: Optional[float] = None
    centroid: Optional[Tuple[float, float]] = None
    polygon: List[Tuple[float, float]] = None  # In world coordinates (mm)
    confidence: float = 0.0


def detect_rooms_from_segments(
    segments: List[Tuple[float, float, float, float]],
    px_to_mm: float,
    plan: Dict[str, Any],
    dpi: int = 300,
    downsample_factor: int = 2,
    min_room_area_px2: int = 500,
) -> List[Room]:
    """
    Detect rooms from wall segments using flood-fill algorithm.

    Algorithm:
    1. Create binary image from wall segments
    2. Downsample to reduce memory
    3. Use flood-fill to identify enclosed spaces
    4. Extract contours as room boundaries
    5. Match text labels to rooms by spatial overlap

    Args:
        segments: List of wall segments (x1, y1, x2, y2)
        px_to_mm: Scale factor
        plan: Full plan JSON for text labels
        dpi: Image DPI (for contour refinement)
        downsample_factor: Downsample for processing
        min_room_area_px2: Minimum room size in pixels

    Returns:
        List of Room objects
    """
    if not segments:
        logger.warning("No segments provided for room detection")
        return []

    # Determine image dimensions from segments
    max_x = max(max(s[0], s[2]) for s in segments)
    max_y = max(max(s[1], s[3]) for s in segments)
    img_width = int(max_x) + 10
    img_height = int(max_y) + 10

    logger.debug(f"Room detection: creating {img_width}x{img_height} image")

    # Create binary image with walls drawn
    binary_img = np.zeros((img_height, img_width), dtype=np.uint8)
    for x1, y1, x2, y2 in segments:
        cv2.line(binary_img, (int(x1), int(y1)), (int(x2), int(y2)), 255, 2)

    # Downsample
    if downsample_factor > 1:
        h, w = binary_img.shape
        binary_img = cv2.resize(
            binary_img,
            (w // downsample_factor, h // downsample_factor),
            interpolation=cv2.INTER_NEAREST,
        )

    # Invert: walls are 0, spaces are 255
    inv_img = cv2.bitwise_not(binary_img)

    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(inv_img, connectivity=8)

    rooms = []
    room_id_counter = 0

    for label_idx in range(1, num_labels):  # Skip background (label 0)
        area_px2 = stats[label_idx, cv2.CC_STAT_AREA]

        if area_px2 < min_room_area_px2 // (downsample_factor**2):
            continue

        # Extract room contour
        mask = (labels == label_idx).astype(np.uint8) * 255

        # Upsample mask if downsampled
        if downsample_factor > 1:
            h_orig = int(max_y) + 10
            w_orig = int(max_x) + 10
            mask = cv2.resize(mask, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        # Use largest contour
        contour = max(contours, key=cv2.contourArea)
        area_px2_final = cv2.contourArea(contour)

        if area_px2_final < min_room_area_px2:
            continue

        # Convert contour to polygon in mm
        polygon_px = contour.reshape(-1, 2).astype(float).tolist()
        polygon_mm = [(x * px_to_mm, y * px_to_mm) for x, y in polygon_px]

        # Calculate centroid
        M = cv2.moments(contour)
        if M["m00"] > 0:
            cx = M["m10"] / M["m00"] * px_to_mm
            cy = M["m01"] / M["m00"] * px_to_mm
        else:
            cx, cy = polygon_mm[0]

        # Convert area to m²
        area_m2 = area_px2_final * (px_to_mm**2) / 1e6

        room = Room(
            id=f"room_{room_id_counter:03d}",
            centroid=(cx, cy),
            polygon=polygon_mm,
            area_px2=area_px2_final,
            area_m2=area_m2,
            confidence=0.5,  # Default confidence
        )

        rooms.append(room)
        room_id_counter += 1

    # Associate text labels with rooms
    _match_text_to_rooms(rooms, plan, px_to_mm)

    logger.info(f"Detected {len(rooms)} rooms")
    return rooms


def _match_text_to_rooms(rooms: List[Room], plan: Dict[str, Any], px_to_mm: float) -> None:
    """Match text features to rooms by spatial overlap."""
    text_features = [
        f for f in plan.get("features", [])
        if f.get("label") == "text"
    ]

    for text_feat in text_features:
        box = text_feat.get("box")
        if not box or len(box) != 4:
            continue

        x_center = (box[0] + box[2]) / 2 * px_to_mm
        y_center = (box[1] + box[3]) / 2 * px_to_mm
        point = np.array([x_center, y_center])

        # Find closest room
        best_room = None
        best_dist = float("inf")

        for room in rooms:
            if room.centroid is None:
                continue

            dist = np.linalg.norm(np.array(room.centroid) - point)
            if dist < best_dist:
                best_dist = dist
                best_room = room

        if best_room is not None:
            content = text_feat.get("metadata", {}).get("content", "")

            # Try to parse area
            if "m²" in content or "m2" in content:
                # Extract area value
                import re
                match = re.search(r"([\d,\.]+)\s*m", content)
                if match:
                    area_str = match.group(1).replace(",", ".")
                    try:
                        area = float(area_str)
                        if best_room.area_m2 is None:
                            best_room.area_m2 = area
                    except ValueError:
                        pass
            elif best_room.name is None:
                # Use as room name if no number
                best_room.name = content


def create_dxf_rooms(
    doc,
    msp,
    rooms: List[Room],
    layer_name: str = "ROOMS",
    hatch_layer: str = "ROOM_HATCHES",
) -> int:
    """
    Add rooms to DXF as hatches and text.

    Args:
        doc: ezdxf document
        msp: Model space
        rooms: List of rooms
        layer_name: Layer for room boundaries
        hatch_layer: Layer for room fill patterns

    Returns:
        Number of rooms added
    """
    try:
        # Create layers
        for layer in [layer_name, hatch_layer]:
            if layer not in doc.layers:
                doc.layers.new(name=layer)

        count = 0
        for room in rooms:
            if room.polygon is None or len(room.polygon) < 3:
                continue

            # Create LWPOLYLINE for room boundary
            poly_points = room.polygon
            msp.add_lwpolyline(
                poly_points,
                dxfattribs={
                    "layer": layer_name,
                    "color": 7,
                    "closed": True,
                }
            )

            # Create HATCH fill (optional)
            try:
                hatch = msp.add_hatch(color=250)
                hatch.dxf.layer = hatch_layer
                hatch.append_edge_path(poly_points)
            except Exception as e:
                logger.debug(f"Could not create hatch for room {room.id}: {e}")

            # Add room label as TEXT
            if room.centroid:
                label_lines = []
                if room.name:
                    label_lines.append(room.name)
                if room.area_m2:
                    label_lines.append(f"{room.area_m2:.1f} m²")

                if label_lines:
                    label_text = "\n".join(label_lines)
                    msp.add_text(
                        label_text,
                        dxfattribs={
                            "layer": layer_name,
                            "height": 100,
                            "halign": 1,  # Center
                            "valign": 0,  # Bottom
                        },
                    ).set_pos(room.centroid)

            count += 1

        logger.info(f"Added {count} rooms to DXF")
        return count

    except Exception as e:
        logger.error(f"Error creating DXF rooms: {e}")
        return 0


def rooms_to_dict(rooms: List[Room]) -> List[Dict[str, Any]]:
    """Convert Room objects to serializable dicts."""
    return [
        {
            "id": r.id,
            "name": r.name,
            "area_m2": r.area_m2,
            "area_px2": r.area_px2,
            "centroid": r.centroid,
            "polygon": r.polygon,
            "confidence": r.confidence,
        }
        for r in rooms
    ]


def summarize_rooms(rooms: List[Room]) -> Dict[str, Any]:
    """Create a summary of room statistics."""
    named_rooms = [r for r in rooms if r.name]
    rooms_with_area = [r for r in rooms if r.area_m2]

    total_area = sum(r.area_m2 for r in rooms_with_area) if rooms_with_area else 0.0

    return {
        "total_rooms": len(rooms),
        "named_rooms": len(named_rooms),
        "rooms_with_area": len(rooms_with_area),
        "total_area_m2": total_area,
        "avg_area_m2": total_area / len(rooms_with_area) if rooms_with_area else 0.0,
    }
