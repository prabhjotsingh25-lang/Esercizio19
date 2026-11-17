"""Valutazione del retrieval su un insieme di domande con fonte attesa.

Uso: python -m rag.valutazione [--domande eval/domande.yaml] [--k 5] [--uscita docs/eval-baseline.md]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from qdrant_client import QdrantClient

from rag.config import ErroreConfigurazione, carica_config
from rag.embedder import EmbedderLMStudio, ErroreEmbedding
from rag.indice import ErroreCollezione
from rag.ingestion import ERRORI_QDRANT
from rag.ricerca import Risultato, cerca

TRATTINO = "—"


@dataclass(frozen=True)
class Domanda:
    testo: str
    attese: tuple[int, ...]
    nota: str | None = None


@dataclass(frozen=True)
class Riga:
    domanda: str
    attese: tuple[int, ...]
    posizione: int | None
    score_migliore: float | None
    primo: str


def carica_domande(percorso: Path) -> list[Domanda]:
    dati = yaml.safe_load(Path(percorso).read_text(encoding="utf-8")) or []
    domande = []
    for i, voce in enumerate(dati, start=1):
        if not isinstance(voce, dict) or "domanda" not in voce or "attese" not in voce:
            raise ValueError(f"Voce {i} di {percorso}: servono 'domanda' e 'attese'")
        domande.append(
            Domanda(str(voce["domanda"]), tuple(int(n) for n in voce["attese"] or []), voce.get("nota"))
        )
    return domande


def note_markdown(domande: list[Domanda]) -> str:
    note = [f"- «{d.testo}»: {d.nota}" for d in domande if d.nota]
    return "\n## Note\n\n" + "\n".join(note) + "\n" if note else ""


def valuta(
    domande: list[Domanda], cerca_fn: Callable[[str, int], list[Risultato]], k: int = 5
) -> list[Riga]:
    righe = []
    for d in domande:
        risultati = cerca_fn(d.testo, k)
        posizione = next((i for i, r in enumerate(risultati, start=1) if r.numero in d.attese), None)
        primo = risultati[0] if risultati else None
        righe.append(
            Riga(
                domanda=d.testo,
                attese=d.attese,
                posizione=posizione,
                score_migliore=primo.score if primo else None,
                primo=f"Ricetta {primo.numero} {TRATTINO} {primo.titolo}" if primo else TRATTINO,
            )
        )
    return righe


def tabella_markdown(righe: list[Riga]) -> str:
    linee = [
        "| Domanda | Fonte attesa | Posizione | Score migliore | Primo risultato |",
        "|---|---|---|---|---|",
    ]
    for r in righe:
        attese = ", ".join(map(str, r.attese)) if r.attese else "nessuna"
        posizione = str(r.posizione) if r.posizione is not None else TRATTINO
        score = f"{r.score_migliore:.3f}" if r.score_migliore is not None else TRATTINO
        linee.append(f"| {r.domanda} | {attese} | {posizione} | {score} | {r.primo} |")
    return "\n".join(linee) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag.valutazione")
    parser.add_argument("--domande", type=Path, default=Path("eval/domande.yaml"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--uscita", type=Path, default=Path("docs/eval-baseline.md"))
    parser.add_argument("--titolo", default="Valutazione")
    args = parser.parse_args(argv)

    config = None
    try:
        config = carica_config()
        domande = carica_domande(args.domande)
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        righe = valuta(
            domande, lambda testo, k: cerca(testo, k, client=client, embedder=embedder, config=config), args.k
        )
    except (ValueError, ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({e})", file=sys.stderr)
        return 1

    tabella = tabella_markdown(righe) + note_markdown(domande)
    trovate = sum(1 for r in righe if r.posizione is not None)
    con_fonte = sum(1 for r in righe if r.attese)
    intestazione = (
        f"# {args.titolo}\n\n"
        f"- Data: {date.today().isoformat()}\n"
        f"- Modello: `{config.modello_embedding}` · collezione `{config.collezione}`\n"
        f"- Chunking: {config.chunk_strategia}, {config.chunk_dimensione} caratteri, overlap {config.chunk_overlap}\n"
        f"- k = {args.k} · fonte trovata nei primi {args.k}: {trovate}/{con_fonte}\n\n"
    )
    args.uscita.parent.mkdir(parents=True, exist_ok=True)
    args.uscita.write_text(intestazione + tabella, encoding="utf-8")
    print(intestazione + tabella)
    print(f"Salvata in {args.uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
