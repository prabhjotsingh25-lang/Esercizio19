"""Test del revisore con modello finto: prompt, indicazione e output non valido."""
from finti import ModelloFinto, chiamata
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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


# --- Fix: il revisore vede riassunto e strumenti del turno ---

def _tokyo(id_chiamata="t1", risultato="2026-11-10T18:17:07+09:00 (Asia/Tokyo)"):
    return [chiamata("Asia/Tokyo", id_chiamata), ToolMessage(risultato, tool_call_id=id_chiamata)]


def test_prompt_con_il_riassunto_prima_del_contesto():
    storia = [HumanMessage("domanda 0"), AIMessage("risposta 0"),
              HumanMessage("Come mi chiamo?"), AIMessage("Ti chiami Prabhjot.")]
    testo = messaggi_per_revisore(storia, "Utente: si chiama Prabhjot.")[-1].content
    assert "Riassunto: Utente: si chiama Prabhjot.\nUtente: domanda 0" in testo
    assert "Riassunto" not in messaggi_per_revisore(storia)[-1].content


def test_prompt_con_gli_strumenti_del_turno_corrente_soltanto():
    storia = [HumanMessage("Che ore sono a Roma?"), *_tokyo("vecchia", "RISULTATO-VECCHIO"),
              AIMessage("A Roma sono le 10."),
              HumanMessage("Che ore sono a Tokyo?"), *_tokyo(), AIMessage("Sono le 18:17."),
              indicazione("manca la data"), *_tokyo("t2", "SECONDO-TENTATIVO"),
              AIMessage("Sono le 18:17 del 10 novembre.")]
    testo = messaggi_per_revisore(storia)[-1].content
    strumenti = testo.split("Strumenti usati in questo turno:")[1].split("Risposta proposta:")[0]
    assert ("ora_corrente({'fuso_orario': 'Asia/Tokyo'}) -> "
            "2026-11-10T18:17:07+09:00 (Asia/Tokyo)") in strumenti
    assert "SECONDO-TENTATIVO" in strumenti  # anche i tentativi precedenti dello stesso turno
    assert "RISULTATO-VECCHIO" not in testo  # non i turni precedenti


def test_strumenti_nessuno_e_risultato_lungo_tagliato():
    senza = messaggi_per_revisore([HumanMessage("Ciao"), AIMessage("Ciao!")])[-1].content
    assert "Strumenti usati in questo turno:\n(nessuno)" in senza
    lungo = "x" * 600
    testo = messaggi_per_revisore(
        [HumanMessage("?"), *_tokyo(risultato=lungo), AIMessage("!")])[-1].content
    assert "x" * 500 + "…" in testo and "x" * 501 not in testo


def test_istruzioni_dati_degli_strumenti_e_riassunto_attendibili():
    sistema = messaggi_per_revisore([HumanMessage("?"), AIMessage("!")])[0].content
    assert "attendibili" in sistema
    assert "non può conoscere" in sistema
    assert "Non puoi verificare" in sistema  # resta: non giudica l'esattezza dei numeri


def test_revisore_passa_il_riassunto_al_modello():
    m = ModelloFinto(risposte=[revisione(True)])
    crea_revisore(m)([HumanMessage("Come mi chiamo?"), AIMessage("Ti chiami Prabhjot.")],
                     "Utente: si chiama Prabhjot.")
    assert "Riassunto: Utente: si chiama Prabhjot." in m.ricevuti[0][-1].content


# --- Step 4: le preferenze dell'utente sono dati attendibili per il revisore ---

def test_prompt_con_le_preferenze_prima_del_riassunto():
    storia = [HumanMessage("Che ore sono?"), AIMessage("A New York sono le 9.")]
    testo = messaggi_per_revisore(storia, "R", "Preferenze dell'utente: fuso America/New_York")[-1].content
    assert ("Conversazione precedente:\nPreferenze dell'utente: fuso America/New_York\n"
            "Riassunto: R") in testo
    assert "Preferenze" not in messaggi_per_revisore(storia)[-1].content
    sistema = messaggi_per_revisore(storia)[0].content
    assert "preferenze dell'utente" in sistema
