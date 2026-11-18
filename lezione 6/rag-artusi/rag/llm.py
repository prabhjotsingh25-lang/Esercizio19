"""Chiamate al modello chat di LM Studio con output vincolato da JSON schema (lezione 8, es. 3).

Usate solo dal server di ricerca per riscrittura e reranking: compiti brevi, temperatura 0,
ragionamento disattivato (`reasoning_effort`) se configurato.
"""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from rag.config import Config


class ErroreLLM(Exception):
    """Servizio non raggiungibile, timeout o risposta HTTP diversa da 200."""


class RispostaNonValida(Exception):
    """Risposta arrivata ma il contenuto non è un oggetto JSON."""


class LLM(Protocol):
    chiamate: int

    def json(self, sistema: str, utente: str, schema: dict, nome: str) -> dict: ...


class LLMLMStudio:
    def __init__(self, config: Config, client: httpx.Client | None = None):
        self.config = config
        self.url = f"{config.lmstudio_url.rstrip('/')}/chat/completions"
        self._client = client or httpx.Client(timeout=config.llm_timeout)
        self.chiamate = 0

    def _corpo(self, sistema: str, utente: str, schema: dict, nome: str) -> dict:
        c = self.config
        corpo = {
            "model": c.modello_chat,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": utente}],
            "temperature": c.llm_temperatura,
            "max_tokens": c.llm_max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {"name": nome, "strict": True, "schema": schema}},
        }
        if c.llm_seed is not None:
            corpo["seed"] = c.llm_seed
        if c.llm_reasoning_effort:
            corpo["reasoning_effort"] = c.llm_reasoning_effort
        return corpo

    def json(self, sistema: str, utente: str, schema: dict, nome: str) -> dict:
        self.chiamate += 1
        try:
            risposta = self._client.post(self.url, json=self._corpo(sistema, utente, schema, nome))
        except httpx.TimeoutException:
            raise ErroreLLM(f"timeout dopo {self.config.llm_timeout} s") from None
        except httpx.HTTPError as e:
            raise ErroreLLM(f"connessione fallita ({type(e).__name__})") from None
        if risposta.status_code != 200:
            raise ErroreLLM(f"HTTP {risposta.status_code}: {' '.join(risposta.text.split())[:200]}")
        try:
            contenuto = risposta.json()["choices"][0]["message"]["content"]
            dati = json.loads(contenuto)
        except (ValueError, KeyError, IndexError, TypeError):
            raise RispostaNonValida("contenuto non JSON") from None
        if not isinstance(dati, dict):
            raise RispostaNonValida("il JSON non è un oggetto")
        return dati
