"""Validate and normalize uploaded images before any model call."""
from io import BytesIO
from pathlib import Path
import warnings

ALLOWED_TYPES = {"image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}, "image/webp": {".webp"}}
MAX_IMAGES = 3  # Existing visual extractor supports up to three.


def save_image(data, filename, content_type, target: Path, max_bytes):
    from PIL import Image, ImageOps
    if content_type not in ALLOWED_TYPES or Path(filename).suffix.lower() not in ALLOWED_TYPES[content_type]:
        raise ValueError("Images must be JPEG, PNG, or WebP with matching filename and content type")
    if not data or len(data) > max_bytes:
        raise ValueError("Image exceeds the 10 MiB limit or is empty")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[content_type]
                if image.format != expected or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Image format mismatch or animated image")
                if image.width * image.height > 20_000_000:
                    raise ValueError("Image exceeds 20 megapixels")
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGB")
                target.parent.mkdir(parents=True, exist_ok=True)
                normalized.save(target, format="JPEG", quality=95)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise ValueError("Invalid image; use a still JPEG, PNG, or WebP of at most 20 megapixels") from exc
    return str(target)
