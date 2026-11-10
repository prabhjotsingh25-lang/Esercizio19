"""Prove reali con LM Studio attivo: si attivano esplicitamente con `pytest -m reale`."""
import re

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import MESSAGGIO_RIFIUTO, costruisci_grafo
from assistente.modello import crea_modello
from assistente.preferenze import PREDEFINITE
from assistente.revisore import Revisione, crea_revisore
from assistente.riassunto import crea_riassuntore
from assistente.router import crea_router
from assistente.sessione import Sessione
from assistente.varianti import lettore_preferenze, strumenti_per_variante

pytestmark = pytest.mark.reale

_ORA = re.compile(r"T(\d{2}:\d{2}):\d{2}")


@pytest.fixture
def file_preferenze(tmp_path, monkeypatch):
    """File delle preferenze temporaneo, con i valori predefiniti; le prove possono riscriverlo
    e chiamare sessione.nuova() per farlo rileggere. Nella variante mcp lo legge il server dal
    proprio PREFERENZE_FILE (come per NOTE_DB)."""
    file = tmp_path / "preferenze.json"
    file.write_text(PREDEFINITE.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("PREFERENZE_FILE", str(file))
    return file


@pytest.fixture
def sessione(tmp_path, monkeypatch, file_preferenze):
    load_dotenv(".env", override=False)
    # Variante locale: note in un database temporaneo. Nelle varianti http e mcp le note
    # vanno nel database del servizio (NOTE_DB impostata all'avvio del servizio).
    monkeypatch.setenv("NOTE_DB", str(tmp_path / "note.sqlite"))
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        pytest.skip(f"Configurazione mancante: {errore}")
    strumenti = strumenti_per_variante(config)
    modello = crea_modello(config)
    grafo = costruisci_grafo(modello, strumenti, config.max_passaggi,
                             router=crea_router(modello, config.ambito),
                             revisore=crea_revisore(modello),
                             max_revisioni=config.max_revisioni,
                             riassuntore=crea_riassuntore(modello),
                             soglia_riassunto=config.soglia_riassunto,
                             messaggi_recenti=config.messaggi_recenti)
    return Sessione(grafo, config.max_passaggi, config.max_revisioni,
                    leggi_preferenze=lettore_preferenze(config))


def _strumenti_del_turno(sessione: Sessione) -> list[str]:
    """Risultati dei ToolMessage aggiunti dopo l'ultima domanda dell'utente."""
    cronologia = sessione.cronologia
    ultima = max(i for i, m in enumerate(cronologia) if isinstance(m, HumanMessage))
    return [m.content for m in cronologia[ultima + 1:] if isinstance(m, ToolMessage)]


def test_tokyo_poi_roma(sessione):
    risposta = sessione.chiedi("Che ore sono a Tokyo?")
    risultati = _strumenti_del_turno(sessione)
    tokyo = [r for r in risultati if r.endswith("(Asia/Tokyo)")]
    assert tokyo, f"nessun ToolMessage per Asia/Tokyo: {risultati}"
    ora = _ORA.search(tokyo[-1])
    assert ora, f"orario non riconoscibile nel risultato: {tokyo[-1]}"
    assert ora.group(1) in risposta, f"{ora.group(1)} assente nella risposta: {risposta!r}"

    sessione.chiedi("E a Roma?")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.endswith("(Europe/Rome)") for r in risultati), (
        f"nessun ToolMessage per Europe/Rome nel secondo turno: {risultati}")


def test_ora_senza_luogo_usa_il_fuso_predefinito(sessione, file_preferenze, caplog):
    # Sostituisce test_ora_senza_luogo: dallo step 4 c'è sempre un fuso orario predefinito
    # (dalle preferenze o dai valori predefiniti), quindi l'agente non chiede più il luogo.
    caplog.set_level("INFO", logger="assistente")
    file_preferenze.write_text('{"fuso_orario": "America/New_York"}', encoding="utf-8")
    sessione.nuova()  # rilegge le preferenze
    risposta = sessione.chiedi("Che ore sono?")
    risultati = _strumenti_del_turno(sessione)
    print(f"Tu> Che ore sono?\nAssistente> {risposta}\nstrumenti: {risultati}")
    new_york = [r for r in risultati if r.endswith("(America/New_York)")]
    assert new_york, f"nessun ToolMessage per America/New_York: {risultati}"
    ora = _ORA.search(new_york[-1])
    assert ora and ora.group(1) in risposta, f"ora assente nella risposta: {risposta!r}"


def test_conversione_km_in_metri(sessione):
    risposta = sessione.chiedi("Quanti metri sono 1,5 km?")
    risultati = _strumenti_del_turno(sessione)
    assert "1.5 km = 1500 m" in risultati, f"conversione non eseguita come atteso: {risultati}"
    assert "1500" in risposta.replace(".", "").replace(" ", ""), f"1500 assente: {risposta!r}"


def test_conversione_incompatibile_non_inventa(sessione):
    sessione.chiedi("Converti 3 kg in metri.")
    risultati = _strumenti_del_turno(sessione)
    assert all(r.startswith("Errore:") for r in risultati), f"risultato inventato: {risultati}"


def test_calcolo_con_la_calcolatrice(sessione):
    risposta = sessione.chiedi("Quanto fa (17 + 4) * 3?")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.endswith("= 63") for r in risultati), f"calcolatrice non usata come atteso: {risultati}"
    assert "63" in risposta, f"63 assente nella risposta: {risposta!r}"


def test_giorni_lavorativi(sessione):
    risposta = sessione.chiedi("Quanti giorni lavorativi ci sono dal 2026-12-21 al 2026-12-31?")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.startswith("Dal 2026-12-21 al 2026-12-31: 7 giorni lavorativi") for r in risultati), (
        f"giorni_scadenze non usato come atteso: {risultati}")
    assert "7" in risposta, f"7 assente nella risposta: {risposta!r}"


def test_catalogo_articolo_presente(sessione):
    risposta = sessione.chiedi("Avete un multimetro in laboratorio? Dove si trova?")
    risultati = _strumenti_del_turno(sessione)
    assert any("MUL-01" in r for r in risultati), f"catalogo_locale non usato come atteso: {risultati}"
    assert "Armadio A" in risposta, f"ubicazione assente nella risposta: {risposta!r}"


def test_catalogo_articolo_assente(sessione):
    sessione.chiedi("Avete un microscopio elettronico in laboratorio?")
    risultati = _strumenti_del_turno(sessione)
    assert risultati, "il modello ha risposto senza consultare il catalogo"
    assert all(r.startswith(("Nessun articolo", "Errore:")) for r in risultati), (
        f"risultato inatteso per un articolo assente: {risultati}")


def test_note_salvataggio(sessione):
    sessione.chiedi("Ricordami di comprare i fusibili da 5 A.")
    risultati = _strumenti_del_turno(sessione)
    assert any(r.startswith("Nota ") and "salvata" in r and "fusibili" in r for r in risultati), (
        f"nota non salvata: {risultati}")


def test_note_eliminazione_chiede_conferma(sessione):
    sessione.chiedi("Salva una nota con questo testo: verificare cancellazione 42.")
    salvate = [r for r in _strumenti_del_turno(sessione) if re.match(r"Nota \d+ salvata", r)]
    assert salvate, "nota di prova non salvata"
    id_nota = re.match(r"Nota (\d+) salvata", salvate[0]).group(1)

    sessione.chiedi(f"Cancella la nota {id_nota}.")
    turno = _strumenti_del_turno(sessione)
    assert not any(r.startswith(f"Nota {id_nota} eliminata") for r in turno), (
        f"nota eliminata senza la conferma dell'utente: {turno}")
    assert any(f"Stai per eliminare la nota {id_nota}" in r for r in turno), (
        f"richiesta di conferma assente: {turno}")

    sessione.chiedi("Sì, confermo.")
    assert any(r.startswith(f"Nota {id_nota} eliminata") for r in _strumenti_del_turno(sessione)), (
        "nota non eliminata dopo la conferma")


def test_meteo_domani(sessione):
    # Richiede internet (Open-Meteo). "domani" verifica che il modello usi la riga giusta.
    risposta = sessione.chiedi("Che tempo farà domani a Roma?")
    risultati = [r for r in _strumenti_del_turno(sessione) if r.startswith("Meteo per Roma")]
    assert risultati, f"meteo_api non usato come atteso: {_strumenti_del_turno(sessione)}"
    domani = re.search(r"\(domani\): min (-?\d+) °C, max (-?\d+) °C", risultati[0])
    assert domani.group(2) in risposta, (
        f"massima di domani ({domani.group(2)} °C) assente nella risposta: {risposta!r}")


def test_meteo_luogo_inesistente_non_inventa(sessione):
    # Un nome plausibile ma inesistente: con una parola senza senso («Zzyzxqwvk») il modello
    # chiede subito chiarimenti senza chiamare lo strumento, e l'errore non viene provato.
    risposta = sessione.chiedi("Che tempo fa a Montefracassone?")
    risultati = _strumenti_del_turno(sessione)
    assert risultati, "il modello ha risposto senza consultare il servizio meteo"
    assert all(r.startswith("Errore:") for r in risultati), f"risultato inatteso: {risultati}"
    assert "°" not in risposta, f"temperatura inventata nella risposta: {risposta!r}"


def test_router_domanda_in_ambito_passa_all_agente(sessione, caplog):
    caplog.set_level("INFO", logger="assistente")
    sessione.chiedi("Che ore sono a Tokyo?")
    assert "router categoria=conversazione" in caplog.text, caplog.text
    assert "agente: chiamata al modello" in caplog.text


def test_router_domanda_fuori_ambito_rifiutata(sessione, caplog):
    caplog.set_level("INFO", logger="assistente")
    risposta = sessione.chiedi("Scrivimi una poesia sul mare.")
    assert "router categoria=fuori_ambito" in caplog.text, caplog.text
    assert risposta == MESSAGGIO_RIFIUTO
    assert "agente:" not in caplog.text, "il nodo agente è stato eseguito"


DUE_PARTI = "Che ore sono a Tokyo e quanto fa (17 + 4) * 3?"


@pytest.fixture
def config_reale():
    load_dotenv(".env", override=False)
    try:
        return carica_configurazione()
    except ErroreConfigurazione as errore:
        pytest.skip(f"Configurazione mancante: {errore}")


def test_revisore_rifiuta_una_risposta_parziale(config_reale, caplog):
    revisore = crea_revisore(crea_modello(config_reale))
    esito = revisore([HumanMessage(DUE_PARTI), AIMessage("A Tokyo sono le 23:15.")])
    print(f"revisore: coerente={esito.coerente} motivo={esito.motivo}")
    assert esito.coerente is False, esito.motivo
    assert "output del revisore non valido" not in caplog.text


def test_revisore_approva_una_risposta_completa(config_reale, caplog):
    revisore = crea_revisore(crea_modello(config_reale))
    esito = revisore([HumanMessage(DUE_PARTI),
                      AIMessage("A Tokyo sono le 23:15 e (17 + 4) * 3 fa 63.")])
    print(f"revisore: coerente={esito.coerente} motivo={esito.motivo}")
    assert esito.coerente is True, esito.motivo
    assert "output del revisore non valido" not in caplog.text


def test_agente_riprova_dopo_l_indicazione_del_revisore(config_reale, caplog):
    # Revisore simulato che rifiuta la prima risposta: verifica che il modello vero accetti
    # l'indicazione come messaggio utente con name="revisore" e riscriva la risposta.
    caplog.set_level("INFO", logger="assistente")
    giudizi = [Revisione(motivo="La risposta non indica il risultato di (17 + 4) * 3.",
                         coerente=False),
               Revisione(motivo="ok", coerente=True)]
    modello = crea_modello(config_reale)
    grafo = costruisci_grafo(modello, strumenti_per_variante(config_reale),
                             config_reale.max_passaggi, revisore=lambda m, r="", p="": giudizi.pop(0))
    sessione = Sessione(grafo, config_reale.max_passaggi, 1)
    risposta = sessione.chiedi(DUE_PARTI)
    nomi = [m.name for m in sessione.cronologia if isinstance(m, HumanMessage)]
    assert nomi == [None, "revisore"], nomi
    assert caplog.text.count("agente: chiamata al modello") >= 2
    assert "63" in risposta, f"63 assente nella nuova risposta: {risposta!r}"


def test_domanda_in_due_parti(sessione, caplog):
    caplog.set_level("INFO", logger="assistente")
    risposta = sessione.chiedi(DUE_PARTI)
    assert "revisore coerente=" in caplog.text, caplog.text
    assert "63" in risposta, f"63 assente nella risposta: {risposta!r}"


# --- Riassunto (step 3): soglia bassa per comprimere già dopo pochi turni ---

@pytest.fixture
def sessione_soglia_bassa(sessione, monkeypatch):
    """Sessione completa con SOGLIA_RIASSUNTO=6 e MESSAGGI_RECENTI=2."""
    monkeypatch.setenv("SOGLIA_RIASSUNTO", "6")
    monkeypatch.setenv("MESSAGGI_RECENTI", "2")
    config = carica_configurazione()
    modello = crea_modello(config)
    grafo = costruisci_grafo(modello, strumenti_per_variante(config), config.max_passaggi,
                             router=crea_router(modello, config.ambito),
                             revisore=crea_revisore(modello),
                             max_revisioni=config.max_revisioni,
                             riassuntore=crea_riassuntore(modello),
                             soglia_riassunto=config.soglia_riassunto,
                             messaggi_recenti=config.messaggi_recenti)
    return Sessione(grafo, config.max_passaggi, config.max_revisioni)


_COMPRESSIONE = re.compile(r"riassunto: (\d+) messaggi, soglia (\d+) -> riassunti (\d+), tenuti (\d+)")


def test_riassunto_sotto_soglia_nessuna_chiamata(sessione_soglia_bassa, caplog):
    caplog.set_level("INFO", logger="assistente")
    risposta = sessione_soglia_bassa.chiedi("Ciao, mi chiamo Prabhjot.")
    print(f"turno 1: {risposta}")
    assert "riassunto: 1 messaggi, sotto la soglia di 6: nessuna chiamata" in caplog.text
    assert not _COMPRESSIONE.search(caplog.text)
    assert sessione_soglia_bassa.riassunto == ""


def test_riassunto_conserva_il_nome_dopo_la_compressione(sessione_soglia_bassa, caplog):
    caplog.set_level("INFO", logger="assistente")
    s = sessione_soglia_bassa
    # La sequenza che prima del fix del revisore falliva: al turno di Tokyo il revisore, che non
    # vedeva i risultati degli strumenti, bocciava l'orario giusto.
    domande = ["Ciao, mi chiamo Prabhjot.", "Quanto fa 12 * 7?", "Converti 3 km in metri.",
               "Che ore sono a Tokyo?"]
    for i, domanda in enumerate(domande, 1):
        inizio = len(caplog.records)
        risposta = s.chiedi(domanda)
        print(f"turno {i}: Tu> {domanda}\n         Assistente> {risposta}")
        revisioni = [r.getMessage() for r in caplog.records[inizio:]
                     if r.getMessage().startswith("revisore ")]
        print(*(f"         {r}" for r in revisioni), sep="\n")
    turno_tokyo = [r for r in revisioni if "coerente=no" in r]
    assert not turno_tokyo, f"il revisore ha bocciato la risposta su Tokyo: {turno_tokyo}"
    compressioni = _COMPRESSIONE.findall(caplog.text)
    print("log:", *(r.getMessage() for r in caplog.records
                    if r.getMessage().startswith("riassunto:")), sep="\n  ")
    print(f"riassunto: {s.riassunto}")
    assert compressioni, "nessuna compressione nei primi turni"
    assert all(m.content != "Ciao, mi chiamo Prabhjot." for m in s.cronologia), (
        "il turno con il nome è ancora in cronologia: non è stato riassunto")
    inizio = len(caplog.records)
    risposta = s.chiedi("Come mi chiamo?")
    print(f"dopo la compressione: Tu> Come mi chiamo?\n         Assistente> {risposta}")
    print(*(f"         {r.getMessage()}" for r in caplog.records[inizio:]
            if r.getMessage().startswith("revisore ")), sep="\n")
    print(f"riassunto visto dall'agente nell'ultimo turno: {s.riassunto}")
    print("messaggi tenuti:", *(f"{type(m).__name__}({m.name or ''}): {m.content!r}"
                                for m in s.cronologia), sep="\n  ")
    assert "router categoria=fuori_ambito" not in caplog.text
    assert "prabhjot" in risposta.lower(), f"nome assente nella risposta: {risposta!r}"


# --- Fix revisore: revisore vero su messaggi preparati (prove veloci) ---

def test_revisore_approva_l_ora_presa_dallo_strumento(config_reale, caplog):
    revisore = crea_revisore(crea_modello(config_reale))
    esito = revisore([
        HumanMessage("Che ore sono a Tokyo?"),
        AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {"fuso_orario": "Asia/Tokyo"},
                                   "id": "t1"}]),
        ToolMessage("2026-11-10T18:17:07+09:00 (Asia/Tokyo)", tool_call_id="t1"),
        AIMessage("Attualmente a Tokyo sono le ore 18:17 del 10 novembre 2026.")])
    print(f"revisore: coerente={esito.coerente} motivo={esito.motivo}")
    assert esito.coerente is True, esito.motivo
    assert "output del revisore non valido" not in caplog.text


def test_revisore_approva_il_nome_preso_dal_riassunto(config_reale, caplog):
    revisore = crea_revisore(crea_modello(config_reale))
    esito = revisore([HumanMessage("Quanto fa 15 + 27?"), AIMessage("15 + 27 fa 42."),
                      HumanMessage("Come mi chiamo?"), AIMessage("Ti chiami Prabhjot.")],
                     "Utente: si chiama Prabhjot.\nL'utente ha chiesto alcuni calcoli.")
    print(f"revisore: coerente={esito.coerente} motivo={esito.motivo}")
    assert esito.coerente is True, esito.motivo
    assert "output del revisore non valido" not in caplog.text


# --- Step 4: preferenze dell'utente ---

_INGLESE = {"the", "is", "of", "result", "equals", "multiplied", "by"}
_ITALIANO = {"il", "è", "di", "risultato", "fa", "per", "moltiplicato"}


def _parole(testo: str, lingua: set[str]) -> int:
    return sum(1 for p in re.findall(r"\w+", testo.lower()) if p in lingua)


def test_lingua_e_stile_valgono_dalla_sessione_successiva(sessione, file_preferenze, caplog):
    caplog.set_level("INFO", logger="assistente")
    domanda = "Quanto fa 12 * 7?"
    prima = sessione.chiedi(domanda)  # predefinite: italiano, sintetico
    file_preferenze.write_text('{"lingua": "en", "stile": "dettagliato"}', encoding="utf-8")
    sessione.nuova()  # /nuova: nuova sessione, preferenze rilette
    dopo = sessione.chiedi(domanda)
    letture = [r.getMessage() for r in caplog.records if r.getMessage().startswith("preferenze:")]
    print("letture:", *letture, sep="\n  ")
    print(f"it/sintetico ({len(prima)} caratteri): {prima}")
    print(f"en/dettagliato ({len(dopo)} caratteri): {dopo}")
    assert _parole(prima, _ITALIANO) > _parole(prima, _INGLESE), prima
    assert _parole(dopo, _INGLESE) > _parole(dopo, _ITALIANO), dopo
    assert "84" in prima and "84" in dopo
    assert len(dopo) > len(prima), "lo stile dettagliato non ha allungato la risposta"


# --- Step 5: prompt (/prompt) che passano da router, agente e revisore ---

def test_prompt_spiega_passa_il_router_e_risponde(sessione, caplog):
    from assistente.varianti import fonte_prompt
    caplog.set_level("INFO", logger="assistente")
    fonte = fonte_prompt(carica_configurazione())
    messaggi = fonte.ottieni("spiega", {"argomento": "Model Context Protocol", "livello": "base"})
    risposta = sessione.chiedi_messaggi(messaggi)
    print(f"Prompt> {messaggi[0].content}\nAssistente> {risposta}")
    assert "router categoria=conversazione" in caplog.text, caplog.text
    assert "protocol" in risposta.lower(), risposta


def test_prompt_riassumi_conversazione_riassume_i_turni(sessione, caplog):
    from assistente.varianti import fonte_prompt
    caplog.set_level("INFO", logger="assistente")
    sessione.chiedi("Quanto fa 12 * 7?")
    sessione.chiedi("Converti 3 km in metri.")
    inizio = len(caplog.records)
    messaggi = fonte_prompt(carica_configurazione()).ottieni(
        "riassumi_conversazione", {"stile": "sintetico"})
    risposta = sessione.chiedi_messaggi(messaggi)
    turno = [r.getMessage() for r in caplog.records[inizio:]]
    print(f"Prompt> {messaggi[0].content}\nAssistente> {risposta}")
    print(*(f"  {r}" for r in turno if r.startswith(("router", "revisore"))), sep="\n")
    assert any(r.startswith("router categoria=conversazione") for r in turno), turno
    assert not any("revisore coerente=no" in r for r in turno), turno
    assert "84" in risposta and "3000" in risposta.replace(".", ""), risposta
