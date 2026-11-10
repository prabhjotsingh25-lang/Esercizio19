"""Servizio HTTP dell'agente (FastAPI), senza stato: il chiamante manda cronologia, riassunto e
preferenze a ogni richiesta e riceve risposta, strumenti usati, cronologia e riassunto aggiornati.

Avvio: python -m assistente.servizio_agente   (host e porta da AGENTE_HOST e AGENTE_PORTA)
Contratto: /docs, /openapi.json e la copia in docs/openapi-agente.json.
"""
import logging
import sys
import time
from collections.abc import Callable

import openai
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, ConfigDict, Field

from assistente.agente import Agente, EsitoTurno, VoceCronologia, da_dialogo, in_dialogo
from assistente.grafo import MESSAGGIO_LIMITE
from assistente.preferenze import PREDEFINITE, Preferenze, descrivi
from assistente.prompt import ErrorePrompt, PromptNonDisponibili

log = logging.getLogger("assistente.agente_http")

Verifica = Callable[[], str | None]


class _Rigida(BaseModel):
    model_config = ConfigDict(extra="forbid")  # campi non previsti (per esempio name) → 422


class RichiestaMessaggio(_Rigida):
    testo: str = Field(min_length=1, description="Domanda dell'utente.")
    cronologia: list[VoceCronologia] = Field(default_factory=list,
                                             description="Turni precedenti: solo utente e assistente.")
    riassunto: str = Field("", description="Riassunto restituito dalla risposta precedente.")
    preferenze: Preferenze | None = Field(None, description="Se mancano: valori predefiniti.")


class RichiestaPrompt(_Rigida):
    nome: str = Field(description="Nome del prompt (GET /prompt).")
    argomenti: dict[str, str] = Field(default_factory=dict)
    cronologia: list[VoceCronologia] = Field(default_factory=list)
    riassunto: str = ""
    preferenze: Preferenze | None = None


class StrumentoUsatoApi(BaseModel):
    nome: str
    argomenti: dict
    risultato: str


class RispostaTurno(BaseModel):
    risposta: str
    strumenti: list[StrumentoUsatoApi]
    cronologia: list[VoceCronologia]
    riassunto: str


class RispostaPrompt(RispostaTurno):
    prompt: list[str] = Field(description="Testi composti dal servizio a partire dal prompt.")


class ArgomentoApi(BaseModel):
    nome: str
    descrizione: str
    obbligatorio: bool


class PromptApi(BaseModel):
    nome: str
    descrizione: str
    argomenti: list[ArgomentoApi]


class Componente(BaseModel):
    stato: str = Field(description="ok oppure errore")
    dettaglio: str


class Stato(BaseModel):
    agente: Componente
    modello: Componente
    strumenti: Componente


def _preferenze(richieste: Preferenze | None) -> Preferenze:
    if richieste is None:
        log.warning("preferenze non inviate dal chiamante: uso le predefinite (%s)",
                    descrivi(PREDEFINITE))
        return PREDEFINITE
    return richieste


def crea_app(agente: Agente, base_url: str, verifica_strumenti: Verifica,
             verifica_modello: Verifica, descrizione_strumenti: str) -> FastAPI:
    """Servizio sopra un `Agente`; verifiche e descrizioni iniettabili per i test."""
    app = FastAPI(title="Agente dell'assistente di laboratorio", version="1.0.0",
                  description="Agente senza stato: ogni richiesta porta cronologia, riassunto "
                              "e preferenze; la risposta li restituisce aggiornati.")

    def esegui(percorso: str, turno: Callable[[], EsitoTurno], testo_utente: str | None,
               cronologia: list[VoceCronologia], riassunto: str) -> EsitoTurno:
        """Controllo degli strumenti, turno, errori tradotti in codici HTTP, log della richiesta."""
        inizio = time.perf_counter()
        codice, strumenti = 200, ""
        try:
            problema = verifica_strumenti()
            if problema:
                raise HTTPException(503, f"strumenti non disponibili: {problema}")
            try:
                esito = turno()
            except GraphRecursionError:
                messaggi = [*da_dialogo(cronologia),
                            *([HumanMessage(testo_utente)] if testo_utente else []),
                            AIMessage(MESSAGGIO_LIMITE)]
                esito = EsitoTurno(MESSAGGIO_LIMITE, [], messaggi, riassunto)
            except PromptNonDisponibili as errore:
                raise HTTPException(503, f"prompt non disponibili: {errore}") from None
            except ErrorePrompt as errore:
                raise HTTPException(422, f"prompt non valido: {errore}") from None
            except (openai.APIConnectionError, openai.APITimeoutError):
                raise HTTPException(503, f"modello non raggiungibile su {base_url}: controlla "
                                         "che LM Studio sia avviato") from None
            except openai.APIError as errore:
                raise HTTPException(502, f"errore dal server del modello: {errore}") from None
            strumenti = ", ".join(s.nome for s in esito.strumenti) or "nessuno"
            return esito
        except HTTPException as errore:
            codice, strumenti = errore.status_code, errore.detail
            raise
        finally:
            log.info("agente_http: POST %s -> %d in %.1f s (strumenti: %s)", percorso, codice,
                     time.perf_counter() - inizio, strumenti)

    def risposta(esito: EsitoTurno) -> dict:
        return {"risposta": esito.risposta,
                "strumenti": [{"nome": s.nome, "argomenti": s.argomenti, "risultato": s.risultato}
                              for s in esito.strumenti],
                "cronologia": in_dialogo(esito.messaggi), "riassunto": esito.riassunto}

    @app.post("/messaggi", response_model=RispostaTurno,
              summary="Una domanda dell'utente, con cronologia, riassunto e preferenze")
    def messaggi(richiesta: RichiestaMessaggio) -> dict:
        preferenze = _preferenze(richiesta.preferenze)
        esito = esegui("/messaggi", lambda: agente.messaggio(
            richiesta.testo, da_dialogo(richiesta.cronologia), richiesta.riassunto, preferenze),
            richiesta.testo, richiesta.cronologia, richiesta.riassunto)
        return risposta(esito)

    @app.post("/prompt", response_model=RispostaPrompt,
              summary="Usa un prompt: il servizio compone i messaggi (name=\"prompt\")")
    def usa_prompt(richiesta: RichiestaPrompt) -> dict:
        preferenze = _preferenze(richiesta.preferenze)
        esito = esegui("/prompt", lambda: agente.prompt(
            richiesta.nome, richiesta.argomenti, da_dialogo(richiesta.cronologia),
            richiesta.riassunto, preferenze), None, richiesta.cronologia, richiesta.riassunto)
        return {**risposta(esito), "prompt": esito.prompt}

    @app.get("/prompt", response_model=list[PromptApi], summary="Elenco dei prompt")
    def elenco_prompt() -> list[dict]:
        try:
            elenco = agente.elenco_prompt()
        except PromptNonDisponibili as errore:
            raise HTTPException(503, f"prompt non disponibili: {errore}") from None
        return [{"nome": i.nome, "descrizione": i.descrizione,
                 "argomenti": [{"nome": a.nome, "descrizione": a.descrizione,
                                "obbligatorio": a.obbligatorio} for a in i.argomenti]}
                for i in elenco]

    @app.get("/stato", response_model=Stato, responses={503: {"model": Stato}},
             summary="Raggiungibilità di agente, modello e strumenti")
    def stato():
        problema_modello, problema_strumenti = verifica_modello(), verifica_strumenti()
        corpo = {"agente": {"stato": "ok", "dettaglio": "in ascolto"},
                 "modello": {"stato": "errore" if problema_modello else "ok",
                             "dettaglio": problema_modello or base_url},
                 "strumenti": {"stato": "errore" if problema_strumenti else "ok",
                               "dettaglio": problema_strumenti or descrizione_strumenti}}
        codice = 503 if problema_modello or problema_strumenti else 200
        return JSONResponse(corpo, status_code=codice)

    return app


def crea_app_da_configurazione(config) -> FastAPI:
    """Come la CLI in-process: stesso grafo, stessa variante di strumenti e prompt."""
    from assistente.agente import grafo_da_configurazione
    from assistente.varianti import (
        descrivi_strumenti, fonte_prompt, verifica_modello, verifica_strumenti)
    agente = Agente(grafo_da_configurazione(config), config.max_passaggi, config.max_revisioni,
                    fonte_prompt(config))
    return crea_app(agente, config.base_url, verifica_strumenti(config), verifica_modello(config),
                    descrivi_strumenti(config))


def scrivi_openapi(percorso: str) -> None:
    """Contratto OpenAPI su file (non dipende dal modello: nessuna chiamata)."""
    import json
    from pathlib import Path
    spec = crea_app(None, "", lambda: None, lambda: None, "").openapi()
    testo = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    Path(percorso).write_text(testo, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """Avvio del servizio con host e porta da configurazione; codice 2 se la configurazione manca.

    `--openapi FILE` scrive soltanto il contratto OpenAPI.
    """
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--openapi"] and len(argv) == 2:
        scrivi_openapi(argv[1])
        return 0
    import uvicorn
    from dotenv import load_dotenv

    from assistente.config import ErroreConfigurazione, carica_configurazione
    from assistente.cli import configura_log
    load_dotenv(".env", override=False)
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    configura_log(config)
    uvicorn.run(crea_app_da_configurazione(config), host=config.agente_host,
                port=config.agente_porta, log_level=config.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
