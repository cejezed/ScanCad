"""
Test suite for geometry_postprocess module.
Tests snapping, merging, orthogonalization, and cleanup.
"""

import pytest
from app.geometry_postprocess import (
    snap_points,
    merge_colinear_segments,
    orthogonalize_segments,
    remove_duplicate_segments,
    postprocess_segments,
    Point,
    segment_length,
    segment_angle,
    angle_between,
)


class TestPoint:
    """Tests for Point class."""

    def test_distance_calculation(self):
        p1 = Point(0, 0)
        p2 = Point(3, 4)
        assert p1.distance_to(p2) == 5.0

    def test_angle_to_other(self):
        p1 = Point(0, 0)
        p2 = Point(1, 0)
        assert p1.angle_to(p2) == 0  # East

    def test_point_equality(self):
        p1 = Point(10.0, 20.0)
        p2 = Point(10.001, 20.001)
        assert p1 == p2  # Within tolerance

    def test_point_hash(self):
        p1 = Point(10.0, 20.0)
        p2 = Point(10.0, 20.0)
        assert hash(p1) == hash(p2)


class TestSegmentUtilities:
    """Tests for segment utility functions."""

    def test_segment_length_horizontal(self):
        assert segment_length((0, 0, 100, 0)) == 100

    def test_segment_length_vertical(self):
        assert segment_length((0, 0, 0, 100)) == 100

    def test_segment_angle_horizontal(self):
        assert segment_angle((0, 0, 100, 0)) == 0

    def test_segment_angle_vertical(self):
        angle = segment_angle((0, 0, 0, 100))
        assert abs(angle - 90) < 0.1

    def test_angle_between(self):
        assert angle_between(0, 5) == 5
        assert angle_between(0, 95) == 85  # Normalized
        assert angle_between(0, 180) == 0  # Opposite angles are same


class TestSnapPoints:
    """Tests for endpoint snapping."""

    def test_snap_close_endpoints(self):
        segments = [
            (0, 0, 100, 0),
            (100, 1, 200, 0),  # Close to first segment's end
        ]
        snapped = snap_points(segments, snap_tolerance_px=2.0)
        assert len(snapped) == 2
        # Both should have endpoint around (100, 0)
        assert snapped[0][2] == snapped[1][0]

    def test_snap_no_effect(self):
        segments = [
            (0, 0, 100, 0),
            (200, 0, 300, 0),
        ]
        snapped = snap_points(segments, snap_tolerance_px=2.0)
        assert len(snapped) == 2
        assert snapped[0] == segments[0]
        assert snapped[1] == segments[1]

    def test_snap_multiple_close(self):
        segments = [
            (0, 0, 100, 0),
            (100.5, 0.5, 200, 0),
            (99.5, -0.5, 150, 100),
        ]
        snapped = snap_points(segments, snap_tolerance_px=1.5)
        # All should snap to centroid around (100, 0)
        assert len(snapped) == 3


class TestMergeColinear:
    """Tests for colinear segment merging."""

    def test_merge_adjacent_horizontal(self):
        segments = [
            (0, 0, 100, 0),
            (102, 0, 200, 0),  # Close to previous
        ]
        merged = merge_colinear_segments(segments, angle_tol_deg=5, gap_tol_px=5)
        assert len(merged) == 1  # Should merge into one

    def test_no_merge_parallel(self):
        segments = [
            (0, 0, 100, 0),
            (0, 10, 100, 10),  # Parallel but separate
        ]
        merged = merge_colinear_segments(segments, angle_tol_deg=5, gap_tol_px=5)
        assert len(merged) == 2  # Should not merge

    def test_merge_different_angles(self):
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),  # Perpendicular
        ]
        merged = merge_colinear_segments(segments, angle_tol_deg=5, gap_tol_px=5)
        assert len(merged) == 2  # Should not merge


class TestOrthogonalize:
    """Tests for orthogonalization."""

    def test_snap_to_horizontal(self):
        segments = [
            (0, 2, 100, -1),  # Almost horizontal
        ]
        ortho = orthogonalize_segments(segments, angle_snap_deg=5)
        # Should snap to perfectly horizontal
        assert ortho[0][1] == ortho[0][3]

    def test_snap_to_vertical(self):
        segments = [
            (2, 0, -1, 100),  # Almost vertical
        ]
        ortho = orthogonalize_segments(segments, angle_snap_deg=5)
        # Should snap to perfectly vertical
        assert ortho[0][0] == ortho[0][2]

    def test_no_snap_diagonal(self):
        segments = [
            (0, 0, 100, 100),  # 45 degrees
        ]
        ortho = orthogonalize_segments(segments, angle_snap_deg=5)
        # Should not change (too far from cardinal)
        assert ortho[0] == segments[0]


class TestRemoveDuplicates:
    """Tests for duplicate segment removal."""

    def test_remove_exact_duplicates(self):
        segments = [
            (0, 0, 100, 100),
            (0, 0, 100, 100),  # Exact duplicate
        ]
        unique = remove_duplicate_segments(segments)
        assert len(unique) == 1

    def test_remove_reversed_duplicates(self):
        segments = [
            (0, 0, 100, 100),
            (100, 100, 0, 0),  # Reversed
        ]
        unique = remove_duplicate_segments(segments)
        assert len(unique) == 1

    def test_keep_different(self):
        segments = [
            (0, 0, 100, 0),
            (0, 0, 0, 100),
        ]
        unique = remove_duplicate_segments(segments)
        assert len(unique) == 2


class TestPostprocessPipeline:
    """Tests for complete postprocessing pipeline."""

    def test_pipeline_simple(self):
        segments = [
            (0, 0, 100, 1),    # Almost horizontal
            (100, 1, 200, 0),  # Close continuation
            (200, 0, 200, 100),  # Vertical
        ]
        result = postprocess_segments(segments)
        assert len(result) >= 2  # Should merge some segments

    def test_pipeline_with_duplicates(self):
        segments = [
            (0, 0, 100, 0),
            (0, 0, 100, 0),  # Duplicate
            (100, 0, 200, 0),
        ]
        result = postprocess_segments(segments)
        # All three segments are colinear and should be merged into one
        assert len(result) == 1

    def test_pipeline_empty(self):
        result = postprocess_segments([])
        assert result == []
