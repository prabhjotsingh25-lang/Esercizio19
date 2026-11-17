"""Ingestion: corpus -> chunk -> embedding -> Qdrant. Uso: python -m rag.ingestion"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from rag.chunking import crea_chunk, testo_da_indicizzare
from rag.config import Config, ErroreConfigurazione, carica_config
from rag.corpus import Ricetta, carica_corpus
from rag.embedder import Embedder, EmbedderLMStudio, ErroreEmbedding
from rag.indice import (
    IN_AGGIORNAMENTO,
    ErroreCollezione,
    aggiorna_campo,
    assicura_indici,
    conta,
    crea_collezione,
    elimina_orfani,
    imposta_formato,
    scrivi,
    testi_salvati,
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
    formato: str = "titolo_capitolo"


def esegui_ingestion(
    config: Config, client: QdrantClient, embedder: Embedder, ricette: list[Ricetta] | None = None
) -> Rapporto:
    if ricette is None:
        ricette = carica_corpus(config.corpus)
    chunk = crea_chunk(ricette, config)

    # Controllo del modello prima di calcolare qualsiasi embedding.
    esiste = verifica_compatibilita(client, config)

    # Tutti gli embedding prima di scrivere: se il calcolo si interrompe, la collezione resta intatta.
    vettori = embedder.embed([testo_da_indicizzare(c, config) for c in chunk])
    dimensione = len(vettori[0])
    if esiste:
        verifica_compatibilita(client, config, dimensione=dimensione)
        assicura_indici(client, config.collezione)
        imposta_formato(client, config.collezione, IN_AGGIORNAMENTO)  # stessa collezione, mai ricreata
    else:
        crea_collezione(client, config, dimensione, formato=IN_AGGIORNAMENTO)

    scritti = scrivi(client, config.collezione, chunk, vettori)
    eliminati = elimina_orfani(client, config.collezione, {c.id for c in chunk})
    imposta_formato(client, config.collezione, config.testo_indicizzato)
    return Rapporto(
        ricette=len(ricette),
        capitoli=len({r.capitolo for r in ricette}),
        chunk=len(chunk),
        scritti=scritti,
        eliminati=eliminati,
        punti=conta(client, config.collezione),
        formato=config.testo_indicizzato,
    )


@dataclass
class RapportoPayload:
    aggiornati: int
    con_dosi: int
    punti: int


def aggiorna_payload(config: Config, client: QdrantClient, ricette: list[Ricetta] | None = None) -> RapportoPayload:
    """Scrive `contiene_dosi` sui punti esistenti con set_payload, senza calcolare embedding."""
    if not verifica_compatibilita(client, config):
        raise ErroreCollezione(
            f'La collezione "{config.collezione}" non esiste: esegui prima l\'ingestion completa '
            "(python -m rag.ingestion)"
        )
    if ricette is None:
        ricette = carica_corpus(config.corpus)
    chunk = crea_chunk(ricette, config)
    salvati = testi_salvati(client, config.collezione)
    attesi = {c.id: c.testo for c in chunk}
    if salvati != attesi:
        diversi = len(set(salvati) ^ set(attesi)) + sum(
            1 for i in set(salvati) & set(attesi) if salvati[i] != attesi[i]
        )
        raise ErroreCollezione(
            f"I chunk non coincidono con la collezione ({len(attesi)} calcolati, {len(salvati)} salvati, "
            f"{diversi} differenze): è cambiato il chunking o il corpus. Esegui l'ingestion completa."
        )
    valori = {c.id: c.payload["contiene_dosi"] for c in chunk}
    aggiornati = aggiorna_campo(client, config.collezione, "contiene_dosi", valori)
    assicura_indici(client, config.collezione)
    return RapportoPayload(
        aggiornati=aggiornati, con_dosi=sum(valori.values()), punti=conta(client, config.collezione)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag.ingestion")
    parser.add_argument(
        "--solo-payload",
        action="store_true",
        help="aggiorna solo i campi del payload (contiene_dosi) sui punti esistenti, senza embedding",
    )
    args = parser.parse_args(argv)

    config = None
    try:
        config = carica_config()
        client = QdrantClient(url=config.qdrant_url)
        if args.solo_payload:
            rapporto = aggiorna_payload(config, client)
        else:
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
