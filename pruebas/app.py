"""
app.py — Interfaz Streamlit para subir una imagen o un PDF.

Ejecutar:
    streamlit run app.py
"""

import os
import tempfile
from pathlib import Path

import streamlit as st

from main import EXTENSIONES_SOPORTADAS, procesar_y_analizar

st.set_page_config(page_title="MediFlow - Carga de documentos", page_icon="🩺")
st.title("🩺 Carga de documentos")
st.caption("Sube una imagen (JPG, PNG, WEBP) o un PDF.")

COLOR_PRIORIDAD = {"CRÍTICA": "🔴", "RUTINA": "🟢", "AMBIGUA": "🟡"}

archivo = st.file_uploader(
    "Selecciona un archivo",
    type=[e.lstrip(".") for e in EXTENSIONES_SOPORTADAS],
)

if archivo is not None:
    # Los loaders trabajan con rutas en disco → guardamos en un temporal
    # conservando la extensión (la usan para decidir el formato).
    sufijo = Path(archivo.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(archivo.getvalue())
        ruta_tmp = tmp.name

    try:
        with st.spinner("Procesando y analizando..."):
            salida = procesar_y_analizar(ruta_tmp)
    except Exception as e:
        st.error(f"No se pudo procesar el archivo: {e}")
    else:
        doc = salida["documento"]
        triaje = salida["triaje"]

        col1, col2, col3 = st.columns(3)
        col1.metric("Tipo", doc["tipo"])
        col2.metric("Modo", doc["modo"])
        col3.metric("Imágenes", len(doc["imagenes_data_url"]))

        if salida["mensaje"]:
            st.warning(salida["mensaje"])

        # --- Resultado del agente de triaje (solo modo texto) ---
        if triaje:
            st.subheader("Resultado del triaje")
            if "error" in triaje:
                st.error(triaje["error"])
            else:
                prioridad = triaje.get("prioridad", "-")
                c1, c2, c3 = st.columns(3)
                c1.metric("Prioridad", f"{COLOR_PRIORIDAD.get(prioridad, '')} {prioridad}")
                c2.metric("Destino", triaje.get("destino_sugerido", "-"))
                c3.metric("Confianza", f"{float(triaje.get('score_confianza', 0)):.0%}")

                st.write(f"**Paciente:** {triaje.get('paciente', '-')}")
                st.write(f"**Médico:** {triaje.get('medico', '-')}")
                st.write(f"**Diagnóstico:** {triaje.get('diagnostico_cie10', '-')}")
                st.write("**Síntomas:** " + ", ".join(triaje.get("sintomas", [])))

                if triaje.get("requiere_auditoria"):
                    st.warning(f"Requiere auditoría humana: {triaje.get('motivo_auditoria', '')}")

            with st.expander("JSON completo"):
                st.json(triaje)

        if doc["texto"] and doc["modo"] != "error":
            with st.expander("Texto extraído"):
                st.text(doc["texto"])

        if doc["imagenes_data_url"]:
            with st.expander("Imágenes enviadas al modelo"):
                for i, data_url in enumerate(doc["imagenes_data_url"], start=1):
                    st.image(data_url, caption=f"Imagen {i}", use_container_width=True)

        st.session_state["salida"] = salida
    finally:
        os.unlink(ruta_tmp)
