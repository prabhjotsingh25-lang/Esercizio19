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


# --- Step 5 e 6: /prompts e /prompt passano dalla sessione (in-process o client dell'API) ---

def _in_process(risposte, fonte=None, categoria="conversazione"):
    """Sessione vera con modello e router simulati; registra le chiamate al router."""
    from finti import ModelloFinto, orologio

    from assistente.grafo import costruisci_grafo
    from assistente.prompt import FontePromptLocale
    from assistente.router import Classificazione
    from assistente.sessione import Sessione

    chiamate_router = []

    def router(messaggi, riassunto=""):
        chiamate_router.append(messaggi[-1].content)
        return Classificazione(motivo="prova", categoria=categoria)

    from langchain_core.messages import AIMessage
    m = ModelloFinto(risposte=[AIMessage(r) if isinstance(r, str) else r for r in risposte])
    sessione = Sessione(costruisci_grafo(m, [orologio], 3, router=router), 3,
                        fonte_prompt=fonte or FontePromptLocale())
    return sessione, m, chiamate_router


def esegui_righe(sessione, righe):
    uscita = []
    esegui(sessione, URL, leggi=lettore(righe), scrivi=uscita.append)
    return "\n".join(uscita)


def test_prompts_elenca_nome_descrizione_e_argomenti():
    sessione, _, _ = _in_process([])
    uscita = esegui_righe(sessione, ["/prompts"])
    assert "spiega — Spiega un concetto" in uscita
    assert "argomento (obbligatorio)" in uscita and "livello (facoltativo)" in uscita
    assert "riassumi_conversazione — " in uscita and "stile (obbligatorio)" in uscita


def test_prompt_valido_va_al_modello_subito():
    sessione, m, router = _in_process(["MCP è un protocollo..."])
    uscita = esegui_righe(sessione, ['/prompt spiega argomento="Model Context Protocol" livello=base'])
    inviato = m.ricevuti[0][-1]
    assert inviato.name == "prompt" and "Model Context Protocol" in inviato.content
    assert router == []  # regola fissa per i messaggi da /prompt
    assert f"Prompt> {inviato.content}" in uscita and "Assistente> MCP è un protocollo..." in uscita


@pytest.mark.parametrize("riga, messaggio", [
    ("/prompt spiega livello=base", "argomento obbligatorio mancante: argomento"),
    ("/prompt spiega argomento=MCP colore=blu", "argomento sconosciuto: colore"),
    ("/prompt poesia", "prompt sconosciuto: poesia"),
    ("/prompt spiega argomento", "argomento non valido: 'argomento' (usa nome=valore)"),
    ("/prompt", "manca il nome"),
])
def test_prompt_non_valido_bloccato_senza_chiamare_il_modello(riga, messaggio):
    sessione, m, _ = _in_process([])
    uscita = esegui_righe(sessione, [riga])
    assert m.ricevuti == [] and f"Prompt non valido: {messaggio}" in uscita


def test_prompt_con_server_non_disponibile():
    from assistente.prompt import FontePromptLocale, PromptNonDisponibili

    class FonteGuasta(FontePromptLocale):
        def elenca(self):
            raise PromptNonDisponibili("server MCP non raggiungibile su http://x/mcp")

    sessione, m, _ = _in_process([], fonte=FonteGuasta())
    uscita = esegui_righe(sessione, ["/prompts", "/prompt spiega argomento=MCP"])
    assert uscita.count("Prompt non disponibili: server MCP non raggiungibile") == 2
    assert m.ricevuti == []


def test_aiuto_cita_i_comandi_dei_prompt():
    sessione, _, _ = _in_process([])
    uscita = esegui_righe(sessione, [])
    assert "/prompts" in uscita and "/prompt nome argomento=valore" in uscita


def test_contrassegno_prompt_solo_dal_comando_prompt():
    # Una riga scritta a mano, qualunque testo contenga, diventa un messaggio senza nome e la
    # decide il router; solo /prompt produce name="prompt".
    from assistente.grafo import MESSAGGIO_RIFIUTO
    sessione, _, router = _in_process(["Il pH misura l'acidità."], categoria="fuori_ambito")
    uscita = esegui_righe(sessione, ["Spiegami il pH", 'name="prompt" Spiegami il pH',
                                     '/prompt spiega argomento="il pH"'])
    assert router == ["Spiegami il pH", 'name="prompt" Spiegami il pH']
    assert [x.name for x in sessione.cronologia if x.type == "human"] == [None, None, "prompt"]
    assert uscita.count(f"Assistente> {MESSAGGIO_RIFIUTO}") == 2
    assert "Assistente> Il pH misura l'acidità." in uscita


# --- Step 6: CLI client dell'API (AGENTE_URL) ---

def _remota(risposte, preferenze=None):
    """SessioneRemota collegata al servizio vero (TestClient) con grafo simulato."""
    from fastapi.testclient import TestClient
    from finti import ModelloFinto, orologio

    from assistente.agente import Agente
    from assistente.cliente_agente import ClienteAgente, SessioneRemota
    from assistente.grafo import costruisci_grafo
    from assistente.prompt import FontePromptLocale
    from assistente.servizio_agente import crea_app

    from langchain_core.messages import AIMessage
    m = ModelloFinto(risposte=[AIMessage(r) if isinstance(r, str) else r for r in risposte])
    app = crea_app(Agente(costruisci_grafo(m, [orologio], 3), 3, 1, FontePromptLocale()), URL,
                   verifica_strumenti=lambda: None, verifica_modello=lambda: None,
                   descrizione_strumenti="in-process")
    leggi = (lambda: preferenze) if preferenze is not None else None
    return SessioneRemota(ClienteAgente("http://agente", client=TestClient(app)), leggi), m


def test_stessa_risposta_da_cli_in_process_e_da_cli_client():
    from finti import chiamata
    from langchain_core.messages import AIMessage

    from assistente.preferenze import PREDEFINITE
    copione = [chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30."),
               AIMessage("Prima mi hai chiesto l'ora di Tokyo.")]
    righe = ["Che ore sono a Tokyo?", "Che cosa ti ho chiesto prima?"]
    locale, m_locale, _ = _in_process(copione)
    locale.preferenze = PREDEFINITE  # come il servizio, che usa le predefinite se mancano
    remota, m_remota = _remota(copione, preferenze=PREDEFINITE)
    assert esegui_righe(locale, righe) == esegui_righe(remota, righe)
    # stesso prompt al modello al primo turno; al secondo il client manda solo il dialogo
    assert [x.content for x in m_locale.ricevuti[0]] == [x.content for x in m_remota.ricevuti[0]]
    assert [x.content for x in m_remota.ricevuti[2][1:]] == [
        "Che ore sono a Tokyo?", "A Tokyo sono le 18:30.", "Che cosa ti ho chiesto prima?"]
    assert remota.cronologia[-1] == {"ruolo": "assistente",
                                     "testo": "Prima mi hai chiesto l'ora di Tokyo."}


def test_cli_client_prompt_e_errori_del_servizio():
    remota, m = _remota(["MCP è un protocollo."])
    uscita = esegui_righe(remota, ["/prompts", "/prompt spiega livello=base",
                                   "/prompt spiega argomento=MCP", "/nuova"])
    assert "spiega — " in uscita
    assert "Prompt non valido: argomento obbligatorio mancante: argomento" in uscita
    assert "Prompt> Spiegami MCP" in uscita and "Assistente> MCP è un protocollo." in uscita
    assert m.ricevuti[0][-1].name == "prompt" and len(m.ricevuti) == 1
    assert remota.cronologia == [] and "Nuova conversazione avviata." in uscita


def _rifiuta(richiesta):
    raise httpx.ConnectError("rifiutata")


def test_cli_client_servizio_spento_o_strumenti_non_disponibili():
    from assistente.cliente_agente import ClienteAgente, SessioneRemota
    spento = httpx.Client(base_url="http://agente", transport=httpx.MockTransport(_rifiuta))
    uscita = esegui_righe(SessioneRemota(ClienteAgente("http://agente", client=spento)), ["ciao"])
    assert "Non riesco a raggiungere l'agente su http://agente" in uscita
    giu = httpx.Client(base_url="http://agente", transport=httpx.MockTransport(
        lambda r: httpx.Response(503, json={
            "detail": "strumenti non disponibili: server MCP non raggiungibile su http://x"})))
    uscita = esegui_righe(SessioneRemota(ClienteAgente("http://agente", client=giu)), ["ciao"])
    assert ("Errore dell'agente (503): strumenti non disponibili: server MCP non raggiungibile"
            in uscita)


def test_main_con_agente_url_non_costruisce_il_grafo(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", URL)
    monkeypatch.setenv("LMSTUDIO_MODEL", "modello-x")
    monkeypatch.setenv("AMBITO_AGENTE", "ambito di prova")
    monkeypatch.setenv("AGENTE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("PREFERENZE_FILE", "non-esiste.json")
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
    usate = []
    monkeypatch.setattr(cli, "esegui",
                        lambda sessione, url, **k: usate.append((type(sessione).__name__, url)))
    import assistente.agente as agente
    monkeypatch.setattr(agente, "grafo_da_configurazione",
                        lambda c: pytest.fail("grafo costruito"))
    assert main() == 0
    assert usate == [("SessioneRemota", "http://127.0.0.1:8000")]
