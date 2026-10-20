"""Centralized configuration for Hybrid Extraction Engine.

All feature flags in one place for easy A/B testing and configuration management.

USER REQUIREMENTS ENFORCED:
- Focused retry OFF by default
- No Gemini calls without explicit approval
- OCR as verification only
- Preprocessing conservative defaults
- All features individually togglable
"""
from pydantic_settings import BaseSettings
from typing import List


class HybridExtractionConfig(BaseSettings):
    """Configuration for hybrid extraction engine.
    
    All features can be individually enabled/disabled via environment variables
    or config files for A/B testing and gradual rollout.
    """
    
    # ==================== PHASE 1: IMAGE PREPROCESSING ====================
    
    # Master switch for preprocessing
    enable_preprocessing: bool = True  # USER APPROVED
    
    # Rotation correction (APPROVED)
    enable_rotation_correction: bool = True
    
    # Deskewing (APPROVED)
    enable_deskew: bool = True
    max_skew_angle: float = 45.0
    
    # Contrast enhancement (APPROVED as OPTIONAL - quality-dependent)
    enable_contrast_enhancement: bool = False  # OFF by default per user
    contrast_threshold: float = 50.0  # Only enhance if mean brightness < this
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: tuple = (8, 8)
    
    # Denoising (OFF by default per user)
    enable_denoising: bool = False
    bilateral_d: int = 9
    bilateral_sigma_color: float = 75.0
    bilateral_sigma_space: float = 75.0
    
    # Adaptive thresholding (OFF by default per user - risky for handwriting)
    enable_adaptive_threshold: bool = False
    adaptive_block_size: int = 11
    adaptive_c: int = 2
    
    # Always preserve original
    preserve_original_image: bool = True  # USER REQUIREMENT: Always
    max_image_dimension: int = 3000
    
    # ==================== PHASE 2: OCR LAYER ====================
    
    # Master switch for OCR
    enable_ocr: bool = True  # USER APPROVED (verification only)
    
    # OCR languages
    ocr_languages: List[str] = ["heb", "eng"]
    
    # OCR confidence threshold
    ocr_min_confidence: float = 70.0
    
    # Extract bounding boxes (for focused retry)
    ocr_extract_bboxes: bool = True
    
    # Tesseract PSM mode
    ocr_psm_mode: int = 3  # Fully automatic
    
    # Tesseract executable path (None = auto-detect)
    tesseract_cmd: str | None = None
    
    # ==================== PHASE 3: HYBRID VERIFICATION ====================
    
    # Master switch for verification
    enable_hybrid_verification: bool = True  # USER APPROVED
    
    # Require Gemini + OCR agreement for "verified" status
    require_agreement_for_verified: bool = True
    
    # OCR confidence threshold for verification
    verification_ocr_threshold: float = 70.0
    
    # Auto-flag conflicts for review
    auto_flag_conflicts: bool = True  # USER REQUIREMENT: Flag, don't auto-fix
    
    # Fields where OCR is unreliable (handwriting)
    ocr_unreliable_fields: List[str] = ["patient_first_name", "patient_last_name"]
    
    # ==================== PHASE 4: FOCUSED RETRY ====================
    
    # Master switch for focused retry (OFF by default)
    # USER REQUIREMENT: OFF, no Gemini calls without approval
    enable_focused_retry: bool = False
    
    # Maximum retries per field
    # USER REQUIREMENT: 0 (not 50), set explicitly when enabled
    max_retries_per_field: int = 0
    
    # Daily quota for focused retry
    # USER REQUIREMENT: 0 (not 50), set based on actual Gemini quota + explicit budget
    daily_focused_retry_quota: int = 0
    
    # Retry triggers
    retry_on_uncertain: bool = True
    retry_on_missing: bool = True
    retry_on_conflicting: bool = False  # Usually flag for human review instead
    
    # Bbox detection confidence
    require_reliable_bbox: bool = True  # USER REQUIREMENT
    min_bbox_confidence: float = 0.7
    
    # ==================== GENERAL SETTINGS ====================
    
    # Prompt version for Gemini
    gemini_prompt_version: str = "2.0"  # "1.0" or "2.0", user can change to "3.0" when ready
    
    # Preprocessing profile (quick preset selector)
    # "none" = no preprocessing
    # "light" = rotation + deskew only
    # "default" = light + conditional contrast
    # "aggressive" = all features (use with caution)
    preprocessing_profile: str = "light"
    
    # Demo mode (use mock extractors)
    demo_mode: bool = False
    
    # Logging verbosity for hybrid features
    hybrid_log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    
    class Config:
        env_prefix = "HYBRID_"  # Environment variables: HYBRID_ENABLE_OCR=true, etc.
        case_sensitive = False
    
    def apply_preprocessing_profile(self):
        """Apply preprocessing profile preset.
        
        USER APPROVED profiles:
        - none: No preprocessing
        - light: Rotation + deskew only (APPROVED)
        - default: Light + conditional contrast (APPROVED if needed)
        - aggressive: All features (use with caution)
        """
        if self.preprocessing_profile == "none":
            self.enable_preprocessing = False
            self.enable_rotation_correction = False
            self.enable_deskew = False
            self.enable_contrast_enhancement = False
            self.enable_denoising = False
            self.enable_adaptive_threshold = False
        
        elif self.preprocessing_profile == "light":
            self.enable_preprocessing = True
            self.enable_rotation_correction = True  # USER APPROVED
            self.enable_deskew = True  # USER APPROVED
            self.enable_contrast_enhancement = False
            self.enable_denoising = False
            self.enable_adaptive_threshold = False
        
        elif self.preprocessing_profile == "default":
            self.enable_preprocessing = True
            self.enable_rotation_correction = True
            self.enable_deskew = True
            self.enable_contrast_enhancement = True  # USER APPROVED as optional
            self.enable_denoising = False
            self.enable_adaptive_threshold = False
        
        elif self.preprocessing_profile == "aggressive":
            # Use with caution - may harm handwriting
            self.enable_preprocessing = True
            self.enable_rotation_correction = True
            self.enable_deskew = True
            self.enable_contrast_enhancement = True
            self.enable_denoising = True  # USER: OFF by default
            self.enable_adaptive_threshold = True  # USER: OFF by default, risky
    
    def get_active_features(self) -> dict:
        """Get summary of active features for logging.
        
        Returns:
            Dictionary of feature_name -> enabled status
        """
        return {
            "preprocessing": self.enable_preprocessing,
            "rotation_correction": self.enable_rotation_correction,
            "deskew": self.enable_deskew,
            "contrast_enhancement": self.enable_contrast_enhancement,
            "denoising": self.enable_denoising,
            "adaptive_threshold": self.enable_adaptive_threshold,
            "ocr": self.enable_ocr,
            "hybrid_verification": self.enable_hybrid_verification,
            "focused_retry": self.enable_focused_retry,
            "focused_retry_quota": self.daily_focused_retry_quota if self.enable_focused_retry else 0
        }
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return warnings.
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check if focused retry is enabled without quota
        if self.enable_focused_retry and self.daily_focused_retry_quota == 0:
            warnings.append(
                "WARNING: Focused retry is enabled but daily_focused_retry_quota=0. "
                "No retries will be performed."
            )
        
        # Check if focused retry is enabled without max retries per field
        if self.enable_focused_retry and self.max_retries_per_field == 0:
            warnings.append(
                "WARNING: Focused retry is enabled but max_retries_per_field=0. "
                "No retries will be performed."
            )
        
        # Check if OCR is disabled but verification is enabled
        if not self.enable_ocr and self.enable_hybrid_verification:
            warnings.append(
                "WARNING: OCR is disabled but hybrid verification is enabled. "
                "Verification will only use Gemini + validation rules."
            )
        
        # Check if adaptive threshold is enabled (risky)
        if self.enable_adaptive_threshold:
            warnings.append(
                "WARNING: Adaptive thresholding is enabled. "
                "This may harm handwriting quality. Use with caution."
            )
        
        return warnings


# Global config instance (singleton)
_hybrid_config: HybridExtractionConfig | None = None


def get_hybrid_config() -> HybridExtractionConfig:
    """Get global hybrid config instance.
    
    Returns:
        HybridExtractionConfig singleton
    """
    global _hybrid_config
    if _hybrid_config is None:
        _hybrid_config = HybridExtractionConfig()
        _hybrid_config.apply_preprocessing_profile()
        
        # Log warnings
        warnings = _hybrid_config.validate_config()
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(warning)
        
        # Log active features
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Hybrid Extraction Config loaded: {_hybrid_config.get_active_features()}")
    
    return _hybrid_config


def reset_hybrid_config():
    """Reset global config (for testing)."""
    global _hybrid_config
    _hybrid_config = None
