"""Catalogo degli strumenti: unica fonte di nomi, descrizioni, schemi e logica.

Ogni variante di integrazione parte da qui, così il modello vede le stesse definizioni
qualunque sia il canale con cui gli strumenti vengono raggiunti.
"""
from collections.abc import Callable
from datetime import datetime

import httpx
from langchain_core.tools import BaseTool

from assistente.calcolatrice import crea_strumento_calcolatrice
from assistente.convertitore import crea_strumento_convertitore
from assistente.inventario import crea_strumento_catalogo
from assistente.meteo import crea_strumento_meteo
from assistente.note import crea_strumento_note
from assistente.scadenze import crea_strumento_scadenze
from assistente.strumenti import crea_strumento_orologio


def strumenti_locali(adesso: Callable[[], datetime] | None = None,
                     trasporto_meteo: httpx.BaseTransport | None = None) -> list[BaseTool]:
    """Strumenti eseguiti in-process (variante 01).

    `adesso` e `trasporto_meteo` (un Open-Meteo finto) sono iniettabili per i test.
    """
    return [crea_strumento_orologio(adesso), crea_strumento_convertitore(),
            crea_strumento_calcolatrice(), crea_strumento_scadenze(), crea_strumento_catalogo(),
            crea_strumento_note(adesso=adesso), crea_strumento_meteo(trasporto_meteo)]
