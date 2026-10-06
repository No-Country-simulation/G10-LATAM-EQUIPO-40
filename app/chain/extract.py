"""
MediFlow - Nodo 2: Extracción de entidades clínicas
Extrae datos estructurados del documento según su tipo.

Modelos:
  - texto  -> command-r-plus-08-2024
  - imagen -> command-a-vision-07-2025
"""

from __future__ import annotations

import json
import logging

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.schemas import (
    DatosExtraidos,
    EstadoPipeline,
    Medicamento,
    MedicoSolicitante,
    Paciente,
)
from app.chain.prompts import (
    SYSTEM_EXTRAER,
    PROMPT_EXTRAER_TEXTO,
    PROMPT_EXTRAER_IMAGEN,
    SCHEMA_EXTRAER,
)

logger = logging.getLogger(__name__)

MODELO_TEXTO  = "command-r-plus-08-2024"
MODELO_VISION = "command-a-vision-07-2025"

def _get_llm(tiene_texto: bool) -> ChatCohere:
    model = MODELO_TEXTO if tiene_texto else MODELO_VISION
    return ChatCohere(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object", "schema": SCHEMA_EXTRAER},
    )

def _construir_mensajes(estado: EstadoPipeline) -> list:
    system = SystemMessage(content=SYSTEM_EXTRAER)

    if estado.texto:
        prompt = PROMPT_EXTRAER_TEXTO.format(texto=estado.texto[:8000])
        return [system, HumanMessage(content=prompt)]

    content = [{"type": "text", "text": PROMPT_EXTRAER_IMAGEN}]
    for data_url in (estado.imagenes_data_url or [])[:3]:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    return [system, HumanMessage(content=content)]

def _parsear_respuesta(raw: str) -> DatosExtraidos:
    data = json.loads(raw)

    # Paciente
    p = data.get("paciente") or {}
    paciente = Paciente(
        nombre=p.get("nombre"),
        edad=p.get("edad"),
        documento_identidad=p.get("documento_identidad"),
    ) if p else None

    # Médico
    m = data.get("medico_solicitante") or {}
    medico = MedicoSolicitante(
        nombre=m.get("nombre"),
        matricula=m.get("matricula"),
        especialidad=m.get("especialidad"),
    ) if m else None

    # Medicamentos
    meds_raw = data.get("medicamentos") or []
    medicamentos = [
        Medicamento(
            nombre=med["nombre"],
            dosis=med.get("dosis"),
            frecuencia=med.get("frecuencia"),
            duracion=med.get("duracion"),
        )
        for med in meds_raw
        if med.get("nombre")
    ] or None

    return DatosExtraidos(
        paciente=paciente,
        medico_solicitante=medico,
        estudio_realizado=data.get("estudio_realizado"),
        diagnostico_principal=data.get("diagnostico_principal"),
        cie10_sugerido=data.get("cie10_sugerido"),
        medicamentos=medicamentos,
        estudios_solicitados=data.get("estudios_solicitados") or None,
        hallazgos_criticos=data.get("hallazgos_criticos") or None,
        campos_faltantes=data.get("campos_faltantes") or None,
    )

def nodo_extraer(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Nodo 2 del pipeline.
    Recibe EstadoPipeline, puebla estado.datos_extraidos y lo devuelve.
    """
    logger.info(f"[EXTRAER] {estado.documento_id}")

    tiene_texto = bool(estado.texto and estado.texto.strip())

    try:
        llm = _get_llm(tiene_texto)
        mensajes = _construir_mensajes(estado)
        response = llm.invoke(mensajes)

        estado.datos_extraidos = _parsear_respuesta(response.content)

        paciente_nombre = (
            estado.datos_extraidos.paciente.nombre
            if estado.datos_extraidos.paciente
            else "no identificado"
        )
        faltantes = estado.datos_extraidos.campos_faltantes or []

        logger.info(
            f"[EXTRAER] paciente={paciente_nombre} | "
            f"dx={estado.datos_extraidos.diagnostico_principal} | "
            f"faltantes={faltantes}"
        )

    except Exception as e:
        logger.error(f"[EXTRAER] Error: {e}")
        estado.error = str(e)
        estado.datos_extraidos = DatosExtraidos(
            campos_faltantes=["Error en extracción: respuesta inesperada del modelo"]
        )

    return estado