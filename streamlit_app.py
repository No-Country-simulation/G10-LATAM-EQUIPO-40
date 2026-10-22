"""
MediFlow - Interfaz Streamlit
Demo visual del agente autónomo de triaje clínico.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from enum import Enum

import streamlit as st
from app.ui_progreso import progreso

from app.chain.pipeline import ejecutar_pipeline
from app.models.schemas import EstadoPipeline

from app.storage.revision import leer_objeto, listar_pendientes, registrar_revision
from app.streamlit_bridge import procesar_archivo, procesar_texto

# Streamlit no configura el logging de la app: sin esto, los logger.info() de
# app.chain.* (clasificar, extraer, enrutar) no aparecen en la consola.
_log_app = logging.getLogger("app")
if not _log_app.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _log_app.addHandler(_h)
    _log_app.setLevel(logging.INFO)


st.set_page_config(
    page_title="MediFlow — Triaje Clínico",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

CASOS_DEMO = [
    {
        "id": "DEMO-001",
        "label": "Caso 1 — TEP Agudo",
        "caption": "Urgencia crítica / Guardia Central",
        "canal": "Guardia_Emergencias",
        "badge": "urgente",
        "badge_texto": "🚨 PRIORIDAD CRÍTICA",
        "descripcion": "Paciente con disnea súbita y tromboembolismo confirmado por AngioTAC.",
        "texto": (
            "HOSPITAL SANTA LUCIA - INFORME DE ESTUDIO RADIOLOGICO\n"
            "Paciente: Carlos Eduardo Mendes, 52 años\n"
            "Médico Solicitante: Dra. Renata Silveira MP 145892\n"
            "Estudio: Tomografía de Tórax con contraste\n"
            "Indicación: Sospecha de embolia pulmonar aguda, disnea súbita\n"
            "Hallazgos: Defecto de llenado en arteria pulmonar principal derecha "
            "compatible con TEP agudo.\n"
            "CONCLUSIÓN: Cuadro compatible con Tromboembolismo Pulmonar Agudo. "
            "Se sugiere correlación clínica urgente."
        ),
    },
    {
        "id": "DEMO-002",
        "label": "Caso 2 — Receta Crónica",
        "caption": "Rutina ambulatoria / Farmacia",
        "canal": "Consultorios_Externos",
        "badge": "rutina",
        "badge_texto": "🟢 RUTINA MÉDICA",
        "descripcion": "Control periódico y renovación de fármacos en paciente con diabetes e hipertensión.",
        "texto": (
            "RECETA MÉDICA — Clínica San Rafael\n"
            "Paciente: Carlos Henríquez, 54 años, DNI 18.234.567\n"
            "Médico: Dr. Fernando Soto, MP 4410, Medicina General\n"
            "Fecha: 24/09/2026\n"
            "Prescripción:\n"
            "- Metformina 850mg — 1 comprimido cada 12 horas por 6 meses\n"
            "- Losartán 50mg — 1 comprimido cada 24 horas por 6 meses\n"
            "Diagnóstico: Diabetes mellitus tipo 2 e hipertensión arterial (E11, I10)\n"
            "Próximo control en 3 meses."
        ),
    },
    {
        "id": "DEMO-003",
        "label": "Caso 3 — Nota Ilegible",
        "caption": "Activación de seguridad HITL",
        "canal": "Admision_General",
        "badge": "hitl",
        "badge_texto": "⚠️ RETENIDO EN AUDITORÍA",
        "descripcion": "Nota ambigua y manuscrita derivada a supervisión humana.",
        "texto": (
            "Orden de procedimiento\n"
            "Paciente: Ana o Alicia (datos no claros)\n"
            "Manuscrito con tinta corrida: dolor abdominal inespecífico...\n"
            "Apendicitis incipiente vs colico biliar??\n"
            "Indico antiespasmódico...\n"
            "Médico: Dr. ??? firma y sello ilegibles. Sin matrícula visible."
        ),
    },
]

def _txt(valor, usar_nombre: bool = False) -> str:
    """Texto limpio de un Enum (o del valor tal cual si ya es str)."""
    if isinstance(valor, Enum):
        return valor.name if usar_nombre else str(valor.value)
    return "—" if valor is None else str(valor)

def _estilos():
    st.markdown(
        """
        <style>
        .badge-urgente {
            background-color: #fee2e2;
            color: #991b1b;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .badge-rutina {
            background-color: #dcfce7;
            color: #166534;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .badge-hitl {
            background-color: #fef3c7;
            color: #92400e;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .chip {
            display: inline-block;
            padding: 2px 10px;
            margin: 4px 6px 0 0;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            background-color: #e5e7eb;
            color: #374151;
        }
        .chip-urgente { background-color: #fee2e2; color: #991b1b; }
        .chip-alta    { background-color: #ffedd5; color: #9a3412; }
        .chip-normal  { background-color: #dbeafe; color: #1e40af; }
        .chip-baja    { background-color: #dcfce7; color: #166534; }

        /* Ajuste de métricas para que la Presión Arterial no se trunque */
        [data-testid="stMetricValue"] {
            font-size: 1.20rem !important;
            white-space: normal !important;
            word-break: break-word !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _inicializar_estado():
    if "cola_hitl" not in st.session_state:
        st.session_state.cola_hitl = []
    if "demos_ejecutadas" not in st.session_state:
        st.session_state.demos_ejecutadas = []  # más reciente primero
    if "cola_cargada" not in st.session_state:
        # Una vez por sesión: recupera de OCI los expedientes aún sin revisar
        st.session_state.cola_cargada = True
        try:
            st.session_state.cola_hitl.extend(listar_pendientes())
        except Exception as e:
            logging.getLogger(__name__).warning(f"No se pudo cargar la cola HITL: {e}")

def _sidebar():
    with st.sidebar:
        st.title("🏥 MediFlow")
        st.markdown("**Agente Clínico Autónomo**")
        st.caption("Hackathon ONE G10 — Grupo 10")

        st.divider()

        st.success("🟢 Cohere command-a-vision / command-r-plus")
        st.info(
            "📦 OCI Buckets:\n"
            "`procesados/urgentes`\n"
            "`procesados/rutina`\n"
            "`auditoria_humana`"
        )

        hitl_count = len(st.session_state.cola_hitl)
        if hitl_count:
            st.warning(f"⚠️ Pendientes HITL: **{hitl_count}**")
        else:
            st.write("Pendientes HITL: **0**")

        st.divider()
        st.caption("MediFlow v1.0 — MVP Hackathon")

def _mostrar_resultado(
    resultado: dict,
    badge: str | None = None,
    badge_texto: str | None = None,
    anidado: bool = False,
):
    """Renderiza el resultado del pipeline en una sola columna, con jerarquía de encabezados."""

    if badge:
        st.markdown(
            f'<span class="badge-{badge}">{badge_texto}</span>',
            unsafe_allow_html=True,
        )

    # ── H5: Decisión (lo más importante: qué se hace con el documento) ──
    st.markdown("##### 🚦 Decisión de Enrutamiento")
    decision = resultado.get("decision")
    if decision:
        destino = _txt(decision.get("destino", "—"))
        requiere_hitl = decision.get("requiere_revision_humana", False)

        if "Emergencia" in destino:
            st.error(f"🆘 **{destino}**")
        elif requiere_hitl:
            st.warning(f"👁️ **{destino}**")
        else:
            st.success(f"✅ **{destino}**")

        st.write(f"💬 {decision.get('justificacion', '')}")

        notif = decision.get("notificacion")
        if notif:
            st.error(f"📣 {notif.get('mensaje', '')}")
    else:
        st.write("Sin decisión de enrutamiento.")

    st.divider()

    # ── H5: Clasificación ──
    st.markdown("##### 🗂️ Clasificación del Documento")
    clf = resultado.get("clasificacion")
    if clf:
        tipo = _txt(clf.get("tipo_documento"), usar_nombre=True)
        prioridad = _txt(clf.get("nivel_prioridad"))
        confianza = clf.get("score_confianza", 0) or 0
        st.markdown(
            f"**Tipo de documento:** {tipo}<br>"
            f'<span class="chip chip-{prioridad.lower()}">Prioridad: {prioridad}</span>'
            f'<span class="chip">Confianza: {confianza:.0%}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.write("Sin clasificación.")

    st.divider()

    # ── H5: Datos extraídos ──
    st.markdown("##### 📋 Datos Extraídos")
    datos = resultado.get("datos_extraidos")
    if datos:
        paciente = datos.get("paciente") or {}
        medico = datos.get("medico_solicitante") or {}

        st.markdown("###### Paciente")
        st.write(f"👤 **Nombre:** {paciente.get('nombre', 'No identificado')}")
        if paciente.get("edad"):
            st.write(f"🎂 **Edad:** {paciente['edad']}")

        st.markdown("###### Médico solicitante")
        st.write(f"🩺 **Nombre:** {medico.get('nombre', 'No identificado')}")
        if medico.get("matricula"):
            st.write(f"🪪 **Matrícula:** {medico['matricula']}")

        # ── Diagnóstico Clínico / Estado de Evaluación ──
        tipo_doc = _txt(clf.get("tipo_documento"), usar_nombre=True) if clf else ""
        dx = datos.get("diagnostico_principal")
        cie = datos.get("cie10_sugerido")

        st.markdown("###### Diagnóstico")
        if dx:
            st.write(f"🔬 **Principal:** {dx}")
            if cie:
                st.write(f"📌 **CIE-10:** {cie}")
        elif tipo_doc == "HOJA_TRIAJE":
            esp = (clf.get("especialidad") if clf else None) or "Medicina de Urgencias"
            st.info(f"⏳ **A la espera de evaluación médica** por especialista derivado ({esp}).")
        else:
            st.caption("Sin diagnóstico consignado en el documento.")

        # ── Signos Vitales y Constantes Fisiológicas ──
        sv = datos.get("signos_vitales")
        if sv:
            sv_dict = (
                sv if isinstance(sv, dict)
                else (sv.model_dump() if hasattr(sv, "model_dump") else getattr(sv, "__dict__", {}))
            )
            if any(sv_dict.values()):
                st.markdown("###### 🫀 Constantes Fisiológicas y Signos Vitales")
                col_sv1, col_sv2, col_sv3 = st.columns(3)
                with col_sv1:
                    st.metric("Presión (PA)", sv_dict.get("presion_arterial") or "—")
                    st.metric("Sat. O2 (SpO2)", sv_dict.get("saturacion_oxigeno") or "—")
                with col_sv2:
                    st.metric("Pulso (FC)", sv_dict.get("frecuencia_cardiaca") or "—")
                    st.metric("Temperatura", sv_dict.get("temperatura") or "—")
                with col_sv3:
                    st.metric("Frec. Resp. (FR)", sv_dict.get("frecuencia_respiratoria") or "—")
                    st.metric("Glasgow", sv_dict.get("glasgow") or "—")

        # ── Estudios y Exámenes de Laboratorio / Imágenes ──
        estudio_hecho = datos.get("estudio_realizado")
        estudios_pedidos = datos.get("estudios_solicitados") or []
        if estudio_hecho or estudios_pedidos:
            st.markdown("###### 🧪 Estudios y Exámenes Clínicos")
            if estudio_hecho:
                st.write(f"🔬 **Estudio realizado:** {estudio_hecho}")
            if estudios_pedidos:
                st.markdown("**Estudios solicitados:**\n" + "\n".join(f"- 📋 {e}" for e in estudios_pedidos))

        # ── Medicamentos ──
        meds = datos.get("medicamentos") or []
        if meds:
            st.markdown("###### Medicamentos")
            st.markdown(
                "\n".join(
                    f"- 💊 {m.get('nombre') or ''} {m.get('dosis') or ''} {m.get('frecuencia') or ''}".rstrip()
                    for m in meds
                )
            )

        # ── Hallazgos Críticos ──
        hallazgos = datos.get("hallazgos_criticos") or []
        if hallazgos:
            st.markdown("###### Hallazgos críticos")
            for h in hallazgos:
                st.error(f"🚨 {h}")

        # ── Campos Faltantes ──
        faltantes = datos.get("campos_faltantes") or []
        if faltantes:
            st.markdown("###### Campos faltantes")
            st.warning(f"⚠️ {', '.join(faltantes)}")
    else:
        st.write("Sin datos extraídos.")

    st.divider()
    if anidado:
        st.markdown("###### JSON completo")
        st.json(resultado, expanded=False)
    else:
        with st.expander("Ver JSON completo"):
            st.json(resultado)


MAX_DEMOS_VISIBLES = 3

def _ejecutar_caso(caso: dict) -> dict:
    """Ejecuta un caso demo, lo encola en HITL si corresponde y devuelve el resultado."""
    with progreso():
        resultado = procesar_texto(
            documento_id=caso["id"],
            canal=caso["canal"],
            texto=caso["texto"],
        )

    decision = resultado.get("decision") or {}
    if decision.get("requiere_revision_humana"):
        ya_en_cola = any(
            item.get("documento_id") == caso["id"]
            for item in st.session_state.cola_hitl
        )
        if not ya_en_cola:
            st.session_state.cola_hitl.append(resultado)

    return resultado

def limpiar_entrada():
    st.session_state.input_key += 1
    st.session_state.pop("resultado", None)  # ajusta al nombre que uses


def _expandir_archivos(archivos) -> list[tuple[str, bytes, str]]:
    """Expande una lista de UploadedFile en (nombre, bytes, mime).

    Los ZIP se descomprimen en memoria y se filtran imágenes/PDF internos.
    """
    pendientes: list[tuple[str, bytes, str]] = []
    for a in archivos:
        nombre = a.name
        contenido = a.getvalue()
        if nombre.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                    for inner in z.namelist():
                        if inner.endswith("/"):
                            continue
                        ext = Path(inner).suffix.lower()
                        mime_map = {
                            ".png": "image/png",
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                            ".pdf": "application/pdf",
                        }
                        if ext in mime_map:
                            pendientes.append((inner, z.read(inner), mime_map[ext]))
            except zipfile.BadZipFile:
                st.error(f"El archivo `{nombre}` no es un ZIP válido.")
        else:
            pendientes.append((nombre, contenido, a.type))
    return pendientes


def _tab_ingesta():
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0

    st.subheader("Ingesta y Triaje de Documentos Clínicos")

    col_input, col_output = st.columns([1, 1], gap="large")

    with col_input:
        st.markdown("#### 1. Seleccioná el método de entrada")

        metodo = st.radio(
            "Método:",
            ["📎 Subir PDF o Imagen", "✏️ Transcripción Manual"],
            label_visibility="collapsed",
        )

        canal = st.selectbox(
            "Canal de origen:",
            [
                "Guardia_Emergencias",
                "Consultorios_Externos",
                "Admision_General",
                "Laboratorio",
                "Radiologia",
            ],
        )

        archivos = []
        texto = ""

        if metodo == "📎 Subir PDF o Imagen":
            archivos = st.file_uploader(
                "Seleccioná uno o varios documentos (PDF, imágenes o ZIP):",
                type=["pdf", "png", "jpg", "jpeg", "zip"],
                accept_multiple_files=True,
                key=f"uploader_{st.session_state.input_key}",
            )
        else:
            texto = st.text_area(
                "Pegá o escribí el contenido del documento:",
                height=220,
                placeholder="Ingresá el informe, receta u orden médica...",
                key=f"texto_{st.session_state.input_key}",
            )

        hay_contenido = bool(archivos) or bool(texto.strip())

        # Reserva el lugar del botón (encima de Procesar)
        espacio_boton = st.empty()

        btn = st.button(
            "🚀 Procesar con MediFlow",
            type="primary",
            use_container_width=True,
            key="btn_procesar",
        )

        # Se dibuja DESPUÉS de saber si se pulsó "Procesar"
        if btn and hay_contenido:
            espacio_boton.button(
                "🛑 Cancelar Procesamiento",
                use_container_width=True,
                key="btn_cancelar",
            )
        else:
            espacio_boton.button(
                "🗑️ Limpiar Campo",
                on_click=limpiar_entrada,
                disabled=not hay_contenido,
                use_container_width=True,
                key="btn_limpiar",
            )

        if archivos:
            st.caption(f"{len(archivos)} archivo(s) seleccionado(s):")
            for a in archivos:
                st.caption(f"• `{a.name}` — {round(a.size / 1024, 1)} KB")
                # Previsualización solo si es imagen única y no ZIP
                if a.type and a.type.startswith("image/"):
                    st.image(a, width="stretch")

    with col_output:
        st.markdown("#### 2. Resultado del Agente")

        if not btn:
            st.info("El resultado aparecerá aquí luego de procesar.")
            return

        try:
            # ── Caso texto manual (sin cambios) ──
            if metodo == "✏️ Transcripción Manual":
                if not texto.strip():
                    st.warning("⚠️ Ingresá un texto primero.")
                    return

                doc_id = f"DOC-{int(time.time())}"
                with progreso():
                    resultado = procesar_texto(
                        documento_id=doc_id,
                        canal=canal,
                        texto=texto,
                    )

                st.success("✅ Procesamiento completado.")
                _mostrar_resultado(resultado)
                return

            # ── Caso archivos (batch) ──
            if not archivos:
                st.warning("⚠️ Seleccioná al menos un archivo.")
                return

            pendientes = _expandir_archivos(archivos)
            if not pendientes:
                st.warning("⚠️ No hay archivos válidos para procesar.")
                return

            st.info(
                f"📦 {len(pendientes)} archivo(s) a procesar "
                f"(de {len(archivos)} seleccionado(s))."
            )

            barra = st.progress(0.0, text="Procesando lote...")
            resultados: list[tuple[str, dict]] = []
            errores: list[tuple[str, str]] = []

            for i, (nombre, contenido, mime) in enumerate(pendientes, start=1):
                doc_id = f"DOC-{int(time.time())}-{i}"
                barra.progress(
                    i / len(pendientes),
                    text=f"[{i}/{len(pendientes)}] {nombre}",
                )
                try:
                    with progreso():
                        res = procesar_archivo(
                            documento_id=doc_id,
                            canal=canal,
                            contenido=contenido,
                            mime=mime,
                        )
                    resultados.append((nombre, res))
                    if (res.get("decision") or {}).get("requiere_revision_humana"):
                        st.session_state.cola_hitl.append(res)
                except Exception as e:
                    errores.append((nombre, str(e)))

            barra.empty()

            # ── Resumen del lote ──
            st.success(
                f"✅ Lote completado: {len(resultados)} OK"
                + (f", {len(errores)} con error" if errores else "")
            )

            if errores:
                with st.expander(f"⚠️ {len(errores)} archivo(s) con error"):
                    for nombre, msg in errores:
                        st.error(f"`{nombre}`: {msg}")

            # ── Resultados por archivo ──
            if len(resultados) == 1:
                nombre, res = resultados[0]
                st.caption(f"Archivo: `{nombre}`")
                _mostrar_resultado(res)
            elif resultados:
                tabs_res = st.tabs([f"📄 {n}" for n, _ in resultados])
                for tab, (nombre, res) in zip(tabs_res, resultados):
                    with tab:
                        _mostrar_resultado(res, anidado=True)

        finally:
            # Se ejecuta siempre: éxito, error o return temprano
            espacio_boton.button(
                "🗑️ Limpiar",
                on_click=limpiar_entrada,
                disabled=not hay_contenido,
                use_container_width=True,
                key="btn_limpiar_final",
            )

def _tab_casos():
    st.subheader("Escenarios Clínicos Reglamentarios")
    st.write("Los 3 flujos obligatorios del hackathon ejecutados en vivo con Cohere.")

    cols = st.columns(3, gap="large")
    caso_a_ejecutar = None

    for col, caso in zip(cols, CASOS_DEMO):
        with col:
            st.markdown(f"### {caso['label']}")
            st.caption(caso["caption"])
            st.write(caso["descripcion"])

            if st.button("▶ Ejecutar", key=caso["id"], use_container_width=True):
                caso_a_ejecutar = caso

    if caso_a_ejecutar:
        resultado = _ejecutar_caso(caso_a_ejecutar)
        previos = [
            d for d in st.session_state.demos_ejecutadas
            if d["caso"]["id"] != caso_a_ejecutar["id"]
        ]
        st.session_state.demos_ejecutadas = (
            [{"caso": caso_a_ejecutar, "resultado": resultado}] + previos
        )[:MAX_DEMOS_VISIBLES]

    demos = st.session_state.demos_ejecutadas
    if demos:
        st.divider()
        st.markdown("#### Resultados")
        for i, demo in enumerate(demos):
            caso = demo["caso"]
            with st.expander(f"{caso['label']} — {caso['badge_texto']}", expanded=(i == 0)):
                _mostrar_resultado(
                    demo["resultado"],
                    badge=caso["badge"],
                    badge_texto=caso["badge_texto"],
                    anidado=True,
                )

@st.cache_data(ttl=300, show_spinner=False)
def _cargar_original(ruta: str):
    return leer_objeto(ruta)

def _mostrar_original(ruta: str | None, clave: str):
    if not ruta:
        st.caption("Documento original no disponible.")
        return
    datos = _cargar_original(ruta)
    if not datos:
        st.caption("No se pudo recuperar el documento original.")
        return
    ext = Path(ruta).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        try:
            st.image(datos, width="stretch")
        except Exception:
            st.warning("El archivo no se puede previsualizar (posiblemente está dañado).")
            st.download_button(
                "⬇️ Descargar archivo original", datos,
                file_name=Path(ruta).name, key=f"dlraw_{clave}",
            )
    elif ext == ".pdf":
        st.download_button(
            "📄 Descargar PDF original", datos,
            file_name=f"{clave}.pdf", mime="application/pdf", key=f"dl_{clave}",
        )
    elif ext == ".txt":
        st.text_area(
            "Texto original", datos.decode("utf-8", "replace"),
            height=160, disabled=True, key=f"txt_{clave}",
        )

def _resolver_expediente(idx: int, doc_id: str, decision: str):
    res = registrar_revision(doc_id, decision)
    st.session_state.cola_hitl.pop(idx)
    if res["status"] == "exito":
        st.session_state.mensaje_hitl = ("ok", f"Expediente {doc_id} {decision}. Registrado en OCI.")
    else:
        st.session_state.mensaje_hitl = (
            "warn", f"Expediente {doc_id} {decision}, pero el registro quedó solo en local ({res['status']}).",
        )
    st.rerun()

def _tab_hitl():
    st.subheader("Consola de Auditoría Human-in-the-Loop")
    st.markdown(
        "Documentos con **score de confianza bajo** o "
        "**campos críticos faltantes** retenidos para revisión."
    )

    msg = st.session_state.pop("mensaje_hitl", None)
    if msg:
        (st.success if msg[0] == "ok" else st.warning)(msg[1])

    if st.button("🔄 Recargar cola desde OCI", key="recargar_cola"):
        st.session_state.cola_hitl = listar_pendientes()
        st.rerun()

    cola = st.session_state.cola_hitl

    if not cola:
        st.success("🎉 Sin expedientes pendientes de auditoría.")
        return

    for idx, item in enumerate(cola):
        doc_id = item.get("documento_id") or f"sin_id_{idx}"
        with st.container(border=True):
            clf = item.get("clasificacion") or {}
            datos = item.get("datos_extraidos") or {}
            decision = item.get("decision") or {}

            paciente = (datos.get("paciente") or {}).get("nombre", "No identificado")
            st.markdown(f"#### Expediente #{idx + 1} — {paciente}")
            st.caption(doc_id)

            col_info, col_accion = st.columns([2, 1])

            with col_info:
                st.write(f"🏷️ **Tipo:** {_txt(clf.get('tipo_documento'), usar_nombre=True)}")
                st.write(f"📊 **Confianza:** {clf.get('score_confianza', 0):.0%}")
                st.write(f"💬 **Motivo:** {decision.get('justificacion', '—')}")

                faltantes = datos.get("campos_faltantes") or []
                if faltantes:
                    st.warning(f"Campos faltantes: {', '.join(faltantes)}")

            with col_accion:
                st.metric(
                    "Score de Confianza",
                    f"{clf.get('score_confianza', 0):.0%}",
                    "Requiere acción",
                )

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✅ Aprobar", key=f"aprobar_{doc_id}"):
                        _resolver_expediente(idx, doc_id, "aprobado")
                    with b2:
                        if st.button("❌ Rechazar", key=f"rechazar_{doc_id}"):
                            _resolver_expediente(idx, doc_id, "rechazado")

            with st.expander("📎 Documento original"):
                _mostrar_original(item.get("archivo_original"), doc_id)

            with st.expander("Ver JSON completo"):
                st.json(item)

def main():
    _estilos()
    _inicializar_estado()
    _sidebar()

    st.title("🏥 MediFlow")
    st.write(
        "Agente autónomo de triaje, extracción y enrutamiento "
        "de documentos clínicos con Cohere AI."
    )

    hitl_count = len(st.session_state.cola_hitl)

    tab_ingesta, tab_casos, tab_hitl = st.tabs([
        "📥 Ingesta y Triaje",
        "🧪 Casos de Demostración",
        f"🩺 Auditoría HITL ({hitl_count})",
    ])

    with tab_ingesta:
        _tab_ingesta()

    with tab_casos:
        _tab_casos()

    with tab_hitl:
        _tab_hitl()

if __name__ == "__main__":
    main()