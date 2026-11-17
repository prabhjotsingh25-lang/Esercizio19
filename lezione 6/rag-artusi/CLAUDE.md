# RAG sull'Artusi

Pipeline RAG di ingestion e ricerca sul corpus `dati/artusi.txt` (Pellegrino Artusi,
*La scienza in cucina e l'arte di mangiar bene*, Project Gutenberg n. 59047: 790 ricette
numerate nel formato `7. Titolo`, 23 capitoli con titolo in maiuscolo, righe spezzate a ~70
caratteri, intestazione e licenza Gutenberg da rimuovere).
Nessun modello generativo: solo embedding e retrieval.

La cartella del progetto è `lezione 6/rag-artusi/` della repository; non leggere né modificare
le altre lezioni.

## Regole stabili
- Python 3.11+, pytest, `requirements.txt` con versioni fissate.
- Struttura: package `rag/`, test in `tests/`, specifiche in `docs/specs/`, piani in `docs/plans/`.
- Ingestion = script separato (`python -m rag.ingestion`), mai uno strumento dell'agente.
- Ricerca = funzione + CLI: `python -m rag.ricerca "domanda" --capitolo X --k 3`.
- Modello di embedding, `QDRANT_URL`, URL di LM Studio (endpoint `/v1/embeddings`; da Docker
  `host.docker.internal`) e nome della collezione solo in configurazione (`.env` + `.env.example`),
  mai nel codice. Modello di riferimento: `nomic-embed-text-v1.5`.
- Qdrant con Docker Compose (`compose.yaml`), porta 6333, volume persistente. Distanza coseno.
- Il modello di embedding è registrato nei metadati della collezione; se la configurazione lo
  cambia, l'ingestion si blocca con un errore chiaro.
- Un punto per chunk, ID stabili (uuid5 da `documento_id` + `chunk_index`), upsert, mai ID
  casuali. I chunk non più prodotti vanno eliminati.
- Payload: `documento_id`, `numero`, `titolo`, `capitolo`, `posizione` (chunk_index), `testo`,
  `fonte`. Indici sul payload per i campi filtrati.
- Chunking configurabile (strategia, dimensione, overlap); default: per paragrafi, 1200 caratteri,
  overlap 200; ricette brevi = 1 chunk.
- Ricerca: top-k con massimo imposto dal codice (k <= 20); filtro per capitolo applicato DURANTE
  la ricerca (filtro nativo Qdrant), non dopo.
- Test con embedder finto (vettori deterministici) e Qdrant in memoria (`QdrantClient(":memory:")`):
  devono passare con LM Studio e Qdrant spenti. Test su una ricetta breve e una lunga.
- `dati/` e `.env` fuori da Git (`.gitignore`). Un passo per commit, Conventional Commits.

## Metodo
- Workflow Superpowers: brainstorming → specifica → piano → implementazione con test → verifica.
- Niente codice prima dell'approvazione della specifica («approvata»); poi piano a passi piccoli,
  ognuno con test e commit.
- Le prove reali (LM Studio e Qdrant accesi) si fanno solo dopo conferma esplicita che i servizi
  sono avviati.

## Git
- Branch `feat/<nome>` creato da `dev`; merge in `dev` solo dopo l'ok. `main` non si tocca,
  push solo su richiesta.
- Conventional Commits in italiano (`feat(ingestion): ...`, `test(ricerca): ...`, `docs: ...`).
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo.
