"""
Tests for LLM analyzer feature capping functionality.
"""

import pytest
from app.llm_analyzer import cap_features, FEATURE_PRIORITY


class TestFeaturePriority:
    """Tests for feature priority ordering."""

    def test_priority_dict_complete(self):
        """Verify priority dict covers major label types."""
        expected_labels = [
            "floorplan",
            "wall_structure",
            "symbol",
            "text",
            "dimension_line",
            "noise",
        ]
        for label in expected_labels:
            assert label in FEATURE_PRIORITY

    def test_priority_ordering(self):
        """Verify priority ordering (lower index = higher priority)."""
        assert FEATURE_PRIORITY["floorplan"] < FEATURE_PRIORITY["noise"]
        assert FEATURE_PRIORITY["wall_structure"] < FEATURE_PRIORITY["noise"]
        assert FEATURE_PRIORITY["text"] < FEATURE_PRIORITY["noise"]
        assert FEATURE_PRIORITY["noise"] > FEATURE_PRIORITY["symbol"]


class TestCapFeatures:
    """Tests for feature capping logic."""

    def test_cap_no_action_needed(self):
        """Test that plans under limit are unchanged."""
        plan = {
            "features": [
                {"id": f"f_{i}", "label": "wall_structure", "conf": 0.9}
                for i in range(100)
            ]
        }

        result = cap_features(plan, max_features=300, log_info=False)

        assert len(result["features"]) == 100
        assert result == plan

    def test_cap_exact_limit(self):
        """Test plan at exact limit."""
        plan = {"features": [{"id": f"f_{i}", "label": "noise", "conf": 0.5} for i in range(300)]}

        result = cap_features(plan, max_features=300, log_info=False)

        assert len(result["features"]) == 300

    def test_cap_exceeds_limit(self):
        """Test that plans over limit are trimmed."""
        plan = {
            "features": [{"id": f"f_{i}", "label": "noise", "conf": 0.5} for i in range(500)]
        }

        result = cap_features(plan, max_features=300, log_info=False)

        assert len(result["features"]) == 300

    def test_cap_respects_priority(self):
        """Test that capping preserves high-priority features."""
        features = []

        # Add 200 noise features (lowest priority)
        for i in range(200):
            features.append({"id": f"noise_{i}", "label": "noise", "conf": 0.9})

        # Add 150 wall features (high priority)
        for i in range(150):
            features.append({"id": f"wall_{i}", "label": "wall_structure", "conf": 0.9})

        plan = {"features": features}

        result = cap_features(plan, max_features=250, log_info=False)

        # Should keep all 150 walls and 100 noise items
        assert len(result["features"]) == 250

        wall_count = sum(1 for f in result["features"] if f["label"] == "wall_structure")
        noise_count = sum(1 for f in result["features"] if f["label"] == "noise")

        assert wall_count == 150
        assert noise_count == 100  # Kept 100 noise, removed 100

    def test_cap_priority_order_maintained(self):
        """Test that priority ordering is strictly maintained."""
        plan = {
            "features": [
                {"id": "text_1", "label": "text", "conf": 0.5},
                {"id": "noise_1", "label": "noise", "conf": 0.9},
                {"id": "wall_1", "label": "wall_structure", "conf": 0.5},
                {"id": "noise_2", "label": "noise", "conf": 0.9},
            ]
        }

        result = cap_features(plan, max_features=3, log_info=False)

        # Should keep: wall (priority 2), text (priority 4), noise (priority 7)
        labels_in_result = [f["label"] for f in result["features"]]
        assert "wall_structure" in labels_in_result
        assert "text" in labels_in_result

        # Check that at least one noise is kept (higher conf than text)
        noise_indices = [i for i, f in enumerate(result["features"]) if f["label"] == "noise"]
        assert len(noise_indices) > 0

    def test_cap_confidence_tiebreaker(self):
        """Test that higher confidence is preferred when priorities match."""
        plan = {
            "features": [
                {"id": "wall_low_conf", "label": "wall_structure", "conf": 0.5},
                {"id": "wall_high_conf", "label": "wall_structure", "conf": 0.95},
                {"id": "wall_med_conf", "label": "wall_structure", "conf": 0.7},
            ]
        }

        result = cap_features(plan, max_features=2, log_info=False)

        # Should keep high and medium confidence, drop low
        kept_ids = [f["id"] for f in result["features"]]
        assert "wall_high_conf" in kept_ids
        assert "wall_med_conf" in kept_ids
        assert "wall_low_conf" not in kept_ids

    def test_cap_empty_features(self):
        """Test capping with empty features list."""
        plan = {"features": []}

        result = cap_features(plan, max_features=300, log_info=False)

        assert result["features"] == []

    def test_cap_missing_features_key(self):
        """Test capping when 'features' key is missing."""
        plan = {"image_dims": [1024, 768]}

        result = cap_features(plan, max_features=300, log_info=False)

        assert result == plan

    def test_cap_non_list_features(self):
        """Test handling of non-list features (should be ignored)."""
        plan = {"features": "not_a_list"}

        result = cap_features(plan, max_features=300, log_info=False)

        assert result["features"] == "not_a_list"  # Unchanged

    def test_cap_mixed_labels_priority(self):
        """Test capping with mixed label priorities."""
        plan = {
            "features": [
                # 60 noise items (priority 8) - should be cut first
                *[{"id": f"noise_{i}", "label": "noise", "conf": 0.8} for i in range(60)],
                # 50 dimension_line items (priority 4)
                *[{"id": f"dim_{i}", "label": "dimension_line", "conf": 0.8} for i in range(50)],
                # 40 floorplan items (priority 0) - highest, should be kept
                *[{"id": f"flp_{i}", "label": "floorplan", "conf": 0.9} for i in range(40)],
                # 40 wall_structure items (priority 1)
                *[{"id": f"wall_{i}", "label": "wall_structure", "conf": 0.9} for i in range(40)],
                # 20 symbol items (priority 2)
                *[{"id": f"sym_{i}", "label": "symbol", "conf": 0.85} for i in range(20)],
                # 10 text items (priority 3)
                *[{"id": f"txt_{i}", "label": "text", "conf": 0.9} for i in range(10)],
            ]
        }

        # Cap to 150
        result = cap_features(plan, max_features=150, log_info=False)

        # Count by label
        label_counts = {}
        for feat in result["features"]:
            label = feat["label"]
            label_counts[label] = label_counts.get(label, 0) + 1

        # All high-priority items should be kept (priorities 0-4)
        assert label_counts.get("floorplan", 0) == 40
        assert label_counts.get("wall_structure", 0) == 40
        assert label_counts.get("symbol", 0) == 20
        assert label_counts.get("text", 0) == 10

        # dimension_line (priority 4) should be kept, noise (priority 8) should be cut
        assert label_counts.get("dimension_line", 0) == 40  # Kept 40 out of 50
        assert label_counts.get("noise", 0) == 0  # All noise cut (lowest priority)

    def test_cap_custom_max(self):
        """Test capping with custom max_features value."""
        plan = {"features": [{"id": f"f_{i}", "label": "noise", "conf": 0.5} for i in range(500)]}

        result50 = cap_features(plan.copy(), max_features=50, log_info=False)
        assert len(result50["features"]) == 50

        result100 = cap_features(plan.copy(), max_features=100, log_info=False)
        assert len(result100["features"]) == 100

        result200 = cap_features(plan.copy(), max_features=200, log_info=False)
        assert len(result200["features"]) == 200
