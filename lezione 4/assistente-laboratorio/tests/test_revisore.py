"""Test del revisore con modello finto: prompt, indicazione e output non valido."""
from finti import ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente.revisore import (
    Revisione, crea_revisore, indicazione, messaggi_per_revisore)

DOMANDA = "Che ore sono a Tokyo e quanto fa (17+4)*3?"


def revisione(coerente: bool, motivo: str = "perché sì") -> AIMessage:
    """Risposta del modello finto nel formato dell'output strutturato (tool calling)."""
    return AIMessage("", tool_calls=[{"name": "Revisione", "id": "r1",
                                      "args": {"motivo": motivo, "coerente": coerente}}])


def test_schema_motivo_prima_del_giudizio():
    assert list(Revisione.model_fields) == ["motivo", "coerente"]


def test_indicazione_e_un_messaggio_utente_del_revisore():
    m = indicazione("manca il calcolo")
    assert isinstance(m, HumanMessage) and m.name == "revisore"
    assert m.content == ("Revisione: la risposta precedente non va bene perché manca il calcolo. "
                         "Riscrivi la risposta alla domanda tenendone conto.")
    assert indicazione("manca il calcolo.").content == m.content


def test_prompt_con_domanda_originale_risposta_e_contesto():
    storia = [HumanMessage("Mi chiamo Anna"), AIMessage("Ciao Anna!"),
              HumanMessage(DOMANDA), AIMessage("A Tokyo sono le 18."),
              indicazione("manca il calcolo"), AIMessage("A Tokyo sono le 18 e fa 63.")]
    sistema, utente = messaggi_per_revisore(storia)
    assert isinstance(sistema, SystemMessage) and "chiarimento" in sistema.content
    testo = utente.content
    contesto, resto = testo.split("Domanda dell'utente:")
    assert "Utente: Mi chiamo Anna" in contesto and "Assistente: Ciao Anna!" in contesto
    assert DOMANDA in resto and "Revisione:" not in resto  # la domanda è quella originale
    assert resto.rstrip().endswith("A Tokyo sono le 18 e fa 63.")  # risposta proposta: l'ultima
    assert "A Tokyo sono le 18." not in contesto  # bozze del turno corrente fuori dal contesto


def test_revisore_restituisce_il_giudizio_del_modello():
    m = ModelloFinto(risposte=[revisione(False, "manca il calcolo")])
    esito = crea_revisore(m)([HumanMessage(DOMANDA), AIMessage("A Tokyo sono le 18.")])
    assert esito == Revisione(motivo="manca il calcolo", coerente=False)


def test_output_non_valido_vale_coerente_con_warning(caplog):
    caplog.set_level("WARNING")
    cattiva = AIMessage("", tool_calls=[{"name": "Revisione", "id": "r1",
                                         "args": {"motivo": "x", "coerente": "forse"}}])
    m = ModelloFinto(risposte=[cattiva, AIMessage("testo libero, niente JSON")])
    revisore = crea_revisore(m)
    for _ in range(2):
        assert revisore([HumanMessage("?"), AIMessage("!")]).coerente is True
    assert caplog.text.count("output del revisore non valido") == 2
