from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

from models.enums import DestinoEnrutamiento, NivelPrioridad, TipoArchivo, TipoDocumento

class Paciente(BaseModel):
    nombre: Optional[str] = None
    edad: Optional[int] = None
    documento_identidad: Optional[str] = None
 
class MedicoSolicitante(BaseModel):
    nombre: Optional[str] = None
    matricula: Optional[str] = None
    especialidad: Optional[str] = None
 
class Medicamento(BaseModel):
    nombre: str
    dosis: Optional[str] = None
    frecuencia: Optional[str] = None
    duracion: Optional[str] = None
 
class Clasificacion(BaseModel):
    tipo_documento: TipoDocumento
    especialidad: Optional[str] = None
    nivel_prioridad: NivelPrioridad
    score_confianza: float = Field(..., ge=0.0, le=1.0)
 
class DatosExtraidos(BaseModel):
    paciente: Optional[Paciente] = None
    medico_solicitante: Optional[MedicoSolicitante] = None
    estudio_realizado: Optional[str] = None
    diagnostico_principal: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    medicamentos: Optional[list[Medicamento]] = None
    estudios_solicitados: Optional[list[str]] = None
    hallazgos_criticos: Optional[list[str]] = None
    campos_faltantes: Optional[list[str]] = None
 
class Notificacion(BaseModel):
    canal: str
    mensaje: str
 
class DecisionEnrutamiento(BaseModel):
    destino: DestinoEnrutamiento
    requiere_revision_humana: bool
    justificacion: str
    notificacion: Optional[Notificacion] = None
 
class AlmacenamientoOCI(BaseModel):
    bucket: str
    ruta: str
    status: str

class EstadoPipeline(BaseModel):
    """Objeto que viaja entre los nodos de la chain."""
    documento_id: str
    canal_origen: str
    tipo_archivo: TipoArchivo
 
    # Contenido procesado por la capa de ingestión
    texto: Optional[str] = None
    imagenes_data_url: Optional[list[str]] = None  # páginas como Data URLs
 
    # Resultados de cada nodo
    clasificacion: Optional[Clasificacion] = None
    datos_extraidos: Optional[DatosExtraidos] = None
    decision: Optional[DecisionEnrutamiento] = None
 
    # Control de flujo
    error: Optional[str] = None
 
class RespuestaTriaje(BaseModel):
    status: str
    documento_id: str
    clasificacion: Optional[Clasificacion] = None
    datos_extraidos: Optional[DatosExtraidos] = None
    decision: Optional[DecisionEnrutamiento] = None
    almacenamiento_oci: Optional[AlmacenamientoOCI] = None
    error_detalle: Optional[str] = None