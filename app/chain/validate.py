"""
MediFlow - Gate previo: ¿es un documento médico?

Se ejecuta antes de la clasificación. Si el documento no es médico, el
pipeline se detiene y se devuelve un mensaje para que el usuario cargue otro.
"""

from __future__ import annotations

import logging

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.chain.llm_utils import invocar_con_reintentos, parsear_json
from app.chain.prompts import (
    PROMPT_VALIDAR_IMAGEN,
    PROMPT_VALIDAR_TEXTO,
    SCHEMA_VALIDAR_DOCUMENTO,
    SYSTEM_VALIDAR_DOCUMENTO,
)
from app.models.schemas import EstadoPipeline, ValidacionDocumento

logger = logging.getLogger(__name__)

MODELO_TEXTO = "command-a-plus-05-2026"
MODELO_VISION = "command-a-vision-07-2025"


def _get_llm(tiene_texto: bool):
    llm = ChatCohere(
        model=MODELO_TEXTO if tiene_texto else MODELO_VISION,
        temperature=0.0,
    )
    kwargs = {
        "response_format": {
            "type": "json_object",
            "json_schema": SCHEMA_VALIDAR_DOCUMENTO,
        }
    }
    if tiene_texto:
        kwargs["thinking"] = {"type": "disabled"}
    return llm.bind(**kwargs)


def _construir_mensajes(estado: EstadoPipeline) -> list:
    system = SystemMessage(content=SYSTEM_VALIDAR_DOCUMENTO)

    if estado.texto and estado.texto.strip():
        prompt = PROMPT_VALIDAR_TEXTO.format(texto=estado.texto[:8000])
        return [system, HumanMessage(content=prompt)]

    content = [{"type": "text", "text": PROMPT_VALIDAR_IMAGEN}]
    for data_url in (estado.imagenes_data_url or [])[:3]:
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    return [system, HumanMessage(content=content)]


def _a_bool(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.strip().lower() in {"true", "1", "si", "sí", "yes"}
    return bool(valor)


def _parsear_respuesta(respuesta) -> ValidacionDocumento:
    data = parsear_json(respuesta)

    try:
        confianza = float(data.get("confianza", 0.5))
    except (TypeError, ValueError):
        confianza = 0.5

    return ValidacionDocumento(
        es_documento_medico=_a_bool(data.get("es_documento_medico", True)),
        motivo=(str(data.get("motivo") or "").strip()[:200] or None),
        confianza=max(0.0, min(1.0, confianza)),
    )


def nodo_validar_documento_medico(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Gate previo a la clasificación.

    - Documento médico o duda razonable -> sigue el pipeline.
    - Documento claramente no médico     -> validacion_documento lo indica;
      el pipeline lo rechaza sin clasificar ni guardar.
    - Fallo del modelo                   -> fail-open: se sigue con la
      clasificación para no perder un documento clínico real.
    """
    if (
        not (estado.texto and estado.texto.strip())
        and not estado.imagenes_data_url
    ):
        return estado

    tiene_texto = bool(estado.texto and estado.texto.strip())

    try:
        respuesta = invocar_con_reintentos(
            _get_llm(tiene_texto),
            _construir_mensajes(estado),
            intentos=2,  # el gate no debe demorar 30 s si el modelo falla
            espera=2.0,
        )
        estado.validacion_documento = _parsear_respuesta(respuesta)

        validacion = estado.validacion_documento
        logger.info(
            "[VALIDAR] %s: documento_medico=%s | confianza=%.0f%%",
            estado.documento_id,
            validacion.es_documento_medico,
            validacion.confianza * 100,
        )

    except Exception as e:
        # No se loguea str(e): puede contener texto del documento.
        logger.warning(
            "[VALIDAR] %s: no se pudo validar (%s); "
            "se continúa con la clasificación.",
            estado.documento_id,
            type(e).__name__,
        )

    return estado
