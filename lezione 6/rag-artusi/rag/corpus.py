"""Pulizia del testo Gutenberg e divisione in ricette (unità di documento)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CAPITOLI: tuple[str, ...] = (
    "Brodi, gelatina e sughi",
    "Minestre in brodo",
    "Minestre asciutte e di magro",
    "Principii",
    "Salse",
    "Uova",
    "Paste e pastelle",
    "Ripieni",
    "Fritti",
    "Lesso",
    "Tramessi",
    "Umidi",
    "Rifreddi",
    "Erbaggi e legumi",
    "Piatti di pesce",
    "Arrosti",
    "Pasticceria",
    "Torte e dolci al cucchiaio",
    "Siroppi",
    "Conserve",
    "Liquori",
    "Gelati",
    "Cose diverse",
)

_TITOLI_CAPITOLO = {c.upper(): c for c in CAPITOLI}
_CONFINE = "MINESTRE"  # chiude la ricetta precedente ma non è un capitolo
_FINE = "APPENDICE"  # dopo questa riga non ci sono più ricette
_INTESTAZIONE = re.compile(r"^(\d+)\. (.+)$")
_ILLUSTRAZIONE = re.compile(r"\[Illustrazione:.*?\]", re.S)
_RICHIAMO_NOTA = re.compile(r"\[\d+\]")


@dataclass(frozen=True)
class Ricetta:
    numero: int
    titolo: str
    capitolo: str
    corpo: str


def pulisci(testo: str) -> str:
    """Toglie BOM, CRLF e tutto ciò che sta fuori dalle righe START/END di Gutenberg."""
    testo = testo.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    righe = testo.split("\n")
    inizio = next((i for i, r in enumerate(righe) if r.startswith("*** START OF")), -1)
    fine = next((i for i, r in enumerate(righe) if r.startswith("*** END OF")), len(righe))
    return "\n".join(righe[inizio + 1 : fine])


def _componi_corpo(righe: list[str]) -> str:
    testo = "\n".join(righe)
    testo = _ILLUSTRAZIONE.sub("", testo)
    testo = _RICHIAMO_NOTA.sub("", testo)
    testo = testo.replace("_", "")

    paragrafi: list[list[str]] = [[]]
    for riga in testo.split("\n"):
        if riga.strip():
            paragrafi[-1].append(riga.rstrip())
        elif paragrafi[-1]:
            paragrafi.append([])

    risultato = []
    for paragrafo in paragrafi:
        if not paragrafo:
            continue
        voci: list[list] = []  # [testo, rientro o None per la prosa]
        for riga in paragrafo:
            rientro = len(riga) - len(riga.lstrip())
            contenuto = riga.strip()
            if rientro:
                # una riga più rientrata della precedente voce rientrata la continua
                if voci and voci[-1][1] is not None and rientro > voci[-1][1]:
                    voci[-1][0] += " " + contenuto
                else:
                    voci.append([contenuto, rientro])
            elif voci and voci[-1][1] is None:
                voci[-1][0] += " " + contenuto
            else:
                voci.append([contenuto, None])
        risultato.append("\n".join(v[0] for v in voci))
    return "\n\n".join(risultato)


def estrai_ricette(testo_pulito: str) -> list[Ricetta]:
    """Divide il testo in ricette numerate 1..N, accettando solo il numero atteso."""
    righe = testo_pulito.split("\n")
    inizio = next((i + 1 for i, r in enumerate(righe) if r.strip() == "RICETTE"), 0)

    ricette: list[Ricetta] = []
    capitolo: str | None = None
    aperta: tuple[int, str, str] | None = None
    corpo: list[str] = []
    atteso = 1

    def chiudi() -> None:
        nonlocal aperta, corpo
        if aperta is not None:
            ricette.append(Ricetta(aperta[0], aperta[1], aperta[2], _componi_corpo(corpo)))
        aperta, corpo = None, []

    for i in range(inizio, len(righe)):
        riga = righe[i]
        pulita = riga.strip()
        if pulita == _FINE:
            break
        if pulita in _TITOLI_CAPITOLO or pulita == _CONFINE:
            chiudi()
            capitolo = _TITOLI_CAPITOLO.get(pulita)
            continue
        m = _INTESTAZIONE.match(riga)
        if m and int(m.group(1)) == atteso:
            chiudi()
            if capitolo is None:
                raise ValueError(f"Ricetta {atteso} senza capitolo (riga {i + 1})")
            aperta = (atteso, m.group(2).strip(), capitolo)
            atteso += 1
            continue
        if m and _isolata(righe, i):
            raise ValueError(
                f"Numerazione inattesa: trovata la ricetta {m.group(1)} mentre si attendeva la {atteso}"
            )
        if aperta is not None:
            corpo.append(riga)
    chiudi()
    return ricette


def _isolata(righe: list[str], i: int) -> bool:
    """Una riga `N. Titolo` tra due righe vuote ha la forma di un'intestazione di ricetta."""
    prima = righe[i - 1].strip() if i > 0 else ""
    dopo = righe[i + 1].strip() if i + 1 < len(righe) else ""
    return not prima and not dopo


def carica_corpus(percorso: Path) -> list[Ricetta]:
    return estrai_ricette(pulisci(Path(percorso).read_text(encoding="utf-8")))
