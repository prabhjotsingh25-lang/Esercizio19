# Step 2 · Revisore: la risposta è coerente con la domanda?

Secondo dei nove step. Approvata dall'utente il 2026-11-09.

## Obiettivo
Prima di restituire la risposta finale dell'agente, un nodo revisore controlla che risponda alla
domanda dell'utente (a tutte le sue parti). Se non è coerente, il motivo entra nella cronologia
come indicazione per l'agente, che riprova; un limite nello stato ferma i tentativi.

## Grafo
```
START -> router -conversazione-> modello <-> strumenti
                                   | (risposta senza tool)
                                   v
                               revisore -coerente-> END
                                   |- non coerente, sotto il limite -> indicazione -> modello
                                   '- non coerente, al limite -> END (WARNING)
        '-fuori_ambito-> rifiuto -> END        limite strumenti -> END   (non revisionati)
```

## Decisioni
- **Nodo `revisore`** (`revisore.py`): stesso modello con output strutturato
  `Revisione(motivo, coerente: bool)`, motivo prima. Riceve la domanda originale del turno, la
  risposta proposta e, come contesto, gli ultimi 6 messaggi di testo precedenti (come il router).
  Non vede strumenti né risultati: giudica la coerenza, non l'esattezza dei dati. Una richiesta
  di chiarimento pertinente e la spiegazione di un errore di uno strumento sono coerenti.
- Rivede solo le risposte finali dell'agente: non il rifiuto del router né il messaggio di
  limite degli strumenti.
- **Indicazione**: messaggio utente con `name="revisore"`: «Revisione: la risposta precedente
  non va bene perché {motivo}. Riscrivi la risposta alla domanda tenendone conto.» (un messaggio
  di sistema a metà conversazione è gestito male da molti template di chat locali).
- **Cronologia**: bozza rifiutata e indicazione **restano** in cronologia anche dopo il turno
  (nessuna rimozione). Le finestre di contesto di router e revisore saltano le indicazioni
  (`name="revisore"`), che altrimenti sembrerebbero domande dell'utente.
- **Limite**: campo `revisioni` nello stato, azzerato a ogni turno da `Sessione`; massimo
  `MAX_REVISIONI` (default 1, intero >= 1). Il revisore valuta anche l'ultima risposta; se la
  rifiuta al limite, la risposta viene restituita con WARNING nel log.
- **Passaggi degli strumenti**: il contatore non si azzera ai nuovi tentativi (limite per turno).
- **Output non valido** del revisore: vale «coerente», con WARNING.
- **Log**: `revisore coerente=no motivo=... -> agente (revisione 1/1)`,
  `revisore coerente=sì motivo=... -> fine`, WARNING `limite di N revisioni raggiunto`.
- **Compatibilità**: `costruisci_grafo(..., revisore=None, max_revisioni=1)`; senza revisore
  il grafo è quello di prima. CLI e prove reali lo passano sempre.

## Verifiche
- Offline (simulati): domanda in due parti con risposta parziale → rifiuto motivato,
  indicazione in cronologia, nuova risposta completa; risposta coerente approvata al primo
  passaggio; revisore che rifiuta sempre → stop al limite con WARNING; rifiuto e limite
  strumenti non revisionati; `revisioni` azzerato a ogni turno; fallback su output non valido.
- Reali (LM Studio): revisore vero su risposta parziale preparata (rifiuto) e completa
  (approvazione); agente vero che riceve l'indicazione `name="revisore"` e riprova; flusso
  completo con domanda in due parti; rilancio di router, note con conferma, Tokyo poi Roma.
  Il modello vero non si può costringere a una risposta parziale: il ciclo rifiuto → nuova
  risposta è garantito dai test simulati e dalle prove con risposta preparata.
