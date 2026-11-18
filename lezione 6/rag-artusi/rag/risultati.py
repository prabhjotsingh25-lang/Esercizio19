"""Formato dei passaggi e del risultato del tool `search_documents` (funzioni pure)."""

from __future__ import annotations

from rag.ricerca import Risultato

ELLISSI = "…"
SEPARATORE_NOTE = " · "


def id_passaggio(numero: int, posizione: int) -> str:
    """Id breve, stabile e citabile: numero della ricetta . posizione del chunk (es. 89.1)."""
    return f"{numero}.{posizione}"


def tronca(testo: str, massimo: int) -> str:
    """Spazi normalizzati; se supera `massimo` caratteri, taglia e chiude con «…» (totale <= massimo)."""
    pulito = " ".join(testo.split())
    if len(pulito) <= massimo:
        return pulito
    return pulito[: max(massimo - 1, 0)].rstrip() + ELLISSI if massimo > 1 else ELLISSI[:massimo]


def limita_top_k(top_k: int, massimo: int) -> tuple[int, str | None]:
    """Porta top_k in [1, massimo]; la nota spiega la correzione al modello."""
    if top_k > massimo:
        return massimo, f"top_k ridotto da {top_k} a {massimo} (massimo consentito)"
    if top_k < 1:
        return 1, f"top_k portato da {top_k} a 1 (minimo consentito)"
    return top_k, None


def passaggio(r: Risultato, max_caratteri: int) -> dict:
    return {
        "id": id_passaggio(r.numero, r.posizione),
        "ricetta": r.numero,
        "titolo": r.titolo,
        "capitolo": r.capitolo,
        "posizione_chunk": r.posizione,
        "score": round(float(r.score), 3),
        "testo": tronca(r.testo, max_caratteri),
    }


def componi_risultato(modalita: str, query_usate: list[str], passaggi: list[dict], note: list[str]) -> dict:
    return {
        "modalita": modalita,
        "query_usate": list(query_usate),
        "passaggi": list(passaggi),
        "nota": SEPARATORE_NOTE.join(n for n in note if n),
    }
