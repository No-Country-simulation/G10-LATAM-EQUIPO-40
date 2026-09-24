from __future__ import annotations

import base64
import io
from pathlib import Path

import pdfplumber

def _pdf_tiene_texto(path: str) -> bool:
    """Devuelve True si el PDF contiene texto seleccionable (no escaneado)."""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                return True
    return False


def extraer_texto_pdf(path: str) -> str:
    """
    Extrae todo el texto de un PDF digital.
    Devuelve string vacío si el PDF no tiene texto (escaneado puro).
    """
    textos: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            texto = page.extract_text() or ""
            if texto.strip():
                textos.append(f"[Página {i + 1}]\n{texto.strip()}")
    return "\n\n".join(textos)


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
            resultado.append(b64)
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
      - imagenes_b64: list[str] (vacío si el PDF tiene texto nativo)
      - modo: "texto" | "imagen" | "mixto" | "error"
    """
    path = str(Path(path).resolve())

    tiene_texto = _pdf_tiene_texto(path)
    texto = ""
    imagenes: list[str] = []

    if tiene_texto:
        texto = extraer_texto_pdf(path)
        # Si el texto es muy corto puede ser mixto; igual renderizamos a imagen
        if len(texto.strip()) < 100:
            try:
                imagenes = pdf_a_imagenes_base64(path)
                modo = "mixto"
            except RuntimeError:
                modo = "texto"
        else:
            modo = "texto"
    else:
        # PDF puramente escaneado → convertir a imágenes
        try:
            imagenes = pdf_a_imagenes_base64(path)
            modo = "imagen"
        except RuntimeError:
            texto = "[ERROR] PDF escaneado sin pdf2image disponible."
            modo = "error"

    return {"texto": texto, "imagenes_b64": imagenes, "modo": modo}