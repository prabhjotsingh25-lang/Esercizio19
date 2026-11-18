import pytest
from qdrant_client import QdrantClient

from rag.corpus import carica_corpus
from rag.embedder import ErroreEmbedding
from rag.ingestion import esegui_ingestion
from rag.llm import ErroreLLM, RispostaNonValida
from rag.pipeline import NOTA_RERANKING_VUOTO, esegui
from tests.conftest import CORPUS_REALE, FIXTURE_MINI, crea_config
from tests.finti import EmbedderFinto, LLMFinto


@pytest.fixture(scope="module")
def indice():
    percorso = CORPUS_REALE if CORPUS_REALE.exists() else FIXTURE_MINI
    client = QdrantClient(":memory:")
    config = crea_config()
    esegui_ingestion(config, client, EmbedderFinto(), carica_corpus(percorso))
    return client, config


def _esegui(indice, modalita, llm, domanda="gnocchi di patate e pollo", top_k=5, embedder=None):
    client, config = indice
    return esegui(domanda, top_k, None, client=client, embedder=embedder or EmbedderFinto(), llm=llm,
                  config=config, modalita=modalita)


def test_base_nessuna_chiamata_llm(indice):
    e = _esegui(indice, "base", LLMFinto())
    assert e.modalita == "base" and e.query_usate == ["gnocchi di patate e pollo"]
    assert len(e.candidati) == 5 and e.chiamate_llm == 0 and e.note == []


def test_modalita_dalla_configurazione(indice):
    client, config = indice
    e = esegui("gnocchi", 3, None, client=client, embedder=EmbedderFinto(), llm=LLMFinto(),
               config=crea_config(modalita_ricerca="base"))
    assert e.modalita == "base"


def test_riscrittura(indice):
    e = _esegui(indice, "riscrittura", LLMFinto({"query": ["gnocchi di patate", "pollo alla cacciatora"]}))
    assert e.query_usate == ["gnocchi di patate e pollo", "gnocchi di patate", "pollo alla cacciatora"]
    assert e.chiamate_llm == 1 and len(e.candidati) == 5
    assert len({c.id for c in e.candidati}) == 5


def test_reranking(indice):
    base = _esegui(indice, "base", None, top_k=10)
    scelti = [base.candidati[3].id, base.candidati[0].id]
    e = _esegui(indice, "reranking", LLMFinto({"id": scelti}))
    assert [c.id for c in e.candidati] == scelti and e.chiamate_llm == 1


def test_entrambe_due_chiamate(indice):
    llm = LLMFinto({"query": ["gnocchi"]}, {"id": []})
    e = _esegui(indice, "entrambe", llm)
    assert e.chiamate_llm == 2 and e.candidati == [] and NOTA_RERANKING_VUOTO in e.note


def test_llm_spento_ripieghi_non_errore(indice):
    e = _esegui(indice, "entrambe", LLMFinto(ErroreLLM("connessione"), RispostaNonValida("x")))
    assert [r.codice for r in e.ripieghi] == ["riscrittura_servizio", "reranking_json"]
    assert len(e.candidati) == 5 and e.query_usate == ["gnocchi di patate e pollo"]
    assert any("solo la domanda originale" in n for n in e.note)
    assert any("ordine della ricerca vettoriale" in n for n in e.note)


class EmbedderSpento:
    def embed(self, testi):
        raise ErroreEmbedding("giù")


def test_embedding_spento_passa_al_chiamante(indice):
    with pytest.raises(ErroreEmbedding):
        _esegui(indice, "riscrittura", LLMFinto({"query": ["x"]}), embedder=EmbedderSpento())
