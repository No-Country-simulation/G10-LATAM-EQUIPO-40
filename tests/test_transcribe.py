from app.chain.transcribe import ocr_primero_activado


def test_una_pagina_usa_lectura_directa(monkeypatch):
    monkeypatch.delenv("MEDIFLOW_OCR_PRIMERO", raising=False)
    assert ocr_primero_activado(1) is False


def test_varias_paginas_activan_ocr(monkeypatch):
    monkeypatch.delenv("MEDIFLOW_OCR_PRIMERO", raising=False)
    assert ocr_primero_activado(2) is True


def test_varias_paginas_activan_ocr_aunque_el_flag_este_en_cero(monkeypatch):
    monkeypatch.setenv("MEDIFLOW_OCR_PRIMERO", "0")
    assert ocr_primero_activado(3) is True


def test_flag_fuerza_ocr_en_una_pagina(monkeypatch):
    monkeypatch.setenv("MEDIFLOW_OCR_PRIMERO", "1")
    assert ocr_primero_activado(1) is True
