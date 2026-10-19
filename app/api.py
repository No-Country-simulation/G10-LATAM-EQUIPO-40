"""
MediFlow - API REST
Recibe PDF o imagen, ejecuta el pipeline y devuelve RespuestaTriaje.
"""

from __future__ import annotations

import logging

import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.chain.pipeline import ejecutar_pipeline
from app.ingest.image_loader import imagen_desde_bytes
from app.ingest.pdf_loader import procesar_pdf
from app.models.schemas import (
    AlmacenamientoOCI,
    EstadoPipeline,
    RespuestaTriaje,
    TipoArchivo,
)
from app.storage.oci_client import guardar_documento, marcar_como_recibido

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="MediFlow API",
    description="Agente autónomo de triaje clínico",
    version="1.0.0",
)

def _construir_estado(
    documento_id: str,
    canal_origen: str,
    tipo_archivo: TipoArchivo,
    contenido: bytes,
    tmp_path: str | None = None,
) -> EstadoPipeline:
    """
    Llama al loader correspondiente y construye el EstadoPipeline inicial.
    """
    estado = EstadoPipeline(
        documento_id=documento_id,
        canal_origen=canal_origen,
        tipo_archivo=tipo_archivo,
    )

    if tipo_archivo == TipoArchivo.IMAGE:
        data_url = imagen_desde_bytes(contenido)
        estado.imagenes_data_url = [data_url]

    elif tipo_archivo == TipoArchivo.PDF:
        if not tmp_path:
            raise ValueError("PDF requiere tmp_path.")

        resultado = procesar_pdf(tmp_path)
        texto = resultado.get("texto", "")
        imagenes = resultado.get("imagenes_data_url", [])

        if texto and texto.strip():
            estado.texto = texto
        if imagenes:
            estado.imagenes_data_url = imagenes

        if not estado.texto and not estado.imagenes_data_url:
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer contenido del PDF.",
            )

    return estado

def _construir_respuesta(estado: EstadoPipeline) -> RespuestaTriaje:
    """
    Persiste en OCI y construye la RespuestaTriaje final.
    """
    if not estado.decision:
        return RespuestaTriaje(
            status="error",
            documento_id=estado.documento_id,
            error_detalle="El pipeline no generó una decisión de enrutamiento.",
        )

    # Determinar status
    status = (
        "revision_humana"
        if estado.decision.requiere_revision_humana
        else "procesado"
    )

    # Determinar si es urgente para OCI
    es_urgente = (
        estado.clasificacion is not None
        and estado.clasificacion.nivel_prioridad.value == "Urgente"
    )

    # Persistir en OCI
    oci_resultado = guardar_documento(
        documento_id=estado.documento_id,
        contenido=estado.model_dump(mode="json", exclude={"imagenes_data_url"}),
        destino=estado.decision.destino.value,
        es_urgente=es_urgente,
    )

    return RespuestaTriaje(
        status=status,
        documento_id=estado.documento_id,
        clasificacion=estado.clasificacion,
        datos_extraidos=estado.datos_extraidos,
        decision=estado.decision,
        almacenamiento_oci=AlmacenamientoOCI(**oci_resultado),
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "servicio": "MediFlow API v1.0"}

@app.post(
    "/triage",
    response_model=RespuestaTriaje,
    summary="Triaje de documento clínico (PDF o Imagen)",
)
async def triage(
    documento_id: str = Form(...),
    canal_origen: str = Form(...),
    tipo_archivo: TipoArchivo = Form(...),
    archivo: UploadFile = File(...),
):
    """
    Recibe un PDF o imagen, ejecuta el pipeline completo y devuelve
    la clasificación, datos extraídos y decisión de enrutamiento.
    """
    contenido = await archivo.read()

    # Registrar recepción en OCI
    marcar_como_recibido(
        documento_id,
        {
            "documento_id": documento_id,
            "canal_origen": canal_origen,
            "tipo_archivo": tipo_archivo,
            "filename": archivo.filename,
        },
    )

    tmp_path = None

    try:
        # PDF necesita archivo en disco para pdfplumber / pdf2image
        if tipo_archivo == TipoArchivo.PDF:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(contenido)
                tmp_path = tmp.name

        estado = _construir_estado(
            documento_id=documento_id,
            canal_origen=canal_origen,
            tipo_archivo=tipo_archivo,
            contenido=contenido,
            tmp_path=tmp_path,
        )

        estado = ejecutar_pipeline(estado)
        return _construir_respuesta(estado)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[API] Error inesperado en {documento_id}: {e}")
        return JSONResponse(
            status_code=500,
            content=RespuestaTriaje(
                status="error",
                documento_id=documento_id,
                error_detalle=str(e),
            ).model_dump(),
        )

    finally:
        # Limpiar archivo temporal
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
