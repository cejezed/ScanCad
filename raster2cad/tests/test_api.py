"""
Tests for FastAPI backend.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_healthz(self):
        """Test health check."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAnalyzeEndpoint:
    """Test image analysis endpoint."""

    def test_analyze_with_image(self):
        """Test analyze endpoint with valid image."""
        # Create a simple test image
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        _, img_bytes = cv2.imencode(".jpg", img)
        img_bytes = img_bytes.tobytes()

        # Send to API
        response = client.post(
            "/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"dpi": 300},
        )

        assert response.status_code == 200
        data = response.json()
        assert "image_source" in data
        assert "image_dims" in data
        assert "dpi" in data
        assert "features" in data

    def test_analyze_empty_file(self):
        """Test analyze with empty file."""
        response = client.post(
            "/analyze",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 400

    def test_analyze_invalid_image(self):
        """Test analyze with invalid image data."""
        response = client.post(
            "/analyze",
            files={"file": ("bad.jpg", b"not an image", "image/jpeg")},
        )
        # Should return 500 since image can't be processed
        assert response.status_code in [400, 500]


class TestVectorizeEndpoint:
    """Test vectorization endpoint."""

    def test_vectorize_with_image(self):
        """Test vectorize endpoint."""
        # Create a simple test image
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        cv2.line(img, (50, 100), (150, 100), (0, 0, 0), 2)
        _, img_bytes = cv2.imencode(".jpg", img)
        img_bytes = img_bytes.tobytes()

        # Send to API
        response = client.post(
            "/vectorize",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"dpi": 300},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/dxf"
        # Should contain DXF signature
        assert b"DXF" in response.content

    def test_vectorize_with_plan(self):
        """Test vectorize with pre-generated plan."""
        # Create test image
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        _, img_bytes = cv2.imencode(".jpg", img)
        img_bytes = img_bytes.tobytes()

        # Create test plan
        plan = {
            "image_source": "test.jpg",
            "image_dims": [200, 200],
            "dpi": 300,
            "features": [],
        }
        plan_bytes = json.dumps(plan).encode()

        # Send to API
        response = client.post(
            "/vectorize",
            files={
                "file": ("test.jpg", img_bytes, "image/jpeg"),
                "plan": ("plan.json", plan_bytes, "application/json"),
            },
            data={"dpi": 300},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/dxf"


class TestPlanEndpoint:
    """Test plan-only endpoint."""

    def test_plan_endpoint(self):
        """Test /plan endpoint."""
        # Create test image
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        _, img_bytes = cv2.imencode(".jpg", img)
        img_bytes = img_bytes.tobytes()

        response = client.post(
            "/plan",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"dpi": 300},
        )

        assert response.status_code == 200
        data = response.json()
        assert "image_dims" in data
        assert "features" in data


class TestSchemaEndpoint:
    """Test schema endpoint."""

    def test_get_schema(self):
        """Test getting schema."""
        response = client.get("/schema")
        assert response.status_code == 200
        schema = response.json()
        assert "$schema" in schema
        assert "properties" in schema


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
