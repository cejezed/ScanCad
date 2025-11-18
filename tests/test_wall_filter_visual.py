#!/usr/bin/env python3
"""
Visual test for wall detection - creates synthetic images and saves results.

This script creates test images with wall-like structures, runs wall detection,
and saves annotated images showing detected walls.
"""

import sys
import numpy as np
import cv2
from pathlib import Path

# Add raster2cad to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raster2cad.app.wall_filter import (
    detect_line_segments,
    filter_wall_segments,
    estimate_line_thickness,
)


def create_synthetic_floor_plan(width=600, height=400, wall_thickness=15):
    """Create a synthetic floor plan with thick walls."""
    img = np.zeros((height, width), dtype=np.uint8)

    # Outer rectangle (walls)
    # Top wall
    img[40:40+wall_thickness, 50:550] = 255
    # Bottom wall
    img[340:340+wall_thickness, 50:550] = 255
    # Left wall
    img[40:355, 50:50+wall_thickness] = 255
    # Right wall
    img[40:355, 535:535+wall_thickness] = 255

    return img


def create_complex_floor_plan(width=800, height=600, wall_thickness=12):
    """Create a more complex floor plan with rooms."""
    img = np.zeros((height, width), dtype=np.uint8)

    # Outer walls
    cv2.rectangle(img, (50, 50), (750, 550), 255, thickness=wall_thickness)

    # Internal vertical wall
    img[70:530, 395:395+wall_thickness] = 255

    # Internal horizontal wall in left room
    img[295:295+wall_thickness, 70:380] = 255

    # Internal horizontal wall in right room
    img[350:350+wall_thickness, 420:730] = 255

    # Thin annotation line (should be filtered out)
    cv2.line(img, (100, 20), (300, 20), 255, thickness=1)

    # Small symbols (should be filtered out)
    cv2.circle(img, (200, 450), 3, 255, -1)

    return img


def draw_segments(img, segments, color=(0, 255, 0), thickness=2):
    """Draw line segments on image (creates RGB copy)."""
    if len(img.shape) == 2:
        # Convert grayscale to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        img_rgb = img.copy()

    for seg in segments:
        x1, y1, x2, y2 = map(int, seg)
        cv2.line(img_rgb, (x1, y1), (x2, y2), color, thickness)
        # Draw endpoints
        cv2.circle(img_rgb, (x1, y1), 3, (0, 0, 255), -1)
        cv2.circle(img_rgb, (x2, y2), 3, (255, 0, 0), -1)

    return img_rgb


def test_simple_rectangle():
    """Test 1: Simple rectangle with thick walls."""
    print("\n" + "="*60)
    print("TEST 1: Simple Rectangle Floor Plan")
    print("="*60)

    img = create_synthetic_floor_plan(600, 400, 15)
    print(f"✓ Created synthetic image: {img.shape[1]}x{img.shape[0]}, {15}px wall thickness")

    # Detect line segments
    detected = detect_line_segments(img, min_line_length=50, max_line_gap=10)
    print(f"✓ Hough detected: {len(detected)} segments")
    for i, seg in enumerate(detected[:5]):
        print(f"    Segment {i}: ({seg[0]:.1f}, {seg[1]:.1f}, {seg[2]:.1f}, {seg[3]:.1f})")

    # Filter for walls
    walls = filter_wall_segments(
        img, detected,
        min_thickness_px=10.0,
        max_thickness_px=30.0,
        min_length_px=100.0
    )
    print(f"✓ Wall filter kept: {len(walls)} segments")
    for i, seg in enumerate(walls[:5]):
        print(f"    Wall {i}: ({seg[0]:.1f}, {seg[1]:.1f}, {seg[2]:.1f}, {seg[3]:.1f})")

    # Create visualization
    img_all = draw_segments(img, detected, color=(100, 100, 255), thickness=1)
    img_walls = draw_segments(img, walls, color=(0, 255, 0), thickness=2)

    # Save results
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    cv2.imwrite(str(output_dir / "test1_original.png"), img)
    cv2.imwrite(str(output_dir / "test1_all_detected.png"), img_all)
    cv2.imwrite(str(output_dir / "test1_walls_only.png"), img_walls)

    print(f"✓ Saved results to: {output_dir}/test1_*.png")

    return len(walls) >= 4


def test_complex_floor_plan():
    """Test 2: Complex floor plan with multiple rooms."""
    print("\n" + "="*60)
    print("TEST 2: Complex Floor Plan with Rooms")
    print("="*60)

    img = create_complex_floor_plan(800, 600, 12)
    print(f"✓ Created complex floor plan: {img.shape[1]}x{img.shape[0]}, {12}px wall thickness")

    # Detect line segments
    detected = detect_line_segments(img, min_line_length=50, max_line_gap=10)
    print(f"✓ Hough detected: {len(detected)} segments")

    # Filter for walls (relaxed parameters for complex plans)
    walls = filter_wall_segments(
        img, detected,
        min_thickness_px=6.0,
        max_thickness_px=25.0,
        min_length_px=50.0
    )
    print(f"✓ Wall filter kept: {len(walls)} segments")

    # Analyze wall thicknesses
    thicknesses = []
    for seg in walls[:5]:
        thickness = estimate_line_thickness(img, *seg, samples=5)
        thicknesses.append(thickness)
        print(f"    Wall segment {seg}: thickness = {thickness:.1f}px")

    # Create visualization
    img_all = draw_segments(img, detected, color=(100, 100, 255), thickness=1)
    img_walls = draw_segments(img, walls, color=(0, 255, 0), thickness=2)

    # Save results
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    cv2.imwrite(str(output_dir / "test2_original.png"), img)
    cv2.imwrite(str(output_dir / "test2_all_detected.png"), img_all)
    cv2.imwrite(str(output_dir / "test2_walls_only.png"), img_walls)

    print(f"✓ Saved results to: {output_dir}/test2_*.png")

    return len(walls) >= 6


def test_noisy_image():
    """Test 3: Floor plan with noise."""
    print("\n" + "="*60)
    print("TEST 3: Noisy Floor Plan")
    print("="*60)

    # Create clean floor plan
    img = create_synthetic_floor_plan(600, 400, 15)

    # Add noise
    noise = np.random.randint(0, 40, img.shape, dtype=np.uint8)
    img_noisy = cv2.add(img, noise)

    print(f"✓ Created noisy floor plan: {img_noisy.shape[1]}x{img_noisy.shape[0]}")

    # Detect line segments
    detected = detect_line_segments(img_noisy, min_line_length=80, max_line_gap=15)
    print(f"✓ Hough detected: {len(detected)} segments")

    # Filter for walls
    walls = filter_wall_segments(
        img_noisy, detected,
        min_thickness_px=10.0,
        max_thickness_px=30.0,
        min_length_px=100.0
    )
    print(f"✓ Wall filter kept: {len(walls)} segments")

    # Create visualization
    img_walls = draw_segments(img_noisy, walls, color=(0, 255, 0), thickness=2)

    # Save results
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    cv2.imwrite(str(output_dir / "test3_noisy.png"), img_noisy)
    cv2.imwrite(str(output_dir / "test3_walls_detected.png"), img_walls)

    print(f"✓ Saved results to: {output_dir}/test3_*.png")

    return len(walls) >= 3


def main():
    """Run all visual tests."""
    print("\n" + "#"*60)
    print("# ScanCad Wall Filter - Visual Tests")
    print("#"*60)

    results = []

    # Run tests
    try:
        results.append(("Simple Rectangle", test_simple_rectangle()))
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        results.append(("Simple Rectangle", False))

    try:
        results.append(("Complex Floor Plan", test_complex_floor_plan()))
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        results.append(("Complex Floor Plan", False))

    try:
        results.append(("Noisy Image", test_noisy_image()))
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        results.append(("Noisy Image", False))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    output_dir = Path(__file__).parent / "output"
    print(f"\nVisualization images saved to: {output_dir}")
    print("\nFiles created:")
    for png_file in sorted(output_dir.glob("*.png")):
        print(f"  - {png_file.name}")

    return 0 if all(p for _, p in results) else 1


if __name__ == "__main__":
    sys.exit(main())
