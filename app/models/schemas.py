"""Esquemas de los datos que se extraen con el agente de 
   Mediflow"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import (
    DestinoEnrutamiento,
    NivelPrioridad,
    TipoArchivo,
    TipoDocumento,
)


class Paciente(BaseModel):
    nombre: str | None = None
    edad: str | None = None
    documento_identidad: str | None = None


class MedicoSolicitante(BaseModel):
    nombre: str | None = None
    matricula: str | None = None
    especialidad: str | None = None


class Medicamento(BaseModel):
    nombre: str
    dosis: str | None = None
    frecuencia: str | None = None
    duracion: str | None = None


class SignosVitales(BaseModel):
    presion_arterial: str | None = Field(
        None, description="Ej: 120/80 mmHg"
    )
    frecuencia_cardiaca: str | None = Field(None, description="Ej: 75 lpm")
    frecuencia_respiratoria: str | None = Field(
        None, description="Ej: 16 rpm"
    )
    saturacion_oxigeno: str | None = Field(None, description="Ej: 98%")
    temperatura: str | None = Field(None, description="Ej: 36.5°C")
    glasgow: str | None = Field(None, description="Ej: 15/15")


class Clasificacion(BaseModel):
    tipo_documento: TipoDocumento
    especialidad: str | None = None
    nivel_prioridad: NivelPrioridad
    score_confianza: float = Field(..., ge=0.0, le=1.0)


class DatosExtraidos(BaseModel):
    paciente: Paciente | None = None
    medico_solicitante: MedicoSolicitante | None = None
    estudio_realizado: str | None = None
    diagnostico_principal: str | None = None
    cie10_sugerido: str | None = None
    signos_vitales: SignosVitales | None = None
    medicamentos: list[Medicamento] | None = None
    estudios_solicitados: list[str] | None = None
    hallazgos_criticos: list[str] | None = None
    campos_faltantes: list[str] | None = None


class Notificacion(BaseModel):
    canal: str
    mensaje: str


class DecisionEnrutamiento(BaseModel):
    destino: DestinoEnrutamiento
    requiere_revision_humana: bool
    justificacion: str
    notificacion: Notificacion | None = None


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
    texto: str | None = None
    imagenes_data_url: list[str] | None = None  # páginas como Data URLs

    # Resultados de cada nodo
    clasificacion: Clasificacion | None = None
    datos_extraidos: DatosExtraidos | None = None
    decision: DecisionEnrutamiento | None = None

    # Control de flujo
    error: str | None = None


class RespuestaTriaje(BaseModel):
    status: str
    documento_id: str
    clasificacion: Clasificacion | None = None
    datos_extraidos: DatosExtraidos | None = None
    decision: DecisionEnrutamiento | None = None
    almacenamiento_oci: AlmacenamientoOCI | None = None
    error_detalle: str | None = None
