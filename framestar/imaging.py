from __future__ import annotations

import io

from PIL import Image as PILImage
from PIL import ImageEnhance, ImageFilter, ImageOps


def fill_frame(photo: bytes, width: int = 1280, height: int = 800) -> bytes:
    """Fit the photo inside width x height over a blurred, dimmed cover-crop of itself."""
    image = ImageOps.exif_transpose(PILImage.open(io.BytesIO(photo))).convert("RGB")
    backdrop = ImageOps.fit(image, (width // 10, height // 10)).filter(ImageFilter.GaussianBlur(3))
    backdrop = ImageEnhance.Brightness(backdrop.resize((width, height), PILImage.Resampling.BILINEAR)).enhance(0.45)
    fitted = ImageOps.contain(image, (width, height), PILImage.Resampling.LANCZOS)
    backdrop.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    out = io.BytesIO()
    backdrop.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()
