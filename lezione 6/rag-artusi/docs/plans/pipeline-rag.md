# Pipeline RAG sull'Artusi — Piano di implementazione (Fase 1)

> **Per chi esegue:** usare superpowers:subagent-driven-development oppure
> superpowers:executing-plans, un task alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** ingestion idempotente delle 790 ricette dell'Artusi in Qdrant con embedding di
LM Studio, e ricerca semantica (funzione + CLI) con filtro nativo per capitolo.

**Architettura:** moduli piccoli nel package `rag/`: `config` (lettura `.env`), `corpus`
(pulizia e parsing in ricette), `chunking` (chunk e ID stabili), `embedder` (client HTTP di
LM Studio), `indice` (operazioni Qdrant e metadati), `ingestion` e `ricerca` (orchestrazione e
CLI). L'embedder e il client Qdrant vengono passati come argomenti, così i test usano un embedder
finto e `QdrantClient(":memory:")`.

**Tecnologie:** Python 3.13 (venv; vincolo 3.11+), `qdrant-client==1.20.0`, `httpx==0.28.1`,
`python-dotenv==1.2.4`, `pytest==9.2.0` (+ `PyYAML==6.0.3` dal Task 9); Docker image
`qdrant/qdrant:v1.20.2`.

**Specifica:** `docs/specs/pipeline-rag.md` (approvata il 2026-11-17). Chi esegue legge
specifica e piano insieme.

## Vincoli globali

- Tutti i percorsi sono relativi a `lezione 6/rag-artusi/`; comandi da quella cartella in
  PowerShell, senza attivare il venv: `.\.venv\Scripts\python.exe -m pytest -v`.
- Modello, `QDRANT_URL`, `LMSTUDIO_URL`, `COLLEZIONE`, prefissi e parametri di chunking solo da
  configurazione (`.env`, `.env.example`), mai letterali nel codice di `rag/`.
- Distanza coseno; un punto per chunk; ID = `uuid5(NAMESPACE_PROGETTO, f"{documento_id}:{chunk_index}")`;
  solo upsert.
- Payload esatto: `documento_id`, `numero`, `titolo`, `capitolo`, `posizione`, `testo`, `fonte`;
  `fonte` = `"Artusi, La scienza in cucina (Project Gutenberg n. 59047)"`.
- `K_MASSIMO = 20`; filtro capitolo come `Filter` nativo passato a Qdrant.
- Tutti i test passano con LM Studio e Qdrant spenti; i test sul corpus reale si saltano se
  `dati/artusi.txt` manca.
- `dati/` e `.env` mai in Git. Un commit per task, Conventional Commits in italiano, con la riga
  `Co-Authored-By` prevista.

## Attenzione in revisione

Casi che la specifica implica ma che nessun criterio di accettazione nomina; ciascuno ha un test
nel task che possiede il codice:
1. **LM Studio spento** durante l'ingestion o la ricerca → messaggio chiaro con URL e modello,
   uscita 1, nessuno stack trace (Task 4 e Task 6/7).
2. **Qdrant spento** → messaggio chiaro con `QDRANT_URL`, uscita 1 (Task 6/7).
3. **Ricerca su una collezione che non esiste** → errore «esegui prima `python -m rag.ingestion`»
   (Task 7).
4. **Domanda vuota o solo spazi** → `ValueError`, nessuna chiamata all'embedder (Task 7).
5. **Capitolo scritto con spazi o maiuscole** (`"  PIATTI di pesce "`) → riconosciuto come
   «Piatti di pesce» (Task 7).

---

### Task 1: Scheletro del progetto e configurazione

**File:**
- Crea: `requirements.txt`, `.env.example`, `compose.yaml`, `rag/__init__.py`, `rag/config.py`,
  `tests/__init__.py`, `tests/conftest.py`, `tests/test_config.py`

**Interfacce:**
- Produce:
  - `@dataclass(frozen=True) class Config` con campi `qdrant_url: str`, `collezione: str`,
    `lmstudio_url: str`, `modello_embedding: str`, `prefisso_documento: str`,
    `prefisso_query: str`, `chunk_strategia: str`, `chunk_dimensione: int`,
    `chunk_overlap: int`, `embedding_batch: int`, `corpus: Path`.
  - `class ErroreConfigurazione(Exception)`.
  - `carica_config(env: Mapping[str, str] | None = None) -> Config`: con `None` chiama
    `load_dotenv()` e legge `os.environ`. Obbligatorie: `QDRANT_URL`, `COLLEZIONE`,
    `LMSTUDIO_URL`, `MODELLO_EMBEDDING`. Default: prefissi `""`, strategia `paragrafi`,
    dimensione 1200, overlap 200, batch 32, corpus `dati/artusi.txt`.
  - Fixture in `tests/conftest.py`: `config_test` (Config valida con `collezione="test"`,
    prefissi `"search_document: "` / `"search_query: "`, modello `"finto"`).

- [ ] **Passo 1: ambiente.** `py -3.13 -m venv .venv`; `requirements.txt` con le quattro
  dipendenze fissate sopra; `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- [ ] **Passo 2: `.env.example`** con le 11 variabili della tabella §6.7 della specifica (valori
  d'esempio della tabella, prefissi tra virgolette per conservare lo spazio finale, commento
  `# da un container: http://host.docker.internal:1234/v1`).
- [ ] **Passo 3: `compose.yaml`** con il solo servizio `qdrant`: `image: qdrant/qdrant:v1.20.2`,
  `ports: ["6333:6333"]`, volume nominato `qdrant_dati:/qdrant/storage`.
- [ ] **Passo 4: test che falliscono** in `tests/test_config.py`:
  - `test_config_completa`: env con tutte le variabili → campi convertiti (`chunk_dimensione == 1200`
    come int, `prefisso_documento == "search_document: "` con lo spazio).
  - `test_default`: solo le 4 obbligatorie → `chunk_strategia == "paragrafi"`, `chunk_overlap == 200`,
    `embedding_batch == 32`, prefissi `""`.
  - `test_variabile_mancante` (parametrizzato sulle 4 obbligatorie): `ErroreConfigurazione` il cui
    messaggio contiene il nome della variabile.
  - `test_overlap_non_valido`: overlap 1200 con dimensione 1200 → `ErroreConfigurazione`; overlap −1
    → idem.
  - `test_strategia_sconosciuta`: `CHUNK_STRATEGIA=frasi` → `ErroreConfigurazione`.
- [ ] **Passo 5:** `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v` → FAIL (modulo assente).
- [ ] **Passo 6:** implementare `rag/config.py`.
- [ ] **Passo 7:** stesso comando → PASS.
- [ ] **Passo 8: commit** `feat(config): scheletro del progetto, configurazione e Qdrant in Compose`.

### Task 2: Pulizia del testo e parsing delle ricette

**File:**
- Crea: `rag/corpus.py`, `tests/fixtures/mini_artusi.txt`, `tests/test_corpus.py`

**Interfacce:**
- Produce:
  - `CAPITOLI: tuple[str, ...]` — i 23 nomi in forma leggibile, nell'ordine della specifica §6.1.4.
  - `@dataclass(frozen=True) class Ricetta`: `numero: int`, `titolo: str`, `capitolo: str`,
    `corpo: str`.
  - `pulisci(testo: str) -> str`: toglie BOM, CRLF → LF, tiene solo il testo tra le righe
    `*** START OF` e `*** END OF`.
  - `estrai_ricette(testo_pulito: str) -> list[Ricetta]`.
  - `carica_corpus(percorso: Path) -> list[Ricetta]` = `estrai_ricette(pulisci(lettura utf-8))`.

**Scelte per chi implementa:**
- Titoli di capitolo riconosciuti per confronto esatto con i nomi in maiuscolo di `CAPITOLI`
  (`nome.upper()`, es. `"BRODI, GELATINA E SUGHI"`) su una riga intera; `MINESTRE` e `APPENDICE`
  sono righe di confine che non diventano capitolo. Il parsing comincia dopo la riga `RICETTE`.
- Intestazione di ricetta: `^(\d+)\. (.+)$` accettata solo se il numero è quello atteso.
- Il corpo di una ricetta finisce alla ricetta successiva, a un titolo di capitolo, a `MINESTRE`
  o ad `APPENDICE`.
- Corpo: paragrafi separati da `\n\n`; righe di prosa unite con uno spazio; righe che nel testo
  originale iniziano con uno spazio restano una per riga (senza rientro) unite da `\n`;
  rimozione di `_` del corsivo, dei blocchi `[Illustrazione: … ]` anche su più righe e dei richiami
  `[n]`.
- Il fixture `mini_artusi.txt` (testo di pubblico dominio preso dal libro, ~80 righe) contiene:
  intestazione Gutenberg, riga START, una riga `RICETTE`, il capitolo `BRODI, GELATINA E SUGHI` con
  le ricette 1 e 2 (la 2 con un corsivo `_…_` e un blocco `[Illustrazione: …]` su due righe), poi
  `MINESTRE` con due righe d'introduzione, `MINESTRE IN BRODO` con la ricetta 3 (elenco ingredienti
  rientrato e una riga di prosa che inizia con `137. `), `APPENDICE`, una riga d'indice
  `227. Scaloppine alla livornese p.`, riga END e due righe di licenza.

- [ ] **Passo 1: test che falliscono** in `tests/test_corpus.py`.
  Sul fixture (sempre eseguiti):
  - `test_pulisci_toglie_gutenberg`: nessun `"Project Gutenberg"` e nessun `"\r"` nel risultato.
  - `test_fixture_tre_ricette`: numeri `[1, 2, 3]`; capitoli `["Brodi, gelatina e sughi"] * 2 +
    ["Minestre in brodo"]`.
  - `test_falso_positivo_nel_corpo`: il corpo della 3 contiene `"137. "`; l'indice dell'Appendice
    non crea ricette.
  - `test_introduzione_scartata`: il corpo della 2 non contiene le righe d'introduzione di `MINESTRE`.
  - `test_marcatura_rimossa`: corpo della 2 senza `"_"` e senza `"[Illustrazione"`, con le parole
    del corsivo.
  - `test_ingredienti_una_per_riga`: nel corpo della 3 ogni ingrediente è una riga a sé, senza
    rientro.
  - `test_titolo_non_nel_corpo`: il corpo non comincia con il titolo.
  Sul corpus reale (`pytest.mark.skipif(not Path("dati/artusi.txt").exists(), reason=...)`), con
  una fixture di modulo che carica il corpus una volta:
  - `test_790_ricette_senza_buchi`: `[r.numero for r in ricette] == list(range(1, 791))`.
  - `test_23_capitoli`: `tuple(dict.fromkeys(r.capitolo for r in ricette)) == CAPITOLI` e
    `len(CAPITOLI) == 23`.
  - `test_confini_capitoli` (verificati sul testo il 2026-11-17): ricetta 6 «Sugo di pomodoro»
    capitolo «Brodi, gelatina e sughi»; 454 «Insalata russa» capitolo «Erbaggi e legumi»;
    636 «Pane di sabbia» capitolo «Pasticceria»; 455 «Cacciucco I» capitolo «Piatti di pesce»;
    790 «Spezie fini» capitolo «Cose diverse».
  - `test_ricetta_6_senza_introduzione_minestre`: il corpo della 6 termina con
    `"questi odori confacenti al bisogno."` e non contiene `"la minestra era la biada dell'uomo"`.
  - `test_altre_introduzioni_scartate`: il corpo della 636 non contiene `"Non per farmene bello"` né
    `"UN AMMIRATORE"`; il corpo della 454 non contiene `"QUALITÀ E STAGIONE DEI PESCI"`.
  - `test_corpi_puliti`: tutti i corpi non vuoti, senza `"_"`, `"[Illustrazione"`, `"Gutenberg"`, né
    richiami `re.search(r"\[\d+\]", corpo)`.
  - `test_208_senza_cacciatora`: `"cacciatora" not in corpo_208.lower()` (premessa della modifica B).
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_corpus.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/corpus.py` e il fixture.
- [ ] **Passo 4:** stesso comando → PASS (i test sul corpus reale girano, non vengono saltati).
- [ ] **Passo 5: commit** `feat(corpus): pulizia del testo Gutenberg e parsing delle 790 ricette`.

### Task 3: Chunking e identificativi stabili

**File:**
- Crea: `rag/chunking.py`, `tests/test_chunking.py`

**Interfacce:**
- Consuma: `Ricetta`, `Config`.
- Produce:
  - `NAMESPACE_PROGETTO: uuid.UUID` (costante fissa, generata una volta e scritta nel codice).
  - `FONTE = "Artusi, La scienza in cucina (Project Gutenberg n. 59047)"`.
  - `documento_id(numero: int) -> str` → `"artusi-089"`.
  - `id_punto(documento_id: str, chunk_index: int) -> str` → `str(uuid5(...))`.
  - `dividi(testo: str, strategia: str, dimensione: int, overlap: int) -> list[str]`.
  - `@dataclass(frozen=True) class Chunk`: `id: str`, `testo: str`, `payload: dict` (i 7 campi).
  - `crea_chunk(ricette: list[Ricetta], config: Config) -> list[Chunk]`.

**Algoritmo `paragrafi`** (la specifica §6.2 lo fissa; qui l'ordine delle operazioni):
1. se `len(testo) <= dimensione` → `[testo]`;
2. spezzare i paragrafi più lunghi di `dimensione` in pezzi ≤ dimensione, a fine frase
   (`. `, `; `, `: `) o, se non basta, a fine parola;
3. accumulare pezzi uniti da `\n\n` finché il testo nuovo resta ≤ dimensione;
4. ogni chunk dopo il primo = coda del precedente (≤ `overlap` caratteri, che inizia a una parola)
   + lo stesso separatore che c'era nel testo originale in quel punto (`"\n\n"` tra paragrafi,
   `" "` tra due pezzi dello stesso paragrafo) + il testo nuovo; con `overlap == 0` nessuna coda.

- [ ] **Passo 1: test che falliscono** in `tests/test_chunking.py`:
  - `test_documento_id`: `documento_id(89) == "artusi-089"`, `documento_id(790) == "artusi-790"`.
  - `test_id_stabile`: due chiamate uguali → stesso ID; `("artusi-089", 0)` ≠ `("artusi-089", 1)` ≠
    `("artusi-090", 0)`; `uuid.UUID(id).version == 5`.
  - `test_breve_un_chunk`: testo di 359 caratteri → `[testo]` identico.
  - `test_lungo_sintetico`: 12 paragrafi da ~300 caratteri → più chunk; ogni chunk
    `len <= 1200 + 200`; dal secondo in poi il chunk comincia con un suffisso del precedente lungo
    ≤ 200; ogni paragrafo originale compare intero in almeno un chunk.
  - `test_paragrafo_gigante`: un paragrafo di 3000 caratteri senza `\n\n` → chunk ≤ 1400 che non
    tagliano parole.
  - `test_strategia_caratteri`: 3000 caratteri, dimensione 1000, overlap 100 → chunk ≤ 1000 che
    iniziano a una parola, concatenazione senza overlap = testo originale.
  - `test_crea_chunk_payload`: per una `Ricetta(89, "Gnocchi di patate", "Minestre asciutte e di magro", ...)`
    il payload ha esattamente le 7 chiavi; `posizione` 0..n-1; `testo` senza prefissi;
    `fonte == FONTE`.
  - Corpus reale (skipif): `test_ricetta_breve_reale` (106 → 1 chunk); `test_ricetta_lunga_reale`
    (7 → ≥ 3 chunk, condizioni come `test_lungo_sintetico`); `test_id_unici_corpus`: nessun ID
    ripetuto su tutti i chunk.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_chunking.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/chunking.py`.
- [ ] **Passo 4:** stesso comando → PASS.
- [ ] **Passo 5: commit** `feat(chunking): chunk per paragrafi con overlap e ID uuid5 stabili`.

### Task 4: Embedder di LM Studio ed embedder finto

**File:**
- Crea: `rag/embedder.py`, `tests/finti.py`, `tests/test_embedder.py`

**Interfacce:**
- Produce:
  - `class Embedder(Protocol)`: `def embed(self, testi: list[str]) -> list[list[float]]` (testi già
    completi di prefisso).
  - `class ErroreEmbedding(Exception)`.
  - `class EmbedderLMStudio`: `__init__(self, url: str, modello: str, batch: int,
    client: httpx.Client | None = None)`; `embed` fa `POST {url}/embeddings` con
    `{"model": modello, "input": lotto}` per lotti di `batch`, ordina per `index` della risposta.
    Errori di connessione, stato ≠ 200 o numero di vettori diverso → `ErroreEmbedding` con URL e
    modello nel messaggio.
  - In `tests/finti.py`: `class EmbedderFinto` con `dimensione: int = 8`, `ricevuti: list[str]`
    (ogni testo ricevuto, in ordine), `chiamate: int`; vettore deterministico ricavato da
    `hashlib.sha256(testo)`.

- [ ] **Passo 1: test che falliscono** (con `httpx.MockTransport`, nessuna rete):
  - `test_richiesta_corretta`: il corpo inviato è `{"model": "m", "input": ["a", "b"]}` all'URL
    `http://x/v1/embeddings`.
  - `test_lotti`: 5 testi con batch 2 → 3 richieste, 5 vettori nell'ordine dei testi.
  - `test_ordine_per_index`: risposta con `index` invertiti → vettori riordinati.
  - `test_errore_http`: stato 500 → `ErroreEmbedding` con `"http://x/v1"` e `"m"` nel messaggio.
  - `test_lmstudio_spento`: transport che solleva `httpx.ConnectError` → `ErroreEmbedding`
    (Attenzione in revisione, punto 1).
  - `test_numero_vettori_sbagliato`: 2 testi, 1 vettore → `ErroreEmbedding`.
  - `test_finto_deterministico`: stesso testo → stesso vettore; testi diversi → vettori diversi;
    `ricevuti` registra i testi.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_embedder.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/embedder.py` e `tests/finti.py`.
- [ ] **Passo 4:** stesso comando → PASS.
- [ ] **Passo 5: commit** `feat(embedder): client degli embedding di LM Studio e embedder finto per i test`.

### Task 5: Collezione, metadati e scrittura in Qdrant

**File:**
- Crea: `rag/indice.py`, `tests/test_indice.py`

**Interfacce:**
- Consuma: `Config`, `Chunk`.
- Produce:
  - `class ErroreCollezione(Exception)` (collezione assente, metadati incompatibili).
  - `metadati_attesi(config: Config, dimensione: int | None = None) -> dict`: chiavi
    `modello_embedding`, `prefisso_documento`, `prefisso_query` (+ `dimensione` se data).
  - `verifica_compatibilita(client: QdrantClient, config: Config, dimensione: int | None = None) -> bool`:
    `False` se la collezione non esiste; `True` se esiste ed è compatibile; altrimenti
    `ErroreCollezione` con messaggio «La collezione "<nome>" è stata creata con <campo> = <vecchio>;
    la configurazione indica <nuovo>. Usa un'altra COLLEZIONE oppure cancella la collezione.»
    (anche per collezione senza metadati). Confronta `dimensione` solo se passata.
  - `crea_collezione(client, config, dimensione: int) -> None`: coseno, `metadata=metadati_attesi(...)`,
    indice payload `capitolo` di tipo keyword.
  - `scrivi(client, nome: str, chunk: list[Chunk], vettori: list[list[float]]) -> int` (upsert, a
    lotti di 256).
  - `elimina_orfani(client, nome: str, id_validi: set[str]) -> int` (scroll di soli ID, delete della
    differenza, restituisce quanti).
  - `conta(client, nome: str) -> int` (`count(exact=True)`).

- [ ] **Passo 1: test che falliscono** con `QdrantClient(":memory:")`:
  - `test_crea_collezione`: distanza `COSINE`, dimensione 8, metadati con i 4 campi, schema del
    payload contiene `capitolo`.
  - `test_verifica_assente`: → `False`.
  - `test_verifica_compatibile`: → `True`.
  - `test_modello_diverso` / `test_prefisso_diverso` / `test_dimensione_diversa`: → `ErroreCollezione`
    con entrambi i valori nel messaggio.
  - `test_senza_metadati`: collezione creata a mano senza `metadata` → `ErroreCollezione`.
  - `test_upsert_idempotente`: `scrivi` due volte gli stessi 3 chunk → `conta == 3`.
  - `test_elimina_orfani`: 5 punti, `id_validi` con 3 → restituisce 2, `conta == 3`.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_indice.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/indice.py`.
- [ ] **Passo 4:** stesso comando → PASS.
- [ ] **Passo 5: commit** `feat(indice): collezione Qdrant con metadati del modello, upsert e pulizia degli orfani`.

### Task 6: Ingestion

**File:**
- Crea: `rag/ingestion.py`, `tests/test_ingestion.py`

**Interfacce:**
- Consuma: `carica_config`, `carica_corpus`, `crea_chunk`, `EmbedderLMStudio`, funzioni di `indice`.
- Produce:
  - `@dataclass class Rapporto`: `ricette: int`, `capitoli: int`, `chunk: int`, `scritti: int`,
    `eliminati: int`, `punti: int`.
  - `esegui_ingestion(config: Config, client: QdrantClient, embedder: Embedder,
    ricette: list[Ricetta] | None = None) -> Rapporto` (con `None` carica `config.corpus`).
    Ordine: corpus → chunk → `verifica_compatibilita` (senza dimensione) **prima di qualsiasi
    embedding** → embedding di `prefisso_documento + chunk.testo` → se la collezione esiste,
    `verifica_compatibilita(..., dimensione=len(vettore))`, altrimenti `crea_collezione` → `scrivi`
    → `elimina_orfani` → `conta`.
  - `main(argv: list[str] | None = None) -> int`: crea `QdrantClient(url=config.qdrant_url)` ed
    `EmbedderLMStudio`, stampa il rapporto (una riga per campo), restituisce 0. Su
    `ErroreConfigurazione`, `ErroreCollezione`, `ErroreEmbedding` o errore di connessione a Qdrant
    stampa il messaggio su stderr e restituisce 1. `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Passo 1: test che falliscono** (embedder finto, Qdrant in memoria, ricette del fixture):
  - `test_due_ingestion_stesso_numero`: due esecuzioni → stesso `punti`, stesso insieme di ID
    (scroll).
  - `test_testo_passato_all_embedder`: `finto.ricevuti[i] == "search_document: " + chunk.testo` per
    ogni chunk; il payload `testo` non contiene `"search_document"`.
  - `test_chunk_eliminati`: ingestion con dimensione 1200, poi con dimensione 300 (più chunk), poi di
    nuovo 1200 → `punti` uguale alla prima volta, `eliminati > 0` nell'ultima.
  - `test_modello_cambiato`: dopo un'ingestion, config con `modello_embedding="altro"` →
    `ErroreCollezione`, `finto.chiamate` invariato, `conta` invariato.
  - `test_main_qdrant_spento`: `main` con `QDRANT_URL=http://127.0.0.1:1` (via monkeypatch dell'env)
    → restituisce 1 e stderr contiene `127.0.0.1:1` (Attenzione in revisione, punto 2).
  - `test_main_lmstudio_spento`: `LMSTUDIO_URL=http://127.0.0.1:1/v1`, Qdrant in memoria iniettato
    con monkeypatch su `rag.ingestion.QdrantClient` → 1, messaggio con l'URL.
  - Corpus reale (skipif): `test_ingestion_corpus_reale`: `ricette == 790`, `capitoli == 23`,
    `punti == chunk`, seconda esecuzione con lo stesso `punti`.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_ingestion.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/ingestion.py`.
- [ ] **Passo 4:** stesso comando → PASS.
- [ ] **Passo 5: commit** `feat(ingestion): ingestion idempotente con controllo del modello e rapporto`.

### Task 7: Ricerca (funzione e CLI)

**File:**
- Crea: `rag/ricerca.py`, `tests/test_ricerca.py`

**Interfacce:**
- Consuma: `Config`, `Embedder`, `verifica_compatibilita`, `CAPITOLI`.
- Produce:
  - `K_MASSIMO = 20`.
  - `@dataclass(frozen=True) class Risultato`: `score: float`, `numero: int`, `titolo: str`,
    `capitolo: str`, `posizione: int`, `documento_id: str`, `testo: str`, `fonte: str`.
  - `normalizza_capitolo(nome: str) -> str`: confronto con `CAPITOLI` dopo `strip()` e
    `casefold()`; sconosciuto → `ValueError` con i 23 nomi nel messaggio.
  - `cerca(domanda: str, k: int = 5, capitolo: str | None = None, *, client: QdrantClient,
    embedder: Embedder, config: Config) -> list[Risultato]`. Ordine: validare `domanda` (non
    vuota) e `1 <= k <= K_MASSIMO` (`ValueError`) → `verifica_compatibilita`; se `False` →
    `ErroreCollezione("... esegui prima python -m rag.ingestion")` → embedding di
    `prefisso_query + domanda` → `client.query_points(..., query_filter=Filter(must=[FieldCondition(
    key="capitolo", match=MatchValue(value=...))]) se capitolo, limit=k, with_payload=True)`.
  - `main(argv: list[str] | None = None) -> int`: argparse con `domanda`, `--capitolo`, `--k`
    (int, default 5). Per ogni risultato stampa
    `"{i}. [{score:.3f}] Ricetta {numero} — {titolo} | {capitolo} | chunk {posizione}"` e i primi
    200 caratteri del testo. Errori come in `ingestion.main` → stderr, 1.

- [ ] **Passo 1: test che falliscono** (fixture di modulo: ingestion del corpus reale se presente,
  altrimenti del fixture, con embedder finto e Qdrant in memoria):
  - `test_filtro_capitolo`: `capitolo="Piatti di pesce"` (o il capitolo del fixture), `k=20` →
    tutti i risultati di quel capitolo, `len <= 20`.
  - `test_filtro_nativo`: spia su `client.query_points` → `query_filter` non è `None` e contiene la
    condizione su `capitolo`.
  - `test_al_massimo_k`: `k=3` → `len <= 3`.
  - `test_k_fuori_intervallo` (parametrizzato 0, 21, -1) → `ValueError`.
  - `test_capitolo_normalizzato`: `"  PIATTI di pesce "` → `"Piatti di pesce"` (Attenzione in
    revisione, punto 5).
  - `test_capitolo_sconosciuto`: `ValueError` con `"Pasticceria"` nel messaggio.
  - `test_domanda_vuota`: `"   "` → `ValueError`, `finto.chiamate` invariato (punto 4).
  - `test_prefisso_query`: l'ultimo testo ricevuto dal finto è `"search_query: gnocchi"`.
  - `test_risultato_completo`: ogni risultato ha `numero`, `titolo`, `capitolo`, `posizione`
    valorizzati e coerenti con il payload.
  - `test_collezione_assente`: → `ErroreCollezione` con `"rag.ingestion"` nel messaggio (punto 3).
  - `test_modello_diverso_in_ricerca`: config con altro modello → `ErroreCollezione`.
  - `test_main_stampa`: `main(["gnocchi", "--k", "2"])` con dipendenze iniettate via monkeypatch →
    0, l'output contiene `"Ricetta "` e `"chunk "`; `main(["x", "--k", "50"])` → 1.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_ricerca.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/ricerca.py`.
- [ ] **Passo 4:** stesso comando → PASS.
- [ ] **Passo 5: commit** `feat(ricerca): ricerca top-k con filtro nativo per capitolo e CLI`.

### Task 8: README e verifica finale della fase

**File:**
- Crea: `README.md`

- [ ] **Passo 1: README** con: scopo e limiti noti (dalla specifica §4), configurazione
  (`copy .env.example .env`, controllo di `MODELLO_EMBEDDING` con `GET /v1/models` di LM Studio),
  avvio di Qdrant (`docker compose up -d`), ingestion, ricerca con esempi, test. Solo comandi
  verificati in questa fase; quelli che richiedono i servizi accesi sono marcati «da verificare
  nella Fase 2».
- [ ] **Passo 2: test a servizi spenti.** Con Qdrant non in esecuzione e LM Studio chiuso:
  `.\.venv\Scripts\python.exe -m pytest -v` → tutti PASS, **nessun test saltato** (il corpus è
  presente in locale).
- [ ] **Passo 3: Git.** `git check-ignore dati/artusi.txt .env` → entrambi stampati;
  `git ls-files dati .env` → vuoto; `git log --oneline` → solo Conventional Commits.
- [ ] **Passo 4: commit** `docs(rag): README con configurazione, comandi e limiti noti`.

### Task 9: Script di valutazione (baseline)

**File:**
- Crea: `eval/domande.yaml`, `rag/valutazione.py`, `tests/test_valutazione.py`,
  `docs/eval-baseline.md` (generato dall'esecuzione reale)
- Modifica: `requirements.txt` (+ `PyYAML==6.0.3`, per leggere il file delle domande)

**Interfacce:**
- Consuma: `cerca`, `Risultato`, `carica_config`, `EmbedderLMStudio`.
- Produce:
  - `@dataclass(frozen=True) class Domanda`: `testo: str`, `attese: tuple[int, ...]` (vuota =
    nessuna fonte attesa).
  - `carica_domande(percorso: Path) -> list[Domanda]`; formato YAML: lista di
    `{domanda: str, attese: [int, ...]}`.
  - `@dataclass(frozen=True) class Riga`: `domanda: str`, `attese: tuple[int, ...]`,
    `posizione: int | None` (posizione 1..k del primo risultato con `numero` in `attese`; `None` se
    assente o se non ci sono fonti attese), `score_migliore: float | None` (score del primo
    risultato), `primo: str` («Ricetta N — Titolo» del primo risultato, per la diagnosi).
  - `valuta(domande: list[Domanda], cerca_fn: Callable[[str, int], list[Risultato]], k: int = 5) -> list[Riga]`.
  - `tabella_markdown(righe: list[Riga]) -> str`: colonne `Domanda | Fonte attesa | Posizione |
    Score migliore | Primo risultato`; fonte attesa `89`, `455, 456` oppure `nessuna`; posizione
    `—` se `None`; score con 3 decimali.
  - `main(argv: list[str] | None = None) -> int`: opzioni `--domande` (default
    `eval/domande.yaml`), `--k` (default 5), `--uscita` (default `docs/eval-baseline.md`), `--titolo`
    (intestazione del file). Stampa la tabella e la salva; errori come in `ricerca.main`.

**Contenuto di `eval/domande.yaml`** (fonti verificate sul testo il 2026-11-17):

| Domanda | Attese | Dove nel testo |
|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | «Patate grosse e gialle, grammi 400. Farina di grano, grammi 150.» |
| Che vino si usa per il pollo alla cacciatora? | 208 | «mezzo bicchiere di San Giovese od altro vino rosso» |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 455: «ne' paesi che costeggiano l'Adriatico è sostituita dalla voce brodetto» |
| Qual è la ricetta del tiramisù? | nessuna | non esiste nel libro |
| Quanti cappelletti bastano a un mangiatore moderato? | 7 | «A un mangiatore discreto bastano due dozzine.» |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | «intrisi con poca farina e appena furono nell'acqua bollente si liquefecero» |
| + 3 domande dell'utente con parole diverse dal testo | da fornire | da chiedere prima del Passo 4 |

- [ ] **Passo 1: test che falliscono** (offline, `cerca_fn` finta che restituisce `Risultato`
  preparati):
  - `test_carica_domande`: YAML di prova con 2 domande → `attese == (455, 456)` e `()`.
  - `test_posizione_trovata`: risultati con numeri `[12, 89, 89]`, attese `(89,)` → `posizione == 2`,
    `score_migliore` = score del primo.
  - `test_posizione_assente`: attese `(208,)` non presenti → `posizione is None`.
  - `test_nessuna_fonte_attesa`: attese `()` → `posizione is None`, `score_migliore` valorizzato.
  - `test_k_passato`: `cerca_fn` riceve `k == 5`.
  - `test_tabella`: intestazione esatta; `455, 456`; `nessuna`; `—`; `0.812`.
  - `test_domande_reali_valide`: `eval/domande.yaml` si carica, ha 9 domande, ogni numero atteso è
    tra 1 e 790.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_valutazione.py -v` → FAIL.
- [ ] **Passo 3:** implementare `rag/valutazione.py` e `eval/domande.yaml` (con le 3 domande
  dell'utente); `pytest -v` completo → PASS. **Commit**
  `feat(valutazione): domande di valutazione e tabella dei risultati`.
- [ ] **Passo 4: esecuzione reale. Fermarsi e chiedere all'utente di avviare LM Studio (con il
  modello di embedding caricato) e Qdrant (`docker compose up -d`); procedere solo dopo la sua
  conferma.** Poi: controllare l'identificativo del modello con `GET {LMSTUDIO_URL}/models`;
  `.\.venv\Scripts\python.exe -m rag.ingestion` **due volte**, annotando i due rapporti;
  `.\.venv\Scripts\python.exe -m rag.valutazione --titolo "Valutazione di partenza"`.
- [ ] **Passo 5:** `docs/eval-baseline.md` contiene data, modello, parametri di chunking, i
  conteggi delle due ingestion (devono coincidere) e la tabella. Nessuna ottimizzazione in questa
  fase. **Commit** `docs(eval): valutazione di partenza`.

---

## Dopo il piano
A fase completata: resoconto di cosa è stato fatto e come è stato testato, poi merge di
`feat/rag-pipeline` in `dev` solo dopo l'ok. Le modifiche A e B hanno specifiche e piani propri.
