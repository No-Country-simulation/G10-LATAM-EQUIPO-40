import smtplib

import pytest

from app.models.enums import DestinoEnrutamiento, NivelPrioridad, TipoDocumento
from app.notifications import alertas


def resultado(destino=DestinoEnrutamiento.HISTORIA_CLINICA, prioridad=NivelPrioridad.NORMAL, **decision):
    return {
        "documento_id": "DOC-1",
        "clasificacion": {
            "tipo_documento": TipoDocumento.EPICRISIS,
            "nivel_prioridad": prioridad,
        },
        "datos_extraidos": {
            "paciente": {"nombre": "Ana Soto"},
            "diagnostico_principal": "Diagnostico secreto",
        },
        "decision": {
            "destino": destino,
            "requiere_revision_humana": False,
            "justificacion": "Hallazgo en Ana Soto",
            "notificacion": {"mensaje": "ALERTA Ana Soto"},
            **decision,
        },
    }


class SmtpFalso:
    enviados: list = []
    falla = False

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, **kwargs):
        pass

    def login(self, *args):
        pass

    def send_message(self, correo):
        if SmtpFalso.falla:
            raise smtplib.SMTPException("clave-secreta")
        SmtpFalso.enviados.append(correo)


@pytest.fixture
def smtp(monkeypatch):
    SmtpFalso.enviados = []
    SmtpFalso.falla = False
    monkeypatch.setattr(alertas.smtplib, "SMTP", SmtpFalso)
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.test")
    monkeypatch.setenv("SMTP_USUARIO", "mediflow@ejemplo.test")
    monkeypatch.setenv("ALERTA_DESTINATARIOS", "equipo@ejemplo.test")
    monkeypatch.delenv("ALERTA_DESTINATARIOS_URGENTES", raising=False)
    return SmtpFalso


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        (resultado(DestinoEnrutamiento.COLA_EMERGENCIA, NivelPrioridad.ALTA), "urgente"),
        (resultado(prioridad=NivelPrioridad.URGENTE), "urgente"),
        (resultado(DestinoEnrutamiento.REVISION_HUMANA, revision_prioritaria=True), "prioritaria"),
        (resultado(DestinoEnrutamiento.REVISION_HUMANA, requiere_revision_humana=True), "revision"),
        (resultado(), "completado"),
        ({"documento_id": "DOC-1"}, "error"),
    ],
)
def test_clasifica_eventos(datos, esperado):
    assert alertas.clasificar_evento(datos) == esperado


def test_envia_correo_sin_datos_clinicos(smtp):
    r = alertas.notificar_documento(
        resultado(DestinoEnrutamiento.COLA_EMERGENCIA, NivelPrioridad.URGENTE), "Guardia"
    )
    correo = smtp.enviados[0]
    assert r == {"estado": "enviado", "evento": "urgente"}
    assert correo["Subject"] == "[MediFlow][URGENTE] DOC-1"
    texto = correo.as_string() + correo.get_content()
    assert "Cola_Emergencia_Medica" in correo.get_content()
    assert "Ana Soto" not in texto
    assert "Diagnostico secreto" not in texto


def test_urgencias_suman_lista_propia(smtp, monkeypatch):
    monkeypatch.setenv("ALERTA_DESTINATARIOS_URGENTES", "guardia@ejemplo.test, equipo@ejemplo.test")
    assert alertas.destinatarios("urgente") == ["equipo@ejemplo.test", "guardia@ejemplo.test"]
    assert alertas.destinatarios("completado") == ["equipo@ejemplo.test"]


def test_sin_configuracion_no_envia(smtp, monkeypatch):
    monkeypatch.delenv("SMTP_HOST")
    assert alertas.notificar_documento(resultado(), "x")["estado"] == "no_configurado"
    assert smtp.enviados == []


def test_falla_de_smtp_no_rompe_ni_filtra_el_error(smtp, caplog):
    smtp.falla = True
    assert alertas.notificar_documento(resultado(), "x")["estado"] == "error"
    assert "clave-secreta" not in caplog.text


def test_bridge_agrega_estado_de_alerta(monkeypatch):
    import app.streamlit_bridge as bridge

    monkeypatch.setattr(bridge, "marcar_como_recibido", lambda *a: None)
    monkeypatch.setattr(bridge, "guardar_original", lambda *a: "ruta")
    monkeypatch.setattr(bridge, "ejecutar_pipeline", lambda e: e)
    monkeypatch.setattr(bridge, "_persistir", lambda *a: None)
    llamadas = []
    monkeypatch.setattr(
        bridge,
        "notificar_documento",
        lambda r, c: llamadas.append(c) or {"estado": "enviado"},
    )
    salida = bridge.procesar_texto("DOC-1", "Guardia", "texto")
    assert salida["alerta"] == {"estado": "enviado"}
    assert llamadas == ["Guardia"]
