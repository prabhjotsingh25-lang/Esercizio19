"""Servizio FastAPI degli strumenti, provato con TestClient (nessuna rete)."""
import pytest
from fastapi.testclient import TestClient
from finti import ISTANTE

from assistente.catalogo import strumenti_locali
from assistente.servizio_http import crea_app


@pytest.fixture
def client():
    return TestClient(crea_app(strumenti_locali(lambda: ISTANTE)))


def test_elenco_strumenti(client):
    risposta = client.get("/strumenti")
    assert risposta.status_code == 200
    nomi = [s["nome"] for s in risposta.json()]
    assert nomi == ["ora_corrente", "convertitore_unita", "calcolatrice_sicura", "giorni_scadenze",
                    "catalogo_locale"]
    assert all(s["descrizione"] and s["schema"]["properties"] for s in risposta.json())


@pytest.mark.parametrize("nome, argomenti, atteso", [
    ("ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "2026-10-26T18:30:05+09:00 (Asia/Tokyo)"),
    ("convertitore_unita", {"valore": 1.5, "da": "km", "a": "m"}, "1.5 km = 1500 m"),
    ("calcolatrice_sicura", {"espressione": "(17 + 4) * 3"}, "(17 + 4) * 3 = 63"),
])
def test_esecuzione_valida(client, nome, argomenti, atteso):
    risposta = client.post(f"/strumenti/{nome}", json=argomenti)
    assert risposta.status_code == 200 and risposta.json() == {"risultato": atteso}


def test_errore_dello_strumento_resta_un_risultato(client):
    risposta = client.post("/strumenti/calcolatrice_sicura", json={"espressione": "1 / 0"})
    assert risposta.status_code == 200
    assert risposta.json() == {"risultato": "Errore: divisione per zero."}


def test_strumento_sconosciuto(client):
    risposta = client.post("/strumenti/meteo", json={})
    assert risposta.status_code == 404 and "meteo" in risposta.json()["detail"]


@pytest.mark.parametrize("argomenti", [{}, {"valore": "tanti", "da": "km", "a": "m"}])
def test_argomenti_non_validi(client, argomenti):
    risposta = client.post("/strumenti/convertitore_unita", json=argomenti)
    assert risposta.status_code == 422
    assert any(e["campo"] == "valore" for e in risposta.json()["detail"])


def test_corpo_non_oggetto(client):
    assert client.post("/strumenti/convertitore_unita", json=[1, 2]).status_code == 422
