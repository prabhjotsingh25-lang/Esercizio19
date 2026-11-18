"""Ricerca semantica top-k con filtro nativo per capitolo.

Uso: python -m rag.ricerca "domanda" [--capitolo X] [--k 3]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from rag.config import K_MASSIMO_CODICE, Config, ErroreConfigurazione, carica_config
from rag.corpus import CAPITOLI
from rag.embedder import Embedder, EmbedderLMStudio, ErroreEmbedding
from rag.indice import IN_AGGIORNAMENTO, ErroreCollezione, formato_salvato, verifica_compatibilita
from rag.ingestion import ERRORI_QDRANT

K_MASSIMO = K_MASSIMO_CODICE


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
    contiene_dosi: bool = False


def costruisci_filtro(capitolo: str | None, solo_dosi: bool) -> models.Filter | None:
    """Filtro nativo Qdrant: le condizioni sono applicate durante la ricerca, non dopo."""
    condizioni = []
    if capitolo is not None:
        condizioni.append(
            models.FieldCondition(key="capitolo", match=models.MatchValue(value=normalizza_capitolo(capitolo)))
        )
    if solo_dosi:
        condizioni.append(models.FieldCondition(key="contiene_dosi", match=models.MatchValue(value=True)))
    return models.Filter(must=condizioni) if condizioni else None


def _verifica_campo_dosi(client: QdrantClient, nome: str) -> None:
    """Con --solo-dosi, punti senza il campo vorrebbero dire risultati mancanti senza spiegazione."""
    senza_campo = client.count(
        nome,
        count_filter=models.Filter(must=[models.IsEmptyCondition(is_empty=models.PayloadField(key="contiene_dosi"))]),
        exact=True,
    ).count
    if senza_campo:
        raise ErroreCollezione(
            f'{senza_campo} punti della collezione "{nome}" non hanno il campo contiene_dosi '
            "(collezione creata prima della modifica A): esegui python -m rag.ingestion --solo-payload"
        )


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
    solo_dosi: bool = False,
    *,
    client: QdrantClient,
    embedder: Embedder,
    config: Config,
) -> list[Risultato]:
    if not domanda or not domanda.strip():
        raise ValueError("La domanda è vuota")
    if not 1 <= k <= K_MASSIMO:
        raise ValueError(f"k deve essere tra 1 e {K_MASSIMO}, ricevuto {k}")
    filtro = costruisci_filtro(capitolo, solo_dosi)
    if not verifica_compatibilita(client, config):
        raise ErroreCollezione(
            f'La collezione "{config.collezione}" non esiste: esegui prima python -m rag.ingestion'
        )

    if solo_dosi:
        _verifica_campo_dosi(client, config.collezione)

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
            contiene_dosi=bool(p.payload.get("contiene_dosi", False)),
        )
        for p in risposta.points
    ]


def _formatta(i: int, r: Risultato) -> str:
    estratto = " ".join(r.testo.split())[:200]
    dosi = " | dosi" if r.contiene_dosi else ""
    return (
        f"{i}. [{r.score:.3f}] Ricetta {r.numero} — {r.titolo} | {r.capitolo} | chunk {r.posizione}{dosi}\n"
        f"   {estratto}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag.ricerca", description=__doc__.splitlines()[0])
    parser.add_argument("domanda")
    parser.add_argument("--capitolo", default=None, help="nome del capitolo (maiuscole indifferenti)")
    parser.add_argument("--solo-dosi", action="store_true", help="solo chunk con un elenco di ingredienti e quantità")
    parser.add_argument("--k", type=int, default=5, help=f"numero di risultati (1-{K_MASSIMO})")
    args = parser.parse_args(argv)

    config = None
    try:
        config = carica_config()
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        risultati = cerca(
            args.domanda, args.k, args.capitolo, args.solo_dosi, client=client, embedder=embedder, config=config
        )
    except (ValueError, ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({e}). "
              "Avvialo con: docker compose up -d", file=sys.stderr)
        return 1

    if formato_salvato(client, config.collezione) == IN_AGGIORNAMENTO:
        print(
            f'Avviso: la collezione "{config.collezione}" è in aggiornamento (un\'ingestion si è interrotta): '
            "i vettori possono essere misti. Riesegui python -m rag.ingestion.",
            file=sys.stderr,
        )
    if not risultati:
        print("Nessun risultato.")
    for i, r in enumerate(risultati, start=1):
        print(_formatta(i, r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
