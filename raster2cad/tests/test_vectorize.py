"""
Tests for vectorization module.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import cv2
import pytest

from app.plan_contract import Plan, Feature
from app.vectorize import Vectorizer, WallSegment, px_to_dxf_units, process_plan


class TestWallSegment:
    """Test WallSegment class."""

    def test_segment_creation(self):
        """Test creating a wall segment."""
        seg = WallSegment(0, 0, 10, 0, thickness=0.2)
        assert seg.x1 == 0
        assert seg.y1 == 0
        assert seg.x2 == 10
        assert seg.y2 == 0
        assert seg.thickness == 0.2

    def test_segment_length(self):
        """Test segment length calculation."""
        seg = WallSegment(0, 0, 3, 4)
        assert seg.length() == 5.0

    def test_segment_horizontal(self):
        """Test horizontal segment detection."""
        seg_h = WallSegment(0, 5, 10, 5)
        assert seg_h.is_horizontal()

    def test_segment_vertical(self):
        """Test vertical segment detection."""
        seg_v = WallSegment(5, 0, 5, 10)
        assert seg_v.is_vertical()


class TestUnitConversion:
    """Test pixel to DXF unit conversion."""

    def test_px_to_dxf_default(self):
        """Test pixel conversion with default DPI."""
        # 1 inch = 25.4 mm, 300 DPI = 300 pixels per inch
        # So 300 pixels = 25.4 mm = 1.0 DXF unit
        result = px_to_dxf_units(300, dpi=300)
        assert abs(result - 25.4) < 0.1

    def test_px_to_dxf_150dpi(self):
        """Test pixel conversion with 150 DPI."""
        # 150 pixels at 150 DPI = 1 inch = 25.4 mm
        result = px_to_dxf_units(150, dpi=150)
        assert abs(result - 25.4) < 0.1


class TestPlan:
    """Test Plan contract validation."""

    def test_plan_from_dict(self):
        """Test creating Plan from dict."""
        data = {
            "image_source": "test.jpg",
            "image_dims": [1024, 768],
            "dpi": 300,
            "features": [
                {
                    "id": "wall_001",
                    "label": "wall_structure",
                    "box": [100, 100, 200, 110],
                    "conf": 0.95,
                    "metadata": {},
                }
            ],
        }
        plan = Plan.from_dict(data)
        assert plan.image_source == "test.jpg"
        assert plan.image_dims == (1024, 768)
        assert len(plan.features) == 1
        assert plan.features[0].label == "wall_structure"

    def test_plan_to_json(self):
        """Test serializing Plan to JSON."""
        feature = Feature(
            id="test_001",
            label="text",
            box=(0, 0, 100, 50),
            conf=0.9,
            metadata={"content": "ROOM A"},
        )
        plan = Plan(
            image_source="test.jpg",
            image_dims=(1024, 768),
            dpi=300,
            features=[feature],
        )
        json_str = plan.to_json()
        data = json.loads(json_str)
        assert data["image_source"] == "test.jpg"
        assert len(data["features"]) == 1


class TestVectorizer:
    """Test Vectorizer class."""

    def test_vectorizer_creation(self):
        """Test creating a vectorizer."""
        vec = Vectorizer(dpi=300, snap_tolerance_px=5.0)
        assert vec.dpi == 300
        assert vec.snap_tolerance_px == 5.0
        assert len(vec.wall_segments) == 0

    def test_are_colinear(self):
        """Test colinearity check."""
        vec = Vectorizer()
        seg1 = WallSegment(0, 0, 10, 0)
        seg2 = WallSegment(10, 0, 20, 0)
        assert vec._are_colinear(seg1, seg2)

    def test_are_adjacent(self):
        """Test adjacency check."""
        vec = Vectorizer()
        seg1 = WallSegment(0, 0, 10, 0)
        seg2 = WallSegment(10, 0.5, 20, 0.5)
        assert vec._are_adjacent(seg1, seg2)

    def test_process_plan_with_image(self):
        """Test processing a plan with image."""
        # Create a simple test image (white background with black line)
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test image
            img = np.ones((200, 200, 3), dtype=np.uint8) * 255
            # Draw a black line (wall)
            cv2.line(img, (50, 100), (150, 100), (0, 0, 0), 2)
            img_path = Path(tmpdir) / "test.jpg"
            cv2.imwrite(str(img_path), img)

            # Create test plan
            plan_dict = {
                "image_source": "test.jpg",
                "image_dims": [200, 200],
                "dpi": 300,
                "features": [
                    {
                        "id": "wall_001",
                        "label": "wall_structure",
                        "box": [40, 90, 160, 110],
                        "conf": 0.95,
                        "metadata": {},
                    }
                ],
            }

            # Process
            output_path = Path(tmpdir) / "output.dxf"
            result = process_plan(plan_dict, str(img_path), str(output_path))

            # Verify output
            assert Path(result).exists()
            assert result.endswith(".dxf")


class TestFeatureTypes:
    """Test different feature types."""

    def test_text_feature(self):
        """Test text feature creation."""
        feature = Feature(
            id="text_001",
            label="text",
            box=(10, 10, 100, 50),
            conf=0.9,
            metadata={"content": "LIVING ROOM", "rotation_deg": 0},
        )
        assert feature.label == "text"
        assert feature.metadata["content"] == "LIVING ROOM"

    def test_symbol_feature(self):
        """Test symbol feature creation."""
        feature = Feature(
            id="sym_001",
            label="symbol",
            box=(100, 100, 120, 120),
            conf=0.85,
            metadata={"symbol_type": "door"},
        )
        assert feature.label == "symbol"
        assert feature.metadata["symbol_type"] == "door"

    def test_invalid_label(self):
        """Test that invalid label raises error."""
        with pytest.raises(ValueError):
            Feature(
                id="invalid",
                label="invalid_type",
                box=(0, 0, 10, 10),
                conf=0.9,
            )

    def test_invalid_confidence(self):
        """Test that invalid confidence raises error."""
        with pytest.raises(ValueError):
            Feature(
                id="test",
                label="wall_structure",
                box=(0, 0, 10, 10),
                conf=1.5,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
