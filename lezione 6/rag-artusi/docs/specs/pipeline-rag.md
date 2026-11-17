# Specifica — Pipeline RAG di ingestion e ricerca sull'Artusi (Fase 1)

Stato: bozza da approvare. Data: 2026-11-17. Branch: `feat/rag-pipeline`.

## 1. Intento

Costruire la parte di *retrieval* di un sistema RAG sul ricettario dell'Artusi: dato il testo
del libro, produrre chunk indicizzati in Qdrant con embedding calcolati da LM Studio, e una
ricerca semantica con filtri. **Nessun modello generativo**: si misura solo quanto bene si
ritrovano i passi giusti. Questa base serve alle fasi successive (valutazione di partenza,
modifica A sui metadati, modifica B sul testo indicizzato), quindi deve essere ripetibile,
misurabile e facile da confrontare.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Ingestion da riga di comando (`python -m rag.ingestion`) idempotente.
- Ricerca come funzione Python e come CLI
  (`python -m rag.ricerca "domanda" --capitolo X --k 3`).
- Ogni risultato dice ricetta (numero e titolo), capitolo e posizione del chunk.
- Test automatici che passano con LM Studio e Qdrant spenti.

**Non obiettivi (in questa fase)**
- Generazione di risposte, reranking, ricerca ibrida, raggruppamento per ricetta.
- Ottimizzazioni del retrieval: arrivano solo con le modifiche A e B, dopo la valutazione.
- Campo `contiene_dosi` e prefisso titolo/capitolo nel testo indicizzato (modifiche A e B).

**Anti-obiettivi (cose che renderebbero il lavoro un fallimento anche se "funziona")**
- ID casuali o punti duplicati a ogni ingestion.
- Filtro per capitolo applicato in Python dopo la ricerca.
- Modello, URL o nome della collezione scritti nel codice.
- Test che richiedono servizi accesi.
- Una collezione con vettori di due modelli diversi.

## 3. Vincoli (da CLAUDE.md)

Python 3.11+, pytest, `requirements.txt` con versioni fissate; package `rag/`, test in
`tests/`; Qdrant in Docker Compose (`compose.yaml`, porta 6333, volume persistente, distanza
coseno); configurazione solo in `.env` (+ `.env.example`); `dati/` e `.env` fuori da Git; un passo
per commit, Conventional Commits.

## 4. Corpus e limiti noti

- File: `dati/artusi.txt`, Project Gutenberg n. 59047 (scaricato dal mirror
  `gutenberg.pglaf.org` perché gutenberg.org era in manutenzione). UTF-8 con BOM, fine riga CRLF.
- **Unità di documento: la ricetta.** Solo le 790 ricette numerate.
- **Limite noto:** prefazione («La storia di un libro…», «Prefazio»), «Spiegazione di voci»,
  «Potere nutritivo delle carni», «Frustata» e l'Appendice («Cucina per gli stomachi deboli»,
  «Note di pranzi») **non sono indicizzati**. Una domanda su quelle parti non trova la fonte.
- **Limite noto:** anche i **testi introduttivi dei capitoli** (il discorso iniziale di
  «Minestre», l'introduzione di «Umidi», **«Qualità e stagione dei pesci»** in «Piatti di pesce»…)
  e la **lettera «Un ammiratore»** in apertura di «Torte e dolci al cucchiaio» **non sono
  indicizzati**. Esempio: una domanda su quali pesci siano migliori in una certa stagione non
  trova la sua fonte.

## 5. Approcci considerati

| Approccio | Pro | Contro |
|---|---|---|
| **A. `qdrant-client` + chiamata HTTP diretta a `/v1/embeddings` con `httpx` (scelto)** | Poche dipendenze; ogni passo (testo inviato, ID, payload, filtro) è visibile e testabile; l'embedder si sostituisce con uno finto con un'interfaccia minima | Qualche riga di codice in più per batch ed errori |
| B. SDK `openai` puntato su LM Studio | Client già pronto | Dipendenza pesante per una sola chiamata; nasconde la richiesta |
| C. LangChain / LlamaIndex | Pipeline pronta | Nasconde ID, payload e chunking: va contro le regole su ID stabili, payload e filtro nativo; difficile da testare con un embedder finto |

Scelta: **A** (scelta mia: l'utente ha fissato i requisiti, non le librerie). Configurazione
letta con `python-dotenv`.

## 6. Decisioni

### 6.1 Pulizia e parsing (decise con l'utente)
1. Rimuovere il BOM, normalizzare CRLF → LF, tenere solo il testo tra la riga
   `*** START OF THIS PROJECT GUTENBERG EBOOK …` e la riga `*** END OF …`.
2. **Ricette per sequenza di numeri:** si cercano righe `^(\d+)\. (.+)$` e si accetta una riga
   come intestazione solo se il numero è esattamente il successivo atteso (1, 2, …, 790). Così si
   scartano i 5 falsi positivi trovati (una riga di testo che inizia con «137. Mettete…», una con
   «1533. …», tre righe d'indice nei menù dell'Appendice).
3. Una ricetta va dalla sua intestazione fino alla **ricetta successiva o al titolo del capitolo
   successivo**, quello che viene prima (decisione dell'utente). Conta come titolo di capitolo
   anche la riga `MINESTRE` che precede «Minestre in brodo». La 790 finisce prima della riga
   `APPENDICE`. Il testo tra un titolo di capitolo e la sua prima ricetta (introduzioni, lettera
   «Un ammiratore») viene scartato (vedi limiti noti, §4).
4. **Capitoli:** il capitolo di una ricetta è l'ultimo titolo di capitolo incontrato prima della
   sua intestazione. Sono **23**: Minestre conta come due capitoli («Minestre in brodo» e «Minestre
   asciutte e di magro»; la riga `MINESTRE` da sola non è un capitolo). I titoli in maiuscolo che
   non sono capitoli (`PASTA FROLLA`, `RICETTA A/B/C`, `PRIMA/SECONDA/TERZA RICETTA`,
   `RICETTA DI DETTA ZUPPA PER SEI PERSONE`, `QUALITÀ E STAGIONE DEI PESCI`, `UN AMMIRATORE`,
   `N. 94.`…) vanno scartati. Il modo di riconoscerli è lasciato al costruttore, ma un test
   verifica che i capitoli siano **esattamente 23**, con i nomi attesi, nell'ordine del libro, e
   che ognuno abbia almeno una ricetta.
   Elenco atteso: Brodi, gelatina e sughi · Minestre in brodo · Minestre asciutte e di magro ·
   Principii · Salse · Uova · Paste e pastelle · Ripieni · Fritti · Lesso · Tramessi · Umidi ·
   Rifreddi · Erbaggi e legumi · Piatti di pesce · Arrosti · Pasticceria · Torte e dolci al
   cucchiaio · Siroppi · Conserve · Liquori · Gelati · Cose diverse.
5. **Forma del nome del capitolo:** leggibile, con la sola iniziale maiuscola come nell'elenco
   sopra (scelta mia).
6. **Paragrafi:** blocchi separati da righe vuote. Le righe di prosa spezzate a ~70 caratteri si
   uniscono con uno spazio. Le righe **rientrate** (elenchi ingredienti, versi) restano una per
   riga, senza il rientro, separate da `\n`, così l'elenco delle dosi resta leggibile (servirà
   alla modifica A).
7. **Testo del chunk = solo il corpo della ricetta, senza la riga del titolo**, che sta nel
   payload. Motivo: la baseline è onesta e la modifica B misura l'effetto di titolo e capitolo
   (esempio: il corpo della 208 «Pollo alla cacciatora» non contiene la parola «cacciatora»).
   Il corpo non è mai vuoto (verificato da un test sul corpus).
8. **Marcatura Gutenberg nel testo** (scelta mia): i trattini bassi del corsivo (`_Pastella per
   fritti_`, ~440 coppie) si tolgono tenendo le parole; i 13 blocchi `[Illustrazione: … NdT: …]`
   (anche su più righe) si eliminano per intero; l'unico richiamo di nota `[n]` si toglie. Un test
   sul corpus verifica che nei corpi non restino `_`, `[Illustrazione` né richiami `[n]`.

### 6.2 Chunking
- Configurabile: `CHUNK_STRATEGIA` (`paragrafi` | `caratteri`), `CHUNK_DIMENSIONE` (default
  1200), `CHUNK_OVERLAP` (default 200). Vincolo: `0 <= overlap < dimensione`, altrimenti errore di
  configurazione.
- **`paragrafi` (default):** si accumulano paragrafi interi (uniti da `\n\n`) finché il chunk
  resta entro la dimensione. Una ricetta che ci sta tutta è **1 chunk**. Un paragrafo da solo
  più lungo della dimensione si spezza a fine frase (`. `, `; `, `: `) e, se non basta, a fine
  parola. **Overlap:** ogni chunk dopo il primo comincia con la coda del precedente, al massimo
  `CHUNK_OVERLAP` caratteri, tagliata all'inizio di una parola. La dimensione massima vale per il
  testo nuovo del chunk; con l'overlap un chunk può arrivare a dimensione + overlap (scelta mia,
  per non spezzare paragrafi solo per far spazio alla coda).
- **`caratteri`:** finestre fisse di `CHUNK_DIMENSIONE` caratteri con passo
  `dimensione − overlap`, aggiustate all'inizio di una parola. Esiste per rendere davvero
  configurabile la strategia e per confronti futuri; non è il default.
- `chunk_index` parte da 0 dentro ogni ricetta.

### 6.3 Identificativi, payload, duplicati
- `documento_id` = `artusi-NNN` (numero a tre cifre, es. `artusi-089`).
- **ID del punto** = `uuid5(NAMESPACE_PROGETTO, f"{documento_id}:{chunk_index}")`, dove
  `NAMESPACE_PROGETTO` è un UUID costante nel codice (non è configurazione: cambiarlo
  cambierebbe tutti gli ID). Scrittura solo con **upsert**.
- **Payload** di ogni punto: `documento_id` (str), `numero` (int), `titolo` (str, es. «Gnocchi di
  patate»), `capitolo` (str), `posizione` (int = chunk_index), `testo` (str, il testo del chunk),
  `fonte` (str = «Artusi, La scienza in cucina (Project Gutenberg n. 59047)»).
- **Chunk eliminati:** dopo l'upsert si leggono (scroll, solo ID) tutti i punti della collezione e
  si cancellano quelli il cui ID non è tra quelli appena prodotti. Funziona anche se il chunking
  cambia e una ricetta ha meno chunk di prima.
- **Duplicati:** due ingestion di fila producono gli stessi ID → stesso numero di punti. I titoli
  ripetuti nel libro (es. «Cacciucco I» e «Cacciucco II») sono ricette diverse con numeri
  diversi, quindi documenti diversi. Nei risultati **non** si raggruppa per ricetta (decisione
  dell'utente): due chunk della stessa ricetta possono occupare due posti.
- **Indici sul payload:** `capitolo` (keyword), l'unico campo filtrato in questa fase.

### 6.4 Collezione e modello
- Nome della collezione da `COLLEZIONE`. Se non esiste, l'ingestion la crea: distanza **coseno**,
  dimensione del vettore ricavata dal primo embedding (768 per nomic-embed-text-v1.5, ma non
  scritta nel codice), indice su `capitolo`.
- **Metadati della collezione** (campo `metadata` nativo di Qdrant, supportato da qdrant-client
  1.20 e dalla modalità in memoria): `modello_embedding`, `dimensione`, `prefisso_documento`,
  `prefisso_query`.
- **Cambio di modello:** se la collezione esiste e `metadata.modello_embedding` è diverso da
  `MODELLO_EMBEDDING`, l'ingestion si ferma **prima di calcolare qualsiasi embedding e di scrivere
  qualsiasi cosa**, con codice di uscita ≠ 0 e un messaggio del tipo: «La collezione "artusi" è
  stata creata con il modello X; la configurazione indica Y. Usa un'altra COLLEZIONE oppure
  cancella la collezione.» Lo stesso controllo vale per la ricerca (una query fatta con un altro
  modello darebbe risultati senza senso). Anche una collezione esistente senza metadati blocca
  l'ingestion (scelta mia: non si sa con che modello è stata riempita).
- Bloccano allo stesso modo anche `prefisso_documento` e `prefisso_query` diversi (scelta mia:
  i prefissi fanno parte del modo d'uso del modello, cambiarli mescolerebbe vettori non
  confrontabili) e una `dimensione` diversa. **Non** blocca un cambio di chunking: i chunk
  rimasti orfani vengono cancellati (6.3), e la modifica B dovrà poter ricalcolare gli embedding
  nella stessa collezione.

### 6.5 Embedding
- Chiamata `POST {LMSTUDIO_URL}/embeddings` con `{"model": MODELLO_EMBEDDING, "input": [...]}`,
  a lotti di `EMBEDDING_BATCH` testi (default 32).
- **Prefissi del modello** in configurazione: `PREFISSO_DOCUMENTO="search_document: "` aggiunto a
  ogni testo indicizzato, `PREFISSO_QUERY="search_query: "` aggiunto alla domanda. Il payload
  `testo` resta senza prefisso.
- Interfaccia minima dell'embedder (per sostituirlo nei test): una funzione/metodo che riceve una
  lista di stringhe **già complete** (prefisso compreso) e restituisce una lista di vettori. Il
  prefisso lo aggiunge la pipeline, non l'embedder, così un embedder finto può registrare
  esattamente il testo ricevuto (servirà al test della modifica B: prefisso del modello **prima**
  di titolo e capitolo).
- Errori: LM Studio non raggiungibile, risposta non 200 o numero di vettori diverso dai testi →
  eccezione con messaggio chiaro (URL e modello), uscita ≠ 0 dalla CLI.

### 6.6 Ricerca
- Funzione `cerca(domanda, k=5, capitolo=None, *, client, embedder, config) -> list[Risultato]`.
  `Risultato` contiene: `score`, `numero`, `titolo`, `capitolo`, `posizione`, `documento_id`,
  `testo`, `fonte`.
- **k:** intero con `1 <= k <= 20`; il massimo 20 è una costante nel codice. Fuori intervallo →
  `ValueError` (la CLI mostra l'errore ed esce con codice ≠ 0). Non si "taglia" in silenzio.
- **Filtro capitolo:** il nome passato è confrontato senza distinzione tra maiuscole e minuscole
  con i 23 capitoli e convertito nella forma salvata; poi diventa un `Filter` nativo Qdrant
  (`FieldCondition(key="capitolo", match=MatchValue(...))`) passato alla query. Capitolo
  sconosciuto → errore con l'elenco dei capitoli validi.
- CLI: `python -m rag.ricerca "domanda" [--capitolo X] [--k N]` (default k=5). Per ogni risultato
  stampa posizione in classifica, score, «Ricetta N — Titolo», capitolo, «chunk P» e un estratto
  del testo.

### 6.7 Configurazione (`.env.example`)
| Variabile | Esempio | Note |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | |
| `COLLEZIONE` | `artusi` | |
| `LMSTUDIO_URL` | `http://localhost:1234/v1` | da un container: `http://host.docker.internal:1234/v1` |
| `MODELLO_EMBEDDING` | `text-embedding-nomic-embed-text-v1.5` | l'identificativo restituito da `GET /v1/models` di LM Studio, da verificare |
| `PREFISSO_DOCUMENTO` | `search_document: ` | |
| `PREFISSO_QUERY` | `search_query: ` | |
| `CHUNK_STRATEGIA` | `paragrafi` | `paragrafi` o `caratteri` |
| `CHUNK_DIMENSIONE` | `1200` | |
| `CHUNK_OVERLAP` | `200` | |
| `EMBEDDING_BATCH` | `32` | |
| `CORPUS` | `dati/artusi.txt` | |

Una variabile obbligatoria mancante (URL, collezione, modello) → errore chiaro che dice quale.

### 6.8 Docker Compose
`compose.yaml` con il solo servizio Qdrant: immagine con versione fissata (che supporti i
metadati della collezione: da verificare in fase di piano), porta 6333, volume nominato
persistente. LM Studio resta sull'host. L'ingestion gira sull'host con il venv.

### 6.9 Output dell'ingestion
Stampa: ricette lette (790), capitoli (23), chunk prodotti, punti upsertati, punti eliminati,
punti nella collezione alla fine.

## 7. Test (tutti con servizi spenti)
- Embedder finto: vettori deterministici ricavati dal testo (es. hash → vettore normalizzato), che
  registra i testi ricevuti. Qdrant: `QdrantClient(":memory:")`.
- **Corpus reale** (`dati/artusi.txt`, fuori da Git): i test che lo usano vengono saltati con un
  messaggio se il file manca. Verificano 790 ricette numerate 1..790 senza buchi, 23 capitoli con i
  nomi attesi, corpi non vuoti, assenza di testo Gutenberg.
- **Introduzioni scartate:** il corpo della ricetta 6 «Sugo di pomodoro» finisce con «…quando
  crediate questi odori confacenti al bisogno.» e **non** contiene l'introduzione di MINESTRE
  (per esempio «la minestra era la biada dell'uomo»). Allo stesso modo l'ultima ricetta di
  «Pasticceria» non contiene la lettera «Un ammiratore» e l'ultima di «Erbaggi e legumi» non
  contiene «Qualità e stagione dei pesci».
- **Estratto di prova** in `tests/fixtures/` (poche ricette in formato Gutenberg, testo di pubblico
  dominio) per i test di parsing e chunking che non devono dipendere dal file completo.
- Ricetta **breve** (es. 106, ~360 caratteri) → 1 chunk identico al corpo; ricetta **lunga** (es. 7,
  ~4200 caratteri) → più chunk, ognuno entro dimensione + overlap, con overlap col precedente,
  nessun testo perso.
- Ingestion due volte → stesso numero di punti, stessi ID.
- Chunk eliminati: si ingerisce con dimensione grande, poi piccola, poi di nuovo grande → nessun
  punto orfano.
- Cambio di modello → errore, collezione intatta, nessuna chiamata all'embedder.
- Ricerca con `--capitolo` → tutti i risultati di quel capitolo, al massimo k; il filtro è passato
  a Qdrant (verificato anche controllando che con k grande non arrivino risultati di altri capitoli).
- k = 0, k = 21 → errore; capitolo sconosciuto → errore con elenco.
- Testo passato all'embedder = `PREFISSO_DOCUMENTO + testo del chunk`; domanda =
  `PREFISSO_QUERY + domanda`.
- Configurazione: variabile mancante → errore; overlap ≥ dimensione → errore.

## 8. Criteri di accettazione (Fase 1)
1. 790 ricette con numerazione senza buchi.
2. Due ingestion di fila danno lo stesso numero di punti.
3. Con `--capitolo` tutti i risultati sono di quel capitolo, al massimo k.
4. Dato un risultato si sa indicare ricetta, capitolo e posizione del chunk.
5. Tutti i test passano con LM Studio e Qdrant spenti.

## 9. Lasciato al costruttore
- Struttura interna dei moduli (proposta: `config`, `corpus`, `chunking`, `embedder`, `indice`,
  `ingestion`, `ricerca`).
- Il modo di riconoscere i titoli di capitolo, purché il test sui 23 capitoli passi.
- Le versioni esatte delle dipendenze e dell'immagine Qdrant, purché compatibili con i metadati
  della collezione.
- Formato esatto della stampa della CLI.
