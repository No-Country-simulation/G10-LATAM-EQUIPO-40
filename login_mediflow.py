"""
MediFlow - Login v9 (ejemplo de diseño, sin conexión real, con layout a pantalla completa).

Usa el menú nativo de Streamlit (⋮ arriba a la derecha): Settings (tema claro /
oscuro / sistema), Print y Record a screencast. No fuerza colores, así que se
adapta solo al tema que elija el usuario.

Archivos necesarios:
    assets/mediflow_logo_insignia_animado.svg
    inicio_mediflow.py   (landing; es la primera vista)

Ejecutar:  streamlit run login_mediflow.py
Credenciales de prueba: demo / demo1234
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="MediFlow — Acceso",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

LOGO_SVG = Path(__file__).parent / "assets" / "mediflow_logo_insignia_animado.svg"
MODELOS = "Cohere command-a-vision / command-r-plus"
BUCKETS = "`procesados/urgentes` · `procesados/rutina` · `auditoria_humana`"

# ──────────────────────────────────────────────────────────────
# TIEMPOS (en segundos) — aquí se ajusta toda la secuencia de entrada
# ──────────────────────────────────────────────────────────────
DURACION_APARICION = 0.7   # cuánto tarda en aparecer cada elemento del panel y del formulario
PANEL_INICIO = 0.7         # cuándo aparece el primer texto del panel (bajo el logo)
PANEL_PASO = 0.10          # pausa entre un elemento del panel y el siguiente
FORM_INICIO = 0.35         # cuándo aparece el primer campo del formulario
FORM_PASO = 0.12           # pausa entre un campo del formulario y el siguiente
TARJETA_RETRASO = 0.15     # cuándo empieza a aparecer la tarjeta del formulario
TARJETA_DURACION = 0.8     # cuánto tarda la tarjeta en aparecer

_ULTIMO_PANEL = 7          # nº de elementos animados del panel (del 2 al 7)
_ULTIMO_FORM = 6           # nº de elementos animados del formulario
FIN_CASCADA = max(
    PANEL_INICIO + PANEL_PASO * (_ULTIMO_PANEL - 2) + DURACION_APARICION,
    FORM_INICIO + FORM_PASO * _ULTIMO_FORM + DURACION_APARICION,
    TARJETA_RETRASO + TARJETA_DURACION,
)

LOGO_PAUSA = 0.1           # espera extra tras la cascada antes de arrancar el logo
LOGO_RETRASO = FIN_CASCADA + LOGO_PAUSA   # o un número fijo, p. ej. 2.5
LOGO_ESCALA = 1.0          # duración de la entrada del logo: 1 = ~2 s · 2 = el doble de lenta · 0.5 = el doble de rápida


# ──────────────────────────────────────────────────────────────
# Autenticación (placeholder)
# ──────────────────────────────────────────────────────────────
def autenticar(usuario: str, clave: str) -> bool:
    """TODO: reemplazar por la validación real (API, OCI IAM, DB...)."""
    return usuario == "demo" and clave == "demo1234"


# ──────────────────────────────────────────────────────────────
# Logo: SVG animado como <img> (así Streamlit no filtra su CSS interno)
# ──────────────────────────────────────────────────────────────
def _logo_b64() -> str | None:
    if not LOGO_SVG.exists():
        return None
    svg = LOGO_SVG.read_text(encoding="utf-8")
    # Se inyectan los tiempos al final del <style>: ganan a los valores por defecto del SVG.
    tiempos = f":root{{--d:{LOGO_RETRASO:.2f}s;--k:{LOGO_ESCALA}}}"
    svg = svg.replace("</style>", tiempos + "\n</style>", 1)
    return base64.b64encode(svg.encode("utf-8")).decode()


def logo_html(ancho: int = 200) -> str:
    b64 = _logo_b64()
    if b64 is None:  # respaldo si falta el archivo
        return '<span class="logo-fallback">🏥</span>'
    return (
        f'<img class="logo-img" alt="Logo de MediFlow" width="{ancho}" '
        f'src="data:image/svg+xml;base64,{b64}">'
    )


# ──────────────────────────────────────────────────────────────
# Estilos: layout, animaciones de entrada y detalles neutros (claro y oscuro)
# ──────────────────────────────────────────────────────────────
_COL = '[data-testid="stColumn"]:first-child [data-testid="stElementContainer"]'
_FORM = '[data-testid="stForm"] [data-testid="stElementContainer"]'

# El logo (hijo 1) trae su propia animación de entrada; el resto cae en cascada.
_DELAYS_PANEL = "".join(
    f"{_COL}:nth-child({i}) {{ animation-delay: {PANEL_INICIO + PANEL_PASO * (i - 2):.2f}s; }}\n"
    for i in range(2, _ULTIMO_PANEL + 1)
)
_DELAYS_FORM = "".join(
    f"{_FORM}:nth-child({i}) {{ animation-delay: {FORM_INICIO + FORM_PASO * i:.2f}s; }}\n"
    for i in range(1, _ULTIMO_FORM + 1)
)

CSS = f"""
/* Sin sidebar en el login; el menú ⋮ (tema, print, screencast) se mantiene */
[data-testid="stSidebar"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}

/* Composición: ocupa casi todo el ancho y se centra en vertical */
[data-testid="stMainBlockContainer"], .block-container {{
    max-width: min(1600px, 96vw);
    min-height: 100dvh;
    display: flex; flex-direction: column; justify-content: center;
    padding: 2rem 3rem;
}}
[data-testid="stMainBlockContainer"] > div, .block-container > div {{ width: 100%; }}

@keyframes aparecer {{
    from {{ opacity: 0; transform: translateY(16px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes tarjeta {{
    from {{ opacity: 0; transform: translateY(32px) scale(.98); }}
    to   {{ opacity: 1; transform: translateY(0) scale(1); }}
}}

/* Panel izquierdo: el logo anima solo; el texto aparece en cascada después */
{_COL} {{ animation: aparecer {DURACION_APARICION}s ease-out both; }}
{_COL}:nth-child(1) {{ animation: none; overflow: visible; flex-shrink: 0; }}
{_DELAYS_PANEL}

/* Logo: tamaño fluido, proporción fija y sin recortes */
.logo-img {{
    display: block; width: clamp(160px, 15vw, 270px); height: auto;
    aspect-ratio: 1 / 1; margin: 0 0 .5rem; overflow: visible;
}}
.logo-fallback {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 110px; height: 110px; border-radius: 24px; font-size: 3.2rem;
    background: rgba(128,128,128,.12); border: 1px solid rgba(128,128,128,.3);
}}

/* Título: espacio para que el emoji 🏥 no se recorte (tamaño de letra por defecto) */
[data-testid="stColumn"]:first-child :is(
    [data-testid="stElementContainer"], [data-testid="stHeading"],
    [data-testid="stHeadingWithActionElements"], h1, h1 *
) {{ overflow: visible !important; }}
[data-testid="stColumn"]:first-child h1 {{
    line-height: 1.5 !important; padding: .6rem 0 1rem !important;
}}

/* Chips de estado (tonos translúcidos: válidos en claro y oscuro) */
.chip {{
    display: inline-block; padding: 2px 10px; margin: 4px 6px 0 0; border-radius: 999px;
    font-size: .8rem; font-weight: 600; border: 1px solid transparent;
}}
.chip-urgente {{ background: rgba(239,68,68,.18);  border-color: rgba(239,68,68,.5); }}
.chip-alta    {{ background: rgba(249,115,22,.18); border-color: rgba(249,115,22,.5); }}
.chip-baja    {{ background: rgba(34,197,94,.18);  border-color: rgba(34,197,94,.5); }}

/* Columna derecha: tarjeta amplia, centrada en su columna */
[data-testid="stColumn"]:last-child > [data-testid="stVerticalBlock"] {{
    max-width: min(100%, 640px); margin-inline: auto;
}}
[data-testid="stForm"] {{
    border-radius: 18px; padding: clamp(1.75rem, 3vw, 3rem);
    box-shadow: 0 18px 45px rgba(0,0,0,.18);
    animation: tarjeta {TARJETA_DURACION}s cubic-bezier(.2,.8,.2,1) {TARJETA_RETRASO}s both;
}}
{_FORM} {{ animation: aparecer {DURACION_APARICION}s ease-out both; }}
{_DELAYS_FORM}

/* Formulario: campos y botón más altos (sin cambiar el tamaño de letra) */
[data-testid="stForm"] [data-baseweb="input"] {{ min-height: 3.6rem; }}
[data-testid="stForm"] button {{ min-height: 3.8rem; }}

/* Pie de página */
.pie {{ text-align: center; font-size: .8rem; opacity: .6; margin-top: 3rem; }}

/* Interacciones sutiles */
[data-testid="stForm"] button {{ transition: transform .2s ease, box-shadow .2s ease; }}
[data-testid="stForm"] button:hover {{ transform: translateY(-2px); box-shadow: 0 8px 18px rgba(0,0,0,.25); }}

/* Móvil: Streamlit apila las columnas. Se oculta el logo animado, los chips y el
   estado técnico para que el formulario quede a la vista. */
@media (max-width: 640px) {{
    {_COL}:has(.logo-img), {_COL}:has(.logo-fallback) {{ display: none; }}
    {_COL}:has(.chip), {_COL}:has(.chip) ~ [data-testid="stElementContainer"] {{ display: none; }}
    .pie {{ margin-top: 1.5rem; }}
}}

@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
"""

# Tras la primera carga se apagan las animaciones de entrada para que cambiar
# el tema desde el menú, o fallar el login, no las repita.
CSS_SIN_INTRO = f"""
{_COL}, {_FORM}, [data-testid="stForm"] {{ animation: none !important; }}
"""

CHIPS_HTML = """
<span class="chip chip-urgente">🚨 Prioridad crítica</span>
<span class="chip chip-baja">🟢 Rutina médica</span>
<span class="chip chip-alta">⚠️ Auditoría HITL</span>
"""


def _estilos() -> None:
    css = CSS + ("" if not st.session_state.get("intro_hecha") else CSS_SIN_INTRO)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# Vistas
# ──────────────────────────────────────────────────────────────
def vista_login() -> None:
    _estilos()

    col_info, col_login = st.columns(
        [1.1, 1], gap="large", vertical_alignment="center"
    )

    # Izquierda: identidad primero (logo → nombre → qué hace), detalles técnicos al final
    with col_info:
        st.markdown(logo_html(), unsafe_allow_html=True)                                   # 1
        st.title("🏥 MediFlow")                                                            # 2
        st.markdown("**Agente Clínico Autónomo**")                                         # 3
        st.caption("Triaje, extracción y enrutamiento de documentos clínicos con Cohere AI.")  # 4
        st.markdown(CHIPS_HTML, unsafe_allow_html=True)                                    # 5
        st.caption(f"🟢 {MODELOS}")                                                        # 6
        st.caption(f"📦 OCI Buckets: {BUCKETS}")                                           # 7

    # Derecha: una sola acción principal, centrada verticalmente respecto al panel
    with col_login:
        with st.form("form_login"):
            st.markdown("#### 🔐 Iniciar sesión")                                          # 1
            st.caption("Ingresa con tus credenciales institucionales.")                    # 2
            usuario = st.text_input("Usuario", placeholder="correo@hospital.org")          # 3
            clave = st.text_input("Contraseña", type="password", placeholder="••••••••")   # 4
            st.checkbox("Mantener sesión iniciada")                                        # 5
            enviar = st.form_submit_button(                                                # 6
                "🚀 Ingresar a MediFlow", type="primary", use_container_width=True
            )

        if enviar:
            if not usuario or not clave:
                st.warning("Completa usuario y contraseña para continuar.")
            elif autenticar(usuario, clave):
                st.session_state.autenticado = True
                st.session_state.usuario = usuario
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos. Revísalos e inténtalo de nuevo.")

    st.markdown(
        '<div class="pie">Hackathon ONE G10 — Grupo 40 · MediFlow v1.0 — MVP Hackathon</div>',
        unsafe_allow_html=True,
    )
    st.session_state.intro_hecha = True

def main() -> None:
    """Flujo: inicio (landing) -> login -> agente."""
    if st.session_state.get("autenticado"):
        from streamlit_app import main as main_agente
        main_agente()
    elif st.session_state.get("vista", "inicio") == "inicio":
        from inicio_mediflow import vista_inicio
        vista_inicio()
    else:
        vista_login()


if __name__ == "__main__":
    main()
