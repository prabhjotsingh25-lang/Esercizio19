import asyncio

from fastmcp import Client

from rag.avanzata import Candidato
from rag.calibrazione import (SCHEMA_RICERCA, confronto_soglie, query_del_modello, riepilogo, riga_score, stat,
                              strumento_ricerca, tabella_due_riepiloghi, tabella_riepilogo, tabella_score)
from rag.llm import ErroreLLM
from rag.server_mcp import Servizi, crea_server
from tests.conftest import crea_config
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


# --- query formulata dal modello ---

class LLMStrumenti:
    def __init__(self, esito):
        self.esito, self.ricevuti = esito, []

    def argomenti_strumento(self, sistema, utente, strumento):
        self.ricevuti.append((sistema, utente, strumento))
        if isinstance(self.esito, BaseException):
            raise self.esito
        return self.esito


def test_schema_uguale_a_quello_del_server():
    async def elenca():
        async with Client(crea_server(Servizi(None, None, crea_config()))) as c:
            return await c.list_tools()
    (t,) = asyncio.run(elenca())
    pubblicato = {k: v for k, v in t.input_schema.items() if k != "additionalProperties"}
    assert pubblicato == SCHEMA_RICERCA
    assert strumento_ricerca()["description"] == t.description


def test_query_del_modello():
    llm = LLMStrumenti({"query": "  tiramisù  "})
    assert query_del_modello(llm, "Qual è la ricetta del tiramisù?") == ("tiramisù", "")
    assert llm.ricevuti[0][1] == "Qual è la ricetta del tiramisù?"
    assert query_del_modello(LLMStrumenti(None), "d") == (None, "il modello non ha chiamato la ricerca")
    assert query_del_modello(LLMStrumenti(ErroreLLM("HTTP 500")), "d")[0] is None


def test_tabelle_con_query_e_due_riepiloghi():
    riga = riga_score(SENZA, _esito([(3, 0.55)]))
    riga.update(query="tiramisù", motivo="")
    assert "| Tiramisù? | tiramisù | senza risposta | 0.550 |" in tabella_score([riga], k=5)
    intera = riepilogo([riga_score(CON, _esito([(89, 0.77)])), riga_score(SENZA, _esito([(3, 0.70)]))])
    modello = riepilogo([riga_score(CON, _esito([(89, 0.60)])), riga_score(SENZA, _esito([(3, 0.55)]))])
    testo = tabella_due_riepiloghi(intera, modello)
    assert "| Senza risposta: top-1 | 0.700 · 0.700 · 0.700 | 0.550 · 0.550 · 0.550 |" in testo
