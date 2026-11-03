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
  (un test la confronta con la data di Pasqua calcolata).

La cronologia vive solo per la durata della sessione.

Gli strumenti si possono raggiungere con varianti di integrazione diverse, scelte da
configurazione (`VARIANTE_STRUMENTI`); all'agente ne viene esposta una sola per volta:

- `locale` (01, default): le funzioni Python sono chiamate direttamente dal programma;
- `http` (02): gli strumenti girano in un servizio FastAPI e l'agente li chiama tramite un
  wrapper HTTP (`httpx`).

Le definizioni (nome, descrizione, schema degli argomenti) vengono tutte dallo stesso catalogo,
quindi il modello vede gli stessi strumenti e lo stesso prompt di sistema in ogni variante:
cambia solo il canale.

Struttura:

- `src/assistente/config.py`: lettura e validazione delle variabili d'ambiente;
- `src/assistente/catalogo.py`: catalogo degli strumenti, fonte unica delle definizioni;
- `src/assistente/varianti.py`: scelta della variante da configurazione;
- `src/assistente/servizio_http.py`: servizio FastAPI degli strumenti (variante 02);
- `src/assistente/variante_http.py`: wrapper HTTP verso il servizio (variante 02);
- `src/assistente/strumenti.py`: strumento orologio;
- `src/assistente/convertitore.py`: strumento convertitore di unità;
- `src/assistente/calcolatrice.py`: strumento calcolatrice sicura;
- `src/assistente/scadenze.py` e `dati/festivita.json`: strumento giorni e scadenze;
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
| `MAX_PASSAGGI_STRUMENTO` | passaggi massimi di strumento per domanda (default 3) |
| `LOG_LEVEL` | livello dei log su stderr (default `INFO`) |
| `VARIANTE_STRUMENTI` | `locale` (default) oppure `http` |
| `STRUMENTI_HTTP_URL` | indirizzo del servizio strumenti, obbligatorio con `http`, es. `http://localhost:8001` |

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

## Test automatici

Non richiedono LM Studio attivo (le prove `reale` sono escluse di default):

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Prove reali

Richiedono LM Studio attivo e `.env` configurato; si attivano esplicitamente:

```powershell
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Le prove usano la variante indicata da `VARIANTE_STRUMENTI`. Per la variante `http`, con il
servizio avviato:

```powershell
$env:VARIANTE_STRUMENTI = "http"; $env:STRUMENTI_HTTP_URL = "http://localhost:8001"
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Nel log del servizio devono comparire le richieste `POST /strumenti/...`.

Prova manuale: avvia l'assistente (locale o Docker), chiedi «Che ore sono a Tokyo?» e poi
«E a Roma?». Sui log (stderr) devono comparire due chiamate `ora_corrente`, con
`Asia/Tokyo` e poi `Europe/Rome`, e le risposte devono usare l'ora restituita.
Per il convertitore: chiedi «Quanti metri sono 1,5 km?»; sui log deve comparire
`convertitore_unita` con risultato `1.5 km = 1500 m`. Per la calcolatrice: chiedi
«Quanto fa (17 + 4) * 3?»; sui log deve comparire `calcolatrice_sicura` con risultato `= 63`.
Per giorni e scadenze: chiedi «Quanti giorni mancano a Natale di quest'anno? Sono in Italia.»;
sui log devono comparire prima `ora_corrente` (per la data di oggi) e poi `giorni_scadenze`.
Una risposta simulata nei test non dimostra che il modello sappia usare lo strumento:
solo queste prove lo fanno.

## Diagnosi

- **LM Studio spento o server non avviato**: l'assistente scrive «Non riesco a raggiungere
  LM Studio su ...: controlla che il server sia avviato». Avvia il server locale in LM Studio.
- **Modello errato**: provato con `LMSTUDIO_MODEL=modello-inesistente` e LM Studio attivo:
  il server non ha dato errore, ha risposto comunque (con il modello caricato). Un
  identificativo sbagliato quindi può passare inosservato: se il modello che risponde non è
  quello atteso, confronta `LMSTUDIO_MODEL` con `Invoke-RestMethod http://localhost:1234/v1/models`.
- **Configurazione mancante**: l'avvio termina con «Configurazione non valida: ...» (codice 2);
  controlla `.env`. Con `VARIANTE_STRUMENTI=http` serve anche `STRUMENTI_HTTP_URL`.
- **Servizio strumenti spento (variante `http`)**: l'assistente non si blocca; lo strumento
  restituisce al modello «Errore: servizio strumenti non raggiungibile su ...», e il modello
  lo riferisce. Avvia il servizio (o, in Docker, usa `--profile http`).
- **Il container non raggiunge l'host**: verifica che `compose.yaml` contenga
  `extra_hosts: host.docker.internal:host-gateway` e che LM Studio sia in ascolto sulla
  porta 1234. Solo se non basta, in LM Studio puoi attivare «Serve on Local Network».
  Attenzione: così l'API di LM Studio è esposta a tutta la rete locale; riportala allo
  stato precedente appena finito. Nelle prove di questo progetto non è stato necessario.
- **Più dettagli**: imposta `LOG_LEVEL=DEBUG` nel `.env` (o, in locale,
  `$env:LOG_LEVEL = "DEBUG"`) e riavvia.
