"""
Tests for wall detection and filtering functionality.

Tests the wall_filter module that detects and filters line segments
matching wall characteristics (thick, straight lines).
"""

import pytest
import numpy as np
import cv2
from raster2cad.app.wall_filter import (
    estimate_line_thickness,
    filter_wall_segments,
    detect_line_segments,
)


class TestEstimateLineThickness:
    """Tests for line thickness estimation."""

    def test_horizontal_thick_line(self):
        """Test thickness estimation for a horizontal thick line."""
        # Create 100x100 image with horizontal thick line (10px height)
        img = np.zeros((100, 100), dtype=np.uint8)
        img[45:55, 10:90] = 255  # 10px thick horizontal line

        thickness = estimate_line_thickness(img, 10, 50, 90, 50, samples=5)

        # Should detect ~10px thickness
        assert 8 <= thickness <= 12

    def test_vertical_thick_line(self):
        """Test thickness estimation for a vertical thick line."""
        # Create 100x100 image with vertical thick line (10px width)
        img = np.zeros((100, 100), dtype=np.uint8)
        img[10:90, 45:55] = 255  # 10px thick vertical line

        thickness = estimate_line_thickness(img, 50, 10, 50, 90, samples=5)

        # Should detect ~10px thickness
        assert 8 <= thickness <= 12

    def test_diagonal_thick_line(self):
        """Test thickness estimation for a diagonal line."""
        # Create 100x100 image with diagonal thick line
        img = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(img, (10, 10), (90, 90), 255, thickness=8)

        thickness = estimate_line_thickness(img, 10, 10, 90, 90, samples=5)

        # Should detect ~8px thickness (allow some variance)
        assert 6 <= thickness <= 12

    def test_thin_line(self):
        """Test thickness estimation for a thin line."""
        # Create 100x100 image with thin line (1px)
        img = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(img, (10, 50), (90, 50), 255, thickness=1)

        thickness = estimate_line_thickness(img, 10, 50, 90, 50, samples=5)

        # Should detect very small thickness
        assert thickness <= 4

    def test_zero_length_line(self):
        """Test with zero-length line (same start and end point)."""
        img = np.zeros((100, 100), dtype=np.uint8)

        thickness = estimate_line_thickness(img, 50, 50, 50, 50, samples=5)

        assert thickness == 0

    def test_line_outside_image_bounds(self):
        """Test with line coordinates outside image bounds."""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[45:55, 10:90] = 255

        # Line extends beyond image bounds - should clamp
        thickness = estimate_line_thickness(img, -10, 50, 110, 50, samples=5)

        # Should still estimate thickness for the portion inside image
        assert thickness > 0

    def test_no_foreground_pixels(self):
        """Test with line in area with no foreground pixels."""
        img = np.zeros((100, 100), dtype=np.uint8)

        thickness = estimate_line_thickness(img, 10, 10, 90, 10, samples=5)

        assert thickness == 0

    def test_single_sample(self):
        """Test with single sample point."""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[45:55, 10:90] = 255

        thickness = estimate_line_thickness(img, 10, 50, 90, 50, samples=1)

        # Should still work with single sample
        assert thickness > 0


class TestFilterWallSegments:
    """Tests for wall segment filtering."""

    def test_filter_by_thickness(self):
        """Test that segments are filtered by thickness."""
        # Create image with thick and thin lines
        img = np.zeros((200, 200), dtype=np.uint8)
        img[50:65, 10:190] = 255  # Thick line (15px)
        cv2.line(img, (10, 100), (190, 100), 255, thickness=2)  # Thin line (2px)

        segments = [
            (10, 57, 190, 57),  # Thick line segment
            (10, 100, 190, 100),  # Thin line segment
        ]

        # Filter: keep thickness >= 10px
        filtered = filter_wall_segments(
            img, segments,
            min_thickness_px=10.0,
            max_thickness_px=50.0,
            min_length_px=30.0
        )

        # Should keep only the thick segment
        assert len(filtered) == 1

    def test_filter_by_length(self):
        """Test that segments are filtered by length."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[50:65, 10:190] = 255  # Long thick line
        img[100:115, 10:40] = 255  # Short thick line

        segments = [
            (10, 57, 190, 57),  # Long segment (180px)
            (10, 107, 40, 107),  # Short segment (30px)
        ]

        # Filter: keep length >= 100px
        filtered = filter_wall_segments(
            img, segments,
            min_thickness_px=5.0,
            max_thickness_px=50.0,
            min_length_px=100.0
        )

        # Should keep only the long segment
        assert len(filtered) == 1
        assert filtered[0] == (10, 57, 190, 57)

    def test_filter_max_thickness(self):
        """Test that very thick segments are filtered out."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[20:80, 10:190] = 255  # Very thick line (60px)

        segments = [(10, 50, 190, 50)]

        # Filter: max thickness 50px
        filtered = filter_wall_segments(
            img, segments,
            min_thickness_px=5.0,
            max_thickness_px=50.0,
            min_length_px=30.0
        )

        # Should filter out the very thick segment
        assert len(filtered) == 0

    def test_filter_empty_segments(self):
        """Test with empty segments list."""
        img = np.zeros((100, 100), dtype=np.uint8)

        filtered = filter_wall_segments(img, [])

        assert filtered == []

    def test_filter_invalid_segment_format(self):
        """Test that invalid segment formats are skipped."""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[45:55, 10:90] = 255

        segments = [
            (10, 50, 90, 50),  # Valid
            (10, 50),  # Invalid: too few values
            None,  # Invalid: None
            [10, 50, 90],  # Invalid: too few values
        ]

        filtered = filter_wall_segments(img, segments, min_thickness_px=5.0)

        # Should keep only valid segment
        assert len(filtered) == 1

    def test_filter_realistic_walls(self):
        """Test with realistic wall-like segments."""
        # Create 600x400 image with rectangle (walls)
        img = np.zeros((400, 600), dtype=np.uint8)

        # Draw thick rectangle (15px thick walls)
        thickness = 15
        # Top wall
        img[40:40+thickness, 50:550] = 255
        # Bottom wall
        img[340:340+thickness, 50:550] = 255
        # Left wall
        img[40:355, 50:50+thickness] = 255
        # Right wall
        img[40:355, 535:535+thickness] = 255

        segments = [
            (50, 47, 550, 47),    # Top wall
            (50, 347, 550, 347),  # Bottom wall
            (57, 40, 57, 355),    # Left wall
            (542, 40, 542, 355),  # Right wall
        ]

        filtered = filter_wall_segments(
            img, segments,
            min_thickness_px=10.0,
            max_thickness_px=30.0,
            min_length_px=100.0
        )

        # Should keep all wall segments
        assert len(filtered) == 4

    def test_filter_preserves_segment_data(self):
        """Test that filtered segments preserve original coordinate data."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[50:65, 10:190] = 255

        original = (10, 57, 190, 57)
        segments = [original]

        filtered = filter_wall_segments(img, segments, min_thickness_px=5.0)

        assert len(filtered) == 1
        assert filtered[0] == original


class TestDetectLineSegments:
    """Tests for line segment detection using Hough transform."""

    def test_detect_horizontal_lines(self):
        """Test detection of horizontal lines."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[50:55, 20:180] = 255  # Horizontal line
        img[150:155, 20:180] = 255  # Another horizontal line

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should detect at least 2 segments
        assert len(segments) >= 2

    def test_detect_vertical_lines(self):
        """Test detection of vertical lines."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[20:180, 50:55] = 255  # Vertical line
        img[20:180, 150:155] = 255  # Another vertical line

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should detect at least 2 segments
        assert len(segments) >= 2

    def test_detect_rectangle(self):
        """Test detection of rectangle (4 lines)."""
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(img, (40, 40), (160, 160), 255, thickness=5)

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should detect 4 or more segments (rectangle has 4 sides, may be split)
        assert len(segments) >= 4

    def test_detect_no_lines(self):
        """Test with blank image (no lines)."""
        img = np.zeros((200, 200), dtype=np.uint8)

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        assert len(segments) == 0

    def test_detect_short_lines_filtered(self):
        """Test that short lines are filtered by min_line_length."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[100:103, 50:80] = 255  # Short line (30px)

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should not detect the short line
        assert len(segments) == 0

    def test_detect_with_gaps(self):
        """Test detection with gaps in lines."""
        img = np.zeros((200, 200), dtype=np.uint8)
        # Dashed line with gaps
        img[100:103, 20:60] = 255
        img[100:103, 70:110] = 255
        img[100:103, 120:160] = 255

        # With large max_gap, should link segments
        segments = detect_line_segments(img, min_line_length=30, max_line_gap=20)

        # Should detect segments (possibly linked)
        assert len(segments) > 0

    def test_detect_diagonal_line(self):
        """Test detection of diagonal line."""
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.line(img, (20, 20), (180, 180), 255, thickness=3)

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should detect at least one segment
        assert len(segments) >= 1

    def test_detect_complex_floor_plan(self):
        """Test detection with complex floor plan structure."""
        img = np.zeros((400, 600), dtype=np.uint8)

        # Outer walls
        cv2.rectangle(img, (50, 50), (550, 350), 255, thickness=10)
        # Internal wall (vertical)
        img[70:330, 295:305] = 255
        # Internal wall (horizontal)
        img[195:205, 70:530] = 255

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should detect multiple segments
        assert len(segments) >= 6

    def test_detect_returns_float_coordinates(self):
        """Test that detected segments have float coordinates."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[100:105, 50:150] = 255

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        if segments:
            x1, y1, x2, y2 = segments[0]
            assert isinstance(x1, float)
            assert isinstance(y1, float)
            assert isinstance(x2, float)
            assert isinstance(y2, float)

    def test_detect_with_float_image(self):
        """Test with float image (should convert to uint8)."""
        img = np.zeros((200, 200), dtype=np.float32)
        img[100:105, 50:150] = 1.0  # Float values 0.0-1.0

        segments = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Should handle conversion and detect line
        assert len(segments) > 0


class TestIntegratedWallDetection:
    """Integration tests combining detection and filtering."""

    def test_full_pipeline_synthetic_floor_plan(self):
        """Test complete pipeline: detect -> filter on synthetic floor plan."""
        # Create realistic floor plan with thick walls
        img = np.zeros((400, 600), dtype=np.uint8)

        # Draw thick walls (15px)
        thickness = 15
        # Outer rectangle
        img[40:40+thickness, 50:550] = 255  # Top
        img[340:340+thickness, 50:550] = 255  # Bottom
        img[40:355, 50:50+thickness] = 255  # Left
        img[40:355, 535:535+thickness] = 255  # Right

        # Add some thin annotation lines (should be filtered out)
        cv2.line(img, (100, 20), (200, 20), 255, thickness=1)

        # Detect all lines
        detected = detect_line_segments(img, min_line_length=50, max_line_gap=10)

        # Filter for walls only
        walls = filter_wall_segments(
            img, detected,
            min_thickness_px=10.0,
            max_thickness_px=30.0,
            min_length_px=100.0
        )

        # Should detect 4 main walls, filtering out thin annotations
        assert len(walls) >= 4
        assert len(walls) <= len(detected)

    def test_pipeline_with_noise(self):
        """Test pipeline with noisy image."""
        img = np.zeros((300, 400), dtype=np.uint8)

        # Main wall
        img[100:115, 50:350] = 255

        # Add noise
        noise = np.random.randint(0, 50, (300, 400), dtype=np.uint8)
        img = cv2.add(img, noise)

        detected = detect_line_segments(img, min_line_length=100, max_line_gap=20)
        walls = filter_wall_segments(img, detected, min_thickness_px=10.0)

        # Should still detect the main wall despite noise
        assert len(walls) >= 1

    def test_pipeline_empty_image(self):
        """Test pipeline with empty image."""
        img = np.zeros((200, 200), dtype=np.uint8)

        detected = detect_line_segments(img)
        walls = filter_wall_segments(img, detected)

        assert len(detected) == 0
        assert len(walls) == 0

    def test_pipeline_preserves_coordinates(self):
        """Test that pipeline preserves coordinate accuracy."""
        img = np.zeros((200, 200), dtype=np.uint8)
        img[95:105, 40:160] = 255  # 10px thick, 120px long horizontal line

        detected = detect_line_segments(img, min_line_length=50, max_line_gap=10)
        walls = filter_wall_segments(img, detected, min_thickness_px=8.0, min_length_px=50.0)

        assert len(walls) > 0

        # Check that coordinates are reasonable
        for x1, y1, x2, y2 in walls:
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            assert length >= 50  # At least min_length


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
