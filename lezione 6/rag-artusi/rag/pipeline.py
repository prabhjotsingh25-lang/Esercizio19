"""Pipeline di ricerca per tutte le modalità (lezione 8): la usano il server MCP e il confronto.

    base:        domanda → Qdrant(top_k)
    riscrittura: LLM → [originale + 1-3 query] → Qdrant(candidati) per query → RRF → top_k
    reranking:   domanda → Qdrant(candidati) → LLM listwise → top_k
    entrambe:    riscrittura → RRF → LLM listwise → top_k
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qdrant_client import QdrantClient

from rag.avanzata import Candidato, Ripiego, da_lista, fondi, riordina, riscrivi
from rag.config import Config
from rag.embedder import Embedder
from rag.llm import LLM
from rag.ricerca import cerca
from rag.soglie import applica, nota_esclusi

DA_CONFIG = "config"  # soglie: quelle della configurazione (se SOGLIE_ATTIVE)

NOTA_RERANKING_VUOTO = "il reranking non ha trovato passaggi pertinenti alla domanda"


@dataclass
class EsitoPipeline:
    modalita: str
    query_usate: list[str]
    candidati: list[Candidato]
    note: list[str] = field(default_factory=list)
    ripieghi: list[Ripiego] = field(default_factory=list)
    chiamate_llm: int = 0
    esclusi_soglia: int = 0


def esegui(domanda: str, top_k: int, capitolo: str | None, *, client: QdrantClient, embedder: Embedder,
           llm: LLM | None, config: Config, modalita: str | None = None,
           soglie: tuple[float, float] | None | str = DA_CONFIG) -> EsitoPipeline:
    """Le eccezioni di Qdrant e dell'embedding passano al chiamante; quelle dell'LLM no (ripieghi).

    `soglie` = (alta, bassa), None (disattivate) o DA_CONFIG. Si applicano al coseno migliore del
    passaggio dopo la fusione e prima del reranking (vedi rag/soglie.py).
    """
    if soglie == DA_CONFIG:
        soglie = (config.soglia_alta, config.soglia_bassa) if config.soglie_attive else None
    modalita = modalita or config.modalita_ricerca
    riscrittura = modalita in ("riscrittura", "entrambe")
    reranking = modalita in ("reranking", "entrambe")
    chiamate_iniziali = llm.chiamate if llm is not None else 0
    originale = domanda.strip()
    query, ripieghi, note = [originale], [], []

    if riscrittura:
        query, nuovi = riscrivi(originale, llm, config.riscrittura_max_query)
        ripieghi += nuovi
    per_query = top_k if modalita == "base" else max(top_k, config.candidati_per_query)
    liste = [cerca(q, per_query, capitolo, client=client, embedder=embedder, config=config) for q in query]
    candidati = da_lista(liste[0]) if len(liste) == 1 else fondi(liste, config.rrf_k)
    esclusi = 0
    if soglie is not None:
        candidati, esclusi = applica(candidati, *soglie)
        nota = nota_esclusi(esclusi, len(candidati), soglie[1])
        if nota:
            note.append(nota)

    if reranking:
        ordinati, nuovi = riordina(originale, candidati, llm, config.rerank_max_candidati,
                                   config.rerank_max_caratteri)
        ripieghi += nuovi
        if ordinati is not None:
            candidati = ordinati
            if not ordinati:
                note.append(NOTA_RERANKING_VUOTO)

    note += [r.descrizione for r in ripieghi]
    chiamate = (llm.chiamate - chiamate_iniziali) if llm is not None else 0
    return EsitoPipeline(modalita=modalita, query_usate=query, candidati=candidati[:top_k], note=note,
                         ripieghi=ripieghi, chiamate_llm=chiamate, esclusi_soglia=esclusi)
