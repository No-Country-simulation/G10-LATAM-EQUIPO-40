import os
import json
import cohere
from dotenv import load_dotenv

load_dotenv()

PROMPT_SISTEMA = """
Eres MediFlow, un agente clínico inteligente especializado en triaje y enrutamiento médico automatizado.
Analiza con rigor el texto médico provisto y responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta:
{
    "paciente": "Nombre completo del paciente o 'No identificado'",
    "medico": "Nombre del médico tratante y registro/matrícula o 'No identificado'",
    "diagnostico_cie10": "Código CIE-10 oficial y descripción del diagnóstico",
    "sintomas": ["lista", "de", "síntomas", "y", "hallazgos"],
    "prioridad": "CRÍTICA" | "RUTINA" | "AMBIGUA",
    "score_confianza": 0.0 a 1.0,
    "destino_sugerido": "Guardia Central" | "Farmacia Ambulatoria" | "Auditoría HITL",
    "requiere_auditoria": true o false,
    "motivo_auditoria": "Explicación breve del motivo si requiere revisión humana"
}

REGLAS DE DECISIÓN CLÍNICA:
1. CRÍTICA: Riesgo vital (TEP, infarto, anafilaxia, shock). Destino: 'Guardia Central'. Score >= 0.90.
2. RUTINA: Controles médicos, recetas crónicas (diabetes, HTA). Destino: 'Farmacia Ambulatoria'. Score >= 0.88.
3. AMBIGUA / HITL: Si hay dudas diagnósticas, datos incompletos del paciente o falta de firma/médico, asigna score_confianza < 0.85, prioridad 'AMBIGUA', requiere_auditoria: true y destino: 'Auditoría HITL'.
"""

def analizar_triaje_cohere(texto_clinico: str) -> dict:
    """Envía el documento clínico al modelo de Cohere y retorna el JSON estructurado."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return {
            "error": "Variable COHERE_API_KEY no encontrada en el entorno o archivo .env",
            "requiere_auditoria": True,
            "motivo_auditoria": "Credenciales de Cohere faltantes."
        }

    try:
        co = cohere.ClientV2(api_key=api_key)
        
        respuesta = co.chat(
            model="command-r-08-2024",
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": f"Documento médico a procesar:\n{texto_clinico}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        contenido_texto = respuesta.message.content[0].text
        datos = json.loads(contenido_texto)

        # Regla de negocio de MediFlow: forzar HITL si la confianza es < 0.85 o faltan datos
        score = float(datos.get("score_confianza", 0.0))
        if score < 0.85 or not datos.get("paciente") or datos.get("paciente") == "No identificado":
            datos["requiere_auditoria"] = True
            datos["destino_sugerido"] = "Auditoría HITL"
            if not datos.get("motivo_auditoria"):
                datos["motivo_auditoria"] = "Confianza del modelo inferior a 85% o datos de filiación incompletos."

        return datos

    except Exception as e:
        return {
            "error": str(e),
            "requiere_auditoria": True,
            "motivo_auditoria": f"Excepción durante la inferencia con Cohere: {e}"
        }