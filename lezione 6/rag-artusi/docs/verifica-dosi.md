# Verifica della regola `contiene_dosi`

- Data: 2026-11-17 · specifica: `docs/specs/modifica-a.md` §3
- Regola: un chunk «contiene dosi» se ha **almeno 2 voci** della forma `Ingrediente, quantità`
  su righe brevi (≤ 100 caratteri), per esempio «Farina di grano, grammi 150.».
- Corpus (chunking paragrafi 1200/200): **392 chunk su 1106** con dosi; **341 ricette su 790** con
  almeno un chunk con dosi.
- Campione: `python -m rag.dosi --campione 30 --seme 42` → 30 positivi e 30 negativi scelti a caso
  con seme fisso, letti e giudicati a mano uno per uno.

## Risultato

| | Corretti | Errori | Tasso |
|---|---|---|---|
| Positivi (rischio di falsi positivi) | 30 | **0 falsi positivi** | 0/30 |
| Negativi (rischio di falsi negativi) | 27 | **3 falsi negativi** | 3/30 |

**Criterio di accettazione** (al massimo 1 falso positivo su 30): **rispettato** (0/30).

### Falsi negativi trovati (non bloccanti, riportati come limiti)
1. **Quantità prima dell'ingrediente** (ricetta 294, chunk 1): elenco introdotto da «i seguenti
   ingredienti:» con righe come «Un bicchiere di brodo o mezzo soltanto.» e «Due o tre cucchiaiate di
   acquavite.». La regola cerca la forma `Ingrediente, quantità`.
2. **Elenco tagliato dal confine del chunk** (ricetta 308, chunk 1): il chunk comincia con la coda
   dell'overlap «grammi 500.» (senza nome dell'ingrediente) e contiene una sola voce intera.
3. **Elenco in prosa** (ricetta 598, chunk 1): «tre uova, tre cucchiaiate d'olio, tre di zucchero»;
   limite noto già previsto dalla specifica (§3.3).

Possibili miglioramenti futuri (non fatti, fuori dalla modifica A): riconoscere anche la forma
«quantità + di + ingrediente» nelle righe brevi; calcolare il campo sulla ricetta intera oltre che
sul chunk.

## Campione giudicato

### Positivi (30)

| # | Ricetta | Chunk | Voci trovate | Giudizio | Motivo |
|---|---|---|---|---|---|
| 1 | 702 — Migliaccio di Romagna | 1 | 11 (es. «Latte, decilitri 7.») | corretto | elenco «Ingrediente, quantità» |
| 2 | 132 — Salsa con capperi per pesce lesso | 0 | 3 (es. «Burro, grammi 50.») | corretto | elenco «Ingrediente, quantità» |
| 3 | 25 — Minestra di mattoncini di ricotta | 0 | 4 (es. «Ricotta, grammi 200.») | corretto | elenco «Ingrediente, quantità» |
| 4 | 768 — Gelato di torrone | 0 | 7 (es. «Latte, un litro.») | corretto | elenco «Ingrediente, quantità» |
| 5 | 371 — Pasticcio di carne | 0 | 7 (es. «Magro di vitella di latte, grammi 200») | corretto | elenco «Ingrediente, quantità» |
| 6 | 346 — Sformato della signora Adele | 0 | 5 (es. «Burro, grammi 100.») | corretto | elenco «Ingrediente, quantità» |
| 7 | 296 — Lombata di castrato ripiena | 0 | 3 (es. «Magro di vitella di latte, grammi 150.») | corretto | elenco «Ingrediente, quantità» |
| 8 | 177 — Fritto alla romana II | 0 | 4 (es. «Petto di pollo, grammi 50.») | corretto | elenco «Ingrediente, quantità» |
| 9 | 766 — Gelato di banane | 0 | 2 (es. «Zucchero bianco, grammi 200.») | corretto | elenco «Ingrediente, quantità» |
| 10 | 116 — Crostini di milza | 0 | 2 (es. «Milza di castrato, grammi 120.») | corretto | elenco «Ingrediente, quantità» |
| 11 | 725 — Siroppo di ribes | 1 | 3 (es. «Liquido, chilogrammi 3.») | corretto | elenco «Ingrediente, quantità» |
| 12 | 652 — Sformato di farina dolce | 0 | 9 (es. «Farina dolce, ossia di castagne, grammi 200.») | corretto | elenco «Ingrediente, quantità» |
| 13 | 98 — Ravioli all'uso di Romagna | 0 | 5 (es. «Ricotta, grammi 150.») | corretto | elenco «Ingrediente, quantità» |
| 14 | 675 — Zuppa inglese | 0 | 4 (es. «Latte, decilitri 5.») | corretto | elenco «Ingrediente, quantità» |
| 15 | 596 — Stiacciata coi siccioli | 0 | 6 (es. «Lievito, grammi 650.») | corretto | elenco «Ingrediente, quantità» |
| 16 | 30 — Minestra di bomboline di riso | 0 | 4 (es. «Riso, grammi 100.») | corretto | elenco «Ingrediente, quantità» |
| 17 | 29 — Minestra di bomboline di patate | 0 | 4 (es. «Patate, grammi 500.») | corretto | elenco «Ingrediente, quantità» |
| 18 | 105 — Spaghetti coi piselli | 0 | 3 (es. «Spaghetti, grammi 500.») | corretto | elenco «Ingrediente, quantità» |
| 19 | 281 — Tordi finti | 0 | 6 (es. «Magro di vitella di latte senz'osso per sei tordi, gr. 300.») | corretto | elenco «Ingrediente, quantità» |
| 20 | 326 — Petto di vitella di latte ripieno | 0 | 6 (es. «Petto di vitella di latte tutto in un pezzo, grammi 500.») | corretto | elenco «Ingrediente, quantità» |
| 21 | 635 — Lingue di gatto | 0 | 3 (es. «Burro, grammi 100.») | corretto | elenco «Ingrediente, quantità» |
| 22 | 684 — Sformato di savoiardi con lo zabaione | 0 | 11 (es. «Savoiardi, grammi 100.») | corretto | elenco «Ingrediente, quantità» |
| 23 | 27 — Minestra di latte composta | 0 | 6 (es. «Farina, grammi 60.») | corretto | elenco «Ingrediente, quantità» |
| 24 | 660 — Budino alla tedesca | 0 | 4 (es. «Midolla di pane sopraffine, grammi 140.») | corretto | elenco «Ingrediente, quantità» |
| 25 | 249 — Tortini di ricotta | 0 | 6 (es. «Ricotta, grammi 200.») | corretto | elenco «Ingrediente, quantità» |
| 26 | 754 — Gelato di limone | 0 | 3 (es. «Zucchero bianco fine, grammi 300.») | corretto | elenco «Ingrediente, quantità» |
| 27 | 707 — Soufflet di castagne | 0 | 6 (es. «Marroni dei più grossi, grammi 150») | corretto | elenco «Ingrediente, quantità» |
| 28 | 746 — Rosolio di Portogallo | 0 | 5 (es. «Zucchero bianco finissimo, grammi 650.») | corretto | elenco «Ingrediente, quantità» |
| 29 | 594 — Roschetti | 0 | 6 (es. «Farina, grammi 200.») | corretto | elenco «Ingrediente, quantità» |
| 30 | 285 — Cignale dolce-forte | 0 | 5 (es. «Uva passolina, grammi 40.») | corretto | elenco «Ingrediente, quantità» |

### Negativi (30)

| # | Ricetta | Chunk | Giudizio | Motivo |
|---|---|---|---|---|
| 1 | 457 — Pesce al piatto | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 2 | 598 — Stiacciata alla livornese | 1 | falso negativo (limite noto) | elenco in prosa: «tre uova, tre cucchiaiate d'olio, tre di zucchero» |
| 3 | 294 — Cosciotto o spalla di castrato in cazzaruola I | 1 | falso negativo | elenco «i seguenti ingredienti:» con la quantità prima dell'ingrediente («Un bicchiere di brodo…», «Due o tre cucchiaiate di acquavite») |
| 4 | 5 — Sugo di carne che i francesi chiamano salsa spagnuola | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 5 | 173 — Fegato di maiale fritto | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 6 | 430 — Pomodori ripieni | 1 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 7 | 349 — Pasticcio di maccheroni | 3 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 8 | 166 — Fritto di cardoni | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 9 | 239 — Pagnottelle ripiene | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 10 | 345 — Sformato di riso col sugo guarnito di rigaglie | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 11 | 99 — Ravioli alla genovese | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 12 | 87 — Maccheroni alla bolognese | 2 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 13 | 390 — Sformato di spinaci | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 14 | 91 — Pappardelle all'aretina | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 15 | 367 — Cappone in vescica | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 16 | 353 — Scaloppine alla bolognese | 1 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 17 | 623 — Cotognata | 1 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 18 | 280 — Tordi colle olive | 2 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 19 | 46 — Cuscussù | 2 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 20 | 464 — Rotelle di palombo in salsa | 1 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 21 | 524 — Arrosto di vitella di latte | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 22 | 128 — Salsa piccante II | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 23 | 388 — Cavolfiore all'uso di Romagna | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 24 | 73 — Risotto colle tinche | 2 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 25 | 539 — Pollo ripieno arrosto | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 26 | 308 — Bracioline alla Bartola | 1 | falso negativo | coda di un elenco tagliata dal confine del chunk: «grammi 500.» senza nome + una sola voce intera + «Un pizzico di prezzemolo.» |
| 27 | 675 — Zuppa inglese | 1 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 28 | 656 — Prugne giulebbate | 1 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 29 | 370 — Pasticcio freddo di cacciagione | 2 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
| 30 | 558 — Arnioni alla parigina | 0 | corretto | nessun elenco: prosa, rimandi «N. …» o quantità isolate |
