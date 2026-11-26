"""Pruebas del indicador de progreso de Streamlit."""

from __future__ import annotations

import logging

from app.ui_progreso import StreamlitHandler, _traducir


class _Placeholder:
    def __init__(self):
        self.html: list[str] = []

    def markdown(self, html: str, unsafe_allow_html: bool = False):
        self.html.append(html)


def _record(
    mensaje: str, name: str = "app.chain.pipeline"
) -> logging.LogRecord:
    return logging.LogRecord(
        name, logging.INFO, __file__, 1, mensaje, None, None
    )


def test_traduce_logs_conocidos():
    assert (
        _traducir("[PIPELINE] ══ Iniciando triaje: X")
        == "Iniciando triaje del documento…"
    )
    assert (
        _traducir("[CLASIFICAR] Iniciando")
        == "Clasificando el documento y leyendo sus datos…"
    )
    assert _traducir("mensaje irrelevante") is None


def test_solo_renderiza_la_frase_actual(capsys):
    ph = _Placeholder()
    handler = StreamlitHandler(ph)

    handler.emit(_record("[PIPELINE] ══ Iniciando triaje: DEMO-003"))
    assert "Iniciando triaje" in ph.html[-1]

    handler.emit(_record("[CLASIFICAR] Iniciando clasificación de DEMO-003"))
    assert "Clasificando" in ph.html[-1]
    assert "Iniciando triaje" not in ph.html[-1]

    # La misma frase no vuelve a repintar el placeholder.
    antes = len(ph.html)
    handler.emit(_record("[CLASIFICAR] Iniciando clasificación de DEMO-003"))
    assert len(ph.html) == antes

    # Ya no se imprime el log desde el handler (evita duplicados en consola).
    assert "LOG:" not in capsys.readouterr().out


def test_respeta_logger_objetivo():
    ph = _Placeholder()
    handler = StreamlitHandler(ph, logger_objetivo="app.chain.pipeline")

    handler.emit(_record("[CLASIFICAR] Iniciando", name="app.chain.classify"))
    assert ph.html == []

    handler.emit(_record("[PIPELINE] ══ Iniciando", name="app.chain.pipeline"))
    assert len(ph.html) == 1
