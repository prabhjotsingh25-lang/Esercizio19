"""Test dell'interfaccia da terminale con sessione e input finti (nessuna rete)."""
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
        if isinstance(risposta, Exception):
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


def test_main_silenzia_i_logger_http(monkeypatch):
    import logging
    monkeypatch.setenv("LMSTUDIO_BASE_URL", URL)
    monkeypatch.setenv("LMSTUDIO_MODEL", "modello-x")
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
