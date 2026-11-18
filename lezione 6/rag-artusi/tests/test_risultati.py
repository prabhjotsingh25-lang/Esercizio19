import json

from rag.ricerca import Risultato
from rag.risultati import componi_risultato, id_passaggio, limita_top_k, passaggio, tronca


def _r(testo="Patate grosse e gialle, grammi 400.", score=0.77349):
    return Risultato(score=score, numero=89, titolo="Gnocchi di patate", capitolo="Minestre asciutte e di magro",
                     posizione=1, documento_id="artusi-089", testo=testo, fonte="Artusi")


def test_id_passaggio():
    assert id_passaggio(89, 1) == "89.1"
    assert id_passaggio(7, 0) == "7.0"


def test_tronca_corto_invariato_e_spazi_normalizzati():
    assert tronca("uno  due\ntre", 50) == "uno due tre"


def test_tronca_lungo():
    testo = "a" * 30
    troncato = tronca(testo, 10)
    assert len(troncato) == 10
    assert troncato.endswith("…")


def test_limita_top_k():
    assert limita_top_k(5, 10) == (5, None)
    assert limita_top_k(50, 10) == (10, "top_k ridotto da 50 a 10 (massimo consentito)")
    assert limita_top_k(0, 10) == (1, "top_k portato da 0 a 1 (minimo consentito)")


def test_passaggio_chiavi_esatte():
    p = passaggio(_r(), 800)
    assert list(p) == ["id", "ricetta", "titolo", "capitolo", "posizione_chunk", "score", "testo"]
    assert p["id"] == "89.1" and p["ricetta"] == 89 and p["posizione_chunk"] == 1
    assert p["score"] == 0.773


def test_passaggio_troncato_e_accenti():
    p = passaggio(_r(testo="Perché è così " * 100), 40)
    assert len(p["testo"]) == 40 and "è" in p["testo"]
    assert "è" in json.dumps(p, ensure_ascii=False)


def test_componi_risultato():
    r = componi_risultato("base", ["q"], [], [])
    assert r == {"modalita": "base", "query_usate": ["q"], "passaggi": [], "nota": ""}
    assert componi_risultato("base", ["q"], [], ["a", "b"])["nota"] == "a · b"
