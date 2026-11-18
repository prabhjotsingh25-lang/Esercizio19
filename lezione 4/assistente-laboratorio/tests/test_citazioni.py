import json

from assistente.citazioni import ControlloCitazioni, citazioni, controlla, id_ricevuti, riga_log


def _risultato(*ids):
    return json.dumps({"modalita": "base", "query_usate": ["q"],
                       "passaggi": [{"id": i, "testo": "t"} for i in ids], "nota": ""})


def test_citazioni_estratte_in_ordine_senza_ripetizioni():
    testo = "Servono 150 g [89.0]. Anche [89.1, 14.0]; di nuovo [89.0] e [208.0;209.0]."
    assert citazioni(testo) == ["89.0", "89.1", "14.0", "208.0", "209.0"]


def test_non_citazioni_ignorate():
    assert citazioni("Vedi [la ricetta](http://x) e [nota], niente id.") == []


def test_numero_senza_chunk_e_una_citazione():
    assert citazioni("Come dice [89].") == ["89"]


def test_id_ricevuti_solo_dai_json_con_passaggi():
    ids, ricerche = id_ricevuti([_risultato("89.0", "89.1"), "Errore: database spento",
                                 json.dumps({"ora": "10:00"}), _risultato("89.1", "14.0"), "12:30"])
    assert ids == ["89.0", "89.1", "14.0"] and ricerche == 2


def test_citazione_valida():
    c = controlla("Farina 150 g [89.0].", [_risultato("89.0", "89.1")])
    assert c == ControlloCitazioni(verificate=["89.0"], sconosciute=[], ricerche=1, passaggi_ricevuti=2)


def test_citazione_sconosciuta():
    c = controlla("Farina [89.0] e uova [999.0] [89].", [_risultato("89.0")])
    assert c.verificate == ["89.0"] and c.sconosciute == ["999.0", "89"]


def test_nessuna_citazione():
    c = controlla("Nel libro non ho trovato il tiramisù.", [_risultato("372.3")])
    assert c == ControlloCitazioni([], [], 1, 1)


def test_ricerca_vuota():
    assert controlla("Non c'è.", [_risultato()]) == ControlloCitazioni([], [], 1, 0)


def test_riga_log():
    assert riga_log(ControlloCitazioni(["89.0", "89.1"], [], 1, 5)) == \
        "citazioni verificate=89.0,89.1 sconosciute=- ricerche=1 passaggi_ricevuti=5"
