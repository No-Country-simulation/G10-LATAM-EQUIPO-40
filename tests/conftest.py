"""Permite probar las reglas sin red, aunque falten las librerías del modelo."""

import importlib.util
import sys
import types
from pathlib import Path

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
