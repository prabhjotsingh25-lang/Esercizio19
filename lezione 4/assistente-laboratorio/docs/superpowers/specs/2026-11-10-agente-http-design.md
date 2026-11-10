# Step 6 · Agente come servizio HTTP

Sesto dei nove step. Approvata dall'utente il 2026-11-10 (con correzioni alla prima proposta).

## Obiettivo
L'agente (grafo con riassunto, router, revisore, preferenze e prompt) diventa un servizio FastAPI
**senza stato**: a ogni richiesta il chiamante manda testo (o nome e argomenti di un prompt),
cronologia, riassunto e preferenze; il servizio risponde con risposta, strumenti usati,
cronologia e riassunto aggiornati. La CLI diventa un client dell'API con `AGENTE_URL`; senza,
resta in-process e usa lo stesso modulo dell'agente.

## Decisioni
- **Un solo modulo dell'agente** (`agente.py`, classe `Agente`): invoca il grafo, raccoglie gli
  strumenti usati nel turno, compone i prompt (controllo dello step 5 e contrassegno
  `name="prompt"`). Lo usano il servizio (`servizio_agente.py`) e la `Sessione` in-process.
- **Endpoint**:
  - `POST /messaggi` — `{testo, cronologia, riassunto, preferenze}` →
    `{risposta, strumenti: [{nome, argomenti, risultato}], cronologia, riassunto}`;
  - `POST /prompt` — `{nome, argomenti, cronologia, riassunto, preferenze}` → come sopra più
    `prompt` (i testi composti dal servizio);
  - `GET /prompt` — elenco dei prompt (nome, descrizione, argomenti obbligatori o facoltativi);
  - `GET /stato` — agente, modello e strumenti (server MCP o servizio strumenti), con dettaglio
    per componente; 200 se tutto è raggiungibile, 503 altrimenti.
- **Cronologia nell'API**: solo `{ruolo: "utente" | "assistente", testo}`; campi in più (per
  esempio `name`), ruoli di sistema o di strumento → 422. Il servizio restituisce il dialogo:
  domande e risposte finali accettate, senza messaggi degli strumenti, indicazioni del revisore e
  bozze scartate (gli strumenti del turno sono nel campo `strumenti`).
- **Contrassegno non falsificabile**: il client non può mandare messaggi con un `name`; il testo
  di `/messaggi` diventa un messaggio senza nome e lo decide il router. Solo `/prompt` produce
  messaggi `name="prompt"`, composti dal servizio dopo il controllo su nome e argomenti.
- **Preferenze**: le manda il chiamante (campo `preferenze`, validato come nello step 4; non
  valide → 422). Se mancano: valori predefiniti con WARNING. La CLI client le legge come oggi (a
  inizio sessione e con `/nuova`) e le manda a ogni richiesta.
- **Errori**: modello non raggiungibile → 503 «modello non raggiungibile su ...»; strumenti non
  disponibili (servizio strumenti o server MCP, controllati prima di chiamare il modello) → 503
  «strumenti non disponibili: ...»; errore del server del modello → 502; prompt non valido →
  422; prompt non disponibili (server MCP) → 503; limite di passaggi → 200 con il messaggio di
  limite. Corpo d'errore: `{"detail": "..."}` (FastAPI).
- **Configurazione**: `AGENTE_HOST` (default `127.0.0.1`), `AGENTE_PORTA` (default `8000`),
  `AGENTE_URL` (facoltativa, per la CLI client). Avvio: `python -m assistente.servizio_agente`.
  Nessuna autenticazione.
- **OpenAPI**: `/docs` e `/openapi.json`; copia nel repository in `docs/openapi-agente.json`, con
  un test che la confronta con quella generata (contratto per back-end e front-end).
- **Log**: quelli di oggi più `agente_http: POST /messaggi -> 200 in 12.3 s (strumenti: ...)`.

## Verifiche
- Offline (`TestClient`, grafo simulato): messaggi e strumenti usati, cronologia e riassunto
  restituiti, `name` o ruoli non ammessi → 422, `name="prompt"` di un client non salta il router,
  prompt valido con contrassegno messo dal servizio, prompt non valido 422, modello e strumenti non
  disponibili 503 con messaggi diversi, limite 200, preferenze mancanti → predefinite con
  WARNING, stato per componente, OpenAPI uguale al file; CLI client con trasporto finto.
- Reali: servizio avviato, domanda con strumento via HTTP (risposta, strumenti, log); modello o
  strumenti spenti; stessa domanda da CLI in-process e da API; prove del router.
