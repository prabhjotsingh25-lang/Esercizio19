# Valutazione dopo la modifica A (`contiene_dosi`, `--solo-dosi`)

- Data: 2026-11-17
- Modello: `text-embedding-nomic-embed-text-v1.5@q8_0` · collezione `artusi`
- Chunking: paragrafi, 1200 caratteri, overlap 200 · k = 5
- Confronto con `docs/eval-baseline.json` (stesse 9 domande; righe salvate in
  `docs/eval-dopo-a.json` e `docs/eval-dopo-a-solo-dosi.json`)

## Aggiornamento dei punti esistenti (senza ricalcolare gli embedding)

`python -m rag.ingestion --solo-payload` sui punti creati prima della modifica:

| | Prima | Dopo |
|---|---|---|
| Punti nella collezione | 1106 | 1106 |
| Punti (su 20 a caso) con `contiene_dosi` | 0 | 20 |
| Vettori identici (stessi 20 punti) | — | 20 su 20 |
| Indici del payload | `capitolo` (keyword) | `capitolo` (keyword), `contiene_dosi` (bool) |
| Chunk con `contiene_dosi` vero | — | 392 |
| Durata | — | 2,1 s (un'ingestion completa con embedding: 130–135 s) |

## 1. Senza filtro: identica alla baseline

| Domanda | Fonte attesa | Posizione baseline | Posizione | Variazione | Score migliore |
|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 1 | 1 | = | 0.769 |
| Che vino si usa per il pollo alla cacciatora? | 208 | — | — | = | 0.701 |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 1 | 1 | = | 0.777 |
| Qual è la ricetta del tiramisù? | nessuna | — | — | = | 0.717 |
| Quanti cappelletti bastano a un mangiatore moderato? | 7 | 2 | 2 | = | 0.730 |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 5 | 5 | = | 0.725 |
| Per quanto tempo si deve cuocere il baccalà? | 510 | — | — | = | 0.750 |
| Con che cosa si insaporisce il brodo? | 1 | 1 | 1 | = | 0.752 |
| Come si fa un dolce di mandorle e zucchero? | 617, 785, 626, 620, 687 | 1 | 1 | = | 0.847 |

Fonte trovata nei primi 5: **6/8** (al primo posto 4/8), come la baseline. Posizioni, primi risultati e score sono
identici: è la conferma che la modifica A non ha toccato i vettori.

## 2. Con `--solo-dosi`

| Domanda | Fonte attesa | Posizione baseline | Posizione | Variazione | Score migliore | Primo risultato |
|---|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 1 | 1 | = | 0.769 | 89 — Gnocchi di patate (chunk 0) |
| Che vino si usa per il pollo alla cacciatora? | 208 | — | — | = | 0.685 | 727 — Marena |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 1 | — | **persa** | 0.671 | 502 — Pasticcio di magro |
| Qual è la ricetta del tiramisù? | nessuna | — | — | = | 0.717 | 609 — Pizza alla napoletana |
| Quanti cappelletti bastano a un mangiatore moderato? | 7 | 2 | 1 | ↑1 (*) | 0.729 | 7 — Cappelletti all'uso di Romagna (chunk 0) |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 5 | 2 | **↑3** | 0.705 | 729 — Orzata |
| Per quanto tempo si deve cuocere il baccalà? | 510 | — | — | = | 0.738 | 512 — Baccalà in salsa bianca |
| Con che cosa si insaporisce il brodo? | 1 | 1 | — | **persa** | 0.706 | 87 — Maccheroni alla bolognese |
| Come si fa un dolce di mandorle e zucchero? | 617, 785, 626, 620, 687 | 1 | 1 | = | 0.847 | 785 — Mandorle tostate |

Fonte trovata nei primi 5: **4/8** · al primo posto: 3/8 (totali calcolati dai JSON, vedi sotto).

### Totali (generati dai dati)

```
python -m rag.valutazione --riepilogo docs/eval-baseline.json docs/eval-dopo-a.json docs/eval-dopo-a-solo-dosi.json
```

| Valutazione | Fonte nei primi k | Al primo posto |
|---|---|---|
| eval-baseline.json | 6/8 | 4/8 |
| eval-dopo-a.json | 6/8 | 4/8 |
| eval-dopo-a-solo-dosi.json | 4/8 | 3/8 |

## Commento: dove il filtro aiuta e dove fa perdere la fonte

**Aiuta quando la risposta sta vicino all'elenco degli ingredienti.**
- *Farina degli gnocchi* (89): resta al 1° posto. La risposta («Farina di grano, grammi 150») è
  proprio nell'elenco, e il filtro toglie di mezzo i chunk di prosa che potrebbero scavalcarla.
- *Gnocchi che si sciolgono* (89): sale dal 5° al 2° posto. Il chunk 0 della 89 contiene sia l'elenco
  sia l'aneddoto della signora («intrisi con poca farina … si liquefecero»): togliendo i chunk senza
  dosi, la concorrenza diminuisce.
- *Mandorle e zucchero*: invariata al 1° posto (le ricette attese sono quasi solo elenco).

**Fa perdere la fonte quando la risposta sta nella prosa.**
- *Cacciucco* (455/456): **persa**. Il passo «sostituita dalla voce brodetto» è nella prosa
  introduttiva della 455, in un chunk senza elenco: il filtro lo esclude a priori.
- *Brodo* (1): **persa**. La ricetta del brodo non ha un elenco di ingredienti con quantità (il
  «mazzettino di erbe aromatiche» è descritto in prosa), quindi nessun suo chunk passa il filtro.
- (*) *Cappelletti* (7): il guadagno è **solo apparente**. Con il filtro esce la ricetta 7 al primo
  posto, ma con il **chunk 0** (l'elenco del ripieno), che **non contiene la risposta**: «A un
  mangiatore discreto bastano due dozzine» sta nei chunk 1 e 2, di prosa, che il filtro esclude. La
  valutazione conta la ricetta, non il chunk, e qui sovrastima il risultato.

**Neutro.**
- *Pollo alla cacciatora* (208) e *baccalà* (510): la fonte manca sia prima sia dopo. La 208 non ha
  un elenco (il vino è nella prosa: «mezzo bicchiere di San Giovese»), quindi con il filtro non
  potrebbe mai uscire; per il baccalà la risposta («al primo bollore … già è cotto») è nella prosa della
  510.
- *Tiramisù*: nessuna fonte, e il primo risultato ha ancora uno score alto (0.717): il filtro non
  aiuta a riconoscere che la risposta non c'è.

**Conclusione.** `--solo-dosi` è utile come filtro **scelto dall'utente** per domande sulle quantità
(«quanta farina…», «quanto zucchero…»), non come impostazione predefinita: su 8 domande con fonte
ne fa perdere 2 e una terza la «trova» con il chunk sbagliato. La regola stessa è affidabile
(0 falsi positivi su 30, vedi `docs/verifica-dosi.md`).
