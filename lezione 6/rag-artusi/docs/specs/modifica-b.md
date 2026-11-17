# Specifica — Modifica B: titolo e capitolo nel testo indicizzato (Fase 4)

Stato: bozza da approvare. Data: 2026-11-17. Branch: `feat/rag-pipeline`.
Specifiche di riferimento: `docs/specs/pipeline-rag.md`, `docs/specs/modifica-a.md` (restano valide).

## 1. Intento
Oggi l'embedding di un chunk vede solo il corpo della ricetta, senza titolo
(`docs/specs/pipeline-rag.md` §6.1.7). Così una domanda che usa le parole del titolo non trova il
chunk: la ricetta 208 «Pollo alla cacciatora» (capitolo «Fritti») non contiene la parola
«cacciatora» e nella baseline non esce nei primi 5. La modifica B mette **titolo e capitolo davanti
al testo passato all'embedder**, lasciando invariato tutto il resto.

## 2. Obiettivi, non obiettivi, anti-obiettivi
**Obiettivi**
- Testo passato all'embedder per ogni chunk:
  `PREFISSO_DOCUMENTO + "Titolo: " + titolo + "\nCapitolo: " + capitolo + "\n\n" + testo del chunk`.
  Esempio (ricetta 208, chunk 0):
  ```
  search_document: Titolo: Pollo alla cacciatora
  Capitolo: Fritti

  Trinciate una grossa cipolla e tenetela per più di mezz'ora nell'acqua fresca, …
  ```
  Il **prefisso del modello viene per primo**, poi titolo e capitolo, poi il testo (richiesta
  dell'utente).
- Il payload `testo` e il `testo` dei risultati restano **il testo originale del chunk**, senza
  prefisso, titolo né capitolo.
- Ricalcolo di **tutti** gli embedding nella **stessa collezione**, senza ricrearla: stessi ID, upsert,
  numero di punti invariato (1106), chunk orfani gestiti come oggi (§6.3 della specifica principale).
- Un test verifica **esattamente** il testo passato all'embedder.

**Non obiettivi**
- Cambiare chunking, ID, payload, la domanda (resta `PREFISSO_QUERY + domanda`), `contiene_dosi`,
  i filtri o il modello.

**Anti-obiettivi**
- Titolo o capitolo che finiscono nel payload `testo` o nei risultati stampati come parte del testo.
- Cancellare e ricreare la collezione, o raddoppiare i punti.
- Una collezione che resta, senza che nessuno lo sappia, con vettori di due formati diversi.

## 3. Decisioni

### 3.1 Formato del testo indicizzato (scelta mia, da approvare)
- Etichette esplicite `Titolo:` e `Capitolo:` su due righe, poi una riga vuota e il testo. Motivo:
  il modello vede chiaramente che cosa è titolo e che cosa è testo; la riga vuota separa come i
  paragrafi del corpus.
- Il numero della ricetta **non** entra nel testo indicizzato: aggiungerebbe solo cifre senza
  significato per la ricerca.
- La composizione è una funzione pura `testo_da_indicizzare(chunk, config) -> str` in
  `rag/chunking.py`, usata dall'ingestion; il `Chunk` resta com'è (`testo` = testo originale).

### 3.2 Configurazione
- Nuova variabile `TESTO_INDICIZZATO` in `.env`/`.env.example`: `titolo_capitolo` (nuovo default) oppure
  `solo_testo` (comportamento della baseline). Serve a poter rifare la baseline e a confrontare;
  valori diversi → `ErroreConfigurazione`.

### 3.3 Metadati della collezione e ricalcolo nella stessa collezione
- Nei metadati della collezione si aggiunge `testo_indicizzato` (`solo_testo` | `titolo_capitolo` |
  `in_aggiornamento`). Una collezione creata prima di B non ha la chiave: vale `solo_testo`.
- `testo_indicizzato` **non blocca** l'ingestion (al contrario di modello, prefissi e dimensione): un
  valore diverso significa «ricalcola tutto», che l'ingestion fa già a ogni esecuzione.
- Sequenza dell'ingestion completa: controlli di compatibilità come oggi → **metadato
  `testo_indicizzato = "in_aggiornamento"`** (`update_collection`, merge dei metadati) → embedding di
  tutti i chunk nel formato configurato → upsert con gli stessi ID → eliminazione degli orfani →
  **metadato = formato configurato**. Se il processo si interrompe a metà, la collezione dice
  `in_aggiornamento` e la prossima ingestion completa la ripara.
- La ricerca, se trova `testo_indicizzato = "in_aggiornamento"`, stampa un **avviso** su stderr
  (risultati possibili ma con vettori misti); non blocca.
- `--solo-payload` (modifica A) non cambia: confronta il `testo` del payload, che resta l'originale.
- Il rapporto dell'ingestion stampa anche il formato del testo indicizzato.

## 4. Test (tutti con servizi spenti)
- **Testo esatto passato all'embedder** (fixture): per la ricetta 1 del fixture,
  `finto.ricevuti[0] == "search_document: Titolo: Brodo\nCapitolo: Brodi, gelatina e sughi\n\n" + testo del chunk`;
  per ogni chunk vale `ricevuti[i] == testo_da_indicizzare(chunk_i)` e
  `ricevuti[i].startswith(PREFISSO_DOCUMENTO + "Titolo: ")`.
- Corpus reale: il testo indicizzato del chunk 0 della 208 è esattamente quello dell'esempio §2.
- Il payload `testo` e il `testo` dei risultati di `cerca` non contengono `"Titolo:"`,
  `"Capitolo:"` né il prefisso.
- Con `TESTO_INDICIZZATO=solo_testo` il testo passato è `PREFISSO_DOCUMENTO + testo` (come la baseline).
- **Ricalcolo nella stessa collezione**: ingestion con `solo_testo`, poi con `titolo_capitolo` (Qdrant in
  memoria) → stessi ID, stesso numero di punti, `eliminati == 0`, vettori **diversi** da prima, payload
  identico, `create_collection` e `delete_collection` **mai chiamati** la seconda volta (spia), metadato
  `testo_indicizzato == "titolo_capitolo"`.
- Interruzione simulata (embedder che fallisce) → il metadato resta `in_aggiornamento`; una nuova
  ingestion lo porta a `titolo_capitolo`; la ricerca con il metadato `in_aggiornamento` stampa l'avviso.
- Collezione senza la chiave `testo_indicizzato` (creata prima di B) → non bloccata, trattata come
  `solo_testo`; modello diverso → ancora bloccata.
- Configurazione: `TESTO_INDICIZZATO=altro` → errore.

## 5. Valutazione dopo B (`docs/eval-dopo-b.md`)
1. Ingestion completa reale con `TESTO_INDICIZZATO=titolo_capitolo`: conteggi (ricette, chunk,
   scritti, eliminati, punti prima e dopo: devono restare 1106), durata, metadati della collezione
   prima e dopo; verifica che la collezione non sia stata ricreata (stesso numero di punti per tutto il
   tempo, `contiene_dosi` e indici ancora presenti).
2. Stesse 9 domande, k = 5, senza filtro, con confronto con la baseline (`docs/eval-baseline.json`;
   dopo A senza filtro è identica alla baseline) → tabella con posizione baseline, posizione dopo B,
   variazione, score.
3. Stesse domande con `--solo-dosi`, confronto con `docs/eval-dopo-a-solo-dosi.json`.
4. Commento, **in particolare sulla ricetta 208** (posizione prima e dopo, quale chunk esce, score),
   e su eventuali peggioramenti (il titolo può anche «attirare» chunk sbagliati di ricette con titoli
   simili, per esempio gli altri «Pollo…»).

## 6. Criteri di accettazione
1. Un test verifica esattamente il testo passato all'embedder (prefisso, poi titolo e capitolo, poi testo).
2. Payload `testo` e risultati restano il testo originale.
3. L'ingestion ricalcola tutti gli embedding senza ricreare la collezione; i punti restano 1106.
4. Tutti i test passano con i servizi spenti.
5. `docs/eval-dopo-b.md` con il confronto con la baseline e il commento sulla 208.

## 7. Lasciato al costruttore
- Dove salvare il JSON della valutazione dopo B (accanto al Markdown, come per A).
- Il testo esatto dell'avviso per `in_aggiornamento`.
