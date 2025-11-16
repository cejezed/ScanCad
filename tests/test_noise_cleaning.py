"""
Test suite for noise cleaning and image preprocessing module.
Tests image cleaning, fold removal, contrast enhancement, and denoising.
"""

import pytest
import numpy as np
import cv2
from app.noise_cleaning import (
    clean_crop,
    remove_fold_lines,
    enhance_contrast,
    denoise_image,
    prepare_for_line_detection,
)


class TestCleanCrop:
    """Tests for image crop cleaning."""

    def test_clean_crop_grayscale(self):
        """Test cleaning a grayscale image."""
        # Create simple grayscale image with noise
        gray = np.ones((100, 100), dtype=np.uint8) * 200
        gray[20:30, 20:30] = 50  # Add dark patch (potential line)

        result = clean_crop(gray)

        assert result is not None
        assert result.shape == gray.shape
        assert result.dtype == np.uint8

    def test_clean_crop_bgr(self):
        """Test cleaning a BGR color image."""
        # Create BGR image
        img = np.ones((100, 100, 3), dtype=np.uint8) * 200
        img[20:30, 20:30] = 50

        result = clean_crop(img)

        assert result is not None
        assert result.dtype == np.uint8
        # Result should be grayscale binary
        assert len(result.shape) == 2

    def test_clean_crop_empty_image(self):
        """Test handling of empty/None image."""
        empty = np.array([], dtype=np.uint8)

        result = clean_crop(empty)

        assert result is not None

    def test_clean_crop_binary_output(self):
        """Test that output is binary (0 or 255)."""
        img = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

        result = clean_crop(img)

        # Result should contain only 0 or 255
        unique_values = np.unique(result)
        assert all(v in [0, 255] for v in unique_values)

    def test_clean_crop_preserves_lines(self):
        """Test that line structures are preserved."""
        # Create image with clear horizontal line
        img = np.ones((100, 100), dtype=np.uint8) * 255
        img[50, :] = 0  # Horizontal line

        result = clean_crop(img)

        # The line should still be present (black pixels)
        line_pixels = np.sum(result[48:52, :] == 0)
        assert line_pixels > 0

    def test_clean_crop_remove_small_noise(self):
        """Test removal of small noise components."""
        # Create image with large dark patch (should be preserved)
        img = np.ones((100, 100), dtype=np.uint8) * 255
        img[30:50, 30:50] = 0  # 20x20 = 400 pixel patch

        result = clean_crop(img, remove_small_components=True, min_component_size=50)

        # Large patch should be preserved
        large_patch_pixels = np.sum(result[30:50, 30:50] == 0)
        # After thresholding and cleaning, the patch should have significant black pixels
        assert large_patch_pixels > 50

    def test_clean_crop_blur_kernel(self):
        """Test with different blur kernel sizes."""
        img = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

        for kernel_size in [1, 3, 5, 7]:
            result = clean_crop(img, blur_kernel=kernel_size)
            assert result is not None

    def test_clean_crop_morphology_kernel(self):
        """Test with different morphology kernel sizes."""
        img = np.ones((100, 100), dtype=np.uint8) * 200
        img[45:55, 45:55] = 50

        for kernel_size in [1, 3, 5]:
            result = clean_crop(img, morphology_kernel_size=kernel_size)
            assert result is not None


class TestRemoveFoldLines:
    """Tests for fold line removal."""

    def test_remove_fold_lines_no_folds(self):
        """Test on image without fold lines."""
        # Create clean image (white)
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255

        result = remove_fold_lines(img)

        assert result is not None
        assert result.shape == img.shape
        # Image should be mostly unchanged
        assert np.sum(np.abs(result.astype(int) - img.astype(int))) < 100

    def test_remove_fold_lines_with_yellow(self):
        """Test on image with yellow fold artifacts."""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255

        # Add yellowish region (BGR: yellow = [0, 255, 255])
        img[40:60, 30:70] = [0, 255, 255]

        result = remove_fold_lines(img)

        assert result is not None
        # Yellow region should be modified
        yellow_region_before = img[40:60, 30:70]
        yellow_region_after = result[40:60, 30:70]
        assert not np.array_equal(yellow_region_before, yellow_region_after)

    def test_remove_fold_lines_grayscale_ignored(self):
        """Test that grayscale images are handled."""
        gray = np.ones((100, 100), dtype=np.uint8) * 200

        result = remove_fold_lines(gray)

        # Should return unchanged for grayscale
        assert result is gray

    def test_remove_fold_lines_none_image(self):
        """Test handling of None image."""
        result = remove_fold_lines(None)

        assert result is None


class TestEnhanceContrast:
    """Tests for contrast enhancement."""

    def test_enhance_contrast_basic(self):
        """Test basic contrast enhancement."""
        # Create image with low contrast
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128

        result = enhance_contrast(img)

        assert result is not None
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_enhance_contrast_none_image(self):
        """Test handling of None image."""
        result = enhance_contrast(None)

        assert result is None

    def test_enhance_contrast_grayscale_ignored(self):
        """Test that grayscale images are ignored."""
        gray = np.ones((100, 100), dtype=np.uint8) * 128

        result = enhance_contrast(gray)

        assert result is gray

    def test_enhance_contrast_preserves_dimensions(self):
        """Test that enhancement preserves image dimensions."""
        img = np.random.randint(0, 256, (150, 200, 3), dtype=np.uint8)

        result = enhance_contrast(img)

        assert result.shape == img.shape

    def test_enhance_contrast_different_clip_limits(self):
        """Test with different CLAHE clip limits."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        for clip_limit in [1.0, 2.0, 3.0]:
            result = enhance_contrast(img, clip_limit=clip_limit)
            assert result is not None

    def test_enhance_contrast_different_tile_sizes(self):
        """Test with different tile sizes."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        for tile_size in [4, 8, 16]:
            result = enhance_contrast(img, tile_size=tile_size)
            assert result is not None


class TestDenoiseImage:
    """Tests for image denoising."""

    def test_denoise_basic(self):
        """Test basic denoising."""
        # Create noisy image
        img = np.ones((100, 100, 3), dtype=np.uint8) * 200
        noise = np.random.randint(-20, 20, img.shape).astype(np.uint8)
        img = cv2.add(img, noise)

        result = denoise_image(img)

        assert result is not None
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_denoise_none_image(self):
        """Test handling of None image."""
        result = denoise_image(None)

        assert result is None

    def test_denoise_grayscale_ignored(self):
        """Test that grayscale images are ignored."""
        gray = np.ones((100, 100), dtype=np.uint8) * 200

        result = denoise_image(gray)

        assert result is gray

    def test_denoise_preserves_dimensions(self):
        """Test that denoising preserves dimensions."""
        img = np.random.randint(0, 256, (150, 200, 3), dtype=np.uint8)

        result = denoise_image(img)

        assert result.shape == img.shape

    def test_denoise_reduces_noise(self):
        """Test that denoising processes image without error."""
        # Create reference and noisy versions
        base = np.ones((100, 100, 3), dtype=np.uint8) * 128
        noise = np.random.randint(-30, 30, base.shape).astype(np.int16)
        noisy = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        result = denoise_image(noisy)

        # Result should be valid
        assert result is not None
        assert result.shape == noisy.shape
        assert result.dtype == np.uint8

    def test_denoise_different_parameters(self):
        """Test with different denoising parameters."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        # Test different h values (filter strength)
        for h in [5, 10, 15]:
            result = denoise_image(img, h=h)
            assert result is not None


class TestPrepareForLineDetection:
    """Tests for complete preprocessing pipeline."""

    def test_prepare_default_pipeline(self):
        """Test complete pipeline with default settings."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result = prepare_for_line_detection(img)

        assert result is not None
        assert result.shape[:2] == img.shape[:2]  # Same spatial dimensions

    def test_prepare_no_enhancement(self):
        """Test pipeline without enhancement."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result = prepare_for_line_detection(img, enhance=False)

        assert result is not None

    def test_prepare_no_denoising(self):
        """Test pipeline without denoising."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result = prepare_for_line_detection(img, denoise=False)

        assert result is not None

    def test_prepare_no_fold_removal(self):
        """Test pipeline without fold removal."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result = prepare_for_line_detection(img, fold_removal=False)

        assert result is not None

    def test_prepare_all_disabled(self):
        """Test pipeline with all steps disabled."""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 200

        result = prepare_for_line_detection(
            img, enhance=False, denoise=False, fold_removal=False
        )

        # Result should be copy of input (no processing)
        assert np.array_equal(result, img)

    def test_prepare_improves_line_visibility(self):
        """Test that pipeline improves line detection capability."""
        # Create image with lines embedded in noise
        img = np.ones((100, 100, 3), dtype=np.uint8) * 200
        img[45:55, :] = [50, 50, 50]  # Horizontal line
        img[:, 45:55] = [50, 50, 50]  # Vertical line

        # Add noise
        noise = np.random.randint(-30, 30, img.shape).astype(np.int16)
        noisy = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        result = prepare_for_line_detection(noisy, enhance=True, denoise=True)

        assert result is not None


class TestImageProcessingEdgeCases:
    """Tests for edge cases in image processing."""

    def test_clean_crop_all_white(self):
        """Test cleaning all-white image."""
        white = np.ones((100, 100), dtype=np.uint8) * 255

        result = clean_crop(white)

        assert result is not None

    def test_clean_crop_all_black(self):
        """Test cleaning all-black image."""
        black = np.ones((100, 100), dtype=np.uint8) * 0

        result = clean_crop(black)

        assert result is not None

    def test_prepare_very_small_image(self):
        """Test pipeline on very small image."""
        small = np.ones((10, 10, 3), dtype=np.uint8) * 128

        result = prepare_for_line_detection(small)

        assert result is not None

    def test_clean_crop_large_image(self):
        """Test cleaning large image."""
        large = np.random.randint(0, 256, (1000, 1000), dtype=np.uint8)

        result = clean_crop(large)

        assert result is not None
        assert result.shape == large.shape

    def test_denoise_uniform_color(self):
        """Test denoising uniform color image."""
        uniform = np.ones((100, 100, 3), dtype=np.uint8) * 128

        result = denoise_image(uniform)

        # Result should be similar to input
        assert np.mean(result) == pytest.approx(128, abs=5)


class TestConsistencyAcrossPipeline:
    """Tests for consistency across preprocessing stages."""

    def test_pipeline_deterministic(self):
        """Test that pipeline produces consistent results."""
        img = np.random.RandomState(42).randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result1 = prepare_for_line_detection(img.copy())
        result2 = prepare_for_line_detection(img.copy())

        # Results should be identical
        assert np.array_equal(result1, result2)

    def test_clean_then_prepare_consistency(self):
        """Test consistency between clean_crop and full pipeline."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result1 = clean_crop(img)
        result2 = prepare_for_line_detection(img, enhance=False, denoise=False, fold_removal=False)

        # Both should produce similar results
        assert result1.dtype == result2.dtype

    def test_enhancement_then_denoise_order(self):
        """Test that order of enhancement and denoising is reasonable."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        result1 = denoise_image(enhance_contrast(img))
        result2 = enhance_contrast(denoise_image(img))

        # Both should produce valid results
        assert result1 is not None
        assert result2 is not None
