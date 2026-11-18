# Lezione 8 · Es. 2 — Aggancio all'agente: piano

> Esecuzione: nativa. Codice in `lezione 4/assistente-laboratorio/` (comandi da quella cartella).

**Goal:** l'agente vede `search_documents` (server stdio dichiarato in `SERVER_MCP_FILE`) accanto agli
strumenti della variante, segue le regole RAG del prompt e l'host registra il controllo delle citazioni.

**Architecture:** `server_esterni.py` legge il file `mcpServers`, scopre i tool (`tools/list`) e li
espone come `StructuredTool` sincroni; `citazioni.py` estrae id ricevuti e citati; `agente.py` logga
il controllo a fine turno; `grafo.py` aggiunge il blocco di regole; `prove_rag.py` salva le 4 tracce.

**Tech Stack:** fastmcp 4.1.6 (`StdioTransport`), langchain-core 1.7, langgraph 1.2.

**Spec:** `docs/specs/l8-es2-aggancio-agente.md` (in `lezione 6/rag-artusi/`)

## Global Constraints
- Nessun import da `rag-artusi`; nei test un server di ricerca finto FastMCP in memoria.
- `SERVER_MCP_FILE` facoltativa: assente/vuota = comportamento identico a prima (prompt, router, strumenti).
- Con `SERVER_MCP_FILE` serve `AMBITO_RICERCA` (obbligatoria), aggiunta all'ambito del router.
- Timeout per server: campo `timeout` della voce, default 120 s; `keep_alive=False`; stderr del server in `logs/ricerca-stdio.log` (`logs/` fuori da Git).
- Il controllo delle citazioni non modifica la risposta; WARNING se ci sono citazioni sconosciute, INFO altrimenti.
- Tutti i test esistenti restano verdi; Compose: `SERVER_MCP_FILE: ""` per `agente` e `assistente`.

## Review Focus
1. Risposta con link Markdown `[testo](url)` o `[nota]` → non sono citazioni (Task 2).
2. Citazioni multiple in una parentesi `[89.0, 208.0]` e ripetute due volte → contate una volta (Task 2).
3. Risultato del tool «Errore: …» (non JSON) → ignorato dal controllo, `ricerche` non incrementate (Task 2).
4. Percorsi con spazi («lezione 6») nel file dei server → risolti rispetto al file (Task 1).
5. Revisore che fa riprovare il modello: gli id ricevuti si contano su tutto il turno (Task 3, ricerca prima della revisione).

---

### Task 1: file dei server e discovery
**Files:** Create `src/assistente/server_esterni.py`, `server_mcp.example.json`; Modify `src/assistente/config.py`, `.env.example`, `.gitignore` (`server_mcp.json`, `logs/`); Test `tests/test_server_esterni.py`, `tests/test_config.py`.
**Produces:**
- `Configurazione.server_mcp_file: str | None = None`, `Configurazione.ambito_ricerca: str = ""` (obbligatoria se il file è impostato: `ErroreConfigurazione` con «AMBITO_RICERCA»).
- `class ErroreServerMCP(Exception)`; `@dataclass(frozen=True) ServerMCP(nome: str, command: str | None, args: tuple[str, ...], cwd: str | None, url: str | None, timeout: int = 120)`.
- `leggi_server(percorso: str) -> list[ServerMCP]` (percorsi relativi di `command` con separatori e di `cwd` risolti rispetto al file; errori: file assente, JSON non valido, `mcpServers` mancante/vuoto, voce senza `command` né `url`, `timeout` non intero positivo).
- `strumenti_server(server: ServerMCP, crea_client: Callable[[], Any] | None = None) -> list[BaseTool]` (tools/list → `StructuredTool` con nome, descrizione e `args_schema` = schema JSON del server; chiamata con `call_tool(..., timeout=server.timeout, raise_on_error=False)`; risultato = testo; `is_error` → «Errore: <testo>»; eccezioni → «Errore: server MCP "<nome>" non raggiungibile (<Tipo>).»; discovery fallita → `ErroreServerMCP`).
- `strumenti_esterni(percorso: str, gia_presenti: list[str], crea_client_per: Callable[[ServerMCP], Callable] | None = None) -> list[BaseTool]` (nome duplicato → `ErroreServerMCP`).
- [ ] Test (server finto in memoria con `search_documents` che restituisce un dict preparato e un tool che solleva `ToolError`): discovery e schema; chiamata → testo JSON; errore del tool → «Errore: …»; client che fallisce in chiamata → «non raggiungibile»; file assente / JSON rotto / voce senza comando / timeout 0; percorsi relativi con spazi risolti; nome duplicato.
- [ ] Implementa, verde, commit `feat(mcp): server MCP esterni da file di configurazione`.

### Task 2: controllo delle citazioni
**Files:** Create `src/assistente/citazioni.py`; Test `tests/test_citazioni.py`.
**Produces:** `@dataclass(frozen=True) ControlloCitazioni(verificate: list[str], sconosciute: list[str], ricerche: int, passaggi_ricevuti: int)`; `citazioni(testo: str) -> list[str]` (ordine di comparsa, senza ripetizioni; token numerici `^\d+(\.\d+)*$` tra parentesi quadre, anche separati da `,`/`;`); `id_ricevuti(risultati: list[str]) -> tuple[list[str], int]`; `controlla(risposta: str, risultati: list[str]) -> ControlloCitazioni`; `riga_log(c: ControlloCitazioni) -> str` = `citazioni verificate=89.0,89.1 sconosciute=- ricerche=1 passaggi_ricevuti=5`.
- [ ] Test: valida, sconosciuta `[999.0]`, `[89]` sconosciuta, nessuna, multiple, link Markdown, risultato non JSON, JSON senza `passaggi`.
- [ ] Implementa, verde, commit `feat(agente): controllo delle citazioni sui passaggi ricevuti`.

### Task 3: agente — regole, ambito, log a fine turno
**Files:** Modify `src/assistente/grafo.py` (`REGOLE_PASSAGGI`, `messaggio_di_sistema(..., regole: str = "")`, `costruisci_grafo(..., regole: str = "")`), `src/assistente/agente.py` (`EsitoTurno.citazioni: ControlloCitazioni | None = None`, log in `turno`, `grafo_da_configurazione` con strumenti esterni, ambito esteso, regole), `src/assistente/cli.py` e `servizio_agente.py` (`ErroreServerMCP` → messaggio e codice 2), `compose.yaml`; Test `tests/test_rag_agente.py`.
- [ ] Test con `ModelloFinto` e server finto: il modello chiede `search_documents` → `ToolMessage` con il JSON; citazione valida; sconosciuta (WARNING, risposta invariata); nessuna citazione; prompt con `REGOLE_PASSAGGI` solo se `regole` passato (e identico a prima senza); ricerche infinite → `MESSAGGIO_LIMITE`; ambito del router = ambito + ambito_ricerca solo con file.
- [ ] Implementa, suite completa verde, commit `feat(agente): ricerca MCP accanto agli strumenti e regole sui passaggi`.

### Task 4: script delle tracce e prova reale
**Files:** Create `src/assistente/prove_rag.py` (`python -m assistente.prove_rag --uscita DIR`), `server_mcp.json` locale (fuori da Git), aggiorna `.env` locale (`SERVER_MCP_FILE`, `AMBITO_RICERCA`), README; Test `tests/test_prove_rag.py`.
**Produces:** `CASI` (4 domande della spec con regole attese), `valuta_caso(caso, esito) -> list[str]` (scostamenti dall'atteso), `traccia(caso, esito, log, durata) -> dict`, `markdown(tracce) -> str`.
- [ ] Test su esiti finti: ogni regola atteso/non atteso; JSON e Markdown scritti.
- [ ] Implementa, verde, commit `feat(agente): script delle tracce dei quattro casi RAG`.
- [ ] Prova reale → `lezione 6/rag-artusi/docs/prove/l8-es2-tracce/` (JSON + `tracce.md`), commit `docs(l8): tracce reali dei quattro casi`.
