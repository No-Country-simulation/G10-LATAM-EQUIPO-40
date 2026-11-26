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

Variables de entorno:
    OCI_BUCKET_NAME   nombre del bucket (default: mediflow-documentos-clinicos)
    OCI_NAMESPACE     namespace de Object Storage (si vacío, se consulta a OCI)
    OCI_REGION        región para modo local (ej. sa-bogota-1)
    OCI_PASS_PHRASE   passphrase de la llave privada (modo local)
    OCI_FORCE_MODE    local | instance | simulated
                      - local:     usa ~/.oci/config, sin sondear el metadata service
                      - instance:  fuerza Instance Principals
                      - simulated: salta OCI por completo (cero espera, ideal en desarrollo)
"""

from __future__ import annotations

import json
import logging
import os
import socket
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos-clinicos")
OCI_NAMESPACE = os.getenv("OCI_NAMESPACE", "")
OCI_REGION = os.getenv("OCI_REGION", "")

# Timeouts del cliente OCI (conexión, lectura) en segundos.
# Evita que una red caída bloquee el pipeline por los reintentos por defecto.
OCI_CLIENT_TIMEOUT = (3, 10)

try:
    import oci  # type: ignore

    _OCI_DISPONIBLE = True
    logger.info("[OCI] SDK disponible.")
except ImportError:
    _OCI_DISPONIBLE = False
    logger.warning("[OCI] SDK no instalado. Modo simulado activo.")


# ──────────────────────────────────────────────────────────────────────
# Autenticación: detección automática local ↔ nube ↔ simulado
# ──────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _esta_en_instancia_oci(timeout: float = 0.3) -> bool:
    """
    True si estamos dentro de una instancia de OCI Compute.

    Se detecta consultando el metadata service local (169.254.169.254),
    que solo responde desde dentro de una instancia cloud. El resultado se
    cachea: el sondeo se hace una sola vez por proceso.

    Override manual con OCI_FORCE_MODE (ver docstring del módulo).
    """
    forzado = os.getenv("OCI_FORCE_MODE", "").lower()
    if forzado == "instance":
        return True
    if forzado in ("local", "simulated"):
        return False

    try:
        with socket.create_connection(("169.254.169.254", 80), timeout=timeout):
            return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def _get_client():
    """
    Devuelve un cliente de Object Storage, o None si debe usarse el modo simulado.

    - OCI_FORCE_MODE=simulated -> None (sin sondeos ni credenciales).
    - En una instancia OCI     -> Instance Principals (sin credenciales en disco).
    - En local / dev           -> ~/.oci/config.
    - Sin SDK o sin credenciales -> None.

    El resultado (incluido None) se cachea con lru_cache, así que la detección
    y la creación ocurren una sola vez por proceso.
    """
    if not _OCI_DISPONIBLE:
        return None

    if os.getenv("OCI_FORCE_MODE", "").lower() == "simulated":
        logger.info("[OCI] Modo simulado forzado por OCI_FORCE_MODE.")
        return None

    if _esta_en_instancia_oci():
        try:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            logger.info("[OCI] Cliente con Instance Principals (modo nube)")
            return oci.object_storage.ObjectStorageClient(
                config={"region": signer.region},
                signer=signer,
                timeout=OCI_CLIENT_TIMEOUT,
            )
        except Exception as e:
            logger.warning(
                f"[OCI] Instance Principals falló ({e}); probando config file…"
            )

    # Modo local (o fallback si Instance Principals falló)
    try:
        config = oci.config.from_file()
        if OCI_REGION:
            config["region"] = OCI_REGION
        if os.getenv("OCI_PASS_PHRASE"):
            config["pass_phrase"] = os.getenv("OCI_PASS_PHRASE")
        logger.info("[OCI] Cliente con config file (modo local)")
        return oci.object_storage.ObjectStorageClient(
            config, timeout=OCI_CLIENT_TIMEOUT
        )
    except Exception as e:
        logger.warning(f"[OCI] Sin credenciales ({e}). Modo simulado activo.")
        return None


def _reset_client_cache() -> None:
    """Fuerza a recrear el cliente (y repetir la detección) en la próxima llamada."""
    _esta_en_instancia_oci.cache_clear()
    _get_client.cache_clear()
    _get_namespace.cache_clear()


@lru_cache(maxsize=1)
def _get_namespace() -> str:
    """Namespace de Object Storage; se consulta a OCI una sola vez por proceso."""
    if OCI_NAMESPACE:
        return OCI_NAMESPACE
    client = _get_client()
    if client is None:
        raise RuntimeError("No hay cliente OCI disponible")
    return client.get_namespace().data


# ──────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────

def _ruta_objeto(documento_id: str, destino: str, es_urgente: bool) -> str:
    """
    Calcula la ruta del objeto según destino de enrutamiento.

    Rechazado (no médico)            -> rechazados/ (no se usa normalmente)
    Cola_Revision_Humana / Auditoria -> auditoria_humana/
    Cola de emergencia o urgente     -> procesados/urgentes/
    Resto                            -> procesados/rutina/
    """
    if "Rechazado" in destino:
        carpeta = "rechazados"
    elif any(x in destino for x in ["Revision_Humana", "Auditoria"]):
        carpeta = "auditoria_humana"
    elif es_urgente or "Emergencia" in destino:
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


def _subir(ruta: str, contenido: bytes) -> str:
    """
    Sube el objeto a OCI; si no hay cliente o falla, guarda en local.

    Returns:
        "exito" | "simulado" | "error_oci: <detalle>"
    """
    client = _get_client()
    if client is None:
        _guardar_local(ruta, contenido)
        return "simulado"

    try:
        client.put_object(
            namespace_name=_get_namespace(),
            bucket_name=BUCKET_NAME,
            object_name=ruta,
            put_object_body=contenido,
            content_type="application/json",
        )
        logger.info(f"[OCI] Guardado: {BUCKET_NAME}/{ruta}")
        return "exito"
    except Exception as e:
        logger.error(f"[OCI] Error al guardar {ruta}: {e}")
        _guardar_local(ruta, contenido)
        return f"error_oci: {str(e)[:80]}"


# ──────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────

def marcar_como_recibido(documento_id: str, metadata: dict) -> None:
    """
    Registra el documento en recibidos/ al momento de ingresar al sistema.
    No bloquea el pipeline si falla.
    """
    ruta = f"recibidos/{documento_id}_metadata.json"
    _subir(ruta, _serializar(metadata))


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
    status = _subir(ruta, _serializar(contenido))
    return {
        "bucket": BUCKET_NAME,
        "ruta": ruta,
        "status": status,
    }
