from pathlib import Path

import pytest

from rag.avanzata import Candidato, Ripiego
from rag.confronto import (DomandaL8, Misura, carica_domande_l8, metriche, misura, rapporto,
                           tabella_metriche, variazioni)
from rag.pipeline import EsitoPipeline
from rag.ricerca import Risultato

FILE_REALE = Path(__file__).resolve().parent.parent / "eval" / "domande_l8.yaml"

SEMPLICE = DomandaL8("Farina negli gnocchi?", "semplice", (89,), (), False, None)
COMPOSTA = DomandaL8("Farina e vino?", "composta", (89, 208), ((89,), (208,)), True, None)
SENZA = DomandaL8("Tiramisù?", "senza_risposta", (), (), False, None)


def _c(numero, posizione=0):
    r = Risultato(score=0.7, numero=numero, titolo="t", capitolo="c", posizione=posizione,
                  documento_id="d", testo="x", fonte="f")
    return Candidato(id=f"{numero}.{posizione}", risultato=r, score=0.7)


def _esito(numeri, chiamate=0, ripieghi=()):
    return EsitoPipeline(modalita="base", query_usate=["q"], candidati=[_c(n) for n in numeri],
                         ripieghi=[Ripiego(c, c) for c in ripieghi], chiamate_llm=chiamate)


def test_file_reale_valido_e_completo():
    domande = carica_domande_l8(FILE_REALE)
    tipi = [d.tipo for d in domande]
    assert tipi.count("composta") >= 2 and tipi.count("senza_risposta") >= 3
    assert all(d.parti for d in domande if d.tipo == "composta")
    assert all(not d.attese for d in domande if d.tipo == "senza_risposta")


def test_file_non_valido(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("- domanda: x\n  tipo: strana\n  attese: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tipo"):
        carica_domande_l8(p)
    p.write_text("- domanda: x\n  tipo: composta\n  attese: [1]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="parti"):
        carica_domande_l8(p)


def test_misura():
    m = misura(COMPOSTA, _esito([14, 208, 89], chiamate=2, ripieghi=["reranking_json"]), 1234.5)
    assert m.posizione == 2 and (m.parti_coperte, m.parti_totali) == (2, 2)
    assert m.astenuta is False and m.chiamate_llm == 2 and m.ripieghi == ["reranking_json"]
    assert misura(SENZA, _esito([]), 10).astenuta is True
    assert misura(SEMPLICE, _esito([1, 2]), 10).posizione is None


def test_metriche():
    misure = [misura(SEMPLICE, _esito([89]), 100), misura(COMPOSTA, _esito([1, 89], 1, ["riscrittura_json"]), 300),
              misura(SENZA, _esito([]), 200), misura(SEMPLICE, _esito([]), 50)]
    m = metriche(misure)
    assert (m["fonte_nei_k"], m["con_fonte"]) == (2, 3)
    assert m["mrr"] == pytest.approx((1 + 1 / 2 + 0) / 3)
    assert (m["parti_coperte"], m["parti_totali"]) == (1, 2)
    assert (m["astensioni_corrette"], m["senza_risposta"], m["astensioni_errate"]) == (1, 1, 1)
    assert m["chiamate_llm"] == 1 and m["latenza_media_ms"] == 162.5 and m["latenza_max_ms"] == 300
    assert m["ripieghi"] == 1 and m["ripieghi_per_codice"] == {"riscrittura_json": 1}


def test_variazioni():
    base = [misura(SEMPLICE, _esito([1, 89]), 1), misura(COMPOSTA, _esito([89]), 1), misura(SENZA, _esito([5]), 1)]
    altra = [misura(SEMPLICE, _esito([89]), 1), misura(COMPOSTA, _esito([89, 208]), 1), misura(SENZA, _esito([5]), 1)]
    migliorati, peggiorati = variazioni(base, altra)
    assert len(migliorati) == 2 and peggiorati == []
    assert "Farina negli gnocchi?" in migliorati[0] and "posizione 2 → 1" in migliorati[0]
    assert "parti 1/2 → 2/2" in migliorati[1]
    migliorati, peggiorati = variazioni(altra, base)
    assert migliorati == [] and len(peggiorati) == 2
    astenuta = [misura(SEMPLICE, _esito([1, 89]), 1), misura(COMPOSTA, _esito([89]), 1), misura(SENZA, _esito([]), 1)]
    migliorati, _ = variazioni(base, astenuta)
    assert migliorati == ["«Tiramisù?» (senza risposta): astensione no → sì"]


def test_tabella_e_rapporto():
    per_config = {"base": [misura(SEMPLICE, _esito([89]), 100)],
                  "reranking": [misura(SEMPLICE, _esito([2, 89], 1), 900)]}
    tabella = tabella_metriche({n: metriche(m) for n, m in per_config.items()}, k=5)
    assert "| base |" in tabella and "| reranking |" in tabella and "1/1" in tabella
    testo = rapporto(per_config, k=5, intestazione="- Data: oggi")
    assert "## Casi migliorati e peggiorati rispetto a base" in testo
    assert "### reranking" in testo and "posizione 1 → 2" in testo
    assert "Misura dettagliata" in testo


def test_esegui_confronto_con_pipeline_finta():
    from rag.confronto import esegui_confronto
    risposte = {"base": [1, 89], "reranking": [89]}
    chiamate = []

    def finta(testo, k, modalita):
        chiamate.append((testo, k, modalita))
        return _esito(risposte[modalita], chiamate=1 if modalita != "base" else 0)

    per_config = esegui_confronto([SEMPLICE, SENZA], ["base", "reranking"], 5, finta)
    assert list(per_config) == ["base", "reranking"]
    assert chiamate == [(SEMPLICE.testo, 5, "base"), (SENZA.testo, 5, "base"),
                        (SEMPLICE.testo, 5, "reranking"), (SENZA.testo, 5, "reranking")]
    assert [m.posizione for m in per_config["reranking"]] == [1, None]
    assert metriche(per_config["reranking"])["chiamate_llm"] == 2
