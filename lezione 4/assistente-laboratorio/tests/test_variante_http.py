"""Wrapper HTTP: stessi strumenti del catalogo, eseguiti chiamando il servizio."""
import httpx
import pytest
from fastapi.testclient import TestClient
from finti import ISTANTE
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.catalogo import strumenti_locali
from assistente.servizio_http import crea_app
from assistente.variante_http import crea_strumenti_http

URL = "http://servizio:8001"


def _per_nome(strumenti):
    return {s.name: s for s in strumenti}


def _con_servizio():
    client = TestClient(crea_app(strumenti_locali(lambda: ISTANTE)))
    return _per_nome(crea_strumenti_http(URL, strumenti_locali(), client=client))


def _con_risposta(gestore):
    client = httpx.Client(transport=httpx.MockTransport(gestore), base_url=URL)
    return _per_nome(crea_strumenti_http(URL, strumenti_locali(), client=client))


def test_definizioni_identiche_alle_locali():
    locali = strumenti_locali()
    remoti = crea_strumenti_http(URL, locali, client=httpx.Client(base_url=URL))
    assert [convert_to_openai_tool(s) for s in remoti] == [convert_to_openai_tool(s) for s in locali]


def test_chiamate_attraverso_il_servizio():
    strumenti = _con_servizio()
    assert strumenti["ora_corrente"].invoke({"fuso_orario": "Asia/Tokyo"}).startswith(
        "2026-10-26T18:30:05+09:00")
    assert strumenti["convertitore_unita"].invoke({"valore": 1.5, "da": "km", "a": "m"}) == "1.5 km = 1500 m"
    assert strumenti["calcolatrice_sicura"].invoke({"espressione": "2 ^ 3"}).startswith("Errore:")


def test_argomenti_validati_prima_della_chiamata():
    chiamate = []
    strumenti = _con_risposta(lambda richiesta: chiamate.append(richiesta) or httpx.Response(200))
    with pytest.raises(Exception, match="validation error"):
        strumenti["convertitore_unita"].invoke({"valore": 1})
    assert chiamate == []


def test_richiesta_inviata():
    ricevute = []

    def gestore(richiesta):
        ricevute.append(richiesta)
        return httpx.Response(200, json={"risultato": "ok"})

    strumenti = _con_risposta(gestore)
    assert strumenti["convertitore_unita"].invoke({"valore": 2, "da": "m", "a": "cm"}) == "ok"
    assert ricevute[0].method == "POST" and ricevute[0].url.path == "/strumenti/convertitore_unita"
    assert ricevute[0].read() == b'{"valore":2.0,"da":"m","a":"cm"}'


def _solleva(eccezione):
    def gestore(richiesta):
        raise eccezione("guasto simulato", request=richiesta)
    return gestore


@pytest.mark.parametrize("gestore, atteso", [
    (_solleva(httpx.ConnectError), f"Errore: servizio strumenti non raggiungibile su {URL}."),
    (_solleva(httpx.ReadTimeout), "Errore: il servizio strumenti non ha risposto entro 10 secondi."),
    (lambda r: httpx.Response(404, json={"detail": "strumento sconosciuto"}),
     "Errore: strumento sconosciuto al servizio: calcolatrice_sicura."),
    (lambda r: httpx.Response(422, json={"detail": [{"campo": "espressione", "messaggio": "x"}]}),
     "Errore: argomenti rifiutati dal servizio: espressione: x."),
    (lambda r: httpx.Response(500, text="Internal Server Error"),
     "Errore: il servizio strumenti ha risposto con il codice 500."),
    (lambda r: httpx.Response(200, text="non json"), "Errore: risposta del servizio strumenti non valida."),
    (lambda r: httpx.Response(200, json={"altro": 1}), "Errore: risposta del servizio strumenti non valida."),
    (lambda r: httpx.Response(200, json={"risultato": 42}), "Errore: risposta del servizio strumenti non valida."),
])
def test_errori_di_rete_e_di_protocollo(gestore, atteso):
    assert _con_risposta(gestore)["calcolatrice_sicura"].invoke({"espressione": "1 + 1"}) == atteso
