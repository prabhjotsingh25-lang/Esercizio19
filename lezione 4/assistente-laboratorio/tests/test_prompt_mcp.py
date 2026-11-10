"""Prompt MCP: pubblicati dal server, elencati e ottenuti dall'host con il client (variante mcp)."""
import asyncio

import mcp.types as tipi
import pytest
from fastmcp import Client
from fastmcp.exceptions import MCPError
from langchain_core.messages import HumanMessage

from assistente.catalogo import strumenti_locali
from assistente.prompt import NOME_PROMPT, ErrorePrompt, FontePromptLocale
from assistente.server_mcp import crea_server
from assistente.variante_mcp import FontePromptMCP

URL = "http://servizio-mcp:8002/mcp"


def _fonte():
    server = crea_server(strumenti_locali())
    return FontePromptMCP(URL, crea_client=lambda: Client(server))


def test_prompt_pubblicati_e_non_tra_i_tool():
    async def elenchi():
        async with Client(crea_server(strumenti_locali())) as client:
            return await client.list_prompts(), await client.list_tools()
    prompt, strumenti = asyncio.run(elenchi())
    assert [p.name for p in prompt] == ["spiega", "riassumi_conversazione"]
    assert not {p.name for p in prompt} & {s.name for s in strumenti}


def test_elenco_mcp_uguale_al_catalogo(caplog):
    caplog.set_level("INFO")
    remoto, locale = _fonte().elenca(), FontePromptLocale().elenca()
    assert [(i.nome, i.descrizione, [(a.nome, a.descrizione, a.obbligatorio) for a in i.argomenti])
            for i in remoto] == [
        (i.nome, i.descrizione, [(a.nome, a.descrizione, a.obbligatorio) for a in i.argomenti])
        for i in locale]
    assert "prompt: prompts/list (mcp) -> 2 prompt: spiega, riassumi_conversazione" in caplog.text


def test_ottieni_mcp_stesso_testo_del_catalogo(caplog):
    caplog.set_level("INFO")
    argomenti = {"argomento": "Model Context Protocol", "livello": "base"}
    remoti = _fonte().ottieni("spiega", argomenti)
    locali = FontePromptLocale().ottieni("spiega", argomenti)
    assert [(type(m), m.name, m.content) for m in remoti] == [
        (type(m), m.name, m.content) for m in locali]
    assert isinstance(remoti[0], HumanMessage) and remoti[0].name == NOME_PROMPT
    assert ("prompt: prompts/get spiega (mcp) argomenti={'argomento': 'Model Context Protocol', "
            "'livello': 'base'} -> messaggi dal server: [user] Spiegami Model Context Protocol"
            ) in caplog.text


def test_predefinito_del_facoltativo_applicato_dal_server():
    testo = _fonte().ottieni("spiega", {"argomento": "MCP"})[0].content
    assert "livello base" in testo


class ClientFinto:
    def __init__(self, all_apertura=None):
        self.all_apertura = all_apertura

    async def __aenter__(self):
        raise self.all_apertura

    async def __aexit__(self, *eccezione):
        return False


@pytest.mark.parametrize("errore, motivo", [
    (RuntimeError("Client failed to connect: All connection attempts failed"), "non raggiungibile"),
    (MCPError(tipi.INTERNAL_ERROR, "Unknown prompt: 'x'"), "Unknown prompt"),
])
def test_errori_mcp_diventano_errori_del_prompt(errore, motivo):
    fonte = FontePromptMCP(URL, crea_client=lambda: ClientFinto(errore))
    with pytest.raises(ErrorePrompt, match=motivo):
        fonte.elenca()
    with pytest.raises(ErrorePrompt, match=motivo):
        fonte.ottieni("spiega", {"argomento": "x"})
