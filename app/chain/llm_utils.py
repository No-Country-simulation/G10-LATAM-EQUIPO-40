"""
MediFlow - Utilidades para llamadas al modelo.
Reintenta errores transitorios (límite de tasa, timeouts, 5xx) con espera creciente.
Los errores del documento o de configuración (400, 401, JSON inválido) NO se reintentan.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_CODIGOS_TRANSITORIOS = {408, 429, 500, 502, 503, 504}
_NOMBRES_TRANSITORIOS = (
    "timeout", "connecterror", "toomanyrequests", "serviceunavailable",
    "gatewaytimeout", "internalservererror", "readerror", "remoteprotocolerror",
)


def es_transitorio(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) in _CODIGOS_TRANSITORIOS:
        return True
    nombre = type(exc).__name__.lower()
    return any(n in nombre for n in _NOMBRES_TRANSITORIOS)


def invocar_con_reintentos(llm, mensajes, intentos: int = 4, espera: float = 4.0):
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
