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

SYSTEM_EXTRAER = """Eres un extractor de entidades clínicas. Tu única tarea es leer el documento y completar el JSON con TODOS los datos que encuentres.

REGLAS ESTRICTAS:
- Extrae EXACTAMENTE lo que está escrito, sin inventar.
- Si el dato está en el documento → ponlo en el campo correspondiente.
- Si el dato NO está → null.
- nombre del paciente: busca "Paciente:", nombres propios, "Sr.", "Sra."
- nombre del médico: busca "Dr.", "Dra.", "Médico:", "Solicitante:"
- matrícula: busca "MP", "Reg", "Matrícula", número junto al nombre del médico.
- diagnóstico: busca "Diagnóstico:", "Dx:", "Conclusión:", "compatible con".
- medicamentos: busca nombres de fármacos con dosis.
- hallazgos_criticos: SOLO si hay riesgo vital explícito (TEP, IAM, ACV, sepsis, hemorragia, shock).
- campos_faltantes: lista los campos importantes que NO encontraste.
- Responde ÚNICAMENTE con el JSON, sin texto adicional."""

PROMPT_EXTRAER_TEXTO = """Extrae todas las entidades clínicas del siguiente documento:

{texto}"""

PROMPT_EXTRAER_IMAGEN = "Extrae todas las entidades clínicas del documento que aparece en la imagen."

SCHEMA_EXTRAER = {
    "type": "object",
    "properties": {
        "nombre_paciente":      {"type": "string"},
        "edad_paciente":        {"type": "integer"},
        "documento_paciente":   {"type": "string"},
        "nombre_medico":        {"type": "string"},
        "matricula_medico":     {"type": "string"},
        "especialidad_medico":  {"type": "string"},
        "estudio_realizado":    {"type": "string"},
        "diagnostico_principal":{"type": "string"},
        "cie10_sugerido":       {"type": "string"},
        "medicamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre":    {"type": "string"},
                    "dosis":     {"type": "string"},
                    "frecuencia":{"type": "string"},
                    "duracion":  {"type": "string"},
                },
                "required": ["nombre"],
            },
        },
        "estudios_solicitados": {"type": "array", "items": {"type": "string"}},
        "hallazgos_criticos":   {"type": "array", "items": {"type": "string"}},
        "campos_faltantes":     {"type": "array", "items": {"type": "string"}},
    },
    "required": ["campos_faltantes"],
}