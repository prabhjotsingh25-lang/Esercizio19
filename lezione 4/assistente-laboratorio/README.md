# Assistente del laboratorio

Applicazione da terminale in Python che conversa con un modello locale servito da LM Studio.
Il flusso è un grafo LangGraph esplicito; il modello può chiedere degli strumenti, che il
programma esegue davvero:

- `ora_corrente`: orologio con fuso orario IANA esplicito, per esempio `Asia/Tokyo`;
- `convertitore_unita`: conversione fra unità di un elenco chiuso (lunghezza `mm cm m km in ft mi`,
  massa `mg g kg t oz lb`, volume `ml l`, temperatura `C F K`). Le conversioni fra grandezze
  diverse, i valori non finiti e le temperature sotto lo zero assoluto danno un errore esplicito;
- `calcolatrice_sicura`: espressioni aritmetiche (`+ - * / % **`, segno, parentesi, decimali con
  il punto) valutate senza `eval`, su una whitelist dell'albero sintattico. Variabili, funzioni e
  ogni altro costrutto sono rifiutati con un errore esplicito, come la divisione per zero e gli
  esponenti oltre 1000. Calcoli in virgola mobile, risultato a 12 cifre significative: oltre
  circa 15 cifre gli interi non sono più esatti;
- `giorni_scadenze`: conta i giorni fra due date (`AAAA-MM-GG`) oppure calcola una scadenza
  aggiungendo o togliendo giorni, di calendario o solo lavorativi (esclusi sabati, domeniche e
  festività). Le festività nazionali italiane, escluse le patronali, stanno nel file locale
  `src/assistente/dati/festivita.json` (fisse più Pasquetta, anni 2025-2030): per i giorni
  lavorativi fuori da quegli anni lo strumento dà un errore esplicito. Il risultato è sempre
  indicato come indicativo e non normativo. Per aggiungere un anno basta una riga nel file
  (un test la confronta con la data di Pasqua calcolata);
- `catalogo_locale`: cerca nell'inventario del laboratorio per testo e/o categoria (senza
  distinguere maiuscole e accenti, al massimo 10 risultati) oppure mostra il dettaglio di un
  articolo dato il codice. Se non trova nulla lo dice esplicitamente, con le categorie
  disponibili: un risultato vuoto non è un errore. L'inventario è il file
  `src/assistente/dati/catalogo.csv` (dati di esempio): colonne
  `codice;nome;categoria;descrizione;ubicazione;quantita`, separatore `;`, UTF-8; si può
  modificare con Excel salvando come «CSV UTF-8». Un file rovinato (intestazione diversa,
  codici duplicati, quantità non numeriche) dà un errore esplicito;
- `note_persistenti`: salva, elenca ed elimina note che restano fra una sessione e l'altra, in
  un database SQLite (`NOTE_DB`, default `note.sqlite`, escluso da Git e da Docker).
  L'eliminazione richiede sempre due chiamate: la prima mostra la nota e chiede conferma
  all'utente, la seconda (`conferma=true`) cancella. Se il modello passa subito
  `conferma=true`, lo strumento non cancella e chiede comunque conferma. Limite: lo strumento
  garantisce le due chiamate, non che fra le due il modello abbia davvero chiesto all'utente
  (le prove reali lo verificano). Gli id delle note cancellate non vengono riusati.
- `meteo_api`: meteo attuale e previsione di oggi, domani e dopodomani per una città, con i
  dati di [Open-Meteo](https://open-meteo.com) (gratuito, senza chiave API, serve internet).
  Il nome della città diventa coordinate con il geocoding di Open-Meteo (primo risultato; nel
  testo compaiono regione e paese, così si vede quale luogo è stato scelto); se il modello
  passa anche il paese («Roma, Italia») si usa solo la parte prima della virgola. Orari
  nell'ora locale del luogo. Città sconosciuta, servizio non raggiungibile (timeout 10 s) o
  risposta incompleta danno un errore esplicito, mai dati inventati. In `http` e `mcp` la
  richiesta a Open-Meteo parte dal processo del servizio.

La cronologia vive solo per la durata della sessione.

**Preferenze dell'utente.** A inizio sessione (e a ogni `/nuova`) l'applicazione legge una
sola volta le preferenze: `lingua` delle risposte (`it`, `en`, `fr`, `de`, `es`),
`fuso_orario` predefinito (IANA) e `stile` (`sintetico` o `dettagliato`). Nella variante `mcp`
le legge dalla **resource** MCP `utente://preferenze` del server (`resources/read`, separata
dalle chiamate agli strumenti: la resource non è un tool e non arriva a `bind_tools`); nelle
varianti `locale` e `http` legge direttamente il file `PREFERENZE_FILE` (default
`preferenze.json`; esempio versionato in `preferenze.example.json`, il file vero resta fuori da
Git). Le preferenze vanno in cima al messaggio di sistema dell'agente e il revisore le vede come
dati attendibili; il router no. Arrivano al grafo nello stato, dal chiamante, non da un nodo.
File assente o non valido, o resource non disponibile: valori predefiniti (`it`,
`Europe/Rome`, `sintetico`) con un WARNING. Con un fuso predefinito l'agente non chiede più il
luogo per «Che ore sono?».

All'inizio di ogni turno un nodo **riassunto** controlla la lunghezza della cronologia: oltre
`SOGLIA_RIASSUNTO` messaggi (default 20, strumenti compresi) i messaggi vecchi vengono tolti e
sostituiti da un riassunto, e restano intatti almeno gli ultimi `MESSAGGI_RECENTI` (default 6).
Il taglio cade solo fra un turno e l'altro (sulla domanda dell'utente più vicina), quindi una
chiamata a uno strumento non resta mai separata dal suo risultato. Il riassunto è un campo
dello stato: a ogni compressione il modello riceve il riassunto precedente e i messaggi da
togliere e ne scrive uno nuovo che li comprende; la prima riga riporta i fatti sull'utente
(«Utente: si chiama ...»). Nel riassunto entrano solo domande e risposte
accettate: niente strumenti, indicazioni del revisore e bozze scartate. L'agente lo riceve in
coda al messaggio di sistema, il router come prima riga del contesto. Sotto la soglia il modello
non viene chiamato; un riassunto vuoto lascia la cronologia com'è (WARNING nel log).

Prima dell'agente un **router** decide se la domanda rientra nell'ambito dell'assistente,
descritto in configurazione (`AMBITO_AGENTE`). Il router usa lo stesso modello con output
strutturato (motivo e categoria `conversazione` / `fuori_ambito`) e vede l'ambito, gli ultimi
6 messaggi di testo della conversazione e la domanda; non vede gli strumenti e non decide se
servono, lo fa l'agente come prima. Le domande fuori ambito ricevono un rifiuto fisso senza
che l'agente venga chiamato; domanda e rifiuto restano nella cronologia. Se l'output del
router non è valido, la domanda passa all'agente (con un WARNING nel log).

Prima di restituirla, un **revisore** controlla che la risposta finale dell'agente risponda alla
domanda, a tutte le sue parti (output strutturato: motivo e `coerente` sì/no). Vede la domanda
originale del turno, la risposta proposta, gli ultimi 6 messaggi di testo e il riassunto come
contesto, e gli strumenti usati nel turno con i loro risultati (`nome(argomenti) -> risultato`,
tagliati a 500 caratteri). Risultati degli strumenti e riassunto sono per lui dati attendibili:
non boccia una risposta perché pensa che l'assistente non possa conoscere l'ora o il nome
dell'utente. Giudica la coerenza e non l'esattezza dei dati (una richiesta di chiarimento
pertinente è coerente). Se la risposta non è coerente, il motivo entra nella
cronologia come messaggio utente con `name="revisore"` e l'agente riprova; bozza rifiutata e
indicazione restano in cronologia. Dopo `MAX_REVISIONI` nuovi tentativi (default 1) si
restituisce l'ultima risposta, con un WARNING nel log. Il rifiuto del router e il messaggio di
limite degli strumenti non vengono revisionati; un output non valido del revisore vale
«coerente» (WARNING nel log):

```
START -> riassunto -> router --conversazione--> modello <-> strumenti
                             |                     | risposta finale
                             |                     v
                             |                  revisore --coerente / limite--> END
                             |                     '--non coerente--> indicazione -> modello
                             '--fuori_ambito--> rifiuto -> END
```

Gli strumenti si possono raggiungere con varianti di integrazione diverse, scelte da
configurazione (`VARIANTE_STRUMENTI`); all'agente ne viene esposta una sola per volta:

- `locale` (01, default): le funzioni Python sono chiamate direttamente dal programma;
- `http` (02): gli strumenti girano in un servizio FastAPI e l'agente li chiama tramite un
  wrapper HTTP (`httpx`);
- `mcp` (03): gli strumenti sono pubblicati da un server FastMCP (trasporto HTTP, endpoint
  `/mcp`) e l'agente li chiama tramite un adattatore basato sul client FastMCP. Ogni chiamata
  apre e chiude una sessione MCP: semplice, al costo di qualche richiesta in più.

Le definizioni (nome, descrizione, schema degli argomenti) vengono tutte dallo stesso catalogo,
quindi il modello vede gli stessi strumenti e lo stesso prompt di sistema in ogni variante:
cambia solo il canale.

Struttura:

- `src/assistente/config.py`: lettura e validazione delle variabili d'ambiente;
- `src/assistente/catalogo.py`: catalogo degli strumenti, fonte unica delle definizioni;
- `src/assistente/varianti.py`: scelta della variante da configurazione;
- `src/assistente/servizio_http.py`: servizio FastAPI degli strumenti (variante 02);
- `src/assistente/variante_http.py`: wrapper HTTP verso il servizio (variante 02);
- `src/assistente/server_mcp.py`: server FastMCP degli strumenti e della resource
  `utente://preferenze` (variante 03);
- `src/assistente/preferenze.py`: preferenze dell'utente (schema, validazione, file, prompt);
- `src/assistente/variante_mcp.py`: adattatore client MCP (variante 03);
- `src/assistente/strumenti.py`: strumento orologio;
- `src/assistente/convertitore.py`: strumento convertitore di unità;
- `src/assistente/calcolatrice.py`: strumento calcolatrice sicura;
- `src/assistente/scadenze.py` e `dati/festivita.json`: strumento giorni e scadenze;
- `src/assistente/inventario.py` e `dati/catalogo.csv`: strumento catalogo locale;
- `src/assistente/note.py`: strumento note persistenti (SQLite);
- `src/assistente/meteo.py`: strumento meteo (Open-Meteo, via `httpx`);
- `src/assistente/router.py`: router (ambito della domanda, output strutturato);
- `src/assistente/revisore.py`: revisore (coerenza della risposta, output strutturato);
- `src/assistente/riassunto.py`: riassunto della cronologia (punto di taglio, riassuntore);
- `src/assistente/contesto.py`: finestra dei messaggi di testo usata da router, revisore e
  riassunto;
- `src/assistente/grafo.py`: grafo LangGraph (stato, nodi, instradamento);
- `src/assistente/sessione.py`: cronologia della conversazione;
- `src/assistente/modello.py`: collegamento a LM Studio (API compatibile con OpenAI);
- `src/assistente/cli.py` e `__main__.py`: interfaccia da terminale e avvio;
- `tests/`: test automatici (offline) e prove reali (`reale`).

## Requisiti

- Windows con PowerShell; Python 3.13.
- LM Studio avviato sul computer host, con un modello caricato e il server locale attivo
  (porta 1234).
- Docker Desktop, solo per l'avvio con Docker Compose.

Tutti i comandi vanno eseguiti da `assistente-laboratorio/`, senza attivare l'ambiente virtuale.

## Configurazione

Crea il file `.env` (resta fuori da Git) a partire dall'esempio:

```powershell
Copy-Item .env.example .env
```

Variabili:

| Variabile | Significato |
| --- | --- |
| `LMSTUDIO_BASE_URL` | indirizzo del server, es. `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | identificativo del modello, così come lo restituisce il server |
| `AMBITO_AGENTE` | obbligatoria: descrizione di che cosa fa l'assistente, usata dal router (testo di esempio in `.env.example`, fra virgolette) |
| `MAX_PASSAGGI_STRUMENTO` | passaggi massimi di strumento per domanda (default 3), contati su tutti i tentativi |
| `MAX_REVISIONI` | nuovi tentativi che il revisore può chiedere per domanda (default 1) |
| `SOGLIA_RIASSUNTO` | oltre questo numero di messaggi quelli vecchi diventano un riassunto (default 20) |
| `MESSAGGI_RECENTI` | messaggi recenti che restano intatti, almeno (default 6, minore di `SOGLIA_RIASSUNTO`) |
| `LOG_LEVEL` | livello dei log su stderr (default `INFO`) |
| `VARIANTE_STRUMENTI` | `locale` (default), `http` oppure `mcp` |
| `STRUMENTI_HTTP_URL` | indirizzo del servizio strumenti, obbligatorio con `http`, es. `http://localhost:8001` |
| `STRUMENTI_MCP_URL` | indirizzo del server MCP, obbligatorio con `mcp`, es. `http://localhost:8002/mcp` |
| `PREFERENZE_FILE` | file JSON delle preferenze (default `preferenze.json`). Nella variante `mcp` conta quello del processo del server MCP |
| `NOTE_DB` | file SQLite delle note (default `note.sqlite`). Nelle varianti `http` e `mcp` conta quello del processo del servizio |

L'identificativo del modello va letto dal server, non inventato:

```powershell
Invoke-RestMethod http://localhost:1234/v1/models
```

Copia il valore del campo `id` in `LMSTUDIO_MODEL`.

## Avvio locale

Creazione dell'ambiente virtuale e installazione delle dipendenze (con quelle di test):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Avvio:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente
```

Comandi nell'applicazione: `/nuova` avvia una nuova conversazione, `/esci` termina
(anche Ctrl+C o fine input). Risposte su stdout, log su stderr. All'avvio il log indica la
variante in uso e gli strumenti esposti.

### Variante `http` (servizio FastAPI)

In un secondo terminale avvia il servizio degli strumenti (ascolta solo su `127.0.0.1`):

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m uvicorn assistente.servizio_http:app --port 8001
```

Controllo rapido del servizio:

```powershell
(Invoke-RestMethod http://localhost:8001/strumenti).nome
Invoke-RestMethod -Method Post http://localhost:8001/strumenti/convertitore_unita -ContentType "application/json" -Body '{"valore": 1.5, "da": "km", "a": "m"}'
```

Poi, nel `.env`, imposta `VARIANTE_STRUMENTI=http` e `STRUMENTI_HTTP_URL=http://localhost:8001`
e avvia l'assistente come sopra.

### Variante `mcp` (server FastMCP)

In un secondo terminale avvia il server MCP (ascolta solo su `127.0.0.1`, endpoint `/mcp`):

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m uvicorn assistente.server_mcp:app --port 8002
```

Poi, nel `.env`, imposta `VARIANTE_STRUMENTI=mcp` e `STRUMENTI_MCP_URL=http://localhost:8002/mcp`
e avvia l'assistente come sopra. Nel log del server ogni chiamata di strumento compare come tre
richieste `POST /mcp` (apertura della sessione, notifica, chiamata).

## Avvio con Docker Compose

LM Studio resta sull'host; il container lo raggiunge tramite `host.docker.internal`
(impostato in `compose.yaml`, che sovrascrive `LMSTUDIO_BASE_URL` del `.env`).
Il `.env` serve comunque per `LMSTUDIO_MODEL`.

```powershell
docker compose build
docker compose run --rm assistente
```

Il secondo comando richiede un terminale interattivo. Senza terminale (prova automatica
con input da pipe):

```powershell
"Che ore sono a Tokyo?`nE a Roma?`n/esci" | docker compose run --rm -T assistente
```

Variante `http`: il servizio `strumenti-http` (stessa immagine, comando `uvicorn`) parte solo
con il profilo `http`, non pubblica porte sull'host ed è raggiungibile dall'assistente come
`http://strumenti-http:8001` (impostato in `compose.yaml`). Senza profilo l'avvio resta quello
di sopra, con la variante `locale`.

```powershell
docker compose --profile http build
"Quanto fa (17 + 4) * 3?`n/esci" | docker compose --profile http run --rm -T -e VARIANTE_STRUMENTI=http assistente
docker compose --profile http down
```

L'ultimo comando ferma il servizio rimasto attivo in background.

Variante `mcp`: allo stesso modo, il servizio `strumenti-mcp` parte solo con il profilo `mcp` ed
è raggiungibile dall'assistente come `http://strumenti-mcp:8002/mcp`.

```powershell
docker compose --profile mcp build
"Quanto fa (17 + 4) * 3?`n/esci" | docker compose --profile mcp run --rm -T -e VARIANTE_STRUMENTI=mcp assistente
docker compose --profile mcp down
```

## Test automatici

Non richiedono LM Studio attivo né internet (le prove `reale` sono escluse di default;
Open-Meteo è simulato con `httpx.MockTransport`):

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Prove reali

Richiedono LM Studio attivo e `.env` configurato (le prove del meteo anche internet); si
attivano esplicitamente:

```powershell
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Le prove usano la variante indicata da `VARIANTE_STRUMENTI`. Per la variante `http`, con il
servizio avviato:

```powershell
$env:VARIANTE_STRUMENTI = "http"; $env:STRUMENTI_HTTP_URL = "http://localhost:8001"
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Nel log del servizio devono comparire le richieste `POST /strumenti/...`. Per la variante `mcp`,
con il server MCP avviato:

```powershell
$env:VARIANTE_STRUMENTI = "mcp"; $env:STRUMENTI_MCP_URL = "http://localhost:8002/mcp"
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Le prove reali dipendono da un modello non deterministico: un fallimento isolato va ripetuto
prima di attribuirlo al codice. Per esempio la vecchia `test_ora_senza_luogo` è fallita una
volta su 13 esecuzioni (il modello ha tentato una chiamata con argomenti non validi, fermata
dalla validazione prima di raggiungere il server), con risultati identici nelle varianti.
Dallo step 4 è sostituita da `test_ora_senza_luogo_usa_il_fuso_predefinito`: con un fuso
predefinito nelle preferenze l'agente non chiede più il luogo, usa quel fuso.

Prova manuale: avvia l'assistente (locale o Docker), chiedi «Che ore sono a Tokyo?» e poi
«E a Roma?». Sui log (stderr) devono comparire due chiamate `ora_corrente`, con
`Asia/Tokyo` e poi `Europe/Rome`, e le risposte devono usare l'ora restituita.
Per il convertitore: chiedi «Quanti metri sono 1,5 km?»; sui log deve comparire
`convertitore_unita` con risultato `1.5 km = 1500 m`. Per la calcolatrice: chiedi
«Quanto fa (17 + 4) * 3?»; sui log deve comparire `calcolatrice_sicura` con risultato `= 63`.
Per giorni e scadenze: chiedi «Quanti giorni mancano a Natale di quest'anno? Sono in Italia.»;
sui log devono comparire prima `ora_corrente` (per la data di oggi) e poi `giorni_scadenze`.
Per il catalogo: chiedi «Avete un multimetro? Dove si trova?» (la risposta deve citare
l'Armadio A) e «Avete un microscopio elettronico?» (lo strumento risponde «Nessun articolo
trovato» e il modello non deve inventarlo).
Per le note: «Ricordami di comprare i fusibili», poi «Che note ho?», poi «Cancella la nota 1»:
al primo «Cancella» la nota non deve sparire e l'assistente deve chiedere conferma; dopo il
«sì» la nota viene eliminata. Le prove reali usano un database temporaneo nella variante
`locale`; nelle varianti `http` e `mcp` scrivono nel database del servizio.
Per il meteo: chiedi «Che tempo farà domani a Roma?»; sui log deve comparire `meteo_api` e la
risposta deve usare la riga «(domani)». Con «Che tempo fa a Montefracassone?» (luogo
inesistente) lo strumento risponde «Errore: luogo ... non trovato» e il modello non deve
inventare temperature.
Per il router: chiedi «Che ore sono a Tokyo?» e poi «Scrivimi una poesia sul mare.». Sui log
deve comparire `router categoria=conversazione ... -> agente` seguito da `agente: chiamata al
modello`, poi `router categoria=fuori_ambito ... -> rifiuto` seguito da `rifiuto: ...` e nessuna
riga `agente:`; la seconda risposta è il messaggio di rifiuto fisso. Le prove reali
`test_router_*` controllano gli stessi log; tutte le altre prove reali passano dal router, quindi
verificano anche che non rifiuti domande valide.
Per il revisore: chiedi «Che ore sono a Tokyo e quanto fa (17 + 4) * 3?». Sui log deve
comparire `revisore coerente=sì ... -> fine` se la risposta copre entrambe le parti, oppure
`revisore coerente=no motivo=... -> agente (revisione 1/1)` seguito da una nuova chiamata
all'agente. Il modello vero non si può costringere a una risposta parziale: il ciclo rifiuto →
nuova risposta è provato dai test simulati, da `test_revisore_rifiuta_una_risposta_parziale`
(revisore vero su una risposta preparata) e da `test_agente_riprova_dopo_l_indicazione_del_revisore`
(agente vero che riceve l'indicazione).
Per il riassunto: avvia con `SOGLIA_RIASSUNTO=6` e `MESSAGGI_RECENTI=2`, scrivi «Ciao, mi chiamo
...», poi tre domande (per esempio «Quanto fa 12 * 7?», «Converti 3 km in metri.», «Che ore
sono a Tokyo?»), poi «Come mi chiamo?». Al primo turno il log mostra `riassunto: 1 messaggi, sotto la soglia di 6: nessuna
chiamata`; quando la soglia viene superata compare `riassunto: N messaggi, soglia 6 ->
riassunti X, tenuti Y` e la risposta finale deve contenere il nome, che ormai sta solo nel
riassunto. Al turno di Tokyo non deve comparire `revisore coerente=no`. Le prove reali
`test_riassunto_*` fanno lo stesso; `test_revisore_approva_l_ora_presa_dallo_strumento` e
`test_revisore_approva_il_nome_preso_dal_riassunto` provano il revisore vero su messaggi
preparati (un minuto circa).
Per le preferenze: scrivi in `preferenze.json` `{"fuso_orario": "America/New_York"}` e chiedi
«Che ore sono?»: nel log compare una sola riga `preferenze: ... -> lingua=it
fuso_orario=America/New_York stile=sintetico` prima della domanda (con la variante `mcp`:
`preferenze: resources/read utente://preferenze (mcp) -> ...`, con il file del server), poi
`ora_corrente` con `America/New_York`, senza domande sul luogo. Cambiando `lingua` o `stile`
nel file, la sessione successiva (`/nuova` o un nuovo avvio) risponde di conseguenza. Le prove
`test_ora_senza_luogo_usa_il_fuso_predefinito` e
`test_lingua_e_stile_valgono_dalla_sessione_successiva` fanno lo stesso con un file temporaneo.
Una risposta simulata nei test non dimostra che il modello sappia usare lo strumento:
solo queste prove lo fanno.

## Diagnosi

- **Preferenze ignorate**: nel log a inizio sessione `preferenze: ... non disponibili (...):
  uso le predefinite` (WARNING) spiega il motivo: file assente, JSON o campo non valido (per
  esempio un fuso orario inesistente), server MCP non raggiungibile. In Docker, senza un file
  montato, si usano le predefinite.

- **LM Studio spento o server non avviato**: l'assistente scrive «Non riesco a raggiungere
  LM Studio su ...: controlla che il server sia avviato». Avvia il server locale in LM Studio.
- **Modello errato**: provato con `LMSTUDIO_MODEL=modello-inesistente` e LM Studio attivo:
  il server non ha dato errore, ha risposto comunque (con il modello caricato). Un
  identificativo sbagliato quindi può passare inosservato: se il modello che risponde non è
  quello atteso, confronta `LMSTUDIO_MODEL` con `Invoke-RestMethod http://localhost:1234/v1/models`.
- **Configurazione mancante**: l'avvio termina con «Configurazione non valida: ...» (codice 2);
  controlla `.env` (serve anche `AMBITO_AGENTE`: copiala da `.env.example`). Con `VARIANTE_STRUMENTI=http` serve anche `STRUMENTI_HTTP_URL`, con `mcp`
  serve `STRUMENTI_MCP_URL`.
- **Domanda valida rifiutata dal router**: nel log `router categoria=fuori_ambito motivo=...`
  spiega la scelta. Se capita spesso per un tipo di domanda, descrivilo meglio in
  `AMBITO_AGENTE`. Con `output del router non valido` nel log, il modello non ha prodotto una
  classificazione e la domanda è passata comunque all'agente.
- **Risposta rifiutata dal revisore**: nel log `revisore coerente=no motivo=...` spiega il
  rifiuto. `limite di N revisioni raggiunto` (WARNING) indica che anche l'ultima risposta non
  è stata giudicata coerente ed è stata restituita comunque. Ogni revisione costa almeno due
  chiamate al modello: con un modello lento si può tenere `MAX_REVISIONI=1`.
- **L'assistente dimentica qualcosa di detto molto prima**: con `LOG_LEVEL=DEBUG` la riga
  `riassunto: testo=...` mostra che cosa è rimasto della parte vecchia della conversazione.
  `riassunto vuoto` (WARNING) indica che il modello non ha prodotto il riassunto: i messaggi
  restano e si riprova al turno dopo. Per tenere più messaggi intatti alza `MESSAGGI_RECENTI`
  o `SOGLIA_RIASSUNTO`.
- **Servizio strumenti spento (variante `http`)**: l'assistente non si blocca; lo strumento
  restituisce al modello «Errore: servizio strumenti non raggiungibile su ...», e il modello
  lo riferisce. Avvia il servizio (o, in Docker, usa `--profile http`).
- **Server MCP spento (variante `mcp`)**: come sopra, lo strumento restituisce «Errore: server MCP
  non raggiungibile su ...». Avvia il server (o, in Docker, usa `--profile mcp`).
- **Note non disponibili**: «Errore: archivio delle note non disponibile» se la cartella di
  `NOTE_DB` non esiste o il file non è un database SQLite. In Docker le note stanno nel volume
  `note` (`/dati/note.sqlite`); `docker compose down -v` lo cancella insieme alle note.
- **Meteo non disponibile**: «Errore: servizio meteo non raggiungibile» se manca internet,
  Open-Meteo è lento (oltre 10 s) o risponde con un errore (per esempio troppe richieste);
  «Errore: risposta del servizio meteo non valida» se la risposta è incompleta. Verifica con
  `Invoke-RestMethod "https://geocoding-api.open-meteo.com/v1/search?name=Roma&count=1&language=it"`
  (senza `language=it` «Roma» viene cercata in inglese e il primo risultato è la Romania).
- **Il container non raggiunge l'host**: verifica che `compose.yaml` contenga
  `extra_hosts: host.docker.internal:host-gateway` e che LM Studio sia in ascolto sulla
  porta 1234. Solo se non basta, in LM Studio puoi attivare «Serve on Local Network».
  Attenzione: così l'API di LM Studio è esposta a tutta la rete locale; riportala allo
  stato precedente appena finito. Nelle prove di questo progetto non è stato necessario.
- **Più dettagli**: imposta `LOG_LEVEL=DEBUG` nel `.env` (o, in locale,
  `$env:LOG_LEVEL = "DEBUG"`) e riavvia.
