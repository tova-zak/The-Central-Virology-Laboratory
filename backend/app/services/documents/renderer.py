"""PDF/image rendering and preprocessing for extraction.

Handles:
- PDF to image conversion
- Orientation detection
- Image preprocessing
"""
import io
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
from PIL import Image


class DocumentRenderer:
    """Renders PDF pages and images for extraction."""
    
    def __init__(self, dpi: int = 300, max_dimension: int = 3000):
        """Initialize renderer.
        
        Args:
            dpi: Resolution for PDF rendering (default 300)
            max_dimension: Max width/height to prevent memory issues
        """
        self.dpi = dpi
        self.max_dimension = max_dimension
    
    def pdf_to_images(self, pdf_path: Path) -> list[bytes]:
        """Convert PDF pages to PNG images.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of PNG image bytes, one per page
            
        Raises:
            ValueError: If PDF is corrupted or exceeds limits
        """
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Calculate target dimensions at desired DPI
                base_scale = self.dpi / 72
                page_rect = page.rect
                target_width = page_rect.width * base_scale
                target_height = page_rect.height * base_scale
                
                # Calculate scale factor to fit within max_dimension while preserving aspect ratio
                scale_factor = base_scale
                if target_width > self.max_dimension or target_height > self.max_dimension:
                    width_scale = self.max_dimension / target_width
                    height_scale = self.max_dimension / target_height
                    # Use the smaller scale to ensure both dimensions fit
                    adjustment_factor = min(width_scale, height_scale)
                    scale_factor = base_scale * adjustment_factor
                
                # Render with calculated scale
                mat = fitz.Matrix(scale_factor, scale_factor)
                pix = page.get_pixmap(matrix=mat)
                
                # Verify final dimensions (should always pass now)
                if pix.width > self.max_dimension or pix.height > self.max_dimension:
                    raise ValueError(
                        f"Page {page_num+1} dimensions ({pix.width}x{pix.height}) "
                        f"still exceed maximum {self.max_dimension}x{self.max_dimension} after scaling"
                    )
                
                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)
            
            doc.close()
            return images
            
        except Exception as e:
            raise ValueError(f"Failed to render PDF: {str(e)}")
    
    def detect_rotation(self, image_bytes: bytes) -> int:
        """Detect if image needs rotation.
        
        Uses basic heuristics (can be improved with OCR/ML).
        
        Args:
            image_bytes: Image data
            
        Returns:
            Rotation needed in degrees: 0, 90, 180, or 270
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            
            # Basic heuristic: if significantly wider than tall, might be rotated
            # This is conservative - many forms are landscape legitimately
            aspect_ratio = width / height
            
            # For MVP: return 0 (no rotation) unless obviously wrong
            # TODO: Implement proper orientation detection if needed
            if aspect_ratio > 2.0:
                # Very wide - might be 90° rotated
                return 90
            elif aspect_ratio < 0.5:
                # Very tall - might be 270° rotated  
                return 270
            else:
                return 0
                
        except Exception:
            # If detection fails, assume no rotation needed
            return 0
    
    def load_image(self, image_path: Path) -> bytes:
        """Load and validate image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Image bytes (PNG/JPEG)
            
        Raises:
            ValueError: If image is invalid or too large
        """
        try:
            img = Image.open(image_path)
            
            # Check dimensions
            width, height = img.size
            if width > self.max_dimension or height > self.max_dimension:
                raise ValueError(
                    f"Image dimensions ({width}x{height}) "
                    f"exceed maximum {self.max_dimension}x{self.max_dimension}"
                )
            
            # Convert to RGB if needed (remove alpha channel)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
            
        except Exception as e:
            raise ValueError(f"Failed to load image: {str(e)}")
