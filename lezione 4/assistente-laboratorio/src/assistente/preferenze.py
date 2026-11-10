"""Preferenze dell'utente: tre campi validati, letti una volta a inizio sessione dall'host.

Una sola logica (schema, validazione, testo per il prompt); i canali cambiano: nella variante
mcp le preferenze arrivano dalla resource `utente://preferenze` del server, nelle altre dal file.
"""
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

log = logging.getLogger("assistente.preferenze")

URI_PREFERENZE = "utente://preferenze"
PERCORSO_PREDEFINITO = Path("preferenze.json")
LINGUE = {"it": "italiano", "en": "inglese", "fr": "francese", "de": "tedesco", "es": "spagnolo"}
STILI = {"sintetico": "risposta finale breve ed essenziale (usa comunque gli strumenti)",
         "dettagliato": "rispondi in due o tre frasi: dai il risultato e spiega come lo hai "
                        "ottenuto (quale strumento o quale calcolo hai usato)"}


class ErrorePreferenze(ValueError):
    """Preferenze assenti o non valide: il messaggio spiega il motivo."""


class Preferenze(BaseModel):
    """Lingua delle risposte, fuso orario predefinito (IANA) e stile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lingua: Literal["it", "en", "fr", "de", "es"] = "it"
    fuso_orario: str = "Europe/Rome"
    stile: Literal["sintetico", "dettagliato"] = "sintetico"

    @field_validator("fuso_orario")
    @classmethod
    def _fuso_iana(cls, valore: str) -> str:
        try:
            ZoneInfo(valore)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"fuso orario IANA sconosciuto: {valore!r}") from None
        return valore


PREDEFINITE = Preferenze()

# Lettore usato dall'host a inizio sessione (e da /nuova): restituisce sempre delle preferenze.
LettorePreferenze = Callable[[], Preferenze]


def da_json(testo: str) -> Preferenze:
    """Valida il JSON delle preferenze; ErrorePreferenze con un motivo leggibile."""
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError as errore:
        raise ErrorePreferenze(f"JSON non valido ({errore.msg})") from None
    if not isinstance(dati, dict):
        raise ErrorePreferenze("serve un oggetto JSON con i campi lingua, fuso_orario, stile")
    try:
        return Preferenze.model_validate(dati)
    except ValidationError as errore:
        campi = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                          for e in errore.errors())
        raise ErrorePreferenze(f"campi non validi: {campi}") from None


def percorso_preferenze() -> Path:
    """Percorso del file: PREFERENZE_FILE, altrimenti preferenze.json nella cartella corrente."""
    return Path(os.environ.get("PREFERENZE_FILE", "").strip() or PERCORSO_PREDEFINITO)


def leggi_file(percorso: Path) -> Preferenze:
    """Legge e valida il file; ErrorePreferenze se manca, è vuoto o non è valido."""
    try:
        testo = Path(percorso).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ErrorePreferenze(f"file {percorso} assente") from None
    if not testo.strip():
        raise ErrorePreferenze(f"file {percorso} vuoto")
    return da_json(testo)


def descrivi(p: Preferenze) -> str:
    """Forma breve per i log."""
    return f"lingua={p.lingua} fuso_orario={p.fuso_orario} stile={p.stile}"


def con_predefinite(origine: str, leggi: Callable[[], Preferenze]) -> Preferenze:
    """Esegue la lettura; se fallisce usa le predefinite con un WARNING. Log della lettura."""
    try:
        preferenze = leggi()
    except ErrorePreferenze as errore:
        log.warning("preferenze: %s non disponibili (%s): uso le predefinite (%s)",
                    origine, errore, descrivi(PREDEFINITE))
        return PREDEFINITE
    log.info("preferenze: %s -> %s", origine, descrivi(preferenze))
    return preferenze


def crea_lettore_file(percorso: Path | str | None = None) -> LettorePreferenze:
    """Lettore diretto del file (varianti locale e http); rilegge a ogni chiamata."""
    file = Path(percorso) if percorso is not None else percorso_preferenze()
    return lambda: con_predefinite(f"lettura del file {file}", lambda: leggi_file(file))


def prompt_preferenze(p: Preferenze) -> str:
    """Blocco in cima al messaggio di sistema dell'agente (e contesto attendibile del revisore)."""
    lingua = LINGUE[p.lingua]
    return (
        "Preferenze dell'utente (dati attendibili, valgono più delle istruzioni generali):\n"
        f"- Rispondi sempre in {lingua}, anche se l'utente scrive in un'altra lingua.\n"
        f"- Fuso orario predefinito: {p.fuso_orario}. Quando l'utente non indica un luogo o un "
        f"fuso orario, usa {p.fuso_orario} senza chiederlo.\n"
        f"- Stile {p.stile}: {STILI[p.stile]}."
    )
