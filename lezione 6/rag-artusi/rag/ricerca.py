"""Ricerca semantica top-k con filtro nativo per capitolo.

Uso: python -m rag.ricerca "domanda" [--capitolo X] [--k 3]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from rag.config import Config, ErroreConfigurazione, carica_config
from rag.corpus import CAPITOLI
from rag.embedder import Embedder, EmbedderLMStudio, ErroreEmbedding
from rag.indice import ErroreCollezione, verifica_compatibilita
from rag.ingestion import ERRORI_QDRANT

K_MASSIMO = 20


@dataclass(frozen=True)
class Risultato:
    score: float
    numero: int
    titolo: str
    capitolo: str
    posizione: int
    documento_id: str
    testo: str
    fonte: str


def normalizza_capitolo(nome: str) -> str:
    cercato = " ".join(nome.split()).casefold()
    for capitolo in CAPITOLI:
        if capitolo.casefold() == cercato:
            return capitolo
    raise ValueError(f"Capitolo sconosciuto: {nome!r}. Capitoli validi: " + "; ".join(CAPITOLI))


def cerca(
    domanda: str,
    k: int = 5,
    capitolo: str | None = None,
    *,
    client: QdrantClient,
    embedder: Embedder,
    config: Config,
) -> list[Risultato]:
    if not domanda or not domanda.strip():
        raise ValueError("La domanda è vuota")
    if not 1 <= k <= K_MASSIMO:
        raise ValueError(f"k deve essere tra 1 e {K_MASSIMO}, ricevuto {k}")
    filtro = None
    if capitolo is not None:
        filtro = models.Filter(
            must=[
                models.FieldCondition(
                    key="capitolo", match=models.MatchValue(value=normalizza_capitolo(capitolo))
                )
            ]
        )
    if not verifica_compatibilita(client, config):
        raise ErroreCollezione(
            f'La collezione "{config.collezione}" non esiste: esegui prima python -m rag.ingestion'
        )

    (vettore,) = embedder.embed([config.prefisso_query + domanda.strip()])
    risposta = client.query_points(
        config.collezione, query=vettore, query_filter=filtro, limit=k, with_payload=True
    )
    return [
        Risultato(
            score=p.score,
            numero=p.payload["numero"],
            titolo=p.payload["titolo"],
            capitolo=p.payload["capitolo"],
            posizione=p.payload["posizione"],
            documento_id=p.payload["documento_id"],
            testo=p.payload["testo"],
            fonte=p.payload["fonte"],
        )
        for p in risposta.points
    ]


def _formatta(i: int, r: Risultato) -> str:
    estratto = " ".join(r.testo.split())[:200]
    return (
        f"{i}. [{r.score:.3f}] Ricetta {r.numero} — {r.titolo} | {r.capitolo} | chunk {r.posizione}\n"
        f"   {estratto}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag.ricerca", description=__doc__.splitlines()[0])
    parser.add_argument("domanda")
    parser.add_argument("--capitolo", default=None, help="nome del capitolo (maiuscole indifferenti)")
    parser.add_argument("--k", type=int, default=5, help=f"numero di risultati (1-{K_MASSIMO})")
    args = parser.parse_args(argv)

    config = None
    try:
        config = carica_config()
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        risultati = cerca(args.domanda, args.k, args.capitolo, client=client, embedder=embedder, config=config)
    except (ValueError, ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({e}). "
              "Avvialo con: docker compose up -d", file=sys.stderr)
        return 1

    if not risultati:
        print("Nessun risultato.")
    for i, r in enumerate(risultati, start=1):
        print(_formatta(i, r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
