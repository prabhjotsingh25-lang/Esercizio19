"""Strumento meteo_api: meteo attuale e previsione di 3 giorni da Open-Meteo (senza chiave API).

Due richieste: il geocoding trasforma il nome della città in coordinate, la previsione
restituisce condizioni attuali e giornaliere nell'ora locale del luogo. In caso di problemi
lo strumento restituisce un errore leggibile e non inventa dati.
"""
from typing import Any

import httpx
from langchain_core.tools import BaseTool, StructuredTool

URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
URL_PREVISIONE = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDI = 10.0
MAX_LUOGO = 100
GIORNI = 3

ERRORE_LUOGO = f"Errore: indica il nome di una città (massimo {MAX_LUOGO} caratteri)."
ERRORE_RETE = "Errore: servizio meteo non raggiungibile, riprova più tardi."
ERRORE_RISPOSTA = "Errore: risposta del servizio meteo non valida."

# Codici meteo WMO usati da Open-Meteo.
_CONDIZIONI = {
    0: "sereno", 1: "prevalentemente sereno", 2: "poco nuvoloso", 3: "coperto",
    45: "nebbia", 48: "nebbia con brina",
    51: "pioggerella debole", 53: "pioggerella moderata", 55: "pioggerella intensa",
    56: "pioggerella gelata debole", 57: "pioggerella gelata intensa",
    61: "pioggia debole", 63: "pioggia moderata", 65: "pioggia forte",
    66: "pioggia gelata debole", 67: "pioggia gelata forte",
    71: "neve debole", 73: "neve moderata", 75: "neve forte", 77: "granelli di neve",
    80: "rovesci deboli", 81: "rovesci moderati", 82: "rovesci violenti",
    85: "rovesci di neve deboli", 86: "rovesci di neve forti",
    95: "temporale", 96: "temporale con grandine debole", 99: "temporale con grandine forte",
}
_ETICHETTE = {0: " (oggi)", 1: " (domani)"}


class _RispostaNonValida(Exception):
    """La risposta di Open-Meteo non ha la forma attesa."""


def _condizione(codice: Any) -> str:
    if isinstance(codice, bool) or not isinstance(codice, int):
        raise _RispostaNonValida
    return _CONDIZIONI.get(codice, f"condizioni non classificate (codice {codice})")


def _numero(valore: Any) -> float:
    if isinstance(valore, bool) or not isinstance(valore, (int, float)):
        raise _RispostaNonValida
    return float(valore)


def _intero(valore: Any) -> int:
    return int(round(_numero(valore))) + 0  # "+ 0" evita "-0"


def _scarica(client: httpx.Client, url: str, parametri: dict[str, Any]) -> dict:
    risposta = client.get(url, params=parametri)
    risposta.raise_for_status()
    try:
        dati = risposta.json()
    except ValueError as errore:
        raise _RispostaNonValida from errore
    if not isinstance(dati, dict):
        raise _RispostaNonValida
    return dati


def _nome_luogo(risultato: dict) -> str:
    dettagli = []
    for parte in (risultato.get("admin1"), risultato.get("country")):
        if isinstance(parte, str) and parte and parte not in dettagli:
            dettagli.append(parte)
    nome = risultato.get("name")
    if not isinstance(nome, str) or not nome:
        raise _RispostaNonValida
    return f"{nome} ({', '.join(dettagli)})" if dettagli else nome


def _testo(luogo: str, previsione: dict) -> str:
    adesso = previsione.get("current")
    giornaliera = previsione.get("daily")
    if not isinstance(adesso, dict) or not isinstance(giornaliera, dict):
        raise _RispostaNonValida
    ora = adesso.get("time")
    if not isinstance(ora, str):
        raise _RispostaNonValida
    righe = [f"Meteo per {luogo}, ora locale {ora.replace('T', ' ')}:",
             f"adesso {_intero(adesso.get('temperature_2m'))} °C, "
             f"{_condizione(adesso.get('weather_code'))}, "
             f"vento {_intero(adesso.get('wind_speed_10m'))} km/h, "
             f"umidità {_intero(adesso.get('relative_humidity_2m'))}%.",
             "Previsione:"]
    colonne = [giornaliera.get(nome) for nome in ("time", "weather_code", "temperature_2m_min",
                                                   "temperature_2m_max", "precipitation_sum")]
    if not all(isinstance(c, list) and len(c) == GIORNI for c in colonne):
        raise _RispostaNonValida
    for indice, (giorno, codice, minima, massima, pioggia) in enumerate(zip(*colonne)):
        if not isinstance(giorno, str):
            raise _RispostaNonValida
        righe.append(f"- {giorno}{_ETICHETTE.get(indice, '')}: min {_intero(minima)} °C, "
                     f"max {_intero(massima)} °C, pioggia {_numero(pioggia):.1f} mm, "
                     f"{_condizione(codice)}")
    return "\n".join(righe)


def meteo(luogo: str, trasporto: httpx.BaseTransport | None = None) -> str:
    """Meteo attuale e previsione di 3 giorni per `luogo`, oppure un messaggio di errore.

    `trasporto` è iniettabile per i test (httpx.MockTransport), così non serve internet.
    """
    citta = luogo.split(",")[0].strip()  # "Roma, Italia": il geocoding vuole solo la città
    if not citta or len(luogo) > MAX_LUOGO:
        return ERRORE_LUOGO
    try:
        with httpx.Client(transport=trasporto, timeout=TIMEOUT_SECONDI) as client:
            geo = _scarica(client, URL_GEOCODING,
                           {"name": citta, "count": 1, "language": "it", "format": "json"})
            risultati = geo.get("results") or []
            if not isinstance(risultati, list):
                raise _RispostaNonValida
            if not risultati:
                return f"Errore: luogo '{citta}' non trovato."
            primo = risultati[0]
            if not isinstance(primo, dict):
                raise _RispostaNonValida
            latitudine, longitudine = _numero(primo.get("latitude")), _numero(primo.get("longitude"))
            previsione = _scarica(client, URL_PREVISIONE, {
                "latitude": latitudine, "longitude": longitudine,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto", "forecast_days": GIORNI,
            })
            return _testo(_nome_luogo(primo), previsione)
    except (httpx.TransportError, httpx.HTTPStatusError):
        return ERRORE_RETE
    except _RispostaNonValida:
        return ERRORE_RISPOSTA


def crea_strumento_meteo(trasporto: httpx.BaseTransport | None = None) -> BaseTool:
    """Costruisce lo strumento `meteo_api`; `trasporto` è iniettabile per i test."""

    def meteo_api(luogo: str) -> str:
        return meteo(luogo, trasporto)

    return StructuredTool.from_function(
        func=meteo_api,
        name="meteo_api",
        description=("Restituisce il meteo attuale e la previsione di oggi, domani e dopodomani "
                     "per una città, con i dati del servizio Open-Meteo. Usala quando l'utente "
                     "chiede che tempo fa o farà in un luogo. luogo: solo il nome della città, "
                     "per esempio Roma."),
    )
