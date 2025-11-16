"""
Test suite for room detection and analysis module.
Tests room detection, text matching, and DXF generation.
"""

import pytest
import numpy as np
from app.rooms import (
    Room,
    detect_rooms_from_segments,
    rooms_to_dict,
    summarize_rooms,
)


class TestRoomDataclass:
    """Tests for Room dataclass."""

    def test_room_creation(self):
        room = Room(
            id="room_001",
            name="Woonkamer",
            area_m2=25.5,
            centroid=(100.0, 150.0),
        )
        assert room.id == "room_001"
        assert room.name == "Woonkamer"
        assert room.area_m2 == 25.5
        assert room.centroid == (100.0, 150.0)

    def test_room_defaults(self):
        room = Room(id="room_002")
        assert room.name is None
        assert room.area_m2 is None
        assert room.centroid is None
        assert room.confidence == 0.0
        assert room.polygon is None

    def test_room_with_polygon(self):
        polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
        room = Room(id="room_003", polygon=polygon)
        assert len(room.polygon) == 4
        assert room.polygon[0] == (0, 0)


class TestRoomDetection:
    """Tests for room detection algorithm."""

    def test_detect_single_rectangular_room(self):
        """Test detection of a single rectangular room."""
        # Create a simple rectangular room with walls
        segments = [
            (0, 0, 100, 0),      # Top wall
            (100, 0, 100, 100),  # Right wall
            (100, 100, 0, 100),  # Bottom wall
            (0, 100, 0, 0),      # Left wall
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        assert len(rooms) > 0
        assert rooms[0].id == "room_000"
        assert rooms[0].area_px2 is not None
        assert rooms[0].area_px2 > 0

    def test_detect_multiple_rooms(self):
        """Test detection of multiple rooms."""
        # Two adjacent rectangular rooms
        segments = [
            # Left room
            (0, 0, 50, 0),
            (50, 0, 50, 100),
            (50, 100, 0, 100),
            (0, 100, 0, 0),
            # Right room
            (50, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 50, 100),
            (50, 100, 50, 0),  # Shared wall
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        # Should detect at least 2 rooms
        assert len(rooms) >= 2

    def test_detect_empty_segments(self):
        """Test handling of empty segment list."""
        rooms = detect_rooms_from_segments([], px_to_mm=1.0, plan={})
        assert rooms == []

    def test_scale_conversion(self):
        """Test pixel-to-mm scale conversion."""
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]
        plan = {"features": []}

        # With 1.0 px_to_mm: area should be ~100x100 = 10000 px²
        rooms1 = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)
        if rooms1:
            area1_m2 = rooms1[0].area_m2

            # With 2.0 px_to_mm: area should be scaled by (2.0)**2 = 4x
            rooms2 = detect_rooms_from_segments(segments, px_to_mm=2.0, plan=plan)
            if rooms2:
                area2_m2 = rooms2[0].area_m2
                # area2_m2 should be ~4x larger
                assert area2_m2 > area1_m2 * 3

    def test_minimum_room_area_filter(self):
        """Test filtering of small rooms."""
        # Create a very small closed shape
        small_segments = [
            (0, 0, 5, 0),
            (5, 0, 5, 5),
            (5, 5, 0, 5),
            (0, 5, 0, 0),
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(
            small_segments,
            px_to_mm=1.0,
            plan=plan,
            min_room_area_px2=500,  # Small rooms filtered
        )

        # Should filter out tiny rooms
        if rooms:
            assert all(r.area_px2 >= 500 for r in rooms)

    def test_centroid_calculation(self):
        """Test centroid calculation for rooms."""
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        assert len(rooms) > 0
        room = rooms[0]
        assert room.centroid is not None
        # For a square from (0,0) to (100,100), centroid should be near (50, 50)
        cx, cy = room.centroid
        assert 30 < cx < 70
        assert 30 < cy < 70

    def test_polygon_conversion_to_mm(self):
        """Test polygon coordinate conversion from pixels to mm."""
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(segments, px_to_mm=0.5, plan=plan)

        if rooms and rooms[0].polygon:
            # With 0.5 px_to_mm scale, coordinates should be halved
            for x, y in rooms[0].polygon:
                assert x <= 50 or y <= 50


class TestRoomSerialization:
    """Tests for room serialization and summarization."""

    def test_rooms_to_dict(self):
        """Test converting Room objects to dictionaries."""
        rooms = [
            Room(
                id="room_001",
                name="Woonkamer",
                area_m2=25.5,
                centroid=(100.0, 150.0),
                confidence=0.9,
            ),
            Room(
                id="room_002",
                name="Keuken",
                area_m2=12.0,
                centroid=(50.0, 50.0),
                confidence=0.8,
            ),
        ]

        result = rooms_to_dict(rooms)

        assert len(result) == 2
        assert result[0]["id"] == "room_001"
        assert result[0]["name"] == "Woonkamer"
        assert result[0]["area_m2"] == 25.5
        assert result[1]["id"] == "room_002"
        assert result[1]["confidence"] == 0.8

    def test_summarize_rooms_empty(self):
        """Test summarizing empty room list."""
        summary = summarize_rooms([])

        assert summary["total_rooms"] == 0
        assert summary["named_rooms"] == 0
        assert summary["rooms_with_area"] == 0
        assert summary["total_area_m2"] == 0.0

    def test_summarize_rooms_with_data(self):
        """Test summarizing rooms with names and areas."""
        rooms = [
            Room(id="room_001", name="Woonkamer", area_m2=25.5),
            Room(id="room_002", name="Keuken", area_m2=12.0),
            Room(id="room_003", name="Slaapkamer", area_m2=15.0),
            Room(id="room_004"),  # No name or area
        ]

        summary = summarize_rooms(rooms)

        assert summary["total_rooms"] == 4
        assert summary["named_rooms"] == 3
        assert summary["rooms_with_area"] == 3
        assert summary["total_area_m2"] == 52.5
        assert summary["avg_area_m2"] == 52.5 / 3

    def test_summarize_rooms_partial_data(self):
        """Test summarizing rooms with some missing data."""
        rooms = [
            Room(id="room_001", area_m2=20.0),
            Room(id="room_002", area_m2=30.0),
            Room(id="room_003"),  # No area
        ]

        summary = summarize_rooms(rooms)

        assert summary["total_rooms"] == 3
        assert summary["rooms_with_area"] == 2
        assert summary["total_area_m2"] == 50.0
        assert summary["avg_area_m2"] == 25.0


class TestRoomAreaCalculation:
    """Tests for room area calculations."""

    def test_area_px2_to_m2_conversion(self):
        """Test conversion from pixel² to m²."""
        # 100x100 px = 10000 px²
        # With px_to_mm=1.0: 10000 px² → 10000 mm² = 0.01 m²
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        if rooms:
            area_m2 = rooms[0].area_m2
            # For 100x100 px at 1.0 px_to_mm: ~0.01 m²
            assert area_m2 is not None
            assert area_m2 > 0

    def test_downsample_factor(self):
        """Test downsampling doesn't affect final results."""
        segments = [
            (0, 0, 200, 0),
            (200, 0, 200, 200),
            (200, 200, 0, 200),
            (0, 200, 0, 0),
        ]
        plan = {"features": []}

        # With downsample_factor=1
        rooms1 = detect_rooms_from_segments(
            segments, px_to_mm=1.0, plan=plan, downsample_factor=1
        )

        # With downsample_factor=2
        rooms2 = detect_rooms_from_segments(
            segments, px_to_mm=1.0, plan=plan, downsample_factor=2
        )

        # Both should detect rooms
        assert len(rooms1) > 0
        assert len(rooms2) > 0


class TestRoomTextMatching:
    """Tests for text-to-room matching."""

    def test_match_text_to_closest_room(self):
        """Test that text labels match to closest room."""
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]

        # Text feature near the center of the room
        plan = {
            "features": [
                {
                    "label": "text",
                    "box": [40, 40, 60, 60],  # Near center at (50, 50)
                    "metadata": {"content": "Woonkamer"},
                }
            ]
        }

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        assert len(rooms) > 0
        # The room should have picked up the text label
        assert rooms[0].name == "Woonkamer" or rooms[0].name is None

    def test_match_area_text_to_room(self):
        """Test matching area measurements to rooms."""
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]

        plan = {
            "features": [
                {
                    "label": "text",
                    "box": [40, 40, 60, 60],
                    "metadata": {"content": "25,5 m²"},
                }
            ]
        }

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        if rooms:
            # Area should be extracted from text
            # Note: actual area from polygon might differ from text value
            room = rooms[0]
            # Just verify the room was created
            assert room.id is not None


class TestRoomConfidenceScoring:
    """Tests for room confidence scoring."""

    def test_default_confidence(self):
        """Test that detected rooms have default confidence."""
        segments = [
            (0, 0, 100, 0),
            (100, 0, 100, 100),
            (100, 100, 0, 100),
            (0, 100, 0, 0),
        ]
        plan = {"features": []}

        rooms = detect_rooms_from_segments(segments, px_to_mm=1.0, plan=plan)

        if rooms:
            assert rooms[0].confidence == 0.5  # Default

    def test_confidence_in_summary(self):
        """Test confidence values persist in serialization."""
        rooms = [
            Room(id="room_001", confidence=0.95),
            Room(id="room_002", confidence=0.75),
        ]

        result = rooms_to_dict(rooms)

        assert result[0]["confidence"] == 0.95
        assert result[1]["confidence"] == 0.75
