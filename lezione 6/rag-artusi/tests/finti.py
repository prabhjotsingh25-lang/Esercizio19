"""Embedder finto per i test: vettori deterministici, nessun servizio esterno."""

from __future__ import annotations

import hashlib


class EmbedderFinto:
    def __init__(self, dimensione: int = 8):
        self.dimensione = dimensione
        self.ricevuti: list[str] = []
        self.chiamate = 0

    def _vettore(self, testo: str) -> list[float]:
        digest = hashlib.sha256(testo.encode("utf-8")).digest()
        return [(digest[i % len(digest)] - 127.5) / 127.5 for i in range(self.dimensione)]

    def embed(self, testi: list[str]) -> list[list[float]]:
        self.chiamate += 1
        self.ricevuti.extend(testi)
        return [self._vettore(t) for t in testi]
