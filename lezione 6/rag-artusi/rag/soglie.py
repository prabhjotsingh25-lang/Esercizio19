"""Soglie di confidenza sul coseno (lezione 8, es. 4).

score >= alta → "affidabile"; bassa <= score < alta → "media"; score < bassa → escluso (mai
inviato al modello). Uno score uguale a una soglia va nella fascia superiore. Le soglie si
applicano al coseno migliore del passaggio fra le query usate, dopo la fusione e prima del
reranking: lo score RRF dipende solo dai ranghi e non dice nulla sulla somiglianza.
"""

from __future__ import annotations

from rag.avanzata import Candidato


def fascia(score: float, alta: float, bassa: float) -> str | None:
    if score >= alta:
        return "affidabile"
    if score >= bassa:
        return "media"
    return None


def applica(candidati: list[Candidato], alta: float, bassa: float) -> tuple[list[Candidato], int]:
    """Candidati rimasti (con la fascia impostata, ordine invariato) e numero di esclusi."""
    rimasti = []
    for c in candidati:
        f = fascia(c.score, alta, bassa)
        if f is not None:
            c.fascia = f
            rimasti.append(c)
    return rimasti, len(candidati) - len(rimasti)


def nota_esclusi(esclusi: int, rimasti: int, bassa: float) -> str | None:
    if not esclusi:
        return None
    if not rimasti:
        return (f"nessun passaggio sopra la soglia minima ({bassa:.2f}): "
                "il libro non sembra contenere la risposta")
    parola = "passaggio escluso" if esclusi == 1 else "passaggi esclusi"
    return f"{esclusi} {parola} perché sotto la soglia minima ({bassa:.2f})"
