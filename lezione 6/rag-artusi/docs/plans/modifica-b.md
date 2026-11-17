# Modifica B — Piano di implementazione (Fase 4)

> **Per chi esegue:** superpowers:executing-plans, un task alla volta, test prima del codice,
> un commit per task.

**Obiettivo:** il testo passato all'embedder diventa `PREFISSO_DOCUMENTO + "Titolo: …\nCapitolo: …\n\n"
+ testo`; payload e risultati restano il testo originale; ricalcolo nella stessa collezione.

**Specifica:** `docs/specs/modifica-b.md` (approvata il 2026-11-17), più le specifiche precedenti.

## Vincoli globali
- Valgono quelli di `docs/plans/pipeline-rag.md` e `docs/plans/modifica-a.md`.
- Mai `create_collection`/`delete_collection` su una collezione esistente; stessi ID, upsert.
- La query resta `PREFISSO_QUERY + domanda`.

## Attenzione in revisione
1. **Collezione creata prima di B** senza la chiave `testo_indicizzato` → trattata come `solo_testo`,
   non bloccata (Task B2).
2. **Interruzione a metà del ricalcolo** → metadato `in_aggiornamento`, riparato dalla prossima
   ingestion; la ricerca avvisa (Task B2, B3).
3. **`TESTO_INDICIZZATO` cambiato senza ricalcolo** (ricerca o `--solo-payload`) → nessuna modifica a
   vettori, payload o metadati (Task B2).
4. **Titolo con caratteri speciali** («Gâteau à la noisette») → passato così com'è (Task B1).
5. **`--solo-payload` dopo B** → confronta il `testo` originale, quindi continua a funzionare (Task B2).

---

### Task B1: configurazione e composizione del testo indicizzato
**File:** modifica `rag/config.py`, `rag/chunking.py`, `.env.example`, `tests/test_config.py`,
`tests/test_chunking.py`, `tests/conftest.py`.
**Produce:** `Config.testo_indicizzato: str` (default `titolo_capitolo`; valori `solo_testo`,
`titolo_capitolo`); `FORMATI_TESTO = ("solo_testo", "titolo_capitolo")`;
`testo_da_indicizzare(chunk: Chunk, config: Config) -> str` in `rag/chunking.py`.
- [ ] Test: default e valore non valido in `test_config.py`; **(1)** stringa esatta per un chunk
  costruito a mano e per la 208 reale (esempio della specifica §2); `solo_testo` →
  `PREFISSO_DOCUMENTO + testo`; il `Chunk.testo` e il payload non cambiano.
- [ ] FAIL → implementare → PASS → commit `feat(chunking): titolo e capitolo nel testo da indicizzare`.

### Task B2: ingestion con ricalcolo nella stessa collezione
**File:** modifica `rag/indice.py`, `rag/ingestion.py`, `tests/test_ingestion.py`, `tests/test_indice.py`.
**Produce:** `imposta_formato(client, nome, valore: str) -> None` (`update_collection(metadata=...)`);
`formato_salvato(client, nome) -> str` (`solo_testo` se la chiave manca); `metadati_attesi` invariato
(il formato non blocca), ma `crea_collezione` scrive anche `testo_indicizzato`; `Rapporto.formato`.
- [ ] Test: **(1)** `finto.ricevuti` == `testo_da_indicizzare` di ogni chunk, esatti, con il prefisso
  per primo; **(2)** payload `testo` senza `"Titolo:"`, `"Capitolo:"`, prefisso; **(3)** ingestion
  `solo_testo` poi `titolo_capitolo`: spie su `create_collection`/`delete_collection` mai chiamate la
  seconda volta, stessi ID, stesso numero di punti, `eliminati == 0`, vettori diversi, payload
  identico, metadato finale `titolo_capitolo`; interruzione (embedder che fallisce) → metadato
  `in_aggiornamento`, punti invariati, nuova ingestion → `titolo_capitolo`; collezione senza la
  chiave → non bloccata; **(5)** dopo un'ingestion `solo_testo`, `cerca` e `aggiorna_payload` con
  config `titolo_capitolo` → vettori, payload e metadati identici a prima.
- [ ] FAIL → implementare → PASS → commit `feat(ingestion): ricalcolo degli embedding con titolo e capitolo nella stessa collezione`.

### Task B3: ricerca invariata e avviso
**File:** modifica `rag/ricerca.py`, `tests/test_ricerca.py`.
- [ ] Test: **(4)** con collezione indicizzata `titolo_capitolo`, `finto.ricevuti == ["search_query: gnocchi"]`
  (niente titolo né capitolo); **(2)** i `Risultato.testo` sono uguali al payload originale e non
  contengono `"Titolo:"`; metadato `in_aggiornamento` → avviso su stderr nella CLI, risultati comunque
  stampati.
- [ ] FAIL → implementare → PASS → commit `feat(ricerca): avviso se la collezione è in aggiornamento`.

### Task B4: ingestion reale e valutazione dopo B (servizi accesi)
- [ ] `.env`: `TESTO_INDICIZZATO=titolo_capitolo`. Conteggio dei punti e metadati prima; ingestion
  completa; conteggio, metadati e indici dopo (1106, nessuna ricreazione).
- [ ] Valutazione senza filtro con `--confronta docs/eval-baseline.json --json docs/eval-dopo-b.json`;
  con `--solo-dosi --confronta docs/eval-dopo-a-solo-dosi.json --json docs/eval-dopo-b-solo-dosi.json`.
- [ ] `docs/eval-dopo-b.md`: tabella baseline / dopo A / dopo B (posizione e score), commento su 208,
  510, tiramisù e peggioramenti con causa probabile (chunk effettivamente restituiti).
- [ ] Commit `docs(eval): valutazione dopo la modifica B`.

### Task B5: `docs/retrieval.md` e README
- [ ] Conteggi delle due ingestion; tabelle di partenza, dopo A, dopo B; due query commentate (una
  riuscita, una fallita) con ricetta, capitolo e posizione del chunk; una riga di motivazione per ogni
  scelta delle specifiche; limiti noti (introduzioni dei capitoli, elenchi in prosa, score non è una
  soglia). README aggiornato con `--solo-dosi`, `--solo-payload`, `TESTO_INDICIZZATO`.
- [ ] Commit `docs(rag): resoconto del retrieval`.
