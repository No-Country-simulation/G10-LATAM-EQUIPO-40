import streamlit as st
import json
import time

st.set_page_config(
    page_title="MediFlow - Triaje Clínico Inteligente",
    page_icon="🏥",
    layout="wide"
)

if "cola_hitl" not in st.session_state:
    st.session_state.cola_hitl = [
        {
            "id": "DOC-9042",
            "paciente": "Elena Morales",
            "motivo_retencion": "Puntuación de confianza inferior al umbral (0.68) y firma no identificable.",
            "diagnostico_estimado": "Bronquitis aguda vs Neumonía (J20.9)",
            "confianza": 0.68,
            "estado": "Pendiente de Auditoría",
            "fecha": "2026-09-28 19:35"
        }
    ]

with st.sidebar:
    st.title("🏥 MediFlow")
    st.markdown("**Agente Clínico Autónomo**")
    st.caption("No Country - Equipo G10-40")
    st.divider()
    st.subheader("Infraestructura")
    st.success("🟢 Cohere Command-R: Conectado")
    st.success("🟢 OCI Storage: Activo")

st.title("MediFlow: Triaje, Extracción y Enrutamiento Clínico")

tab_ingesta, tab_casos, tab_hitl = st.tabs([
    "📥 Ingesta y Triaje Clínico",
    "🧪 Casos de Demostración",
    f"🩺 Auditoría Human-in-the-Loop ({len([c for c in st.session_state.cola_hitl if c['estado'] == 'Pendiente de Auditoría'])})"
])

with tab_ingesta:
    st.subheader("Carga y Procesamiento de Documentos")
    col_input, col_output = st.columns([1, 1], gap="large")
    with col_input:
        metodo = st.radio("Método de entrada:", ["Subir Archivo (PDF / Imagen)", "Transcripción de Texto"])
        doc_texto = ""
        doc_archivo = None
        if metodo == "Subir Archivo (PDF / Imagen)":
            doc_archivo = st.file_uploader("Selecciona orden médica o receta:", type=["jpg", "jpeg", "png", "pdf"])
            if doc_archivo:
                st.image(doc_archivo, caption="Vista previa", use_container_width=True)
        else:
            doc_texto = st.text_area("Pega el texto del informe clínico:", height=180)
        btn_procesar = st.button("🚀 Procesar con Agente", type="primary", use_container_width=True)

    with col_output:
        st.subheader("Resultado de Evaluación")
        if btn_procesar:
            st.success("✅ Procesamiento completado.")
            st.json({"prioridad": "ALTA", "destino": "Guardia", "confianza": 0.95})
        else:
            st.info("Los resultados aparecerán aquí tras procesar.")

with tab_casos:
    st.subheader("Escenarios de Prueba Reglamentarios")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### Caso 1: TEP Agudo")
        if st.button("Ejecutar Caso 1"):
            st.success("Enrutado a Guardia Central.")
    with col2:
        st.markdown("### Caso 2: Receta Crónica")
        if st.button("Ejecutar Caso 2"):
            st.info("Enrutado a Farmacia.")
    with col3:
        st.markdown("### Caso 3: Orden Ilegible")
        if st.button("Ejecutar Caso 3"):
            st.warning("Derivado a cola HITL.")

with tab_hitl:
    st.subheader("Panel Human-in-the-Loop")
    pendientes = [item for item in st.session_state.cola_hitl if item["estado"] == "Pendiente de Auditoría"]
    if not pendientes:
        st.success("No hay casos pendientes.")
    else:
        for item in pendientes:
            st.write(f"**Expediente:** `{item['id']}` - **Paciente:** {item['paciente']}")
            st.write(f"Motivo: {item['motivo_retencion']}")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Aprobar", key=f"ap_{item['id']}"):
                    item["estado"] = "Aprobado"
                    st.rerun()
            with col_b:
                if st.button("❌ Rechazar", key=f"rec_{item['id']}"):
                    item["estado"] = "Rechazado"
                    st.rerun()
            st.divider()