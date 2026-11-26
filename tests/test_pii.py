import io
import logging

from app.chain import extract
from app.chain.extract import nodo_extraer
from app.chain.router import nodo_enrutar
from app.models.schemas import (
    Clasificacion,
    DatosExtraidos,
    EstadoPipeline,
    NivelPrioridad,
    Paciente,
    TipoArchivo,
    TipoDocumento,
)
from app.security.pii import (
    RedactingFormatter,
    mask_documento,
    mask_nombre,
    redactar,
)


def _capturar(nombre_logger):
    logger = logging.getLogger(nombre_logger)
    nivel = logger.level
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter("%(message)s"))
    logger.addHandler(handler)
    return logger, handler, stream, nivel


def test_nombre_conserva_solo_iniciales():
    assert mask_nombre("Ana María Soto") == "A** M**** S***"
    assert mask_nombre("Bernardo") == "B****"
    assert mask_nombre(None) == "—"
    assert mask_nombre("   ") == "—"


def test_documento_no_muestra_digitos_por_defecto():
    assert mask_documento("1.020.304.567") == "***"
    assert mask_documento("1020304567") == "***"
    assert mask_documento(None) == "—"
    # Solo para canales restringidos, nunca para el log de la app.
    assert mask_documento("1020304567", visibles=2) == "********67"


def test_redactar_no_rompe_ids_ni_fechas():
    texto = "DOC-1723456789 2026-11-19 10:23:45 prioridad=Alta"
    assert redactar(texto) == texto


def test_redactar_mascara_documentos_correos_y_telefonos():
    texto = "CC 1.020.304.567, cel 300 123 4567, correo ana@ejemplo.test"
    salida = redactar(texto)
    assert "1.020.304.567" not in salida
    assert "300 123 4567" not in salida
    assert "ana@ejemplo.test" not in salida
    assert "[correo]" in salida


def test_redactar_mascara_nombres_conocidos():
    salida = redactar(
        "Hallazgo crítico (TEP) en Ana María Soto.",
        nombres=["Ana María Soto"],
    )
    assert "Ana María Soto" not in salida
    assert "A** M**** S***" in salida


def test_formatter_redacta_args_ya_interpolados():
    logger, handler, stream, nivel = _capturar("test.pii.formatter")
    try:
        logger.info(
            "[EXTRAER] %s | cc %s | %s",
            "DOC-1723456789",
            "1020304567",
            "ana@ejemplo.test",
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)

    salida = stream.getvalue()
    assert "DOC-1723456789" in salida
    assert "1020304567" not in salida
    assert "ana@ejemplo.test" not in salida


def test_extraer_no_loguea_nombre_ni_diagnostico(monkeypatch):
    datos = DatosExtraidos(
        paciente=Paciente(
            nombre="Ana María Soto", documento_identidad="1020304567"
        ),
        diagnostico_principal="Tromboembolismo pulmonar",
        cie10_sugerido="I26",
    )
    estado = EstadoPipeline(
        documento_id="DOC-1723456789",
        canal_origen="Guardia",
        tipo_archivo=TipoArchivo.PDF,
        texto=(
            "Paciente: Ana María Soto, CC 1020304567. "
            "Diagnóstico: tromboembolismo pulmonar."
        ),
    )

    monkeypatch.setattr(extract, "_get_llm", lambda *a, **k: object())
    monkeypatch.setattr(extract, "_construir_mensajes", lambda e: [])
    monkeypatch.setattr(
        extract, "invocar_con_reintentos", lambda *a, **k: object()
    )
    monkeypatch.setattr(extract, "_parsear_respuesta", lambda r: datos)

    logger, handler, stream, nivel = _capturar("app.chain.extract")
    try:
        nodo_extraer(estado)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)

    salida = stream.getvalue()
    assert "Ana María Soto" not in salida
    assert "Tromboembolismo pulmonar" not in salida
    assert "1020304567" not in salida
    assert "A** M**** S***" in salida
    assert "I26" in salida


def test_enrutar_no_loguea_el_nombre_del_paciente():
    estado = EstadoPipeline(
        documento_id="DOC-1723456789",
        canal_origen="Guardia",
        tipo_archivo=TipoArchivo.PDF,
    )
    estado.clasificacion = Clasificacion(
        tipo_documento=TipoDocumento.HOJA_TRIAJE,
        nivel_prioridad=NivelPrioridad.URGENTE,
        score_confianza=0.95,
    )
    estado.datos_extraidos = DatosExtraidos(
        paciente=Paciente(nombre="Ana María Soto"),
        diagnostico_principal="Tromboembolismo pulmonar",
    )

    logger, handler, stream, nivel = _capturar("app.chain.router")
    try:
        nodo_enrutar(estado)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)

    salida = stream.getvalue()
    assert "Ana María Soto" not in salida
    assert "A** M**** S***" in salida
    assert "Cola_Emergencia_Medica" in salida
