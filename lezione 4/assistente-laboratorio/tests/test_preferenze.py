"""Preferenze dell'utente: validazione, testo per il prompt, lettura del file con predefinite."""
import json

import pytest

from assistente.preferenze import (
    PREDEFINITE, ErrorePreferenze, Preferenze, crea_lettore_file, da_json, prompt_preferenze)


def test_predefinite():
    assert PREDEFINITE == Preferenze(lingua="it", fuso_orario="Europe/Rome", stile="sintetico")


def test_json_completo_e_parziale():
    p = da_json('{"lingua": "en", "fuso_orario": "America/New_York", "stile": "dettagliato"}')
    assert p == Preferenze(lingua="en", fuso_orario="America/New_York", stile="dettagliato")
    assert da_json('{"fuso_orario": "Asia/Tokyo"}') == Preferenze(fuso_orario="Asia/Tokyo")


@pytest.mark.parametrize("testo, motivo", [
    ("non è json", "JSON non valido"),
    ("[1, 2]", "oggetto"),
    ('{"lingua": "klingon"}', "lingua"),
    ('{"fuso_orario": "Marte/Base"}', "fuso_orario"),
    ('{"stile": "poetico"}', "stile"),
    ('{"nome": "Anna"}', "nome"),  # campi non previsti: rifiutati
])
def test_json_non_valido(testo, motivo):
    with pytest.raises(ErrorePreferenze, match=motivo):
        da_json(testo)


def test_prompt_con_le_preferenze():
    testo = prompt_preferenze(Preferenze(lingua="en", fuso_orario="America/New_York",
                                        stile="dettagliato"))
    assert testo.startswith("Preferenze dell'utente")
    assert "inglese" in testo and "America/New_York" in testo and "dettagliat" in testo
    assert "senza chiederlo" in testo  # il fuso predefinito evita la domanda sul luogo
    assert "sintetic" in prompt_preferenze(PREDEFINITE)


def test_lettore_file_valido(tmp_path, caplog):
    caplog.set_level("INFO")
    file = tmp_path / "preferenze.json"
    file.write_text(json.dumps({"lingua": "en", "stile": "dettagliato"}), encoding="utf-8")
    assert crea_lettore_file(file)() == Preferenze(lingua="en", stile="dettagliato")
    assert f"preferenze: lettura del file {file} -> lingua=en fuso_orario=Europe/Rome " \
           "stile=dettagliato" in caplog.text


@pytest.mark.parametrize("contenuto", [None, "", '{"stile": "poetico"}'])
def test_lettore_file_assente_o_non_valido_usa_le_predefinite(tmp_path, caplog, contenuto):
    file = tmp_path / "preferenze.json"
    if contenuto is not None:
        file.write_text(contenuto, encoding="utf-8")
    assert crea_lettore_file(file)() == PREDEFINITE
    avvisi = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(avvisi) == 1 and "uso le predefinite" in avvisi[0].getMessage()


def test_lettore_rilegge_a_ogni_chiamata(tmp_path):
    file = tmp_path / "preferenze.json"
    file.write_text('{"lingua": "en"}', encoding="utf-8")
    leggi = crea_lettore_file(file)
    assert leggi().lingua == "en"
    file.write_text('{"lingua": "fr"}', encoding="utf-8")
    assert leggi().lingua == "fr"  # /nuova rilegge il file


def test_stile_sintetico_non_scoraggia_gli_strumenti():
    # Regressione: «una sola frase breve, senza spiegazioni» faceva rispondere a mente il modello
    # piccolo (calcolatrice usata 0-1 volte su 3). Il testo chiede brevità solo per la risposta
    # finale e ricorda gli strumenti; il modello vero resta comunque non garantito (README).
    testo = prompt_preferenze(PREDEFINITE)
    assert "risposta finale breve ed essenziale (usa comunque gli strumenti)" in testo
    assert "senza spiegazioni" not in testo
