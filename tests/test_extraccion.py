from app.chain.extract import verificar_contra_texto
from app.models.schemas import DatosExtraidos, Medicamento, Paciente

TEXTO = "Paciente: Ana Soto, 45 años. Metformina 850 mg cada 12 horas."


def test_descarta_dosis_y_frecuencia_alteradas():
    med = Medicamento(nombre="Metformina", dosis="8500mg", frecuencia="cada 2 horas")
    datos = DatosExtraidos(medicamentos=[med])
    descartados = verificar_contra_texto(datos, TEXTO)
    assert med.dosis is None and med.frecuencia is None
    assert "dosis de Metformina" in descartados
    assert "frecuencia de Metformina" in descartados


def test_conserva_dosis_presentes_en_el_texto():
    med = Medicamento(nombre="Metformina", dosis="850mg", frecuencia="cada 12 horas")
    assert verificar_contra_texto(DatosExtraidos(medicamentos=[med]), TEXTO) == []
    assert med.dosis == "850mg"


def test_decimal_con_coma_o_punto():
    med = Medicamento(nombre="Levotiroxina", dosis="0.5 mg")
    assert verificar_contra_texto(
        DatosExtraidos(medicamentos=[med]), "Levotiroxina 0,5 mg"
    ) == []


def test_edad_con_caracteres_especiales_no_rompe():
    datos = DatosExtraidos(paciente=Paciente(nombre="Ana Soto", edad="45 (años"))
    verificar_contra_texto(datos, TEXTO)
    assert datos.paciente.edad is None
