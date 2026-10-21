"""Wrap an uploaded PNG/JPEG in a single-page PDF so images use the verified PDF storage/extraction path.

Why: Supabase delivery was observed to rewrite raw PNG downloads (different bytes), while PDFs arrive intact.
- JPEG without EXIF rotation is embedded as the ORIGINAL stream (no re-encoding).
- PNG is embedded losslessly (pixel-exact; MuPDF recompresses the stream, so bytes differ but pixels do not).
- EXIF-rotated images are transposed and embedded as lossless PNG; CMYK is converted to RGB.
- Page size = pixels x 72 / DPI (DPI from metadata when plausible, else 150): aspect ratio is exact, nothing is cropped.
Failures raise ValueError with a generic message (never image content or metadata).
"""
import io

import pymupdf
from PIL import Image, ImageOps

SUPPORTED_MIME_TYPES = ("image/png", "image/jpeg")
_MIN_DPI, _MAX_DPI, _DEFAULT_DPI = 100.0, 600.0, 150.0
_EXIF_ORIENTATION = 274


def _page_dpi(image) -> float:
    dpi = image.info.get("dpi")
    try:
        value = float(dpi[0]) if isinstance(dpi, (tuple, list)) else float(dpi)
    except (TypeError, ValueError):
        return _DEFAULT_DPI
    return value if _MIN_DPI <= value <= _MAX_DPI else _DEFAULT_DPI


def _png_stream(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_pdf(stream: bytes, width_px: int, height_px: int, dpi: float) -> bytes:
    document = pymupdf.open()
    try:
        page = document.new_page(width=width_px * 72.0 / dpi, height=height_px * 72.0 / dpi)
        page.insert_image(page.rect, stream=stream, keep_proportion=False)
        return document.tobytes()
    finally:
        document.close()


def wrap_image_as_pdf(content: bytes, mime_type: str, max_pixels: int) -> bytes:
    """Return the bytes of a one-page PDF containing the image. Raises ValueError for unusable input."""
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError("Unsupported image type")
    try:
        with Image.open(io.BytesIO(content)) as probe:
            if probe.width < 1 or probe.height < 1 or probe.width * probe.height > max_pixels:
                raise ValueError("Image dimensions not permitted")
            probe.verify()
        with Image.open(io.BytesIO(content)) as image:
            image.load()  # full decode: rejects truncated or corrupt data
            dpi = _page_dpi(image)
            orientation = image.getexif().get(_EXIF_ORIENTATION, 1)
            stream, width, height = content, image.width, image.height
            if orientation not in (1, None) or image.mode == "CMYK":
                fixed = ImageOps.exif_transpose(image)
                if fixed.mode == "CMYK":
                    fixed = fixed.convert("RGB")
                stream, width, height = _png_stream(fixed), fixed.width, fixed.height
            fallback_source = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            try:
                pdf = _build_pdf(stream, width, height, dpi)
            except Exception:
                # Unusual modes (e.g. 16-bit): embed an RGB(A) rendition instead.
                pdf = _build_pdf(_png_stream(fallback_source), width, height, dpi)
        with pymupdf.open(stream=pdf, filetype="pdf") as check:
            if check.page_count != 1 or len(check[0].get_images()) != 1:
                raise ValueError("Conversion produced an unexpected document")
        return pdf
    except ValueError:
        raise
    except Exception:
        raise ValueError("Image could not be converted") from None
