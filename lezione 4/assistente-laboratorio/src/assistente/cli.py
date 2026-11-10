"""Interfaccia da terminale: ciclo di lettura, comandi e avvio dell'applicazione.

Con AGENTE_URL la CLI è un client dell'API dell'agente (`cliente_agente.SessioneRemota`);
senza, l'agente gira nel processo (`sessione.Sessione`). I comandi sono gli stessi.
"""
import logging
import sys
from collections.abc import Callable

import openai
from dotenv import load_dotenv
from langgraph.errors import GraphRecursionError

from assistente.cliente_agente import ErroreAgente
from assistente.config import Configurazione, ErroreConfigurazione, carica_configurazione
from assistente.prompt import ErrorePrompt, PromptNonDisponibili, analizza_comando, descrivi_elenco


def _usa_prompt(sessione, resto: str, scrivi: Callable[[str], None]) -> None:
    """/prompt: l'analisi della riga è locale; controllo e composizione li fa l'agente."""
    try:
        nome, argomenti = analizza_comando(resto)
    except ErrorePrompt as errore:
        scrivi(f"Prompt non valido: {errore}")
        return
    try:
        esito = sessione.usa_prompt(nome, argomenti)
    except PromptNonDisponibili as errore:
        scrivi(f"Prompt non disponibili: {errore}")
        return
    except ErrorePrompt as errore:
        scrivi(f"Prompt non valido: {errore}")
        return
    for testo in esito.prompt:
        scrivi(f"Prompt> {testo}")
    scrivi(f"Assistente> {esito.risposta}")


def esegui(sessione, base_url: str,
           leggi: Callable[[str], str] = input,
           scrivi: Callable[[str], None] = print) -> None:
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
        try:
            if riga == "/nuova":
                sessione.nuova()
                scrivi("Nuova conversazione avviata.")
            elif riga == "/prompts":
                try:
                    scrivi(descrivi_elenco(sessione.elenco_prompt()))
                except PromptNonDisponibili as errore:
                    scrivi(f"Prompt non disponibili: {errore}")
            elif riga == "/prompt" or riga.startswith("/prompt "):
                _usa_prompt(sessione, riga[len("/prompt"):], scrivi)
            else:
                scrivi(f"Assistente> {sessione.chiedi(riga)}")
        except ErroreAgente as errore:  # CLI client: servizio, modello o strumenti non disponibili
            scrivi(str(errore))
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


def configura_log(config: Configurazione) -> None:
    """Log su stderr al livello configurato; i client HTTP solo da WARNING in su."""
    logging.basicConfig(stream=sys.stderr, level=config.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for nome in ("httpx", "httpx2"):  # openai può usare l'uno o l'altro client HTTP
        logging.getLogger(nome).setLevel(logging.WARNING)


def main() -> int:
    """Punto di ingresso: 0 a esecuzione normale, 2 se la configurazione manca."""
    load_dotenv(".env", override=False)
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    configura_log(config)
    from assistente.varianti import lettore_preferenze
    if config.agente_url:
        from assistente.cliente_agente import ClienteAgente, SessioneRemota
        logging.getLogger("assistente").info("CLI client dell'agente su %s", config.agente_url)
        # Le preferenze le legge la CLI (host), una volta e con /nuova, e le manda all'agente.
        sessione = SessioneRemota(ClienteAgente(config.agente_url),
                                  leggi_preferenze=lettore_preferenze(config))
        esegui(sessione, config.agente_url)
        return 0
    from assistente.agente import grafo_da_configurazione
    from assistente.sessione import Sessione
    from assistente.varianti import fonte_prompt
    sessione = Sessione(grafo_da_configurazione(config), config.max_passaggi,
                        config.max_revisioni, leggi_preferenze=lettore_preferenze(config),
                        fonte_prompt=fonte_prompt(config))
    esegui(sessione, config.base_url)
    return 0
