# Assistente del laboratorio

Applicazione da terminale in Python che conversa con un modello locale servito da LM Studio.
Il flusso è un grafo LangGraph esplicito; il modello può chiedere lo strumento `ora_corrente`
(orologio con fuso orario IANA esplicito, per esempio `Asia/Tokyo`), che il programma esegue
davvero. La cronologia vive solo per la durata della sessione.

Struttura:

- `src/assistente/config.py`: lettura e validazione delle variabili d'ambiente;
- `src/assistente/strumenti.py`: strumento orologio;
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
(anche Ctrl+C o fine input). Risposte su stdout, log su stderr.

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

Prova manuale: avvia l'assistente (locale o Docker), chiedi «Che ore sono a Tokyo?» e poi
«E a Roma?». Sui log (stderr) devono comparire due chiamate `ora_corrente`, con
`Asia/Tokyo` e poi `Europe/Rome`, e le risposte devono usare l'ora restituita.
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
  controlla `.env`.
- **Il container non raggiunge l'host**: verifica che `compose.yaml` contenga
  `extra_hosts: host.docker.internal:host-gateway` e che LM Studio sia in ascolto sulla
  porta 1234. Solo se non basta, in LM Studio puoi attivare «Serve on Local Network».
  Attenzione: così l'API di LM Studio è esposta a tutta la rete locale; riportala allo
  stato precedente appena finito. Nelle prove di questo progetto non è stato necessario.
- **Più dettagli**: imposta `LOG_LEVEL=DEBUG` nel `.env` (o, in locale,
  `$env:LOG_LEVEL = "DEBUG"`) e riavvia.
