"""Scelta della variante di integrazione (strumenti e preferenze), da configurazione."""
from langchain_core.tools import BaseTool

from assistente.catalogo import strumenti_locali
from assistente.config import Configurazione
from assistente.variante_http import crea_strumenti_http
from assistente.preferenze import LettorePreferenze, crea_lettore_file
from assistente.variante_mcp import crea_lettore_mcp, crea_strumenti_mcp


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
