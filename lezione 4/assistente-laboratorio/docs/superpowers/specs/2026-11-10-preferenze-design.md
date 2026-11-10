# Step 4 · Resource: preferenze dell'utente

Quarto dei nove step. Approvata dall'utente il 2026-11-10 (con correzioni alla prima proposta).

## Obiettivo
Il server MCP pubblica le preferenze dell'utente come resource `utente://preferenze`. L'host le
legge una sola volta a inizio sessione e le mette in cima al prompt di sistema dell'agente.

## Decisioni
- **Tre campi, tutti validati** (`preferenze.py`, schema pydantic, campi extra rifiutati):
  `lingua` delle risposte (`it`, `en`, `fr`, `de`, `es`), `fuso_orario` predefinito (IANA,
  verificato con `zoneinfo`), `stile` (`sintetico` o `dettagliato`). Campi mancanti → valore
  predefinito del campo. Predefinite: `it`, `Europe/Rome`, `sintetico`.
- **Resource**: URI `utente://preferenze`, `application/json`, pubblicata da `server_mcp.py`; il
  server legge il proprio `PREFERENZE_FILE` a ogni `resources/read`. File assente o non valido →
  errore della resource. La resource non è un tool: non compare in `list_tools` né fra gli
  strumenti passati a `bind_tools`.
- **Canali**: variante `mcp` → `client.read_resource("utente://preferenze")`; varianti `locale` e
  `http` → lettura diretta del file `PREFERENZE_FILE` (default `preferenze.json`). Nessun
  endpoint HTTP nuovo. Una sola logica di validazione per tutti i canali.
- **Lettura dall'host, una volta**: `Sessione(..., leggi_preferenze=...)` legge prima della
  prima domanda e di nuovo con `/nuova`; nessun nodo che rilegge a ogni turno. Nel log una riga
  `preferenze: resources/read utente://preferenze (mcp) -> lingua=... fuso_orario=... stile=...`
  (o `preferenze: lettura del file ... -> ...`), separata dalle chiamate agli strumenti.
- **Pensando allo step 6**: le preferenze entrano nel grafo dallo stato (campo `preferenze`,
  passato dal chiamante), non da un nodo; un agente HTTP potrà riceverle dalla richiesta.
- **Chi le vede**: l'agente, in cima al messaggio di sistema (prima delle istruzioni generali, che
  restano identiche; il riassunto resta in coda); il revisore, come dati attendibili (prima riga
  del contesto); il router no.
- **Errori**: resource non disponibile, server irraggiungibile, file assente o non valido →
  predefinite con un WARNING che dice il motivo.
- **Git**: `preferenze.example.json` versionato; `preferenze.json` in `.gitignore`.
- **Prova sostituita**: `test_ora_senza_luogo` (l'agente chiedeva il luogo) diventa
  `test_ora_senza_luogo_usa_il_fuso_predefinito`: con un fuso predefinito l'agente lo usa.

## Verifiche
- Offline: validazione e motivi d'errore, testo per il prompt, lettore del file (anche rilettura),
  resource sul server con client in memoria (pubblicata, non fra i tool, file del server non
  valido), lettore MCP con server irraggiungibile, errore e contenuto non testuale; grafo
  (preferenze in cima, invariato senza, revisore sì e router no, bind_tools senza resource);
  sessione (una lettura prima della prima domanda, nessuna per turno, rilettura con `/nuova`);
  configurazione e scelta del lettore per variante.
- Reali: CLI nella variante `mcp` con server avviato e `America/New_York`: una sola
  `resources/read` prima della domanda, poi `ora_corrente` con quel fuso senza chiedere il luogo;
  `test_ora_senza_luogo_usa_il_fuso_predefinito`; `test_lingua_e_stile_valgono_dalla_sessione_successiva`;
  prove del router.

## Note dall'implementazione
- Prima versione della prova su lingua e stile fallita: a «Quanto fa 12 * 7?» il modello
  rispondeva solo «84» in entrambe le sessioni (lingua non riconoscibile) e lo stile
  `dettagliato` non allungava la risposta. Diagnosi con il modello vero: la lingua veniva
  rispettata («12 * 7 equals 84.»), lo stile no, perché il testo era vago. Il testo dello stile
  ora è concreto («una sola frase breve, senza spiegazioni» / «due o tre frasi: risultato e come
  lo hai ottenuto»): 13 contro 109 caratteri. Nessuna decisione cambia.
