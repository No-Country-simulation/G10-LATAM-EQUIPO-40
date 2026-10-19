"""
MediFlow - Indicador de progreso para Streamlit (electrocardiograma).
Reemplaza a st.spinner: se usa igual, con `with progreso():`.

Las frases rotan con una animación CSS (cada `segundos`), en el orden típico del
agente; no están atadas a la etapa exacta en que va el pipeline.
"""

from contextlib import contextmanager
from urllib.parse import quote

import streamlit as st

FRASES = [
    "Recibiendo el documento…",
    "Identificando el documento…",
    "Preparando las páginas…",
    "Extrayendo el texto de cada página…",
    "Clasificando el documento y leyendo sus datos…",
    "Verificando los datos contra el documento…",
    "Decidiendo a dónde enviarlo…",
    "Guardando el expediente…",
]

_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 110 40'>"
    "<path d='M2 22 H28 L33 22 L38 8 L45 36 L51 22 H70 L75 16 L80 22 H108' "
    "fill='none' stroke='black' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/></svg>"
)
_URL = "data:image/svg+xml," + quote(_SVG, safe="")


def _html(frases: list[str], segundos: int) -> str:
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
        f'<span style="animation-delay:{i * segundos}s">{f}</span>' for i, f in enumerate(frases)
    )
    # Todo en una línea: un salto de línea en blanco rompería el bloque HTML de Markdown
    return f'<style>{css}</style><div class="mf-prog"><div class="mf-ecg"></div><div class="mf-rot">{spans}</div></div>'


@contextmanager
def progreso(frases: list[str] | None = None, segundos: int = 4):
    """Muestra el electrocardiograma con frases rotando mientras corre el bloque."""
    espacio = st.empty()
    espacio.markdown(_html(frases or FRASES, segundos), unsafe_allow_html=True)
    try:
        yield
    finally:
        espacio.empty()
