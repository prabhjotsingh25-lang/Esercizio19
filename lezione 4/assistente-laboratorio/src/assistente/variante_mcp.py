"""Adattatore MCP (variante 03): stesse definizioni del catalogo, esecuzione tramite client FastMCP;
lettura della resource `utente://preferenze` e dei prompt (prompts/list, prompts/get) per l'host.

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

from assistente.prompt import (
    ArgomentoPrompt, ErrorePrompt, InfoPrompt, PromptNonDisponibili, log, log_messaggi, messaggio)
from assistente.preferenze import (
    URI_PREFERENZE, ErrorePreferenze, LettorePreferenze, Preferenze, con_predefinite, da_json)

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


def _leggi_preferenze(crea_client: Callable[[], Any], url: str) -> Preferenze:
    """Una resources/read di utente://preferenze; ogni guasto diventa ErrorePreferenze."""

    async def leggi():
        async with crea_client() as client:
            return await client.read_resource(URI_PREFERENZE)

    try:
        contenuti = asyncio.run(leggi())
    except MCPError as errore:
        raise ErrorePreferenze(f"errore del server MCP: {errore.error.message}") from None
    except RuntimeError as errore:
        if "failed to connect" not in str(errore):
            raise  # non è un problema di rete: non va mascherato
        raise ErrorePreferenze(f"server MCP non raggiungibile su {url}") from None
    testi = [c.text for c in contenuti or [] if isinstance(c, tipi.TextResourceContents)]
    if len(testi) != 1 or len(contenuti) != 1:
        raise ErrorePreferenze("contenuto della resource non valido")
    return da_json(testi[0])


def crea_lettore_mcp(url: str, crea_client: Callable[[], Any] | None = None) -> LettorePreferenze:
    """Lettore delle preferenze tramite la resource MCP; predefinite con WARNING se fallisce."""
    crea_client = crea_client or (lambda: Client(url, timeout=TIMEOUT_SECONDI))
    return lambda: con_predefinite(f"resources/read {URI_PREFERENZE} (mcp)",
                                   lambda: _leggi_preferenze(crea_client, url))


class FontePromptMCP:
    """Prompt dal server MCP: prompts/list per l'elenco, prompts/get per il testo."""

    def __init__(self, url: str, crea_client: Callable[[], Any] | None = None):
        self._url = url
        self._crea_client = crea_client or (lambda: Client(url, timeout=TIMEOUT_SECONDI))

    def _esegui(self, operazione):
        async def esegui():
            async with self._crea_client() as client:
                return await operazione(client)
        try:
            return asyncio.run(esegui())
        except MCPError as errore:
            raise PromptNonDisponibili(f"errore del server MCP: {errore.error.message}") from None
        except RuntimeError as errore:
            if "failed to connect" not in str(errore):
                raise  # non è un problema di rete: non va mascherato
            raise PromptNonDisponibili(f"server MCP non raggiungibile su {self._url}") from None

    def elenca(self) -> list[InfoPrompt]:
        voci = self._esegui(lambda client: client.list_prompts())
        elenco = [InfoPrompt(p.name, p.description or "",
                             tuple(ArgomentoPrompt(a.name, a.description or "", bool(a.required))
                                   for a in p.arguments or []))
                  for p in voci]
        log.info("prompt: prompts/list (mcp) -> %d prompt: %s", len(elenco),
                 ", ".join(i.nome for i in elenco))
        return elenco

    def ottieni(self, nome: str, argomenti: dict[str, str]) -> list:
        risultato = self._esegui(lambda client: client.get_prompt(nome, argomenti))
        messaggi = []
        for m in risultato.messages:
            if not isinstance(m.content, tipi.TextContent):
                raise PromptNonDisponibili("il server ha restituito un messaggio non testuale")
            messaggi.append(messaggio(m.role, m.content.text))
        if not messaggi:
            raise PromptNonDisponibili("il server non ha restituito messaggi")
        log_messaggi("mcp", nome, argomenti, messaggi)
        return messaggi
