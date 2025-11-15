"""
PDF utility functions for handling PDF input.
Converts PDF pages to images for analysis.
"""

import logging
from io import BytesIO
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


def pdf_to_images(
    pdf_bytes: bytes, page_num: Optional[int] = None, dpi: int = 300
) -> List[Tuple[bytes, int]]:
    """
    Convert PDF to image bytes (jpg).

    Args:
        pdf_bytes: Raw PDF file bytes
        page_num: Specific page to convert (1-indexed), None for all pages
        dpi: Resolution for image conversion

    Returns:
        List of tuples (image_bytes, page_number)

    Raises:
        ImportError: If pdf2image not installed
        ValueError: If PDF is invalid
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.error("pdf2image not installed. Install with: pip install pdf2image")
        raise ImportError("pdf2image required for PDF support")

    try:
        if page_num is not None:
            images = convert_from_bytes(pdf_bytes, first_page=page_num, last_page=page_num, dpi=dpi)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
    except Exception as e:
        raise ValueError(f"Failed to convert PDF: {e}")

    # Convert PIL images to JPEG bytes
    result = []
    for idx, img in enumerate(images, 1):
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        page_number = page_num if page_num is not None else idx
        result.append((img_bytes.getvalue(), page_number))

    return result


def extract_pdf_metadata(pdf_bytes: bytes) -> dict:
    """
    Extract metadata from PDF (title, author, page count).

    Args:
        pdf_bytes: Raw PDF file bytes

    Returns:
        Dictionary with metadata

    Raises:
        ImportError: If PyPDF2 not installed
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        logger.warning("PyPDF2 not installed, skipping metadata extraction")
        return {}

    try:
        pdf_reader = PdfReader(BytesIO(pdf_bytes))
        metadata = pdf_reader.metadata
        page_count = len(pdf_reader.pages)

        return {
            "title": metadata.get("/Title", "Unknown") if metadata else "Unknown",
            "author": metadata.get("/Author", "Unknown") if metadata else "Unknown",
            "page_count": page_count,
        }
    except Exception as e:
        logger.warning(f"Failed to extract PDF metadata: {e}")
        return {}


def is_pdf(file_bytes: bytes) -> bool:
    """
    Check if file is a valid PDF.

    Args:
        file_bytes: Raw file bytes

    Returns:
        True if PDF signature detected
    """
    return file_bytes.startswith(b"%PDF")
