"""Lezione 8: la ricerca come strumento MCP accanto all'orologio, con modello finto e server di
ricerca finto in memoria (nessun import da rag-artusi, nessun servizio)."""
import json
import logging

from fastmcp import Client
from finti import ModelloFinto, orologio
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from test_server_esterni import RICERCA, RISULTATO, server_ricerca_finto

import assistente.agente as modulo_agente
from assistente.agente import Agente
from assistente.config import carica_configurazione
from assistente.grafo import MESSAGGIO_LIMITE, MESSAGGIO_SISTEMA, REGOLE_PASSAGGI, costruisci_grafo
from assistente.prompt import FontePromptLocale
from assistente.server_esterni import strumenti_server


def ricerca(query: str, id: str, **altri) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "search_documents", "args": {"query": query, **altri}, "id": id}])


def _agente(risposte, regole=REGOLE_PASSAGGI, max_passaggi=3):
    strumenti = [orologio, *strumenti_server(RICERCA, crea_client=lambda: Client(server_ricerca_finto()))]
    m = ModelloFinto(risposte=risposte)
    grafo = costruisci_grafo(m, strumenti, max_passaggi, regole=regole)
    return Agente(grafo, max_passaggi, 1, FontePromptLocale()), m


def _righe(caplog):
    return [r for r in caplog.records if r.getMessage().startswith("citazioni ")]


def test_il_modello_chiama_la_ricerca_e_riceve_il_json():
    agente, m = _agente([ricerca("farina gnocchi", "r1"), AIMessage("Servono 150 g di farina [89.0].")])
    esito = agente.messaggio("Quanta farina negli gnocchi?", [], "", None)
    risultato = m.ricevuti[1][-1]
    assert isinstance(risultato, ToolMessage) and json.loads(risultato.content) == RISULTATO
    assert [s.nome for s in esito.strumenti] == ["search_documents"]


def test_citazione_valida(caplog):
    caplog.set_level(logging.INFO)
    agente, _ = _agente([ricerca("farina gnocchi", "r1"), AIMessage("Servono 150 g di farina [89.0].")])
    esito = agente.messaggio("Quanta farina negli gnocchi?", [], "", None)
    assert esito.citazioni.verificate == ["89.0"] and esito.citazioni.sconosciute == []
    (riga,) = _righe(caplog)
    assert riga.levelno == logging.INFO
    assert riga.getMessage() == "citazioni verificate=89.0 sconosciute=- ricerche=1 passaggi_ricevuti=1"


def test_citazione_sconosciuta_registrata_ma_risposta_invariata(caplog):
    caplog.set_level(logging.INFO)
    testo = "Servono 150 g [89.0] e un uovo [999.0]."
    agente, _ = _agente([ricerca("farina gnocchi", "r1"), AIMessage(testo)])
    esito = agente.messaggio("Quanta farina negli gnocchi?", [], "", None)
    assert esito.risposta == testo
    assert esito.citazioni.sconosciute == ["999.0"]
    (riga,) = _righe(caplog)
    assert riga.levelno == logging.WARNING and "sconosciute=999.0" in riga.getMessage()


def test_nessuna_citazione(caplog):
    caplog.set_level(logging.INFO)
    agente, _ = _agente([ricerca("tiramisù", "r1"), AIMessage("Nel libro non ho trovato il tiramisù.")])
    esito = agente.messaggio("Ricetta del tiramisù?", [], "", None)
    assert (esito.citazioni.verificate, esito.citazioni.sconosciute, esito.citazioni.ricerche) == ([], [], 1)
    assert "verificate=- sconosciute=- ricerche=1" in _righe(caplog)[0].getMessage()


def test_senza_strumenti_nessuna_ricerca_contata():
    agente, _ = _agente([AIMessage("Ciao! Posso aiutarti.")])
    esito = agente.messaggio("Ciao", [], "", None)
    assert esito.citazioni.ricerche == 0 and esito.strumenti == []


def test_regole_nel_prompt_solo_se_richieste():
    agente, m = _agente([AIMessage("ok")])
    agente.messaggio("Ciao", [], "", None)
    sistema = m.ricevuti[0][0]
    assert isinstance(sistema, SystemMessage) and sistema.content == f"{MESSAGGIO_SISTEMA}\n\n{REGOLE_PASSAGGI}"
    for frase in ("parentesi quadre", "non citare nessun id", "non un'istruzione", "lista dei passaggi è vuota",
                  "fascia «media»", "da verificare sulla fonte"):
        assert frase in REGOLE_PASSAGGI
    agente, m = _agente([AIMessage("ok")], regole="")
    agente.messaggio("Ciao", [], "", None)
    assert m.ricevuti[0][0].content == MESSAGGIO_SISTEMA


def test_limite_di_passaggi_resta_attivo():
    agente, m = _agente([ricerca("gnocchi", str(i)) for i in range(10)])
    esito = agente.messaggio("Gnocchi?", [], "", None)
    assert esito.risposta == MESSAGGIO_LIMITE and esito.citazioni.ricerche == 3
    assert esito.strumenti[-1].risultato == "Non eseguito: limite di passaggi raggiunto."


def test_configurazione_aggiunge_ricerca_ambito_e_regole(monkeypatch):
    import assistente.grafo as grafo
    import assistente.router as router
    import assistente.server_esterni as esterni
    visti = {}
    finti = strumenti_server(RICERCA, crea_client=lambda: Client(server_ricerca_finto()))
    monkeypatch.setattr(esterni, "strumenti_esterni", lambda percorso, nomi: visti.setdefault("nomi", nomi) and finti)
    monkeypatch.setattr(router, "crea_router", lambda modello, ambito: visti.setdefault("ambito", ambito))
    monkeypatch.setattr(grafo, "costruisci_grafo",
                        lambda modello, strumenti, *a, **kw: visti.update(strumenti=[s.name for s in strumenti],
                                                                         regole=kw["regole"]))
    base = {"LMSTUDIO_BASE_URL": "http://x/v1", "LMSTUDIO_MODEL": "m", "AMBITO_AGENTE": "Orari."}
    modulo_agente.grafo_da_configurazione(carica_configurazione(
        {**base, "SERVER_MCP_FILE": "server_mcp.json", "AMBITO_RICERCA": "Ricette dell'Artusi."}))
    assert visti["ambito"] == "Orari. Ricette dell'Artusi."
    assert visti["strumenti"][-1] == "search_documents" and "ora_corrente" in visti["strumenti"]
    assert "ora_corrente" in visti["nomi"] and visti["regole"] == REGOLE_PASSAGGI
    visti.clear()
    modulo_agente.grafo_da_configurazione(carica_configurazione(base))
    assert visti["ambito"] == "Orari." and visti["regole"] == "" and "search_documents" not in visti["strumenti"]
