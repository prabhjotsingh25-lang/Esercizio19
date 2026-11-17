import pytest
from qdrant_client import QdrantClient, models

import rag.ingestion as ingestion
from rag.chunking import crea_chunk
from rag.corpus import carica_corpus
from rag.embedder import ErroreEmbedding
from rag.indice import ErroreCollezione, conta, formato_salvato
from rag.ingestion import aggiorna_payload, esegui_ingestion, main
from rag.ricerca import cerca
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


def test_indici_assicurati_anche_su_collezione_esistente(client, ricette, monkeypatch):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    chiamate = []
    monkeypatch.setattr(ingestion, "assicura_indici", lambda c, nome: chiamate.append(nome) or [])
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    assert chiamate == ["test"]


def test_rapporto(client, ricette):
    r = esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    assert (r.ricette, r.capitoli) == (3, 2)
    assert r.scritti == r.chunk == r.punti


def test_testo_passato_all_embedder(client, ricette):
    """(1) testo esatto: prefisso del modello, poi titolo e capitolo, poi il testo del chunk."""
    finto = EmbedderFinto()
    esegui_ingestion(crea_config(), client, finto, ricette)
    punti = sorted(client.scroll("test", limit=1000)[0], key=lambda p: (p.payload["numero"], p.payload["posizione"]))
    assert finto.ricevuti == [
        f"search_document: Titolo: {p.payload['titolo']}\nCapitolo: {p.payload['capitolo']}\n\n{p.payload['testo']}"
        for p in punti
    ]
    assert finto.ricevuti[0].startswith("search_document: Titolo: Brodo\nCapitolo: Brodi, gelatina e sughi\n\n")


def test_testo_passato_solo_testo(client, ricette):
    finto = EmbedderFinto()
    esegui_ingestion(crea_config(testo_indicizzato="solo_testo"), client, finto, ricette)
    punti = sorted(client.scroll("test", limit=1000)[0], key=lambda p: (p.payload["numero"], p.payload["posizione"]))
    assert finto.ricevuti == ["search_document: " + p.payload["testo"] for p in punti]


def test_payload_testo_originale(client, ricette):
    """(2) il payload `testo` è il testo originale del chunk, senza prefisso, titolo né capitolo."""
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    attesi = {c.id: c.testo for c in crea_chunk(ricette, crea_config())}
    for p in client.scroll("test", limit=1000)[0]:
        assert p.payload["testo"] == attesi[str(p.id)]
        assert not any(s in p.payload["testo"] for s in ("search_document", "Titolo:", "Capitolo:"))


def _metadati(client):
    return client.get_collection("test").config.metadata


def test_ricalcolo_nella_stessa_collezione(client, ricette, monkeypatch):
    """(3) la collezione non viene mai ricreata e il numero di punti non cambia."""
    primo = esegui_ingestion(crea_config(testo_indicizzato="solo_testo"), client, EmbedderFinto(), ricette)
    assert _metadati(client)["testo_indicizzato"] == "solo_testo"
    prima = _punti(client)

    def vietata(*a, **k):
        raise AssertionError("la collezione non va ricreata né cancellata")

    monkeypatch.setattr(client, "create_collection", vietata)
    monkeypatch.setattr(client, "delete_collection", vietata)
    secondo = esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)

    dopo = _punti(client)
    assert set(dopo) == set(prima)
    assert secondo.punti == primo.punti == len(prima)
    assert secondo.eliminati == 0
    assert all(dopo[i].vector != prima[i].vector for i in prima)
    assert all(dopo[i].payload == prima[i].payload for i in prima)
    assert _metadati(client)["testo_indicizzato"] == "titolo_capitolo"
    assert secondo.formato == "titolo_capitolo"


class EmbedderRotto:
    def embed(self, testi):
        raise ErroreEmbedding("LM Studio spento a metà")


def test_errore_negli_embedding_non_tocca_la_collezione(client, ricette):
    esegui_ingestion(crea_config(testo_indicizzato="solo_testo"), client, EmbedderFinto(), ricette)
    prima, metadati_prima = _punti(client), dict(_metadati(client))
    with pytest.raises(ErroreEmbedding):
        esegui_ingestion(crea_config(), client, EmbedderRotto(), ricette)
    assert _metadati(client) == metadati_prima  # niente scritto: resta solo_testo, coerente
    assert {i: p.vector for i, p in _punti(client).items()} == {i: p.vector for i, p in prima.items()}


def test_interruzione_durante_la_scrittura_lascia_in_aggiornamento(client, ricette, monkeypatch):
    esegui_ingestion(crea_config(testo_indicizzato="solo_testo"), client, EmbedderFinto(), ricette)
    prima = conta(client, "test")
    originale = client.upsert

    def upsert_rotto(*a, **k):
        raise ConnectionError("Qdrant caduto durante la scrittura")

    monkeypatch.setattr(client, "upsert", upsert_rotto)
    with pytest.raises(ConnectionError):
        esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    assert _metadati(client)["testo_indicizzato"] == "in_aggiornamento"
    assert conta(client, "test") == prima
    monkeypatch.setattr(client, "upsert", originale)
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    assert _metadati(client)["testo_indicizzato"] == "titolo_capitolo"


def test_collezione_senza_formato_non_bloccata(client, ricette):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    metadati = {k: v for k, v in _metadati(client).items() if k != "testo_indicizzato"}
    nuovo = QdrantClient(":memory:")  # collezione «creata prima di B»: stessi metadati senza la chiave
    nuovo.create_collection(
        "test", vectors_config=models.VectorParams(size=8, distance=models.Distance.COSINE), metadata=metadati
    )
    assert formato_salvato(nuovo, "test") == "solo_testo"
    rapporto = esegui_ingestion(crea_config(), nuovo, EmbedderFinto(), ricette)
    assert rapporto.formato == "titolo_capitolo"
    with pytest.raises(ErroreCollezione):
        esegui_ingestion(crea_config(modello_embedding="altro"), nuovo, EmbedderFinto(), ricette)


def test_cambio_formato_senza_ricalcolo_non_modifica_nulla(client, ricette):
    """(5) cambiare TESTO_INDICIZZATO e usare ricerca o --solo-payload non tocca vettori, payload, metadati."""
    esegui_ingestion(crea_config(testo_indicizzato="solo_testo"), client, EmbedderFinto(), ricette)
    prima, metadati_prima = _punti(client), dict(_metadati(client))
    nuova = crea_config()  # titolo_capitolo
    cerca("gnocchi", client=client, embedder=EmbedderFinto(), config=nuova)
    aggiorna_payload(nuova, client, ricette)
    dopo = _punti(client)
    assert {i: p.payload for i, p in dopo.items()} == {i: p.payload for i, p in prima.items()}
    # Qdrant in memoria normalizza i vettori alla prima ricerca (differenze ~6e-8, float32):
    # si confronta con tolleranza; nessuna scrittura dei vettori avviene.
    for i, p in prima.items():
        assert dopo[i].vector == pytest.approx(p.vector, abs=1e-6)
    assert _metadati(client) == metadati_prima


def test_rapporto_indica_formato(client, ricette):
    assert esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette).formato == "titolo_capitolo"


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


class EmbedderVietato:
    def embed(self, testi):
        raise AssertionError("l'aggiornamento del payload non deve calcolare embedding")


def _punti(client):
    return {str(p.id): p for p in client.retrieve("test", list(_id(client)), with_vectors=True, with_payload=True)}


def test_solo_payload_senza_embedding(client, ricette):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    client.delete_payload("test", keys=["contiene_dosi"], points=models.FilterSelector(filter=models.Filter()))
    prima = _punti(client)
    assert not any("contiene_dosi" in p.payload for p in prima.values())

    rapporto = aggiorna_payload(crea_config(), client, ricette)

    dopo = _punti(client)
    attesi = {c.id: c.payload["contiene_dosi"] for c in crea_chunk(ricette, crea_config())}
    assert {i: p.payload["contiene_dosi"] for i, p in dopo.items()} == attesi
    assert {i: p.vector for i, p in dopo.items()} == {i: p.vector for i, p in prima.items()}
    assert rapporto.aggiornati == rapporto.punti == len(prima)
    assert rapporto.con_dosi == sum(attesi.values()) == 1  # solo la ricetta 3 del fixture


def test_solo_payload_crea_indice(client, ricette, monkeypatch):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    chiamate = []
    monkeypatch.setattr(ingestion, "assicura_indici", lambda c, nome: chiamate.append(nome) or [])
    aggiorna_payload(crea_config(), client, ricette)
    assert chiamate == ["test"]


def test_solo_payload_chunk_diversi(client, ricette):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    client.delete_payload("test", keys=["contiene_dosi"], points=models.FilterSelector(filter=models.Filter()))
    with pytest.raises(ErroreCollezione, match="ingestion completa"):
        aggiorna_payload(crea_config(chunk_dimensione=60, chunk_overlap=10), client, ricette)
    assert not any("contiene_dosi" in p.payload for p in _punti(client).values())


def test_solo_payload_collezione_assente(client, ricette):
    with pytest.raises(ErroreCollezione, match="ingestion completa"):
        aggiorna_payload(crea_config(), client, ricette)


def test_solo_payload_modello_diverso(client, ricette):
    esegui_ingestion(crea_config(), client, EmbedderFinto(), ricette)
    with pytest.raises(ErroreCollezione):
        aggiorna_payload(crea_config(modello_embedding="altro"), client, ricette)


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


def test_main_solo_payload_non_crea_embedder(ambiente, capsys):
    memoria = QdrantClient(":memory:")
    esegui_ingestion(crea_config(), memoria, EmbedderFinto(), carica_corpus(FIXTURE_MINI))
    ambiente.setenv("PREFISSO_DOCUMENTO", "search_document: ")
    ambiente.setenv("PREFISSO_QUERY", "search_query: ")
    ambiente.setattr(ingestion, "QdrantClient", lambda *a, **k: memoria)

    def vietato(*a, **k):
        raise AssertionError("embedder creato")

    ambiente.setattr(ingestion, "EmbedderLMStudio", vietato)
    assert main(["--solo-payload"]) == 0
    uscita = capsys.readouterr().out
    assert "aggiornati: " in uscita and "con_dosi: 1" in uscita


@serve_corpus
def test_ingestion_corpus_reale(client):
    config = crea_config(corpus=CORPUS_REALE)
    primo = esegui_ingestion(config, client, EmbedderFinto())
    assert (primo.ricette, primo.capitoli) == (790, 23)
    assert primo.punti == primo.chunk
    secondo = esegui_ingestion(config, client, EmbedderFinto())
    assert secondo.punti == primo.punti
