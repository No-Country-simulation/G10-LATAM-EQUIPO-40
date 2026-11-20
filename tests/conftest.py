"""Permite probar las reglas sin red, aunque falten las librerías del modelo."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if importlib.util.find_spec("langchain_cohere") is None:
    cohere = types.ModuleType("langchain_cohere")
    cohere.ChatCohere = object
    core = types.ModuleType("langchain_core")
    messages = types.ModuleType("langchain_core.messages")
    messages.HumanMessage = messages.SystemMessage = object
    sys.modules.update(
        {
            "langchain_cohere": cohere,
            "langchain_core": core,
            "langchain_core.messages": messages,
        }
    )

if importlib.util.find_spec("pdfplumber") is None:
    sys.modules["pdfplumber"] = types.ModuleType("pdfplumber")


@pytest.fixture(autouse=True)
def _sin_gate_medico(monkeypatch):
    """Los tests existentes no deben llamar al modelo por el gate médico."""
    from app.chain import pipeline

    monkeypatch.setattr(
        pipeline, "nodo_validar_documento_medico", lambda estado: estado
    )
