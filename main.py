"""MediFlow: Agente Autónomo de Triaje Clínico Multimodal
Hackathon ONE Grupo 10 (Oracle Next Education & Alura)
"""

import os
import json
import tempfile

try:
    from google.colab import userdata
    COHERE_API_KEY = userdata.get('COHERE_API_KEY')
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')

if not COHERE_API_KEY:
    raise ValueError('Debes configurar COHERE_API_KEY en .env o Secrets de Colab')

# Ingesta
from app.ingest.pdf_loader import procesar_pdf
from app.ingest.image_loader import imagen_desde_bytes

# LangChain + Cohere
from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage

llm = ChatCohere(
    cohere_api_key=COHERE_API_KEY,
    model="command-a-vision-07-2025"
)

# Schema JSON (contrato de salida) 
CLINICAL_SCHEMA = {
    "title": "DiagnosticoTriajeClinico",
    "type": "object",
    "properties": {
        "clasificacion": {
            "type": "object",
            "properties": {
                "tipo_documento":                {"type": "string"},
                "especialidad":                  {"type": "string"},
                "nivel_prioridad":               {"type": "string", "enum": ["Urgente", "Moderada", "Rutina"]},
                "score_confianza_clasificacion": {"type": "number"}
            },
            "required": ["tipo_documento", "especialidad", "nivel_prioridad", "score_confianza_clasificacion"]
        },
        "datos_extraidos": {
            "type": "object",
            "properties": {
                "paciente": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "edad":   {"type": "integer"}
                    },
                    "required": ["nombre"]
                },
                "medico_solicitante": {
                    "type": "object",
                    "properties": {
                        "nombre":    {"type": "string"},
                        "matricula": {"type": "string"}
                    },
                    "required": ["nombre"]
                },
                "estudio_realizado":    {"type": "string"},
                "diagnostico_principal":{"type": "string"},
                "cie10_sugerido":       {"type": "string"}
            },
            "required": ["paciente", "diagnostico_principal"]
        }
    },
    "required": ["clasificacion", "datos_extraidos"]
}

# Helpers
def parsear_json_seguro(texto: str) -> dict:
    """Extrae el primer objeto JSON del texto e ignora cualquier dato extra."""
    texto = texto.strip()
    inicio = texto.find("{")
    if inicio == -1:
        raise ValueError(f"La respuesta no contiene JSON:\n{texto}")
    obj, _ = json.JSONDecoder().raw_decode(texto[inicio:])
    return obj


PROMPT_EXTRACCION = (
    "Eres MediFlow, agente de triaje clínico. "
    "Extrae los datos clínicos siguiendo estrictamente el esquema JSON.\n"
    "Reglas:\n"
    "1. Si faltan datos clave o el documento es borroso/ilegible, "
    "pon 'score_confianza_clasificacion' < 0.85.\n"
    "2. Si hay riesgo vital (TEP, IAM, ACV, shock), 'nivel_prioridad' = 'Urgente'.\n"
    "3. Sugiere código CIE-10 acorde al diagnóstico.\n"
    "4. Si un campo es ilegible usa 'ilegible', nunca inventes datos.\n"
    "5. Responde SOLO con el objeto JSON, sin texto adicional.\n"
)

# Motor de inferencia
def extraer_datos_clinicos(texto: str = None, data_url: str = None) -> dict:
    """
    Extrae entidades clínicas desde texto o imagen (data URL).
    Siempre usa command-a-vision-07-2025.
    """
    contenido = [{"type": "text", "text": PROMPT_EXTRACCION}]

    if texto:
        contenido.append({"type": "text", "text": f"Documento a analizar:\n{texto}"})

    if data_url:
        contenido.append({"type": "image_url", "image_url": {"url": data_url}})

    respuesta = llm.invoke(
        [HumanMessage(content=contenido)],
        response_format={"type": "json_object", "schema": CLINICAL_SCHEMA}
    )
    return parsear_json_seguro(respuesta.content)


# Grafo de decisión condicional
def nodo_enrutamiento_condicional(documento_id: str, extraccion_raw: dict) -> dict:
    """Evalúa reglas condicionales: HITL, Urgencia o Rutina."""
    clasif    = extraccion_raw.get("clasificacion", {})
    score     = float(clasif.get("score_confianza_clasificacion", 0.5))
    prioridad = clasif.get("nivel_prioridad", "Rutina")
    tipo_doc  = clasif.get("tipo_documento", "").lower()

    if score < 0.85:
        destino       = "Cola_Auditoria_Humana"
        requiere_hitl = True
        justificacion = f"Score insuficiente ({score:.2f}). Requiere revisión manual."
        canal         = "Alerta_Auditoria_Medica"
        mensaje       = f"AUDITORÍA: Documento {documento_id} derivado a revisión clínica."
        carpeta_oci   = "auditoria_humana"
        status        = "requiere_auditoria"

    elif prioridad == "Urgente":
        destino       = "Cola_Emergencia_Medica"
        requiere_hitl = False
        justificacion = "Hallazgo clínico crítico con riesgo vital identificado."
        canal         = "Alerta_Guardia_Medica"
        mensaje       = f"ALERTA URGENTE: Documento crítico {documento_id}."
        carpeta_oci   = "procesados/urgentes"
        status        = "procesado"

    else:
        requiere_hitl = False
        canal         = None
        mensaje       = None
        carpeta_oci   = "procesados/rutina"
        status        = "procesado"
        if "receta" in tipo_doc:
            destino       = "Farmacia_Hospitalaria"
            justificacion = "Prescripción ambulatoria autorizada para dispensación."
        else:
            destino       = "Historia_Clinica_Electronica"
            justificacion = "Documento de rutina archivado en historia clínica."

    return {
        "status":        status,
        "documento_id":  documento_id,
        "clasificacion": clasif,
        "datos_extraidos": extraccion_raw.get("datos_extraidos", {}),
        "decision_enrutamiento": {
            "destino_principal":       destino,
            "requiere_auditoria_humana": requiere_hitl,
            "justificacion_enrutamiento": justificacion,
            "notificacion_generada":   {"canal": canal, "mensaje": mensaje} if canal else None
        },
        "_carpeta_oci": carpeta_oci
    }


# Persistencia OCI 
def persistir_en_oci(resultado_triaje: dict) -> dict:
    """Persiste el JSON en OCI Object Storage o simula localmente."""
    doc_id      = resultado_triaje["documento_id"]
    carpeta     = resultado_triaje.pop("_carpeta_oci", "procesados/rutina")
    ruta_objeto = f"{carpeta}/{doc_id}.json"
    bucket_name = "mediflow-documentos-clinicos"

    try:
        import oci
        config = oci.config.from_file(os.getenv("OCI_CONFIG_PATH", "~/.oci/config"))
        client = oci.object_storage.ObjectStorageClient(config)
        client.put_object(
            namespace_name=os.getenv("OCI_NAMESPACE", "mediflow_ns"),
            bucket_name=bucket_name,
            object_name=ruta_objeto,
            put_object_body=json.dumps(resultado_triaje, indent=2, ensure_ascii=False).encode("utf-8"),
            content_type="application/json"
        )
        status_backup = "exito"
    except Exception:
        os.makedirs(f"oci_storage_local/{carpeta}", exist_ok=True)
        with open(f"oci_storage_local/{ruta_objeto}", "w", encoding="utf-8") as f:
            json.dump(resultado_triaje, f, indent=2, ensure_ascii=False)
        status_backup = "simulado_local"

    resultado_triaje["almacenamiento_oci"] = {
        "bucket":        bucket_name,
        "ruta_objeto":   ruta_objeto,
        "status_backup": status_backup
    }
    return resultado_triaje


# Pipeline completo 
def procesar_triaje_mediflow(doc_id: str, texto: str = None, data_url: str = None) -> dict:
    """Ejecuta el ciclo completo: extracción → decisión → persistencia."""
    raw       = extraer_datos_clinicos(texto=texto, data_url=data_url)
    triaje    = nodo_enrutamiento_condicional(doc_id, raw)
    resultado = persistir_en_oci(triaje)
    return resultado


# Puente con los loaders
def procesar_archivo_mediflow(doc_id: str, archivo_bytes: bytes, tipo_mime: str) -> dict:
    """
    Puente entre los loaders de ingestión y el pipeline.
    Recibe bytes del archivo subido desde app.py (Streamlit).
    """
    if tipo_mime == "application/pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(archivo_bytes)
            tmp_path = tmp.name

        resultado_ingest = procesar_pdf(tmp_path)
        os.unlink(tmp_path)

        modo = resultado_ingest["modo"]

        if modo == "texto":
            # PDF digital con texto extraído → modelo texto
            return procesar_triaje_mediflow(doc_id, texto=resultado_ingest["texto"])

        elif modo in ("imagen", "mixto"):
            # PDF escaneado → usar primera página como imagen
            imagenes = resultado_ingest["imagenes_data_url"]
            if imagenes:
                return procesar_triaje_mediflow(doc_id, data_url=imagenes[0])
            # mixto con texto suficiente como fallback
            return procesar_triaje_mediflow(doc_id, texto=resultado_ingest["texto"])

        else:
            # modo "error"
            return {
                "status": "requiere_auditoria",
                "documento_id": doc_id,
                "decision_enrutamiento": {
                    "destino_principal": "Cola_Auditoria_Humana",
                    "requiere_auditoria_humana": True,
                    "justificacion_enrutamiento": resultado_ingest["texto"],  # mensaje de error
                }
            }

    elif tipo_mime.startswith("image/"):
        data_url = imagen_desde_bytes(archivo_bytes, tipo_mime)
        return procesar_triaje_mediflow(doc_id, data_url=data_url)

    else:
        return {
            "status": "error",
            "documento_id": doc_id,
            "error_detalle": f"Tipo de archivo no soportado: {tipo_mime}"
        }


# Demo CLI
if __name__ == "__main__":
    casos_prueba = [
        {
            "id": "DOC-CLIN-2026-8942",
            "descripcion": "CASO 1: Urgencia Médica (TEP Agudo)",
            "texto": (
                "HOSPITAL SANTA LUCIA. INFORME RADIOLOGICO. Paciente: Carlos Eduardo Mendes, 52 años. "
                "Medico Solicitante: Dra. Renata Silveira MP 145892. Estudio: Tomografia de Torax con contraste. "
                "Indicacion: Sospecha de embolia pulmonar aguda, disnea subita. Hallazgos: Defecto de llenado "
                "en arteria pulmonar principal derecha compatible con TEP agudo. CONCLUSION: Tromboembolismo "
                "Pulmonar Agudo. Se sugiere correlacion urgente."
            )
        },
        {
            "id": "DOC-CLIN-2026-3021",
            "descripcion": "CASO 2: Rutina (Receta ambulatoria)",
            "texto": (
                "CENTRO DE SALUD FAMILIAR. RECETA MEDICA. Paciente: Maria Jose Fernandez, 45 años. "
                "Medico: Dr. Andres Morales MP 77210. Diagnostico: Hipertension arterial esencial. "
                "Prescripcion: Losartan 50mg. Tomar 1 comprimido cada 12 horas por 60 dias."
            )
        },
        {
            "id": "DOC-CLIN-2026-1049",
            "descripcion": "CASO 3: Ambiguo (HITL)",
            "texto": (
                "NOTA CLINICA MANUSCRITA ILEGIBLE: Pcte: ...berto Gomez? Edad: sin datos. "
                "Rct: Tomar comp... [dosis ilegible]. Dr. [firma no identificable, sin matricula]."
            )
        }
    ]

    print("=== DEMO MEDIFLOW ===\n")
    for c in casos_prueba:
        print(f"→ {c['descripcion']}")
        res = procesar_triaje_mediflow(c["id"], texto=c["texto"])
        print(json.dumps(res, indent=2, ensure_ascii=False))
        print("-" * 80)