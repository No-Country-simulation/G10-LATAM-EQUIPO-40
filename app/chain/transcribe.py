"""
MediFlow - Transcripción previa (OCR) de documentos escaneados.

Con MEDIFLOW_OCR_PRIMERO=1, el modelo de visión solo TRANSCRIBE las páginas a texto
y la clasificación y la extracción corren sobre ese texto con el modelo de texto.
Leer imágenes y a la vez llenar un JSON complejo rinde peor que transcribir.

Si la transcripción falla, el pipeline sigue con la lectura directa de imágenes.
Cuesta una llamada más por documento escaneado (3 en lugar de 2).
"""

from __future__ import annotations

import logging
import os

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.chain.classify import MODELO_VISION
from app.chain.llm_utils import invocar_con_reintentos
from app.models.schemas import EstadoPipeline

logger = logging.getLogger(__name__)

MAX_PAGINAS = 3        # igual que el resto del pipeline
MIN_CARACTERES = 80    # una transcripción más corta se considera fallida

SYSTEM_TRANSCRIBIR = """Eres un sistema de OCR para documentos clínicos escaneados.
Transcribe fielmente TODO el texto visible, en orden de lectura: encabezados, datos del paciente, tablas (una fila por línea), listas, sellos y firmas con texto legible, y pies de página.

REGLAS:
- No resumas, no interpretes, no corrijas, no completes y no agregues nada que no esté escrito.
- Separa las páginas con una línea "[Página N]".
- Si una palabra o número es ilegible, escribe [ilegible]. Nunca adivines nombres de medicamentos, dosis ni cifras.
- Responde solo con la transcripción, sin comentarios."""


def ocr_primero_activado() -> bool:
    return os.getenv("MEDIFLOW_OCR_PRIMERO") == "1"


def nodo_transcribir(estado: EstadoPipeline) -> EstadoPipeline:
    """Pone la transcripción en estado.texto. Si falla, deja el estado intacto."""
    imagenes = (estado.imagenes_data_url or [])[:MAX_PAGINAS]
    logger.info(f"[OCR] {estado.documento_id} ({len(imagenes)} página(s))")

    try:
        llm = ChatCohere(model=MODELO_VISION, temperature=0.0)
        contenido = [{"type": "text", "text": f"El documento tiene {len(imagenes)} página(s). Transcríbelo completo."}]
        for url in imagenes:
            contenido.append({"type": "image_url", "image_url": {"url": url}})

        response = invocar_con_reintentos(
            llm, [SystemMessage(content=SYSTEM_TRANSCRIBIR), HumanMessage(content=contenido)]
        )
        texto = str(response.content).strip()

        if len(texto) < MIN_CARACTERES:
            raise ValueError(f"transcripción demasiado corta ({len(texto)} caracteres)")

        estado.texto = texto
        logger.info(f"[OCR] {estado.documento_id}: {len(texto)} caracteres transcritos")

        # Solo depuración: la transcripción contiene datos del paciente
        if os.getenv("MEDIFLOW_DEBUG_RAW") == "1":
            logger.info(f"[OCR] transcripción:\n{texto}")

    except Exception as e:
        logger.warning(f"[OCR] {estado.documento_id}: falló ({e}); se usa lectura directa de imágenes.")

    return estado
