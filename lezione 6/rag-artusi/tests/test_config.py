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


# --- Lezione 8: server di ricerca MCP ---

def test_ricerca_default():
    c = carica_config(OBBLIGATORIE)
    assert c.ricerca_top_k_max == 10
    assert c.ricerca_max_caratteri == 800
    assert c.ricerca_log_file is None


def test_ricerca_valori():
    c = carica_config({**OBBLIGATORIE, "RICERCA_TOP_K_MAX": "7", "RICERCA_MAX_CARATTERI": "300",
                       "RICERCA_LOG_FILE": "logs/ricerca.log"})
    assert (c.ricerca_top_k_max, c.ricerca_max_caratteri, c.ricerca_log_file) == (7, 300, "logs/ricerca.log")


@pytest.mark.parametrize("valore", ["0", "21", "dieci"])
def test_ricerca_top_k_max_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="RICERCA_TOP_K_MAX"):
        carica_config({**OBBLIGATORIE, "RICERCA_TOP_K_MAX": valore})


def test_ricerca_max_caratteri_zero():
    with pytest.raises(ErroreConfigurazione, match="RICERCA_MAX_CARATTERI"):
        carica_config({**OBBLIGATORIE, "RICERCA_MAX_CARATTERI": "0"})


# --- Lezione 8 es. 3: modalità avanzate ---

def test_modalita_e_llm_default():
    c = carica_config(OBBLIGATORIE)
    assert c.modalita_ricerca == "base"
    assert c.modello_chat == "google/gemma-4-e2b"
    assert (c.llm_temperatura, c.llm_seed, c.llm_reasoning_effort) == (0.0, 42, "none")
    assert (c.llm_max_tokens, c.llm_timeout) == (300, 60)
    assert (c.riscrittura_max_query, c.candidati_per_query, c.rerank_max_candidati) == (3, 10, 10)
    assert (c.rerank_max_caratteri, c.rrf_k) == (400, 60)


def test_seed_e_reasoning_vuoti_non_inviati():
    c = carica_config({**OBBLIGATORIE, "LLM_SEED": "", "LLM_REASONING_EFFORT": ""})
    assert c.llm_seed is None and c.llm_reasoning_effort is None


@pytest.mark.parametrize("nome, valore", [
    ("MODALITA_RICERCA", "tutte"), ("RISCRITTURA_MAX_QUERY", "4"), ("RISCRITTURA_MAX_QUERY", "0"),
    ("CANDIDATI_PER_QUERY", "21"), ("RERANK_MAX_CANDIDATI", "0"), ("RERANK_MAX_CARATTERI", "0"),
    ("RRF_K", "-1"), ("LLM_TEMPERATURA", "caldo"), ("LLM_TEMPERATURA", "3"), ("LLM_MAX_TOKENS", "0"),
    ("LLM_TIMEOUT", "0"),
])
def test_valori_avanzati_non_validi(nome, valore):
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_config({**OBBLIGATORIE, nome: valore})
