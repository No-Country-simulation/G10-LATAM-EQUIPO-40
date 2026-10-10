"""
MediFlow - Interfaz Streamlit
Demo visual del agente autónomo de triaje clínico.
"""

from __future__ import annotations

import time

from dotenv import load_dotenv

load_dotenv()

from enum import Enum

import streamlit as st

from app.streamlit_bridge import procesar_archivo, procesar_texto

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
        </style>
        """,
        unsafe_allow_html=True,
    )

def _inicializar_estado():
    if "cola_hitl" not in st.session_state:
        st.session_state.cola_hitl = []
    if "demos_ejecutadas" not in st.session_state:
        st.session_state.demos_ejecutadas = []  # más reciente primero

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

    # ── H5: Datos extraídos (una sola columna, H6 por grupo) ──
    st.markdown("##### 📋 Datos Extraídos")
    datos = resultado.get("datos_extraidos")
    if datos:
        paciente = datos.get("paciente") or {}
        medico = datos.get("medico_solicitante") or {}

        st.markdown("###### Paciente")
        st.write(f"👤 **Nombre:** {paciente.get('nombre', 'No identificado')}")
        if paciente.get("edad"):
            st.write(f"🎂 **Edad:** {paciente['edad']} años")

        st.markdown("###### Médico solicitante")
        st.write(f"🩺 **Nombre:** {medico.get('nombre', 'No identificado')}")
        if medico.get("matricula"):
            st.write(f"🪪 **Matrícula:** {medico['matricula']}")

        if datos.get("diagnostico_principal") or datos.get("cie10_sugerido"):
            st.markdown("###### Diagnóstico")
            if datos.get("diagnostico_principal"):
                st.write(f"🔬 **Principal:** {datos['diagnostico_principal']}")
            if datos.get("cie10_sugerido"):
                st.write(f"📌 **CIE-10:** {datos['cie10_sugerido']}")

        meds = datos.get("medicamentos") or []
        if meds:
            st.markdown("###### Medicamentos")
            st.markdown(
                "\n".join(
                    f"- 💊 {m.get('nombre') or ''} {m.get('dosis') or ''} {m.get('frecuencia') or ''}".rstrip()
                    for m in meds
                )
            )

        hallazgos = datos.get("hallazgos_criticos") or []
        if hallazgos:
            st.markdown("###### Hallazgos críticos")
            for h in hallazgos:
                st.error(f"🚨 {h}")

        faltantes = datos.get("campos_faltantes") or []
        if faltantes:
            st.markdown("###### Campos faltantes")
            st.warning(f"⚠️ {', '.join(faltantes)}")
    else:
        st.write("Sin datos extraídos.")

    st.divider()
    if anidado:
        # Streamlit no permite expanders dentro de expanders
        st.markdown("###### JSON completo")
        st.json(resultado, expanded=False)
    else:
        with st.expander("Ver JSON completo"):
            st.json(resultado)


MAX_DEMOS_VISIBLES = 3

def _ejecutar_caso(caso: dict) -> dict:
    """Ejecuta un caso demo, lo encola en HITL si corresponde y devuelve el resultado."""
    with st.spinner(f"Procesando {caso['id']} con Cohere..."):
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

def _tab_ingesta():
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

        archivo = None
        texto = ""
        btn = False

        if metodo == "📎 Subir PDF o Imagen":
            archivo = st.file_uploader(
                "Seleccioná el documento clínico:",
                type=["pdf", "png", "jpg", "jpeg"],
            )

            # El botón va ANTES de la previsualización
            btn = st.button(
                "🚀 Procesar con MediFlow",
                type="primary",
                use_container_width=True,
                key="btn_procesar_archivo",
            )

            if archivo:
                st.caption(f"`{archivo.name}` — {round(archivo.size / 1024, 1)} KB")
                if archivo.type.startswith("image/"):
                    st.image(archivo, width="stretch")

        else:
            texto = st.text_area(
                "Pegá o escribí el contenido del documento:",
                height=220,
                placeholder="Ingresá el informe, receta u orden médica...",
            )
            btn = st.button(
                "🚀 Procesar con MediFlow",
                type="primary",
                use_container_width=True,
                key="btn_procesar_texto",
            )

    with col_output:
        st.markdown("#### 2. Resultado del Agente")

        if not btn:
            st.info("El resultado aparecerá aquí luego de procesar.")
            return

        doc_id = f"DOC-{int(time.time())}"

        if metodo == "📎 Subir PDF o Imagen":
            if not archivo:
                st.warning("⚠️ Seleccioná un archivo primero.")
                return

            with st.spinner("Procesando con Cohere..."):
                resultado = procesar_archivo(
                    documento_id=doc_id,
                    canal=canal,
                    contenido=archivo.getvalue(),
                    mime=archivo.type,
                )
        else:
            if not texto.strip():
                st.warning("⚠️ Ingresá un texto primero.")
                return

            with st.spinner("Procesando con Cohere..."):
                resultado = procesar_texto(
                    documento_id=doc_id,
                    canal=canal,
                    texto=texto,
                )

        st.success("✅ Procesamiento completado.")

        # Determinar badge según resultado
        decision = resultado.get("decision") or {}
        clf = resultado.get("clasificacion") or {}
        destino = decision.get("destino", "")
        prioridad = clf.get("nivel_prioridad", "")

        if "Emergencia" in destino or prioridad == "Urgente":
            badge, badge_texto = "urgente", "🚨 PRIORIDAD CRÍTICA"
        elif decision.get("requiere_revision_humana"):
            badge, badge_texto = "hitl", "⚠️ RETENIDO EN AUDITORÍA"
        else:
            badge, badge_texto = "rutina", "🟢 FLUJO ESTÁNDAR"

        _mostrar_resultado(resultado, badge=badge, badge_texto=badge_texto)

        if decision.get("requiere_revision_humana"):
            st.session_state.cola_hitl.append(resultado)

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

    # Fuera de las columnas: todo lo siguiente ocupa el ancho completo
    if caso_a_ejecutar:
        resultado = _ejecutar_caso(caso_a_ejecutar)
        # Si el mismo demo ya estaba, se descarta el anterior y queda el nuevo
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
            # Solo el más reciente aparece desplegado; los demás, plegados
            with st.expander(f"{caso['label']} — {caso['badge_texto']}", expanded=(i == 0)):
                _mostrar_resultado(
                    demo["resultado"],
                    badge=caso["badge"],
                    badge_texto=caso["badge_texto"],
                    anidado=True,
                )

def _tab_hitl():
    st.subheader("Consola de Auditoría Human-in-the-Loop")
    st.markdown(
        "Documentos con **score de confianza bajo** o "
        "**campos críticos faltantes** retenidos para revisión."
    )

    cola = st.session_state.cola_hitl

    if not cola:
        st.success("🎉 Sin expedientes pendientes de auditoría.")
        return

    for idx, item in enumerate(cola):
        with st.container(border=True):
            clf = item.get("clasificacion") or {}
            datos = item.get("datos_extraidos") or {}
            decision = item.get("decision") or {}

            paciente = (datos.get("paciente") or {}).get("nombre", "No identificado")
            st.markdown(f"#### Expediente #{idx + 1} — {paciente}")

            col_info, col_accion = st.columns([2, 1])

            with col_info:
                st.write(f"🏷️ **Tipo:** {clf.get('tipo_documento', '—')}")
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
                    if st.button("✅ Aprobar", key=f"aprobar_{idx}"):
                        st.session_state.cola_hitl.pop(idx)
                        st.success("Expediente aprobado.")
                        st.rerun()
                with b2:
                    if st.button("❌ Rechazar", key=f"rechazar_{idx}"):
                        st.session_state.cola_hitl.pop(idx)
                        st.warning("Expediente rechazado.")
                        st.rerun()

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
