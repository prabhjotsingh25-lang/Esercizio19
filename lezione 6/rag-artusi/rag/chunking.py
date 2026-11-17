"""Divisione delle ricette in chunk e identificativi stabili dei punti."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from rag.config import Config
from rag.corpus import Ricetta
from rag.dosi import contiene_dosi

# Costante del progetto: cambiarla cambierebbe tutti gli ID dei punti.
NAMESPACE_PROGETTO = uuid.UUID("3f6c2a8e-1b7d-4e55-9a0c-5d2e8f4b7a61")
FONTE = "Artusi, La scienza in cucina (Project Gutenberg n. 59047)"

_FINE_FRASE = re.compile(r"[.;:](?=\s)")
_SPAZIO = re.compile(r"\s")


@dataclass(frozen=True)
class Chunk:
    id: str
    testo: str
    payload: dict


def documento_id(numero: int) -> str:
    return f"artusi-{numero:03d}"


def id_punto(documento_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(NAMESPACE_PROGETTO, f"{documento_id}:{chunk_index}"))


def _taglio(testo: str, limite: int, frasi: bool) -> int:
    """Posizione (<= limite) dove tagliare: a fine frase se richiesto, altrimenti a fine parola."""
    finestra = testo[: limite + 1]
    if frasi:
        fini = [m.end() for m in _FINE_FRASE.finditer(finestra) if m.end() <= limite]
        if fini:
            return fini[-1]
    spazi = [m.start() for m in _SPAZIO.finditer(finestra)]
    return spazi[-1] if spazi and spazi[-1] > 0 else limite


def _spezza_paragrafo(paragrafo: str, dimensione: int) -> list[tuple[str, str]]:
    """Pezzi <= dimensione, ciascuno con il separatore che lo precedeva nel testo."""
    pezzi: list[tuple[str, str]] = []
    resto, separatore = paragrafo, ""
    while len(resto) > dimensione:
        taglio = _taglio(resto, dimensione, frasi=True)
        pezzi.append((resto[:taglio].rstrip(), separatore))
        dopo = resto[taglio:]
        spazi = len(dopo) - len(dopo.lstrip())
        separatore = dopo[:spazi] or " "
        resto = dopo.lstrip()
    if resto:
        pezzi.append((resto, separatore))
    return pezzi


def _coda(testo: str, overlap: int) -> str:
    """Ultimi <= overlap caratteri di `testo`, a partire dall'inizio di una parola."""
    if overlap <= 0:
        return ""
    if len(testo) <= overlap:
        return testo
    coda = testo[-overlap:]
    if not testo[-overlap - 1].isspace():
        m = _SPAZIO.search(coda)
        coda = coda[m.end():] if m else ""
    return coda.lstrip()


def _per_paragrafi(testo: str, dimensione: int, overlap: int) -> list[str]:
    pezzi: list[tuple[str, str]] = []
    for i, paragrafo in enumerate(testo.split("\n\n")):
        for j, (pezzo, sep) in enumerate(_spezza_paragrafo(paragrafo, dimensione)):
            pezzi.append((pezzo, sep if j else ("\n\n" if i else "")))

    gruppi: list[list[tuple[str, str]]] = []
    lunghezza = 0
    for pezzo, sep in pezzi:
        if gruppi and lunghezza + len(sep) + len(pezzo) <= dimensione:
            gruppi[-1].append((pezzo, sep))
            lunghezza += len(sep) + len(pezzo)
        else:
            gruppi.append([(pezzo, sep)])
            lunghezza = len(pezzo)

    chunk: list[str] = []
    for gruppo in gruppi:
        nuovo = gruppo[0][0] + "".join(sep + pezzo for pezzo, sep in gruppo[1:])
        coda = _coda(chunk[-1], overlap) if chunk else ""
        chunk.append(coda + gruppo[0][1] + nuovo if coda else nuovo)
    return chunk


def _per_caratteri(testo: str, dimensione: int, overlap: int) -> list[str]:
    chunk: list[str] = []
    inizio = 0
    while inizio < len(testo):
        if len(testo) - inizio <= dimensione:
            chunk.append(testo[inizio:])
            break
        taglio = inizio + _taglio(testo[inizio:], dimensione, frasi=False)
        chunk.append(testo[inizio:taglio].rstrip())
        prossimo = taglio - overlap
        if prossimo > inizio and not testo[prossimo - 1].isspace():
            m = _SPAZIO.search(testo, prossimo, taglio)
            prossimo = m.end() if m else taglio
        prossimo = max(prossimo, inizio + 1)
        while prossimo < len(testo) and testo[prossimo].isspace():
            prossimo += 1
        inizio = prossimo
    return chunk


def dividi(testo: str, strategia: str, dimensione: int, overlap: int) -> list[str]:
    if strategia not in ("paragrafi", "caratteri"):
        raise ValueError(f"Strategia di chunking sconosciuta: {strategia!r}")
    if len(testo) <= dimensione:
        return [testo]
    if strategia == "paragrafi":
        return _per_paragrafi(testo, dimensione, overlap)
    return _per_caratteri(testo, dimensione, overlap)


def crea_chunk(ricette: list[Ricetta], config: Config) -> list[Chunk]:
    risultato: list[Chunk] = []
    for ricetta in ricette:
        doc = documento_id(ricetta.numero)
        testi = dividi(ricetta.corpo, config.chunk_strategia, config.chunk_dimensione, config.chunk_overlap)
        for posizione, testo in enumerate(testi):
            risultato.append(
                Chunk(
                    id=id_punto(doc, posizione),
                    testo=testo,
                    payload={
                        "documento_id": doc,
                        "numero": ricetta.numero,
                        "titolo": ricetta.titolo,
                        "capitolo": ricetta.capitolo,
                        "posizione": posizione,
                        "testo": testo,
                        "fonte": FONTE,
                        "contiene_dosi": contiene_dosi(testo),
                    },
                )
            )
    return risultato
