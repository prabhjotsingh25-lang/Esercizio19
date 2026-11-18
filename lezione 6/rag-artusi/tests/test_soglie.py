import pytest

from rag.avanzata import Candidato
from rag.ricerca import Risultato
from rag.soglie import applica, fascia, nota_esclusi


def _c(numero, score):
    r = Risultato(score=score, numero=numero, titolo="t", capitolo="c", posizione=0, documento_id="d",
                  testo="x", fonte="f")
    return Candidato(id=f"{numero}.0", risultato=r, score=score)


@pytest.mark.parametrize("score, attesa", [
    (0.75, "affidabile"), (0.45, "media"), (0.10, None),
    (0.6, "affidabile"), (0.3, "media"), (0.5999, "media"), (0.2999, None), (-0.2, None), (1.0, "affidabile"),
])
def test_fasce_con_soglie_di_partenza(score, attesa):
    assert fascia(score, 0.6, 0.3) == attesa


def test_alta_uguale_a_bassa():
    assert fascia(0.5, 0.5, 0.5) == "affidabile" and fascia(0.49, 0.5, 0.5) is None


def test_applica_imposta_le_fasce_e_conta_gli_esclusi():
    rimasti, esclusi = applica([_c(1, 0.75), _c(2, 0.45), _c(3, 0.10)], 0.6, 0.3)
    assert [(c.id, c.fascia) for c in rimasti] == [("1.0", "affidabile"), ("2.0", "media")]
    assert esclusi == 1


def test_note():
    assert nota_esclusi(0, 3, 0.3) is None
    assert nota_esclusi(2, 3, 0.3) == "2 passaggi esclusi perché sotto la soglia minima (0.30)"
    assert nota_esclusi(1, 3, 0.3) == "1 passaggio escluso perché sotto la soglia minima (0.30)"
    assert nota_esclusi(5, 0, 0.3) == ("nessun passaggio sopra la soglia minima (0.30): "
                                       "il libro non sembra contenere la risposta")
