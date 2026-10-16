"""
MediFlow - Transcripción previa (OCR) de documentos escaneados.

Con MEDIFLOW_OCR_PRIMERO=1, el modelo de visión solo TRANSCRIBE las páginas a texto
y la clasificación y la extracción corren sobre ese texto con el modelo de texto.

Protecciones:
  - Una llamada por página (una sola imagen por petición), en paralelo.
  - Si el modelo devuelve su propio prompt en vez del documento, o la transcripción
    es demasiado corta, el documento va a revisión humana (nunca se sigue con basura).
  - Si la API falla del todo, se usa la lectura directa de imágenes.
Cuesta una llamada por página, más las 2 habituales (las páginas se leen a la vez).
"""

from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.chain.classify import MODELO_VISION
from app.chain.llm_utils import invocar_con_reintentos
from app.models.schemas import EstadoPipeline

logger = logging.getLogger(__name__)

MAX_PAGINAS = 3         # igual que el resto del pipeline
MIN_CARACTERES = 80     # transcripción total mínima

SYSTEM_TRANSCRIBIR = """Eres un sistema de OCR para documentos clínicos escaneados.
Transcribe fielmente TODO el texto visible de la imagen, en orden de lectura: encabezados, datos del paciente, tablas (una fila por línea), listas, sellos y firmas con texto legible, y pies de página.

REGLAS:
- No resumas, no interpretes, no corrijas, no completes y no agregues nada que no esté escrito.
- Si una palabra o número es ilegible, escribe [ilegible]. Nunca adivines nombres de medicamentos, dosis ni cifras.
- No uses formato Markdown (ni #, ni **, ni ---) y no agregues títulos propios.
- Responde solo con la transcripción, sin comentarios."""

# Frases que delatan que el modelo devolvió su propio contexto y no el documento
_MARCAS_ECO = (
    "preamble", "contextual safety mode", "information cutoff",
    "large language model built by cohere", "eres un sistema de ocr",
    "no resumas, no interpretes",
)


class TranscripcionInvalida(Exception):
    pass


def ocr_primero_activado() -> bool:
    return os.getenv("MEDIFLOW_OCR_PRIMERO") == "1"


def es_eco_del_prompt(texto: str) -> bool:
    t = texto.lower()
    return any(m in t for m in _MARCAS_ECO)


def limpiar_markdown(texto: str) -> str:
    """Quita el formato que el modelo agrega (###, **, ---) y títulos que no son del documento."""
    lineas: list[str] = []
    for linea in texto.splitlines():
        l = linea.strip()
        if re.fullmatch(r"[-*_=]{3,}", l):
            continue
        if re.match(r"^#{1,6}\s*transcripci[oó]n de la p[áa]gina", l, re.IGNORECASE):
            continue
        linea = re.sub(r"^\s*#{1,6}\s*", "", linea).replace("**", "")
        lineas.append(linea.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def _transcribir_pagina(i: int, total: int, url: str) -> str:
    llm = ChatCohere(model=MODELO_VISION, temperature=0.0)
    contenido = [
        {"type": "text", "text": f"Transcribe esta página (página {i} de {total})."},
        {"type": "image_url", "image_url": {"url": url}},
    ]
    response = invocar_con_reintentos(
        llm, [SystemMessage(content=SYSTEM_TRANSCRIBIR), HumanMessage(content=contenido)]
    )
    texto = str(response.content).strip()
    texto = re.sub(r"^\s*\[P[áa]gina\s*\d+\]\s*", "", texto)  # el marcador lo ponemos nosotros
    texto = limpiar_markdown(texto)

    if es_eco_del_prompt(texto):
        raise TranscripcionInvalida(f"la página {i} devolvió texto ajeno al documento")
    return f"[Página {i}]\n{texto}"


def nodo_transcribir(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Pone la transcripción en estado.texto.
    - Transcripción inválida -> estado.error (el pipeline la envía a revisión humana).
    - Fallo de la API         -> estado intacto (se usa la lectura directa de imágenes).
    """
    imagenes = (estado.imagenes_data_url or [])[:MAX_PAGINAS]
    logger.info(f"[OCR] {estado.documento_id} ({len(imagenes)} página(s))")

    try:
        with ThreadPoolExecutor(max_workers=len(imagenes) or 1) as pool:
            futuros = [
                pool.submit(_transcribir_pagina, i, len(imagenes), url)
                for i, url in enumerate(imagenes, start=1)
            ]
            paginas = [f.result() for f in futuros]   # conserva el orden de las páginas

        total = "\n\n".join(paginas)
        if len(re.sub(r"\[P[áa]gina \d+\]", "", total).strip()) < MIN_CARACTERES:
            raise TranscripcionInvalida("transcripción demasiado corta")

        estado.texto = total
        logger.info(f"[OCR] {estado.documento_id}: {len(total)} caracteres transcritos")

        # Solo depuración: la transcripción contiene datos del paciente
        if os.getenv("MEDIFLOW_DEBUG_RAW") == "1":
            logger.info(f"[OCR] transcripción:\n{total}")

    except TranscripcionInvalida as e:
        logger.warning(f"[OCR] {estado.documento_id}: {e}; va a revisión humana.")
        estado.error = f"Transcripción no confiable ({e}). Revisar el documento manualmente."

    except Exception as e:
        logger.warning(f"[OCR] {estado.documento_id}: falló ({e}); se usa lectura directa de imágenes.")

    return estado
