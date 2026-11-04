"""Doppioni per i test: istante fisso, orologio controllato e modello finto."""
from datetime import datetime, timezone
from typing import Any

import httpx
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


# Open-Meteo finto, condiviso dai test di meteo_api e dal confronto fra varianti.
GEO_ROMA = {"results": [{"name": "Roma", "latitude": 41.89, "longitude": 12.51,
                         "country": "Italia", "admin1": "Lazio", "timezone": "Europe/Rome"}]}
PREVISIONE = {
    "current": {"time": "2026-11-04T12:00", "temperature_2m": 18.3, "relative_humidity_2m": 60,
                "weather_code": 2, "wind_speed_10m": 12.1},
    "daily": {"time": ["2026-11-04", "2026-11-05", "2026-11-06"],
              "weather_code": [2, 61, 3],
              "temperature_2m_max": [19.2, 17.0, 16.4],
              "temperature_2m_min": [11.0, 12.4, 9.6],
              "precipitation_sum": [0.0, 4.2, 0.5]},
}


def meteo_finto(geo=GEO_ROMA, previsione=PREVISIONE, richieste=None) -> httpx.MockTransport:
    """Risponde a geocoding e previsione di Open-Meteo senza internet; annota le richieste."""
    def gestisci(richiesta: httpx.Request) -> httpx.Response:
        if richieste is not None:
            richieste.append(richiesta)
        if richiesta.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json=geo)
        if richiesta.url.host == "api.open-meteo.com":
            return httpx.Response(200, json=previsione)
        return httpx.Response(404)
    return httpx.MockTransport(gestisci)
