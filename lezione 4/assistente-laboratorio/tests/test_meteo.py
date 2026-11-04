"""Test di meteo_api con un Open-Meteo finto (httpx.MockTransport): nessun accesso a internet."""
import httpx
import pytest
from finti import PREVISIONE, meteo_finto

from assistente.meteo import crea_strumento_meteo, meteo

ATTESO_ROMA = (
    "Meteo per Roma (Lazio, Italia), ora locale 2026-11-04 12:00:\n"
    "adesso 18 °C, poco nuvoloso, vento 12 km/h, umidità 60%.\n"
    "Previsione:\n"
    "- 2026-11-04 (oggi): min 11 °C, max 19 °C, pioggia 0.0 mm, poco nuvoloso\n"
    "- 2026-11-05 (domani): min 12 °C, max 17 °C, pioggia 4.2 mm, pioggia debole\n"
    "- 2026-11-06: min 10 °C, max 16 °C, pioggia 0.5 mm, coperto"
)


def _guasto(eccezione):
    def gestisci(richiesta):
        raise eccezione("guasto simulato", request=richiesta)
    return httpx.MockTransport(gestisci)


def test_citta_valida():
    assert meteo("Roma", trasporto=meteo_finto()) == ATTESO_ROMA


def test_parametri_delle_richieste():
    richieste = []
    meteo("  Roma ", trasporto=meteo_finto(richieste=richieste))
    geo, prev = richieste
    assert geo.url.path == "/v1/search"
    assert dict(geo.url.params) == {"name": "Roma", "count": "1", "language": "it", "format": "json"}
    assert prev.url.path == "/v1/forecast"
    assert prev.url.params["latitude"] == "41.89" and prev.url.params["longitude"] == "12.51"
    assert prev.url.params["timezone"] == "auto" and prev.url.params["forecast_days"] == "3"


def test_luogo_con_paese_usa_solo_la_citta():
    richieste = []
    meteo("Roma, Italia", trasporto=meteo_finto(richieste=richieste))
    assert richieste[0].url.params["name"] == "Roma"


def test_regione_mancante():
    geo = {"results": [{"name": "Monaco", "latitude": 43.7, "longitude": 7.4, "country": "Monaco"}]}
    assert meteo("Monaco", trasporto=meteo_finto(geo=geo)).startswith(
        "Meteo per Monaco (Monaco), ora locale")


@pytest.mark.parametrize("luogo", ["", "   ", "x" * 101])
def test_luogo_non_valido_senza_chiamate(luogo):
    richieste = []
    assert meteo(luogo, trasporto=meteo_finto(richieste=richieste)) == (
        "Errore: indica il nome di una città (massimo 100 caratteri).")
    assert richieste == []


@pytest.mark.parametrize("geo", [{}, {"results": []}])
def test_luogo_non_trovato(geo):
    assert meteo("Xyzabc", trasporto=meteo_finto(geo=geo)) == "Errore: luogo 'Xyzabc' non trovato."


@pytest.mark.parametrize("eccezione", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError])
def test_servizio_non_raggiungibile(eccezione):
    assert meteo("Roma", trasporto=_guasto(eccezione)) == (
        "Errore: servizio meteo non raggiungibile, riprova più tardi.")


@pytest.mark.parametrize("stato", [429, 500, 503])
def test_servizio_in_errore(stato):
    trasporto = httpx.MockTransport(lambda richiesta: httpx.Response(stato))
    assert meteo("Roma", trasporto=trasporto) == (
        "Errore: servizio meteo non raggiungibile, riprova più tardi.")


def _rovinata(**modifiche):
    previsione = {"current": dict(PREVISIONE["current"]), "daily": dict(PREVISIONE["daily"])}
    for chiave, valore in modifiche.items():
        sezione, campo = chiave.split("__")
        if valore is None and campo == "tutto":
            del previsione[sezione]
        else:
            previsione[sezione][campo] = valore
    return previsione


@pytest.mark.parametrize("previsione", [
    _rovinata(current__tutto=None),
    _rovinata(daily__tutto=None),
    _rovinata(current__temperature_2m=None),
    _rovinata(daily__temperature_2m_max=[19.2, None, 16.4]),
    _rovinata(daily__precipitation_sum=[0.0]),
    _rovinata(daily__time=[]),
    _rovinata(current__weather_code="due"),
])
def test_previsione_non_valida(previsione):
    assert meteo("Roma", trasporto=meteo_finto(previsione=previsione)) == (
        "Errore: risposta del servizio meteo non valida.")


def test_geocoding_non_valido():
    geo = {"results": [{"name": "Roma"}]}  # senza coordinate
    assert meteo("Roma", trasporto=meteo_finto(geo=geo)) == (
        "Errore: risposta del servizio meteo non valida.")


def test_risposta_non_json():
    trasporto = httpx.MockTransport(lambda richiesta: httpx.Response(200, text="<html>"))
    assert meteo("Roma", trasporto=trasporto) == "Errore: risposta del servizio meteo non valida."


def test_codice_meteo_sconosciuto():
    previsione = _rovinata(current__weather_code=42)
    assert "adesso 18 °C, condizioni non classificate (codice 42)," in meteo(
        "Roma", trasporto=meteo_finto(previsione=previsione))


def test_temperature_negative_arrotondate():
    previsione = _rovinata(current__temperature_2m=-0.3,
                           daily__temperature_2m_min=[-4.6, 12.4, 9.6])
    testo = meteo("Roma", trasporto=meteo_finto(previsione=previsione))
    assert "adesso 0 °C," in testo and "min -5 °C" in testo


def test_strumento_langchain():
    strumento = crea_strumento_meteo(meteo_finto())
    assert strumento.name == "meteo_api"
    schema = strumento.args_schema.model_json_schema()
    assert schema["required"] == ["luogo"]
    assert set(schema["properties"]) == {"luogo"}
    assert "Open-Meteo" in strumento.description
    assert strumento.invoke({"luogo": "Roma"}) == ATTESO_ROMA
