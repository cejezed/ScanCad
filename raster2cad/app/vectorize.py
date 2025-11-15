"""
Hybrid CV + DXF vectorization engine.
Processes plan JSON and image to generate DXF output.
"""

import logging
import math
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import io

import ezdxf
import numpy as np
import cv2

from .plan_contract import Plan, Feature

logger = logging.getLogger(__name__)


class WallSegment:
    """Represents a detected wall segment."""

    def __init__(
        self, x1: float, y1: float, x2: float, y2: float, thickness: float = 0.15
    ):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.thickness = thickness

    def length(self) -> float:
        """Get segment length."""
        return math.sqrt((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2)

    def angle(self) -> float:
        """Get segment angle in radians."""
        return math.atan2(self.y2 - self.y1, self.x2 - self.x1)

    def is_horizontal(self, tolerance: float = 0.1) -> bool:
        """Check if segment is horizontal."""
        angle = self.angle()
        return abs(angle) < tolerance or abs(abs(angle) - math.pi) < tolerance

    def is_vertical(self, tolerance: float = 0.1) -> bool:
        """Check if segment is vertical."""
        angle = self.angle()
        return abs(angle - math.pi / 2) < tolerance or abs(angle + math.pi / 2) < tolerance

    def distance_to_point(self, px: float, py: float) -> float:
        """Calculate perpendicular distance from point to line segment."""
        # Use cross product method
        numerator = abs(
            (self.y2 - self.y1) * px - (self.x2 - self.x1) * py
            + self.x2 * self.y1 - self.y2 * self.x1
        )
        denominator = math.sqrt((self.y2 - self.y1) ** 2 + (self.x2 - self.x1) ** 2)
        return numerator / denominator if denominator > 0 else float("inf")


def px_to_dxf_units(px: float, dpi: int = 300) -> float:
    """Convert pixels to DXF units (mm, assuming 1 DXF unit = 1 mm)."""
    # 1 inch = 25.4 mm, DPI pixels per inch
    return (px / dpi) * 25.4


class Vectorizer:
    """Main vectorization engine."""

    def __init__(self, dpi: int = 300, snap_tolerance_px: float = 5.0):
        self.dpi = dpi
        self.snap_tolerance_px = snap_tolerance_px
        self.wall_segments: List[WallSegment] = []
        self.detected_texts: List[Dict[str, Any]] = []
        self.detected_symbols: List[Dict[str, Any]] = []

    def process_plan(
        self,
        plan: Dict[str, Any],
        image_path: str,
        out_path: str,
    ) -> str:
        """
        Process plan and image to generate DXF.

        Args:
            plan: Plan dict from llm_analyzer
            image_path: Path to input image
            out_path: Path to output DXF

        Returns:
            Path to generated DXF file
        """
        # Parse plan
        plan_obj = Plan.from_dict(plan)

        # Load image
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            raise

        # Create DXF document
        dwg = ezdxf.new("R2010")
        msp = dwg.modelspace()

        # Create layers
        self._create_layers(dwg)

        # Setup blocks
        try:
            from blocks.dxf_block_definitions import setup_standard_blocks
        except ImportError:
            from ..blocks.dxf_block_definitions import setup_standard_blocks
        setup_standard_blocks(dwg)

        # Process features by type
        for feature in plan_obj.features:
            try:
                self._process_feature(feature, image, dwg, msp)
            except Exception as e:
                logger.warning(f"Failed to process feature {feature.id}: {e}")

        # Post-processing
        self._merge_colinear_segments()
        self._snap_endpoints()
        self._estimate_wall_thickness()

        # Write walls to DXF
        for segment in self.wall_segments:
            self._add_wall_to_dxf(msp, segment)

        # Write texts
        for text_item in self.detected_texts:
            msp.add_text(
                text_item["content"],
                dxfattribs={
                    "layer": "TEXTS",
                    "height": text_item.get("height", 0.5),
                    "rotation": text_item.get("rotation_deg", 0),
                    "insert": (text_item["x"], text_item["y"]),
                },
            )

        # Write symbols
        for symbol_item in self.detected_symbols:
            msp.add_blockref(
                symbol_item["block_name"],
                (symbol_item["x"], symbol_item["y"]),
                dxfattribs={"layer": "SYMBOLS"},
            )

        # Save DXF
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        dwg.saveas(out_path)
        logger.info(f"DXF saved to {out_path}")

        return out_path

    def _create_layers(self, dwg) -> None:
        """Create standard layers in DXF."""
        msp = dwg.modelspace()
        layer_defs = {
            "WALLS": {"color": 7, "linetype": "Continuous"},
            "LINES": {"color": 7, "linetype": "Continuous"},
            "TEXTS": {"color": 1, "linetype": "Continuous"},
            "SYMBOLS": {"color": 3, "linetype": "Continuous"},
            "ELEV_LINES": {"color": 5, "linetype": "Continuous"},
            "SECTION_LINES": {"color": 6, "linetype": "Continuous"},
            "DIMENSIONS": {"color": 2, "linetype": "Continuous"},
            "CONSTRUCTION": {"color": 4, "linetype": "Continuous"},
        }

        for layer_name, attrs in layer_defs.items():
            if layer_name not in dwg.layers:
                dwg.layers.new(
                    name=layer_name, dxfattribs={"color": attrs["color"]}
                )

    def _process_feature(
        self,
        feature: Feature,
        image: np.ndarray,
        dwg,
        msp: Any,
    ) -> None:
        """Process a single feature based on its label."""
        label = feature.label

        if label == "wall_structure":
            self._handle_wall_structure(feature, image)
        elif label == "text":
            self._handle_text(feature)
        elif label == "symbol":
            self._handle_symbol(feature)
        elif label in ["elevation", "section"]:
            self._handle_elevation_or_section(feature, image, msp, label)
        elif label in ["dimension_line", "noise", "north_arrow", "floorplan"]:
            logger.debug(f"Skipping {label}: {feature.id}")
        else:
            logger.warning(f"Unknown label: {label}")

    def _handle_wall_structure(self, feature: Feature, image: np.ndarray) -> None:
        """Detect and vectorize wall structures using CV."""
        x1, y1, x2, y2 = [int(v) for v in feature.box]

        # Ensure valid box
        if x2 <= x1 or y2 <= y1:
            return

        # Crop region
        roi = image[y1:y2, x1:x2]

        # Preprocess
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Threshold
        _, thresh = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)
        # Morphological opening
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Detect lines using LSD
        try:
            lsd = cv2.createLineSegmentDetector(0, 0.8, 0.1, 50)
            lines, _, _, _ = lsd.detect(opened)
        except Exception as e:
            logger.warning(f"LSD detection failed: {e}")
            return

        if lines is None:
            return

        # Convert to global coordinates and add to segments
        for line in lines:
            x_local1, y_local1, x_local2, y_local2 = line[0]
            x_global1 = x1 + x_local1
            y_global1 = y1 + y_local1
            x_global2 = x1 + x_local2
            y_global2 = y1 + y_local2

            segment = WallSegment(x_global1, y_global1, x_global2, y_global2)
            self.wall_segments.append(segment)

    def _handle_text(self, feature: Feature) -> None:
        """Extract text annotations."""
        x1, y1, x2, y2 = feature.box
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        content = feature.metadata.get("content", "TEXT")
        rotation = feature.metadata.get("rotation_deg", 0)

        # Convert pixel coords to DXF units
        dxf_x = px_to_dxf_units(cx, self.dpi)
        dxf_y = px_to_dxf_units(cy, self.dpi)
        dxf_height = px_to_dxf_units((y2 - y1), self.dpi) * 0.8

        self.detected_texts.append(
            {
                "content": content,
                "x": dxf_x,
                "y": dxf_y,
                "height": max(dxf_height, 0.3),
                "rotation_deg": rotation,
            }
        )

    def _handle_symbol(self, feature: Feature) -> None:
        """Place architectural symbols."""
        x1, y1, x2, y2 = feature.box
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        symbol_type = feature.metadata.get("symbol_type", "fixture")

        try:
            from blocks.dxf_block_definitions import get_block_name_for_symbol
        except ImportError:
            from ..blocks.dxf_block_definitions import get_block_name_for_symbol
        block_name = get_block_name_for_symbol(symbol_type)

        dxf_x = px_to_dxf_units(cx, self.dpi)
        dxf_y = px_to_dxf_units(cy, self.dpi)

        self.detected_symbols.append(
            {
                "block_name": block_name,
                "x": dxf_x,
                "y": dxf_y,
                "symbol_type": symbol_type,
            }
        )

    def _handle_elevation_or_section(
        self, feature: Feature, image: np.ndarray, msp: Any, label: str
    ) -> None:
        """Detect lines in elevation or section views."""
        x1, y1, x2, y2 = [int(v) for v in feature.box]

        if x2 <= x1 or y2 <= y1:
            return

        roi = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

        try:
            lsd = cv2.createLineSegmentDetector(0, 0.8, 0.1, 50)
            lines, _, _, _ = lsd.detect(thresh)
        except Exception:
            return

        if lines is None:
            return

        layer = "ELEV_LINES" if label == "elevation" else "SECTION_LINES"

        for line in lines:
            x_l1, y_l1, x_l2, y_l2 = line[0]
            # Convert to global coordinates and then to DXF
            px1 = x1 + x_l1
            py1 = y1 + y_l1
            px2 = x1 + x_l2
            py2 = y1 + y_l2

            dxf_x1 = px_to_dxf_units(px1, self.dpi)
            dxf_y1 = px_to_dxf_units(py1, self.dpi)
            dxf_x2 = px_to_dxf_units(px2, self.dpi)
            dxf_y2 = px_to_dxf_units(py2, self.dpi)

            msp.add_line((dxf_x1, dxf_y1), (dxf_x2, dxf_y2), dxfattribs={"layer": layer})

    def _merge_colinear_segments(self) -> None:
        """Merge colinear wall segments."""
        if len(self.wall_segments) < 2:
            return

        merged = []
        used = set()

        for i, seg1 in enumerate(self.wall_segments):
            if i in used:
                continue

            current = [seg1]

            # Try to find adjacent colinear segments
            for j, seg2 in enumerate(self.wall_segments):
                if i == j or j in used:
                    continue

                # Check if colinear and adjacent
                if self._are_colinear(seg1, seg2) and self._are_adjacent(seg1, seg2):
                    current.append(seg2)
                    used.add(j)

            if len(current) > 1:
                # Merge segments
                all_points = [
                    (current[0].x1, current[0].y1),
                    (current[0].x2, current[0].y2),
                ]
                for seg in current[1:]:
                    all_points.append((seg.x2, seg.y2))

                # Find extremes
                xs = [p[0] for p in all_points]
                ys = [p[1] for p in all_points]
                merged_seg = WallSegment(min(xs), min(ys), max(xs), max(ys))
                merged.append(merged_seg)
            else:
                merged.append(seg1)

            used.add(i)

        self.wall_segments = merged

    def _are_colinear(self, seg1: WallSegment, seg2: WallSegment, tolerance: float = 0.1) -> bool:
        """Check if two segments are colinear."""
        angle1 = seg1.angle()
        angle2 = seg2.angle()
        # Account for 180-degree difference
        angle_diff = abs(angle1 - angle2)
        return angle_diff < tolerance or abs(angle_diff - math.pi) < tolerance

    def _are_adjacent(self, seg1: WallSegment, seg2: WallSegment, tolerance: float = 10.0) -> bool:
        """Check if two segments are adjacent (within tolerance)."""
        dist1 = math.sqrt((seg1.x2 - seg2.x1) ** 2 + (seg1.y2 - seg2.y1) ** 2)
        dist2 = math.sqrt((seg1.x1 - seg2.x2) ** 2 + (seg1.y1 - seg2.y2) ** 2)
        return dist1 < tolerance or dist2 < tolerance

    def _snap_endpoints(self) -> None:
        """Snap segment endpoints within tolerance."""
        if len(self.wall_segments) < 2:
            return

        tolerance = self.snap_tolerance_px
        snapped = False

        for i in range(len(self.wall_segments)):
            for j in range(i + 1, len(self.wall_segments)):
                seg1 = self.wall_segments[i]
                seg2 = self.wall_segments[j]

                # Check all endpoint pairs
                for attr1, attr2 in [
                    (("x1", "y1"), ("x2", "y2")),
                    (("x1", "y1"), ("x1", "y1")),
                    (("x2", "y2"), ("x2", "y2")),
                    (("x2", "y2"), ("x1", "y1")),
                ]:
                    x1, y1 = getattr(seg1, attr1[0]), getattr(seg1, attr1[1])
                    x2, y2 = getattr(seg2, attr2[0]), getattr(seg2, attr2[1])

                    dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    if dist < tolerance and dist > 0:
                        # Snap to average position
                        new_x = (x1 + x2) / 2
                        new_y = (y1 + y2) / 2

                        setattr(seg1, attr1[0], new_x)
                        setattr(seg1, attr1[1], new_y)
                        setattr(seg2, attr2[0], new_x)
                        setattr(seg2, attr2[1], new_y)
                        snapped = True

        if snapped:
            logger.debug("Snapped endpoints")

    def _estimate_wall_thickness(self) -> None:
        """Estimate wall thickness based on segment characteristics."""
        for segment in self.wall_segments:
            # Simple heuristic: longer segments are likely walls (thickness ~0.2-0.3 units)
            if segment.length() > 50:  # pixels
                segment.thickness = 0.2
            else:
                segment.thickness = 0.1

    def _add_wall_to_dxf(self, msp: Any, segment: WallSegment) -> None:
        """Add a wall segment to DXF as a thickened polyline."""
        dxf_x1 = px_to_dxf_units(segment.x1, self.dpi)
        dxf_y1 = px_to_dxf_units(segment.y1, self.dpi)
        dxf_x2 = px_to_dxf_units(segment.x2, self.dpi)
        dxf_y2 = px_to_dxf_units(segment.y2, self.dpi)

        # Add polyline with thickness
        lwpoly = msp.add_lwpolyline(
            [(dxf_x1, dxf_y1), (dxf_x2, dxf_y2)],
            dxfattribs={"layer": "WALLS"},
        )
        lwpoly.width = segment.thickness


def process_plan(
    plan: Dict[str, Any],
    image_path: str,
    out_path: str,
    dpi: int = 300,
) -> str:
    """
    Convenience function to process a plan and generate DXF.

    Args:
        plan: Plan dictionary
        image_path: Input image path
        out_path: Output DXF path
        dpi: Resolution in DPI

    Returns:
        Path to generated DXF
    """
    vectorizer = Vectorizer(dpi=dpi)
    return vectorizer.process_plan(plan, image_path, out_path)
