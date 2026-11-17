"""Valutazione del retrieval su un insieme di domande con fonte attesa.

Uso: python -m rag.valutazione [--domande eval/domande.yaml] [--k 5] [--uscita docs/eval-baseline.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
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
    domande: list[Domanda],
    cerca_fn: Callable[..., list[Risultato]],
    k: int = 5,
    solo_dosi: bool = False,
) -> list[Riga]:
    righe = []
    for d in domande:
        risultati = cerca_fn(d.testo, k, solo_dosi=True) if solo_dosi else cerca_fn(d.testo, k)
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


def _fmt_posizione(p: int | None) -> str:
    return str(p) if p is not None else TRATTINO


def salva_json(righe: list[Riga], percorso: Path) -> None:
    dati = [{**asdict(r), "attese": list(r.attese)} for r in righe]
    Path(percorso).write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def righe_da_json(percorso: Path) -> list[Riga]:
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return [Riga(**{**d, "attese": tuple(d["attese"])}) for d in dati]


def variazione(prima: int | None, dopo: int | None) -> str:
    if prima == dopo:
        return "="
    if dopo is None:
        return "persa"
    if prima is None:
        return "trovata"
    return f"↑{prima - dopo}" if dopo < prima else f"↓{dopo - prima}"


def tabella_confronto(righe: list[Riga], base: list[Riga]) -> str:
    per_domanda = {b.domanda: b for b in base}
    mancanti = [r.domanda for r in righe if r.domanda not in per_domanda]
    if mancanti:
        raise ValueError(f"Domande assenti nel file di confronto: {mancanti}")
    linee = [
        "| Domanda | Fonte attesa | Posizione baseline | Posizione | Variazione | Score migliore |",
        "|---|---|---|---|---|---|",
    ]
    for r in righe:
        b = per_domanda[r.domanda]
        attese = ", ".join(map(str, r.attese)) if r.attese else "nessuna"
        score = f"{r.score_migliore:.3f}" if r.score_migliore is not None else TRATTINO
        linee.append(
            f"| {r.domanda} | {attese} | {_fmt_posizione(b.posizione)} | {_fmt_posizione(r.posizione)} "
            f"| {variazione(b.posizione, r.posizione)} | {score} |"
        )
    return "\n".join(linee) + "\n"


def totali(righe: list[Riga]) -> tuple[int, int, int]:
    """(fonte nei primi k, fonte al primo posto, domande con fonte attesa): calcolati, mai scritti a mano."""
    con_fonte = [r for r in righe if r.attese]
    return (
        sum(1 for r in con_fonte if r.posizione is not None),
        sum(1 for r in con_fonte if r.posizione == 1),
        len(con_fonte),
    )


def riga_totali(righe: list[Riga], k: int) -> str:
    trovate, primo, con_fonte = totali(righe)
    return f"fonte trovata nei primi {k}: {trovate}/{con_fonte} · al primo posto: {primo}/{con_fonte}"


def riepilogo_markdown(percorsi: list[Path]) -> str:
    linee = ["| Valutazione | Fonte nei primi k | Al primo posto |", "|---|---|---|"]
    for percorso in percorsi:
        trovate, primo, con_fonte = totali(righe_da_json(percorso))
        linee.append(f"| {Path(percorso).name} | {trovate}/{con_fonte} | {primo}/{con_fonte} |")
    return "\n".join(linee) + "\n"


def crea_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rag.valutazione")
    parser.add_argument("--domande", type=Path, default=Path("eval/domande.yaml"))
    parser.add_argument("--k", type=int, default=5)
    # mai la baseline come default: un'esecuzione di prova non deve sovrascrivere il rapporto di partenza
    parser.add_argument("--uscita", type=Path, default=Path("docs/eval-ultima.md"))
    parser.add_argument("--titolo", default="Valutazione")
    parser.add_argument("--solo-dosi", action="store_true", help="applica il filtro contiene_dosi a ogni domanda")
    parser.add_argument("--json", type=Path, default=None, help="salva anche le righe in JSON")
    parser.add_argument("--confronta", type=Path, default=None, help="JSON di una valutazione precedente")
    parser.add_argument(
        "--riepilogo", type=Path, nargs="+", default=None,
        help="stampa solo i totali dei JSON indicati (non servono Qdrant né LM Studio)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = crea_parser().parse_args(argv)
    if args.riepilogo:
        try:
            print(riepilogo_markdown(args.riepilogo), end="")
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"Errore: {e}", file=sys.stderr)
            return 1
        return 0

    config = None
    try:
        config = carica_config()
        domande = carica_domande(args.domande)
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        righe = valuta(
            domande,
            lambda testo, k, solo_dosi=False: cerca(
                testo, k, solo_dosi=solo_dosi, client=client, embedder=embedder, config=config
            ),
            args.k,
            solo_dosi=args.solo_dosi,
        )
        base = righe_da_json(args.confronta) if args.confronta else None
        tabella = tabella_confronto(righe, base) if base else tabella_markdown(righe)
    except (ValueError, OSError, ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({e})", file=sys.stderr)
        return 1

    tabella += note_markdown(domande)
    filtro = " · filtro: solo chunk con dosi" if args.solo_dosi else ""
    confronto = f" · confronto con `{args.confronta.as_posix()}`" if args.confronta else ""
    intestazione = (
        f"# {args.titolo}\n\n"
        f"- Data: {date.today().isoformat()}\n"
        f"- Modello: `{config.modello_embedding}` · collezione `{config.collezione}`\n"
        f"- Chunking: {config.chunk_strategia}, {config.chunk_dimensione} caratteri, overlap {config.chunk_overlap}\n"
        f"- k = {args.k}{filtro}{confronto} · {riga_totali(righe, args.k)}\n\n"
    )
    if args.json:
        salva_json(righe, args.json)
    args.uscita.parent.mkdir(parents=True, exist_ok=True)
    args.uscita.write_text(intestazione + tabella, encoding="utf-8")
    print(intestazione + tabella)
    print(f"Salvata in {args.uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
