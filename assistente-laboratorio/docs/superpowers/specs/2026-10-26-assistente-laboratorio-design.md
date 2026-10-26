# Assistente del laboratorio — specifica (lezione 4)

Data: 2026-10-26 · Stato: **approvata dall'utente il 2026-10-26**

## 1. Intento

Un'applicazione Python da terminale che conversa con un modello locale servito da LM Studio
sull'host. Serve come base didattica del corso «Deep Learning e LLM»: il flusso deve essere un
grafo LangGraph esplicito, leggibile (stato, nodi, instradamento riconoscibili), e deve mostrare
un vero ciclo di *tool calling*: il modello chiede lo strumento orologio, il programma lo esegue
davvero, il risultato torna al modello, che produce la risposta finale.

Il progetto continuerà nelle lezioni successive, quindi la struttura deve restare semplice e
facile da estendere, senza anticipare nulla.

## 2. Obiettivi

1. Conversazione da terminale con il modello di LM Studio, tramite l'API compatibile OpenAI.
2. Cronologia della conversazione conservata per tutta la sessione, solo in memoria.
3. Strumento orologio con fuso orario esplicito, richiesto dal modello ed eseguito dal grafo.
4. Chiamate allo strumento visibili nei log; numero di passaggi limitato.
5. Avvio sia locale (venv) sia con Docker Compose; LM Studio resta sull'host.
6. Test automatici che non richiedono un modello attivo; prove reali separate e attivate
   esplicitamente, con istruzioni nel README.

## 3. Non obiettivi (vietati in questa lezione)

- Altri strumenti oltre all'orologio, MCP, RAG, workflow, agenti multipli.
- Interfacce web/grafiche, servizi cloud, persistenza della cronologia (file, DB, checkpointer
  su disco).
- Containerizzare LM Studio.
- Streaming dei token, codice asincrono.

**Anti-obiettivi** (fallimento anche se "funziona"):
- l'ora nella risposta è inventata dal modello e non proviene dallo strumento;
- un test "verde" che usa una risposta simulata venduto come prova che il modello locale sappia
  usare lo strumento;
- identificativo del modello o indirizzo del server scritti nel codice.

## 4. Vincoli

- Python 3.13 (versione presente sull'host; stessa versione nell'immagine Docker).
- Codice sincrono, moduli piccoli: grafo, collegamento al modello, strumenti, interfaccia.
- Indirizzo del server e identificativo del modello **solo** da variabili d'ambiente;
  l'identificativo è quello restituito da `GET /v1/models` (oggi: `google/gemma-4-e2b`).
- `.env.example` versionato senza credenziali; `.env` reale fuori da Git.
- Dipendenze con versioni fissate; comandi documentati per PowerShell.
- Tutto dentro `assistente-laboratorio/` (la repository Git è `Lezione 4/`, branch `main`,
  inizializzata il 2026-10-26, ancora senza commit). Anche `.gitignore` sta dentro
  `assistente-laboratorio/`; alla radice resta solo `CLAUDE.md`. *(Mia scelta.)*

## 5. Comportamento concordato

### 5.1 Conversazione
- Il programma mostra un prompt, legge una riga, la invia al grafo, stampa la risposta finale.
- La cronologia (messaggi utente, assistente, chiamate e risultati dello strumento) resta in
  memoria per la sessione e viene ripassata al grafo a ogni turno. Alla chiusura si perde.
- **Lingua**: l'assistente risponde nella lingua in cui l'utente scrive (deciso dall'utente).
- **Ora senza luogo**: se l'utente chiede l'ora senza indicare luogo o fuso, l'assistente chiede
  dove, invece di indovinare (deciso dall'utente).
- Queste due regole, e l'indicazione di usare sempre lo strumento per data e ora, stanno in un
  messaggio di sistema fisso, non salvato nella cronologia visibile.
- **Prova di accettazione** (decisa dall'utente): «Che ore sono a Tokyo?» seguita da
  «E a Roma?». La seconda risposta dimostra anche che la cronologia funziona.

### 5.2 Strumento orologio
- Nome: `ora_corrente`. Argomento obbligatorio `fuso_orario` (stringa, nome IANA,
  es. `Europe/Rome`, `Asia/Tokyo`) (deciso dall'utente).
- Risultato: data e ora correnti in ISO 8601 con offset, più il nome del fuso
  (es. `2026-10-26T18:30:05+09:00 (Asia/Tokyo)`) (deciso dall'utente).
- Fuso non valido o mancante: lo strumento non solleva eccezioni verso l'utente; restituisce al
  modello un messaggio d'errore leggibile, e il modello risponde di conseguenza.
  Anche gli errori di validazione degli argomenti (argomento assente, tipo sbagliato) e le
  richieste di uno strumento sconosciuto vengono catturati dal nodo `strumenti` e restituiti
  come risultato d'errore. *(Mia scelta.)*
- L'istante corrente è iniettabile (una funzione "adesso"), così i test usano un istante fisso.

### 5.3 Grafo
- **Stato**: lista di messaggi (con reducer che accoda) + contatore dei passaggi strumento del
  turno corrente.
- **Nodi**:
  - `modello` — invia messaggio di sistema + cronologia al modello con lo strumento collegato;
  - `strumenti` — esegue le chiamate richieste, aggiunge i risultati, incrementa il contatore;
  - `limite` — usato quando il modello chiede ancora lo strumento a limite raggiunto.
- **Instradamento** dopo `modello`: nessuna chiamata → fine; chiamate e contatore sotto il
  limite → `strumenti`; chiamate a limite raggiunto → `limite`. Da `strumenti` si torna sempre a
  `modello`. `limite` → fine.
- **Limite**: al massimo **3** esecuzioni del nodo `strumenti` per domanda, configurabile da
  variabile d'ambiente. *(Mia scelta.)* Il nodo `limite` risponde con le chiamate in sospeso
  chiuse da un risultato "non eseguito: limite raggiunto" e un messaggio finale fisso in
  italiano che spiega il blocco, così la cronologia resta valida per il turno successivo.
  *(Mia scelta.)* Il messaggio fisso è in italiano anche se l'utente scrive in un'altra lingua:
  eccezione consapevole alla regola della lingua, per tenerlo deterministico. *(Mia scelta.)*
  Il contatore riparte da 0 a ogni domanda: l'interfaccia lo passa a 0 a ogni invocazione.
  In più, un `recursion_limit` di LangGraph come rete di sicurezza, pari a
  `2 × MAX_PASSAGGI_STRUMENTO + 5`. *(Mia scelta.)*

### 5.4 Log
- `logging` standard su **stderr** (la risposta va su stdout). Livello `INFO` di default,
  regolabile con `LOG_LEVEL`. *(Mia scelta.)*
- Per ogni chiamata allo strumento: numero di passaggio, nome, argomenti, risultato. Log anche
  dell'intervento del limite. A `DEBUG` eventuali dettagli in più sulle chiamate al modello.

### 5.5 Interfaccia da terminale *(mia scelta)*
- `/esci` (o Ctrl+C / fine input) chiude in modo pulito.
- `/nuova` azzera la cronologia.
- Righe vuote ignorate. Errore di connessione a LM Studio: messaggio chiaro (indirizzo usato,
  suggerimento di controllare che il server sia avviato), la sessione continua.

### 5.6 Configurazione
| Variabile | Obbligatoria | Esempio |
|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | `http://localhost:1234/v1` (locale), `http://host.docker.internal:1234/v1` (Docker) |
| `LMSTUDIO_MODEL` | sì | `google/gemma-4-e2b` |
| `MAX_PASSAGGI_STRUMENTO` | no (default 3) | `3` |
| `LOG_LEVEL` | no (default `INFO`) | `DEBUG` |

Mancanza di una variabile obbligatoria: errore esplicito all'avvio con il nome della variabile.
LM Studio non richiede chiave; al client si passa un valore segnaposto non segreto.

### 5.7 Docker *(mia scelta)*
- `Dockerfile` su `python:3.13-slim`, solo dipendenze di esecuzione.
- `compose.yaml` con un servizio `assistente`: `env_file: .env`, `stdin_open` e `tty`,
  `environment: LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1` (sovrascrive il valore
  locale del `.env`, così lo stesso file serve a entrambi gli avvii), e
  `extra_hosts: host.docker.internal:host-gateway` (necessario su Linux, innocuo su Docker
  Desktop).
- Avvio interattivo: `docker compose run --rm assistente`.
- Con Docker Desktop su Windows un server legato solo a `127.0.0.1` può non essere
  raggiungibile dal container: va verificato **all'inizio** dell'implementazione con una
  chiamata a `/v1/models` da un container, non solo citato nella diagnosi. Se serve, si attiva
  in LM Studio «Serve on Local Network» (vedi §11).

## 6. Dipendenze *(mia scelta, da confermare)*

Ultime versioni stabili su PyPI al 2026-10-26, da fissare esattamente. Si fissano le
dipendenze dirette; `pip install --dry-run` su Python 3.13.14 non mostra conflitti.
*(Mia scelta: niente file di vincoli per le indirette.)*

| Pacchetto | Versione | Motivo |
|---|---|---|
| `langgraph` | 1.2.17 | grafo esplicito (requisito) |
| `langchain-openai` | 1.7.2 | `ChatOpenAI` con `base_url` verso LM Studio, `bind_tools`, messaggi compatibili con LangGraph |
| `langchain-core` | 1.7.0 | messaggi e definizione dello strumento (già dipendenza dei precedenti, fissata esplicitamente) |
| `tzdata` | 2026.5 | dati dei fusi IANA per `zoneinfo`: Windows non li ha, l'immagine slim potrebbe non averli |
| `python-dotenv` | 1.2.4 | caricare `.env` nell'esecuzione locale su PowerShell senza esportare variabili a mano |
| `pytest` | 9.1.1 | test (solo sviluppo, in `requirements-dev.txt`) |

## 7. Test e verifiche

**Automatici (nessun modello attivo, `pytest`):**
- strumento con istante fisso: fusi diversi, formato ISO 8601, fuso non valido/mancante;
- instradamento: nessuna chiamata → fine; chiamata sotto limite → strumenti; a limite → limite;
- grafo completo con un modello finto che prima chiede lo strumento e poi risponde: il risultato
  dello strumento arriva al modello, la risposta finale è quella attesa;
- limite: modello finto che chiede sempre lo strumento → si ferma dopo 3 esecuzioni, cronologia
  valida;
- cronologia: due turni consecutivi, il secondo vede i messaggi del primo; `/nuova` azzera;
- configurazione: variabili mancanti → errore esplicito;
- log: la chiamata allo strumento compare nei log.

**Prove reali (separate, attivate esplicitamente):**
- test `pytest` marcati `reale`, esclusi di default (`-m "not reale"` nella configurazione
  pytest in `pyproject.toml`) ed eseguiti solo con `pytest -m reale`, contro LM Studio attivo.
  Criterio: nella cronologia c'è un risultato di `ora_corrente` con `Asia/Tokyo`, e la risposta
  finale contiene l'ora (HH:MM) di quel risultato; secondo turno «E a Roma?» → nuova chiamata
  con `Europe/Rome`. *(Mia scelta.)*
- prova manuale documentata nel README, locale e in Docker, con la prova di accettazione
  (Tokyo, poi Roma) e controllo dei log.

Un test con modello finto non dimostra che il modello locale sappia usare lo strumento: il
resoconto finale distinguerà le due cose.

## 8. Struttura prevista *(mia scelta)*

```
Lezione 4/                       (repository Git)
├── CLAUDE.md
├── .gitignore
└── assistente-laboratorio/
    ├── README.md
    ├── requirements.txt / requirements-dev.txt
    ├── .env.example
    ├── Dockerfile / compose.yaml / .dockerignore
    ├── src/assistente/          config, modello, strumenti, grafo, cli, __main__
    ├── tests/
    └── docs/superpowers/        specs/ e plans/
```

Avvio locale: `python -m assistente` (con `src` nel percorso, dettaglio lasciato al piano).

## 9. Lasciato a chi costruisce

- Nomi interni di funzioni e moduli oltre a quelli citati; testo esatto del messaggio di sistema
  e dei messaggi d'errore.
- Come costruire il modello finto nei test, purché i test non tocchino la rete.
- Come rendere importabile il pacchetto (`pyproject.toml` minimale, già previsto per pytest).

## 10. Rischi noti

- `gemma-4-e2b` è un modello piccolo: una sonda manuale ha prodotto una chiamata corretta
  (`ora_corrente` con `Asia/Tokyo`), ma l'affidabilità su più turni va verificata con le prove
  reali. Se fallisce, lo si documenta e si valuta un altro modello (l'id cambia solo in `.env`).
- Il modello produce anche `reasoning_content`; va ignorato in output, non è un errore.

## 11. Decisioni dell'utente (2026-10-26)

- Dipendenze della §6: confermate.
- «Serve on Local Network» in LM Studio: si può attivare, se la verifica iniziale mostra che il
  container non raggiunge il server su `127.0.0.1`. Va indicato nel README che così l'API è
  esposta alla rete locale.
