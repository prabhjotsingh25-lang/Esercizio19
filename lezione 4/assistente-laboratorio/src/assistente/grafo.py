"""Grafo LangGraph: nodi `router`, `rifiuto`, `modello`, `strumenti`, `limite` e `revisore`.

L'instradamento è esplicito: archi condizionali dopo il router, il modello e il revisore.
"""
import logging
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.contesto import e_indicazione
from assistente.revisore import Revisore, indicazione
from assistente.router import Router

log = logging.getLogger("assistente.grafo")

# Neutro: non nomina strumenti (arrivano al modello con bind_tools), quindi è identico
# qualunque sia l'insieme di strumenti o la variante di integrazione esposta.
MESSAGGIO_SISTEMA = (
    "Sei un assistente di laboratorio. "
    "Quando una richiesta riguarda dati che non conosci o che possono cambiare "
    "(per esempio data e ora) o un calcolo da eseguire, usa gli strumenti disponibili: "
    "non inventare i risultati. "
    "Se manca un'informazione necessaria per usare uno strumento "
    "(per esempio il luogo o il fuso orario), chiedila all'utente. "
    "Se uno strumento restituisce un errore, spiegalo all'utente. "
    "Rispondi nella lingua dell'utente."
)
MESSAGGIO_LIMITE = (
    "Ho raggiunto il limite di passaggi dello strumento per questa domanda "
    "e mi sono fermato. Prova a riformulare la richiesta."
)
MESSAGGIO_RIFIUTO = (
    "Mi dispiace, questa richiesta è fuori dal mio ambito. Posso aiutarti con orari, "
    "scadenze, calcoli e conversioni, catalogo, note e meteo: chiedimi pure."
)
_NON_ESEGUITO = "Non eseguito: limite di passaggi raggiunto."


class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    passaggi: int
    categoria: NotRequired[str]  # decisa dal router: conversazione o fuori_ambito
    revisioni: NotRequired[int]  # nuovi tentativi chiesti dal revisore in questo turno


def scegli_dopo_router(stato: Stato) -> Literal["modello", "rifiuto"]:
    """Dopo il router: la conversazione va all'agente, il resto al rifiuto."""
    return "rifiuto" if stato["categoria"] == "fuori_ambito" else "modello"


def scegli_dopo_revisore(stato: Stato) -> Literal["modello", "__end__"]:
    """Dopo il revisore: se ha lasciato un'indicazione l'agente riprova, altrimenti fine."""
    return "modello" if e_indicazione(stato["messages"][-1]) else "__end__"


def scegli_prossimo(stato: Stato, max_passaggi: int) -> Literal["strumenti", "limite", "__end__"]:
    """Dopo il modello: fine, esecuzione degli strumenti oppure stop per limite."""
    ultimo = stato["messages"][-1]
    if not getattr(ultimo, "tool_calls", None):
        return "__end__"
    return "limite" if stato["passaggi"] >= max_passaggi else "strumenti"


def limite_ricorsione(max_passaggi: int, max_revisioni: int = 0) -> int:
    """Limite di ricorsione di LangGraph, con margine rispetto a passaggi e revisioni consentiti.

    Ogni passaggio di strumento costa 2 nodi (strumenti, modello), ogni revisione 2 (revisore,
    modello); il margine copre router, primo modello, ultimo revisore e limite.
    """
    return 2 * max_passaggi + 2 * max_revisioni + 5


def costruisci_grafo(modello: BaseChatModel, strumenti: list[BaseTool], max_passaggi: int,
                     router: Router | None = None, revisore: Revisore | None = None,
                     max_revisioni: int = 1):
    """Compila il grafo: START -> modello -> (strumenti -> modello | limite -> END | END).

    Con un router: START -> router -> (modello -> ... | rifiuto -> END).
    Con un revisore la risposta finale passa da lui: revisore -> (END | modello).
    """
    modello_con_strumenti = modello.bind_tools(strumenti)
    per_nome = {s.name: s for s in strumenti}

    def nodo_modello(stato: Stato) -> dict:
        messaggi = [SystemMessage(MESSAGGIO_SISTEMA), *stato["messages"]]
        log.info("agente: chiamata al modello con %d messaggi", len(messaggi))
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

    def nodo_router(stato: Stato) -> dict:
        esito = router(stato["messages"])
        destinazione = "rifiuto" if esito.categoria == "fuori_ambito" else "agente"
        log.info("router categoria=%s motivo=%s -> %s", esito.categoria, esito.motivo, destinazione)
        return {"categoria": esito.categoria}

    def nodo_rifiuto(stato: Stato) -> dict:
        log.info("rifiuto: domanda fuori ambito, l'agente non viene chiamato")
        return {"messages": [AIMessage(MESSAGGIO_RIFIUTO)]}

    def nodo_revisore(stato: Stato) -> dict:
        esito = revisore(stato["messages"])
        revisioni = stato.get("revisioni", 0)
        if esito.coerente:
            log.info("revisore coerente=sì motivo=%s -> fine", esito.motivo)
            return {"revisioni": revisioni}
        if revisioni >= max_revisioni:
            log.info("revisore coerente=no motivo=%s", esito.motivo)
            log.warning("limite di %d revisioni raggiunto: restituisco l'ultima risposta",
                        max_revisioni)
            return {"revisioni": revisioni}
        log.info("revisore coerente=no motivo=%s -> agente (revisione %d/%d)",
                 esito.motivo, revisioni + 1, max_revisioni)
        return {"messages": [indicazione(esito.motivo)], "revisioni": revisioni + 1}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    if router is None:
        grafo.add_edge(START, "modello")
    else:
        grafo.add_node("router", nodo_router)
        grafo.add_node("rifiuto", nodo_rifiuto)
        grafo.add_edge(START, "router")
        grafo.add_conditional_edges("router", scegli_dopo_router,
                                    {"modello": "modello", "rifiuto": "rifiuto"})
        grafo.add_edge("rifiuto", END)
    if revisore is not None:
        grafo.add_node("revisore", nodo_revisore)
        grafo.add_conditional_edges("revisore", scegli_dopo_revisore,
                                    {"modello": "modello", "__end__": END})
    grafo.add_conditional_edges(
        "modello", lambda stato: scegli_prossimo(stato, max_passaggi),
        {"strumenti": "strumenti", "limite": "limite",
         "__end__": END if revisore is None else "revisore"})
    grafo.add_edge("strumenti", "modello")
    grafo.add_edge("limite", END)
    return grafo.compile()
