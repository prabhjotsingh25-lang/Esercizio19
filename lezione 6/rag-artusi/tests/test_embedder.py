import json

import httpx
import pytest

from rag.embedder import EmbedderLMStudio, ErroreEmbedding
from tests.finti import EmbedderFinto

URL = "http://x/v1"


def _embedder(gestore, batch=32):
    return EmbedderLMStudio(URL, "m", batch, client=httpx.Client(transport=httpx.MockTransport(gestore)))


def _risposta(testi, inverti=False):
    dati = [{"index": i, "embedding": [float(i), 1.0]} for i in range(len(testi))]
    if inverti:
        dati.reverse()
    return httpx.Response(200, json={"data": dati})


def test_richiesta_corretta():
    richieste = []

    def gestore(req):
        richieste.append(req)
        return _risposta(json.loads(req.content)["input"])

    _embedder(gestore).embed(["a", "b"])
    assert str(richieste[0].url) == "http://x/v1/embeddings"
    assert richieste[0].method == "POST"
    assert json.loads(richieste[0].content) == {"model": "m", "input": ["a", "b"]}


def test_lotti():
    lotti = []

    def gestore(req):
        testi = json.loads(req.content)["input"]
        lotti.append(testi)
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": [float(ord(t))]} for i, t in enumerate(testi)]}
        )

    vettori = _embedder(gestore, batch=2).embed(list("abcde"))
    assert lotti == [["a", "b"], ["c", "d"], ["e"]]
    assert vettori == [[float(ord(c))] for c in "abcde"]


def test_ordine_per_index():
    vettori = _embedder(lambda req: _risposta(["a", "b", "c"], inverti=True)).embed(["a", "b", "c"])
    assert vettori == [[0.0, 1.0], [1.0, 1.0], [2.0, 1.0]]


def test_lista_vuota_nessuna_richiesta():
    def gestore(req):
        raise AssertionError("nessuna richiesta attesa")

    assert _embedder(gestore).embed([]) == []


def test_errore_http():
    with pytest.raises(ErroreEmbedding) as e:
        _embedder(lambda req: httpx.Response(500, text="boom")).embed(["a"])
    assert URL in str(e.value) and "m" in str(e.value)


def test_lmstudio_spento():
    def gestore(req):
        raise httpx.ConnectError("rifiutata")

    with pytest.raises(ErroreEmbedding) as e:
        _embedder(gestore).embed(["a"])
    assert URL in str(e.value)


def test_numero_vettori_sbagliato():
    with pytest.raises(ErroreEmbedding):
        _embedder(lambda req: _risposta(["a"])).embed(["a", "b"])


def test_risposta_malformata():
    with pytest.raises(ErroreEmbedding):
        _embedder(lambda req: httpx.Response(200, json={"errore": "x"})).embed(["a"])


def test_finto_deterministico():
    finto = EmbedderFinto()
    a1, b = finto.embed(["ciao", "altro"])
    (a2,) = finto.embed(["ciao"])
    assert a1 == a2
    assert a1 != b
    assert len(a1) == finto.dimensione
    assert finto.ricevuti == ["ciao", "altro", "ciao"]
    assert finto.chiamate == 2
