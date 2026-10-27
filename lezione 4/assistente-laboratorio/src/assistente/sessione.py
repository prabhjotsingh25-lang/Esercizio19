"""Sessione di conversazione: cronologia in memoria e invocazione del grafo."""
from langchain_core.messages import BaseMessage, HumanMessage

from assistente.grafo import limite_ricorsione


class Sessione:
    """Tiene la cronologia della conversazione per la durata del processo."""

    def __init__(self, grafo, max_passaggi: int):
        self._grafo = grafo
        self._config = {"recursion_limit": limite_ricorsione(max_passaggi)}
        self.cronologia: list[BaseMessage] = []

    def chiedi(self, testo: str) -> str:
        """Invia una domanda e restituisce il testo della risposta finale.

        La cronologia cambia solo se l'invocazione riesce; le eccezioni passano al chiamante.
        """
        uscita = self._grafo.invoke(
            {"messages": [*self.cronologia, HumanMessage(testo)], "passaggi": 0},
            config=self._config)
        self.cronologia = list(uscita["messages"])
        return self.cronologia[-1].content

    def nuova(self) -> None:
        """Avvia una nuova conversazione azzerando la cronologia."""
        self.cronologia = []
