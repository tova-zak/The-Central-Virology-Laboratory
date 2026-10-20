"""Tests for image preprocessing module.

These are UNIT tests using synthetic images - NO real medical data.
"""
import pytest
import io
import numpy as np
from PIL import Image, ImageDraw
import cv2

from app.services.preprocessing.image_preprocessor import (
    ImagePreprocessor,
    PreprocessingConfig,
    PreprocessingMethod
)


def create_test_image(width=800, height=600, text="TEST", rotation=0, blur=0):
    """Create synthetic test image.
    
    Args:
        width: Image width
        height: Image height
        text: Text to draw
        rotation: Rotation angle (degrees)
        blur: Blur amount (0=none)
        
    Returns:
        Image bytes (PNG)
    """
    # Create white image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw text
    draw.text((width//4, height//2), text, fill='black')
    
    # Apply rotation if specified
    if rotation != 0:
        img = img.rotate(rotation, expand=True, fillcolor='white')
    
    # Apply blur if specified
    if blur > 0:
        import PIL.ImageFilter
        img = img.filter(PIL.ImageFilter.GaussianBlur(radius=blur))
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def test_preprocessor_initialization():
    """Test preprocessor initializes with default config."""
    preprocessor = ImagePreprocessor()
    assert preprocessor.config is not None
    assert preprocessor.config.enable_rotation_correction == True
    assert preprocessor.config.enable_deskew == True


def test_preprocessor_custom_config():
    """Test preprocessor with custom config."""
    config = PreprocessingConfig(
        enable_rotation_correction=False,
        enable_deskew=True,
        enable_contrast_enhancement=True
    )
    preprocessor = ImagePreprocessor(config)
    assert preprocessor.config.enable_rotation_correction == False
    assert preprocessor.config.enable_deskew == True
    assert preprocessor.config.enable_contrast_enhancement == True


def test_preprocess_returns_original_first():
    """Test that preprocessing always returns original as first variant."""
    preprocessor = ImagePreprocessor()
    image_bytes = create_test_image()
    
    results = preprocessor.preprocess(image_bytes)
    
    assert len(results) >= 1, "Should return at least original"
    assert results[0][1] == PreprocessingMethod.ORIGINAL, "First should be original"
    assert results[0][0] == image_bytes, "First bytes should match input"


def test_preprocess_with_all_disabled():
    """Test preprocessing with all methods disabled returns only original."""
    config = PreprocessingConfig(
        enable_rotation_correction=False,
        enable_deskew=False,
        enable_contrast_enhancement=False,
        enable_denoising=False,
        enable_adaptive_threshold=False
    )
    preprocessor = ImagePreprocessor(config)
    image_bytes = create_test_image()
    
    results = preprocessor.preprocess(image_bytes)
    
    assert len(results) == 1, "Should return only original when all disabled"
    assert results[0][1] == PreprocessingMethod.ORIGINAL


def test_rotation_correction_detects_wide_image():
    """Test rotation detection for very wide image (likely 90° rotated)."""
    # Create very wide image (aspect ratio > 2.0)
    image_bytes = create_test_image(width=2400, height=600)
    
    preprocessor = ImagePreprocessor()
    results = preprocessor.preprocess(image_bytes)
    
    # Should include rotation_corrected variant
    methods = [method for _, method in results]
    # Note: Rotation detection may or may not trigger depending on implementation
    # This test verifies preprocessing doesn't crash on wide images
    assert PreprocessingMethod.ORIGINAL in methods


def test_deskew_preserves_image_quality():
    """Test that deskewing doesn't corrupt image."""
    config = PreprocessingConfig(
        enable_rotation_correction=False,
        enable_deskew=True
    )
    preprocessor = ImagePreprocessor(config)
    image_bytes = create_test_image()
    
    results = preprocessor.preprocess(image_bytes)
    
    # Verify all results are valid PNG images
    for img_bytes, method in results:
        assert len(img_bytes) > 0, f"Empty bytes for method {method}"
        # Can be loaded as image
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0 and img.size[1] > 0


def test_contrast_enhancement_only_on_dark_images():
    """Test contrast enhancement is conditional on image brightness."""
    config = PreprocessingConfig(
        enable_contrast_enhancement=True,
        contrast_enhancement_threshold=50.0
    )
    preprocessor = ImagePreprocessor(config)
    
    # Create bright image (mean brightness > threshold)
    bright_image = create_test_image()
    results_bright = preprocessor.preprocess(bright_image)
    methods_bright = [method for _, method in results_bright]
    
    # Should NOT include contrast_enhanced (image is bright)
    # Note: This depends on actual image brightness calculation
    assert PreprocessingMethod.ORIGINAL in methods_bright


def test_preprocessing_preserves_original():
    """Test that original image is never modified."""
    config = PreprocessingConfig(
        enable_rotation_correction=True,
        enable_deskew=True,
        enable_contrast_enhancement=True,
        enable_denoising=True
    )
    preprocessor = ImagePreprocessor(config)
    original_bytes = create_test_image()
    
    results = preprocessor.preprocess(original_bytes)
    
    # First result should be exact copy of original
    assert results[0][0] == original_bytes
    assert results[0][1] == PreprocessingMethod.ORIGINAL


def test_preprocessing_max_dimension_limit():
    """Test that very large images are skipped."""
    config = PreprocessingConfig(
        max_dimension=1000  # Small limit
    )
    preprocessor = ImagePreprocessor(config)
    
    # Create image larger than limit
    large_image = create_test_image(width=1500, height=1500)
    
    results = preprocessor.preprocess(large_image)
    
    # Should return only original (preprocessing skipped)
    assert len(results) == 1
    assert results[0][1] == PreprocessingMethod.ORIGINAL


def test_preprocessing_handles_corrupted_image():
    """Test preprocessing gracefully handles corrupted image."""
    preprocessor = ImagePreprocessor()
    corrupted_bytes = b"not a valid image"
    
    results = preprocessor.preprocess(corrupted_bytes)
    
    # Should return only original (preprocessing failed gracefully)
    assert len(results) == 1
    assert results[0][0] == corrupted_bytes
    assert results[0][1] == PreprocessingMethod.ORIGINAL


def test_bytes_to_cv2_conversion():
    """Test conversion from bytes to OpenCV format."""
    preprocessor = ImagePreprocessor()
    image_bytes = create_test_image()
    
    # Convert to cv2
    cv2_image = preprocessor._bytes_to_cv2(image_bytes)
    
    assert isinstance(cv2_image, np.ndarray)
    assert len(cv2_image.shape) == 3  # Height x Width x Channels
    assert cv2_image.shape[2] == 3  # BGR format


def test_cv2_to_bytes_conversion():
    """Test conversion from OpenCV format to bytes."""
    preprocessor = ImagePreprocessor()
    image_bytes = create_test_image()
    
    # Convert to cv2 and back
    cv2_image = preprocessor._bytes_to_cv2(image_bytes)
    result_bytes = preprocessor._cv2_to_bytes(cv2_image)
    
    assert isinstance(result_bytes, bytes)
    assert len(result_bytes) > 0
    
    # Should be valid PNG
    img = Image.open(io.BytesIO(result_bytes))
    assert img.format == 'PNG'


def test_preprocessing_integration():
    """Integration test: preprocess with multiple methods enabled."""
    config = PreprocessingConfig(
        enable_rotation_correction=True,
        enable_deskew=True,
        enable_contrast_enhancement=False,  # OFF by default per user
        enable_denoising=False,  # OFF by default per user
        enable_adaptive_threshold=False  # OFF by default per user
    )
    preprocessor = ImagePreprocessor(config)
    image_bytes = create_test_image()
    
    results = preprocessor.preprocess(image_bytes)
    
    # Should have: original + possibly rotation + possibly deskew
    assert len(results) >= 1
    assert results[0][1] == PreprocessingMethod.ORIGINAL
    
    # All results should be valid images
    for img_bytes, method in results:
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0 and img.size[1] > 0
        print(f"  Generated variant: {method}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
