# Lezione 8 · Esercizio 4 — Soglie di confidenza sullo score

Stato: **da approvare**.

## Scopo
Non mandare al modello passaggi troppo poco simili alla domanda e dire al modello quanto fidarsi di
quelli che restano; con nessun passaggio rimasto, lista vuota dichiarata → l'agente si astiene.

## Regole
- `SOGLIA_ALTA` (partenza 0,6) e `SOGLIA_BASSA` (partenza 0,3) da configurazione; valide se
  `0 ≤ bassa ≤ alta ≤ 1`, altrimenti errore all'avvio. `SOGLIE_ATTIVE=true|false` (default `true`)
  per il confronto con/senza.
- `score ≥ alta` → `"fascia": "affidabile"`; `bassa ≤ score < alta` → `"media"`; `score < bassa` →
  **escluso**, mai inviato al modello. Uguale a una soglia = fascia superiore.
- Ogni passaggio restituito ha il campo `fascia` (con soglie disattivate: `"non_valutata"`, così
  il formato non cambia).
- Nessun passaggio rimasto → `passaggi: []` e `nota` «nessun passaggio sopra la soglia minima
  (0,30): il libro non sembra contenere la risposta». Esclusioni parziali → nota «N passaggi esclusi
  perché sotto la soglia minima».
- Log: la riga della chiamata riporta `esclusi_soglia=N`.

## Dove si applicano le soglie (decisione)
Nelle modalità avanzate esistono tre numeri: il coseno di ogni query, il punteggio RRF dopo la
fusione, l'ordine del reranking (che non ha uno score).

| | Pro | Contro |
|---|---|---|
| A. su ogni lista per query, **prima** della fusione | semplice | cambia i ranghi usati dall'RRF: la fusione non vede più gli stessi dati delle prove senza soglie |
| **B. dopo la fusione, prima del reranking, sul coseno migliore del passaggio** (Raccomandata) | le soglie sono definite su una grandezza con un significato (similarità coseno, la stessa che misuriamo nella calibrazione); i ranghi dell'RRF restano quelli senza soglie; il reranker non vede mai passaggi esclusi (meno token, non può «ripescarli») | il coseno «migliore» può venire da una query riscritta più che dalla domanda originale |
| C. alla fine, dopo il reranking | il reranker lavora su tutto | si pagano token per candidati poi esclusi; due criteri che si contraddicono sullo stesso passaggio |
| D. sul punteggio RRF | — | **non ha senso**: 1/(60+r) dipende solo dal rango e dal numero di query, non dalla somiglianza; con una sola query il 1° ha sempre 1/61 anche se è irrilevante. Le soglie 0,6/0,3 su valori ~0,016–0,05 escluderebbero tutto |

In `base` B coincide con «subito dopo Qdrant».

**Soglie e `top_k` (decisione mia)**: le soglie si applicano alla lista dei **candidati**, prima del
taglio a `top_k`. Nelle modalità avanzate (candidati = `CANDIDATI_PER_QUERY` per query) un passaggio
escluso può quindi essere sostituito da un candidato successivo sopra soglia; in `base` i candidati
sono i `top_k` di Qdrant, quindi le esclusioni danno solo meno passaggi. Il numero N della nota =
candidati esclusi. La differenza tra modalità è dichiarata nel confronto.

**Soglie attive per default** con 0,6/0,3 come da consegna; le tre tracce dell'agente si fanno
**dopo** la calibrazione, con i valori proposti messi in `.env` (con il tuo ok sui valori finali,
annotati in `docs/rag-agente.md`). Lo `score` del passaggio è quindi sempre il coseno
(arrotondato), la `fascia` deriva da quello.

## Fatto già misurato che conta (lezione 7, `docs/eval-dopo-b.md`)
Con nomic + prefissi, i primi risultati hanno coseno **0,70–0,85 sia con sia senza risposta**
(tiramisù: 0,706; gnocchi che si sciolgono, risposta giusta: 0,720). Con le soglie di partenza
0,6/0,3 **ogni passaggio sarebbe «affidabile»** e le soglie non avrebbero effetto. Non scelgo io i
valori finali: la calibrazione li deve proporre da score misurati, e può anche concludere che sul
coseno non esiste una soglia che separi bene (in quel caso lo si scrive, con i numeri).

## Agente (istruzioni aggiornate, nel blocco RAG dell'es. 2)
- «Ogni passaggio ha una `fascia`. Un'informazione che viene **solo** da passaggi di fascia
  `media` va presentata come da verificare sulla fonte (scrivi «da verificare sulla fonte»).»
- «Se la lista dei passaggi è vuota, il libro non contiene la risposta: dillo e non citare nulla.»

## Script di calibrazione
Da `lezione 6/rag-artusi`:
```
.\.venv\Scripts\python.exe -m rag.calibrazione --domande eval/domande_l8.yaml --k 5 --uscita docs/calibrazione-l8.md
```
1. **Score**: per ogni domanda (modalità `base`, soglie disattivate) registra i coseni dei primi k
   passaggi, il coseno della fonte attesa (se trovata) e il tipo (con / senza risposta). Tabella
   per domanda + riepilogo: per le domande CON risposta min/mediana/max del top-1 e dello score
   della fonte attesa; per quelle SENZA risposta min/mediana/max del top-1; sovrapposizione degli
   intervalli. Il JSON grezzo è salvato accanto (`docs/calibrazione-l8.json`).
2. **Confronto con/senza soglie** sulle stesse domande dell'es. 3, per `base` ed `entrambe`
   (`--configurazioni` per sceglierne altre): astensioni corrette, astensioni errate, fonte attesa
   nei primi k (stesse definizioni dell'es. 3), più la distribuzione delle fasce restituite.
   Le soglie usate sono quelle di `.env` o di `--alta/--bassa` (per provare valori candidati senza
   toccare `.env`).
3. Lo script **non sceglie** le soglie: stampa i numeri; la proposta motivata la scrivo in
   `docs/rag-agente.md` dopo averli letti. Se i servizi sono spenti, lo script si ferma con il
   messaggio d'errore e io lascio in `docs/rag-agente.md` il segnaposto «DA ESEGUIRE» con il comando.

## Criteri di accettazione
Test offline (funzione pura delle soglie + server con ricerca finta che restituisce score preparati):
1. Score 0,75 / 0,45 / 0,10 con soglie 0,6/0,3 → affidabile / media / escluso.
2. Score esattamente 0,6 → affidabile; esattamente 0,3 → media.
3. Tutti sotto la bassa → `passaggi: []` e nota che lo dichiara; esclusioni parziali → nota con il numero.
4. Con le soglie, un passaggio escluso non compare nel prompt del reranking (LLM finto).
5. Nella modalità con riscrittura la fascia usa il coseno migliore tra le query (score preparati
   diversi per query).
6. Configurazione: bassa > alta, valori fuori da [0,1] o non numerici → errore chiaro all'avvio.
7. `SOGLIE_ATTIVE=false` → nessuna esclusione, `fascia: "non_valutata"`.
8. Prompt dell'agente: contiene le regole su «da verificare sulla fonte» e sulla lista vuota.
9. Script di calibrazione su dati finti: tabella degli score, riepilogo, confronto con/senza.
Prova reale: calibrazione eseguita; tre tracce dell'agente (risposta affidabile, risposta da
verificare, senza risposta con astensione) in `docs/rag-agente.md`. Se nessuna domanda reale cade
nella fascia media con le soglie scelte, lo dico invece di forzare un esempio.
