import uuid

import pytest

from rag.chunking import FONTE, crea_chunk, dividi, documento_id, id_punto
from rag.corpus import Ricetta, carica_corpus
from tests.conftest import CORPUS_REALE, crea_config, serve_corpus

CHIAVI_PAYLOAD = {"documento_id", "numero", "titolo", "capitolo", "posizione", "testo", "fonte"}


def _parola(i: int) -> str:
    return f"parola{i}"


def _paragrafo(n: int, lunghezza: int = 300) -> str:
    parole, i = [], 0
    while len(" ".join(parole)) < lunghezza - 12:
        parole.append(_parola(n * 1000 + i))
        i += 1
    return " ".join(parole) + "."


def _controlla_overlap(chunk: list[str], overlap: int) -> None:
    for prima, dopo in zip(chunk, chunk[1:]):
        # il chunk successivo comincia con un suffisso del precedente lungo al massimo `overlap`
        trovato = any(
            dopo.startswith(prima[-n:]) for n in range(1, min(overlap, len(prima)) + 1)
        )
        assert trovato, (prima[-80:], dopo[:80])


def test_documento_id():
    assert documento_id(89) == "artusi-089"
    assert documento_id(790) == "artusi-790"


def test_id_stabile():
    a = id_punto("artusi-089", 0)
    assert a == id_punto("artusi-089", 0)
    assert len({a, id_punto("artusi-089", 1), id_punto("artusi-090", 0)}) == 3
    assert uuid.UUID(a).version == 5


def test_breve_un_chunk():
    testo = "a" * 100 + " " + "b" * 258
    assert len(testo) == 359
    assert dividi(testo, "paragrafi", 1200, 200) == [testo]


def test_lungo_sintetico():
    paragrafi = [_paragrafo(n) for n in range(12)]
    testo = "\n\n".join(paragrafi)
    chunk = dividi(testo, "paragrafi", 1200, 200)
    assert len(chunk) > 1
    assert all(len(c) <= 1200 + 200 for c in chunk)
    _controlla_overlap(chunk, 200)
    for p in paragrafi:
        assert any(p in c for c in chunk)


def test_senza_overlap():
    testo = "\n\n".join(_paragrafo(n) for n in range(12))
    chunk = dividi(testo, "paragrafi", 1200, 0)
    assert "\n\n".join(chunk) == testo


def test_paragrafo_gigante():
    testo = " ".join(_parola(i) for i in range(400))  # ~3500 caratteri, un solo paragrafo
    chunk = dividi(testo, "paragrafi", 1200, 200)
    assert len(chunk) >= 3
    parole = set(testo.split())
    for c in chunk:
        assert len(c) <= 1400
        assert set(c.split()) <= parole  # nessuna parola tagliata
    _controlla_overlap(chunk, 200)


def test_paragrafo_gigante_taglia_a_fine_frase():
    frasi = [f"Frase numero {i} con qualche parola in più per allungarla un poco." for i in range(60)]
    testo = " ".join(frasi)
    chunk = dividi(testo, "paragrafi", 1200, 0)
    assert all(c.endswith(".") for c in chunk)


def test_strategia_caratteri():
    testo = " ".join(_parola(i) for i in range(300))
    chunk = dividi(testo, "caratteri", 1000, 100)
    assert len(chunk) > 1
    parole = set(testo.split())
    for c in chunk:
        assert len(c) <= 1000
        assert set(c.split()) <= parole
    _controlla_overlap(chunk, 100)
    assert chunk[0] == testo[: len(chunk[0])]
    assert testo.endswith(chunk[-1])


def test_strategia_sconosciuta():
    with pytest.raises(ValueError):
        dividi("testo", "frasi", 1200, 200)


def test_crea_chunk_payload():
    corpo = "\n\n".join(_paragrafo(n) for n in range(8))
    ricetta = Ricetta(89, "Gnocchi di patate", "Minestre asciutte e di magro", corpo)
    chunk = crea_chunk([ricetta], crea_config())
    assert len(chunk) > 1
    for i, c in enumerate(chunk):
        assert set(c.payload) == CHIAVI_PAYLOAD
        assert c.payload["documento_id"] == "artusi-089"
        assert c.payload["numero"] == 89
        assert c.payload["titolo"] == "Gnocchi di patate"
        assert c.payload["capitolo"] == "Minestre asciutte e di magro"
        assert c.payload["posizione"] == i
        assert c.payload["fonte"] == FONTE
        assert c.payload["testo"] == c.testo
        assert "search_document" not in c.testo
        assert c.id == id_punto("artusi-089", i)


def test_fonte():
    assert FONTE == "Artusi, La scienza in cucina (Project Gutenberg n. 59047)"


@pytest.fixture(scope="module")
def ricette():
    return {r.numero: r for r in carica_corpus(CORPUS_REALE)}


@serve_corpus
def test_ricetta_breve_reale(ricette):
    corpo = ricette[106].corpo
    assert len(corpo) < 1200
    chunk = crea_chunk([ricette[106]], crea_config())
    assert [c.testo for c in chunk] == [corpo]


@serve_corpus
def test_ricetta_lunga_reale(ricette):
    corpo = ricette[7].corpo
    chunk = crea_chunk([ricette[7]], crea_config())
    testi = [c.testo for c in chunk]
    assert len(testi) >= 3
    assert all(len(t) <= 1400 for t in testi)
    _controlla_overlap(testi, 200)
    for paragrafo in corpo.split("\n\n"):
        if len(paragrafo) <= 1200:
            assert any(paragrafo in t for t in testi)


@serve_corpus
def test_id_unici_corpus(ricette):
    chunk = crea_chunk(list(ricette.values()), crea_config())
    assert len({c.id for c in chunk}) == len(chunk)
