"""Scelta della variante di integrazione (strumenti, preferenze, prompt) e controlli di
raggiungibilità di strumenti e modello, da configurazione."""
import asyncio
from collections.abc import Callable

import httpx
from fastmcp import Client
from langchain_core.tools import BaseTool

from assistente.catalogo import strumenti_locali
from assistente.config import Configurazione
from assistente.variante_http import crea_strumenti_http
from assistente.preferenze import LettorePreferenze, crea_lettore_file
from assistente.prompt import FontePrompt, FontePromptLocale
from assistente.variante_mcp import FontePromptMCP, crea_lettore_mcp, crea_strumenti_mcp


def strumenti_per_variante(config: Configurazione) -> list[BaseTool]:
    """Restituisce gli strumenti della sola variante scelta: stesse definizioni, canale diverso."""
    if config.variante == "http":
        return crea_strumenti_http(config.strumenti_http_url, strumenti_locali())
    if config.variante == "mcp":
        return crea_strumenti_mcp(config.strumenti_mcp_url, strumenti_locali())
    return strumenti_locali()


def lettore_preferenze(config: Configurazione) -> LettorePreferenze:
    """mcp: resource utente://preferenze del server; locale e http: lettura diretta del file."""
    if config.variante == "mcp":
        return crea_lettore_mcp(config.strumenti_mcp_url)
    return crea_lettore_file(config.preferenze_file)


def fonte_prompt(config: Configurazione) -> FontePrompt:
    """mcp: prompts/list e prompts/get sul server; locale e http: catalogo locale dei prompt."""
    if config.variante == "mcp":
        return FontePromptMCP(config.strumenti_mcp_url)
    return FontePromptLocale()


# Controllo di raggiungibilità: None se il componente risponde, altrimenti il motivo.
Verifica = Callable[[], str | None]
TIMEOUT_VERIFICA = 5


def descrivi_strumenti(config: Configurazione) -> str:
    return {"locale": "in-process", "http": f"servizio strumenti su {config.strumenti_http_url}",
            "mcp": f"server MCP su {config.strumenti_mcp_url}"}[config.variante]


def verifica_strumenti(config: Configurazione,
                       trasporto: httpx.BaseTransport | None = None) -> Verifica:
    """locale: sempre disponibili; http: GET /strumenti; mcp: tools/list sul server."""
    if config.variante == "http":
        def http() -> str | None:
            try:
                with httpx.Client(transport=trasporto, timeout=TIMEOUT_VERIFICA) as client:
                    client.get(f"{config.strumenti_http_url}/strumenti").raise_for_status()
            except httpx.HTTPError as errore:
                return f"servizio strumenti non raggiungibile su {config.strumenti_http_url} ({errore})"
            return None
        return http
    if config.variante == "mcp":
        def mcp() -> str | None:
            async def elenca():
                async with Client(config.strumenti_mcp_url, timeout=TIMEOUT_VERIFICA) as client:
                    return await client.list_tools()
            try:
                asyncio.run(elenca())
            except Exception as errore:  # connessione rifiutata, timeout, errore MCP
                return f"server MCP non raggiungibile su {config.strumenti_mcp_url} ({errore})"
            return None
        return mcp
    return lambda: None


def verifica_modello(config: Configurazione,
                     trasporto: httpx.BaseTransport | None = None) -> Verifica:
    """GET /models di LM Studio: il server risponde e il modello configurato è fra quelli elencati."""
    def verifica() -> str | None:
        try:
            with httpx.Client(transport=trasporto, timeout=TIMEOUT_VERIFICA) as client:
                risposta = client.get(f"{config.base_url.rstrip('/')}/models")
                risposta.raise_for_status()
                modelli = [m.get("id") for m in risposta.json().get("data", [])]
        except (httpx.HTTPError, ValueError) as errore:
            return f"modello non raggiungibile su {config.base_url} ({errore})"
        if config.modello not in modelli:
            return f"il modello {config.modello} non è fra quelli del server ({', '.join(modelli)})"
        return None
    return verifica
