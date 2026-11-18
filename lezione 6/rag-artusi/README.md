# RAG sull'Artusi — ingestion e ricerca

Pipeline di *retrieval* sul ricettario di Pellegrino Artusi, *La scienza in cucina e l'arte di
mangiar bene* (Project Gutenberg n. 59047). Nessun modello generativo: solo embedding (LM Studio,
`nomic-embed-text-v1.5`) e ricerca in Qdrant. Specifica: `docs/specs/pipeline-rag.md`;
piano: `docs/plans/pipeline-rag.md`.

## Che cosa viene indicizzato
- Le **790 ricette** numerate, ciascuna con numero, titolo e uno dei **23 capitoli**.
- Chunk per paragrafi (default 1200 caratteri, overlap 200); le ricette brevi sono un chunk solo.
- Payload di ogni punto: `documento_id`, `numero`, `titolo`, `capitolo`, `posizione` (indice del
  chunk nella ricetta), `testo`, `fonte`, `contiene_dosi` (vero se il chunk ha un elenco di almeno 2
  voci «Ingrediente, quantità»; indice bool, filtro `--solo-dosi`).

**Limiti noti:** non sono indicizzati prefazione, «Spiegazione di voci», Appendice («Cucina per
gli stomachi deboli», «Note di pranzi»), i testi introduttivi dei capitoli (per esempio
«Qualità e stagione dei pesci») e la lettera «Un ammiratore».

## Requisiti
- Python 3.11+ (verificato con 3.13), Docker, LM Studio sull'host con il modello di embedding
  caricato.
- Il testo in `dati/artusi.txt` (fuori da Git): scaricarlo da Project Gutenberg, ebook 59047,
  formato «Plain Text UTF-8» (per esempio
  `https://gutenberg.pglaf.org/5/9/0/4/59047/59047-0.txt`).

## Installazione (PowerShell, dalla cartella `lezione 6/rag-artusi/`)
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```
In `.env`, `MODELLO_EMBEDDING` deve essere l'identificativo esatto restituito da LM Studio
(`GET http://localhost:1234/v1/models`). Da un container, LM Studio si raggiunge con
`http://host.docker.internal:1234/v1`.

`numpy` è fissato a 2.3.5 perché su questo Windows il controllo delle applicazioni blocca la DLL
di numpy 2.5.5.

## Uso
Comandi verificati il 2026-11-17 con Qdrant 1.20.2 e LM Studio accesi:
```powershell
docker compose up -d                                   # Qdrant su http://localhost:6333
.\.venv\Scripts\python.exe -m rag.ingestion            # idempotente: rieseguibile (~2 min)
.\.venv\Scripts\python.exe -m rag.ingestion --solo-payload   # aggiorna contiene_dosi senza embedding
.\.venv\Scripts\python.exe -m rag.ricerca "Che vino si usa per il pollo alla cacciatora?" --k 3
.\.venv\Scripts\python.exe -m rag.ricerca "come si cuoce il pesce in umido" --capitolo "piatti di pesce" --k 3
.\.venv\Scripts\python.exe -m rag.ricerca "quanta farina per gli gnocchi" --solo-dosi --capitolo "Minestre asciutte e di magro"
.\.venv\Scripts\python.exe -m rag.valutazione --titolo "Valutazione" --confronta docs/eval-baseline.json --uscita docs/eval-ultima.md
.\.venv\Scripts\python.exe -m rag.dosi --campione 30 --seme 42   # campione per verificare contiene_dosi
docker compose down                                    # i dati restano nel volume qdrant_dati
```
- `--k` va da 1 a 20 (massimo imposto dal codice); `--capitolo` accetta il nome del capitolo con
  maiuscole qualsiasi; `--solo-dosi` tiene solo i chunk con un elenco «Ingrediente, quantità»; i
  filtri sono applicati da Qdrant durante la ricerca e si possono combinare.
- `TESTO_INDICIZZATO` (`titolo_capitolo` predefinito, oppure `solo_testo`) decide se il testo passato
  all'embedder comincia con titolo e capitolo della ricetta; cambiarlo richiede un'ingestion completa,
  che ricalcola gli embedding nella stessa collezione. Payload e risultati restano il testo originale.
- Resoconto e valutazioni: `docs/retrieval.md`.
- L'ingestion registra nei metadati della collezione modello, prefissi e dimensione del vettore:
  se la configurazione cambia modello o prefissi si ferma con un errore (usare un'altra
  `COLLEZIONE` o cancellare la collezione). Un cambio di chunking invece è ammesso: i chunk non
  più prodotti vengono cancellati.

## Server MCP di ricerca (lezione 8)

La ricerca è anche un tool MCP, `search_documents(query, top_k=5, filtro=None)`, che l'agente
di `lezione 4/assistente-laboratorio` può decidere di chiamare.

```powershell
.\.venv\Scripts\python.exe -m rag.server_mcp                  # stdio (lo avvia l'agente)
.\.venv\Scripts\python.exe -m rag.server_mcp --http --porta 8003   # HTTP per prove, endpoint /mcp
.\.venv\Scripts\python.exe -m rag.cliente_mcp "Che vino si usa per il pollo alla cacciatora?" --top-k 3
```

- Risultato: `{modalita, query_usate, passaggi[], nota}`; ogni passaggio ha `id` (`ricetta.chunk`,
  es. `208.0`, da citare tra parentesi quadre), `ricetta`, `titolo`, `capitolo`, `posizione_chunk`,
  `score` (coseno) e `testo` troncato a `RICERCA_MAX_CARATTERI`.
- `top_k` oltre `RICERCA_TOP_K_MAX` (max 20) viene ridotto e la riduzione è scritta in `nota`.
- `filtro` = nome di un capitolo (maiuscole indifferenti); valori validi nella resource
  `ricerca://filtri` e nel messaggio d'errore.
- Errori previsti (query vuota, filtro inesistente, collezione assente o incompatibile, Qdrant o
  LM Studio spenti) arrivano al modello come errori del tool con un messaggio utile, senza traceback.
- Log: una riga `ricerca esito=…` per chiamata su stderr e in `RICERCA_LOG_FILE` (`logs/`, fuori da Git).
- Specifiche e piani: `docs/specs/l8-*.md`, `docs/plans/l8-*.md`; prova reale:
  `docs/prove/l8-es1-chiamata-reale.md`.

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
I test usano un embedder finto e `QdrantClient(":memory:")`: non servono LM Studio né Qdrant.
I test sul corpus completo vengono saltati se `dati/artusi.txt` manca.
