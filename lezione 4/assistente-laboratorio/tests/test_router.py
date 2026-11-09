"""Test del router con modello finto: prompt, finestra dei messaggi e output non valido."""
from finti import ModelloFinto, chiamata
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.router import FINESTRA, Classificazione, crea_router, messaggi_per_router

AMBITO = "Assistente di laboratorio: orari, calcoli e meteo."


def classificazione(categoria: str, motivo: str = "perché sì") -> AIMessage:
    """Risposta del modello finto nel formato dell'output strutturato (tool calling)."""
    return AIMessage("", tool_calls=[{"name": "Classificazione", "id": "c1",
                                      "args": {"motivo": motivo, "categoria": categoria}}])


def test_schema_motivo_prima_della_categoria():
    assert list(Classificazione.model_fields) == ["motivo", "categoria"]


def test_prompt_con_ambito_e_domanda():
    messaggi = messaggi_per_router([HumanMessage("Che ore sono a Tokyo?")], AMBITO)
    assert isinstance(messaggi[0], SystemMessage) and AMBITO in messaggi[0].content
    assert "Che ore sono a Tokyo?" in messaggi[-1].content


def test_finestra_solo_testo_e_al_massimo_sei_messaggi():
    storia = []
    for i in range(5):  # 5 turni = 10 messaggi di testo, più chiamate e risultati degli strumenti
        storia += [HumanMessage(f"domanda {i}"), chiamata("Asia/Tokyo", f"t{i}"),
                   ToolMessage("RISULTATO-STRUMENTO", tool_call_id=f"t{i}"),
                   AIMessage(f"risposta {i}")]
    storia.append(HumanMessage("E a Roma?"))
    testo = messaggi_per_router(storia, AMBITO)[-1].content
    assert "RISULTATO-STRUMENTO" not in testo
    assert "domanda 1" not in testo and "risposta 1" not in testo  # fuori dalla finestra
    assert all(f"domanda {i}" in testo and f"risposta {i}" in testo for i in (2, 3, 4))
    assert testo.count("Utente:") + testo.count("Assistente:") == FINESTRA == 6
    assert testo.rstrip().endswith("E a Roma?")


def test_router_restituisce_la_classificazione_del_modello():
    m = ModelloFinto(risposte=[classificazione("fuori_ambito", "chiede una poesia")])
    esito = crea_router(m, AMBITO)([HumanMessage("Scrivimi una poesia")])
    assert esito == Classificazione(motivo="chiede una poesia", categoria="fuori_ambito")
    assert AMBITO in m.ricevuti[0][0].content


def test_output_non_valido_diventa_conversazione_con_warning(caplog):
    caplog.set_level("WARNING")
    m = ModelloFinto(risposte=[classificazione("boh"), AIMessage("testo libero, niente JSON")])
    router = crea_router(m, AMBITO)
    for _ in range(2):
        assert router([HumanMessage("?")]).categoria == "conversazione"
    assert caplog.text.count("output del router non valido") == 2


def test_finestra_salta_le_indicazioni_del_revisore():
    storia = [HumanMessage("Che ore sono a Tokyo e quanto fa 2+2?"), AIMessage("Sono le 18."),
              HumanMessage("Revisione: manca il calcolo.", name="revisore"),
              AIMessage("Sono le 18 e 2+2 fa 4."), HumanMessage("Grazie!")]
    testo = messaggi_per_router(storia, AMBITO)[-1].content
    assert "Revisione:" not in testo
    assert "Assistente: Sono le 18." in testo  # la bozza rifiutata resta visibile
