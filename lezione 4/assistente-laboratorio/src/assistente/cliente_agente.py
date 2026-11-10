"""Client dell'API dell'agente (CLI con AGENTE_URL): stessa interfaccia della `Sessione`.

L'agente è senza stato: la sessione remota conserva cronologia (solo utente e assistente),
riassunto e preferenze e li manda a ogni richiesta.
"""
from dataclasses import dataclass, field

import httpx

from assistente.preferenze import LettorePreferenze, Preferenze
from assistente.prompt import ArgomentoPrompt, ErrorePrompt, InfoPrompt, PromptNonDisponibili

TIMEOUT_SECONDI = 900  # il modello locale può impiegare più di 7 minuti per un turno
TIMEOUT_CONNESSIONE = 10  # un agente spento si vede subito

# Percorsi dell'agente usati dai client: devono esistere in docs/openapi-agente.json (test).
MESSAGGI = ("POST", "/messaggi")
PROMPT = ("POST", "/prompt")
ELENCO_PROMPT = ("GET", "/prompt")
STATO = ("GET", "/stato")
PERCORSI_USATI = (MESSAGGI, PROMPT, ELENCO_PROMPT, STATO)


class ErroreAgente(Exception):
    """Servizio, modello o strumenti non disponibili: il messaggio è per l'utente.

    `codice` è il codice HTTP da restituire a chi chiama (503 agente non raggiungibile, 504
    nessuna risposta entro il timeout, altrimenti quello dell'agente); `dettaglio` il motivo.
    """

    def __init__(self, messaggio: str, codice: int = 503, dettaglio: str | None = None):
        super().__init__(messaggio)
        self.codice = codice
        self.dettaglio = dettaglio or messaggio


@dataclass
class EsitoRemoto:
    risposta: str
    strumenti: list[dict]
    prompt: list[str] = field(default_factory=list)


class ClienteAgente:
    """Chiamate HTTP all'agente; `client` iniettabile per i test (per esempio un TestClient)."""

    def __init__(self, url: str, client: httpx.Client | None = None,
                 timeout: float = TIMEOUT_SECONDI):
        self._url = url
        self._timeout = timeout
        self._client = client or httpx.Client(
            base_url=url, timeout=httpx.Timeout(timeout, connect=TIMEOUT_CONNESSIONE))

    def _richiesta(self, metodo: str, percorso: str, **opzioni) -> httpx.Response:
        try:
            return self._client.request(metodo, percorso, **opzioni)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            messaggio = f"agente non raggiungibile su {self._url}"
            raise ErroreAgente(f"Non riesco a raggiungere l'agente su {self._url}: controlla "
                               "che il servizio sia avviato.", 503, messaggio) from None
        except httpx.TimeoutException:
            messaggio = f"l'agente non ha risposto entro {self._timeout:g} s"
            raise ErroreAgente(f"Errore dell'agente: {messaggio}.", 504, messaggio) from None
        except httpx.TransportError as errore:
            messaggio = f"agente non raggiungibile su {self._url} ({errore})"
            raise ErroreAgente(f"Non riesco a raggiungere l'agente su {self._url}: controlla "
                               "che il servizio sia avviato.", 503, messaggio) from None

    def chiama(self, metodo: str, percorso: str, **opzioni) -> object:
        """JSON della risposta; 422 dei prompt → ErrorePrompt, 503 dei prompt →
        PromptNonDisponibili, altri errori → ErroreAgente con il messaggio del servizio."""
        risposta = self._richiesta(metodo, percorso, **opzioni)
        if risposta.is_success:
            return risposta.json()
        try:
            dettaglio = risposta.json().get("detail")
        except ValueError:
            dettaglio = risposta.text
        if isinstance(dettaglio, str) and dettaglio.startswith("prompt non valido: "):
            raise ErrorePrompt(dettaglio.removeprefix("prompt non valido: "))
        if isinstance(dettaglio, str) and dettaglio.startswith("prompt non disponibili: "):
            raise PromptNonDisponibili(dettaglio.removeprefix("prompt non disponibili: "))
        raise ErroreAgente(f"Errore dell'agente ({risposta.status_code}): {dettaglio}",
                           risposta.status_code, f"agente: {dettaglio}")


class SessioneRemota:
    """Come `Sessione`, ma ogni turno è una richiesta all'API dell'agente."""

    def __init__(self, cliente: ClienteAgente, leggi_preferenze: LettorePreferenze | None = None):
        self._cliente = cliente
        self._leggi_preferenze = leggi_preferenze
        self.cronologia: list[dict] = []
        self.riassunto = ""
        self.preferenze: Preferenze | None = self._leggi()

    def _contesto(self) -> dict:
        contesto = {"cronologia": self.cronologia, "riassunto": self.riassunto}
        if self.preferenze is not None:
            contesto["preferenze"] = self.preferenze.model_dump()
        return contesto

    def _aggiorna(self, corpo: dict) -> EsitoRemoto:
        self.cronologia, self.riassunto = corpo["cronologia"], corpo["riassunto"]
        return EsitoRemoto(corpo["risposta"], corpo["strumenti"], corpo.get("prompt", []))

    def chiedi(self, testo: str) -> str:
        corpo = self._cliente.chiama(*MESSAGGI, json={"testo": testo, **self._contesto()})
        return self._aggiorna(corpo).risposta

    def usa_prompt(self, nome: str, argomenti: dict[str, str]) -> EsitoRemoto:
        corpo = self._cliente.chiama(*PROMPT, json={
            "nome": nome, "argomenti": argomenti, **self._contesto()})
        return self._aggiorna(corpo)

    def elenco_prompt(self) -> list[InfoPrompt]:
        return [InfoPrompt(p["nome"], p["descrizione"],
                           tuple(ArgomentoPrompt(a["nome"], a["descrizione"], a["obbligatorio"])
                                 for a in p["argomenti"]))
                for p in self._cliente.chiama(*ELENCO_PROMPT)]

    def nuova(self) -> None:
        self.cronologia, self.riassunto = [], ""
        self.preferenze = self._leggi()

    def _leggi(self) -> Preferenze | None:
        return self._leggi_preferenze() if self._leggi_preferenze is not None else None
