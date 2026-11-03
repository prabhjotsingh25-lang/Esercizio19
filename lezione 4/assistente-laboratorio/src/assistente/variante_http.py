"""Wrapper HTTP (variante 02): stesse definizioni del catalogo, esecuzione tramite il servizio."""
import httpx
from langchain_core.tools import BaseTool, StructuredTool

TIMEOUT_SECONDI = 10


def _chiama(client: httpx.Client, base_url: str, nome: str, argomenti: dict) -> str:
    """Esegue lo strumento sul servizio; ogni guasto diventa un errore leggibile dal modello."""
    try:
        risposta = client.post(f"/strumenti/{nome}", json=argomenti)
    except httpx.TimeoutException:
        return f"Errore: il servizio strumenti non ha risposto entro {TIMEOUT_SECONDI} secondi."
    except httpx.RequestError:
        return f"Errore: servizio strumenti non raggiungibile su {base_url}."
    if risposta.status_code == 404:
        return f"Errore: strumento sconosciuto al servizio: {nome}."
    if risposta.status_code == 422:
        try:
            dettagli = "; ".join(f"{d['campo']}: {d['messaggio']}" for d in risposta.json()["detail"])
        except (ValueError, KeyError, TypeError):
            dettagli = "dettagli non disponibili"
        return f"Errore: argomenti rifiutati dal servizio: {dettagli}."
    if risposta.status_code != 200:
        return f"Errore: il servizio strumenti ha risposto con il codice {risposta.status_code}."
    try:
        risultato = risposta.json()["risultato"]
    except (ValueError, KeyError, TypeError):
        risultato = None
    if not isinstance(risultato, str):
        return "Errore: risposta del servizio strumenti non valida."
    return risultato


def crea_strumenti_http(base_url: str, definizioni: list[BaseTool],
                        client: httpx.Client | None = None) -> list[BaseTool]:
    """Uno strumento remoto per ogni definizione: stesso nome, descrizione e schema.

    Gli argomenti sono validati con lo schema prima della chiamata, come in locale.
    `client` è iniettabile per i test (TestClient o MockTransport).
    """
    client = client or httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDI)

    def remoto(definizione: BaseTool) -> BaseTool:
        def esegui(**argomenti) -> str:
            return _chiama(client, base_url, definizione.name, argomenti)

        return StructuredTool.from_function(func=esegui, name=definizione.name,
                                            description=definizione.description,
                                            args_schema=definizione.args_schema)

    return [remoto(d) for d in definizioni]
