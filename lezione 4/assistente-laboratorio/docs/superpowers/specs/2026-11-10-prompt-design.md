# Step 5 · Prompt MCP: comandi /prompts e /prompt

Quinto dei nove step. Approvata dall'utente il 2026-11-10 (con correzioni alla prima proposta).

## Obiettivo
Il server MCP pubblica dei prompt (modelli di richiesta con argomenti) che sceglie l'utente.
La CLI li elenca con `/prompts` e li usa con `/prompt nome argomento=valore`; i messaggi ottenuti
entrano in cronologia e vanno al grafo come una domanda.

## Decisioni
- **Due prompt**, in un solo catalogo (`prompt.py`): `spiega(argomento, livello="base")` e
  `riassumi_conversazione(stile)`. `riassumi_conversazione` produce solo l'istruzione «Riassumi i
  turni della sessione corrente nello stile X»: il server non vede la cronologia, risponde
  l'agente con quella che ha. Non c'entra con il nodo `riassunto` dello step 3.
- **Canali**: variante `mcp` → prompt MCP pubblicati da `server_mcp.py`, `prompts/list` e
  `prompts/get` dal client (`FontePromptMCP`); varianti `locale` e `http` → catalogo locale
  (`FontePromptLocale`), senza endpoint nuovi. I prompt non sono tool: non arrivano a `bind_tools`.
- **Sintassi**: `/prompt nome argomento=valore` sulla stessa riga, virgolette per i valori con
  spazi (`shlex`). `/prompts` mostra nome, descrizione e argomenti (obbligatori o facoltativi).
- **Controllo nell'host** rispetto a `prompts/list`, prima di `prompts/get`: prompt sconosciuto,
  argomento obbligatorio mancante o argomento sconosciuto bloccano la richiesta con un messaggio
  chiaro, senza chiamare il server per il testo né il modello. Nessun controllo di formato.
- **Invio**: subito, senza conferma; la CLI mostra `Prompt> testo` e i messaggi vanno al grafo
  (router, strumenti e revisore compresi) con `Sessione.chiedi_messaggi`.
- **Router** (scelte dell'utente durante l'implementazione): il router vero rifiutava sempre
  `spiega` («argomento teorico fuori ambito», la regola dello step 1). Prima prova: messaggio
  marcato e regola nelle istruzioni del router → accettato solo 2 volte su 6 alla prima domanda.
  Decisione finale: **regola fissa nel nodo router**. I messaggi utente di un prompt hanno
  `name="prompt"`; per loro il nodo router non chiama il modello e scrive
  `router categoria=conversazione motivo=richiesta da un prompt dell'assistente (regola) ->
  agente`. Il contrassegno lo mette solo `prompt.messaggio()` (fonti dei prompt, comando
  `/prompt`); una riga scritta a mano diventa un messaggio senza nome e la decide il modello del
  router: «Spiegami il pH» scritto a mano resta fuori ambito.
- **Log**: `prompt: prompts/list (mcp) -> N prompt: ...` e `prompt: prompts/get NOME (mcp)
  argomenti={...} -> messaggi dal server: [user] ...`, separati dalle chiamate agli strumenti;
  `prompts/get` compare solo con `/prompt`.
- **Errori**: server MCP non raggiungibile o errore del server → «Prompt non disponibili: ...»,
  nessuna domanda inviata.

## Verifiche
- Offline: catalogo, analisi della riga (virgolette, nome=valore, ripetuti), controllo rispetto
  all'elenco, testo di `/prompts`, fonte locale e MCP (stesso elenco e stesso testo, predefinito
  applicato dal server, non fra i tool, errori), router con la segnalazione, sessione, CLI
  (invio, blocchi senza chiamate, server non disponibile), scelta della fonte per variante.
- Reali: CLI variante `mcp` con `/prompts`, `spiega`, argomento mancante e sconosciuto, due
  domande e `riassumi_conversazione`; prove pytest `test_prompt_*`; prove del router.
