# Confronto delle modalità di ricerca (lezione 8)

- Data: 2026-11-18 · commit `4807d6e`
- Comando: `.\.venv\Scripts\python.exe -m rag.confronto --domande eval/domande_l8.yaml --k 5 --uscita docs/confronto-l8.md`
- Indice: collezione `artusi`, embedding `text-embedding-nomic-embed-text-v1.5@q8_0` · LLM `google/gemma-4-e2b`, temperatura 0.0, seed 42, reasoning_effort none
- k = 5 · candidati per query 10 · reranking su al più 10 candidati da 400 caratteri · RRF_K 60 · 14 domande da `eval/domande_l8.yaml`
- Un solo fattore cambia fra le configurazioni: la modalità (soglie disattivate). Latenza = tempo della pipeline (embedding, Qdrant, LLM) per domanda.

## Tabella riassuntiva

| Configurazione | Fonte nei primi 5 | MRR | Copertura composte | Astensioni corrette | Astensioni errate | Chiamate LLM | Latenza media (ms) | Latenza max (ms) | Ripieghi |
|---|---|---|---|---|---|---|---|---|---|
| base | 11/11 | 0.886 | 5/6 | 0/3 | 0 | 0 | 563 | 5894 | 0 |
| riscrittura | 11/11 | 0.836 | 6/6 | 0/3 | 0 | 14 | 28008 | 30396 | 0 |
| reranking | 11/11 | 1.000 | 6/6 | 0/3 | 0 | 14 | 36775 | 41326 | 1 (reranking_id_duplicati 1) |
| entrambe | 11/11 | 0.909 | 6/6 | 0/3 | 0 | 28 | 44427 | 49034 | 0 |

## Casi migliorati e peggiorati rispetto a base

### riscrittura

Migliorati (2):

- «Per quanto tempo si deve cuocere il baccalà?» (semplice): posizione 4 → 1
- «Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà?» (composta): parti 1/2 → 2/2

Peggiorati (2):

- «Che vino si usa per il pollo alla cacciatora?» (semplice): posizione 1 → 5
- «Quanti cappelletti bastano a un mangiatore moderato?» (semplice): posizione 1 → 2

### reranking

Migliorati (3):

- «Per quanto tempo si deve cuocere il baccalà?» (semplice): posizione 4 → 1
- «Come si fa un dolce di mandorle e zucchero?» (semplice): posizione 2 → 1
- «Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà?» (composta): parti 1/2 → 2/2

Peggiorati (0):

- nessuno

### entrambe

Migliorati (2):

- «Per quanto tempo si deve cuocere il baccalà?» (semplice): posizione 4 → 2
- «Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà?» (composta): parti 1/2 → 2/2

Peggiorati (0):

- nessuno

## Misura dettagliata per domanda

| Domanda | Tipo | Attese | base | riscrittura | reranking | entrambe |
|---|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | semplice | 89 | pos 1 | pos 1 | pos 1 | pos 1 |
| Che vino si usa per il pollo alla cacciatora? | semplice | 208 | pos 1 | pos 5 | pos 1 | pos 1 |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | semplice | 455, 456 | pos 1 | pos 1 | pos 1 | pos 1 |
| Qual è la ricetta del tiramisù? | senza risposta | nessuna | 5 passaggi | 5 passaggi | 1 passaggi | 2 passaggi |
| Quanti cappelletti bastano a un mangiatore moderato? | semplice | 7 | pos 1 | pos 2 | pos 1 | pos 1 |
| Perché gli gnocchi possono sciogliersi nell'acqua? | semplice | 89 | pos 1 | pos 1 | pos 1 | pos 1 |
| Per quanto tempo si deve cuocere il baccalà? | semplice | 510 | pos 4 | pos 1 | pos 1 · ripieghi: reranking_id_duplicati | pos 2 |
| Con che cosa si insaporisce il brodo? | semplice | 1 | pos 1 | pos 1 | pos 1 | pos 1 |
| Come si fa un dolce di mandorle e zucchero? | semplice | 617, 785, 626, 620, 687 | pos 2 | pos 2 | pos 1 | pos 2 |
| Quanta farina serve per gli gnocchi di patate e che vino si usa nel pollo alla cacciatora? | composta | 89, 208 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 2/2 |
| Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà? | composta | 1, 510 | pos 1, parti 1/2 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 2/2 |
| Come si chiama il cacciucco sull'Adriatico e quanti cappelletti bastano a un mangiatore discreto? | composta | 455, 456, 7 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 2/2 |
| Qual è la ricetta della carbonara? | senza risposta | nessuna | 5 passaggi | 5 passaggi | 3 passaggi | 2 passaggi |
| Come si prepara il sushi? | senza risposta | nessuna | 5 passaggi | 5 passaggi | 1 passaggi | 2 passaggi |
