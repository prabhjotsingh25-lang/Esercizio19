"""Interfaccia da terminale: ciclo di lettura, comandi e avvio dell'applicazione."""
import logging
import sys
from collections.abc import Callable

import openai
from dotenv import load_dotenv
from langgraph.errors import GraphRecursionError

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.prompt import (
    ErrorePrompt, FontePrompt, analizza_comando, controlla, descrivi_elenco)
from assistente.revisore import crea_revisore
from assistente.riassunto import crea_riassuntore
from assistente.router import crea_router
from assistente.sessione import Sessione
from assistente.varianti import fonte_prompt, lettore_preferenze, strumenti_per_variante


def _prompt(fonte: FontePrompt | None, resto: str, scrivi: Callable[[str], None]):
    """Prepara i messaggi di /prompt; None (con un messaggio) se il comando va bloccato.

    Il controllo su nome e argomenti si fa sull'elenco (prompts/list) prima di chiedere il
    testo (prompts/get): un comando non valido non arriva né al server né al modello.
    """
    if fonte is None:
        scrivi("Prompt non disponibili.")
        return None
    try:
        nome, argomenti = analizza_comando(resto)
    except ErrorePrompt as errore:
        scrivi(f"Prompt non valido: {errore}")
        return None
    try:
        elenco = fonte.elenca()
    except ErrorePrompt as errore:
        scrivi(f"Prompt non disponibili: {errore}")
        return None
    try:
        controlla(elenco, nome, argomenti)
    except ErrorePrompt as errore:
        scrivi(f"Prompt non valido: {errore}")
        return None
    try:
        messaggi = fonte.ottieni(nome, argomenti)
    except ErrorePrompt as errore:
        scrivi(f"Prompt non disponibili: {errore}")
        return None
    for m in messaggi:
        scrivi(f"Prompt> {m.content}")
    return messaggi


def esegui(sessione: Sessione, base_url: str,
           leggi: Callable[[str], str] = input,
           scrivi: Callable[[str], None] = print,
           prompt: FontePrompt | None = None) -> None:
    """Ciclo di conversazione; termina con /esci, fine input o Ctrl+C."""
    scrivi("Comandi: /esci per uscire, /nuova per una nuova conversazione, /prompts per "
           "l'elenco dei prompt, /prompt nome argomento=valore per usarne uno.")
    while True:
        try:
            riga = leggi("Tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            scrivi("")
            return
        if not riga:
            continue
        if riga == "/esci":
            return
        if riga == "/nuova":
            sessione.nuova()
            scrivi("Nuova conversazione avviata.")
            continue
        if riga == "/prompts":
            try:
                scrivi(descrivi_elenco(prompt.elenca()) if prompt else "Prompt non disponibili.")
            except ErrorePrompt as errore:
                scrivi(f"Prompt non disponibili: {errore}")
            continue
        if riga == "/prompt" or riga.startswith("/prompt "):
            messaggi = _prompt(prompt, riga[len("/prompt"):], scrivi)
            if messaggi is None:
                continue
            invia = lambda m=messaggi: sessione.chiedi_messaggi(m)  # noqa: E731
        else:
            invia = lambda r=riga: sessione.chiedi(r)  # noqa: E731
        try:
            scrivi(f"Assistente> {invia()}")
        except (openai.APIConnectionError, openai.APITimeoutError):
            scrivi(f"Non riesco a raggiungere LM Studio su {base_url}: "
                   "controlla che il server sia avviato.")
        except openai.APIError as errore:
            scrivi(f"Errore dal server del modello: {errore}")
        except KeyboardInterrupt:  # Ctrl+C durante l'attesa della risposta
            scrivi("")
            return
        except GraphRecursionError:
            scrivi("Ho raggiunto il limite di passaggi consentiti per questa domanda: "
                   "prova a riformularla.")


def main() -> int:
    """Punto di ingresso: 0 a esecuzione normale, 2 se la configurazione manca."""
    load_dotenv(".env", override=False)
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    logging.basicConfig(stream=sys.stderr, level=config.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for nome in ("httpx", "httpx2"):  # openai può usare l'uno o l'altro client HTTP
        logging.getLogger(nome).setLevel(logging.WARNING)
    strumenti = strumenti_per_variante(config)
    logging.getLogger("assistente").info("variante strumenti: %s (%s)", config.variante,
                                         ", ".join(s.name for s in strumenti))
    modello = crea_modello(config)
    grafo = costruisci_grafo(modello, strumenti, config.max_passaggi,
                             router=crea_router(modello, config.ambito),
                             revisore=crea_revisore(modello),
                             max_revisioni=config.max_revisioni,
                             riassuntore=crea_riassuntore(modello),
                             soglia_riassunto=config.soglia_riassunto,
                             messaggi_recenti=config.messaggi_recenti)
    # Le preferenze si leggono qui, una volta prima della prima domanda (e di nuovo con /nuova).
    sessione = Sessione(grafo, config.max_passaggi, config.max_revisioni,
                        leggi_preferenze=lettore_preferenze(config))
    esegui(sessione, config.base_url, prompt=fonte_prompt(config))
    return 0
