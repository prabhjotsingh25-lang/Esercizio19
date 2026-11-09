"""Revisore: controlla che la risposta proposta dall'agente sia coerente con la domanda."""
import logging
from collections.abc import Callable, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from assistente.contesto import NOME_REVISORE, contesto_testuale, e_indicazione

log = logging.getLogger("assistente.revisore")

ISTRUZIONI_REVISORE = (
    "Sei il revisore di un assistente. Non rispondere alla domanda: giudica soltanto la "
    "risposta proposta.\n"
    "La risposta è coerente se risponde alla domanda dell'utente, a tutte le sue parti. "
    "Sono coerenti anche una richiesta di chiarimento pertinente (per esempio quale città o "
    "quale fuso orario) e la spiegazione di un errore di uno strumento.\n"
    "Non puoi verificare i dati: non giudicare se numeri, orari o fatti sono esatti. "
    "Usa la conversazione precedente solo per capire la domanda.\n"
    "Scrivi prima il motivo, in una frase, poi il giudizio."
)


class Revisione(BaseModel):
    """Giudizio sulla risposta proposta rispetto alla domanda dell'utente."""

    motivo: str = Field(description="Una frase che spiega il giudizio.")
    coerente: bool = Field(
        description="true se la risposta risponde a tutta la domanda, altrimenti false.")


Revisore = Callable[[Sequence[BaseMessage]], Revisione]


def indicazione(motivo: str) -> HumanMessage:
    """Messaggio per l'agente quando la risposta non è coerente (resta in cronologia)."""
    return HumanMessage(
        f"Revisione: la risposta precedente non va bene perché {motivo.strip().rstrip('.')}. "
        "Riscrivi la risposta alla domanda tenendone conto.",
        name=NOME_REVISORE)


def messaggi_per_revisore(messaggi: Sequence[BaseMessage]) -> list[BaseMessage]:
    """Prompt del revisore: contesto precedente, domanda originale del turno, ultima risposta."""
    i = max(i for i, m in enumerate(messaggi)
            if isinstance(m, HumanMessage) and not e_indicazione(m))
    return [SystemMessage(ISTRUZIONI_REVISORE),
            HumanMessage(f"Conversazione precedente:\n{contesto_testuale(messaggi[:i])}\n\n"
                         f"Domanda dell'utente:\n{messaggi[i].content}\n\n"
                         f"Risposta proposta:\n{messaggi[-1].content}")]


def crea_revisore(modello: BaseChatModel) -> Revisore:
    """Revisore basato sul modello con output strutturato.

    Un output non valido vale «coerente» (la risposta dell'agente passa così com'è); gli
    errori di connessione al modello passano al chiamante.
    """
    strutturato = modello.with_structured_output(Revisione)

    def rivedi(messaggi: Sequence[BaseMessage]) -> Revisione:
        try:
            esito = strutturato.invoke(messaggi_per_revisore(messaggi))
        except ValueError as errore:  # JSON rotto o campi non validi (ValidationError)
            esito = errore
        if not isinstance(esito, Revisione):
            log.warning("output del revisore non valido (%s): considero la risposta coerente",
                        esito if esito is not None else "nessun giudizio")
            return Revisione(motivo="output del revisore non valido", coerente=True)
        return esito

    return rivedi
