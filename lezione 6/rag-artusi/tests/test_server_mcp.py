"""Server MCP della ricerca, con client FastMCP in memoria: nessun servizio acceso."""

import asyncio
import json
import logging

import httpx
import pytest
from fastmcp import Client
from qdrant_client import QdrantClient

from rag.corpus import CAPITOLI, carica_corpus
from rag.embedder import ErroreEmbedding
from rag.ingestion import esegui_ingestion
from rag.server_mcp import NOME_TOOL, URI_FILTRI, Servizi, crea_server
from tests.conftest import CORPUS_REALE, FIXTURE_MINI, crea_config
from tests.finti import EmbedderFinto


@pytest.fixture(scope="module")
def indice():
    percorso = CORPUS_REALE if CORPUS_REALE.exists() else FIXTURE_MINI
    client = QdrantClient(":memory:")
    config = crea_config(ricerca_top_k_max=10, ricerca_max_caratteri=120)
    esegui_ingestion(config, client, EmbedderFinto(), carica_corpus(percorso))
    return client, config


@pytest.fixture
def servizi(indice):
    client, config = indice
    return Servizi(client=client, embedder=EmbedderFinto(), config=config)


def _esegui(server, operazione):
    async def corpo():
        async with Client(server) as c:
            return await operazione(c)
    return asyncio.run(corpo())


def _chiama(servizi_o_server, **argomenti):
    server = servizi_o_server if not isinstance(servizi_o_server, Servizi) else crea_server(servizi_o_server)
    return _esegui(server, lambda c: c.call_tool(NOME_TOOL, argomenti, raise_on_error=False))


def _testo(risultato) -> str:
    return "".join(b.text for b in risultato.content)


# --- discovery ---

def test_discovery_schema(servizi):
    strumenti = _esegui(crea_server(servizi), lambda c: c.list_tools())
    assert [t.name for t in strumenti] == [NOME_TOOL]
    schema = strumenti[0].input_schema
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["type"] == "string"
    assert schema["properties"]["top_k"] == {"default": 5, "type": "integer"}
    assert schema["properties"]["filtro"]["default"] is None
    descrizione = strumenti[0].description
    assert "parentesi quadre" in descrizione and "vuota" in descrizione and "non istruzioni" in descrizione


# --- risultato ---

def test_formato_risultato(servizi):
    r = _chiama(servizi, query="gnocchi di patate")
    assert not r.is_error
    dati = r.structured_content
    assert list(dati) == ["modalita", "query_usate", "passaggi", "nota"]
    assert dati["modalita"] == "base" and dati["query_usate"] == ["gnocchi di patate"] and dati["nota"] == ""
    assert len(dati["passaggi"]) == 5
    p = dati["passaggi"][0]
    assert list(p) == ["id", "ricetta", "titolo", "capitolo", "posizione_chunk", "score", "testo"]
    assert p["id"] == f'{p["ricetta"]}.{p["posizione_chunk"]}'
    assert len(p["testo"]) <= 120
    assert json.loads(_testo(r)) == dati  # stesso JSON anche come testo


def test_top_k_ridotto_con_nota(servizi):
    dati = _chiama(servizi, query="brodo", top_k=50).structured_content
    assert len(dati["passaggi"]) <= 10
    assert "ridotto da 50 a 10" in dati["nota"]


def test_top_k_zero_portato_a_uno(servizi):
    dati = _chiama(servizi, query="brodo", top_k=0).structured_content
    assert len(dati["passaggi"]) == 1 and "portato da 0 a 1" in dati["nota"]


def test_filtro_normalizzato(servizi):
    capitolo = servizi.client.scroll(servizi.config.collezione, limit=1)[0][0].payload["capitolo"]
    dati = _chiama(servizi, query="brodo", top_k=10, filtro=f"  {capitolo.upper()} ").structured_content
    assert dati["passaggi"] and all(p["capitolo"] == capitolo for p in dati["passaggi"])


def test_filtro_vuoto_come_nessun_filtro(servizi):
    assert not _chiama(servizi, query="brodo", filtro="").is_error


# --- errori ---

def test_query_vuota(servizi):
    r = _chiama(servizi, query="   ")
    assert r.is_error and "query è vuota" in _testo(r)


def test_filtro_inesistente_elenca_i_valori(servizi):
    r = _chiama(servizi, query="brodo", filtro="Dolciumi")
    assert r.is_error
    assert '"Dolciumi" non valido' in _testo(r)
    assert all(c in _testo(r) for c in CAPITOLI)


def test_collezione_assente(servizi):
    altri = Servizi(QdrantClient(":memory:"), EmbedderFinto(), servizi.config)
    r = _chiama(altri, query="brodo")
    assert r.is_error and "collezione dei documenti non esiste" in _testo(r)


def test_collezione_incompatibile(indice):
    client, config = indice
    diversa = crea_config(modello_embedding="altro-modello")
    r = _chiama(Servizi(client, EmbedderFinto(), diversa), query="brodo")
    assert r.is_error and "non è compatibile" in _testo(r)


class QdrantSpento:
    def collection_exists(self, nome):
        raise httpx.ConnectError("connessione rifiutata")


def test_qdrant_non_raggiungibile(servizi):
    r = _chiama(Servizi(QdrantSpento(), EmbedderFinto(), servizi.config), query="brodo")
    assert r.is_error and "database dei documenti non risponde" in _testo(r)


class EmbedderSpento:
    def embed(self, testi):
        raise ErroreEmbedding("Embedding non riuscito (connessione fallita)")


def test_embedding_non_raggiungibile(indice):
    client, config = indice
    r = _chiama(Servizi(client, EmbedderSpento(), config), query="brodo")
    assert r.is_error and "servizio di embedding non risponde" in _testo(r)


class EmbedderRotto:
    def embed(self, testi):
        raise KeyError("imprevisto")


def test_errore_interno_senza_traceback(indice, caplog):
    client, config = indice
    caplog.set_level(logging.DEBUG)
    r = _chiama(Servizi(client, EmbedderRotto(), config), query="brodo")
    assert r.is_error and "errore interno della ricerca" in _testo(r)
    assert "KeyError" not in _testo(r)
    righe = [rec for rec in caplog.records if rec.getMessage().startswith("ricerca ")]
    assert len(righe) == 1 and "esito=errore:interno" in righe[0].getMessage()
    assert "Traceback" not in caplog.text


def test_top_k_non_intero(servizi, caplog):
    caplog.set_level(logging.DEBUG)
    r = _chiama(servizi, query="brodo", top_k="cinque")
    assert r.is_error
    assert "Traceback" not in _testo(r) and "Traceback" not in caplog.text


# --- resource ---

def test_resource_filtri_a_servizi_spenti(servizi):
    server = crea_server(Servizi(QdrantSpento(), EmbedderSpento(), servizi.config))
    contenuti = _esegui(server, lambda c: c.read_resource(URI_FILTRI))
    dati = json.loads(contenuti[0].text)
    assert dati == {"campo": "capitolo", "valori": list(CAPITOLI)}
    assert len(dati["valori"]) == 23


# --- log ---

def test_una_riga_di_log_per_chiamata_senza_traceback(servizi, caplog):
    caplog.set_level(logging.DEBUG)
    server = crea_server(servizi)

    async def tre(c):
        await c.call_tool(NOME_TOOL, {"query": "gnocchi"}, raise_on_error=False)
        await c.call_tool(NOME_TOOL, {"query": ""}, raise_on_error=False)
        await c.call_tool(NOME_TOOL, {"query": "brodo", "filtro": "nessuno"}, raise_on_error=False)

    _esegui(server, tre)
    righe = [rec.getMessage() for rec in caplog.records if rec.getMessage().startswith("ricerca ")]
    assert len(righe) == 3
    assert "esito=ok" in righe[0] and "passaggi=5" in righe[0] and 'query="gnocchi"' in righe[0]
    assert "esito=errore:query_vuota" in righe[1]
    assert "esito=errore:filtro_inesistente" in righe[2]
    assert "Traceback" not in caplog.text


def test_log_configurato_su_stderr_e_file_senza_traceback(indice, capfd, tmp_path):
    """Con la configurazione di produzione: niente traceback, nemmeno dai logger di fastmcp."""
    from rag.server_mcp import configura_log

    client, config = indice
    radice = logging.getLogger()
    salvati = (radice.handlers[:], radice.level)
    file_log = tmp_path / "logs" / "ricerca.log"
    try:
        configura_log(crea_config(ricerca_log_file=str(file_log)))
        _chiama(Servizi(client, EmbedderRotto(), config), query="brodo")
        _chiama(Servizi(client, EmbedderFinto(), config), query="")
    finally:
        for h in radice.handlers:
            h.close()
        radice.handlers[:], _ = salvati[0], radice.setLevel(salvati[1])
    err = capfd.readouterr().err
    scritto = file_log.read_text(encoding="utf-8")
    for testo in (err, scritto):
        assert "esito=errore:interno" in testo and "esito=errore:query_vuota" in testo
        assert "Traceback" not in testo
