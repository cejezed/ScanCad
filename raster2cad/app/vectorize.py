"""
Hybrid CV + DXF vectorization engine.
Processes plan JSON and image to generate DXF output.
Integrates advanced modules for preprocessing, scaling, geometry cleanup, and analysis.
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
from .scale_inference import infer_scale_from_plan
from .noise_cleaning import prepare_for_line_detection
from .geometry_postprocess import postprocess_segments
from .rooms import detect_rooms_from_segments, rooms_to_dict
from .dimensions import extract_dimensions, validate_dimensions, dimensions_to_dict
from .plan_graph import build_room_graph, analyze_connectivity
from .overlay import draw_overlay, draw_overlay_with_categories

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
    """Main vectorization engine with advanced preprocessing and analysis."""

    def __init__(
        self,
        dpi: int = 300,
        snap_tolerance_px: float = 5.0,
        enable_preprocessing: bool = True,
        enable_scale_inference: bool = True,
        enable_room_detection: bool = True,
        enable_dimension_extraction: bool = True,
        enable_overlay: bool = False,
        overlay_path: Optional[str] = None,
    ):
        self.dpi = dpi
        self.snap_tolerance_px = snap_tolerance_px
        self.enable_preprocessing = enable_preprocessing
        self.enable_scale_inference = enable_scale_inference
        self.enable_room_detection = enable_room_detection
        self.enable_dimension_extraction = enable_dimension_extraction
        self.enable_overlay = enable_overlay
        self.overlay_path = overlay_path

        self.wall_segments: List[WallSegment] = []
        self.detected_texts: List[Dict[str, Any]] = []
        self.detected_symbols: List[Dict[str, Any]] = []

        # New module outputs
        self.inferred_px_to_mm: Optional[float] = None
        self.detected_rooms: List[Any] = []
        self.detected_dimensions: List[Any] = []
        self.plan_graph: Optional[Any] = None
        self.connectivity_analysis: Optional[Dict[str, Any]] = None

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

        # **Phase 1: Preprocessing**
        if self.enable_preprocessing:
            try:
                logger.info("Applying image preprocessing...")
                image = prepare_for_line_detection(image)
            except Exception as e:
                logger.warning(f"Preprocessing failed: {e}. Continuing without preprocessing.")

        # **Phase 2: Scale Inference**
        px_to_mm = px_to_dxf_units(1.0, self.dpi)  # Default from DPI
        if self.enable_scale_inference:
            try:
                logger.info("Inferring scale from dimension lines...")
                inferred_scale = infer_scale_from_plan(plan, default_px_to_mm=px_to_mm)
                if inferred_scale:
                    px_to_mm = inferred_scale
                    self.inferred_px_to_mm = inferred_scale
                    logger.info(f"Inferred scale: {px_to_mm:.4f} mm/px")
            except Exception as e:
                logger.warning(f"Scale inference failed: {e}. Using default DPI-based scale.")

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

        # **Phase 3: Advanced Geometry Postprocessing**
        wall_segments_raw = [(s.x1, s.y1, s.x2, s.y2) for s in self.wall_segments]
        try:
            logger.info("Applying advanced geometry postprocessing...")
            wall_segments_cleaned = postprocess_segments(wall_segments_raw)
            # Reconstruct WallSegment objects
            self.wall_segments = [
                WallSegment(x1, y1, x2, y2) for x1, y1, x2, y2 in wall_segments_cleaned
            ]
            logger.info(f"Cleaned segments: {len(wall_segments_raw)} → {len(wall_segments_cleaned)}")
        except Exception as e:
            logger.warning(f"Geometry postprocessing failed: {e}. Using original segments.")

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

        # **Phase 4: Room Detection**
        if self.enable_room_detection and self.wall_segments:
            try:
                logger.info("Detecting rooms from wall segments...")
                wall_segments_world = [
                    (s.x1 * px_to_mm, s.y1 * px_to_mm, s.x2 * px_to_mm, s.y2 * px_to_mm)
                    for s in self.wall_segments
                ]
                self.detected_rooms = detect_rooms_from_segments(
                    wall_segments_world, px_to_mm=1.0, plan=plan
                )
                if self.detected_rooms:
                    logger.info(f"Detected {len(self.detected_rooms)} rooms")
                    # Add rooms to DXF
                    try:
                        from .rooms import create_dxf_rooms
                        create_dxf_rooms(dwg, msp, self.detected_rooms)
                    except Exception as e:
                        logger.warning(f"Could not add rooms to DXF: {e}")
            except Exception as e:
                logger.warning(f"Room detection failed: {e}")

        # **Phase 5: Dimension Extraction**
        if self.enable_dimension_extraction:
            try:
                logger.info("Extracting dimensions...")
                self.detected_dimensions = extract_dimensions(plan, px_to_mm=px_to_mm)
                if self.detected_dimensions:
                    valid_dims, suspicious_dims = validate_dimensions(
                        self.detected_dimensions
                    )
                    logger.info(f"Extracted {len(valid_dims)} valid, {len(suspicious_dims)} suspicious dimensions")
                    # Add dimensions to DXF
                    try:
                        from .dimensions import create_dxf_dimensions
                        create_dxf_dimensions(dwg, msp, valid_dims)
                    except Exception as e:
                        logger.warning(f"Could not add dimensions to DXF: {e}")
            except Exception as e:
                logger.warning(f"Dimension extraction failed: {e}")

        # **Phase 6: Spatial Topology Analysis**
        if self.enable_room_detection and self.detected_rooms:
            try:
                logger.info("Analyzing spatial topology...")
                self.plan_graph = build_room_graph(
                    rooms_to_dict(self.detected_rooms), plan
                )
                self.connectivity_analysis = analyze_connectivity(self.plan_graph)
                logger.info(f"Topology: {self.connectivity_analysis.get('total_rooms', 0)} rooms, "
                           f"{self.connectivity_analysis.get('total_connections', 0)} connections")
            except Exception as e:
                logger.warning(f"Topology analysis failed: {e}")

        # **Phase 7: Optional Overlay Visualization**
        if self.enable_overlay and self.overlay_path:
            try:
                logger.info("Creating debug overlay...")
                draw_overlay_with_categories(image_path, plan, self.overlay_path)
                logger.info(f"Overlay saved to {self.overlay_path}")
            except Exception as e:
                logger.warning(f"Overlay creation failed: {e}")

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
        """Vectorize wall structures from bounding box coordinates.

        OpenAI detects walls as rectangular boxes. We convert these directly to
        DXF line segments without CV line detection (which fails on thin walls).
        """
        x1, y1, x2, y2 = [int(v) for v in feature.box]

        # Ensure valid box
        if x2 <= x1 or y2 <= y1:
            return

        width = x2 - x1
        height = y2 - y1

        # Determine if wall is horizontal or vertical based on aspect ratio
        # Horizontal wall: width >> height
        # Vertical wall: height >> width
        is_horizontal = width > height * 2
        is_vertical = height > width * 2

        if not (is_horizontal or is_vertical):
            # Box is too square-ish, skip it (likely noise)
            logger.debug(f"Skipping roughly-square wall box {feature.id}: {width}x{height}")
            return

        if is_horizontal:
            # Horizontal wall: draw line across the middle
            y_mid = (y1 + y2) / 2
            segment = WallSegment(x1, y_mid, x2, y_mid)
        else:
            # Vertical wall: draw line down the middle
            x_mid = (x1 + x2) / 2
            segment = WallSegment(x_mid, y1, x_mid, y2)

        self.wall_segments.append(segment)
        logger.debug(f"Added wall segment from box {feature.id}: ({segment.x1}, {segment.y1}) → ({segment.x2}, {segment.y2})")

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
