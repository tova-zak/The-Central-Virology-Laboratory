"""Image preprocessing for extraction quality improvement.

This module provides modular preprocessing methods:
- Rotation correction (basic and advanced)
- Deskewing (straightening skewed scans)
- Contrast enhancement (CLAHE for low-contrast forms)
- Denoising (bilateral filter for speckled scans)
- Adaptive thresholding (binarization - use with caution)

All methods are optional and controlled via configuration.
Original image is always preserved.
"""
import io
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

import cv2
import numpy as np
from PIL import Image


logger = logging.getLogger(__name__)


class PreprocessingMethod(str, Enum):
    """Available preprocessing methods."""
    ORIGINAL = "original"
    ROTATION_CORRECTED = "rotation_corrected"
    DESKEWED = "deskewed"
    CONTRAST_ENHANCED = "contrast_enhanced"
    DENOISED = "denoised"
    ADAPTIVE_THRESHOLD = "adaptive_threshold"


@dataclass
class PreprocessingConfig:
    """Configuration for image preprocessing.
    
    Each method can be individually enabled/disabled via feature flags.
    """
    # Rotation correction (basic heuristic + advanced detection)
    enable_rotation_correction: bool = True  # APPROVED by user
    
    # Deskewing (straighten skewed scans)
    enable_deskew: bool = True  # APPROVED by user
    max_skew_angle: float = 45.0  # Maximum angle to correct
    
    # Contrast enhancement (CLAHE for low-contrast forms)
    # APPROVED as OPTIONAL - only applied if image quality is low
    enable_contrast_enhancement: bool = False  # OFF by default per user
    contrast_enhancement_threshold: float = 50.0  # Only if mean brightness < threshold
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: Tuple[int, int] = (8, 8)
    
    # Denoising (bilateral filter for speckled scans)
    enable_denoising: bool = False  # OFF by default per user
    bilateral_d: int = 9  # Diameter of pixel neighborhood
    bilateral_sigma_color: float = 75.0
    bilateral_sigma_space: float = 75.0
    
    # Adaptive thresholding (binarization - use with extreme caution)
    enable_adaptive_threshold: bool = False  # OFF by default per user
    adaptive_block_size: int = 11
    adaptive_c: int = 2
    
    # General settings
    preserve_original: bool = True  # Always preserve original image
    max_dimension: int = 3000  # Prevent memory issues
    selection_policy: str = "quality"  # "original" explicitly disables variant selection


class ImagePreprocessor:
    """Modular image preprocessor for extraction quality improvement.
    
    All methods are optional and can be individually enabled/disabled.
    Original image is always preserved and returned as first variant.
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """Initialize preprocessor.
        
        Args:
            config: Preprocessing configuration (uses defaults if None)
        """
        self.config = config or PreprocessingConfig()
        logger.info(f"ImagePreprocessor initialized with config: {self.config}")
    
    def preprocess(self, image_bytes: bytes) -> list[Tuple[bytes, PreprocessingMethod]]:
        """Apply configured preprocessing methods to image.
        
        Returns list of (image_bytes, method_name) tuples.
        First tuple is always the original image.
        
        Args:
            image_bytes: Input image (PNG/JPEG)
            
        Returns:
            List of (processed_image_bytes, method_name) tuples
            Always includes original as first element
            
        Example:
            [
                (original_bytes, PreprocessingMethod.ORIGINAL),
                (deskewed_bytes, PreprocessingMethod.DESKEWED),
                (contrast_enhanced_bytes, PreprocessingMethod.CONTRAST_ENHANCED)
            ]
        """
        results = []
        
        # Always include original first
        results.append((image_bytes, PreprocessingMethod.ORIGINAL))
        
        # Convert to OpenCV format
        try:
            image = self._bytes_to_cv2(image_bytes)
        except Exception as e:
            logger.error(f"Failed to load image for preprocessing: {e}")
            return results  # Return original only
        
        # Check dimensions
        h, w = image.shape[:2]
        if h > self.config.max_dimension or w > self.config.max_dimension:
            logger.warning(
                f"Image dimensions ({w}x{h}) exceed max {self.config.max_dimension}. "
                f"Skipping preprocessing to prevent memory issues."
            )
            return results  # Return original only
        
        # Apply rotation correction
        if self.config.enable_rotation_correction:
            try:
                rotated = self._correct_rotation(image.copy())
                if rotated is not None and not np.array_equal(rotated, image):
                    rotated_bytes = self._cv2_to_bytes(rotated)
                    results.append((rotated_bytes, PreprocessingMethod.ROTATION_CORRECTED))
                    logger.info("Applied rotation correction")
            except Exception as e:
                logger.warning(f"Rotation correction failed: {e}")
        
        # Apply deskewing
        if self.config.enable_deskew:
            try:
                deskewed = self._deskew(image.copy())
                if deskewed is not None and not np.array_equal(deskewed, image):
                    deskewed_bytes = self._cv2_to_bytes(deskewed)
                    results.append((deskewed_bytes, PreprocessingMethod.DESKEWED))
                    logger.info("Applied deskewing")
            except Exception as e:
                logger.warning(f"Deskewing failed: {e}")
        
        # Apply contrast enhancement (only if image quality is low)
        if self.config.enable_contrast_enhancement:
            try:
                # Check if contrast enhancement is needed
                mean_brightness = np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
                if mean_brightness < self.config.contrast_enhancement_threshold:
                    enhanced = self._enhance_contrast(image.copy())
                    if enhanced is not None:
                        enhanced_bytes = self._cv2_to_bytes(enhanced)
                        results.append((enhanced_bytes, PreprocessingMethod.CONTRAST_ENHANCED))
                        logger.info(f"Applied contrast enhancement (brightness: {mean_brightness:.1f})")
                else:
                    logger.debug(f"Skipping contrast enhancement (brightness: {mean_brightness:.1f} >= {self.config.contrast_enhancement_threshold})")
            except Exception as e:
                logger.warning(f"Contrast enhancement failed: {e}")
        
        # Apply denoising
        if self.config.enable_denoising:
            try:
                denoised = self._denoise(image.copy())
                if denoised is not None:
                    denoised_bytes = self._cv2_to_bytes(denoised)
                    results.append((denoised_bytes, PreprocessingMethod.DENOISED))
                    logger.info("Applied denoising")
            except Exception as e:
                logger.warning(f"Denoising failed: {e}")
        
        # Apply adaptive thresholding (use with caution - may harm handwriting)
        if self.config.enable_adaptive_threshold:
            try:
                threshold = self._adaptive_threshold(image.copy())
                if threshold is not None:
                    threshold_bytes = self._cv2_to_bytes(threshold)
                    results.append((threshold_bytes, PreprocessingMethod.ADAPTIVE_THRESHOLD))
                    logger.info("Applied adaptive thresholding")
            except Exception as e:
                logger.warning(f"Adaptive thresholding failed: {e}")
        
        logger.info(f"Preprocessing generated {len(results)} image variants")
        return results

    def select_variant(self, original: bytes, variants) -> Tuple[bytes, PreprocessingMethod]:
        """Conservative image-only gate; never claims OCR/semantic accuracy.

        Geometry candidates must retain size, ink and edge detail, and improve horizontal
        line concentration by at least 15%. Contrast/threshold/denoise alone cannot prove
        orientation improvement and remain opt-in generation only. Ties keep the original.
        No image content or metrics containing text are logged or persisted.
        """
        fallback = (original, PreprocessingMethod.ORIGINAL)
        if self.config.selection_policy == "original":
            return fallback
        try:
            base = self._selection_metrics(original)
        except Exception:
            return fallback
        if base["ink"] < 64 or base["sharpness"] <= 0:
            return fallback
        best, best_score = fallback, base["alignment"] * 1.15
        for content, method in variants or []:
            if method not in (PreprocessingMethod.DESKEWED, PreprocessingMethod.ROTATION_CORRECTED):
                continue
            try:
                candidate = self._selection_metrics(content)
                # Expanded rotation canvases are allowed, crops and downscales are not.
                before, after = sorted(base["size"]), sorted(candidate["size"])
                if any(b < a * .98 or b > a * 1.25 for a, b in zip(before, after)):
                    continue
                if not .85 <= candidate["ink"] / base["ink"] <= 1.15:
                    continue
                if candidate["sharpness"] < base["sharpness"] * .65:
                    continue
                if candidate["alignment"] > best_score:
                    best, best_score = (content, method), candidate["alignment"]
            except Exception:
                continue  # A bad candidate must never discard a readable original.
        return best

    def _selection_metrics(self, content: bytes) -> dict:
        image = self._bytes_to_cv2(content)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = gray < 180
        ink = int(mask.sum())
        rows = mask.sum(axis=1).astype(float)
        return {"size": gray.shape, "ink": ink,
                "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                "alignment": float(np.sum(rows * rows) * len(rows) / max(1, ink * ink))}
    
    def _correct_rotation(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Correct image rotation using basic heuristics.
        
        Detects and corrects 90°, 180°, 270° rotations.
        Uses aspect ratio and edge detection.
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            Rotated image or None if no rotation needed
        """
        h, w = image.shape[:2]
        aspect_ratio = w / h
        
        # Heuristic 1: Very wide images (likely 90° rotated)
        if aspect_ratio > 2.0:
            logger.debug(f"Detected likely 90° rotation (aspect ratio: {aspect_ratio:.2f})")
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Heuristic 2: Very tall images (likely 270° rotated)
        if aspect_ratio < 0.5:
            logger.debug(f"Detected likely 270° rotation (aspect ratio: {aspect_ratio:.2f})")
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        
        # No rotation needed
        return None
    
    def _deskew(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Deskew (straighten) a skewed image.
        
        Uses Hough Line Transform to detect text lines and calculate skew angle.
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            Deskewed image or original if skew angle is negligible
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines using Hough Transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            logger.debug("No lines detected for deskewing")
            return image  # Return original
        
        # Calculate average angle
        angles = []
        for line in lines:
            rho, theta = line[0]
            # Convert to degrees
            angle_deg = (theta - np.pi / 2) * 180 / np.pi
            # Filter out angles that are too large
            if abs(angle_deg) < self.config.max_skew_angle:
                angles.append(angle_deg)
        
        if not angles:
            logger.debug("No valid skew angles detected")
            return image  # Return original
        
        # Calculate median angle (more robust than mean)
        median_angle = np.median(angles)
        
        # Only deskew if angle is significant (> 0.5 degrees)
        if abs(median_angle) < 0.5:
            logger.debug(f"Skew angle too small ({median_angle:.2f}°), skipping deskew")
            return image  # Return original
        
        logger.debug(f"Detected skew angle: {median_angle:.2f}°")
        
        # Rotate image to correct skew
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        
        # Calculate new bounding dimensions
        cos = np.abs(rotation_matrix[0, 0])
        sin = np.abs(rotation_matrix[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        # Adjust rotation matrix for translation
        rotation_matrix[0, 2] += (new_w / 2) - center[0]
        rotation_matrix[1, 2] += (new_h / 2) - center[1]
        
        # Perform rotation with white background
        deskewed = cv2.warpAffine(
            image, 
            rotation_matrix, 
            (new_w, new_h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )
        
        return deskewed
    
    def _enhance_contrast(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).
        
        Improves visibility of text in low-contrast images.
        Applied only to grayscale channel to preserve color information.
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            Contrast-enhanced image
        """
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel only (lightness)
        clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip_limit,
            tileGridSize=self.config.clahe_tile_grid_size
        )
        l_clahe = clahe.apply(l)
        
        # Merge channels
        lab_clahe = cv2.merge([l_clahe, a, b])
        
        # Convert back to BGR
        enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
        
        return enhanced
    
    def _denoise(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Reduce noise using bilateral filter.
        
        Reduces speckles while preserving edges (important for handwriting).
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            Denoised image
        """
        denoised = cv2.bilateralFilter(
            image,
            d=self.config.bilateral_d,
            sigmaColor=self.config.bilateral_sigma_color,
            sigmaSpace=self.config.bilateral_sigma_space
        )
        return denoised
    
    def _adaptive_threshold(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Apply adaptive thresholding for binarization.
        
        WARNING: May harm handwriting quality. Use with caution.
        Converts image to black and white based on local pixel neighborhoods.
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            Binarized image (converted back to BGR for consistency)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            self.config.adaptive_block_size,
            self.config.adaptive_c
        )
        
        # Convert back to BGR for consistency
        binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
        return binary_bgr
    
    def _bytes_to_cv2(self, image_bytes: bytes) -> np.ndarray:
        """Convert image bytes to OpenCV format.
        
        Args:
            image_bytes: PNG/JPEG bytes
            
        Returns:
            OpenCV image (BGR format)
        """
        # Use PIL to load image
        pil_image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB (PIL) then to BGR (OpenCV)
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert to numpy array
        image_array = np.array(pil_image)
        
        # Convert RGB to BGR (OpenCV format)
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        
        return image_bgr
    
    def _cv2_to_bytes(self, image: np.ndarray) -> bytes:
        """Convert OpenCV image to PNG bytes.
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            PNG bytes
        """
        # Encode as PNG
        success, encoded = cv2.imencode('.png', image)
        
        if not success:
            raise ValueError("Failed to encode image to PNG")
        
        return encoded.tobytes()
