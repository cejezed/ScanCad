"""
Test suite for dimension extraction and reconstruction module.
Tests dimension parsing, validation, and DXF generation.
"""

import pytest
from app.dimensions import (
    Dimension,
    extract_dimensions,
    validate_dimensions,
    dimensions_to_dict,
    summarize_dimensions,
)


class TestDimensionDataclass:
    """Tests for Dimension dataclass."""

    def test_dimension_creation(self):
        dim = Dimension(
            id="dim_001",
            from_mm=(0.0, 0.0),
            to_mm=(100.0, 0.0),
            value_mm=100.0,
            raw_text="100 mm",
            confidence=0.95,
            orientation="horizontal",
        )
        assert dim.id == "dim_001"
        assert dim.value_mm == 100.0
        assert dim.orientation == "horizontal"
        assert dim.confidence == 0.95

    def test_dimension_with_deviation(self):
        dim = Dimension(
            id="dim_002",
            from_mm=(0.0, 0.0),
            to_mm=(100.0, 0.0),
            value_mm=100.0,
            raw_text="100 mm",
            confidence=0.9,
            orientation="horizontal",
            deviation_percent=5.0,
        )
        assert dim.deviation_percent == 5.0

    def test_dimension_defaults(self):
        dim = Dimension(
            id="dim_003",
            from_mm=(0.0, 0.0),
            to_mm=(50.0, 0.0),
            value_mm=50.0,
            raw_text="50",
            confidence=0.8,
            orientation="horizontal",
        )
        assert dim.deviation_percent is None


class TestDimensionExtraction:
    """Tests for dimension extraction from plans."""

    def test_extract_single_dimension(self):
        """Test extracting a single dimension feature."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],
                    "conf": 0.95,
                    "metadata": {"dimension": "100 mm"},
                }
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        assert len(dimensions) == 1
        assert dimensions[0].id == "f_001"
        assert dimensions[0].value_mm == 100.0

    def test_extract_multiple_dimensions(self):
        """Test extracting multiple dimensions."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],
                    "conf": 0.95,
                    "metadata": {"dimension": "100 mm"},
                },
                {
                    "id": "f_002",
                    "label": "dimension_line",
                    "box": [0, 100, 0, 200],
                    "conf": 0.90,
                    "metadata": {"dimension": "5,00 m"},
                },
                {
                    "id": "f_003",
                    "label": "dimension_line",
                    "box": [150, 0, 250, 0],
                    "conf": 0.85,
                    "metadata": {"dimension": "3.5 m"},
                },
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        assert len(dimensions) == 3
        assert dimensions[0].value_mm == 100.0
        assert dimensions[1].value_mm == 5000.0
        assert dimensions[2].value_mm == 3500.0

    def test_filter_by_confidence(self):
        """Test filtering dimensions by minimum confidence."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],
                    "conf": 0.95,
                    "metadata": {"dimension": "100 mm"},
                },
                {
                    "id": "f_002",
                    "label": "dimension_line",
                    "box": [0, 100, 0, 200],
                    "conf": 0.45,  # Below threshold
                    "metadata": {"dimension": "50 mm"},
                },
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0, min_confidence=0.5)

        assert len(dimensions) == 1
        assert dimensions[0].id == "f_001"

    def test_skip_non_dimension_features(self):
        """Test that non-dimension features are skipped."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "wall_structure",
                    "box": [0, 0, 100, 0],
                    "conf": 0.95,
                },
                {
                    "id": "f_002",
                    "label": "dimension_line",
                    "box": [0, 100, 0, 200],
                    "conf": 0.90,
                    "metadata": {"dimension": "50 mm"},
                },
                {
                    "id": "f_003",
                    "label": "text",
                    "box": [150, 0, 200, 20],
                    "conf": 0.85,
                },
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        assert len(dimensions) == 1
        assert dimensions[0].id == "f_002"

    def test_invalid_dimension_text(self):
        """Test handling of invalid dimension text."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],
                    "conf": 0.95,
                    "metadata": {"dimension": "invalid_text"},
                },
                {
                    "id": "f_002",
                    "label": "dimension_line",
                    "box": [0, 100, 0, 200],
                    "conf": 0.90,
                    "metadata": {},  # No dimension field
                },
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        # Invalid dimensions should be filtered out
        assert len(dimensions) == 0

    def test_scale_conversion(self):
        """Test pixel-to-mm scale conversion for dimensions."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 0],
                    "conf": 0.95,
                    "metadata": {"dimension": "100 mm"},
                }
            ]
        }

        # Extract with different scales
        dims_scale1 = extract_dimensions(plan, px_to_mm=1.0)
        dims_scale2 = extract_dimensions(plan, px_to_mm=2.0)

        # The dimension value itself doesn't change (it's from text)
        # but from_mm/to_mm coordinates are scaled
        assert dims_scale1[0].value_mm == 100.0
        assert dims_scale2[0].value_mm == 100.0

        # But coordinates should be scaled
        assert dims_scale2[0].from_mm[0] == dims_scale1[0].from_mm[0] * 2


class TestDimensionOrientation:
    """Tests for dimension orientation detection."""

    def test_horizontal_orientation(self):
        """Test detection of horizontal dimensions."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 50, 200, 52],  # dx > 2*dy
                    "conf": 0.95,
                    "metadata": {"dimension": "200 mm"},
                }
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        assert dimensions[0].orientation == "horizontal"

    def test_vertical_orientation(self):
        """Test detection of vertical dimensions."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [50, 0, 52, 200],  # dy > 2*dx
                    "conf": 0.95,
                    "metadata": {"dimension": "200 mm"},
                }
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        assert dimensions[0].orientation == "vertical"

    def test_diagonal_orientation(self):
        """Test detection of diagonal dimensions."""
        plan = {
            "features": [
                {
                    "id": "f_001",
                    "label": "dimension_line",
                    "box": [0, 0, 100, 100],  # dx ~ dy
                    "conf": 0.95,
                    "metadata": {"dimension": "141 mm"},
                }
            ]
        }

        dimensions = extract_dimensions(plan, px_to_mm=1.0)

        assert dimensions[0].orientation == "diagonal"


class TestDimensionValidation:
    """Tests for dimension validation."""

    def test_validate_dimensions_all_valid(self):
        """Test validation when all dimensions are valid."""
        dimensions = [
            Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.95,
                orientation="horizontal",
                deviation_percent=5.0,
            ),
            Dimension(
                id="d_002",
                from_mm=(0, 100),
                to_mm=(0, 200),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.90,
                orientation="vertical",
                deviation_percent=8.0,
            ),
        ]

        valid, suspicious = validate_dimensions(dimensions, max_deviation_percent=20.0)

        assert len(valid) == 2
        assert len(suspicious) == 0

    def test_validate_dimensions_with_suspicious(self):
        """Test validation with suspicious dimensions."""
        dimensions = [
            Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.95,
                orientation="horizontal",
                deviation_percent=5.0,
            ),
            Dimension(
                id="d_002",
                from_mm=(0, 100),
                to_mm=(0, 200),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.90,
                orientation="vertical",
                deviation_percent=35.0,  # High deviation
            ),
        ]

        valid, suspicious = validate_dimensions(dimensions, max_deviation_percent=20.0)

        assert len(valid) == 1
        assert len(suspicious) == 1
        assert valid[0].id == "d_001"
        assert suspicious[0].id == "d_002"

    def test_validate_no_deviation_data(self):
        """Test validation when deviation is None."""
        dimensions = [
            Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.95,
                orientation="horizontal",
                deviation_percent=None,
            )
        ]

        valid, suspicious = validate_dimensions(dimensions)

        assert len(valid) == 1
        assert len(suspicious) == 0


class TestDimensionSerialization:
    """Tests for dimension serialization."""

    def test_dimensions_to_dict(self):
        """Test converting Dimension objects to dictionaries."""
        dimensions = [
            Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.95,
                orientation="horizontal",
                deviation_percent=5.0,
            ),
            Dimension(
                id="d_002",
                from_mm=(0, 100),
                to_mm=(0, 200),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.90,
                orientation="vertical",
                deviation_percent=None,
            ),
        ]

        result = dimensions_to_dict(dimensions)

        assert len(result) == 2
        assert result[0]["id"] == "d_001"
        assert result[0]["value_mm"] == 100.0
        assert result[0]["orientation"] == "horizontal"
        assert result[1]["deviation_percent"] is None

    def test_summarize_dimensions_empty(self):
        """Test summarizing empty dimension list."""
        summary = summarize_dimensions([])

        assert summary["total"] == 0
        assert summary["horizontal"] == 0
        assert summary["vertical"] == 0
        assert summary["diagonal"] == 0
        assert summary["avg_confidence"] == 0.0

    def test_summarize_dimensions_with_data(self):
        """Test summarizing dimensions with various orientations."""
        dimensions = [
            Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.95,
                orientation="horizontal",
            ),
            Dimension(
                id="d_002",
                from_mm=(0, 100),
                to_mm=(0, 200),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.90,
                orientation="vertical",
            ),
            Dimension(
                id="d_003",
                from_mm=(0, 0),
                to_mm=(100, 100),
                value_mm=141.0,
                raw_text="141 mm",
                confidence=0.85,
                orientation="diagonal",
            ),
        ]

        summary = summarize_dimensions(dimensions)

        assert summary["total"] == 3
        assert summary["horizontal"] == 1
        assert summary["vertical"] == 1
        assert summary["diagonal"] == 1
        assert summary["avg_confidence"] == pytest.approx((0.95 + 0.90 + 0.85) / 3, rel=0.01)
        assert summary["avg_value_mm"] == pytest.approx((100 + 100 + 141) / 3, rel=0.01)

    def test_summarize_mixed_orientations(self):
        """Test summarizing dimensions with only some orientations."""
        dimensions = [
            Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.95,
                orientation="horizontal",
            ),
            Dimension(
                id="d_002",
                from_mm=(50, 0),
                to_mm=(150, 0),
                value_mm=100.0,
                raw_text="100 mm",
                confidence=0.90,
                orientation="horizontal",
            ),
        ]

        summary = summarize_dimensions(dimensions)

        assert summary["total"] == 2
        assert summary["horizontal"] == 2
        assert summary["vertical"] == 0
        assert summary["diagonal"] == 0


class TestDimensionDeviation:
    """Tests for deviation calculation."""

    def test_small_deviation(self):
        """Test dimension with small deviation."""
        dim = Dimension(
            id="d_001",
            from_mm=(0, 0),
            to_mm=(100, 0),
            value_mm=100.0,
            raw_text="100 mm",
            confidence=0.95,
            orientation="horizontal",
            deviation_percent=2.0,
        )

        assert dim.deviation_percent == 2.0
        assert dim.deviation_percent <= 20.0  # Would be valid

    def test_large_deviation(self):
        """Test dimension with large deviation."""
        dim = Dimension(
            id="d_001",
            from_mm=(0, 0),
            to_mm=(100, 0),
            value_mm=100.0,
            raw_text="100 mm",
            confidence=0.95,
            orientation="horizontal",
            deviation_percent=35.0,
        )

        assert dim.deviation_percent == 35.0
        assert dim.deviation_percent > 20.0  # Would be suspicious


class TestDimensionRawText:
    """Tests for raw text preservation."""

    def test_preserve_raw_text(self):
        """Test that raw dimension text is preserved."""
        raw_texts = [
            "100 mm",
            "5,00 m",
            "3.5m",
            "12 cm",
            "2,50m",
        ]

        for raw_text in raw_texts:
            dim = Dimension(
                id="d_001",
                from_mm=(0, 0),
                to_mm=(100, 0),
                value_mm=100.0,
                raw_text=raw_text,
                confidence=0.95,
                orientation="horizontal",
            )

            assert dim.raw_text == raw_text
