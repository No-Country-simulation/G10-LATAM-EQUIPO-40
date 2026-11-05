from app.storage.revision import ordenar_cola


def item(doc, prioridad="Normal", **decision):
    return {
        "documento_id": doc,
        "clasificacion": {"nivel_prioridad": prioridad},
        "decision": decision,
    }


def test_sospechas_criticas_van_primero():
    cola = ordenar_cola(
        [
            item("A"),
            item("B", "Baja", revision_prioritaria=True),
            item("C", "Alta"),
        ]
    )
    assert [i["documento_id"] for i in cola] == ["B", "C", "A"]


def test_reconoce_expedientes_antiguos_por_su_motivo():
    antiguo = item("Z", justificacion="Posible hallazgo crítico sin prioridad urgente")
    assert ordenar_cola([item("A"), antiguo])[0]["documento_id"] == "Z"
