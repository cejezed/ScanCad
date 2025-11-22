"""
This module provides advanced image processing functionalities for vectorization.
It includes functions for image preprocessing, line detection, and other CV tasks.
"""

import cv2
import numpy as np
from typing import List, Tuple

def preprocess_for_line_detection(image: np.ndarray) -> np.ndarray:
    """
    Prepares an image for line detection by converting to grayscale, applying a binary threshold,
    and using morphological operations to clean up noise and thin lines.

    Args:
        image: Input image (can be color or grayscale).

    Returns:
        A binary image optimized for line detection.
    """
    # Convert to grayscale if it's a color image
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Apply adaptive thresholding to get a binary image
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # Use morphological operations to remove noise
    kernel = np.ones((3,3), np.uint8)
    denoised = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Thin the lines to a single pixel width
    thinned = cv2.ximgproc.thinning(denoised)

    return thinned

def detect_lines(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Detects straight lines in a binary image using the Hough Line Transform.

    Args:
        image: A binary input image (preferably preprocessed and thinned).

    Returns:
        A list of lines, where each line is a tuple of (x1, y1, x2, y2).
    """
    lines = cv2.HoughLinesP(
        image,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=50,
        maxLineGap=10
    )

    if lines is not None:
        return [tuple(line[0]) for line in lines]
    return []
