"""Servizio FastAPI che espone gli strumenti del catalogo (variante 02).

Avvio: uvicorn assistente.servizio_http:app --port 8001
"""
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from assistente.catalogo import strumenti_locali


def crea_app(strumenti: list[BaseTool]) -> FastAPI:
    """Costruisce il servizio; gli errori degli strumenti restano risultati (200), come in locale."""
    app = FastAPI(title="Servizio strumenti dell'assistente")
    per_nome = {s.name: s for s in strumenti}

    @app.get("/strumenti")
    def elenco() -> list[dict[str, Any]]:
        return [{"nome": s.name, "descrizione": s.description,
                 "schema": s.args_schema.model_json_schema()} for s in strumenti]

    @app.post("/strumenti/{nome}")
    def esegui(nome: str, argomenti: dict[str, Any] = Body(...)) -> dict[str, str]:
        strumento = per_nome.get(nome)
        if strumento is None:
            raise HTTPException(404, f"strumento sconosciuto: {nome}")
        try:
            validati = strumento.args_schema.model_validate(argomenti)
        except ValidationError as errore:
            raise HTTPException(422, [
                {"campo": ".".join(str(p) for p in e["loc"]), "messaggio": e["msg"]}
                for e in errore.errors()]) from None
        return {"risultato": str(strumento.invoke(validati.model_dump()))}

    return app


app = crea_app(strumenti_locali())
