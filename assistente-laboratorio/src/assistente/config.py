"""Configurazione dell'assistente, letta solo da variabili d'ambiente."""
import os
from collections.abc import Mapping
from dataclasses import dataclass


class ErroreConfigurazione(ValueError):
    """Configurazione mancante o non valida."""


@dataclass(frozen=True)
class Configurazione:
    base_url: str
    modello: str
    max_passaggi: int = 3
    log_level: str = "INFO"


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ErroreConfigurazione(f"Variabile d'ambiente obbligatoria mancante o vuota: {nome}")
    return valore


def _max_passaggi(env: Mapping[str, str]) -> int:
    grezzo = env.get("MAX_PASSAGGI_STRUMENTO", "").strip()
    if not grezzo:
        return 3
    try:
        valore = int(grezzo)
    except ValueError:
        valore = 0
    if valore < 1:
        raise ErroreConfigurazione(
            f"MAX_PASSAGGI_STRUMENTO deve essere un intero >= 1 (ricevuto: {grezzo!r})"
        )
    return valore


LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _log_level(env: Mapping[str, str]) -> str:
    grezzo = env.get("LOG_LEVEL", "").strip()
    if not grezzo:
        return "INFO"
    livello = grezzo.upper()
    if livello not in LIVELLI_LOG:
        raise ErroreConfigurazione(
            f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)} (ricevuto: {grezzo!r})"
        )
    return livello


def carica_configurazione(env: Mapping[str, str] | None = None) -> Configurazione:
    """Costruisce la configurazione; con env=None legge os.environ."""
    if env is None:
        env = os.environ
    return Configurazione(
        base_url=_obbligatoria(env, "LMSTUDIO_BASE_URL"),
        modello=_obbligatoria(env, "LMSTUDIO_MODEL"),
        max_passaggi=_max_passaggi(env),
        log_level=_log_level(env),
    )
