"""Front-end: pagina di chat statica (HTML, CSS e JavaScript senza librerie) servita da FastAPI.

Il browser parla solo con il back-end, all'indirizzo BACKEND_URL che la pagina legge da
/config.js (generato qui dalla configurazione: nel JavaScript non c'è nessun indirizzo).
Avvio: python -m assistente.frontend   (host e porta da FRONTEND_HOST e FRONTEND_PORTA)
"""
import json
import sys
from importlib import resources

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

MARGINE_TIMEOUT_SECONDI = 60  # il browser aspetta un po' più del back-end, che aspetta l'agente


def crea_frontend(backend_url: str, agente_timeout: int) -> FastAPI:
    app = FastAPI(title="Front-end dell'assistente di laboratorio", docs_url=None,
                  redoc_url=None, openapi_url=None)
    configurazione = {"backendUrl": backend_url,
                      "timeoutMs": (agente_timeout + MARGINE_TIMEOUT_SECONDI) * 1000}

    @app.get("/config.js")
    def config_js() -> Response:
        testo = f"window.CONFIG = {json.dumps(configurazione)};\n"
        return Response(testo, media_type="text/javascript",
                        headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def sempre_aggiornato(richiesta, prossimo):
        # Il browser ricontrolla i file a ogni caricamento: dopo un aggiornamento niente
        # pagina vecchia dalla cache (i file sono piccoli).
        risposta = await prossimo(richiesta)
        risposta.headers.setdefault("Cache-Control", "no-cache")
        return risposta

    cartella = resources.files("assistente").joinpath("web")
    app.mount("/", StaticFiles(directory=str(cartella), html=True), name="frontend")
    return app


def main() -> int:
    import uvicorn
    from dotenv import load_dotenv

    from assistente.cli import configura_log
    from assistente.config import ErroreConfigurazione, carica_configurazione
    load_dotenv(".env", override=False)
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    configura_log(config)
    uvicorn.run(crea_frontend(config.backend_url, config.agente_timeout),
                host=config.frontend_host, port=config.frontend_porta,
                log_level=config.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
