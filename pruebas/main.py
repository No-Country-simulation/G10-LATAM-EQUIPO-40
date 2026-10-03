"""
main.py — Punto de entrada de procesamiento de archivos.

1. procesar_archivo(): decide si el archivo es imagen o PDF y llama al loader
   correspondiente (procesar_pdf / imagen_a_base64), devolviendo SIEMPRE:

    {
        "tipo": "imagen" | "pdf",
        "texto": str,                      # vacío para imágenes
        "imagenes_data_url": list[str],    # data URLs para el modelo de visión
        "modo": "texto" | "imagen" | "mixto" | "error",
    }

2. procesar_y_analizar(): enruta según el modo:
    - "texto"  -> agente de texto   (agent_cohere.analizar_triaje_cohere)
    - "imagen" -> agente de visión  (agent_vision.analizar_triaje_vision)
    - resto    -> pendiente ("mixto") o error
"""

from pathlib import Path

from agent_cohere import analizar_triaje_cohere
from agent_vision import analizar_triaje_vision
from image_loader import imagen_a_base64
from pdf_loader import procesar_pdf

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
EXTENSIONES_PDF = {".pdf"}
EXTENSIONES_SOPORTADAS = sorted(EXTENSIONES_IMAGEN | EXTENSIONES_PDF)


def detectar_tipo(ruta: str) -> str:
    """Devuelve "imagen" o "pdf" según la extensión. Lanza ValueError si no es soportado."""
    ext = Path(ruta).suffix.lower()
    if ext in EXTENSIONES_PDF:
        return "pdf"
    if ext in EXTENSIONES_IMAGEN:
        return "imagen"
    raise ValueError(
        f"Formato '{ext}' no soportado. Válidos: {', '.join(EXTENSIONES_SOPORTADAS)}"
    )


def procesar_archivo(ruta: str) -> dict:
    """Procesa un archivo (imagen o PDF) y devuelve el resultado normalizado."""
    tipo = detectar_tipo(ruta)

    if tipo == "pdf":
        resultado = procesar_pdf(ruta)
        return {
            "tipo": "pdf",
            "texto": resultado["texto"],
            "imagenes_data_url": resultado["imagenes_data_url"],
            "modo": resultado["modo"],
        }

    return {
        "tipo": "imagen",
        "texto": "",
        "imagenes_data_url": [imagen_a_base64(ruta)],
        "modo": "imagen",
    }


def analizar_documento(documento: dict) -> dict:
    """Enruta un documento ya cargado (salida de procesar_archivo) al agente que corresponda.

    Devuelve:
        {
            "documento": <el mismo documento>,
            "triaje": dict | None,      # JSON del agente (None si no hay agente para ese modo)
            "mensaje": str | None,      # aviso cuando no se pudo analizar
        }
    """
    modo = documento["modo"]

    if modo == "texto":
        return {
            "documento": documento,
            "triaje": analizar_triaje_cohere(documento["texto"]),
            "mensaje": None,
        }

    if modo == "imagen":
        return {
            "documento": documento,
            "triaje": analizar_triaje_vision(documento["imagenes_data_url"]),
            "mensaje": None,
        }

    if modo == "error":
        return {"documento": documento, "triaje": None, "mensaje": documento["texto"]}

    return {
        "documento": documento,
        "triaje": None,
        "mensaje": f"Modo '{modo}': aún no hay agente definido para este caso.",
    }


def procesar_y_analizar(ruta: str) -> dict:
    """Carga el archivo y lo analiza con el agente correspondiente (todo en un paso)."""
    return analizar_documento(procesar_archivo(ruta))


if __name__ == "__main__":
    # Prueba rápida: python main.py ruta/al/archivo.pdf
    import json
    import sys

    if len(sys.argv) < 2:
        print("Uso: python main.py <ruta_archivo>")
        sys.exit(1)

    r = procesar_y_analizar(sys.argv[1])
    d = r["documento"]
    print(f"tipo={d['tipo']} | modo={d['modo']} | "
          f"chars_texto={len(d['texto'])} | imágenes={len(d['imagenes_data_url'])}")
    if r["mensaje"]:
        print(r["mensaje"])
    if r["triaje"]:
        print(json.dumps(r["triaje"], ensure_ascii=False, indent=2))
