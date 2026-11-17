"""Riconoscimento degli elenchi di ingredienti con quantità (campo `contiene_dosi`).

Una voce di dose ha la forma «Ingrediente, quantità.» su una riga breve (es. «Farina di grano,
grammi 150.»); un chunk contiene dosi se ha almeno 2 voci. Specifica: docs/specs/modifica-a.md §3.

Uso: python -m rag.dosi --campione 30 --seme 42
"""

from __future__ import annotations

import argparse
import random
import re
import sys

from rag.chunking import Chunk

RIGA_MASSIMA = 100
MINIMO_VOCI = 2

_QUANTITA = (
    r"(?:\d|N\.|gr\.|\b(?:grammi|chilogramm\w*|ettogramm\w*|decilitr\w*|litr[oi]|cucchia\w*"
    r"|bicchier\w*|presa|pizzico|quanto|idem|inter[oaie]|ross[oi])\b)"
)
_VOCE = re.compile(r"^[A-ZÀ-Ý][^,]{1,59},\s*(?P<quantita>.{0,40})$")
_QUANTITA_RE = re.compile(_QUANTITA, re.I)
_SEPARA_VOCI = re.compile(r"(?<=\.)\s+(?=[A-ZÀ-Ý])")
_SOSPETTA = re.compile(r"\d|" + _QUANTITA, re.I)


def voci_dose(testo: str) -> list[str]:
    """Le voci «Ingrediente, quantità» riconosciute nelle righe brevi del testo."""
    voci = []
    for riga in testo.split("\n"):
        riga = riga.strip()
        if not riga or len(riga) > RIGA_MASSIMA:
            continue
        for segmento in _SEPARA_VOCI.split(riga):
            m = _VOCE.match(segmento)
            if m and _QUANTITA_RE.search(m.group("quantita")):
                voci.append(segmento)
    return voci


def contiene_dosi(testo: str) -> bool:
    return len(voci_dose(testo)) >= MINIMO_VOCI


def campione(chunk: list[Chunk], n: int, seme: int) -> tuple[list[Chunk], list[Chunk]]:
    """n chunk positivi e n negativi scelti a caso con seme fisso (tutti, se sono meno di n)."""
    positivi = [c for c in chunk if contiene_dosi(c.testo)]
    negativi = [c for c in chunk if not contiene_dosi(c.testo)]
    rng = random.Random(seme)
    return (
        rng.sample(positivi, min(n, len(positivi))),
        rng.sample(negativi, min(n, len(negativi))),
    )


def _descrivi(c: Chunk, positivo: bool) -> str:
    p = c.payload
    if positivo:
        righe = voci_dose(c.testo)
    else:
        righe = [r for r in c.testo.split("\n") if r.strip() and len(r) <= RIGA_MASSIMA and _SOSPETTA.search(r)]
    dettaglio = "\n".join(f"      {r}" for r in righe) or "      (nessuna riga breve con quantità)"
    return f"- Ricetta {p['numero']} — {p['titolo']} | chunk {p['posizione']} | {len(c.testo)} caratteri\n{dettaglio}"


def main(argv: list[str] | None = None) -> int:
    from rag.chunking import crea_chunk
    from rag.config import ErroreConfigurazione, carica_config
    from rag.corpus import carica_corpus

    parser = argparse.ArgumentParser(prog="python -m rag.dosi")
    parser.add_argument("--campione", type=int, default=30)
    parser.add_argument("--seme", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        config = carica_config()
        chunk = crea_chunk(carica_corpus(config.corpus), config)
    except (ErroreConfigurazione, FileNotFoundError) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    totale_veri = sum(contiene_dosi(c.testo) for c in chunk)
    ricette = len({c.payload["numero"] for c in chunk if contiene_dosi(c.testo)})
    print(f"Chunk con dosi: {totale_veri} su {len(chunk)}; ricette con almeno un chunk con dosi: {ricette}")
    positivi, negativi = campione(chunk, args.campione, args.seme)
    print(f"\n## Positivi ({len(positivi)}, seme {args.seme})")
    for c in positivi:
        print(_descrivi(c, True))
    print(f"\n## Negativi ({len(negativi)}, seme {args.seme})")
    for c in negativi:
        print(_descrivi(c, False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
