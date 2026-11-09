"""Router: prima dell'agente decide se la domanda rientra nell'ambito dell'assistente."""
import logging
from collections.abc import Callable, Sequence
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from assistente.contesto import FINESTRA, contesto_testuale

log = logging.getLogger("assistente.router")

__all__ = ["FINESTRA", "Classificazione", "Router", "crea_router", "messaggi_per_router"]

ISTRUZIONI_ROUTER = (
    "Sei il router di un assistente. Non rispondere alla domanda: classificala soltanto.\n"
    "Ambito dell'assistente: {ambito}\n"
    "Categoria 'conversazione': la domanda rientra nell'ambito, oppure prosegue la "
    "conversazione precedente. Categoria 'fuori_ambito': qualsiasi altra richiesta.\n"
    "Non valutare quali strumenti servono: lo decide l'assistente. "
    "Scrivi prima il motivo, in una frase, poi la categoria."
)


class Classificazione(BaseModel):
    """Classificazione dell'ultima domanda dell'utente rispetto all'ambito dell'assistente."""

    motivo: str = Field(description="Una frase che spiega la scelta.")
    categoria: Literal["conversazione", "fuori_ambito"] = Field(
        description="conversazione se la domanda rientra nell'ambito, altrimenti fuori_ambito.")


Router = Callable[[Sequence[BaseMessage]], Classificazione]


def messaggi_per_router(messaggi: Sequence[BaseMessage], ambito: str) -> list[BaseMessage]:
    """Prompt del router: ambito, ultimi FINESTRA messaggi di testo e domanda da classificare."""
    *precedenti, domanda = messaggi
    contesto = contesto_testuale(precedenti)
    return [SystemMessage(ISTRUZIONI_ROUTER.format(ambito=ambito)),
            HumanMessage(f"Conversazione precedente:\n{contesto}\n\n"
                         f"Domanda da classificare:\n{domanda.content}")]


def crea_router(modello: BaseChatModel, ambito: str) -> Router:
    """Router basato sul modello con output strutturato.

    Un output non valido vale «conversazione» (meglio passare all'agente che rifiutare una
    domanda valida); gli errori di connessione al modello passano al chiamante.
    """
    strutturato = modello.with_structured_output(Classificazione)

    def classifica(messaggi: Sequence[BaseMessage]) -> Classificazione:
        try:
            esito = strutturato.invoke(messaggi_per_router(messaggi, ambito))
        except ValueError as errore:  # JSON rotto o campi non validi (ValidationError)
            esito = errore
        if not isinstance(esito, Classificazione):
            log.warning("output del router non valido (%s): uso la categoria conversazione",
                        esito if esito is not None else "nessuna classificazione")
            return Classificazione(motivo="output del router non valido",
                                   categoria="conversazione")
        return esito

    return classifica
