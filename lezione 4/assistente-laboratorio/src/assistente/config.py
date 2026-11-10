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
    preferenze_file: str = "preferenze.json"  # letto dall'host nelle varianti locale e http
    agente_host: str = "127.0.0.1"  # servizio HTTP dell'agente (step 9: 0.0.0.0 in Compose)
    agente_porta: int = 8000
    agente_url: str | None = None  # se presente, la CLI è un client dell'API dell'agente
    agente_timeout: int = 900  # secondi di attesa di una risposta dell'agente (back-end, CLI)
    database_url: str | None = None  # PostgreSQL del back-end (con la password: solo in .env)
    backend_host: str = "127.0.0.1"
    backend_porta: int = 8080
    backend_url: str = "http://127.0.0.1:8080"  # usato dal front-end (nel browser)
    frontend_host: str = "127.0.0.1"
    frontend_porta: int = 8090
    frontend_origine: str = "http://127.0.0.1:8090"  # unica origine ammessa dal CORS del back-end


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


def _porta(env: Mapping[str, str], nome: str, default: int) -> int:
    valore = _intero_positivo(env, nome, default)
    if valore > 65535:
        raise ErroreConfigurazione(f"{nome} deve essere una porta fra 1 e 65535 (ricevuto: {valore})")
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
        preferenze_file=env.get("PREFERENZE_FILE", "").strip() or "preferenze.json",
        agente_host=env.get("AGENTE_HOST", "").strip() or "127.0.0.1",
        agente_porta=_porta(env, "AGENTE_PORTA", 8000),
        agente_url=env.get("AGENTE_URL", "").strip().rstrip("/") or None,
        agente_timeout=_intero_positivo(env, "AGENTE_TIMEOUT", 900),
        database_url=env.get("DATABASE_URL", "").strip() or None,
        backend_host=env.get("BACKEND_HOST", "").strip() or "127.0.0.1",
        backend_porta=_porta(env, "BACKEND_PORTA", 8080),
        backend_url=env.get("BACKEND_URL", "").strip().rstrip("/") or "http://127.0.0.1:8080",
        frontend_host=env.get("FRONTEND_HOST", "").strip() or "127.0.0.1",
        frontend_porta=_porta(env, "FRONTEND_PORTA", 8090),
        frontend_origine=env.get("FRONTEND_ORIGINE", "").strip().rstrip("/")
        or "http://127.0.0.1:8090",
    )
