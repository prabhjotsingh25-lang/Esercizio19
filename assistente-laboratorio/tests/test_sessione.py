import pytest
from finti import ModelloFinto, chiamata, orologio
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import MESSAGGIO_LIMITE, costruisci_grafo
from assistente.sessione import Sessione


def test_secondo_turno_vede_il_primo():
    m = ModelloFinto(risposte=[AIMessage("Ciao Anna"), AIMessage("Ti chiami Anna")])
    s = Sessione(costruisci_grafo(m, [orologio], 3), 3)
    s.chiedi("Mi chiamo Anna")
    assert s.chiedi("Come mi chiamo?") == "Ti chiami Anna"
    assert [x.content for x in m.ricevuti[1][1:]] == ["Mi chiamo Anna", "Ciao Anna", "Come mi chiamo?"]


def test_nuova_azzera():
    s = Sessione(costruisci_grafo(ModelloFinto(risposte=[AIMessage("a")]), [orologio], 3), 3)
    s.chiedi("x")
    s.nuova()
    assert s.cronologia == []


def test_contatore_riparte_a_ogni_domanda():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), chiamata("Asia/Tokyo", "2"), AIMessage("uno"),
                               chiamata("Asia/Tokyo", "3"), chiamata("Asia/Tokyo", "4"), AIMessage("due")])
    s = Sessione(costruisci_grafo(m, [orologio], 2), 2)
    assert (s.chiedi("a"), s.chiedi("b")) == ("uno", "due")


def test_dopo_il_limite_la_domanda_successiva_funziona():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), chiamata("Asia/Tokyo", "2"), AIMessage("ok")])
    s = Sessione(costruisci_grafo(m, [orologio], 1), 1)
    assert s.chiedi("a") == MESSAGGIO_LIMITE
    assert s.chiedi("b") == "ok"
    chiamate = {c["id"] for x in s.cronologia if isinstance(x, AIMessage) for c in x.tool_calls}
    risposte = {x.tool_call_id for x in s.cronologia if isinstance(x, ToolMessage)}
    assert chiamate == risposte


def test_errore_del_modello_lascia_invariata_la_cronologia():
    s = Sessione(costruisci_grafo(ModelloFinto(risposte=[AIMessage("a")]), [orologio], 3), 3)
    s.chiedi("x")
    prima = list(s.cronologia)
    with pytest.raises(IndexError):  # ModelloFinto senza risposte
        s.chiedi("y")
    assert s.cronologia == prima
