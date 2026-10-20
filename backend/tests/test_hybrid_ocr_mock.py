"""Tests for OCR module using MockOCRExtractor only.

These tests do NOT require Tesseract installation.
They verify OCR interface and MockOCRExtractor behavior.
"""
import pytest
from app.services.ocr.tesseract_extractor import MockOCRExtractor
from app.services.extraction.extractor import ExtractionError


def test_mock_ocr_initialization():
    """Test MockOCRExtractor initializes without Tesseract."""
    # Should not raise error even if Tesseract not installed
    extractor = MockOCRExtractor()
    assert extractor is not None


def test_mock_ocr_extract_returns_empty_fields():
    """Test MockOCRExtractor returns empty fields."""
    extractor = MockOCRExtractor()
    
    # Create dummy image bytes
    image_bytes = b"fake image data"
    
    result = extractor.extract(
        image=image_bytes,
        document_id="test_doc",
        page_index=0
    )
    
    assert result is not None
    assert result.fields is not None
    
    # All fields should be None or empty list
    assert result.fields["patient_first_name"] is None
    assert result.fields["patient_last_name"] is None
    assert result.fields["patient_id_number"] is None
    assert result.fields["sender"] is None
    assert result.fields["received_date"] is None
    assert result.fields["central_numbers"] == []
    assert result.fields["commitment_numbers"] == []


def test_mock_ocr_warnings():
    """Test MockOCRExtractor includes appropriate warnings."""
    extractor = MockOCRExtractor()
    image_bytes = b"fake image"
    
    result = extractor.extract(image_bytes, "test_doc", 0)
    
    assert len(result.warnings) > 0
    
    # Should have warnings about being mock
    warning_text = " ".join(result.warnings).lower()
    assert "mock" in warning_text or "disabled" in warning_text


def test_mock_ocr_metadata():
    """Test MockOCRExtractor metadata is correct."""
    extractor = MockOCRExtractor()
    image_bytes = b"fake image"
    
    result = extractor.extract(image_bytes, "test_doc", 0)
    
    assert result.model_id == "mock-ocr"
    assert result.prompt_version == "mock-v1"
    assert result.processing_time_ms >= 0
    assert result.raw_response is not None


def test_mock_ocr_consistent_output():
    """Test MockOCRExtractor returns consistent output for same input."""
    extractor = MockOCRExtractor()
    image_bytes = b"fake image"
    
    result1 = extractor.extract(image_bytes, "test_doc", 0)
    result2 = extractor.extract(image_bytes, "test_doc", 0)
    
    # Structure should be identical
    assert result1.fields.keys() == result2.fields.keys()
    assert result1.model_id == result2.model_id


# NOTE: Tests for real TesseractExtractor would require Tesseract installation
# and are not included here per user requirement (Mock only).
# When Tesseract is installed, additional tests can be added:
#
# def test_real_tesseract_initialization():
#     from app.services.ocr.tesseract_extractor import TesseractExtractor, OCRConfig
#     config = OCRConfig(languages=["eng"])
#     extractor = TesseractExtractor(config)
#     assert extractor is not None
#
# def test_real_tesseract_extract_printed_text():
#     # Test with synthetic image containing printed text
#     pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
