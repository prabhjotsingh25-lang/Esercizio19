"""Confronto fra varianti: stesso copione, stesso percorso e stessi risultati."""
import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from finti import ISTANTE, ModelloFinto, meteo_finto
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.catalogo import strumenti_locali as _strumenti_locali
from assistente.config import Configurazione
from assistente.grafo import costruisci_grafo
from assistente.server_mcp import crea_server
from assistente.servizio_http import crea_app
from assistente.variante_http import crea_strumenti_http
from assistente.variante_mcp import crea_strumenti_mcp
from assistente.varianti import strumenti_per_variante


def _adesso():
    return ISTANTE


def strumenti_locali(adesso):
    """Catalogo con Open-Meteo finto: il confronto non usa internet."""
    return _strumenti_locali(adesso, trasporto_meteo=meteo_finto())


def _varianti():
    client = TestClient(crea_app(strumenti_locali(_adesso)))
    server = crea_server(strumenti_locali(_adesso))
    return {"locale": strumenti_locali(_adesso),
            "http": crea_strumenti_http("http://servizio", strumenti_locali(_adesso), client=client),
            "mcp": crea_strumenti_mcp("http://servizio-mcp/mcp", strumenti_locali(_adesso),
                                      crea_client=lambda: Client(server))}


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
                 ("catalogo_locale", {"codice": "MUL-01", "testo": "x"}, "11"),
                 ("note_persistenti", {"azione": "aggiungi", "testo": "comprare i fusibili"}, "12"),
                 ("note_persistenti", {"azione": "elenca"}, "13"),
                 ("note_persistenti", {"azione": "elimina", "id": 1}, "14"),
                 ("note_persistenti", {"azione": "elimina", "id": 1, "conferma": True}, "15"),
                 ("note_persistenti", {"azione": "elimina", "id": 1, "conferma": True}, "16"),
                 ("meteo_api", {"luogo": "Roma"}, "17"),
                 ("meteo_api", {"luogo": ""}, "18")),
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
    assert definizioni["locale"] == definizioni["http"] == definizioni["mcp"]


def test_stessa_cronologia_fra_varianti(tmp_path, monkeypatch):
    risultati = {}
    for nome, strumenti in _varianti().items():
        monkeypatch.setenv("NOTE_DB", str(tmp_path / f"{nome}.sqlite"))  # ogni variante parte vuota
        risultati[nome] = _esegui(strumenti)
    m_loc, out_loc = risultati["locale"]
    for nome in ("http", "mcp"):
        modello, uscita = risultati[nome]
        assert _traccia(uscita["messages"]) == _traccia(out_loc["messages"]), nome
        assert uscita["passaggi"] == out_loc["passaggi"] == 2, nome
        assert [_traccia(r) for r in modello.ricevuti] == [_traccia(r) for r in m_loc.ricevuti], nome
    contenuti = [c for _, c, _ in _traccia(out_loc["messages"])]
    assert "(17 + 4) * 3 = 63" in contenuti and "Errore: divisione per zero." in contenuti
    assert any(c.startswith("2026-12-07 + 2 giorni lavorativi = 2026-12-10") for c in contenuti)
    assert any(c.startswith("Nessun articolo trovato per 'microscopio'") for c in contenuti)
    assert 'Nota 1 eliminata: "comprare i fusibili".' in contenuti
    assert "Nessuna nota con id 1." in contenuti
    assert any(c.startswith("Meteo per Roma (Lazio, Italia)") for c in contenuti)


@pytest.mark.parametrize("variante", ["locale", "http", "mcp"])
def test_scelta_da_configurazione(variante):
    config = Configurazione("u", "m", variante=variante, strumenti_http_url="http://servizio:8001",
                            strumenti_mcp_url="http://servizio-mcp:8002/mcp")
    nomi = [s.name for s in strumenti_per_variante(config)]
    assert nomi == ["ora_corrente", "convertitore_unita", "calcolatrice_sicura", "giorni_scadenze",
                    "catalogo_locale", "note_persistenti", "meteo_api"]


def test_lettore_preferenze_per_variante(tmp_path, monkeypatch, caplog):
    from assistente.varianti import lettore_preferenze
    caplog.set_level("INFO")
    file = tmp_path / "preferenze.json"
    file.write_text('{"lingua": "en"}', encoding="utf-8")
    locale = Configurazione("u", "m", preferenze_file=str(file))
    assert lettore_preferenze(locale)().lingua == "en"
    assert "lettura del file" in caplog.text
    http = Configurazione("u", "m", variante="http", strumenti_http_url="http://s",
                          preferenze_file=str(file))
    assert lettore_preferenze(http)().lingua == "en"  # http: file letto direttamente
    mcp = Configurazione("u", "m", variante="mcp", strumenti_mcp_url="http://127.0.0.1:9/mcp",
                         preferenze_file=str(file))
    caplog.clear()
    assert lettore_preferenze(mcp)().lingua == "it"  # server spento: predefinite
    assert "resources/read utente://preferenze (mcp) non disponibili" in caplog.text
