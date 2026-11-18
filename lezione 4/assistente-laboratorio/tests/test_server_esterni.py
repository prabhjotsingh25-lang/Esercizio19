"""Server MCP esterni dichiarati in un file mcpServers: discovery e chiamate, senza servizi veri."""
import json

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from assistente.server_esterni import (
    ErroreServerMCP, ServerMCP, leggi_server, strumenti_esterni, strumenti_server)

RISULTATO = {"modalita": "base", "query_usate": ["gnocchi"],
             "passaggi": [{"id": "89.0", "ricetta": 89, "titolo": "Gnocchi di patate", "capitolo": "x",
                           "posizione_chunk": 0, "score": 0.77, "testo": "Patate grosse e gialle"}],
             "nota": ""}


def server_ricerca_finto(risultato=RISULTATO) -> FastMCP:
    server = FastMCP("ricerca-finta")

    @server.tool(description="Cerca nel libro dell'Artusi. Cita gli id tra parentesi quadre.")
    def search_documents(query: str, top_k: int = 5, filtro: str | None = None) -> dict:
        if not query.strip():
            raise ToolError("query è vuota")
        return risultato

    return server


RICERCA = ServerMCP(nome="ricerca", command="python", args=("-m", "rag.server_mcp"), cwd=None, url=None)


def _strumenti(server=None):
    server = server or server_ricerca_finto()
    return {s.name: s for s in strumenti_server(RICERCA, crea_client=lambda: Client(server))}


def test_discovery_nome_descrizione_schema():
    s = _strumenti()["search_documents"]
    assert "parentesi quadre" in s.description
    assert s.args_schema["required"] == ["query"]
    assert set(s.args_schema["properties"]) == {"query", "top_k", "filtro"}


def test_chiamata_restituisce_il_json():
    testo = _strumenti()["search_documents"].invoke({"query": "gnocchi"})
    assert json.loads(testo) == RISULTATO


def test_errore_del_tool():
    testo = _strumenti()["search_documents"].invoke({"query": " "})
    assert testo.startswith("Errore:") and "query è vuota" in testo


class ClientCheCadeInChiamata:
    def __init__(self, vero):
        self.vero, self.aperture = vero, 0

    def __call__(self):
        self.aperture += 1
        if self.aperture > 1:
            raise OSError("processo terminato")
        return self.vero


def test_server_che_cade_dopo_la_discovery():
    fabbrica = ClientCheCadeInChiamata(Client(server_ricerca_finto()))
    s = {t.name: t for t in strumenti_server(RICERCA, crea_client=fabbrica)}["search_documents"]
    testo = s.invoke({"query": "gnocchi"})
    assert testo == 'Errore: server MCP "ricerca" non raggiungibile (OSError).'


def test_discovery_fallita():
    def rotto():
        raise OSError("comando inesistente")
    with pytest.raises(ErroreServerMCP, match='"ricerca".*OSError'):
        strumenti_server(RICERCA, crea_client=rotto)


# --- file dei server ---

def _file(tmp_path, contenuto) -> str:
    percorso = tmp_path / "server_mcp.json"
    percorso.write_text(contenuto if isinstance(contenuto, str) else json.dumps(contenuto), encoding="utf-8")
    return str(percorso)


def test_leggi_server_percorsi_relativi_con_spazi(tmp_path):
    p = _file(tmp_path, {"mcpServers": {"ricerca": {
        "command": "../../lezione 6/rag-artusi/.venv/Scripts/python.exe",
        "args": ["-m", "rag.server_mcp"], "cwd": "../../lezione 6/rag-artusi", "timeout": 90}}})
    (s,) = leggi_server(p)
    base = tmp_path.resolve()
    assert s.nome == "ricerca" and s.args == ("-m", "rag.server_mcp") and s.timeout == 90
    assert s.cwd == str((base / "../../lezione 6/rag-artusi").resolve())
    assert s.command == str((base / "../../lezione 6/rag-artusi/.venv/Scripts/python.exe").resolve())


def test_comando_senza_percorso_resta_com_e(tmp_path):
    (s,) = leggi_server(_file(tmp_path, {"mcpServers": {"r": {"command": "python"}}}))
    assert s.command == "python" and s.args == () and s.timeout == 120


@pytest.mark.parametrize("contenuto, messaggio", [
    ("{rotto", "JSON non valido"),
    ({"altro": {}}, "mcpServers"),
    ({"mcpServers": {}}, "mcpServers"),
    ({"mcpServers": {"r": {"args": []}}}, "command"),
    ({"mcpServers": {"r": {"command": "python", "timeout": 0}}}, "timeout"),
])
def test_file_non_valido(tmp_path, contenuto, messaggio):
    with pytest.raises(ErroreServerMCP, match=messaggio):
        leggi_server(_file(tmp_path, contenuto))


def test_file_assente(tmp_path):
    with pytest.raises(ErroreServerMCP, match="non trovato"):
        leggi_server(str(tmp_path / "manca.json"))


def test_strumenti_esterni_e_nome_duplicato(tmp_path):
    p = _file(tmp_path, {"mcpServers": {"ricerca": {"command": "python"}}})
    finto = server_ricerca_finto()
    nomi = [s.name for s in strumenti_esterni(p, ["ora_corrente"], lambda server: lambda: Client(finto))]
    assert nomi == ["search_documents"]
    with pytest.raises(ErroreServerMCP, match="search_documents.*già"):
        strumenti_esterni(p, ["search_documents"], lambda server: lambda: Client(finto))
