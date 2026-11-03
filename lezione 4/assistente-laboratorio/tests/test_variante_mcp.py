"""Adattatore MCP: stessi strumenti del catalogo, eseguiti tramite il client FastMCP."""
import mcp.types as tipi
import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.exceptions import MCPError
from finti import ISTANTE
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.catalogo import strumenti_locali
from assistente.server_mcp import crea_server
from assistente.variante_mcp import crea_strumenti_mcp

URL = "http://servizio-mcp:8002/mcp"


def _per_nome(strumenti):
    return {s.name: s for s in strumenti}


def _con_server():
    server = crea_server(strumenti_locali(lambda: ISTANTE))
    return _per_nome(crea_strumenti_mcp(URL, strumenti_locali(), crea_client=lambda: Client(server)))


class ClientFinto:
    """Client asincrono finto: registra le chiamate e restituisce o solleva quanto preparato."""

    def __init__(self, esito=None, all_apertura=None):
        self.esito, self.all_apertura, self.chiamate = esito, all_apertura, []

    async def __aenter__(self):
        if self.all_apertura:
            raise self.all_apertura
        return self

    async def __aexit__(self, *eccezione):
        return False

    async def call_tool(self, nome, argomenti, **opzioni):
        self.chiamate.append((nome, argomenti, opzioni))
        if isinstance(self.esito, BaseException):
            raise self.esito
        return self.esito


def _con_finto(finto):
    return _per_nome(crea_strumenti_mcp(URL, strumenti_locali(), crea_client=lambda: finto))


def _risultato(*testi, errore=False):
    return CallToolResult(content=[tipi.TextContent(type="text", text=t) for t in testi],
                          structured_content=None, meta=None, is_error=errore)


def test_definizioni_identiche_alle_locali():
    locali = strumenti_locali()
    remoti = crea_strumenti_mcp(URL, locali, crea_client=lambda: ClientFinto())
    assert [convert_to_openai_tool(s) for s in remoti] == [convert_to_openai_tool(s) for s in locali]


def test_chiamate_attraverso_il_server():
    strumenti = _con_server()
    assert strumenti["ora_corrente"].invoke({"fuso_orario": "Asia/Tokyo"}).startswith(
        "2026-10-26T18:30:05+09:00")
    assert strumenti["convertitore_unita"].invoke({"valore": 1.5, "da": "km", "a": "m"}) == "1.5 km = 1500 m"
    assert strumenti["calcolatrice_sicura"].invoke({"espressione": "2 ^ 3"}).startswith("Errore:")


def test_argomenti_validati_prima_della_chiamata():
    finto = ClientFinto(_risultato("ok"))
    with pytest.raises(Exception, match="validation error"):
        _con_finto(finto)["convertitore_unita"].invoke({"valore": 1})
    assert finto.chiamate == []


def test_richiesta_inviata():
    finto = ClientFinto(_risultato("ok"))
    assert _con_finto(finto)["convertitore_unita"].invoke({"valore": 2, "da": "m", "a": "cm"}) == "ok"
    nome, argomenti, opzioni = finto.chiamate[0]
    assert (nome, argomenti) == ("convertitore_unita", {"valore": 2.0, "da": "m", "a": "cm"})
    assert opzioni == {"timeout": 10, "raise_on_error": False}


@pytest.mark.parametrize("finto, atteso", [
    (ClientFinto(all_apertura=RuntimeError("Client failed to connect: All connection attempts failed")),
     f"Errore: server MCP non raggiungibile su {URL}."),
    (ClientFinto(MCPError(tipi.REQUEST_TIMEOUT, "Request 'tools/call' timed out")),
     "Errore: il server MCP non ha risposto entro 10 secondi."),
    (ClientFinto(MCPError(tipi.INTERNAL_ERROR, "guasto interno")),
     "Errore: il server MCP ha restituito un errore: guasto interno."),
    (ClientFinto(_risultato("argomenti non validi: valore", errore=True)),
     "Errore: il server MCP ha rifiutato la chiamata: argomenti non validi: valore."),
    (ClientFinto(_risultato()), "Errore: risposta del server MCP non valida."),
    (ClientFinto(CallToolResult(content=[tipi.ImageContent(type="image", data="AA==", mime_type="image/png")],
                                structured_content=None, meta=None)),
     "Errore: risposta del server MCP non valida."),
])
def test_errori_di_rete_e_di_protocollo(finto, atteso):
    assert _con_finto(finto)["calcolatrice_sicura"].invoke({"espressione": "1 + 1"}) == atteso


def test_errore_inatteso_non_viene_nascosto():
    finto = ClientFinto(all_apertura=RuntimeError("altro problema"))
    with pytest.raises(RuntimeError, match="altro problema"):
        _con_finto(finto)["calcolatrice_sicura"].invoke({"espressione": "1 + 1"})
