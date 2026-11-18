# Confronto delle modalità di ricerca (lezione 8)

- Data: 2026-11-18 · commit `1c07c21`
- Comando: `.\.venv\Scripts\python.exe -m rag.confronto --domande eval/domande_l8.yaml --k 5 --configurazioni base riscrittura entrambe --base-da docs/confronto-l8.json --uscita docs/confronto-l8-prompt-corretto.md`
- Configurazione base presa da `docs/confronto-l8.json` (stesso indice, nessun LLM: deterministica)
- Indice: collezione `artusi`, embedding `text-embedding-nomic-embed-text-v1.5@q8_0` · LLM `google/gemma-4-e2b`, temperatura 0.0, seed 42, reasoning_effort none
- k = 5 · candidati per query 10 · reranking su al più 10 candidati da 400 caratteri · RRF_K 60 · 14 domande da `eval/domande_l8.yaml`
- Un solo fattore cambia fra le configurazioni: la modalità (soglie disattivate). Latenza = tempo della pipeline (embedding, Qdrant, LLM) per domanda.

## Tabella riassuntiva

| Configurazione | Fonte nei primi 5 | MRR | Copertura composte | Astensioni corrette | Astensioni errate | Chiamate LLM | Latenza media (ms) | Latenza max (ms) | Ripieghi |
|---|---|---|---|---|---|---|---|---|---|
| base | 11/11 | 0.886 | 5/6 | 0/3 | 0 | 0 | 563 | 5894 | 0 |
| riscrittura | 10/11 | 0.864 | 6/6 | 0/3 | 0 | 14 | 20906 | 23496 | 0 |
| entrambe | 11/11 | 0.894 | 4/6 | 0/3 | 0 | 28 | 34855 | 53957 | 2 (reranking_id_duplicati 2) |

## Casi migliorati e peggiorati rispetto a base

### riscrittura

Migliorati (1):

- «Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà?» (composta): parti 1/2 → 2/2

Peggiorati (1):

- «Per quanto tempo si deve cuocere il baccalà?» (semplice): posizione 4 → assente

### entrambe

Migliorati (2):

- «Per quanto tempo si deve cuocere il baccalà?» (semplice): posizione 4 → 3
- «Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà?» (composta): parti 1/2 → 2/2

Peggiorati (2):

- «Quanta farina serve per gli gnocchi di patate e che vino si usa nel pollo alla cacciatora?» (composta): parti 2/2 → 1/2
- «Come si chiama il cacciucco sull'Adriatico e quanti cappelletti bastano a un mangiatore discreto?» (composta): parti 2/2 → 1/2

## Misura dettagliata per domanda

| Domanda | Tipo | Attese | base | riscrittura | entrambe |
|---|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | semplice | 89 | pos 1 | pos 1 | pos 1 |
| Che vino si usa per il pollo alla cacciatora? | semplice | 208 | pos 1 | pos 1 | pos 1 |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | semplice | 455, 456 | pos 1 | pos 1 | pos 1 |
| Qual è la ricetta del tiramisù? | senza risposta | nessuna | 5 passaggi | 5 passaggi | 1 passaggi |
| Quanti cappelletti bastano a un mangiatore moderato? | semplice | 7 | pos 1 | pos 1 | pos 1 |
| Perché gli gnocchi possono sciogliersi nell'acqua? | semplice | 89 | pos 1 | pos 1 | pos 1 |
| Per quanto tempo si deve cuocere il baccalà? | semplice | 510 | pos 4 | pos assente | pos 3 |
| Con che cosa si insaporisce il brodo? | semplice | 1 | pos 1 | pos 1 | pos 1 |
| Come si fa un dolce di mandorle e zucchero? | semplice | 617, 785, 626, 620, 687 | pos 2 | pos 2 | pos 2 |
| Quanta farina serve per gli gnocchi di patate e che vino si usa nel pollo alla cacciatora? | composta | 89, 208 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 1/2 · ripieghi: reranking_id_duplicati |
| Con che cosa si insaporisce il brodo e quanto si cuoce il baccalà? | composta | 1, 510 | pos 1, parti 1/2 | pos 1, parti 2/2 | pos 1, parti 2/2 |
| Come si chiama il cacciucco sull'Adriatico e quanti cappelletti bastano a un mangiatore discreto? | composta | 455, 456, 7 | pos 1, parti 2/2 | pos 1, parti 2/2 | pos 1, parti 1/2 |
| Qual è la ricetta della carbonara? | senza risposta | nessuna | 5 passaggi | 5 passaggi | 1 passaggi · ripieghi: reranking_id_duplicati |
| Come si prepara il sushi? | senza risposta | nessuna | 5 passaggi | 5 passaggi | 1 passaggi |
