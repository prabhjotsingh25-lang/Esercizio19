# Assistente del laboratorio — specifica Lezione 5 (strumenti e MCP)

Data: 2026-11-04 · Stato: **scritta a posteriori, da approvare**

> Questa specifica è stata scritta dopo l'implementazione, ricostruendola da codice, README,
> commit e accordi presi in chat (sessioni del 2026-11-03 e 2026-11-04). CLAUDE.md chiede di
> salvarla prima di scrivere codice: qui serve a fissare per iscritto ciò che è stato
> concordato e realizzato. Le decisioni marcate *(decisa dall'utente)* sono state prese in chat
> il 2026-11-04; per gli strumenti precedenti la firma è stata concordata in chat ma il testo
> esatto dell'accordo non è più disponibile, quindi qui è descritto ciò che il codice fa.

## 1. Intento

Lezione 5 / Blocco 5 del corso «Deep Learning e LLM»: «MCP e strumenti condivisi».
L'assistente della Lezione 4 (grafo LangGraph, modello in LM Studio, strumento `ora_corrente`)
riceve sei strumenti nuovi, e lo stesso insieme di strumenti diventa raggiungibile in tre modi
diversi. Lo scopo didattico è confrontare i canali a parità di tutto il resto: stesse
definizioni, stesso prompt, stessa cronologia; cambia solo come la chiamata arriva alla logica.

## 2. Obiettivi

1. Sei strumenti, aggiunti uno alla volta: `convertitore_unita`, `calcolatrice_sicura`,
   `giorni_scadenze`, `catalogo_locale`, `note_persistenti`, `meteo_api`.
2. Tre varianti di integrazione, scelte da configurazione (`VARIANTE_STRUMENTI`); all'agente se
   ne espone una sola per volta:
   - `locale` (01): chiamata diretta delle funzioni Python;
   - `http` (02): servizio FastAPI + wrapper HTTP (`httpx`);
   - `mcp` (03): server FastMCP (trasporto HTTP, endpoint `/mcp`) + adattatore client.
3. Una sola logica e una sola definizione per strumento (`catalogo.py`): nome, descrizione e
   schema sono identici nelle tre varianti, così la cronologia è confrontabile.
4. Per ogni strumento: test offline sui casi validi e di errore, prove reali con LM Studio,
   README aggiornato.

## 3. Non obiettivi e anti-obiettivi

Non obiettivi: workflow, RAG, interfacce grafiche, servizi cloud, framework non concordati.
`ora_corrente` resta lo strumento di riferimento e non viene rifatto.

Anti-obiettivi (fallimento anche se «funziona»):
- uno strumento che restituisce dati inventati invece di un errore esplicito;
- definizioni diverse fra le varianti (il confronto perderebbe senso);
- un test con risposta simulata presentato come prova che il modello sappia usare lo strumento;
- un'eliminazione di note senza la conferma dell'utente.

## 4. Vincoli

- Dipendenze nuove ammesse solo dal task della variante che le richiede: FastAPI e Uvicorn
  (variante `http`), FastMCP (variante `mcp`), `httpx` (wrapper http, poi riusato da
  `meteo_api`). Versioni fissate in `requirements.txt`.
- Codice sincrono; il client FastMCP, asincrono, è avvolto con `asyncio.run` per chiamata.
- Prompt di sistema neutro: non nomina strumenti, così vale per ogni variante e catalogo.
- Ogni errore è un testo che inizia con `Errore:` restituito al modello, mai un'eccezione che
  interrompe la conversazione.
- Un branch `feat/<nome>` per task, da `dev`; merge in `dev` solo dopo l'ok dell'utente.

## 5. Architettura

- `catalogo.py` → `strumenti_locali(adesso, trasporto_meteo)`: l'elenco degli strumenti, in
  quest'ordine: `ora_corrente`, `convertitore_unita`, `calcolatrice_sicura`, `giorni_scadenze`,
  `catalogo_locale`, `note_persistenti`, `meteo_api`. `adesso` (orologio) e `trasporto_meteo`
  (Open-Meteo finto) sono iniettabili per i test.
- `varianti.py` → `strumenti_per_variante(config)`: restituisce gli strumenti locali oppure
  quelli che inoltrano al servizio http o al server MCP, costruiti dalle stesse definizioni.
- `servizio_http.py` (porta 8001): `GET /strumenti` (elenco), `POST /strumenti/{nome}`.
- `server_mcp.py` (porta 8002, `/mcp`): pubblica gli strumenti del catalogo con le stesse
  descrizioni e schemi.
- Docker Compose: servizi `strumenti-http` e `strumenti-mcp` con profili `http` e `mcp`, senza
  porte pubblicate sull'host; volume `note` condiviso (`/dati/note.sqlite`).

Errori del canale (aggiunti dal wrapper o dall'adattatore, uguali per tutti gli strumenti):
servizio/server non raggiungibile, nessuna risposta entro 10 s, strumento sconosciuto,
argomenti rifiutati, risposta non valida.

## 6. Strumenti

### 6.1 `convertitore_unita(valore: number, da: str, a: str)`
Conversione fra unità di un elenco chiuso: lunghezza `mm cm m km in ft mi`, massa
`mg g kg t oz lb`, volume `ml l`, temperatura `C F K`.
Errori: unità non supportata (con elenco delle ammesse), grandezze incompatibili, valore non
finito, temperatura sotto lo zero assoluto, risultato non rappresentabile.

### 6.2 `calcolatrice_sicura(espressione: str)`
Espressioni con numeri (punto decimale), `+ - * / % **`, segno, parentesi; valutate senza
`eval`, su una whitelist dell'albero sintattico. Massimo 200 caratteri, esponente massimo 1000.
Errori: espressione vuota o troppo lunga, sintassi non valida, elemento non consentito
(variabili, funzioni, `//`, `^` con suggerimento di `**`, virgola decimale), divisione per zero,
risultato non reale o non rappresentabile.

### 6.3 `giorni_scadenze(data_inizio, data_fine=None, giorni=None, solo_lavorativi=False)`
Conta i giorni fra due date oppure calcola una scadenza (date `AAAA-MM-GG`, uno solo fra
`data_fine` e `giorni`). Con `solo_lavorativi` esclude weekend e festività nazionali italiane
dal file `dati/festivita.json` (anni 2025-2030). Risultato sempre indicato come «indicativo,
non normativo». Intervallo massimo 3650 giorni.
Errori: data non valida, entrambi o nessuno fra `data_fine` e `giorni`, intervallo troppo
grande, anno senza festività, file delle festività rovinato.

### 6.4 `catalogo_locale(testo="", categoria="", codice="")`
Ricerca nell'inventario `dati/catalogo.csv` per testo e/o categoria (senza distinguere
maiuscole e accenti, massimo 10 risultati) oppure dettaglio per codice. Nessun risultato non è
un errore: lo strumento lo dice e mostra le categorie disponibili.
Errori: nessun criterio, codice insieme ad altri criteri, testo oltre 100 caratteri, categoria
inesistente, catalogo rovinato.

### 6.5 `note_persistenti(azione, testo="", id=None, conferma=False)`
`azione` fra `aggiungi`, `elenca`, `elimina`. Note su SQLite (`NOTE_DB`, default
`note.sqlite`), che sopravvivono alla sessione; testo massimo 500 caratteri, elenco massimo 50.
Eliminazione in due passi: la prima chiamata mostra la nota e chiede conferma, solo la seconda
con `conferma=true` cancella. La richiesta di conferma è salvata nel database, così funziona
anche con http e mcp. Una chiamata con `conferma=true` senza richiesta precedente vale come
primo passo (correzione trovata con le prove reali). Gli id cancellati non vengono riusati.
La descrizione chiede di usare lo strumento anche per «ricordami di…» *(decisa dall'utente il
2026-11-04: senza, il modello salvava la nota 1 volta su 4)*.
Errori: testo mancante o troppo lungo, id mancante, nota inesistente, azione sconosciuta,
archivio non disponibile.

### 6.6 `meteo_api(luogo: str)`
Meteo attuale e previsione di oggi, domani e dopodomani da Open-Meteo, senza chiave API
*(servizio scelto dall'utente il 2026-11-04)*. Un solo argomento: `giorni` è stato tolto e la
risposta contiene sempre tre giorni, con le etichette «(oggi)» e «(domani)», perché un modello
piccolo può non passare il numero di giorni giusto *(decisa dall'utente il 2026-11-04, su
proposta)*.
Due richieste: geocoding (`language=it`, primo risultato; senza `language=it` «Roma» diventa
la Romania) e previsione (`timezone=auto`, ora locale del luogo). Nel testo compaiono regione e
paese del luogo scelto. Se il modello passa «Roma, Italia» si usa la parte prima della
virgola *(mia scelta)*. Timeout 10 s; in `http` e `mcp` la richiesta parte dal servizio.
Errori: luogo vuoto o oltre 100 caratteri, luogo non trovato, servizio non raggiungibile
(rete, timeout, codice HTTP di errore), risposta non valida (JSON rotto, campi mancanti o nulli).

## 7. Verifica

- Test offline (nessun modello, nessuna rete): per ogni strumento casi validi ed errori; per
  ogni canale gli errori di trasporto; confronto a tre varianti con lo stesso copione
  (`test_varianti.py`: stesse definizioni, stessa cronologia, stessi passaggi). Esito al
  2026-11-04: 305 test passati.
- Prove reali con LM Studio (`pytest -m reale`, 12 prove), da ripetere per variante. Esito al
  2026-11-04 su `dev`: 12/12 in `locale`, `http` e `mcp`.
- Docker: le note sopravvivono ai container e sono condivise dai tre servizi; i tre container
  raggiungono Open-Meteo. Conversazione completa con il modello dentro Docker (2026-11-04),
  domande inviate da file allo stdin del container: in `locale` meteo di domani a Roma,
  salvataggio ed elenco di una nota; in `http` e `mcp` meteo di Tokyo ed elenco delle note,
  con la nota salvata nella conversazione `locale` (volume condiviso). Tutto corretto.

## 8. Realizzazione (in ordine, un branch per task)

`feat/aggiorna-claude-md`, `feat/prompt-neutro`, `feat/convertitore-unita`,
`feat/calcolatrice-sicura`, `feat/variante-http`, `feat/giorni-scadenze`,
`feat/catalogo-locale`, `feat/variante-mcp`, `feat/note-persistenti`, `feat/meteo-api`.
Ogni canale nuovo, nel task in cui nasce, espone tutti gli strumenti già presenti nel catalogo.

## 9. Da fare

- Prova manuale da terminale con note e meteo, digitando le domande (la prova in Docker le ha
  inviate da file: stesso programma, ma senza una persona che scrive).
- Prova reale dell'eliminazione di una nota dentro Docker (provata solo fuori da Docker).
