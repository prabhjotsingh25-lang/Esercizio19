"""Server FastMCP degli strumenti, provato con il client in memoria (nessuna rete)."""
import asyncio

import pytest
from fastmcp import Client
from finti import ISTANTE

from assistente.catalogo import strumenti_locali
from assistente.server_mcp import crea_server


def _con_client(azione):
    server = crea_server(strumenti_locali(lambda: ISTANTE))

    async def esegui():
        async with Client(server) as client:
            return await azione(client)

    return asyncio.run(esegui())


def _testo(risultato):
    return "".join(blocco.text for blocco in risultato.content)


def test_elenco_con_le_definizioni_del_catalogo():
    strumenti = _con_client(lambda c: c.list_tools())
    catalogo = strumenti_locali()
    assert [s.name for s in strumenti] == [s.name for s in catalogo]
    for pubblicato, atteso in zip(strumenti, catalogo):
        assert pubblicato.description == atteso.description
        assert pubblicato.input_schema == atteso.args_schema.model_json_schema()


@pytest.mark.parametrize("nome, argomenti, atteso", [
    ("ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "2026-10-26T18:30:05+09:00 (Asia/Tokyo)"),
    ("convertitore_unita", {"valore": 1.5, "da": "km", "a": "m"}, "1.5 km = 1500 m"),
    ("calcolatrice_sicura", {"espressione": "(17 + 4) * 3"}, "(17 + 4) * 3 = 63"),
    ("catalogo_locale", {"codice": "XYZ-99"}, "Nessun articolo con codice 'XYZ-99'."),
])
def test_esecuzione_valida(nome, argomenti, atteso):
    risultato = _con_client(lambda c: c.call_tool(nome, argomenti, raise_on_error=False))
    assert not risultato.is_error and _testo(risultato) == atteso


def test_errore_dello_strumento_resta_un_risultato():
    risultato = _con_client(lambda c: c.call_tool(
        "calcolatrice_sicura", {"espressione": "1 / 0"}, raise_on_error=False))
    assert not risultato.is_error and _testo(risultato) == "Errore: divisione per zero."


@pytest.mark.parametrize("argomenti", [{}, {"valore": "tanti", "da": "km", "a": "m"}])
def test_argomenti_non_validi(argomenti):
    risultato = _con_client(lambda c: c.call_tool("convertitore_unita", argomenti, raise_on_error=False))
    assert risultato.is_error and "valore" in _testo(risultato)


def test_strumento_sconosciuto():
    risultato = _con_client(lambda c: c.call_tool("meteo", {}, raise_on_error=False))
    assert risultato.is_error and "meteo" in _testo(risultato)
