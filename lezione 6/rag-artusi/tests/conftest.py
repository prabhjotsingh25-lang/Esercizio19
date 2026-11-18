from pathlib import Path

import pytest

from rag.config import Config

CORPUS_REALE = Path(__file__).resolve().parent.parent / "dati" / "artusi.txt"
FIXTURE_MINI = Path(__file__).resolve().parent / "fixtures" / "mini_artusi.txt"

serve_corpus = pytest.mark.skipif(
    not CORPUS_REALE.exists(), reason="dati/artusi.txt assente (fuori da Git): test sul corpus reale saltato"
)


def crea_config(**modifiche) -> Config:
    valori = dict(
        qdrant_url="http://localhost:6333",
        collezione="test",
        lmstudio_url="http://localhost:1234/v1",
        modello_embedding="finto",
        prefisso_documento="search_document: ",
        prefisso_query="search_query: ",
        chunk_strategia="paragrafi",
        chunk_dimensione=1200,
        chunk_overlap=200,
        embedding_batch=32,
        corpus=CORPUS_REALE,
        testo_indicizzato="titolo_capitolo",
        soglie_attive=False,  # i test delle soglie le attivano esplicitamente
    )
    valori.update(modifiche)
    return Config(**valori)


@pytest.fixture
def config_test() -> Config:
    return crea_config()
