from pathlib import Path

import pytest

from rag.ricerca import Risultato
from rag.valutazione import Domanda, Riga, carica_domande, tabella_markdown, valuta

DOMANDE_REALI = Path(__file__).resolve().parent.parent / "eval" / "domande.yaml"


def _r(numero: int, score: float, titolo: str = "Titolo") -> Risultato:
    return Risultato(score, numero, titolo, "Salse", 0, f"artusi-{numero:03d}", "testo", "fonte")


def _cerca_fissa(risultati, chiamate=None):
    def cerca_fn(domanda, k):
        if chiamate is not None:
            chiamate.append((domanda, k))
        return risultati[:k]

    return cerca_fn


def test_carica_domande(tmp_path):
    f = tmp_path / "d.yaml"
    f.write_text(
        "- domanda: Come si chiama il cacciucco?\n  attese: [455, 456]\n"
        "- domanda: Tiramisù?\n  attese: []\n",
        encoding="utf-8",
    )
    domande = carica_domande(f)
    assert domande == [Domanda("Come si chiama il cacciucco?", (455, 456)), Domanda("Tiramisù?", ())]


def test_nota_facoltativa(tmp_path):
    f = tmp_path / "d.yaml"
    f.write_text("- domanda: A?\n  attese: [7]\n  nota: moderato contro discreto\n", encoding="utf-8")
    (d,) = carica_domande(f)
    assert d.nota == "moderato contro discreto"


def test_note_markdown():
    from rag.valutazione import note_markdown

    domande = [Domanda("A?", (7,), "moderato contro discreto"), Domanda("B?", (1,))]
    assert note_markdown(domande) == "\n## Note\n\n- «A?»: moderato contro discreto\n"
    assert note_markdown([Domanda("B?", (1,))]) == ""


def test_carica_domande_malformate(tmp_path):
    f = tmp_path / "d.yaml"
    f.write_text("- domanda: senza attese\n", encoding="utf-8")
    with pytest.raises(ValueError):
        carica_domande(f)


def test_posizione_trovata():
    (riga,) = valuta([Domanda("gnocchi", (89,))], _cerca_fissa([_r(12, 0.9), _r(89, 0.8), _r(89, 0.7)]))
    assert riga.posizione == 2
    assert riga.score_migliore == 0.9
    assert riga.primo == "Ricetta 12 — Titolo"


def test_posizione_assente():
    (riga,) = valuta([Domanda("vino", (208,))], _cerca_fissa([_r(12, 0.9), _r(13, 0.8)]))
    assert riga.posizione is None


def test_nessuna_fonte_attesa():
    (riga,) = valuta([Domanda("tiramisù", ())], _cerca_fissa([_r(700, 0.6)]))
    assert riga.posizione is None
    assert riga.score_migliore == 0.6


def test_nessun_risultato():
    (riga,) = valuta([Domanda("x", (1,))], _cerca_fissa([]))
    assert (riga.posizione, riga.score_migliore, riga.primo) == (None, None, "—")


def test_k_passato():
    chiamate = []
    valuta([Domanda("a", (1,))], _cerca_fissa([_r(1, 0.5)], chiamate))
    assert chiamate == [("a", 5)]


def test_tabella():
    righe = [
        Riga("Come si chiama il cacciucco?", (455, 456), 1, 0.8123, "Ricetta 455 — Cacciucco I"),
        Riga("Tiramisù?", (), None, 0.5, "Ricetta 700 — Zuppa inglese"),
        Riga("Vino?", (208,), None, None, "—"),
    ]
    testo = tabella_markdown(righe)
    linee = testo.splitlines()
    assert linee[0] == "| Domanda | Fonte attesa | Posizione | Score migliore | Primo risultato |"
    assert linee[2] == "| Come si chiama il cacciucco? | 455, 456 | 1 | 0.812 | Ricetta 455 — Cacciucco I |"
    assert linee[3] == "| Tiramisù? | nessuna | — | 0.500 | Ricetta 700 — Zuppa inglese |"
    assert linee[4] == "| Vino? | 208 | — | — | — |"


def test_domande_reali_valide():
    domande = carica_domande(DOMANDE_REALI)
    assert len(domande) == 9
    assert all(1 <= n <= 790 for d in domande for n in d.attese)
    assert sum(1 for d in domande if not d.attese) >= 1  # il tiramisù
