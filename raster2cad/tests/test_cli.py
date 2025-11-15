"""
Tests for CLI tool.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import cv2
import pytest


def create_test_image(path: Path, width: int = 200, height: int = 200):
    """Create a simple test image."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    # Draw a black line
    cv2.line(img, (50, 100), (150, 100), (0, 0, 0), 2)
    cv2.imwrite(str(path), img)


def create_test_plan(path: Path):
    """Create a test plan file."""
    plan = {
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
    with open(path, "w") as f:
        json.dump(plan, f)


class TestCLI:
    """Test CLI functionality."""

    def test_cli_help(self):
        """Test CLI help."""
        result = subprocess.run(
            ["python", "-m", "cli.raster2cad", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Convert architectural drawings to DXF" in result.stdout

    def test_cli_vectorize_simple(self):
        """Test CLI vectorization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test image
            img_path = tmpdir / "test.jpg"
            create_test_image(img_path)

            # Run CLI
            output_path = tmpdir / "output.dxf"
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "cli.raster2cad",
                    "--in",
                    str(img_path),
                    "--out",
                    str(output_path),
                    "--dpi",
                    "300",
                ],
                capture_output=True,
                text=True,
            )

            # Check result
            assert result.returncode == 0
            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_cli_with_plan(self):
        """Test CLI with pre-generated plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test image and plan
            img_path = tmpdir / "test.jpg"
            plan_path = tmpdir / "plan.json"
            create_test_image(img_path)
            create_test_plan(plan_path)

            # Run CLI
            output_path = tmpdir / "output.dxf"
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "cli.raster2cad",
                    "--in",
                    str(img_path),
                    "--out",
                    str(output_path),
                    "--plan",
                    str(plan_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert output_path.exists()

    def test_cli_analyze_only(self):
        """Test CLI analyze-only mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test image
            img_path = tmpdir / "test.jpg"
            create_test_image(img_path)

            # Run CLI with --analyze-only
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "cli.raster2cad",
                    "--in",
                    str(img_path),
                    "--analyze-only",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            # Should output JSON
            try:
                data = json.loads(result.stdout)
                assert "image_dims" in data
                assert "features" in data
            except json.JSONDecodeError:
                pytest.fail("CLI did not output valid JSON")

    def test_cli_output_plan(self):
        """Test CLI saving plan to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test image
            img_path = tmpdir / "test.jpg"
            create_test_image(img_path)

            # Run CLI
            plan_path = tmpdir / "plan.json"
            output_path = tmpdir / "output.dxf"
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "cli.raster2cad",
                    "--in",
                    str(img_path),
                    "--out",
                    str(output_path),
                    "--output-plan",
                    str(plan_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert plan_path.exists()
            with open(plan_path) as f:
                plan = json.load(f)
            assert "features" in plan

    def test_cli_missing_input(self):
        """Test CLI with missing input file."""
        result = subprocess.run(
            ["python", "-m", "cli.raster2cad", "--in", "nonexistent.jpg", "--out", "out.dxf"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_cli_missing_output(self):
        """Test CLI with missing output file when not analyze-only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            img_path = tmpdir / "test.jpg"
            create_test_image(img_path)

            result = subprocess.run(
                ["python", "-m", "cli.raster2cad", "--in", str(img_path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
