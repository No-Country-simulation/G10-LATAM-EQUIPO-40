"""
MediFlow - Entry Point

Uso:
  # API REST
  uv run uvicorn main:app --reload --port 8000

  # Demo CLI (3 casos de prueba sin servidor)
  uv run python main.py --demo
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from app.api import app  # noqa: F401, E402

CASOS_DEMO = [
    {
        "id": "DEMO-001",
        "canal": "Consultorios_Externos",
        "tipo": "texto",
        "label": "Flujo estándar — Receta médica",
        "contenido": (
            "RECETA MÉDICA — Clínica San Rafael\n"
            "Paciente: María García, 45 años, DNI 28.456.789\n"
            "Médico: Dr. Alejandro Ramos, MP 98234, Clínica General\n"
            "Fecha: 24/09/2026\n"
            "Prescripción:\n"
            "- Amoxicilina 500mg — 1 comprimido cada 8 horas por 7 días\n"
            "- Ibuprofeno 400mg — 1 comprimido cada 8 horas si hay dolor\n"
            "Diagnóstico: Faringitis bacteriana aguda (J02.0)\n"
            "Control en 7 días."
        ),
    },
    {
        "id": "DEMO-002",
        "canal": "Guardia_Emergencias",
        "tipo": "texto",
        "label": "Urgencia médica — TEP agudo",
        "contenido": (
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
        "id": "DEMO-003",
        "canal": "Admision_General",
        "tipo": "texto",
        "label": "Ambigüedad — Derivado a revisión humana",
        "contenido": (
            "Orden de procedimiento\n"
            "Paciente: [ILEGIBLE]\n"
            "Solicito resonancia magnética de rodilla izquierda\n"
            "Médico: Dr. ??? firma ilegible\n"
            "Sin diagnóstico especificado. Sin matrícula visible."
        ),
    },
]

def _imprimir_resultado(estado) -> None:
    print()
    if estado.clasificacion:
        print(f"  🏷️  Tipo       : {estado.clasificacion.tipo_documento.value}")
        print(f"  🚦 Prioridad  : {estado.clasificacion.nivel_prioridad.value}")
        print(f"  📊 Confianza  : {estado.clasificacion.score_confianza:.0%}")

    if estado.datos_extraidos:
        nombre = (
            estado.datos_extraidos.paciente.nombre
            if estado.datos_extraidos.paciente
            else "no identificado"
        )
        print(f"  👤 Paciente   : {nombre}")
        print(f"  🔬 Dx         : {estado.datos_extraidos.diagnostico_principal or 'no especificado'}")

        faltantes = estado.datos_extraidos.campos_faltantes or []
        if faltantes:
            print(f"  ⚠️  Faltantes  : {', '.join(faltantes)}")

    if estado.decision:
        es_emergencia = "Emergencia" in estado.decision.destino.value
        es_hitl = estado.decision.requiere_revision_humana
        icono = "🆘" if es_emergencia else "👁️" if es_hitl else "✅"

        print(f"  {icono} Destino    : {estado.decision.destino.value}")
        print(f"  💬 Motivo     : {estado.decision.justificacion}")

        if estado.decision.notificacion:
            print(f"  📣 Alerta     : {estado.decision.notificacion.mensaje}")

def demo_cli() -> None:
    if not os.getenv("CO_API_KEY"):
        print("❌ ERROR: CO_API_KEY no definida en .env")
        sys.exit(1)

    from app.chain.pipeline import ejecutar_pipeline
    from app.models.schemas import EstadoPipeline, TipoArchivo

    print("\n" + "═" * 55)
    print("  MediFlow — Demo CLI")
    print("═" * 55)

    for caso in CASOS_DEMO:
        print(f"\n{'─' * 55}")
        print(f"  📄 {caso['id']} | {caso['label']}")
        print(f"  📡 Canal: {caso['canal']}")
        print("─" * 55)

        estado = EstadoPipeline(
            documento_id=caso["id"],
            canal_origen=caso["canal"],
            tipo_archivo=TipoArchivo.PDF,   # texto interno, tipo referencial
            texto=caso["contenido"],
        )

        estado = ejecutar_pipeline(estado)
        _imprimir_resultado(estado)

    print(f"\n{'═' * 55}\n")

if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo_cli()
    else:
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)