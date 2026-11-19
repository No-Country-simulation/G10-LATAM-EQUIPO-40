"""
MediFlow - Utilidades para llamadas al modelo.
Reintenta errores transitorios (límite de tasa, timeouts, 5xx) con espera
creciente.
Los errores del documento o de configuración (400, 401, JSON inválido) NO se
reintentan.
"""

from __future__ import annotations

import json
import logging
import time

logger = logging.getLogger(__name__)


def texto_de_respuesta(respuesta) -> str:
    """Devuelve solo el texto final de una respuesta del modelo.

    Con `thinking` activo, langchain-cohere entrega `AIMessage.content` como
    una lista de bloques ({"type": "reasoning", ...} y
    {"type": "text", ...}). Aquí se conserva únicamente el bloque de texto para
    no colar el razonamiento en el JSON ni en la transcripción.
    """
    contenido = getattr(respuesta, "content", respuesta)

    if isinstance(contenido, str):
        return contenido

    if isinstance(contenido, list):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict) and bloque.get("type") == "text":
                texto = bloque.get("text")
                if texto:
                    partes.append(texto)
        return "\n".join(partes)

    return "" if contenido is None else str(contenido)


def parsear_json(respuesta) -> dict:
    """Extrae el primer objeto JSON de la respuesta del modelo.

    Tolera bloques de razonamiento, cercas Markdown (```json) y texto
    alrededor, igual que hacía el antiguo `parsear_json_seguro`.
    """
    texto = texto_de_respuesta(respuesta).strip()

    if not texto:
        raise ValueError("La respuesta del modelo está vacía.")

    if texto.startswith("```"):
        lineas = texto.splitlines()[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        texto = "\n".join(lineas).strip()

    inicio = texto.find("{")
    if inicio == -1:
        raise ValueError(
            "La respuesta del modelo no contiene un objeto JSON: "
            f"{texto[:200]!r}"
        )

    try:
        objeto, _ = json.JSONDecoder().raw_decode(texto[inicio:])
    except json.JSONDecodeError as e:
        finish = getattr(respuesta, "response_metadata", {}).get(
            "finish_reason"
        )
        detalle = f" (finish_reason={finish})" if finish else ""
        raise ValueError(
            f"JSON inválido en la respuesta del modelo{detalle}: {e}"
        ) from e

    if not isinstance(objeto, dict):
        raise TypeError("El JSON de la respuesta no es un objeto.")

    return objeto


_CODIGOS_TRANSITORIOS = {408, 429, 500, 502, 503, 504}
_NOMBRES_TRANSITORIOS = (
    "timeout",
    "connecterror",
    "toomanyrequests",
    "serviceunavailable",
    "gatewaytimeout",
    "internalservererror",
    "readerror",
    "remoteprotocolerror",
)


def es_transitorio(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) in _CODIGOS_TRANSITORIOS:
        return True
    nombre = type(exc).__name__.lower()
    return any(n in nombre for n in _NOMBRES_TRANSITORIOS)


def invocar_con_reintentos(
    llm, mensajes, intentos: int = 4, espera: float = 4.0
):
    """llm.invoke() con hasta `intentos` intentos y esperas de 4s, 8s, 16s."""
    for n in range(1, intentos + 1):
        try:
            return llm.invoke(mensajes)
        except Exception as e:
            if n == intentos or not es_transitorio(e):
                raise
            pausa = espera * 2 ** (n - 1)
            logger.warning(
                f"[LLM] Error transitorio ({type(e).__name__}); "
                f"reintento {n}/{intentos - 1} en {pausa:.0f}s"
            )
            time.sleep(pausa)
