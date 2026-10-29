"""
MediFlow  Pipeline principal
Ensambla los 3 nodos en secuencia con bifurcaciones condicionales.

Flujo:
  ingestar → clasificar → [score < 0.6?] → REVISION_HUMANA
                        ↓ (score OK)
                     extraer → enrutar → FIN
"""

from __future__ import annotations

import logging
import time

from app.chain.classify import nodo_clasificar
from app.chain.extract import nodo_extraer
from app.chain.router import UMBRAL_CONFIANZA_BAJA, nodo_enrutar
from app.chain.transcribe import nodo_transcribir, ocr_primero_activado
from app.models.schemas import (
    DecisionEnrutamiento,
    DestinoEnrutamiento,
    EstadoPipeline,
)

logger = logging.getLogger(__name__)


def _edge_post_clasificar(estado: EstadoPipeline) -> str:
    """
    Bifurcación después de clasificar.

    Returns:
        "extraer"         -> confianza OK, continuar pipeline
        "revision_humana" -> error o confianza muy baja
    """
    if estado.error:
        return "revision_humana"

    if not estado.clasificacion:
        return "revision_humana"

    if estado.clasificacion.score_confianza < UMBRAL_CONFIANZA_BAJA:
        return "revision_humana"

    return "extraer"


def _nodo_revision_humana(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Nodo terminal HITL.
    Se activa cuando clasificación falla o tiene baja confianza.
    Saltea extracción para no gastar tokens en un documento dudoso.
    """
    score_str = ""
    if estado.clasificacion:
        score_str = f" (confianza: {estado.clasificacion.score_confianza:.0%})"

    motivo = estado.error or f"Clasificación con baja confianza{score_str}"

    estado.decision = DecisionEnrutamiento(
        destino=DestinoEnrutamiento.REVISION_HUMANA,
        requiere_revision_humana=True,
        justificacion=f"Derivado a revisión humana. Motivo: {motivo}",
    )

    logger.warning(
        f"[HITL] {estado.documento_id} → REVISION_HUMANA | {motivo}"
    )
    return estado


def ejecutar_pipeline(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Ejecuta el pipeline completo de triaje clínico.

    Nodos:
      1. clasificar  -> determina tipo y prioridad
      2. extraer     -> extrae entidades clínicas (solo si confianza OK)
      3. enrutar     -> aplica reglas y decide destino

    Args:
        estado: EstadoPipeline construido por api.py con texto o imagenes_data_url

    Returns:
        EstadoPipeline con clasificacion, datos_extraidos y decision poblados
    """
    logger.info(f"[PIPELINE] ══ Iniciando triaje: {estado.documento_id} ══")
    t_inicio = time.perf_counter()
    tiempos: dict[str, float] = {}

    # Opcional: transcribir primero los documentos escaneados 
    # (MEDIFLOW_OCR_PRIMERO=1)
    
    sin_texto = not (estado.texto and estado.texto.strip())
    if (
        ocr_primero_activado()
        and estado.imagenes_data_url
        and sin_texto
        and not estado.error
    ):
        t = time.perf_counter()
        estado = nodo_transcribir(estado)
        tiempos["ocr"] = time.perf_counter() - t

    if estado.error:
        # Error previo (archivo ilegible) o transcripción no confiable:
        # revisión humana sin gastar llamadas al modelo
        estado = _nodo_revision_humana(estado)
        logger.info(
            f"[PIPELINE] ══ Completado: {estado.documento_id} "
            f"→ {estado.decision.destino.value} ══"
        )
        return estado

    # Nodo 1: Clasificar
    t = time.perf_counter()
    estado = nodo_clasificar(estado)
    tiempos["clasificar"] = time.perf_counter() - t

    # Bifurcación post-clasificación
    siguiente = _edge_post_clasificar(estado)

    if siguiente == "revision_humana":
        estado = _nodo_revision_humana(estado)

    else:
        # Nodo 2: Extraer
        t = time.perf_counter()
        estado = nodo_extraer(estado)
        tiempos["extraer"] = time.perf_counter() - t

        # Nodo 3: Enrutar
        estado = nodo_enrutar(estado)

    detalle = ", ".join(f"{k}={v:.1f}s" for k, v in tiempos.items())
    logger.info(
        f"[PIPELINE] tiempos: {detalle}, total={time.perf_counter() - t_inicio:.1f}s"
    )

    destino = estado.decision.destino.value if estado.decision else "N/A"
    logger.info(
        f"[PIPELINE] ══ Completado: {estado.documento_id} → {destino} ══"
    )

    return estado
