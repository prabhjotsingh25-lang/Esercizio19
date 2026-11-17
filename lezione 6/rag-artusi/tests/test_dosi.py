import pytest

from rag.chunking import crea_chunk
from rag.corpus import carica_corpus
from rag.dosi import campione, contiene_dosi, voci_dose
from tests.conftest import CORPUS_REALE, FIXTURE_MINI, crea_config, serve_corpus

POSITIVI = {
    "89": "Patate grosse e gialle, grammi 400.\nFarina di grano, grammi 150.",
    "617": "Mandorle dolci, grammi 120.\nZucchero in polvere, grammi 100.\n\nSbucciate le mandorle.",
    "626": "Zucchero bianco in polvere, grammi 250.\nMandorle dolci, grammi 100.\n"
    "Mandorle amare, grammi 50.\nChiare d'uovo, N. 2.",
    "quanto basta": "Burro, quanto una noce.\nSale, quanto basta.",
    "uova": "Farina, grammi 200.\nUova, uno intero e due rossi.",
}

NEGATIVI = {
    "208 prosa": "conditelo con sale e pepe e annaffiatelo con mezzo bicchiere di San\nGiovese",
    "305 elenco in prosa": "Per quattro persone: grammi 500 di magro senz'osso, grammi 70 di burro e due "
    "decilitri di panna.",
    "256 frammento": "se no, un pizzico di funghi secchi.",
    "ingrediente unico": "Semolino di grana grossa, grammi 300.\n\nMettete il semolino in un catino.",
    "prosa lunga": "Prendete grammi 50 di burro, mettetelo al fuoco in una cazzaruola e quando sarà "
    "liquefatto aggiungete la farina, grammi 30, rimestando sempre.",
    "brodo": "Lo sa il popolo e il comune che per ottenere il brodo buono bisogna mettere la carne ad "
    "acqua diaccia.",
}


@pytest.mark.parametrize("nome", POSITIVI)
def test_positivi(nome):
    assert contiene_dosi(POSITIVI[nome]) is True


@pytest.mark.parametrize("nome", NEGATIVI)
def test_negativi(nome):
    assert contiene_dosi(NEGATIVI[nome]) is False


def test_riga_con_piu_voci_141():
    voci = voci_dose("Uova, N. 4. Burro, grammi 40. Panna, un decilitro.")
    assert voci == ["Uova, N. 4.", "Burro, grammi 40.", "Panna, un decilitro."]
    assert contiene_dosi("Uova, N. 4. Burro, grammi 40. Panna, un decilitro.")


def test_due_voci_minimo():
    assert len(voci_dose(POSITIVI["89"])) == 2
    assert contiene_dosi("Farina di grano, grammi 150.") is False


def test_overlap_con_coda_di_elenco():
    # la coda di un elenco arrivata con l'overlap conta come il resto del testo
    coda = "Mandorle amare, grammi 50.\nChiare d'uovo, N. 2.\n\nLe mandorle spellatele e seccatele al sole."
    assert contiene_dosi(coda) is True
    assert contiene_dosi("Chiare d'uovo, N. 2.\n\nLe mandorle spellatele.") is False


def test_campione_deterministico():
    chunk = crea_chunk(carica_corpus(FIXTURE_MINI), crea_config())  # ricette 1, 2 senza dosi; 3 con dosi
    pos1, neg1 = campione(chunk, 2, seme=42)
    pos2, neg2 = campione(chunk, 2, seme=42)
    assert [c.id for c in pos1] == [c.id for c in pos2]
    assert [c.id for c in neg1] == [c.id for c in neg2]
    assert [c.payload["numero"] for c in pos1] == [3]  # meno positivi di n: li prende tutti
    assert len(neg1) == 2
    assert all(contiene_dosi(c.testo) for c in pos1)
    assert not any(contiene_dosi(c.testo) for c in neg1)


@pytest.fixture(scope="module")
def chunk_reali():
    return crea_chunk(carica_corpus(CORPUS_REALE), crea_config())


@serve_corpus
def test_corpus_89_vero_208_falso(chunk_reali):
    per_numero = {}
    for c in chunk_reali:
        per_numero.setdefault(c.payload["numero"], []).append(c)
    assert contiene_dosi(per_numero[89][0].testo) is True
    assert not any(contiene_dosi(c.testo) for c in per_numero[208])
    assert contiene_dosi(per_numero[141][0].testo) is True
