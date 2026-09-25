from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image


FORMATOS_SOPORTADOS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}

MAX_LADO_PX = 2048


def _normalizar_imagen(img: Image.Image) -> Image.Image:
    """Convierte a RGB y redimensiona si supera MAX_LADO_PX."""
    if img.mode != "RGB":
        img = img.convert("RGB")

    ancho, alto = img.size
    if max(ancho, alto) > MAX_LADO_PX:
        factor = MAX_LADO_PX / max(ancho, alto)
        nuevo_ancho = int(ancho * factor)
        nuevo_alto = int(alto * factor)
        img = img.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)

    return img


def imagen_a_base64(path: str) -> str:
    """
    Carga una imagen desde disco y devuelve Data URL.
    media_type: "image/jpeg" | "image/png" | "image/webp"
    """
    path_obj = Path(path)
    ext = path_obj.suffix.lower()

    if ext not in FORMATOS_SOPORTADOS:
        raise ValueError(
            f"Formato '{ext}' no soportado. "
            f"Formatos válidos: {', '.join(FORMATOS_SOPORTADOS)}"
        )

    with Image.open(path_obj) as img:
        img = _normalizar_imagen(img)
        buffer = io.BytesIO()

        if ext in {".jpg", ".jpeg"}:
            img.save(buffer, format="JPEG", quality=90)
            media_type = "image/jpeg"
        elif ext == ".webp":
            img.save(buffer, format="WEBP", quality=90)
            media_type = "image/webp"
        else:
            img.save(buffer, format="PNG")
            media_type = "image/png"

        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:{media_type};base64,{b64}"


def imagen_desde_bytes(data: bytes, media_type: str = "image/jpeg") -> str:
    """
    Convierte bytes de imagen (ya cargada, ej. desde upload) a base64.
    Normaliza resolución si es necesario.
    """
    fmt_map = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    fmt = fmt_map.get(media_type, "PNG")

    img = Image.open(io.BytesIO(data))
    img = _normalizar_imagen(img)

    buffer = io.BytesIO()
    img.save(buffer, format=fmt)

    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:{media_type};base64,{b64}"