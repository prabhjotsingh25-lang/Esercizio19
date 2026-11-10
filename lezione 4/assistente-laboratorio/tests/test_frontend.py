"""Front-end: file serviti, config.js dalla configurazione, contratto di app.js con il back-end."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from assistente.frontend import crea_frontend

RADICE = Path(__file__).parent.parent
WEB = RADICE / "src" / "assistente" / "web"
CHIAMATA = re.compile(r'api\("(GET|POST|PUT|DELETE)",\s*`([^`]*)`')


def _client():
    return TestClient(crea_frontend("http://backend.esempio:8080", 900))


def test_serve_pagina_stile_e_script():
    client = _client()
    pagina = client.get("/")
    assert pagina.status_code == 200 and "text/html" in pagina.headers["content-type"]
    assert '<script src="config.js"></script>' in pagina.text and 'src="app.js"' in pagina.text
    assert client.get("/stile.css").status_code == 200
    script = client.get("/app.js")
    assert "async function api(" in script.text
    assert script.headers["cache-control"] == "no-cache"  # niente versioni vecchie dalla cache


def test_config_js_dalla_configurazione():
    r = _client().get("/config.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-store"
    assert r.text == ('window.CONFIG = {"backendUrl": "http://backend.esempio:8080", '
                      '"timeoutMs": 960000};\n')


def test_nessun_indirizzo_scritto_nel_codice_del_front_end():
    for file in WEB.iterdir():
        testo = file.read_text(encoding="utf-8")
        assert not re.search(r"https?://|localhost|127\.0\.0\.1", testo), file.name


def test_contratto_app_js_con_docs_openapi_backend():
    spec = json.loads((RADICE / "docs" / "openapi-backend.json").read_text(encoding="utf-8"))
    codice = (WEB / "app.js").read_text(encoding="utf-8")
    chiamate = CHIAMATA.findall(codice)
    assert chiamate, "nessuna chiamata api() trovata"
    # ogni fetch passa da api(): nessuna chiamata diretta altrove
    assert codice.count("fetch(") == 1
    usate = set()
    for metodo, percorso in chiamate:
        modello = re.sub(r"\$\{[^}]+\}", "{id}", percorso)
        assert modello in spec["paths"], f"{metodo} {modello} non è nel contratto"
        assert metodo.lower() in spec["paths"][modello], f"{metodo} {modello} non è nel contratto"
        usate.add((metodo, modello))
    assert usate == {("GET", "/conversazioni"), ("POST", "/conversazioni"),
                     ("GET", "/conversazioni/{id}"), ("DELETE", "/conversazioni/{id}"),
                     ("POST", "/conversazioni/{id}/messaggi"), ("POST", "/conversazioni/{id}/riprova")}
    # il corpo dell'invio ha i campi richiesti dal contratto
    richiesta = spec["components"]["schemas"]["RichiestaTesto"]
    assert richiesta["required"] == ["testo"] and "{ testo }" in codice
