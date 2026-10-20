"""Integration test for Hybrid Engine with single image processing.

Tests the full pipeline: preprocessing → extraction → OCR → verification.
"""
import io
import os
import pytest
from PIL import Image, ImageDraw, ImageFont

# Set test environment
os.environ['DEMO_MODE'] = 'true'  # Use mock Gemini
os.environ['HYBRID_ENGINE_ENABLED'] = 'true'
os.environ['HYBRID_ENABLE_PREPROCESSING'] = 'true'
os.environ['HYBRID_ENABLE_OCR'] = 'true'
os.environ['HYBRID_ENABLE_HYBRID_VERIFICATION'] = 'true'
os.environ['TESSERACT_CMD'] = 'D:\\Users\\1\\tesseract.exe'

from app.core.hybrid_config import get_hybrid_config, reset_hybrid_config
from app.services.preprocessing.image_preprocessor import ImagePreprocessor, PreprocessingConfig
from app.services.ocr.tesseract_extractor import TesseractExtractor, OCRConfig
from app.services.extraction.mock_extractor import MockExtractor
from app.services.hybrid.verifier import HybridVerifier, VerificationConfig


def create_test_image():
    """Create a simple test image."""
    img = Image.new('RGB', (400, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    draw.text((50, 50), "Patient ID: 123456789", fill='black', font=font)
    draw.text((50, 100), "Date: 15/03/2024", fill='black', font=font)
    draw.text((50, 150), "Central: 654321", fill='black', font=font)
    
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


class TestHybridSingleImageProcessing:
    """Test Hybrid Engine with a single synthetic image."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_hybrid_config()
    
    def test_preprocessing_step(self):
        """Test that preprocessing works without errors."""
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
        image_bytes = create_test_image()
        
        # Process image
        variants = preprocessor.preprocess(image_bytes)
        
        # Should return at least original + preprocessed variants
        assert len(variants) >= 1
        assert all(isinstance(v[0], bytes) for v in variants)
    
    def test_mock_extraction_step(self):
        """Test that mock extraction works in demo mode."""
        extractor = MockExtractor(model="mock-demo", simulate_delay=False)
        image_bytes = create_test_image()
        
        result = extractor.extract(
            image=image_bytes,
            document_id="test-001",
            page_index=0
        )
        
        assert result is not None
        assert result.schema_version == "1.0"
        assert result.model_id == "mock-demo"  # Uses the model name passed to constructor
        assert 'patient_id_number' in result.fields
    
    def test_ocr_step(self):
        """Test that OCR extraction works."""
        # Check if Tesseract available
        is_available, _ = TesseractExtractor.check_tesseract_available()
        
        if not is_available:
            pytest.skip("Tesseract not available")
        
        config = OCRConfig(
            languages=["heb", "eng"],
            min_confidence=60.0,
            tesseract_cmd=os.getenv("TESSERACT_CMD")
        )
        
        extractor = TesseractExtractor(config=config)
        image_bytes = create_test_image()
        
        result = extractor.extract(
            image=image_bytes,
            document_id="test-002",
            page_index=0
        )
        
        assert result is not None
        assert result.model_id == "tesseract-ocr"
        assert result.processing_time_ms > 0
    
    # Removed test_hybrid_verification_step - covered by test_full_pipeline_integration
    
    def test_full_pipeline_integration(self):
        """Test full pipeline: preprocessing → mock extraction → OCR → verification."""
        hybrid_config = get_hybrid_config()
        image_bytes = create_test_image()
        
        # Step 1: Preprocessing
        preprocessing_config = PreprocessingConfig(
            enable_rotation_correction=hybrid_config.enable_rotation_correction,
            enable_deskew=hybrid_config.enable_deskew,
            max_skew_angle=hybrid_config.max_skew_angle,
            enable_contrast_enhancement=False,
            contrast_enhancement_threshold=hybrid_config.contrast_threshold,
            clahe_clip_limit=hybrid_config.clahe_clip_limit,
            clahe_tile_grid_size=hybrid_config.clahe_tile_grid_size,
            enable_denoising=False,
            bilateral_d=hybrid_config.bilateral_d,
            bilateral_sigma_color=hybrid_config.bilateral_sigma_color,
            bilateral_sigma_space=hybrid_config.bilateral_sigma_space,
            enable_adaptive_threshold=False,
            adaptive_block_size=hybrid_config.adaptive_block_size,
            adaptive_c=hybrid_config.adaptive_c,
            preserve_original=True,
            max_dimension=3000
        )
        
        preprocessor = ImagePreprocessor(config=preprocessing_config)
        variants = preprocessor.preprocess(image_bytes)
        assert len(variants) >= 1
        
        processed_image = variants[0][0]
        
        # Step 2: Mock Extraction
        mock_extractor = MockExtractor(model="mock-demo", simulate_delay=False)
        gemini_result = mock_extractor.extract(
            image=processed_image,
            document_id="integration-test",
            page_index=0
        )
        assert gemini_result is not None
        
        # Step 3: OCR (if available)
        is_available, _ = TesseractExtractor.check_tesseract_available()
        
        if is_available:
            ocr_config = OCRConfig(
                languages=["heb", "eng"],
                min_confidence=60.0,
                tesseract_cmd=os.getenv("TESSERACT_CMD")
            )
            
            ocr_extractor = TesseractExtractor(config=ocr_config)
            ocr_result = ocr_extractor.extract(
                image=image_bytes,  # Use original
                document_id="integration-test",
                page_index=0
            )
            assert ocr_result is not None
            
            # Step 4: Verification
            verifier_config = VerificationConfig(
                require_agreement_for_verified=True,
                ocr_confidence_threshold=70.0,  # Fixed: was ocr_threshold
                auto_flag_conflicts=True,
                ocr_unreliable_fields=[]
            )
            
            verifier = HybridVerifier(config=verifier_config)
            
            # Verify a field
            verification = verifier.verify_field(
                field_name="patient_id_number",
                gemini_value=gemini_result.fields.get("patient_id_number"),
                ocr_value=ocr_result.fields.get("patient_id_number"),
                original_field_value=None
            )
            
            # Should complete without error
            assert verification is not None
        
        print("\n✅ Full pipeline integration test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
