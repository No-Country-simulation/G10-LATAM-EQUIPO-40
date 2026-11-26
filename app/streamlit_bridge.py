"""
MediFlow - Bridge para Streamlit
Adapta ejecutar_pipeline() a lo que app.py necesita.
"""

import tempfile
from pathlib import Path

from app.chain.pipeline import ejecutar_pipeline
from app.ingest.image_loader import imagen_desde_bytes
from app.ingest.pdf_loader import procesar_pdf
from app.models.enums import DestinoEnrutamiento
from app.models.schemas import EstadoPipeline, TipoArchivo
from app.notifications.alertas import notificar_documento
from app.storage.oci_client import guardar_documento, marcar_como_recibido
from app.storage.revision import guardar_original


def _es_rechazo(estado: EstadoPipeline) -> bool:
    return bool(
        estado.decision
        and estado.decision.destino
        == DestinoEnrutamiento.RECHAZADO_NO_MEDICO
    )


def _registrar_recibido(
    documento_id: str, canal: str, mime: str, contenido: bytes
):
    """Guarda el original solo después del gate médico."""
    marcar_como_recibido(
        documento_id,
        {
            "documento_id": documento_id,
            "canal_origen": canal,
            "mime": mime,
        },
    )
    return guardar_original(documento_id, mime, contenido)


def procesar_texto(documento_id: str, canal: str, texto: str) -> dict:
    """Para el tab de Transcripción Manual y Casos Demo."""
    estado = EstadoPipeline(
        documento_id=documento_id,
        canal_origen=canal,
        tipo_archivo=TipoArchivo.PDF,
        texto=texto,
    )
    estado = ejecutar_pipeline(estado)

    if _es_rechazo(estado):
        return _con_alerta(_serializar(estado), canal)

    ruta_original = _registrar_recibido(
        documento_id, canal, "text/plain", texto.encode("utf-8")
    )
    oci = _persistir(estado, ruta_original)
    return _con_alerta(_serializar(estado, oci, ruta_original), canal)


def procesar_archivo(
    documento_id: str, canal: str, contenido: bytes, mime: str
) -> dict:
    """Para el tab de Ingesta con archivo real."""
    es_pdf = mime == "application/pdf"
    estado = EstadoPipeline(
        documento_id=documento_id,
        canal_origen=canal,
        tipo_archivo=TipoArchivo.PDF if es_pdf else TipoArchivo.IMAGE,
    )

    try:
        if es_pdf:
            with tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False
            ) as tmp:
                tmp.write(contenido)
                tmp_path = tmp.name
            try:
                resultado = procesar_pdf(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if resultado.get("modo") == "error":
                estado.error = resultado.get("texto")
            else:
                estado.texto = resultado.get("texto") or None
                estado.imagenes_data_url = (
                    resultado.get("imagenes_data_url") or None
                )
        else:
            estado.imagenes_data_url = [imagen_desde_bytes(contenido, mime)]
    except Exception as e:
        # Archivo corrupto o ilegible: va a revisión humana sin llamar al modelo
        estado.error = f"No se pudo leer el archivo: {e}"

    estado = ejecutar_pipeline(estado)

    if _es_rechazo(estado):
        return _con_alerta(_serializar(estado), canal)

    ruta_original = _registrar_recibido(documento_id, canal, mime, contenido)
    oci = _persistir(estado, ruta_original)
    return _con_alerta(_serializar(estado, oci, ruta_original), canal)


def _con_alerta(resultado: dict, canal: str) -> dict:
    destino = (resultado.get("decision") or {}).get("destino")
    if destino == DestinoEnrutamiento.RECHAZADO_NO_MEDICO:
        resultado["alerta"] = {"estado": "no_aplica"}
    else:
        resultado["alerta"] = notificar_documento(resultado, canal)
    return resultado


def _serializar(
    estado: EstadoPipeline,
    oci: dict | None = None,
    ruta_original: str | None = None,
) -> dict:
    """Convierte EstadoPipeline a dict plano para st.json()."""
    return {
        "documento_id": estado.documento_id,
        "mensaje_usuario": estado.mensaje_usuario,
        "validacion_documento": estado.validacion_documento.model_dump()
        if estado.validacion_documento
        else None,
        "clasificacion": estado.clasificacion.model_dump()
        if estado.clasificacion
        else None,
        "datos_extraidos": estado.datos_extraidos.model_dump()
        if estado.datos_extraidos
        else None,
        "decision": estado.decision.model_dump() if estado.decision else None,
        "error": estado.error,
        "archivo_original": ruta_original,
        "almacenamiento_oci": oci,
    }


def _persistir(
    estado: EstadoPipeline, ruta_original: str | None = None
) -> dict | None:
    if not estado.decision or _es_rechazo(estado):
        return None
    es_urgente = (
        estado.clasificacion is not None
        and estado.clasificacion.nivel_prioridad.value == "Urgente"
    )
    contenido = estado.model_dump(mode="json", exclude={"imagenes_data_url"})
    contenido["archivo_original"] = ruta_original
    return guardar_documento(
        documento_id=estado.documento_id,
        contenido=contenido,
        destino=estado.decision.destino.value,
        es_urgente=es_urgente,
    )
