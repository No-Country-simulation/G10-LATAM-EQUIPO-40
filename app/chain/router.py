"""
MediFlow - Nodo 3: Enrutamiento
Lógica de decisión condicional pura, sin LLM.
Determina el destino del documento según reglas de negocio.

Orden de precedencia:
  1. Error en pipeline              -> REVISION_HUMANA
  2. score_confianza < 0.6          -> REVISION_HUMANA
  3. Hallazgo crítico o Urgente     -> COLA_EMERGENCIA
  4. Campos faltantes o score < 0.8 -> AUDITORIA_AUTORIZACIONES
  5. Tipo de documento              -> destino específico
"""

from __future__ import annotations

import logging

from app.models.schemas import (
    DecisionEnrutamiento,
    DestinoEnrutamiento,
    EstadoPipeline,
    NivelPrioridad,
    Notificacion,
    TipoDocumento,
)

logger = logging.getLogger(__name__)

UMBRAL_CONFIANZA_BAJA  = 0.60
UMBRAL_CONFIANZA_MEDIA = 0.80

KEYWORDS_CRITICOS = {
    "tep", "tromboembolismo", "embolia pulmonar",
    "infarto", "iam", "sindrome coronario",
    "acv", "ictus", "stroke",
    "hemorragia", "sepsis", "shock",
    "insuficiencia respiratoria aguda",
    "paro cardiaco", "parada cardiaca",
    "neumotorax", "abdomen agudo",
    "meningitis", "anafilaxia",
    "edema agudo de pulmon", "cetoacidosis",
}

DESTINO_POR_TIPO: dict[TipoDocumento, DestinoEnrutamiento] = {
    TipoDocumento.RECETA_MEDICA:       DestinoEnrutamiento.FARMACIA,
    TipoDocumento.INFORME_IMAGENES:    DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.INFORME_LABORATORIO: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.ORDEN_PROCEDIMIENTO: DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES,
    TipoDocumento.EPICRISIS:           DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.CERTIFICADO_MEDICO:  DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.DESCONOCIDO:         DestinoEnrutamiento.REVISION_HUMANA,
}

def _score(estado: EstadoPipeline) -> float:
    return estado.clasificacion.score_confianza if estado.clasificacion else 0.0

def _tiene_hallazgo_critico(estado: EstadoPipeline) -> bool:
    if not estado.datos_extraidos:
        return False

    # Lista explícita de hallazgos críticos
    hallazgos = estado.datos_extraidos.hallazgos_criticos or []
    if any(h and h.strip() for h in hallazgos):
        return True

    # Keywords en diagnóstico y estudio
    textos = [
        estado.datos_extraidos.diagnostico_principal or "",
        estado.datos_extraidos.estudio_realizado or "",
    ]
    for texto in textos:
        texto_norm = texto.lower()
        if any(kw in texto_norm for kw in KEYWORDS_CRITICOS):
            return True

    return False

def _tiene_campos_faltantes(estado: EstadoPipeline) -> bool:
    if not estado.datos_extraidos:
        return True

    faltantes = estado.datos_extraidos.campos_faltantes or []

    if len(faltantes) > 2:
        return True

    for campo in faltantes:
        if campo and "paciente" in campo.lower():
            return True

    return False

def _nombre_paciente(estado: EstadoPipeline) -> str:
    try:
        return estado.datos_extraidos.paciente.nombre or "paciente desconocido"
    except AttributeError:
        return "paciente desconocido"

def _diagnostico(estado: EstadoPipeline) -> str:
    try:
        return estado.datos_extraidos.diagnostico_principal or "diagnóstico no disponible"
    except AttributeError:
        return "diagnóstico no disponible"

def _regla_error(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    if not estado.error:
        return None
    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.REVISION_HUMANA,
        requiere_revision_humana=True,
        justificacion=f"Error en el pipeline: {estado.error}",
    )

def _regla_confianza_baja(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    score = _score(estado)
    if score >= UMBRAL_CONFIANZA_BAJA:
        return None
    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.REVISION_HUMANA,
        requiere_revision_humana=True,
        justificacion=f"Score de confianza bajo ({score:.0%}). Requiere validación manual.",
    )

def _regla_urgencia(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    prioridad = (
        estado.clasificacion.nivel_prioridad
        if estado.clasificacion
        else NivelPrioridad.NORMAL
    )
    critico = _tiene_hallazgo_critico(estado)

    if not critico and prioridad != NivelPrioridad.URGENTE:
        return None

    paciente = _nombre_paciente(estado)
    dx = _diagnostico(estado)

    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.COLA_EMERGENCIA,
        requiere_revision_humana=False,
        justificacion=f"Hallazgo crítico ({dx}) en {paciente}.",
        notificacion=Notificacion(
            canal="Alerta_Guardia_Medica",
            mensaje=f"⚠️ ALERTA URGENTE: {dx} — {paciente} — {estado.canal_origen}",
        ),
    )

def _regla_auditoria(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    score = _score(estado)
    faltantes = _tiene_campos_faltantes(estado)

    if not faltantes and score >= UMBRAL_CONFIANZA_MEDIA:
        return None

    campos = ", ".join(estado.datos_extraidos.campos_faltantes or []) if estado.datos_extraidos else "no especificados"

    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES,
        requiere_revision_humana=True,
        justificacion=(
            f"Confianza media ({score:.0%}) o campos faltantes: {campos or 'ninguno identificado'}."
        ),
    )

def _regla_tipo(estado: EstadoPipeline) -> DecisionEnrutamiento:
    tipo = (
        estado.clasificacion.tipo_documento
        if estado.clasificacion
        else TipoDocumento.DESCONOCIDO
    )
    score = _score(estado)
    destino = DESTINO_POR_TIPO.get(tipo, DestinoEnrutamiento.REVISION_HUMANA)

    return DecisionEnrutamiento(
        destino=destino,
        requiere_revision_humana=(tipo == TipoDocumento.DESCONOCIDO),
        justificacion=(
            f"Documento tipo '{tipo.value}' con confianza {score:.0%}. "
            f"Enrutado a {destino.value}."
        ),
    )

def nodo_enrutar(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Nodo 3 del pipeline.
    Aplica reglas en orden de precedencia y puebla estado.decision.
    """
    logger.info(f"[ENRUTAR] {estado.documento_id}")

    reglas = [
        _regla_error,
        _regla_confianza_baja,
        _regla_urgencia,
        _regla_auditoria,
    ]

    for regla in reglas:
        decision = regla(estado)
        if decision is not None:
            estado.decision = decision
            logger.info(f"[ENRUTAR] → {decision.destino.value} | {decision.justificacion}")
            return estado

    # Ninguna regla de excepción aplicó -> enrutamiento por tipo
    estado.decision = _regla_tipo(estado)
    logger.info(f"[ENRUTAR] → {estado.decision.destino.value} | {estado.decision.justificacion}")
    return estado