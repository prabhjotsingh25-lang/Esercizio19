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
def sessione():
    load_dotenv(".env", override=False)
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
