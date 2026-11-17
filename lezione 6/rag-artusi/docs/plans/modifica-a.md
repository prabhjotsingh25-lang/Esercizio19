# Modifica A — Piano di implementazione (Fase 3)

> **Per chi esegue:** superpowers:executing-plans, un task alla volta, test prima del codice,
> un commit per task.

**Obiettivo:** campo booleano `contiene_dosi` nel payload, con indice, aggiornato sui punti esistenti
senza ricalcolare gli embedding, e filtro `--solo-dosi` combinabile con `--capitolo`.

**Architettura:** nuova funzione pura in `rag/dosi.py`; `crea_chunk` la usa per il payload;
`indice` gestisce l'indice `bool` e l'aggiornamento con `set_payload`; `ingestion --solo-payload`
orchestra l'aggiornamento; `cerca` aggiunge la condizione al `Filter` nativo.

**Specifica:** `docs/specs/modifica-a.md` (approvata il 2026-11-17), più `docs/specs/pipeline-rag.md`.

## Vincoli globali
- Valgono tutti quelli di `docs/plans/pipeline-rag.md` (comandi da `lezione 6/rag-artusi/`,
  `.\.venv\Scripts\python.exe -m pytest -v`, servizi spenti nei test, Conventional Commits).
- Mai ricalcolare embedding né ricreare la collezione per scrivere il campo.
- Filtri solo come `Filter(must=[...])` passato a `query_points`.

## Attenzione in revisione
1. **Collezione creata prima di A** senza indice `contiene_dosi` → l'ingestion completa e
   `--solo-payload` lo creano (Task A2/A3).
2. **`--solo-payload` con chunking cambiato** → errore senza scritture (Task A3).
3. **`--solo-dosi` con un capitolo senza chunk con dosi** → lista vuota e messaggio «Nessun
   risultato.», non errore (Task A4).
4. **`--solo-payload` su collezione assente** → errore «esegui prima l'ingestion completa» (Task A3).
5. **Testo con voci di dose solo nell'overlap** → conta come il resto del testo (Task A1).

---

### Task A1: regola `contiene_dosi` e campione di verifica
**File:** crea `rag/dosi.py`, `tests/test_dosi.py`.
**Produce:** `voci_dose(testo: str) -> list[str]` (i segmenti riconosciuti),
`contiene_dosi(testo: str) -> bool` (= `len(voci_dose(testo)) >= 2`),
`campione(chunk: list[Chunk], n: int, seme: int) -> tuple[list[Chunk], list[Chunk]]` (positivi,
negativi, `random.Random(seme).sample`), `main(argv)` per `python -m rag.dosi --campione 30 --seme 42`
che stampa per ogni chunk ricetta, titolo, posizione, valore e righe rilevanti (voci trovate per i
positivi; righe ≤ 100 caratteri con cifre o parole di quantità per i negativi).
- [ ] Test (falliscono): positivi 89 («Patate grosse e gialle, grammi 400.\nFarina di grano, grammi
  150.»), 141 (una riga con tre voci → 3 voci), 617, 626, «Burro, quanto una noce.\nSale, quanto
  basta.»; negativi 208 (prosa con «mezzo bicchiere»), 305 (elenco in prosa), «se no, un pizzico di
  funghi secchi.», un solo ingrediente, un paragrafo di prosa lungo > 100 con «grammi 50»; corpus
  reale (skipif): chunk 0 della 89 vero, chunk della 208 falso; `campione` deterministico con lo
  stesso seme e disgiunto.
- [ ] `pytest tests/test_dosi.py` → FAIL; implementare; → PASS; suite intera → PASS.
- [ ] Commit `feat(dosi): regola contiene_dosi e campione di verifica`.

### Task A2: payload e indici
**File:** modifica `rag/chunking.py`, `rag/indice.py`, `tests/test_chunking.py`, `tests/test_indice.py`.
**Produce:** payload con 8 chiavi (`contiene_dosi` aggiunto); `INDICI = {"capitolo": KEYWORD,
"contiene_dosi": BOOL}`; `assicura_indici(client, nome) -> list[str]` (crea gli indici che mancano
nel `payload_schema`, restituisce quelli creati); `crea_collezione` usa `assicura_indici`.
- [ ] Test: `test_crea_chunk_payload` aggiornato (8 chiavi, `contiene_dosi` booleano coerente con
  `contiene_dosi(testo)`); `test_crea_collezione` → spia vede `capitolo` KEYWORD e `contiene_dosi`
  BOOL; `test_assicura_indici` (spia: richiede solo i mancanti).
- [ ] FAIL → implementare → PASS; l'ingestion completa chiama `assicura_indici` anche su una
  collezione esistente (test in `test_ingestion.py`).
- [ ] Commit `feat(indice): campo contiene_dosi nel payload e indice bool`.

### Task A3: `--solo-payload` senza ricalcolo degli embedding
**File:** modifica `rag/indice.py`, `rag/ingestion.py`, `tests/test_ingestion.py`.
**Produce:** in `indice`: `aggiorna_campo(client, nome, campo: str, valori: dict[str, bool]) -> int`
(una `set_payload` per valore, a lotti di 1000 ID); `testi_salvati(client, nome) -> dict[str, str]`
(ID → `testo`, con scroll). In `ingestion`: `aggiorna_payload(config, client, ricette=None) ->
RapportoPayload(aggiornati, con_dosi, punti)`; `main(["--solo-payload"])` non crea l'embedder.
- [ ] Test: dopo un'ingestion si toglie `contiene_dosi` con `delete_payload`; `aggiorna_payload` →
  ogni punto ha il valore atteso, vettori identici (`retrieve(..., with_vectors=True)` prima e dopo),
  `EmbedderFinto.chiamate == 0` anche via `main(["--solo-payload"])` (embedder sostituito con uno che
  fallisce se chiamato), punti invariati; chunk non coincidenti (dimensione 300) → `ErroreCollezione`
  e nessun punto modificato; collezione assente → `ErroreCollezione` con «ingestion completa».
- [ ] FAIL → implementare → PASS.
- [ ] Commit `feat(ingestion): aggiornamento del payload senza ricalcolare gli embedding`.

### Task A4: filtro `--solo-dosi`
**File:** modifica `rag/ricerca.py`, `tests/test_ricerca.py`.
**Produce:** `cerca(domanda, k=5, capitolo=None, solo_dosi=False, *, client, embedder, config)`;
`costruisci_filtro(capitolo: str | None, solo_dosi: bool) -> Filter | None`; CLI `--solo-dosi`;
nella stampa « | dosi» quando vero.
- [ ] Test richiesti dall'utente:
  1. `test_solo_dosi_tutti_veri`: `solo_dosi=True, k=20` → tutti `contiene_dosi` vero (letto dal
     payload del punto), `len <= 20`; e con `k=3` → `len <= 3`.
  2. `test_solo_dosi_e_capitolo`: `solo_dosi=True, capitolo="Pasticceria"` (corpus reale; fixture:
     capitolo del fixture) → tutti veri e di quel capitolo.
  3. `test_filtro_nativo_dosi`: spia su `query_points` → `query_filter == Filter(must=[capitolo,
     contiene_dosi])` e `limit == k`; nessun risultato scartato dopo (len risultati == len punti
     restituiti dalla spia).
  Più: `Risultato` ha `contiene_dosi`; CLI con `--solo-dosi --capitolo` stampa solo righe con
  «dosi»; capitolo senza dosi → «Nessun risultato.».
- [ ] FAIL → implementare → PASS.
- [ ] Commit `feat(ricerca): filtro --solo-dosi combinabile con --capitolo`.

### Task A5: valutazione con filtro, JSON e confronto
**File:** modifica `rag/valutazione.py`, `tests/test_valutazione.py`.
**Produce:** opzioni `--solo-dosi`, `--json <file>` (righe serializzate), `--confronta <file.json>`
(aggiunge alla tabella le colonne «Posizione baseline» e «Variazione»: `=`, `↑n`, `↓n`, `persa`,
`trovata`); funzioni `righe_da_json(path)`, `tabella_confronto(righe, base) -> str`.
- [ ] Test sulle funzioni pure (serializzazione andata e ritorno; simboli di variazione).
- [ ] FAIL → implementare → PASS.
- [ ] Commit `feat(valutazione): filtro solo-dosi, salvataggio JSON e confronto`.

### Task A6: esecuzione reale e documenti (servizi accesi, già confermati dall'utente)
- [ ] `python -m rag.valutazione --titolo "Valutazione di partenza (baseline)" --json
  docs/eval-baseline.json` prima dell'aggiornamento (vettori invariati), ripristinando la sezione
  sulle ingestion di `docs/eval-baseline.md`.
- [ ] `python -m rag.dosi --campione 30 --seme 42`: lettura e giudizio di ogni chunk →
  `docs/verifica-dosi.md` (criterio: ≤ 1 falso positivo su 30).
- [ ] Conteggio dei punti e copia dei vettori di 20 punti; `python -m rag.ingestion --solo-payload`;
  di nuovo conteggio (1106) e confronto dei vettori (identici); indice `contiene_dosi` presente.
- [ ] Valutazione senza filtro (`--confronta docs/eval-baseline.json`) e con `--solo-dosi` →
  `docs/eval-dopo-a.md` con le due tabelle, il confronto e il commento.
- [ ] Commit `docs(eval): verifica della regola sulle dosi e valutazione dopo la modifica A`.
