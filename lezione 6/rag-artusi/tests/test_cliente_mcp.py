from rag.cliente_mcp import argomenti_tool, crea_parser, formatta


def test_argomenti_tool():
    a = crea_parser().parse_args(["Che vino per il pollo?", "--top-k", "3", "--filtro", "Fritti"])
    assert argomenti_tool(a) == {"query": "Che vino per il pollo?", "top_k": 3, "filtro": "Fritti"}
    b = crea_parser().parse_args(["brodo"])
    assert argomenti_tool(b) == {"query": "brodo"}


def test_formatta_risultato_ed_errore():
    ok = formatta(False, '{"modalita": "base", "passaggi": []}')
    assert ok.startswith("esito: ok") and '"modalita": "base"' in ok
    assert formatta(True, "filtro non valido").startswith("esito: errore del tool")
