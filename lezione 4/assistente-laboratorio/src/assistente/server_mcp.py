"""Server FastMCP che espone gli strumenti del catalogo (variante 03).

Avvio: uvicorn assistente.server_mcp:app --port 8002   (endpoint MCP: /mcp)
"""
from typing import Any

import anyio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool, ToolResult
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr, ValidationError

from assistente.catalogo import strumenti_locali


class StrumentoMCP(Tool):
    """Strumento MCP che pubblica nome, descrizione e schema del catalogo così come sono."""

    _strumento: BaseTool = PrivateAttr()

    @classmethod
    def da_catalogo(cls, strumento: BaseTool) -> "StrumentoMCP":
        voce = cls(name=strumento.name, description=strumento.description,
                   parameters=strumento.args_schema.model_json_schema())
        voce._strumento = strumento
        return voce

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            validati = self._strumento.args_schema.model_validate(arguments)
        except ValidationError as errore:
            campi = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                              for e in errore.errors())
            raise ToolError(f"argomenti non validi: {campi}") from None
        # Gli strumenti sono sincroni: girano in un thread per non bloccare il server.
        risultato = await anyio.to_thread.run_sync(self._strumento.invoke, validati.model_dump())
        return ToolResult(content=str(risultato))


def crea_server(strumenti: list[BaseTool]) -> FastMCP:
    """Server con uno strumento MCP per ogni voce; gli errori degli strumenti restano risultati."""
    return FastMCP("strumenti-assistente", tools=[StrumentoMCP.da_catalogo(s) for s in strumenti])


server = crea_server(strumenti_locali())
app = server.http_app()
