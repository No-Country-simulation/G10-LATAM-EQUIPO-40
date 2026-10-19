from __future__ import annotations
import logging
import re
import unicodedata

from app.models.schemas import (
    DecisionEnrutamiento, DestinoEnrutamiento, EstadoPipeline,
    NivelPrioridad, Notificacion, TipoDocumento,
)

logger = logging.getLogger(__name__)

UMBRAL_CONFIANZA_BAJA  = 0.60
UMBRAL_CONFIANZA_MEDIA = 0.80

KEYWORDS_CRITICOS = {
    "tep", "tromboembolismo", "embolia pulmonar", "infarto", "iam", "sindrome coronario",
    "acv", "ictus", "stroke", "hemorragia", "sepsis", "shock",
    "insuficiencia respiratoria aguda", "paro cardiaco", "parada cardiaca",
    "neumotorax", "abdomen agudo", "meningitis", "anafilaxia",
    "edema agudo de pulmon", "cetoacidosis",
}

_KW_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in sorted(KEYWORDS_CRITICOS, key=len, reverse=True)) + r")\b")
_MAX_RESUMEN = 80

DESTINO_POR_TIPO: dict[TipoDocumento, DestinoEnrutamiento] = {
    TipoDocumento.RECETA_MEDICA:       DestinoEnrutamiento.FARMACIA,
    TipoDocumento.INFORME_IMAGENES:    DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.INFORME_LABORATORIO: DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.ORDEN_PROCEDIMIENTO: DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES,
    TipoDocumento.EPICRISIS:           DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.CERTIFICADO_MEDICO:  DestinoEnrutamiento.HISTORIA_CLINICA,
    TipoDocumento.HOJA_TRIAJE:         DestinoEnrutamiento.COLA_EMERGENCIA,
    TipoDocumento.DESCONOCIDO:         DestinoEnrutamiento.REVISION_HUMANA,
}

def _score(estado: EstadoPipeline) -> float:
    return estado.clasificacion.score_confianza if estado.clasificacion else 0.0

def _norm(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c))

def _acortar(texto: str, n: int = _MAX_RESUMEN) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"

def _hallazgos_validos(estado: EstadoPipeline) -> list[str]:
    if not estado.datos_extraidos: return []
    return [h.strip() for h in (estado.datos_extraidos.hallazgos_criticos or []) if h and h.strip()]

def _tiene_hallazgo_critico(estado: EstadoPipeline) -> bool:
    if not estado.datos_extraidos: return False
    if _hallazgos_validos(estado): return True
    textos = [estado.datos_extraidos.diagnostico_principal or "", estado.datos_extraidos.estudio_realizado or ""]
    return any(_KW_RE.search(_norm(t)) for t in textos)

def _detalle_sospecha(estado: EstadoPipeline) -> str:
    hallazgos = _hallazgos_validos(estado)
    if hallazgos: return "; ".join(_acortar(h, 60) for h in hallazgos[:2])
    datos = estado.datos_extraidos
    for texto in (datos.diagnostico_principal or "", datos.estudio_realizado or ""):
        m = _KW_RE.search(_norm(texto))
        if m: return f"mención de '{m.group(0)}'"
    return "señal crítica no especificada"

def _tiene_campos_faltantes(estado: EstadoPipeline) -> bool:
    if not estado.datos_extraidos: return True
    faltantes = estado.datos_extraidos.campos_faltantes or []
    if len(faltantes) > 2: return True
    for campo in faltantes:
        if campo and "paciente" in campo.lower(): return True
    return False

def _nombre_paciente(estado: EstadoPipeline) -> str:
    try: return estado.datos_extraidos.paciente.nombre or "paciente desconocido"
    except AttributeError: return "paciente desconocido"

def _resumen_critico(estado: EstadoPipeline) -> str | None:
    datos = estado.datos_extraidos
    if not datos: return None
    dx = (datos.diagnostico_principal or "").strip()
    if dx and len(dx) <= _MAX_RESUMEN: return dx
    hallazgos = _hallazgos_validos(estado)
    if hallazgos: return _acortar(hallazgos[0])
    return _acortar(dx) if dx else None

def _regla_error(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    if not estado.error: return None
    return DecisionEnrutamiento(destino=DestinoEnrutamiento.REVISION_HUMANA, requiere_revision_humana=True, justificacion=f"Error en el pipeline: {estado.error}")

def _regla_confianza_baja(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    score = _score(estado)
    if score >= UMBRAL_CONFIANZA_BAJA: return None
    return DecisionEnrutamiento(destino=DestinoEnrutamiento.REVISION_HUMANA, requiere_revision_humana=True, justificacion=f"Score de confianza bajo ({score:.0%}). Requiere validación manual.")

def _especialidad(estado: EstadoPipeline) -> str | None:
    if estado.clasificacion and estado.clasificacion.especialidad:
        esp = estado.clasificacion.especialidad.strip()
        if esp and esp.lower() not in {"ninguna", "desconocida", "no aplica", "n/a", "null"}: return esp
    return None

def _decision_emergencia(estado: EstadoPipeline) -> DecisionEnrutamiento:
    paciente, resumen, esp = _nombre_paciente(estado), _resumen_critico(estado), _especialidad(estado)
    esp_txt = f" | Derivación a: {esp}" if esp else ""
    if resumen:
        justificacion = f"Hallazgo crítico ({resumen}) en {paciente}. Derivar a interconsulta con {esp or 'Guardia / Emergencias'}."
        mensaje = f"⚠️ ALERTA URGENTE: {resumen} — {paciente}{esp_txt} — {estado.canal_origen}"
    else:
        tipo = estado.clasificacion.tipo_documento.value if estado.clasificacion else "Documento"
        justificacion = f"{tipo} clasificado como Urgente en {paciente}. Derivar a interconsulta con {esp or 'Guardia / Emergencias'}."
        mensaje = f"⚠️ ALERTA URGENTE: {tipo} clasificado como Urgente — {paciente}{esp_txt} — {estado.canal_origen}. Revisar el documento."
    return DecisionEnrutamiento(destino=DestinoEnrutamiento.COLA_EMERGENCIA, requiere_revision_humana=False, justificacion=justificacion, notificacion=Notificacion(canal="Alerta_Guardia_Medica", mensaje=mensaje))

def _regla_urgencia(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    prioridad = estado.clasificacion.nivel_prioridad if estado.clasificacion else NivelPrioridad.NORMAL
    if prioridad == NivelPrioridad.URGENTE: return _decision_emergencia(estado)
    if _tiene_hallazgo_critico(estado):
        return DecisionEnrutamiento(destino=DestinoEnrutamiento.REVISION_HUMANA, requiere_revision_humana=True, justificacion=f"Posible hallazgo crítico sin prioridad urgente en la clasificación ({_detalle_sospecha(estado)}). Requiere validación humana.")
    return None

def _regla_auditoria(estado: EstadoPipeline) -> DecisionEnrutamiento | None:
    score, faltantes = _score(estado), _tiene_campos_faltantes(estado)
    if not faltantes and score >= UMBRAL_CONFIANZA_MEDIA: return None
    motivos = []
    if faltantes:
        lista = (estado.datos_extraidos.campos_faltantes or []) if estado.datos_extraidos else []
        motivos.append(f"faltan datos obligatorios ({', '.join(lista)})" if lista else "sin datos extraídos")
    if score < UMBRAL_CONFIANZA_MEDIA: motivos.append(f"confianza {score:.0%} menor al umbral de {UMBRAL_CONFIANZA_MEDIA:.0%}")
    return DecisionEnrutamiento(destino=DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES, requiere_revision_humana=True, justificacion="Requiere auditoría: " + "; ".join(motivos) + ".")

def _regla_tipo(estado: EstadoPipeline) -> DecisionEnrutamiento:
    tipo = estado.clasificacion.tipo_documento if estado.clasificacion else TipoDocumento.DESCONOCIDO
    score, esp = _score(estado), _especialidad(estado)
    destino = DESTINO_POR_TIPO.get(tipo, DestinoEnrutamiento.REVISION_HUMANA)
    esp_txt = f" (Especialidad sugerida: {esp})" if esp else ""
    return DecisionEnrutamiento(destino=destino, requiere_revision_humana=(tipo == TipoDocumento.DESCONOCIDO), justificacion=f"Documento tipo '{tipo.value}' con confianza {score:.0%}. Enrutado a {destino.value}{esp_txt}.")

def nodo_enrutar(estado: EstadoPipeline) -> EstadoPipeline:
    logger.info(f"[ENRUTAR] {estado.documento_id}")
    for regla in [_regla_error, _regla_confianza_baja, _regla_urgencia, _regla_auditoria]:
        decision = regla(estado)
        if decision is not None:
            estado.decision = decision
            logger.info(f"[ENRUTAR] -> {decision.destino.value} | {decision.justificacion}")
            return estado
    estado.decision = _regla_tipo(estado)
    logger.info(f"[ENRUTAR] -> {estado.decision.destino.value} | {estado.decision.justificacion}")
    return estado