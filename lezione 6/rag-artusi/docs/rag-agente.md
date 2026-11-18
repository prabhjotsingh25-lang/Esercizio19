# Lezione 8 — il retrieval come tool MCP dell'agente

Resoconto dei quattro esercizi. Tutti i numeri e le tracce vengono da esecuzioni reali con Qdrant
(Docker, collezione `artusi`, 1106 punti) e LM Studio (`text-embedding-nomic-embed-text-v1.5@q8_0`,
`google/gemma-4-e2b`) del 2026-11-18; i file grezzi sono indicati sezione per sezione.

- Specifiche: `docs/specs/l8-es1..es4-*.md` · piani: `docs/plans/l8-*.md`
- Codice: `rag/` (server, pipeline, script) e, per l'agente, `lezione 4/assistente-laboratorio/src/assistente/`
  (`server_esterni.py`, `citazioni.py`, `prove_rag.py`, regole in `grafo.py`)

## Verifiche dell'utente
- **2026-11-18 — domande di valutazione:** l'utente ha verificato sul testo di Gutenberg 59047 le
  fonti attese di `eval/domande_l8.yaml` (3 domande composte, carbonara e sushi senza risposta) e le
  ha confermate corrette; i marcatori `verificare: true` sono stati tolti (commit `84017bc`). Il
  confronto dell'esercizio 3 era già stato lanciato sullo stesso contenuto (il file è cambiato solo
  nei commenti e nei marcatori) e non è stato rilanciato.

## Ambiguità non coperte dalle specifiche (scelta conservativa)
1. **Conferma delle fonti con il modello di messaggio non compilato** (prima conferma: «[Scegli:]»):
   il file non era cambiato, quindi è stato trattato come «nessuna modifica»; la conferma esplicita
   è arrivata subito dopo (sopra).
2. **Soglie nei test**: `crea_config` dei test ha `soglie_attive=False`, così i test degli esercizi
   1-3 non dipendono dalle soglie; i test dell'es. 4 le attivano esplicitamente. In produzione il
   default resta `SOGLIE_ATTIVE=true` come da specifica.
3. **Confronto dell'es. 3 a soglie disattivate** (la specifica lo dice; il comando non ha un'opzione
   per attivarle): le soglie si misurano solo con la calibrazione.
4. **Query «formulata dal modello» nella calibrazione** (richiesta dell'utente del 2026-11-18): è
   ottenuta con una chiamata di tool calling a gemma con la stessa descrizione e lo stesso schema di
   `search_documents` e un prompt di sistema breve, non con l'intero grafo dell'agente (router,
   preferenze e regole RAG non ci sono): approssima la prima mossa dell'agente, in modo ripetibile.
5. **Reranking che sceglie meno di k passaggi**: il reranking listwise restituisce solo gli id
   pertinenti, quindi può dare meno di k passaggi; non si completano con altri candidati.

## Esercizio 1 — il server MCP di ricerca
`python -m rag.server_mcp` (stdio). Tool `search_documents(query, top_k=5, filtro=None)`, risultato
`{modalita, query_usate, passaggi[], nota}`, resource `ricerca://filtri`, una riga di log per chiamata.

Prova reale: `docs/prove/l8-es1-chiamata-reale.md`, con il comando
`.\.venv\Scripts\python.exe -m rag.cliente_mcp "domanda" [--top-k N] [--filtro CAPITOLO]`:
gnocchi (89.0 primo, 0,773), pollo alla cacciatora con filtro `fritti` (208.0 primo, 0,749), tiramisù,
`top_k=50` ridotto a 10 con nota, filtro `Dolciumi` → errore del tool con i 23 capitoli, query vuota
→ errore del tool; nessun traceback nel log.

## Esercizio 2 — aggancio all'agente: tracce dei quattro casi
Comando (da `lezione 4/assistente-laboratorio`, con `SERVER_MCP_FILE=server_mcp.json` e
`AMBITO_RICERCA` nel `.env`):
`$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.prove_rag --uscita "..\..\lezione 6\rag-artusi\docs\prove\l8-es2-tracce"`.
Tracce complete: `docs/prove/l8-es2-tracce/` (`tracce.md` + un JSON per caso). Variante strumenti
`locale`, ricerca via stdio, modalità `base`, prompt con le regole 1-4 (la regola 5 sulle fasce è
dell'es. 4 ed è stata aggiunta dopo queste tracce).

| Caso | Domanda | Strumenti (argomenti) | Risposta | Citazioni verificate / sconosciute | Esito | Durata |
|---|---|---|---|---|---|---|
| documentale | Quanta farina serve per 400 grammi di patate negli gnocchi? | `search_documents` {query: «farina per gnocchi patate»} → 89.0, 89.1, 90.0, 201.0, 661.1 | «… servono 150 grammi di farina di grano per gli gnocchi [89.0].» | 89.0 / — | atteso | 313 s |
| ora | Che ore sono a Tokyo? | `ora_corrente` {fuso_orario: Asia/Tokyo} | «Attualmente a Tokyo sono le ore 18:11:25 del 18 novembre 2026.» | — / — (ricerche 0) | atteso | 110 s |
| generica | Ciao! Cosa sai fare? | nessuno | elenco delle capacità (cita anche la ricerca nelle ricette) | — / — (ricerche 0) | atteso | 116 s |
| senza risposta | Qual è la ricetta del tiramisù? | `search_documents` {query: «tiramisù»} → 575.1 Brioches (0,548), 560.0, 261.0, 182.0, 256.2 | «Non ho trovato la ricetta del tiramisù nei documenti disponibili.» | — / — (ricerche 1, passaggi 5) | atteso | 215 s |

Osservazioni:
- Il router ha fatto passare le tre domande in ambito grazie ad `AMBITO_RICERCA`; il revisore ha
  accettato anche l'astensione («La ricerca non ha prodotto risultati pertinenti…»).
- Il controllo nell'host ha scritto, per ogni turno, la riga
  `citazioni verificate=… sconosciute=… ricerche=… passaggi_ricevuti=…`: nessuna citazione
  sconosciuta nei quattro casi.
- Il modello riformula la domanda in una query breve: «farina per gnocchi patate», «tiramisù». Con
  la query breve gli score del tiramisù scendono a 0,52–0,55 (con la domanda intera il primo era
  0,706, lezione 7): da qui la calibrazione su entrambe le formulazioni (es. 4).
- Durate di 2-5 minuti a turno: gemma su LM Studio (router + agente + revisore) più l'avvio del
  server stdio a ogni ricerca (log del server: 9 s per la ricerca del tiramisù, embedding compreso).

## Esercizio 3 — riscrittura, scomposizione e reranking a confronto
Comando unico (da `lezione 6/rag-artusi`), riproducibile: stesse 14 domande, stesso indice, k = 5,
temperatura 0, seed 42, `reasoning_effort=none`, soglie disattivate; cambia solo la modalità.

```
.\.venv\Scripts\python.exe -m rag.confronto --domande eval/domande_l8.yaml --k 5 --uscita docs/confronto-l8.md
```

Rapporto completo: `docs/confronto-l8.md`; righe grezze (query usate, id, score, ripieghi, latenze):
`docs/confronto-l8.json`. Il codice della pipeline usato è quello del commit `33c8766` (l'intestazione
del rapporto riporta `4807d6e`, il commit corrente alla fine dell'esecuzione: in mezzo sono cambiati
solo calibrazione e documentazione).

| Configurazione | Fonte nei primi 5 | MRR | Copertura composte | Astensioni corrette | Astensioni errate | Chiamate LLM | Latenza media | Latenza max | Ripieghi |
|---|---|---|---|---|---|---|---|---|---|
| base | 11/11 | 0,886 | 5/6 | 0/3 | 0 | 0 | 0,6 s | 5,9 s¹ | 0 |
| riscrittura | 11/11 | 0,836 | 6/6 | 0/3 | 0 | 14 | 28,0 s | 30,4 s | 0 |
| reranking | 11/11 | **1,000** | 6/6 | 0/3 | 0 | 14 | 36,8 s | 41,3 s | 1 (id duplicati) |
| entrambe | 11/11 | 0,909 | 6/6 | 0/3 | 0 | 28 | 44,4 s | 49,0 s | 0 |

¹ prima domanda della serie (caricamento del modello di embedding in LM Studio); le altre sono
sotto il secondo.

### Casi migliorati e peggiorati rispetto a base
**riscrittura** — migliorati 2, peggiorati 2
- ↑ «Per quanto tempo si deve cuocere il baccalà?»: 510 dalla 4ª alla 1ª posizione (la query
  «baccalà Artusi» porta in cima il Baccalà fritto).
- ↑ «Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà?»: parti coperte 1/2 → 2/2:
  è il caso per cui serve la scomposizione (in base i 5 posti vanno tutti al brodo).
- ↓ «Che vino si usa per il pollo alla cacciatora?»: 208 dalla 1ª alla 5ª. Le query generate
  («Artusi vino», «ricette carne Ottocento», «vino per pollo») sono generiche: le altre ricette di
  pollo compaiono in più liste e l'RRF, che premia il consenso, le mette davanti alla 208 (che ha
  ancora il coseno più alto, 0,749).
- ↓ «Quanti cappelletti bastano a un mangiatore moderato?»: 7 dalla 1ª alla 2ª, sopravanzata da
  579.1 per lo stesso motivo («porzioni ricette», «ricettario artusi»).

**reranking** — migliorati 3, peggiorati 0
- ↑ baccalà (4 → 1), ↑ mandorle e zucchero (2 → 1: il reranker scarta la 613 «Dolce di mandorle», il
  falso positivo da titolo della lezione 7), ↑ brodo + baccalà (parti 1/2 → 2/2).
- Un ripiego: per il baccalà il modello ha ripetuto un id; il duplicato è stato scartato e segnato.

**entrambe** — migliorati 2, peggiorati 0
- ↑ baccalà (4 → 2), ↑ brodo + baccalà (1/2 → 2/2). Il reranking recupera i due peggioramenti della
  sola riscrittura (pollo e cappelletti tornano 1°).

### Commento
- **Chi funziona meglio e su quali domande.** Il **reranking** è il migliore su queste domande:
  MRR 1,000 (fonte sempre al 1° posto), tutte le composte coperte, nessun peggioramento. La
  **riscrittura** serve soprattutto alle **domande composte** (brodo + baccalà), ma da sola peggiora
  due domande semplici: con gemma-4-e2b le query generate contengono spesso parole del contesto
  del prompt («Artusi», «Ottocento») invece delle parole della domanda, e l'RRF premia le ricette che
  queste query generiche trovano tutte. `entrambe` corregge quei peggioramenti ma costa il doppio.
- **A quale costo.** base: 0 chiamate e meno di un secondo; ogni chiamata a gemma aggiunge circa
  25-35 s su questo computer (riscrittura 28 s, reranking 37 s, entrambe 44 s per domanda). Nel
  turno dell'agente (110-313 s nelle tracce dell'es. 2) il reranking aggiunge circa 35 s per ogni
  ricerca.
- **Astensioni: nessuna configurazione si astiene davvero** (0/3). Il reranking riduce i passaggi
  delle domande senza risposta (tiramisù 1, sushi 1, carbonara 3) ma non restituisce mai la lista
  vuota: trova sempre «qualcosa di pertinente» (per il tiramisù 618.1). L'astensione resta quindi al
  modello dell'agente (come nella traccia del tiramisù dell'es. 2) e alle soglie dell'es. 4.
- **Ripieghi**: 1 su 42 chiamate all'LLM (id duplicato). Nessun JSON non valido: lo structured
  output di LM Studio con `json_schema` (e l'`enum` degli id) tiene il modello piccolo dentro lo schema.
- **Limite della metrica**: la posizione conta la ricetta, non il chunk. Per i cappelletti il
  reranking tiene solo 7.2, mentre la frase «A un mangiatore discreto bastano due dozzine» è nel
  chunk 7.1 (lezione 7): conta come trovata ma il passaggio giusto non arriva al modello.
### Seconda versione: prompt di riscrittura corretto (un solo fattore cambiato)
Il prompt originale cominciava con «Prepari query per cercare passaggi in un ricettario italiano
dell'Ottocento (Pellegrino Artusi).» e gemma copiava «Artusi»/«Ottocento» nelle query. Su richiesta
dell'utente il prompt è stato corretto (commit `c69b4e9`): niente libro, autore ed epoca, e il
divieto esplicito di inserirli nelle query. **È cambiato solo il prompt di riscrittura**: stesse
domande, stesso indice, k, temperatura, seed; sono state rilanciate solo `riscrittura` ed
`entrambe`; `base` è presa dal primo confronto (`--base-da`, deterministica, nessun LLM);
`reranking` non usa la riscrittura e resta quella sopra.

```
.\.venv\Scripts\python.exe -m rag.confronto --domande eval/domande_l8.yaml --k 5 --configurazioni base riscrittura entrambe --base-da docs/confronto-l8.json --uscita docs/confronto-l8-prompt-corretto.md
```

| Configurazione | Prompt di riscrittura | Fonte nei primi 5 | MRR | Copertura composte | Astensioni corrette | Chiamate LLM | Latenza media | Ripieghi |
|---|---|---|---|---|---|---|---|---|
| base | — | 11/11 | 0,886 | 5/6 | 0/3 | 0 | 0,6 s | 0 |
| riscrittura | originale | 11/11 | 0,836 | 6/6 | 0/3 | 14 | 28,0 s | 0 |
| riscrittura | **corretto** | **10/11** | 0,864 | 6/6 | 0/3 | 14 | 20,9 s | 0 |
| entrambe | originale | 11/11 | 0,909 | 6/6 | 0/3 | 28 | 44,4 s | 0 |
| entrambe | **corretto** | 11/11 | 0,894 | **4/6** | 0/3 | 28 | 34,9 s | 2 (id duplicati) |
| reranking | — | 11/11 | 1,000 | 6/6 | 0/3 | 14 | 36,8 s | 1 (id duplicati) |

Casi rispetto a base con il prompt corretto (`docs/confronto-l8-prompt-corretto.md`):
- **riscrittura** — migliorato: brodo + baccalà (parti 1/2 → 2/2); peggiorato: «Per quanto tempo si
  deve cuocere il baccalà?» (510 dalla 4ª posizione a **fuori dai primi 5**). I due peggioramenti
  del prompt originale (pollo 1 → 5, cappelletti 1 → 2) **non ci sono più**: il pollo torna 1°.
- **entrambe** — migliorati: baccalà (4 → 3), brodo + baccalà (1/2 → 2/2); peggiorati: le composte
  gnocchi + pollo e cacciucco + cappelletti (parti 2/2 → 1/2): il reranking ha tenuto un solo lato.

Perché: le parole del contesto sono sparite, ma gemma ora copia **gli esempi del nuovo prompt**
(«piatti, ingredienti, quantità, tempi») e produce query come «ingredienti tiramisù», «quantità
sushi», «cuocere baccalà quantità», che allontanano la 510 nel caso del baccalà. Con il prompt
corretto le query di una domanda composta sono giuste («farina gnocchi quantità», «vino pollo alla
cacciatora»), ma è il reranking che poi tiene un solo lato. Latenza più bassa (21 s e 35 s): query
più corte da generare.

### Indicazione pratica
`MODALITA_RICERCA=reranking` se la latenza è accettabile (è la sola configurazione senza
peggioramenti in entrambe le prove), altrimenti `base`. La riscrittura, con qualunque dei due prompt,
sposta i problemi invece di risolverli con un modello da 2B: il prompt va riscritto senza elenchi di
esempi che il modello possa copiare, e va riprovato con questo stesso comando.

## Esercizio 4 — soglie di confidenza

### Dove si applicano
Sul **coseno migliore** del passaggio fra le query usate, **dopo la fusione RRF e prima del
reranking** (specifica es. 4): lo score RRF dipende solo dai ranghi (1/(60+r)), non dalla
somiglianza, e il reranking non deve vedere passaggi esclusi. In `base` le soglie filtrano i k
risultati di Qdrant.

### Calibrazione (score reali)
Comando: `.\.venv\Scripts\python.exe -m rag.calibrazione --domande eval/domande_l8.yaml --k 5 --timeout-query 180 --uscita docs/calibrazione-l8.md`.
Rapporto: `docs/calibrazione-l8.md` (+ `.json`). Gli score sono misurati in due modi (richiesta
dell'utente): con la **domanda intera** e con la **query che gemma passa a `search_documents`**
(tool calling con descrizione e schema del tool).

| Gruppo | Domanda intera (min · mediana · max) | Query del modello (min · mediana · max) |
|---|---|---|
| Con risposta: top-1 | 0,715 · 0,766 · 0,821 | 0,734 · 0,766 · 0,823 |
| Con risposta: score della fonte attesa | 0,715 · 0,754 · 0,817 | 0,734 · 0,766 · 0,821 |
| Senza risposta: top-1 | 0,695 · 0,706 · 0,728 | 0,548 · 0,673 · 0,691 |

- Con la domanda intera gli intervalli **si sovrappongono** (carbonara 0,728 sopra due domande con
  risposta, 0,715 e 0,720): nessuna soglia separa.
- Con la query del modello sono **separati** (0,691 sushi contro 0,734 baccalà): il modello accorcia
  le domande senza risposta a poche parole («tiramisù» 0,548; «ricetta della carbonara» 0,673).
- La query del modello c'è per **11 domande su 14**: per tre domande gemma ha risposto senza
  chiamare la ricerca (gnocchi che si sciolgono; cappelletti; cacciucco + cappelletti). Le ultime
  due erano andate in timeout a 60 s; rifatte con `--aggiorna-query … --timeout-query 180` non sono
  andate in timeout ma il modello non ha chiamato la ricerca.
- Con le soglie di partenza 0,6/0,3 nessun effetto: 70 passaggi su 70 «affidabile» con la domanda
  intera, 0 astensioni.

### Valori proposti: `SOGLIA_ALTA=0.73`, `SOGLIA_BASSA=0.70`
Approvati dall'utente il 2026-11-18 a condizione che reggano anche dopo la correzione del prompt di
riscrittura (verifica più sotto).
Effetto calcolato sugli score registrati (in `base` le soglie sono un filtro su quegli score):

| Soglie (alta/bassa) | Formulazione | Astensioni corrette | Astensioni errate | Fonti perse | Fonte in fascia «media» |
|---|---|---|---|---|---|
| **0,73 / 0,70** | domanda intera | 1/3 (sushi) | 0 | 0 | 2 |
| **0,73 / 0,70** | query del modello | **3/3** | 0 | 0 | 0 |
| 0,73 / 0,68 | query del modello | 2/3 | 0 | 0 | 0 |
| 0,75 / 0,72 | domanda intera | 2/3 | **1** | **1** | 4 |

- **Bassa 0,70**: sotto la fonte attesa più bassa misurata (0,715 / 0,734), quindi non perde
  risposte; sopra il top-1 di tutte le domande senza risposta formulate dal modello (max 0,691).
- **Alta 0,73**: sopra il top-1 più alto delle domande senza risposta in entrambe le formulazioni
  (0,728): un passaggio di una domanda senza risposta non è mai «affidabile».

### Verifica dopo la correzione del prompt di riscrittura: le soglie reggono
Calibrazione rilanciata con le soglie proposte e il prompt corretto (`docs/calibrazione-l8-verifica.md`):

```
.\.venv\Scripts\python.exe -m rag.calibrazione --domande eval/domande_l8.yaml --k 5 --alta 0.73 --bassa 0.70 --configurazioni base entrambe --timeout-query 180 --uscita docs/calibrazione-l8-verifica.md
```

| Variante | Fonte nei primi 5 | Astensioni corrette | Astensioni errate | Fasce restituite |
|---|---|---|---|---|
| base senza soglie | 11/11 | 0/3 | 0 | non valutata 70 |
| base con soglie | 11/11 | 1/3 (sushi) | 0 | affidabile 32, media 24 |
| entrambe senza soglie | 11/11 | 0/3 | 0 | non valutata 31 |
| entrambe con soglie (nuove query) | 11/11 | 1/3 (sushi) | 0 | affidabile 16, media 9 |
| base, query del modello, senza soglie | 11/11 | 0/3 | 0 | non valutata 70 |
| base, query del modello, con soglie | 11/11 | 2/3 (tiramisù, sushi) | 0 | affidabile 28, media 22 |

Criteri di tenuta, tutti rispettati: **nessuna fonte persa** (11/11 con e senza soglie in ogni
variante), **nessuna astensione errata**, **nessun passaggio di una domanda senza risposta in fascia
«affidabile»** (tiramisù 0,704-0,706 e carbonara 0,702-0,728 restano in «media», cioè «da
verificare»). In `entrambe` le soglie agiscono sul coseno migliore fra le query, e la domanda
originale è sempre fra le query: per questo i suoi score contano come quelli della domanda intera.
In questa esecuzione le query del modello per carbonara e sushi sono andate in timeout anche a 180 s
(LM Studio più carico): in quella variante si è usata la domanda intera, quindi la carbonara (0,728)
non si astiene; con la sua query misurata nella prima calibrazione («ricetta della carbonara»,
0,673) sarebbe esclusa. Le soglie 0,73/0,70 sono state fissate come default (`.env.example`,
`rag/config.py`, commit `70a5276`).

**Limiti (da leggere prima di usarle):** le soglie sono calibrate su **14 domande** (11 con la
query del modello), con **margine stretto** (0,691 → 0,70: 0,009); valgono **solo con query brevi
formulate dal modello** (con la domanda intera non separano: tiramisù 0,706 e carbonara 0,728
restano sopra la soglia bassa); vanno **ricalibrate se cambia il modello di embedding o il modello
chat** (lo stesso comando, poi `--alta/--bassa` per provare i valori).
