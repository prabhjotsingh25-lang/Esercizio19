"""Archivio del back-end: stesse prove sull'archivio in memoria e su PostgreSQL vero.

Le prove PostgreSQL usano il database `assistente_test` (creato se manca) sul server di
DATABASE_URL; si attivano con `pytest -m postgres`.
"""
from urllib.parse import urlparse

import pytest
from dotenv import dotenv_values

from assistente.archivio import ArchivioMemoria, ArchivioPostgres

PREFERENZE = {"lingua": "it", "fuso_orario": "Europe/Rome", "stile": "sintetico"}


def _url_di_test() -> str:
    url = dotenv_values(".env").get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL mancante in .env")
    return urlparse(url)._replace(path="/assistente_test").geturl()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.postgres)])
def archivio(request):
    if request.param == "memoria":
        return ArchivioMemoria()
    url = _url_di_test()
    ArchivioPostgres.crea_database(url)
    a = ArchivioPostgres(url)
    a.svuota()  # solo nel database di test
    return a


def test_conversazione_creata_e_letta(archivio):
    c = archivio.crea(PREFERENZE)
    letta = archivio.leggi(c.id)
    assert letta.preferenze == PREFERENZE and letta.titolo is None and letta.riassunto == ""
    assert letta.cronologia_agente == [] and not letta.turno_in_corso
    assert archivio.leggi("00000000-0000-0000-0000-000000000000") is None


def test_messaggi_in_ordine_con_strumenti_prompt_e_stato(archivio):
    c = archivio.crea(PREFERENZE)
    d = archivio.aggiungi(c.id, "utente", "Che ore sono?", stato="in_attesa")
    archivio.aggiorna_domanda(d.id, stato="risposta")
    r = archivio.aggiungi(c.id, "assistente", "Sono le 12.",
                          strumenti=[{"nome": "ora_corrente", "argomenti": {"fuso_orario": "Europe/Rome"},
                                      "risultato": "12:00"}])
    p = archivio.aggiungi(c.id, "utente", "/prompt spiega", stato="in_attesa",
                          prompt={"nome": "spiega", "argomenti": {"argomento": "MCP"}})
    archivio.aggiorna_domanda(p.id, testo="Spiegami MCP", stato="errore", errore="agente spento")
    messaggi = archivio.messaggi(c.id)
    assert [(m.posizione, m.ruolo, m.testo, m.stato) for m in messaggi] == [
        (1, "utente", "Che ore sono?", "risposta"), (2, "assistente", "Sono le 12.", None),
        (3, "utente", "Spiegami MCP", "errore")]
    assert messaggi[1].strumenti[0]["nome"] == "ora_corrente" and messaggi[2].errore == "agente spento"
    assert messaggi[2].prompt == {"nome": "spiega", "argomenti": {"argomento": "MCP"}}
    assert r.id != d.id and archivio.leggi(c.id).aggiornata >= c.aggiornata
    archivio.elimina_messaggio(p.id)
    assert len(archivio.messaggi(c.id)) == 2


def test_stato_dell_agente_salvato_cosi_com_e(archivio):
    c = archivio.crea(PREFERENZE)
    cronologia = [{"ruolo": "utente", "testo": "ciao"}, {"ruolo": "assistente", "testo": "salve"}]
    archivio.salva_stato_agente(c.id, cronologia, "Utente: si chiama Anna.")
    letta = archivio.leggi(c.id)
    assert letta.cronologia_agente == cronologia and letta.riassunto == "Utente: si chiama Anna."


def test_un_solo_turno_alla_volta_e_azzeramento(archivio):
    c = archivio.crea(PREFERENZE)
    assert archivio.inizia_turno(c.id) is True
    assert archivio.inizia_turno(c.id) is False
    archivio.fine_turno(c.id)
    assert archivio.inizia_turno(c.id) is True
    d = archivio.aggiungi(c.id, "utente", "x", stato="in_attesa")
    archivio.azzera_turni()  # all'avvio: turni interrotti da un arresto
    assert archivio.leggi(c.id).turno_in_corso is False
    assert archivio.messaggi(c.id)[0].stato == "errore" and "interrotto" in archivio.messaggi(c.id)[0].errore
    assert d.stato == "in_attesa"


def test_titolo_preferenze_elenco_ed_eliminazione(archivio):
    a, b = archivio.crea(PREFERENZE), archivio.crea(PREFERENZE)
    archivio.imposta_titolo(a.id, "Primo titolo")
    archivio.imposta_titolo(a.id, "Non sovrascrive")
    archivio.aggiungi(a.id, "utente", "più recente", stato="risposta")
    archivio.aggiorna_preferenze(b.id, {**PREFERENZE, "lingua": "en"})
    assert archivio.leggi(a.id).titolo == "Primo titolo"
    assert archivio.leggi(b.id).preferenze["lingua"] == "en"
    assert [x.id for x in archivio.elenca()][0] == a.id  # dall'ultimo messaggio più recente
    assert archivio.elimina(b.id) is True and archivio.elimina(b.id) is False
    assert [x.id for x in archivio.elenca()] == [a.id]


@pytest.mark.postgres
def test_dati_presenti_con_una_nuova_connessione():
    # Come un riavvio del back-end: un nuovo archivio sullo stesso database vede le chat.
    url = _url_di_test()
    ArchivioPostgres.crea_database(url)
    primo = ArchivioPostgres(url)
    primo.svuota()
    c = primo.crea(PREFERENZE)
    primo.aggiungi(c.id, "utente", "resto qui?", stato="risposta")
    secondo = ArchivioPostgres(url)
    assert [m.testo for m in secondo.messaggi(c.id)] == ["resto qui?"]
    assert secondo.ping() is None
