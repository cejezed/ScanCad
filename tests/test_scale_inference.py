"""
Test suite for scale_inference module.
Tests dimension parsing, scale inference, and validation.
"""

import pytest
from app.scale_inference import (
    parse_dimension_text_to_mm,
    get_dimension_line_length_px,
    infer_scale_from_plan,
    validate_inferred_scale,
)


class TestParseDimensionText:
    """Tests for dimension text parsing."""

    def test_parse_plain_mm(self):
        # Plain numbers >100 are interpreted as mm, <=100 as meters
        assert parse_dimension_text_to_mm("1306") == 1306.0  # >100 → mm
        assert parse_dimension_text_to_mm("100") == 100000.0  # 100 not >100 → meters → *1000

    def test_parse_mm_explicit(self):
        assert parse_dimension_text_to_mm("1306 mm") == 1306
        assert parse_dimension_text_to_mm("100mm") == 100

    def test_parse_meters_comma(self):
        assert parse_dimension_text_to_mm("7,20 m") == 7200
        assert parse_dimension_text_to_mm("1,3 m") == 1300

    def test_parse_meters_dot(self):
        assert parse_dimension_text_to_mm("7.20 m") == 7200
        assert parse_dimension_text_to_mm("1.3 m") == 1300

    def test_parse_cm(self):
        assert parse_dimension_text_to_mm("130.6 cm") == 1306
        assert parse_dimension_text_to_mm("100 cm") == 1000

    def test_parse_invalid(self):
        assert parse_dimension_text_to_mm("") is None
        assert parse_dimension_text_to_mm("abc") is None
        assert parse_dimension_text_to_mm(None) is None

    def test_parse_dutch_formats(self):
        # Common Dutch formats
        assert parse_dimension_text_to_mm("9,90 m2") == 9900
        assert parse_dimension_text_to_mm("7 m2") == 7000


class TestDimensionLineLength:
    """Tests for dimension line length calculation."""

    def test_horizontal_line(self):
        assert get_dimension_line_length_px([0, 0, 100, 0]) == 100

    def test_vertical_line(self):
        assert get_dimension_line_length_px([0, 0, 0, 100]) == 100

    def test_diagonal_line(self):
        result = get_dimension_line_length_px([0, 0, 100, 100])
        assert abs(result - 141.42) < 0.1

    def test_negative_coords(self):
        assert get_dimension_line_length_px([-50, -50, 50, 50]) == pytest.approx(141.42, 0.1)


class TestScaleInference:
    """Tests for scale inference from plan."""

    def test_single_dimension(self):
        plan = {
            "features": [
                {
                    "id": "dim_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],  # 100px wide
                    "conf": 0.9,
                    "metadata": {"dimension": "100 mm"},  # 100mm
                },
            ]
        }
        scale = infer_scale_from_plan(plan)
        assert abs(scale - 1.0) < 0.01  # 1 mm per pixel

    def test_multiple_dimensions_median(self):
        plan = {
            "features": [
                {
                    "id": "dim_001",
                    "label": "dimension_line",
                    "box": [0, 0, 1000, 0],
                    "conf": 0.9,
                    "metadata": {"dimension": "100 mm"},  # 0.1 mm/px
                },
                {
                    "id": "dim_002",
                    "label": "dimension_line",
                    "box": [0, 0, 2000, 0],
                    "conf": 0.9,
                    "metadata": {"dimension": "200 mm"},  # 0.1 mm/px
                },
                {
                    "id": "dim_003",
                    "label": "dimension_line",
                    "box": [0, 0, 3000, 0],
                    "conf": 0.9,
                    "metadata": {"dimension": "300 mm"},  # 0.1 mm/px
                },
            ]
        }
        scale = infer_scale_from_plan(plan)
        assert abs(scale - 0.1) < 0.01

    def test_no_dimensions(self):
        plan = {"features": []}
        default = 0.085
        scale = infer_scale_from_plan(plan, default_px_to_mm=default)
        assert scale == default

    def test_low_confidence_ignored(self):
        plan = {
            "features": [
                {
                    "id": "dim_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],
                    "conf": 0.5,  # Below threshold
                    "metadata": {"dimension": "100 mm"},
                },
            ]
        }
        default = 0.085
        scale = infer_scale_from_plan(plan, min_dimension_confidence=0.7, default_px_to_mm=default)
        assert scale == default


class TestScaleValidation:
    """Tests for scale validation."""

    def test_valid_scale(self):
        plan = {
            "features": [
                {
                    "id": "dim_001",
                    "label": "dimension_line",
                    "box": [0, 0, 1000, 0],
                    "conf": 0.9,
                    "metadata": {"dimension": "100 mm"},
                },
            ]
        }
        scale = 0.1  # 1000px = 100mm
        assert validate_inferred_scale(plan, scale, tolerance_percent=20)

    def test_invalid_scale(self):
        plan = {
            "features": [
                {
                    "id": "dim_001",
                    "label": "dimension_line",
                    "box": [0, 0, 1000, 0],
                    "conf": 0.9,
                    "metadata": {"dimension": "100 mm"},
                },
            ]
        }
        scale = 0.5  # Wrong scale (1000px = 500mm instead of 100mm)
        assert not validate_inferred_scale(plan, scale, tolerance_percent=20)
