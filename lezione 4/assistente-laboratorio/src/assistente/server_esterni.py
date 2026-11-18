"""Server MCP esterni (lezione 8): dichiarati in un file nel formato standard `mcpServers`
(stdio con `command`/`args`/`cwd`, oppure `url`), scoperti con tools/list e offerti al modello
accanto agli strumenti della variante scelta.

Diversamente dagli strumenti del catalogo, nome, descrizione e schema arrivano dal server
(discovery). Come nell'adattatore della variante mcp, ogni chiamata apre una connessione e la
chiude (`asyncio.run`): con stdio vuol dire un processo per chiamata (`keep_alive=False`).
"""
import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mcp.types as tipi
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import MCPError
from langchain_core.tools import BaseTool, StructuredTool

log = logging.getLogger("assistente.server_esterni")

TIMEOUT_PREDEFINITO = 120  # secondi: avvio stdio + embedding + eventuali chiamate all'LLM del server
LOG_STDIO = Path("logs") / "ricerca-stdio.log"  # stderr dei server stdio (le loro righe di log)


class ErroreServerMCP(Exception):
    """File dei server non valido, server non avviabile o nome di strumento in conflitto."""


@dataclass(frozen=True)
class ServerMCP:
    nome: str
    command: str | None
    args: tuple[str, ...]
    cwd: str | None
    url: str | None
    timeout: int = TIMEOUT_PREDEFINITO


def _risolvi(base: Path, valore: str) -> str:
    return str((base / valore).resolve())


def leggi_server(percorso: str) -> list[ServerMCP]:
    """Legge il file `mcpServers`; i percorsi relativi sono relativi alla cartella del file."""
    file = Path(percorso)
    if not file.is_file():
        raise ErroreServerMCP(f"file dei server MCP non trovato: {percorso}")
    try:
        dati = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, OSError) as errore:
        raise ErroreServerMCP(f"file dei server MCP {percorso}: JSON non valido ({errore})") from None
    voci = dati.get("mcpServers") if isinstance(dati, dict) else None
    if not isinstance(voci, dict) or not voci:
        raise ErroreServerMCP(f"file dei server MCP {percorso}: manca l'oggetto mcpServers con almeno un server")
    base = file.resolve().parent
    server = []
    for nome, voce in voci.items():
        if not isinstance(voce, dict) or not (voce.get("command") or voce.get("url")):
            raise ErroreServerMCP(f'server MCP "{nome}": serve "command" (stdio) oppure "url"')
        timeout = voce.get("timeout", TIMEOUT_PREDEFINITO)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
            raise ErroreServerMCP(f'server MCP "{nome}": "timeout" deve essere un intero >= 1 (secondi)')
        argomenti = voce.get("args", [])
        if not isinstance(argomenti, list):
            raise ErroreServerMCP(f'server MCP "{nome}": "args" deve essere una lista di stringhe')
        comando = voce.get("command")
        if comando and ("/" in comando or "\\" in comando):
            comando = _risolvi(base, comando)
        cwd = voce.get("cwd")
        server.append(ServerMCP(nome=nome, command=comando, args=tuple(str(a) for a in argomenti),
                                cwd=_risolvi(base, cwd) if cwd else None, url=voce.get("url"), timeout=timeout))
    return server


def crea_client_per(server: ServerMCP) -> Callable[[], Any]:
    """Fabbrica di client reali: stdio (un processo per connessione) oppure HTTP."""
    if server.url:
        return lambda: Client(server.url, timeout=server.timeout)

    def stdio():
        LOG_STDIO.parent.mkdir(parents=True, exist_ok=True)
        trasporto = StdioTransport(server.command, list(server.args), cwd=server.cwd, keep_alive=False,
                                   log_file=LOG_STDIO)
        return Client(trasporto, timeout=server.timeout)
    return stdio


def _testo(risultato) -> str | None:
    testi = [b.text for b in risultato.content if isinstance(b, tipi.TextContent)]
    if not testi or len(testi) != len(risultato.content):
        return None
    return "".join(testi)


def _chiama(server: ServerMCP, crea_client: Callable[[], Any], nome: str, argomenti: dict) -> str:
    async def esegui():
        async with crea_client() as client:
            return await client.call_tool(nome, argomenti, timeout=server.timeout, raise_on_error=False)

    try:
        risultato = asyncio.run(esegui())
    except MCPError as errore:
        if errore.error.code == tipi.REQUEST_TIMEOUT:
            return f'Errore: il server MCP "{server.nome}" non ha risposto entro {server.timeout} secondi.'
        return f'Errore: il server MCP "{server.nome}" ha restituito un errore: {errore.error.message}.'
    except Exception as errore:  # processo che non parte o cade, connessione rifiutata
        log.warning('server MCP "%s": chiamata a %s fallita (%s: %s)', server.nome, nome,
                    type(errore).__name__, " ".join(str(errore).split())[:200])
        return f'Errore: server MCP "{server.nome}" non raggiungibile ({type(errore).__name__}).'
    testo = _testo(risultato)
    if testo is None:
        return f'Errore: risposta del server MCP "{server.nome}" non valida.'
    return f"Errore: {testo}" if risultato.is_error else testo


def strumenti_server(server: ServerMCP, crea_client: Callable[[], Any] | None = None) -> list[BaseTool]:
    """tools/list sul server e uno StructuredTool sincrono per ogni strumento scoperto."""
    crea_client = crea_client or crea_client_per(server)

    async def elenca():
        async with crea_client() as client:
            return await client.list_tools()

    try:
        scoperti = asyncio.run(elenca())
    except Exception as errore:
        raise ErroreServerMCP(
            f'server MCP "{server.nome}" non avviabile o non raggiungibile ({type(errore).__name__}: '
            f'{" ".join(str(errore).split())[:200]})') from None

    def strumento(t) -> BaseTool:
        def esegui(**argomenti) -> str:
            return _chiama(server, crea_client, t.name, argomenti)
        return StructuredTool.from_function(func=esegui, name=t.name, description=t.description or "",
                                            args_schema=t.input_schema)

    return [strumento(t) for t in scoperti]


def strumenti_esterni(percorso: str, gia_presenti: list[str],
                      crea_client_per: Callable[[ServerMCP], Callable[[], Any]] = crea_client_per) -> list[BaseTool]:
    """Strumenti di tutti i server del file; un nome già usato blocca l'avvio con un errore chiaro."""
    nomi = list(gia_presenti)
    strumenti: list[BaseTool] = []
    for server in leggi_server(percorso):
        for s in strumenti_server(server, crea_client_per(server)):
            if s.name in nomi:
                raise ErroreServerMCP(f'strumento "{s.name}" del server MCP "{server.nome}": nome già usato')
            nomi.append(s.name)
            strumenti.append(s)
        log.info('server MCP "%s": strumenti %s', server.nome,
                 ", ".join(s.name for s in strumenti if s.name not in gia_presenti))
    return strumenti
