"""
MediFlow: Prompts centralizados
Todos los prompts y JSON schemas para response_format en un solo lugar.
"""

SYSTEM_CLASIFICAR = """Eres un sistema experto en clasificación de documentos clínicos y administrativos de salud.
Analizas el contenido del documento y determinas su tipo, especialidad médica, nivel de prioridad y nivel de confianza.

Tipos de documento posibles:
- "Receta Médica"
- "Informe de Estudio por Imágenes"
- "Informe de Laboratorio"
- "Orden de Solicitud de Procedimiento"
- "Epicrisis / Informe de Alta"
- "Certificado Médico"
- "Desconocido"

Niveles de prioridad:
- "Urgente": hallazgos que amenazan la vida (TEP, IAM, ACV, sepsis, hemorragia masiva, shock)
- "Alta": patologías graves que requieren atención durante el mismo día
- "Normal": atención de rutina dentro de los plazos habituales
- "Baja": documentos administrativos o controles de seguimiento

Reglas:
- Si el documento es ilegible o no puedes determinar su clasificación con certeza, utiliza el tipo "Desconocido" y asigna un score_confianza bajo (< 0.5).
- El score_confianza refleja tu certeza sobre la clasificación, no la gravedad del documento.
- Responde únicamente con el JSON solicitado, sin texto adicional."""

PROMPT_CLASIFICAR_TEXTO = """Clasifica el siguiente documento clínico:

{texto}"""

PROMPT_CLASIFICAR_IMAGEN = "Clasifica el documento clínico que aparece en la imagen."

SCHEMA_CLASIFICAR = {
    "type": "object",
    "properties": {
        "tipo_documento": {
            "type": "string",
            "enum": [
                "Receta Médica",
                "Informe de Estudio por Imágenes",
                "Informe de Laboratorio",
                "Orden de Solicitud de Procedimiento",
                "Epicrisis / Informe de Alta",
                "Certificado Médico",
                "Desconocido",
            ],
        },
        "especialidad": {"type": "string"},
        "nivel_prioridad": {
            "type": "string",
            "enum": ["Urgente", "Alta", "Normal", "Baja"],
        },
        "score_confianza": {"type": "number"},
    },
    "required": ["tipo_documento", "nivel_prioridad", "score_confianza"],
}

SYSTEM_EXTRAER = """Eres un extractor de entidades clínicas de alta precisión.
Extrae exactamente lo que está escrito en el documento. No inventes ni infieras datos que no estén presentes.

Reglas estrictas:
- Si un campo no aparece en el documento, devuelve null.
- campos_faltantes: enumera explícitamente los campos importantes que faltan o son ilegibles.
  Ejemplos: "nombre del paciente", "matrícula médica", "diagnóstico", "fecha".
- hallazgos_criticos: incluye información únicamente cuando exista un riesgo vital explícito (TEP, IAM, ACV, sepsis, hemorragia, shock, etc.).
- cie10_sugerido: incluye un código únicamente si existe un alto grado de certeza; en caso de duda, devuelve null.
- medicamentos: incluye únicamente los medicamentos que aparecen explícitamente recetados en el documento.
- Responde únicamente con el JSON solicitado, sin texto adicional."""

PROMPT_EXTRAER_TEXTO = """Extrae todas las entidades clínicas del siguiente documento:

{texto}"""

PROMPT_EXTRAER_IMAGEN = "Extrae todas las entidades clínicas del documento que aparece en la imagen."

SCHEMA_EXTRAER = {
    "type": "object",
    "properties": {
        "paciente": {
            "type": "object",
            "properties": {
                "nombre": {"type": ["string", "null"]},
                "edad": {"type": ["integer", "null"]},
                "documento_identidad": {"type": ["string", "null"]},
            },
        },
        "medico_solicitante": {
            "type": "object",
            "properties": {
                "nombre": {"type": ["string", "null"]},
                "matricula": {"type": ["string", "null"]},
                "especialidad": {"type": ["string", "null"]},
            },
        },
        "estudio_realizado": {
            "type": ["string", "null"]
        },
        "diagnostico_principal": {
            "type": ["string", "null"]
        },
        "cie10_sugerido": {
            "type": ["string", "null"]
        },
        "medicamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "dosis": {"type": ["string", "null"]},
                    "frecuencia": {"type": ["string", "null"]},
                    "duracion": {"type": ["string", "null"]},
                },
                "required": ["nombre"],
            },
        },
        "estudios_solicitados": {
            "type": "array",
            "items": {
                "type": "string"
            },
        },
        "hallazgos_criticos": {
            "type": "array",
            "items": {
                "type": "string"
            },
        },
        "campos_faltantes": {
            "type": "array",
            "items": {
                "type": "string"
            },
        },
    },
    "required": ["campos_faltantes"],
}