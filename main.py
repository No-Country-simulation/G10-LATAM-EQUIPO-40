""" MediFlow: Agente Autónomo de Triaje Clínico Multimodal
**Hackathon ONE Grupo 10 (Oracle Next Education & Alura)**

Pipeline completo de extracción clínica con **Cohere Multimodal**, grafo de decisión 
condicional, derivación a **Human-in-the-Loop (HITL)** y persistencia segregada en 
**OCI Object Storage (Always Free)**.
"""

# 1. Instalación de dependencias (con uv instalado, ejecutar **uv sync**

# 2. Configuración de API Keys (Soporte dual: Colab y Local .env)
import os

try:
    from google.colab import userdata
    COHERE_API_KEY = userdata.get('COHERE_API_KEY')
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')

if not COHERE_API_KEY:
    raise ValueError('Debes configurar COHERE_API_KEY en los Secrets de Colab o en tu archivo .env')

# 3. Helpers de Visión Multimodal y Lectura de Archivos
import base64
import mimetypes

def to_data_url(path: str) -> str:
    """Convierte una imagen local a Data URL Base64 para modelos de visión."""
    mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
    with open(path, 'rb') as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"

# 4. Contrato de Datos Clínicos y Esquema JSON (Requisito MVP Hackathon)
CLINICAL_SCHEMA = {
    "title": "DiagnosticoTriajeClinico",
    "type": "object",
    "properties": {
        "clasificacion": {
            "type": "object",
            "properties": {
                "tipo_documento": {"type": "string"},
                "especialidad": {"type": "string"},
                "nivel_prioridad": {"type": "string", "enum": ["Urgente", "Moderada", "Rutina"]},
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
                        "edad": {"type": "integer"}
                    },
                    "required": ["nombre"]
                },
                "medico_solicitante": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "matricula": {"type": "string"}
                    },
                    "required": ["nombre"]
                },
                "estudio_realizado": {"type": "string"},
                "diagnostico_principal": {"type": "string"},
                "cie10_sugerido": {"type": "string"}
            },
            "required": ["paciente", "diagnostico_principal"]
        }
    },
    "required": ["clasificacion", "datos_extraidos"]
}

# 4.5 Parser salida

def parsear_json_seguro(texto: str) -> dict:
    """Extrae el primer objeto JSON del texto e ignora cualquier dato extra."""
    texto = texto.strip()
    inicio = texto.find("{")
    if inicio == -1:
        raise ValueError(f"La respuesta no contiene JSON:\n{texto}")
    obj, _ = json.JSONDecoder().raw_decode(texto[inicio:])
    return obj

# 5. Motor de Inferencia Multimodal (Cohere Command-A-Vision)
from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage
import json

llm = ChatCohere(
    cohere_api_key=COHERE_API_KEY,
    model="command-a-vision-07-2025"
)

def extraer_datos_clinicos(texto: str = None, ruta_imagen: str = None) -> dict:
    """Extrae entidades clínicas tanto desde texto estructurado como desde imágenes escaneadas."""
    contenido_mensaje = [
        {
            "type": "text",
            "text": (
                "Eres MediFlow, agente de triaje clínico. Extrae los datos clínicos siguiendo estrictamente el esquema JSON.\n"
                "Reglas:\n"
                "1. Si faltan datos clave o el documento es borroso/ilegible, pon 'score_confianza_clasificacion' < 0.85.\n"
                "2. Si el cuadro clínico presenta riesgo vital inminente (TEP, IAM, ACV, shock), 'nivel_prioridad' debe ser 'Urgente'.\n"
                "3. Sugiere el código CIE-10 acorde al diagnóstico.\n"
                "4. Si un campo obligatorio es ilegible o no aparece, usa el valor 'ilegible' (nunca inventes datos) y baja el score de confianza.\n"
                "5. Responde SOLO con el objeto JSON, sin texto adicional ni explicaciones.\n"
            )
        }
    ]

    if texto:
        contenido_mensaje.append({"type": "text", "text": f"Documento a analizar:\n{texto}"})
    if ruta_imagen:
        contenido_mensaje.append({"type": "image_url", "image_url": {"url": to_data_url(ruta_imagen)}})

    mensaje = HumanMessage(content=contenido_mensaje)
    respuesta = llm.invoke([mensaje], response_format={"type": "json_object", "schema": CLINICAL_SCHEMA})
    print(respuesta.content)  # temporal: para ver qué había después del JSON
    return parsear_json_seguro(respuesta.content)

# 6. Grafo de Decisión Condicional y Bifurcación
def nodo_enrutamiento_condicional(documento_id: str, extraccion_raw: dict) -> dict:
    """Evalúa reglas condicionales: HITL (ambigüedad), Urgencia (Guardia) o Rutina."""
    clasif = extraccion_raw.get("clasificacion", {})
    score = float(clasif.get("score_confianza_clasificacion", 0.5))
    prioridad = clasif.get("nivel_prioridad", "Rutina")
    tipo_doc = clasif.get("tipo_documento", "").lower()

    # Bifurcación 1: Ambigüedad o Ilegibilidad -> Auditoría Humana (HITL)
    if score < 0.85:
        destino = "Cola_Auditoria_Humana"
        requiere_hitl = True
        justificacion = f"Score de certeza insuficiente ({score:.2f}). Requiere revisión manual por posibles datos truncados o borrosos."
        canal = "Alerta_Auditoria_Medica"
        mensaje = f"AUDITORÍA: Documento {documento_id} derivado a revisión clínica manual."
        carpeta_oci = "auditoria_humana"
        status = "requiere_auditoria"

    # Bifurcación 2: Urgencia Médica Crítica -> Cola de Emergencias
    elif prioridad == "Urgente":
        destino = "Cola_Emergencia_Medica"
        requiere_hitl = False
        justificacion = "Hallazgo clínico crítico identificado con potencial riesgo vital."
        canal = "Alerta_Guardia_Medica"
        mensaje = f"ALERTA URGENTE: Notificación crítica inmediata para el documento {documento_id}."
        carpeta_oci = "procesados/urgentes"
        status = "procesado"

    # Bifurcación 3: Rutina Estándar
    else:
        requiere_hitl = False
        canal = None
        mensaje = None
        carpeta_oci = "procesados/rutina"
        status = "procesado"
        if "receta" in tipo_doc:
            destino = "Farmacia_Hospitalaria"
            justificacion = "Prescripción ambulatoria autorizada para dispensación en farmacia."
        else:
            destino = "Historia_Clinica_Electronica"
            justificacion = "Informe de estudio de rutina archivado en la ficha clínica del paciente."

    return {
        "status": status,
        "documento_id": documento_id,
        "clasificacion": clasif,
        "datos_extraidos": extraccion_raw.get("datos_extraidos", {}),
        "decision_enrutamiento": {
            "destino_principal": destino,
            "requiere_auditoria_humana": requiere_hitl,
            "justificacion_enrutamiento": justificacion,
            "notificacion_generada": {"canal": canal, "mensaje": mensaje} if canal else None
        },
        "_carpeta_oci": carpeta_oci
    }

# 7. Módulo de Persistencia en OCI Object Storage (Always Free)
def persistir_en_oci(resultado_triaje: dict) -> dict:
    """Persiste el JSON en el bucket Always Free segregado por carpetas de estado."""
    doc_id = resultado_triaje["documento_id"]
    carpeta = resultado_triaje.pop("_carpeta_oci", "procesados/rutina")
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
            put_object_body=json.dumps(resultado_triaje, indent=2, ensure_ascii=False).encode('utf-8'),
            content_type="application/json"
        )
        status_backup = "exito"
    except Exception:
        # Simulación local transparente para pruebas sin credenciales cargadas
        os.makedirs(f"oci_storage_local/{carpeta}", exist_ok=True)
        with open(f"oci_storage_local/{ruta_objeto}", "w", encoding="utf-8") as f:
            json.dump(resultado_triaje, f, indent=2, ensure_ascii=False)
        status_backup = "simulado_local_always_free"

    resultado_triaje["almacenamiento_oci"] = {
        "bucket": bucket_name,
        "ruta_objeto": ruta_objeto,
        "status_backup": status_backup
    }
    return resultado_triaje

# 8. Pipeline Integral MediFlow
def procesar_triaje_mediflow(doc_id: str, texto: str = None, ruta_imagen: str = None) -> dict:
    """Ejecuta el ciclo de vida completo del documento clínico."""
    # 1. Extracción con Cohere
    raw = extraer_datos_clinicos(texto=texto, ruta_imagen=ruta_imagen)
    # 2. Grafo condicional de decisión
    triaje = nodo_enrutamiento_condicional(doc_id, raw)
    # 3. Persistencia en OCI Always Free
    resultado_final = persistir_en_oci(triaje)
    return resultado_final

# 9. Demostración de los 3 Casos de Prueba Obligatorios del Hackathon

casos_prueba = [
    {
        "id": "DOC-CLIN-2026-8942",
        "descripcion": "CASO 1: Urgencia Médica (Hallazgo crítico - TEP Agudo)",
        "texto": (
            "HOSPITAL SANTA LUCIA. INFORME RADIOLOGICO. Paciente: Carlos Eduardo Mendes, 52 años. "
            "Medico Solicitante: Dra. Renata Silveira MP 145892. Estudio: Tomografia de Torax con contraste. "
            "Indicacion: Sospecha de embolia pulmonar aguda, disnea subita. Hallazgos: Defecto de llenado en arteria "
            "pulmonar principal derecha compatible con TEP agudo. CONCLUSION: Tromboembolismo Pulmonar Agudo. Se sugiere correlacion urgente."
        )
    },
    {
        "id": "DOC-CLIN-2026-3021",
        "descripcion": "CASO 2: Rutina / Aprobado (Receta ambulatoria estándar)",
        "texto": (
            "CENTRO DE SALUD FAMILIAR. RECETA MEDICA. Paciente: Maria Jose Fernandez, 45 años. "
            "Medico: Dr. Andres Morales MP 77210. Diagnostico: Hipertension arterial esencial. "
            "Prescripcion: Losartan 50 mg comprimidos. Tomar 1 comprimido cada 12 horas por 60 dias. Control medico rutinario en 2 meses."
        )
    },
    {
        "id": "DOC-CLIN-2026-1049",
        "descripcion": "CASO 3: Ambiguo / Faltante (Texto manuscrito borroso para HITL)",
        "texto": (
            "NOTA CLINICA MANUSCRITA ILEGIBLE: Pcte: ...berto Gomez? Edad: sin datos claros. "
            "Rct: Tomar comp... [dosis manchada, ilegible] cada... Dr. [firma no identificable, sin matricula medica visible]."
        )
    }
]

print("=== EJECUTANDO DEMOSTRACIÓN DE EVALUACIÓN MEDIFLOW ===\n")
for c in casos_prueba:
    print(f"-> {c['descripcion']}")
    res = procesar_triaje_mediflow(c['id'], texto=c['texto'])
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("-" * 80)