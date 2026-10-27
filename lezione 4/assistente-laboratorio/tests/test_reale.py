"""Prove reali con LM Studio attivo: si attivano esplicitamente con `pytest -m reale`."""
import re

import pytest
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.sessione import Sessione
from assistente.strumenti import crea_strumento_orologio

pytestmark = pytest.mark.reale

_ORA = re.compile(r"T(\d{2}:\d{2}):\d{2}")


@pytest.fixture
def sessione():
    load_dotenv(".env", override=False)
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        pytest.skip(f"Configurazione mancante: {errore}")
    grafo = costruisci_grafo(crea_modello(config), [crea_strumento_orologio()],
                             config.max_passaggi)
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
