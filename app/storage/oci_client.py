"""
MediFlow - OCI Object Storage Client
Persiste documentos y resultados en buckets organizados por estado.

Estructura:
  mediflow-documentos-clinicos/
    ├── recibidos/
    ├── procesados/
    │   ├── urgentes/
    │   └── rutina/
    └── auditoria_humana/

Modo simulado: si OCI no está configurado, guarda localmente en ./oci_simulado/
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

# Importaciones para modo local o mube más añadido caché
import socket
from functools import lru_cache

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos-clinicos")
OCI_NAMESPACE = os.getenv("OCI_NAMESPACE", "")
OCI_REGION = os.getenv("OCI_REGION", "")

try:
    import oci  # type: ignore
    _OCI_DISPONIBLE = True
    logger.info("[OCI] SDK disponible.")
except ImportError:
    _OCI_DISPONIBLE = False
    logger.warning("[OCI] SDK no instalado. Modo simulado activo.")

# ──────────────────────────────────────────────────────────────────────
# Autenticación: detección automática local ↔ nube
# ──────────────────────────────────────────────────────────────────────

def _esta_en_instancia_oci(timeout: float = 1.0) -> bool:
    """
    True si estamos dentro de una instancia de OCI Compute.

    Se detecta consultando el metadata service local (169.254.169.254),
    que solo responde desde dentro de una instancia cloud.

    Override manual con la variable de entorno OCI_FORCE_MODE:
        OCI_FORCE_MODE=local     -> fuerza config file
        OCI_FORCE_MODE=instance  -> fuerza Instance Principals
    """
    forzado = os.getenv("OCI_FORCE_MODE", "").lower()
    if forzado == "instance":
        return True
    if forzado == "local":
        return False

    try:
        with socket.create_connection(("169.254.169.254", 80), timeout=timeout):
            return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def _get_client():
    """
    Devuelve un cliente de Object Storage, detectando el entorno:

    - En una instancia OCI  -> Instance Principals (sin credenciales en disco).
    - En local / dev        -> ~/.oci/config.

    El resultado se cachea: la detección y la creación se hacen una sola vez
    por proceso, así no se repite el sondeo al metadata service en cada llamada.
    """
    if _esta_en_instancia_oci():
        try:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            logger.info("[OCI] Cliente con Instance Principals (modo nube)")
            return oci.object_storage.ObjectStorageClient(
                config={"region": signer.region},
                signer=signer,
            )
        except Exception as e:
            logger.warning(
                f"[OCI] Instance Principals falló ({e}); probando config file…"
            )

    # Modo local (o fallback si Instance Principals falló)
    config = oci.config.from_file()
    if OCI_REGION:
        config["region"] = OCI_REGION
    if os.getenv("OCI_PASS_PHRASE"):
        config["pass_phrase"] = os.getenv("OCI_PASS_PHRASE")
    logger.info("[OCI] Cliente con config file (modo local)")
    return oci.object_storage.ObjectStorageClient(config)


# Borrar cache si se cambian las credenciales en caliente
def _reset_client_cache() -> None:
    """Fuerza a recrear el cliente en la próxima llamada."""
    _get_client.cache_clear()

def _get_namespace(client) -> str:
    return OCI_NAMESPACE or client.get_namespace().data

def _ruta_objeto(documento_id: str, destino: str, es_urgente: bool) -> str:
    """
    Calcula la ruta del objeto según destino de enrutamiento.

    Cola_Revision_Humana / Auditoria -> auditoria_humana/
    Urgente                          -> procesados/urgentes/
    Resto                            -> procesados/rutina/
    """
    if any(x in destino for x in ["Revision_Humana", "Auditoria"]):
        carpeta = "auditoria_humana"
    elif es_urgente:
        carpeta = "procesados/urgentes"
    else:
        carpeta = "procesados/rutina"

    return f"{carpeta}/{documento_id}.json"

def _guardar_local(ruta: str, contenido: bytes) -> None:
    """Fallback local cuando OCI no está disponible."""
    path = Path("./oci_simulado") / ruta
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contenido)
    logger.info(f"[OCI-SIM] Guardado localmente: {path}")

def _serializar(contenido: dict) -> bytes:
    return json.dumps(contenido, ensure_ascii=False, indent=2).encode("utf-8")

def marcar_como_recibido(documento_id: str, metadata: dict) -> None:
    """
    Registra el documento en recibidos/ al momento de ingresar al sistema.
    No bloquea el pipeline si falla.
    """
    ruta = f"recibidos/{documento_id}_metadata.json"
    contenido = _serializar(metadata)

    if not _OCI_DISPONIBLE:
        _guardar_local(ruta, contenido)
        return

    try:
        client = _get_client()
        namespace = _get_namespace(client)
        client.put_object(
            namespace_name=namespace,
            bucket_name=BUCKET_NAME,
            object_name=ruta,
            put_object_body=contenido,
            content_type="application/json",
        )
        logger.info(f"[OCI] Recepción registrada: {ruta}")
    except Exception as e:
        logger.warning(f"[OCI] No se pudo registrar recepción de {documento_id}: {e}")
        _guardar_local(ruta, contenido)


def guardar_documento(
    documento_id: str,
    contenido: dict,
    destino: str = "procesados/rutina",
    es_urgente: bool = False,
) -> dict[str, str]:
    """
    Guarda el resultado JSON del triaje en OCI Object Storage.

    Returns:
        dict con bucket, ruta y status para AlmacenamientoOCI
    """
    ruta = _ruta_objeto(documento_id, destino, es_urgente)
    contenido_bytes = _serializar(contenido)

    if not _OCI_DISPONIBLE:
        _guardar_local(ruta, contenido_bytes)
        return {
            "bucket": BUCKET_NAME,
            "ruta": ruta,
            "status": "simulado",
        }

    try:
        client = _get_client()
        namespace = _get_namespace(client)
        client.put_object(
            namespace_name=namespace,
            bucket_name=BUCKET_NAME,
            object_name=ruta,
            put_object_body=contenido_bytes,
            content_type="application/json",
        )
        logger.info(f"[OCI] Guardado: {BUCKET_NAME}/{ruta}")
        return {
            "bucket": BUCKET_NAME,
            "ruta": ruta,
            "status": "exito",
        }

    except Exception as e:
        logger.error(f"[OCI] Error al guardar {documento_id}: {e}")
        _guardar_local(ruta, contenido_bytes)
        return {
            "bucket": BUCKET_NAME,
            "ruta": ruta,
            "status": f"error_oci: {str(e)[:80]}",
        }
