"""Unit tests for Hybrid Engine integration - parameter matching fix.

Tests that PreprocessingConfig instantiation matches actual class definition.
"""
import pytest
import os

# Set test environment
os.environ['DEMO_MODE'] = 'true'
os.environ['HYBRID_ENGINE_ENABLED'] = 'true'
os.environ['HYBRID_ENABLE_PREPROCESSING'] = 'true'
os.environ['TESSERACT_CMD'] = 'D:\\Users\\1\\tesseract.exe'

from app.core.hybrid_config import get_hybrid_config, reset_hybrid_config
from app.services.preprocessing.image_preprocessor import ImagePreprocessor, PreprocessingConfig


class TestPreprocessingConfigIntegration:
    """Test PreprocessingConfig parameter matching."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_hybrid_config()
    
    def test_preprocessing_config_instantiation(self):
        """Test that PreprocessingConfig can be created with hybrid_config parameters."""
        hybrid_config = get_hybrid_config()
        
        # This is exactly how BackgroundProcessor creates PreprocessingConfig
        config = PreprocessingConfig(
            enable_rotation_correction=hybrid_config.enable_rotation_correction,
            enable_deskew=hybrid_config.enable_deskew,
            max_skew_angle=hybrid_config.max_skew_angle,
            enable_contrast_enhancement=hybrid_config.enable_contrast_enhancement,
            contrast_enhancement_threshold=hybrid_config.contrast_threshold,
            clahe_clip_limit=hybrid_config.clahe_clip_limit,
            clahe_tile_grid_size=hybrid_config.clahe_tile_grid_size,
            enable_denoising=hybrid_config.enable_denoising,
            bilateral_d=hybrid_config.bilateral_d,
            bilateral_sigma_color=hybrid_config.bilateral_sigma_color,
            bilateral_sigma_space=hybrid_config.bilateral_sigma_space,
            enable_adaptive_threshold=hybrid_config.enable_adaptive_threshold,
            adaptive_block_size=hybrid_config.adaptive_block_size,
            adaptive_c=hybrid_config.adaptive_c,
            preserve_original=hybrid_config.preserve_original_image,
            max_dimension=hybrid_config.max_image_dimension
        )
        
        # Should not raise TypeError
        assert config is not None
        assert config.enable_rotation_correction == hybrid_config.enable_rotation_correction
        assert config.enable_deskew == hybrid_config.enable_deskew
        assert config.preserve_original == hybrid_config.preserve_original_image
    
    def test_image_preprocessor_initialization(self):
        """Test that ImagePreprocessor can be initialized with config."""
        hybrid_config = get_hybrid_config()
        
        config = PreprocessingConfig(
            enable_rotation_correction=hybrid_config.enable_rotation_correction,
            enable_deskew=hybrid_config.enable_deskew,
            max_skew_angle=hybrid_config.max_skew_angle,
            enable_contrast_enhancement=hybrid_config.enable_contrast_enhancement,
            contrast_enhancement_threshold=hybrid_config.contrast_threshold,
            clahe_clip_limit=hybrid_config.clahe_clip_limit,
            clahe_tile_grid_size=hybrid_config.clahe_tile_grid_size,
            enable_denoising=hybrid_config.enable_denoising,
            bilateral_d=hybrid_config.bilateral_d,
            bilateral_sigma_color=hybrid_config.bilateral_sigma_color,
            bilateral_sigma_space=hybrid_config.bilateral_sigma_space,
            enable_adaptive_threshold=hybrid_config.enable_adaptive_threshold,
            adaptive_block_size=hybrid_config.adaptive_block_size,
            adaptive_c=hybrid_config.adaptive_c,
            preserve_original=hybrid_config.preserve_original_image,
            max_dimension=hybrid_config.max_image_dimension
        )
        
        preprocessor = ImagePreprocessor(config=config)
        
        assert preprocessor is not None
        assert preprocessor.config.enable_rotation_correction == config.enable_rotation_correction
    
    def test_all_preprocessing_parameters_match(self):
        """Verify all parameter names match between hybrid_config and PreprocessingConfig."""
        hybrid_config = get_hybrid_config()
        
        # Map hybrid_config attribute names to PreprocessingConfig parameter names
        parameter_mapping = {
            'enable_rotation_correction': 'enable_rotation_correction',
            'enable_deskew': 'enable_deskew',
            'max_skew_angle': 'max_skew_angle',
            'enable_contrast_enhancement': 'enable_contrast_enhancement',
            'contrast_threshold': 'contrast_enhancement_threshold',
            'clahe_clip_limit': 'clahe_clip_limit',
            'clahe_tile_grid_size': 'clahe_tile_grid_size',
            'enable_denoising': 'enable_denoising',
            'bilateral_d': 'bilateral_d',
            'bilateral_sigma_color': 'bilateral_sigma_color',
            'bilateral_sigma_space': 'bilateral_sigma_space',
            'enable_adaptive_threshold': 'enable_adaptive_threshold',
            'adaptive_block_size': 'adaptive_block_size',
            'adaptive_c': 'adaptive_c',
            'preserve_original_image': 'preserve_original',
            'max_image_dimension': 'max_dimension'
        }
        
        # Check that all hybrid_config attributes exist
        for hybrid_attr in parameter_mapping.keys():
            assert hasattr(hybrid_config, hybrid_attr), f"Missing attribute: {hybrid_attr}"
        
        # Check that PreprocessingConfig accepts all parameters
        kwargs = {}
        for hybrid_attr, config_param in parameter_mapping.items():
            kwargs[config_param] = getattr(hybrid_config, hybrid_attr)
        
        # Should not raise TypeError
        config = PreprocessingConfig(**kwargs)
        assert config is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
