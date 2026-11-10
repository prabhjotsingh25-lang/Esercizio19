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
    variante: str = "locale"
    strumenti_http_url: str | None = None
    strumenti_mcp_url: str | None = None
    ambito: str = ""  # cosa fa l'assistente: il router lo usa per le domande fuori ambito
    max_revisioni: int = 1  # nuovi tentativi chiesti dal revisore per ogni domanda
    soglia_riassunto: int = 20  # oltre questi messaggi, quelli vecchi diventano un riassunto
    messaggi_recenti: int = 6  # messaggi recenti che restano intatti (almeno)


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ErroreConfigurazione(f"Variabile d'ambiente obbligatoria mancante o vuota: {nome}")
    return valore


def _intero_positivo(env: Mapping[str, str], nome: str, default: int) -> int:
    grezzo = env.get(nome, "").strip()
    if not grezzo:
        return default
    try:
        valore = int(grezzo)
    except ValueError:
        valore = 0
    if valore < 1:
        raise ErroreConfigurazione(f"{nome} deve essere un intero >= 1 (ricevuto: {grezzo!r})")
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


VARIANTI = ("locale", "http", "mcp")


def _variante(env: Mapping[str, str]) -> str:
    grezzo = env.get("VARIANTE_STRUMENTI", "").strip()
    if not grezzo:
        return "locale"
    variante = grezzo.lower()
    if variante not in VARIANTI:
        raise ErroreConfigurazione(
            f"VARIANTE_STRUMENTI deve essere uno tra {', '.join(VARIANTI)} (ricevuto: {grezzo!r})"
        )
    return variante


def carica_configurazione(env: Mapping[str, str] | None = None) -> Configurazione:
    """Costruisce la configurazione; con env=None legge os.environ."""
    if env is None:
        env = os.environ
    variante = _variante(env)
    soglia = _intero_positivo(env, "SOGLIA_RIASSUNTO", 20)
    recenti = _intero_positivo(env, "MESSAGGI_RECENTI", 6)
    if recenti >= soglia:
        raise ErroreConfigurazione(
            f"MESSAGGI_RECENTI ({recenti}) deve essere minore di SOGLIA_RIASSUNTO ({soglia})")
    return Configurazione(
        base_url=_obbligatoria(env, "LMSTUDIO_BASE_URL"),
        modello=_obbligatoria(env, "LMSTUDIO_MODEL"),
        max_passaggi=_intero_positivo(env, "MAX_PASSAGGI_STRUMENTO", 3),
        log_level=_log_level(env),
        variante=variante,
        strumenti_http_url=_obbligatoria(env, "STRUMENTI_HTTP_URL") if variante == "http" else None,
        strumenti_mcp_url=_obbligatoria(env, "STRUMENTI_MCP_URL") if variante == "mcp" else None,
        ambito=_obbligatoria(env, "AMBITO_AGENTE"),
        max_revisioni=_intero_positivo(env, "MAX_REVISIONI", 1),
        soglia_riassunto=soglia,
        messaggi_recenti=recenti,
    )
