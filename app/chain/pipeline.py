"""
MediFlow  Pipeline principal
Ensambla los nodos en secuencia con bifurcaciones condicionales.

Flujo:
  ingestar → validar_documento_medico ── no médico ──> RECHAZADO_NO_MEDICO
                        ↓ (médico o duda)
                     clasificar → [score < 0.6?] → REVISION_HUMANA
                        ↓ (score OK)
                     extraer → enrutar → FIN
"""

from __future__ import annotations

import logging
import time

from app.chain.classify import nodo_clasificar
from app.chain.extract import nodo_extraer
from app.chain.router import (
    UMBRAL_CONFIANZA_BAJA,
    _regla_urgencia,
    nodo_enrutar,
)
from app.chain.transcribe import nodo_transcribir, ocr_primero_activado
from app.chain.validate import nodo_validar_documento_medico
from app.models.schemas import (
    DecisionEnrutamiento,
    DestinoEnrutamiento,
    EstadoPipeline,
)

logger = logging.getLogger(__name__)

# Por debajo de este valor no se rechaza: el documento sigue el pipeline y
# probablemente termine en revisión humana. Así evitamos descartar un
# documento clínico real por una respuesta dudosa del modelo.
UMBRAL_RECHAZO = 0.60


def _debe_rechazar(estado: EstadoPipeline) -> bool:
    """True si el gate determinó que no es un documento médico."""
    validacion = estado.validacion_documento
    return bool(
        validacion
        and not validacion.es_documento_medico
        and validacion.confianza >= UMBRAL_RECHAZO
    )


def _nodo_rechazo(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Nodo terminal para archivos que no son documentos médicos.
    No clasifica, no extrae y no se persiste en OCI.
    """
    estado.mensaje_usuario = (
        "El archivo que cargaste no parece ser un documento médico. "
        "Intenta con una receta, un informe de laboratorio o de imágenes, "
        "una orden de procedimiento, una epicrisis, un certificado médico "
        "o una ficha de triaje."
    )
    estado.decision = DecisionEnrutamiento(
        destino=DestinoEnrutamiento.RECHAZADO_NO_MEDICO,
        requiere_revision_humana=False,
        justificacion="Documento rechazado: no parece un documento médico.",
    )
    logger.info(
        "[VALIDAR] %s → RECHAZADO_NO_MEDICO",
        estado.documento_id,
    )
    return estado


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
    # Una señal de urgencia nunca queda en la cola común sin alerta
    urgencia = _regla_urgencia(estado)
    if urgencia:
        estado.decision = urgencia
        logger.warning(
            f"[HITL] {estado.documento_id} → {urgencia.destino.value} | señal crítica"
        )
        return estado

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
      0. validar_documento_medico -> corta el flujo si no es médico
      1. clasificar               -> determina tipo y prioridad
      2. extraer                  -> extrae entidades clínicas (confianza OK)
      3. enrutar                  -> aplica reglas y decide destino

    Args:
        estado: EstadoPipeline construido por api.py con texto o imagenes_data_url

    Returns:
        EstadoPipeline con clasificacion, datos_extraidos y decision poblados
    """
    logger.info(f"[PIPELINE] ══ Iniciando triaje: {estado.documento_id} ══")
    t_inicio = time.perf_counter()
    tiempos: dict[str, float] = {}

    if estado.error:
        # Error de ingesta: no hay contenido que validar ni clasificar.
        estado = _nodo_revision_humana(estado)
        logger.info(
            f"[PIPELINE] ══ Completado: {estado.documento_id} "
            f"→ {estado.decision.destino.value} ══"
        )
        return estado

    # Nodo 0: validar que sea un documento médico antes de gastar más llamadas.
    t = time.perf_counter()
    estado = nodo_validar_documento_medico(estado)
    tiempos["validar"] = time.perf_counter() - t

    if _debe_rechazar(estado):
        estado = _nodo_rechazo(estado)
        logger.info(
            f"[PIPELINE] ══ Completado: {estado.documento_id} "
            f"→ {estado.decision.destino.value} ══"
        )
        return estado

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
        # Transcripción no confiable: revisión humana sin seguir el pipeline
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
