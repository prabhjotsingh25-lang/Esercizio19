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


def test_riassunto_default_e_valori():
    c = carica_configurazione(dict(BASE))
    assert (c.soglia_riassunto, c.messaggi_recenti) == (20, 6)
    c = carica_configurazione({**BASE, "SOGLIA_RIASSUNTO": " 6 ", "MESSAGGI_RECENTI": "2"})
    assert (c.soglia_riassunto, c.messaggi_recenti) == (6, 2)


@pytest.mark.parametrize("nome", ["SOGLIA_RIASSUNTO", "MESSAGGI_RECENTI"])
@pytest.mark.parametrize("valore", ["dieci", "0", "-1"])
def test_riassunto_non_intero_positivo(nome, valore):
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_configurazione({**BASE, nome: valore})


@pytest.mark.parametrize("soglia, recenti", [("6", "6"), ("6", "7"), ("3", "6")])
def test_messaggi_recenti_devono_essere_meno_della_soglia(soglia, recenti):
    with pytest.raises(ErroreConfigurazione, match="MESSAGGI_RECENTI.*SOGLIA_RIASSUNTO"):
        carica_configurazione({**BASE, "SOGLIA_RIASSUNTO": soglia, "MESSAGGI_RECENTI": recenti})


def test_file_delle_preferenze_default_e_valore():
    assert carica_configurazione(dict(BASE)).preferenze_file == "preferenze.json"
    c = carica_configurazione({**BASE, "PREFERENZE_FILE": " C:/dati/pref.json "})
    assert c.preferenze_file == "C:/dati/pref.json"


def test_agente_http_default_e_valori():
    c = carica_configurazione(dict(BASE))
    assert (c.agente_host, c.agente_porta, c.agente_url) == ("127.0.0.1", 8000, None)
    c = carica_configurazione({**BASE, "AGENTE_HOST": "0.0.0.0", "AGENTE_PORTA": "8100",
                               "AGENTE_URL": " http://127.0.0.1:8100/ "})
    assert (c.agente_host, c.agente_porta, c.agente_url) == ("0.0.0.0", 8100, "http://127.0.0.1:8100")


@pytest.mark.parametrize("valore", ["zero", "0", "70000"])
def test_agente_porta_non_valida(valore):
    with pytest.raises(ErroreConfigurazione, match="AGENTE_PORTA"):
        carica_configurazione({**BASE, "AGENTE_PORTA": valore})


def test_backend_default_e_valori():
    c = carica_configurazione(dict(BASE))
    assert (c.database_url, c.backend_host, c.backend_porta, c.agente_timeout) == (
        None, "127.0.0.1", 8080, 900)
    c = carica_configurazione({**BASE, "DATABASE_URL": " postgresql://u:p@h:1/d ",
                               "BACKEND_PORTA": "8090", "AGENTE_TIMEOUT": "1200"})
    assert (c.database_url, c.backend_porta, c.agente_timeout) == ("postgresql://u:p@h:1/d", 8090, 1200)


@pytest.mark.parametrize("nome, valore", [("AGENTE_TIMEOUT", "0"), ("BACKEND_PORTA", "99999")])
def test_backend_valori_non_validi(nome, valore):
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_configurazione({**BASE, nome: valore})
