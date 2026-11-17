"""Calcolo degli embedding tramite l'endpoint /v1/embeddings di LM Studio."""

from __future__ import annotations

from typing import Protocol

import httpx


class Embedder(Protocol):
    def embed(self, testi: list[str]) -> list[list[float]]:
        """Riceve testi già completi di prefisso e restituisce un vettore per testo."""
        ...


class ErroreEmbedding(Exception):
    """LM Studio non raggiungibile o risposta non valida."""


class EmbedderLMStudio:
    def __init__(self, url: str, modello: str, batch: int, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.modello = modello
        self.batch = batch
        self._client = client or httpx.Client(timeout=120.0)

    def _errore(self, motivo: str) -> ErroreEmbedding:
        return ErroreEmbedding(
            f"Embedding non riuscito ({motivo}). LM Studio: {self.url}, modello: {self.modello}. "
            "Controlla che LM Studio sia acceso e che il modello di embedding sia caricato."
        )

    def _lotto(self, testi: list[str]) -> list[list[float]]:
        try:
            risposta = self._client.post(
                f"{self.url}/embeddings", json={"model": self.modello, "input": testi}
            )
        except httpx.HTTPError as e:
            raise self._errore(f"connessione fallita: {e}") from e
        if risposta.status_code != 200:
            raise self._errore(f"HTTP {risposta.status_code}: {risposta.text[:200]}")
        try:
            dati = sorted(risposta.json()["data"], key=lambda d: d["index"])
            vettori = [list(map(float, d["embedding"])) for d in dati]
        except (ValueError, KeyError, TypeError) as e:
            raise self._errore(f"risposta non valida: {e}") from e
        if len(vettori) != len(testi):
            raise self._errore(f"{len(vettori)} vettori per {len(testi)} testi")
        return vettori

    def embed(self, testi: list[str]) -> list[list[float]]:
        vettori: list[list[float]] = []
        for i in range(0, len(testi), self.batch):
            vettori.extend(self._lotto(testi[i : i + self.batch]))
        return vettori
