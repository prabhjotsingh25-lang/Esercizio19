# Calibrazione delle soglie (lezione 8)

- Data: 2026-11-18 · commit `54326ab`
- Comando: `.\.venv\Scripts\python.exe -m rag.calibrazione --domande eval/domande_l8.yaml --k 5 --alta 0.73 --bassa 0.7 --configurazioni base entrambe --timeout-query 180 --uscita docs/calibrazione-l8-verifica.md`
- Score = similarità coseno (`text-embedding-nomic-embed-text-v1.5@q8_0`, collezione `artusi`), modalità base, soglie disattivate, k = 5
- Query del modello: `google/gemma-4-e2b` con tool calling (descrizione e schema di search_documents, temperatura 0.0, seed 42, timeout 180 s); domande senza query del modello: 5
- Configurazioni con LLM: modalità base, entrambe con i prompt di `rag/avanzata.py` al commit indicato

## Riepilogo: domanda intera e query del modello

| Gruppo | Domanda intera (min · mediana · max) | Query del modello (min · mediana · max) |
|---|---|---|
| Con risposta: top-1 | 0.715 · 0.766 · 0.821 | 0.734 · 0.766 · 0.823 |
| Con risposta: fonte attesa | 0.715 · 0.754 · 0.817 | 0.734 · 0.766 · 0.821 |
| Senza risposta: top-1 | 0.695 · 0.706 · 0.728 | 0.548 · 0.548 · 0.548 |

- domanda intera: intervalli del top-1 sovrapposti **sì**; domande con risposta sotto il top-1 più alto delle senza risposta: **2**
- query del modello: intervalli del top-1 sovrapposti **no**; domande con risposta sotto il top-1 più alto delle senza risposta: **0**

## Score con la domanda intera

| Domanda | Tipo | Top-1 | Score dei primi 5 | Score della fonte attesa |
|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | semplice | 0.773 | 0.773, 0.748, 0.745, 0.742, 0.719 | 0.773 (pos 1) |
| Che vino si usa per il pollo alla cacciatora? | semplice | 0.749 | 0.749, 0.706, 0.706, 0.703, 0.701 | 0.749 (pos 1) |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | semplice | 0.774 | 0.774, 0.720, 0.719, 0.701, 0.697 | 0.774 (pos 1) |
| Qual è la ricetta del tiramisù? | senza risposta | 0.706 | 0.706, 0.704, 0.699, 0.699, 0.698 | nessuna fonte |
| Quanti cappelletti bastano a un mangiatore moderato? | semplice | 0.745 | 0.745, 0.742, 0.734, 0.729, 0.726 | 0.745 (pos 1) |
| Perché gli gnocchi possono sciogliersi nell'acqua? | semplice | 0.720 | 0.720, 0.715, 0.706, 0.701, 0.699 | 0.720 (pos 1) |
| Per quanto tempo si deve cuocere il baccalà? | semplice | 0.766 | 0.766, 0.758, 0.754, 0.754, 0.753 | 0.754 (pos 4) |
| Con che cosa si insaporisce il brodo? | semplice | 0.768 | 0.768, 0.763, 0.756, 0.750, 0.749 | 0.768 (pos 1) |
| Come si fa un dolce di mandorle e zucchero? | semplice | 0.821 | 0.821, 0.817, 0.807, 0.780, 0.775 | 0.817 (pos 2) |
| Quanta farina serve per gli gnocchi di patate e che vino si usa nel pollo alla cacciatora? | composta | 0.737 | 0.737, 0.732, 0.731, 0.725, 0.724 | 0.737 (pos 1) |
| Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà? | composta | 0.766 | 0.766, 0.760, 0.746, 0.743, 0.738 | 0.766 (pos 1) |
| Come si chiama il cacciucco sull'Adriatico e quanti cappelletti bastano a un mangiatore discreto? | composta | 0.715 | 0.715, 0.710, 0.705, 0.699, 0.694 | 0.715 (pos 1) |
| Qual è la ricetta della carbonara? | senza risposta | 0.728 | 0.728, 0.711, 0.702, 0.697, 0.696 | nessuna fonte |
| Come si prepara il sushi? | senza risposta | 0.695 | 0.695, 0.690, 0.689, 0.689, 0.686 | nessuna fonte |

## Score con la query formulata dal modello

| Domanda | Query del modello | Tipo | Top-1 | Score dei primi 5 | Score della fonte attesa |
|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | farina per gnocchi patate artusi | semplice | 0.795 | 0.795, 0.772, 0.757, 0.732, 0.729 | 0.795 (pos 1) |
| Che vino si usa per il pollo alla cacciatora? | vino per pollo alla cacciatora | semplice | 0.764 | 0.764, 0.704, 0.702, 0.701, 0.700 | 0.764 (pos 1) |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | cacciucco sulle coste dell'Adriatico | semplice | 0.745 | 0.745, 0.692, 0.690, 0.687, 0.685 | 0.745 (pos 1) |
| Qual è la ricetta del tiramisù? | tiramisù | senza risposta | 0.548 | 0.548, 0.528, 0.526, 0.525, 0.523 | nessuna fonte |
| Quanti cappelletti bastano a un mangiatore moderato? | il modello non ha chiamato la ricerca | semplice | — | — | non nei primi 5 |
| Perché gli gnocchi possono sciogliersi nell'acqua? | il modello non ha chiamato la ricerca | semplice | — | — | non nei primi 5 |
| Per quanto tempo si deve cuocere il baccalà? | tempo cottura baccalà | semplice | 0.734 | 0.734, 0.731, 0.727, 0.707, 0.706 | 0.734 (pos 1) |
| Con che cosa si insaporisce il brodo? | insaporire il brodo | semplice | 0.740 | 0.740, 0.736, 0.732, 0.723, 0.717 | 0.740 (pos 1) |
| Come si fa un dolce di mandorle e zucchero? | dolce di mandorle e zucchero | semplice | 0.823 | 0.823, 0.821, 0.803, 0.779, 0.778 | 0.821 (pos 2) |
| Quanta farina serve per gli gnocchi di patate e che vino si usa nel pollo alla cacciatora? | farina per gli gnocchi di patate | composta | 0.800 | 0.800, 0.758, 0.752, 0.740, 0.726 | 0.800 (pos 1) |
| Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà? | come insaporire il brodo e tempo di cottura del baccalà | composta | 0.768 | 0.768, 0.766, 0.765, 0.757, 0.755 | 0.768 (pos 1) |
| Come si chiama il cacciucco sull'Adriatico e quanti cappelletti bastano a un mangiatore discreto? | il modello non ha chiamato la ricerca | composta | — | — | non nei primi 5 |
| Qual è la ricetta della carbonara? | errore: connessione fallita (ReadTimeout) | senza risposta | — | — | nessuna fonte |
| Come si prepara il sushi? | errore: connessione fallita (ReadTimeout) | senza risposta | — | — | nessuna fonte |

## Confronto con/senza soglie (alta 0.73, bassa 0.7)

| Variante | Fonte nei primi 5 | Astensioni corrette | Astensioni errate | Fasce restituite |
|---|---|---|---|---|
| base senza soglie | 11/11 | 0/3 | 0 | non_valutata 70 |
| base con soglie | 11/11 | 1/3 | 0 | affidabile 32, media 24 |
| entrambe senza soglie | 11/11 | 0/3 | 0 | non_valutata 31 |
| entrambe con soglie | 11/11 | 1/3 | 0 | affidabile 16, media 9 |
| base, query del modello, senza soglie | 11/11 | 0/3 | 0 | non_valutata 70 |
| base, query del modello, con soglie | 11/11 | 2/3 | 0 | affidabile 28, media 22 |
