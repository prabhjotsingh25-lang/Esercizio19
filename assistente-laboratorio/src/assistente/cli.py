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
from assistente.sessione import Sessione
from assistente.strumenti import crea_strumento_orologio


def esegui(sessione: Sessione, base_url: str,
           leggi: Callable[[str], str] = input,
           scrivi: Callable[[str], None] = print) -> None:
    """Ciclo di conversazione; termina con /esci, fine input o Ctrl+C."""
    scrivi("Comandi: /esci per uscire, /nuova per una nuova conversazione.")
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
        try:
            scrivi(f"Assistente> {sessione.chiedi(riga)}")
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
    grafo = costruisci_grafo(crea_modello(config), [crea_strumento_orologio()],
                             config.max_passaggi)
    esegui(Sessione(grafo, config.max_passaggi), config.base_url)
    return 0
