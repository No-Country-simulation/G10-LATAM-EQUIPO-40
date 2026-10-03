"""
agent_vision.py — Agente MediFlow de triaje clínico sobre imágenes (Cohere Vision).

Recibe una o varias imágenes (data URLs) de un documento médico —una foto, un
escaneo o las páginas de un PDF escaneado— y devuelve el mismo JSON de triaje
que agent_cohere.analizar_triaje_cohere.

Requiere COHERE_API_KEY en el entorno o en un archivo .env.
"""

import os
import json

import cohere
from dotenv import load_dotenv

from agent_cohere import PROMPT_SISTEMA, aplicar_reglas_hitl

load_dotenv()

MODELO_VISION = "command-a-vision-07-2025"
MAX_IMAGENES = 20  # límite de imágenes por request del modelo de visión

INSTRUCCION_USUARIO = (
    "Documento médico a procesar, adjunto como imagen(es) en orden de página. "
    "Lee todo el texto visible (incluyendo sellos, firmas y campos manuscritos) "
    "y aplica las reglas de decisión. Si algo es ilegible o falta, reduce la "
    "confianza y explícalo en 'motivo_auditoria'."
)


def _parsear_json(texto: str) -> dict:
    """Parsea el JSON de la respuesta, tolerando bloques ```json ... ```."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.strip("`")
        if limpio.lower().startswith("json"):
            limpio = limpio[4:]
    return json.loads(limpio.strip())


def analizar_triaje_vision(imagenes_data_url: list[str]) -> dict:
    """Envía las imágenes del documento al modelo de visión y retorna el JSON estructurado."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return {
            "error": "Variable COHERE_API_KEY no encontrada en el entorno o archivo .env",
            "requiere_auditoria": True,
            "motivo_auditoria": "Credenciales de Cohere faltantes.",
        }

    if not imagenes_data_url:
        return {
            "error": "No se recibieron imágenes para analizar.",
            "requiere_auditoria": True,
            "motivo_auditoria": "Documento sin imágenes procesables.",
        }

    truncado = len(imagenes_data_url) > MAX_IMAGENES
    imagenes = imagenes_data_url[:MAX_IMAGENES]

    try:
        co = cohere.ClientV2(api_key=api_key)

        contenido = [{"type": "text", "text": INSTRUCCION_USUARIO}]
        contenido += [
            {"type": "image_url", "image_url": {"url": url}} for url in imagenes
        ]

        respuesta = co.chat(
            model=MODELO_VISION,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": contenido},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        datos = _parsear_json(respuesta.message.content[0].text)

        if truncado:
            datos["requiere_auditoria"] = True
            datos["destino_sugerido"] = "Auditoría HITL"
            datos["motivo_auditoria"] = (
                f"Solo se analizaron las primeras {MAX_IMAGENES} páginas del documento. "
                + (datos.get("motivo_auditoria") or "")
            ).strip()

        return aplicar_reglas_hitl(datos)

    except Exception as e:
        return {
            "error": str(e),
            "requiere_auditoria": True,
            "motivo_auditoria": f"Excepción durante la inferencia con Cohere Vision: {e}",
        }
