#!/usr/bin/env python3
"""
Test wall detection on custom/user-provided floor plan images.

Usage:
    python test_custom_floor_plan.py <image_path>
    python test_custom_floor_plan.py /path/to/floor_plan.pdf
    python test_custom_floor_plan.py /path/to/floor_plan.jpg
"""

import sys
import argparse
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

# Try to import PDF support
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("⚠ Warning: pdf2image not installed. PDF support disabled.")


def load_image(file_path):
    """
    Load image from file (supports JPG, PNG, PDF).

    Returns:
        Grayscale image as numpy array, or None if failed
    """
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"✗ Error: File not found: {file_path}")
        return None

    # Handle PDF files
    if file_path.suffix.lower() == '.pdf':
        if not PDF_SUPPORT:
            print("✗ Error: PDF support not available. Install: pip install pdf2image")
            return None

        try:
            print(f"Converting PDF to image...")
            # Convert first page to image
            images = convert_from_path(str(file_path), first_page=1, last_page=1, dpi=300)
            if not images:
                print("✗ Error: No pages in PDF")
                return None

            # Convert PIL image to OpenCV format
            img_pil = images[0]
            img = np.array(img_pil)

            # Convert to grayscale if needed
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

            print(f"✓ Converted PDF page 1: {img.shape[1]}x{img.shape[0]} pixels @ 300 DPI")
            return img

        except Exception as e:
            print(f"✗ Error converting PDF: {e}")
            return None

    # Handle image files (JPG, PNG, etc.)
    else:
        try:
            img = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"✗ Error: Could not read image file: {file_path}")
                return None

            print(f"✓ Loaded image: {img.shape[1]}x{img.shape[0]} pixels")
            return img

        except Exception as e:
            print(f"✗ Error loading image: {e}")
            return None


def analyze_floor_plan(img, file_path, output_dir, params=None):
    """
    Analyze floor plan and detect walls.

    Args:
        img: Grayscale image
        file_path: Original file path (for naming outputs)
        output_dir: Directory to save results
        params: Optional dict with detection parameters
    """
    if params is None:
        params = {}

    # Default parameters
    min_line_length = params.get('min_line_length', 80)
    max_line_gap = params.get('max_line_gap', 15)
    min_thickness_px = params.get('min_thickness_px', 8.0)
    max_thickness_px = params.get('max_thickness_px', 50.0)
    min_length_px = params.get('min_length_px', 80.0)

    print("\n" + "="*70)
    print("WALL DETECTION ANALYSIS")
    print("="*70)

    # Check if we need to invert (architectural drawings are black-on-white)
    mean_value = np.mean(img)
    print(f"\nImage statistics:")
    print(f"  Mean pixel value: {mean_value:.1f} (0=black, 255=white)")
    print(f"  Size: {img.shape[1]}x{img.shape[0]} pixels")

    if mean_value > 127:
        # White background - typical architectural drawing
        img_proc = cv2.bitwise_not(img)
        print(f"  Background: WHITE (inverted for processing)")
    else:
        # Black background
        img_proc = img
        print(f"  Background: BLACK (no inversion needed)")

    # Save original
    output_dir.mkdir(parents=True, exist_ok=True)
    file_stem = Path(file_path).stem
    cv2.imwrite(str(output_dir / f"{file_stem}_original.png"), img)

    # Detect line segments
    print(f"\n--- Line Detection ---")
    print(f"Parameters: min_length={min_line_length}px, max_gap={max_line_gap}px")

    detected = detect_line_segments(img_proc,
                                    min_line_length=min_line_length,
                                    max_line_gap=max_line_gap)
    print(f"✓ Hough detected: {len(detected)} total line segments")

    if not detected:
        print("✗ No line segments detected. Try adjusting parameters or check image quality.")
        return None

    # Show sample of detected segments
    print("\nSample of detected segments:")
    for i, (x1, y1, x2, y2) in enumerate(detected[:5]):
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        angle = np.degrees(np.arctan2(y2-y1, x2-x1))
        print(f"  {i+1}. ({x1:.0f},{y1:.0f}) -> ({x2:.0f},{y2:.0f}) "
              f"length={length:.0f}px angle={angle:.1f}°")

    # Visualize all detected segments
    img_all = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for x1, y1, x2, y2 in detected:
        cv2.line(img_all, (int(x1), int(y1)), (int(x2), int(y2)),
                (255, 100, 100), 1)
    cv2.imwrite(str(output_dir / f"{file_stem}_all_segments.png"), img_all)

    # Filter for walls
    print(f"\n--- Wall Filtering ---")
    print(f"Parameters: thickness={min_thickness_px}-{max_thickness_px}px, "
          f"length>={min_length_px}px")

    walls = filter_wall_segments(
        img_proc, detected,
        min_thickness_px=min_thickness_px,
        max_thickness_px=max_thickness_px,
        min_length_px=min_length_px
    )

    print(f"✓ Wall filter kept: {len(walls)} wall segments")
    print(f"✗ Filtered out: {len(detected) - len(walls)} non-wall segments")
    print(f"  Retention rate: {100*len(walls)/len(detected):.1f}%")

    if not walls:
        print("\n⚠ No walls detected. Possible issues:")
        print("  - Walls might be too thin (try decreasing min_thickness_px)")
        print("  - Walls might be too thick (try increasing max_thickness_px)")
        print("  - Walls might be too short (try decreasing min_length_px)")
        print("  - Image might need preprocessing (cleaning, rotation correction)")
        return None

    # Analyze detected walls
    print(f"\n--- Wall Analysis ---")

    horizontal_walls = []
    vertical_walls = []
    diagonal_walls = []
    thicknesses = []

    for x1, y1, x2, y2 in walls:
        thickness = estimate_line_thickness(img_proc, x1, y1, x2, y2, samples=7)
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        angle = abs(np.degrees(np.arctan2(y2-y1, x2-x1)))

        thicknesses.append(thickness)

        # Classify by orientation
        if angle < 15 or angle > 165:
            horizontal_walls.append((x1, y1, x2, y2, length, thickness))
        elif 75 < angle < 105:
            vertical_walls.append((x1, y1, x2, y2, length, thickness))
        else:
            diagonal_walls.append((x1, y1, x2, y2, length, thickness))

    print(f"\nWall orientation distribution:")
    print(f"  Horizontal: {len(horizontal_walls)} walls")
    print(f"  Vertical:   {len(vertical_walls)} walls")
    print(f"  Diagonal:   {len(diagonal_walls)} walls")

    print(f"\nWall thickness statistics:")
    print(f"  Minimum:  {min(thicknesses):.1f} pixels")
    print(f"  Maximum:  {max(thicknesses):.1f} pixels")
    print(f"  Average:  {np.mean(thicknesses):.1f} pixels")
    print(f"  Median:   {np.median(thicknesses):.1f} pixels")

    print(f"\nTop 10 longest walls:")
    walls_with_length = [(x1, y1, x2, y2, np.sqrt((x2-x1)**2 + (y2-y1)**2),
                          estimate_line_thickness(img_proc, x1, y1, x2, y2, samples=5))
                         for x1, y1, x2, y2 in walls]
    walls_sorted = sorted(walls_with_length, key=lambda w: w[4], reverse=True)

    for i, (x1, y1, x2, y2, length, thickness) in enumerate(walls_sorted[:10]):
        is_horizontal = abs(y2 - y1) < abs(x2 - x1)
        orientation = "H" if is_horizontal else "V"
        print(f"  {i+1:2d}. {orientation} ({x1:4.0f},{y1:4.0f})->({x2:4.0f},{y2:4.0f}) "
              f"L={length:4.0f}px T={thickness:4.1f}px")

    # Create visualization with walls only
    img_walls = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    # Draw walls with color-coding by orientation
    for x1, y1, x2, y2 in walls:
        angle = abs(np.degrees(np.arctan2(y2-y1, x2-x1)))

        # Color code: horizontal=green, vertical=blue, diagonal=yellow
        if angle < 15 or angle > 165:
            color = (0, 255, 0)  # Green - horizontal
        elif 75 < angle < 105:
            color = (255, 0, 0)  # Blue - vertical
        else:
            color = (0, 255, 255)  # Yellow - diagonal

        cv2.line(img_walls, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)
        # Mark endpoints
        cv2.circle(img_walls, (int(x1), int(y1)), 5, (0, 0, 255), -1)
        cv2.circle(img_walls, (int(x2), int(y2)), 5, (255, 0, 0), -1)

    # Add legend
    cv2.putText(img_walls, "Green=Horizontal Blue=Vertical Yellow=Diagonal",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    cv2.putText(img_walls, f"Detected: {len(walls)} walls",
                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    # Save visualization
    cv2.imwrite(str(output_dir / f"{file_stem}_walls_detected.png"), img_walls)

    print(f"\n--- Output Files ---")
    print(f"✓ {output_dir}/{file_stem}_original.png")
    print(f"✓ {output_dir}/{file_stem}_all_segments.png (all {len(detected)} segments)")
    print(f"✓ {output_dir}/{file_stem}_walls_detected.png ({len(walls)} walls)")

    return {
        'total_segments': len(detected),
        'wall_segments': len(walls),
        'horizontal': len(horizontal_walls),
        'vertical': len(vertical_walls),
        'diagonal': len(diagonal_walls),
        'avg_thickness': np.mean(thicknesses),
        'min_thickness': min(thicknesses),
        'max_thickness': max(thicknesses),
    }


def main():
    parser = argparse.ArgumentParser(
        description='Test wall detection on custom floor plan images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_custom_floor_plan.py my_floor_plan.pdf
  python test_custom_floor_plan.py old_drawing.jpg --min-thickness 5 --max-thickness 30
  python test_custom_floor_plan.py scan.png --output results/
        """
    )

    parser.add_argument('image_path', type=str,
                       help='Path to floor plan image (JPG, PNG, PDF)')

    parser.add_argument('--output', '-o', type=str, default='tests/output',
                       help='Output directory for results (default: tests/output)')

    parser.add_argument('--min-thickness', type=float, default=8.0,
                       help='Minimum wall thickness in pixels (default: 8.0)')

    parser.add_argument('--max-thickness', type=float, default=50.0,
                       help='Maximum wall thickness in pixels (default: 50.0)')

    parser.add_argument('--min-length', type=float, default=80.0,
                       help='Minimum wall length in pixels (default: 80.0)')

    parser.add_argument('--min-line-length', type=float, default=80.0,
                       help='Hough min line length (default: 80.0)')

    parser.add_argument('--max-line-gap', type=float, default=15.0,
                       help='Hough max line gap (default: 15.0)')

    args = parser.parse_args()

    print("#"*70)
    print("# ScanCad Wall Detection - Custom Floor Plan Test")
    print("#"*70)
    print(f"\nInput file: {args.image_path}")

    # Load image
    img = load_image(args.image_path)
    if img is None:
        return 1

    # Set up parameters
    params = {
        'min_thickness_px': args.min_thickness,
        'max_thickness_px': args.max_thickness,
        'min_length_px': args.min_length,
        'min_line_length': args.min_line_length,
        'max_line_gap': args.max_line_gap,
    }

    # Analyze
    output_dir = Path(args.output)
    result = analyze_floor_plan(img, args.image_path, output_dir, params)

    if result is None:
        print("\n✗ Analysis failed")
        return 1

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"✓ Successfully detected {result['wall_segments']} walls")
    print(f"  Horizontal: {result['horizontal']}")
    print(f"  Vertical:   {result['vertical']}")
    print(f"  Diagonal:   {result['diagonal']}")
    print(f"  Avg thickness: {result['avg_thickness']:.1f}px")
    print(f"\nCheck the output directory for visualizations:")
    print(f"  {output_dir}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
