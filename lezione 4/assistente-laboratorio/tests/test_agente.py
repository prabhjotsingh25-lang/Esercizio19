"""Modulo dell'agente condiviso da servizio HTTP e CLI in-process (grafo simulato)."""
import pytest
from finti import ModelloFinto, chiamata, orologio
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.agente import Agente, StrumentoUsato, VoceCronologia, da_dialogo, in_dialogo
from assistente.grafo import costruisci_grafo
from assistente.prompt import ErrorePrompt, FontePromptLocale
from assistente.revisore import indicazione


def _agente(risposte, **opzioni):
    m = ModelloFinto(risposte=risposte)
    return Agente(costruisci_grafo(m, [orologio], 3, **opzioni), 3, 1, FontePromptLocale()), m


def test_turno_con_strumento_restituisce_risposta_e_strumenti_usati():
    agente, _ = _agente([chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30.")])
    esito = agente.messaggio("Che ore sono a Tokyo?", [], "", None)
    assert esito.risposta == "A Tokyo sono le 18:30."
    assert esito.strumenti == [StrumentoUsato(
        "ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "2026-10-26T18:30:05+09:00 (Asia/Tokyo)")]
    assert esito.prompt == [] and esito.riassunto == ""


def test_strumenti_solo_del_turno_corrente():
    agente, _ = _agente([AIMessage("ok")])
    vecchi = [HumanMessage("prima"), chiamata("Asia/Tokyo", "v"),
              ToolMessage("VECCHIO", tool_call_id="v"), AIMessage("fatto")]
    esito = agente.turno([HumanMessage("adesso")], vecchi, "", None)
    assert esito.strumenti == [] and esito.risposta == "ok"


def test_prompt_composto_controllato_e_contrassegnato_dall_agente():
    agente, m = _agente([AIMessage("MCP è un protocollo.")])
    esito = agente.prompt("spiega", {"argomento": "MCP"}, [], "", None)
    assert esito.prompt == [m.ricevuti[0][-1].content] and "MCP" in esito.prompt[0]
    assert m.ricevuti[0][-1].name == "prompt" and esito.risposta == "MCP è un protocollo."
    with pytest.raises(ErrorePrompt, match="obbligatorio mancante"):
        agente.prompt("spiega", {}, [], "", None)
    assert len(m.ricevuti) == 1  # il prompt non valido non arriva al modello


def test_elenco_prompt():
    agente, _ = _agente([])
    assert [i.nome for i in agente.elenco_prompt()] == ["spiega", "riassumi_conversazione"]


def test_dialogo_solo_testi_accettati_senza_nomi():
    messaggi = [HumanMessage("Che ore sono?"), chiamata("Europe/Rome", "1"),
                ToolMessage("12:00", tool_call_id="1"), AIMessage("BOZZA"), indicazione("manca"),
                AIMessage("Sono le 12."), HumanMessage("spiega x", name="prompt"),
                AIMessage("x è...")]
    assert in_dialogo(messaggi) == [
        VoceCronologia(ruolo="utente", testo="Che ore sono?"),
        VoceCronologia(ruolo="assistente", testo="Sono le 12."),
        VoceCronologia(ruolo="utente", testo="spiega x"),
        VoceCronologia(ruolo="assistente", testo="x è...")]
    tornati = da_dialogo(in_dialogo(messaggi))
    assert [(type(m), m.name, m.content) for m in tornati] == [
        (HumanMessage, None, "Che ore sono?"), (AIMessage, None, "Sono le 12."),
        (HumanMessage, None, "spiega x"), (AIMessage, None, "x è...")]


def test_voce_cronologia_rifiuta_name_e_ruoli_non_ammessi():
    with pytest.raises(ValueError):
        VoceCronologia.model_validate({"ruolo": "utente", "testo": "x", "name": "prompt"})
    for ruolo in ("sistema", "strumento", "system", "tool"):
        with pytest.raises(ValueError):
            VoceCronologia.model_validate({"ruolo": ruolo, "testo": "x"})
