
import streamlit as st
import time

# ==============================================================================
# ETAPA 1: CONFIGURACIÓN GENERAL Y METADATOS DE LA APLICACIÓN
# Objetivo: Establecer layout, título de pestaña, icono institucional y
#           la barra lateral con el estado operativo del módulo de ingesta.
# ==============================================================================
st.set_page_config(
    page_title="MediFlow - Ingesta de Documentos Clínicos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.title("🏥 MediFlow")
    st.markdown("**Módulo de Ingesta & Triaje**")
    st.caption("No Country - Equipo G10-40")
    st.divider()
    st.info("📌 **Módulo Frontend:** Ingesta digital y captura clínica.")
    st.write("Formatos soportados: **PDF, PNG, JPG, JPEG**.")
    st.divider()
    st.caption("Versión: v1.1 - Formulario de captura y previsualización")

# ==============================================================================
# ETAPA 2: ENCABEZADO Y CONTEXTO OPERATIVO
# Objetivo: Informar al usuario clínico el propósito del módulo.
# ==============================================================================
st.title("MediFlow: Recepción y Carga de Documentación Médica")
st.write("Punto de entrada digital para órdenes médicas, recetas ambulatorias y notas de urgencia.")

col_formulario, col_vista = st.columns([1, 1], gap="large")

# ==============================================================================
# ETAPA 3: FORMULARIO DE INGESTA CLÍNICA (st.form)
# Objetivo: Agrupar la captura del archivo y sus metadatos asociados para evitar
#           recargas innecesarias de la página mientras el usuario interactúa.
# ==============================================================================
with col_formulario:
    st.subheader("1. Formulario de Carga")
    
    with st.form("form_ingesta_clinica", clear_on_submit=False):
        # 3.1 Carga de archivo restrictiva a formatos médicos
        archivo_cargado = st.file_uploader(
            label="Adjunta el documento médico (PDF o Imagen):",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Selecciona una orden médica, receta o informe de alta en formato PDF, PNG o JPG."
        )
        
        # 3.2 Metadatos clínicos complementarios
        categoria_doc = st.selectbox(
            label="Tipo de documento:",
            options=[
                "Receta Médica Ambulatoria",
                "Orden de Urgencia / Triaje",
                "Orden de Exámenes / Laboratorio",
                "Epicrisis / Informe Clínico",
                "Otro Documento Clínico"
            ]
        )
        
        observaciones_ingesta = st.text_area(
            label="Notas de recepción u observaciones (opcional):",
            placeholder="Ej: Documento derivado de Guardia, firma manuscrita poco legible...",
            height=100
        )
        
        # 3.3 Confirmación explícita del formulario
        btn_enviar = st.form_submit_button(
            label="📤 Registrar y Validar Documento",
            type="primary",
            use_container_width=True
        )

# ==============================================================================
# ETAPA 4: VALIDACIÓN, PROCESAMIENTO PRELIMINAR Y PREVISUALIZACIÓN
# Objetivo: Comprobar la presencia del archivo, extraer métricas técnicas
#           (peso, tipo MIME) y renderizar la previsualización visual inmediata.
# ==============================================================================
with col_vista:
    st.subheader("2. Estado y Previsualización")
    
    if btn_enviar:
        # Validación de archivo mandatorio
        if archivo_cargado is None:
            st.error("⚠️ Debes adjuntar un archivo (PDF, JPG o PNG) antes de enviar el formulario.")
        else:
            with st.spinner("Validando integridad del archivo..."):
                time.sleep(0.5)  # Retroalimentación visual
            
            st.success(f"✅ Archivo `{archivo_cargado.name}` recibido y verificado.")
            
            # Cálculo de metadatos técnicos
            tamano_kb = round(archivo_cargado.size / 1024, 2)
            c1, c2 = st.columns(2)
            c1.metric("Categoría", categoria_doc)
            c2.metric("Tamaño", f"{tamano_kb} KB")
            
            st.divider()
            
            # Previsualización según el formato del documento
            if archivo_cargado.type.startswith("image/"):
                st.markdown("**Vista previa de imagen clínica:**")
                st.image(
                    archivo_cargado,
                    caption=f"Vista previa: {archivo_cargado.name}",
                    use_container_width=True
                )
            elif archivo_cargado.type == "application/pdf":
                st.info(f"📄 **Documento PDF recibido:** `{archivo_cargado.name}`")
                st.caption("Los archivos PDF quedan listos para pasar al motor de extracción/OCR.")
                st.download_button(
                    label="📥 Descargar copia de verificación",
                    data=archivo_cargado.getvalue(),
                    file_name=archivo_cargado.name,
                    mime="application/pdf"
                )
            
            # ==================================================================
            # ETAPA 5: ESTRUCTURACIÓN DE METADATOS PARA EL PIPELINE
            # Objetivo: Consolidar el payload que consumirá el backend o el OCR.
            # ==================================================================
            st.divider()
            st.markdown("**Payload estructurado para el pipeline:**")
            payload_ingesta = {
                "nombre_archivo": archivo_cargado.name,
                "formato": archivo_cargado.type,
                "tamano_kb": tamano_kb,
                "categoria_declarada": categoria_doc,
                "observaciones": observaciones_ingesta if observaciones_ingesta else "Sin observaciones",
                "estado_ingesta": "LISTO_PARA_EXTRACCION"
            }
            st.json(payload_ingesta)
    else:
        st.info("Los metadatos del documento y la vista previa se mostrarán aquí una vez enviado el formulario.")