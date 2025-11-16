"""
Tests for plan cleanup and normalization functionality.

Tests the infer_floorplan_box and normalize_floorplan_and_walls functions
that correct LLM-generated bounding boxes.
"""

import pytest
from app.plan_cleanup import (
    union_box,
    infer_floorplan_box,
    normalize_floorplan_and_walls,
)


class TestUnionBox:
    """Tests for union_box helper function."""

    def test_union_box_single_box(self):
        """Test union of a single box."""
        boxes = [(10, 20, 100, 200)]
        result = union_box(boxes)
        assert result == (10, 20, 100, 200)

    def test_union_box_multiple_boxes(self):
        """Test union of multiple boxes."""
        boxes = [(10, 20, 100, 200), (50, 30, 150, 180), (5, 10, 110, 210)]
        result = union_box(boxes)
        assert result == (5, 10, 150, 210)

    def test_union_box_empty(self):
        """Test union of empty list."""
        result = union_box([])
        assert result is None

    def test_union_box_overlapping(self):
        """Test union of overlapping boxes."""
        boxes = [(0, 0, 100, 100), (50, 50, 150, 150)]
        result = union_box(boxes)
        assert result == (0, 0, 150, 150)


class TestInferFloorplanBox:
    """Tests for floorplan inference logic."""

    def test_infer_from_text_features(self):
        """Test that floorplan is inferred from text feature bounds."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [100, 100, 200, 150], "conf": 0.9},
                {"id": "t2", "label": "text", "box": [300, 300, 400, 350], "conf": 0.9},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=10)
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        # Should include both text boxes with padding
        assert x1 <= 100 - 10
        assert y1 <= 100 - 10
        assert x2 >= 400 + 10
        assert y2 >= 350 + 10

    def test_infer_ignores_dimension_lines(self):
        """Test that dimension lines are ignored in inference."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [100, 100, 200, 150], "conf": 0.9},
                # Dimension line far outside the main plan
                {"id": "d1", "label": "dimension_line", "box": [10, 1000, 5000, 1100], "conf": 0.9},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=0)
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        # Should NOT include the dimension line
        assert y2 < 1000

    def test_infer_ignores_noise(self):
        """Test that noise features are ignored."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [100, 100, 200, 150], "conf": 0.9},
                {"id": "n1", "label": "noise", "box": [5000, 5000, 6000, 6000], "conf": 0.5},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=0)
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        # Should NOT include noise
        assert x2 < 5000

    def test_infer_includes_symbols(self):
        """Test that symbols are included in inference."""
        plan = {
            "features": [
                {"id": "s1", "label": "symbol", "box": [200, 200, 250, 250], "conf": 0.9, "metadata": {}},
                {"id": "s2", "label": "symbol", "box": [400, 400, 450, 450], "conf": 0.9, "metadata": {}},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=0)
        assert bbox is not None
        # Should enclose both symbols
        x1, y1, x2, y2 = bbox
        assert x1 <= 200
        assert x2 >= 450

    def test_infer_includes_walls(self):
        """Test that wall_structure is included in inference."""
        plan = {
            "features": [
                {"id": "w1", "label": "wall_structure", "box": [50, 50, 500, 500], "conf": 0.9, "metadata": {}},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=0)
        assert bbox is not None
        assert bbox == (50, 50, 500, 500)

    def test_infer_with_padding(self):
        """Test that padding is correctly applied."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [100, 100, 200, 200], "conf": 0.9},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=20)
        assert bbox == (80, 80, 220, 220)

    def test_infer_with_padding_at_edge(self):
        """Test that padding doesn't go negative."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [5, 5, 100, 100], "conf": 0.9},
            ]
        }
        bbox = infer_floorplan_box(plan, padding=10)
        x1, y1, x2, y2 = bbox
        # x1 and y1 should be clamped to 0
        assert x1 == 0
        assert y1 == 0
        assert x2 == 110
        assert y2 == 110

    def test_infer_no_candidates(self):
        """Test inference with no valid features."""
        plan = {
            "features": [
                {"id": "d1", "label": "dimension_line", "box": [10, 10, 100, 100], "conf": 0.9},
            ]
        }
        bbox = infer_floorplan_box(plan)
        assert bbox is None

    def test_infer_empty_features(self):
        """Test inference with empty features list."""
        plan = {"features": []}
        bbox = infer_floorplan_box(plan)
        assert bbox is None

    def test_infer_no_features_key(self):
        """Test inference when features key is missing."""
        plan = {"image_dims": [1024, 768]}
        bbox = infer_floorplan_box(plan)
        assert bbox is None


class TestNormalizeFloorplanAndWalls:
    """Tests for floorplan and wall normalization."""

    def test_normalize_updates_existing_floorplan(self):
        """Test that existing floorplan feature is updated."""
        plan = {
            "features": [
                {"id": "fp1", "label": "floorplan", "box": [50, 50, 200, 200], "conf": 0.9},
                {"id": "t1", "label": "text", "box": [100, 100, 300, 300], "conf": 0.9},
            ]
        }
        result = normalize_floorplan_and_walls(plan)

        # Find the floorplan feature
        floorplan_feature = next(f for f in result["features"] if f["label"] == "floorplan")
        # Should be expanded to include text feature
        x1, y1, x2, y2 = floorplan_feature["box"]
        assert x1 <= 100
        assert y1 <= 100
        assert x2 >= 300
        assert y2 >= 300

    def test_normalize_creates_floorplan_if_missing(self):
        """Test that floorplan is created if not present."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [100, 100, 200, 200], "conf": 0.9},
            ]
        }
        result = normalize_floorplan_and_walls(plan)

        # Should have a floorplan feature now
        floorplans = [f for f in result["features"] if f["label"] == "floorplan"]
        assert len(floorplans) > 0
        floorplan_feature = floorplans[0]
        assert floorplan_feature["id"] == "auto_floorplan"
        assert floorplan_feature["conf"] == 0.99

    def test_normalize_updates_largest_wall(self):
        """Test that largest wall_structure is updated."""
        plan = {
            "features": [
                {"id": "w1", "label": "wall_structure", "box": [100, 100, 200, 200], "conf": 0.9},
                {"id": "w2", "label": "wall_structure", "box": [300, 300, 350, 350], "conf": 0.9},  # Smaller
                {"id": "t1", "label": "text", "box": [120, 120, 350, 350], "conf": 0.9},
            ]
        }
        result = normalize_floorplan_and_walls(plan)

        # Find walls
        walls = [f for f in result["features"] if f["label"] == "wall_structure"]
        # Largest wall should be expanded
        largest_wall = max(walls, key=lambda f: (f["box"][2] - f["box"][0]) * (f["box"][3] - f["box"][1]))
        x1, y1, x2, y2 = largest_wall["box"]
        assert x2 >= 350
        assert y2 >= 350

    def test_normalize_realistic_floor_plan(self):
        """Test normalization with a realistic floor plan structure."""
        plan = {
            "features": [
                {"id": "fp1", "label": "floorplan", "box": [10, 10, 100, 100], "conf": 0.95},
                {"id": "w1", "label": "wall_structure", "box": [15, 15, 95, 95], "conf": 0.94},
                {"id": "s1", "label": "symbol", "box": [40, 40, 60, 60], "conf": 0.9, "metadata": {"symbol_type": "door"}},
                {"id": "t1", "label": "text", "box": [30, 20, 70, 40], "conf": 0.95, "metadata": {"content": "room"}},
                {"id": "t2", "label": "text", "box": [30, 70, 70, 90], "conf": 0.95, "metadata": {"content": "10 m²"}},
            ]
        }
        result = normalize_floorplan_and_walls(plan)

        # Verify structure is preserved
        assert len(result["features"]) >= 5

        # Verify floorplan encloses all semantic features
        floorplan = next(f for f in result["features"] if f["label"] == "floorplan")
        fp_x1, fp_y1, fp_x2, fp_y2 = floorplan["box"]

        for feature in result["features"]:
            if feature["label"] in ["dimension_line", "noise", "north_arrow"]:
                continue
            feat_x1, feat_y1, feat_x2, feat_y2 = feature["box"]
            assert fp_x1 <= feat_x1
            assert fp_y1 <= feat_y1
            assert fp_x2 >= feat_x2
            assert fp_y2 >= feat_y2

    def test_normalize_preserves_metadata(self):
        """Test that normalization preserves feature metadata."""
        plan = {
            "features": [
                {
                    "id": "s1",
                    "label": "symbol",
                    "box": [100, 100, 150, 150],
                    "conf": 0.9,
                    "metadata": {"symbol_type": "door", "swing_direction": "left"},
                },
            ]
        }
        result = normalize_floorplan_and_walls(plan)

        # Find the symbol
        symbol = next(f for f in result["features"] if f["label"] == "symbol")
        assert symbol["metadata"]["symbol_type"] == "door"
        assert symbol["metadata"]["swing_direction"] == "left"

    def test_normalize_with_no_features(self):
        """Test normalization with empty features."""
        plan = {"features": []}
        result = normalize_floorplan_and_walls(plan)
        assert result["features"] == []

    def test_normalize_with_non_list_features(self):
        """Test that non-list features are handled gracefully."""
        plan = {"features": "invalid"}
        result = normalize_floorplan_and_walls(plan)
        assert result["features"] == "invalid"

    def test_normalize_ignores_malformed_boxes(self):
        """Test that features with invalid boxes are skipped during inference."""
        plan = {
            "features": [
                {"id": "t1", "label": "text", "box": [100, 100, 200, 200], "conf": 0.9},
                {"id": "t2", "label": "text", "box": None, "conf": 0.9},  # Invalid
                {"id": "t3", "label": "text", "box": [50, 50], "conf": 0.9},  # Wrong length
            ]
        }
        result = normalize_floorplan_and_walls(plan)

        # Should still create a floorplan from valid boxes
        floorplan = next(f for f in result["features"] if f["label"] == "floorplan")
        assert floorplan is not None
