"""Calibrazione delle soglie (lezione 8, es. 4): score reali dei primi passaggi per domande CON e
SENZA risposta, misurati due volte (con la domanda intera e con la query che il modello passa a
search_documents), poi confronto con/senza soglie sulle stesse domande dell'esercizio 3.

Uso (da lezione 6/rag-artusi):
    python -m rag.calibrazione --domande eval/domande_l8.yaml --k 5 [--alta 0.6 --bassa 0.3]
                               [--configurazioni base entrambe] --uscita docs/calibrazione-l8.md

Lo script non sceglie le soglie: misura e stampa i numeri su cui sceglierle.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path

from rag.config import MODALITA, ErroreConfigurazione, carica_config
from rag.confronto import DomandaL8, Misura, _commit, carica_domande_l8, esegui_confronto, metriche
from rag.embedder import EmbedderLMStudio, ErroreEmbedding
from rag.indice import ErroreCollezione
from rag.ingestion import ERRORI_QDRANT
from rag.llm import ErroreLLM, LLMLMStudio, RispostaNonValida
from rag.pipeline import EsitoPipeline, esegui

TRATTINO = "—"

# Per la query «formulata dal modello»: stessa descrizione e stesso schema che l'agente riceve
# dalla discovery MCP (un test controlla che lo schema coincida con quello del server).
SCHEMA_RICERCA = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "top_k": {"default": 5, "type": "integer"},
                   "filtro": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}},
    "required": ["query"],
}
SISTEMA_QUERY = (
    "Sei un assistente. Quando una domanda riguarda ricette o cucina del libro dell'Artusi usa lo "
    "strumento di ricerca, non inventare. Rispondi nella lingua dell'utente."
)


def strumento_ricerca() -> dict:
    from rag.server_mcp import DESCRIZIONE_TOOL, NOME_TOOL
    return {"name": NOME_TOOL, "description": DESCRIZIONE_TOOL, "parameters": SCHEMA_RICERCA}


def query_del_modello(llm, domanda: str) -> tuple[str | None, str]:
    """La query che il modello chat passa a search_documents per `domanda` (tool calling, temperatura
    della configurazione). (None, motivo) se non chiama lo strumento o la risposta non è usabile."""
    try:
        argomenti = llm.argomenti_strumento(SISTEMA_QUERY, domanda, strumento_ricerca())
    except (ErroreLLM, RispostaNonValida) as e:
        return None, f"errore: {e}"
    query = (argomenti or {}).get("query")
    if not isinstance(query, str) or not query.strip():
        return None, "il modello non ha chiamato la ricerca"
    return " ".join(query.split()), ""


def stat(valori: list[float]) -> tuple[float | None, float | None, float | None]:
    if not valori:
        return None, None, None
    return round(min(valori), 3), round(statistics.median(valori), 3), round(max(valori), 3)


def riga_score(d: DomandaL8, esito: EsitoPipeline) -> dict:
    scores = [round(c.score, 3) for c in esito.candidati]
    posizione = next((i for i, c in enumerate(esito.candidati, start=1) if c.risultato.numero in d.attese), None)
    return {"domanda": d.testo, "tipo": d.tipo, "attese": list(d.attese), "scores": scores,
            "ids": [c.id for c in esito.candidati], "top1": scores[0] if scores else None,
            "posizione_fonte": posizione, "score_fonte": scores[posizione - 1] if posizione else None}


def riepilogo(righe: list[dict]) -> dict:
    con = [r for r in righe if r["attese"]]
    senza = [r for r in righe if r["tipo"] == "senza_risposta"]
    top1_con = [r["top1"] for r in con if r["top1"] is not None]
    top1_senza = [r["top1"] for r in senza if r["top1"] is not None]
    max_senza = max(top1_senza) if top1_senza else None
    return {
        "con_risposta_top1": stat(top1_con),
        "fonte_attesa": stat([r["score_fonte"] for r in con if r["score_fonte"] is not None]),
        "senza_risposta_top1": stat(top1_senza),
        "con_risposta_sotto_max_senza": sum(1 for s in top1_con if max_senza is not None and s < max_senza),
        "sovrapposti": bool(top1_con and top1_senza and min(top1_con) <= max(top1_senza)),
    }


def _f(x) -> str:
    return f"{x:.3f}" if x is not None else TRATTINO


def tabella_score(righe: list[dict], k: int) -> str:
    con_query = any("query" in r for r in righe)
    linee = [f"| Domanda |{' Query del modello |' if con_query else ''} Tipo | Top-1 | Score dei primi {k} | "
             "Score della fonte attesa |", "|---|" + ("---|" if con_query else "") + "---|---|---|---|"]
    for r in righe:
        if r["score_fonte"] is not None:
            fonte = f"{_f(r['score_fonte'])} (pos {r['posizione_fonte']})"
        else:
            fonte = "nessuna fonte" if not r["attese"] else f"non nei primi {k}"
        query = f" {r.get('query') or r.get('motivo') or TRATTINO} |" if con_query else ""
        linee.append(f"| {r['domanda']} |{query} {r['tipo'].replace('_', ' ')} | {_f(r['top1'])} | "
                     f"{', '.join(_f(s) for s in r['scores']) or TRATTINO} | {fonte} |")
    return "\n".join(linee) + "\n"


GRUPPI = (("Con risposta: top-1", "con_risposta_top1"), ("Con risposta: fonte attesa", "fonte_attesa"),
          ("Senza risposta: top-1", "senza_risposta_top1"))


def tabella_riepilogo(s: dict) -> str:
    linee = ["| Gruppo | Min | Mediana | Max |", "|---|---|---|---|"]
    for etichetta, chiave in GRUPPI:
        linee.append(f"| {etichetta} | " + " | ".join(_f(x) for x in s[chiave]) + " |")
    linee.append("")
    linee.append(f"- Intervalli del top-1 sovrapposti: **{'sì' if s['sovrapposti'] else 'no'}**; domande con "
                 f"risposta il cui top-1 è sotto il top-1 più alto delle domande senza risposta: "
                 f"**{s['con_risposta_sotto_max_senza']}**.")
    return "\n".join(linee) + "\n"


def tabella_due_riepiloghi(intera: dict, modello: dict) -> str:
    """Min / mediana / max affiancati: domanda intera e query formulata dal modello."""
    linee = ["| Gruppo | Domanda intera (min · mediana · max) | Query del modello (min · mediana · max) |",
             "|---|---|---|"]
    for etichetta, chiave in GRUPPI:
        linee.append(f"| {etichetta} | {' · '.join(_f(x) for x in intera[chiave])} | "
                     f"{' · '.join(_f(x) for x in modello[chiave])} |")
    linee.append("")
    for nome, s in (("domanda intera", intera), ("query del modello", modello)):
        linee.append(f"- {nome}: intervalli del top-1 sovrapposti **{'sì' if s['sovrapposti'] else 'no'}**; "
                     f"domande con risposta sotto il top-1 più alto delle senza risposta: "
                     f"**{s['con_risposta_sotto_max_senza']}**")
    return "\n".join(linee) + "\n"


def confronto_soglie(per_variante: dict[str, list[Misura]], k: int) -> str:
    linee = [f"| Variante | Fonte nei primi {k} | Astensioni corrette | Astensioni errate | Fasce restituite |",
             "|---|---|---|---|---|"]
    for nome, misure in per_variante.items():
        m = metriche(misure)
        fasce = Counter(f for x in misure for f in x.fasce)
        testo_fasce = ", ".join(f"{f} {n}" for f, n in sorted(fasce.items())) or "nessun passaggio"
        linee.append(f"| {nome} | {m['fonte_nei_k']}/{m['con_fonte']} | "
                     f"{m['astensioni_corrette']}/{m['senza_risposta']} | {m['astensioni_errate']} | {testo_fasce} |")
    return "\n".join(linee) + "\n"


def crea_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rag.calibrazione")
    parser.add_argument("--domande", type=Path, default=Path("eval/domande_l8.yaml"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--alta", type=float, default=None, help="soglia alta da provare (default: .env)")
    parser.add_argument("--bassa", type=float, default=None, help="soglia bassa da provare (default: .env)")
    parser.add_argument("--configurazioni", nargs="+", choices=MODALITA, default=["base", "entrambe"])
    parser.add_argument("--uscita", type=Path, default=Path("docs/calibrazione-l8.md"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = crea_parser().parse_args(argv)
    from qdrant_client import QdrantClient
    config = None
    try:
        config = carica_config()
        alta = config.soglia_alta if args.alta is None else args.alta
        bassa = config.soglia_bassa if args.bassa is None else args.bassa
        if not 0 <= bassa <= alta <= 1:
            raise ValueError(f"soglie non valide: bassa {bassa}, alta {alta} (serve 0 <= bassa <= alta <= 1)")
        domande = carica_domande_l8(args.domande)
        client = QdrantClient(url=config.qdrant_url)
        embedder = EmbedderLMStudio(config.lmstudio_url, config.modello_embedding, config.embedding_batch)
        llm = LLMLMStudio(config)

        def base(testo, soglie=None):
            return esegui(testo, args.k, None, client=client, embedder=embedder, llm=llm, config=config,
                          modalita="base", soglie=soglie)

        def esegui_con(soglie, traduci=lambda testo: testo):
            return lambda testo, k, modalita: esegui(traduci(testo), k, None, client=client, embedder=embedder,
                                                     llm=llm, config=config, modalita=modalita, soglie=soglie)

        # 1. score con la domanda intera
        righe = [riga_score(d, base(d.testo)) for d in domande]
        # 2. score con la query che il modello passa a search_documents (tool calling)
        query_modello: dict[str, str | None] = {}
        righe_modello = []
        for d in domande:
            query, motivo = query_del_modello(llm, d.testo)
            query_modello[d.testo] = query
            print(f"  query del modello: {d.testo[:50]} → {query or motivo}", file=sys.stderr, flush=True)
            riga = riga_score(d, base(query)) if query else riga_score(d, EsitoPipeline("base", [], []))
            riga.update(query=query, motivo=motivo)
            righe_modello.append(riga)
        # 3. confronto con/senza soglie
        per_variante: dict[str, list[Misura]] = {}
        for nome in args.configurazioni:
            per_variante[f"{nome} senza soglie"] = esegui_confronto(domande, [nome], args.k, esegui_con(None))[nome]
            per_variante[f"{nome} con soglie"] = esegui_confronto(domande, [nome], args.k,
                                                                   esegui_con((alta, bassa)))[nome]
        # la query del modello sostituisce la domanda (se non ha chiamato la ricerca: domanda intera)
        traduci = lambda testo: query_modello.get(testo) or testo  # noqa: E731
        per_variante["base, query del modello, senza soglie"] = esegui_confronto(
            domande, ["base"], args.k, esegui_con(None, traduci))["base"]
        per_variante["base, query del modello, con soglie"] = esegui_confronto(
            domande, ["base"], args.k, esegui_con((alta, bassa), traduci))["base"]
    except (ValueError, OSError, ErroreConfigurazione, ErroreCollezione, ErroreEmbedding) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    except ERRORI_QDRANT as e:
        print(f"Errore: Qdrant non raggiungibile su {config.qdrant_url} ({type(e).__name__})", file=sys.stderr)
        return 1
    s, s_modello = riepilogo(righe), riepilogo(righe_modello)
    senza_chiamata = sum(1 for q in query_modello.values() if not q)
    testo = (f"# Calibrazione delle soglie (lezione 8)\n\n"
             f"- Data: {date.today().isoformat()} · commit `{_commit()}`\n"
             f"- Comando: `.\\.venv\\Scripts\\python.exe -m rag.calibrazione --domande {args.domande.as_posix()} "
             f"--k {args.k} --alta {alta} --bassa {bassa} --configurazioni {' '.join(args.configurazioni)} "
             f"--uscita {args.uscita.as_posix()}`\n"
             f"- Score = similarità coseno (`{config.modello_embedding}`, collezione `{config.collezione}`), "
             f"modalità base, soglie disattivate, k = {args.k}\n"
             f"- Query del modello: `{config.modello_chat}` con tool calling (descrizione e schema di "
             f"search_documents, temperatura {config.llm_temperatura}, seed {config.llm_seed}); domande in cui "
             f"non ha chiamato la ricerca: {senza_chiamata}\n\n"
             f"## Riepilogo: domanda intera e query del modello\n\n{tabella_due_riepiloghi(s, s_modello)}\n"
             f"## Score con la domanda intera\n\n{tabella_score(righe, args.k)}\n"
             f"## Score con la query formulata dal modello\n\n{tabella_score(righe_modello, args.k)}\n"
             f"## Confronto con/senza soglie (alta {alta}, bassa {bassa})\n\n{confronto_soglie(per_variante, args.k)}")
    args.uscita.parent.mkdir(parents=True, exist_ok=True)
    args.uscita.write_text(testo, encoding="utf-8")
    args.uscita.with_suffix(".json").write_text(json.dumps(
        {"soglie": {"alta": alta, "bassa": bassa}, "score_domanda_intera": righe,
         "score_query_modello": righe_modello, "riepilogo_domanda_intera": s, "riepilogo_query_modello": s_modello,
         "confronto": {n: [asdict(m) for m in ms] for n, ms in per_variante.items()}},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(testo)
    print(f"Salvato in {args.uscita} e {args.uscita.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
