# Retrieval sull'Artusi — resoconto

Pipeline di ingestion e ricerca (nessun modello generativo) sulle 790 ricette di *La scienza in
cucina e l'arte di mangiar bene* (Project Gutenberg n. 59047). Embedding:
`text-embedding-nomic-embed-text-v1.5@q8_0` servito da LM Studio sull'host; indice: Qdrant 1.20.2 in
Docker Compose (porta 6333, volume `qdrant_dati`, distanza coseno). Data: 2026-11-17.

Specifiche: `docs/specs/pipeline-rag.md`, `docs/specs/modifica-a.md`, `docs/specs/modifica-b.md`.
Dettagli delle valutazioni: `docs/eval-baseline.md`, `docs/eval-dopo-a.md`, `docs/eval-dopo-b.md`,
`docs/verifica-dosi.md`.

## 1. Conteggi delle ingestion

Le due ingestion di fila richieste (fase 1, testo indicizzato = solo testo del chunk):

| Esecuzione | Ricette | Capitoli | Chunk | Scritti (upsert) | Eliminati | Punti nella collezione | Durata |
|---|---|---|---|---|---|---|---|
| 1ª (collezione nuova) | 790 | 23 | 1106 | 1106 | 0 | **1106** | 135 s |
| 2ª (subito dopo) | 790 | 23 | 1106 | 1106 | 0 | **1106** | 130 s |

Le ingestion successive sulla stessa collezione:

| Operazione | Punti prima | Punti dopo | Embedding ricalcolati | Durata |
|---|---|---|---|---|
| Modifica A: `--solo-payload` (`contiene_dosi` con `set_payload`) | 1106 | 1106 | no (20/20 vettori identici) | 2,1 s |
| Modifica B: ingestion con titolo e capitolo (stessi ID, upsert) | 1106 | 1106 | sì, tutti | 137 s |

Prova del blocco: un'ingestion con `MODELLO_EMBEDDING=…@q4_k_m` si è fermata con errore («La collezione
"artusi" è stata creata con modello_embedding = …@q8_0; la configurazione indica …@q4_k_m») senza
modificare nulla.

## 2. Valutazioni (9 domande, k = 5)

Posizione = posto della prima fonte accettata tra i primi 5 (— = assente); score = score del primo
risultato.

| Domanda | Fonte attesa | Partenza | Dopo A | Dopo A + `--solo-dosi` | Dopo B |
|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 1 (0.769) | 1 (0.769) | 1 (0.769) | 1 (0.773) |
| Che vino si usa per il pollo alla cacciatora? | 208 | — (0.701) | — (0.701) | — (0.685) | **1 (0.749)** |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 1 (0.777) | 1 (0.777) | — (0.671) | 1 (0.774) |
| Qual è la ricetta del tiramisù? | nessuna | — (0.717) | — (0.717) | — (0.717) | — (0.706) |
| Quanti cappelletti bastano a un mangiatore moderato? ¹ | 7 | 2 (0.730) | 2 (0.730) | 1 (0.729) ² | **1 (0.745)** |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 5 (0.725) | 5 (0.725) | 2 (0.705) | **1 (0.720)** |
| Per quanto tempo si deve cuocere il baccalà? | 510 | — (0.750) | — (0.750) | — (0.738) | **4 (0.766)** |
| Con che cosa si insaporisce il brodo? | 1 | 1 (0.752) | 1 (0.752) | — (0.706) | 1 (0.768) |
| Come si fa un dolce di mandorle e zucchero? ³ | 617, 785, 626, 620, 687 | 1 (0.847) | 1 (0.847) | 1 (0.847) | 2 (0.821) |
| **Fonte nei primi 5** | | **6/8** | **6/8** | **5/8** | **8/8** |

¹ La domanda dice «moderato», il testo della ricetta 7 dice «A un mangiatore **discreto** bastano due
dozzine»: caso voluto di parole diverse da quelle del testo.
² Ricetta giusta ma chunk sbagliato: con `--solo-dosi` esce il chunk 0 (elenco del ripieno), mentre la
risposta è nei chunk 1–2 di prosa.
³ Fonti multiple accettate; posizione della prima che compare.

- **Dopo A senza filtro** la tabella è identica alla partenza: la modifica A non tocca i vettori.
- **`--solo-dosi`** aiuta quando la risposta è vicino all'elenco degli ingredienti (gnocchi che si
  sciolgono, 5 → 2) e fa perdere la fonte quando la risposta è nella prosa (cacciucco, brodo).
- **Dopo B** si trovano tutte le 8 fonti: 208 (titolo), 89 e 7 con il chunk di prosa giusto, 510 al 4°
  posto. Peggioramento: mandorle 1 → 2, perché sale la 613 «Dolce di mandorle», il cui titolo coincide
  con la domanda ma non è tra le fonti accettate.

## 3. Due query commentate (stato finale, dopo B)

### Riuscita
```
python -m rag.ricerca "Che vino si usa per il pollo alla cacciatora?" --k 3
1. [0.749] Ricetta 208 — Pollo alla cacciatora | Fritti | chunk 0
2. [0.706] Ricetta 539 — Pollo ripieno arrosto | Arrosti | chunk 0
3. [0.706] Ricetta 545 — Pollo vestito | Arrosti | chunk 0
```
- **Ricetta 208 «Pollo alla cacciatora», capitolo «Fritti», chunk 0** (posizione 0, unico chunk della
  ricetta), al **1° posto**. Il chunk contiene la risposta: «annaffiatelo con mezzo bicchiere di San
  Giovese od altro vino rosso del migliore».
- Perché ora funziona: il corpo della ricetta non contiene «cacciatora»; dalla modifica B il testo
  indicizzato comincia con «Titolo: Pollo alla cacciatora / Capitolo: Fritti». Nella valutazione di
  partenza la 208 non era nei primi 5.
- Da notare: le posizioni 2–3 sono altre ricette «Pollo …», attirate dal titolo.

### Fallita
```
python -m rag.ricerca "Per quanto tempo si deve cuocere il baccalà?" --k 3
1. [0.766] Ricetta 506 — Baccalà alla fiorentina | Piatti di pesce | chunk 2
2. [0.758] Ricetta 118 — Baccalà montebianco | Principii | chunk 1
3. [0.754] Ricetta 506 — Baccalà alla fiorentina | Piatti di pesce | chunk 1
```
- La risposta è nella **ricetta 510 «Baccalà fritto», capitolo «Piatti di pesce», chunk 0**: «Per
  lessarlo mettetelo al fuoco in acqua diaccia e appena abbia alzato il primo bollore levatelo che già è
  cotto». Con k = 3 **non compare**: è al **4° posto** (0.754), quindi esce solo con k ≥ 4.
- I primi tre sono chunk di altre ricette di baccalà: il chunk 2 della 506 parla del baccalà come
  alimento, il chunk 1 della 118 di come pulirlo, il chunk 1 della 506 della pesca del merluzzo.
  Tutte hanno «Baccalà» nel titolo e quindi, dopo B, vettori simili alla domanda; nessuna risponde.
- Causa: la domanda chiede un tempo di cottura generico, la risposta è dentro una ricetta di frittura;
  la ricerca semantica premia la somiglianza del tema (baccalà), non la presenza della risposta.

## 4. Scelte delle specifiche, una riga di motivazione ciascuna

**Pipeline (`docs/specs/pipeline-rag.md`)**
- Unità di documento = ricetta (solo le 790): numero, titolo e capitolo certi per ogni risultato.
- Ricette riconosciute per sequenza 1..790: scarta i 5 falsi positivi (righe che iniziano con un numero).
- Capitoli da un elenco di 23 nomi, con test: i titoli in maiuscolo che non sono capitoli sono molti.
- Una ricetta finisce anche al titolo del capitolo successivo: le introduzioni non finiscono nella ricetta sbagliata.
- Marcatura Gutenberg tolta (corsivi, illustrazioni, note): non aggiunge significato all'embedding.
- Ingredienti una per riga: l'elenco resta leggibile ed è la base della modifica A.
- Titolo fuori dal testo del chunk: baseline onesta, per misurare l'effetto della modifica B.
- Chunk per paragrafi, 1200 caratteri, overlap 200: non spezza le frasi; l'overlap conserva il contesto tra chunk.
- Ricetta breve = 1 chunk: niente frammenti inutili (la mediana delle ricette è 874 caratteri).
- ID = uuid5(documento_id:chunk_index): stessi ID a ogni ingestion, quindi upsert idempotente.
- Cancellazione degli orfani dopo l'upsert: un cambio di chunking non lascia punti vecchi.
- Payload con documento_id, numero, titolo, capitolo, posizione, testo, fonte: ogni risultato è citabile.
- Indice keyword su `capitolo`: il filtro è applicato da Qdrant durante la ricerca.
- Modello, prefissi e dimensione nei metadati della collezione, con blocco se cambiano: mai vettori di modelli diversi insieme.
- Prefissi `search_document: ` / `search_query: ` in configurazione: li richiede nomic-embed-text-v1.5.
- Risultati = chunk, non raggruppati per ricetta: valutazione diretta, nessuna ottimizzazione nascosta.
- k massimo 20 nel codice ed errore se fuori intervallo: niente troncamenti silenziosi.
- Test con embedder finto e Qdrant in memoria: ripetibili senza servizi accesi.
- numpy fissato a 2.3.5: il controllo delle applicazioni di Windows blocca la DLL di numpy 2.5.5.

**Modifica A (`docs/specs/modifica-a.md`)**
- `contiene_dosi` = almeno 2 voci «Ingrediente, quantità»: è la forma degli elenchi nel libro; una riga sola non è un elenco.
- Verifica su un campione con seme fisso (30 + 30): la regola è misurata, non solo dichiarata (0 falsi positivi su 30).
- `--solo-payload` con `set_payload`: aggiungere un metadato non richiede di ricalcolare gli embedding.
- Controllo che i chunk coincidano prima di scrivere: evita di assegnare il campo al punto sbagliato.
- Indice bool su `contiene_dosi` e condizione nello stesso `Filter` del capitolo: filtri combinabili e nativi.

**Modifica B (`docs/specs/modifica-b.md`)**
- Prefisso del modello, poi «Titolo:» e «Capitolo:», poi il testo: il prefisso resta dove il modello lo aspetta, le etichette separano contesto e contenuto.
- Payload e risultati con il testo originale: si cita il libro, non il testo costruito per l'embedder.
- Query invariata: il contesto serve al documento; la domanda resta quella dell'utente.
- `TESTO_INDICIZZATO` in configurazione: si può tornare alla baseline e confrontare.
- Ricalcolo nella stessa collezione con upsert: ID, payload, `contiene_dosi` e indici restano.
- Metadato `in_aggiornamento` solo durante la scrittura: un'interruzione a metà non passa inosservata (gli embedding sono calcolati tutti prima di scrivere).

## 5. Limiti noti
- **Introduzioni dei capitoli non indicizzate** (per esempio «Qualità e stagione dei pesci», il
  discorso iniziale di «Minestre», la lettera «Un ammiratore»), come prefazione, «Spiegazione di voci»
  e Appendice: le domande su quelle parti non trovano la fonte.
- **Elenchi in prosa non riconosciuti da `contiene_dosi`** («tre uova, tre cucchiaiate d'olio, tre di
  zucchero»), né quelli con la quantità prima dell'ingrediente o spezzati dal confine di un chunk
  (3 falsi negativi su 30 nel campione).
- **Lo score non è una soglia**: il tiramisù, che nel libro non c'è, ha il primo risultato a 0.706–0.717,
  nella stessa fascia delle risposte giuste (0.72–0.85). La ricerca restituisce sempre k risultati.
- **La valutazione conta la ricetta, non il chunk**: un risultato può essere la ricetta giusta con il
  chunk che non contiene la risposta (cappelletti con `--solo-dosi`).
- **Il titolo attira ricette con titolo simile** (dopo B): classifiche piene di «Pollo …» o «Baccalà
  …», e la 613 «Dolce di mandorle» davanti alle fonti accettate.
- **8/8 non è una prova di generalità.** La valutazione ha solo 9 domande, e due di queste (208 e
  baccalà 510) erano già note come casi falliti prima della modifica B, che è stata pensata proprio
  per casi come la 208: il miglioramento è misurato sugli stessi esempi che l'hanno motivato. Per
  dire che B funziona in generale servirebbero domande nuove, scritte prima di vedere i risultati.
