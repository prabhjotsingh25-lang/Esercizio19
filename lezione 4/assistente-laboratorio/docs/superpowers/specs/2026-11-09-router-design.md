# Step 1 · Router: conversazione o fuori ambito

Primo dei nove step che portano l'agente delle lezioni 4 e 5 verso un'applicazione completa.
Approvata dall'utente il 2026-11-09.

## Obiettivo
Prima dell'agente, un nodo LLM decide se la domanda rientra nell'ambito dell'assistente.
In ambito la domanda passa all'agente (che decide da solo se usare strumenti); fuori ambito
l'assistente risponde con un rifiuto fisso senza chiamare l'agente.

## Grafo
```
START → router ──conversazione──→ modello ⇄ strumenti → END   (resto invariato, limite compreso)
               └─fuori_ambito──→ rifiuto → END
```

## Decisioni
- **Ambito in configurazione**: variabile `AMBITO_AGENTE`, obbligatoria (manca o vuota →
  «Configurazione non valida», codice 2). Testo in `.env.example`. Le domande generiche di
  scienza senza strumenti (es. «cos'è il pH?») restano fuori ambito.
- **Nodo `router`**: stesso modello di LM Studio con output strutturato
  (`with_structured_output`), schema `Classificazione(motivo, categoria)` con
  `categoria ∈ {conversazione, fuori_ambito}`; il motivo viene prima, così il modello ragiona
  prima di decidere. Riceve l'ambito, gli ultimi 6 messaggi di testo della conversazione
  (domande e risposte, senza tool) e la domanda nuova. Non riceve gli strumenti e non valuta se
  servono. Log INFO: `router categoria=... motivo=... -> agente|rifiuto`.
- **Output non valido** (JSON rotto o assente): si tratta come `conversazione`, con WARNING nel
  log. Gli errori di connessione al modello non vengono assorbiti: li gestisce la CLI come prima.
- **Nodo `rifiuto`**: messaggio fisso in italiano, senza chiamare il modello. Domanda e rifiuto
  restano nella cronologia.
- **Nodo agente**: resta `modello`; scrive una riga INFO `agente: ...` a ogni esecuzione.
- **Compatibilità**: `costruisci_grafo(..., router=None)`; senza router il grafo è quello di
  prima. La CLI e le prove reali passano sempre il router.

## Verifiche
- Offline, con router simulato: percorso conversazione (agente eseguito), percorso fuori ambito
  (rifiuto, modello mai chiamato, nessuna riga `agente` nei log), log di categoria e motivo,
  output non valido → conversazione con WARNING, finestra di 6 messaggi senza tool.
- Reali con LM Studio: una domanda in ambito e una fuori ambito con log; rilancio delle 12
  prove reali esistenti per controllare che il router non rifiuti domande valide.

## Revisione del testo dell'ambito (2026-11-09, approvata)
Con il primo testo la suite reale ha dato 12/14: il router rifiutava «Avete un microscopio
elettronico in laboratorio?» (2 volte su 3 in una prova ripetuta: «catalogo» non richiama le
attrezzature) e lasciava passare «Cos'è il pH?» (3/3), contro la decisione presa. Il testo
attuale (in `.env.example`) descrive l'inventario con parole d'uso (attrezzature e materiali,
dove si trovano, quanti ne abbiamo) ed elenca esplicitamente che cosa è fuori ambito. Prova del
solo router, 8 domande × 5 ripetizioni: 40/40 corrette (microscopio, multimetro, meteo,
conversione e saluto passano; poesia, pH e «chi ha scoperto la gravità?» rifiutati).
Il fallimento di `test_meteo_luogo_inesistente_non_inventa` era invece dell'agente (strumento
non chiamato), non del router: variabilità del modello già nota.
