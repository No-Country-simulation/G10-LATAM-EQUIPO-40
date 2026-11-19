"""Pruebas del parseo de respuestas del modelo."""

from app.chain.llm_utils import parsear_json, texto_de_respuesta


class _Respuesta:
    def __init__(self, content, finish_reason="COMPLETE"):
        self.content = content
        self.response_metadata = {"finish_reason": finish_reason}


def test_texto_plano():
    assert parsear_json('{"a": 1}') == {"a": 1}


def test_ignora_bloque_de_razonamiento():
    respuesta = _Respuesta(
        [
            {"type": "reasoning", "summary": [{"text": "pienso..."}]},
            {"type": "text", "text": '{"tipo_documento": "RECETA_MEDICA"}'},
        ]
    )
    assert parsear_json(respuesta) == {"tipo_documento": "RECETA_MEDICA"}


def test_texto_de_respuesta_descarta_razonamiento():
    respuesta = _Respuesta(
        [
            {"type": "reasoning", "summary": [{"text": "pienso..."}]},
            {"type": "text", "text": '{"a": 1}'},
        ]
    )
    assert texto_de_respuesta(respuesta) == '{"a": 1}'


def test_quita_cerca_markdown():
    respuesta = _Respuesta('```json\n{"a": 1}\n```')
    assert parsear_json(respuesta) == {"a": 1}


def test_ignora_texto_alrededor():
    respuesta = _Respuesta('Aquí está el JSON:\n{"a": 1}\nListo.')
    assert parsear_json(respuesta) == {"a": 1}


def test_respuesta_vacia_falla():
    try:
        parsear_json(_Respuesta(""))
    except ValueError as e:
        assert "vacía" in str(e)
    else:
        raise AssertionError("debió fallar con una respuesta vacía")


def test_json_invalido_reporta_finish_reason():
    respuesta = _Respuesta('{"a": 1', finish_reason="MAX_TOKENS")
    try:
        parsear_json(respuesta)
    except ValueError as e:
        assert "MAX_TOKENS" in str(e)
    else:
        raise AssertionError("debió fallar con un JSON truncado")


def test_solo_razonamiento_sin_texto_falla():
    respuesta = _Respuesta(
        [{"type": "reasoning", "summary": [{"text": "pienso..."}]}]
    )
    try:
        parsear_json(respuesta)
    except ValueError as e:
        assert "vacía" in str(e)
    else:
        raise AssertionError("debió fallar sin bloque de texto")
