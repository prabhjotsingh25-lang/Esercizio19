"""Operazioni sulla collezione Qdrant: creazione, metadati del modello, scrittura e pulizia."""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from rag.chunking import Chunk
from rag.config import Config

LOTTO_SCRITTURA = 256
LOTTO_SCROLL = 1000
INDICI = {
    "capitolo": models.PayloadSchemaType.KEYWORD,
    "contiene_dosi": models.PayloadSchemaType.BOOL,
}


class ErroreCollezione(Exception):
    """Collezione assente o creata con una configurazione di embedding diversa."""


def metadati_attesi(config: Config, dimensione: int | None = None) -> dict:
    metadati = {
        "modello_embedding": config.modello_embedding,
        "prefisso_documento": config.prefisso_documento,
        "prefisso_query": config.prefisso_query,
    }
    if dimensione is not None:
        metadati["dimensione"] = dimensione
    return metadati


def verifica_compatibilita(client: QdrantClient, config: Config, dimensione: int | None = None) -> bool:
    """False se la collezione non esiste, True se è compatibile, altrimenti ErroreCollezione."""
    nome = config.collezione
    if not client.collection_exists(nome):
        return False
    salvati = client.get_collection(nome).config.metadata or {}
    if not salvati:
        raise ErroreCollezione(
            f'La collezione "{nome}" non ha metadati sul modello di embedding: non si sa con quale '
            "modello è stata riempita. Usa un'altra COLLEZIONE oppure cancella la collezione."
        )
    for campo, nuovo in metadati_attesi(config, dimensione).items():
        vecchio = salvati.get(campo)
        if vecchio != nuovo:
            raise ErroreCollezione(
                f'La collezione "{nome}" è stata creata con {campo} = {vecchio!r}; '
                f"la configurazione indica {nuovo!r}. Usa un'altra COLLEZIONE oppure cancella la collezione."
            )
    return True


def crea_collezione(client: QdrantClient, config: Config, dimensione: int) -> None:
    client.create_collection(
        config.collezione,
        vectors_config=models.VectorParams(size=dimensione, distance=models.Distance.COSINE),
        metadata=metadati_attesi(config, dimensione),
    )
    assicura_indici(client, config.collezione)


def assicura_indici(client: QdrantClient, nome: str) -> list[str]:
    """Crea gli indici del payload che mancano; restituisce i campi indicizzati ora."""
    presenti = client.get_collection(nome).payload_schema or {}
    creati = []
    for campo, tipo in INDICI.items():
        if campo not in presenti:
            client.create_payload_index(nome, campo, field_schema=tipo)
            creati.append(campo)
    return creati


def scrivi(client: QdrantClient, nome: str, chunk: list[Chunk], vettori: list[list[float]]) -> int:
    if len(chunk) != len(vettori):
        raise ValueError(f"{len(chunk)} chunk ma {len(vettori)} vettori")
    punti = [models.PointStruct(id=c.id, vector=v, payload=c.payload) for c, v in zip(chunk, vettori)]
    for i in range(0, len(punti), LOTTO_SCRITTURA):
        client.upsert(nome, points=punti[i : i + LOTTO_SCRITTURA], wait=True)
    return len(punti)


def elimina_orfani(client: QdrantClient, nome: str, id_validi: set[str]) -> int:
    """Cancella i punti il cui ID non è tra quelli prodotti dall'ultima ingestion."""
    orfani: list = []
    offset = None
    while True:
        punti, offset = client.scroll(
            nome, limit=LOTTO_SCROLL, offset=offset, with_payload=False, with_vectors=False
        )
        orfani.extend(p.id for p in punti if str(p.id) not in id_validi)
        if offset is None:
            break
    if orfani:
        client.delete(nome, points_selector=models.PointIdsList(points=orfani), wait=True)
    return len(orfani)


def testi_salvati(client: QdrantClient, nome: str) -> dict[str, str]:
    """ID del punto -> `testo` del payload, per tutti i punti della collezione."""
    testi: dict[str, str] = {}
    offset = None
    while True:
        punti, offset = client.scroll(
            nome, limit=LOTTO_SCROLL, offset=offset, with_payload=["testo"], with_vectors=False
        )
        testi.update({str(p.id): (p.payload or {}).get("testo") for p in punti})
        if offset is None:
            return testi


def aggiorna_campo(client: QdrantClient, nome: str, campo: str, valori: dict[str, bool]) -> int:
    """Scrive `campo` con set_payload (una chiamata per valore, a lotti): i vettori non si toccano."""
    for valore in sorted(set(valori.values())):
        ids = [i for i, v in valori.items() if v == valore]
        for j in range(0, len(ids), LOTTO_SCROLL):
            client.set_payload(nome, payload={campo: valore}, points=ids[j : j + LOTTO_SCROLL], wait=True)
    return len(valori)


def conta(client: QdrantClient, nome: str) -> int:
    return client.count(nome, exact=True).count
