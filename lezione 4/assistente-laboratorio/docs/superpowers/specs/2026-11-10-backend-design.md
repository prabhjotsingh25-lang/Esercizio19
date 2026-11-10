# Step 7 · Back-end: API e salvataggio in PostgreSQL

Settimo dei nove step. Approvata dall'utente il 2026-11-10 (con correzioni alla prima proposta).

## Obiettivo
Un servizio FastAPI (`backend.py`) fra il front-end (step 8) e l'agente senza stato (step 6):
salva conversazioni e messaggi in PostgreSQL e a ogni turno chiama l'agente con cronologia,
riassunto e preferenze presi dal database, poi salva ciò che l'agente restituisce.

## Decisioni
- **Database**: PostgreSQL 16 in un container (`docker run postgres:16`, porta host 55432 perché
  la 5432 era occupata); driver **pg8000** (Python puro) con SQL scritto a mano, versione fissata.
  psycopg 3, concordato all'inizio, non si carica sull'host: Windows blocca la sua DLL («Un
  criterio di controllo dell'applicazione ha bloccato il file»); scelta dell'utente: pg8000.
  `DATABASE_URL` con la password solo in `.env` (fuori da Git). Schema in `schema.sql`, applicato
  all'avvio con `CREATE TABLE IF NOT EXISTS`.
- **Tabelle**: `conversazioni` (id uuid, titolo, creata, aggiornata = data dell'ultimo messaggio,
  `preferenze` jsonb, `riassunto`, `cronologia_agente` jsonb, `turno_in_corso`); `messaggi`
  (conversazione, posizione, ruolo `utente`/`assistente`, testo, `strumenti` jsonb, `prompt` jsonb
  con nome e argomenti, `stato` della domanda `risposta`/`errore`, `errore`, creato). Nessuna
  tabella utenti.
- **Due copie, usi diversi**: `cronologia_agente` e `riassunto` sono salvati così come li
  restituisce l'agente e rimandati identici al turno dopo (stato dell'agente); `messaggi` è lo
  storico completo per il front-end, solo in aggiunta (la compressione dell'agente non lo tocca).
- **Preferenze**: per conversazione. Alla creazione, dal corpo della richiesta oppure lette una
  volta dalla fonte di oggi (resource `utente://preferenze` nella variante `mcp`, file
  `PREFERENZE_FILE` nelle altre; predefinite con WARNING se mancano). Si cambiano con
  `PUT /conversazioni/{id}/preferenze`.
- **Invio sincrono**: `POST /conversazioni/{id}/messaggi` salva la domanda, chiama l'agente, salva
  e restituisce la risposta. Un solo turno alla volta per conversazione (409 sul secondo invio).
  Timeout verso l'agente `AGENTE_TIMEOUT` (default 900 s) con connessione a 10 s. Front-end e
  proxy dovranno avere timeout alti (oppure si passerà allo streaming).
- **Titolo**: le prime parole della prima domanda (al massimo 6 parole e 60 caratteri, «…» se
  tagliato), senza chiamare il modello; per un prompt, «nome: argomenti». L'elenco mostra titolo
  e data dell'ultimo messaggio, dal più recente.
- **Errori dell'agente (scelta di questo step)**: la domanda dell'utente **viene salvata** con
  `stato="errore"` e il messaggio dell'errore; non viene aggiunta nessuna risposta e lo stato
  dell'agente (cronologia, riassunto) non cambia. Il front-end la mostra con l'errore e può
  riprovare con `POST /conversazioni/{id}/riprova`, che rimanda la stessa domanda (stesso testo o
  stesso prompt) senza duplicarla: se va bene la domanda passa a `stato="risposta"` e si aggiunge
  la risposta. Si può riprovare solo l'ultima domanda, se è in errore (altrimenti 409). Una nuova
  domanda dopo un errore è permessa: quella in errore resta nello storico ma non va all'agente.
  Codici: agente non raggiungibile 503, agente senza risposta entro il timeout 504, errori
  dell'agente 503/502 con il suo messaggio; prompt non valido 422 e in quel caso la domanda **non**
  resta salvata (non c'è niente da riprovare).
- **Contratto con l'agente**: il client usa solo i percorsi e i campi di `docs/openapi-agente.json`;
  un test verifica percorsi, metodi e campi delle richieste sul file; i test d'integrazione fanno
  parlare il back-end con l'app vera dell'agente (grafo simulato). Contratto del back-end in
  `docs/openapi-backend.json` (stesso test di uguaglianza dello step 6).
- **Configurazione**: `DATABASE_URL`, `BACKEND_HOST` (127.0.0.1), `BACKEND_PORTA` (8080),
  `AGENTE_URL` (indirizzo dell'agente), `AGENTE_TIMEOUT` (900). Avvio:
  `python -m assistente.backend`. Nessuna autenticazione. All'avvio i `turno_in_corso` rimasti
  attivi da un arresto vengono azzerati (un solo processo del back-end).
- **Test**: offline con un archivio in memoria che ha la stessa interfaccia di quello
  PostgreSQL; prove con PostgreSQL vero separate (marker `postgres`).

## Verifiche
- Offline: due turni con strumento, titolo, elenco, 409, preferenze, errori (agente spento,
  timeout, 503 dell'agente) con domanda salvata in errore e riprova senza duplicati, prompt e 422,
  stato, contratto con `docs/openapi-agente.json`, OpenAPI del back-end.
- PostgreSQL vero: archivio (schema, messaggi, stato dell'agente) e dati presenti dopo una nuova
  connessione. Reali: back-end + agente + LM Studio, due turni con strumento, riavvio del
  back-end, agente spento; prove del router.
