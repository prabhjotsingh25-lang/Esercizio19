"""Doppioni per i test: istante fisso, orologio controllato e modello finto."""
from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from assistente.strumenti import crea_strumento_orologio

ISTANTE = datetime(2026, 10, 26, 9, 30, 5, tzinfo=timezone.utc)
orologio = crea_strumento_orologio(lambda: ISTANTE)


class ModelloFinto(BaseChatModel):
    """Modello che restituisce risposte preparate e registra i messaggi ricevuti."""

    risposte: list[AIMessage]
    ricevuti: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "modello-finto"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ModelloFinto":
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.ricevuti.append(list(messages))
        if not self.risposte:
            raise IndexError("ModelloFinto: risposte esaurite")
        return ChatResult(generations=[ChatGeneration(message=self.risposte.pop(0))])


def chiamata(fuso: str, id: str) -> AIMessage:
    """Risposta del modello che richiede `ora_corrente` per il fuso indicato."""
    return AIMessage("", tool_calls=[
        {"name": "ora_corrente", "args": {"fuso_orario": fuso}, "id": id}])
