"""Grafo LangGraph: nodi `modello`, `strumenti` e `limite`, con instradamento esplicito."""
import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

log = logging.getLogger("assistente.grafo")

MESSAGGIO_SISTEMA = (
    "Sei un assistente di laboratorio. "
    "Per conoscere data e ora usa sempre lo strumento ora_corrente: non inventarle. "
    "Se l'utente chiede l'ora senza indicare un luogo o un fuso orario, chiedigli dove. "
    "Rispondi nella lingua dell'utente."
)
MESSAGGIO_LIMITE = (
    "Ho raggiunto il limite di passaggi dello strumento per questa domanda "
    "e mi sono fermato. Prova a riformulare la richiesta."
)
_NON_ESEGUITO = "Non eseguito: limite di passaggi raggiunto."


class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    passaggi: int


def scegli_prossimo(stato: Stato, max_passaggi: int) -> Literal["strumenti", "limite", "__end__"]:
    """Dopo il modello: fine, esecuzione degli strumenti oppure stop per limite."""
    ultimo = stato["messages"][-1]
    if not getattr(ultimo, "tool_calls", None):
        return "__end__"
    return "limite" if stato["passaggi"] >= max_passaggi else "strumenti"


def limite_ricorsione(max_passaggi: int) -> int:
    """Limite di ricorsione di LangGraph, con margine rispetto ai passaggi consentiti."""
    return 2 * max_passaggi + 5


def costruisci_grafo(modello: BaseChatModel, strumenti: list[BaseTool], max_passaggi: int):
    """Compila il grafo: START -> modello -> (strumenti -> modello | limite -> END | END)."""
    modello_con_strumenti = modello.bind_tools(strumenti)
    per_nome = {s.name: s for s in strumenti}

    def nodo_modello(stato: Stato) -> dict:
        messaggi = [SystemMessage(MESSAGGIO_SISTEMA), *stato["messages"]]
        log.debug("chiamata al modello con %d messaggi", len(messaggi))
        risposta = modello_con_strumenti.invoke(messaggi)
        log.debug("risposta del modello: %r", risposta)
        return {"messages": [risposta]}

    def nodo_strumenti(stato: Stato) -> dict:
        passaggio = stato["passaggi"] + 1
        risultati = []
        for chiamata in stato["messages"][-1].tool_calls:
            nome, argomenti = chiamata["name"], chiamata["args"]
            strumento = per_nome.get(nome)
            if strumento is None:
                esito = f"Errore: strumento sconosciuto: {nome}"
            else:
                try:
                    esito = str(strumento.invoke(argomenti))
                except Exception as errore:  # argomenti non validi o guasto: lo vede il modello
                    esito = f"Errore: {errore}"
            log.info("strumento passaggio=%d nome=%s argomenti=%s risultato=%s",
                     passaggio, nome, argomenti, esito)
            risultati.append(ToolMessage(esito, tool_call_id=chiamata["id"]))
        return {"messages": risultati, "passaggi": passaggio}

    def nodo_limite(stato: Stato) -> dict:
        log.warning("limite di %d passaggi raggiunto: chiamate non eseguite", max_passaggi)
        chiuse = [ToolMessage(_NON_ESEGUITO, tool_call_id=c["id"])
                  for c in stato["messages"][-1].tool_calls]
        return {"messages": [*chiuse, AIMessage(MESSAGGIO_LIMITE)]}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_edge(START, "modello")
    grafo.add_conditional_edges(
        "modello", lambda stato: scegli_prossimo(stato, max_passaggi),
        {"strumenti": "strumenti", "limite": "limite", "__end__": END})
    grafo.add_edge("strumenti", "modello")
    grafo.add_edge("limite", END)
    return grafo.compile()
