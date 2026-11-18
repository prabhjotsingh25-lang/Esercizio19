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


# --- es. 4: soglie nella pipeline (ricerca finta con score preparati) ---

from rag.ricerca import Risultato  # noqa: E402
import rag.pipeline as modulo_pipeline  # noqa: E402


def _r(numero, score):
    return Risultato(score=score, numero=numero, titolo=f"R{numero}", capitolo="c", posizione=0,
                     documento_id="d", testo="testo", fonte="f")


def _con_score(monkeypatch, per_query):
    """Sostituisce cerca: per ogni query restituisce la lista di (numero, score) preparata."""
    def cerca_finta(query, k, capitolo, **kw):
        return [_r(n, s) for n, s in per_query[query]][:k]
    monkeypatch.setattr(modulo_pipeline, "cerca", cerca_finta)


def _esegui_soglie(llm, modalita, soglie=(0.6, 0.3), domanda="d"):
    return esegui(domanda, 5, None, client=None, embedder=None, llm=llm, config=crea_config(),
                  modalita=modalita, soglie=soglie)


def test_soglie_fasce_ed_esclusi(monkeypatch):
    _con_score(monkeypatch, {"d": [(1, 0.75), (2, 0.6), (3, 0.45), (4, 0.3), (5, 0.1)]})
    e = _esegui_soglie(None, "base")
    assert [(c.id, c.fascia) for c in e.candidati] == [
        ("1.0", "affidabile"), ("2.0", "affidabile"), ("3.0", "media"), ("4.0", "media")]
    assert e.esclusi_soglia == 1 and "1 passaggio escluso" in e.note[0]


def test_tutti_sotto_la_soglia_lista_vuota_e_nessun_reranking(monkeypatch):
    _con_score(monkeypatch, {"d": [(1, 0.2), (2, 0.1)]})
    llm = LLMFinto()
    e = _esegui_soglie(llm, "reranking")
    assert e.candidati == [] and llm.chiamate == 0
    assert "nessun passaggio sopra la soglia minima" in e.note[0]


def test_escluso_non_arriva_al_reranking(monkeypatch):
    _con_score(monkeypatch, {"d": [(1, 0.7), (2, 0.1), (3, 0.5)]})
    llm = LLMFinto({"id": ["3.0"]})
    e = _esegui_soglie(llm, "reranking")
    assert "[2.0]" not in llm.richieste[0]["utente"] and "[1.0]" in llm.richieste[0]["utente"]
    assert [(c.id, c.fascia) for c in e.candidati] == [("3.0", "media")]


def test_riscrittura_usa_il_coseno_migliore(monkeypatch):
    _con_score(monkeypatch, {"d": [(1, 0.25), (2, 0.5)], "q2": [(1, 0.65)]})
    e = _esegui_soglie(LLMFinto({"query": ["q2"]}), "riscrittura")
    per_id = {c.id: c for c in e.candidati}
    assert per_id["1.0"].fascia == "affidabile" and per_id["1.0"].score == 0.65
    assert e.esclusi_soglia == 0


def test_soglie_disattivate(monkeypatch):
    _con_score(monkeypatch, {"d": [(1, 0.1)]})
    e = _esegui_soglie(None, "base", soglie=None)
    assert [c.fascia for c in e.candidati] == ["non_valutata"] and e.note == []


def test_soglie_dalla_configurazione(monkeypatch):
    _con_score(monkeypatch, {"d": [(1, 0.5)]})
    e = esegui("d", 5, None, client=None, embedder=None, llm=None,
               config=crea_config(soglia_alta=0.7, soglia_bassa=0.4, soglie_attive=True))
    assert e.candidati[0].fascia == "media"
    e = esegui("d", 5, None, client=None, embedder=None, llm=None, config=crea_config(soglie_attive=False))
    assert e.candidati[0].fascia == "non_valutata"
