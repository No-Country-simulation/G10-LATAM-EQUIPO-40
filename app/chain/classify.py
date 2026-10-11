"""
MediFlow - Nodo 1: Clasificación
Determina tipo de documento, especialidad, prioridad y score de confianza.

Modelos:
  - texto  -> command-r-plus-08-2024
  - imagen -> command-a-vision-07-2025
"""

from __future__ import annotations
import json
import logging
import os

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.schemas import Clasificacion, EstadoPipeline
from app.models.enums import NivelPrioridad, TipoDocumento
from app.chain.prompts import SYSTEM_CLASIFICAR, PROMPT_CLASIFICAR_TEXTO, PROMPT_CLASIFICAR_IMAGEN, SCHEMA_CLASIFICAR

logger = logging.getLogger(__name__)

MODELO_TEXTO  = "command-r-plus-08-2024"
MODELO_VISION = "command-a-vision-07-2025"

def _get_llm(tiene_texto: bool):
    model = MODELO_TEXTO if tiene_texto else MODELO_VISION
    llm = ChatCohere(model=model, temperature=0.1)
    # OJO: response_format debe ir con bind(). Si se pasa al constructor de
    # ChatCohere, langchain-cohere lo descarta y Cohere nunca recibe el esquema.
    return llm.bind(
        response_format={"type": "json_object", "json_schema": SCHEMA_CLASIFICAR}
    )

def _construir_mensajes(estado: EstadoPipeline) -> list:
    """Construye los mensajes según si el contenido es texto o imagen."""
    system = SystemMessage(content=SYSTEM_CLASIFICAR)

    if estado.texto:
        prompt = PROMPT_CLASIFICAR_TEXTO.format(texto=estado.texto[:8000])
        return [system, HumanMessage(content=prompt)]

    # Imagen: uno o varios data URLs (máximo 3 páginas)
    content = [{"type": "text", "text": PROMPT_CLASIFICAR_IMAGEN}]
    for data_url in (estado.imagenes_data_url or [])[:3]:
        content.append({
            "type": "image_url",
            "image_url": {"url": data_url}
        })

    return [system, HumanMessage(content=content)]

def _a_tipo_documento(valor) -> TipoDocumento:
    """Acepta el código del esquema (RECETA_MEDICA) o, por tolerancia, el valor legible."""
    codigo = str(valor if valor is not None else "DESCONOCIDO").strip()
    try:
        return TipoDocumento[codigo]
    except KeyError:
        pass
    try:
        return TipoDocumento(codigo)
    except ValueError:
        raise ValueError(f"tipo_documento inválido en la respuesta del modelo: {codigo!r}")

def _parsear_respuesta(raw: str) -> Clasificacion:
    data = json.loads(raw)

    return Clasificacion(
        tipo_documento=_a_tipo_documento(data.get("tipo_documento")),
        especialidad=data.get("especialidad"),
        nivel_prioridad=NivelPrioridad(data.get("nivel_prioridad", "Normal")),
        score_confianza=float(data.get("score_confianza", 0.5)),
    )

def nodo_clasificar(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Nodo 1 del pipeline.
    Recibe EstadoPipeline, puebla estado.clasificacion y lo devuelve.
    """
    logger.info(f"[CLASIFICAR] {estado.documento_id}")

    tiene_texto = bool(estado.texto and estado.texto.strip())

    try:
        llm = _get_llm(tiene_texto)
        mensajes = _construir_mensajes(estado)
        response = llm.invoke(mensajes)

        # Solo depuración: la respuesta cruda puede contener datos del paciente
        if os.getenv("MEDIFLOW_DEBUG_RAW") == "1":
            logger.info(f"[CLASIFICAR] respuesta cruda: {response.content}")

        estado.clasificacion = _parsear_respuesta(response.content)

        logger.info(
            f"[CLASIFICAR] tipo={estado.clasificacion.tipo_documento.value} | "
            f"prioridad={estado.clasificacion.nivel_prioridad.value} | "
            f"confianza={estado.clasificacion.score_confianza:.0%}"
        )

    except Exception as e:
        logger.error(f"[CLASIFICAR] Error: {e}")
        estado.error = str(e)
        estado.clasificacion = Clasificacion(
            tipo_documento=TipoDocumento.DESCONOCIDO,
            nivel_prioridad=NivelPrioridad.NORMAL,
            score_confianza=0.0,
        )

    return estado
