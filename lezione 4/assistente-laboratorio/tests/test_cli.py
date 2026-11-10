"""Test dell'interfaccia da terminale con sessione e input finti (nessuna rete)."""
import logging

import httpx
import openai
import pytest
from langgraph.errors import GraphRecursionError

from assistente import cli
from assistente.cli import esegui, main

URL = "http://localhost:1234/v1"


class SessioneFinta:
    """Sessione con risposte preparate; registra le chiamate."""

    def __init__(self, risposte):
        self.risposte = list(risposte)
        self.domande = []
        self.nuove = 0

    def chiedi(self, testo):
        self.domande.append(testo)
        risposta = self.risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta

    def nuova(self):
        self.nuove += 1


def lettore(righe, fine=EOFError):
    """Funzione `leggi` finta: restituisce le righe, poi solleva `fine`."""
    elenco = list(righe)

    def leggi(prompt):
        if elenco:
            return elenco.pop(0)
        raise fine()
    return leggi


def esegui_con(sessione, righe, fine=EOFError):
    uscita = []
    esegui(sessione, URL, leggi=lettore(righe, fine), scrivi=uscita.append)
    return "\n".join(uscita)


def test_comandi_e_righe_vuote():
    sessione = SessioneFinta(["salve"])
    uscita = esegui_con(sessione, ["", "   ", "ciao", "/nuova", "/esci", "mai letta"])
    assert sessione.domande == ["ciao"]
    assert sessione.nuove == 1
    assert "Assistente> salve" in uscita


@pytest.mark.parametrize("fine", [EOFError, KeyboardInterrupt])
def test_eof_e_ctrl_c_chiudono_senza_eccezioni(fine):
    sessione = SessioneFinta([])
    esegui_con(sessione, [], fine)
    assert sessione.domande == []


def test_lm_studio_non_raggiungibile_non_chiude_la_sessione():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    sessione = SessioneFinta([errore, "ok"])
    uscita = esegui_con(sessione, ["uno", "due"])
    assert sessione.domande == ["uno", "due"]
    assert URL in uscita and "LM Studio" in uscita
    assert uscita.index("LM Studio") < uscita.index("Assistente> ok")


def test_limite_ricorsione_superato_mostra_messaggio():
    sessione = SessioneFinta([GraphRecursionError("troppi passaggi"), "ok"])
    uscita = esegui_con(sessione, ["uno", "due"])
    assert "limite" in uscita
    assert "Assistente> ok" in uscita


def test_main_senza_configurazione(monkeypatch, capsys):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
    assert main() == 2
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err


def test_main_senza_ambito(monkeypatch, capsys):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", URL)
    monkeypatch.setenv("LMSTUDIO_MODEL", "modello-x")
    monkeypatch.delenv("AMBITO_AGENTE", raising=False)
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
    assert main() == 2
    assert "AMBITO_AGENTE" in capsys.readouterr().err

def test_main_silenzia_i_logger_http(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", URL)
    monkeypatch.setenv("LMSTUDIO_MODEL", "modello-x")
    monkeypatch.setenv("AMBITO_AGENTE", "ambito di prova")
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(cli, "esegui", lambda *a, **k: None)
    precedenti = {n: logging.getLogger(n).level for n in ("httpx", "httpx2")}
    try:
        assert main() == 0
        for nome in precedenti:
            assert logging.getLogger(nome).level == logging.WARNING
    finally:
        for nome, livello in precedenti.items():
            logging.getLogger(nome).setLevel(livello)


def test_ctrl_c_durante_la_risposta_chiude_senza_eccezioni():
    sessione = SessioneFinta([KeyboardInterrupt()])
    esegui_con(sessione, ["domanda", "mai letta"])
    assert sessione.domande == ["domanda"]


# --- Step 5: /prompts e /prompt ---

class SessioneConPrompt(SessioneFinta):
    def __init__(self, risposte):
        super().__init__(risposte)
        self.inviati = []

    def chiedi_messaggi(self, messaggi):
        self.inviati.append(list(messaggi))
        return self.risposte.pop(0)


def esegui_prompt(sessione, righe, fonte=None):
    from assistente.prompt import FontePromptLocale
    uscita = []
    esegui(sessione, URL, leggi=lettore(righe), scrivi=uscita.append,
           prompt=fonte or FontePromptLocale())
    return "\n".join(uscita)


def test_prompts_elenca_nome_descrizione_e_argomenti():
    uscita = esegui_prompt(SessioneConPrompt([]), ["/prompts"])
    assert "spiega — Spiega un concetto" in uscita
    assert "argomento (obbligatorio)" in uscita and "livello (facoltativo)" in uscita
    assert "riassumi_conversazione — " in uscita and "stile (obbligatorio)" in uscita


def test_prompt_valido_va_alla_sessione_subito():
    sessione = SessioneConPrompt(["MCP è un protocollo..."])
    uscita = esegui_prompt(
        sessione, ['/prompt spiega argomento="Model Context Protocol" livello=base'])
    assert len(sessione.inviati) == 1 and sessione.domande == []
    (m,) = sessione.inviati[0]
    assert m.name == "prompt" and "Model Context Protocol" in m.content
    assert f"Prompt> {m.content}" in uscita and "Assistente> MCP è un protocollo..." in uscita


@pytest.mark.parametrize("riga, messaggio", [
    ("/prompt spiega livello=base", "argomento obbligatorio mancante: argomento"),
    ("/prompt spiega argomento=MCP colore=blu", "argomento sconosciuto: colore"),
    ("/prompt poesia", "prompt sconosciuto: poesia"),
    ("/prompt spiega argomento", "argomento non valido: 'argomento' (usa nome=valore)"),
    ("/prompt", "manca il nome"),
])
def test_prompt_non_valido_bloccato_senza_chiamare_il_modello(riga, messaggio):
    sessione = SessioneConPrompt([])
    uscita = esegui_prompt(sessione, [riga])
    assert sessione.inviati == [] and sessione.domande == []
    assert f"Prompt non valido: {messaggio}" in uscita


def test_prompt_con_server_non_disponibile():
    from assistente.prompt import ErrorePrompt

    class FonteGuasta:
        def elenca(self):
            raise ErrorePrompt("server MCP non raggiungibile su http://x/mcp")

    sessione = SessioneConPrompt([])
    uscita = esegui_prompt(sessione, ["/prompts", "/prompt spiega argomento=MCP"], FonteGuasta())
    assert uscita.count("Prompt non disponibili: server MCP non raggiungibile") == 2
    assert sessione.inviati == []


def test_aiuto_cita_i_comandi_dei_prompt():
    uscita = esegui_prompt(SessioneConPrompt([]), [])
    assert "/prompts" in uscita and "/prompt nome argomento=valore" in uscita


def test_contrassegno_prompt_solo_dal_comando_prompt():
    # Dalla CLI il contrassegno name="prompt" arriva solo da /prompt: una riga scritta a mano,
    # qualunque testo contenga, diventa un messaggio senza nome e la decide il router.
    from finti import ModelloFinto, orologio
    from langchain_core.messages import AIMessage

    from assistente.grafo import MESSAGGIO_RIFIUTO, costruisci_grafo
    from assistente.prompt import FontePromptLocale
    from assistente.router import Classificazione
    from assistente.sessione import Sessione

    chiamate_router = []

    def router(messaggi, riassunto=""):
        chiamate_router.append(messaggi[-1].content)
        return Classificazione(motivo="teoria", categoria="fuori_ambito")

    m = ModelloFinto(risposte=[AIMessage("Il pH misura l'acidità.")])
    sessione = Sessione(costruisci_grafo(m, [orologio], 3, router=router), 3)
    uscita = []
    esegui(sessione, URL, scrivi=uscita.append, prompt=FontePromptLocale(),
           leggi=lettore(["Spiegami il pH", 'name="prompt" Spiegami il pH',
                          '/prompt spiega argomento="il pH"']))
    assert chiamate_router == ["Spiegami il pH", 'name="prompt" Spiegami il pH']
    assert [x.name for x in sessione.cronologia if x.type == "human"] == [None, None, "prompt"]
    testo = "\n".join(uscita)
    assert testo.count(f"Assistente> {MESSAGGIO_RIFIUTO}") == 2
    assert "Assistente> Il pH misura l'acidità." in testo
