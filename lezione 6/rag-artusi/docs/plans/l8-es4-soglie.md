# Lezione 8 · Es. 4 — Soglie di confidenza: piano

> Esecuzione: nativa. Comandi da `lezione 6/rag-artusi` (Task 4: `lezione 4/assistente-laboratorio`).

**Goal:** fasce `affidabile`/`media` sui passaggi, esclusione sotto la soglia bassa, nota per la
lista vuota, istruzioni dell'agente aggiornate e uno script di calibrazione che misura gli score reali.

**Architecture:** `rag/soglie.py` (funzioni pure), applicate in `rag/pipeline.py` dopo la fusione e
prima del reranking sul coseno migliore; `fascia` nel passaggio; `rag/calibrazione.py` riusa la
pipeline e le metriche di `rag/confronto.py`.

**Spec:** `docs/specs/l8-es4-soglie.md`

## Global Constraints
- `SOGLIA_ALTA=0.6`, `SOGLIA_BASSA=0.3` (partenza), `SOGLIE_ATTIVE=true`; `0 ≤ bassa ≤ alta ≤ 1`.
- `score ≥ alta` → `affidabile`; `bassa ≤ score < alta` → `media`; `< bassa` → escluso (mai inviato). Uguale = fascia superiore.
- Soglie disattivate → `fascia: "non_valutata"`, nessuna esclusione.
- Valori finali solo da score misurati e con l'approvazione dell'utente.

## Review Focus
1. Score negativi (coseno < 0) → esclusi senza errori (Task 1).
2. `alta == bassa` → nessuna fascia media, nessun errore (Task 1).
3. Esclusi tutti con reranking attivo → nessuna chiamata all'LLM (Task 2).
4. Score arrotondato a 3 decimali nel risultato ma fascia calcolata sul valore pieno (0,5999 → media anche se mostra 0.6) — documentato nel passaggio (Task 2).
5. Soglie su `riscrittura` con il coseno migliore che viene da una query riscritta (Task 2).

---

### Task 1: configurazione e funzioni delle soglie
**Files:** Modify `rag/config.py`, `.env.example`; Create `rag/soglie.py`; Test `tests/test_soglie.py`, `tests/test_config.py`.
**Produces:** `Config.soglia_alta: float = 0.6`, `Config.soglia_bassa: float = 0.3`, `Config.soglie_attive: bool = True`; `fascia(score: float, alta: float, bassa: float) -> str | None`; `applica(candidati: list[Candidato], alta, bassa) -> tuple[list[Candidato], int]` (imposta `Candidato.fascia`); `nota_esclusi(esclusi: int, rimasti: int, bassa: float) -> str | None`.
- [ ] Test: 0,75/0,45/0,10 → affidabile/media/escluso; 0,6 → affidabile; 0,3 → media; score negativo; alta == bassa; note (tutti esclusi / parziale / nessuno); config non valida.
- [ ] Commit `feat(ricerca): fasce di confidenza sullo score`.

### Task 2: soglie nella pipeline e nel risultato
**Files:** Modify `rag/avanzata.py` (`Candidato.fascia: str = "non_valutata"`), `rag/pipeline.py` (`soglie: tuple[float, float] | None` sovrascrivibile per la calibrazione), `rag/risultati.py` (`passaggio` da `Candidato`, chiave `fascia`), `rag/server_mcp.py` (riga di log `esclusi_soglia=`); Test `tests/test_pipeline.py`, `tests/test_server_mcp.py`.
- [ ] Test con ricerca finta a score preparati: fasce nel risultato MCP; tutti sotto → `passaggi: []` + nota; escluso assente dal prompt del reranking; riscrittura con coseno migliore da una query diversa; soglie disattivate → `non_valutata`.
- [ ] Commit `feat(mcp): soglie di confidenza nel risultato della ricerca`.

### Task 3: calibrazione
**Files:** Create `rag/calibrazione.py`; Test `tests/test_calibrazione.py`.
**Produces:** `riga_score(domanda, esito) -> dict`; `riepilogo(righe) -> dict` (min/mediana/max del top-1 con e senza risposta, score della fonte attesa, sovrapposizione); `tabella_score(righe) -> str`; confronto con/senza soglie per `base` ed `entrambe` (`--configurazioni`) con le metriche di `rag.confronto`; `main()` (`--domande --k --alta --bassa --uscita`).
- [ ] Test su esiti finti; commit `feat(valutazione): calibrazione delle soglie`.
- [ ] Calibrazione reale → `docs/calibrazione-l8.md` + `.json`; **sosta**: proporre i valori all'utente con la tabella.

### Task 4: agente e tracce
**Files:** Modify `lezione 4/assistente-laboratorio/src/assistente/grafo.py` (`REGOLE_PASSAGGI` con fascia media → «da verificare sulla fonte» e lista vuota), `prove_rag.py` (`--serie soglie`: 3 casi affidabile / da verificare / senza risposta); Test `tests/test_rag_agente.py`, `tests/test_prove_rag.py`.
- [ ] Commit `feat(agente): istruzioni sulle fasce di confidenza`.
- [ ] Dopo l'ok sui valori: default in `.env.example`, tracce reali, `docs/rag-agente.md`.
