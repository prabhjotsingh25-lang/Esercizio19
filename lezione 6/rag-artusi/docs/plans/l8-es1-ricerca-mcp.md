# Lezione 8 · Es. 1 — Server MCP di ricerca: piano

> Esecuzione: nativa (Claude implementa task per task, review finale sull'intero branch).

**Goal:** esporre `rag.ricerca.cerca` come tool FastMCP `search_documents` con risultato strutturato,
errori utili al modello, una riga di log per chiamata e la resource `ricerca://filtri`.

**Architecture:** funzioni pure di formato in `rag/risultati.py`; `rag/server_mcp.py` con
`esegui_ricerca` (logica + mappatura errori) e `crea_server` (registrazione FastMCP) con servizi
iniettabili; `rag/cliente_mcp.py` per la chiamata reale via stdio.

**Tech Stack:** Python 3.11+, fastmcp 4.1.6, qdrant-client 1.20, pytest.

**Spec:** `docs/specs/l8-es1-ricerca-mcp.md`

## Global Constraints
- Schema del tool: `search_documents(query: str, top_k: int = 5, filtro: str | None = None)`, identico in ogni configurazione.
- Valori da config: `RICERCA_TOP_K_MAX` (default 10, intero 1..20), `RICERCA_MAX_CARATTERI` (default 800, > 0), `RICERCA_LOG_FILE` (vuota = solo stderr).
- Log solo su stderr/file, mai su stdout; mai «Traceback» né nel log né nei messaggi.
- Test senza servizi: `QdrantClient(":memory:")`, `EmbedderFinto`, `fastmcp.Client(server)` in memoria.
- Conventional Commits in italiano, un commit per task.

## Review Focus
1. Testo del passaggio con caratteri non ASCII (accenti, «»): il JSON resta leggibile → test in Task 2 su `testo` con «è».
2. `filtro` con spazi e maiuscole diverse («  minestre IN brodo ») → accettato (Task 3).
3. `filtro=""` (stringa vuota) → trattato come nessun filtro, non errore (Task 3).
4. FastMCP che scrive da sé un traceback quando il tool solleva → test sul log di tutti i logger catturati (Task 3).
5. `top_k` non intero dal modello (es. "5") → errore di validazione di FastMCP, senza traceback (Task 3).

---

### Task 1: configurazione e dipendenza
**Files:** Modify `rag/config.py`, `.env.example`, `requirements.txt`, `.gitignore` (`logs/`); Test `tests/test_config.py`.
**Produces:** `Config.ricerca_top_k_max: int = 10`, `Config.ricerca_max_caratteri: int = 800`, `Config.ricerca_log_file: str | None = None` (campi con default in coda alla dataclass).
- [ ] Test: `test_ricerca_default` (10, 800, None); `test_ricerca_top_k_max_oltre_20` → `ErroreConfigurazione` con «RICERCA_TOP_K_MAX»; `test_ricerca_max_caratteri_zero` → errore; `test_ricerca_log_file`.
- [ ] Verifica che falliscano; implementa; `pytest tests/test_config.py -q` verde.
- [ ] `fastmcp==4.1.6` in `requirements.txt`; commit `feat(config): parametri del server di ricerca MCP`.

### Task 2: formato dei passaggi e del risultato
**Files:** Create `rag/risultati.py`; Test `tests/test_risultati.py`.
**Produces:**
- `id_passaggio(numero: int, posizione: int) -> str` → `"89.1"`
- `tronca(testo: str, massimo: int) -> str` (spazi normalizzati, «…» finale se tagliato; lunghezza totale ≤ massimo)
- `limita_top_k(top_k: int, massimo: int) -> tuple[int, str | None]` (nota «top_k ridotto da 50 a 10 (massimo consentito)» / «top_k portato da 0 a 1 (minimo consentito)»)
- `passaggio(r: Risultato, max_caratteri: int) -> dict` con chiavi esatte `id, ricetta, titolo, capitolo, posizione_chunk, score (round 3), testo`
- `componi_risultato(modalita: str, query_usate: list[str], passaggi: list[dict], note: list[str]) -> dict` → chiavi `modalita, query_usate, passaggi, nota` (`nota` = note unite da « · », "" se nessuna)
- [ ] Test con valori della spec (`id_passaggio(89,1)=="89.1"`, troncamento a 10 di un testo di 30, top_k 50→10 con nota, 0→1 con nota, 5→5 senza nota, chiavi esatte, testo con «è» invariato).
- [ ] Implementa; verde; commit `feat(ricerca): formato dei passaggi per il tool MCP`.

### Task 3: server FastMCP
**Files:** Create `rag/server_mcp.py`; Test `tests/test_server_mcp.py`.
**Interfaces:**
- `class ErroreRicerca(Exception)`: `codice: str`, messaggio per il modello.
- `@dataclass Servizi`: `client: QdrantClient`, `embedder: Embedder`, `config: Config`.
- `esegui_ricerca(servizi: Servizi, query: str, top_k: int, filtro: str | None) -> dict` — solleva `ErroreRicerca` con codici `query_vuota`, `filtro_inesistente` (messaggio con tutti i `CAPITOLI` separati da «; »), `collezione_assente` (controllo `collection_exists` prima di `cerca`), `collezione_incompatibile`, `qdrant_non_raggiungibile` (`ERRORI_QDRANT`), `embedding_non_raggiungibile` (`ErroreEmbedding`), `interno` (qualunque altra eccezione; messaggio «errore interno della ricerca»). Nota «collezione in aggiornamento…» se `formato_salvato == IN_AGGIORNAMENTO`. Modalità fissa `"base"` in questo esercizio.
- `DESCRIZIONE_TOOL: str` (testo della spec).
- `crea_server(servizi: Servizi | Callable[[], Servizi]) -> FastMCP` — tool `search_documents` (solleva `ToolError(messaggio)` da `ErroreRicerca`) e resource `ricerca://filtri` → `{"campo": "capitolo", "valori": [...CAPITOLI]}`; una riga di log `ricerca esito=… modalita=… query="…" top_k=… filtro=… passaggi=N ids=… nota="…" ms=…` per chiamata sul logger `rag.server_mcp`; logger di fastmcp che non deve emettere traceback (se lo fa: filtro sul logger che toglie `exc_info`).
- `configura_log(config: Config) -> None` (stderr + file opzionale), `main(argv) -> int` (`--http`, `--porta`).
- [ ] Test in memoria: discovery (nome, `required == ["query"]`, default 5 e null, descrizione con «parentesi quadre» e «vuota»); risultato con chiavi e id; top_k 50 → ≤10 passaggi + «ridotto»; filtro valido normalizzato; filtro `""` = nessun filtro; un test per errore (6) con `is_error` e messaggio; resource a servizi finti che falliscono su tutto; caplog: una riga `ricerca ` per chiamata e nessun «Traceback» (anche per `interno`); `top_k="cinque"` → errore senza traceback.
- [ ] Implementa; `pytest -q` verde (tutta la suite); commit `feat(mcp): server di ricerca search_documents`.

### Task 4: cliente stdio, README e prova reale
**Files:** Create `rag/cliente_mcp.py` (`python -m rag.cliente_mcp "domanda" [--top-k N] [--filtro X]`: avvia `python -m rag.server_mcp` via `StdioTransport`, stampa discovery e risultato JSON), Modify `README.md`; Test `tests/test_cliente_mcp.py` (parsing argomenti e formattazione con risultato finto).
- [ ] Test, implementa, verde, commit `feat(mcp): cliente stdio per la prova reale`.
- [ ] Prova reale (Qdrant con `docker compose up -d`, LM Studio acceso): una domanda, una con filtro, una con filtro errato; output salvato in `docs/prove/l8-es1-chiamata-reale.md`; commit `docs(l8): prova reale del server di ricerca`.
