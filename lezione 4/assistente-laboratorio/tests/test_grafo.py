from finti import ModelloFinto, chiamata, orologio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from assistente.grafo import (
    INTESTAZIONE_RIASSUNTO, MESSAGGIO_LIMITE, MESSAGGIO_RIFIUTO, MESSAGGIO_SISTEMA,
    costruisci_grafo, limite_ricorsione,
    scegli_dopo_router, scegli_prossimo)
from assistente.preferenze import Preferenze, prompt_preferenze
from assistente.revisore import Revisione, messaggi_per_revisore
from assistente.router import Classificazione
from assistente.sessione import Sessione


def test_instradamento():
    fine = {"messages": [AIMessage("ciao")], "passaggi": 0}
    assert scegli_prossimo(fine, 3) == "__end__"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 2}, 3) == "strumenti"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 3}, 3) == "limite"


def test_limite_ricorsione():
    assert limite_ricorsione(3) == 12


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
    assert [t.tool_call_id for t in errori] == ["a", "b"]


def test_limite_ferma_il_ciclo_e_chiude_le_chiamate():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", str(i)) for i in range(10)])
    out = costruisci_grafo(m, [orologio], 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    assert out["passaggi"] == 3 and len(m.ricevuti) == 4
    assert out["messages"][-1].content == MESSAGGIO_LIMITE
    assert out["messages"][-2].content == "Non eseguito: limite di passaggi raggiunto."
    assert out["messages"][-2].tool_call_id == "3"


def test_log_della_chiamata(caplog):
    caplog.set_level("INFO")
    costruisci_grafo(ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("ok")]),
                     [orologio], 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    assert "passaggio=1" in caplog.text and "ora_corrente" in caplog.text and "Asia/Tokyo" in caplog.text


def _primo_messaggio_al_modello(strumenti) -> SystemMessage:
    m = ModelloFinto(risposte=[AIMessage("ok")])
    costruisci_grafo(m, strumenti, 3).invoke({"messages": [HumanMessage("?")], "passaggi": 0})
    return m.ricevuti[0][0]


def test_prompt_di_sistema_non_nomina_strumenti():
    assert "ora_corrente" not in MESSAGGIO_SISTEMA
    assert orologio.name not in MESSAGGIO_SISTEMA


def test_prompt_di_sistema_identico_con_strumenti_diversi():
    altro = StructuredTool.from_function(func=lambda testo: testo, name="eco",
                                         description="Restituisce il testo ricevuto.")
    primi = [_primo_messaggio_al_modello(s) for s in ([], [orologio], [orologio, altro])]
    assert all(isinstance(p, SystemMessage) for p in primi)
    assert {p.content for p in primi} == {MESSAGGIO_SISTEMA}


# --- Router (step 1): risposte del router simulate, nessun modello per la classificazione ---

def router_finto(categoria, motivo="motivo di prova", ricevuti=None):
    """Router simulato: restituisce sempre la stessa classificazione e annota cosa riceve."""
    def classifica(messaggi, riassunto=""):
        if ricevuti is not None:
            ricevuti.append(list(messaggi))
        return Classificazione(motivo=motivo, categoria=categoria)
    return classifica


def test_scegli_dopo_router():
    assert scegli_dopo_router({"categoria": "conversazione"}) == "modello"
    assert scegli_dopo_router({"categoria": "fuori_ambito"}) == "rifiuto"


def test_router_conversazione_passa_all_agente(caplog):
    caplog.set_level("INFO")
    ricevuti = []
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30.")])
    router = router_finto("conversazione", "chiede l'ora, che è nell'ambito", ricevuti)
    out = costruisci_grafo(m, [orologio], 3, router=router).invoke(
        {"messages": [HumanMessage("Che ore sono a Tokyo?")], "passaggi": 0})
    assert ricevuti[0][-1].content == "Che ore sono a Tokyo?"
    assert out["messages"][-1].content == "A Tokyo sono le 18:30."
    assert out["passaggi"] == 1 and len(m.ricevuti) == 2  # l'agente ha usato lo strumento
    assert ("router categoria=conversazione motivo=chiede l'ora, che è nell'ambito -> agente"
            in caplog.text)
    assert "agente: chiamata al modello" in caplog.text


def test_router_fuori_ambito_rifiuta_senza_chiamare_l_agente(caplog):
    caplog.set_level("DEBUG")
    m = ModelloFinto(risposte=[])  # se l'agente venisse chiamato: IndexError
    router = router_finto("fuori_ambito", "chiede una poesia")
    out = costruisci_grafo(m, [orologio], 3, router=router).invoke(
        {"messages": [HumanMessage("Scrivimi una poesia sul mare")], "passaggi": 0})
    assert [type(x) for x in out["messages"]] == [HumanMessage, AIMessage]
    assert out["messages"][-1].content == MESSAGGIO_RIFIUTO
    assert m.ricevuti == [] and out["passaggi"] == 0
    assert "router categoria=fuori_ambito motivo=chiede una poesia -> rifiuto" in caplog.text
    assert "agente:" not in caplog.text and "strumento passaggio" not in caplog.text


def test_rifiuto_resta_in_cronologia_e_il_turno_dopo_riparte_dal_router():
    categorie = iter(["fuori_ambito", "conversazione"])
    m = ModelloFinto(risposte=[AIMessage("Ciao!")])
    grafo = costruisci_grafo(m, [orologio], 3,
                             router=lambda messaggi, riassunto: Classificazione(motivo="x",
                                                                     categoria=next(categorie)))
    s = Sessione(grafo, 3)
    assert s.chiedi("Scrivimi una poesia") == MESSAGGIO_RIFIUTO
    assert s.chiedi("Ciao") == "Ciao!"
    assert [x.content for x in s.cronologia] == [
        "Scrivimi una poesia", MESSAGGIO_RIFIUTO, "Ciao", "Ciao!"]


# --- Revisore (step 2): giudizi del revisore simulati ---

def revisore_finto(*giudizi, ricevuti=None):
    """Revisore simulato: restituisce i giudizi (coerente, motivo) in ordine, poi l'ultimo."""
    elenco = list(giudizi)

    def rivedi(messaggi, riassunto="", preferenze=""):
        if ricevuti is not None:
            ricevuti.append(list(messaggi))
        coerente, motivo = elenco.pop(0) if len(elenco) > 1 else elenco[0]
        return Revisione(motivo=motivo, coerente=coerente)
    return rivedi


DUE_PARTI = "Che ore sono a Tokyo e quanto fa (17+4)*3?"


def test_risposta_parziale_rifiutata_e_poi_completa(caplog):
    caplog.set_level("INFO")
    ricevuti = []
    m = ModelloFinto(risposte=[AIMessage("A Tokyo sono le 18:30."),
                               AIMessage("A Tokyo sono le 18:30 e (17+4)*3 fa 63.")])
    revisore = revisore_finto((False, "manca il risultato di (17+4)*3"),
                              (True, "risponde a entrambe le parti"), ricevuti=ricevuti)
    out = costruisci_grafo(m, [orologio], 3, revisore=revisore).invoke(
        {"messages": [HumanMessage(DUE_PARTI)], "passaggi": 0, "revisioni": 0})
    contenuti = [x.content for x in out["messages"]]
    assert contenuti[0] == DUE_PARTI and contenuti[1] == "A Tokyo sono le 18:30."
    assert out["messages"][2].name == "revisore" and "manca il risultato" in contenuti[2]
    assert contenuti[3] == "A Tokyo sono le 18:30 e (17+4)*3 fa 63." and len(contenuti) == 4
    assert out["revisioni"] == 1 and len(ricevuti) == 2
    assert m.ricevuti[1][-1].name == "revisore"  # l'agente riprova vedendo l'indicazione
    assert ("revisore coerente=no motivo=manca il risultato di (17+4)*3 -> agente (revisione 1/1)"
            in caplog.text)
    assert "revisore coerente=sì motivo=risponde a entrambe le parti -> fine" in caplog.text


def test_risposta_coerente_approvata_al_primo_passaggio(caplog):
    caplog.set_level("INFO")
    ricevuti = []
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30.")])
    out = costruisci_grafo(m, [orologio], 3,
                           revisore=revisore_finto((True, "risponde"), ricevuti=ricevuti)).invoke(
        {"messages": [HumanMessage("Che ore sono a Tokyo?")], "passaggi": 0, "revisioni": 0})
    assert out["messages"][-1].content == "A Tokyo sono le 18:30."
    assert len(ricevuti) == 1 and out["revisioni"] == 0
    assert ricevuti[0][-1].content == "A Tokyo sono le 18:30."  # rivede la risposta finale
    assert "revisore coerente=sì" in caplog.text and "revisore coerente=no" not in caplog.text


def test_revisore_che_rifiuta_sempre_si_ferma_al_limite(caplog):
    caplog.set_level("INFO")
    ricevuti = []
    m = ModelloFinto(risposte=[AIMessage("uno"), AIMessage("due"), AIMessage("tre")])
    out = costruisci_grafo(m, [orologio], 3, max_revisioni=2,
                           revisore=revisore_finto((False, "non va"), ricevuti=ricevuti)).invoke(
        {"messages": [HumanMessage("?")], "passaggi": 0, "revisioni": 0})
    assert out["messages"][-1].content == "tre"  # al limite: l'ultima risposta
    assert len(m.ricevuti) == 3 and len(ricevuti) == 3 and out["revisioni"] == 2
    assert [x.name for x in out["messages"] if isinstance(x, HumanMessage)] == [
        None, "revisore", "revisore"]
    assert "(revisione 1/2)" in caplog.text and "(revisione 2/2)" in caplog.text
    assert "limite di 2 revisioni raggiunto: restituisco l'ultima risposta" in caplog.text
    assert any(r.levelname == "WARNING" and "limite di 2 revisioni" in r.message
               for r in caplog.records)


def test_rifiuto_del_router_e_limite_strumenti_non_sono_revisionati():
    ricevuti = []
    revisore = revisore_finto((False, "non va"), ricevuti=ricevuti)
    out = costruisci_grafo(ModelloFinto(risposte=[]), [orologio], 3, revisore=revisore,
                           router=router_finto("fuori_ambito")).invoke(
        {"messages": [HumanMessage("poesia")], "passaggi": 0, "revisioni": 0})
    assert out["messages"][-1].content == MESSAGGIO_RIFIUTO
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), chiamata("Asia/Tokyo", "2")])
    out = costruisci_grafo(m, [orologio], 1, revisore=revisore).invoke(
        {"messages": [HumanMessage("?")], "passaggi": 0, "revisioni": 0})
    assert out["messages"][-1].content == MESSAGGIO_LIMITE
    assert ricevuti == []


def test_passaggi_degli_strumenti_non_si_azzerano_al_nuovo_tentativo():
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("parziale"),
                               chiamata("Asia/Tokyo", "2"), AIMessage("completa")])
    out = costruisci_grafo(m, [orologio], 3,
                           revisore=revisore_finto((False, "parziale"), (True, "ok"))).invoke(
        {"messages": [HumanMessage("?")], "passaggi": 0, "revisioni": 0})
    assert out["messages"][-1].content == "completa" and out["passaggi"] == 2


def test_sessione_azzera_le_revisioni_a_ogni_turno():
    m = ModelloFinto(risposte=[AIMessage("a1"), AIMessage("a2"), AIMessage("b1"), AIMessage("b2")])
    giudizi = revisore_finto((False, "no"), (True, "sì"), (False, "no"), (True, "sì"))
    s = Sessione(costruisci_grafo(m, [orologio], 3, revisore=giudizi), 3)
    assert s.chiedi("a") == "a2"
    assert s.chiedi("b") == "b2"  # con revisioni non azzerate, al limite resterebbe "b1"
    assert [x.content for x in s.cronologia if x.name == "revisore"] != []  # restano in cronologia
    assert len(s.cronologia) == 8


def test_limite_di_ricorsione_basta_nel_caso_peggiore():
    # router + strumento + revisore che rifiuta sempre: 9 nodi con 1 passaggio e 2 revisioni
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("a"), AIMessage("b"),
                               AIMessage("c")])
    grafo = costruisci_grafo(m, [orologio], 1, router=router_finto("conversazione"),
                             revisore=revisore_finto((False, "no")), max_revisioni=2)
    assert Sessione(grafo, 1, max_revisioni=2).chiedi("?") == "c"
    assert limite_ricorsione(1, 2) == 12 and limite_ricorsione(3) == 12


# --- Riassunto (step 3): riassuntore simulato che annota cosa riceve ---

def riassuntore_finto(*testi, chiamate=None):
    """Restituisce i testi in ordine (l'ultimo si ripete) e annota (precedente, messaggi)."""
    elenco = list(testi)

    def riassumi(precedente, messaggi):
        if chiamate is not None:
            chiamate.append((precedente, list(messaggi)))
        return elenco.pop(0) if len(elenco) > 1 else elenco[0]
    return riassumi


def storia(turni):
    """`turni` turni di domanda e risposta, più la domanda nuova."""
    messaggi = []
    for i in range(turni):
        messaggi += [HumanMessage(f"domanda {i}"), AIMessage(f"risposta {i}")]
    return [*messaggi, HumanMessage("nuova")]


def test_sotto_la_soglia_nessuna_chiamata_al_riassuntore(caplog):
    caplog.set_level("INFO")
    chiamate = []
    m = ModelloFinto(risposte=[AIMessage("ok")])
    out = costruisci_grafo(m, [orologio], 3, riassuntore=riassuntore_finto("R", chiamate=chiamate),
                           soglia_riassunto=5, messaggi_recenti=2).invoke(
        {"messages": storia(2), "passaggi": 0})  # 5 messaggi: non oltre la soglia
    assert chiamate == [] and len(out["messages"]) == 6
    assert out.get("riassunto", "") == ""
    assert "riassunto: 5 messaggi, sotto la soglia di 5: nessuna chiamata" in caplog.text


def test_oltre_la_soglia_i_vecchi_diventano_riassunto(caplog):
    caplog.set_level("INFO")
    chiamate = []
    m = ModelloFinto(risposte=[AIMessage("ok")])
    out = costruisci_grafo(m, [orologio], 3,
                           riassuntore=riassuntore_finto("NUOVO", chiamate=chiamate),
                           soglia_riassunto=5, messaggi_recenti=2).invoke(
        {"messages": storia(3), "passaggi": 0, "riassunto": "VECCHIO"})  # 7 messaggi
    assert [x.content for x in out["messages"]] == ["domanda 2", "risposta 2", "nuova", "ok"]
    assert out["riassunto"] == "NUOVO"
    precedente, vecchi = chiamate[0]
    assert precedente == "VECCHIO"
    assert [x.content for x in vecchi] == ["domanda 0", "risposta 0", "domanda 1", "risposta 1"]
    assert "riassunto: 7 messaggi, soglia 5 -> riassunti 4, tenuti 3" in caplog.text
    sistema = m.ricevuti[0][0]
    assert sistema.content.startswith(MESSAGGIO_SISTEMA)
    assert sistema.content.endswith(f"{INTESTAZIONE_RIASSUNTO}\nNUOVO")
    assert "informazioni che l'utente ti ha dato" in INTESTAZIONE_RIASSUNTO
    assert [x.content for x in m.ricevuti[0][1:]] == ["domanda 2", "risposta 2", "nuova"]


def test_il_router_riceve_il_riassunto():
    ricevuti = []

    def router(messaggi, riassunto):
        ricevuti.append(riassunto)
        return Classificazione(motivo="x", categoria="conversazione")
    costruisci_grafo(ModelloFinto(risposte=[AIMessage("ok")]), [orologio], 3, router=router,
                     riassuntore=riassuntore_finto("NUOVO"), soglia_riassunto=5,
                     messaggi_recenti=2).invoke({"messages": storia(3), "passaggi": 0})
    assert ricevuti == ["NUOVO"]


def test_riassunto_vuoto_non_toglie_messaggi(caplog):
    m = ModelloFinto(risposte=[AIMessage("ok")])
    out = costruisci_grafo(m, [orologio], 3, riassuntore=riassuntore_finto("  "),
                           soglia_riassunto=5, messaggi_recenti=2).invoke(
        {"messages": storia(3), "passaggi": 0, "riassunto": "VECCHIO"})
    assert len(out["messages"]) == 8 and out["riassunto"] == "VECCHIO"
    assert "riassunto vuoto" in caplog.text
    assert [r.levelname for r in caplog.records if "riassunto vuoto" in r.message] == ["WARNING"]


def test_un_solo_turno_lungo_non_si_riassume(caplog):
    caplog.set_level("INFO")
    chiamate = []
    # 3 messaggi oltre la soglia di 2, ma tutti nello stesso turno: il taglio cade all'inizio
    out = costruisci_grafo(ModelloFinto(risposte=[AIMessage("ok")]), [orologio], 3,
                           riassuntore=riassuntore_finto("R", chiamate=chiamate),
                           soglia_riassunto=2, messaggi_recenti=1).invoke(
        {"messages": [HumanMessage("a"), AIMessage("b"), AIMessage("c")], "passaggi": 0})
    assert chiamate == [] and len(out["messages"]) == 4
    assert "niente da riassumere" in caplog.text


def test_sessione_conserva_e_aggiorna_il_riassunto():
    chiamate = []
    m = ModelloFinto(risposte=[AIMessage(f"risposta {i}") for i in range(5)])
    s = Sessione(costruisci_grafo(m, [orologio], 3,
                                  riassuntore=riassuntore_finto("R1", "R2", chiamate=chiamate),
                                  soglia_riassunto=4, messaggi_recenti=2), 3)
    for i in range(3):
        s.chiedi(f"domanda {i}")
    assert s.riassunto == "R1" and chiamate[0][0] == ""  # turno 3: 5 messaggi -> riassunto
    assert [x.content for x in s.cronologia] == ["domanda 1", "risposta 1", "domanda 2",
                                                 "risposta 2"]
    s.chiedi("domanda 3")  # 5 messaggi: il nuovo riassunto riceve il precedente
    assert s.riassunto == "R2" and chiamate[1][0] == "R1"
    s.nuova()
    assert s.riassunto == "" and s.cronologia == []


# --- Fix revisore: il revisore simulato giudica dal prompt vero (messaggi_per_revisore) ---

def revisore_dal_prompt(dato, ricevuti=None):
    """Boccia la risposta se `dato` non compare nel prompt che il revisore vero riceverebbe."""
    def rivedi(messaggi, riassunto="", preferenze=""):
        testo = messaggi_per_revisore(messaggi, riassunto, preferenze)[-1].content
        if ricevuti is not None:
            ricevuti.append(testo)
        if dato in testo:
            return Revisione(motivo="dato presente", coerente=True)
        return Revisione(motivo="non hai accesso a questo dato", coerente=False)
    return rivedi


def test_risposta_basata_su_strumento_non_bocciata(caplog):
    caplog.set_level("INFO")
    m = ModelloFinto(risposte=[chiamata("Asia/Tokyo", "1"), AIMessage("A Tokyo sono le 18:30.")])
    out = costruisci_grafo(m, [orologio], 3,
                           revisore=revisore_dal_prompt("2026-10-26T18:30:05+09:00")).invoke(
        {"messages": [HumanMessage("Che ore sono a Tokyo?")], "passaggi": 0, "revisioni": 0})
    assert out["messages"][-1].content == "A Tokyo sono le 18:30." and out["revisioni"] == 0
    assert "revisore coerente=sì" in caplog.text and "coerente=no" not in caplog.text


def test_nome_dal_riassunto_non_bocciato_dopo_la_compressione(caplog):
    caplog.set_level("INFO")
    ricevuti = []
    m = ModelloFinto(risposte=[AIMessage("Ti chiami Prabhjot.")])
    out = costruisci_grafo(m, [orologio], 3,
                           revisore=revisore_dal_prompt("si chiama Prabhjot", ricevuti),
                           riassuntore=riassuntore_finto("Utente: si chiama Prabhjot."),
                           soglia_riassunto=5, messaggi_recenti=2).invoke(
        {"messages": [*storia(3)[:-1], HumanMessage("Come mi chiamo?")], "passaggi": 0,
         "revisioni": 0})
    assert "riassunti 4" in caplog.text  # la compressione è avvenuta
    assert out["messages"][-1].content == "Ti chiami Prabhjot." and out["revisioni"] == 0
    assert ricevuti[0].startswith("Conversazione precedente:\nRiassunto: Utente: si chiama")


# --- Step 4: preferenze dell'utente in cima al prompt dell'agente e al revisore ---

NEW_YORK = Preferenze(lingua="en", fuso_orario="America/New_York")


class ModelloCheRegistraBind(ModelloFinto):
    legati: list = []

    def bind_tools(self, tools, **kwargs):
        self.legati = list(tools)
        return self


def test_preferenze_in_cima_al_messaggio_di_sistema():
    m = ModelloCheRegistraBind(risposte=[AIMessage("ok")])
    costruisci_grafo(m, [orologio], 3, riassuntore=riassuntore_finto("RIASSUNTO"),
                     soglia_riassunto=5, messaggi_recenti=2).invoke(
        {"messages": storia(3), "passaggi": 0, "preferenze": NEW_YORK})
    sistema = m.ricevuti[0][0].content
    assert sistema.startswith(prompt_preferenze(NEW_YORK) + "\n\n" + MESSAGGIO_SISTEMA)
    assert sistema.endswith("RIASSUNTO")
    assert [s.name for s in m.legati] == ["ora_corrente"]  # la resource non è un tool


def test_senza_preferenze_messaggio_di_sistema_invariato():
    m = ModelloFinto(risposte=[AIMessage("ok")])
    costruisci_grafo(m, [orologio], 3).invoke(
        {"messages": [HumanMessage("?")], "passaggi": 0, "preferenze": None})
    assert m.ricevuti[0][0].content == MESSAGGIO_SISTEMA


def test_il_revisore_vede_le_preferenze_il_router_no():
    ricevuti_router = []
    m = ModelloFinto(risposte=[chiamata("America/New_York", "1"),
                               AIMessage("A New York sono le 05:30.")])
    out = costruisci_grafo(m, [orologio], 3,
                           router=router_finto("conversazione", ricevuti=ricevuti_router),
                           revisore=revisore_dal_prompt("Fuso orario predefinito: America/New_York")
                           ).invoke({"messages": [HumanMessage("Che ore sono?")], "passaggi": 0,
                                     "revisioni": 0, "preferenze": NEW_YORK})
    assert out["revisioni"] == 0 and out["messages"][-1].content == "A New York sono le 05:30."
    assert len(ricevuti_router) == 1  # il router riceve solo messaggi e riassunto


def test_sessione_legge_le_preferenze_una_volta_e_le_rilegge_con_nuova(caplog):
    letture = []

    def leggi():
        letture.append(1)
        return NEW_YORK if len(letture) == 1 else Preferenze(lingua="fr")
    m = ModelloFinto(risposte=[AIMessage("a"), AIMessage("b"), AIMessage("c")])
    s = Sessione(costruisci_grafo(m, [orologio], 3), 3, leggi_preferenze=leggi)
    assert len(letture) == 1 and s.preferenze == NEW_YORK  # prima della prima domanda
    s.chiedi("uno")
    s.chiedi("due")
    assert len(letture) == 1  # non a ogni turno
    assert all(r[0].content.startswith(prompt_preferenze(NEW_YORK)) for r in m.ricevuti)
    s.nuova()
    assert len(letture) == 2 and s.preferenze.lingua == "fr"
    s.chiedi("tre")
    assert m.ricevuti[-1][0].content.startswith(prompt_preferenze(Preferenze(lingua="fr")))


def test_sessione_senza_lettore_non_ha_preferenze():
    m = ModelloFinto(risposte=[AIMessage("a")])
    s = Sessione(costruisci_grafo(m, [orologio], 3), 3)
    s.chiedi("uno")
    assert s.preferenze is None and m.ricevuti[0][0].content == MESSAGGIO_SISTEMA
