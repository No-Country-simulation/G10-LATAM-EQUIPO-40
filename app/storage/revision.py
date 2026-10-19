"""
MediFlow - Revisión humana (HITL) sobre OCI Object Storage.

  recibidos/<id>_original.<ext>   archivo tal como llegó (imagen, PDF o texto)
  auditoria_humana/<id>.json      resultado del triaje que requiere revisión
  revisiones/<id>_revision.json   decisión del revisor (aprobado / rechazado)

Un expediente está pendiente si está en auditoria_humana/ y no tiene una revisión
posterior. Si OCI no está disponible, todo se guarda y lee en ./oci_simulado/.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.storage import oci_client as _oci
from app.storage.oci_client import BUCKET_NAME, _guardar_local, _serializar

logger = logging.getLogger(__name__)

LOCAL_DIR = Path("./oci_simulado")

_EXT = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "text/plain": ".txt",
}


def ruta_original(documento_id: str, mime: str) -> str:
    return f"recibidos/{documento_id}_original{_EXT.get((mime or '').lower(), '.bin')}"


def _guardar(ruta: str, contenido: bytes, content_type: str) -> str:
    """Guarda en OCI; si falla, en local. Devuelve 'exito' | 'simulado' | 'error_oci'."""
    if not _oci._OCI_DISPONIBLE:
        _guardar_local(ruta, contenido)
        return "simulado"
    try:
        client = _oci._get_client()
        client.put_object(
            namespace_name=_oci._get_namespace(client),
            bucket_name=BUCKET_NAME,
            object_name=ruta,
            put_object_body=contenido,
            content_type=content_type,
        )
        logger.info(f"[OCI] Guardado: {BUCKET_NAME}/{ruta}")
        return "exito"
    except Exception as e:
        logger.warning(f"[OCI] No se pudo guardar {ruta}: {e}")
        _guardar_local(ruta, contenido)
        return "error_oci"


def guardar_original(documento_id: str, mime: str, contenido: bytes) -> str:
    """Guarda el archivo recibido y devuelve su ruta (para mostrarlo al revisor)."""
    ruta = ruta_original(documento_id, mime)
    _guardar(ruta, contenido, mime or "application/octet-stream")
    return ruta


def leer_objeto(ruta: str) -> bytes | None:
    """Lee un objeto de OCI; si no se puede, busca la copia local."""
    if _oci._OCI_DISPONIBLE:
        try:
            client = _oci._get_client()
            resp = client.get_object(
                namespace_name=_oci._get_namespace(client),
                bucket_name=BUCKET_NAME,
                object_name=ruta,
            )
            return resp.data.content
        except Exception as e:
            logger.info(f"[OCI] No se pudo leer {ruta} de OCI ({e}); se busca en local.")
    local = LOCAL_DIR / ruta
    return local.read_bytes() if local.exists() else None


def _listar(prefijo: str) -> dict[str, float]:
    """Objetos bajo un prefijo -> fecha de modificación (epoch). Une OCI y local."""
    objetos: dict[str, float] = {}
    if _oci._OCI_DISPONIBLE:
        try:
            client = _oci._get_client()
            ns = _oci._get_namespace(client)
            inicio = None
            while True:
                resp = client.list_objects(
                    namespace_name=ns,
                    bucket_name=BUCKET_NAME,
                    prefix=prefijo,
                    fields="name,timeModified",
                    start=inicio,
                )
                for o in resp.data.objects:
                    t = getattr(o, "time_modified", None)
                    objetos[o.name] = t.timestamp() if t else 0.0
                inicio = resp.data.next_start_with
                if not inicio:
                    break
        except Exception as e:
            logger.warning(f"[OCI] No se pudo listar {prefijo}: {e}")

    base = LOCAL_DIR / prefijo
    if base.exists():
        for p in base.rglob("*"):
            if p.is_file():
                nombre = p.relative_to(LOCAL_DIR).as_posix()
                objetos[nombre] = max(objetos.get(nombre, 0.0), p.stat().st_mtime)
    return objetos


def listar_pendientes() -> list[dict]:
    """Expedientes de auditoria_humana/ sin revisión posterior."""
    auditoria = _listar("auditoria_humana/")
    sufijo = "_revision.json"
    revisados = {
        Path(n).name[: -len(sufijo)]: t
        for n, t in _listar("revisiones/").items()
        if n.endswith(sufijo)
    }

    pendientes: list[dict] = []
    for nombre, t in sorted(auditoria.items()):
        if not nombre.endswith(".json"):
            continue
        doc_id = Path(nombre).stem
        if doc_id in revisados and revisados[doc_id] >= t:
            continue
        raw = leer_objeto(nombre)
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[HITL] JSON inválido en {nombre}; se omite.")
            continue
        item.setdefault("documento_id", doc_id)
        pendientes.append(item)
    return pendientes


def registrar_revision(documento_id: str, decision: str, notas: str = "") -> dict:
    """Guarda la decisión del revisor. decision: 'aprobado' | 'rechazado'."""
    registro = {
        "documento_id": documento_id,
        "decision": decision,
        "notas": notas,
        "fecha_revision": datetime.now(timezone.utc).isoformat(),
    }
    ruta = f"revisiones/{documento_id}_revision.json"
    status = _guardar(ruta, _serializar(registro), "application/json")
    return {"ruta": ruta, "status": status}
