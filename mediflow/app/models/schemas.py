from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class TipoArchivo(str, Enum):
    PDF    = "PDF"
    IMAGEN = "IMAGEN"

class TipoDocumento(str, Enum):
    RECETA_MEDICA      = "Receta Médica"
    INFORME_IMAGENES   = "Informe de Estudio por Imágenes"
    INFORME_LABORATORIO = "Informe de Laboratorio"
    ORDEN_PROCEDIMIENTO = "Orden de Solicitud de Procedimiento"
    EPICRISIS          = "Epicrisis / Informe de Alta"
    CERTIFICADO_MEDICO = "Certificado Médico"
    DESCONOCIDO        = "Desconocido"

class NivelPrioridad(str, Enum):
    URGENTE = "Urgente"
    ALTA    = "Alta"
    NORMAL  = "Normal"
    BAJA    = "Baja"

class DestinoEnrutamiento(str, Enum):
    COLA_EMERGENCIA         = "Cola_Emergencia_Medica"
    AUDITORIA_AUTORIZACIONES = "Auditoria_Autorizaciones"
    FARMACIA                = "Farmacia_Hospitalaria"
    HISTORIA_CLINICA        = "Historia_Clinica_Electronica"
    REVISION_HUMANA         = "Cola_Revision_Humana"

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

    texto: Optional[str] = None
    imagenes_b64: Optional[list[str]] = None 

    clasificacion: Optional[Clasificacion] = None
    datos_extraidos: Optional[DatosExtraidos] = None
    decision: Optional[DecisionEnrutamiento] = None

    error: Optional[str] = None

class RespuestaTriaje(BaseModel):
    status: str 
    documento_id: str
    clasificacion: Optional[Clasificacion] = None
    datos_extraidos: Optional[DatosExtraidos] = None
    decision: Optional[DecisionEnrutamiento] = None
    almacenamiento_oci: Optional[AlmacenamientoOCI] = None
    error_detalle: Optional[str] = None