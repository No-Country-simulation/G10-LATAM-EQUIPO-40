from __future__ import annotations

import base64
import io
from pathlib import Path

import pdfplumber


import pypdfium2 as pdfium


def pdf_a_imagenes_base64(path: str, dpi: int = 150) -> list[str]:
    """Convierte cada página del PDF en una imagen base64 (PNG). Sin poppler."""
    try:
        pdf = pdfium.PdfDocument(path)
        try:
            resultado: list[str] = []
            for page in pdf:
                img = page.render(scale=dpi / 72).to_pil().convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                resultado.append(f"data:image/png;base64,{b64}")
            return resultado
        finally:
            pdf.close()
    except Exception as e:
        raise RuntimeError(f"No se pudo convertir el PDF a imágenes: {e}")


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
        except Exception as e:  # ImportError (pdf2image) o PDFInfoNotInstalledError (poppler)
            raise RuntimeError(
                f"No se pudo convertir el PDF a imágenes ({e}). "
                "Instala pdf2image (pip install pdf2image) y poppler: "
                "sudo apt install poppler-utils"
            )

    return {"texto": texto, "imagenes_data_url": imagenes, "modo": modo}

if __name__ == "__main__":
    # Prueba manual: python pdf_loader.py
    resultado = procesar_pdf(
        "/home/nicolas/Escritorio/NoCountry/G10-LATAM-EQUIPO-40/imagenes_de_muestra/documento.pdf"
    )
    print(f"modo={resultado['modo']} | chars_texto={len(resultado['texto'])} "
          f"| imágenes={len(resultado['imagenes_data_url'])}")