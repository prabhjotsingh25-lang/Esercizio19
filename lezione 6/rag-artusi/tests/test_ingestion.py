import pytest
from qdrant_client import QdrantClient

import rag.ingestion as ingestion
from rag.corpus import carica_corpus
from rag.indice import ErroreCollezione, conta
from rag.ingestion import esegui_ingestion, main
from tests.conftest import CORPUS_REALE, FIXTURE_MINI, crea_config, serve_corpus
from tests.finti import EmbedderFinto


@pytest.fixture
def client():
    return QdrantClient(":memory:")


@pytest.fixture
def ricette():
    return carica_corpus(FIXTURE_MINI)


def _id(client, nome="test"):
    return {str(p.id) for p in client.scroll(nome, limit=1000)[0]}


def test_due_ingestion_stesso_numero(client, ricette):
    config = crea_config()
    primo = esegui_ingestion(config, client, EmbedderFinto(), ricette)
    id_primo = _id(client)
    secondo = esegui_ingestion(config, client, EmbedderFinto(), ricette)
    assert primo.punti == secondo.punti == primo.chunk == len(id_primo)
    assert _id(client) == id_primo
    assert secondo.eliminati == 0


def test_rapporto(client, ricette):
    r = esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    assert (r.ricette, r.capitoli) == (3, 2)
    assert r.scritti == r.chunk == r.punti


def test_testo_passato_all_embedder(client, ricette):
    finto = EmbedderFinto()
    esegui_ingestion(crea_config(), client, finto, ricette)
    punti = sorted(client.scroll("test", limit=1000)[0], key=lambda p: (p.payload["numero"], p.payload["posizione"]))
    assert finto.ricevuti == ["search_document: " + p.payload["testo"] for p in punti]
    assert all("search_document" not in p.payload["testo"] for p in punti)


def test_chunk_eliminati(client, ricette):
    grande = esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    piccolo = esegui_ingestion(crea_config(chunk_dimensione=60, chunk_overlap=10), client, EmbedderFinto(), ricette)
    assert piccolo.punti > grande.punti
    di_nuovo = esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    assert di_nuovo.punti == grande.punti
    assert di_nuovo.eliminati == piccolo.punti - grande.punti
    assert conta(client, "test") == grande.punti


def test_modello_cambiato(client, ricette):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    prima = conta(client, "test")
    finto = EmbedderFinto()
    with pytest.raises(ErroreCollezione):
        esegui_ingestion(crea_config(modello_embedding="altro"), client, finto, ricette)
    assert finto.chiamate == 0
    assert conta(client, "test") == prima


def test_dimensione_cambiata(client, ricette):
    esegui_ingestion(crea_config(), client, EmbedderFinto(dimensione=8), ricette)
    with pytest.raises(ErroreCollezione):
        esegui_ingestion(crea_config(), client, EmbedderFinto(dimensione=16), ricette)


ENV = {
    "QDRANT_URL": "http://127.0.0.1:1",
    "COLLEZIONE": "test",
    "LMSTUDIO_URL": "http://127.0.0.1:1/v1",
    "MODELLO_EMBEDDING": "finto",
    "CORPUS": str(FIXTURE_MINI),
}


@pytest.fixture
def ambiente(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("rag.config.load_dotenv", lambda *a, **k: None)  # ignora un eventuale .env reale
    return monkeypatch


def test_main_qdrant_spento(ambiente, capsys):
    ambiente.setattr(ingestion, "EmbedderLMStudio", lambda *a, **k: EmbedderFinto())
    assert main([]) == 1
    errore = capsys.readouterr().err
    assert "127.0.0.1:1" in errore
    assert "Traceback" not in errore


def test_main_lmstudio_spento(ambiente, capsys):
    memoria = QdrantClient(":memory:")
    ambiente.setattr(ingestion, "QdrantClient", lambda *a, **k: memoria)
    assert main([]) == 1
    assert "http://127.0.0.1:1/v1" in capsys.readouterr().err


def test_main_configurazione_mancante(ambiente, capsys):
    ambiente.delenv("MODELLO_EMBEDDING")
    assert main([]) == 1
    assert "MODELLO_EMBEDDING" in capsys.readouterr().err


def test_main_riuscito(ambiente, capsys):
    memoria = QdrantClient(":memory:")
    ambiente.setattr(ingestion, "QdrantClient", lambda *a, **k: memoria)
    ambiente.setattr(ingestion, "EmbedderLMStudio", lambda *a, **k: EmbedderFinto())
    assert main([]) == 0
    uscita = capsys.readouterr().out
    assert "ricette: 3" in uscita and "punti" in uscita


@serve_corpus
def test_ingestion_corpus_reale(client):
    config = crea_config(corpus=CORPUS_REALE)
    primo = esegui_ingestion(config, client, EmbedderFinto())
    assert (primo.ricette, primo.capitoli) == (790, 23)
    assert primo.punti == primo.chunk
    secondo = esegui_ingestion(config, client, EmbedderFinto())
    assert secondo.punti == primo.punti
