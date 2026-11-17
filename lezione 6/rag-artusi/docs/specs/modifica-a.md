# Specifica — Modifica A: campo `contiene_dosi` e opzione `--solo-dosi` (Fase 3)

Stato: bozza da approvare. Data: 2026-11-17. Branch: `feat/rag-pipeline` (la revisione
dell'intero branch è rimandata a dopo le modifiche A e B, per decisione dell'utente).
Specifica di riferimento: `docs/specs/pipeline-rag.md` (tutte le sue regole restano valide).

## 1. Intento
Permettere di cercare solo nei chunk che contengono un **elenco di ingredienti con quantità**,
per domande come «quanta farina serve…». È una modifica **di metadati**: i vettori non cambiano,
quindi i punti esistenti ricevono il campo **senza ricalcolare gli embedding**.

## 2. Obiettivi, non obiettivi, anti-obiettivi
**Obiettivi**
- Campo booleano `contiene_dosi` nel payload di ogni punto, con indice sul payload (tipo `bool`).
- Opzione `--solo-dosi` della CLI e parametro `solo_dosi: bool = False` di `cerca()`,
  combinabili con `--capitolo`: entrambi i filtri sono condizioni `must` dello stesso `Filter`
  nativo Qdrant, applicato durante la ricerca.
- Aggiornamento dei 1106 punti esistenti con `set_payload`, senza chiamare l'embedder.

**Non obiettivi**
- Estrarre le quantità (quale ingrediente, quanti grammi): solo vero/falso.
- Cambiare chunking, testo indicizzato o ordinamento dei risultati (la modifica B è a parte).

**Anti-obiettivi**
- Ricalcolare gli embedding o ricreare la collezione per aggiungere un campo.
- Filtrare in Python dopo la ricerca.
- Un riconoscimento «a occhio» che nessuno può verificare: la regola è scritta, testata e
  misurata su un campione.

## 3. Definizione di «contiene dosi»

### 3.1 Che aspetto ha un elenco nel libro
Analisi dei 1106 chunk (2026-11-17): il parser tiene **una riga per ingrediente** (le righe
rientrate del testo originale). Le righe brevi (≤ 100 caratteri) dei chunk finiscono quasi tutte con
una quantità dopo l'ultima virgola: `grammi N.` (1167 righe), `N. N.` (241), `decilitri N.` (88),
`quanto basta.` (64), `mezzo litro.` (30), `chilogrammi N.` (22), `una cucchiaiata.` (20),
`un litro.` (19), `una presa.` (17), `un pizzico.` (14), `quanto una noce.` (11)…
Esempio (ricetta 89):

```
Patate grosse e gialle, grammi 400.
Farina di grano, grammi 150.
```

Alcuni elenchi stanno su **una sola riga** con più voci (ricetta 141: «Uova, N. 4. Burro, grammi 40.
Panna, un decilitro.»).

### 3.2 Regola
1. **Voce di dose**: un segmento di riga che
   - sta in una riga lunga al massimo 100 caratteri (le righe di prosa unite dal parser sono quasi
     sempre più lunghe);
   - comincia con una **lettera maiuscola** (il nome dell'ingrediente), ha una **virgola** entro i
     primi 60 caratteri e, dopo la virgola, entro 40 caratteri, una **quantità**: un numero, oppure
     una di queste espressioni: `grammi`, `gr.`, `N.`, `chilogrammi`, `ettogrammi`, `decilitri`,
     `litro`/`litri`, `cucchiaiata`/`cucchiaino` (e plurali), `bicchiere`/`bicchierino`, `presa`,
     `pizzico`, `quanto basta`, `quanto una noce`/`quanto un…`, `idem`, `intero`/`intera`/`rossi`/`rosso`
     (per le uova).
   - Una riga con più voci (come la 141) si divide in segmenti a ogni punto seguito da spazio e
     maiuscola; ogni segmento conta da solo.
2. **`contiene_dosi = vero`** se il chunk ha **almeno 2 voci di dose**. Una riga isolata non è un
   «elenco».
3. La regola è una funzione pura `contiene_dosi(testo: str) -> bool` in `rag/dosi.py`, calcolata sul
   testo del chunk (senza prefissi), con espressioni regolari scritte nel codice (sono conoscenza del
   corpus, non configurazione).

### 3.3 Casi limite noti (decisi qui)
- **Elenchi in prosa** («Per quattro persone: grammi 500 di magro, grammi 70 di burro e due
  decilitri di panna», ricetta 305): **falso** (non c'è la forma `Nome, quantità`). Limite noto,
  misurato nel campione dei negativi (§3.4).
- **Quantità sparse nella prosa** («annaffiatelo con mezzo bicchiere di San Giovese», ricetta 208):
  **falso**.
- **Ingrediente unico** su una riga («Semolino di grana grossa, grammi 300.»): **falso** (non è un elenco).
- **Overlap:** un chunk che riceve solo la coda di un elenco dal chunk precedente è vero solo se la
  coda contiene almeno 2 voci intere.

### 3.4 Verifica dei falsi positivi (e dei falsi negativi)
- **Test con esempi etichettati a mano** (`tests/test_dosi.py`), sempre eseguiti: righe e paragrafi
  presi dal libro, positivi (89, 141, 617, 626) e negativi (208, 305, il pezzo «se no, un pizzico di
  funghi secchi.» della 256, il Brodo 1, un ingrediente unico).
- **Campione sul corpus reale**: uno script (`python -m rag.dosi --campione 30 --seme 42`) estrae a
  caso, con seme fisso, **30 chunk positivi e 30 negativi** e stampa per ciascuno ricetta, posizione e
  le righe che hanno fatto scattare la regola (o le righe più «sospette» per i negativi: righe brevi
  con numeri). Il campione viene **letto e giudicato a mano** e il risultato salvato in
  `docs/verifica-dosi.md`: tabella con ricetta, chunk, valore calcolato, giudizio (corretto / falso
  positivo / falso negativo) e motivo.
- **Criterio di accettazione:** al massimo **1 falso positivo su 30** positivi del campione. I falsi
  negativi si contano e si riportano (gli elenchi in prosa sono un limite noto) ma non bloccano.
  Se il criterio non è rispettato, si corregge la regola, si aggiunge l'esempio ai test e si rifà il
  campione con lo **stesso seme**.
- Si riportano anche i totali: chunk con `contiene_dosi` vero sul totale (stima dell'analisi:
  ~394 su 1106) e ricette con almeno un chunk vero.

## 4. Aggiornamento dei punti esistenti (senza ricalcolare gli embedding)
- Nuova opzione **`python -m rag.ingestion --solo-payload`**:
  1. verifica la compatibilità della collezione (stesse regole di oggi; collezione assente →
     errore «esegui prima l'ingestion completa»);
  2. ricalcola i chunk dal corpus con la configurazione attuale e **controlla che coincidano** con i
     punti presenti: stesso numero, stessi ID e stesso `testo` nel payload. Se non coincidono (per
     esempio è cambiato il chunking) → errore «i chunk non coincidono con la collezione: esegui
     l'ingestion completa», nessuna scrittura;
  3. scrive il campo con **`set_payload`**: una chiamata per gli ID con valore vero e una per quelli
     con valore falso (a lotti), **senza toccare i vettori** e senza creare l'embedder;
  4. crea l'indice `contiene_dosi` (tipo `bool`) se manca.
  Stampa: punti aggiornati, chunk con dosi, punti nella collezione.
- L'**ingestion completa** mette `contiene_dosi` nel payload di ogni chunk (`crea_chunk`) e si
  assicura che entrambi gli indici (`capitolo`, `contiene_dosi`) esistano, anche su una collezione già
  creata.
- I metadati della collezione non cambiano (il campo non riguarda il modello).

## 5. Ricerca
- `cerca(domanda, k=5, capitolo=None, solo_dosi=False, *, client, embedder, config)`.
- CLI: `python -m rag.ricerca "domanda" [--capitolo X] [--solo-dosi] [--k N]`.
- Con `solo_dosi` il filtro contiene `FieldCondition(key="contiene_dosi", match=MatchValue(value=True))`;
  con anche il capitolo, entrambe le condizioni in `must`.
- La stampa di ogni risultato aggiunge «dosi» quando il campo è vero.

## 6. Test (tutti con servizi spenti)
- `tests/test_dosi.py`: esempi etichettati (§3.4), regola delle 2 voci, riga con più voci, overlap.
- Payload: ogni chunk ha `contiene_dosi` booleano; il chunk 0 della 89 è vero, la 208 è falsa (corpus
  reale, saltato se manca).
- `--solo-payload` (Qdrant in memoria + embedder finto): dopo un'ingestion, si toglie il campo a tutti
  i punti (`delete_payload`), si esegue l'aggiornamento → tutti i punti hanno il campo corretto,
  **vettori identici a prima** (confronto con `with_vectors=True`), **embedder mai chiamato**
  (`chiamate == 0`), numero di punti invariato, indice `contiene_dosi` richiesto (spia, come per
  `capitolo`).
- Chunk non coincidenti (configurazione con altra dimensione di chunk) → errore, nessuna scrittura.
- Ricerca: con `solo_dosi=True` tutti i risultati hanno `contiene_dosi` vero, al massimo k; combinata
  con il capitolo → tutti di quel capitolo e con dosi; il `Filter` passato a Qdrant contiene le due
  condizioni (spia su `query_points`).
- CLI: `--solo-dosi` e `--capitolo` insieme.

## 7. Valutazione dopo A (`docs/eval-dopo-a.md`)
1. Aggiornamento reale con `--solo-payload` sui 1106 punti (servizi accesi); conteggio dei punti prima
   e dopo (devono restare 1106) e controllo su un campione di punti che i vettori siano identici a
   prima.
2. Stesse 9 domande, k = 5, **senza filtro**: ci si aspetta una tabella **identica alla baseline**
   (prova che gli embedding non sono cambiati).
3. Stesse domande **con `--solo-dosi`**: mostra dove il filtro aiuta (domande sulle quantità, per
   esempio la farina degli gnocchi) e dove toglie la fonte giusta (per esempio i cappelletti: la
   risposta «due dozzine» sta in un chunk di prosa).
4. Tabella di confronto con la baseline: domanda | posizione baseline | posizione dopo A |
   posizione dopo A con `--solo-dosi`. Per farlo lo script di valutazione salva anche un file JSON
   accanto al Markdown e accetta `--confronta <file.json>`; la baseline JSON si genera rieseguendo la
   valutazione di partenza (i vettori sono gli stessi).

## 8. Criteri di accettazione
1. Ogni punto ha `contiene_dosi` booleano; esiste l'indice sul payload `contiene_dosi`.
2. Con `--solo-dosi` tutti i risultati hanno il campo vero, al massimo k; combinabile con `--capitolo`.
3. I punti esistenti ricevono il campo senza ricalcolare gli embedding (test + verifica reale).
4. Campione di verifica: al massimo 1 falso positivo su 30; risultato in `docs/verifica-dosi.md`.
5. Tutti i test passano con i servizi spenti.
6. `docs/eval-dopo-a.md` con il confronto con la baseline.

## 9. Lasciato al costruttore
- Le espressioni regolari esatte, purché rispettino §3.2 e gli esempi dei test.
- Il formato della stampa del campione e del JSON della valutazione.
