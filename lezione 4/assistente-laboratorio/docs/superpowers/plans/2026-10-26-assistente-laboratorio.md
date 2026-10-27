# Assistente del laboratorio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** applicazione Python da terminale che conversa con il modello di LM Studio attraverso un
grafo LangGraph esplicito, con strumento orologio, cronologia in memoria, limite dei passaggi,
log e avvio con Docker Compose.

**Architecture:** quattro moduli con una responsabilità ciascuno (`strumenti`, `grafo`,
`modello`, `cli`) più `config` e `sessione`. Il grafo riceve modello e strumenti dall'esterno,
quindi i test usano un modello finto senza rete. La sessione tiene la cronologia e la ripassa al
grafo a ogni domanda; nessun checkpointer.

**Tech Stack:** Python 3.13, langgraph 1.2.17, langchain-openai 1.7.2, langchain-core 1.7.0,
tzdata 2026.5, python-dotenv 1.2.4, pytest 9.1.1, Docker Compose.

**Spec:** `assistente-laboratorio/docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`

## Global Constraints

- Tutti i file in `assistente-laboratorio/`; comandi eseguiti da quella cartella. Branch `main`.
- Codice sincrono, Python 3.13, niente altri strumenti, MCP, RAG, interfacce web, persistenza.
- `LMSTUDIO_BASE_URL` e `LMSTUDIO_MODEL` solo da variabili d'ambiente; nessun default nel codice.
- Default: `MAX_PASSAGGI_STRUMENTO=3`, `LOG_LEVEL=INFO`; `recursion_limit = 2 × max + 5`.
- Strumento `ora_corrente(fuso_orario: str)`; risultato `<ISO 8601 con offset, secondi> (<fuso>)`.
- Log su stderr, risposte su stdout.
- Versioni fissate con `==`. Comandi documentati per PowerShell, senza attivare il venv:
  `.\.venv\Scripts\python.exe ...`.
- Commit: Conventional Commits in italiano; prima `git status`, `git diff --staged`, staging
  selettivo; trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nessun push.
- Mai versionare `.env`, `.venv/`, cache.

## Review Focus

1. Il modello passa un fuso non IANA (`"Tokyo"`, `"GMT+9"`, `""`): errore leggibile al modello,
   nessuna eccezione → test in Task 2.
2. Il modello chiede due chiamate nella stessa risposta (Tokyo e Roma): entrambe eseguite, conta
   come **un** passaggio, un ToolMessage per ciascun `tool_call_id` → test in Task 3.
3. Dopo l'intervento del limite la domanda successiva funziona: ogni `tool_call` della cronologia
   ha il suo ToolMessage → test in Task 4.
4. LM Studio spento a metà sessione: messaggio chiaro, cronologia invariata, la sessione
   continua → test in Task 4 (sessione) e Task 5 (CLI).
5. Input vuoto, solo spazi, fine input (EOF) o Ctrl+C: ignorato o chiusura pulita, senza
   traceback → test in Task 5.

---

### Task 1: Struttura del progetto, configurazione e verifica di rete Docker

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.env.example`
- Create: `src/assistente/__init__.py` (vuoto), `src/assistente/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Configurazione` (dataclass frozen: `base_url: str`, `modello: str`,
  `max_passaggi: int = 3`, `log_level: str = "INFO"`);
  `ErroreConfigurazione(ValueError)`;
  `carica_configurazione(env: Mapping[str, str] | None = None) -> Configurazione`
  (con `None` legge `os.environ`).

- [ ] **Step 1: Verifica iniziale: il container raggiunge LM Studio?** (spec §5.7, decisione §11)

Run:
```powershell
docker run --rm --add-host=host.docker.internal:host-gateway python:3.13-slim python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=5).read().decode()[:300])"
```
Expected: JSON con `google/gemma-4-e2b`. Se fallisce (connection refused/timeout): chiedere
all'utente di attivare «Serve on Local Network» nelle impostazioni del server di LM Studio
(autorizzato, spec §11), poi ripetere. Annotare l'esito per il README (Task 7).

- [ ] **Step 2: File di progetto**

`requirements.txt`: `langgraph==1.2.17`, `langchain-openai==1.7.2`, `langchain-core==1.7.0`,
`tzdata==2026.5`, `python-dotenv==1.2.4`.
`requirements-dev.txt`: `-r requirements.txt` e `pytest==9.1.1`.
`pyproject.toml`: solo `[tool.pytest.ini_options]` con `pythonpath = ["src"]`,
`testpaths = ["tests"]`, `addopts = "-m 'not reale'"`,
`markers = ["reale: prove con LM Studio attivo, da attivare con -m reale"]`.
`.env.example`:
```
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=google/gemma-4-e2b
MAX_PASSAGGI_STRUMENTO=3
LOG_LEVEL=INFO
```

Run:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```
Expected: installazione senza errori.

- [ ] **Step 3: Test che falliscono** in `tests/test_config.py`

```python
def test_configurazione_completa():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": "http://x:1/v1", "LMSTUDIO_MODEL": "m",
                               "MAX_PASSAGGI_STRUMENTO": "5", "LOG_LEVEL": "debug"})
    assert c == Configurazione("http://x:1/v1", "m", 5, "DEBUG")

def test_default_facoltativi():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m"})
    assert (c.max_passaggi, c.log_level) == (3, "INFO")

@pytest.mark.parametrize("manca", ["LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL"])
def test_variabile_obbligatoria_mancante_o_vuota(manca):
    env = {"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m"}
    for valore in (None, "  "):
        e = dict(env); e.pop(manca) if valore is None else e.__setitem__(manca, valore)
        with pytest.raises(ErroreConfigurazione, match=manca):
            carica_configurazione(e)

@pytest.mark.parametrize("valore", ["zero", "0", "-1"])
def test_max_passaggi_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSAGGI_STRUMENTO"):
        carica_configurazione({"LMSTUDIO_BASE_URL": "u", "LMSTUDIO_MODEL": "m",
                               "MAX_PASSAGGI_STRUMENTO": valore})
```

- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v` → FAIL (import).
- [ ] **Step 5: Implementare `config.py`** — valori con `.strip()`; `LOG_LEVEL` in maiuscolo;
  `MAX_PASSAGGI_STRUMENTO` intero ≥ 1.
- [ ] **Step 6:** stesso comando → PASS.
- [ ] **Step 7: Commit** `git add requirements.txt requirements-dev.txt pyproject.toml .env.example src/assistente/__init__.py src/assistente/config.py tests/test_config.py`
  → `feat(config): struttura del progetto e configurazione da variabili d'ambiente`.
  Prima del commit, `git status` non deve mostrare `.venv/` (coperto dal `.gitignore`).

### Task 2: Strumento orologio

**Files:**
- Create: `src/assistente/strumenti.py`
- Test: `tests/test_strumenti.py`

**Interfaces:**
- Produces: `descrivi_ora(fuso_orario: str, adesso: Callable[[], datetime]) -> str`;
  `crea_strumento_orologio(adesso: Callable[[], datetime] | None = None) -> BaseTool`
  (nome `ora_corrente`, argomento `fuso_orario: str`, default `datetime.now(timezone.utc)`).
  `adesso` restituisce un datetime con fuso.

- [ ] **Step 1: Test che falliscono**

```python
ISTANTE = datetime(2026, 10, 26, 9, 30, 5, tzinfo=timezone.utc)
adesso = lambda: ISTANTE

def test_tokyo():
    assert descrivi_ora("Asia/Tokyo", adesso) == "2026-10-26T18:30:05+09:00 (Asia/Tokyo)"

def test_roma_dopo_cambio_ora():  # 25 ottobre 2026: Roma torna a +01:00
    assert descrivi_ora("Europe/Rome", adesso) == "2026-10-26T10:30:05+01:00 (Europe/Rome)"

@pytest.mark.parametrize("fuso", ["Tokyo", "GMT+9", "", "../etc/passwd"])
def test_fuso_non_valido_restituisce_errore(fuso):
    risultato = descrivi_ora(fuso, adesso)
    assert risultato.startswith("Errore:") and "Europe/Rome" in risultato

def test_strumento_langchain():
    strumento = crea_strumento_orologio(adesso)
    assert strumento.name == "ora_corrente"
    assert strumento.args_schema.model_json_schema()["required"] == ["fuso_orario"]
    assert strumento.invoke({"fuso_orario": "Asia/Tokyo"}).startswith("2026-10-26T18:30:05")
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_strumenti.py -v` → FAIL.
- [ ] **Step 3: Implementare** — `ZoneInfo(fuso)`, cattura `ZoneInfoNotFoundError` e
  `ValueError` (anche stringa vuota) e restituisce
  `"Errore: fuso orario non valido: '<fuso>'. Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo."`;
  formato `isoformat(timespec="seconds")`. Lo strumento si costruisce con
  `StructuredTool.from_function` e una descrizione che dice di passare un fuso IANA.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** → `feat(strumenti): strumento orologio con fuso orario esplicito`.

### Task 3: Grafo LangGraph

**Files:**
- Create: `src/assistente/grafo.py`, `tests/finti.py`
- Test: `tests/test_grafo.py`

**Interfaces:**
- Consumes: `crea_strumento_orologio` (Task 2).
- Produces:
  - `class Stato(TypedDict)`: `messages: Annotated[list[AnyMessage], add_messages]`, `passaggi: int`;
  - `MESSAGGIO_SISTEMA: str`, `MESSAGGIO_LIMITE: str`;
  - `scegli_prossimo(stato: Stato, max_passaggi: int) -> Literal["strumenti", "limite", "__end__"]`;
  - `limite_ricorsione(max_passaggi: int) -> int` (= `2 * max_passaggi + 5`);
  - `costruisci_grafo(modello: BaseChatModel, strumenti: list[BaseTool], max_passaggi: int)`
    → grafo compilato, nodi `modello`, `strumenti`, `limite`;
  - in `tests/finti.py` (importato con `from finti import ...`; pytest aggiunge `tests/` al
    percorso): `ISTANTE` e `orologio = crea_strumento_orologio(lambda: ISTANTE)` come nel
    Task 2; `ModelloFinto(BaseChatModel)` con campi `risposte: list[AIMessage]`
    e `ricevuti: list[list[BaseMessage]]`; `_generate` registra i messaggi e restituisce la
    risposta successiva; `bind_tools` restituisce `self`. Helper
    `chiamata(fuso: str, id: str) -> AIMessage` (contenuto vuoto, un `tool_call` a `ora_corrente`).

Testi fissati: `MESSAGGIO_SISTEMA` dice (1) usa sempre `ora_corrente` per data e ora, non
inventarle; (2) se l'utente chiede l'ora senza luogo o fuso, chiedi dove; (3) rispondi nella
lingua dell'utente. `MESSAGGIO_LIMITE = "Ho raggiunto il limite di passaggi dello strumento per
questa domanda e mi sono fermato. Prova a riformulare la richiesta."`

- [ ] **Step 1: Test che falliscono** in `tests/test_grafo.py` (orologio con `ISTANTE` del Task 2):

```python
def test_instradamento():
    fine = {"messages": [AIMessage("ciao")], "passaggi": 0}
    assert scegli_prossimo(fine, 3) == "__end__"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 2}, 3) == "strumenti"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 3}, 3) == "limite"

def test_ciclo_completo_con_strumento():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30.")])
    out = costruisci_grafo(m, [orologio], 3).invoke(
        {"messages": [HumanMessage("Che ore sono a Tokyo?")], "passaggi": 0})
    assert out["messages"][-1].content == "A Tokyo sono le 18:30."
    assert out["passaggi"] == 1
    secondo = m.ricevuti[1]
    assert isinstance(secondo[0], SystemMessage)
    assert secondo[-1].tool_call_id == "1" and secondo[-1].content.startswith("2026-10-26T18:30:05+09:00")

def test_due_chiamate_nella_stessa_risposta_contano_un_passaggio():
    doppia = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {"fuso_orario": "Asia/Tokyo"}, "id": "a"},
                                       {"name": "ora_corrente", "args": {"fuso_orario": "Europe/Rome"}, "id": "b"}])
    out = costruisci_grafo(ModelloFinto(risposte=[doppia, AIMessage("ok")]), [orologio], 3).invoke(
        {"messages": [HumanMessage("Tokyo e Roma?")], "passaggi": 0})
    assert [t.tool_call_id for t in out["messages"] if isinstance(t, ToolMessage)] == ["a", "b"]
    assert out["passaggi"] == 1

def test_argomenti_sbagliati_e_strumento_sconosciuto_diventano_errori():
    cattive = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "a"},
                                        {"name": "meteo", "args": {}, "id": "b"}])
    out = costruisci_grafo(ModelloFinto(risposte=[cattive, AIMessage("ok")]), [orologio], 3).invoke(
        {"messages": [HumanMessage("?")], "passaggi": 0})
    errori = [t for t in out["messages"] if isinstance(t, ToolMessage)]
    assert all(t.content.startswith("Errore:") for t in errori) and len(errori) == 2

def test_limite_ferma_il_ciclo_e_chiude_le_chiamate():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", str(i)) for i in range(10)])
    out = costruisci_grafo(m, [orologio], 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    assert out["passaggi"] == 3 and len(m.ricevuti) == 4
    assert out["messages"][-1].content == MESSAGGIO_LIMITE
    assert out["messages"][-2].content == "Non eseguito: limite di passaggi raggiunto."

def test_log_della_chiamata(caplog):
    caplog.set_level("INFO")
    costruisci_grafo(ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("ok")]),
                     [orologio], 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    assert "passaggio=1" in caplog.text and "ora_corrente" in caplog.text and "Asia/Tokyo" in caplog.text
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py -v` → FAIL.
- [ ] **Step 3: Implementare `grafo.py`** — nodo `modello`: `modello.bind_tools(strumenti)`
  chiamato con `[SystemMessage(MESSAGGIO_SISTEMA), *stato["messages"]]` (il messaggio di
  sistema non entra nello stato). Nodo `strumenti`: per ogni `tool_call` dell'ultimo messaggio,
  cerca per nome, `invoke(args)` dentro `try/except Exception` → `ToolMessage("Errore: ...")`;
  strumento sconosciuto → `"Errore: strumento sconosciuto: <nome>"`; log `INFO` con logger
  `assistente.grafo`: `strumento passaggio=%d nome=%s argomenti=%s risultato=%s`; restituisce
  `passaggi + 1`. Nodo `limite`: un `ToolMessage("Non eseguito: limite di passaggi raggiunto.")`
  per chiamata in sospeso + `AIMessage(MESSAGGIO_LIMITE)`, log `WARNING`. Archi:
  `START→modello`, condizionale da `modello` con `scegli_prossimo`, `strumenti→modello`,
  `limite→END`. Log `DEBUG` delle chiamate al modello.
- [ ] **Step 4:** stesso comando → PASS; poi l'intera suite → PASS.
- [ ] **Step 5: Commit** → `feat(grafo): grafo con nodi modello, strumenti e limite dei passaggi`.

### Task 4: Sessione e cronologia

**Files:**
- Create: `src/assistente/sessione.py`
- Test: `tests/test_sessione.py`

**Interfaces:**
- Consumes: `costruisci_grafo`, `limite_ricorsione` (Task 3), `ModelloFinto`, `chiamata`, `orologio` (`tests/finti.py`).
- Produces: `class Sessione` con `__init__(self, grafo, max_passaggi: int)`,
  `cronologia: list[BaseMessage]`, `chiedi(self, testo: str) -> str` (testo della risposta
  finale), `nuova(self) -> None`.

- [ ] **Step 1: Test che falliscono**

```python
def test_secondo_turno_vede_il_primo():
    m = ModelloFinto(risposte=[AIMessage("Ciao Anna"), AIMessage("Ti chiami Anna")])
    s = Sessione(costruisci_grafo(m, [orologio], 3), 3)
    s.chiedi("Mi chiamo Anna"); assert s.chiedi("Come mi chiamo?") == "Ti chiami Anna"
    assert [x.content for x in m.ricevuti[1][1:]] == ["Mi chiamo Anna", "Ciao Anna", "Come mi chiamo?"]

def test_nuova_azzera():
    s = Sessione(costruisci_grafo(ModelloFinto(risposte=[AIMessage("a")]), [orologio], 3), 3)
    s.chiedi("x"); s.nuova(); assert s.cronologia == []

def test_contatore_riparte_a_ogni_domanda():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), chiamata("Asia/Tokyo", "2"), AIMessage("uno"),
                               chiamata("Asia/Tokyo", "3"), chiamata("Asia/Tokyo", "4"), AIMessage("due")])
    s = Sessione(costruisci_grafo(m, [orologio], 2), 2)
    assert (s.chiedi("a"), s.chiedi("b")) == ("uno", "due")

def test_dopo_il_limite_la_domanda_successiva_funziona():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), chiamata("Asia/Tokyo", "2"), AIMessage("ok")])
    s = Sessione(costruisci_grafo(m, [orologio], 1), 1)
    assert s.chiedi("a") == MESSAGGIO_LIMITE and s.chiedi("b") == "ok"
    chiamate = {c["id"] for x in s.cronologia if isinstance(x, AIMessage) for c in x.tool_calls}
    risposte = {x.tool_call_id for x in s.cronologia if isinstance(x, ToolMessage)}
    assert chiamate == risposte

def test_errore_del_modello_lascia_invariata_la_cronologia():
    s = Sessione(costruisci_grafo(ModelloFinto(risposte=[AIMessage("a")]), [orologio], 3), 3)
    s.chiedi("x"); prima = list(s.cronologia)
    with pytest.raises(Exception):  # ModelloFinto senza risposte → errore
        s.chiedi("y")
    assert s.cronologia == prima
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_sessione.py -v` → FAIL.
- [ ] **Step 3: Implementare** — `chiedi` invoca il grafo con
  `{"messages": [*cronologia, HumanMessage(testo)], "passaggi": 0}` e
  `config={"recursion_limit": limite_ricorsione(max_passaggi)}`; aggiorna `cronologia` solo se
  l'invocazione riesce; restituisce il testo dell'ultimo messaggio. Le eccezioni passano al
  chiamante.
- [ ] **Step 4:** stesso comando → PASS; intera suite → PASS.
- [ ] **Step 5: Commit** → `feat(sessione): cronologia della conversazione in memoria`.

### Task 5: Collegamento al modello e interfaccia da terminale

**Files:**
- Create: `src/assistente/modello.py`, `src/assistente/cli.py`, `src/assistente/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Configurazione`, `carica_configurazione`, `ErroreConfigurazione` (Task 1),
  `crea_strumento_orologio` (2), `costruisci_grafo` (3), `Sessione` (4).
- Produces: `crea_modello(config: Configurazione) -> ChatOpenAI` (`base_url`, `model`,
  `api_key="lm-studio"`, `timeout=120`);
  `esegui(sessione: Sessione, base_url: str, leggi: Callable[[str], str] = input, scrivi: Callable[[str], None] = print) -> None`;
  `main() -> int` (0 normale, 2 configurazione mancante); `__main__.py`: `raise SystemExit(main())`.

- [ ] **Step 1: Test che falliscono** — `leggi` finto da una lista che alla fine solleva
  `EOFError`; `sessione` finta con `chiedi` registrato.

```python
def test_comandi_e_righe_vuote(): ...
    # input: ["", "   ", "ciao", "/nuova", "/esci", "mai letta"]
    # → chiedi chiamato solo con "ciao"; nuova chiamata una volta; "mai letta" non letta;
    #   l'output contiene la risposta della sessione
def test_eof_e_ctrl_c_chiudono_senza_eccezioni(): ...
    # leggi solleva EOFError (poi, in un secondo caso, KeyboardInterrupt) → esegui ritorna
def test_lm_studio_non_raggiungibile_non_chiude_la_sessione(): ...
    # chiedi solleva openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    # alla prima domanda, poi risponde "ok" alla seconda → output con l'indirizzo base_url
    #   e "LM Studio", poi "ok"
def test_limite_ricorsione_superato_mostra_messaggio(): ...
    # chiedi solleva langgraph.errors.GraphRecursionError → messaggio, la sessione continua
def test_main_senza_configurazione(monkeypatch, capsys): ...
    # variabili cancellate, load_dotenv sostituito da no-op → main() == 2,
    #   stderr contiene "LMSTUDIO_BASE_URL"
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -v` → FAIL.
- [ ] **Step 3: Implementare** — `esegui`: prompt `"Tu> "`, risposta preceduta da
  `"Assistente> "`; all'avvio stampa una riga con i comandi `/esci` e `/nuova`.
  `openai.APIConnectionError`/`APITimeoutError` → «Non riesco a raggiungere LM Studio su
  <base_url>: controlla che il server sia avviato.»; altri `openai.APIError` → messaggio con
  l'errore; `GraphRecursionError` → messaggio sul limite. `main`:
  `load_dotenv(".env")` (senza sovrascrivere variabili già presenti), configurazione,
  `logging.basicConfig(stream=sys.stderr, level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`,
  logger `httpx` a `WARNING`, poi grafo e sessione.
- [ ] **Step 4:** stesso comando → PASS; intera suite → PASS.
- [ ] **Step 5: Prova manuale reale (locale)** — `Copy-Item .env.example .env`, poi
  `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente`. Chiedere
  «Che ore sono a Tokyo?» e poi «E a Roma?». Atteso: log `ora_corrente` con `Asia/Tokyo` e poi
  `Europe/Rome`, ore coerenti con l'orologio reale; poi «Che ore sono?» → l'assistente chiede
  dove; `/esci`. Registrare l'esito (anche se negativo) per il resoconto.
- [ ] **Step 6: Commit** → `feat(cli): interfaccia da terminale collegata a LM Studio`.

### Task 6: Prove reali automatizzate (marcate `reale`)

**Files:**
- Test: `tests/test_reale.py`

**Interfaces:**
- Consumes: `carica_configurazione`, `crea_modello`, `crea_strumento_orologio`,
  `costruisci_grafo`, `Sessione`.

- [ ] **Step 1: Scrivere i test** con `pytestmark = pytest.mark.reale`; carica `.env` con
  `load_dotenv`; `pytest.skip` se la configurazione manca.
  - `test_tokyo_poi_roma`: sessione reale; dopo «Che ore sono a Tokyo?» la cronologia contiene
    un ToolMessage il cui risultato inizia con l'istante di `Asia/Tokyo`, e la risposta finale
    contiene l'`HH:MM` di quel risultato; dopo «E a Roma?» c'è un nuovo ToolMessage con
    `(Europe/Rome)`.
  - `test_ora_senza_luogo`: «Che ore sono?» → nessun ToolMessage nel turno (il modello chiede
    dove).
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest -v` → i test `reale` risultano
  *deselected*.
- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest -m reale -v` con LM Studio attivo →
  registrare l'esito esatto. Un fallimento dovuto al modello non si "aggiusta" allentando le
  asserzioni: si riporta.
- [ ] **Step 4: Commit** → `test(reale): prove con LM Studio attivabili con -m reale`.

### Task 7: Docker Compose, README e CLAUDE.md

**Files:**
- Create: `Dockerfile`, `compose.yaml`, `.dockerignore`, `README.md`
- Modify: `../CLAUDE.md` (sezione struttura e comandi; solo convenzioni stabili)

- [ ] **Step 1: Docker** — `Dockerfile`: `python:3.13-slim`, `WORKDIR /app`,
  `PYTHONUNBUFFERED=1`, `PYTHONPATH=/app/src`, `pip install --no-cache-dir -r requirements.txt`,
  copia `src/`, `CMD ["python", "-m", "assistente"]`. `.dockerignore`: `.env`, `.venv/`,
  `venv/`, `__pycache__/`, `.pytest_cache/`, `tests/`, `docs/`, `.git`.
  `compose.yaml`: servizio `assistente` con `build: .`, `env_file: .env`,
  `environment: LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1`, `stdin_open: true`,
  `tty: true`, `extra_hosts: ["host.docker.internal:host-gateway"]`.
- [ ] **Step 2: Verifica** — `docker compose build` → successo;
  `docker compose run --rm assistente`: stessa prova di accettazione del Task 5 Step 5 (Tokyo,
  Roma, log visibili, `/esci`). Registrare l'esito.
- [ ] **Step 3: README** — sezioni: requisiti; configurazione (`.env` da `.env.example`, id da
  `GET /v1/models` con `Invoke-RestMethod http://localhost:1234/v1/models`); avvio locale;
  avvio Docker; test automatici; prove reali (`-m reale` e prova manuale); diagnosi (LM Studio
  spento, modello errato, container che non raggiunge l'host, «Serve on Local Network» e la sua
  esposizione sulla rete locale, `LOG_LEVEL=DEBUG`). Solo comandi eseguiti nei Task 1–7.
- [ ] **Step 4: CLAUDE.md** — sostituire «Struttura, dipendenze e comandi verranno definiti…»
  con struttura reale, comando dei test e delle prove reali.
- [ ] **Step 5:** `.\.venv\Scripts\python.exe -m pytest -v` → tutta la suite PASS.
- [ ] **Step 6: Commit** (separati) → `feat(docker): avvio con Docker Compose` e
  `docs: README con configurazione, avvio, test e diagnosi`.

## Resoconto finale

Indicare, separatamente: test automatici (comando ed esito), prova reale locale, `-m reale`,
prova in Docker; cosa non è stato provato (es. Docker su Linux).
