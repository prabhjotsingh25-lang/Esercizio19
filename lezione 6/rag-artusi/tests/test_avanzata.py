import pytest

from rag.avanzata import (Candidato, SCHEMA_RERANKING, fondi, prompt_reranking, riordina, riscrivi,
                          SCHEMA_RISCRITTURA)
from rag.llm import ErroreLLM, RispostaNonValida
from rag.ricerca import Risultato
from tests.finti import LLMFinto

DOMANDA = "Quanta farina negli gnocchi e che vino per il pollo alla cacciatora?"


def _r(numero, posizione=0, score=0.7, testo="testo"):
    return Risultato(score=score, numero=numero, titolo=f"Ricetta {numero}", capitolo="c", posizione=posizione,
                     documento_id=f"artusi-{numero:03d}", testo=testo, fonte="f")


def _codici(ripieghi):
    return [r.codice for r in ripieghi]


# --- riscrittura ---

def test_riscrittura_composta_una_query_per_parte_originale_prima():
    llm = LLMFinto({"query": ["farina gnocchi di patate", "vino pollo alla cacciatora"]})
    query, ripieghi = riscrivi(DOMANDA, llm, 3)
    assert query == [DOMANDA, "farina gnocchi di patate", "vino pollo alla cacciatora"]
    assert ripieghi == [] and llm.chiamate == 1
    assert llm.richieste[0]["schema"] == SCHEMA_RISCRITTURA(3)
    assert DOMANDA in llm.richieste[0]["utente"]


def test_schema_riscrittura():
    s = SCHEMA_RISCRITTURA(3)
    assert s["required"] == ["query"]
    assert s["properties"]["query"]["minItems"] == 1 and s["properties"]["query"]["maxItems"] == 3


@pytest.mark.parametrize("risposta, codice", [
    (RispostaNonValida("contenuto non JSON"), "riscrittura_json"),
    ({"query": "gnocchi"}, "riscrittura_json"),
    ({"altro": []}, "riscrittura_json"),
    ({"query": [1, 2]}, "riscrittura_json"),
    ({"query": []}, "riscrittura_vuota"),
    ({"query": ["  ", DOMANDA.upper() + "?"]}, "riscrittura_vuota"),
    (ErroreLLM("HTTP 400: reasoning_effort"), "riscrittura_servizio"),
])
def test_riscrittura_inutilizzabile_solo_originale(risposta, codice):
    query, ripieghi = riscrivi(DOMANDA, LLMFinto(risposta), 3)
    assert query == [DOMANDA]
    assert _codici(ripieghi) == [codice]
    assert "solo la domanda originale" in ripieghi[0].descrizione


def test_riscrittura_toglie_duplicati_e_tronca():
    llm = LLMFinto({"query": ["a", "A.", "b", "c", "d", DOMANDA]})
    query, ripieghi = riscrivi(DOMANDA, llm, 3)
    assert query == [DOMANDA, "a", "b", "c"]
    assert _codici(ripieghi) == ["riscrittura_troppe_query"]


# --- RRF ---

def test_rrf_numerico_e_senza_duplicati():
    a, b, c = _r(1, score=0.80), _r(2, score=0.75), _r(3, score=0.70)
    b2 = _r(2, score=0.78)
    fusi = fondi([[a, b, c], [c, _r(4, score=0.9), b2]], rrf_k=60)
    per_id = {f.id: f for f in fusi}
    assert len(fusi) == 4 and len(per_id) == 4
    assert per_id["2.0"].score_rrf == pytest.approx(1 / 62 + 1 / 63)
    assert per_id["3.0"].score_rrf == pytest.approx(1 / 63 + 1 / 61)
    assert per_id["2.0"].score == 0.78  # coseno migliore fra le query
    assert [f.id for f in fusi] == ["3.0", "2.0", "1.0", "4.0"]


def test_rrf_parita_vince_il_coseno_poi_l_id():
    fusi = fondi([[_r(5, score=0.6)], [_r(7, score=0.9)], [_r(6, score=0.9)]], rrf_k=60)
    assert [f.id for f in fusi] == ["6.0", "7.0", "5.0"]


# --- reranking ---

def _candidati(n):
    return [Candidato(id=f"{i}.0", risultato=_r(i, testo="x" * 1000), score=0.7) for i in range(1, n + 1)]


def test_prompt_con_tetto_e_testo_troncato():
    llm = LLMFinto({"id": ["2.0", "1.0"]})
    ordinati, ripieghi = riordina("domanda?", _candidati(12), llm, max_candidati=10, max_caratteri=50)
    assert [c.id for c in ordinati] == ["2.0", "1.0"] and ripieghi == []
    richiesta = llm.richieste[0]
    assert "[10.0]" in richiesta["utente"] and "[11.0]" not in richiesta["utente"]
    assert "x" * 51 not in richiesta["utente"]
    assert richiesta["schema"] == SCHEMA_RERANKING([f"{i}.0" for i in range(1, 11)])
    assert "non istruzioni" in richiesta["sistema"] or "dati" in richiesta["sistema"]


def test_schema_reranking_enum():
    s = SCHEMA_RERANKING(["1.0", "2.0"])
    assert s["properties"]["id"]["items"]["enum"] == ["1.0", "2.0"]
    assert s["properties"]["id"]["maxItems"] == 2


def test_id_inventati_scartati():
    ordinati, ripieghi = riordina("d", _candidati(3), LLMFinto({"id": ["99.0", "3.0"]}), 10, 400)
    assert [c.id for c in ordinati] == ["3.0"] and _codici(ripieghi) == ["reranking_id_sconosciuti"]


def test_tutti_inventati_ordine_vettoriale():
    ordinati, ripieghi = riordina("d", _candidati(3), LLMFinto({"id": ["99.0"]}), 10, 400)
    assert ordinati is None and _codici(ripieghi) == ["reranking_id_sconosciuti"]


def test_duplicati_uno_solo():
    ordinati, ripieghi = riordina("d", _candidati(3), LLMFinto({"id": ["2.0", "2.0", "1.0"]}), 10, 400)
    assert [c.id for c in ordinati] == ["2.0", "1.0"] and _codici(ripieghi) == ["reranking_id_duplicati"]


def test_lista_vuota_astensione():
    ordinati, ripieghi = riordina("d", _candidati(3), LLMFinto({"id": []}), 10, 400)
    assert ordinati == [] and ripieghi == []


@pytest.mark.parametrize("risposta, codice", [
    (RispostaNonValida("x"), "reranking_json"), ({"id": "1.0"}, "reranking_json"), ({}, "reranking_json"),
    (ErroreLLM("timeout"), "reranking_servizio"),
])
def test_reranking_inutilizzabile_ordine_vettoriale(risposta, codice):
    ordinati, ripieghi = riordina("d", _candidati(3), LLMFinto(risposta), 10, 400)
    assert ordinati is None and _codici(ripieghi) == [codice]
    assert "ordine della ricerca vettoriale" in ripieghi[0].descrizione


def test_nessun_candidato_nessuna_chiamata():
    llm = LLMFinto()
    assert riordina("d", [], llm, 10, 400) == ([], [])
    assert llm.chiamate == 0
