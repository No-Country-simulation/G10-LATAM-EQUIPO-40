from types import SimpleNamespace

from app.chain import pipeline
from app.chain.validate import _parsear_respuesta
from app.models.enums import (
    DestinoEnrutamiento,
    NivelPrioridad,
    TipoArchivo,
    TipoDocumento,
)
from app.models.schemas import (
    Clasificacion,
    DatosExtraidos,
    DecisionEnrutamiento,
    EstadoPipeline,
    ValidacionDocumento,
)


def _estado(texto: str = "Receta médica: Metformina 850 mg") -> EstadoPipeline:
    return EstadoPipeline(
        documento_id="T",
        canal_origen="Guardia",
        tipo_archivo=TipoArchivo.PDF,
        texto=texto,
    )


def test_parsea_respuesta_de_validacion():
    respuesta = SimpleNamespace(
        content=(
            '{"es_documento_medico": false, "motivo": "factura", '
            '"confianza": 0.92}'
        )
    )

    validacion = _parsear_respuesta(respuesta)

    assert validacion.es_documento_medico is False
    assert validacion.motivo == "factura"
    assert validacion.confianza == 0.92


def test_no_medico_corta_antes_de_clasificar(monkeypatch):
    def validar(estado):
        estado.validacion_documento = ValidacionDocumento(
            es_documento_medico=False,
            motivo="factura de servicios",
            confianza=0.95,
        )
        return estado

    def clasificar(_estado):
        raise AssertionError("No debe clasificar un documento no médico")

    monkeypatch.setattr(pipeline, "nodo_validar_documento_medico", validar)
    monkeypatch.setattr(pipeline, "nodo_clasificar", clasificar)

    salida = pipeline.ejecutar_pipeline(_estado("Factura de luz"))

    assert salida.decision.destino == DestinoEnrutamiento.RECHAZADO_NO_MEDICO
    assert salida.clasificacion is None
    assert salida.datos_extraidos is None
    assert salida.mensaje_usuario


def test_documento_medico_continua_el_pipeline(monkeypatch):
    def validar(estado):
        estado.validacion_documento = ValidacionDocumento(
            es_documento_medico=True,
            confianza=0.91,
        )
        return estado

    def clasificar(estado):
        estado.clasificacion = Clasificacion(
            tipo_documento=TipoDocumento.RECETA_MEDICA,
            nivel_prioridad=NivelPrioridad.NORMAL,
            score_confianza=0.9,
        )
        return estado

    def extraer(estado):
        estado.datos_extraidos = DatosExtraidos(campos_faltantes=[])
        return estado

    monkeypatch.setattr(pipeline, "nodo_validar_documento_medico", validar)
    monkeypatch.setattr(pipeline, "nodo_clasificar", clasificar)
    monkeypatch.setattr(pipeline, "nodo_extraer", extraer)

    salida = pipeline.ejecutar_pipeline(_estado())

    assert salida.decision.destino == DestinoEnrutamiento.FARMACIA
    assert salida.clasificacion is not None


def test_fallo_del_gate_no_bloquea(monkeypatch):
    from app.chain import validate

    monkeypatch.setattr(validate, "_get_llm", lambda *a, **k: object())
    monkeypatch.setattr(
        validate,
        "invocar_con_reintentos",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sin red")),
    )

    estado = validate.nodo_validar_documento_medico(_estado())

    assert estado.validacion_documento is None
    assert estado.error is None


def test_rechazo_no_se_persiste(monkeypatch):
    import app.streamlit_bridge as bridge

    def guardar(*_args, **_kwargs):
        raise AssertionError("No debe guardar un documento no médico")

    monkeypatch.setattr(bridge, "guardar_documento", guardar)

    estado = _estado("Factura de luz")
    estado.decision = DecisionEnrutamiento(
        destino=DestinoEnrutamiento.RECHAZADO_NO_MEDICO,
        requiere_revision_humana=False,
        justificacion="Documento rechazado.",
    )

    assert bridge._persistir(estado) is None


def test_api_responde_rechazo_sin_guardar(monkeypatch):
    from app import api

    def guardar(*_args, **_kwargs):
        raise AssertionError("No debe guardar un documento no médico")

    monkeypatch.setattr(api, "guardar_documento", guardar)
    monkeypatch.setattr(api, "notificar_documento", guardar)

    estado = _estado("Factura de luz")
    estado.mensaje_usuario = "El archivo no parece ser un documento médico."
    estado.decision = DecisionEnrutamiento(
        destino=DestinoEnrutamiento.RECHAZADO_NO_MEDICO,
        requiere_revision_humana=False,
        justificacion="Documento rechazado.",
    )

    respuesta = api._construir_respuesta(estado)

    assert respuesta.status == "rechazado"
    assert respuesta.mensaje_usuario == estado.mensaje_usuario
    assert respuesta.almacenamiento_oci is None
