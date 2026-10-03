"""
app.py — MediFlow: triaje, extracción y enrutamiento clínico (Streamlit).

Ejecutar:
    streamlit run app.py

Pipeline de ingesta:
    archivo → main.procesar_archivo (image_loader / pdf_loader)
            → main.analizar_documento → agent_cohere (texto) | agent_vision (imagen)
"""

import os
import tempfile
from pathlib import Path

import streamlit as st

from agent_cohere import analizar_triaje_cohere
from main import EXTENSIONES_SOPORTADAS, analizar_documento, procesar_archivo

# ==============================================================================
# CONFIGURACIÓN GENERAL Y ESTILO
# ==============================================================================
st.set_page_config(
    page_title="MediFlow - Agente Clínico (Cohere AI)",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .badge-urgente { background-color: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 6px; font-weight: 600; }
    .badge-rutina { background-color: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 6px; font-weight: 600; }
    .badge-hitl { background-color: #fef3c7; color: #92400e; padding: 4px 10px; border-radius: 6px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Estado de la sesión
if "cola_hitl" not in st.session_state:
    st.session_state.cola_hitl = []
if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado = None
if "doc_cache" not in st.session_state:
    st.session_state.doc_cache = None

# Barra lateral
with st.sidebar:
    st.title("🏥 MediFlow")
    st.markdown("**Agente Clínico Autónomo**")
    st.caption("No Country - Equipo G10-40")
    st.divider()
    st.success("🟢 Inferencia: Cohere (command-r texto · command-a-vision imagen)")
    st.info("📦 Buckets OCI: `triage-urgencias`, `triage-rutina`, `triage-hitl`")
    st.write(f"Casos en Auditoría HITL: **{len(st.session_state.cola_hitl)}**")
    st.divider()
    st.caption("Versión: v2.1 - Pipeline con agentes de texto y visión")


# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================
def cargar_documento(archivo):
    """Guarda el archivo subido en un temporal, lo procesa con los loaders y cachea el resultado.

    Devuelve (documento, error). El análisis con IA NO ocurre aquí.
    """
    clave = (archivo.name, archivo.size)
    cache = st.session_state.doc_cache
    if cache and cache["clave"] == clave:
        return cache["documento"], None

    sufijo = Path(archivo.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(archivo.getvalue())
        ruta_tmp = tmp.name
    try:
        documento = procesar_archivo(ruta_tmp)
    except Exception as e:
        return None, str(e)
    finally:
        os.unlink(ruta_tmp)

    st.session_state.doc_cache = {"clave": clave, "documento": documento}
    st.session_state.ultimo_resultado = None  # archivo nuevo → limpiar resultado previo
    return documento, None


def mostrar_resultado(resultado: dict):
    """Pinta el resultado del triaje (badge, métricas, destino OCI y JSON)."""
    if "error" in resultado:
        st.error(f"Error: {resultado['error']}")
        return

    confianza = float(resultado.get("score_confianza", 0.0))
    prioridad = resultado.get("prioridad", "AMBIGUA")
    destino = resultado.get("destino_sugerido", "No definido")

    if resultado.get("requiere_auditoria"):
        st.markdown('<span class="badge-hitl">⚠️ RETENIDO PARA AUDITORÍA CLÍNICA (HITL)</span>', unsafe_allow_html=True)
        st.metric("Confianza del Modelo", f"{confianza * 100:.1f}%", "- Requiere revisión manual (< 85%)")
        st.warning(f"**Motivo:** {resultado.get('motivo_auditoria', 'Incertidumbre o datos incompletos')}")
        st.markdown("**Destino OCI:** `oci://triage-hitl/`")
    elif prioridad == "CRÍTICA":
        st.markdown('<span class="badge-urgente">🚨 PRIORIDAD: CRÍTICA / URGENCIA</span>', unsafe_allow_html=True)
        st.metric("Confianza del Modelo", f"{confianza * 100:.1f}%", "Aprobado (> 85%)")
        st.success(f"**Destino:** {destino}")
        st.markdown("**Destino OCI:** `oci://triage-urgencias/`")
    else:
        st.markdown('<span class="badge-rutina">🟢 PRIORIDAD: RUTINA AMBULATORIA</span>', unsafe_allow_html=True)
        st.metric("Confianza del Modelo", f"{confianza * 100:.1f}%", "Aprobado (> 85%)")
        st.info(f"**Destino:** {destino}")
        st.markdown("**Destino OCI:** `oci://triage-rutina/`")

    st.markdown("#### Entidades Clínicas Extraídas (JSON)")
    st.json(resultado)


# ==============================================================================
st.title("MediFlow: Triaje, Extracción y Enrutamiento Clínico")
st.write("Automatización de ingesta médica con inferencia Cohere y supervisión médica Human-in-the-Loop.")

tab_ingesta, tab_casos, tab_hitl = st.tabs([
    "📥 Ingesta y Triaje Clínico",
    "🧪 Casos de Demostración",
    f"🩺 Auditoría Human-in-the-Loop ({len(st.session_state.cola_hitl)})",
])

# ------------------------------------------------------------------------------
# PESTAÑA 1: INGESTA Y TRIAJE EN VIVO
# ------------------------------------------------------------------------------
with tab_ingesta:
    st.subheader("1. Ingesta de Documentos")
    col_input, col_output = st.columns([1, 1], gap="large")

    with col_input:
        metodo = st.radio("Método de entrada:", ["Subir Documento (PDF / Imagen)", "Transcripción Manual"])
        subir = metodo == "Subir Documento (PDF / Imagen)"
        documento = None
        texto_manual = ""

        if subir:
            archivo = st.file_uploader(
                "Selecciona una orden médica o receta:",
                type=[e.lstrip(".") for e in EXTENSIONES_SOPORTADAS],
            )

            if archivo:
                st.caption(f"Archivo: `{archivo.name}` ({round(archivo.size / 1024, 2)} KB)")
                with st.spinner("Leyendo documento..."):
                    documento, err = cargar_documento(archivo)

                if err:
                    st.error(f"No se pudo leer el archivo: {err}")
                else:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Tipo", documento["tipo"])
                    c2.metric("Modo", documento["modo"])
                    c3.metric("Imágenes", len(documento["imagenes_data_url"]))

                    if documento["modo"] == "texto":
                        # Texto nativo: editable antes de enviarlo al agente de texto
                        texto_editado = st.text_area(
                            "Texto extraído del documento (editable):",
                            value=documento["texto"],
                            height=220,
                            key=f"texto_{archivo.name}_{archivo.size}",
                        )
                        documento = {**documento, "texto": texto_editado}
                    elif documento["modo"] == "error":
                        st.error(documento["texto"])
                    else:
                        # Imagen / escaneado: vista previa de lo que verá el agente de visión
                        for i, url in enumerate(documento["imagenes_data_url"][:3], start=1):
                            st.image(url, caption=f"Imagen {i}", use_container_width=True)
                        restantes = len(documento["imagenes_data_url"]) - 3
                        if restantes > 0:
                            st.caption(f"... y {restantes} imagen(es) más.")
        else:
            texto_manual = st.text_area(
                "Ingresa o pega el informe clínico:",
                height=220,
                placeholder="Escribe los síntomas, antecedentes y hallazgos diagnósticos...",
            )

        btn_evaluar = st.button("🚀 Procesar con Agente MediFlow (Cohere)", type="primary", use_container_width=True)

    with col_output:
        st.subheader("2. Evaluación y Enrutamiento")

        if btn_evaluar:
            resultado = None
            if subir:
                if documento is None:
                    st.warning("⚠️ Debes subir un documento válido.")
                else:
                    agente = "visión" if documento["modo"] == "imagen" else "texto"
                    with st.spinner(f"Analizando con el agente de {agente} de Cohere..."):
                        salida = analizar_documento(documento)
                    if salida["mensaje"]:
                        st.warning(salida["mensaje"])
                    resultado = salida["triaje"]
            elif not texto_manual.strip():
                st.warning("⚠️ Debes proporcionar un texto clínico para evaluar.")
            else:
                with st.spinner("Procesando con Cohere AI y extrayendo entidades clínicas..."):
                    resultado = analizar_triaje_cohere(texto_manual)

            if resultado:
                if "error" not in resultado and resultado.get("requiere_auditoria"):
                    st.session_state.cola_hitl.append(resultado)
                st.session_state.ultimo_resultado = resultado

        if st.session_state.ultimo_resultado:
            mostrar_resultado(st.session_state.ultimo_resultado)
        elif not btn_evaluar:
            st.info("Los resultados de la inferencia clínica aparecerán aquí al procesar el documento.")

# ------------------------------------------------------------------------------
# PESTAÑA 2: CASOS DE DEMOSTRACIÓN (EN VIVO CON COHERE)
# ------------------------------------------------------------------------------
with tab_casos:
    st.subheader("Escenarios Clínicos Reglamentarios")
    st.write("Prueba los tres flujos en vivo ejecutados a través de Cohere:")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### Caso 1: TEP Agudo")
        st.caption("Urgencia Crítica / Guardia Central")
        st.write("Paciente con disnea súbita y tromboembolismo confirmado por AngioTAC.")
        if st.button("Ejecutar Caso 1 (Urgencia)", use_container_width=True):
            texto_c1 = "Paciente: Mateo Rivas, 61 años. Ingresa por guardia con disnea súbita, taquipnea (28 rpm) y dolor pleurítico derecho. AngioTAC confirma defecto de repleción masivo compatible con TEP agudo. Se indica Heparina IV continua. Dra. Sofía Mendoza Reg 8831."
            with st.spinner("Analizando Caso 1..."):
                r1 = analizar_triaje_cohere(texto_c1)
            st.markdown('<span class="badge-urgente">🚨 PRIORIDAD CRÍTICA</span>', unsafe_allow_html=True)
            st.json(r1)

    with c2:
        st.markdown("### Caso 2: Receta Crónica")
        st.caption("Rutina Ambulatoria / Farmacia")
        st.write("Control periódico y renovación de fármacos en paciente con diabetes e hipertensión.")
        if st.button("Ejecutar Caso 2 (Rutina)", use_container_width=True):
            texto_c2 = "Control de salud crónico. Paciente: Carlos Henríquez, 54 años. Antecedente de diabetes mellitus tipo 2 e hipertensión arterial compensada. Se renueva prescripción: Metformina 850mg cada 12h y Losartán 50mg cada 24h por 6 meses. Dr. Fernando Soto Reg 4410."
            with st.spinner("Analizando Caso 2..."):
                r2 = analizar_triaje_cohere(texto_c2)
            st.markdown('<span class="badge-rutina">🟢 RUTINA MÉDICA</span>', unsafe_allow_html=True)
            st.json(r2)

    with c3:
        st.markdown("### Caso 3: Nota Ilegible")
        st.caption("Activación de Seguridad HITL")
        st.write("Nota ambigua y manuscrita que debe ser derivada para supervisión humana.")
        if st.button("Ejecutar Caso 3 (Auditoría)", use_container_width=True):
            texto_c3 = "Paciente: Ana o Alicia (datos no claros). Manuscrito con tinta corrida: dolor abdominal inespecífico... apendicitis incipiente vs colico biliar??... Indico antiespasmódico... Firma y sello ilegibles."
            with st.spinner("Analizando Caso 3..."):
                r3 = analizar_triaje_cohere(texto_c3)
            st.markdown('<span class="badge-hitl">⚠️ RETENIDO EN AUDITORÍA</span>', unsafe_allow_html=True)
            st.session_state.cola_hitl.append(r3)
            st.json(r3)

# ------------------------------------------------------------------------------
# PESTAÑA 3: AUDITORÍA HUMAN-IN-THE-LOOP (HITL)
# ------------------------------------------------------------------------------
with tab_hitl:
    st.subheader("Consola de Supervisión y Control de Calidad Médica")
    st.markdown("Documentos con score de confianza menor a **0.85** o inconsistencias clínicas.")

    if not st.session_state.cola_hitl:
        st.success("🎉 No hay expedientes pendientes de auditoría médica.")
    else:
        for idx, item in enumerate(st.session_state.cola_hitl):
            with st.container():
                st.markdown(f"#### Expediente #{idx + 1}: Paciente **{item.get('paciente', 'No identificado')}**")
                col_izq_hitl, col_der_hitl = st.columns([2, 1])

                with col_izq_hitl:
                    st.write(f"**Motivo de retención:** {item.get('motivo_auditoria', 'Confianza insuficiente')}")
                    st.write(f"**Diagnóstico preliminar:** {item.get('diagnostico_cie10', 'Sin clasificar')}")
                    st.write(f"**Médico detectado:** {item.get('medico', 'No identificado')}")
                    st.write(f"**Síntomas identificados:** {', '.join(item.get('sintomas', []))}")

                with col_der_hitl:
                    conf = float(item.get("score_confianza", 0.0))
                    st.metric("Confianza del Modelo", f"{conf * 100:.1f}%", "- Requiere acción")

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("✅ Aprobar", key=f"ap_{idx}"):
                            st.session_state.cola_hitl.pop(idx)
                            st.success("Expediente aprobado y remitido al bucket final.")
                            st.rerun()
                    with b2:
                        if st.button("❌ Rechazar", key=f"rec_{idx}"):
                            st.session_state.cola_hitl.pop(idx)
                            st.warning("Expediente rechazado y devuelto a recepción.")
                            st.rerun()
                st.divider()
