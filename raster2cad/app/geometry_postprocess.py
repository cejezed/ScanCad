"""
CAD snapping and geometry post-processing engine.

Handles endpoint merging, co-linear segment fusion, orthogonalization,
and other geometric cleanup for vector drawings.
"""

import logging
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Type alias for line segments
Segment = Tuple[float, float, float, float]  # (x1, y1, x2, y2)


@dataclass
class Point:
    """2D point representation."""
    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        """Euclidean distance to another point."""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx**2 + dy**2)

    def angle_to(self, other: "Point") -> float:
        """Angle from this point to another (in degrees, 0-360)."""
        dx = other.x - self.x
        dy = other.y - self.y
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        return angle_deg % 360

    def __hash__(self):
        return hash((round(self.x, 3), round(self.y, 3)))

    def __eq__(self, other):
        if not isinstance(other, Point):
            return False
        return abs(self.x - other.x) < 0.01 and abs(self.y - other.y) < 0.01


def segment_length(seg: Segment) -> float:
    """Calculate length of a line segment."""
    x1, y1, x2, y2 = seg
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx**2 + dy**2)


def segment_angle(seg: Segment) -> float:
    """Calculate angle of a segment (0-180 degrees)."""
    x1, y1, x2, y2 = seg
    dx = x2 - x1
    dy = y2 - y1
    angle = math.degrees(math.atan2(dy, dx))
    # Normalize to 0-180 (lines don't have direction)
    angle = angle % 180
    return angle


def angle_between(angle1: float, angle2: float) -> float:
    """Calculate minimum angle between two angles (0-90)."""
    diff = abs(angle1 - angle2)
    # Since lines repeat every 180°, take the minimum
    diff = min(diff, 180 - diff)
    return diff


def snap_points(
    segments: List[Segment],
    snap_tolerance_px: float = 2.0,
) -> List[Segment]:
    """
    Merge endpoints that are close together (within snap tolerance).

    Algorithm:
    1. Collect all endpoints
    2. Cluster endpoints within snap_tolerance
    3. Replace each endpoint with its cluster centroid
    4. Return new segments with snapped endpoints

    Args:
        segments: List of (x1, y1, x2, y2) segments
        snap_tolerance_px: Maximum distance to snap (pixels)

    Returns:
        List of segments with snapped endpoints
    """
    if not segments:
        return []

    # Extract all endpoints
    endpoints = []
    for x1, y1, x2, y2 in segments:
        endpoints.append(Point(x1, y1))
        endpoints.append(Point(x2, y2))

    # Cluster endpoints
    clusters: List[List[Point]] = []
    used = set()

    for point in endpoints:
        if point in used:
            continue

        cluster = [point]
        used.add(point)

        for other in endpoints:
            if other in used:
                continue
            if point.distance_to(other) <= snap_tolerance_px:
                cluster.append(other)
                used.add(other)

        clusters.append(cluster)

    # Calculate centroid for each cluster
    centroids = {}
    for cluster in clusters:
        avg_x = sum(p.x for p in cluster) / len(cluster)
        avg_y = sum(p.y for p in cluster) / len(cluster)
        centroid = Point(avg_x, avg_y)
        for point in cluster:
            centroids[point] = centroid

    # Rebuild segments with snapped endpoints
    snapped = []
    for x1, y1, x2, y2 in segments:
        p1 = Point(x1, y1)
        p2 = Point(x2, y2)
        c1 = centroids.get(p1, p1)
        c2 = centroids.get(p2, p2)
        snapped.append((c1.x, c1.y, c2.x, c2.y))

    logger.debug(f"Snapped {len(endpoints)} endpoints into {len(clusters)} clusters")
    return snapped


def merge_colinear_segments(
    segments: List[Segment],
    angle_tol_deg: float = 5.0,
    gap_tol_px: float = 2.0,
) -> List[Segment]:
    """
    Merge segments that are approximately colinear and close together.

    Algorithm:
    1. Group segments by angle (within angle_tol_deg)
    2. Within each group, find segments that are collinear and nearby
    3. Merge collinear segments into one longer segment
    4. Return merged list

    Args:
        segments: List of (x1, y1, x2, y2) segments
        angle_tol_deg: Maximum angle difference to consider parallel
        gap_tol_px: Maximum gap between segment ends to merge

    Returns:
        List of merged segments
    """
    if not segments:
        return []

    # Group by angle
    angle_groups = {}
    for seg in segments:
        angle = segment_angle(seg)
        # Quantize angle to nearest tolerance
        angle_key = round(angle / angle_tol_deg) * angle_tol_deg
        if angle_key not in angle_groups:
            angle_groups[angle_key] = []
        angle_groups[angle_key].append(seg)

    # Merge within each angle group
    merged = []
    for angle_key, group in angle_groups.items():
        merged.extend(_merge_group(group, gap_tol_px))

    logger.debug(f"Merged {len(segments)} segments into {len(merged)}")
    return merged


def _merge_group(segments: List[Segment], gap_tol_px: float) -> List[Segment]:
    """Merge colinear segments within a group."""
    if not segments:
        return []

    # Sort segments by starting x or y (depending on orientation)
    if len(segments) > 0:
        first_seg = segments[0]
        x1, y1, x2, y2 = first_seg
        if abs(x2 - x1) > abs(y2 - y1):
            # Mostly horizontal
            segments = sorted(segments, key=lambda s: (s[0] + s[2]) / 2)
        else:
            # Mostly vertical
            segments = sorted(segments, key=lambda s: (s[1] + s[3]) / 2)

    # Merge adjacent colinear segments
    merged = []
    current = None

    for seg in segments:
        if current is None:
            current = seg
        else:
            merged_seg = _try_merge_two(current, seg, gap_tol_px)
            if merged_seg is not None:
                current = merged_seg
            else:
                merged.append(current)
                current = seg

    if current is not None:
        merged.append(current)

    return merged


def _try_merge_two(seg1: Segment, seg2: Segment, gap_tol_px: float) -> Optional[Segment]:
    """Try to merge two collinear segments."""
    x1a, y1a, x2a, y2a = seg1
    x1b, y1b, x2b, y2b = seg2

    # Check if endpoints are close
    end_a = Point(x2a, y2a)
    start_b = Point(x1b, y1b)
    distance = end_a.distance_to(start_b)

    if distance <= gap_tol_px:
        # Merge: extend seg1 to include seg2
        return (x1a, y1a, x2b, y2b)

    return None


def orthogonalize_segments(
    segments: List[Segment],
    angle_snap_deg: float = 5.0,
) -> List[Segment]:
    """
    Snap segments to cardinal directions if close enough.

    Makes walls perfectly horizontal or vertical if they're approximately
    aligned with cardinal axes.

    Args:
        segments: List of (x1, y1, x2, y2) segments
        angle_snap_deg: Threshold angle to snap to 0/90/180/270

    Returns:
        Orthogonalized segments
    """
    orthogonalized = []

    for x1, y1, x2, y2 in segments:
        angle = segment_angle((x1, y1, x2, y2))

        # Check if angle is close to cardinal direction
        snap_angle = None
        if angle < angle_snap_deg or angle > (180 - angle_snap_deg):
            snap_angle = 0  # Horizontal
        elif 90 - angle_snap_deg < angle < 90 + angle_snap_deg:
            snap_angle = 90  # Vertical

        if snap_angle is not None:
            # Snap to cardinal direction
            if snap_angle == 0:  # Horizontal
                y_mid = (y1 + y2) / 2
                x1, y1, x2, y2 = x1, y_mid, x2, y_mid
            else:  # Vertical
                x_mid = (x1 + x2) / 2
                x1, y1, x2, y2 = x_mid, y1, x_mid, y2

        orthogonalized.append((x1, y1, x2, y2))

    return orthogonalized


def remove_duplicate_segments(
    segments: List[Segment],
    tolerance_px: float = 1.0,
) -> List[Segment]:
    """
    Remove duplicate or nearly-identical segments.

    Args:
        segments: List of segments
        tolerance_px: Tolerance for endpoint comparison

    Returns:
        Deduplicated segment list
    """
    unique = []
    seen = set()

    for seg in segments:
        x1, y1, x2, y2 = seg

        # Normalize: ensure (x1,y1) <= (x2,y2) for comparison
        key = (
            min(round(x1, 1), round(x2, 1)),
            min(round(y1, 1), round(y2, 1)),
            max(round(x1, 1), round(x2, 1)),
            max(round(y1, 1), round(y2, 1)),
        )

        if key not in seen:
            unique.append(seg)
            seen.add(key)

    logger.debug(f"Removed {len(segments) - len(unique)} duplicate segments")
    return unique


def postprocess_segments(
    segments: List[Segment],
    snap_tolerance_px: float = 2.0,
    angle_tol_deg: float = 5.0,
    gap_tol_px: float = 2.0,
    angle_snap_deg: float = 5.0,
) -> List[Segment]:
    """
    Complete post-processing pipeline for line segments.

    Steps:
    1. Remove duplicates
    2. Snap endpoints
    3. Merge colinear segments
    4. Orthogonalize to cardinal directions
    5. Remove duplicates again (in case merging created duplicates)

    Args:
        segments: Input segments
        snap_tolerance_px: Snap distance
        angle_tol_deg: Angle tolerance for colinearity
        gap_tol_px: Gap tolerance for merging
        angle_snap_deg: Angle snap to cardinal

    Returns:
        Post-processed segments
    """
    logger.info(f"Starting post-processing {len(segments)} segments")

    segments = remove_duplicate_segments(segments)
    segments = snap_points(segments, snap_tolerance_px)
    segments = merge_colinear_segments(segments, angle_tol_deg, gap_tol_px)
    segments = orthogonalize_segments(segments, angle_snap_deg)
    segments = remove_duplicate_segments(segments)

    logger.info(f"Post-processing complete: {len(segments)} segments")
    return segments
