import re

import pytest

from rag.corpus import CAPITOLI, carica_corpus, estrai_ricette, pulisci
from tests.conftest import CORPUS_REALE, FIXTURE_MINI, serve_corpus


# --- estratto di prova (sempre eseguiti) -------------------------------------------------


@pytest.fixture(scope="module")
def mini():
    return {r.numero: r for r in carica_corpus(FIXTURE_MINI)}


def test_pulisci_toglie_gutenberg():
    testo = pulisci(FIXTURE_MINI.read_text(encoding="utf-8"))
    assert "Project Gutenberg" not in testo
    assert "This file should be named" not in testo
    assert "\r" not in testo
    assert not testo.startswith("﻿")


def test_fixture_tre_ricette(mini):
    assert sorted(mini) == [1, 2, 3]
    assert [mini[n].capitolo for n in (1, 2, 3)] == [
        "Brodi, gelatina e sughi",
        "Brodi, gelatina e sughi",
        "Minestre in brodo",
    ]
    assert mini[2].titolo == "Cappelletti di prova"


def test_falso_positivo_nel_corpo(mini):
    assert "137. Mettete il composto" in mini[3].corpo
    assert "Scaloppine" not in mini[3].corpo


def test_introduzione_scartata(mini):
    assert "biada dell'uomo" not in mini[2].corpo
    assert mini[2].corpo.endswith("bastano due dozzine.")


def test_testo_fuori_dalle_ricette_scartato(mini):
    tutto = " ".join(r.corpo for r in mini.values())
    assert "prefazione" not in tutto
    assert "STOMACHI" not in tutto


def test_marcatura_rimossa(mini):
    corpo = mini[2].corpo
    assert "_" not in corpo
    assert "[Illustrazione" not in corpo
    assert "[1]" not in corpo
    assert "avrete il cappelletto compito" in corpo


def test_prosa_unita(mini):
    assert "bisogna mettere la carne" in mini[1].corpo
    assert mini[1].corpo.count("\n\n") == 1


def test_ingredienti_una_per_riga(mini):
    righe = mini[3].corpo.split("\n\n")[0].split("\n")
    assert righe == [
        "Cervello di vitella, o di agnello, o di altra bestia consimile, grammi 120.",
        "Fegatini di pollo, N. 3.",
        "Uova, N. 3.",
    ]


def test_titolo_non_nel_corpo(mini):
    for r in mini.values():
        assert not r.corpo.startswith(r.titolo)
        assert not r.corpo.startswith(f"{r.numero}.")


def test_numerazione_rotta_errore():
    testo = pulisci(FIXTURE_MINI.read_text(encoding="utf-8")).replace("2. Cappelletti", "4. Cappelletti")
    with pytest.raises(ValueError):
        estrai_ricette(testo)


# --- corpus reale (saltati se dati/artusi.txt manca) --------------------------------------


@pytest.fixture(scope="module")
def ricette():
    return {r.numero: r for r in carica_corpus(CORPUS_REALE)}


@serve_corpus
def test_790_ricette_senza_buchi(ricette):
    assert list(ricette) == list(range(1, 791))


@serve_corpus
def test_23_capitoli(ricette):
    assert len(CAPITOLI) == 23
    assert tuple(dict.fromkeys(r.capitolo for r in ricette.values())) == CAPITOLI


@serve_corpus
@pytest.mark.parametrize(
    "numero, titolo, capitolo",
    [
        (6, "Sugo di pomodoro", "Brodi, gelatina e sughi"),
        (454, "Insalata russa", "Erbaggi e legumi"),
        (636, "Pane di sabbia", "Pasticceria"),
        (455, "Cacciucco I", "Piatti di pesce"),
        (790, "Spezie fini", "Cose diverse"),
    ],
)
def test_confini_capitoli(ricette, numero, titolo, capitolo):
    assert (ricette[numero].titolo, ricette[numero].capitolo) == (titolo, capitolo)


@serve_corpus
def test_ricetta_6_senza_introduzione_minestre(ricette):
    corpo = ricette[6].corpo
    assert corpo.endswith("questi odori confacenti al bisogno.")
    assert "la minestra era la biada dell'uomo" not in corpo


@serve_corpus
def test_altre_introduzioni_scartate(ricette):
    assert "Non per farmene bello" not in ricette[636].corpo
    assert "UN AMMIRATORE" not in ricette[636].corpo
    assert "QUALITÀ E STAGIONE DEI PESCI" not in ricette[454].corpo
    assert "APPENDICE" not in ricette[790].corpo


@serve_corpus
def test_corpi_puliti(ricette):
    for r in ricette.values():
        assert r.corpo.strip(), r.numero
        assert "_" not in r.corpo, r.numero
        assert "[Illustrazione" not in r.corpo, r.numero
        assert "Gutenberg" not in r.corpo, r.numero
        assert not re.search(r"\[\d+\]", r.corpo), r.numero


@serve_corpus
def test_208_senza_cacciatora(ricette):
    assert ricette[208].titolo == "Pollo alla cacciatora"
    assert "cacciatora" not in ricette[208].corpo.lower()
