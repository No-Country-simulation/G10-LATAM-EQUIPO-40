"""
MediFlow - Página de presentación (landing), mismo estilo que login_mediflow.py.

Sigue el tema nativo de Streamlit (claro / oscuro / sistema): no fuerza colores,
usa tonos translúcidos, chips de estado y la misma entrada en cascada del login.

Archivo necesario:
    assets/mediflow_logo_insignia_animado.svg      (el mismo del login)

Se muestra como primera vista desde login_mediflow.main().
Vista previa suelta:  streamlit run inicio_mediflow.py
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

LOGO_SVG = Path(__file__).parent / "assets" / "mediflow_logo_insignia_animado.svg"
PIE = "Hackathon ONE G10 — Grupo 40 · MediFlow v1.0 — MVP Hackathon"

EQUIPO = [
    "🇨🇴 Nicolas Cardona Ramírez",
    "🇨🇱 Jimmy Pérez Cortés",
    "🇵🇪 Daniel Lara",
    "🇲🇽 Luis Eduardo Rello Cal y Mayor",
]

# Tiempos del logo (mismos parámetros que el login)
LOGO_RETRASO = 0.4   # segundos antes de que arranque la animación del logo
LOGO_ESCALA = 1.0    # 1 = ~2 s · 2 = el doble de lenta · 0.5 = el doble de rápida

# ──────────────────────────────────────────────────────────────
# Contenido
# ──────────────────────────────────────────────────────────────
INTRO = [
    "MediFlow es un agente autónomo que se encarga del trabajo documental repetitivo "
    "de un centro de salud: lee los documentos clínicos que llegan escaneados o en PDF, "
    "extrae sus datos clave, comprueba que esté todo lo obligatorio y los envía al lugar "
    "que les corresponde según su prioridad.",
    "El objetivo es sencillo: que el personal médico y administrativo dedique menos tiempo "
    "a transcribir, clasificar y archivar, y más tiempo a atender pacientes. Nada se aprueba "
    "a ciegas: lo incompleto o dudoso lo decide siempre una persona.",
]

BENEFICIOS = [
    ("⏱️", "Ahorra tiempo",
     "Automatiza la lectura, la transcripción y el archivo que hoy se hacen a mano."),
    ("🎯", "Reduce errores",
     "Los datos salen del documento ya estructurados, sin tener que digitarlos de nuevo."),
    ("🚨", "Lo urgente, primero",
     "La clasificación por prioridad evita que un caso crítico espere detrás de la rutina."),
    ("🗂️", "Todo en orden",
     "Cada documento queda en el lugar que le corresponde, fácil de encontrar después."),
    ("🧑‍⚕️", "Criterio humano",
     "La IA prepara el trabajo; el personal de salud conserva la decisión final."),
    ("💬", "Más tiempo para los pacientes",
     "Menos papeleo para el equipo y más atención para quien la necesita."),
]

FUNCIONES = [
    ("🩻", "Lee documentos escaneados",
     "Un modelo de visión de Cohere interpreta imágenes escaneadas; los PDF con texto se leen directamente."),
    ("🧾", "Extrae los datos clave",
     "Convierte el contenido en campos estructurados, listos para consultarse en lugar de quedar atrapados en una imagen."),
    ("🚦", "Clasifica por prioridad",
     "Distingue lo crítico de la rutina para que lo urgente se atienda primero."),
    ("✅", "Valida lo obligatorio",
     "Si falta un solo campo obligatorio, el documento no avanza por su cuenta."),
    ("🧑‍⚕️", "Humano en el circuito",
     "Lo incompleto o dudoso llega a la pestaña Auditoría, que muestra cuántos documentos hay pendientes."),
    ("☁️", "Guarda en la nube",
     "Cada documento termina en su bucket de Oracle Cloud Object Storage."),
    ("🧹", "Protege los datos del paciente",
     "Los registros se limpian antes de compartirse, para reducir la exposición de información sensible."),
    ("🧪", "Modo simulado",
     "Permite probar todo el flujo sin información real, ideal para demostraciones y pruebas."),
]

PASOS = [
    ("Entrada", "Subes una imagen escaneada o un PDF."),
    ("Lectura", "El agente extrae el texto y organiza los campos."),
    ("Validación", "Comprueba que estén todos los campos obligatorios."),
    ("Destino", "Envía el documento al bucket que le corresponde."),
]

# (clase del chip, etiqueta, bucket, descripción)
DESTINOS = [
    ("urgente", "🚨 Prioridad crítica", "procesados/urgentes",
     "Documentos que requieren atención inmediata."),
    ("baja", "🟢 Rutina médica", "procesados/rutina",
     "Documentos completos y sin urgencia."),
    ("alta", "⚠️ Auditoría HITL", "auditoria_humana",
     "Faltan datos o hay dudas: decide una persona."),
]

# (nombre, clase de color)
TECNOLOGIA = [
    ("Cohere", "cohere"),
    ("LangChain", "langchain"),
    ("FastAPI", "fastapi"),
    ("Streamlit", "streamlit"),
    ("Oracle Cloud Infrastructure (OCI)", "oci"),
    ("Python", "python"),
    ("uv", "uv"),
    ("Podman", "podman"),
]

FAQ = [
    ("¿Qué documentos puede procesar?",
     "MediFlow trabaja con imágenes escaneadas y con PDF de documentos clínicos. Si el PDF "
     "contiene texto, se lee directamente; si es una imagen o un escaneo, un modelo de visión "
     "de Cohere interpreta su contenido y lo convierte en campos estructurados."),
    ("¿Qué pasa si a un documento le falta un dato?",
     "Si falta un solo campo obligatorio, el documento no avanza por su cuenta. Pasa a la "
     "pestaña Auditoría y queda pendiente hasta que una persona lo revise y lo complete. "
     "Así se evita que información incompleta llegue a su destino final sin que nadie la vea."),
    ("¿Qué significa «HITL» o «humano en el circuito»?",
     "Son las siglas en inglés de human in the loop. Significa que la inteligencia artificial "
     "no decide sola en los casos dudosos: los deja marcados para que una persona los revise. "
     "En MediFlow, esos casos aparecen en la pestaña Auditoría con un contador de pendientes."),
    ("¿Cómo decide a dónde enviar cada documento?",
     "Después de extraer y validar los datos, el agente clasifica el documento y lo envía a una "
     "de tres rutas: prioridad crítica, rutina médica o auditoría humana. Cada ruta corresponde "
     "a un bucket distinto, así lo urgente se localiza rápido y lo dudoso no se mezcla con lo ya validado."),
    ("¿Reemplaza al personal de salud?",
     "No. MediFlow apoya la gestión documental: lee, ordena y prioriza. Las decisiones clínicas "
     "siguen siendo del personal de salud, y cualquier caso incompleto o dudoso lo resuelve una persona."),
    ("¿Dónde se guardan los documentos?",
     "En buckets de Oracle Cloud Object Storage, separados por prioridad y por auditoría humana. "
     "Esa separación permite encontrar lo crítico de inmediato y llevar un orden claro de lo procesado."),
    ("¿Qué pasa con los datos de los pacientes?",
     "Los registros se limpian antes de compartirse. Además, MediFlow incluye un modo simulado para "
     "probar el flujo completo sin usar información real. Como esta es una versión MVP creada en un "
     "hackatón, lo recomendable es usarla con datos de prueba."),
    ("¿Puedo probarlo sin documentos reales?",
     "Sí. Con el modo simulado puedes recorrer todo el proceso (subida, lectura, validación y destino) "
     "sin exponer datos de pacientes. Es la mejor forma de conocer la herramienta antes de usarla con casos propios."),
    ("¿Con qué tecnologías está construido?",
     "Usa modelos de Cohere para texto y visión, LangChain para orquestar el agente, FastAPI y Streamlit "
     "para el servicio y la interfaz, y Oracle Cloud Infrastructure para el almacenamiento. El proyecto está "
     "escrito en Python y se gestiona con uv y Podman."),
    ("¿Cómo empiezo?",
     "Pulsa «Ingresar a MediFlow», inicia sesión y sube tu primer documento. Si es tu primera vez, "
     "prueba con el modo simulado para ver cómo recorre el documento cada etapa."),
]


# ──────────────────────────────────────────────────────────────
# Logo: SVG animado como <img> (igual que en el login)
# ──────────────────────────────────────────────────────────────
def _logo_b64() -> str | None:
    if not LOGO_SVG.exists():
        return None
    svg = LOGO_SVG.read_text(encoding="utf-8")
    tiempos = f":root{{--d:{LOGO_RETRASO:.2f}s;--k:{LOGO_ESCALA}}}"
    svg = svg.replace("</style>", tiempos + "\n</style>", 1)
    return base64.b64encode(svg.encode("utf-8")).decode()


def logo_html() -> str:
    b64 = _logo_b64()
    if b64 is None:  # respaldo si falta el archivo
        return '<span class="logo-fallback">🏥</span>'
    return (
        '<img class="logo-hero" alt="Logo de MediFlow" '
        f'src="data:image/svg+xml;base64,{b64}">'
    )


# ──────────────────────────────────────────────────────────────
# Estilos
# ──────────────────────────────────────────────────────────────
CSS = """
html, [data-testid="stMain"], [data-testid="stAppViewContainer"] { scroll-behavior: smooth; }

/* Sin sidebar; el menú ⋮ (tema, print, screencast) se mantiene */
[data-testid="stSidebar"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* Padding superior amplio: deja libre la barra de Streamlit (Deploy y menú ⋮) */
[data-testid="stMainBlockContainer"], .block-container {
    max-width: min(1280px, 94vw);
    padding: 5rem 2rem 3rem;
}

/* ── Entrada: cascada en el hero, revelado al hacer scroll en el resto ── */
@keyframes aparecer {
    from { opacity: 0; translate: 0 16px; }
    to   { opacity: 1; translate: 0 0; }
}
.rev, .st-key-nav,
[data-testid="stHeading"], .st-key-datos, .st-key-faq, .st-key-cta_final {
    animation: aparecer .8s ease-out both;
    animation-delay: var(--d, 0s);
}
.d1 { --d: .10s; } .d2 { --d: .22s; } .d3 { --d: .34s; }
.d4 { --d: .46s; } .d5 { --d: .70s; }

/* Debajo del pliegue: se revela mientras entra en pantalla (si el navegador puede) */
@supports (animation-timeline: view()) {
    .rev-scroll, [data-testid="stHeading"], .st-key-datos,
    .st-key-faq, .st-key-cta_final {
        animation: aparecer linear both;
        animation-timeline: view();
        animation-range: entry 0% entry 35%;
    }
}

/* ── Barra superior ── */
.marca { font-size: 1.25rem; font-weight: 700; letter-spacing: -.01em; margin: 0; }
.st-key-nav [data-testid="stColumn"]:nth-child(2) p { margin: 0; text-align: center; }
.st-key-nav [data-testid="stColumn"]:nth-child(2) a { margin: 0 .8rem; text-decoration: none; opacity: .8; }
.st-key-nav [data-testid="stColumn"]:nth-child(2) a:hover { opacity: 1; text-decoration: underline; }

/* ── Hero ── */
.st-key-hero {
    min-height: min(78dvh, 760px);
    display: flex; flex-direction: column; justify-content: center;
}
.hero-h1 {
    font-size: clamp(2.2rem, 4.6vw, 3.9rem); line-height: 1.12; font-weight: 700;
    letter-spacing: -.025em; margin: 0 0 1.1rem; padding: 0;
    max-width: 20ch; text-wrap: balance;
}
.hero-lead {
    font-size: clamp(1.05rem, 1.4vw, 1.25rem); line-height: 1.6; opacity: .82;
    max-width: 56ch; margin: 0 0 1.6rem;
}

.logo-hero {
    display: block; width: clamp(200px, 30vw, 440px); height: auto;
    aspect-ratio: 1 / 1; margin-inline: auto;
}
.logo-fallback {
    display: flex; align-items: center; justify-content: center;
    width: 160px; height: 160px; margin-inline: auto; border-radius: 32px; font-size: 4rem;
    background: rgba(128,128,128,.12); border: 1px solid rgba(128,128,128,.3);
}
.bajo-logo { text-align: center; margin-top: .4rem; }

/* Chips (tonos translúcidos: válidos en claro y oscuro) */
.chip {
    display: inline-block; padding: 2px 10px; margin: 4px 6px 0 0; border-radius: 999px;
    font-size: .8rem; font-weight: 600; border: 1px solid transparent;
}
.chip-n      { background: rgba(128,128,128,.14); border-color: rgba(128,128,128,.35); }
.chip-urgente { background: rgba(239,68,68,.18);  border-color: rgba(239,68,68,.5); }
.chip-alta    { background: rgba(249,115,22,.18); border-color: rgba(249,115,22,.5); }
.chip-baja    { background: rgba(34,197,94,.18);  border-color: rgba(34,197,94,.5); }

/* Chips de tecnología, cada uno con su color */
.chip-t { padding: 5px 14px; font-size: .9rem; margin: 6px 8px 0 0; }
.t-cohere    { background: rgba(217,70,239,.18); border-color: rgba(217,70,239,.55); }
.t-langchain { background: rgba(34,197,94,.18);  border-color: rgba(34,197,94,.55); }
.t-fastapi   { background: rgba(20,184,166,.18); border-color: rgba(20,184,166,.55); }
.t-streamlit { background: rgba(255,75,75,.18);  border-color: rgba(255,75,75,.55); }
.t-oci       { background: rgba(249,115,22,.18); border-color: rgba(249,115,22,.55); }
.t-python    { background: rgba(59,130,246,.18); border-color: rgba(59,130,246,.55); }
.t-uv        { background: rgba(139,92,246,.18); border-color: rgba(139,92,246,.55); }
.t-podman    { background: rgba(245,158,11,.18); border-color: rgba(245,158,11,.55); }

/* Botones: más altos y con el mismo hover del login */
[data-testid="stButton"] button { min-height: 3.2rem; transition: transform .2s ease, box-shadow .2s ease; }
[data-testid="stButton"] button:hover { transform: translateY(-2px); box-shadow: 0 8px 18px rgba(0,0,0,.25); }
.st-key-cta_final [data-testid="stButton"] button { min-height: 3.6rem; }

/* ── Secciones ── */
[data-testid="stHeading"] { padding-top: clamp(3rem, 7vw, 5rem); padding-bottom: 1.25rem; scroll-margin-top: 1rem; }
.st-key-datos { margin-top: 1rem; }

/* Introducción */
.intro { margin-top: .5rem; }
.intro p { font-size: clamp(1.05rem, 1.3vw, 1.2rem); line-height: 1.75; opacity: .88; margin: 0 0 1rem; }
.ben-grid {
    display: grid; gap: 1rem; margin-top: 1.5rem;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
}
.ben {
    display: flex; gap: .9rem; align-items: flex-start;
    padding: 1.1rem 1.3rem; border-radius: 0 14px 14px 0;
    background: rgba(128,128,128,.06); border-left: 3px solid rgba(255,75,75,.7);
}
.ben .ico { font-size: 1.5rem; line-height: 1.2; }
.ben h3 { font-size: 1.02rem; font-weight: 650; margin: 0 0 .25rem; padding: 0; }
.ben p { margin: 0; opacity: .78; line-height: 1.55; font-size: .95rem; }

.grid {
    display: grid; gap: 1.25rem; margin-top: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 270px), 1fr));
}
.card {
    padding: 1.6rem; border-radius: 18px;
    background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.28);
    transition: transform .25s ease, box-shadow .25s ease;
}
.card:hover { transform: translateY(-3px); box-shadow: 0 14px 32px rgba(0,0,0,.18); }
.card .ico { font-size: 1.7rem; line-height: 1; margin-bottom: .9rem; }
.card h3 { font-size: 1.1rem; font-weight: 650; margin: 0 0 .45rem; padding: 0; }
.card p { margin: .7rem 0 0; opacity: .78; line-height: 1.6; max-width: 52ch; }
.card .ico + h3 + p { margin-top: 0; }
.card-urgente { border-color: rgba(239,68,68,.5); }
.card-alta    { border-color: rgba(249,115,22,.5); }
.card-baja    { border-color: rgba(34,197,94,.5); }
.ruta {
    display: inline-block; margin-top: 1rem; padding: 2px 8px; border-radius: 8px;
    background: rgba(128,128,128,.16); font-family: ui-monospace, monospace; font-size: .82rem;
}

/* ── Pasos: secuencia animada (un punto recorre la línea del paso 1 al 4) ── */
.pasos-wrap { --acento: var(--primary-color, #ff4b4b); margin-top: 2rem; }
.riel {
    position: relative; height: 2px; border-radius: 2px;
    background: rgba(128,128,128,.4);
}
.punto {
    position: absolute; top: 50%; left: 0; width: 14px; height: 14px; margin: -7px 0 0 -7px;
    border-radius: 50%; background: var(--acento); opacity: 0;
    box-shadow: 0 0 0 4px rgba(255,75,75,.25), 0 0 14px rgba(255,75,75,.7);
    animation: viaje 16s linear infinite;
}
@keyframes viaje {
    0%   { left: 0; opacity: 0; }
    5%   { left: 0; opacity: 1; }
    70%  { left: calc(75% + 1.125rem); opacity: 1; }
    78%  { left: calc(75% + 1.125rem); opacity: 0; }
    100% { left: 0; opacity: 0; }
}
.pasos {
    display: grid; gap: 0 1.5rem;
    grid-template-columns: repeat(4, 1fr);
}
.paso { position: relative; padding-top: 1.3rem; }
/* Marcador de cada paso: se enciende cuando el punto llega */
.paso::before {
    content: ""; position: absolute; top: -6px; left: -5px; width: 10px; height: 10px;
    border-radius: 50%; background: rgba(128,128,128,.7);
    animation: marcar 16s linear infinite; animation-delay: var(--t, 0s);
}
.paso:nth-child(1) { --t: .8s; }
.paso:nth-child(2) { --t: 4.27s; }
.paso:nth-child(3) { --t: 7.73s; }
.paso:nth-child(4) { --t: 11.2s; }
@keyframes marcar {
    0%, 12% { background: var(--acento); scale: 1.8; }
    22%, 100% { background: rgba(128,128,128,.7); scale: 1; }
}
.paso .n { font-size: .9rem; font-weight: 700; opacity: .6; display: inline-block;
           animation: numero 16s linear infinite; animation-delay: var(--t, 0s); }
@keyframes numero {
    0%, 12% { opacity: 1; }
    22%, 100% { opacity: .6; }
}
.paso h3 { font-size: 1.1rem; font-weight: 650; margin: .3rem 0 .35rem; padding: 0; }
.paso p { margin: 0; opacity: .78; line-height: 1.55; }

/* Banda de privacidad */
.banda {
    padding: clamp(1.5rem, 3vw, 2.5rem); border-radius: 22px; margin-top: 1rem;
    background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.28);
    display: grid; gap: 1.5rem 2.5rem;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
}
.banda p { margin: 0; line-height: 1.6; opacity: .85; }
.banda strong { display: block; margin-bottom: .2rem; opacity: 1; }

.st-key-faq { padding-top: 1.5rem; }
[data-testid="stExpander"] details { border-radius: 14px; }
[data-testid="stExpander"] p { line-height: 1.7; }

/* Cierre */
.st-key-cta_final { margin-top: clamp(3rem, 7vw, 5rem); text-align: center; }
.st-key-cta_final h2 { margin: 0 0 .4rem; padding: 0; font-size: clamp(1.6rem, 3vw, 2.2rem); }
.st-key-cta_final p { opacity: .8; margin: 0 0 1.4rem; }

.equipo { display: flex; flex-direction: column; align-items: center; margin-top: 3.5rem; }
.equipo h3 { margin: 0 0 .9rem; padding: 0; font-size: 1.15rem; font-weight: 650; text-align: center; }
.equipo-lista { text-align: left; }
.equipo-lista p { margin: 0 0 .35rem; font-size: 1rem; opacity: .85; }
.pie { text-align: center; font-size: .8rem; opacity: .6; margin-top: 1.2rem; }

/* Tablet: pasos en 2 columnas, sin el punto viajero */
@media (max-width: 900px) {
    .pasos { grid-template-columns: repeat(2, 1fr); gap: 1.5rem; }
    .riel { display: none; }
    .paso { border-top: 2px solid rgba(128,128,128,.4); }
}

/* Móvil: Streamlit apila las columnas */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"], .block-container { padding: 4.5rem 1.1rem 2rem; }
    .st-key-nav [data-testid="stColumn"]:nth-child(2) { display: none; }
    .logo-hero { width: clamp(150px, 48vw, 220px); }
    .st-key-hero { min-height: auto; }
    .pasos { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""

# Tras la primera carga se apaga la entrada del hero para que cambiar de tema
# desde el menú no la repita.
CSS_SIN_INTRO = """
.rev:not(.rev-scroll), .st-key-nav { animation: none !important; }
"""


def _estilos() -> None:
    css = CSS + ("" if not st.session_state.get("inicio_intro_hecha") else CSS_SIN_INTRO)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Piezas de HTML
# ──────────────────────────────────────────────────────────────
def _chips_destinos() -> str:
    return "".join(f'<span class="chip chip-{c}">{t}</span>' for c, t, _, _ in DESTINOS)


def _bloque_intro() -> str:
    parrafos = f"<p>{' '.join(INTRO)}</p>"
    beneficios = "".join(
        f'<div class="ben rev rev-scroll"><div class="ico">{i}</div>'
        f"<div><h3>{t}</h3><p>{d}</p></div></div>"
        for i, t, d in BENEFICIOS
    )
    return f'<div class="intro rev rev-scroll">{parrafos}</div><div class="ben-grid">{beneficios}</div>'


def _grid_funciones() -> str:
    tarjetas = "".join(
        f'<div class="card rev rev-scroll"><div class="ico">{i}</div>'
        f"<h3>{t}</h3><p>{d}</p></div>"
        for i, t, d in FUNCIONES
    )
    return f'<div class="grid">{tarjetas}</div>'


def _grid_pasos() -> str:
    pasos = "".join(
        f'<div class="paso"><span class="n">Paso {n}</span>'
        f"<h3>{t}</h3><p>{d}</p></div>"
        for n, (t, d) in enumerate(PASOS, start=1)
    )
    return (
        '<div class="pasos-wrap rev rev-scroll">'
        '<div class="riel"><span class="punto"></span></div>'
        f'<div class="pasos">{pasos}</div></div>'
    )


def _grid_destinos() -> str:
    tarjetas = "".join(
        f'<div class="card card-{c} rev rev-scroll">'
        f'<span class="chip chip-{c}">{t}</span><p>{d}</p>'
        f'<span class="ruta">{ruta}</span></div>'
        for c, t, ruta, d in DESTINOS
    )
    return f'<div class="grid">{tarjetas}</div>'


def _banda_privacidad() -> str:
    return (
        '<div class="banda rev rev-scroll">'
        "<p><strong>Una persona decide lo dudoso</strong>"
        "Lo incompleto no se aprueba solo: pasa a auditoría humana.</p>"
        "<p><strong>Datos de pacientes protegidos</strong>"
        "Los registros se limpian antes de compartirse y hay un modo simulado "
        "para probar sin información real.</p>"
        "<p><strong>Apoyo, no reemplazo</strong>"
        "MediFlow ayuda con la gestión documental; las decisiones clínicas "
        "son del personal de salud.</p>"
        "<p><strong>Versión MVP</strong>"
        "Creada en un hackatón: úsala con datos de prueba.</p>"
        "</div>"
    )


def _chips_tecnologia() -> str:
    chips = "".join(
        f'<span class="chip chip-t t-{c}">{t}</span>' for t, c in TECNOLOGIA
    )
    return f'<div class="rev rev-scroll">{chips}</div>'


# ──────────────────────────────────────────────────────────────
# Navegación (conectada al login)
# ──────────────────────────────────────────────────────────────
def ir_al_login() -> None:
    """Pasa a la vista de login; login_mediflow.main() enruta según esta clave."""
    st.session_state.vista = "login"
    st.rerun()


# ──────────────────────────────────────────────────────────────
# Vista
# ──────────────────────────────────────────────────────────────
def vista_inicio() -> None:
    _estilos()

    # Barra superior
    with st.container(key="nav"):
        c_marca, c_links, c_btn = st.columns([1.8, 3.4, 2], vertical_alignment="center")
        with c_marca:
            st.html('<p class="marca">🏥 MediFlow</p>')
        with c_links:
            st.markdown(
                "[Qué es](#que-es) [Qué hace](#que-hace) "
                "[Cómo funciona](#como-funciona) [Preguntas](#preguntas)"
            )
        with c_btn:
            if st.button("🚀 Ingresar a MediFlow", type="primary",
                         key="nav_ingresar", use_container_width=True):
                ir_al_login()

    # Hero
    with st.container(key="hero"):
        col_txt, col_logo = st.columns([1.15, 1], gap="large", vertical_alignment="center")
        with col_txt:
            st.html(
                '<h1 class="hero-h1 rev d2">Cada documento clínico, en el lugar correcto y a tiempo</h1>'
                '<p class="hero-lead rev d3">MediFlow lee documentos clínicos, extrae los datos clave, '
                "los clasifica por prioridad y envía a revisión humana todo lo que no queda completo.</p>"
            )
            st.html(f'<div class="rev d5">{_chips_destinos()}</div>')
        with col_logo:
            st.markdown(logo_html(), unsafe_allow_html=True)
            st.html(
                '<div class="bajo-logo rev d1">'
                '<span class="chip chip-n">MediFlow · Agente Clínico Autónomo</span>'
                "</div>"
            )

    # Datos clave
    with st.container(border=True, key="datos"):
        m1, m2, m3 = st.columns(3)
        m1.metric("Rutas de destino", "3")
        m2.metric("Modelos de texto y visión", "Cohere")
        m3.metric("Regla: falta un campo, va a auditoría", "1")

    # Qué es MediFlow
    st.header("¿Qué es MediFlow?", anchor="que-es")
    st.html(_bloque_intro())

    # Qué hace
    st.header("Lo que hace el agente", anchor="que-hace")
    st.html(_grid_funciones())

    # Cómo funciona
    st.header("Cómo funciona", anchor="como-funciona")
    st.html(_grid_pasos())

    # Destinos
    st.header("A dónde va cada documento", anchor="destinos")
    st.html(_grid_destinos())

    # Privacidad
    st.header("Pensado para datos sensibles", anchor="privacidad")
    st.html(_banda_privacidad())

    # Tecnología
    st.header("Construido con", anchor="tecnologia")
    st.html(_chips_tecnologia())

    # Preguntas frecuentes
    st.header("Preguntas frecuentes", anchor="preguntas")
    with st.container(key="faq"):
        for pregunta, respuesta in FAQ:
            with st.expander(pregunta):
                st.write(respuesta)

    # Cierre (botón centrado con columnas: funciona en cualquier versión de Streamlit)
    with st.container(key="cta_final"):
        st.html(
            "<h2>Empieza a procesar documentos</h2>"
            "<p>Inicia sesión y sube tu primer documento clínico.</p>"
        )
        _, c_centro, _ = st.columns([1, 1.2, 1])
        with c_centro:
            if st.button("🚀 Ingresar a MediFlow", type="primary",
                         key="final_ingresar", use_container_width=True):
                ir_al_login()

    miembros = "".join(f"<p>{m}</p>" for m in EQUIPO)
    st.html(
        '<div class="equipo"><h3>Autores del proyecto</h3>'
        f'<div class="equipo-lista">{miembros}</div></div>'
        f'<div class="pie">{PIE}</div>'
    )
    st.session_state.inicio_intro_hecha = True


# ──────────────────────────────────────────────────────────────
# Entrada independiente
# ──────────────────────────────────────────────────────────────
def main() -> None:
    vista_inicio()


if __name__ == "__main__":
    st.set_page_config(
        page_title="MediFlow — Agente Clínico Autónomo",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    main()
