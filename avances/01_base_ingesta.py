import streamlit as st
import time

st.set_page_config(
    page_title="MediFlow - Triaje Clínico",
    page_icon="🏥",
    layout="wide"
)

with st.sidebar:
    st.title("🏥 MediFlow")
    st.markdown("**Agente Clínico Autónomo**")
    st.caption("No Country - Equipo G10-40")
    st.divider()
    st.info("📌 **Fase 1:** Maquetación e ingesta base")

st.title("MediFlow: Recepción y Triaje de Documentos")
st.write("Módulo de ingesta clínica para documentos médicos.")

col_izq, col_der = st.columns([1, 1], gap="medium")

with col_izq:
    st.subheader("1. Entrada de Documentación")
    metodo = st.radio("Selecciona formato de entrada:", ["Subir Archivo", "Texto Manual"])

    if metodo == "Subir Archivo":
        archivo = st.file_uploader("Adjunta orden médica o receta:", type=["jpg", "jpeg", "png", "pdf"])
        if archivo:
            st.success(f"Archivo cargado: `{archivo.name}`")
            if archivo.type.startswith("image/"):
                st.image(archivo, caption="Previsualización", use_container_width=True)
    else:
        texto_medico = st.text_area(
            "Transcripción o reporte clínico:",
            placeholder="Ingresa los hallazgos médicos o síntomas del paciente...",
            height=180
        )

    btn_evaluar = st.button("Procesar Documento", type="primary", use_container_width=True)

with col_der:
    st.subheader("2. Salida Preliminar")
    if btn_evaluar:
        with st.spinner("Validando formato de entrada..."):
            time.sleep(1)
        st.success("✅ Entrada recibida correctamente por el frontend.")
        st.caption("Listo para conectar con el backend.")
    else:
        st.info("Los datos procesados se mostrarán aquí una vez integrado el modelo.")