"""Tests for DocumentRenderer - PDF rendering and scaling."""
import io
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import pytest

from app.services.documents.renderer import DocumentRenderer


def create_test_pdf(tmp_path: Path, width: float, height: float, name: str = "test.pdf") -> Path:
    """Create a test PDF with specific dimensions.
    
    Args:
        tmp_path: Temporary directory
        width: Page width in points (1/72 inch)
        height: Page height in points
        name: Filename
        
    Returns:
        Path to created PDF
    """
    pdf_path = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    
    # Add some text so it's not empty
    page.insert_text((50, 50), f"Test PDF {width}x{height}", fontsize=12)
    
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


class TestDocumentRenderer:
    """Test DocumentRenderer PDF conversion and scaling."""
    
    def test_a4_portrait_normal(self, tmp_path):
        """Test standard A4 portrait page (595x842 points)."""
        # A4 = 210x297mm = 595x842 points
        pdf_path = create_test_pdf(tmp_path, 595, 842, "a4_portrait.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1
        
        # Verify image dimensions
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        # At 300 DPI: 595*300/72 = 2479, 842*300/72 = 3508
        # Should be scaled down to fit 3000 max
        assert width <= 3000, f"Width {width} exceeds 3000"
        assert height <= 3000, f"Height {height} exceeds 3000"
        
        # Verify aspect ratio preserved (A4 ratio ~1.414)
        aspect_ratio = height / width
        expected_ratio = 842 / 595
        assert abs(aspect_ratio - expected_ratio) < 0.01, "Aspect ratio not preserved"
    
    def test_large_page_scaled_down(self, tmp_path):
        """Test that large pages are automatically scaled to fit max_dimension."""
        # Create a large page that would be 2480x3546 at 300 DPI
        # Points = pixels * 72 / DPI
        # So: points = target_pixels * 72 / 300
        large_width = 2480 * 72 / 300  # ~595 points
        large_height = 3546 * 72 / 300  # ~852 points
        
        pdf_path = create_test_pdf(tmp_path, large_width, large_height, "large.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1
        
        # Verify dimensions fit within limit
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        assert width <= 3000, f"Width {width} exceeds 3000"
        assert height <= 3000, f"Height {height} exceeds 3000"
        
        # The height should be exactly 3000 (limiting dimension)
        assert height == 3000, f"Expected height 3000, got {height}"
        
        # Width should be scaled proportionally
        expected_width = int(3000 * large_width / large_height)
        assert abs(width - expected_width) <= 1, f"Width not scaled correctly: {width} vs {expected_width}"
    
    def test_landscape_page(self, tmp_path):
        """Test landscape orientation page."""
        # A4 landscape: 842x595 points
        pdf_path = create_test_pdf(tmp_path, 842, 595, "landscape.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1
        
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        # Width should be larger than height (landscape)
        assert width > height, "Landscape orientation not preserved"
        
        # Both dimensions within limit
        assert width <= 3000
        assert height <= 3000
    
    def test_multi_page_pdf(self, tmp_path):
        """Test PDF with multiple pages of different sizes."""
        pdf_path = tmp_path / "multi_page.pdf"
        doc = fitz.open()
        
        # Page 1: A4 portrait
        page1 = doc.new_page(width=595, height=842)
        page1.insert_text((50, 50), "Page 1", fontsize=12)
        
        # Page 2: A4 landscape
        page2 = doc.new_page(width=842, height=595)
        page2.insert_text((50, 50), "Page 2", fontsize=12)
        
        # Page 3: Large page
        page3 = doc.new_page(width=600, height=900)
        page3.insert_text((50, 50), "Page 3", fontsize=12)
        
        doc.save(str(pdf_path))
        doc.close()
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 3, "Should render all 3 pages"
        
        # Verify each page is valid and within limits
        for i, img_bytes in enumerate(images):
            img = Image.open(io.BytesIO(img_bytes))
            width, height = img.size
            assert width <= 3000, f"Page {i+1} width {width} exceeds 3000"
            assert height <= 3000, f"Page {i+1} height {height} exceeds 3000"
    
    def test_very_large_page(self, tmp_path):
        """Test extremely large page (e.g., poster size)."""
        # Create a very large page: 2000x3000 points (~28x42 inches)
        pdf_path = create_test_pdf(tmp_path, 2000, 3000, "poster.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1
        
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        # Should be scaled to fit
        assert width <= 3000
        assert height <= 3000
        
        # Aspect ratio preserved
        aspect_ratio = height / width
        expected_ratio = 3000 / 2000
        assert abs(aspect_ratio - expected_ratio) < 0.01
    
    def test_small_page_not_upscaled(self, tmp_path):
        """Test that small pages are rendered at requested DPI, not upscaled unnecessarily."""
        # Small page: 200x300 points (~2.8x4.2 inches)
        pdf_path = create_test_pdf(tmp_path, 200, 300, "small.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1
        
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        # At 300 DPI: 200*300/72 = 833, 300*300/72 = 1250
        expected_width = int(200 * 300 / 72)
        expected_height = int(300 * 300 / 72)
        
        # Should match expected dimensions (no upscaling, no downscaling)
        assert abs(width - expected_width) <= 1
        assert abs(height - expected_height) <= 1
    
    def test_square_page(self, tmp_path):
        """Test square page dimensions."""
        # Square: 600x600 points
        pdf_path = create_test_pdf(tmp_path, 600, 600, "square.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1
        
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        # Should be square
        assert width == height, "Square aspect ratio not preserved"
        assert width <= 3000
    
    def test_corrupted_pdf_raises_error(self, tmp_path):
        """Test that corrupted PDF raises proper error."""
        pdf_path = tmp_path / "corrupted.pdf"
        pdf_path.write_text("This is not a PDF file")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        
        with pytest.raises(ValueError, match="Failed to render PDF"):
            renderer.pdf_to_images(pdf_path)
    
    def test_specific_dimensions_2480x3546(self, tmp_path):
        """Test the specific dimensions from the bug report: 2480x3546 pixels at 300 DPI.
        
        This reproduces the exact error case from the user's PDF.
        """
        # Calculate the page dimensions in points that would result in 2480x3546 at 300 DPI
        # points = pixels * 72 / dpi
        target_width_px = 2480
        target_height_px = 3546
        dpi = 300
        
        width_points = target_width_px * 72 / dpi  # ~595 points (A4 width)
        height_points = target_height_px * 72 / dpi  # ~852 points (slightly taller than A4)
        
        pdf_path = create_test_pdf(tmp_path, width_points, height_points, "bug_case.pdf")
        
        renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        
        # This should NOT raise an error anymore
        images = renderer.pdf_to_images(pdf_path)
        
        assert len(images) == 1, "Should successfully render 1 page"
        
        # Verify the image is valid and scaled correctly
        img = Image.open(io.BytesIO(images[0]))
        width, height = img.size
        
        # Should be scaled down to fit 3000 max dimension
        assert width <= 3000, f"Width {width} exceeds 3000"
        assert height <= 3000, f"Height {height} exceeds 3000"
        
        # Height should be the limiting factor (3546 > 3000)
        assert height == 3000, f"Expected height scaled to 3000, got {height}"
        
        # Width should be scaled proportionally
        # scale_factor = 3000 / 3546
        # expected_width = 2480 * scale_factor = ~2098
        scale_factor = 3000 / target_height_px
        expected_width = int(target_width_px * scale_factor)
        
        assert abs(width - expected_width) <= 1, \
            f"Width not scaled correctly: expected {expected_width}, got {width}"
        
        # Verify aspect ratio preserved
        original_ratio = target_width_px / target_height_px
        final_ratio = width / height
        assert abs(original_ratio - final_ratio) < 0.01, \
            f"Aspect ratio changed: {original_ratio:.3f} -> {final_ratio:.3f}"


class TestDocumentRendererImageLoading:
    """Test image loading and validation."""
    
    def test_load_valid_png(self, tmp_path):
        """Test loading a valid PNG image."""
        img_path = tmp_path / "test.png"
        
        # Create a test image
        img = Image.new('RGB', (800, 600), color='red')
        img.save(img_path)
        
        renderer = DocumentRenderer(max_dimension=3000)
        img_bytes = renderer.load_image(img_path)
        
        assert img_bytes is not None
        
        # Verify it's valid PNG
        loaded = Image.open(io.BytesIO(img_bytes))
        assert loaded.size == (800, 600)
    
    def test_load_rgba_converts_to_rgb(self, tmp_path):
        """Test that RGBA images are converted to RGB."""
        img_path = tmp_path / "test_alpha.png"
        
        # Create image with alpha channel
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        img.save(img_path)
        
        renderer = DocumentRenderer(max_dimension=3000)
        img_bytes = renderer.load_image(img_path)
        
        # Should be converted to RGB
        loaded = Image.open(io.BytesIO(img_bytes))
        assert loaded.mode == 'RGB', f"Expected RGB mode, got {loaded.mode}"
    
    def test_load_oversized_image_raises_error(self, tmp_path):
        """Test that oversized images are rejected."""
        img_path = tmp_path / "huge.png"
        
        # Create image larger than max_dimension
        img = Image.new('RGB', (4000, 3000), color='blue')
        img.save(img_path)
        
        renderer = DocumentRenderer(max_dimension=3000)
        
        with pytest.raises(ValueError, match="exceed maximum"):
            renderer.load_image(img_path)


class TestRotationDetection:
    """Test basic rotation detection."""
    
    def test_normal_aspect_no_rotation(self):
        """Test normal portrait/landscape images don't trigger rotation."""
        renderer = DocumentRenderer()
        
        # Portrait (taller than wide)
        img = Image.new('RGB', (600, 800), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        
        rotation = renderer.detect_rotation(buffer.getvalue())
        assert rotation == 0, "Normal portrait shouldn't trigger rotation"
        
        # Landscape (wider than tall, but not extreme)
        img2 = Image.new('RGB', (800, 600), color='white')
        buffer2 = io.BytesIO()
        img2.save(buffer2, format='PNG')
        
        rotation2 = renderer.detect_rotation(buffer2.getvalue())
        assert rotation2 == 0, "Normal landscape shouldn't trigger rotation"
    
    def test_very_wide_triggers_rotation(self):
        """Test very wide images suggest 90° rotation."""
        renderer = DocumentRenderer()
        
        # Very wide (aspect > 2.0)
        img = Image.new('RGB', (2000, 800), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        
        rotation = renderer.detect_rotation(buffer.getvalue())
        assert rotation == 90, "Very wide image should suggest 90° rotation"
    
    def test_very_tall_triggers_rotation(self):
        """Test very tall images suggest 270° rotation."""
        renderer = DocumentRenderer()
        
        # Very tall (aspect < 0.5)
        img = Image.new('RGB', (800, 2000), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        
        rotation = renderer.detect_rotation(buffer.getvalue())
        assert rotation == 270, "Very tall image should suggest 270° rotation"
