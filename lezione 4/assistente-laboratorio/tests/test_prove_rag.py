"""Script delle tracce della lezione 8: regole atteso/non atteso e formato, senza servizi."""
import json

from assistente.agente import EsitoTurno, StrumentoUsato
from assistente.citazioni import ControlloCitazioni
from assistente.prove_rag import CASI, markdown, traccia, valuta_caso

PER_NOME = {c.nome: c for c in CASI}
RISULTATO = json.dumps({"modalita": "base", "query_usate": ["q"], "nota": "",
                        "passaggi": [{"id": "89.0", "titolo": "Gnocchi di patate", "score": 0.77}]})


def test_quattro_casi():
    assert list(PER_NOME) == ["documentale", "ora", "generica", "senza_risposta"]


def test_documentale():
    caso = PER_NOME["documentale"]
    assert valuta_caso(caso, ["search_documents"], ["89.0"], []) == []
    assert valuta_caso(caso, [], [], []) == ["la ricerca non è stata chiamata", "nessuna citazione verificata"]
    assert "citazioni sconosciute: 999.0" in valuta_caso(caso, ["search_documents"], ["89.0"], ["999.0"])


def test_ora():
    caso = PER_NOME["ora"]
    assert valuta_caso(caso, ["ora_corrente"], [], []) == []
    assert valuta_caso(caso, ["search_documents"], [], []) == [
        "la ricerca è stata chiamata ma non doveva", "lo strumento ora_corrente non è stato chiamato"]


def test_generica():
    assert valuta_caso(PER_NOME["generica"], [], [], []) == []
    assert valuta_caso(PER_NOME["generica"], ["ora_corrente"], [], []) == ["strumenti chiamati: ora_corrente"]


def test_senza_risposta():
    caso = PER_NOME["senza_risposta"]
    assert valuta_caso(caso, ["search_documents"], [], []) == []
    assert valuta_caso(caso, ["search_documents"], ["372.3"], []) == ["citazioni presenti: 372.3"]


def test_traccia_e_markdown():
    esito = EsitoTurno(risposta="Servono 150 g [89.0].", messaggi=[], riassunto="",
                       strumenti=[StrumentoUsato("search_documents", {"query": "farina"}, RISULTATO)],
                       citazioni=ControlloCitazioni(["89.0"], [], 1, 1))
    t = traccia(PER_NOME["documentale"], esito, ["INFO assistente.agente citazioni ..."], ["riga server"], 12.34)
    assert t["esito"] == "atteso" and t["durata_s"] == 12.3
    assert t["strumenti"][0]["risultato"]["passaggi"][0]["id"] == "89.0"
    testo = markdown([t], "- Data: oggi")
    assert "| documentale |" in testo and "**atteso**" in testo
    assert "89.0 (Gnocchi di patate, 0.77)" in testo and "> Servono 150 g [89.0]." in testo
    assert "riga server" in testo


def test_serie_soglie_e_da_verificare():
    from assistente.prove_rag import CASI_SOGLIE, SERIE
    per_nome = {c.nome: c for c in CASI_SOGLIE}
    assert list(SERIE) == ["base", "soglie"] and len(CASI_SOGLIE) == 3
    media = per_nome["da_verificare"]
    assert valuta_caso(media, ["search_documents"], ["617.0"], [], "Croccante [617.0], da verificare sulla fonte.") == []
    assert "la risposta non dice «da verificare»" in valuta_caso(media, ["search_documents"], ["617.0"], [], "Croccante.")
    affidabile = per_nome["affidabile"]
    assert valuta_caso(affidabile, ["search_documents"], ["208.0"], [], "Vino rosso [208.0].") == []
    assert valuta_caso(affidabile, ["search_documents"], ["208.0"], [], "Vino [208.0], da verificare.") == [
        "la risposta dice «da verificare» ma i passaggi erano affidabili"]
