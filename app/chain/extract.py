"""
MediFlow - Nodo 2: Extracción de entidades clínicas
Extrae datos estructurados del documento según su tipo.

Modelos:
  - texto  -> command-r-plus-08-2024
  - imagen -> command-a-vision-07-2025
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata

from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage

from app.chain.llm_utils import invocar_con_reintentos
from app.chain.prompts import (
    PROMPT_EXTRAER_IMAGEN,
    PROMPT_EXTRAER_TEXTO,
    SCHEMA_EXTRAER,
    SYSTEM_EXTRAER,
)
from app.models.enums import TipoDocumento
from app.models.schemas import (
    DatosExtraidos,
    EstadoPipeline,
    Medicamento,
    MedicoSolicitante,
    Paciente,
    SignosVitales,
)

logger = logging.getLogger(__name__)

MODELO_TEXTO = "command-r-plus-08-2024"
MODELO_VISION = "command-a-vision-07-2025"


def _get_llm(tiene_texto: bool):
    model = MODELO_TEXTO if tiene_texto else MODELO_VISION
    llm = ChatCohere(model=model, temperature=0.0)
    return llm.bind(
        response_format={"type": "json_object", "json_schema": SCHEMA_EXTRAER}
    )


def _construir_mensajes(estado: EstadoPipeline) -> list:
    system = SystemMessage(content=SYSTEM_EXTRAER)

    if estado.texto:
        prompt = PROMPT_EXTRAER_TEXTO.format(texto=estado.texto[:8000])
        return [system, HumanMessage(content=prompt)]

    content = [{"type": "text", "text": PROMPT_EXTRAER_IMAGEN}]
    for data_url in (estado.imagenes_data_url or [])[:3]:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    return [system, HumanMessage(content=content)]


_RELLENOS = {
    "null",
    "none",
    "nil",
    "n/a",
    "na",
    "n.a",
    "-",
    "--",
    "?",
    "??",
    "???",
    "no disponible",
    "no especificado",
    "no identificado",
    "sin dato",
    "sin datos",
    "desconocido",
    "ilegible",
    "no legible",
    "no aplica",
    "undefined",
    "firma ilegible",
    "sin firma",
    "en blanco",
    "no consta",
    "no especificada",
    "no identificada",
    "no indicado",
    "no indicada",
}

_PALABRAS_ETIQUETA = {
    "medico",
    "medica",
    "solicitante",
    "tratante",
    "responsable",
    "remitente",
    "firmante",
    "doctor",
    "doctora",
    "dr",
    "dra",
    "paciente",
    "nombre",
    "firma",
    "sello",
    "registro",
    "profesional",
    "matricula",
    "mp",
    "reg",
    "rm",
    "numero",
    "no",
    "de",
    "del",
    "documento",
    "identificacion",
    "cedula",
    "cc",
    "especialista",
    "servicio",
}


def _es_etiqueta(valor: str) -> bool:
    toks = _tokens(valor)
    return bool(toks) and all(t in _PALABRAS_ETIQUETA for t in toks)


def _limpiar(valor, descartar_interrogaciones: bool = False):
    if not isinstance(valor, str):
        return valor
    v = valor.strip()
    if not v or not re.search(r"\w", v):
        return None
    if v.lower().strip(" .:;()[]{}\"'") in _RELLENOS:
        return None
    solo_digitos = re.sub(r"[\s.\-]", "", v)
    if re.fullmatch(r"0+|(\d)\1{3,}|1234\d{0,5}", solo_digitos):
        return None
    if descartar_interrogaciones and v.count("?") >= 2:
        return None
    if descartar_interrogaciones and _es_etiqueta(v):
        return None
    return v


def _a_lista(valor) -> list | None:
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        return None
    limpios = [x for x in (_limpiar(i) for i in valor) if isinstance(x, str)]
    return limpios or None


def _a_entero(valor) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str):
        m = re.search(r"\d+", valor)
        return int(m.group()) if m else None
    return None


def _parsear_respuesta(raw: str) -> DatosExtraidos:
    data = json.loads(raw)

    # Paciente
    nombre_paciente = _limpiar(data.get("nombre_paciente"), True)
    edad_paciente = _limpiar(data.get("edad_paciente"))
    doc_paciente = _limpiar(data.get("documento_paciente"), True)
    paciente = (
        Paciente(
            nombre=nombre_paciente,
            edad=edad_paciente,
            documento_identidad=doc_paciente,
        )
        if any([nombre_paciente, edad_paciente, doc_paciente])
        else None
    )

    # Médico
    nombre_medico = _limpiar(data.get("nombre_medico"), True)
    matricula_medico = _limpiar(data.get("matricula_medico"), True)
    especialidad_medico = _limpiar(data.get("especialidad_medico"))
    medico = (
        MedicoSolicitante(
            nombre=nombre_medico,
            matricula=matricula_medico,
            especialidad=especialidad_medico,
        )
        if any([nombre_medico, matricula_medico, especialidad_medico])
        else None
    )

    # Signos Vitales
    pa = _limpiar(data.get("presion_arterial"))
    fc = _limpiar(data.get("frecuencia_cardiaca"))
    fr = _limpiar(data.get("frecuencia_respiratoria"))
    spo2 = _limpiar(data.get("saturacion_oxigeno"))
    temp = _limpiar(data.get("temperatura"))
    glasgow = _limpiar(data.get("glasgow"))

    signos_vitales = (
        SignosVitales(
            presion_arterial=pa,
            frecuencia_cardiaca=fc,
            frecuencia_respiratoria=fr,
            saturacion_oxigeno=spo2,
            temperatura=temp,
            glasgow=glasgow,
        )
        if any([pa, fc, fr, spo2, temp, glasgow])
        else None
    )

    # Medicamentos
    meds_raw = data.get("medicamentos") or []
    if not isinstance(meds_raw, list):
        meds_raw = []
    medicamentos = [
        Medicamento(
            nombre=_limpiar(med.get("nombre")),
            dosis=_limpiar(med.get("dosis")),
            frecuencia=_limpiar(med.get("frecuencia")),
            duracion=_limpiar(med.get("duracion")),
        )
        for med in meds_raw
        if isinstance(med, dict) and _limpiar(med.get("nombre"))
    ] or None

    return DatosExtraidos(
        paciente=paciente,
        medico_solicitante=medico,
        estudio_realizado=_limpiar(data.get("estudio_realizado")),
        diagnostico_principal=_limpiar(data.get("diagnostico_principal")),
        cie10_sugerido=_limpiar(data.get("cie10_sugerido")),
        signos_vitales=signos_vitales,
        medicamentos=medicamentos,
        estudios_solicitados=_a_lista(data.get("estudios_solicitados")),
        hallazgos_criticos=_a_lista(data.get("hallazgos_criticos")),
        campos_faltantes=_a_lista(data.get("campos_faltantes")),
    )


def _tokens(texto: str) -> list[str]:
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(c)
    )
    return re.findall(r"[a-z0-9]+", sin_tildes)


def _respaldado(
    valor: str,
    tokens_texto: set[str],
    minimo: float = 0.6,
    largo_min: int = 3,
    solo_alfa: bool = False,
) -> bool:
    toks: list[str] = []
    for t in _tokens(valor):
        if t.isdigit():
            if not solo_alfa:
                toks.append(t)
        elif len(t) >= largo_min and not any(ch.isdigit() for ch in t):
            toks.append(t)
    if not toks:
        return True
    return sum(t in tokens_texto for t in toks) / len(toks) >= minimo


def verificar_contra_texto(datos: DatosExtraidos, texto: str) -> list[str]:
    """Descarta (pone en None) lo que no aparece en el texto. Devuelve qué se
    descartó."""
    tokens_texto = set(_tokens(texto))
    descartados: list[str] = []

    def ok(valor, **kw) -> bool:
        return _respaldado(valor, tokens_texto, **kw)

    pac = datos.paciente
    if pac:
        if pac.nombre and not ok(pac.nombre):
            pac.nombre = None
            descartados.append("nombre del paciente")
        if pac.documento_identidad and not ok(
            pac.documento_identidad, minimo=1.0
        ):
            pac.documento_identidad = None
            descartados.append("documento del paciente")
        if pac.edad and not re.search(rf"(?<!\d){pac.edad}(?!\d)", texto):
            pac.edad = None
            descartados.append("edad")
        if not (pac.nombre or pac.documento_identidad or pac.edad):
            datos.paciente = None

    med = datos.medico_solicitante
    if med:
        if med.nombre and not ok(med.nombre):
            med.nombre = None
            descartados.append("nombre del médico")
        if med.matricula and not ok(med.matricula, minimo=1.0):
            med.matricula = None
            descartados.append("matrícula")
        if not (med.nombre or med.matricula or med.especialidad):
            datos.medico_solicitante = None

    if datos.diagnostico_principal and not ok(
        datos.diagnostico_principal, minimo=0.5, largo_min=4
    ):
        datos.diagnostico_principal = None
        descartados.append("diagnóstico")
    if datos.estudio_realizado and not ok(datos.estudio_realizado, minimo=0.6):
        datos.estudio_realizado = None
        descartados.append("estudio realizado")

    if datos.medicamentos:
        validos = [
            m
            for m in datos.medicamentos
            if m.nombre
            and ok(m.nombre, minimo=1.0, largo_min=5, solo_alfa=True)
        ]
        if len(validos) < len(datos.medicamentos):
            descartados.append("medicamentos")
        datos.medicamentos = validos or None

    if datos.estudios_solicitados:
        validos_e = [
            e
            for e in datos.estudios_solicitados
            if ok(e, minimo=0.6, largo_min=4)
        ]
        if len(validos_e) < len(datos.estudios_solicitados):
            descartados.append("estudios solicitados")
        datos.estudios_solicitados = validos_e or None

    return descartados


# Campos obligatorios por tipo de documento.
# En HOJA_TRIAJE solo se exige paciente: el diagnóstico formal aún no existe al
# momento del ingreso.

_OBLIGATORIOS: dict[TipoDocumento, list[str]] = {
    TipoDocumento.RECETA_MEDICA: [
        "paciente",
        "médico",
        "matrícula",
        "medicamentos",
    ],
    TipoDocumento.INFORME_IMAGENES: [
        "paciente",
        "médico",
        "estudio realizado",
        "diagnóstico",
    ],
    TipoDocumento.INFORME_LABORATORIO: [
        "paciente",
        "médico",
        "estudio realizado",
    ],
    TipoDocumento.ORDEN_PROCEDIMIENTO: [
        "paciente",
        "médico",
        "matrícula",
        "estudios solicitados",
    ],
    TipoDocumento.EPICRISIS: ["paciente", "médico", "diagnóstico"],
    TipoDocumento.CERTIFICADO_MEDICO: ["paciente", "médico", "matrícula"],
    TipoDocumento.HOJA_TRIAJE: ["paciente"],
    TipoDocumento.DESCONOCIDO: ["paciente", "médico"],
}


def _presente(datos: DatosExtraidos, campo: str) -> bool:
    pac, med = datos.paciente, datos.medico_solicitante
    if campo == "paciente":
        return bool(pac and pac.nombre)
    if campo == "médico":
        return bool(med and med.nombre)
    if campo == "matrícula":
        return bool(med and med.matricula)
    if campo == "estudio realizado":
        return bool(datos.estudio_realizado)
    if campo == "diagnóstico":
        return bool(datos.diagnostico_principal or datos.hallazgos_criticos)
    if campo == "medicamentos":
        return bool(datos.medicamentos)
    if campo == "estudios solicitados":
        return bool(datos.estudios_solicitados)
    return True


def calcular_faltantes(
    datos: DatosExtraidos, tipo: TipoDocumento
) -> list[str] | None:
    obligatorios = _OBLIGATORIOS.get(
        tipo, _OBLIGATORIOS[TipoDocumento.DESCONOCIDO]
    )
    faltantes = [c for c in obligatorios if not _presente(datos, c)]
    return faltantes or None


def segunda_pasada_activada() -> bool:
    return os.getenv("MEDIFLOW_SEGUNDA_PASADA", "1") != "0"


_CLAVES_POR_CAMPO = {
    "paciente": ["nombre_paciente"],
    "médico": ["nombre_medico"],
    "matrícula": ["matricula_medico"],
    "estudio realizado": ["estudio_realizado"],
    "diagnóstico": ["diagnostico_principal"],
    "medicamentos": ["medicamentos"],
    "estudios solicitados": ["estudios_solicitados"],
}

_PISTAS = {
    "nombre_paciente": 'nombre del paciente ("Paciente:", nombres propios)',
    "nombre_medico": 'nombre del médico ("Dr.", "Dra.", "Médico:", "Solicitante:", o junto a la firma o el sello)',
    "matricula_medico": 'matrícula o registro profesional del médico ("MP", "Reg.", "Matrícula")',
    "estudio_realizado": "estudio cuyo resultado reporta el documento",
    "diagnostico_principal": 'diagnóstico en una línea breve ("Diagnóstico", "Dx", "Conclusión", "Diagnóstico de egreso")',
    "medicamentos": "medicamentos con nombre, dosis, frecuencia y duración",
    "estudios_solicitados": "estudios o procedimientos que el documento solicita",
}

SYSTEM_COMPLETAR = """Eres un extractor de entidades clínicas. En una primera
                    lectura no se encontraron algunos datos. Busca SOLO los 
                    datos que se piden, leyendo todo el documento, incluidos 
                    sellos, firmas y pies de página.

                    REGLAS:
                    - Extrae EXACTAMENTE lo que está escrito. NUNCA inventes ni 
                        uses valores de ejemplo.
                    - Si un dato realmente NO aparece, omite ese campo.
                    - Responde ÚNICAMENTE con el JSON."""


def _get_llm_completar(schema: dict):
    llm = ChatCohere(model=MODELO_TEXTO, temperature=0.0)
    return llm.bind(
        response_format={"type": "json_object", "json_schema": schema}
    )


def _esquema_parcial(claves: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {k: SCHEMA_EXTRAER["properties"][k] for k in claves},
        "required": claves,
    }


def _fusionar(datos: DatosExtraidos, nuevo: DatosExtraidos) -> list[str]:
    recuperados: list[str] = []

    if (
        not (datos.paciente and datos.paciente.nombre)
        and nuevo.paciente
        and nuevo.paciente.nombre
    ):
        datos.paciente = datos.paciente or Paciente()
        datos.paciente.nombre = nuevo.paciente.nombre
        recuperados.append("paciente")

    nm = nuevo.medico_solicitante
    if (
        nm
        and nm.nombre
        and not (datos.medico_solicitante and datos.medico_solicitante.nombre)
    ):
        datos.medico_solicitante = (
            datos.medico_solicitante or MedicoSolicitante()
        )
        datos.medico_solicitante.nombre = nm.nombre
        recuperados.append("médico")
    if (
        nm
        and nm.matricula
        and not (
            datos.medico_solicitante and datos.medico_solicitante.matricula
        )
    ):
        datos.medico_solicitante = (
            datos.medico_solicitante or MedicoSolicitante()
        )
        datos.medico_solicitante.matricula = nm.matricula
        recuperados.append("matrícula")

    if not datos.signos_vitales and nuevo.signos_vitales:
        datos.signos_vitales = nuevo.signos_vitales

    for campo, etiqueta in (
        ("estudio_realizado", "estudio realizado"),
        ("diagnostico_principal", "diagnóstico"),
        ("medicamentos", "medicamentos"),
        ("estudios_solicitados", "estudios solicitados"),
    ):
        if not getattr(datos, campo) and getattr(nuevo, campo):
            setattr(datos, campo, getattr(nuevo, campo))
            recuperados.append(etiqueta)

    return recuperados


def aplicar_faltantes(estado: EstadoPipeline) -> None:
    if not estado.datos_extraidos or estado.error:
        return
    tipo = (
        estado.clasificacion.tipo_documento
        if estado.clasificacion
        else TipoDocumento.DESCONOCIDO
    )
    estado.datos_extraidos.campos_faltantes = calcular_faltantes(
        estado.datos_extraidos, tipo
    )


def completar_extraccion(estado: EstadoPipeline) -> list[str]:
    datos = estado.datos_extraidos
    if (
        not datos
        or not datos.campos_faltantes
        or not (estado.texto and estado.texto.strip())
    ):
        return []

    claves = [
        k
        for campo in datos.campos_faltantes
        for k in _CLAVES_POR_CAMPO.get(campo, [])
    ]
    if not claves:
        return []

    logger.info(
        f"[EXTRAER] {estado.documento_id}: segunda pasada para {datos.campos_faltantes}"
    )
    try:
        pistas = "\n".join(f"- {k}: {_PISTAS[k]}" for k in claves)
        prompt = (
            f"DATOS A BUSCAR:\n{pistas}\n\nDOCUMENTO:\n{estado.texto[:8000]}"
        )
        response = invocar_con_reintentos(
            _get_llm_completar(_esquema_parcial(claves)),
            [
                SystemMessage(content=SYSTEM_COMPLETAR),
                HumanMessage(content=prompt),
            ],
        )
        if os.getenv("MEDIFLOW_DEBUG_RAW") == "1":
            logger.info(
                f"[EXTRAER] segunda pasada, respuesta cruda: {response.content}"
            )

        nuevo = _parsear_respuesta(response.content)
        verificar_contra_texto(nuevo, estado.texto)
        recuperados = _fusionar(datos, nuevo)
    except Exception as e:
        logger.warning(
            f"""[EXTRAER] {estado.documento_id}: la segunda pasada falló ({e}); 
                se sigue sin ella."""
        )
        return []

    aplicar_faltantes(estado)
    logger.info(
        f"[EXTRAER] {estado.documento_id}: segunda pasada recuperó {recuperados} | "
        f"faltantes ahora={estado.datos_extraidos.campos_faltantes or []}"
    )
    return recuperados


def nodo_extraer(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Nodo 2 del pipeline.
    Recibe EstadoPipeline, puebla estado.datos_extraidos y lo devuelve.
    """
    logger.info(
        "[EXTRAER] Extrayendo entidades clínicas de %s", estado.documento_id
    )

    tiene_texto = bool(estado.texto and estado.texto.strip())

    try:
        llm = _get_llm(tiene_texto)
        mensajes = _construir_mensajes(estado)
        response = invocar_con_reintentos(llm, mensajes)

        if os.getenv("MEDIFLOW_DEBUG_RAW") == "1":
            logger.info(f"[EXTRAER] respuesta cruda: {response.content}")

        estado.datos_extraidos = _parsear_respuesta(response.content)

        if tiene_texto:
            descartados = verificar_contra_texto(
                estado.datos_extraidos, estado.texto
            )
            if descartados:
                logger.warning(
                    f"[EXTRAER] {estado.documento_id}: datos sin respaldo en el texto, "
                    f"descartados: {descartados}"
                )

        tipo = (
            estado.clasificacion.tipo_documento
            if estado.clasificacion
            else TipoDocumento.DESCONOCIDO
        )
        estado.datos_extraidos.campos_faltantes = calcular_faltantes(
            estado.datos_extraidos, tipo
        )

        paciente_nombre = (
            estado.datos_extraidos.paciente.nombre
            if estado.datos_extraidos.paciente
            else "no identificado"
        )
        faltantes = estado.datos_extraidos.campos_faltantes or []

        logger.info(
            f"[EXTRAER] paciente={paciente_nombre} | "
            f"dx={estado.datos_extraidos.diagnostico_principal} | "
            f"faltantes={faltantes}"
        )

    except Exception as e:
        logger.error(f"[EXTRAER] Error: {e}")
        estado.error = str(e)
        estado.datos_extraidos = DatosExtraidos(
            campos_faltantes=[
                "Error en extracción: respuesta inesperada del modelo"
            ]
        )

    return estado
