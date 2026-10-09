"""
MediFlow - Bridge para Streamlit
Adapta ejecutar_pipeline() a lo que app.py necesita.
"""

import tempfile
from pathlib import Path

from app.chain.pipeline import ejecutar_pipeline
from app.ingest.image_loader import imagen_desde_bytes
from app.ingest.pdf_loader import procesar_pdf
from app.models.schemas import EstadoPipeline, TipoArchivo
from app.storage.oci_client import guardar_documento, marcar_como_recibido


def procesar_texto(documento_id: str, canal: str, texto: str) -> dict:
    """Para el tab de Transcripción Manual y Casos Demo."""
    marcar_como_recibido(documento_id, {"documento_id": documento_id, "canal_origen": canal})

    estado = EstadoPipeline(
        documento_id=documento_id,
        canal_origen=canal,
        tipo_archivo=TipoArchivo.PDF,
        texto=texto,
    )
    estado = ejecutar_pipeline(estado)
    oci = _persistir(estado)
    return _serializar(estado, oci)


def procesar_archivo(documento_id: str, canal: str, contenido: bytes, mime: str) -> dict:
    """Para el tab de Ingesta con archivo real."""
    marcar_como_recibido(documento_id, {"documento_id": documento_id, "canal_origen": canal})

    estado = EstadoPipeline(
        documento_id=documento_id,
        canal_origen=canal,
        tipo_archivo=TipoArchivo.PDF if mime == "application/pdf" else TipoArchivo.IMAGE,
    )

    if mime == "application/pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name
        try:
            resultado = procesar_pdf(tmp_path)
            estado.texto = resultado.get("texto") or None
            estado.imagenes_data_url = resultado.get("imagenes_data_url") or None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        estado.imagenes_data_url = [imagen_desde_bytes(contenido, mime)]

    estado = ejecutar_pipeline(estado)
    oci = _persistir(estado)
    return _serializar(estado, oci)


def _serializar(estado: EstadoPipeline, oci: dict | None = None) -> dict:
    """Convierte EstadoPipeline a dict plano para st.json()."""
    return {
        "documento_id": estado.documento_id,
        "clasificacion": estado.clasificacion.model_dump() if estado.clasificacion else None,
        "datos_extraidos": estado.datos_extraidos.model_dump() if estado.datos_extraidos else None,
        "decision": estado.decision.model_dump() if estado.decision else None,
        "error": estado.error,
        "almacenamiento_oci": oci,
    }


def _persistir(estado: EstadoPipeline) -> dict | None:
    if not estado.decision:
        return None
    es_urgente = (
        estado.clasificacion is not None
        and estado.clasificacion.nivel_prioridad.value == "Urgente"
    )
    return guardar_documento(
        documento_id=estado.documento_id,
        contenido=estado.model_dump(mode="json", exclude={"imagenes_data_url"}),
        destino=estado.decision.destino.value,
        es_urgente=es_urgente,
    )
