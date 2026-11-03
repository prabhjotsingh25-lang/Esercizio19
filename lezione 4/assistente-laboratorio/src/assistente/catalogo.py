"""Catalogo degli strumenti: unica fonte di nomi, descrizioni, schemi e logica.

Ogni variante di integrazione parte da qui, così il modello vede le stesse definizioni
qualunque sia il canale con cui gli strumenti vengono raggiunti.
"""
from collections.abc import Callable
from datetime import datetime

from langchain_core.tools import BaseTool

from assistente.calcolatrice import crea_strumento_calcolatrice
from assistente.convertitore import crea_strumento_convertitore
from assistente.strumenti import crea_strumento_orologio


def strumenti_locali(adesso: Callable[[], datetime] | None = None) -> list[BaseTool]:
    """Strumenti eseguiti in-process (variante 01); `adesso` è iniettabile per i test."""
    return [crea_strumento_orologio(adesso), crea_strumento_convertitore(),
            crea_strumento_calcolatrice()]
