"""
Noise cleaning and image preprocessing for architectural drawings.

Handles scan artifacts, fold lines, and improves line detection quality
through adaptive thresholding and morphological operations.
"""

import logging
import numpy as np
import cv2
from typing import Optional

logger = logging.getLogger(__name__)


def clean_crop(
    crop: np.ndarray,
    blur_kernel: int = 5,
    adaptive_block_size: int = 11,
    adaptive_constant: float = 2.0,
    morphology_kernel_size: int = 3,
    remove_small_components: bool = True,
    min_component_size: int = 10,
) -> np.ndarray:
    """
    Clean and preprocess an image crop for line detection.

    Process:
    1. Convert to grayscale if needed
    2. Apply Gaussian blur to reduce noise
    3. Apply adaptive thresholding for better edge detection
    4. Morphological opening to remove small noise components
    5. Optional: remove very small connected components

    Args:
        crop: Input image (BGR or grayscale)
        blur_kernel: Size of Gaussian blur kernel (odd number)
        adaptive_block_size: Block size for adaptive threshold (odd number)
        adaptive_constant: Constant subtracted from mean for adaptive threshold
        morphology_kernel_size: Size of morphology kernel
        remove_small_components: Whether to remove small connected components
        min_component_size: Minimum size (in pixels) to keep

    Returns:
        Binary (0-255) image suitable for line detection
    """
    if crop is None or crop.size == 0:
        logger.warning("Empty crop provided to clean_crop")
        return crop

    # Ensure grayscale
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop.copy()

    # Apply Gaussian blur to reduce scan noise
    if blur_kernel > 1:
        blurred = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)
    else:
        blurred = gray

    # Adaptive thresholding (better than fixed threshold for uneven lighting)
    try:
        thresh = cv2.adaptiveThreshold(
            blurred,
            maxValue=255,
            adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=adaptive_block_size,
            C=-adaptive_constant,
        )
    except cv2.error as e:
        logger.warning(f"Adaptive threshold failed, falling back to Otsu: {e}")
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological opening: remove small noise while keeping lines
    if morphology_kernel_size > 1:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (morphology_kernel_size, morphology_kernel_size))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    else:
        opened = thresh

    # Remove very small connected components
    if remove_small_components:
        opened = _remove_small_components(opened, min_component_size)

    return opened


def _remove_small_components(binary_img: np.ndarray, min_size: int) -> np.ndarray:
    """
    Remove connected components smaller than min_size.

    Args:
        binary_img: Binary image (0 or 255)
        min_size: Minimum component size in pixels

    Returns:
        Cleaned binary image
    """
    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img, connectivity=8)

    # Create output image
    output = np.zeros_like(binary_img)

    # Keep only components >= min_size
    for label in range(1, num_labels):
        size = stats[label, cv2.CC_STAT_AREA]
        if size >= min_size:
            output[labels == label] = 255

    return output


def remove_fold_lines(
    img: np.ndarray,
    fold_detection_threshold: int = 50,
) -> np.ndarray:
    """
    Attempt to detect and reduce scan fold lines (usually yellowish or dark).

    Simple heuristic: look for long continuous horizontal/vertical lines
    and reduce their intensity.

    Args:
        img: Input image (BGR)
        fold_detection_threshold: Tolerance for fold line detection

    Returns:
        Image with fold lines reduced
    """
    if img is None or len(img.shape) != 3:
        return img

    result = img.copy()

    # Look for yellowish regions (fold artifacts are often yellow/brown)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Yellow hue range: 20-30
    lower_yellow = np.array([15, 100, 100])
    upper_yellow = np.array([35, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

    if yellow_mask.sum() > 0:
        # Dilate to connect nearby yellow regions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        yellow_mask = cv2.dilate(yellow_mask, kernel, iterations=2)

        # Reduce intensity in yellow regions (make them lighter)
        result[yellow_mask > 0] = result[yellow_mask > 0] * 0.7 + 180 * 0.3

        logger.debug(f"Removed {yellow_mask.sum() // 255} yellow fold line pixels")

    return result


def enhance_contrast(
    img: np.ndarray,
    clip_limit: float = 2.0,
    tile_size: int = 8,
) -> np.ndarray:
    """
    Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).

    Useful for scans with uneven lighting.

    Args:
        img: Input image
        clip_limit: Clip limit for CLAHE
        tile_size: Size of grid tiles

    Returns:
        Contrast-enhanced image
    """
    if img is None or len(img.shape) != 3:
        return img

    # Convert to LAB color space
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

    # Apply CLAHE to L channel
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])

    # Convert back to BGR
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return result


def denoise_image(
    img: np.ndarray,
    h: int = 10,
    template_window_size: int = 7,
    search_window_size: int = 21,
) -> np.ndarray:
    """
    Apply Non-Local Means Denoising.

    Effective for removing sensor noise while preserving edges.

    Args:
        img: Input image (BGR)
        h: Filter strength
        template_window_size: Size of template patch
        search_window_size: Size of search area

    Returns:
        Denoised image
    """
    if img is None or len(img.shape) != 3:
        return img

    try:
        denoised = cv2.fastNlMeansDenoisingColored(
            img,
            h=h,
            hForColorComponents=h,
            templateWindowSize=template_window_size,
            searchWindowSize=search_window_size,
        )
        return denoised
    except Exception as e:
        logger.warning(f"Denoising failed: {e}")
        return img


def prepare_for_line_detection(
    img: np.ndarray,
    enhance: bool = True,
    denoise: bool = True,
    fold_removal: bool = True,
) -> np.ndarray:
    """
    Full preprocessing pipeline for line detection.

    Combines enhancement, denoising, and fold removal.

    Args:
        img: Input image
        enhance: Apply contrast enhancement
        denoise: Apply denoising
        fold_removal: Attempt to remove fold lines

    Returns:
        Preprocessed image ready for line detection
    """
    result = img.copy()

    if fold_removal:
        result = remove_fold_lines(result)

    if denoise:
        result = denoise_image(result)

    if enhance:
        result = enhance_contrast(result)

    return result
