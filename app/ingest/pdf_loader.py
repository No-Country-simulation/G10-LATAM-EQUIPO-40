from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import pdfplumber

from app.ingest.image_loader import _normalizar_imagen

logger = logging.getLogger(__name__)

MAX_PAGINAS_IMAGEN = 3  # los nodos del pipeline usan como máximo 3 imágenes
UMBRAL_TEXTO_MIN = 100  # menos caracteres que esto = PDF escaneado


def pdf_a_imagenes_base64(
    path: str, dpi: int = 150, max_paginas: int = MAX_PAGINAS_IMAGEN
) -> list[str]:
    """
    Convierte las primeras páginas del PDF en imágenes (data URL JPEG).
    Usa pdfplumber (pypdfium2): no requiere pdf2image ni poppler.
    """
    resultado: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:max_paginas]:
            img = _normalizar_imagen(page.to_image(resolution=dpi).original)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=88)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            resultado.append(f"data:image/jpeg;base64,{b64}")
    return resultado


def procesar_pdf(path: str) -> dict[str, str | list[str]]:
    """
    Punto de entrada principal para PDFs.
    Devuelve:
      - texto: str (vacío si es escaneado)
      - imagenes_data_url: list[str] (solo si el PDF es escaneado)
      - modo: "texto" | "imagen" | "error"
    """
    path = str(Path(path).resolve())

    textos: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            if t.strip():
                textos.append(f"[Página {i + 1}]\n{t.strip()}")
    texto = "\n\n".join(textos)

    if len(texto.strip()) >= UMBRAL_TEXTO_MIN:
        return {"texto": texto, "imagenes_data_url": [], "modo": "texto"}

    # Poco o ningún texto: escaneado. Se usan las imágenes y se descarta el texto
    # residual, para que el modelo de visión lea la página completa.
    try:
        imagenes = pdf_a_imagenes_base64(path)
    except Exception:
        logger.exception("[PDF] No se pudo convertir a imágenes")
        imagenes = []

    if imagenes:
        return {"texto": "", "imagenes_data_url": imagenes, "modo": "imagen"}
    if texto.strip():
        return {"texto": texto, "imagenes_data_url": [], "modo": "texto"}
    return {
        "texto": "No se pudo leer el PDF: no tiene texto y no se pudo convertir a imagen.",
        "imagenes_data_url": [],
        "modo": "error",
    }
