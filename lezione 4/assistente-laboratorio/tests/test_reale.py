"""Prove reali con LM Studio attivo: si attivano esplicitamente con `pytest -m reale`."""
import re

import pytest
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.sessione import Sessione
from assistente.varianti import strumenti_per_variante

pytestmark = pytest.mark.reale

_ORA = re.compile(r"T(\d{2}:\d{2}):\d{2}")


@pytest.fixture
def sessione(tmp_path, monkeypatch):
    load_dotenv(".env", override=False)
    # Variante locale: note in un database temporaneo. Nelle varianti http e mcp le note
    # vanno nel database del servizio (NOTE_DB impostata all'avvio del servizio).
    monkeypatch.setenv("NOTE_DB", str(tmp_path / "note.sqlite"))
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        pytest.skip(f"Configurazione mancante: {errore}")
    strumenti = strumenti_per_variante(config)
    grafo = costruisci_grafo(crea_modello(config), strumenti, config.max_passaggi)
    return Sessione(grafo, config.max_passaggi)


def _strumenti_del_turno(sessione: Sessione) -> list[str]:
    """Risultati dei ToolMessage aggiunti dopo l'ultima domanda dell'utente."""
    cronologia = sessione.cronologia
    ultima = max(i for i, m in enumerate(cronologia) if isinstance(m, HumanMessage))
    return [m.content for m in cronologia[ultima + 1:] if isinstance(m, ToolMessage)]


def test_tokyo_poi_roma(sessione):
    risposta = sessione.chiedi("Che ore sono a Tokyo?")
    risultati = _strumenti_del_turno(sessione)
    tokyo = [r for r in risultati if r.endswith("(Asia/Tokyo)")]
    assert tokyo, f"nessun ToolMessage per Asia/Tokyo: {risultati}"
    ora = _ORA.search(tokyo[-1])
    assert ora, f"orario non riconoscibile nel risultato: {tokyo[-1]}"
    assert ora.group(1) in risposta, f"{ora.group(1)} assente nella risposta: {risposta!r}"

    sessione.chiedi("E a Roma?")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.endswith("(Europe/Rome)") for r in risultati), (
        f"nessun ToolMessage per Europe/Rome nel secondo turno: {risultati}")


def test_ora_senza_luogo(sessione):
    sessione.chiedi("Che ore sono?")
    assert _strumenti_del_turno(sessione) == []


def test_conversione_km_in_metri(sessione):
    risposta = sessione.chiedi("Quanti metri sono 1,5 km?")
    risultati = _strumenti_del_turno(sessione)
    assert "1.5 km = 1500 m" in risultati, f"conversione non eseguita come atteso: {risultati}"
    assert "1500" in risposta.replace(".", "").replace(" ", ""), f"1500 assente: {risposta!r}"


def test_conversione_incompatibile_non_inventa(sessione):
    sessione.chiedi("Converti 3 kg in metri.")
    risultati = _strumenti_del_turno(sessione)
    assert all(r.startswith("Errore:") for r in risultati), f"risultato inventato: {risultati}"


def test_calcolo_con_la_calcolatrice(sessione):
    risposta = sessione.chiedi("Quanto fa (17 + 4) * 3?")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.endswith("= 63") for r in risultati), f"calcolatrice non usata come atteso: {risultati}"
    assert "63" in risposta, f"63 assente nella risposta: {risposta!r}"


def test_giorni_lavorativi(sessione):
    risposta = sessione.chiedi("Quanti giorni lavorativi ci sono dal 2026-12-21 al 2026-12-31?")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.startswith("Dal 2026-12-21 al 2026-12-31: 7 giorni lavorativi") for r in risultati), (
        f"giorni_scadenze non usato come atteso: {risultati}")
    assert "7" in risposta, f"7 assente nella risposta: {risposta!r}"


def test_catalogo_articolo_presente(sessione):
    risposta = sessione.chiedi("Avete un multimetro in laboratorio? Dove si trova?")
    risultati = _strumenti_del_turno(sessione)
    assert any("MUL-01" in r for r in risultati), f"catalogo_locale non usato come atteso: {risultati}"
    assert "Armadio A" in risposta, f"ubicazione assente nella risposta: {risposta!r}"


def test_catalogo_articolo_assente(sessione):
    sessione.chiedi("Avete un microscopio elettronico in laboratorio?")
    risultati = _strumenti_del_turno(sessione)
    assert risultati, "il modello ha risposto senza consultare il catalogo"
    assert all(r.startswith(("Nessun articolo", "Errore:")) for r in risultati), (
        f"risultato inatteso per un articolo assente: {risultati}")


def test_note_salvataggio(sessione):
    sessione.chiedi("Ricordami di comprare i fusibili da 5 A.")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.startswith("Nota ") and "salvata" in r and "fusibili" in r for r in risultati), (
        f"nota non salvata: {risultati}")


def test_note_eliminazione_chiede_conferma(sessione):
    sessione.chiedi("Salva una nota con questo testo: verificare cancellazione 42.")
    salvate = [r for r in _strumenti_del_turno(sessione) if re.match(r"Nota \d+ salvata", r)]
    assert salvate, "nota di prova non salvata"
    id_nota = re.match(r"Nota (\d+) salvata", salvate[0]).group(1)

    sessione.chiedi(f"Cancella la nota {id_nota}.")
    turno = _strumenti_del_turno(sessione)
    assert not any(r.startswith(f"Nota {id_nota} eliminata") for r in turno), (
        f"nota eliminata senza la conferma dell'utente: {turno}")
    assert any(f"Stai per eliminare la nota {id_nota}" in r for r in turno), (
        f"richiesta di conferma assente: {turno}")

    sessione.chiedi("Sì, confermo.")
    assert any(r.startswith(f"Nota {id_nota} eliminata") for r in _strumenti_del_turno(sessione)), (
        "nota non eliminata dopo la conferma")


def test_meteo_domani(sessione):
    # Richiede internet (Open-Meteo). "domani" verifica che il modello usi la riga giusta.
    risposta = sessione.chiedi("Che tempo farà domani a Roma?")
    risultati = [r for r in _strumenti_del_turno(sessione) if r.startswith("Meteo per Roma")]
    assert risultati, f"meteo_api non usato come atteso: {_strumenti_del_turno(sessione)}"
    domani = re.search(r"\(domani\): min (-?\d+) °C, max (-?\d+) °C", risultati[0])
    assert domani.group(2) in risposta, (
        f"massima di domani ({domani.group(2)} °C) assente nella risposta: {risposta!r}")


def test_meteo_luogo_inesistente_non_inventa(sessione):
    # Un nome plausibile ma inesistente: con una parola senza senso («Zzyzxqwvk») il modello
    # chiede subito chiarimenti senza chiamare lo strumento, e l'errore non viene provato.
    risposta = sessione.chiedi("Che tempo fa a Montefracassone?")
    risultati = _strumenti_del_turno(sessione)
    assert risultati, "il modello ha risposto senza consultare il servizio meteo"
    assert all(r.startswith("Errore:") for r in risultati), f"risultato inatteso: {risultati}"
    assert "°" not in risposta, f"temperatura inventata nella risposta: {risposta!r}"
