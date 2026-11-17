import pytest
from qdrant_client import QdrantClient, models

import rag.ricerca as ricerca
from rag.corpus import CAPITOLI, carica_corpus
from rag.indice import ErroreCollezione
from rag.ingestion import esegui_ingestion
from rag.ricerca import K_MASSIMO, cerca, main, normalizza_capitolo
from tests.conftest import CORPUS_REALE, FIXTURE_MINI, crea_config
from tests.finti import EmbedderFinto


@pytest.fixture(scope="module")
def indicizzato():
    """Corpus reale se presente, altrimenti l'estratto di prova, indicizzato in memoria."""
    percorso = CORPUS_REALE if CORPUS_REALE.exists() else FIXTURE_MINI
    client = QdrantClient(":memory:")
    config = crea_config()
    esegui_ingestion(config, client, EmbedderFinto(), carica_corpus(percorso))
    capitolo = "Piatti di pesce" if percorso == CORPUS_REALE else "Minestre in brodo"
    return client, config, capitolo


def _cerca(indicizzato, domanda="gnocchi di patate", embedder=None, **kw):
    client, config, _ = indicizzato
    return cerca(domanda, client=client, embedder=embedder or EmbedderFinto(), config=config, **kw)


def test_filtro_capitolo(indicizzato):
    capitolo = indicizzato[2]
    risultati = _cerca(indicizzato, k=20, capitolo=capitolo)
    assert risultati
    assert len(risultati) <= 20
    assert all(r.capitolo == capitolo for r in risultati)


def test_filtro_nativo(indicizzato, monkeypatch):
    client = indicizzato[0]
    chiamate = []
    originale = client.query_points

    def spia(*a, **kw):
        chiamate.append(kw)
        return originale(*a, **kw)

    monkeypatch.setattr(client, "query_points", spia)
    _cerca(indicizzato, k=5, capitolo=indicizzato[2])
    filtro = chiamate[0]["query_filter"]
    assert filtro == models.Filter(
        must=[models.FieldCondition(key="capitolo", match=models.MatchValue(value=indicizzato[2]))]
    )
    assert chiamate[0]["limit"] == 5


def test_al_massimo_k(indicizzato):
    assert len(_cerca(indicizzato, k=3)) == 3


def test_k_massimo():
    assert K_MASSIMO == 20


@pytest.mark.parametrize("k", [0, 21, -1])
def test_k_fuori_intervallo(indicizzato, k):
    with pytest.raises(ValueError, match="20"):
        _cerca(indicizzato, k=k)


def test_capitolo_normalizzato():
    assert normalizza_capitolo("  PIATTI di pesce ") == "Piatti di pesce"


def test_capitolo_sconosciuto():
    with pytest.raises(ValueError) as e:
        normalizza_capitolo("Antipasti")
    assert "Pasticceria" in str(e.value)
    assert all(c in str(e.value) for c in CAPITOLI)


def test_domanda_vuota(indicizzato):
    finto = EmbedderFinto()
    with pytest.raises(ValueError):
        _cerca(indicizzato, domanda="   ", embedder=finto)
    assert finto.chiamate == 0


def test_prefisso_query(indicizzato):
    finto = EmbedderFinto()
    _cerca(indicizzato, domanda="gnocchi", embedder=finto)
    assert finto.ricevuti == ["search_query: gnocchi"]


def test_risultato_completo(indicizzato):
    client, config, _ = indicizzato
    for r in _cerca(indicizzato, k=5):
        assert r.numero >= 1 and r.titolo and r.capitolo in CAPITOLI and r.posizione >= 0
        assert r.documento_id == f"artusi-{r.numero:03d}"
        (punto,) = [p for p in client.scroll(config.collezione, limit=5000)[0] if p.payload["testo"] == r.testo]
        assert punto.payload["numero"] == r.numero
        assert punto.payload["posizione"] == r.posizione
        assert r.fonte.startswith("Artusi")


def test_ordinati_per_score(indicizzato):
    scores = [r.score for r in _cerca(indicizzato, k=10)]
    assert scores == sorted(scores, reverse=True)


def test_collezione_assente():
    with pytest.raises(ErroreCollezione, match="rag.ingestion"):
        cerca("gnocchi", client=QdrantClient(":memory:"), embedder=EmbedderFinto(), config=crea_config())


def test_modello_diverso_in_ricerca(indicizzato):
    client = indicizzato[0]
    with pytest.raises(ErroreCollezione):
        cerca("gnocchi", client=client, embedder=EmbedderFinto(), config=crea_config(modello_embedding="altro"))


def _dosi_nel_punto(client, config, r):
    (punto,) = [p for p in client.scroll(config.collezione, limit=5000)[0] if p.payload["testo"] == r.testo]
    return punto.payload["contiene_dosi"]


def test_solo_dosi_tutti_veri(indicizzato):
    """(1) con --solo-dosi tutti i risultati hanno contiene_dosi vero e sono al massimo k."""
    client, config, _ = indicizzato
    for k in (20, 3):
        risultati = _cerca(indicizzato, k=k, solo_dosi=True)
        assert risultati and len(risultati) <= k
        assert all(r.contiene_dosi is True for r in risultati)
        assert all(_dosi_nel_punto(client, config, r) is True for r in risultati)


def test_solo_dosi_e_capitolo(indicizzato):
    """(2) --solo-dosi con --capitolo: tutti veri e tutti del capitolo richiesto."""
    client, config, _ = indicizzato
    capitolo = "Pasticceria" if CORPUS_REALE.exists() else "Minestre in brodo"
    risultati = _cerca(indicizzato, k=20, capitolo=capitolo, solo_dosi=True)
    assert risultati and len(risultati) <= 20
    assert all(r.capitolo == capitolo and r.contiene_dosi for r in risultati)
    assert all(_dosi_nel_punto(client, config, r) is True for r in risultati)


def test_filtro_nativo_dosi(indicizzato, monkeypatch):
    """(3) il filtro è passato a Qdrant nella query: nessun risultato viene scartato dopo."""
    client = indicizzato[0]
    chiamate, restituiti = [], []
    originale = client.query_points

    def spia(*a, **kw):
        chiamate.append(kw)
        risposta = originale(*a, **kw)
        restituiti.append(len(risposta.points))
        return risposta

    monkeypatch.setattr(client, "query_points", spia)
    risultati = _cerca(indicizzato, k=4, capitolo=indicizzato[2], solo_dosi=True)
    assert chiamate[0]["query_filter"] == models.Filter(
        must=[
            models.FieldCondition(key="capitolo", match=models.MatchValue(value=indicizzato[2])),
            models.FieldCondition(key="contiene_dosi", match=models.MatchValue(value=True)),
        ]
    )
    assert chiamate[0]["limit"] == 4
    assert len(risultati) == restituiti[0]


def test_filtro_solo_dosi_senza_capitolo():
    from rag.ricerca import costruisci_filtro

    assert costruisci_filtro(None, False) is None
    assert costruisci_filtro(None, True) == models.Filter(
        must=[models.FieldCondition(key="contiene_dosi", match=models.MatchValue(value=True))]
    )


def test_solo_dosi_capitolo_senza_dosi():
    client = QdrantClient(":memory:")
    esegui_ingestion(crea_config(), client, EmbedderFinto(), carica_corpus(FIXTURE_MINI))
    risultati = cerca("brodo", 5, "Brodi, gelatina e sughi", True, client=client, embedder=EmbedderFinto(), config=crea_config())
    assert risultati == []


ENV = {
    "QDRANT_URL": "http://127.0.0.1:1",
    "COLLEZIONE": "test",
    "LMSTUDIO_URL": "http://127.0.0.1:1/v1",
    "MODELLO_EMBEDDING": "finto",
    "PREFISSO_DOCUMENTO": "search_document: ",
    "PREFISSO_QUERY": "search_query: ",
}


@pytest.fixture
def ambiente(monkeypatch, indicizzato):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("rag.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(ricerca, "QdrantClient", lambda *a, **k: indicizzato[0])
    monkeypatch.setattr(ricerca, "EmbedderLMStudio", lambda *a, **k: EmbedderFinto())
    return monkeypatch


def test_main_stampa(ambiente, capsys):
    assert main(["gnocchi", "--k", "2"]) == 0
    uscita = capsys.readouterr().out
    assert uscita.count("Ricetta ") == 2
    assert "chunk " in uscita


def test_main_capitolo(ambiente, capsys, indicizzato):
    assert main(["gnocchi", "--capitolo", indicizzato[2].upper(), "--k", "3"]) == 0
    assert indicizzato[2] in capsys.readouterr().out


def test_main_solo_dosi_e_capitolo(ambiente, capsys, indicizzato):
    assert main(["farina", "--solo-dosi", "--capitolo", indicizzato[2], "--k", "3"]) == 0
    righe = [r for r in capsys.readouterr().out.splitlines() if r.startswith(("1.", "2.", "3."))]
    assert righe and all("| dosi" in r and indicizzato[2] in r for r in righe)


def test_main_k_troppo_grande(ambiente, capsys):
    assert main(["x", "--k", "50"]) == 1
    assert "20" in capsys.readouterr().err


def test_main_capitolo_sconosciuto(ambiente, capsys):
    assert main(["x", "--capitolo", "Antipasti"]) == 1
    assert "Pasticceria" in capsys.readouterr().err


def test_main_qdrant_spento(monkeypatch, capsys):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("rag.config.load_dotenv", lambda *a, **k: None)
    assert main(["gnocchi"]) == 1
    errore = capsys.readouterr().err
    assert "127.0.0.1:1" in errore and "Traceback" not in errore
