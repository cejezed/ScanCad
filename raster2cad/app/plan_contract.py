"""
Plan contract validation and data models.
Validates the architectural plan JSON schema and provides type hints.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class FeatureLabel(str, Enum):
    """Valid feature labels for architectural analysis."""
    FLOORPLAN = "floorplan"
    ELEVATION = "elevation"
    SECTION = "section"
    TEXT = "text"
    SYMBOL = "symbol"
    WALL_STRUCTURE = "wall_structure"
    DIMENSION_LINE = "dimension_line"
    NORTH_ARROW = "north_arrow"
    NOISE = "noise"


class Feature:
    """Represents a detected feature in the architectural plan."""

    def __init__(
        self,
        id: str,
        label: str,
        box: Tuple[float, float, float, float],
        conf: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.label = label
        self.box = box  # [x1, y1, x2, y2]
        self.conf = conf
        self.metadata = metadata or {}

        # Validate
        if label not in [e.value for e in FeatureLabel]:
            raise ValueError(f"Invalid label: {label}")
        if not (0 <= conf <= 1):
            raise ValueError(f"Confidence must be in [0, 1], got {conf}")
        if len(box) != 4:
            raise ValueError(f"Box must have 4 coordinates, got {len(box)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "box": list(self.box),
            "conf": self.conf,
            "metadata": self.metadata,
        }


class Plan:
    """Represents a complete architectural plan analysis result."""

    def __init__(
        self,
        image_source: str,
        image_dims: Tuple[int, int],
        dpi: int,
        features: List[Feature],
    ):
        self.image_source = image_source
        self.image_dims = image_dims  # (width, height)
        self.dpi = dpi
        self.features = features

        # Validate
        if dpi <= 0:
            raise ValueError(f"DPI must be positive, got {dpi}")
        if len(image_dims) != 2:
            raise ValueError(f"Image dims must be (w, h), got {image_dims}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_source": self.image_source,
            "image_dims": list(self.image_dims),
            "dpi": self.dpi,
            "features": [f.to_dict() for f in self.features],
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Plan":
        """Create Plan from dictionary."""
        features = [
            Feature(
                id=f["id"],
                label=f["label"],
                box=tuple(f["box"]),
                conf=f["conf"],
                metadata=f.get("metadata", {}),
            )
            for f in data.get("features", [])
        ]
        return Plan(
            image_source=data["image_source"],
            image_dims=tuple(data["image_dims"]),
            dpi=data["dpi"],
            features=features,
        )

    @staticmethod
    def from_json(json_str: str) -> "Plan":
        """Create Plan from JSON string."""
        data = json.loads(json_str)
        return Plan.from_dict(data)

    @staticmethod
    def from_file(path: str) -> "Plan":
        """Load Plan from JSON file."""
        with open(path, "r") as f:
            return Plan.from_json(f.read())

    def save(self, path: str) -> None:
        """Save Plan to JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())

    def get_features_by_label(self, label: str) -> List[Feature]:
        """Get all features with a specific label."""
        return [f for f in self.features if f.label == label]
