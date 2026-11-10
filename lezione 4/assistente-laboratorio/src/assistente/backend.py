"""Back-end (FastAPI): conversazioni e messaggi in PostgreSQL, turni sincroni verso l'agente.

Avvio: python -m assistente.backend   (host e porta da BACKEND_HOST e BACKEND_PORTA)
Contratto: /docs, /openapi.json e la copia in docs/openapi-backend.json. Verso l'agente usa solo
i percorsi e i campi di docs/openapi-agente.json (tests/test_backend.py).

Errori dell'agente: la domanda resta salvata con stato «errore» e il motivo; nessuna risposta e
nessun cambio dello stato dell'agente. `POST /conversazioni/{id}/riprova` rimanda l'ultima domanda
in errore senza duplicarla. Prompt non valido (422): la domanda non resta salvata.
"""
import logging
import sys
import time
from datetime import datetime

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from assistente.archivio import Archivio, Conversazione, Messaggio
from assistente.cliente_agente import (
    ELENCO_PROMPT, MESSAGGI, PROMPT, STATO, ClienteAgente, ErroreAgente)
from assistente.preferenze import LettorePreferenze, Preferenze
from assistente.prompt import ErrorePrompt, PromptNonDisponibili

log = logging.getLogger("assistente.backend")

MAX_PAROLE_TITOLO = 6
MAX_CARATTERI_TITOLO = 60


def titolo_da(testo: str) -> str:
    """Prime parole della prima domanda (al massimo 6 parole e 60 caratteri), «…» se tagliato."""
    parole = testo.split()
    titolo = " ".join(parole[:MAX_PAROLE_TITOLO])
    tagliato = len(parole) > MAX_PAROLE_TITOLO
    if len(titolo) > MAX_CARATTERI_TITOLO - 1:
        titolo, tagliato = titolo[:MAX_CARATTERI_TITOLO - 1].rstrip(), True
    return titolo + ("…" if tagliato else "")


def _contesto(conv: Conversazione) -> dict:
    return {"cronologia": conv.cronologia_agente, "riassunto": conv.riassunto,
            "preferenze": conv.preferenze}


def corpo_messaggio(conv: Conversazione, testo: str) -> dict:
    """Corpo di POST /messaggi dell'agente (RichiestaMessaggio in docs/openapi-agente.json)."""
    return {"testo": testo, **_contesto(conv)}


def corpo_prompt(conv: Conversazione, nome: str, argomenti: dict) -> dict:
    """Corpo di POST /prompt dell'agente (RichiestaPrompt in docs/openapi-agente.json)."""
    return {"nome": nome, "argomenti": argomenti, **_contesto(conv)}


# --- Modelli dell'API del back-end (contratto per il front-end) ---

class MessaggioApi(BaseModel):
    id: int
    posizione: int
    ruolo: str = Field(description="utente oppure assistente")
    testo: str
    strumenti: list[dict] | None = Field(None, description="Risposte: strumenti usati.")
    prompt: dict | None = Field(None, description="Domande da /prompt: nome e argomenti.")
    stato: str | None = Field(None, description="Domande: in_attesa, risposta oppure errore.")
    errore: str | None = Field(None, description="Domande in errore: il motivo, da mostrare.")
    creato: datetime


class ConversazioneBreve(BaseModel):
    id: str
    titolo: str | None
    ultimo_messaggio: datetime = Field(description="Data dell'ultimo messaggio (o della creazione).")


class ConversazioneCompleta(ConversazioneBreve):
    preferenze: Preferenze
    turno_in_corso: bool
    messaggi: list[MessaggioApi]


class RichiestaNuova(BaseModel):
    preferenze: Preferenze | None = Field(
        None, description="Se mancano: lette una volta dalla fonte dell'host (resource o file).")


class RichiestaTesto(BaseModel):
    testo: str = Field(min_length=1)


class RichiestaPromptBackend(BaseModel):
    nome: str
    argomenti: dict[str, str] = Field(default_factory=dict)


class Turno(BaseModel):
    domanda: MessaggioApi
    risposta: MessaggioApi


class Errore(BaseModel):
    detail: str


ERRORI_TURNO = {
    404: {"model": Errore, "description": "Conversazione inesistente."},
    409: {"model": Errore, "description": "Un turno è già in corso (o niente da riprovare)."},
    422: {"model": Errore, "description": "Prompt non valido: la domanda non viene salvata."},
    502: {"model": Errore, "description": "Errore del server del modello (domanda salvata in errore)."},
    503: {"model": Errore, "description": "Agente, modello o strumenti non disponibili (domanda "
                                          "salvata in errore: si può riprovare)."},
    504: {"model": Errore, "description": "L'agente non ha risposto entro AGENTE_TIMEOUT (domanda "
                                          "salvata in errore: si può riprovare)."},
}


def _messaggio(m: Messaggio) -> dict:
    return {"id": m.id, "posizione": m.posizione, "ruolo": m.ruolo, "testo": m.testo,
            "strumenti": m.strumenti, "prompt": m.prompt, "stato": m.stato, "errore": m.errore,
            "creato": m.creato}


def crea_backend(archivio: Archivio, agente: ClienteAgente, leggi_preferenze: LettorePreferenze,
                 agente_url: str) -> FastAPI:
    """Back-end sopra un archivio e un client dell'agente (iniettabili per i test)."""
    app = FastAPI(title="Back-end dell'assistente di laboratorio", version="1.0.0",
                  description="Conversazioni salvate in PostgreSQL; ogni invio è sincrono e può "
                              "durare minuti (timeout alti nel chiamante).")

    def conversazione(id: str) -> Conversazione:
        conv = archivio.leggi(id)
        if conv is None:
            raise HTTPException(404, f"conversazione inesistente: {id}")
        return conv

    def turno(id: str, *, testo: str | None = None, prompt: dict | None = None,
              domanda: Messaggio | None = None) -> dict:
        """Salva la domanda (o riusa quella da riprovare), chiama l'agente, salva la risposta."""
        conv = conversazione(id)
        if not archivio.inizia_turno(id):
            raise HTTPException(409, "un turno è già in corso per questa conversazione")
        inizio = time.perf_counter()
        try:
            if domanda is None:
                visibile = testo if prompt is None else \
                    f"/prompt {prompt['nome']} " + " ".join(f'{k}="{v}"' for k, v in
                                                            prompt["argomenti"].items())
                domanda = archivio.aggiungi(id, "utente", visibile.strip(), prompt=prompt,
                                            stato="in_attesa")
            else:
                archivio.aggiorna_domanda(domanda.id, stato="in_attesa")

            def metti_titolo() -> None:  # solo se la domanda resta salvata (non con il 422)
                if conv.titolo is None:
                    p = domanda.prompt
                    archivio.imposta_titolo(id, titolo_da(
                        domanda.testo if p is None else
                        f"{p['nome']}: {' '.join(p['argomenti'].values())}"))
            try:
                if domanda.prompt is not None:
                    esito = agente.chiama(*PROMPT, json=corpo_prompt(
                        conv, domanda.prompt["nome"], domanda.prompt["argomenti"]))
                else:
                    esito = agente.chiama(*MESSAGGI, json=corpo_messaggio(conv, domanda.testo))
            except PromptNonDisponibili as errore:
                motivo = f"agente: prompt non disponibili: {errore}"
                archivio.aggiorna_domanda(domanda.id, stato="errore", errore=motivo)
                metti_titolo()
                raise HTTPException(503, motivo) from None
            except ErrorePrompt as errore:
                archivio.elimina_messaggio(domanda.id)  # input non valido: niente da riprovare
                raise HTTPException(422, f"prompt non valido: {errore}") from None
            except ErroreAgente as errore:
                archivio.aggiorna_domanda(domanda.id, stato="errore", errore=errore.dettaglio)
                metti_titolo()
                raise HTTPException(errore.codice, errore.dettaglio) from None
            metti_titolo()
            testo_domanda = "\n".join(esito.get("prompt") or []) or None
            archivio.aggiorna_domanda(domanda.id, stato="risposta", testo=testo_domanda)
            risposta = archivio.aggiungi(id, "assistente", esito["risposta"],
                                         strumenti=esito["strumenti"])
            archivio.salva_stato_agente(id, esito["cronologia"], esito["riassunto"])
            log.info("backend: turno %s -> 200 in %.1f s (strumenti: %s)", id,
                     time.perf_counter() - inizio,
                     ", ".join(s["nome"] for s in esito["strumenti"]) or "nessuno")
            aggiornata = next(m for m in archivio.messaggi(id) if m.id == domanda.id)
            return {"domanda": _messaggio(aggiornata), "risposta": _messaggio(risposta)}
        except HTTPException as errore:
            log.warning("backend: turno %s -> %d in %.1f s: %s", id, errore.status_code,
                        time.perf_counter() - inizio, errore.detail)
            raise
        finally:
            archivio.fine_turno(id)

    @app.post("/conversazioni", status_code=201, response_model=ConversazioneCompleta,
              summary="Nuova conversazione (preferenze dal corpo o lette dalla fonte dell'host)")
    def nuova(richiesta: RichiestaNuova | None = None) -> dict:
        preferenze = richiesta.preferenze if richiesta and richiesta.preferenze else leggi_preferenze()
        conv = archivio.crea(preferenze.model_dump())
        return completa(conv.id)

    @app.get("/conversazioni", response_model=list[ConversazioneBreve],
             summary="Elenco: titolo e data dell'ultimo messaggio, dal più recente")
    def elenco() -> list[dict]:
        return [{"id": c.id, "titolo": c.titolo, "ultimo_messaggio": c.aggiornata}
                for c in archivio.elenca()]

    @app.get("/conversazioni/{id}", response_model=ConversazioneCompleta,
             responses={404: ERRORI_TURNO[404]}, summary="Storico completo della conversazione")
    def completa(id: str) -> dict:
        conv = conversazione(id)
        return {"id": conv.id, "titolo": conv.titolo, "ultimo_messaggio": conv.aggiornata,
                "preferenze": conv.preferenze, "turno_in_corso": conv.turno_in_corso,
                "messaggi": [_messaggio(m) for m in archivio.messaggi(id)]}

    @app.delete("/conversazioni/{id}", status_code=204, responses={404: ERRORI_TURNO[404]})
    def elimina(id: str) -> Response:
        if not archivio.elimina(id):
            raise HTTPException(404, f"conversazione inesistente: {id}")
        return Response(status_code=204)

    @app.put("/conversazioni/{id}/preferenze", response_model=Preferenze,
             responses={404: ERRORI_TURNO[404]})
    def preferenze(id: str, nuove: Preferenze) -> dict:
        conversazione(id)
        archivio.aggiorna_preferenze(id, nuove.model_dump())
        return nuove.model_dump()

    @app.post("/conversazioni/{id}/messaggi", response_model=Turno, responses=ERRORI_TURNO,
              summary="Invio sincrono: salva la domanda, chiama l'agente, salva la risposta")
    def messaggi(id: str, richiesta: RichiestaTesto) -> dict:
        return turno(id, testo=richiesta.testo)

    @app.post("/conversazioni/{id}/prompt", response_model=Turno, responses=ERRORI_TURNO,
              summary="Usa un prompt (composto e controllato dall'agente)")
    def usa_prompt(id: str, richiesta: RichiestaPromptBackend) -> dict:
        return turno(id, prompt={"nome": richiesta.nome, "argomenti": richiesta.argomenti})

    @app.post("/conversazioni/{id}/riprova", response_model=Turno, responses=ERRORI_TURNO,
              summary="Rimanda l'ultima domanda in errore, senza duplicarla")
    def riprova(id: str) -> dict:
        conversazione(id)
        ultimi = archivio.messaggi(id)
        if not ultimi or ultimi[-1].ruolo != "utente" or ultimi[-1].stato != "errore":
            raise HTTPException(409, "nessuna domanda in errore da riprovare")
        return turno(id, domanda=ultimi[-1])

    @app.get("/prompt", summary="Elenco dei prompt (dall'agente)")
    def elenco_prompt() -> list[dict]:
        try:
            return agente.chiama(*ELENCO_PROMPT)
        except (ErroreAgente, PromptNonDisponibili) as errore:
            raise HTTPException(getattr(errore, "codice", 503),
                                getattr(errore, "dettaglio", str(errore))) from None

    @app.get("/stato", summary="Raggiungibilità di back-end, database e agente")
    def stato() -> JSONResponse:
        problema_db = archivio.ping()
        try:
            componenti, problema_agente = agente.chiama(*STATO), None
        except ErroreAgente as errore:
            componenti, problema_agente = None, errore.dettaglio
        agente_ok = problema_agente is None and all(
            c["stato"] == "ok" for c in componenti.values())
        corpo = {"backend": {"stato": "ok", "dettaglio": "in ascolto"},
                 "database": {"stato": "errore" if problema_db else "ok",
                              "dettaglio": problema_db or "raggiungibile"},
                 "agente": {"stato": "ok" if agente_ok else "errore",
                            "dettaglio": problema_agente or agente_url,
                            "componenti": componenti}}
        return JSONResponse(corpo, status_code=200 if agente_ok and not problema_db else 503)

    return app


def crea_backend_da_configurazione(config) -> FastAPI:
    from assistente.archivio import ArchivioPostgres
    from assistente.varianti import lettore_preferenze
    if not config.database_url:
        from assistente.config import ErroreConfigurazione
        raise ErroreConfigurazione("Variabile d'ambiente obbligatoria mancante o vuota: DATABASE_URL")
    archivio = ArchivioPostgres(config.database_url)
    archivio.azzera_turni()  # turni rimasti a metà da un arresto: domande in errore, riprovabili
    agente_url = config.agente_url or f"http://{config.agente_host}:{config.agente_porta}"
    return crea_backend(archivio, ClienteAgente(agente_url, timeout=config.agente_timeout),
                        lettore_preferenze(config), agente_url)


def scrivi_openapi(percorso: str) -> None:
    import json
    from pathlib import Path

    from assistente.archivio import ArchivioMemoria
    spec = crea_backend(ArchivioMemoria(), ClienteAgente("http://agente"), Preferenze,
                        "http://agente").openapi()
    testo = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    Path(percorso).write_text(testo, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """Avvio del back-end; `--openapi FILE` scrive soltanto il contratto. Codice 2 se manca la
    configurazione."""
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--openapi"] and len(argv) == 2:
        scrivi_openapi(argv[1])
        return 0
    import uvicorn
    from dotenv import load_dotenv

    from assistente.cli import configura_log
    from assistente.config import ErroreConfigurazione, carica_configurazione
    load_dotenv(".env", override=False)
    try:
        config = carica_configurazione()
        app = crea_backend_da_configurazione(config)
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    configura_log(config)
    uvicorn.run(app, host=config.backend_host, port=config.backend_porta,
                log_level=config.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
