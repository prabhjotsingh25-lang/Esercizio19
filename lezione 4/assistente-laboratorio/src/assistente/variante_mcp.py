"""Adattatore MCP (variante 03): stesse definizioni del catalogo, esecuzione tramite client FastMCP.

Il client FastMCP è asincrono, il resto del programma è sincrono: ogni chiamata apre una
connessione, esegue lo strumento e la chiude (`asyncio.run`). Semplice e senza stato condiviso.
"""
import asyncio
from collections.abc import Callable
from typing import Any

import mcp.types as tipi
from fastmcp import Client
from fastmcp.exceptions import MCPError
from langchain_core.tools import BaseTool, StructuredTool

TIMEOUT_SECONDI = 10


def _chiama(crea_client: Callable[[], Any], url: str, nome: str, argomenti: dict) -> str:
    """Esegue lo strumento sul server MCP; ogni guasto noto diventa un errore leggibile."""

    async def esegui():
        async with crea_client() as client:
            return await client.call_tool(nome, argomenti, timeout=TIMEOUT_SECONDI,
                                          raise_on_error=False)

    try:
        risultato = asyncio.run(esegui())
    except MCPError as errore:
        if errore.error.code == tipi.REQUEST_TIMEOUT:
            return f"Errore: il server MCP non ha risposto entro {TIMEOUT_SECONDI} secondi."
        return f"Errore: il server MCP ha restituito un errore: {errore.error.message}."
    except RuntimeError as errore:
        if "failed to connect" not in str(errore):
            raise  # non è un problema di rete: non va mascherato
        return f"Errore: server MCP non raggiungibile su {url}."
    testi = [b.text for b in risultato.content if isinstance(b, tipi.TextContent)]
    if not testi or len(testi) != len(risultato.content):
        return "Errore: risposta del server MCP non valida."
    testo = "".join(testi)
    if risultato.is_error:
        return f"Errore: il server MCP ha rifiutato la chiamata: {testo}."
    return testo


def crea_strumenti_mcp(url: str, definizioni: list[BaseTool],
                       crea_client: Callable[[], Any] | None = None) -> list[BaseTool]:
    """Uno strumento per ogni definizione: stesso nome, descrizione e schema del catalogo.

    `crea_client` è iniettabile per i test (client in memoria o finto).
    """
    crea_client = crea_client or (lambda: Client(url, timeout=TIMEOUT_SECONDI))

    def remoto(definizione: BaseTool) -> BaseTool:
        def esegui(**argomenti) -> str:
            return _chiama(crea_client, url, definizione.name, argomenti)

        return StructuredTool.from_function(func=esegui, name=definizione.name,
                                            description=definizione.description,
                                            args_schema=definizione.args_schema)

    return [remoto(d) for d in definizioni]
