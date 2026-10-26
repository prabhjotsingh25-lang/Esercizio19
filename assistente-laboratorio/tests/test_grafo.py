from finti import ModelloFinto, chiamata, orologio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import MESSAGGIO_LIMITE, costruisci_grafo, limite_ricorsione, scegli_prossimo


def test_instradamento():
    fine = {"messages": [AIMessage("ciao")], "passaggi": 0}
    assert scegli_prossimo(fine, 3) == "__end__"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 2}, 3) == "strumenti"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 3}, 3) == "limite"


def test_limite_ricorsione():
    assert limite_ricorsione(3) == 11


def test_ciclo_completo_con_strumento():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30.")])
    out = costruisci_grafo(m, [orologio], 3).invoke(
        {"messages": [HumanMessage("Che ore sono a Tokyo?")], "passaggi": 0})
    assert out["messages"][-1].content == "A Tokyo sono le 18:30."
    assert out["passaggi"] == 1
    secondo = m.ricevuti[1]
    assert isinstance(secondo[0], SystemMessage)
    assert secondo[-1].tool_call_id == "1" and secondo[-1].content.startswith("2026-10-26T18:30:05+09:00")


def test_due_chiamate_nella_stessa_risposta_contano_un_passaggio():
    doppia = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {"fuso_orario": "Asia/Tokyo"}, "id": "a"},
                                       {"name": "ora_corrente", "args": {"fuso_orario": "Europe/Rome"}, "id": "b"}])
    out = costruisci_grafo(ModelloFinto(risposte=[doppia, AIMessage("ok")]), [orologio], 3).invoke(
        {"messages": [HumanMessage("Tokyo e Roma?")], "passaggi": 0})
    assert [t.tool_call_id for t in out["messages"] if isinstance(t, ToolMessage)] == ["a", "b"]
    assert out["passaggi"] == 1


def test_argomenti_sbagliati_e_strumento_sconosciuto_diventano_errori():
    cattive = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "a"},
                                        {"name": "meteo", "args": {}, "id": "b"}])
    out = costruisci_grafo(ModelloFinto(risposte=[cattive, AIMessage("ok")]), [orologio], 3).invoke(
        {"messages": [HumanMessage("?")], "passaggi": 0})
    errori = [t for t in out["messages"] if isinstance(t, ToolMessage)]
    assert all(t.content.startswith("Errore:") for t in errori) and len(errori) == 2
    assert [t.tool_call_id for t in errori] == ["a", "b"]


def test_limite_ferma_il_ciclo_e_chiude_le_chiamate():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", str(i)) for i in range(10)])
    out = costruisci_grafo(m, [orologio], 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    assert out["passaggi"] == 3 and len(m.ricevuti) == 4
    assert out["messages"][-1].content == MESSAGGIO_LIMITE
    assert out["messages"][-2].content == "Non eseguito: limite di passaggi raggiunto."
    assert out["messages"][-2].tool_call_id == "3"


def test_log_della_chiamata(caplog):
    caplog.set_level("INFO")
    costruisci_grafo(ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("ok")]),
                     [orologio], 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    assert "passaggio=1" in caplog.text and "ora_corrente" in caplog.text and "Asia/Tokyo" in caplog.text
