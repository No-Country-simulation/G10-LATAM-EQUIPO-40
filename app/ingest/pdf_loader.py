from __future__ import annotations

import base64
import io
from pathlib import Path

import pdfplumber


def pdf_a_imagenes_base64(path: str, dpi: int = 150) -> list[str]:
    """
    Convierte cada página del PDF en una imagen base64 (PNG).
    Útil para PDFs escaneados o cuando queremos visión multimodal.
    Requiere: pdf2image + poppler instalado.
    """
    try:
        from pdf2image import convert_from_path  # type: ignore

        imagenes = convert_from_path(path, dpi=dpi)
        resultado: list[str] = []
        for img in imagenes:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            resultado.append(f"data:image/png;base64,{b64}")
        return resultado
    except ImportError:
        raise RuntimeError(
            "pdf2image no está instalado. Instala con: pip install pdf2image\n"
            "También necesitas poppler: https://poppler.freedesktop.org/"
        )


def procesar_pdf(path: str) -> dict[str, str | list[str]]:
    """
    Punto de entrada principal para PDFs.
    Devuelve:
      - texto: str (puede ser vacío si es escaneado)
      - imagenes_data_url: list[str] (data URLs, vacío si el PDF tiene texto nativo)
      - modo: "texto" | "imagen" | "mixto" | "error"
    """
    path = str(Path(path).resolve())
    imagenes: list[str] = []

    textos: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            if t.strip():
                textos.append(f"[Página {i + 1}]\n{t.strip()}")

    texto = "\n\n".join(textos)

    if texto.strip():
        # PDF con texto nativo
        if len(texto.strip()) < 100:
            # Texto muy corto: probablemente mixto
            try:
                imagenes = pdf_a_imagenes_base64(path)
                modo = "mixto"
            except RuntimeError:
                modo = "texto"
        else:
            modo = "texto"
    else:
        # PDF escaneado: convertir a imágenes
        try:
            imagenes = pdf_a_imagenes_base64(path)
            modo = "imagen"
        except RuntimeError:
            texto = "[ERROR] PDF escaneado sin pdf2image disponible."
            modo = "error"

    return {"texto": texto, "imagenes_data_url": imagenes, "modo": modo}