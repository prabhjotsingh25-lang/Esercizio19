"""Strumento note persistenti: aggiunta, elenco ed eliminazione con conferma, su SQLite.

L'eliminazione richiede due chiamate: la prima mostra la nota e registra la richiesta,
la seconda (con conferma=true) cancella. La richiesta è salvata nel database, così il
meccanismo funziona anche quando ogni chiamata arriva da un processo diverso (http, mcp).
Il percorso del database si legge a ogni chiamata da NOTE_DB (default: note.sqlite).
"""
import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Literal

from langchain_core.tools import BaseTool, StructuredTool

PERCORSO_PREDEFINITO = Path("note.sqlite")
MAX_TESTO = 500
MAX_ELENCO = 50
AZIONI = ("aggiungi", "elenca", "elimina")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- AUTOINCREMENT: gli id cancellati non tornano
    testo TEXT NOT NULL,
    creata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conferme_richieste (
    id_nota INTEGER PRIMARY KEY
);
"""


class _Rifiuto(Exception):
    """Richiesta rifiutata: il messaggio è già pronto per il modello."""


def _adesso_locale() -> datetime:
    return datetime.now().astimezone()


def _percorso(percorso: Path | None) -> Path:
    return Path(percorso or os.environ.get("NOTE_DB") or PERCORSO_PREDEFINITO)


def _aggiungi(conn: sqlite3.Connection, testo: str, adesso: Callable[[], datetime]) -> str:
    if not testo:
        raise _Rifiuto("per aggiungere una nota serve il testo.")
    if len(testo) > MAX_TESTO:
        raise _Rifiuto(f"testo troppo lungo (massimo {MAX_TESTO} caratteri).")
    cursore = conn.execute("INSERT INTO note (testo, creata) VALUES (?, ?)",
                           (testo, adesso().isoformat(timespec="minutes")))
    return f'Nota {cursore.lastrowid} salvata: "{testo}".'


def _elenca(conn: sqlite3.Connection) -> str:
    totale = conn.execute("SELECT COUNT(*) FROM note").fetchone()[0]
    if totale == 0:
        return "Nessuna nota salvata."
    ultime = conn.execute("SELECT id, testo, creata FROM note ORDER BY id DESC LIMIT ?",
                          (MAX_ELENCO,)).fetchall()
    intestazione = (f"Note salvate ({totale}):" if totale <= MAX_ELENCO
                    else f"Note salvate: {totale}; mostrate le ultime {MAX_ELENCO}.")
    righe = [f"- {i} · {datetime.fromisoformat(c).strftime('%Y-%m-%d %H:%M')} · {t}"
             for i, t, c in reversed(ultime)]
    return "\n".join([intestazione, *righe])


def _elimina(conn: sqlite3.Connection, id_nota: int | None, conferma: bool) -> str:
    if id_nota is None:
        raise _Rifiuto("per eliminare una nota serve il suo id (vedi azione elenca).")
    riga = conn.execute("SELECT testo FROM note WHERE id = ?", (id_nota,)).fetchone()
    if riga is None:
        return f"Nessuna nota con id {id_nota}."
    testo = riga[0]
    if conferma:
        richiesta = conn.execute("DELETE FROM conferme_richieste WHERE id_nota = ?", (id_nota,))
        if richiesta.rowcount == 1:  # secondo passo: c'era già una richiesta di conferma
            conn.execute("DELETE FROM note WHERE id = ?", (id_nota,))
            return f'Nota {id_nota} eliminata: "{testo}".'
    # Primo passo, anche se il modello ha già passato conferma=true (per esempio dopo aver
    # chiesto conferma a parole): non si cancella mai alla prima chiamata.
    conn.execute("INSERT OR REPLACE INTO conferme_richieste (id_nota) VALUES (?)", (id_nota,))
    premessa = "Prima di eliminare serve la conferma dell'utente. " if conferma else ""
    return (f'{premessa}Stai per eliminare la nota {id_nota}: "{testo}". Chiedi conferma '
            "all'utente e non procedere da solo; se l'utente conferma, richiama con "
            f"azione=elimina, id={id_nota} e conferma=true.")


def gestisci_note(azione: str, testo: str = "", id: int | None = None, conferma: bool = False,
                  percorso: Path | None = None,
                  adesso: Callable[[], datetime] | None = None) -> str:
    """Esegue l'azione sulle note; restituisce il risultato o un errore leggibile dal modello."""
    try:
        if azione not in AZIONI:
            raise _Rifiuto(f"azione sconosciuta: '{azione}'. Azioni ammesse: {', '.join(AZIONI)}.")
        testo = (testo or "").strip()
        try:
            with closing(sqlite3.connect(_percorso(percorso), timeout=5)) as conn:
                with conn:  # transazione: commit se tutto va bene, rollback altrimenti
                    conn.executescript(_SCHEMA)
                    if azione == "aggiungi":
                        return _aggiungi(conn, testo, adesso or _adesso_locale)
                    if azione == "elenca":
                        return _elenca(conn)
                    return _elimina(conn, id, conferma)
        except (sqlite3.Error, OSError):
            raise _Rifiuto("archivio delle note non disponibile.") from None
    except _Rifiuto as rifiuto:
        return f"Errore: {rifiuto}"


def crea_strumento_note(percorso: Path | None = None,
                        adesso: Callable[[], datetime] | None = None) -> BaseTool:
    """Costruisce lo strumento `note_persistenti`; `percorso` e `adesso` sono iniettabili."""

    def note_persistenti(azione: Literal["aggiungi", "elenca", "elimina"], testo: str = "",
                         id: int | None = None, conferma: bool = False) -> str:
        return gestisci_note(azione, testo, id, conferma, percorso, adesso)

    return StructuredTool.from_function(
        func=note_persistenti,
        name="note_persistenti",
        description=("Gestisce le note dell'utente, che restano salvate fra una sessione e "
                     "l'altra. azione=aggiungi con testo salva una nota; azione=elenca mostra "
                     "le note con il loro id; azione=elimina con id avvia l'eliminazione: la "
                     "prima chiamata non cancella ma chiede conferma, e solo dopo il sì "
                     "dell'utente si richiama con conferma=true. Usala anche quando l'utente "
                     "chiede di ricordare qualcosa (per esempio \"ricordami di...\")."),
    )
