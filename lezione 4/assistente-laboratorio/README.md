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

**Prompt.** `/prompts` elenca i prompt (nome, descrizione, argomenti obbligatori o
facoltativi); `/prompt nome argomento=valore` ne usa uno, con le virgolette per i valori con
spazi, per esempio `/prompt spiega argomento="Model Context Protocol" livello=base` o
`/prompt riassumi_conversazione stile=sintetico`. Nella variante `mcp` i prompt sono **prompt
MCP** del server (`prompts/list`, `prompts/get`); nelle altre vengono dal catalogo locale
(`prompt.py`). Prima di chiedere il testo l'host controlla nome e argomenti rispetto
all'elenco: un prompt sconosciuto, un argomento obbligatorio mancante o uno sconosciuto
bloccano la richiesta («Prompt non valido: ...») senza chiamare il modello. Il testo ottenuto
(`Prompt> ...`) entra in cronologia come messaggio utente con `name="prompt"` e passa da
router, agente e revisore. Per questi messaggi il nodo router applica una regola fissa, senza
chiamare il modello (`router categoria=conversazione motivo=richiesta da un prompt
dell'assistente (regola) -> agente`): il contrassegno lo mette solo il comando `/prompt`, e una
riga scritta a mano la decide sempre il modello («Spiegami il pH» resta fuori ambito). `riassumi_conversazione` chiede
all'agente di riassumere i turni della sessione: il server non vede la cronologia (non c'entra
con il nodo riassunto). I prompt non sono tool e non arrivano al modello come strumenti.

**Agente come servizio HTTP.** `python -m assistente.servizio_agente` avvia l'agente come
servizio FastAPI **senza stato** su `AGENTE_HOST`:`AGENTE_PORTA` (default `127.0.0.1:8000`,
nessuna autenticazione). A ogni richiesta il chiamante manda cronologia (solo `{ruolo:
utente|assistente, testo}`), riassunto e preferenze; la risposta li restituisce aggiornati,
con gli strumenti usati (`nome`, `argomenti`, `risultato`). Endpoint: `POST /messaggi`
(domanda), `POST /prompt` (nome e argomenti: il servizio compone i messaggi, li controlla come
la CLI e mette lui il contrassegno `name="prompt"`), `GET /prompt` (elenco), `GET /stato`
(agente, modello e strumenti, con dettaglio per componente; 503 se uno non risponde).
Campi non previsti (per esempio `name`) o ruoli di sistema o di strumento → 422: un client non
può far saltare il router. Errori: modello non raggiungibile 503, strumenti non disponibili
503 (messaggio diverso, controllato prima di chiamare il modello), errore del server del
modello 502, prompt non valido 422, limite di passaggi 200 con il messaggio di limite.
Preferenze mancanti: valori predefiniti con WARNING. Contratto: `/docs`, `/openapi.json` e la
copia `docs/openapi-agente.json` (rigenerabile con `python -m assistente.servizio_agente
--openapi docs/openapi-agente.json`; un test la confronta con quella generata). Con
`AGENTE_URL` la CLI è un client dell'API (legge le preferenze e le manda a ogni richiesta);
senza, esegue l'agente nel processo con lo stesso modulo (`agente.py`).

Formato della cronologia restituita (è quella che il chiamante, e il back-end dello step 7,
salva così com'è e rimanda al turno dopo): un elenco di `{ruolo, testo}` con soltanto le domande
dell'utente e le risposte finali dell'assistente, in ordine. Restano fuori le chiamate e i
risultati degli strumenti (sono nel campo `strumenti` della risposta), le indicazioni del
revisore e le bozze che il revisore ha rifiutato: dopo un turno con revisione la cronologia ha
solo domanda e risposta finale. Le domande composte da un prompt compaiono come testo
dell'utente, senza contrassegno. Se il nodo riassunto ha compresso la conversazione, la
cronologia contiene solo i turni recenti e il resto sta nel campo `riassunto`, da rimandare
insieme. Questa cronologia passa sempre la validazione in ingresso (provato da
`test_cronologia_dopo_una_revisione_si_rimanda_senza_422`).

**Back-end con PostgreSQL.** `python -m assistente.backend` avvia su `BACKEND_HOST`:
`BACKEND_PORTA` (default `127.0.0.1:8080`, nessuna autenticazione) il servizio che salva le
conversazioni in PostgreSQL (`DATABASE_URL`, driver pg8000) e chiama l'agente su `AGENTE_URL`.
Tabelle in `src/assistente/schema.sql`, create all'avvio se mancano. Per ogni conversazione:
titolo (prime parole della prima domanda, senza chiamare il modello), preferenze (dal corpo di
`POST /conversazioni` o lette una volta dalla fonte dell'host: resource MCP o file; si cambiano
con `PUT /conversazioni/{id}/preferenze`), lo **stato dell'agente** (cronologia e riassunto,
salvati così come li restituisce l'agente e rimandati al turno dopo) e lo **storico completo**
dei messaggi (tabella `messaggi`, solo in aggiunta: la compressione dell'agente non lo tocca).
`GET /conversazioni` dà titolo e data dell'ultimo messaggio, dal più recente.

L'invio (`POST /conversazioni/{id}/messaggi`, `.../prompt`) è **sincrono**: salva la domanda,
chiama l'agente, salva e restituisce domanda e risposta. Un turno può superare i 7 minuti:
il back-end aspetta l'agente fino a `AGENTE_TIMEOUT` (default 900 s; connessione 10 s, così un
agente spento si vede subito). **Front-end e proxy dovranno avere timeout alti** (almeno
`AGENTE_TIMEOUT`), altrimenti si passerà allo streaming. Un solo turno alla volta per
conversazione: un secondo invio riceve 409.

Se l'agente non risponde o dà errore, **la domanda resta salvata** con `stato: "errore"` e il
motivo in `errore` (da mostrare); non si aggiunge nessuna risposta e lo stato dell'agente non
cambia. Codici: agente non raggiungibile 503, nessuna risposta entro il timeout 504, errori
dell'agente con il loro codice e il messaggio preceduto da `agente:` (per esempio 503
`agente: strumenti non disponibili: ...`). Per riprovare senza duplicare la domanda:
`POST /conversazioni/{id}/riprova` rimanda l'ultima domanda in errore (stesso testo o stesso
prompt); 409 se l'ultima domanda non è in errore. Una domanda nuova dopo un errore è permessa:
quella in errore resta nello storico ma non va all'agente. Un prompt non valido (422) invece
non viene salvato. Le domande rimaste `in_attesa` per un arresto del back-end passano a
`errore` al riavvio, e si possono riprovare. Contratto: `/docs`, `/openapi.json` e
`docs/openapi-backend.json` (rigenerabile con `python -m assistente.backend --openapi
docs/openapi-backend.json`); verso l'agente il back-end usa solo percorsi e campi di
`docs/openapi-agente.json`, verificati da un test.

**Front-end.** `python -m assistente.frontend` serve su `FRONTEND_HOST`:`FRONTEND_PORTA`
(default `http://127.0.0.1:8090`) una pagina di chat in HTML, CSS e JavaScript senza librerie
(`src/assistente/web/`). La pagina parla solo con il back-end, all'indirizzo `BACKEND_URL` che
legge da `/config.js` (nessun indirizzo scritto nel codice); il back-end accetta le richieste
del browser solo dall'origine `FRONTEND_ORIGINE` (CORS). Funzioni: elenco delle chat con titolo
e data dell'ultimo messaggio, nuova chat, eliminazione, messaggi e invio, «Strumenti usati»
richiudibile sotto ogni risposta, attesa con cronometro (l'invio resta disattivato; il browser
aspetta fino a `AGENTE_TIMEOUT` + 60 s), errori comprensibili e pulsante «Riprova» sull'ultima
domanda in errore. Con il back-end spento la pagina mostra «Non riesco a raggiungere il
back-end su ...» e resta utilizzabile. Usa solo gli endpoint di `docs/openapi-backend.json`
(verificato da un test).

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
  `utente://preferenze` e dei prompt (variante 03);
- `src/assistente/prompt.py`: prompt dell'utente (catalogo, comando `/prompt`, controlli);
- `src/assistente/agente.py`: agente senza stato (turno sul grafo, strumenti usati, prompt),
  usato dal servizio e dalla CLI in-process;
- `src/assistente/servizio_agente.py`: servizio HTTP dell'agente (FastAPI);
- `src/assistente/cliente_agente.py`: client dell'API dell'agente (CLI e back-end);
- `src/assistente/backend.py`: back-end FastAPI (conversazioni, turni sincroni, riprova);
- `src/assistente/frontend.py` e `src/assistente/web/`: front-end (pagina di chat e `config.js`);
- `src/assistente/archivio.py` e `schema.sql`: archivio delle conversazioni (PostgreSQL con
  pg8000, oppure in memoria per i test);
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

## Streaming della risposta

Lo streaming non è implementato in questa consegna. La risposta compare nel browser solo quando è completa: nelle prove con LM Studio e un modello locale piccolo un turno dura tra circa 100 e 450 secondi, perché ogni domanda richiede più chiamate al modello (router, agente, eventuali strumenti, revisore).

Per ora il front-end mostra la domanda subito, con un cronometro di attesa, e il back-end usa un timeout lungo verso l'agente (AGENTE_TIMEOUT).

Decisione sul revisore: con il revisore attivo la bozza dell'agente può essere rifiutata e riscritta. Si sceglie quindi di mostrare in streaming solo la risposta approvata, non la bozza, per non far comparire testo poi scartato. Percorso previsto: l'agente emette testo ed eventi degli strumenti, il back-end inoltra il flusso con Server-Sent Events e salva il messaggio completo alla fine, il front-end mostra il testo mentre arriva e segnala l'uso di uno strumento.

## Evidenze

Screenshot delle prove nel browser (Edge senza finestra) e resoconto, in `docs/evidenze/`:

- `Evoluzione9step_resoconto.pdf`: resoconto dei 9 step (decisioni, problemi risolti, avvio, limiti noti).
- `step8/0-backend-spento.png`: back-end spento, la pagina mostra l'errore e resta utilizzabile.
- `step8/1-attesa-cronometro.png`: domanda inviata, attesa con cronometro e invio disattivato.
- `step8/2-conversazione-con-strumento.png`: due turni, «Strumenti usati» con `giorni_scadenze`.
- `step8/3-dopo-riavvio-backend.png`: la stessa chat dopo il riavvio del back-end.
- `step8/4-agente-spento-errore-riprova.png`: agente spento, errore mostrato e pulsante «Riprova».
- `step8/5-riprova-in-attesa.png`: dopo il clic su «Riprova», di nuovo in attesa.
- `step8/6-riprova-riuscita.png`: risposta arrivata dopo «Riprova», senza domanda duplicata.
- `step8/giro1-router/4-agente-spento-errore-riprova.png`: primo giro, errore con «Quanto fa 137 * 49?».
- `step8/giro1-router/5-riprova-in-attesa.png`: primo giro, attesa dopo «Riprova».
- `step8/giro1-router/6-riprova-riuscita.png`: primo giro, «Riprova» riuscito ma il router rifiuta la domanda.
- `step9/1-attesa-cronometro.png`: in Docker Compose, prima domanda di una chat nuova con cronometro.
- `step9/2-conversazione-con-strumento.png`: in Docker Compose, due turni con `giorni_scadenze`.
- `step9/3-dopo-riavvio-backend.png`: in Docker Compose, la stessa chat dopo `docker compose down` e `up`.

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
| `AGENTE_HOST`, `AGENTE_PORTA` | indirizzo d'ascolto del servizio dell'agente (default `127.0.0.1`, `8000`) |
| `AGENTE_URL` | facoltativa: se c'è, la CLI usa l'API dell'agente a questo indirizzo |
| `AGENTE_TIMEOUT` | secondi di attesa di una risposta dell'agente (default 900) |
| `DATABASE_URL` | PostgreSQL del back-end, con la password (solo nel `.env`) |
| `BACKEND_URL` | indirizzo del back-end usato dalla pagina del front-end (default `http://127.0.0.1:8080`) |
| `FRONTEND_HOST`, `FRONTEND_PORTA` | indirizzo d'ascolto del front-end (default `127.0.0.1`, `8090`) |
| `FRONTEND_ORIGINE` | unica origine ammessa dal CORS del back-end (default `http://127.0.0.1:8090`) |
| `BACKEND_HOST`, `BACKEND_PORTA` | indirizzo d'ascolto del back-end (default `127.0.0.1`, `8080`) |
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

### Agente come servizio HTTP

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.servizio_agente
# in un altro terminale: stato, una domanda, la CLI come client
Invoke-RestMethod http://127.0.0.1:8000/stato
Invoke-RestMethod http://127.0.0.1:8000/messaggi -Method Post -ContentType application/json `
  -Body '{"testo": "Che ore sono a Tokyo?"}'
$env:AGENTE_URL = "http://127.0.0.1:8000"; .\.venv\Scripts\python.exe -m assistente
```

Documentazione interattiva su `http://127.0.0.1:8000/docs`.

### Back-end con PostgreSQL

PostgreSQL 16 in un container (porta host 55432: la 5432 può essere già occupata); la password
è quella di `POSTGRES_PASSWORD` nel `.env`, la stessa di `DATABASE_URL`:

```powershell
docker run -d --name assistente-postgres -e POSTGRES_USER=assistente -e POSTGRES_DB=assistente `
  -e POSTGRES_PASSWORD=<la password del .env> -p 127.0.0.1:55432:5432 `
  -v assistente-pg:/var/lib/postgresql/data postgres:16
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.servizio_agente   # agente
$env:AGENTE_URL = "http://127.0.0.1:8000"; .\.venv\Scripts\python.exe -m assistente.backend
Invoke-RestMethod http://127.0.0.1:8080/stato
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.frontend   # http://127.0.0.1:8090
```

Il driver è pg8000 (solo Python): psycopg 3 con la sua DLL è bloccato su questo Windows da un
criterio di controllo delle applicazioni. Prove con PostgreSQL vero (database `assistente_test`,
creato se manca): `.\.venv\Scripts\python.exe -m pytest -m postgres -v`.

## Avvio con Docker Compose

LM Studio resta sull'host; i container lo raggiungono tramite `host.docker.internal`
(impostato in `compose.yaml`, che sovrascrive `LMSTUDIO_BASE_URL` del `.env`).
Il `.env` serve comunque per `LMSTUDIO_MODEL`, `AMBITO_AGENTE` e `POSTGRES_PASSWORD`.

### Applicazione completa (chat web)

```powershell
docker compose up -d --build        # postgres, agente, backend, frontend
Invoke-RestMethod http://localhost:8080/stato
start http://localhost:8090         # la chat nel browser
docker compose down                 # ferma tutto; le chat restano nel volume pgdati
```

Servizi: `postgres` (postgres:16, volume `pgdati`, nessuna porta sull'host), `agente` (variante
`locale`, nessuna porta sull'host), `backend` (`127.0.0.1:8080`) e `frontend`
(`127.0.0.1:8090`). Nei container i servizi ascoltano su `0.0.0.0` e si parlano con i nomi di
Compose (`http://agente:8000`, `postgres:5432`); `BACKEND_URL` e `FRONTEND_ORIGINE` invece sono
indirizzi visti dal browser (`http://localhost:8080`, `http://localhost:8090`) e devono usare
lo stesso nome (`localhost`), altrimenti il CORS blocca le richieste: apri la chat da
`http://localhost:8090`, non da `127.0.0.1`. Il back-end parte quando PostgreSQL è pronto
(healthcheck). Nei container non c'è un `preferenze.json`: si usano le preferenze predefinite
(WARNING nel log). Questo PostgreSQL è separato da quello avviato a mano con `docker run`
(porta 55432). Log: `docker compose logs -f backend agente`.

### CLI nel container

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
Per i prompt: `/prompts`, poi `/prompt spiega argomento="Model Context Protocol" livello=base`
(nel log `prompt: prompts/list ...` e `prompt: prompts/get spiega ... -> messaggi dal server:
...`, poi `router categoria=conversazione`), `/prompt spiega livello=base` e `/prompt spiega
argomento=MCP colore=blu` (bloccati, nessuna riga `agente:`), due domande e `/prompt
riassumi_conversazione stile=sintetico` (la risposta riassume quei turni). Le prove
`test_prompt_*` fanno lo stesso con pytest.
Una risposta simulata nei test non dimostra che il modello sappia usare lo strumento:
solo queste prove lo fanno.

## Diagnosi

- **Back-end**: `GET /stato` dice se database e agente rispondono (con i componenti
  dell'agente). Una domanda con `stato: "errore"` mostra in `errore` il motivo (agente spento,
  timeout, strumenti non disponibili); si riprova con `POST /conversazioni/{id}/riprova`.
  «database non raggiungibile» all'avvio o in `/stato`: controlla il container
  (`docker ps`) e `DATABASE_URL`.

- **Servizio dell'agente**: `GET /stato` dice quale componente non risponde (`modello` o
  `strumenti`, con il motivo). La CLI client scrive «Non riesco a raggiungere l'agente su ...»
  se il servizio è spento, oppure «Errore dell'agente (503): ...» con il messaggio del servizio.

- **Calcolo fatto a mente invece che con lo strumento**: comportamento noto del modello piccolo
  (`gemma-4-e2b`) quando ci sono le preferenze in cima al prompt di sistema. Misurato su tre
  domande (12 * 7, 3 km in metri, 137 * 49): senza preferenze strumento usato 3 volte su 3, con
  le preferenze 0-2 su 3 qualunque formulazione e posizione. Nel log manca la riga `strumento
  passaggio=...`; il risultato di solito è giusto ma non è garantito. Con un modello più grande
  il problema dovrebbe ridursi; un controllo nel revisore è in valutazione.

- **`/prompt` rifiutato**: «Prompt non valido: ...» dice che cosa manca o non è previsto
  (controlla con `/prompts`); «Prompt non disponibili: ...» indica un problema del server MCP.

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
