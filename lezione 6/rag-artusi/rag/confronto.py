"""Confronto delle modalità di ricerca (lezione 8, es. 3): stesse domande, stesso indice, stesso k,
temperatura 0; cambia un solo fattore alla volta (la modalità).

Uso (da lezione 6/rag-artusi):
    python -m rag.confronto --domande eval/domande_l8.yaml --k 5 --uscita docs/confronto-l8.md

Chiama la pipeline direttamente (stesso codice del server MCP, senza il trasporto).
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import yaml

from rag.config import MODALITA, Config, ErroreConfigurazione, carica_config
from rag.embedder import EmbedderLMStudio, ErroreEmbedding
from rag.indice import ErroreCollezione
from rag.ingestion import ERRORI_QDRANT
from rag.llm import LLMLMStudio
from rag.pipeline import EsitoPipeline, esegui

TIPI = ("semplice", "composta", "senza_risposta")
TRATTINO = "—"


@dataclass(frozen=True)
class DomandaL8:
    testo: str
    tipo: str
    attese: tuple[int, ...]
    parti: tuple[tuple[int, ...], ...]
    verificare: bool
    nota: str | None


@dataclass
class Misura:
    domanda: str
    tipo: str
    attese: list[int]
    ricette: list[int]  # numeri delle ricette restituite, in ordine
    ids: list[str]
    posizione: int | None  # rango (da 1) del primo passaggio di una fonte attesa
    parti_coperte: int
    parti_totali: int
    astenuta: bool  # nessun passaggio restituito
    chiamate_llm: int
    latenza_ms: float
    ripieghi: list[str] = field(default_factory=list)
    query_usate: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    fasce: list[str] = field(default_factory=list)


def carica_domande_l8(percorso: Path) -> list[DomandaL8]:
    dati = yaml.safe_load(Path(percorso).read_text(encoding="utf-8")) or []
    domande = []
    for i, voce in enumerate(dati, start=1):
        if not isinstance(voce, dict) or "domanda" not in voce or "attese" not in voce:
            raise ValueError(f"Voce {i} di {percorso}: servono 'domanda' e 'attese'")
        tipo = voce.get("tipo", "semplice")
        if tipo not in TIPI:
            raise ValueError(f"Voce {i} di {percorso}: tipo {tipo!r} non valido ({', '.join(TIPI)})")
        parti = tuple(tuple(int(n) for n in p) for p in voce.get("parti") or [])
        if tipo == "composta" and len(parti) < 2:
            raise ValueError(f"Voce {i} di {percorso}: una domanda composta richiede almeno due 'parti'")
        attese = tuple(int(n) for n in voce["attese"] or [])
        if tipo == "senza_risposta" and attese:
            raise ValueError(f"Voce {i} di {percorso}: una domanda senza risposta non ha 'attese'")
        domande.append(DomandaL8(str(voce["domanda"]), tipo, attese, parti, bool(voce.get("verificare")),
                                 voce.get("nota")))
    return domande


def misura(d: DomandaL8, esito: EsitoPipeline, latenza_ms: float) -> Misura:
    ricette = [c.risultato.numero for c in esito.candidati]
    posizione = next((i for i, n in enumerate(ricette, start=1) if n in d.attese), None)
    coperte = sum(1 for parte in d.parti if any(n in parte for n in ricette))
    return Misura(domanda=d.testo, tipo=d.tipo, attese=list(d.attese), ricette=ricette,
                  ids=[c.id for c in esito.candidati], posizione=posizione, parti_coperte=coperte,
                  parti_totali=len(d.parti), astenuta=not esito.candidati, chiamate_llm=esito.chiamate_llm,
                  latenza_ms=round(latenza_ms, 1), ripieghi=[r.codice for r in esito.ripieghi],
                  query_usate=list(esito.query_usate), scores=[round(c.score, 3) for c in esito.candidati],
                  fasce=[c.fascia for c in esito.candidati])


def metriche(misure: list[Misura]) -> dict:
    con_fonte = [m for m in misure if m.attese]
    senza = [m for m in misure if m.tipo == "senza_risposta"]
    latenze = [m.latenza_ms for m in misure] or [0.0]
    codici = Counter(c for m in misure for c in m.ripieghi)
    return {
        "fonte_nei_k": sum(1 for m in con_fonte if m.posizione is not None),
        "con_fonte": len(con_fonte),
        "mrr": sum(1 / m.posizione for m in con_fonte if m.posizione) / len(con_fonte) if con_fonte else 0.0,
        "parti_coperte": sum(m.parti_coperte for m in misure),
        "parti_totali": sum(m.parti_totali for m in misure),
        "astensioni_corrette": sum(1 for m in senza if m.astenuta),
        "senza_risposta": len(senza),
        "astensioni_errate": sum(1 for m in con_fonte if m.astenuta),
        "chiamate_llm": sum(m.chiamate_llm for m in misure),
        "latenza_media_ms": round(statistics.fmean(latenze), 1),
        "latenza_max_ms": max(latenze),
        "ripieghi": sum(codici.values()),
        "ripieghi_per_codice": dict(sorted(codici.items())),
    }


def _pos(p: int | None) -> str:
    return str(p) if p is not None else "assente"


def _confronta(b: Misura, a: Misura) -> tuple[int, str]:
    """(+1 migliorato, -1 peggiorato, 0 uguale) e la descrizione della variazione."""
    if b.tipo == "senza_risposta":
        if a.astenuta == b.astenuta:
            return 0, ""
        sn = lambda v: "sì" if v else "no"  # noqa: E731
        return (1 if a.astenuta else -1), f"astensione {sn(b.astenuta)} → {sn(a.astenuta)}"
    if b.tipo == "composta" and a.parti_coperte != b.parti_coperte:
        return ((1 if a.parti_coperte > b.parti_coperte else -1),
                f"parti {b.parti_coperte}/{b.parti_totali} → {a.parti_coperte}/{a.parti_totali}")
    pb, pa = b.posizione or 10**6, a.posizione or 10**6
    if pa == pb:
        return 0, ""
    return (1 if pa < pb else -1), f"posizione {_pos(b.posizione)} → {_pos(a.posizione)}"


ETICHETTE_TIPO = {"semplice": "semplice", "composta": "composta", "senza_risposta": "senza risposta"}


def variazioni(base: list[Misura], altra: list[Misura]) -> tuple[list[str], list[str]]:
    migliorati, peggiorati = [], []
    per_domanda = {m.domanda: m for m in base}
    for a in altra:
        segno, descrizione = _confronta(per_domanda[a.domanda], a)
        riga = f"«{a.domanda}» ({ETICHETTE_TIPO[a.tipo]}): {descrizione}"
        if segno > 0:
            migliorati.append(riga)
        elif segno < 0:
            peggiorati.append(riga)
    return migliorati, peggiorati


def tabella_metriche(per_config: dict[str, dict], k: int) -> str:
    righe = [f"| Configurazione | Fonte nei primi {k} | MRR | Copertura composte | Astensioni corrette "
             "| Astensioni errate | Chiamate LLM | Latenza media (ms) | Latenza max (ms) | Ripieghi |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for nome, m in per_config.items():
        ripieghi = str(m["ripieghi"])
        if m["ripieghi_per_codice"]:
            ripieghi += " (" + ", ".join(f"{c} {n}" for c, n in m["ripieghi_per_codice"].items()) + ")"
        righe.append(f"| {nome} | {m['fonte_nei_k']}/{m['con_fonte']} | {m['mrr']:.3f} | "
                     f"{m['parti_coperte']}/{m['parti_totali']} | {m['astensioni_corrette']}/{m['senza_risposta']} | "
                     f"{m['astensioni_errate']} | {m['chiamate_llm']} | {m['latenza_media_ms']:.0f} | "
                     f"{m['latenza_max_ms']:.0f} | {ripieghi} |")
    return "\n".join(righe) + "\n"


def _dettaglio(per_config: dict[str, list[Misura]]) -> str:
    nomi = list(per_config)
    righe = ["| Domanda | Tipo | Attese | " + " | ".join(nomi) + " |", "|---|---|---|" + "---|" * len(nomi)]
    for i, m in enumerate(per_config[nomi[0]]):
        celle = []
        for nome in nomi:
            x = per_config[nome][i]
            if x.astenuta:
                cella = "astenuta"
            elif x.tipo == "composta":
                cella = f"pos {_pos(x.posizione)}, parti {x.parti_coperte}/{x.parti_totali}"
            elif x.tipo == "senza_risposta":
                cella = f"{len(x.ids)} passaggi"
            else:
                cella = f"pos {_pos(x.posizione)}"
            if x.ripieghi:
                cella += " · ripieghi: " + ", ".join(x.ripieghi)
            celle.append(cella)
        attese = ", ".join(map(str, m.attese)) or "nessuna"
        righe.append(f"| {m.domanda} | {ETICHETTE_TIPO[m.tipo]} | {attese} | " + " | ".join(celle) + " |")
    return "\n".join(righe) + "\n"


def rapporto(per_config: dict[str, list[Misura]], k: int, intestazione: str) -> str:
    tabella = tabella_metriche({n: metriche(m) for n, m in per_config.items()}, k)
    parti = [f"# Confronto delle modalità di ricerca (lezione 8)\n\n{intestazione}\n\n## Tabella riassuntiva\n\n",
             tabella, "\n## Casi migliorati e peggiorati rispetto a base\n"]
    base = per_config.get("base")
    for nome, misure in per_config.items():
        if nome == "base" or base is None:
            continue
        migliorati, peggiorati = variazioni(base, misure)
        parti.append(f"\n### {nome}\n\nMigliorati ({len(migliorati)}):\n\n"
                     + ("\n".join(f"- {r}" for r in migliorati) or "- nessuno")
                     + f"\n\nPeggiorati ({len(peggiorati)}):\n\n"
                     + ("\n".join(f"- {r}" for r in peggiorati) or "- nessuno") + "\n")
    parti.append("\n## Misura dettagliata per domanda\n\n" + _dettaglio(per_config))
    return "".join(parti)


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "sconosciuto"


def intestazione(config: Config, args, n_domande: int) -> str:
    return (f"- Data: {date.today().isoformat()} · commit `{_commit()}`\n"
            f"- Comando: `.\\.venv\\Scripts\\python.exe -m rag.confronto --domande {args.domande.as_posix()} "
            f"--k {args.k} --uscita {args.uscita.as_posix()}`\n"
            f"- Indice: collezione `{config.collezione}`, embedding `{config.modello_embedding}` · "
            f"LLM `{config.modello_chat}`, temperatura {config.llm_temperatura}, seed {config.llm_seed}, "
            f"reasoning_effort {config.llm_reasoning_effort}\n"
            f"- k = {args.k} · candidati per query {config.candidati_per_query} · reranking su al più "
            f"{config.rerank_max_candidati} candidati da {config.rerank_max_caratteri} caratteri · RRF_K {config.rrf_k} · "
            f"{n_domande} domande da `{args.domande.as_posix()}`\n"
            f"- Un solo fattore cambia fra le configurazioni: la modalità (soglie disattivate). Latenza = tempo della pipeline "
            f"(embedding, Qdrant, LLM) per domanda.")


def esegui_confronto(domande: list[DomandaL8], configurazioni: list[str], k: int, esegui_fn) -> dict[str, list[Misura]]:
    per_config: dict[str, list[Misura]] = {}
    for nome in configurazioni:
        misure = []
        for d in domande:
            inizio = time.perf_counter()
            esito = esegui_fn(d.testo, k, nome)
            misure.append(misura(d, esito, (time.perf_counter() - inizio) * 1000))
            print(f"  {nome}: {d.testo[:60]} → {misure[-1].ids}", file=sys.stderr, flush=True)
        per_config[nome] = misure
    return per_config


def crea_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rag.confronto")
    parser.add_argument("--domande", type=Path, default=Path("eval/domande_l8.yaml"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--uscita", type=Path, default=Path("docs/confronto-l8.md"))
    parser.add_argument("--configurazioni", nargs="+", choices=MODALITA, default=list(MODALITA))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = crea_parser().parse_args(argv)
    from qdrant_client import QdrantClient
    config = None
    try:
        config = carica_config()
        domande = carica_domande_l8(args.domande)
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        llm = LLMLMStudio(config)
        per_config = esegui_confronto(
            domande, args.configurazioni, args.k,
            lambda testo, k, modalita: esegui(testo, k, None, client=client, embedder=embedder, llm=llm,
                                              config=config, modalita=modalita, soglie=None))
    except (ValueError, OSError, ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({type(e).__name__})", file=sys.stderr)
        return 1
    testo = rapporto(per_config, args.k, intestazione(config, args, len(domande)))
    args.uscita.parent.mkdir(parents=True, exist_ok=True)
    args.uscita.write_text(testo, encoding="utf-8")
    args.uscita.with_suffix(".json").write_text(
        json.dumps({n: [asdict(m) for m in ms] for n, ms in per_config.items()}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(testo)
    print(f"Salvato in {args.uscita} e {args.uscita.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
