"""Tests for document segmentation functionality."""
import pytest
from app.services.segmentation.segmenter import segment_pages_into_forms
from app.domain.models import LogicalForm


def test_single_page_segmentation():
    """Test that a single page creates a single form."""
    images = [b"fake_image_data"]
    forms = segment_pages_into_forms(images, "doc_001", ocr_extractor=None)
    
    assert len(forms) == 1
    assert forms[0].page_indices == [0]
    assert forms[0].segmentation_method == "single_page"
    assert forms[0].document_id == "doc_001"


def test_multiple_single_pages():
    """Test that multiple pages without notation create separate forms."""
    images = [b"page1", b"page2", b"page3"]
    forms = segment_pages_into_forms(images, "doc_002", ocr_extractor=None)
    
    # Without OCR, each page becomes a separate form (conservative approach)
    assert len(forms) == 3
    assert all(len(f.page_indices) == 1 for f in forms)


def test_empty_document():
    """Test that empty document returns empty form list."""
    images = []
    forms = segment_pages_into_forms(images, "doc_003", ocr_extractor=None)
    
    assert len(forms) == 0


def test_form_id_generation():
    """Test that each form gets a unique ID."""
    images = [b"page1", b"page2"]
    forms = segment_pages_into_forms(images, "doc_004", ocr_extractor=None)
    
    assert len(forms) == 2
    assert forms[0].form_id != forms[1].form_id
    assert "doc_004" in forms[0].form_id
    assert "doc_004" in forms[1].form_id
