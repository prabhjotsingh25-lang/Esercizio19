# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `assistente-laboratorio/`; questo file e il progetto stanno nella cartella `lezione 4/` della repository,
accanto alle altre lezioni (es. `lezione 3/`).
Struttura: `src/assistente/` (config, router, grafo, sessione, modello, cli, `__main__`; strumenti in
moduli propri; `catalogo`, `varianti` e un modulo per variante di integrazione),
`tests/`, `docs/superpowers/`, `Dockerfile`, `compose.yaml`, `requirements*.txt`, `.env.example`.
Comandi (da `assistente-laboratorio/`, PowerShell, senza attivare il venv):
- test offline: `.\.venv\Scripts\python.exe -m pytest -v`
- prove reali con LM Studio: `.\.venv\Scripts\python.exe -m pytest -m reale -v`
  (usano la variante di `VARIANTE_STRUMENTI`)
- avvio locale: `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente`
- servizio strumenti (variante `http`):
  `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m uvicorn assistente.servizio_http:app --port 8001`
- server MCP (variante `mcp`):
  `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m uvicorn assistente.server_mcp:app --port 8002`
- avvio Docker: `docker compose run --rm assistente`; varianti `http` e `mcp`:
  `docker compose --profile http run --rm -e VARIANTE_STRUMENTI=http assistente`,
  `docker compose --profile mcp run --rm -e VARIANTE_STRUMENTI=mcp assistente`
- le prove reali dipendono da un modello non deterministico: un fallimento isolato va ripetuto
  e diagnosticato prima di cambiare il codice.

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- prima dell'agente, un router rifiuta le domande fuori dall'ambito descritto in `AMBITO_AGENTE`;
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. RAG arriverà nelle lezioni successive: non anticiparlo.
- Evoluzione in 9 step (router, revisore, riassunto della cronologia, resource, prompt MCP,
  agente come servizio HTTP, back-end con PostgreSQL, front-end, Docker Compose): uno per volta,
  senza anticipare i successivi; per ogni step specifica e piano approvati prima del codice,
  evidenze nei log o nei test, poi commit proposto e attesa di «avanti». Si estende il progetto
  esistente, non lo si riscrive.
- Lezione 5 (Blocco 5, MCP e strumenti condivisi): si aggiungono sei strumenti, uno alla volta,
  in tre varianti di integrazione: 01 chiamata locale, 02 servizio FastAPI con wrapper HTTP,
  03 server FastMCP con client/adattatore. All'agente si espone una sola variante per volta,
  scelta da configurazione. `ora_corrente` resta lo strumento di riferimento e non va rifatto.
  Firma, argomenti ed errori di ogni strumento vanno concordati prima di implementarlo.
  Ogni strumento ha una sola logica e una sola definizione (`catalogo.py`); le varianti
  cambiano solo il canale, così nome, descrizione, schema e prompt restano identici e la
  cronologia è confrontabile. La variante indicata per uno strumento è il task in cui nasce
  quel canale; un canale nuovo espone tutti gli strumenti del catalogo.
- MCP (FastMCP), FastAPI, Uvicorn e httpx sono ammessi, ciascuno solo dal task della variante
  che lo richiede. Niente interfacce grafiche, servizi cloud o altri framework non concordati.
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Un branch `feat/<nome>` per task, creato sempre da `dev`; nessun worktree se non richiesto.
  Non toccare `main`.

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Per ogni strumento, test sui casi validi e su quelli di errore.
- La cronologia iniziale (prompt di sistema compreso) deve essere comparabile fra le tre
  varianti: si confrontano percorso e correttezza, non timestamp identici.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Branch: un `feat/<nome>` per task, creato da `dev`; commit piccoli (`feat:`, `test:`, `docs:`,
  `refactor:`). A task finito mostrare cosa è stato fatto e come è stato testato, e fare il merge
  in `dev` solo dopo il mio ok. `main` non si tocca.
- Push soltanto su mia richiesta.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
