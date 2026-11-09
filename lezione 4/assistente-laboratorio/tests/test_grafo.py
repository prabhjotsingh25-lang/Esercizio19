from finti import ModelloFinto, chiamata, orologio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from assistente.grafo import (
    MESSAGGIO_LIMITE, MESSAGGIO_RIFIUTO, MESSAGGIO_SISTEMA, costruisci_grafo, limite_ricorsione,
    scegli_dopo_router, scegli_prossimo)
from assistente.revisore import Revisione
from assistente.router import Classificazione
from assistente.sessione import Sessione


def test_instradamento():
    fine = {"messages": [AIMessage("ciao")], "passaggi": 0}
    assert scegli_prossimo(fine, 3) == "__end__"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 2}, 3) == "strumenti"
    assert scegli_prossimo({"messages": [chiamata("Asia/Tokyo", "1")], "passaggi": 3}, 3) == "limite"


def test_limite_ricorsione():
    assert limite_ricorsione(3) == 11


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
    def classifica(messaggi):
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
                             router=lambda messaggi: Classificazione(motivo="x",
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

    def rivedi(messaggi):
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
    assert limite_ricorsione(1, 2) == 11 and limite_ricorsione(3) == 11
