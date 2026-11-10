"""Back-end con archivio in memoria e agente vero (grafo simulato), più il contratto con l'agente."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from finti import ModelloFinto, chiamata, orologio
from langchain_core.messages import AIMessage

from assistente.agente import Agente
from assistente.archivio import ArchivioMemoria
from assistente.backend import corpo_messaggio, corpo_prompt, crea_backend, titolo_da
from assistente.cliente_agente import PERCORSI_USATI, ClienteAgente
from assistente.grafo import costruisci_grafo
from assistente.preferenze import Preferenze, prompt_preferenze
from assistente.prompt import FontePromptLocale
from assistente.servizio_agente import crea_app

DOCS = Path(__file__).parent.parent / "docs"
URL_AGENTE = "http://agente"


class Commutabile:
    """Client HTTP che si può «spegnere» a metà prova: delega a quello corrente."""

    def __init__(self, client):
        self.corrente = client

    def request(self, *a, **k):
        return self.corrente.request(*a, **k)


def _rifiuta(richiesta):
    raise httpx.ConnectError("rifiutata")


def _lento(richiesta):
    raise httpx.ReadTimeout("nessuna risposta")


SPENTO = httpx.Client(base_url=URL_AGENTE, transport=httpx.MockTransport(_rifiuta))
LENTO = httpx.Client(base_url=URL_AGENTE, transport=httpx.MockTransport(_lento))


class Ambiente:
    def __init__(self, risposte=(), preferenze=None, strumenti_giu=None):
        self.modello = ModelloFinto(risposte=[AIMessage(r) if isinstance(r, str) else r
                                              for r in risposte])
        agente = Agente(costruisci_grafo(self.modello, [orologio], 3), 3, 1, FontePromptLocale())
        self.app_agente = crea_app(agente, "http://lm/v1", verifica_strumenti=lambda: strumenti_giu,
                                   verifica_modello=lambda: None, descrizione_strumenti="in-process")
        self.agente_http = Commutabile(TestClient(self.app_agente))
        self.archivio = ArchivioMemoria()
        lettore = (lambda: preferenze) if preferenze is not None else (lambda: Preferenze())
        self.client = TestClient(crea_backend(
            self.archivio, ClienteAgente(URL_AGENTE, client=self.agente_http, timeout=900),
            lettore, URL_AGENTE))

    def nuova(self, **corpo):
        r = self.client.post("/conversazioni", json=corpo or None)
        assert r.status_code == 201, r.text
        return r.json()["id"]


def test_due_turni_con_strumento_storico_titolo_ed_elenco():
    a = Ambiente([chiamata("Asia/Tokyo", "1"), "A Tokyo sono le 18:30.",
                  "Mi hai chiesto l'ora di Tokyo."])
    id = a.nuova()
    primo = a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "Che ore sono a Tokyo?"})
    assert primo.status_code == 200, primo.text
    assert primo.json()["domanda"]["stato"] == "risposta"
    assert primo.json()["risposta"]["testo"] == "A Tokyo sono le 18:30."
    assert primo.json()["risposta"]["strumenti"][0]["nome"] == "ora_corrente"
    secondo = a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "Che cosa ti ho chiesto?"})
    assert secondo.status_code == 200
    # al secondo turno l'agente riceve la cronologia salvata dopo il primo
    assert [m.content for m in a.modello.ricevuti[2][1:]] == [
        "Che ore sono a Tokyo?", "A Tokyo sono le 18:30.", "Che cosa ti ho chiesto?"]
    conv = a.client.get(f"/conversazioni/{id}").json()
    assert conv["titolo"] == "Che ore sono a Tokyo?"
    assert [(m["ruolo"], m["testo"]) for m in conv["messaggi"]] == [
        ("utente", "Che ore sono a Tokyo?"), ("assistente", "A Tokyo sono le 18:30."),
        ("utente", "Che cosa ti ho chiesto?"), ("assistente", "Mi hai chiesto l'ora di Tokyo.")]
    elenco = a.client.get("/conversazioni").json()
    assert elenco[0]["id"] == id and elenco[0]["titolo"] == "Che ore sono a Tokyo?"
    assert elenco[0]["ultimo_messaggio"] == conv["messaggi"][-1]["creato"]
    stato = a.archivio.leggi(id)  # stato dell'agente salvato così come restituito
    assert len(stato.cronologia_agente) == 4 and not stato.turno_in_corso


def test_preferenze_alla_creazione_e_con_put():
    a = Ambiente(["ok", "ok"], preferenze=Preferenze(lingua="en"))
    id = a.nuova()
    assert a.client.get(f"/conversazioni/{id}").json()["preferenze"]["lingua"] == "en"
    a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "ciao"})
    assert a.modello.ricevuti[0][0].content.startswith(prompt_preferenze(Preferenze(lingua="en")))
    nuove = {"lingua": "fr", "fuso_orario": "America/New_York", "stile": "dettagliato"}
    assert a.client.put(f"/conversazioni/{id}/preferenze", json=nuove).status_code == 200
    a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "ancora"})
    assert a.modello.ricevuti[1][0].content.startswith(prompt_preferenze(Preferenze(**nuove)))
    id2 = a.nuova(preferenze={"stile": "dettagliato"})
    assert a.client.get(f"/conversazioni/{id2}").json()["preferenze"]["stile"] == "dettagliato"
    assert a.client.put(f"/conversazioni/{id}/preferenze",
                        json={"fuso_orario": "Marte/Base"}).status_code == 422


def test_secondo_invio_durante_un_turno_409():
    a = Ambiente()
    id = a.nuova()
    a.archivio.inizia_turno(id)  # un turno già in corso
    r = a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "ciao"})
    assert r.status_code == 409 and "turno" in r.json()["detail"]
    assert a.archivio.messaggi(id) == []


def test_agente_spento_domanda_salvata_in_errore_e_riprova_senza_duplicati():
    a = Ambiente(["Ciao!"])
    id = a.nuova()
    a.agente_http.corrente = SPENTO
    r = a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "ciao"})
    assert r.status_code == 503
    assert r.json()["detail"] == f"agente non raggiungibile su {URL_AGENTE}"
    (domanda,) = a.client.get(f"/conversazioni/{id}").json()["messaggi"]
    assert domanda["stato"] == "errore" and domanda["errore"] == f"agente non raggiungibile su {URL_AGENTE}"
    assert not a.archivio.leggi(id).turno_in_corso
    a.agente_http.corrente = TestClient(a.app_agente)
    r = a.client.post(f"/conversazioni/{id}/riprova")
    assert r.status_code == 200 and r.json()["domanda"]["id"] == domanda["id"]
    messaggi = a.client.get(f"/conversazioni/{id}").json()["messaggi"]
    assert [(m["ruolo"], m["testo"], m["stato"]) for m in messaggi] == [
        ("utente", "ciao", "risposta"), ("assistente", "Ciao!", None)]
    assert a.client.post(f"/conversazioni/{id}/riprova").status_code == 409  # niente da riprovare


def test_timeout_e_errore_dell_agente():
    a = Ambiente(strumenti_giu="server MCP non raggiungibile su http://x/mcp")
    id = a.nuova()
    r = a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "Che ore sono?"})
    assert r.status_code == 503
    assert r.json()["detail"] == "agente: strumenti non disponibili: server MCP non raggiungibile su http://x/mcp"
    a.agente_http.corrente = LENTO
    r = a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "di nuovo"})
    assert r.status_code == 504 and r.json()["detail"] == "l'agente non ha risposto entro 900 s"
    assert [m["stato"] for m in a.client.get(f"/conversazioni/{id}").json()["messaggi"]] == [
        "errore", "errore"]


def test_domanda_in_errore_non_va_all_agente_al_turno_dopo():
    a = Ambiente(["ok"])
    id = a.nuova()
    a.agente_http.corrente = SPENTO
    a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "persa"})
    a.agente_http.corrente = TestClient(a.app_agente)
    assert a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "nuova"}).status_code == 200
    assert [m.content for m in a.modello.ricevuti[0][1:]] == ["nuova"]
    assert len(a.client.get(f"/conversazioni/{id}").json()["messaggi"]) == 3


def test_prompt_valido_e_non_valido():
    a = Ambiente(["MCP è un protocollo."])
    id = a.nuova()
    r = a.client.post(f"/conversazioni/{id}/prompt",
                      json={"nome": "spiega", "argomenti": {"argomento": "MCP"}})
    assert r.status_code == 200, r.text
    assert r.json()["domanda"]["testo"].startswith("Spiegami MCP")
    assert r.json()["domanda"]["prompt"] == {"nome": "spiega", "argomenti": {"argomento": "MCP"}}
    assert a.modello.ricevuti[0][-1].name == "prompt"
    assert a.client.get(f"/conversazioni/{id}").json()["titolo"] == "spiega: MCP"
    r = a.client.post(f"/conversazioni/{id}/prompt", json={"nome": "spiega", "argomenti": {}})
    assert r.status_code == 422
    assert r.json()["detail"] == "prompt non valido: argomento obbligatorio mancante: argomento"
    assert len(a.client.get(f"/conversazioni/{id}").json()["messaggi"]) == 2  # non salvata


def test_elenco_prompt_eliminazione_e_404():
    a = Ambiente()
    assert [p["nome"] for p in a.client.get("/prompt").json()] == ["spiega", "riassumi_conversazione"]
    id = a.nuova()
    assert a.client.delete(f"/conversazioni/{id}").status_code == 204
    assert a.client.get(f"/conversazioni/{id}").status_code == 404
    assert a.client.post(f"/conversazioni/{id}/messaggi", json={"testo": "x"}).status_code == 404
    assert a.client.get("/conversazioni/non-un-uuid").status_code == 404


def test_stato_di_backend_database_e_agente():
    a = Ambiente()
    ok = a.client.get("/stato")
    assert ok.status_code == 200
    assert ok.json()["backend"]["stato"] == "ok" and ok.json()["database"]["stato"] == "ok"
    assert ok.json()["agente"]["stato"] == "ok"
    assert ok.json()["agente"]["componenti"]["strumenti"]["dettaglio"] == "in-process"
    a.agente_http.corrente = SPENTO
    giu = a.client.get("/stato")
    assert giu.status_code == 503
    assert giu.json()["agente"] == {"stato": "errore", "dettaglio": f"agente non raggiungibile su {URL_AGENTE}",
                                    "componenti": None}


@pytest.mark.parametrize("testo, titolo", [
    ("Che ore sono a Tokyo?", "Che ore sono a Tokyo?"),
    ("Quanti giorni lavorativi ci sono dal 21 al 31 dicembre 2026?",
     "Quanti giorni lavorativi ci sono dal…"),
    ("  spazi   multipli\ne a capo  ", "spazi multipli e a capo"),
    ("x" * 80, "x" * 59 + "…"),
])
def test_titolo_dalle_prime_parole(testo, titolo):
    assert titolo_da(testo) == titolo


def test_openapi_del_backend_consultabile_e_uguale_al_file():
    client = Ambiente().client
    assert client.get("/docs").status_code == 200
    generato = client.get("/openapi.json").json()
    assert json.loads((DOCS / "openapi-backend.json").read_text(encoding="utf-8")) == generato, (
        "contratto cambiato: rigenera docs/openapi-backend.json")


def _schema(spec, nome):
    return spec["components"]["schemas"][nome]


def test_contratto_con_l_agente_da_docs_openapi_agente():
    spec = json.loads((DOCS / "openapi-agente.json").read_text(encoding="utf-8"))
    for metodo, percorso in PERCORSI_USATI:
        assert metodo.lower() in spec["paths"].get(percorso, {}), f"{metodo} {percorso} non nel contratto"
    conv = ArchivioMemoria().crea({"lingua": "it", "fuso_orario": "Europe/Rome", "stile": "sintetico"})
    for corpo, nome in ((corpo_messaggio(conv, "ciao"), "RichiestaMessaggio"),
                        (corpo_prompt(conv, "spiega", {"argomento": "x"}), "RichiestaPrompt")):
        schema = _schema(spec, nome)
        assert set(corpo) <= set(schema["properties"]), set(corpo) - set(schema["properties"])
        assert set(schema.get("required", [])) <= set(corpo)
    voce = _schema(spec, "VoceCronologia")
    assert set(voce["properties"]) == {"ruolo", "testo"}


def test_prompt_non_valido_come_prima_domanda_non_lascia_il_titolo():
    a = Ambiente()
    id = a.nuova()
    assert a.client.post(f"/conversazioni/{id}/prompt", json={"nome": "poesia"}).status_code == 422
    assert a.client.get(f"/conversazioni/{id}").json()["titolo"] is None


def test_cors_solo_per_l_origine_del_front_end():
    a = Ambiente()
    app = crea_backend(a.archivio, ClienteAgente(URL_AGENTE, client=a.agente_http), Preferenze,
                       URL_AGENTE, ["http://127.0.0.1:8090"])
    client = TestClient(app)
    preflight = {"Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"}
    ok = client.options("/conversazioni", headers={"Origin": "http://127.0.0.1:8090", **preflight})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "http://127.0.0.1:8090"
    altro = client.options("/conversazioni", headers={"Origin": "http://evil.example", **preflight})
    assert "access-control-allow-origin" not in altro.headers
    r = client.get("/conversazioni", headers={"Origin": "http://127.0.0.1:8090"})
    assert r.headers["access-control-allow-origin"] == "http://127.0.0.1:8090"
