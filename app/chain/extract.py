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
import os
import re

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.schemas import (
    DatosExtraidos,
    EstadoPipeline,
    Medicamento,
    MedicoSolicitante,
    Paciente,
)
from app.chain.llm_utils import invocar_con_reintentos
from app.models.enums import TipoDocumento
from app.chain.prompts import (
    SYSTEM_EXTRAER,
    PROMPT_EXTRAER_TEXTO,
    PROMPT_EXTRAER_IMAGEN,
    SCHEMA_EXTRAER,
)

logger = logging.getLogger(__name__)

MODELO_TEXTO  = "command-r-plus-08-2024"
MODELO_VISION = "command-a-vision-07-2025"

def _get_llm(tiene_texto: bool):
    model = MODELO_TEXTO if tiene_texto else MODELO_VISION
    llm = ChatCohere(model=model, temperature=0.0)
    # OJO: response_format debe ir con bind(). Si se pasa al constructor de
    # ChatCohere, langchain-cohere lo descarta y Cohere nunca recibe el esquema.
    return llm.bind(
        response_format={"type": "json_object", "json_schema": SCHEMA_EXTRAER}
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

# Textos de relleno que el modelo escribe cuando no hay dato (el esquema no le
# permite devolver null). Nunca deben tratarse como información real.
_RELLENOS = {
    "null", "none", "nil", "n/a", "na", "n.a", "-", "--", "?", "??", "???",
    "no disponible", "no especificado", "no identificado", "sin dato", "sin datos",
    "desconocido", "ilegible", "no legible", "no aplica", "undefined",
    "firma ilegible", "sin firma", "en blanco", "no consta",
}

def _limpiar(valor, descartar_interrogaciones: bool = False):
    """Convierte textos de relleno ('null', '???') en None. Deja pasar lo demás."""
    if not isinstance(valor, str):
        return valor
    v = valor.strip()
    if not v or not re.search(r"\w", v):
        return None
    if v.lower().strip(" .:;()[]{}\"'") in _RELLENOS:
        return None
    # Nombres o matrículas con varios '?' (p. ej. "Dr. ???") no son datos reales
    if descartar_interrogaciones and v.count("?") >= 2:
        return None
    return v

def _a_lista(valor) -> list | None:
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        return None
    limpios = [x for x in (_limpiar(i) for i in valor) if isinstance(x, str)]
    return limpios or None

def _a_entero(valor) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str):
        m = re.search(r"\d+", valor)
        return int(m.group()) if m else None
    return None

def _parsear_respuesta(raw: str) -> DatosExtraidos:
    data = json.loads(raw)

    # Paciente
    nombre_paciente = _limpiar(data.get("nombre_paciente"), True)
    edad_paciente   = _a_entero(data.get("edad_paciente"))
    doc_paciente    = _limpiar(data.get("documento_paciente"), True)
    paciente = Paciente(
        nombre=nombre_paciente,
        edad=edad_paciente,
        documento_identidad=doc_paciente,
    ) if any([nombre_paciente, edad_paciente, doc_paciente]) else None

    # Médico
    nombre_medico       = _limpiar(data.get("nombre_medico"), True)
    matricula_medico    = _limpiar(data.get("matricula_medico"), True)
    especialidad_medico = _limpiar(data.get("especialidad_medico"))
    medico = MedicoSolicitante(
        nombre=nombre_medico,
        matricula=matricula_medico,
        especialidad=especialidad_medico,
    ) if any([nombre_medico, matricula_medico, especialidad_medico]) else None

    # Medicamentos
    meds_raw = data.get("medicamentos") or []
    if not isinstance(meds_raw, list):
        meds_raw = []
    medicamentos = [
        Medicamento(
            nombre=_limpiar(med.get("nombre")),
            dosis=_limpiar(med.get("dosis")),
            frecuencia=_limpiar(med.get("frecuencia")),
            duracion=_limpiar(med.get("duracion")),
        )
        for med in meds_raw
        if isinstance(med, dict) and _limpiar(med.get("nombre"))
    ] or None

    return DatosExtraidos(
        paciente=paciente,
        medico_solicitante=medico,
        estudio_realizado=_limpiar(data.get("estudio_realizado")),
        diagnostico_principal=_limpiar(data.get("diagnostico_principal")),
        cie10_sugerido=_limpiar(data.get("cie10_sugerido")),
        medicamentos=medicamentos,
        estudios_solicitados=_a_lista(data.get("estudios_solicitados")),
        hallazgos_criticos=_a_lista(data.get("hallazgos_criticos")),
        campos_faltantes=_a_lista(data.get("campos_faltantes")),
    )

# Campos obligatorios por tipo de documento. La lista de faltantes se calcula en
# código a partir de lo realmente extraído: la que declara el modelo no es confiable.
_OBLIGATORIOS: dict[TipoDocumento, list[str]] = {
    TipoDocumento.RECETA_MEDICA:       ["paciente", "médico", "matrícula", "medicamentos"],
    TipoDocumento.INFORME_IMAGENES:    ["paciente", "médico", "estudio realizado", "diagnóstico"],
    TipoDocumento.INFORME_LABORATORIO: ["paciente", "médico", "estudio realizado"],
    TipoDocumento.ORDEN_PROCEDIMIENTO: ["paciente", "médico", "matrícula", "estudios solicitados"],
    TipoDocumento.EPICRISIS:           ["paciente", "médico", "diagnóstico"],
    TipoDocumento.CERTIFICADO_MEDICO:  ["paciente", "médico", "matrícula"],
    TipoDocumento.DESCONOCIDO:         ["paciente", "médico"],
}

def _presente(datos: DatosExtraidos, campo: str) -> bool:
    pac, med = datos.paciente, datos.medico_solicitante
    if campo == "paciente":
        return bool(pac and pac.nombre)
    if campo == "médico":
        return bool(med and med.nombre)
    if campo == "matrícula":
        return bool(med and med.matricula)
    if campo == "estudio realizado":
        return bool(datos.estudio_realizado)
    if campo == "diagnóstico":
        return bool(datos.diagnostico_principal or datos.hallazgos_criticos)
    if campo == "medicamentos":
        return bool(datos.medicamentos)
    if campo == "estudios solicitados":
        return bool(datos.estudios_solicitados)
    return True

def calcular_faltantes(datos: DatosExtraidos, tipo: TipoDocumento) -> list[str] | None:
    obligatorios = _OBLIGATORIOS.get(tipo, _OBLIGATORIOS[TipoDocumento.DESCONOCIDO])
    faltantes = [c for c in obligatorios if not _presente(datos, c)]
    return faltantes or None

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
        response = invocar_con_reintentos(llm, mensajes)

        # Solo para depuración: la respuesta cruda puede contener datos del paciente
        if os.getenv("MEDIFLOW_DEBUG_RAW") == "1":
            logger.info(f"[EXTRAER] respuesta cruda: {response.content}")

        estado.datos_extraidos = _parsear_respuesta(response.content)

        tipo = (
            estado.clasificacion.tipo_documento
            if estado.clasificacion
            else TipoDocumento.DESCONOCIDO
        )
        estado.datos_extraidos.campos_faltantes = calcular_faltantes(estado.datos_extraidos, tipo)

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