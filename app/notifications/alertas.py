"""
MediFlow - Alertas por correo al terminar de procesar un documento.

El correo solo lleva datos operativos (ID, tipo, prioridad y destino). Los datos
del paciente y el diagnóstico quedan en la aplicación.

Una falla al enviar nunca detiene el pipeline: se registra y se informa en la UI.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)

TIMEOUT_SMTP = 8  # segundos: el usuario espera el resultado en pantalla

EVENTOS = {
    "urgente": ("URGENTE", "Documento derivado a emergencia."),
    "prioritaria": (
        "REVISIÓN PRIORITARIA",
        "Posible hallazgo crítico: revisar antes que el resto de la cola.",
    ),
    "revision": ("REVISIÓN", "Documento retenido para revisión humana."),
    "completado": ("PROCESADO", "Documento procesado y enrutado."),
    "error": ("ERROR", "El documento terminó sin decisión de enrutamiento."),
}


def _valor(dato, defecto: str = "—") -> str:
    """Texto de un Enum o de un valor ya serializado."""
    dato = getattr(dato, "value", dato)
    return defecto if dato in (None, "") else str(dato)


def _lista(variable: str) -> list[str]:
    return [c.strip() for c in os.getenv(variable, "").split(",") if c.strip()]


def clasificar_evento(resultado: dict) -> str:
    decision = resultado.get("decision") or {}
    if not decision:
        return "error"
    prioridad = _valor((resultado.get("clasificacion") or {}).get("nivel_prioridad"))
    if "Emergencia" in _valor(decision.get("destino")) or prioridad == "Urgente":
        return "urgente"
    if decision.get("revision_prioritaria"):
        return "prioritaria"
    if decision.get("requiere_revision_humana"):
        return "revision"
    return "completado"


def destinatarios(evento: str) -> list[str]:
    """Los urgentes pueden ir además a una lista propia, como Guardia."""
    correos = _lista("ALERTA_DESTINATARIOS")
    if evento in ("urgente", "prioritaria"):
        correos += _lista("ALERTA_DESTINATARIOS_URGENTES")
    return list(dict.fromkeys(correos))


def construir_correo(resultado: dict, canal: str, para: list[str]) -> EmailMessage:
    evento = clasificar_evento(resultado)
    etiqueta, resumen = EVENTOS[evento]
    clf = resultado.get("clasificacion") or {}
    decision = resultado.get("decision") or {}
    doc_id = _valor(resultado.get("documento_id"))

    lineas = [
        resumen,
        "",
        f"Documento: {doc_id}",
        f"Canal de origen: {_valor(canal)}",
        f"Tipo: {_valor(clf.get('tipo_documento'))}",
        f"Prioridad: {_valor(clf.get('nivel_prioridad'))}",
        f"Destino: {_valor(decision.get('destino'))}",
        "Requiere revisión humana: "
        + ("Sí" if decision.get("requiere_revision_humana") else "No"),
    ]
    url = os.getenv("APP_URL", "").strip()
    if url:
        lineas += ["", f"Ver en MediFlow: {url}"]
    lineas += [
        "",
        "Los datos clínicos no se incluyen en este correo.",
        "Proyecto demostrativo, no es un dispositivo médico.",
    ]

    correo = EmailMessage()
    correo["Subject"] = f"[MediFlow][{etiqueta}] {doc_id}"
    correo["From"] = os.getenv("ALERTA_REMITENTE") or os.getenv("SMTP_USUARIO", "")
    correo["To"] = ", ".join(para)
    correo.set_content("\n".join(lineas))
    return correo


def _enviar(correo: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    puerto = int(os.getenv("SMTP_PUERTO", "587"))
    usuario = os.getenv("SMTP_USUARIO", "")
    clave = os.getenv("SMTP_CLAVE", "")
    contexto = ssl.create_default_context()

    if puerto == 465:
        servidor = smtplib.SMTP_SSL(
            host, puerto, timeout=TIMEOUT_SMTP, context=contexto
        )
    else:
        servidor = smtplib.SMTP(host, puerto, timeout=TIMEOUT_SMTP)

    with servidor:
        if puerto != 465:
            servidor.starttls(context=contexto)
        if usuario:
            servidor.login(usuario, clave)
        servidor.send_message(correo)


def notificar_documento(resultado: dict, canal: str) -> dict:
    """Envía el aviso y devuelve {'estado': 'enviado'|'no_configurado'|'error', ...}."""
    evento = clasificar_evento(resultado)
    para = destinatarios(evento)
    doc_id = _valor(resultado.get("documento_id"))

    if not os.getenv("SMTP_HOST") or not para:
        logger.info("[ALERTA] %s: correo no configurado.", doc_id)
        return {"estado": "no_configurado", "evento": evento}

    try:
        _enviar(construir_correo(resultado, canal, para))
    except Exception as e:
        # Solo el tipo de error: el mensaje podría traer datos de la cuenta
        logger.error("[ALERTA] %s: no se pudo enviar (%s).", doc_id, type(e).__name__)
        return {"estado": "error", "evento": evento}

    logger.info("[ALERTA] %s: aviso '%s' enviado.", doc_id, evento)
    return {"estado": "enviado", "evento": evento}
