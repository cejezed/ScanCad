#!/usr/bin/env python3
"""
CLI tool for raster2cad vectorization.
Converts architectural drawings to DXF format.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from app.llm_analyzer import analyze_image, mock_analyze
from app.vectorize import process_plan
from app.pdf_utils import pdf_to_images, is_pdf

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert architectural drawings to DXF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  raster2cad --in scan.jpg --out out.dxf
  raster2cad --in scan.jpg --out out.dxf --plan plan.json
  raster2cad --in scan.pdf --out out.dxf --dpi 300
  raster2cad --in scan.jpg --out out.dxf --analyze-only
        """,
    )

    parser.add_argument(
        "--in",
        dest="input",
        required=True,
        help="Input image (jpg, png) or PDF file",
    )
    parser.add_argument(
        "--out",
        dest="output",
        help="Output DXF file (required unless --analyze-only)",
    )
    parser.add_argument(
        "--plan",
        dest="plan_file",
        help="Pre-generated plan.json file",
    )
    parser.add_argument(
        "--dpi",
        dest="dpi",
        type=int,
        default=300,
        help="Resolution in DPI (default: 300)",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze and output plan.json (no vectorization)",
    )
    parser.add_argument(
        "--output-plan",
        dest="output_plan",
        help="Save analyzed plan to JSON file",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate inputs
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    if not args.analyze_only and not args.output:
        logger.error("--out is required unless using --analyze-only")
        sys.exit(1)

    try:
        # Read input file
        logger.info(f"Reading {args.input}")
        with open(args.input, "rb") as f:
            file_bytes = f.read()

        # Handle PDF
        if is_pdf(file_bytes):
            logger.info("PDF detected, converting first page to image")
            images = pdf_to_images(file_bytes, page_num=1, dpi=args.dpi)
            if not images:
                logger.error("Failed to convert PDF")
                sys.exit(1)
            file_bytes, _ = images[0]

            # Save temporary image
            temp_image = Path(args.input).stem + "_temp.jpg"
            with open(temp_image, "wb") as f:
                f.write(file_bytes)
            image_path = temp_image
        else:
            image_path = args.input

        # Get or generate plan
        if args.plan_file:
            logger.info(f"Loading plan from {args.plan_file}")
            with open(args.plan_file, "r") as f:
                plan_dict = json.load(f)
        else:
            logger.info("Analyzing image")
            plan_dict = analyze_image(file_bytes, dpi=args.dpi, api_key=args.api_key)

        # Save plan if requested
        if args.output_plan:
            logger.info(f"Saving plan to {args.output_plan}")
            Path(args.output_plan).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output_plan, "w") as f:
                json.dump(plan_dict, f, indent=2)

        # Early exit if analyze-only
        if args.analyze_only:
            logger.info("Analysis complete")
            if not args.output_plan:
                # Print plan to stdout
                print(json.dumps(plan_dict, indent=2))
            sys.exit(0)

        # Vectorize to DXF
        logger.info(f"Vectorizing to {args.output}")
        output_path = process_plan(
            plan_dict,
            image_path,
            args.output,
            dpi=args.dpi,
        )

        logger.info(f"Success! DXF saved to {output_path}")

        # Cleanup temp PDF-converted image
        if is_pdf(file_bytes):
            try:
                Path(image_path).unlink()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
