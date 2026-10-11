"""
MediFlow: Prompts centralizados
Todos los prompts y JSON schemas para response_format en un solo lugar.
"""

SYSTEM_CLASIFICAR = """Eres un sistema experto en clasificación de documentos clínicos y administrativos de salud.
Analizas el contenido del documento y determinas su tipo, especialidad médica, nivel de prioridad y nivel de confianza.

Tipos de documento posibles (responde con el CÓDIGO exacto en tipo_documento):
- RECETA_MEDICA: receta médica
- INFORME_IMAGENES: informe de estudio por imágenes (radiografía, tomografía, ecografía, resonancia)
- INFORME_LABORATORIO: informe de laboratorio
- ORDEN_PROCEDIMIENTO: orden de solicitud de procedimiento
- EPICRISIS: epicrisis o informe de alta
- CERTIFICADO_MEDICO: certificado médico
- DESCONOCIDO: ilegible o no clasificable

Niveles de prioridad:
- "Urgente": hallazgos que amenazan la vida (TEP, IAM, ACV, sepsis, hemorragia masiva, shock)
- "Alta": patologías graves que requieren atención durante el mismo día
- "Normal": atención de rutina dentro de los plazos habituales
- "Baja": documentos administrativos o controles de seguimiento

La prioridad depende del CONTENIDO CLÍNICO del documento (hallazgos, conclusión, indicación), NO de su tipo. Un informe de imágenes, de laboratorio o una epicrisis pueden ser Urgente si describen un riesgo vital. Si en cualquier parte del documento hay un hallazgo que amenaza la vida, la prioridad es "Urgente" aunque el documento sea un informe de rutina.

Ejemplos de prioridad:
- Informe de Estudio por Imágenes que concluye "defecto de llenado en arteria pulmonar compatible con embolia pulmonar aguda, correlación urgente" -> tipo INFORME_IMAGENES, prioridad "Urgente" (el tipo de documento es habitual, pero el hallazgo amenaza la vida).
- Informe de Estudio por Imágenes que describe "consolidación lobar compatible con neumonía, paciente febril con saturación 92%" -> "Alta" (grave, requiere atención el mismo día, sin riesgo vital inmediato).
- Informe de Laboratorio con "hemograma y glucemia dentro de valores normales, control anual" -> "Normal".

Reglas:
- Si el documento es ilegible o no puedes determinar su clasificación con certeza, utiliza el tipo DESCONOCIDO y asigna un score_confianza bajo (< 0.5).
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
                "RECETA_MEDICA",
                "INFORME_IMAGENES",
                "INFORME_LABORATORIO",
                "ORDEN_PROCEDIMIENTO",
                "EPICRISIS",
                "CERTIFICADO_MEDICO",
                "DESCONOCIDO",
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

SYSTEM_EXTRAER = """Eres un extractor de entidades clínicas. Tu única tarea es leer el documento y completar el JSON con los datos que encuentres.

REGLAS ESTRICTAS:
- Extrae EXACTAMENTE lo que está escrito, sin inventar.
- Si un dato NO aparece o es ilegible, OMITE ese campo. Nunca escribas "null", "N/A", "???" ni texto de relleno.
- nombre del paciente: busca "Paciente:", nombres propios, "Sr.", "Sra.".
- nombre del médico: busca "Dr.", "Dra.", "Médico:", "Solicitante:".
- matrícula: busca "MP", "Reg", "Matrícula", número junto al nombre del médico.
- diagnostico_principal: busca "Diagnóstico:", "Dx:", "Conclusión:", "compatible con". En informes de imágenes o de laboratorio, toma el diagnóstico de la CONCLUSIÓN. Si es dudoso o ilegible, omítelo.
- medicamentos: nombres de fármacos con dosis.
- estudios_solicitados: solo si el documento SOLICITA estudios (órdenes). No repitas aquí el estudio realizado.
- hallazgos_criticos: SOLO si hay riesgo vital explícito (TEP, IAM, ACV, sepsis, hemorragia, shock). Si no hay, devuelve una lista vacía [].
- campos_faltantes: solo campos importantes que NO encontraste Y que corresponden a este tipo de documento (por ejemplo, "medicamentos" solo aplica a recetas; en un informe de imágenes no lo listes).
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
