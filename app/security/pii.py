"""
MediFlow - Redacción de datos personales en el borde de observabilidad.

Los documentos del proyecto son sintéticos, pero los logs pueden acabar en la
consola, en la UI de Streamlit o en una captura de la demo. Este módulo
enmascara nombres y números de documento **solo al formatear logs**: no toca
`EstadoPipeline`, ni los prompts, ni lo que se envía al modelo.

Uso:
    handler.setFormatter(RedactingFormatter("%(levelname)s: %(message)s"))

    logger.info("paciente=%s", mask_nombre(nombre))
    logger.info("[ENRUTAR] %s", redactar(justificacion, nombres=[nombre]))
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

__all__ = [
    "RedactingFormatter",
    "mask_documento",
    "mask_nombre",
    "redactar",
]

_ANCHO_NOMBRE = 4
_VACIO = "—"

# Correos y teléfonos primero: si se parte el número, el documento queda suelto.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TELEFONO = re.compile(
    r"(?<![\w.-])(?:\+?57[\s.-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}(?![\w.-])"
)
# Cédulas escritas con puntos: 1.020.304.567
_DOC_CON_PUNTOS = re.compile(
    r"(?<![\w.-])\d{1,3}(?:\.\d{3}){2,4}(?![\w.-])"
)
# Cédulas y números de 6 a 12 dígitos, sin tocar ids tipo DOC-1723456789.
_DOC = re.compile(r"(?<![\w.-])\d{6,12}(?![\w.-])")


def mask_nombre(nombre: str | None, ancho: int = _ANCHO_NOMBRE) -> str:
    """Conserva solo la inicial de cada palabra: 'Ana Soto' -> 'A** S***'."""
    if not nombre or not nombre.strip():
        return _VACIO
    return " ".join(
        palabra
        if len(palabra) == 1
        else palabra[0] + "*" * min(len(palabra) - 1, ancho)
        for palabra in nombre.split()
    )


def mask_documento(documento: str | None, visibles: int = 0) -> str:
    """
    Enmascara un número de documento.

    Por defecto no muestra ningún dígito: en Colombia los últimos dígitos son
    justo los que discriminan. Usa `visibles > 0` solo en canales restringidos
    (soporte presencial), nunca en los logs de la aplicación.
    """
    if not documento or not documento.strip():
        return _VACIO
    digitos = re.sub(r"\D", "", documento)
    if not digitos:
        return _VACIO
    if visibles <= 0:
        return "***"
    visibles = max(0, min(visibles, len(digitos) - 3))
    if visibles == 0:
        return "***"
    return "*" * (len(digitos) - visibles) + digitos[-visibles:]


def redactar(texto: str, nombres: Iterable[str] | None = None) -> str:
    """
    Redacta lo reconocible por patrón (documentos, teléfonos, correos) y, si se
    pasan, los nombres conocidos del documento.

    El texto clínico libre (diagnósticos, hallazgos) no se puede reconocer por
    patrón: eso se resuelve en cada call site, no aquí.
    """
    if not texto:
        return texto

    for nombre in nombres or ():
        if not nombre or not nombre.strip():
            continue
        nombre = nombre.strip()
        patron = re.compile(
            rf"(?<!\w){re.escape(nombre)}(?!\w)", re.IGNORECASE
        )
        texto = patron.sub(mask_nombre(nombre), texto)

    texto = _EMAIL.sub("[correo]", texto)
    texto = _TELEFONO.sub(lambda m: mask_documento(m.group()), texto)
    texto = _DOC_CON_PUNTOS.sub(lambda m: mask_documento(m.group()), texto)
    texto = _DOC.sub(lambda m: mask_documento(m.group()), texto)
    return texto


class RedactingFormatter(logging.Formatter):
    """
    Formatter que redacta el texto final, ya interpolado.

    Se aplica en el handler, no en el logger: así cubre los records de los
    loggers hijos, las llamadas `logger.info("... %s", valor)` y el traceback
    de `logger.exception`.
    """

    def format(self, record: logging.LogRecord) -> str:
        return redactar(super().format(record))
