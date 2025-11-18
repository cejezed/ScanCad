#!/usr/bin/env python3
"""
Test wall detection on realistic floor plan images.

This script tests the wall filter on more realistic floor plans that simulate
actual architectural drawings with proper wall thickness.
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


def create_realistic_floor_plan():
    """Create a realistic architectural floor plan with proper wall thickness."""
    # Create white background (like a real architectural drawing)
    img = np.ones((900, 1200), dtype=np.uint8) * 255

    # Define wall thickness (typical 20-30cm at 300 DPI ≈ 20-30 pixels)
    wall_thickness = 24

    # Outer walls (thicker)
    outer_thickness = wall_thickness

    # Draw outer perimeter (solid walls)
    # Left wall
    img[100:800, 100:100+outer_thickness] = 0
    # Top wall
    img[100:100+outer_thickness, 100:1100] = 0
    # Right wall
    img[100:800, 1100-outer_thickness:1100] = 0
    # Bottom wall
    img[800-outer_thickness:800, 100:1100] = 0

    # Internal vertical wall (divides rooms)
    internal_thickness = 18
    img[120:780, 600-internal_thickness//2:600+internal_thickness//2] = 0

    # Internal horizontal wall (kitchen separation)
    img[650-internal_thickness//2:650+internal_thickness//2, 120:580] = 0

    # Door opening in vertical wall (gap in the wall)
    door_y_start = 400
    door_height = 90
    img[door_y_start:door_y_start+door_height,
        600-internal_thickness//2:600+internal_thickness//2] = 255

    # Window openings (thinner lines in walls)
    # Window in top wall
    window_y = 100 + outer_thickness//2
    img[window_y-1:window_y+2, 250:350] = 255  # Gap
    cv2.line(img, (250, window_y), (350, window_y), 0, 1)  # Thin line

    # Add some annotations (thin lines - should be filtered out)
    # Dimension lines
    cv2.line(img, (90, 150), (90, 750), 128, 1)
    cv2.line(img, (87, 150), (93, 150), 128, 1)
    cv2.line(img, (87, 750), (93, 750), 128, 1)

    # Text annotations (simulate with small rectangles)
    cv2.putText(img, '10.5m', (50, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 128, 1)

    # Room labels (small text)
    cv2.putText(img, 'LIVING ROOM', (200, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 64, 2)
    cv2.putText(img, 'BEDROOM', (700, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 64, 2)
    cv2.putText(img, 'KITCHEN', (300, 720), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 64, 2)

    # Furniture outlines (thin lines - should be filtered)
    cv2.rectangle(img, (200, 500), (400, 700), 180, 2)  # Table
    cv2.rectangle(img, (700, 200), (900, 350), 180, 2)  # Bed

    return img


def create_scanned_floor_plan():
    """Create a floor plan that simulates a scanned document with noise."""
    # Start with realistic plan
    img = create_realistic_floor_plan()

    # Add scanner artifacts
    # Slight rotation (common in scans)
    h, w = img.shape
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, 0.5, 1.0)
    img = cv2.warpAffine(img, rotation_matrix, (w, h),
                         borderMode=cv2.BORDER_CONSTANT, borderValue=255)

    # Add noise (paper texture, scan artifacts)
    noise = np.random.normal(0, 3, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Add some JPEG compression artifacts
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
    _, encoded = cv2.imencode('.jpg', img, encode_param)
    img = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)

    return img


def test_realistic_floor_plan():
    """Test wall detection on realistic architectural floor plan."""
    print("\n" + "="*70)
    print("TEST: Realistic Architectural Floor Plan")
    print("="*70)

    # Create test image
    img = create_realistic_floor_plan()
    print(f"✓ Created realistic floor plan: {img.shape[1]}x{img.shape[0]} pixels")

    # Save original
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(output_dir / "real_plan_original.png"), img)

    # Invert image: wall filter expects white foreground on black background
    # Real architectural drawings have black lines on white paper
    img_inverted = cv2.bitwise_not(img)

    # Detect line segments
    print("\n--- Line Detection ---")
    detected = detect_line_segments(img_inverted, min_line_length=100, max_line_gap=15)
    print(f"Hough detected: {len(detected)} total segments")

    # Show some detected segments
    if detected:
        print("\nFirst 5 detected segments:")
        for i, (x1, y1, x2, y2) in enumerate(detected[:5]):
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            print(f"  {i+1}. ({x1:.0f},{y1:.0f}) -> ({x2:.0f},{y2:.0f}) length={length:.0f}px")

    # Filter for walls (use inverted image for thickness estimation)
    print("\n--- Wall Filtering ---")
    walls = filter_wall_segments(
        img_inverted, detected,
        min_thickness_px=12.0,  # Architectural walls are thick
        max_thickness_px=40.0,
        min_length_px=100.0     # Walls are long
    )
    print(f"Wall filter kept: {len(walls)} wall segments")
    print(f"Filtered out: {len(detected) - len(walls)} non-wall segments")

    # Analyze detected walls
    if walls:
        print("\nDetected walls analysis:")
        thicknesses = []
        for i, (x1, y1, x2, y2) in enumerate(walls[:8]):
            thickness = estimate_line_thickness(img_inverted, x1, y1, x2, y2, samples=7)
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            is_horizontal = abs(y2 - y1) < abs(x2 - x1)
            orientation = "horizontal" if is_horizontal else "vertical"
            thicknesses.append(thickness)

            print(f"  Wall {i+1}: {orientation:10s} length={length:4.0f}px thickness={thickness:4.1f}px")

        avg_thickness = np.mean(thicknesses)
        print(f"\nAverage wall thickness: {avg_thickness:.1f} pixels")

    # Create visualizations
    print("\n--- Creating Visualizations ---")

    # All detected segments
    img_all = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for x1, y1, x2, y2 in detected:
        cv2.line(img_all, (int(x1), int(y1)), (int(x2), int(y2)), (255, 100, 100), 1)

    # Walls only
    img_walls = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for x1, y1, x2, y2 in walls:
        cv2.line(img_walls, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
        # Mark endpoints
        cv2.circle(img_walls, (int(x1), int(y1)), 5, (0, 0, 255), -1)
        cv2.circle(img_walls, (int(x2), int(y2)), 5, (255, 0, 0), -1)

    # Save visualizations
    cv2.imwrite(str(output_dir / "real_plan_all_detected.png"), img_all)
    cv2.imwrite(str(output_dir / "real_plan_walls_only.png"), img_walls)
    print(f"✓ Saved visualizations to {output_dir}/")

    # Validation
    expected_walls = 7  # 4 outer + 2 inner + partitions
    success = len(walls) >= expected_walls - 2  # Allow some tolerance

    if success:
        print(f"\n✓ SUCCESS: Detected {len(walls)} walls (expected ~{expected_walls})")
    else:
        print(f"\n✗ WARNING: Only detected {len(walls)} walls (expected ~{expected_walls})")

    return success


def test_scanned_floor_plan():
    """Test wall detection on scanned floor plan with artifacts."""
    print("\n" + "="*70)
    print("TEST: Scanned Floor Plan (with noise and rotation)")
    print("="*70)

    # Create scanned version
    img = create_scanned_floor_plan()
    print(f"✓ Created scanned floor plan: {img.shape[1]}x{img.shape[0]} pixels")
    print("  (includes: rotation, noise, JPEG artifacts)")

    # Save original
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(output_dir / "scanned_plan_original.png"), img)

    # Invert image for wall detection
    img_inverted = cv2.bitwise_not(img)

    # Detect with more lenient parameters for scanned images
    print("\n--- Line Detection (relaxed for scan artifacts) ---")
    detected = detect_line_segments(img_inverted, min_line_length=80, max_line_gap=20)
    print(f"Hough detected: {len(detected)} total segments")

    # Filter for walls
    print("\n--- Wall Filtering ---")
    walls = filter_wall_segments(
        img_inverted, detected,
        min_thickness_px=10.0,  # Slightly relaxed for scan artifacts
        max_thickness_px=45.0,
        min_length_px=80.0
    )
    print(f"Wall filter kept: {len(walls)} wall segments")
    print(f"Filtered out: {len(detected) - len(walls)} non-wall segments")

    # Create visualization
    img_walls = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for x1, y1, x2, y2 in walls:
        cv2.line(img_walls, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)

    cv2.imwrite(str(output_dir / "scanned_plan_walls.png"), img_walls)
    print(f"✓ Saved visualization to {output_dir}/scanned_plan_walls.png")

    # Validation
    success = len(walls) >= 5  # Should detect at least major walls

    if success:
        print(f"\n✓ SUCCESS: Detected {len(walls)} walls despite scan artifacts")
    else:
        print(f"\n✗ WARNING: Only detected {len(walls)} walls (scan quality affected results)")

    return success


def test_sample_image():
    """Test on the demo sample.jpg if it exists."""
    sample_path = Path(__file__).parent.parent / "raster2cad" / "examples" / "sample.jpg"

    if not sample_path.exists():
        print("\n⊘ Skipping sample.jpg test (file not found)")
        return None

    print("\n" + "="*70)
    print("TEST: Example Sample Image (sample.jpg)")
    print("="*70)

    # Load image
    img = cv2.imread(str(sample_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("✗ Failed to load sample.jpg")
        return False

    print(f"✓ Loaded sample image: {img.shape[1]}x{img.shape[0]} pixels")

    # Check if we need to invert (if background is white)
    mean_value = np.mean(img)
    if mean_value > 127:
        # White background, invert
        img_proc = cv2.bitwise_not(img)
        print("  (inverted: black-on-white -> white-on-black)")
    else:
        img_proc = img

    # Detect
    detected = detect_line_segments(img_proc, min_line_length=50, max_line_gap=10)
    print(f"Hough detected: {len(detected)} segments")

    # Filter
    walls = filter_wall_segments(
        img_proc, detected,
        min_thickness_px=2.0,   # Thin lines in sample
        max_thickness_px=10.0,
        min_length_px=50.0
    )
    print(f"Wall filter kept: {len(walls)} segments")

    # Visualize
    output_dir = Path(__file__).parent / "output"
    img_walls = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for x1, y1, x2, y2 in walls:
        cv2.line(img_walls, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

    cv2.imwrite(str(output_dir / "sample_walls.png"), img_walls)
    print(f"✓ Saved visualization to {output_dir}/sample_walls.png")

    return len(walls) >= 4  # Should detect the 4 main walls


def main():
    """Run all real floor plan tests."""
    print("\n" + "#"*70)
    print("# ScanCad Wall Filter - Real Floor Plan Tests")
    print("#"*70)

    results = []

    # Test 1: Realistic floor plan
    try:
        result = test_realistic_floor_plan()
        results.append(("Realistic Floor Plan", result))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Realistic Floor Plan", False))

    # Test 2: Scanned floor plan
    try:
        result = test_scanned_floor_plan()
        results.append(("Scanned Floor Plan", result))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Scanned Floor Plan", False))

    # Test 3: Sample image (optional)
    try:
        result = test_sample_image()
        if result is not None:
            results.append(("Sample Image", result))
    except Exception as e:
        print(f"\n✗ Sample test failed: {e}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    output_dir = Path(__file__).parent / "output"
    print(f"\nVisualization images saved to: {output_dir}/")

    return 0 if all(p for _, p in results) else 1


if __name__ == "__main__":
    sys.exit(main())
