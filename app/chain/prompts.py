"""
MediFlow: Prompts centralizados
Todos los prompts y JSON schemas para response_format en un solo lugar.
"""

SYSTEM_CLASIFICAR = """Eres un sistema experto en clasificación de documentos clínicos y administrativos de salud.
Analizas el contenido del documento y determinas su tipo, especialidad médica, nivel de prioridad y nivel de confianza.

Tipos de documento posibles (responde con el CÓDIGO exacto en tipo_documento):
- RECETA_MEDICA: receta médica
- INFORME_IMAGENES: el documento ES el informe de un estudio de imágenes (radiografía, tomografía, ecografía, resonancia). Si solo menciona una imagen dentro de un resumen de hospitalización, no lo es
- INFORME_LABORATORIO: informe de laboratorio
- ORDEN_PROCEDIMIENTO: orden de solicitud de procedimiento
- EPICRISIS: epicrisis o informe de alta: resumen de una hospitalización (títulos como "Epicrisis", "Resumen de egreso", "Diagnóstico de egreso", fechas de ingreso y egreso, evolución por días), aunque mencione estudios y medicamentos
- CERTIFICADO_MEDICO: certificado médico
- DESCONOCIDO: ilegible o no clasificable

Niveles de prioridad:
- "Urgente": hallazgos que amenazan la vida (TEP, IAM, ACV, sepsis, hemorragia masiva, shock, neumotórax a tensión) o resultados de laboratorio que el propio documento marca como CRÍTICOS. Un diagnóstico descartado ("se descarta TEP") no cuenta
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
- Clasifica por la naturaleza del documento completo (su título y estructura), no por los estudios o medicamentos que mencione.
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
                "Evaluación de Triaje / Urgencias",
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
- Extrae EXACTAMENTE lo que está escrito. NUNCA inventes datos ni uses valores de ejemplo (como 123456789 o 12345).
- Si un dato NO aparece o es ilegible, OMITE ese campo. Nunca escribas "null", "N/A", "???" ni texto de relleno.
- Lee todas las páginas: el médico, su matrícula y el diagnóstico de egreso suelen estar en la última.
- nombre del paciente: busca "Paciente:", nombres propios, "Sr.", "Sra.".
- edad_paciente: extrae la edad exactamente como aparece en el documento, incluyendo su unidad. Usa formatos como "45 años", "8 meses" o "15 días". No conviertas meses o días a años. Si solo aparece el número sin unidad, conserva el número sin inventar la unidad. Si la edad no aparece o es ilegible, omite el campo.
- nombre del médico: busca "Dr.", "Dra.", "Médico:", "Solicitante:". Matrícula: "MP", "Reg", "Matrícula", junto al nombre o sello del médico.
- diagnostico_principal: UNA línea breve (máximo 15 palabras) con la entidad clínica, no el párrafo completo. Búscala en "Diagnóstico:", "Dx:", "Conclusión:", "Diagnóstico de egreso", "compatible con". Si es dudoso o ilegible, omítelo. La indicación clínica de una orden no es un diagnóstico.
- estudio_realizado: solo si el documento reporta el resultado de un estudio ya hecho (informe de imágenes o de laboratorio). En recetas, órdenes o epicrisis no lo completes.
- estudios_solicitados: el procedimiento o estudio pedido en órdenes y solicitudes (por ejemplo, "Colonoscopia"). No repitas aquí un estudio realizado.
- medicamentos: nombre, dosis (por ejemplo "10 mg"), frecuencia (por ejemplo "cada 12 horas") y duración, por separado.
- hallazgos_criticos: solo hallazgos que el documento AFIRME y que impliquen riesgo vital inmediato (TEP, IAM, ACV, sepsis, hemorragia masiva, shock, neumotórax a tensión), o resultados que el propio documento marque como CRÍTICOS (por ejemplo, un valor de laboratorio señalado "CRÍTICO"). Cada uno en menos de 12 palabras. NO incluyas diagnósticos descartados ("se descarta X"), valores normales o levemente alterados, fracturas u otros hallazgos no vitales, ni notas administrativas como "se comunicó por teléfono". Si no hay, devuelve una lista vacía [].
- campos_faltantes: solo campos importantes que NO encontraste Y que corresponden a este tipo de documento.
- Responde ÚNICAMENTE con el JSON, sin texto adicional."""

PROMPT_EXTRAER_TEXTO = """Extrae todas las entidades clínicas del siguiente documento:

{texto}"""

PROMPT_EXTRAER_IMAGEN = "Extrae todas las entidades clínicas del documento que aparece en la imagen."

SCHEMA_EXTRAER = {
    "type": "object",
    "properties": {
        "nombre_paciente":      {"type": "string"},
        "edad_paciente":        {"type": "string"},
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
