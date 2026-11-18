import json

import httpx
import pytest

from rag.llm import ErroreLLM, LLMLMStudio, RispostaNonValida
from tests.conftest import crea_config

SCHEMA = {"type": "object", "properties": {"query": {"type": "array", "items": {"type": "string"}}},
          "required": ["query"]}


def _llm(gestore, **config):
    richieste = []

    def registra(request):
        richieste.append(request)
        return gestore(request)

    client = httpx.Client(transport=httpx.MockTransport(registra))
    return LLMLMStudio(crea_config(**config), client=client), richieste


def _risposta(contenuto, status=200):
    return lambda request: httpx.Response(status, json={"choices": [{"message": {"content": contenuto}}]})


def test_richiesta_vincolata_e_json_valido():
    llm, richieste = _llm(_risposta('{"query": ["gnocchi di patate"]}'))
    assert llm.json("sistema", "utente", SCHEMA, "riscrittura") == {"query": ["gnocchi di patate"]}
    assert llm.chiamate == 1
    corpo = json.loads(richieste[0].content)
    assert str(richieste[0].url) == "http://localhost:1234/v1/chat/completions"
    assert corpo["model"] == "google/gemma-4-e2b"
    assert corpo["messages"] == [{"role": "system", "content": "sistema"}, {"role": "user", "content": "utente"}]
    assert corpo["temperature"] == 0.0 and corpo["seed"] == 42 and corpo["reasoning_effort"] == "none"
    assert corpo["max_tokens"] == 300
    assert corpo["response_format"] == {"type": "json_schema", "json_schema": {
        "name": "riscrittura", "strict": True, "schema": SCHEMA}}


def test_seed_e_reasoning_assenti_se_non_configurati():
    llm, richieste = _llm(_risposta('{"query": []}'), llm_seed=None, llm_reasoning_effort=None)
    llm.json("s", "u", SCHEMA, "x")
    corpo = json.loads(richieste[0].content)
    assert "seed" not in corpo and "reasoning_effort" not in corpo


@pytest.mark.parametrize("contenuto", ["non è json", '```json\n{"query": []}\n```', '["a"]', ""])
def test_contenuto_non_valido(contenuto):
    llm, _ = _llm(_risposta(contenuto))
    with pytest.raises(RispostaNonValida):
        llm.json("s", "u", SCHEMA, "x")


def test_risposta_senza_choices():
    llm, _ = _llm(lambda r: httpx.Response(200, json={"errore": "x"}))
    with pytest.raises(RispostaNonValida):
        llm.json("s", "u", SCHEMA, "x")


def test_http_400():
    llm, _ = _llm(lambda r: httpx.Response(400, text="reasoning_effort not supported"))
    with pytest.raises(ErroreLLM, match="HTTP 400"):
        llm.json("s", "u", SCHEMA, "x")
    assert llm.chiamate == 1


def test_connessione_rifiutata():
    def rifiuta(request):
        raise httpx.ConnectError("rifiutata")
    llm, _ = _llm(rifiuta)
    with pytest.raises(ErroreLLM, match="connessione"):
        llm.json("s", "u", SCHEMA, "x")
