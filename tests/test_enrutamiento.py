import pytest

import app.chain.pipeline as pipeline
from app.chain.extract import calcular_faltantes
from app.chain.router import nodo_enrutar
from app.models.schemas import (
    Clasificacion,
    DatosExtraidos,
    DestinoEnrutamiento,
    EstadoPipeline,
    Medicamento,
    MedicoSolicitante,
    NivelPrioridad,
    Paciente,
    TipoArchivo,
    TipoDocumento,
)
from app.storage.oci_client import _ruta_objeto

PACIENTE = Paciente(nombre="Ana Soto")
MEDICO = MedicoSolicitante(nombre="Dra. Lara", matricula="MP 123")


def estado(tipo, prioridad, score=0.9, datos=None, texto=None, error=None):
    e = EstadoPipeline(
        documento_id="T",
        canal_origen="Guardia",
        tipo_archivo=TipoArchivo.PDF,
        texto=texto,
        error=error,
    )
    e.clasificacion = Clasificacion(
        tipo_documento=tipo, nivel_prioridad=prioridad, score_confianza=score
    )
    e.datos_extraidos = datos
    if datos and not error:
        datos.campos_faltantes = calcular_faltantes(datos, tipo)
    return e


def test_receta_sin_medico_va_a_auditoria():
    datos = DatosExtraidos(
        paciente=PACIENTE, medicamentos=[Medicamento(nombre="Metformina")]
    )
    d = nodo_enrutar(estado(TipoDocumento.RECETA_MEDICA, NivelPrioridad.NORMAL, datos=datos)).decision
    assert d.destino == DestinoEnrutamiento.AUDITORIA_AUTORIZACIONES
    assert d.requiere_revision_humana


def test_receta_completa_sigue_a_farmacia():
    datos = DatosExtraidos(
        paciente=PACIENTE,
        medico_solicitante=MEDICO,
        medicamentos=[Medicamento(nombre="Metformina")],
    )
    d = nodo_enrutar(estado(TipoDocumento.RECETA_MEDICA, NivelPrioridad.NORMAL, datos=datos)).decision
    assert d.destino == DestinoEnrutamiento.FARMACIA


def test_urgente_con_error_de_extraccion_alerta_a_guardia():
    e = estado(
        TipoDocumento.INFORME_IMAGENES,
        NivelPrioridad.URGENTE,
        datos=DatosExtraidos(campos_faltantes=["Error"]),
        error="respuesta inesperada",
    )
    d = nodo_enrutar(e).decision
    assert d.destino == DestinoEnrutamiento.COLA_EMERGENCIA
    assert d.notificacion
    assert "Validar contra el documento original" in d.justificacion


def test_urgente_con_baja_confianza_en_el_pipeline(monkeypatch):
    e = EstadoPipeline(
        documento_id="T", canal_origen="Guardia", tipo_archivo=TipoArchivo.PDF, texto="x"
    )

    def clasificar(est):
        est.clasificacion = Clasificacion(
            tipo_documento=TipoDocumento.INFORME_IMAGENES,
            nivel_prioridad=NivelPrioridad.URGENTE,
            score_confianza=0.55,
        )
        return est

    monkeypatch.setattr(pipeline, "nodo_clasificar", clasificar)
    d = pipeline.ejecutar_pipeline(e).decision
    assert d.destino == DestinoEnrutamiento.COLA_EMERGENCIA
    assert d.notificacion


def test_error_de_clasificacion_con_termino_critico_es_prioritario(monkeypatch):
    e = EstadoPipeline(
        documento_id="T",
        canal_origen="Guardia",
        tipo_archivo=TipoArchivo.PDF,
        texto="Paciente con neumotórax a tensión",
    )

    def clasificar(est):
        est.error = "fallo del modelo"
        est.clasificacion = Clasificacion(
            tipo_documento=TipoDocumento.DESCONOCIDO,
            nivel_prioridad=NivelPrioridad.NORMAL,
            score_confianza=0.0,
        )
        return est

    monkeypatch.setattr(pipeline, "nodo_clasificar", clasificar)
    d = pipeline.ejecutar_pipeline(e).decision
    assert d.revision_prioritaria
    assert d.notificacion


def test_hallazgo_extraido_sin_urgencia_es_prioritario():
    datos = DatosExtraidos(paciente=PACIENTE, hallazgos_criticos=["Sospecha de SCA"])
    d = nodo_enrutar(estado(TipoDocumento.HOJA_TRIAJE, NivelPrioridad.NORMAL, datos=datos)).decision
    assert d.destino == DestinoEnrutamiento.REVISION_HUMANA
    assert d.revision_prioritaria
    assert d.notificacion


@pytest.mark.parametrize(
    "texto",
    [
        "Se observa neumotórax derecho",
        "Hemorragias digestivas altas",
        "No se descarta TEP",
        "Se descarta IAM. Compatible con TEP agudo",
        "No responde, shock hipovolémico",
    ],
)
def test_detecta_terminos_criticos_en_texto_original(texto):
    datos = DatosExtraidos(paciente=PACIENTE)
    d = nodo_enrutar(
        estado(TipoDocumento.HOJA_TRIAJE, NivelPrioridad.NORMAL, datos=datos, texto=texto)
    ).decision
    assert d.revision_prioritaria


@pytest.mark.parametrize(
    "texto",
    ["Se descarta TEP", "Sin signos de hemorragia", "Niega infarto previo"],
)
def test_no_alerta_por_terminos_negados(texto):
    datos = DatosExtraidos(paciente=PACIENTE)
    d = nodo_enrutar(
        estado(TipoDocumento.HOJA_TRIAJE, NivelPrioridad.NORMAL, datos=datos, texto=texto)
    ).decision
    assert not d.revision_prioritaria
    assert d.destino == DestinoEnrutamiento.HISTORIA_CLINICA


def test_emergencia_de_prioridad_alta_se_guarda_en_urgentes():
    ruta = _ruta_objeto("T", DestinoEnrutamiento.COLA_EMERGENCIA.value, False)
    assert ruta == "procesados/urgentes/T.json"


def test_revision_sigue_en_auditoria_aunque_sea_urgente():
    ruta = _ruta_objeto("T", DestinoEnrutamiento.REVISION_HUMANA.value, True)
    assert ruta == "auditoria_humana/T.json"
