from app.chain.transcribe import ocr_primero_activado


def test_ocr_primero_activo_por_defecto(monkeypatch):
    monkeypatch.delenv("MEDIFLOW_OCR_PRIMERO", raising=False)
    assert ocr_primero_activado() is True


def test_ocr_primero_se_puede_desactivar(monkeypatch):
    monkeypatch.setenv("MEDIFLOW_OCR_PRIMERO", "0")
    assert ocr_primero_activado() is False


def test_ocr_primero_activo_con_uno(monkeypatch):
    monkeypatch.setenv("MEDIFLOW_OCR_PRIMERO", "1")
    assert ocr_primero_activado() is True
