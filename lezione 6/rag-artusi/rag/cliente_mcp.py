"""Chiamata reale al server di ricerca via stdio, come farebbe l'agente.

Uso: python -m rag.cliente_mcp "domanda" [--top-k N] [--filtro CAPITOLO]
Avvia `python -m rag.server_mcp` come sottoprocesso (stesso interprete, cartella corrente),
stampa gli strumenti scoperti e il risultato. I log del server finiscono su stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from rag.server_mcp import NOME_TOOL


def crea_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rag.cliente_mcp")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--filtro", default=None)
    return parser


def argomenti_tool(args: argparse.Namespace) -> dict:
    argomenti = {"query": args.query}
    if args.top_k is not None:
        argomenti["top_k"] = args.top_k
    if args.filtro is not None:
        argomenti["filtro"] = args.filtro
    return argomenti


def formatta(errore: bool, testo: str) -> str:
    if errore:
        return f"esito: errore del tool\n{testo}"
    try:
        testo = json.dumps(json.loads(testo), ensure_ascii=False, indent=2)
    except ValueError:
        pass
    return f"esito: ok\n{testo}"


async def _chiama(argomenti: dict) -> tuple[list[str], bool, str]:
    trasporto = StdioTransport(sys.executable, ["-m", "rag.server_mcp"], keep_alive=False)
    async with Client(trasporto, timeout=120) as client:
        nomi = [t.name for t in await client.list_tools()]
        r = await client.call_tool(NOME_TOOL, argomenti, raise_on_error=False)
    return nomi, r.is_error, "".join(getattr(b, "text", "") for b in r.content)


def main(argv: list[str] | None = None) -> int:
    args = crea_parser().parse_args(argv)
    argomenti = argomenti_tool(args)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # la console di Windows non è UTF-8
    try:
        nomi, errore, testo = asyncio.run(_chiama(argomenti))
    except Exception as e:  # server che non parte, timeout
        print(f"Errore: server MCP non raggiungibile ({type(e).__name__}: {e})", file=sys.stderr)
        return 1
    print(f"strumenti: {', '.join(nomi)}")
    print(f"argomenti: {json.dumps(argomenti, ensure_ascii=False)}")
    print(formatta(errore, testo))
    return 1 if errore else 0


if __name__ == "__main__":
    sys.exit(main())
