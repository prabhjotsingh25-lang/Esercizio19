# Lezione 8 · Es. 3 — Riscrittura, scomposizione e reranking: piano

> Esecuzione: nativa. Comandi da `lezione 6/rag-artusi`.

**Goal:** modalità `base | riscrittura | reranking | entrambe` scelta da `MODALITA_RICERCA`, con
ripieghi segnalati, e uno script di confronto riproducibile con le metriche della spec.

**Architecture:** `rag/llm.py` (chiamate JSON a LM Studio), `rag/avanzata.py` (riscrittura, RRF,
reranking: funzioni pure + LLM iniettabile), `rag/pipeline.py` (una pipeline per tutte le modalità,
usata dal server e dal confronto), `rag/confronto.py` (metriche e rapporto).

**Tech Stack:** httpx (già presente), PyYAML, fastmcp.

**Spec:** `docs/specs/l8-es3-riscrittura-reranking.md`

## Global Constraints
- Lo schema del tool non cambia: test parametrizzato sulle 4 modalità.
- Config (`.env.example`): `MODALITA_RICERCA=base`, `MODELLO_CHAT=google/gemma-4-e2b`, `LLM_TEMPERATURA=0`, `LLM_SEED=42`, `LLM_REASONING_EFFORT=none`, `LLM_MAX_TOKENS=300`, `LLM_TIMEOUT=60`, `RISCRITTURA_MAX_QUERY=3` (1..3), `CANDIDATI_PER_QUERY=10` (1..20), `RERANK_MAX_CANDIDATI=10` (1..20), `RERANK_MAX_CARATTERI=400`, `RRF_K=60`.
- Ripieghi: codici `riscrittura_json`, `riscrittura_vuota`, `riscrittura_servizio`, `riscrittura_troppe_query`, `reranking_json`, `reranking_servizio`, `reranking_id_sconosciuti`, `reranking_id_duplicati`; mai un errore del tool per colpa dell'LLM.
- Il testo grezzo dell'LLM non va mai nei messaggi al modello; nel log al massimo 200 caratteri su una riga.
- Lo `score` mostrato resta il coseno (migliore tra le query).

## Review Focus
1. LLM che restituisce JSON valido ma con tipi sbagliati (`{"query": "gnocchi"}` stringa invece di lista) → ripiego `riscrittura_json` (Task 2).
2. LLM che risponde con testo prima/dopo il JSON o dentro un blocco ```json → trattato come JSON non valido (nessun parsing «furbo») (Task 1).
3. Query generate uguali all'originale a meno di maiuscole/punteggiatura finale → scartate (Task 2).
4. Reranking con 0 candidati (collezione filtrata vuota) → nessuna chiamata all'LLM, lista vuota (Task 3).
5. HTTP 400 di LM Studio per `reasoning_effort` non supportato → ripiego `*_servizio` e una riga di log con lo status (Task 1).

---

### Task 1: client LLM JSON
**Files:** Create `rag/llm.py`; Modify `rag/config.py`, `.env.example`; Test `tests/test_llm.py`, `tests/test_config.py`.
**Produces:** campi `Config` della lista sopra (con default); `class ErroreLLM(Exception)` (servizio: connessione, timeout, HTTP ≠ 200); `class RispostaNonValida(Exception)` (contenuto non JSON o non oggetto); `class LLM(Protocol): chiamate: int; def json(self, sistema: str, utente: str, schema: dict, nome: str) -> dict`; `LLMLMStudio(config: Config, client: httpx.Client | None = None)` che invia `model`, `messages`, `temperature`, `max_tokens`, `response_format={"type": "json_schema", "json_schema": {"name": nome, "strict": True, "schema": schema}}`, `seed` e `reasoning_effort` solo se configurati.
- [ ] Test con `httpx.MockTransport`: corpo della richiesta; JSON valido → dict; testo non JSON / blocco ```json / lista → `RispostaNonValida`; HTTP 400 e connessione rifiutata → `ErroreLLM` con status; contatore `chiamate`. Config: default, valori non validi.
- [ ] Commit `feat(llm): chiamate JSON a LM Studio con output vincolato`.

### Task 2: riscrittura e RRF
**Files:** Create `rag/avanzata.py`; Test `tests/test_avanzata.py`, `tests/finti.py` (`LLMFinto(risposte: list[dict | Exception])`, registra `richieste`).
**Produces:** `@dataclass(frozen=True) Ripiego(codice: str, descrizione: str)`; `SCHEMA_RISCRITTURA(max_query) -> dict`; `riscrivi(domanda: str, llm: LLM, max_query: int) -> tuple[list[str], list[Ripiego]]` (originale prima, dedup casefold senza punteggiatura finale, vuote scartate, oltre `max_query` troncate con ripiego); `@dataclass Candidato(id: str, risultato: Risultato, score: float, score_rrf: float = 0.0)`; `fondi(liste: list[list[Risultato]], rrf_k: int) -> list[Candidato]` (score = coseno migliore; ordine per score_rrf decrescente, poi score, poi id).
- [ ] Test: JSON non valido / tipo sbagliato / servizio giù / lista vuota → solo originale + ripiego col codice; duplicati dell'originale tolti; 5 query → 3 + `riscrittura_troppe_query`; domanda composta → 3 query_usate; RRF numerico (1° e 3° = 1/61 + 1/63), niente duplicati, parità.
- [ ] Commit `feat(ricerca): riscrittura delle domande e fusione RRF`.

### Task 3: reranking listwise
**Files:** Modify `rag/avanzata.py`; Test `tests/test_avanzata.py`.
**Produces:** `SCHEMA_RERANKING(ids: list[str]) -> dict` (enum degli id, `maxItems`); `prompt_reranking(domanda, candidati, max_caratteri) -> str`; `riordina(domanda: str, candidati: list[Candidato], llm: LLM, max_candidati: int, max_caratteri: int) -> tuple[list[Candidato] | None, list[Ripiego]]` (None = ripiego sull'ordine ricevuto; [] = astensione).
- [ ] Test: tetto ai candidati e testo troncato nel prompt; id inventati scartati; tutti inventati → None + `reranking_id_sconosciuti`; duplicati → uno + ripiego; lista vuota → []; JSON non valido / servizio → None; 0 candidati → nessuna chiamata.
- [ ] Commit `feat(ricerca): reranking listwise con LLM`.

### Task 4: pipeline e server
**Files:** Create `rag/pipeline.py`; Modify `rag/server_mcp.py` (usa la pipeline; `Servizi.llm`; riga di log con `ripieghi=` e `llm=`), `tests/test_server_mcp.py`; Test `tests/test_pipeline.py`.
**Produces:** `@dataclass EsitoPipeline(modalita, query_usate, risultati: list[Candidato], note: list[str], ripieghi: list[Ripiego], chiamate_llm: int)`; `esegui(domanda: str, top_k: int, capitolo: str | None, *, client, embedder, llm, config, modalita: str | None = None) -> EsitoPipeline`.
- [ ] Test: le 4 modalità con LLM finto (query_usate, numero di chiamate 0/1/1/2); embedding giù → `ErroreEmbedding` (diventa errore del tool); LLM giù → ripieghi, non errore; schema del tool identico nelle 4 modalità; nota con il ripiego nel risultato MCP.
- [ ] Commit `feat(mcp): modalità di ricerca da configurazione`.

### Task 5: confronto
**Files:** Create `rag/confronto.py`, `eval/domande_l8.yaml`; Test `tests/test_confronto.py`.
**Produces:** `DomandaL8(testo, tipo, attese, parti, verificare, nota)`; `carica_domande_l8(percorso) -> list[DomandaL8]`; `misura(domanda, esito, latenza_ms) -> Misura`; `metriche(misure, k) -> dict`; `variazioni(base, altra) -> tuple[list[str], list[str]]`; `rapporto(...) -> str`; `main()` (`--domande --k --uscita --json --configurazioni`).
- [ ] Test su pipeline finte: ogni metrica calcolata su casi preparati (fonte nei primi k, MRR, copertura, astensioni corrette/errate, chiamate, latenze, ripieghi), migliorati/peggiorati, tabella.
- [ ] Commit `feat(valutazione): confronto delle quattro modalità di ricerca`.
- [ ] **Sosta**: mostrare `eval/domande_l8.yaml` all'utente prima del confronto reale.
- [ ] Confronto reale → `docs/confronto-l8.md` + `.json`, commit `docs(l8): confronto reale delle quattro configurazioni`.
