import pytest

from assistente.config import Configurazione, ErroreConfigurazione, carica_configurazione

BASE = {"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m", "AMBITO_AGENTE": "a"}


def test_configurazione_completa():
    c = carica_configurazione({**BASE, "LMSTUDIO_BASE_URL": "http://x:1/v1",
                               "MAX_PASSAGGI_STRUMENTO": "5", "LOG_LEVEL": "debug"})
    assert c == Configurazione("http://x:1/v1", "m", 5, "DEBUG", ambito="a")


def test_default_facoltativi():
    c = carica_configurazione(dict(BASE))
    assert (c.max_passaggi, c.log_level) == (3, "INFO")


@pytest.mark.parametrize("manca", ["LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "AMBITO_AGENTE"])
def test_variabile_obbligatoria_mancante_o_vuota(manca):
    env = dict(BASE)
    for valore in (None, "  "):
        e = dict(env)
        e.pop(manca) if valore is None else e.__setitem__(manca, valore)
        with pytest.raises(ErroreConfigurazione, match=manca):
            carica_configurazione(e)


@pytest.mark.parametrize("valore", ["zero", "0", "-1"])
def test_max_passaggi_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSAGGI_STRUMENTO"):
        carica_configurazione({**BASE,
                               "MAX_PASSAGGI_STRUMENTO": valore})


@pytest.mark.parametrize("valore", ["VERBOSE", "debugg"])
def test_log_level_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({**BASE,
                               "LOG_LEVEL": valore})


def test_variante_di_default_locale():
    c = carica_configurazione(dict(BASE))
    assert (c.variante, c.strumenti_http_url) == ("locale", None)


def test_variante_http_con_indirizzo():
    c = carica_configurazione({**BASE,
                               "VARIANTE_STRUMENTI": " HTTP ",
                               "STRUMENTI_HTTP_URL": "http://localhost:8001"})
    assert (c.variante, c.strumenti_http_url) == ("http", "http://localhost:8001")


@pytest.mark.parametrize("valore", ["grpc", "remota", "01"])
def test_variante_non_valida(valore):
    with pytest.raises(ErroreConfigurazione, match="VARIANTE_STRUMENTI"):
        carica_configurazione({**BASE,
                               "VARIANTE_STRUMENTI": valore})


@pytest.mark.parametrize("indirizzo", [None, "  "])
def test_variante_http_senza_indirizzo(indirizzo):
    env = {**BASE, "VARIANTE_STRUMENTI": "http"}
    if indirizzo is not None:
        env["STRUMENTI_HTTP_URL"] = indirizzo
    with pytest.raises(ErroreConfigurazione, match="STRUMENTI_HTTP_URL"):
        carica_configurazione(env)


def test_variante_mcp_con_indirizzo():
    c = carica_configurazione({**BASE,
                               "VARIANTE_STRUMENTI": "MCP",
                               "STRUMENTI_MCP_URL": "http://localhost:8002/mcp"})
    assert (c.variante, c.strumenti_mcp_url, c.strumenti_http_url) == (
        "mcp", "http://localhost:8002/mcp", None)


@pytest.mark.parametrize("indirizzo", [None, "  "])
def test_variante_mcp_senza_indirizzo(indirizzo):
    env = {**BASE, "VARIANTE_STRUMENTI": "mcp",
           "STRUMENTI_HTTP_URL": "http://localhost:8001"}
    if indirizzo is not None:
        env["STRUMENTI_MCP_URL"] = indirizzo
    with pytest.raises(ErroreConfigurazione, match="STRUMENTI_MCP_URL"):
        carica_configurazione(env)


def test_ambito_letto_e_ripulito():
    c = carica_configurazione({**BASE, "AMBITO_AGENTE": "  orari e meteo  "})
    assert c.ambito == "orari e meteo"


def test_max_revisioni_default_e_valore():
    assert carica_configurazione(dict(BASE)).max_revisioni == 1
    assert carica_configurazione({**BASE, "MAX_REVISIONI": " 2 "}).max_revisioni == 2


@pytest.mark.parametrize("valore", ["due", "0", "-1"])
def test_max_revisioni_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_REVISIONI"):
        carica_configurazione({**BASE, "MAX_REVISIONI": valore})
