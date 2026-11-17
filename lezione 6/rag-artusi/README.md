# RAG sull'Artusi — ingestion e ricerca

Pipeline di *retrieval* sul ricettario di Pellegrino Artusi, *La scienza in cucina e l'arte di
mangiar bene* (Project Gutenberg n. 59047). Nessun modello generativo: solo embedding (LM Studio,
`nomic-embed-text-v1.5`) e ricerca in Qdrant. Specifica: `docs/specs/pipeline-rag.md`;
piano: `docs/plans/pipeline-rag.md`.

## Che cosa viene indicizzato
- Le **790 ricette** numerate, ciascuna con numero, titolo e uno dei **23 capitoli**.
- Chunk per paragrafi (default 1200 caratteri, overlap 200); le ricette brevi sono un chunk solo.
- Payload di ogni punto: `documento_id`, `numero`, `titolo`, `capitolo`, `posizione` (indice del
  chunk nella ricetta), `testo`, `fonte`.

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
Da verificare con i servizi accesi (Fase 2):
```powershell
docker compose up -d                                   # Qdrant su http://localhost:6333
.\.venv\Scripts\python.exe -m rag.ingestion            # idempotente: rieseguibile
.\.venv\Scripts\python.exe -m rag.ricerca "Che vino si usa per il pollo alla cacciatora?" --k 3
.\.venv\Scripts\python.exe -m rag.ricerca "come si cuoce il pesce" --capitolo "Piatti di pesce" --k 5
docker compose down                                    # i dati restano nel volume qdrant_dati
```
- `--k` va da 1 a 20 (massimo imposto dal codice); `--capitolo` accetta il nome del capitolo con
  maiuscole qualsiasi; il filtro è applicato da Qdrant durante la ricerca.
- L'ingestion registra nei metadati della collezione modello, prefissi e dimensione del vettore:
  se la configurazione cambia modello o prefissi si ferma con un errore (usare un'altra
  `COLLEZIONE` o cancellare la collezione). Un cambio di chunking invece è ammesso: i chunk non
  più prodotti vengono cancellati.

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
I test usano un embedder finto e `QdrantClient(":memory:")`: non servono LM Studio né Qdrant.
I test sul corpus completo vengono saltati se `dati/artusi.txt` manca.
