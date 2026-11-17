"""Ingestion: corpus -> chunk -> embedding -> Qdrant. Uso: python -m rag.ingestion"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from rag.chunking import crea_chunk
from rag.config import Config, ErroreConfigurazione, carica_config
from rag.corpus import Ricetta, carica_corpus
from rag.embedder import Embedder, EmbedderLMStudio, ErroreEmbedding
from rag.indice import (
    ErroreCollezione,
    assicura_indici,
    conta,
    crea_collezione,
    elimina_orfani,
    scrivi,
    verifica_compatibilita,
)

ERRORI_QDRANT = (ResponseHandlingException, UnexpectedResponse, httpx.HTTPError, ConnectionError)


@dataclass
class Rapporto:
    ricette: int
    capitoli: int
    chunk: int
    scritti: int
    eliminati: int
    punti: int


def esegui_ingestion(
    config: Config, client: QdrantClient, embedder: Embedder, ricette: list[Ricetta] | None = None
) -> Rapporto:
    if ricette is None:
        ricette = carica_corpus(config.corpus)
    chunk = crea_chunk(ricette, config)

    # Controllo del modello prima di calcolare qualsiasi embedding.
    esiste = verifica_compatibilita(client, config)

    vettori = embedder.embed([config.prefisso_documento + c.testo for c in chunk])
    dimensione = len(vettori[0])
    if esiste:
        verifica_compatibilita(client, config, dimensione=dimensione)
        assicura_indici(client, config.collezione)
    else:
        crea_collezione(client, config, dimensione)

    scritti = scrivi(client, config.collezione, chunk, vettori)
    eliminati = elimina_orfani(client, config.collezione, {c.id for c in chunk})
    return Rapporto(
        ricette=len(ricette),
        capitoli=len({r.capitolo for r in ricette}),
        chunk=len(chunk),
        scritti=scritti,
        eliminati=eliminati,
        punti=conta(client, config.collezione),
    )


def main(argv: list[str] | None = None) -> int:
    config = None
    try:
        config = carica_config()
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        rapporto = esegui_ingestion(config, client, embedder)
    except (ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({e}). "
              "Avvialo con: docker compose up -d", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"Errore: corpus non trovato ({e}). Controlla CORPUS nel file .env.", file=sys.stderr)
        return 1

    print(f"Collezione: {config.collezione} (modello {config.modello_embedding})")
    for campo, valore in vars(rapporto).items():
        print(f"{campo}: {valore}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
