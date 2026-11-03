import json
from datetime import date, timedelta

import pytest
from finti import ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.grafo import costruisci_grafo
from assistente.scadenze import PERCORSO_FESTIVITA, calcola_giorni, crea_strumento_scadenze

NOTA = "(Calcolo indicativo, non normativo.)"
NOTA_LAVORATIVI = ("(Calcolo indicativo, non normativo: festività nazionali italiane "
                   "da file locale, escluse le patronali.)")


# --- conteggio fra due date ---------------------------------------------------------------

@pytest.mark.parametrize("inizio, fine, atteso", [
    ("2026-11-03", "2026-12-25", "Dal 2026-11-03 al 2026-12-25: 52 giorni di calendario."),
    ("2026-11-03", "2026-11-04", "Dal 2026-11-03 al 2026-11-04: 1 giorno di calendario."),
    ("2026-11-03", "2026-11-03", "Dal 2026-11-03 al 2026-11-03: 0 giorni di calendario."),
    ("2026-12-25", "2026-11-03", "Dal 2026-12-25 al 2026-11-03: -52 giorni di calendario."),
    ("2040-01-01", "2040-03-01", "Dal 2040-01-01 al 2040-03-01: 60 giorni di calendario."),
])
def test_conteggio_di_calendario(inizio, fine, atteso):
    assert calcola_giorni(inizio, data_fine=fine) == f"{atteso} {NOTA}"


@pytest.mark.parametrize("inizio, fine, atteso", [
    ("2026-12-21", "2026-12-31", "Dal 2026-12-21 al 2026-12-31: 7 giorni lavorativi; "
                                 "festività escluse: 2026-12-25."),
    ("2026-12-31", "2026-12-21", "Dal 2026-12-31 al 2026-12-21: -7 giorni lavorativi; "
                                 "festività escluse: 2026-12-25."),
    ("2026-11-02", "2026-11-06", "Dal 2026-11-02 al 2026-11-06: 4 giorni lavorativi; "
                                 "festività escluse: nessuna."),
    ("2025-12-31", "2026-12-31", "Dal 2025-12-31 al 2026-12-31: 254 giorni lavorativi; "
                                 "festività escluse: 2026-01-01, 2026-01-06, 2026-04-06, "
                                 "2026-05-01, 2026-06-02, 2026-12-08, 2026-12-25."),
])
def test_conteggio_lavorativo(inizio, fine, atteso):
    assert calcola_giorni(inizio, data_fine=fine, solo_lavorativi=True) == f"{atteso} {NOTA_LAVORATIVI}"


# --- scadenza ------------------------------------------------------------------------------

@pytest.mark.parametrize("inizio, giorni, atteso", [
    ("2026-11-03", 10, "2026-11-03 + 10 giorni = 2026-11-13 (venerdì)."),
    ("2028-02-28", 2, "2028-02-28 + 2 giorni = 2028-03-01 (mercoledì)."),
    ("2026-11-03", -10, "2026-11-03 - 10 giorni = 2026-10-24 (sabato)."),
    ("2026-11-03", 0, "2026-11-03 + 0 giorni = 2026-11-03 (martedì)."),
    ("2026-11-03", 1, "2026-11-03 + 1 giorno = 2026-11-04 (mercoledì)."),
])
def test_scadenza_di_calendario(inizio, giorni, atteso):
    assert calcola_giorni(inizio, giorni=giorni) == f"{atteso} {NOTA}"


@pytest.mark.parametrize("inizio, giorni, atteso", [
    ("2026-11-03", 10, "2026-11-03 + 10 giorni lavorativi = 2026-11-17 (martedì); "
                       "festività saltate: nessuna."),
    ("2026-12-07", 2, "2026-12-07 + 2 giorni lavorativi = 2026-12-10 (giovedì); "
                      "festività saltate: 2026-12-08."),
    ("2026-04-03", 1, "2026-04-03 + 1 giorno lavorativo = 2026-04-07 (martedì); "
                      "festività saltate: 2026-04-06."),
    ("2026-12-31", 1, "2026-12-31 + 1 giorno lavorativo = 2027-01-04 (lunedì); "
                      "festività saltate: 2027-01-01."),
    ("2026-11-17", -10, "2026-11-17 - 10 giorni lavorativi = 2026-11-03 (martedì); "
                        "festività saltate: nessuna."),
])
def test_scadenza_lavorativa(inizio, giorni, atteso):
    assert calcola_giorni(inizio, giorni=giorni, solo_lavorativi=True) == f"{atteso} {NOTA_LAVORATIVI}"


# --- errori --------------------------------------------------------------------------------

@pytest.mark.parametrize("data", ["03/11/2026", "2026-02-30", "20261103", "2026-W45-2", "", "domani"])
def test_data_non_valida(data):
    risultato = calcola_giorni(data, giorni=1)
    assert risultato.startswith(f"Errore: data_inizio non valida: '{data}'.")
    assert "AAAA-MM-GG" in risultato


def test_data_fine_non_valida():
    assert calcola_giorni("2026-11-03", data_fine="31-12-2026").startswith(
        "Errore: data_fine non valida: '31-12-2026'.")


@pytest.mark.parametrize("argomenti", [{}, {"data_fine": "2026-12-25", "giorni": 3}, {"data_fine": ""}])
def test_serve_esattamente_una_modalita(argomenti):
    assert calcola_giorni("2026-11-03", **argomenti).startswith(
        "Errore: indica esattamente uno tra data_fine")


@pytest.mark.parametrize("giorni", [3651, -3651])
def test_giorni_fuori_intervallo(giorni):
    assert calcola_giorni("2026-11-03", giorni=giorni) == (
        "Errore: giorni deve essere compreso fra -3650 e 3650.")


def test_date_troppo_distanti():
    assert calcola_giorni("2000-01-01", data_fine="2026-01-01") == (
        "Errore: le date distano più di 3650 giorni.")


@pytest.mark.parametrize("argomenti", [
    {"data_fine": "2031-01-10"}, {"giorni": 300}, {"data_fine": "2024-12-20"}])
def test_anno_non_coperto_per_i_lavorativi(argomenti):
    risultato = calcola_giorni("2030-12-20", solo_lavorativi=True, **argomenti)
    assert risultato.startswith("Errore: festività non disponibili per il ")
    assert "2025-2030" in risultato


def test_anno_non_coperto_va_bene_per_il_calendario():
    assert calcola_giorni("2030-12-20", data_fine="2031-01-10").startswith("Dal 2030-12-20")


@pytest.mark.parametrize("contenuto", [None, "non è json", '{"fisse": ["13-45"], "pasquetta": {}}',
                                       '{"fisse": "01-01"}', "[]"])
def test_file_festivita_mancante_o_rovinato(tmp_path, contenuto):
    percorso = tmp_path / "festivita.json"
    if contenuto is not None:
        percorso.write_text(contenuto, encoding="utf-8")
    risultato = calcola_giorni("2026-11-03", giorni=3, solo_lavorativi=True, percorso=percorso)
    assert risultato == "Errore: file delle festività non disponibile o non valido."
    assert calcola_giorni("2026-11-03", giorni=3, percorso=percorso).startswith("2026-11-03 + 3")


# --- file delle festività --------------------------------------------------------------------

def _pasqua(anno: int) -> date:
    """Algoritmo anonimo gregoriano (Meeus/Jones/Butcher)."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(anno, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


def test_file_festivita_coerente():
    dati = json.loads(PERCORSO_FESTIVITA.read_text(encoding="utf-8"))
    assert sorted(dati["pasquetta"]) == [str(a) for a in range(2025, 2031)]
    for anno, giorno in dati["pasquetta"].items():
        assert date.fromisoformat(giorno) == _pasqua(int(anno)) + timedelta(days=1), anno
    assert dati["fisse"] == ["01-01", "01-06", "04-25", "05-01", "06-02",
                             "08-15", "11-01", "12-08", "12-25", "12-26"]


# --- strumento e grafo -----------------------------------------------------------------------

def test_strumento_langchain():
    strumento = crea_strumento_scadenze()
    assert strumento.name == "giorni_scadenze"
    schema = strumento.args_schema.model_json_schema()
    assert schema["required"] == ["data_inizio"]
    assert set(schema["properties"]) == {"data_inizio", "data_fine", "giorni", "solo_lavorativi"}
    assert "AAAA-MM-GG" in strumento.description
    assert strumento.invoke({"data_inizio": "2026-12-21", "data_fine": "2026-12-31",
                             "solo_lavorativi": True}).startswith("Dal 2026-12-21 al 2026-12-31: 7 giorni")


def test_ciclo_completo_nel_grafo():
    richiesta = AIMessage("", tool_calls=[{"name": "giorni_scadenze", "id": "s1", "args": {
        "data_inizio": "2026-12-07", "giorni": 2, "solo_lavorativi": True}}])
    m = ModelloFinto(risposte=[richiesta, AIMessage("La scadenza è giovedì 10 dicembre.")])
    out = costruisci_grafo(m, [crea_strumento_scadenze()], 3).invoke(
        {"messages": [HumanMessage("Scadenza a 2 giorni lavorativi dal 7 dicembre?")], "passaggi": 0})
    risultati = [t.content for t in out["messages"] if isinstance(t, ToolMessage)]
    assert risultati[0].startswith("2026-12-07 + 2 giorni lavorativi = 2026-12-10 (giovedì)")
