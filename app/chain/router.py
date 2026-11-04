from __future__ import annotations

import logging
import re
import unicodedata

from app.models.schemas import (
    DecisionEnrutamiento,
    DestinoEnrutamiento,
    EstadoPipeline,
    NivelPrioridad,
    Notificacion,
    TipoDocumento,
)

logger = logging.getLogger(__name__)

UMBRAL_CONFIANZA_BAJA = 0.60
UMBRAL_CONFIANZA_MEDIA = 0.80

KEYWORDS_CRITICOS = {
    "tep",
    "tromboembolismo",
    "embolia pulmonar",
    "infarto",
    "iam",
    "sindrome coronario",
    "acv",
    "ictus",
    "stroke",
    "hemorragia",
    "sepsis",
    "shock",
    "insuficiencia respiratoria aguda",
    "paro cardiaco",
    "parada cardiaca",
    "neumotorax",
    "abdomen agudo",
    "meningitis",
    "anafilaxia",
    "edema agudo de pulmon",
    "cetoacidosis",
}

_KW_RE = re.compile(
    r"\b(?:"
    + "|".join(
        re.escape(k) for k in sorted(KEYWORDS_CRITICOS, key=len, reverse=True)
    )
    + r")(?:es|s)?\b"
)
_MAX_RESUMEN = 80

# Negación en la misma frase, antes del término crítico.
_CORTE_FRASE = re.compile(r"[.,;:\n]")
_AFIRMA_DUDA = re.compile(r"\bno\s+(?:se\s+)?(?:puede\s+)?descarta")
_NIEGA = re.compile(
    r"\b(?:descarta\w*|descartad\w*|sin|no|niega|niegan|negativ\w*|ausencia|ningun\w*)\b"
)
_VENTANA_NEGACION = 40

DESTINO_POR_TIPO: dict[TipoDocumento, DestinoEnrutamiento] = {
    TipoDocumento.RECETA_MEDICA: DestinoEnrutamiento.FARMACIA,
    TipoDocumento.INFORME_IMAGENES: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.INFORME_LABORATORIO: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.ORDEN_PROCEDIMIENTO: DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES,
    TipoDocumento.EPICRISIS: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.CERTIFICADO_MEDICO: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.HOJA_TRIAJE: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.DESCONOCIDO: DestinoEnrutamiento.REVISION_HUMANA,
}


def _score(estado: EstadoPipeline) -> float:
    return (
        estado.clasificacion.score_confianza if estado.clasificacion else 0.0
    )


def _norm(texto: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(c)
    )


def _acortar(texto: str, n: int = _MAX_RESUMEN) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def _hallazgos_validos(estado: EstadoPipeline) -> list[str]:
    if not estado.datos_extraidos:
        return []
    return [
        h.strip()
        for h in (estado.datos_extraidos.hallazgos_criticos or [])
        if h and h.strip()
    ]


def _esta_negado(texto: str, inicio: int) -> bool:
    """True si la frase niega el término crítico que empieza en `inicio`."""
    previo = texto[max(0, inicio - _VENTANA_NEGACION) : inicio]
    previo = _CORTE_FRASE.split(previo)[-1]
    if _AFIRMA_DUDA.search(previo):  # "no se descarta TEP" sigue siendo sospecha
        return False
    return bool(_NIEGA.search(previo))


def _termino_critico(texto: str) -> str | None:
    """Primer término crítico afirmado en el texto, o None."""
    normalizado = _norm(texto)
    for m in _KW_RE.finditer(normalizado):
        if not _esta_negado(normalizado, m.start()):
            return m.group(0)
    return None


def _textos_a_revisar(estado: EstadoPipeline) -> list[str]:
    """Campos extraídos y texto original: el modelo puede omitir un hallazgo."""
    datos = estado.datos_extraidos
    return [
        datos.diagnostico_principal or "" if datos else "",
        datos.estudio_realizado or "" if datos else "",
        estado.texto or "",
    ]


def _tiene_hallazgo_critico(estado: EstadoPipeline) -> bool:
    if _hallazgos_validos(estado):
        return True
    return any(_termino_critico(t) for t in _textos_a_revisar(estado))


def _detalle_sospecha(estado: EstadoPipeline) -> str:
    hallazgos = _hallazgos_validos(estado)
    if hallazgos:
        return "; ".join(_acortar(h, 60) for h in hallazgos[:2])
    for texto in _textos_a_revisar(estado):
        termino = _termino_critico(texto)
        if termino:
            return f"mención de '{termino}'"
    return "señal crítica no especificada"


def _tiene_campos_faltantes(estado: EstadoPipeline) -> bool:
    if not estado.datos_extraidos:
        return True
    # Cualquier campo obligatorio faltante va a auditoría.
    return bool(estado.datos_extraidos.campos_faltantes)


def _nombre_paciente(estado: EstadoPipeline) -> str:
    try:
        return estado.datos_extraidos.paciente.nombre or "paciente desconocido"
    except AttributeError:
        return "paciente desconocido"


def _resumen_critico(estado: EstadoPipeline) -> str | None:
    datos = estado.datos_extraidos
    if not datos:
        return None
    dx = (datos.diagnostico_principal or "").strip()
    if dx and len(dx) <= _MAX_RESUMEN:
        return dx
    hallazgos = _hallazgos_validos(estado)
    if hallazgos:
        return _acortar(hallazgos[0])
    return _acortar(dx) if dx else None


def _regla_error(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    if not estado.error:
        return None
    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.REVISION_HUMANA,
        requiere_revision_humana=True,
        justificacion=f"Error en el pipeline: {estado.error}",
    )


def _regla_confianza_baja(
    estado: EstadoPipeline,
) -> DecisionEnrutamiento | None:
    score = _score(estado)
    if score >= UMBRAL_CONFIANZA_BAJA:
        return None
    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.REVISION_HUMANA,
        requiere_revision_humana=True,
        justificacion=f"Score de confianza bajo ({score:.0%}). Requiere validación manual.",
    )


def _especialidad(estado: EstadoPipeline) -> str | None:
    if estado.clasificacion and estado.clasificacion.especialidad:
        esp = estado.clasificacion.especialidad.strip()
        if esp and esp.lower() not in {
            "ninguna",
            "desconocida",
            "no aplica",
            "n/a",
            "null",
        }:
            return esp
    return None


def _decision_emergencia(estado: EstadoPipeline) -> DecisionEnrutamiento:
    paciente, resumen, esp = (
        _nombre_paciente(estado),
        _resumen_critico(estado),
        _especialidad(estado),
    )
    esp_txt = f" | Derivación a: {esp}" if esp else ""
    motivos_duda = []
    if estado.error:
        motivos_duda.append("la lectura del documento falló")
    if _score(estado) < UMBRAL_CONFIANZA_BAJA:
        motivos_duda.append(f"confianza {_score(estado):.0%}")
    validar = (
        f" Validar contra el documento original ({', '.join(motivos_duda)})."
        if motivos_duda
        else ""
    )
    if resumen:
        justificacion = f"Hallazgo crítico ({resumen}) en {paciente}. Derivar a interconsulta con {esp or 'Guardia / Emergencias'}.{validar}"
        mensaje = f"⚠️ ALERTA URGENTE: {resumen} — {paciente}{esp_txt} — {estado.canal_origen}"
    else:
        tipo = (
            estado.clasificacion.tipo_documento.value
            if estado.clasificacion
            else "Documento"
        )
        justificacion = f"{tipo} clasificado como Urgente en {paciente}. Derivar a interconsulta con {esp or 'Guardia / Emergencias'}.{validar}"
        mensaje = f"⚠️ ALERTA URGENTE: {tipo} clasificado como Urgente — {paciente}{esp_txt} — {estado.canal_origen}. Revisar el documento."
    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.COLA_EMERGENCIA,
        requiere_revision_humana=False,
        justificacion=justificacion,
        notificacion=Notificacion(
            canal="Alerta_Guardia_Medica", mensaje=mensaje
        ),
    )


def _regla_urgencia(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    prioridad = (
        estado.clasificacion.nivel_prioridad
        if estado.clasificacion
        else NivelPrioridad.NORMAL
    )
    if prioridad == NivelPrioridad.URGENTE:
        return _decision_emergencia(estado)
    if _tiene_hallazgo_critico(estado):
        detalle = _detalle_sospecha(estado)
        return DecisionEnrutamiento(
            destino=DestinoEnrutamiento.REVISION_HUMANA,
            requiere_revision_humana=True,
            revision_prioritaria=True,
            justificacion=f"Posible hallazgo crítico sin prioridad urgente en la clasificación ({detalle}). Requiere validación humana.",
            notificacion=Notificacion(
                canal="Alerta_Revision_Prioritaria",
                mensaje=f"⚠️ POSIBLE URGENCIA: {detalle} — {_nombre_paciente(estado)} — {estado.canal_origen}. Revisar con prioridad.",
            ),
        )
    return None


def _regla_auditoria(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    score, faltantes = _score(estado), _tiene_campos_faltantes(estado)
    if not faltantes and score >= UMBRAL_CONFIANZA_MEDIA:
        return None
    motivos = []
    if faltantes:
        lista = (
            (estado.datos_extraidos.campos_faltantes or [])
            if estado.datos_extraidos
            else []
        )
        motivos.append(
            f"faltan datos obligatorios ({', '.join(lista)})"
            if lista
            else "sin datos extraídos"
        )
    if score < UMBRAL_CONFIANZA_MEDIA:
        motivos.append(
            f"confianza {score:.0%} menor al umbral de {UMBRAL_CONFIANZA_MEDIA:.0%}"
        )
    return DecisionEnrutamiento(
        destino=DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES,
        requiere_revision_humana=True,
        justificacion="Requiere auditoría: " + "; ".join(motivos) + ".",
    )


def _regla_tipo(estado: EstadoPipeline) -> DecisionEnrutamiento:
    tipo = (
        estado.clasificacion.tipo_documento
        if estado.clasificacion
        else TipoDocumento.DESCONOCIDO
    )
    score, esp = _score(estado), _especialidad(estado)
    prioridad = (
        estado.clasificacion.nivel_prioridad
        if estado.clasificacion
        else NivelPrioridad.NORMAL
    )
    esp_txt = f" (Especialidad sugerida: {esp})" if esp else ""

    # Criterio clínico diferenciado para Triaje Hospitalario
    if tipo == TipoDocumento.HOJA_TRIAJE:
        if prioridad == NivelPrioridad.ALTA:
            destino = DestinoEnrutamiento.COLA_EMERGENCIA
            justificacion = f"Triaje con Prioridad Alta (confianza {score:.0%}). Enrutado a Guardia/Emergencias para atención prioritaria{esp_txt}."
        else:
            destino = DestinoEnrutamiento.HISTORIA_CLINICA
            justificacion = f"Triaje clasificado como Prioridad {prioridad.value} (confianza {score:.0%}). Registrado en Historia Clínica para atención ambulatoria según turno de espera{esp_txt}."
        return DecisionEnrutamiento(
            destino=destino,
            requiere_revision_humana=False,
            justificacion=justificacion,
        )

    destino = DESTINO_POR_TIPO.get(tipo, DestinoEnrutamiento.REVISION_HUMANA)
    return DecisionEnrutamiento(
        destino=destino,
        requiere_revision_humana=(tipo == TipoDocumento.DESCONOCIDO),
        justificacion=f"Documento tipo '{tipo.value}' con confianza {score:.0%}. Enrutado a {destino.value}{esp_txt}.",
    )


def nodo_enrutar(estado: EstadoPipeline) -> EstadoPipeline:
    logger.info("[ENRUTAR] Aplicando reglas de enrutamiento…")
    # La urgencia va primero: un error o baja confianza no debe silenciar una alerta.
    for regla in [
        _regla_urgencia,
        _regla_error,
        _regla_confianza_baja,
        _regla_auditoria,
    ]:
        decision = regla(estado)
        if decision is not None:
            estado.decision = decision
            logger.info(
                f"[ENRUTAR] -> {decision.destino.value} | {decision.justificacion}"
            )
            return estado
    estado.decision = _regla_tipo(estado)
    logger.info(
        f"[ENRUTAR] -> {estado.decision.destino.value} | {estado.decision.justificacion}"
    )
    return estado
