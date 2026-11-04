import sqlite3

import pytest
from finti import ISTANTE, ModelloFinto
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.grafo import costruisci_grafo
from assistente.note import MAX_ELENCO, crea_strumento_note, gestisci_note


@pytest.fixture
def db(tmp_path):
    return tmp_path / "note.sqlite"


def _note(db, azione, **argomenti):
    return gestisci_note(azione, percorso=db, adesso=lambda: ISTANTE, **argomenti)


# --- aggiunta ed elenco ----------------------------------------------------------------------

def test_aggiunta(db):
    assert _note(db, "aggiungi", testo="  comprare i fusibili  ") == 'Nota 1 salvata: "comprare i fusibili".'
    assert _note(db, "aggiungi", testo="tarare l'oscilloscopio") == "Nota 2 salvata: \"tarare l'oscilloscopio\"."


def test_elenco_vuoto(db):
    assert _note(db, "elenca") == "Nessuna nota salvata."


def test_elenco(db):
    _note(db, "aggiungi", testo="prima")
    _note(db, "aggiungi", testo="seconda")
    assert _note(db, "elenca") == (
        "Note salvate (2):\n"
        "- 1 · 2026-10-26 09:30 · prima\n"
        "- 2 · 2026-10-26 09:30 · seconda")


def test_elenco_troppo_lungo_mostra_le_ultime(db):
    for i in range(1, MAX_ELENCO + 6):
        _note(db, "aggiungi", testo=f"nota {i}")
    righe = _note(db, "elenca").splitlines()
    assert righe[0] == f"Note salvate: {MAX_ELENCO + 5}; mostrate le ultime {MAX_ELENCO}."
    assert righe[1].startswith("- 6 ·") and righe[-1].startswith(f"- {MAX_ELENCO + 5} ·")


def test_le_note_restano_fra_un_avvio_e_l_altro(db):
    crea_strumento_note(db).invoke({"azione": "aggiungi", "testo": "persistente"})
    nuovo = crea_strumento_note(db)  # come se l'assistente fosse stato riavviato
    assert "persistente" in nuovo.invoke({"azione": "elenca"})


# --- eliminazione con conferma ---------------------------------------------------------------

def test_eliminazione_in_due_passi(db):
    _note(db, "aggiungi", testo="comprare i fusibili")
    anteprima = _note(db, "elimina", id=1)
    assert anteprima.startswith('Stai per eliminare la nota 1: "comprare i fusibili". Chiedi conferma')
    assert "conferma=true" in anteprima
    assert "comprare i fusibili" in _note(db, "elenca")  # il primo passo non cancella
    assert _note(db, "elimina", id=1, conferma=True) == 'Nota 1 eliminata: "comprare i fusibili".'
    assert _note(db, "elenca") == "Nessuna nota salvata."


def test_conferma_senza_primo_passo_diventa_il_primo_passo(db):
    # Il modello a volte chiede conferma a parole e poi chiama subito con conferma=true:
    # lo strumento non cancella, fa il primo passo e chiede di nuovo conferma.
    _note(db, "aggiungi", testo="da tenere")
    assert _note(db, "elimina", id=1, conferma=True).startswith(
        'Prima di eliminare serve la conferma dell\'utente. Stai per eliminare la nota 1: "da tenere".')
    assert "da tenere" in _note(db, "elenca")
    assert _note(db, "elimina", id=1, conferma=True) == 'Nota 1 eliminata: "da tenere".'


def test_la_conferma_vale_una_volta_sola(db):
    _note(db, "aggiungi", testo="a")
    _note(db, "elimina", id=1)
    _note(db, "elimina", id=1, conferma=True)
    _note(db, "aggiungi", testo="b")  # id 2: gli id non vengono riusati
    assert _note(db, "elimina", id=2, conferma=True).startswith("Prima di eliminare serve la conferma")
    assert "b" in _note(db, "elenca")


def test_servono_sempre_due_chiamate(db):
    _note(db, "aggiungi", testo="a")
    for conferma in (True, False):
        assert "Stai per eliminare la nota 1" in _note(db, "elimina", id=1, conferma=conferma)
        assert "- 1 ·" in _note(db, "elenca")


def test_gli_id_non_vengono_riusati(db):
    _note(db, "aggiungi", testo="a")
    _note(db, "elimina", id=1)
    _note(db, "elimina", id=1, conferma=True)
    assert _note(db, "aggiungi", testo="b") == 'Nota 2 salvata: "b".'


@pytest.mark.parametrize("conferma", [False, True])
def test_eliminazione_di_nota_inesistente(db, conferma):
    assert _note(db, "elimina", id=7, conferma=conferma) == "Nessuna nota con id 7."


# --- errori ----------------------------------------------------------------------------------

@pytest.mark.parametrize("testo", ["", "   "])
def test_aggiunta_senza_testo(db, testo):
    assert _note(db, "aggiungi", testo=testo) == "Errore: per aggiungere una nota serve il testo."


def test_testo_troppo_lungo(db):
    assert _note(db, "aggiungi", testo="x" * 501) == "Errore: testo troppo lungo (massimo 500 caratteri)."
    assert _note(db, "elenca") == "Nessuna nota salvata."


def test_eliminazione_senza_id(db):
    assert _note(db, "elimina") == "Errore: per eliminare una nota serve il suo id (vedi azione elenca)."


def test_azione_sconosciuta(db):
    assert _note(db, "modifica").startswith("Errore: azione sconosciuta: 'modifica'.")


def test_database_rovinato(db):
    db.write_bytes(b"questo non e' un database sqlite" * 10)
    assert _note(db, "elenca") == "Errore: archivio delle note non disponibile."


def test_cartella_inesistente(tmp_path):
    assert _note(tmp_path / "manca" / "note.sqlite", "elenca") == (
        "Errore: archivio delle note non disponibile.")


def test_percorso_da_variabile_d_ambiente(tmp_path, monkeypatch):
    percorso = tmp_path / "da_env.sqlite"
    monkeypatch.setenv("NOTE_DB", str(percorso))
    crea_strumento_note().invoke({"azione": "aggiungi", "testo": "x"})
    with sqlite3.connect(percorso) as conn:
        assert conn.execute("SELECT testo FROM note").fetchall() == [("x",)]


# --- strumento e grafo -----------------------------------------------------------------------

def test_strumento_langchain(db):
    strumento = crea_strumento_note(db)
    assert strumento.name == "note_persistenti"
    schema = strumento.args_schema.model_json_schema()
    assert schema["required"] == ["azione"]
    assert schema["properties"]["azione"]["enum"] == ["aggiungi", "elenca", "elimina"]
    assert set(schema["properties"]) == {"azione", "testo", "id", "conferma"}
    assert "conferma" in strumento.description
    assert "ricordami" in strumento.description  # «ricordami di...» va salvato come nota
    with pytest.raises(Exception, match="validation error"):
        strumento.invoke({"azione": "modifica"})


def test_ciclo_con_conferma_nel_grafo(db):
    def chiamata(i, **argomenti):
        return AIMessage("", tool_calls=[{"name": "note_persistenti", "args": argomenti, "id": i}])
    strumento = crea_strumento_note(db)
    _note(db, "aggiungi", testo="comprare i fusibili")
    primo = ModelloFinto(risposte=[chiamata("a", azione="elimina", id=1),
                                   AIMessage("Confermi l'eliminazione?")])
    out = costruisci_grafo(primo, [strumento], 3).invoke(
        {"messages": [HumanMessage("Cancella la nota 1")], "passaggi": 0})
    secondo = ModelloFinto(risposte=[chiamata("b", azione="elimina", id=1, conferma=True),
                                     AIMessage("Fatto.")])
    out = costruisci_grafo(secondo, [strumento], 3).invoke(
        {"messages": [*out["messages"], HumanMessage("Sì")], "passaggi": 0})
    risultati = [t.content for t in out["messages"] if isinstance(t, ToolMessage)]
    assert risultati[0].startswith("Stai per eliminare la nota 1")
    assert risultati[1] == 'Nota 1 eliminata: "comprare i fusibili".'
