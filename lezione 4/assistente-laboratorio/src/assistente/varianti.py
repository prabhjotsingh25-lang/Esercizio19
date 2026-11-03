"""Scelta della variante di integrazione degli strumenti, da configurazione."""
from langchain_core.tools import BaseTool

from assistente.catalogo import strumenti_locali
from assistente.config import Configurazione
from assistente.variante_http import crea_strumenti_http


def strumenti_per_variante(config: Configurazione) -> list[BaseTool]:
    """Restituisce gli strumenti della sola variante scelta: stesse definizioni, canale diverso."""
    if config.variante == "http":
        return crea_strumenti_http(config.strumenti_http_url, strumenti_locali())
    return strumenti_locali()
