"""Prompt dell'utente: catalogo, comando /prompt, controllo rispetto all'elenco, fonte locale."""
import pytest
from langchain_core.messages import HumanMessage

from assistente.contesto import e_domanda, e_indicazione
from assistente.prompt import (
    CATALOGO_PROMPT, NOME_PROMPT, ErrorePrompt, FontePromptLocale, analizza_comando, controlla,
    descrivi_elenco)


def _info(nome):
    return next(i for i in FontePromptLocale().elenca() if i.nome == nome)


def test_catalogo_spiega_e_riassumi_conversazione():
    assert [d.nome for d in CATALOGO_PROMPT] == ["spiega", "riassumi_conversazione"]
    spiega = _info("spiega")
    assert [(a.nome, a.obbligatorio) for a in spiega.argomenti] == [("argomento", True),
                                                                    ("livello", False)]
    assert [(a.nome, a.obbligatorio) for a in _info("riassumi_conversazione").argomenti] == [
        ("stile", True)]


def test_analizza_comando_con_virgolette():
    assert analizza_comando('spiega argomento="Model Context Protocol" livello=base') == (
        "spiega", {"argomento": "Model Context Protocol", "livello": "base"})
    assert analizza_comando("riassumi_conversazione stile=sintetico") == (
        "riassumi_conversazione", {"stile": "sintetico"})


@pytest.mark.parametrize("riga, motivo", [
    ("", "manca il nome"),
    ("spiega argomento", "nome=valore"),
    ("spiega =x", "nome=valore"),
    ("spiega a=1 a=2", "ripetuto"),
    ('spiega argomento="non chiuso', "virgolette"),
])
def test_analizza_comando_non_valido(riga, motivo):
    with pytest.raises(ErrorePrompt, match=motivo):
        analizza_comando(riga)


def test_controlla_argomenti_rispetto_all_elenco():
    elenco = FontePromptLocale().elenca()
    controlla(elenco, "spiega", {"argomento": "MCP"})  # livello facoltativo
    with pytest.raises(ErrorePrompt, match="obbligatorio mancante: argomento"):
        controlla(elenco, "spiega", {"livello": "base"})
    with pytest.raises(ErrorePrompt, match="sconosciuto: colore"):
        controlla(elenco, "spiega", {"argomento": "MCP", "colore": "blu"})
    with pytest.raises(ErrorePrompt, match="prompt sconosciuto: poesia"):
        controlla(elenco, "poesia", {})


def test_descrivi_elenco_nome_descrizione_e_argomenti():
    testo = descrivi_elenco(FontePromptLocale().elenca())
    assert "spiega — " in testo and "riassumi_conversazione — " in testo
    assert "argomento (obbligatorio)" in testo and "livello (facoltativo)" in testo
    assert "stile (obbligatorio)" in testo


def test_fonte_locale_messaggi_marcati_e_predefinito(caplog):
    caplog.set_level("INFO")
    messaggi = FontePromptLocale().ottieni("spiega", {"argomento": "Model Context Protocol"})
    assert len(messaggi) == 1 and isinstance(messaggi[0], HumanMessage)
    assert messaggi[0].name == NOME_PROMPT
    assert "Model Context Protocol" in messaggi[0].content and "livello base" in messaggi[0].content
    assert "prompt: prompts/get spiega (locale) argomenti={'argomento': 'Model Context Protocol'}" \
        in caplog.text and "messaggi dal server: [user] Spiegami" in caplog.text
    # un messaggio da prompt è una domanda dell'utente, non un'indicazione del revisore
    assert e_domanda(messaggi[0]) and not e_indicazione(messaggi[0])


def test_riassumi_conversazione_e_un_istruzione_per_l_agente():
    testo = FontePromptLocale().ottieni("riassumi_conversazione", {"stile": "a punti"})[0].content
    assert "Riassumi i turni della sessione corrente nello stile a punti" in testo


def test_fonte_locale_log_dell_elenco(caplog):
    caplog.set_level("INFO")
    FontePromptLocale().elenca()
    assert "prompt: prompts/list (locale) -> 2 prompt: spiega, riassumi_conversazione" in caplog.text
