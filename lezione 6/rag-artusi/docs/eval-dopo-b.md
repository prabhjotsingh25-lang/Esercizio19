# Valutazione dopo la modifica B (titolo e capitolo nel testo indicizzato)

- Data: 2026-11-17
- Modello: `text-embedding-nomic-embed-text-v1.5@q8_0` · collezione `artusi`
- Chunking: paragrafi, 1200 caratteri, overlap 200 · k = 5
- Testo passato all'embedder: `search_document: Titolo: <titolo>\nCapitolo: <capitolo>\n\n<testo del chunk>`;
  la domanda resta `search_query: <domanda>`; payload e risultati restano il testo originale.
- Righe salvate in `docs/eval-dopo-b.json` e `docs/eval-dopo-b-solo-dosi.json`.

## Ricalcolo nella stessa collezione

`TESTO_INDICIZZATO=titolo_capitolo` in `.env`, poi `python -m rag.ingestion`:

| | Prima | Dopo |
|---|---|---|
| Punti | 1106 | 1106 |
| Ricette / capitoli / chunk | — | 790 / 23 / 1106 |
| Scritti (upsert, stessi ID) / eliminati | — | 1106 / 0 |
| Metadati | modello, prefissi, dimensione 768 (nessun `testo_indicizzato` = `solo_testo`) | gli stessi + `testo_indicizzato: titolo_capitolo` |
| Indici del payload | `capitolo` keyword (1106), `contiene_dosi` bool (1106) | invariati |
| Durata | — | 137 s |

La collezione non è stata ricreata: stessi ID, stesso numero di punti, indici e campo `contiene_dosi`
(scritto dalla modifica A con `set_payload`) ancora presenti.

## Confronto: baseline, dopo A (senza filtro), dopo B

| Domanda | Fonte attesa | Baseline pos. (score) | Dopo A pos. (score) | Dopo B pos. (score) | Variazione B |
|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 1 (0.769) | 1 (0.769) | 1 (0.773) | = |
| Che vino si usa per il pollo alla cacciatora? | 208 | — (0.701) | — (0.701) | **1 (0.749)** | trovata |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 1 (0.777) | 1 (0.777) | 1 (0.774) | = |
| Qual è la ricetta del tiramisù? | nessuna | — (0.717) | — (0.717) | — (0.706) | = |
| Quanti cappelletti bastano a un mangiatore moderato? | 7 | 2 (0.730) | 2 (0.730) | **1 (0.745)** | ↑1 |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 5 (0.725) | 5 (0.725) | **1 (0.720)** | ↑4 |
| Per quanto tempo si deve cuocere il baccalà? | 510 | — (0.750) | — (0.750) | **4 (0.766)** | trovata |
| Con che cosa si insaporisce il brodo? | 1 | 1 (0.752) | 1 (0.752) | 1 (0.768) | = |
| Come si fa un dolce di mandorle e zucchero? | 617, 785, 626, 620, 687 | 1 (0.847) | 1 (0.847) | 2 (0.821) | **↓1** |

Lo score è quello del primo risultato. Fonte trovata nei primi 5: **baseline 6/8 · dopo A 6/8 ·
dopo B 8/8**; al primo posto: baseline 4/8 · dopo A 4/8 · dopo B 6/8.

### Totali (generati dai dati)

```
python -m rag.valutazione --riepilogo docs/eval-baseline.json docs/eval-dopo-a.json docs/eval-dopo-a-solo-dosi.json docs/eval-dopo-b.json docs/eval-dopo-b-solo-dosi.json
```

| Valutazione | Fonte nei primi k | Al primo posto |
|---|---|---|
| eval-baseline.json | 6/8 | 4/8 |
| eval-dopo-a.json | 6/8 | 4/8 |
| eval-dopo-a-solo-dosi.json | 4/8 | 3/8 |
| eval-dopo-b.json | 8/8 | 6/8 |
| eval-dopo-b-solo-dosi.json | 4/8 | 3/8 |

### Con `--solo-dosi` (confronto con dopo A con lo stesso filtro)

| Domanda | Dopo A + solo-dosi | Dopo B + solo-dosi | Variazione |
|---|---|---|---|
| Farina negli gnocchi (89) | 1 | 1 | = |
| Pollo alla cacciatora (208) | — | — | = (la 208 non ha un elenco di dosi) |
| Cacciucco (455, 456) | — | — | = (risposta nella prosa) |
| Tiramisù (nessuna) | — | — | = |
| Cappelletti (7) | 1 | 1 | = (ancora il chunk 0, senza la risposta) |
| Gnocchi che si sciolgono (89) | 2 | 1 | ↑1 |
| Baccalà (510) | — | — | = (risposta nella prosa) |
| Brodo (1) | — | — | = (nessun elenco) |
| Mandorle e zucchero | 1 | 2 | ↓1 (stessa causa della tabella sopra) |

## Commento

### Ricetta 208 — Pollo alla cacciatora: da assente a 1° posto
Nella baseline il corpo della 208 non contiene la parola «cacciatora» e la ricetta non entrava nei
primi 5 (primo risultato: 209 «Pollo fritto coi pomodori», 0.701). Ora il testo indicizzato comincia
con «Titolo: Pollo alla cacciatora / Capitolo: Fritti» e il **chunk 0 della 208** (l'unico, che
contiene «mezzo bicchiere di San Giovese od altro vino rosso») esce **1° con score 0.749**. È
esattamente il caso per cui è stata pensata la modifica B.
Effetto collaterale visibile: le posizioni 2–5 sono tutte ricette con «Pollo» nel titolo (539 Pollo
ripieno arrosto, 545 Pollo vestito, 258 Pollo disossato ripieno, 209 Pollo fritto coi pomodori): il
titolo pesa molto nel vettore.

### Baccalà (510): da assente a 4° posto
La risposta («appena abbia alzato il primo bollore levatelo che già è cotto») è nel chunk 0 della 510
«Baccalà fritto», che ora esce **4° (0.754)**. Davanti ci sono altre ricette di baccalà (506 alla
fiorentina, chunk 2 e 1; 118 montebianco, chunk 1): con il titolo nel vettore, **tutte** le ricette
«Baccalà …» diventano simili alla domanda, e vince quella che parla anche di cottura. La domanda
non nomina la frittura, quindi la 510 non ha un vantaggio dal titolo.

### Tiramisù: nessuna fonte, score ancora alto
Il libro non ha il tiramisù. Il primo risultato è 372 «Pasticcio di lepre», chunk 3 (0.706; prima
609 «Pizza alla napoletana», 0.717). Lo score scende di poco ma resta nella stessa fascia delle
risposte giuste (0.72–0.77): **lo score non è una soglia** utilizzabile per dire «non c'è».

### Altri miglioramenti (con il chunk giusto)
- **Gnocchi che si sciolgono** (89): dal 5° al **1°** posto con il **chunk 1**, che contiene «si
  liquefecero»: il titolo «Gnocchi di patate» dà al chunk di prosa il contesto che gli mancava.
- **Cappelletti** (7): dal 2° al **1°** posto con il **chunk 1**, che contiene «A un mangiatore discreto
  bastano due dozzine» (dopo A con `--solo-dosi` usciva il chunk 0, senza la risposta). La differenza
  «moderato»/«discreto» non è più un problema.

### Peggioramenti e causa probabile
- **Mandorle e zucchero: dal 1° al 2° posto.** Al 1° posto sale la **613 «Dolce di mandorle»**
  (0.821), che **non è tra le fonti accettate** (contiene anche farina di patate, burro e uova), ma il
  suo **titolo coincide quasi parola per parola con la domanda**. La 785 «Mandorle tostate» è 2ª
  (0.817), poi 626 e 617. Causa: titolo uguale alle parole della domanda. Si può anche discutere se la
  613 sia una risposta accettabile; con le fonti fissate prima della prova resta un peggioramento.
- **Titoli simili che occupano la classifica** (non conteggiato come peggioramento, ma visibile):
  per il pollo alla cacciatora 4 «Pollo …» nelle posizioni 2–5; per il baccalà 4 risultati su 5 sono
  ricette di baccalà diverse dalla fonte. Con k piccolo (3) il baccalà resterebbe fuori.
- **Cacciucco** (455): stessa posizione (1°), score leggermente più basso (0.777 → 0.774); nessun
  effetto pratico.
- Con `--solo-dosi` restano perse le stesse fonti di dopo A (cacciucco, brodo): il problema lì è il
  filtro, non il testo indicizzato.

### Sintesi
La modifica B risolve i due casi in cui la parola chiave della domanda era solo nel titolo (208) o
in un chunk di prosa senza contesto (89 chunk 1, 7 chunk 1) e porta il baccalà nei primi 5: da 6/8 a
**8/8**. Il prezzo è che il titolo «attira» ricette con titolo simile, con un peggioramento misurato
(mandorle, 1° → 2°) e classifiche più affollate di ricette omonime.
