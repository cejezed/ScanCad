"""
Test suite for plan overlay visualization module.
Tests feature overlay drawing and comparison visualizations.
"""

import pytest
import tempfile
import os
from pathlib import Path
from app.overlay import (
    FEATURE_COLORS,
    draw_overlay,
    _categorize_features,
    _format_category_summary,
)


class TestFeatureColors:
    """Tests for feature color definitions."""

    def test_feature_colors_exist(self):
        """Test that color map contains expected feature types."""
        expected_labels = [
            "wall_structure",
            "text",
            "symbol",
            "dimension_line",
            "region",
            "noise",
        ]

        for label in expected_labels:
            assert label in FEATURE_COLORS
            color = FEATURE_COLORS[label]
            assert isinstance(color, tuple)
            assert len(color) == 3  # RGB
            assert all(0 <= c <= 255 for c in color)

    def test_default_color(self):
        """Test that default color exists."""
        assert "default" in FEATURE_COLORS
        color = FEATURE_COLORS["default"]
        assert isinstance(color, tuple)
        assert len(color) == 3

    def test_color_values_in_range(self):
        """Test that all colors are valid BGR values."""
        for label, color in FEATURE_COLORS.items():
            assert all(isinstance(c, int) for c in color)
            assert all(0 <= c <= 255 for c in color)


class TestFeatureCategorization:
    """Tests for feature categorization."""

    def test_categorize_empty_plan(self):
        """Test categorizing an empty plan."""
        plan = {"features": []}
        categories = _categorize_features(plan)
        assert categories == {}

    def test_categorize_single_feature(self):
        """Test categorizing a single feature."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "wall_structure",
                    "box": [0, 0, 100, 100],
                }
            ]
        }

        categories = _categorize_features(plan)

        assert "wall_structure" in categories
        assert len(categories["wall_structure"]) == 1
        assert categories["wall_structure"][0]["id"] == "f_001"

    def test_categorize_multiple_features(self):
        """Test categorizing multiple features."""
        plan = {
            "features": [
                {"label": "wall_structure", "box": [0, 0, 100, 100]},
                {"label": "wall_structure", "box": [100, 0, 200, 100]},
                {"label": "text", "box": [50, 50, 80, 70]},
                {"label": "symbol", "box": [150, 150, 170, 170]},
            ]
        }

        categories = _categorize_features(plan)

        assert len(categories) == 3
        assert len(categories["wall_structure"]) == 2
        assert len(categories["text"]) == 1
        assert len(categories["symbol"]) == 1

    def test_categorize_unknown_label(self):
        """Test categorizing features with unknown labels."""
        plan = {
            "features": [
                {"label": "unknown_type", "box": [0, 0, 50, 50]},
                {"label": "another_unknown", "box": [100, 100, 150, 150]},
            ]
        }

        categories = _categorize_features(plan)

        assert "unknown_type" in categories
        assert "another_unknown" in categories

    def test_categorize_missing_label(self):
        """Test features without label field."""
        plan = {
            "features": [
                {"id": "f_001", "box": [0, 0, 50, 50]},  # No label
                {"label": "wall_structure", "box": [100, 100, 150, 150]},
            ]
        }

        categories = _categorize_features(plan)

        assert "unknown" in categories
        assert "wall_structure" in categories


class TestCategorySummary:
    """Tests for category summary formatting."""

    def test_format_empty_categories(self):
        """Test formatting empty category summary."""
        summary = _format_category_summary({})

        assert "Feature Summary:" in summary
        assert "Total: 0" in summary

    def test_format_single_category(self):
        """Test formatting a single category."""
        categories = {
            "wall_structure": [
                {"id": "f_001"},
                {"id": "f_002"},
            ]
        }

        summary = _format_category_summary(categories)

        assert "wall_structure: 2" in summary
        assert "Total: 2" in summary

    def test_format_multiple_categories(self):
        """Test formatting multiple categories."""
        categories = {
            "wall_structure": [{"id": "f_001"}, {"id": "f_002"}],
            "text": [{"id": "f_003"}, {"id": "f_004"}, {"id": "f_005"}],
            "symbol": [{"id": "f_006"}],
        }

        summary = _format_category_summary(categories)

        assert "wall_structure: 2" in summary
        assert "text: 3" in summary
        assert "symbol: 1" in summary
        assert "Total: 6" in summary

    def test_format_sorted_categories(self):
        """Test that categories are sorted in summary."""
        categories = {
            "text": [{"id": "f_001"}],
            "wall_structure": [{"id": "f_002"}],
            "symbol": [{"id": "f_003"}],
        }

        summary = _format_category_summary(categories)
        lines = summary.split("\n")

        # Skip header, check category lines are sorted
        category_lines = [l for l in lines[1:-1] if ":" in l]
        assert category_lines[0].startswith("symbol")
        assert category_lines[1].startswith("text")
        assert category_lines[2].startswith("wall_structure")


class TestOverlayDrawing:
    """Tests for overlay drawing functionality."""

    def test_draw_overlay_empty_plan(self):
        """Test drawing overlay on empty plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temporary test image
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {"features": []}
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_single_feature(self):
        """Test drawing overlay with a single feature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((200, 200, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 100, 100],
                        "conf": 0.95,
                    }
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_multiple_features(self):
        """Test drawing overlay with multiple features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((300, 300, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 100, 100],
                        "conf": 0.95,
                    },
                    {
                        "id": "f_002",
                        "label": "text",
                        "box": [150, 150, 250, 180],
                        "conf": 0.90,
                        "metadata": {"content": "Room 1"},
                    },
                    {
                        "id": "f_003",
                        "label": "symbol",
                        "box": [50, 200, 80, 230],
                        "conf": 0.85,
                    },
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_missing_image(self):
        """Test handling of missing image file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "nonexistent.png")
            plan = {"features": []}
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert not success

    def test_draw_overlay_clamp_bounds(self):
        """Test that feature boxes are clamped to image bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            # Feature extends beyond image bounds
            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [-50, -50, 150, 150],  # Extends beyond 100x100
                        "conf": 0.95,
                    }
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_feature_filter(self):
        """Test filtering features by label."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((200, 200, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 100, 100],
                        "conf": 0.95,
                    },
                    {
                        "id": "f_002",
                        "label": "text",
                        "box": [120, 120, 180, 180],
                        "conf": 0.90,
                    },
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            # Only draw wall_structure features
            success = draw_overlay(
                image_path, plan, out_path, feature_filter=["wall_structure"]
            )

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_transparency(self):
        """Test drawing overlay with different transparency levels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 80, 80],
                        "conf": 0.95,
                    }
                ]
            }

            # Test different alpha values
            for alpha in [0.1, 0.3, 0.5, 0.8]:
                out_path = os.path.join(tmpdir, f"overlay_alpha{alpha}.png")
                success = draw_overlay(image_path, plan, out_path, alpha=alpha)
                assert success
                assert os.path.exists(out_path)

    def test_draw_overlay_no_confidence_display(self):
        """Test drawing overlay without showing confidence scores."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 80, 80],
                        "conf": 0.95,
                    }
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(
                image_path, plan, out_path, show_confidence=False, show_ids=False
            )

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_text_content(self):
        """Test that text feature content is included in overlay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((200, 200, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "text",
                        "box": [50, 50, 150, 100],
                        "conf": 0.95,
                        "metadata": {"content": "Woonkamer 25m²"},
                    }
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_invalid_box(self):
        """Test handling of invalid bounding boxes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [50, 50, 50, 80],  # x1 == x2, invalid
                        "conf": 0.95,
                    },
                    {
                        "id": "f_002",
                        "label": "text",
                        "box": [10, 20, 30],  # Only 3 values, invalid
                        "conf": 0.90,
                    },
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            # Should handle gracefully
            assert success
            assert os.path.exists(out_path)

    def test_draw_overlay_different_line_thickness(self):
        """Test drawing overlay with different line thicknesses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 80, 80],
                        "conf": 0.95,
                    }
                ]
            }

            # Test different thicknesses
            for thickness in [1, 2, 4]:
                out_path = os.path.join(tmpdir, f"overlay_thick{thickness}.png")
                success = draw_overlay(
                    image_path, plan, out_path, line_thickness=thickness
                )
                assert success
                assert os.path.exists(out_path)


class TestOverlayEdgeCases:
    """Tests for overlay edge cases."""

    def test_overlay_with_zero_confidence(self):
        """Test drawing features with zero confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "wall_structure",
                        "box": [20, 20, 80, 80],
                        "conf": 0.0,
                    }
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)

    def test_overlay_with_missing_metadata(self):
        """Test drawing features with missing metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import cv2
            import numpy as np

            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            image_path = os.path.join(tmpdir, "test.png")
            cv2.imwrite(image_path, test_image)

            plan = {
                "features": [
                    {
                        "id": "f_001",
                        "label": "text",
                        "box": [20, 20, 80, 80],
                        "conf": 0.95,
                        # No metadata
                    }
                ]
            }
            out_path = os.path.join(tmpdir, "overlay.png")

            success = draw_overlay(image_path, plan, out_path)

            assert success
            assert os.path.exists(out_path)
