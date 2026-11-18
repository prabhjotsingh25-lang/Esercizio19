"""Prove reali della lezione 8: quattro casi eseguiti dall'agente vero e salvati come tracce.

Uso: python -m assistente.prove_rag --uscita CARTELLA [--casi documentale ora ...]

Servono LM Studio, Qdrant e `SERVER_MCP_FILE` nel `.env`. Lo script non giudica la qualità della
risposta: registra il percorso (strumenti, argomenti, risultati, log, citazioni) e segnala gli
scostamenti dal comportamento atteso, perché il modello non è deterministico.
"""
import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from assistente.server_esterni import LOG_STDIO

RICERCA = "search_documents"


@dataclass(frozen=True)
class Caso:
    nome: str
    domanda: str
    attesa: str  # descrizione leggibile
    ricerca: bool  # la ricerca deve (True) o non deve (False) essere chiamata
    strumenti_richiesti: tuple[str, ...] = ()
    nessuno_strumento: bool = False
    citazioni: str = "qualsiasi"  # "verificate": almeno una e nessuna sconosciuta; "nessuna"
    da_verificare: bool | None = None  # es. 4: la risposta deve (True) / non deve (False) dire «da verificare»


CASI = (
    Caso("documentale", "Quanta farina serve per 400 grammi di patate negli gnocchi?",
         "ricerca chiamata, citazioni tutte verificate", ricerca=True, citazioni="verificate"),
    Caso("ora", "Che ore sono a Tokyo?", "orologio, non ricerca", ricerca=False,
         strumenti_richiesti=("ora_corrente",)),
    Caso("generica", "Ciao! Cosa sai fare?", "nessuno strumento", ricerca=False, nessuno_strumento=True),
    Caso("senza_risposta", "Qual è la ricetta del tiramisù?",
         "ricerca chiamata, astensione, nessuna citazione", ricerca=True, citazioni="nessuna"),
)


# Es. 4: tre casi per le fasce di confidenza (domande scelte dopo la calibrazione, vedi
# docs/rag-agente.md). Si eseguono con --serie soglie.
CASI_SOGLIE = (
    Caso("affidabile", "Che vino si usa per il pollo alla cacciatora?",
         "ricerca, passaggi affidabili, citazioni verificate, nessun «da verificare»", ricerca=True,
         citazioni="verificate", da_verificare=False),
    Caso("da_verificare", "Come si fa un dolce di mandorle e zucchero?",
         "ricerca, passaggi di fascia media, risposta segnata «da verificare sulla fonte»", ricerca=True,
         citazioni="verificate", da_verificare=True),
    Caso("senza_risposta_soglie", "Come si prepara il sushi?",
         "ricerca con lista vuota (sotto la soglia), astensione, nessuna citazione", ricerca=True,
         citazioni="nessuna"),
)
SERIE = {"base": CASI, "soglie": CASI_SOGLIE}


def valuta_caso(caso: Caso, nomi_strumenti: list[str], verificate: list[str], sconosciute: list[str],
                risposta: str = "") -> list[str]:
    """Scostamenti dal comportamento atteso (lista vuota = atteso)."""
    scostamenti = []
    dice_verificare = "da verificare" in risposta.lower()
    if caso.da_verificare is True and not dice_verificare:
        scostamenti.append("la risposta non dice «da verificare»")
    if caso.da_verificare is False and dice_verificare:
        scostamenti.append("la risposta dice «da verificare» ma i passaggi erano affidabili")
    if caso.ricerca and RICERCA not in nomi_strumenti:
        scostamenti.append("la ricerca non è stata chiamata")
    if not caso.ricerca and RICERCA in nomi_strumenti:
        scostamenti.append("la ricerca è stata chiamata ma non doveva")
    for nome in caso.strumenti_richiesti:
        if nome not in nomi_strumenti:
            scostamenti.append(f"lo strumento {nome} non è stato chiamato")
    if caso.nessuno_strumento and nomi_strumenti:
        scostamenti.append(f"strumenti chiamati: {', '.join(nomi_strumenti)}")
    if caso.citazioni == "verificate" and not verificate:
        scostamenti.append("nessuna citazione verificata")
    if caso.citazioni == "nessuna" and (verificate or sconosciute):
        scostamenti.append(f"citazioni presenti: {', '.join(verificate + sconosciute)}")
    if sconosciute:
        scostamenti.append(f"citazioni sconosciute: {', '.join(sconosciute)}")
    return scostamenti


def _risultato_leggibile(testo: str):
    try:
        return json.loads(testo)
    except ValueError:
        return testo


def traccia(caso: Caso, esito, log: list[str], log_server: list[str], durata: float) -> dict:
    nomi = [s.nome for s in esito.strumenti]
    c = esito.citazioni
    scostamenti = valuta_caso(caso, nomi, c.verificate, c.sconosciute, esito.risposta)
    return {
        "caso": caso.nome, "domanda": caso.domanda, "atteso": caso.attesa,
        "esito": "atteso" if not scostamenti else "non atteso", "scostamenti": scostamenti,
        "durata_s": round(durata, 1),
        "strumenti": [{"nome": s.nome, "argomenti": s.argomenti, "risultato": _risultato_leggibile(s.risultato)}
                      for s in esito.strumenti],
        "risposta": esito.risposta,
        "citazioni": asdict(c),
        "log_agente": log, "log_server_ricerca": log_server,
    }


def _riassunto_risultato(r) -> str:
    if isinstance(r, dict) and "passaggi" in r:
        ids = ", ".join(f'{p["id"]} ({p["titolo"]}, {p["score"]}' + (f', {p["fascia"]}' if "fascia" in p else "") + ")"
                        for p in r["passaggi"]) or "nessuno"
        nota = f' · nota: {r["nota"]}' if r.get("nota") else ""
        return f'modalità {r.get("modalita")}, passaggi: {ids}{nota}'
    return str(r)[:300]


def markdown(tracce: list[dict], intestazione: str = "", titolo: str = "Lezione 8 · Es. 2 — tracce dei quattro casi") -> str:
    righe = [f"# {titolo}", "", intestazione, "",
             "| Caso | Domanda | Atteso | Strumenti | Citazioni verificate / sconosciute | Esito | Durata |",
             "|---|---|---|---|---|---|---|"]
    for t in tracce:
        c = t["citazioni"]
        righe.append(f'| {t["caso"]} | {t["domanda"]} | {t["atteso"]} | '
                     f'{", ".join(s["nome"] for s in t["strumenti"]) or "nessuno"} | '
                     f'{", ".join(c["verificate"]) or "-"} / {", ".join(c["sconosciute"]) or "-"} | '
                     f'**{t["esito"]}** | {t["durata_s"]} s |')
    for t in tracce:
        righe += ["", f'## {t["caso"]}: «{t["domanda"]}»', "",
                  f'- Atteso: {t["atteso"]} → **{t["esito"]}**'
                  + (f' ({"; ".join(t["scostamenti"])})' if t["scostamenti"] else "")]
        for s in t["strumenti"]:
            righe.append(f'- Strumento `{s["nome"]}` {json.dumps(s["argomenti"], ensure_ascii=False)} → '
                         f'{_riassunto_risultato(s["risultato"])}')
        if not t["strumenti"]:
            righe.append("- Nessuno strumento chiamato")
        righe += ["", "Risposta:", "", *[f"> {r}" for r in t["risposta"].splitlines() or [""]], "",
                  "Log dell'agente:", "", "```", *t["log_agente"], "```"]
        if t["log_server_ricerca"]:
            righe += ["", "Log del server di ricerca:", "", "```", *t["log_server_ricerca"], "```"]
    return "\n".join(righe) + "\n"


class _Raccoglitore(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.righe: list[str] = []

    def emit(self, record):
        self.righe.append(f"{record.levelname} {record.name} {record.getMessage()}")


def _righe_nuove(percorso: Path, inizio: int) -> list[str]:
    if not percorso.exists():
        return []
    with percorso.open("rb") as f:
        f.seek(inizio)
        testo = f.read().decode("utf-8", errors="replace")
    return [r for r in testo.splitlines() if "rag.server_mcp" in r or "Traceback" in r]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m assistente.prove_rag")
    parser.add_argument("--uscita", type=Path, required=True)
    parser.add_argument("--serie", choices=list(SERIE), default="base")
    parser.add_argument("--casi", nargs="*", default=None, help="sottoinsieme dei casi della serie")
    args = parser.parse_args(argv)
    casi = [c for c in SERIE[args.serie] if args.casi is None or c.nome in args.casi]
    from dotenv import load_dotenv

    from assistente.agente import Agente, grafo_da_configurazione
    from assistente.cli import configura_log
    from assistente.config import ErroreConfigurazione, carica_configurazione
    from assistente.server_esterni import ErroreServerMCP
    from assistente.varianti import lettore_preferenze
    load_dotenv(".env", override=False)
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        config = carica_configurazione()
        if not config.server_mcp_file:
            raise ErroreConfigurazione("SERVER_MCP_FILE non impostata: la ricerca non sarebbe disponibile")
        configura_log(config)
        agente = Agente(grafo_da_configurazione(config), config.max_passaggi, config.max_revisioni)
    except (ErroreConfigurazione, ErroreServerMCP) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 2
    preferenze = lettore_preferenze(config)()
    raccoglitore = _Raccoglitore()
    logging.getLogger("assistente").addHandler(raccoglitore)
    args.uscita.mkdir(parents=True, exist_ok=True)
    tracce = []
    for caso in casi:
        raccoglitore.righe = []
        inizio_log = LOG_STDIO.stat().st_size if LOG_STDIO.exists() else 0
        print(f"caso {caso.nome}: {caso.domanda}", flush=True)
        partenza = time.perf_counter()
        esito = agente.messaggio(caso.domanda, [], "", preferenze)
        t = traccia(caso, esito, list(raccoglitore.righe), _righe_nuove(LOG_STDIO, inizio_log),
                    time.perf_counter() - partenza)
        (args.uscita / f"{caso.nome}.json").write_text(json.dumps(t, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
        print(f'  -> {t["esito"]} {t["scostamenti"]} ({t["durata_s"]} s)', flush=True)
        tracce.append(t)
    intestazione = (f"- Data: {time.strftime('%Y-%m-%d %H:%M')} · modello `{config.modello}` · variante "
                    f"strumenti `{config.variante}` · server MCP da `{config.server_mcp_file}`\n"
                    f"- Comando (da `lezione 4/assistente-laboratorio`): "
                    f"`$env:PYTHONPATH = \"src\"; .\\.venv\\Scripts\\python.exe -m assistente.prove_rag "
                    f"--serie {args.serie} --uscita <cartella>`")
    titolo = ("Lezione 8 · Es. 4 — tracce con le soglie" if args.serie == "soglie"
              else "Lezione 8 · Es. 2 — tracce dei quattro casi")
    (args.uscita / "tracce.md").write_text(markdown(tracce, intestazione, titolo), encoding="utf-8")
    print(f"Tracce salvate in {args.uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
