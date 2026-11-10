from finti import ModelloFinto, chiamata
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.revisore import indicazione
from assistente.riassunto import crea_riassuntore, dialogo_da_riassumere, punto_di_taglio


def turno(i):
    """Turno semplice: domanda e risposta."""
    return [HumanMessage(f"domanda {i}"), AIMessage(f"risposta {i}")]


def turno_con_strumento(i):
    """Turno con strumento: domanda, chiamata, risultato, risposta (4 messaggi)."""
    return [HumanMessage(f"domanda {i}"), chiamata("Asia/Tokyo", f"t{i}"),
            ToolMessage(f"RISULTATO {i}", tool_call_id=f"t{i}"), AIMessage(f"risposta {i}")]


def test_taglio_esatto_su_una_domanda():
    storia = turno(0) + turno(1) + [HumanMessage("nuova")]  # 5 messaggi
    assert punto_di_taglio(storia, 3) == 2  # tiene domanda 1, risposta 1, nuova


def test_taglio_torna_indietro_fino_alla_domanda():
    storia = turno(0) + turno(1) + [HumanMessage("nuova")]
    assert punto_di_taglio(storia, 2) == 2  # «ultimi 2» partirebbe da risposta 1


def test_taglio_non_separa_chiamata_e_tool_message():
    storia = turno(0) + turno_con_strumento(1) + [HumanMessage("nuova")]  # 7 messaggi
    for recenti in (2, 3, 4):  # «ultimi N» cadrebbe su risposta, ToolMessage o chiamata
        taglio = punto_di_taglio(storia, recenti)
        assert taglio == 2 and storia[taglio].content == "domanda 1"


def test_taglio_salta_le_indicazioni_del_revisore():
    storia = turno(0) + [HumanMessage("domanda 1"), AIMessage("bozza"), indicazione("manca"),
                         AIMessage("risposta 1"), HumanMessage("nuova")]
    assert punto_di_taglio(storia, 3) == 2  # l'indicazione non è una domanda: tiene la bozza


def test_taglio_zero_con_un_solo_turno():
    storia = [HumanMessage("unica"), *turno_con_strumento(0)[1:], chiamata("Asia/Tokyo", "x")]
    assert punto_di_taglio(storia, 1) == 0


def test_dialogo_solo_domande_e_risposte_accettate():
    storia = (turno_con_strumento(0)
              + [HumanMessage("domanda 1"), AIMessage("BOZZA SCARTATA"), indicazione("manca"),
                 AIMessage("risposta 1")])
    testo = dialogo_da_riassumere(storia)
    assert testo == ("Utente: domanda 0\nAssistente: risposta 0\n"
                     "Utente: domanda 1\nAssistente: risposta 1")


def test_riassuntore_incorpora_il_precedente():
    m = ModelloFinto(risposte=[AIMessage("  L'utente si chiama Anna e ha chiesto l'ora.  ")])
    nuovo = crea_riassuntore(m)("L'utente si chiama Anna.", turno(0))
    assert nuovo == "L'utente si chiama Anna e ha chiesto l'ora."
    sistema, richiesta = m.ricevuti[0]
    assert isinstance(sistema, SystemMessage) and "riassunto" in sistema.content.lower()
    assert "«Utente:»" in sistema.content  # i fatti sull'utente vengono per primi
    assert "Riassunto precedente:\nL'utente si chiama Anna." in richiesta.content
    assert "Utente: domanda 0\nAssistente: risposta 0" in richiesta.content


def test_riassuntore_senza_precedente():
    m = ModelloFinto(risposte=[AIMessage("r")])
    crea_riassuntore(m)("", turno(0))
    assert "Riassunto precedente:\n(nessuno)" in m.ricevuti[0][1].content
