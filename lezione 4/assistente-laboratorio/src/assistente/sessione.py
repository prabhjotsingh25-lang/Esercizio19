"""Sessione di conversazione in-process: conserva cronologia, riassunto e preferenze e usa
lo stesso modulo dell'agente del servizio HTTP (`agente.Agente`)."""
from langchain_core.messages import BaseMessage

from assistente.agente import Agente, EsitoTurno
from assistente.preferenze import LettorePreferenze, Preferenze
from assistente.prompt import FontePrompt, InfoPrompt


class Sessione:
    """Tiene la cronologia della conversazione per la durata del processo."""

    def __init__(self, grafo, max_passaggi: int, max_revisioni: int = 0,
                 leggi_preferenze: LettorePreferenze | None = None,
                 fonte_prompt: FontePrompt | None = None):
        """`leggi_preferenze` (host): letto qui, prima della prima domanda, e da `nuova()`."""
        self._agente = Agente(grafo, max_passaggi, max_revisioni, fonte_prompt)
        self._leggi_preferenze = leggi_preferenze
        self.cronologia: list[BaseMessage] = []
        self.riassunto = ""  # messaggi vecchi già riassunti (vuoto senza nodo riassunto)
        self.preferenze: Preferenze | None = self._leggi()

    def _aggiorna(self, esito: EsitoTurno) -> EsitoTurno:
        # Cronologia e riassunto cambiano solo se il turno riesce (le eccezioni passano prima).
        self.cronologia = esito.messaggi
        self.riassunto = esito.riassunto
        return esito

    def chiedi(self, testo: str) -> str:
        """Invia una domanda scritta dall'utente e restituisce il testo della risposta finale."""
        return self._aggiorna(self._agente.messaggio(
            testo, self.cronologia, self.riassunto, self.preferenze)).risposta

    def chiedi_messaggi(self, messaggi: list[BaseMessage]) -> str:
        """Aggiunge messaggi già pronti e invoca il grafo (usato dai test e dalle prove reali)."""
        return self._aggiorna(self._agente.turno(
            messaggi, self.cronologia, self.riassunto, self.preferenze)).risposta

    def elenco_prompt(self) -> list[InfoPrompt]:
        return self._agente.elenco_prompt()

    def usa_prompt(self, nome: str, argomenti: dict[str, str]) -> EsitoTurno:
        """Prompt controllato e composto dall'agente; ErrorePrompt se non valido."""
        return self._aggiorna(self._agente.prompt(
            nome, argomenti, self.cronologia, self.riassunto, self.preferenze))

    def nuova(self) -> None:
        """Avvia una nuova conversazione: azzera cronologia e riassunto, rilegge le preferenze."""
        self.cronologia = []
        self.riassunto = ""
        self.preferenze = self._leggi()

    def _leggi(self) -> Preferenze | None:
        return self._leggi_preferenze() if self._leggi_preferenze is not None else None
