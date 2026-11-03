"""Confronto fra varianti: stesso copione, stesso percorso e stessi risultati."""
import pytest
from fastapi.testclient import TestClient
from finti import ISTANTE, ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.catalogo import strumenti_locali
from assistente.config import Configurazione
from assistente.grafo import costruisci_grafo
from assistente.servizio_http import crea_app
from assistente.variante_http import crea_strumenti_http
from assistente.varianti import strumenti_per_variante


def _adesso():
    return ISTANTE


def _varianti():
    client = TestClient(crea_app(strumenti_locali(_adesso)))
    return {"locale": strumenti_locali(_adesso),
            "http": crea_strumenti_http("http://servizio", strumenti_locali(_adesso), client=client)}


def _copione():
    def chiamate(*voci):
        return AIMessage("", tool_calls=[{"name": n, "args": a, "id": i} for n, a, i in voci])
    return [
        chiamate(("ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "1"),
                 ("convertitore_unita", {"valore": 5, "da": "kg", "a": "m"}, "2")),
        chiamate(("calcolatrice_sicura", {"espressione": "(17 + 4) * 3"}, "3"),
                 ("calcolatrice_sicura", {"espressione": "1 / 0"}, "4"),
                 ("ora_corrente", {}, "5"),
                 ("meteo", {"citta": "Roma"}, "6"),
                 ("giorni_scadenze", {"data_inizio": "2026-12-07", "giorni": 2,
                                      "solo_lavorativi": True}, "7"),
                 ("giorni_scadenze", {"data_inizio": "2026-02-30", "giorni": 1}, "8"),
                 ("catalogo_locale", {"testo": "multimetro"}, "9"),
                 ("catalogo_locale", {"testo": "microscopio"}, "10"),
                 ("catalogo_locale", {"codice": "MUL-01", "testo": "x"}, "11")),
        AIMessage("Fatto."),
    ]


def _esegui(strumenti):
    modello = ModelloFinto(risposte=_copione())
    uscita = costruisci_grafo(modello, strumenti, 3).invoke(
        {"messages": [HumanMessage("Prova di confronto")], "passaggi": 0})
    return modello, uscita


def _traccia(messaggi):
    return [(type(m).__name__, m.content, getattr(m, "tool_call_id", None)) for m in messaggi]


def test_stesse_definizioni_fra_varianti():
    definizioni = {nome: [convert_to_openai_tool(s) for s in strumenti]
                   for nome, strumenti in _varianti().items()}
    assert definizioni["locale"] == definizioni["http"]


def test_stessa_cronologia_fra_varianti():
    risultati = {nome: _esegui(strumenti) for nome, strumenti in _varianti().items()}
    (m_loc, out_loc), (m_http, out_http) = risultati["locale"], risultati["http"]
    assert _traccia(out_loc["messages"]) == _traccia(out_http["messages"])
    assert out_loc["passaggi"] == out_http["passaggi"] == 2
    assert [_traccia(r) for r in m_loc.ricevuti] == [_traccia(r) for r in m_http.ricevuti]
    contenuti = [c for _, c, _ in _traccia(out_loc["messages"])]
    assert "(17 + 4) * 3 = 63" in contenuti and "Errore: divisione per zero." in contenuti
    assert any(c.startswith("2026-12-07 + 2 giorni lavorativi = 2026-12-10") for c in contenuti)
    assert any(c.startswith("Nessun articolo trovato per 'microscopio'") for c in contenuti)


@pytest.mark.parametrize("variante", ["locale", "http"])
def test_scelta_da_configurazione(variante):
    config = Configurazione("u", "m", variante=variante, strumenti_http_url="http://servizio:8001")
    nomi = [s.name for s in strumenti_per_variante(config)]
    assert nomi == ["ora_corrente", "convertitore_unita", "calcolatrice_sicura", "giorni_scadenze",
                    "catalogo_locale"]
