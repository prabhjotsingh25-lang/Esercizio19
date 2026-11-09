"""Contesto testuale della conversazione, condiviso da router e revisore."""
from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

# Messaggi di testo precedenti (domande e risposte, senza strumenti) che router e revisore vedono.
FINESTRA = 6
# Nome dei messaggi con cui il revisore dà indicazioni all'agente: non sono domande dell'utente.
NOME_REVISORE = "revisore"


def e_indicazione(messaggio: BaseMessage) -> bool:
    """Vero per le indicazioni del revisore (messaggi utente con name="revisore")."""
    return isinstance(messaggio, HumanMessage) and messaggio.name == NOME_REVISORE


def _testo(messaggio: BaseMessage) -> str | None:
    """Testo di una domanda o di una risposta finale; None per strumenti, indicazioni e vuoti."""
    if e_indicazione(messaggio):
        return None
    if isinstance(messaggio, HumanMessage) or (
            isinstance(messaggio, AIMessage) and not messaggio.tool_calls):
        if isinstance(messaggio.content, str) and messaggio.content.strip():
            return messaggio.content.strip()
    return None


def contesto_testuale(precedenti: Sequence[BaseMessage]) -> str:
    """Ultimi FINESTRA messaggi di testo come righe «Utente: ...» / «Assistente: ...»."""
    righe = []
    for m in precedenti:
        testo = _testo(m)
        if testo is not None:
            righe.append(f"{'Utente' if isinstance(m, HumanMessage) else 'Assistente'}: {testo}")
    return "\n".join(righe[-FINESTRA:]) or "(nessuna)"
