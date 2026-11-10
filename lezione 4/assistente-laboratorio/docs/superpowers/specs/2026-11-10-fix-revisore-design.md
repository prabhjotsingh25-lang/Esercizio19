# Fix · Il revisore vede riassunto e strumenti del turno

Correzione del debito trovato nello step 3. Approvata dall'utente il 2026-11-10.

## Problema
Il revisore riceveva solo domanda, risposta e ultimi 6 messaggi di testo: bocciava risposte giuste
basate su dati che non vedeva (orario di Tokyo preso da `ora_corrente`, nome rimasto solo nel
riassunto). L'agente si correggeva con una risposta sbagliata, che restava in cronologia.

## Decisioni
- **Riassunto**: `revisore(messaggi, riassunto)` come il router; nel prompt è la prima riga del
  contesto («Riassunto: ...»).
- **Strumenti del turno**: sezione «Strumenti usati in questo turno» con una riga per chiamata
  dopo la domanda originale (anche dei tentativi precedenti nello stesso turno):
  `nome(argomenti) -> risultato`; «(nessuno)» se non ce ne sono. Risultati oltre 500 caratteri
  tagliati con «…».
- **Istruzioni**: risultati degli strumenti e riassunto sono dati attendibili; una risposta che li
  riporta è fondata; non bocciare una risposta perché si pensa che l'assistente non possa
  conoscere un dato. Resta: non verificare l'esattezza dei numeri.
- **Invariato dallo step 2**: limite `MAX_REVISIONI`, fallback «coerente» su output non valido,
  indicazione `name="revisore"`, finestra di 6 messaggi.

## Verifiche
- Offline: prompt con riassunto, strumenti del turno (non dei turni precedenti), taglio dei
  risultati lunghi, «(nessuno)», istruzioni; grafo che passa il riassunto al revisore; revisore
  simulato che giudica dal prompt: risposta basata su strumento e «Ti chiami Prabhjot» dopo la
  compressione non bocciate.
- Reali, in quest'ordine: prove veloci con il revisore vero su messaggi preparati (Tokyo con
  risultato di `ora_corrente`; nome nel riassunto); solo se passano, il flusso completo con
  «Che ore sono a Tokyo?» nella prova di compressione (niente `revisore coerente=no` al turno di
  Tokyo, nome corretto); poi le prove del router. Un fallimento del flusso completo si ripete con
  i log attivi e si diagnostica (revisore o variabilità del modello) prima di cambiare il codice.
