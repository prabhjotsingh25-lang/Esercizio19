# Step 3 · Riassunto: la cronologia lunga diventa un riassunto

Terzo dei nove step. Approvata dall'utente il 2026-11-10.

## Obiettivo
Quando la conversazione si allunga, un nodo all'inizio del turno sostituisce i messaggi vecchi
con un riassunto e conserva intatti quelli recenti, così al modello non arriva tutta la
cronologia a ogni domanda.

## Grafo
```
START -> riassunto -> router -conversazione-> modello <-> strumenti -> revisore ...
                             '-fuori_ambito-> rifiuto -> END            (resto invariato)
```

## Decisioni
- **Configurazione**: `SOGLIA_RIASSUNTO` (default 20) e `MESSAGGI_RECENTI` (default 6), interi
  >= 1 validati come `MAX_REVISIONI`; in più `MESSAGGI_RECENTI` < `SOGLIA_RIASSUNTO`. Valori non
  validi → «Configurazione non valida», codice 2. Si contano tutti i messaggi dello stato
  (strumenti compresi e domanda nuova compresa).
- **Sotto soglia** (messaggi <= soglia): nessuna chiamata al modello, log INFO.
- **Punto di taglio solo tra turni**: si parte da «ultimi `MESSAGGI_RECENTI`» e si torna indietro
  fino alla domanda dell'utente più vicina (le indicazioni del revisore non contano come
  domanda). Così una richiesta di tool non resta mai separata dal suo `ToolMessage` e
  un'indicazione non resta senza la sua bozza. I messaggi tenuti possono essere più di N, mai
  meno. Se il taglio cade all'inizio (un solo turno lungo) non c'è niente da riassumere: nessuna
  chiamata, log INFO.
- **Riassunto nello stato**: campo `riassunto: str`, aggiornato e non accumulato. Il modello
  riceve il riassunto precedente e i messaggi da togliere e scrive un nuovo riassunto che
  incorpora il precedente. I messaggi vecchi escono dallo stato con `RemoveMessage`.
- **Cosa entra nel riassunto**: solo il dialogo accettato (domande dell'utente e risposte
  finali). Restano fuori le indicazioni del revisore (`name="revisore"`), la bozza scartata
  che precede ogni indicazione, le chiamate agli strumenti e i loro risultati (i dati utili sono
  già nella risposta finale). Un'indicazione nel riassunto sembrerebbe detta dall'utente. Nella
  parte recente della cronologia le indicazioni restano come prima.
- **Chi usa il riassunto**: l'agente, in coda al messaggio di sistema («Riassunto della
  conversazione precedente: ...»); il router, come prima riga del contesto (altrimenti «come mi
  chiamo?» dopo la compressione potrebbe sembrare fuori ambito). Il revisore no: giudica la
  coerenza, non i dati.
- **Errori**: riassunto vuoto → nessun messaggio tolto, WARNING (si riprova al turno dopo);
  errori di connessione al modello → al chiamante, come per gli altri nodi.
- **Log**: `riassunto: 23 messaggi, soglia 20 -> riassunti 16, tenuti 7`;
  `riassunto: 8 messaggi, sotto la soglia di 20: nessuna chiamata`; testo del riassunto a DEBUG.
- **Sessione**: conserva anche il riassunto e lo ripassa a ogni turno; `/nuova` lo azzera. Il
  limite di ricorsione cresce di 1 (nodo riassunto).
- **Compatibilità**: `costruisci_grafo(..., riassuntore=None, soglia_riassunto=20,
  messaggi_recenti=6)`; senza riassuntore il grafo è quello di prima. CLI e prove reali lo
  passano sempre.

## Verifiche
- Offline (simulati): punto di taglio con strumenti, indicazioni, turno unico e sotto soglia;
  testo da riassumere senza indicazioni, bozze e strumenti; nessuna chiamata sotto soglia;
  messaggi vecchi tolti e riassunto aggiornato (il nuovo riceve il precedente); riassunto nel
  messaggio di sistema dell'agente e nel contesto del router; riassunto vuoto → nessun taglio;
  sessione che conserva e azzera il riassunto.
- Reali (LM Studio, `SOGLIA_RIASSUNTO=6`, `MESSAGGI_RECENTI=2`): turno 1 con il nome, log della
  compressione, «come mi chiamo?» risposto correttamente dopo la compressione; caso sotto
  soglia senza chiamata. Rilancio delle prove del router e di «note con conferma».

## Note dall'implementazione
- Prima prova reale fallita due volte: il riassunto conteneva il nome («Prabhjot ha iniziato
  una conversazione...») ma il modello rispondeva «non mi hai detto il tuo nome». Diagnosi
  sull'ultimo turno ricostruito: serve che il riassunto dica esplicitamente chi è l'utente.
  Le istruzioni del riassunto ora chiedono una prima riga «Utente: ...» con i fatti
  sull'utente, e l'intestazione nel messaggio di sistema dice che sono informazioni date
  dall'utente da usare per rispondere. Nessuna decisione della specifica cambia.
- La prova reale usa «Quanto fa 15 + 27?» al posto di «Che ore sono a Tokyo?»: il revisore
  (step 2) non vede i risultati degli strumenti e bocciava l'orario giusto; la correzione
  dell'agente («non ho accesso a dati in tempo reale») restava fra i messaggi recenti e
  faceva fallire la domanda sul nome anche con il riassunto migliorato. Il difetto del
  revisore è un debito noto (CLAUDE.md) e si corregge in un commit separato `fix(revisore)`.
