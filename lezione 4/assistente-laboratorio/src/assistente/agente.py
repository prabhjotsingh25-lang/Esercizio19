"""Agente: un turno sul grafo, strumenti usati, prompt. Lo usano il servizio HTTP e la CLI.

Il modulo non tiene stato: cronologia, riassunto e preferenze arrivano dal chiamante a ogni
turno (la `Sessione` in-process li conserva, il servizio HTTP li riceve nella richiesta).
"""
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict

from assistente.contesto import e_indicazione
from assistente.grafo import limite_ricorsione
from assistente.preferenze import Preferenze
from assistente.prompt import FontePrompt, InfoPrompt, controlla


@dataclass(frozen=True)
class StrumentoUsato:
    nome: str
    argomenti: dict
    risultato: str


@dataclass
class EsitoTurno:
    risposta: str
    strumenti: list[StrumentoUsato]
    messaggi: list[BaseMessage]  # cronologia completa dopo il turno (strumenti compresi)
    riassunto: str
    prompt: list[str] = field(default_factory=list)  # testi composti da un prompt, se usato


class VoceCronologia(BaseModel):
    """Cronologia nell'API: solo testi dell'utente e dell'assistente, nessun altro campo."""

    model_config = ConfigDict(extra="forbid")

    ruolo: Literal["utente", "assistente"]
    testo: str


def strumenti_usati(messaggi: Sequence[BaseMessage]) -> list[StrumentoUsato]:
    """Chiamate agli strumenti presenti in `messaggi`, con il loro risultato."""
    chiamate = {c["id"]: c for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls}
    return [StrumentoUsato(chiamate[m.tool_call_id]["name"], chiamate[m.tool_call_id]["args"],
                           str(m.content))
            for m in messaggi
            if isinstance(m, ToolMessage) and m.tool_call_id in chiamate]


def in_dialogo(messaggi: Sequence[BaseMessage]) -> list[VoceCronologia]:
    """Domande e risposte finali accettate; senza strumenti, indicazioni, bozze e nomi."""
    voci = []
    for i, m in enumerate(messaggi):
        successivo = messaggi[i + 1] if i + 1 < len(messaggi) else None
        if isinstance(m, HumanMessage) and not e_indicazione(m):
            voci.append(VoceCronologia(ruolo="utente", testo=str(m.content)))
        elif (isinstance(m, AIMessage) and not m.tool_calls and str(m.content).strip()
              and not (successivo is not None and e_indicazione(successivo))):
            voci.append(VoceCronologia(ruolo="assistente", testo=str(m.content)))
    return voci


def da_dialogo(voci: Sequence[VoceCronologia]) -> list[BaseMessage]:
    """Messaggi senza nome dalla cronologia dell'API."""
    return [HumanMessage(v.testo) if v.ruolo == "utente" else AIMessage(v.testo) for v in voci]


class Agente:
    """Grafo compilato più fonte dei prompt; ogni chiamata è un turno indipendente."""

    def __init__(self, grafo, max_passaggi: int, max_revisioni: int,
                 fonte_prompt: FontePrompt | None = None):
        self._grafo = grafo
        self._config = {"recursion_limit": limite_ricorsione(max_passaggi, max_revisioni)}
        self._fonte = fonte_prompt

    def turno(self, nuovi: list[BaseMessage], cronologia: list[BaseMessage], riassunto: str,
              preferenze: Preferenze | None) -> EsitoTurno:
        """Invoca il grafo con cronologia + nuovi messaggi; le eccezioni passano al chiamante."""
        # Un id ai messaggi nuovi: il riassunto può togliere messaggi vecchi, quindi gli strumenti
        # del turno si contano dopo l'ultimo dei nuovi, cercato per id (il riassunto non lo
        # toglie mai: il taglio cade al più sulla prima domanda del turno).
        nuovi = [m if m.id else m.model_copy(update={"id": str(uuid4())}) for m in nuovi]
        uscita = self._grafo.invoke(
            {"messages": [*cronologia, *nuovi], "passaggi": 0, "revisioni": 0,
             "riassunto": riassunto, "preferenze": preferenze}, config=self._config)
        messaggi = list(uscita["messages"])
        inizio = next(i + 1 for i, m in enumerate(messaggi) if m.id == nuovi[-1].id)
        return EsitoTurno(risposta=str(messaggi[-1].content),
                          strumenti=strumenti_usati(messaggi[inizio:]), messaggi=messaggi,
                          riassunto=uscita.get("riassunto", ""))

    def messaggio(self, testo: str, cronologia: list[BaseMessage], riassunto: str,
                  preferenze: Preferenze | None) -> EsitoTurno:
        """Una domanda scritta dall'utente: messaggio senza nome, lo decide il router."""
        return self.turno([HumanMessage(testo)], cronologia, riassunto, preferenze)

    def elenco_prompt(self) -> list[InfoPrompt]:
        if self._fonte is None:
            return []
        return self._fonte.elenca()

    def prompt(self, nome: str, argomenti: dict[str, str], cronologia: list[BaseMessage],
               riassunto: str, preferenze: Preferenze | None) -> EsitoTurno:
        """Controlla nome e argomenti sull'elenco, compone i messaggi (name="prompt") e li invia.

        Il contrassegno lo mettono solo le fonti dei prompt, dopo il controllo: chi chiama
        l'agente passa nome e argomenti, mai messaggi già composti.
        """
        controlla(self.elenco_prompt(), nome, argomenti)
        nuovi = self._fonte.ottieni(nome, argomenti)
        esito = self.turno(nuovi, cronologia, riassunto, preferenze)
        esito.prompt = [str(m.content) for m in nuovi]
        return esito


def grafo_da_configurazione(config):
    """Grafo completo (riassunto, router, revisore, strumenti della variante) da configurazione.

    Usato dalla CLI in-process e dal servizio HTTP: stesso agente nei due modi.
    """
    import logging

    from assistente.grafo import costruisci_grafo
    from assistente.modello import crea_modello
    from assistente.revisore import crea_revisore
    from assistente.riassunto import crea_riassuntore
    from assistente.router import crea_router
    from assistente.varianti import strumenti_per_variante

    strumenti = strumenti_per_variante(config)
    logging.getLogger("assistente").info("variante strumenti: %s (%s)", config.variante,
                                         ", ".join(s.name for s in strumenti))
    modello = crea_modello(config)
    return costruisci_grafo(modello, strumenti, config.max_passaggi,
                            router=crea_router(modello, config.ambito),
                            revisore=crea_revisore(modello),
                            max_revisioni=config.max_revisioni,
                            riassuntore=crea_riassuntore(modello),
                            soglia_riassunto=config.soglia_riassunto,
                            messaggi_recenti=config.messaggi_recenti)
