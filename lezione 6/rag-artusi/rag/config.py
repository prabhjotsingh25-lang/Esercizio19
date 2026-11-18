"""Configurazione letta dall'ambiente (.env): niente valori di servizio nel codice."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

OBBLIGATORIE = ("QDRANT_URL", "COLLEZIONE", "LMSTUDIO_URL", "MODELLO_EMBEDDING")
STRATEGIE = ("paragrafi", "caratteri")
FORMATI_TESTO = ("solo_testo", "titolo_capitolo")
MODALITA = ("base", "riscrittura", "reranking", "entrambe")
K_MASSIMO_CODICE = 20  # tetto imposto dal codice a RICERCA_TOP_K_MAX (= K_MASSIMO della ricerca)


class ErroreConfigurazione(Exception):
    """Configurazione mancante o non valida."""


@dataclass(frozen=True)
class Config:
    qdrant_url: str
    collezione: str
    lmstudio_url: str
    modello_embedding: str
    prefisso_documento: str
    prefisso_query: str
    chunk_strategia: str
    chunk_dimensione: int
    chunk_overlap: int
    embedding_batch: int
    corpus: Path
    testo_indicizzato: str = "titolo_capitolo"
    # Lezione 8: server di ricerca MCP
    ricerca_top_k_max: int = 10
    ricerca_max_caratteri: int = 800
    ricerca_log_file: str | None = None
    # Lezione 8 es. 3: modalità avanzate (riscrittura, reranking) e LLM di LM Studio
    modalita_ricerca: str = "base"
    modello_chat: str = "google/gemma-4-e2b"
    llm_temperatura: float = 0.0
    llm_seed: int | None = 42
    llm_reasoning_effort: str | None = "none"
    llm_max_tokens: int = 300
    llm_timeout: int = 60
    riscrittura_max_query: int = 3
    candidati_per_query: int = 10
    rerank_max_candidati: int = 10
    rerank_max_caratteri: int = 400
    rrf_k: int = 60


def _intero(env: Mapping[str, str], nome: str, default: int) -> int:
    valore = env.get(nome)
    if valore is None or valore.strip() == "":
        return default
    try:
        return int(valore)
    except ValueError:
        raise ErroreConfigurazione(f"{nome} deve essere un numero intero, trovato {valore!r}") from None


def _intero_tra(env: Mapping[str, str], nome: str, default: int, minimo: int, massimo: int | None = None) -> int:
    valore = _intero(env, nome, default)
    if valore < minimo or (massimo is not None and valore > massimo):
        limite = f"tra {minimo} e {massimo}" if massimo is not None else f">= {minimo}"
        raise ErroreConfigurazione(f"{nome} deve essere {limite}, trovato {valore}")
    return valore


def _seed(env: Mapping[str, str]) -> int | None:
    if "LLM_SEED" in env and not env["LLM_SEED"].strip():
        return None
    return _intero(env, "LLM_SEED", 42)


def _temperatura(env: Mapping[str, str]) -> float:
    grezzo = env.get("LLM_TEMPERATURA", "").strip()
    try:
        valore = float(grezzo) if grezzo else 0.0
    except ValueError:
        raise ErroreConfigurazione(f"LLM_TEMPERATURA deve essere un numero, trovato {grezzo!r}") from None
    if not 0 <= valore <= 2:
        raise ErroreConfigurazione(f"LLM_TEMPERATURA deve essere tra 0 e 2, trovato {valore}")
    return valore


def carica_config(env: Mapping[str, str] | None = None) -> Config:
    """Legge la configurazione da `env` o, se None, da .env e dalle variabili d'ambiente."""
    if env is None:
        load_dotenv()
        env = os.environ

    mancanti = [n for n in OBBLIGATORIE if not env.get(n, "").strip()]
    if mancanti:
        raise ErroreConfigurazione(
            "Variabili di configurazione mancanti: " + ", ".join(mancanti) + " (vedi .env.example)"
        )

    strategia = env.get("CHUNK_STRATEGIA", "").strip() or "paragrafi"
    if strategia not in STRATEGIE:
        raise ErroreConfigurazione(
            f"CHUNK_STRATEGIA {strategia!r} sconosciuta: valori ammessi {', '.join(STRATEGIE)}"
        )

    dimensione = _intero(env, "CHUNK_DIMENSIONE", 1200)
    overlap = _intero(env, "CHUNK_OVERLAP", 200)
    if dimensione <= 0:
        raise ErroreConfigurazione("CHUNK_DIMENSIONE deve essere positiva")
    if not 0 <= overlap < dimensione:
        raise ErroreConfigurazione(
            f"CHUNK_OVERLAP ({overlap}) deve essere >= 0 e minore di CHUNK_DIMENSIONE ({dimensione})"
        )
    formato = env.get("TESTO_INDICIZZATO", "").strip() or "titolo_capitolo"
    if formato not in FORMATI_TESTO:
        raise ErroreConfigurazione(
            f"TESTO_INDICIZZATO {formato!r} sconosciuto: valori ammessi {', '.join(FORMATI_TESTO)}"
        )
    top_k_max = _intero(env, "RICERCA_TOP_K_MAX", 10)
    if not 1 <= top_k_max <= K_MASSIMO_CODICE:
        raise ErroreConfigurazione(f"RICERCA_TOP_K_MAX deve essere tra 1 e {K_MASSIMO_CODICE}, trovato {top_k_max}")
    max_caratteri = _intero(env, "RICERCA_MAX_CARATTERI", 800)
    if max_caratteri <= 0:
        raise ErroreConfigurazione("RICERCA_MAX_CARATTERI deve essere positivo")
    modalita = env.get("MODALITA_RICERCA", "").strip().lower() or "base"
    if modalita not in MODALITA:
        raise ErroreConfigurazione(f"MODALITA_RICERCA {modalita!r} sconosciuta: valori ammessi {', '.join(MODALITA)}")
    if "LLM_REASONING_EFFORT" in env:
        reasoning = env["LLM_REASONING_EFFORT"].strip() or None
    else:
        reasoning = "none"
    avanzate = dict(
        modalita_ricerca=modalita,
        modello_chat=env.get("MODELLO_CHAT", "").strip() or "google/gemma-4-e2b",
        llm_temperatura=_temperatura(env),
        llm_seed=_seed(env),
        llm_reasoning_effort=reasoning,
        llm_max_tokens=_intero_tra(env, "LLM_MAX_TOKENS", 300, 1),
        llm_timeout=_intero_tra(env, "LLM_TIMEOUT", 60, 1),
        riscrittura_max_query=_intero_tra(env, "RISCRITTURA_MAX_QUERY", 3, 1, 3),
        candidati_per_query=_intero_tra(env, "CANDIDATI_PER_QUERY", 10, 1, K_MASSIMO_CODICE),
        rerank_max_candidati=_intero_tra(env, "RERANK_MAX_CANDIDATI", 10, 1, K_MASSIMO_CODICE),
        rerank_max_caratteri=_intero_tra(env, "RERANK_MAX_CARATTERI", 400, 1),
        rrf_k=_intero_tra(env, "RRF_K", 60, 0),
    )
    batch = _intero(env, "EMBEDDING_BATCH", 32)
    if batch <= 0:
        raise ErroreConfigurazione("EMBEDDING_BATCH deve essere positivo")

    return Config(
        qdrant_url=env["QDRANT_URL"].strip(),
        collezione=env["COLLEZIONE"].strip(),
        lmstudio_url=env["LMSTUDIO_URL"].strip().rstrip("/"),
        modello_embedding=env["MODELLO_EMBEDDING"].strip(),
        prefisso_documento=env.get("PREFISSO_DOCUMENTO", ""),
        prefisso_query=env.get("PREFISSO_QUERY", ""),
        chunk_strategia=strategia,
        chunk_dimensione=dimensione,
        chunk_overlap=overlap,
        embedding_batch=batch,
        corpus=Path(env.get("CORPUS", "").strip() or "dati/artusi.txt"),
        testo_indicizzato=formato,
        ricerca_top_k_max=top_k_max,
        ricerca_max_caratteri=max_caratteri,
        ricerca_log_file=env.get("RICERCA_LOG_FILE", "").strip() or None,
        **avanzate,
    )
