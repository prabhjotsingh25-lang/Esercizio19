import pytest

from rag.config import ErroreConfigurazione, carica_config

OBBLIGATORIE = {
    "QDRANT_URL": "http://localhost:6333",
    "COLLEZIONE": "artusi",
    "LMSTUDIO_URL": "http://localhost:1234/v1",
    "MODELLO_EMBEDDING": "nomic",
}


def test_config_completa():
    env = {
        **OBBLIGATORIE,
        "PREFISSO_DOCUMENTO": "search_document: ",
        "PREFISSO_QUERY": "search_query: ",
        "CHUNK_STRATEGIA": "caratteri",
        "CHUNK_DIMENSIONE": "1200",
        "CHUNK_OVERLAP": "100",
        "EMBEDDING_BATCH": "16",
        "CORPUS": "altro/file.txt",
    }
    c = carica_config(env)
    assert c.qdrant_url == "http://localhost:6333"
    assert c.collezione == "artusi"
    assert c.modello_embedding == "nomic"
    assert c.chunk_dimensione == 1200
    assert c.chunk_overlap == 100
    assert c.embedding_batch == 16
    assert c.chunk_strategia == "caratteri"
    assert c.prefisso_documento == "search_document: "
    assert c.prefisso_query == "search_query: "
    assert c.corpus.as_posix() == "altro/file.txt"


def test_default():
    c = carica_config(dict(OBBLIGATORIE))
    assert c.chunk_strategia == "paragrafi"
    assert c.chunk_dimensione == 1200
    assert c.chunk_overlap == 200
    assert c.embedding_batch == 32
    assert c.prefisso_documento == ""
    assert c.prefisso_query == ""
    assert c.corpus.as_posix() == "dati/artusi.txt"


@pytest.mark.parametrize("nome", list(OBBLIGATORIE))
def test_variabile_mancante(nome):
    env = {k: v for k, v in OBBLIGATORIE.items() if k != nome}
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_config(env)


@pytest.mark.parametrize("overlap", ["1200", "-1"])
def test_overlap_non_valido(overlap):
    env = {**OBBLIGATORIE, "CHUNK_DIMENSIONE": "1200", "CHUNK_OVERLAP": overlap}
    with pytest.raises(ErroreConfigurazione):
        carica_config(env)


def test_strategia_sconosciuta():
    with pytest.raises(ErroreConfigurazione, match="frasi"):
        carica_config({**OBBLIGATORIE, "CHUNK_STRATEGIA": "frasi"})


def test_env_example_valido_con_spazio_nei_prefissi():
    from pathlib import Path

    from dotenv import dotenv_values

    esempio = Path(__file__).resolve().parent.parent / ".env.example"
    c = carica_config(dotenv_values(esempio))
    assert c.prefisso_documento == "search_document: "
    assert c.prefisso_query == "search_query: "
    assert c.chunk_dimensione == 1200 and c.chunk_overlap == 200


def test_testo_indicizzato_default_e_valori():
    assert carica_config(dict(OBBLIGATORIE)).testo_indicizzato == "titolo_capitolo"
    assert carica_config({**OBBLIGATORIE, "TESTO_INDICIZZATO": "solo_testo"}).testo_indicizzato == "solo_testo"
    with pytest.raises(ErroreConfigurazione, match="TESTO_INDICIZZATO"):
        carica_config({**OBBLIGATORIE, "TESTO_INDICIZZATO": "altro"})


def test_numero_non_valido():
    with pytest.raises(ErroreConfigurazione, match="CHUNK_DIMENSIONE"):
        carica_config({**OBBLIGATORIE, "CHUNK_DIMENSIONE": "tanti"})
