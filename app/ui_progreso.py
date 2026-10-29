"""
MediFlow - Indicador de progreso para Streamlit (electrocardiograma).
Reemplaza a st.spinner: se usa igual, con `with progreso():`.

Las frases se generan EN VIVO desde el logger del pipeline.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from urllib.parse import quote

import streamlit as st

# ──────────────────────────────────────────────────────────────────────
# Traducción de logs → frases legibles para la UI
# ──────────────────────────────────────────────────────────────────────
# El orden importa: se comprueba de arriba a abajo.
REGLAS = [
    ("[PIPELINE] ══ Iniciando", "Iniciando triaje del documento…"),
    ("[PIPELINE] ══ Completado", "Proceso completado."),
    ("[PIPELINE] tiempos:", "Cerrando el pipeline…"),
    ("[OCR]", "Extrayendo el texto de cada página…"),
    ("[TRANSCRIBIR]", "Transcribiendo documento escaneado…"),
    ("[CLASIFICAR]", "Clasificando el documento y leyendo sus datos…"),
    ("[EXTRAER]", "Extrayendo entidades clínicas…"),
    ("[ENRUTAR]", "Decidiendo a dónde enviarlo…"),
    ("[HITL]", "Derivando a revisión humana…"),
    ("[GUARDAR]", "Guardando el expediente…"),
    ("[OCI] Error", "Guardando respaldo (modo simulado)…"),
    ("[OCI-SIM] Guardado", "Respaldo local guardado."),
]


def _traducir(mensaje: str) -> str | None:
    """Devuelve la frase para la UI o None si el log no es relevante."""
    for etiqueta, frase in REGLAS:
        if etiqueta in mensaje:
            return frase
    return None


# ──────────────────────────────────────────────────────────────────────
# SVG del electrocardiograma (igual que antes)
# ──────────────────────────────────────────────────────────────────────
_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 110 40'>"
    "<path d='M2 22 H28 L33 22 L38 8 L45 36 L51 22 H70 L75 16 L80 22 H108' "
    "fill='none' stroke='black' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/></svg>"
)
_URL = "data:image/svg+xml," + quote(_SVG, safe="")


def _html(frases: list[str], segundos: int = 3) -> str:
    """Igual que antes, pero admite 1 sola frase (sin rotación)."""
    if not frases:
        frases = ["Procesando…"]
    if len(frases) == 1:
        spans = f'<span style="opacity:1">{frases[0]}</span>'
        css = (
            ".mf-prog{display:flex;align-items:center;gap:10px;padding:4px 0}"
            ".mf-ecg{width:54px;height:20px;flex:none;color:#3b82f6;background:currentColor;"
            f'-webkit-mask:url("{_URL}") center/contain no-repeat;'
            f'mask:url("{_URL}") center/contain no-repeat;'
            "animation:mfdraw 2.2s linear infinite}"
            ".mf-rot{position:relative;flex:1;min-width:0;height:1.5em}"
            ".mf-rot span{position:absolute;left:0;right:0;white-space:nowrap;"
            "overflow:hidden;text-overflow:ellipsis}"
            "@keyframes mfdraw{0%{clip-path:inset(0 100% 0 0);opacity:1}"
            "70%{clip-path:inset(0);opacity:1}100%{clip-path:inset(0);opacity:0}}"
        )
    else:
        n = len(frases)
        visible = 100 / n
        css = (
            ".mf-prog{display:flex;align-items:center;gap:10px;padding:4px 0}"
            ".mf-ecg{width:54px;height:20px;flex:none;color:#3b82f6;background:currentColor;"
            f'-webkit-mask:url("{_URL}") center/contain no-repeat;'
            f'mask:url("{_URL}") center/contain no-repeat;'
            "animation:mfdraw 2.2s linear infinite}"
            ".mf-rot{position:relative;flex:1;min-width:0;height:1.5em}"
            ".mf-rot span{position:absolute;left:0;right:0;opacity:0;white-space:nowrap;"
            f"overflow:hidden;text-overflow:ellipsis;animation:mfrot{n} {n * segundos}s infinite}}"
            "@keyframes mfdraw{0%{clip-path:inset(0 100% 0 0);opacity:1}"
            "70%{clip-path:inset(0);opacity:1}100%{clip-path:inset(0);opacity:0}}"
            f"@keyframes mfrot{n}{{0%{{opacity:0}}2%{{opacity:1}}"
            f"{visible - 2:.2f}%{{opacity:1}}{visible:.2f}%{{opacity:0}}100%{{opacity:0}}}}"
        )
        spans = "".join(
            f'<span style="animation-delay:{i * segundos}s">{f}</span>'
            for i, f in enumerate(frases)
        )
    return (
        f'<style>{css}</style><div class="mf-prog">'
        f'<div class="mf-ecg"></div><div class="mf-rot">{spans}</div></div>'
    )


# ──────────────────────────────────────────────────────────────────────
# Handler de logging → placeholder de Streamlit
# ──────────────────────────────────────────────────────────────────────
class StreamlitHandler(logging.Handler):
    """Cada log que coincida con una regla actualiza el placeholder."""

    def __init__(
        self,
        placeholder,
        segundos: int = 3,
        logger_objetivo: str | None = None,
    ):
        super().__init__()
        self.placeholder = placeholder
        self.segundos = segundos
        self.logger_objetivo = logger_objetivo
        self.frases: list[str] = []

    def emit(self, record):
        print(
            "LOG:",
            record.name,
            "|",
            record.levelname,
            "|",
            record.getMessage(),
        )
        # Si nos han dicho qué logger escuchar, filtramos
        if self.logger_objetivo and record.name != self.logger_objetivo:
            return
        try:
            frase = _traducir(record.getMessage())
            if frase is None:
                return
            # Evita repetir la misma frase consecutiva
            if not self.frases or self.frases[-1] != frase:
                self.frases.append(frase)
            self.placeholder.markdown(
                _html(self.frases, self.segundos), unsafe_allow_html=True
            )
        except Exception:
            self.handleError(record)


# ──────────────────────────────────────────────────────────────────────
# Context manager público
# ──────────────────────────────────────────────────────────────────────
@contextmanager
def progreso(
    frases: list[str] | None = None,
    segundos: int = 3,
    logger_nombre: str | None = None,
):
    """
    Uso:
        with progreso():                 # escucha todos los loggers
        with progreso(logger_nombre="app.pipeline"):   # solo ese logger

    Si pasas `frases` explícitas, se usan como animación estática
    (compatibilidad con el modo anterior). Si no, se generan desde el logger.
    """
    espacio = st.empty()

    # Modo estático (compatibilidad): frases fijas rotando
    if frases is not None:
        espacio.markdown(_html(frases, segundos), unsafe_allow_html=True)
        try:
            yield
        finally:
            espacio.empty()
        return

    # Modo dinámico: escuchar logs
    # Frase inicial mientras no llega ningún log
    espacio.markdown(
        _html(["Preparando el pipeline…"], segundos), unsafe_allow_html=True
    )

    handler = StreamlitHandler(
        espacio, segundos=segundos, logger_objetivo=logger_nombre
    )
    # Enganchamos al root logger para capturar cualquier `logging.getLogger(...)`
    root = logging.getLogger()
    nivel_original = root.level
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    root.addHandler(handler)
    try:
        yield
    finally:
        root.removeHandler(handler)
        root.setLevel(nivel_original)
        espacio.empty()
