# Step 8 · Front-end: interfaccia di chat (versione minimale)

Ottavo dei nove step. Approvata dall'utente il 2026-11-10 in versione minimale.

## Obiettivo
Una pagina di chat che parla solo con il back-end, usando gli endpoint di
`docs/openapi-backend.json` senza indovinarne altri.

## Decisioni
- **Tecnologia**: HTML, CSS e JavaScript senza librerie né compilazione, in
  `src/assistente/web/` (`index.html`, `stile.css`, `app.js`), serviti da `frontend.py` (FastAPI
  `StaticFiles`, già fra le dipendenze). Avvio: `python -m assistente.frontend` su
  `FRONTEND_HOST`:`FRONTEND_PORTA` (default `127.0.0.1:8090`).
- **Indirizzo del back-end da configurazione**: `BACKEND_URL`, passato alla pagina da `/config.js`
  (`window.CONFIG = {backendUrl, timeoutMs}`); nel codice del front-end non c'è nessun indirizzo
  (verificato da un test).
- **Solo il back-end**: il browser chiama direttamente `BACKEND_URL`; il back-end abilita il CORS
  solo per `FRONTEND_ORIGINE` (default `http://127.0.0.1:8090`). Il contratto del back-end non
  cambia.
- **Funzioni (solo quelle della slide)**: elenco, creazione ed eliminazione delle chat (titolo e
  data dell'ultimo messaggio); vista dei messaggi e invio; «Strumenti usati» richiudibile sotto la
  risposta; attesa con cronometro e invio disattivato; errori comprensibili con «Riprova»
  (`POST /conversazioni/{id}/riprova`) sull'ultima domanda in errore; back-end spento → avviso
  senza bloccare la pagina. Niente menu dei prompt, preferenze o indicatore di stato.
- **Endpoint usati**: `GET`/`POST /conversazioni`, `GET`/`DELETE /conversazioni/{id}`,
  `POST /conversazioni/{id}/messaggi`, `POST /conversazioni/{id}/riprova`. Tutte le chiamate
  passano da una funzione `api(metodo, percorso)`; un test le confronta con il contratto.
- **Attesa**: il `fetch` ha un limite di `AGENTE_TIMEOUT` + 60 s (da `config.js`); dopo ogni
  turno, riuscito o no, la pagina rilegge la chat dal back-end (lo storico salvato è la fonte).

## Verifiche
- Offline: `frontend.py` serve pagina, stile, script e `config.js`; nessun indirizzo nel codice;
  contratto di `app.js` con `docs/openapi-backend.json`; CORS solo per l'origine del front-end.
- Reali (Edge senza finestra pilotato dal protocollo di debug, screenshot): attesa con
  cronometro, conversazione con uno strumento, chat presente dopo il riavvio del back-end,
  agente spento con errore e «Riprova» riuscito.

## Note dall'implementazione
- Prima prova nel browser: con la prima domanda di una chat nuova la creazione della chat
  ridisegnava l'area dei messaggi e cancellava domanda e cronometro. Ora la chat si crea prima di
  mostrare l'attesa.
- Seconda correzione: alla fine del turno la pagina riattivava l'invio prima di rileggere la chat,
  e per un attimo restava l'attesa ferma senza il riquadro d'errore. Ora rilegge prima e poi
  riattiva.
- I file del front-end hanno `Cache-Control: no-cache`: un browser con la versione vecchia di
  `app.js` in cache mostrava ancora il primo difetto.
- In una prova il router ha classificato «Quanto fa 137 * 49?» come fuori ambito (variabilità del
  modello piccolo, non del front-end): la «Riprova» ha funzionato, ma la risposta era il rifiuto.
- L'estensione per pilotare Chrome non è stata installata (scelta dell'utente): le evidenze sono
  raccolte con Edge senza finestra via Chrome DevTools Protocol (script di prova fuori dal
  progetto, che usa `websockets` già presente nel venv).
