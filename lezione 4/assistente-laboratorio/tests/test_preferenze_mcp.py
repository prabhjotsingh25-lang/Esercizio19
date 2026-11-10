"""Resource `utente://preferenze`: pubblicata dal server MCP e letta dall'host (variante mcp)."""
import asyncio

import mcp.types as tipi
from fastmcp import Client
from fastmcp.exceptions import MCPError

from assistente.catalogo import strumenti_locali
from assistente.preferenze import PREDEFINITE, URI_PREFERENZE, Preferenze
from assistente.server_mcp import crea_server
from assistente.variante_mcp import crea_lettore_mcp, crea_strumenti_mcp

URL = "http://servizio-mcp:8002/mcp"


def _server():
    return crea_server(strumenti_locali())


async def _elenchi(server):
    async with Client(server) as client:
        return await client.list_resources(), await client.list_tools()


def test_resource_pubblicata_e_non_tra_i_tool():
    risorse, strumenti = asyncio.run(_elenchi(_server()))
    assert [(str(r.uri), r.mime_type) for r in risorse] == [(URI_PREFERENZE, "application/json")]
    assert URI_PREFERENZE not in {s.name for s in strumenti}
    assert {s.name for s in strumenti} == {s.name for s in strumenti_locali()}


def test_tool_dell_adattatore_invariati():
    # La resource non diventa uno strumento: bind_tools riceve solo gli strumenti del catalogo.
    remoti = crea_strumenti_mcp(URL, strumenti_locali(), crea_client=lambda: Client(_server()))
    assert [s.name for s in remoti] == [s.name for s in strumenti_locali()]


def test_lettore_mcp_legge_la_resource(tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO")
    file = tmp_path / "preferenze.json"
    file.write_text('{"lingua": "en", "fuso_orario": "America/New_York"}', encoding="utf-8")
    monkeypatch.setenv("PREFERENZE_FILE", str(file))  # letto dal server a ogni resources/read
    server = _server()
    leggi = crea_lettore_mcp(URL, crea_client=lambda: Client(server))
    assert leggi() == Preferenze(lingua="en", fuso_orario="America/New_York")
    assert ("preferenze: resources/read utente://preferenze (mcp) -> lingua=en "
            "fuso_orario=America/New_York stile=sintetico") in caplog.text


def test_lettore_mcp_file_del_server_non_valido_usa_le_predefinite(tmp_path, monkeypatch, caplog):
    file = tmp_path / "preferenze.json"
    file.write_text('{"stile": "poetico"}', encoding="utf-8")
    monkeypatch.setenv("PREFERENZE_FILE", str(file))
    server = _server()
    assert crea_lettore_mcp(URL, crea_client=lambda: Client(server))() == PREDEFINITE
    avvisi = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(avvisi) == 1 and "resources/read" in avvisi[0] and "stile" in avvisi[0]


class ClientFinto:
    def __init__(self, all_apertura=None, contenuti=None):
        self.all_apertura, self.contenuti = all_apertura, contenuti

    async def __aenter__(self):
        if self.all_apertura:
            raise self.all_apertura
        return self

    async def __aexit__(self, *eccezione):
        return False

    async def read_resource(self, uri, **opzioni):
        return self.contenuti


def test_lettore_mcp_server_irraggiungibile_usa_le_predefinite(caplog):
    client = ClientFinto(all_apertura=RuntimeError("Client failed to connect: All connection attempts failed"))
    assert crea_lettore_mcp(URL, crea_client=lambda: client)() == PREDEFINITE
    assert "non raggiungibile" in caplog.text and "uso le predefinite" in caplog.text


def test_lettore_mcp_errore_del_server_e_contenuto_non_testo(caplog):
    errore = MCPError(tipi.INTERNAL_ERROR, "guasto interno")
    assert crea_lettore_mcp(URL, crea_client=lambda: ClientFinto(all_apertura=errore))() \
        == PREDEFINITE
    blob = tipi.BlobResourceContents(uri=URI_PREFERENZE, blob="AAAA", mime_type="application/json")
    assert crea_lettore_mcp(URL, crea_client=lambda: ClientFinto(contenuti=[blob]))() \
        == PREDEFINITE
    assert caplog.text.count("uso le predefinite") == 2
