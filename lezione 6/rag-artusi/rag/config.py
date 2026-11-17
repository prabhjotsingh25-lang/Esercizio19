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


def _intero(env: Mapping[str, str], nome: str, default: int) -> int:
    valore = env.get(nome)
    if valore is None or valore.strip() == "":
        return default
    try:
        return int(valore)
    except ValueError:
        raise ErroreConfigurazione(f"{nome} deve essere un numero intero, trovato {valore!r}") from None


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
    )
