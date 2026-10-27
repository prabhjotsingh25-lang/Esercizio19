"""Strumento orologio: ora corrente in un fuso orario IANA esplicito."""
from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, StructuredTool


def _adesso_utc() -> datetime:
    return datetime.now(timezone.utc)


def descrivi_ora(fuso_orario: str, adesso: Callable[[], datetime]) -> str:
    """Restituisce l'ora nel fuso indicato, oppure un messaggio di errore leggibile dal modello."""
    try:
        fuso = ZoneInfo(fuso_orario)
    except (ZoneInfoNotFoundError, ValueError):
        return (f"Errore: fuso orario non valido: '{fuso_orario}'. "
                "Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo.")
    ora = adesso().astimezone(fuso)
    return f"{ora.isoformat(timespec='seconds')} ({fuso_orario})"


def crea_strumento_orologio(adesso: Callable[[], datetime] | None = None) -> BaseTool:
    """Costruisce lo strumento `ora_corrente`; `adesso` è iniettabile per i test."""
    sorgente = adesso or _adesso_utc

    def ora_corrente(fuso_orario: str) -> str:
        return descrivi_ora(fuso_orario, sorgente)

    return StructuredTool.from_function(
        func=ora_corrente,
        name="ora_corrente",
        description=("Restituisce data e ora correnti in un fuso orario. "
                     "Passa in fuso_orario un nome IANA, per esempio Europe/Rome o Asia/Tokyo."),
    )
