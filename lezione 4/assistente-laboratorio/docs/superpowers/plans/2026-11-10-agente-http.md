# Piano · Step 6 Agente come servizio HTTP

Branch `feat/agente-http` da `dev`. Specifica: `../specs/2026-11-10-agente-http-design.md`.

1. `agente.py` (TDD): `Agente` (turno sul grafo, strumenti usati, prompt con controllo e
   contrassegno, elenco), conversione fra cronologia dell'API e messaggi; `Sessione` lo usa.
2. `varianti.py`: controllo di raggiungibilità degli strumenti per variante; controllo del
   modello (`GET /models`).
3. `servizio_agente.py` (TDD con `TestClient`): `/messaggi`, `/prompt`, `GET /prompt`, `/stato`,
   errori, log per richiesta; `config.py` (`AGENTE_HOST`, `AGENTE_PORTA`, `AGENTE_URL`).
4. `cliente_agente.py` e `cli.py`: CLI client dell'API con `AGENTE_URL` (trasporto finto nei
   test), in-process senza; `/prompts` e `/prompt` passano dall'agente in entrambi i modi.
5. `docs/openapi-agente.json` e test del contratto.
6. Prove reali: servizio con LM Studio (domanda con strumento, stato, modello e strumenti
   spenti), stessa risposta da CLI e API, prove del router.
7. README, CLAUDE.md, `.env.example`; evidenze e proposta di commit, poi stop.
