import time

import streamlit as st

from agent_cohere import analizar_triaje_cohere
from main import procesar_archivo_mediflow


# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

st.set_page_config(
    page_title="MediFlow - Agente Clínico (Cohere AI)",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==============================================================================
# DEPENDENCIAS OPCIONALES
# ==============================================================================

try:
    import pypdf

    PYPDF_DISPONIBLE = True
except ImportError:
    PYPDF_DISPONIBLE = False


# ==============================================================================
# CONSTANTES
# ==============================================================================

TIPOS_ARCHIVO = ["pdf", "png", "jpg", "jpeg"]

CATEGORIAS_DOCUMENTO = [
    "Receta Médica Ambulatoria",
    "Orden de Urgencia / Triaje",
    "Examen de Laboratorio",
    "Otro",
]


# ==============================================================================
# ESTILOS
# ==============================================================================

def configurar_estilos():
    st.markdown(
        """
        <style>
            .badge-urgente {
                background-color: #fee2e2;
                color: #991b1b;
                padding: 4px 10px;
                border-radius: 6px;
                font-weight: 600;
            }

            .badge-rutina {
                background-color: #dcfce7;
                color: #166534;
                padding: 4px 10px;
                border-radius: 6px;
                font-weight: 600;
            }

            .badge-hitl {
                background-color: #fef3c7;
                color: #92400e;
                padding: 4px 10px;
                border-radius: 6px;
                font-weight: 600;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# ESTADO DE SESIÓN
# ==============================================================================

def inicializar_estado():
    if "cola_hitl" not in st.session_state:
        st.session_state.cola_hitl = []


# ==============================================================================
# SIDEBAR
# ==============================================================================

def renderizar_sidebar():
    with st.sidebar:
        st.title("🏥 MediFlow")
        st.markdown("**Agente Clínico Autónomo**")
        st.caption("No Country - Equipo G10-40")

        st.divider()

        st.success("🟢 Inferencia: Cohere (command-r)")

        st.info(
            "📦 Buckets OCI: "
            "`triage-urgencias`, "
            "`triage-rutina`, "
            "`triage-hitl`"
        )

        st.write(
            "Casos en Auditoría HITL: "
            f"**{len(st.session_state.cola_hitl)}**"
        )

        st.divider()

        st.caption(
            "Versión: v2.0 - Pipeline Completo "
            "con Inferencia Cohere"
        )


# ==============================================================================
# PDF
# ==============================================================================

def extraer_texto_pdf(archivo):
    """
    Extrae texto de un archivo PDF utilizando pypdf.
    """

    if not PYPDF_DISPONIBLE:
        return (
            "Instala 'pypdf' para lectura automática, "
            "o escribe aquí el contenido."
        )

    try:
        lector = pypdf.PdfReader(archivo)

        paginas = []

        for pagina in lector.pages:
            texto = pagina.extract_text()

            if texto:
                paginas.append(texto)

        return "\n".join(paginas)

    except Exception as error:
        return f"Error al leer PDF: {error}"


# ==============================================================================
# INGESTA DE DOCUMENTOS
# ==============================================================================

def renderizar_ingesta():
    st.subheader("1. Ingesta de Documentos")

    col_input, col_output = st.columns(
        [1, 1],
        gap="large",
    )

    with col_input:
        metodo = st.radio(
            "Método de entrada:",
            [
                "Subir Documento (PDF / Imagen)",
                "Transcripción Manual",
            ],
        )

        texto_a_procesar = ""
        archivo = None

        # ----------------------------------------------------------------------
        # ARCHIVO
        # ----------------------------------------------------------------------

        if metodo == "Subir Documento (PDF / Imagen)":

            archivo = st.file_uploader(
                "Selecciona una orden médica o receta:",
                type=TIPOS_ARCHIVO,
            )

            st.selectbox(
                "Categoría declarada:",
                CATEGORIAS_DOCUMENTO,
            )

            if archivo:
                tamano_kb = round(
                    archivo.size / 1024,
                    2,
                )

                st.caption(
                    f"Archivo: `{archivo.name}` "
                    f"({tamano_kb} KB)"
                )

                # --------------------------------------------------------------
                # IMAGEN
                # --------------------------------------------------------------

                if archivo.type.startswith("image/"):

                    st.image(
                        archivo,
                        caption="Previsualización del documento",
                        use_container_width=True,
                    )

                    texto_a_procesar = st.text_area(
                        "Texto extraído del documento "
                        "(OCR / Transcripción):",
                        value=(
                            "POSTA RURAL DE SALUD. "
                            "Paciente Alicia o Ana M... "
                            "Dolor abd difuso, nauseas leves. "
                            "Hipotesis: Colico biliar vs "
                            "Apendicitis incipiente?? "
                            "Viadil amp. Firma ilegible."
                        ),
                        height=120,
                    )

                # --------------------------------------------------------------
                # PDF
                # --------------------------------------------------------------

                elif archivo.type == "application/pdf":

                    st.info(
                        f"📄 Archivo PDF cargado: "
                        f"`{archivo.name}`"
                    )

                    texto_extraido = extraer_texto_pdf(
                        archivo
                    )

                    texto_a_procesar = st.text_area(
                        "Contenido extraído del PDF:",
                        value=texto_extraido,
                        height=160,
                    )

        # ----------------------------------------------------------------------
        # TRANSCRIPCIÓN
        # ----------------------------------------------------------------------

        else:

            texto_a_procesar = st.text_area(
                "Ingresa o pega el informe clínico:",
                height=220,
                placeholder=(
                    "Escribe los síntomas, antecedentes "
                    "y hallazgos diagnósticos..."
                ),
            )

        # ----------------------------------------------------------------------
        # BOTÓN
        # ----------------------------------------------------------------------

        btn_evaluar = st.button(
            "🚀 Procesar con Agente MediFlow (Cohere)",
            type="primary",
            use_container_width=True,
        )

    # --------------------------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------------------------

    with col_output:

        st.subheader("2. Evaluación y Enrutamiento")

        if not btn_evaluar:
            return

        resultado = None

        # ----------------------------------------------------------------------
        # PROCESAR ARCHIVO
        # ----------------------------------------------------------------------

        if metodo == "Subir Documento (PDF / Imagen)":

            if not archivo:
                st.warning(
                    "⚠️ Debés proporcionar un archivo."
                )
                return

            with st.spinner(
                "Procesando archivo con Cohere Vision..."
            ):
                resultado = procesar_archivo_mediflow(
                    doc_id=f"DOC-{int(time.time())}",
                    archivo_bytes=archivo.getvalue(),
                    tipo_mime=archivo.type,
                )

        # ----------------------------------------------------------------------
        # PROCESAR TEXTO
        # ----------------------------------------------------------------------

        elif metodo == "Transcripción Manual":

            if not texto_a_procesar.strip():
                st.warning(
                    "⚠️ Debés proporcionar un texto."
                )
                return

            with st.spinner(
                "Procesando con Cohere AI..."
            ):
                resultado = analizar_triaje_cohere(
                    texto_a_procesar
                )

        # ----------------------------------------------------------------------
        # MOSTRAR RESULTADO
        # ----------------------------------------------------------------------

        if resultado is not None:
            st.success("✅ Procesamiento completado.")
            st.json(resultado)


# ==============================================================================
# CASOS DE DEMOSTRACIÓN
# ==============================================================================

def ejecutar_caso_1():
    texto = (
        "Paciente: Mateo Rivas, 61 años. "
        "Ingresa por guardia con disnea súbita, "
        "taquipnea (28 rpm) y dolor pleurítico derecho. "
        "AngioTAC confirma defecto de repleción masivo "
        "compatible con TEP agudo. "
        "Se indica Heparina IV continua. "
        "Dra. Sofía Mendoza Reg 8831."
    )

    with st.spinner("Analizando Caso 1..."):
        resultado = analizar_triaje_cohere(texto)

    st.markdown(
        '<span class="badge-urgente">'
        "🚨 PRIORIDAD CRÍTICA"
        "</span>",
        unsafe_allow_html=True,
    )

    st.json(resultado)


def ejecutar_caso_2():
    texto = (
        "Control de salud crónico. "
        "Paciente: Carlos Henríquez, 54 años. "
        "Antecedente de diabetes mellitus tipo 2 "
        "e hipertensión arterial compensada. "
        "Se renueva prescripción: Metformina 850mg "
        "cada 12h y Losartán 50mg cada 24h "
        "por 6 meses. "
        "Dr. Fernando Soto Reg 4410."
    )

    with st.spinner("Analizando Caso 2..."):
        resultado = analizar_triaje_cohere(texto)

    st.markdown(
        '<span class="badge-rutina">'
        "🟢 RUTINA MÉDICA"
        "</span>",
        unsafe_allow_html=True,
    )

    st.json(resultado)


def ejecutar_caso_3():
    texto = (
        "Paciente: Ana o Alicia (datos no claros). "
        "Manuscrito con tinta corrida: "
        "dolor abdominal inespecífico... "
        "apendicitis incipiente vs colico biliar??... "
        "Indico antiespasmódico... "
        "Firma y sello ilegibles."
    )

    with st.spinner("Analizando Caso 3..."):
        resultado = analizar_triaje_cohere(texto)

    st.markdown(
        '<span class="badge-hitl">'
        "⚠️ RETENIDO EN AUDITORÍA"
        "</span>",
        unsafe_allow_html=True,
    )

    st.session_state.cola_hitl.append(resultado)

    st.json(resultado)


def renderizar_casos():
    st.subheader("Escenarios Clínicos Reglamentarios")

    st.write(
        "Prueba los tres flujos en vivo "
        "ejecutados a través de Cohere:"
    )

    c1, c2, c3 = st.columns(3)

    # --------------------------------------------------------------------------
    # CASO 1
    # --------------------------------------------------------------------------

    with c1:
        st.markdown("### Caso 1: TEP Agudo")
        st.caption("Urgencia Crítica / Guardia Central")

        st.write(
            "Paciente con disnea súbita y "
            "tromboembolismo confirmado por AngioTAC."
        )

        if st.button(
            "Ejecutar Caso 1 (Urgencia)",
            use_container_width=True,
        ):
            ejecutar_caso_1()

    # --------------------------------------------------------------------------
    # CASO 2
    # --------------------------------------------------------------------------

    with c2:
        st.markdown("### Caso 2: Receta Crónica")
        st.caption("Rutina Ambulatoria / Farmacia")

        st.write(
            "Control periódico y renovación de fármacos "
            "en paciente con diabetes e hipertensión."
        )

        if st.button(
            "Ejecutar Caso 2 (Rutina)",
            use_container_width=True,
        ):
            ejecutar_caso_2()

    # --------------------------------------------------------------------------
    # CASO 3
    # --------------------------------------------------------------------------

    with c3:
        st.markdown("### Caso 3: Nota Ilegible")
        st.caption("Activación de Seguridad HITL")

        st.write(
            "Nota ambigua y manuscrita que debe ser "
            "derivada para supervisión humana."
        )

        if st.button(
            "Ejecutar Caso 3 (Auditoría)",
            use_container_width=True,
        ):
            ejecutar_caso_3()


# ==============================================================================
# AUDITORÍA HITL
# ==============================================================================

def aprobar_expediente(idx):
    st.session_state.cola_hitl.pop(idx)

    st.success(
        "Expediente aprobado y remitido "
        "al bucket final."
    )

    st.rerun()


def rechazar_expediente(idx):
    st.session_state.cola_hitl.pop(idx)

    st.warning(
        "Expediente rechazado y devuelto "
        "a recepción."
    )

    st.rerun()


def renderizar_hitl():
    st.subheader(
        "Consola de Supervisión y "
        "Control de Calidad Médica"
    )

    st.markdown(
        "Documentos con score de confianza menor "
        "a **0.85** o inconsistencias clínicas."
    )

    cola = st.session_state.cola_hitl

    if not cola:
        st.success(
            "🎉 No hay expedientes pendientes "
            "de auditoría médica."
        )
        return

    for idx, item in enumerate(cola):

        with st.container():

            paciente = item.get(
                "paciente",
                "No identificado",
            )

            st.markdown(
                f"#### Expediente #{idx + 1}: "
                f"Paciente **{paciente}**"
            )

            col_izq, col_der = st.columns([2, 1])

            # ------------------------------------------------------------------
            # INFORMACIÓN
            # ------------------------------------------------------------------

            with col_izq:

                st.write(
                    "**Motivo de retención:** "
                    f"{item.get(
                        'motivo_auditoria',
                        'Confianza insuficiente'
                    )}"
                )

                st.write(
                    "**Diagnóstico preliminar:** "
                    f"{item.get(
                        'diagnostico_cie10',
                        'Sin clasificar'
                    )}"
                )

                st.write(
                    "**Médico detectado:** "
                    f"{item.get(
                        'medico',
                        'No identificado'
                    )}"
                )

                sintomas = item.get(
                    "sintomas",
                    [],
                )

                st.write(
                    "**Síntomas identificados:** "
                    f"{', '.join(sintomas)}"
                )

            # ------------------------------------------------------------------
            # ACCIONES
            # ------------------------------------------------------------------

            with col_der:

                conf = float(
                    item.get(
                        "score_confianza",
                        0.0,
                    )
                )

                st.metric(
                    "Confianza del Modelo",
                    f"{conf * 100:.1f}%",
                    "- Requiere acción",
                )

                b1, b2 = st.columns(2)

                with b1:
                    if st.button(
                        "✅ Aprobar",
                        key=f"aprobar_{idx}",
                    ):
                        aprobar_expediente(idx)

                with b2:
                    if st.button(
                        "❌ Rechazar",
                        key=f"rechazar_{idx}",
                    ):
                        rechazar_expediente(idx)

            st.divider()


# ==============================================================================
# APLICACIÓN PRINCIPAL
# ==============================================================================

def main():
    configurar_estilos()
    inicializar_estado()
    renderizar_sidebar()

    st.title(
        "MediFlow: Triaje, Extracción "
        "y Enrutamiento Clínico"
    )

    st.write(
        "Automatización de ingesta médica con "
        "inferencia Cohere y supervisión médica "
        "Human-in-the-Loop."
    )

    tab_ingesta, tab_casos, tab_hitl = st.tabs(
        [
            "📥 Ingesta y Triaje Clínico",
            "🧪 Casos de Demostración",
            f"🩺 Auditoría Human-in-the-Loop "
            f"({len(st.session_state.cola_hitl)})",
        ]
    )

    with tab_ingesta:
        renderizar_ingesta()

    with tab_casos:
        renderizar_casos()

    with tab_hitl:
        renderizar_hitl()


if __name__ == "__main__":
    main()
