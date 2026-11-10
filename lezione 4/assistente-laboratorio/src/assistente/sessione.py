"""Sessione di conversazione: cronologia in memoria e invocazione del grafo."""
from langchain_core.messages import BaseMessage, HumanMessage

from assistente.grafo import limite_ricorsione
from assistente.preferenze import LettorePreferenze, Preferenze


class Sessione:
    """Tiene la cronologia della conversazione per la durata del processo."""

    def __init__(self, grafo, max_passaggi: int, max_revisioni: int = 0,
                 leggi_preferenze: LettorePreferenze | None = None):
        """`leggi_preferenze` (host): letto qui, prima della prima domanda, e da `nuova()`."""
        self._grafo = grafo
        self._leggi_preferenze = leggi_preferenze
        self._config = {"recursion_limit": limite_ricorsione(max_passaggi, max_revisioni)}
        self.cronologia: list[BaseMessage] = []
        self.riassunto = ""  # messaggi vecchi già riassunti (vuoto senza nodo riassunto)
        self.preferenze: Preferenze | None = self._leggi()

    def chiedi(self, testo: str) -> str:
        """Invia una domanda e restituisce il testo della risposta finale."""
        return self.chiedi_messaggi([HumanMessage(testo)])

    def chiedi_messaggi(self, messaggi: list[BaseMessage]) -> str:
        """Aggiunge i messaggi (una domanda, o quelli di un prompt) e invoca il grafo.

        Cronologia e riassunto cambiano solo se l'invocazione riesce; le eccezioni passano
        al chiamante.
        """
        uscita = self._grafo.invoke(
            {"messages": [*self.cronologia, *messaggi], "passaggi": 0, "revisioni": 0,
             "riassunto": self.riassunto, "preferenze": self.preferenze},
            config=self._config)
        self.cronologia = list(uscita["messages"])
        self.riassunto = uscita.get("riassunto", "")
        return self.cronologia[-1].content

    def nuova(self) -> None:
        """Avvia una nuova conversazione: azzera cronologia e riassunto, rilegge le preferenze."""
        self.cronologia = []
        self.riassunto = ""
        self.preferenze = self._leggi()

    def _leggi(self) -> Preferenze | None:
        return self._leggi_preferenze() if self._leggi_preferenze is not None else None
