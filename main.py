import os
from dotenv import load_dotenv

load_dotenv()

# Usar cohere con langchain
# pip install -q langchain langchain-cohere langchain-community(optional) langchain-core

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

from langchain_cohere import ChatCohere
from langchain_core.messages import AIMessage, HumanMessage

# Define the Cohere LLM
# llm = ChatCohere(
#     cohere_api_key=COHERE_API_KEY, 
#     model="command-a-03-2025",
#     temperature=0.7
# )

# respuesta = llm.invoke("Cúal es la capital de Francia?")
# print(respuesta.content)

import base64, mimetypes
from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage

def to_data_url(path):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"

llm = ChatCohere(
    cohere_api_key=COHERE_API_KEY,
    model="command-a-vision-07-2025",
)

schema = {
    "title": "DocumentoMedico",
    "type": "object",
    "properties": {
        "paciente": {"type": "string"},
        "fecha": {"type": "string"},
        "medico": {"type": "string"},
        "diagnostico": {"type": "string"},
        "medicamentos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["paciente", "fecha"],
}

msg = HumanMessage(content=[
    {"type": "text", "text": "Extrae los campos del documento. Si un campo no aparece, déjalo vacío. No inventes datos."},
    {"type": "image_url", "image_url": {"url": to_data_url("./imagenes_de_muestra/documento.jpg")}},
])

res = llm.invoke([msg], response_format={"type": "json_object", "schema": schema})
print(res.content)