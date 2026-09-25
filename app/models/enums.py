from __future__ import annotations
from enum import Enum

class TipoArchivo(str, Enum):
    PDF = "PDF"
    IMAGE = "IMAGEN"

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