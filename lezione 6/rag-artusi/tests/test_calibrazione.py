from rag.avanzata import Candidato
from rag.calibrazione import confronto_soglie, riepilogo, riga_score, stat, tabella_riepilogo, tabella_score
from rag.confronto import DomandaL8, misura
from rag.pipeline import EsitoPipeline
from rag.ricerca import Risultato

CON = DomandaL8("Farina negli gnocchi?", "semplice", (89,), (), False, None)
COMPOSTA = DomandaL8("Farina e vino?", "composta", (89, 208), ((89,), (208,)), False, None)
SENZA = DomandaL8("Tiramisù?", "senza_risposta", (), (), False, None)


def _esito(coppie, fascia="non_valutata"):
    candidati = []
    for numero, score in coppie:
        r = Risultato(score=score, numero=numero, titolo="t", capitolo="c", posizione=0, documento_id="d",
                      testo="x", fonte="f")
        candidati.append(Candidato(id=f"{numero}.0", risultato=r, score=score, fascia=fascia))
    return EsitoPipeline(modalita="base", query_usate=["q"], candidati=candidati)


def test_stat():
    assert stat([0.7, 0.8, 0.75]) == (0.7, 0.75, 0.8)
    assert stat([]) == (None, None, None)


def test_riga_score():
    r = riga_score(CON, _esito([(5, 0.80), (89, 0.77), (6, 0.70)]))
    assert r["top1"] == 0.8 and r["scores"] == [0.8, 0.77, 0.7]
    assert (r["posizione_fonte"], r["score_fonte"]) == (2, 0.77)
    vuota = riga_score(SENZA, _esito([]))
    assert vuota["top1"] is None and vuota["score_fonte"] is None


def test_riepilogo_e_sovrapposizione():
    righe = [riga_score(CON, _esito([(89, 0.77)])), riga_score(COMPOSTA, _esito([(1, 0.72), (89, 0.70)])),
             riga_score(SENZA, _esito([(3, 0.74)]))]
    s = riepilogo(righe)
    assert s["con_risposta_top1"] == (0.72, 0.745, 0.77)
    assert s["fonte_attesa"] == (0.70, 0.735, 0.77)
    assert s["senza_risposta_top1"] == (0.74, 0.74, 0.74)
    assert s["con_risposta_sotto_max_senza"] == 1  # 0.72 < 0.74: con una soglia a 0.74 sarebbe persa
    assert s["sovrapposti"] is True
    assert "| Con risposta: top-1 | 0.720 | 0.745 | 0.770 |" in tabella_riepilogo(s)


def test_tabella_score():
    testo = tabella_score([riga_score(CON, _esito([(5, 0.80), (89, 0.77)]))], k=2)
    assert "| Farina negli gnocchi? | semplice | 0.800 | 0.800, 0.770 | 0.770 (pos 2) |" in testo


def test_confronto_soglie():
    per_variante = {
        "base senza soglie": [misura(CON, _esito([(89, 0.77)]), 1), misura(SENZA, _esito([(3, 0.71)]), 1)],
        "base con soglie": [misura(CON, _esito([(89, 0.77)], "affidabile"), 1), misura(SENZA, _esito([]), 1)],
    }
    testo = confronto_soglie(per_variante, k=5)
    assert "| base senza soglie | 1/1 | 0/1 | 0 | non_valutata 2 |" in testo
    assert "| base con soglie | 1/1 | 1/1 | 0 | affidabile 1 |" in testo
