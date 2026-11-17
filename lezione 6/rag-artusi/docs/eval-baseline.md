# Valutazione di partenza (baseline)

- Data: 2026-11-17
- Modello: `text-embedding-nomic-embed-text-v1.5@q8_0` · collezione `artusi`
- Chunking: paragrafi, 1200 caratteri, overlap 200
- k = 5 · fonte trovata nei primi 5: 6/8

## Ingestion (Qdrant 1.20.2 in Docker, LM Studio sull'host)

| Esecuzione | Ricette | Capitoli | Chunk | Scritti (upsert) | Eliminati | Punti nella collezione | Durata |
|---|---|---|---|---|---|---|---|
| 1ª (collezione nuova) | 790 | 23 | 1106 | 1106 | 0 | 1106 | 135 s |
| 2ª (subito dopo) | 790 | 23 | 1106 | 1106 | 0 | 1106 | 130 s |

Metadati della collezione: `modello_embedding` = `text-embedding-nomic-embed-text-v1.5@q8_0`,
`prefisso_documento` = `search_document: `, `prefisso_query` = `search_query: `, `dimensione` = 768;
distanza coseno; indice keyword su `capitolo` (1106 punti). Un'ingestion con
`MODELLO_EMBEDDING=...@q4_k_m` si è fermata con errore senza modificare la collezione.

## Risultati (k = 5)

| Domanda | Fonte attesa | Posizione | Score migliore | Primo risultato |
|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 1 | 0.769 | Ricetta 89 — Gnocchi di patate |
| Che vino si usa per il pollo alla cacciatora? | 208 | — | 0.701 | Ricetta 209 — Pollo fritto coi pomodori |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 1 | 0.777 | Ricetta 455 — Cacciucco I |
| Qual è la ricetta del tiramisù? | nessuna | — | 0.717 | Ricetta 609 — Pizza alla napoletana |
| Quanti cappelletti bastano a un mangiatore moderato? | 7 | 2 | 0.730 | Ricetta 349 — Pasticcio di maccheroni |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 5 | 0.725 | Ricetta 427 — Piselli colla carnesecca |
| Per quanto tempo si deve cuocere il baccalà? | 510 | — | 0.750 | Ricetta 508 — Baccalà dolce-forte |
| Con che cosa si insaporisce il brodo? | 1 | 1 | 0.752 | Ricetta 1 — Brodo |
| Come si fa un dolce di mandorle tagliate a filetti e versate nello zucchero fuso? | 617 | 1 | 0.817 | Ricetta 617 — Croccante |

## Note

- «Quanti cappelletti bastano a un mangiatore moderato?»: La domanda dice «moderato», il testo della ricetta 7 dice «A un mangiatore discreto bastano due dozzine»: caso utile di parole diverse da quelle del testo.
- «Come si fa un dolce di mandorle tagliate a filetti e versate nello zucchero fuso?»: Sostituisce «Come si fa un dolce di mandorle e zucchero?», che non ha una fonte univoca (Croccante 617, Mandorle tostate 785, Amaretti 626, Ricciarelli 620, Pallottole di mandorle 687...).
