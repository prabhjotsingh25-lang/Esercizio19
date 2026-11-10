# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `assistente-laboratorio/`; questo file e il progetto stanno nella cartella `lezione 4/` della repository,
accanto alle altre lezioni (es. `lezione 3/`).
Struttura: `src/assistente/` (config, contesto, preferenze, prompt, riassunto, router, revisore,
grafo, sessione, modello, cli, `__main__`; strumenti in moduli propri; `catalogo`, `varianti` e un modulo per
variante di integrazione),
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
  oltre `SOGLIA_RIASSUNTO` messaggi quelli vecchi diventano un riassunto (restano intatti almeno
  gli ultimi `MESSAGGI_RECENTI`);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- legge una volta a inizio sessione le preferenze dell'utente (lingua, fuso orario predefinito,
  stile): resource MCP `utente://preferenze` nella variante mcp, file `PREFERENZE_FILE` nelle
  altre; vanno in cima al prompt di sistema dell'agente;
- offre i prompt `spiega` e `riassumi_conversazione` con `/prompts` e `/prompt nome arg=valore`
  (prompt MCP nella variante mcp, catalogo locale nelle altre); i messaggi passano dal grafo;
- prima dell'agente, un router rifiuta le domande fuori dall'ambito descritto in `AMBITO_AGENTE`;
- dopo l'agente, un revisore controlla che la risposta sia coerente con la domanda e, se no,
  lo fa riprovare (al massimo `MAX_REVISIONI` volte); vede anche riassunto e risultati degli
  strumenti del turno, che considera attendibili;
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

## Comportamenti noti
- **Preferenze e strumenti con il modello piccolo** (`gemma-4-e2b`, misurato il 2026-11-10 su
  «Quanto fa 12 * 7?», «Converti 3 km in metri.», «Quanto fa 137 * 49?»): senza preferenze
  l'agente usa lo strumento 3 volte su 3; con il blocco delle preferenze in cima al prompt di
  sistema 0-2 su 3, qualunque formulazione dello stile; con le preferenze in fondo 0 su 3 (la
  posizione non conta). Di solito il risultato a mente è giusto, ma non sempre (una volta
  «96»). L'ora usa sempre `ora_corrente`. Il testo dello stile sintetico è «risposta finale
  breve ed essenziale (usa comunque gli strumenti)».
- **Contrassegno dei prompt** (step 5): i messaggi ottenuti con `/prompt` hanno
  `name="prompt"` e il nodo router li fa passare con una regola fissa, senza chiamare il modello.
  Oggi il contrassegno lo mette solo la CLI (comando `/prompt`). Allo step 6 (agente come
  servizio HTTP) dovrà arrivare dal chiamante in modo non falsificabile da un client qualsiasi
  (per esempio: il servizio compone lui i messaggi da nome e argomenti del prompt e non accetta
  `name="prompt"` nei messaggi ricevuti), altrimenti chiunque potrebbe aggirare il router.
- **Revisore e riassumi_conversazione** (step 5): il revisore vede solo gli ultimi 6 messaggi
  di testo, quindi ha bocciato due volte un riassunto giusto della sessione perché citava un turno
  più vecchio («Spiegazione del Model Context Protocol»); la risposta è uscita al limite delle
  revisioni.

### Possibili fix (da valutare dopo lo step 5, ciascuno con specifica a parte)
1. **Più contesto al revisore per `riassumi_conversazione`**: la finestra di 6 messaggi non basta
   per giudicare un riassunto della sessione (per esempio: tutti i messaggi di testo del turno
   corrente della sessione, o il riassunto più i turni recenti, quando la domanda viene dal
   prompt `riassumi_conversazione`).
2. **Controllo «calcolo senza strumento» nel revisore**: se la risposta contiene un calcolo o
   una conversione ma nel turno non c'è nessuno strumento, l'agente rifà usando lo strumento.
3. **Contrassegno `/prompt` non falsificabile allo step 6**: il servizio HTTP compone lui i
   messaggi da nome e argomenti del prompt e rifiuta `name="prompt"` nei messaggi ricevuti.

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
