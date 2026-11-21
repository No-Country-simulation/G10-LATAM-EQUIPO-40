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


def test_razonamiento_con_ejemplo_json_en_el_texto():
    """command-a-plus puede razonar en el bloque de texto pese a thinking=disabled.

    El ejemplo de JSON del razonamiento no debe ganarle a la respuesta final.
    """
    respuesta = _Respuesta(
        "Analizo el documento. Podría ser:\n"
        '{"tipo_documento": "RECETA_MEDICA", "score_confianza": 0.1}\n'
        "pero la orden de procedimiento es más específica.\n"
        '{"tipo_documento": "ORDEN_PROCEDIMIENTO", "score_confianza": 0.9}'
    )
    assert parsear_json(respuesta) == {
        "tipo_documento": "ORDEN_PROCEDIMIENTO",
        "score_confianza": 0.9,
    }


def test_razonamiento_con_json_parcial_antes_de_la_respuesta():
    respuesta = _Respuesta(
        'Así quedaría el JSON:\n{"tipo_documento": "ORDEN_PROCEDIMIENTO",\n'
        '...y la respuesta final es:\n{"tipo_documento": "ORDEN_PROCEDIMIENTO"}'
    )
    assert parsear_json(respuesta) == {"tipo_documento": "ORDEN_PROCEDIMIENTO"}


def test_respuestas_json_duplicadas_devuelve_la_ultima():
    respuesta = _Respuesta('{\n  "a": 1\n}{"a": 2}')
    assert parsear_json(respuesta) == {"a": 2}


def test_json_anidado_no_devuelve_el_hijo():
    respuesta = _Respuesta('{"a": {"b": 1}, "c": 2}')
    assert parsear_json(respuesta) == {"a": {"b": 1}, "c": 2}
