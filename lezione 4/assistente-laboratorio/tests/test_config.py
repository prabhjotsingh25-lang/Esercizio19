import pytest

from assistente.config import Configurazione, ErroreConfigurazione, carica_configurazione


def test_configurazione_completa():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": "http://x:1/v1", "LMSTUDIO_MODEL": "m",
                               "MAX_PASSAGGI_STRUMENTO": "5", "LOG_LEVEL": "debug"})
    assert c == Configurazione("http://x:1/v1", "m", 5, "DEBUG")


def test_default_facoltativi():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m"})
    assert (c.max_passaggi, c.log_level) == (3, "INFO")


@pytest.mark.parametrize("manca", ["LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL"])
def test_variabile_obbligatoria_mancante_o_vuota(manca):
    env = {"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m"}
    for valore in (None, "  "):
        e = dict(env)
        e.pop(manca) if valore is None else e.__setitem__(manca, valore)
        with pytest.raises(ErroreConfigurazione, match=manca):
            carica_configurazione(e)


@pytest.mark.parametrize("valore", ["zero", "0", "-1"])
def test_max_passaggi_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSAGGI_STRUMENTO"):
        carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m",
                               "MAX_PASSAGGI_STRUMENTO": valore})


@pytest.mark.parametrize("valore", ["VERBOSE", "debugg"])
def test_log_level_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m",
                               "LOG_LEVEL": valore})


def test_variante_di_default_locale():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m"})
    assert (c.variante, c.strumenti_http_url) == ("locale", None)


def test_variante_http_con_indirizzo():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m",
                               "VARIANTE_STRUMENTI": " HTTP ",
                               "STRUMENTI_HTTP_URL": "http://localhost:8001"})
    assert (c.variante, c.strumenti_http_url) == ("http", "http://localhost:8001")


@pytest.mark.parametrize("valore", ["mcp", "remota", "01"])
def test_variante_non_valida(valore):
    with pytest.raises(ErroreConfigurazione, match="VARIANTE_STRUMENTI"):
        carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m",
                               "VARIANTE_STRUMENTI": valore})


@pytest.mark.parametrize("indirizzo", [None, "  "])
def test_variante_http_senza_indirizzo(indirizzo):
    env = {"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m", "VARIANTE_STRUMENTI": "http"}
    if indirizzo is not None:
        env["STRUMENTI_HTTP_URL"] = indirizzo
    with pytest.raises(ErroreConfigurazione, match="STRUMENTI_HTTP_URL"):
        carica_configurazione(env)
