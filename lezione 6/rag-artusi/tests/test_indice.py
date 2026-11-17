import pytest
from qdrant_client import QdrantClient, models

from rag.chunking import Chunk, id_punto
from rag.indice import (
    ErroreCollezione,
    assicura_indici,
    conta,
    crea_collezione,
    elimina_orfani,
    formato_salvato,
    imposta_formato,
    metadati_attesi,
    scrivi,
    verifica_compatibilita,
)
from tests.conftest import crea_config


@pytest.fixture
def client():
    return QdrantClient(":memory:")


def _chunk(n: int) -> list[Chunk]:
    return [
        Chunk(id_punto("artusi-001", i), f"testo {i}", {"capitolo": "Salse", "posizione": i, "testo": f"testo {i}"})
        for i in range(n)
    ]


def _vettori(n: int) -> list[list[float]]:
    return [[1.0, float(i), 0.5] for i in range(n)]


def test_metadati_attesi(config_test):
    assert metadati_attesi(config_test) == {
        "modello_embedding": "finto",
        "prefisso_documento": "search_document: ",
        "prefisso_query": "search_query: ",
    }
    assert metadati_attesi(config_test, 8)["dimensione"] == 8


def test_crea_collezione(client, config_test):
    indici = []
    originale = client.create_payload_index

    def spia(collection_name, field_name, field_schema=None, **kw):
        indici.append((collection_name, field_name, field_schema))
        return originale(collection_name, field_name, field_schema=field_schema, **kw)

    client.create_payload_index = spia
    crea_collezione(client, config_test, 8)
    info = client.get_collection("test")
    assert info.config.params.vectors.distance == models.Distance.COSINE
    assert info.config.params.vectors.size == 8
    assert info.config.metadata == {**metadati_attesi(config_test, 8), "testo_indicizzato": "titolo_capitolo"}
    # in memoria l'indice non ha effetto: si verifica che venga richiesto
    assert sorted(indici) == [
        ("test", "capitolo", models.PayloadSchemaType.KEYWORD),
        ("test", "contiene_dosi", models.PayloadSchemaType.BOOL),
    ]


class _SchemaFinto:
    def __init__(self, presenti):
        self.payload_schema = {nome: object() for nome in presenti}


def test_assicura_indici_solo_mancanti(client, config_test):
    crea_collezione(client, config_test, 3)
    richiesti = []
    client.get_collection = lambda nome: _SchemaFinto(["capitolo"])  # come un server con un solo indice
    client.create_payload_index = lambda collection_name, field_name, field_schema=None, **kw: richiesti.append(
        (field_name, field_schema)
    )
    assert assicura_indici(client, "test") == ["contiene_dosi"]
    assert richiesti == [("contiene_dosi", models.PayloadSchemaType.BOOL)]


def test_formato_salvato_e_imposta(client, config_test):
    crea_collezione(client, config_test, 3, formato="in_aggiornamento")
    assert formato_salvato(client, "test") == "in_aggiornamento"
    imposta_formato(client, "test", "titolo_capitolo")
    assert formato_salvato(client, "test") == "titolo_capitolo"
    assert client.get_collection("test").config.metadata["modello_embedding"] == "finto"  # merge, non sostituzione


def test_formato_non_blocca(client, config_test):
    crea_collezione(client, config_test, 3, formato="solo_testo")
    assert verifica_compatibilita(client, config_test) is True  # config titolo_capitolo


def test_verifica_assente(client, config_test):
    assert verifica_compatibilita(client, config_test) is False


def test_verifica_compatibile(client, config_test):
    crea_collezione(client, config_test, 8)
    assert verifica_compatibilita(client, config_test) is True
    assert verifica_compatibilita(client, config_test, dimensione=8) is True


@pytest.mark.parametrize(
    "modifica, vecchio, nuovo",
    [
        ({"modello_embedding": "altro"}, "finto", "altro"),
        ({"prefisso_documento": "doc: "}, "search_document: ", "doc: "),
        ({"prefisso_query": "q: "}, "search_query: ", "q: "),
    ],
)
def test_configurazione_diversa(client, config_test, modifica, vecchio, nuovo):
    crea_collezione(client, config_test, 8)
    with pytest.raises(ErroreCollezione) as e:
        verifica_compatibilita(client, crea_config(**modifica))
    assert vecchio in str(e.value) and nuovo in str(e.value)
    assert "COLLEZIONE" in str(e.value)


def test_dimensione_diversa(client, config_test):
    crea_collezione(client, config_test, 8)
    with pytest.raises(ErroreCollezione) as e:
        verifica_compatibilita(client, config_test, dimensione=768)
    assert "8" in str(e.value) and "768" in str(e.value)


def test_senza_metadati(client, config_test):
    client.create_collection("test", vectors_config=models.VectorParams(size=8, distance=models.Distance.COSINE))
    with pytest.raises(ErroreCollezione):
        verifica_compatibilita(client, config_test)


def test_upsert_idempotente(client, config_test):
    crea_collezione(client, config_test, 3)
    assert scrivi(client, "test", _chunk(3), _vettori(3)) == 3
    scrivi(client, "test", _chunk(3), _vettori(3))
    assert conta(client, "test") == 3


def test_payload_salvato(client, config_test):
    crea_collezione(client, config_test, 3)
    scrivi(client, "test", _chunk(2), _vettori(2))
    (punto,) = client.retrieve("test", [id_punto("artusi-001", 1)], with_payload=True)
    assert punto.payload == {"capitolo": "Salse", "posizione": 1, "testo": "testo 1"}


def test_elimina_orfani(client, config_test):
    crea_collezione(client, config_test, 3)
    scrivi(client, "test", _chunk(5), _vettori(5))
    validi = {c.id for c in _chunk(3)}
    assert elimina_orfani(client, "test", validi) == 2
    assert conta(client, "test") == 3
    rimasti = {p.id for p in client.scroll("test", limit=100)[0]}
    assert rimasti == validi


def test_elimina_orfani_nessuno(client, config_test):
    crea_collezione(client, config_test, 3)
    scrivi(client, "test", _chunk(3), _vettori(3))
    assert elimina_orfani(client, "test", {c.id for c in _chunk(3)}) == 0


def test_scrivi_lunghezze_diverse(client, config_test):
    crea_collezione(client, config_test, 3)
    with pytest.raises(ValueError):
        scrivi(client, "test", _chunk(3), _vettori(2))
