from datetime import datetime, timezone

import pytest

from assistente.strumenti import crea_strumento_orologio, descrivi_ora

ISTANTE = datetime(2026, 10, 26, 9, 30, 5, tzinfo=timezone.utc)


def adesso():
    return ISTANTE


def test_tokyo():
    assert descrivi_ora("Asia/Tokyo", adesso) == "2026-10-26T18:30:05+09:00 (Asia/Tokyo)"


def test_roma_dopo_cambio_ora():  # 25 ottobre 2026: Roma torna a +01:00
    assert descrivi_ora("Europe/Rome", adesso) == "2026-10-26T10:30:05+01:00 (Europe/Rome)"


@pytest.mark.parametrize("fuso", ["Tokyo", "GMT+9", "", "../etc/passwd"])
def test_fuso_non_valido_restituisce_errore(fuso):
    risultato = descrivi_ora(fuso, adesso)
    assert risultato.startswith("Errore:") and "Europe/Rome" in risultato


def test_strumento_langchain():
    strumento = crea_strumento_orologio(adesso)
    assert strumento.name == "ora_corrente"
    assert strumento.args_schema.model_json_schema()["required"] == ["fuso_orario"]
    assert strumento.invoke({"fuso_orario": "Asia/Tokyo"}).startswith("2026-10-26T18:30:05")
